# 目录：src/tui

## 它负责什么

`src/tui` 是 OpenClaw 终端交互界面的实现目录，负责把 CLI 的 `tui` / `terminal` / `chat` 入口转成一个可交互的文本 UI。它不是单纯的渲染层，而是把终端组件、输入提交、斜杠命令、会话切换、Gateway 连接、本地嵌入后端、流式消息组装、状态提示和退出清理串在一起的前端运行环路。

从当前片段看，核心外部依赖是 `@earendil-works/pi-tui`，`src/tui/tui.ts` 直接使用 `TUI`、`Container`、`ProcessTerminal`、`CombinedAutocompleteProvider`、`Loader`、`Text`、`Key` 等终端 UI 能力。OpenClaw 自身侧，它连接 `src/gateway/protocol/*` 的命令类型、`src/routing/session-key.ts` 的会话键规则、`src/config/config.ts` 的运行配置，以及 `src/agents/agent-scope.ts` 的默认 agent / workspace 推断逻辑。

这个目录的定位可以理解为“终端客户端层”：它知道如何展示、如何收集用户输入、如何把输入交给后端、如何消费后端事件；但真正的 provider、agent runtime、Gateway 服务、插件发现等不在这里实现。`src/tui/AGENTS.md` 也明确提醒，fake-backend PTY 测试只证明真实 `runTui()` 环路和假的 `TuiBackend` 能协作，不证明 Gateway transport、嵌入后端运行时、provider、session persistence 或 live streaming。

## 直接子目录地图

`src/tui/components` 是可复用 TUI 组件区。它包含聊天日志、用户消息、助手消息、Markdown 消息、工具执行块、内联提示、自定义编辑器、可搜索/可过滤选择列表、selector 组件和超链接 Markdown 包装等。这里的文件名很直观，例如 `src/tui/components/chat-log.ts` 管聊天记录容器，`src/tui/components/custom-editor.ts` 管输入编辑器，`src/tui/components/tool-execution.ts` 管工具调用显示，`src/tui/components/hyperlink-markdown.ts` 处理终端里带 OSC 8 超链接能力的 Markdown 渲染。概览阅读时不需要逐个叶子展开，只要知道它们服务于 `src/tui/tui.ts` 的界面拼装。

`src/tui/theme` 是终端 UI 主题区，目前从目录形状看主要入口是 `src/tui/theme/theme.ts`，并有 `src/tui/theme/theme.test.ts` 覆盖。`src/tui/tui.ts` 引入 `theme` 和 `editorTheme`，说明主题不仅影响普通文本，还影响编辑器样式。

根层 `src/tui/*.ts` 是主逻辑区。这里没有再拆子目录，而是按职责拆成多个平级模块：启动、后端、Gateway 聊天、命令处理、事件处理、提交处理、会话动作、状态摘要、等待文案、格式化、overlay、本地 shell、最后会话记忆、流式组装等。

## 关键入口

最重要的入口是 `src/tui/tui.ts`。它导出 `runTui`，并重新导出 `TuiOptions`、`resolveFinalAssistantText`、`createEditorSubmitHandler`、`createSubmitBurstCoalescer`、`shouldEnableWindowsGitBashPasteFallback` 等给测试或外部调用复用。CLI 侧的 `src/cli/tui-cli.ts` 会动态 import `../tui/tui.js`，然后调用 `runTui`；`src/crestodian/operations.ts` 在 `open-tui` 操作中也会调用 `runTui({ local: true, ... })`；setup wizard 相关代码则可能通过 `src/tui/tui-launch.ts` 重新拉起 TUI 子进程。

`src/tui/tui-launch.ts` 是“从当前进程重新启动 TUI CLI”的入口。它构造当前 CLI entry 参数，过滤 `--inspect*` 调试参数，追加 `tui` 子命令和 `--local`、`--url`、`--token`、`--password`、`--session`、`--thinking`、`--message`、`--timeout-ms`、`--history-limit`、`--deliver` 等选项，再用 `spawn(process.execPath, args, { stdio: "inherit" })` 继承终端启动子进程。它还会在启动前暂停 stdin，并在结束后按原状态恢复。

`src/tui/tui-backend.ts` 定义 TUI 与后端交互的抽象边界。根据文件名和 `src/tui/tui.ts` 的 import，可以把它看作 TUI 运行环路依赖的后端接口层；`src/tui/embedded-backend.ts`、`src/tui/gateway-chat.ts` 则分别偏向本地嵌入后端与 Gateway 聊天客户端实现。根据当前片段推断，`runTui` 可以接收注入的 `backend?: TuiBackend`，这也是 PTY fake-backend 测试能够运行真实 UI 环路的原因。

## 主流程位置

启动主流程在 `src/tui/tui.ts`。这个文件先解析本地配置和 session 相关输入：例如 `resolveInitialTuiAgentId` 会优先从传入的 session key 解析 agent id，再尝试按当前 workspace 推断，最后回退到默认 agent；`resolveTuiSessionKey` 会把空值、`global`、完整 `agent:*` key 或短 main key 归一化为 TUI 使用的 session key。它还处理本地 auth CLI 调用、终端停止异常、退格去重、Gateway 断开状态等边界问题。

界面拼装主流程也集中在 `src/tui/tui.ts`。它引入 `ChatLog`、`CustomEditor`、`theme`、`editorTheme`、`getSlashCommands`，并通过 `@earendil-works/pi-tui` 创建终端 UI。根据 import 关系，主界面大致由聊天日志、编辑器、等待/状态文本、overlay、选择列表和命令补全组成。

用户输入提交主流程在 `src/tui/tui-submit.ts`。`src/tui/tui.ts` 使用 `createEditorSubmitHandler` 和 `createSubmitBurstCoalescer`，说明这里负责把编辑器内容转换为一次可控提交，并处理快速重复提交、Windows Git Bash 粘贴兼容等终端输入细节。

后端事件进入 UI 的主流程在 `src/tui/tui-event-handlers.ts`。它使用 `TuiStreamAssembler` 和 `tui-formatters`，并会调用 `tui.requestRender()` 触发重绘。根据测试名和 import，可推断它处理 agent event、chat event、btw event、streaming watchdog 等事件，把后端流式输出、命令消息、工具调用结果等变成聊天日志状态。

斜杠命令和会话动作主流程分别在 `src/tui/tui-command-handlers.ts` 与 `src/tui/tui-session-actions.ts`。前者处理 TUI 内部命令，如状态、会话选择、新会话等；后者封装会话列表、加载历史、切换当前 session、写入最后会话记录等动作。`src/tui/tui-last-session.ts` 负责持久化或读取上次 TUI session 指针，`src/tui/tui-session-list-policy.ts` 则保存会话列表查询限制之类的策略常量。

本地 shell 相关流程在 `src/tui/tui-local-shell.ts`。从文件名和 import 看，它负责在 TUI 中启动或管理本地 shell 运行，并与 `tui.requestRender()` 联动刷新显示。Gateway 连接相关流程在 `src/tui/gateway-chat.ts`，其中测试片段显示客户端 display name 使用 `openclaw-tui`，并且会作为 TUI 客户端走 Gateway 认证/通信路径。

## 推荐阅读顺序

第一步读 `src/tui/AGENTS.md`，先理解测试证明边界，尤其 fake-backend PTY 与真实 Gateway / provider / session persistence 的区别。

第二步读 `src/tui/tui-types.ts` 和 `src/tui/tui-backend.ts`。前者建立状态、事件、选项、session 等核心类型词汇；后者建立 TUI 与后端之间的契约。先看契约再看实现，会比直接进入 `tui.ts` 更容易。

第三步读 `src/tui/tui.ts`。重点看 `runTui` 周围的初始化、状态对象、组件创建、handler 组装和退出清理，不必陷入每个 helper 的细节。

第四步按主流程分支读：输入提交看 `src/tui/tui-submit.ts`；事件消费看 `src/tui/tui-event-handlers.ts` 和 `src/tui/tui-stream-assembler.ts`；斜杠命令看 `src/tui/commands.ts` 与 `src/tui/tui-command-handlers.ts`；会话切换看 `src/tui/tui-session-actions.ts`、`src/tui/tui-last-session.ts`。

第五步再读展示层：`src/tui/components/chat-log.ts`、`src/tui/components/custom-editor.ts`、`src/tui/components/markdown-message.ts`、`src/tui/components/tool-execution.ts` 和 `src/tui/theme/theme.ts`。这时已经知道数据从哪里来，组件代码会更容易对应到屏幕表现。

第六步看测试入口。窄单元测试分布在对应 `*.test.ts`；端到端 PTY 相关是 `src/tui/tui-pty-harness.e2e.test.ts` 和 `src/tui/tui-pty-local.e2e.test.ts`。测试命令遵循 `src/tui/AGENTS.md`：快速 fake-backend PTY lane 使用 `node scripts/run-vitest.mjs run --config test/vitest/vitest.tui-pty.config.ts`，本地后端 smoke 需额外设置 `OPENCLAW_TUI_PTY_INCLUDE_LOCAL=1`。

## 常见误区

不要把 `src/tui` 当成 Gateway 或 agent runtime 的实现目录。它是终端客户端层，Gateway 协议、server 方法、provider 路由、插件加载和 agent 执行主体分别在其他目录。`src/tui/gateway-chat.ts` 只是 TUI 客户端接入 Gateway 的一侧。

不要把 fake-backend PTY 测试结论扩大。`src/tui/AGENTS.md` 已明确说明，fake-backend lane 证明真实 `runTui()` 循环能和假的 `TuiBackend` 工作；它不证明 Gateway transport、embedded backend runtime、providers、session persistence 或 live streaming。

不要只看 `components` 就以为掌握了 TUI。组件只是展示积木，真正决定行为的是 `src/tui/tui.ts`、`src/tui/tui-submit.ts`、`src/tui/tui-event-handlers.ts`、`src/tui/tui-command-handlers.ts` 和 `src/tui/tui-session-actions.ts` 这些根层模块。

不要把 `openclaw-tui` 当作真实 session key。相关 agent 工具测试里有提示，UI label 和 session key 不是一回事；TUI 自身会通过 `resolveTuiSessionKey`、`buildAgentMainSessionKey`、`parseAgentSessionKey` 等逻辑维护规范 session key。

不要在学习时逐文件铺开所有测试。这个目录测试很多，但 overview 深度更适合按“启动入口、后端契约、输入提交、事件消费、会话管理、展示组件、PTY 验证”这张地图阅读。
