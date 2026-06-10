# 目录：ui-tui/src

## 它负责什么

`ui-tui/src` 是 Hermes TUI 的 TypeScript/React 终端前端源码目录。它不是一个普通 Web UI，也不是 dashboard 里的 React 聊天重写，而是基于 `@hermes/ink` 渲染到终端的交互界面。它负责终端屏幕布局、输入框、消息转写、工具调用进度、弹窗、会话切换、快捷键、滚动、主题、剪贴板、选择复制、模型选择等用户可见体验。

从当前片段看，TUI 前端本身不直接运行大模型逻辑。`entry.tsx` 创建 `GatewayClient`，由它启动或连接后端 gateway；`App` 和 `useMainApp` 订阅 gateway 事件、维护前端状态，并把整理后的 `actions`、`composer`、`progress`、`status`、`transcript` 交给布局组件渲染。真正的会话、工具、slash 命令后端执行等能力在 Python 侧 `tui_gateway` 中完成，`ui-tui/src` 主要是终端交互壳和事件驱动的状态呈现层。

## 直接子目录地图

`ui-tui/src/app` 是主应用状态与编排层。这里放 `useMainApp.ts`、`createGatewayEventHandler.ts`、`createSlashHandler.ts`、`useSubmission.ts`、`useInputHandlers.ts`、`useSessionLifecycle.ts`、`turnStore.ts`、`uiStore.ts`、`overlayStore.ts` 等文件，承担“把 gateway 事件、用户输入、全局 UI 状态组织成可渲染模型”的职责。`app/slash` 是 slash 命令相关的细分实现区域。

`ui-tui/src/components` 是 Ink 组件层。文件名显示它包含主布局 `appLayout.tsx`、外框状态 `appChrome.tsx`、消息行 `messageLine.tsx`、输入框 `textInput.tsx`、流式助手输出 `streamingAssistant.tsx`、Markdown 渲染 `markdown.tsx`、工具思考/进度 `thinking.tsx`、提示与审批 `prompts.tsx`、会话选择 `sessionPicker.tsx`、模型选择 `modelPicker.tsx`、覆盖层 `appOverlays.tsx` 等。

`ui-tui/src/config` 放前端运行参数与限制，例如环境变量解析、历史长度或尺寸限制、定时参数。`content` 放展示文案、占位符、hotkeys、faces、verbs、fortunes、charms 等轻量内容资源。`domain` 放业务语义的小型纯函数或类型规则，例如消息、路径、provider、slash、usage、viewport、roles、details。

`ui-tui/src/hooks` 是可复用 React hooks，例如补全、Git 分支、输入历史、队列、虚拟历史滚动。`lib` 是跨组件工具库，覆盖剪贴板、OSC52、RPC 解析、终端尺寸/模式、平台判断、文本处理、Markdown/语法辅助、性能、内存、虚拟高度、todo、subagent 树等。`protocol` 放协议级处理，目前可见 `interpolation.ts` 和 `paste.ts`。`types` 放声明文件，`__tests__` 是 Vitest/组件测试集合，覆盖输入、滚动、gateway、slash、终端兼容、状态隔离等行为。

## 关键入口

最外层入口是 `ui-tui/src/entry.tsx`。它首先导入 `lib/forceTruecolor.js`，检查 `stdin` 是否为 TTY，然后修正异常终端尺寸、重置终端模式、清屏或在 Termux 下保留历史输出。随后创建 `GatewayClient` 并调用 `gw.start()`，设置退出清理、内存监控、URL 点击处理、帧性能采样，最后动态导入 `@hermes/ink` 和 `./app.js`，执行 `ink.render(<App gw={gw} />)`。

React 根组件是 `ui-tui/src/app.tsx`。这个文件很薄，只调用 `useMainApp(gw)` 得到应用模型，再通过 `GatewayProvider` 注入 gateway 上下文，最终渲染 `AppLayout`。因此调试 UI 时不应把 `app.tsx` 当成复杂业务入口，它更像组合点。

核心编排入口是 `ui-tui/src/app/useMainApp.ts`。它连接 `@hermes/ink` 的终端能力、React 状态、nanostores 状态、gateway RPC、会话生命周期、输入提交、滚动、选择复制、配置同步、长耗时工具提示等逻辑。当前片段中可以看到它维护 `historyItems`、`catalog`、语音状态、当前 turn 状态、overlay 状态、terminal 列宽等，并创建大量 ref 来协调高频事件和异步 RPC。

通信入口是 `ui-tui/src/gatewayClient.ts`。它封装 Node 子进程、WebSocket attach/sidecar、JSON-RPC pending 请求、gateway 日志环形缓冲、启动超时、事件缓冲、transport 退出处理等。根据当前片段推断，TUI 支持两种形态：本地 spawn Python gateway，或通过环境变量连接已有 gateway/sidecar；依据是文件中存在 `resolveGatewayAttachUrl`、`resolveSidecarUrl`、`resolvePython`、`spawn`、`WebSocket` 等逻辑。

## 主流程位置

启动主流程在 `entry.tsx`：准备终端环境，启动 `GatewayClient`，等待 gateway 发布事件，再渲染 `App`。终端异常尺寸、truecolor、退出清理、内存高水位处理都在这里，是排查“界面起不来、终端被弄乱、gateway 未启动”的第一站。

渲染主流程在 `app.tsx` 到 `components/appLayout.tsx`。`useMainApp` 产出结构化的 `appActions`、`appComposer`、`appProgress`、`appStatus`、`appTranscript`，`AppLayout` 再把它们分配给外框、消息区、输入区、状态区、overlay 等组件。消息具体呈现通常落到 `components/messageLine.tsx`、`components/streamingAssistant.tsx`、`components/markdown.tsx`、`components/thinking.tsx`。

输入与提交主流程在 `app/useInputHandlers.ts`、`app/useComposerState.ts`、`app/useSubmission.ts` 和 `components/textInput.tsx` 一带。用户键入内容先进入 composer 状态；如果是本地可处理命令，会走 slash handler；普通 prompt 则通过 gateway RPC 提交。`useMainApp.ts` 中的 `startPromptLiveSession` 展示了一个典型分支：先新建 live session，可选切模型，再 dispatch prompt。

事件回流主流程在 `app/createGatewayEventHandler.ts` 和 `app/turnStore.ts`。gateway 发来的 `message.delta`、`message.complete`、`tool.start/progress/complete`、审批请求、会话事件等会被转换为前端 transcript、turn live tail、progress/status、overlay prompt。根据命名和测试覆盖推断，这里是处理流式输出、工具活动和状态恢复的关键位置。

## 推荐阅读顺序

建议先读 `ui-tui/src/entry.tsx`，建立“Node 入口、终端准备、GatewayClient、Ink render”的启动模型。第二步读 `ui-tui/src/app.tsx`，理解根组件只是把 `useMainApp` 的结果交给 `AppLayout`。第三步读 `ui-tui/src/app/useMainApp.ts`，重点看它引入了哪些 hooks、stores、handlers，不必一开始逐行深挖所有状态。

第四步读 `ui-tui/src/gatewayClient.ts`，弄清 TUI 前端如何和 Python gateway 通信、如何处理 ready、timeout、exit、RPC pending。第五步按用户路径读组件：输入相关看 `components/textInput.tsx`、`app/useComposerState.ts`、`app/useInputHandlers.ts`、`app/useSubmission.ts`；消息展示看 `components/messageLine.tsx`、`components/streamingAssistant.tsx`、`components/thinking.tsx`；弹窗与审批看 `components/prompts.tsx`、`components/appOverlays.tsx`。最后再看 `lib`、`domain`、`hooks` 中被调用到的辅助函数。

## 常见误区

不要把 `ui-tui/src` 当成后端 agent 目录。它不会直接决定模型调用、工具执行、记忆写入等核心 agent 行为；这些通常在 Python gateway 或 agent 主体里。这里更多负责“把后端事件变成终端 UI”。

不要把 dashboard 的 `/chat` 理解成另一套 React 聊天实现。项目说明中强调 dashboard 嵌入真实 `hermes --tui`，所以主聊天体验应扩展 Ink TUI，而不是在 dashboard React 页面重新造 transcript 和 composer。

不要只看 `components` 就试图理解业务流程。组件主要渲染 props；状态来源、RPC 调用、事件转换集中在 `app` 层，尤其是 `useMainApp.ts`、`createGatewayEventHandler.ts`、`createSlashHandler.ts`、`useSubmission.ts`。

不要忽略终端兼容代码。`lib/terminalDimensions.ts`、`lib/terminalModes.ts`、`lib/termux.ts`、`lib/osc52.ts`、`lib/platform.ts` 这类文件看似边缘，但对 TUI 是否能在 macOS Terminal、WSL、Termux、SSH、不同剪贴板路径下稳定运行很重要。

不要把 `__tests__` 当成附属噪音。这个目录的测试名本身就是行为地图：gateway recovery、slash parity、cursor drift、virtual history、terminal parity、text input、selection、viewport、status rule 等，能快速告诉你这个 TUI 最容易出问题的边界在哪里。
