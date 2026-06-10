# 文件：ui-tui/README.md

## 一句话定位

`ui-tui/README.md` 是 Hermes 终端 TUI 子系统的开发者入口文档：它不参与运行时逻辑，而是说明 `hermes --tui` 如何把 TypeScript/Ink 前端、`GatewayClient` 子进程桥接层和 Python `tui_gateway` 后端串成一个可交互的聊天界面。

## 它暴露/定义了什么

这个文件暴露的是“架构契约”，不是代码 API。它定义了几类关键信息：启动方式与本地命令、前端入口 `src/entry.tsx`、核心 UI 容器 `src/app.tsx`、子进程桥 `src/gatewayClient.ts`、Python 侧 `tui_gateway/entry.py` 与 `tui_gateway/server.py` 的职责边界、JSON-RPC over stdio 的通信模型、主要事件类型、主题合并规则、快捷键行为、prompt 流程、slash command 分流策略，以及 TUI 目录下重要文件的职责地图。

它最核心的设计声明是：TypeScript 负责屏幕和交互状态，Python 负责 session、工具、模型调用和大多数命令逻辑。这条边界会影响后续所有改动判断。

## 谁调用它

没有证据表明运行时代码会读取或解析 `ui-tui/README.md`。根据当前片段推断，它主要被开发者、维护者、文档作者和调试人员“调用”：当需要理解 TUI 启动链路、排查 `hermes --tui`、新增本地 slash command、调整输入行为、修改 prompt overlay、或定位前后端协议问题时，会以此文件作为导航。

间接关联的用户入口是 `hermes --tui`。CLI 启动 TUI 时会进入编译后的 `ui-tui/dist/entry.js` 或源码开发模式，但这条运行链不会依赖 README 本身。

## 它调用谁

README 本身不调用任何模块。它描述的调用关系是：`src/entry.tsx` 启动时检查 TTY、清理终端状态、创建 `GatewayClient`，然后渲染 `<App gw={gw} />`；`GatewayClient` 默认通过 `python -m tui_gateway.entry` 拉起 Python 子进程，也支持通过 `HERMES_TUI_GATEWAY_URL` 连接已有 gateway；`tui_gateway/entry.py` 发出 `gateway.ready`，随后循环读取 stdin 中的 JSON-RPC 请求并交给 `tui_gateway.server.dispatch`；`src/app.tsx` 及 `src/app/*` 通过 `GatewayClient.request()` 发送 `prompt.submit`、`complete.slash`、`session.list`、`slash.exec`、`command.dispatch` 等 RPC，并订阅 gateway events 更新 Ink UI。

## 核心流程

启动流程是：用户运行 `hermes --tui`，Node 入口进入 `src/entry.tsx`。如果 stdin 不是 TTY，进程直接退出；否则先规范终端尺寸、重置终端模式、启动内存监控和退出清理，再创建并启动 `GatewayClient`。`GatewayClient` 解析 Python 路径，优先使用 `HERMES_PYTHON`、`PYTHON`、虚拟环境解释器，最后退到系统 `python3` 或 Windows 的 `python`，然后以 stdio 拉起 `tui_gateway.entry`。

通信流程是 newline-delimited JSON-RPC：前端写请求到 Python stdin，后端写响应和 `event` notification 到 stdout；stderr 不直接污染终端，而是进入内存日志并转成 `gateway.stderr`。如果 stdout 出现非协议行，会被视为 protocol noise 并上报 `gateway.protocol_error`。

交互流程是：用户输入由 `app.tsx`、`useComposerState.ts`、`useInputHandlers.ts`、`components/textInput.tsx` 管理；普通文本在 agent 忙时进入队列，空 Enter、Ctrl+C、Tab、方向键等按 README 中的规则切换为提交、中断、补全或编辑队列。提交后前端调用 `prompt.submit`，Python 侧创建或复用 session，驱动 agent 与工具调用，并用 `message.delta`、`reasoning.delta`、`tool.start/progress/complete` 等事件回推 UI。阻塞型输入如 approval、clarify、sudo、secret 不开新屏，而是在 `app.tsx` 中切换状态分支和 overlay。

命令流程是两段式：少量必须由前端直接处理的命令，如 `/help`、`/quit`、`/clear`、`/resume`、`/copy`、`/paste`、`/details`、`/queue`，由本地 slash handler 处理；其他命令先走 `slash.exec`，再 fall through 到 `command.dispatch`，从而保持 Python 的命令注册、插件、skills、别名系统为权威来源。

## 关键函数的高层作用

`src/entry.tsx` 的顶层启动逻辑是 TUI 的生命周期入口：它负责 TTY gate、终端模式恢复、gateway 启停、内存保护、Ink render 和链接点击处理。

`GatewayClient.start()` 是前端到后端的连接建立点：它决定是连接 WebSocket gateway，还是 spawn `python -m tui_gateway.entry`，并设置 ready timeout、stdout/stderr 读取、事件缓冲和重连状态。

`GatewayClient.request()` 根据当前 transport 发送 JSON-RPC 请求，维护 pending map、超时、响应解析和错误传播，是 UI 调用 Python 功能的统一出口。

`tui_gateway.entry.main()` 是 Python stdio 服务入口：它可选安装 dashboard sidecar publisher，后台发现 MCP tools，发送 `gateway.ready`，循环解析 stdin 请求并调用 `dispatch()`，同时记录 broken pipe、signal、EOF 等退出原因。

`tui_gateway.server.dispatch()` 是 Python RPC 分发表。它把 `prompt.submit`、`session.list`、`complete.slash`、`slash.exec`、`command.dispatch`、`model.options` 等方法路由到具体 handler；长耗时方法会走线程池，避免卡住 stdio 请求循环。

`createGatewayEventHandler.ts` 根据 gateway event 更新前端状态，属于协议事件到 React/Ink 状态树的转换层；`createSlashHandler.ts` 处理本地命令与后端 fallthrough；`useComposerState.ts`、`useInputHandlers.ts` 分别承载草稿/队列状态和按键路由。

## 修改风险

最大风险是破坏前后端协议契约。README 列出的事件名、payload 形状、RPC 方法名和 fallthrough 顺序必须与 `ui-tui/src/app/interfaces.ts`、`ui-tui/src/gatewayClient.ts`、`tui_gateway/server.py` 保持一致；否则表现会是 UI 卡住、提示框无法响应、slash command 在 CLI 可用但 TUI 失效、补全或 session resume 无响应。

第二类风险是输入体验回归。TUI 的主输入、队列编辑、历史导航、补全、阻塞 prompt 共享按键空间，改 `useInputHandlers.ts` 或 `components/textInput.tsx` 时容易让 `Enter`、`Ctrl+C`、`Up/Down` 在不同模式下互相抢占。

第三类风险是启动与退出稳定性。`entry.tsx` 和 `tui_gateway/entry.py` 都有大量为终端状态、SSH/PTY 断连、SIGPIPE、stderr 隔离、内存 OOM、dashboard sidecar 设计的保护逻辑；简化这些逻辑可能让用户终端残留鼠标模式、gateway 静默死亡或错误日志泄漏到主 UI。

第四类风险是重复实现 Python 已有能力。README 明确要求 Python 拥有 aliases、plugins、skills 和 registry-backed commands 的权威逻辑；新增命令时，如果不需要直接控制前端状态，应优先让 TUI fall through 到 `slash.exec` 或 `command.dispatch`，避免 TypeScript 和 Python 两套行为分叉。
