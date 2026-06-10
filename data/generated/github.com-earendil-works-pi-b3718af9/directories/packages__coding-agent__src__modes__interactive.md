# 子系统：packages/coding-agent/src/modes/interactive

## 解决什么问题

`packages/coding-agent/src/modes/interactive` 负责 `pi` 的终端交互模式，也就是用户不使用 `--print`、RPC 等非交互入口时看到的 TUI 会话界面。它把底层 coding agent 的会话、模型调用、工具执行、分支、恢复、配置选择、登录选择、项目信任确认等能力包装成可操作的终端 UI。

从 `packages/coding-agent/src/main.ts` 的调用关系看，主程序会先解析 CLI 参数并判断 `appMode`，当模式为 `"interactive"` 时初始化主题，然后构造 `InteractiveMode`，依次调用 `init()`、`run()`，异常或退出时调用 `stop()`。因此这个目录不是 agent 推理核心本身，而是“交互式外壳”：它接收键盘输入、展示流式响应、渲染工具执行状态，并把用户操作转换为对运行时和会话系统的调用。

## 相关目录和文件

核心入口是 `packages/coding-agent/src/modes/interactive/interactive-mode.ts`。它定义 `InteractiveMode`，承接主程序传入的 runtime 和启动选项，负责交互模式生命周期、输入处理、事件处理、状态展示、扩展 UI 上下文、会话分支/恢复等流程。

`packages/coding-agent/src/modes/interactive/components` 存放 TUI 组件。它不是普通“页面组件”集合，而是交互模式的渲染层：`assistant-message.ts`、`user-message.ts` 渲染对话消息；`tool-execution.ts`、`bash-execution.ts`、`diff.ts` 渲染工具、命令和变更；`footer.ts`、`bordered-loader.ts`、`dynamic-border.ts` 提供通用界面结构；`model-selector.ts`、`theme-selector.ts`、`settings-selector.ts`、`trust-selector.ts`、`session-selector.ts`、`tree-selector.ts` 等提供可键盘导航的选择器；`extension-*` 相关文件承接扩展的交互输入和编辑 UI。

`packages/coding-agent/src/modes/interactive/theme` 负责主题系统。`theme.ts` 暴露 `initTheme`、`stopThemeWatcher`、`theme`、`highlightCode` 等能力，`dark.json`、`light.json` 和 `theme-schema.json` 是主题数据和约束。测试中也直接初始化主题，说明组件渲染依赖这个全局主题状态。

相邻目录 `packages/coding-agent/src/modes/rpc`、print mode 相关代码则是其他运行模式。`packages/coding-agent/src/cli` 中的 `startup-ui.ts`、`config-selector.ts`、`session-picker.ts` 会复用 interactive 的组件，说明这些组件不只服务主 TUI，也服务启动阶段的选择流程。

## 核心对象

`InteractiveMode` 是本目录的中心对象。根据当前片段推断，它承担四类职责：一是生命周期管理，包括 `init()`、`run()`、`stop()`；二是输入命令处理，例如 `/clone`、状态展示、会话树选择、用户消息选择、配置/模型/主题选择；三是把 runtime 发出的事件转换为 UI 输出，例如 assistant 消息、工具调用、bash 执行、压缩摘要、分支摘要、技能调用等；四是为扩展系统提供 UI 能力，例如自定义组件、主题设置、自动补全 provider。

组件层的核心抽象来自 `@earendil-works/pi-tui`，常见对象包括 `Container`、`Text`、`Box`、`Markdown`、`Spacer`、`Component`。各选择器组件通常继承 `Container` 或实现 `Component`，内部维护 `selectedIndex`、过滤条件、可见列表等状态，通过 `handleInput(keyData)` 响应按键。

`theme` 是交互显示的共享服务。组件通常调用 `theme.fg()`、`theme.bg()`、`theme.bold()` 生成带样式的终端文本。`UserMessageComponent` 还包裹 OSC 133 控制序列，用于标记终端 shell integration 区域；这类细节说明渲染输出不仅是字符串，还要兼容终端协议。

## 运行流程

启动时，`main.ts` 先判断 stdin 和 CLI 参数。如果 stdin 是 TTY，则默认进入 interactive；如果带 `--print` 等参数则走非交互模式。进入 interactive 后，主程序调用 `initTheme(settingsManager.getTheme(), true)`，然后创建 `new InteractiveMode(runtime, options)`。

`InteractiveMode.init()` 根据当前片段推断会完成会话、配置、资源、扩展、状态栏等初始化工作。若启动参数包含初始 prompt，它需要在 UI 准备后把该 prompt 送入会话。随后 `run()` 接管终端输入循环：普通文本会作为用户消息提交给 agent runtime；特殊按键和 slash 命令会打开选择器、切换设置、恢复会话、分支、克隆或显示状态。

agent runtime 执行期间会产生流式事件。`InteractiveMode` 的事件处理逻辑将这些事件映射到组件：用户输入显示为 `UserMessageComponent`，模型回复显示为 `AssistantMessageComponent`，工具调用显示为 `ToolExecutionComponent`，shell 命令显示为 `BashExecutionComponent`，会话压缩和分支等元信息显示为对应 summary component。组件把状态渲染成终端行，footer 则展示模型、上下文、工具展开状态或键位提示。

当用户进入选择流程时，例如模型选择、主题选择、项目信任、会话恢复、树形分支选择，当前输入处理会临时交给对应 selector component。确认后回调写入设置或调用 runtime/session API；取消则回到主输入状态。

## 上下游依赖

上游入口主要是 `packages/coding-agent/src/main.ts` 和 `packages/coding-agent/src/cli`。`main.ts` 决定是否进入 interactive，并负责主题初始化、runtime 构造、项目信任流程、启动参数传递。`cli` 目录中的启动 UI 和配置选择器复用了 interactive components，因此组件修改可能影响启动阶段，而不只是会话中界面。

下游依赖包括 `packages/coding-agent/src/core` 下的会话、信任、扩展、工具、资源加载等能力。比如 `trust-selector.ts` 直接依赖 `core/trust-manager.ts` 的 `getProjectTrustOptions`、`getProjectTrustPath`；会话选择器和树选择器依赖 session tree、entry id、message 结构；工具展示组件依赖工具调用事件和结果格式。

外部依赖最重要的是 `@earendil-works/pi-tui`。本目录的组件结构、按键匹配、Markdown 渲染、宽度截断、容器布局都建立在这个包上。修改 UI 行为时需要同时理解 pi-tui 的 `render(width)`、`handleInput()`、`getKeybindings()` 和宽度计算规则。

测试位于 `packages/coding-agent/test`，覆盖了 `trust-selector`、`oauth-selector`、`session-selector`、`tool-execution-component`、`user-message`、`syntax-highlight`、`tree-selector`、`theme-detection`、`interactive-mode-status`、`interactive-mode-compaction` 等。它们是理解边界行为的重要依据。

## 修改时最容易踩的坑

第一，按键不要写死。组件中有些地方兼容 `j/k` 或回车，但主要动作应通过 `getKeybindings().matches()` 走可配置 keybinding，否则会破坏用户配置。

第二，终端宽度和视觉行数很容易出错。`visual-truncate.ts` 专门用 `Text.render(width)` 计算换行后的视觉行，再截取末尾内容。工具输出、bash 输出、长消息都应遵循同类逻辑，不能只按 `\n` 或字符串长度截断。

第三，主题必须先初始化。很多组件直接使用 `theme` 单例，测试也会调用 `initTheme()`。新增组件如果在主题未初始化时渲染，可能出现测试不稳定或启动阶段样式异常。

第四，交互组件通常是有状态对象。`selectedIndex`、搜索条件、过滤模式、折叠节点、当前 leaf id 等状态要和 `render()`、`handleInput()` 保持一致。尤其是会话树和恢复选择器，entry id、parentId、active path 的关系不能只按列表下标处理。

第五，interactive 组件被 CLI 启动流程复用。修改 `components` 下的 selector 时，要考虑 `src/cli/config-selector.ts`、`src/cli/session-picker.ts`、`src/cli/startup-ui.ts` 的使用场景，不能假设一定处于完整 `InteractiveMode` 会话内。

第六，输出中有终端控制序列。比如 `UserMessageComponent` 使用 OSC 133 标记区域。调整渲染边界、包裹 Box 或 Markdown 时，必须确认控制序列仍在正确的首尾行上。

## 推荐阅读顺序

1. 先读 `packages/coding-agent/src/main.ts` 中 interactive 分支，理解何时创建 `InteractiveMode`，以及 `initTheme()`、`init()`、`run()`、`stop()` 的外层顺序。

2. 再读 `packages/coding-agent/src/modes/interactive/interactive-mode.ts`，重点看构造参数、生命周期方法、输入处理、事件处理、状态展示和扩展 UI 上下文。

3. 接着读 `packages/coding-agent/src/modes/interactive/theme/theme.ts` 和 `dark.json`、`light.json`，理解样式、语法高亮和主题 watcher 如何供组件使用。

4. 然后按功能读组件：先看 `user-message.ts`、`assistant-message.ts`，再看 `tool-execution.ts`、`bash-execution.ts`、`diff.ts`，最后看 `session-selector.ts`、`tree-selector.ts`、`model-selector.ts`、`trust-selector.ts` 等交互选择器。

5. 最后读相关测试，尤其是 `packages/coding-agent/test/interactive-mode-status.test.ts`、`tool-execution-component.test.ts`、`tree-selector.test.ts`、`session-selector-*`、`theme-detection.test.ts`。这些测试比源码注释更能说明交互边界和历史回归点。
