# 文件：packages/coding-agent/src/modes/interactive/interactive-mode.ts

## 一句话定位

`interactive-mode.ts` 是 `packages/coding-agent` 的交互式 TUI 入口：它把 `AgentSessionRuntime` 提供的会话能力包装成终端界面，负责渲染聊天、编辑器、状态栏、选择器、快捷键、扩展 UI，并把用户输入、slash command、bash 命令、模型切换、压缩、重试、退出等交互转交给会话层执行。

## 它暴露/定义了什么

文件核心导出是 `InteractiveMode` 类和 `InteractiveModeOptions` 配置接口，另有少量可复用工具函数，例如 `formatResumeCommand()` 和 `isApiKeyLoginProvider()`。

`InteractiveModeOptions` 描述启动交互模式时的外部输入：迁移认证提示、模型恢复失败提示、启动后自动信任的 cwd、初始文本消息、初始图片、多条启动消息，以及是否强制 verbose startup。

`InteractiveMode` 内部维护大量 UI 状态：`TUI`、聊天容器、待发送消息容器、状态容器、编辑器、footer、keybindings、autocomplete provider、streaming assistant message、pending tool components、bash 执行组件、auto-compaction loader、retry loader、extension widgets、custom header/footer 等。它不是纯渲染组件，而是一个“交互模式协调器”。

## 谁调用它

根据当前片段推断，`InteractiveMode` 由 coding-agent 的主入口或 mode 分发层在进入交互式运行模式时实例化。依据是文件导出的类名、构造函数接收 `AgentSessionRuntime`，以及测试 fixture 中出现过 `main-new.ts runInteractiveMode` 迁移到 `InteractiveMode` 的设计记录。实际调用点应在 `packages/coding-agent/src/main*.ts` 或 `packages/coding-agent/src/modes/index.ts` 附近；本次可见的调用检索输出被历史 fixture 内容干扰，未完整确认最终源码调用链。

典型调用关系应是：CLI 解析参数、构造 `AgentSessionRuntime` 和 `AgentSession`，然后创建 `new InteractiveMode(runtimeHost, options)`，再启动初始化和事件循环。

## 它调用谁

向下主要调用四类对象。

第一类是会话与业务层：`AgentSessionRuntime`、`AgentSession`、`SessionManager`、`AgentSessionEvent`。它通过 `runtimeHost.session` 取得当前 `AgentSession`，再使用 session/agent/sessionManager/settingsManager 完成 prompt、abort、session 切换、消息保存、自动压缩、模型与 thinking level 变化等业务。

第二类是 TUI 基础设施：`@earendil-works/pi-tui` 的 `TUI`、`ProcessTerminal`、`Container`、`Text`、`Markdown`、`Loader`、`CombinedAutocompleteProvider`、`matchesKey`、`setKeybindings` 等。文件自身负责把这些基础组件组装成完整终端应用。

第三类是交互模式组件：`AssistantMessageComponent`、`UserMessageComponent`、`ToolExecutionComponent`、`BashExecutionComponent`、`CustomEditor`、`FooterComponent`、`ModelSelectorComponent`、`SessionSelectorComponent`、`TrustSelectorComponent`、`OAuthSelectorComponent`、`ExtensionSelectorComponent` 等。这些组件承担具体视图或弹层渲染，`InteractiveMode` 负责创建、插入容器、更新状态和清理。

第四类是横切工具：认证路径、配置目录、版本检查、剪贴板、图片剪贴板、主题、扩展、项目信任、HTTP dispatcher、package manager、changelog 解析、shell 子进程清理等。说明此文件处在 CLI 交互入口，天然连接许多子系统。

## 核心流程

启动时，构造函数先绑定 `runtimeHost` 的 session invalidation/rebind 回调，创建 `TUI(new ProcessTerminal())`，初始化 header/chat/pending/status/editor/widget/footer 等容器，创建 `KeybindingsManager` 并注入 TUI 全局 keybindings，然后读取 settings 初始化 editor padding、autocomplete 数量、硬件光标、窗口缩小时清屏、隐藏 thinking block、主题注册与主题实例。

初始化阶段通常会继续装配主布局、注册键盘处理、创建 autocomplete provider、订阅 `AgentSession` 事件、展示启动 notice、changelog、认证或模型恢复提示，并发送 `initialMessage`、`initialImages`、`initialMessages`。从字段和导入可以看出，它还会处理版本检查、项目 trust、OAuth/API key 登录、扩展 UI 注入和资源诊断。

运行中，用户在 `CustomEditor` 输入文本。普通文本会进入 session prompt 流程；以 `!` 开头的输入进入 bash mode，渲染 `BashExecutionComponent` 并交给 session/runtime 执行；以 `/` 开头的输入走 built-in slash commands 或 extension commands。agent 流式输出时，文件维护 `streamingComponent` 和 `streamingMessage`，增量更新 assistant message；工具调用时，用 `pendingTools` 以 toolCallId 关联 `ToolExecutionComponent`；压缩、重试、取消则通过 loader、countdown 和 Escape handler 表达状态。

退出或重绑会话时，它需要清理 extension UI、terminal input unsubscribers、signal handlers、theme watcher、detached child processes，并确保 TUI 恢复终端状态。

## 关键函数的高层作用

`constructor()` 是依赖注入和 UI 骨架搭建点，把 runtime/session/settings/keybindings/theme/editor/footer 串起来，是理解全文件状态来源的入口。

`formatResumeCommand()` 根据 `SessionManager` 当前持久化状态生成恢复命令；它会检查 stdout 是否是 TTY、session 是否已持久化、session file 是否存在，并在非默认 session dir 时追加 `--session-dir`。

`isApiKeyLoginProvider()` 判断某 provider 在登录界面应走 API key 还是 OAuth：内置展示名优先视为 API key provider，已知 built-in provider 默认不是 API key，非 OAuth 的第三方 provider 视为 API key。

`createBaseAutocompleteProvider()` 组装内置 slash command 自动补全，并为 `/model` 等命令提供基于当前 scoped models 或 model registry 的参数补全；它也会把 prompt templates、skills、extension commands 合并进 autocomplete 体系。

`getBuiltInCommandConflictDiagnostics()` 检查 extension command 是否和内置 slash command 冲突，用于资源诊断和 autocomplete 规避。

`getAutocompleteSourceTag()`、`prefixAutocompleteDescription()` 只是给补全项加来源标签，便于区分 user/project/tool、npm 或 git 来源。

`isDeadTerminalError()`、`isAnthropicSubscriptionAuthKey()`、`isUnknownModel()`、`quoteIfNeeded()` 属于局部辅助函数，分别服务终端错误容忍、认证提示、模型恢复判断和 shell 参数展示。

## 修改风险

最高风险是交互状态机被破坏。这个文件同时管理 editor、streaming message、pending tools、bash、auto-compaction、retry、extension UI 和 shutdown，任何异步路径漏清理或重复清理，都可能造成终端残留、快捷键失效、输出错位、消息重复、Escape/Ctrl-C 行为异常。

第二类风险是 session 边界。`InteractiveMode` 通过 convenience getter 访问 `runtimeHost.session`，并支持 session invalidate/rebind。修改时如果缓存了旧 session、旧 settingsManager、旧 extension runner 或旧 footer data，切换会话后可能把消息写入错误 session，或显示旧 cwd/model/trust 状态。

第三类风险是 TUI 与业务耦合。这里看似是 UI 文件，但会触发 prompt、bash、compaction、OAuth、trust、version check、clipboard image、extension commands。改 slash command、快捷键或输入提交逻辑时，需要同时确认 `AgentSession`、`KeybindingsManager`、`BUILTIN_SLASH_COMMANDS`、组件选择器和测试 harness 的约定。

第四类风险是扩展系统。custom editor/header/footer/widgets、autocomplete wrappers、terminal input unsubscribers 都由此文件统一挂载；新增 UI 插槽或重置逻辑时要保证 `dispose()` 和 unsubscribe 成对发生，尤其是 session reload 前后的 `resetExtensionUI()`。

第五类风险是终端兼容性。`ProcessTerminal`、dead terminal errors、hardware cursor、clear-on-shrink、visible width、Markdown 渲染、loader 动画都依赖真实 TTY 行为。修改布局或文字宽度计算后，最好用项目的 tmux 交互测试方式验证，而不只依赖类型检查。
