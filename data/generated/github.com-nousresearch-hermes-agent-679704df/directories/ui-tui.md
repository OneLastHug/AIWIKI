# 目录：ui-tui

## 它负责什么

`ui-tui` 是 Hermes 的终端图形界面前端，技术栈是 TypeScript、React、Ink。它的职责边界很清楚：TypeScript 侧负责“屏幕、输入、滚动、选择、覆盖层、状态栏、流式渲染”等终端 UI 体验；Python 侧仍然负责会话、工具调用、模型请求和大部分命令逻辑。也就是说，这里不是一个独立 Agent 实现，而是 Hermes 主体能力的 TUI 客户端。

从 `README.md` 和 `src/entry.tsx` 可见，运行路径通常是 `hermes --tui`，本包启动后会创建 `GatewayClient`，再渲染 `App`。`GatewayClient` 默认通过子进程启动 `python -m tui_gateway.entry`，与 Python 后端使用 newline-delimited JSON-RPC over stdio 通信；也支持通过环境变量附着到已有 WebSocket gateway。stderr 不直接写入界面，而是进入内存日志环并转成 `gateway.stderr` 事件。

## 直接子目录地图

`src` 是主要业务源码目录。它包含入口、应用编排、组件、领域函数、协议辅助、hooks、类型定义和测试。理解 TUI 时主要读这里。

`src/app` 放应用状态和主编排逻辑，包括 gateway 事件处理、slash 命令处理、输入状态、会话生命周期、turn 状态、overlay 状态、UI store、提交逻辑等。它是“把后端事件变成界面状态”的核心层。

`src/components` 放 Ink 组件，例如整体布局、消息行、Markdown 渲染、输入框、prompt、session picker、model picker、工具活动展示、todo 面板、状态栏与覆盖层等。它更接近展示层。

`src/domain` 放偏纯的领域格式化与解析逻辑，例如 message、path、provider、role、slash、usage、viewport 等，不直接承担 React 树组织。

`src/hooks` 放可复用 React hooks，例如补全、Git 分支、输入历史、队列、虚拟历史滚动等。

`src/lib` 是底层工具函数和跨组件基础设施，覆盖剪贴板、OSC52、RPC 辅助、终端模式、终端尺寸、文本处理、Markdown/语法相关辅助、性能、内存监控、平台差异等。

`src/protocol` 放与输入协议或文本协议相关的小模块，例如 paste、interpolation。

`src/config` 放环境、限制、时间配置；`src/content` 放界面文案、快捷键、占位内容、动效词等数据；`src/types` 和 `src/types.ts` 放类型补充。

`src/__tests__` 是 vitest 测试区，覆盖输入、滚动、gateway、slash、渲染、终端兼容、状态隔离等行为。测试名本身可以作为功能地图。

`packages/hermes-ink` 是本仓库内的本地 Ink 包，`package.json` 中通过 `@hermes/ink: file:./packages/hermes-ink` 引入。根据当前片段推断，它承担 Hermes TUI 对 Ink 的定制或封装，依据是 `src/entry.tsx`、`src/app/useMainApp.ts` 从 `@hermes/ink` 导入 `render`、`useApp`、`useStdout`、`ScrollBoxHandle`、选择相关 API 等。

`scripts` 放构建和 profiling 脚本，例如 `build.mjs`、`profile-tui.mjs`。根部的 `package.json`、`tsconfig*.json`、`vitest.config.ts`、`eslint.config.mjs` 是包管理、构建、测试与 lint 配置。

## 关键入口

`src/entry.tsx` 是进程入口。它首先处理 truecolor、TTY 检查、终端尺寸修正、终端模式重置、清屏或 Termux 特殊行为；随后创建并启动 `GatewayClient`，注册 graceful exit 和内存监控，最后动态导入 `@hermes/ink`、`./app.js` 并执行 `ink.render(<App gw={gw} />)`。

`src/gatewayClient.ts` 是前端到 Python 后端的通信入口。它负责解析 Python 路径、启动 `tui_gateway.entry` 子进程、读取 stdout JSON-RPC 帧、收集 stderr、维护 pending RPC、发布 gateway event、处理启动超时、WebSocket attach、sidecar mirror 和 transport 重启/退出。

`src/app.tsx` 是 React 应用入口，但它本身很薄：调用 `useMainApp(gw)` 得到 actions、composer、progress、status、transcript、gateway，然后用 `GatewayProvider` 包住 `AppLayout`。真正复杂度被下沉到 `src/app/useMainApp.ts` 和相关 app 模块。

`src/app/useMainApp.ts` 是主状态编排入口。它连接 `GatewayClient`、终端尺寸、历史消息、输入状态、会话状态、turn 状态、overlay store、补全、滚动、选择、粘贴、提交和 gateway event handler。阅读它可以看到 TUI 如何把“用户输入”和“后端事件”汇合成界面模型。

`src/components/appLayout.tsx` 是主要布局入口；`src/components/messageLine.tsx`、`src/components/streamingAssistant.tsx`、`src/components/thinking.tsx`、`src/components/prompts.tsx`、`src/components/textInput.tsx` 是理解界面呈现和交互的关键组件。

## 主流程位置

启动主流程在 `src/entry.tsx`：准备终端环境，启动 `GatewayClient`，渲染 `App`。这一步解决的是“Node/Ink TUI 怎么活起来”。

后端连接主流程在 `src/gatewayClient.ts`：`start()` 决定是 attach WebSocket 还是 spawn Python；默认 `startSpawnedGateway()` 执行 `python -m tui_gateway.entry`，并通过 stdout/stderr 建立 JSON-RPC 事件流。`dispatch()` 将响应匹配到 pending RPC，或把 `method: "event"` 的消息发布为 `GatewayEvent`。

应用状态主流程在 `src/app/useMainApp.ts`：它创建 transcript、composer、overlay、turn、session、scroll 等状态，并把 `GatewayClient` 的事件交给 `createGatewayEventHandler.ts`。用户输入则经 `useInputHandlers.ts`、`useComposerState.ts`、`useSubmission.ts` 进入提交链路。

slash 命令主流程在 `src/app/createSlashHandler.ts`。根据 README，`/help`、`/quit`、`/clear`、`/resume`、`/copy`、`/paste`、`/details`、`/logs`、`/queue`、`/undo`、`/retry` 等需要客户端直接处理的命令在本地分发；其他命令会落到 gateway 侧。

渲染主流程在 `src/components`。普通历史消息进入 transcript；实时 assistant 输出、reasoning、tool progress、subagents、todos 等进入 live 区域；approval、clarify、sudo、secret、session picker 这类阻塞式交互通过 overlay/prompt 组件覆盖主输入。

## 推荐阅读顺序

1. 先读 `ui-tui/README.md`，建立边界：TUI 只管屏幕，Python 管 Agent 和工具。
2. 再读 `ui-tui/package.json`，了解 `npm run dev`、`npm start`、`npm run build`、`npm test` 以及本地包 `@hermes/ink`。
3. 读 `src/entry.tsx`，掌握启动、终端初始化、gateway 生命周期和 Ink render。
4. 读 `src/gatewayClient.ts`，理解前后端 JSON-RPC、事件发布、stderr 日志、WebSocket attach 与子进程模式。
5. 读 `src/app.tsx` 和 `src/app/useMainApp.ts`，看应用如何组织状态。
6. 按兴趣进入 `src/app/createGatewayEventHandler.ts`、`src/app/createSlashHandler.ts`、`src/app/useSubmission.ts`、`src/app/useInputHandlers.ts`。
7. 最后读 `src/components/appLayout.tsx`、`messageLine.tsx`、`textInput.tsx`、`prompts.tsx`、`thinking.tsx`，把状态和实际 UI 对上。

## 常见误区

不要把 `ui-tui` 当成 Hermes Agent 的核心循环。模型调用、工具调用、会话存储和多数命令处理仍在 Python 侧，TUI 通过 `GatewayClient` 请求和接收事件。

不要在 dashboard 的 React 页面里重写主聊天体验。根据仓库说明，dashboard 的 `/chat` 嵌入真实 `hermes --tui`，主 transcript、composer、slash 行为应该扩展 Ink TUI，而不是另做一套 React chat。

不要以为所有 slash 命令都在 TypeScript 里实现。这里仅处理需要本地 UI 能力的命令；大量命令仍应通过 gateway 或 Python 命令系统处理。

不要绕过 `GatewayClient` 直接读写 Python 子进程输出。stdout 是 JSON-RPC 协议流，stderr 被收集成日志事件；直接输出到终端会破坏 Ink 渲染。

不要只读 `components` 就判断行为。很多交互规则在 `src/app`、`src/hooks`、`src/lib` 中，组件通常只消费已经整理好的状态。
