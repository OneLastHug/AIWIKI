# 文件：ui-tui/src/gatewayClient.ts

## 一句话定位

`ui-tui/src/gatewayClient.ts` 是 Ink TUI 前端和 Python `tui_gateway` 后端之间的传输层客户端：它负责启动或连接 gateway、发送 JSON-RPC 请求、接收异步事件，并把底层进程/WebSocket 生命周期包装成前端可消费的 `EventEmitter` 接口。

## 它暴露/定义了什么

该文件核心暴露 `GatewayClient` 类。它继承 `EventEmitter`，对外主要提供：

- `start()`：初始化 gateway 传输。默认拉起本地 Python 子进程；如果存在 `HERMES_TUI_GATEWAY_URL`，则改为 WebSocket attach 模式。
- `request<T>(method, params)`：发送 JSON-RPC 请求并返回 Promise，所有 TUI 到后端的 RPC 都走这里。
- `drain()`：开启事件订阅，并把启动早期缓存的事件一次性补发给 UI。
- `getLogTail(limit)`：取 gateway stderr、生命周期日志尾部，用于诊断启动失败、崩溃和 `/logs` 类场景。
- `kill(reason)`：关闭 transport、清理 sidecar socket、拒绝挂起请求。

文件还定义了一批内部工具：`resolvePython()` 负责选择 Python 解释器；`redactUrl()` 在日志中隐藏 token、query 和 user-info；`asWireText()` 处理 WebSocket 文本/二进制帧；`Pending` 描述未完成 RPC。

## 谁调用它

入口是 `ui-tui/src/entry.tsx`：启动 TUI 时创建 `const gw = new GatewayClient()`，立即调用 `gw.start()`，并在 graceful exit 时调用 `gw.kill()`。

上层应用通过 props 传递 `gw`。主要调用方包括：

- `ui-tui/src/app.tsx`、`ui-tui/src/app/useMainApp.ts`：监听 gateway 事件、维护整体会话和 UI 状态。
- `ui-tui/src/app/useSubmission.ts`：调用 `prompt.submit` 提交用户输入。
- `ui-tui/src/app/createSlashHandler.ts`：调用 `slash.exec`，失败时回退到 `command.dispatch`。
- `ui-tui/src/hooks/useCompletion.ts`：调用 `complete.slash`、`complete.path` 获取补全。
- `ui-tui/src/app/useConfigSync.ts`、`components/modelPicker.tsx`、`components/sessionPicker.tsx`、`components/agentsOverlay.tsx` 等：通过不同 RPC 读写配置、会话、模型和 agent 状态。
- `ui-tui/src/__tests__/gatewayClient.test.ts`：覆盖 attach、重连、超时、kill、日志等行为。

## 它调用谁

默认模式下，它通过 `node:child_process.spawn()` 执行 `python -m tui_gateway.entry`，并用 stdin/stdout 交换 newline-delimited JSON-RPC。`tui_gateway/entry.py` 启动后会先发 `gateway.ready`，随后从 stdin 读取请求并调度到 `tui_gateway/server.py`。

attach 模式下，它连接 `HERMES_TUI_GATEWAY_URL` 指向的 WebSocket。根据 `tui_gateway/ws.py`，WebSocket 传输与 stdio 使用同样 JSON-RPC 协议，并复用 `tui_gateway.server.dispatch`。如果设置 `HERMES_TUI_SIDECAR_URL`，客户端还会把 gateway 事件帧镜像到 sidecar WebSocket。

此外，它调用 `CircularBuffer` 保存有限日志和启动前事件，调用 `recordParentLifecycle()` 将父进程侧生命周期线索写入持久日志。

## 核心流程

启动流程分两条。`start()` 先解析源码根、attach URL、sidecar URL，然后 `resetStartupState()`：拒绝旧请求、清空 ready 状态、关闭 readline、清理启动定时器。接着关闭旧 WebSocket/sidecar，并根据 `HERMES_TUI_GATEWAY_URL` 选择 `startAttachedGateway()` 或 `startSpawnedGateway()`。

spawn 模式中，`startSpawnedGateway()` 选择 Python、设置 `PYTHONPATH`、启动 `tui_gateway.entry`。stdout 每行按 JSON 解析后进入 `dispatch()`；stderr 进入日志并发布 `gateway.stderr`。子进程 `error` 或 `exit` 会走 `handleTransportExit()`，清理 ready timer、关闭 sidecar、拒绝 pending RPC，并发出或缓存 `exit`。

attach 模式中，`startAttachedGateway()` 建立 WebSocket，message 帧经 `handleWebSocketFrame()` 解析。连接期间的 RPC 会等待 `wsConnectPromise`。close/error 同样会转换成日志、stderr 事件或 transport exit。

请求流程由 `request()` 统一处理：如果当前是 attach 模式，必要时重启 transport，再调用 `requestOverWebSocket()`；否则确保子进程可用，必要时自动 `start()`。每个请求分配 `rN` id，写入 JSON-RPC `{id,jsonrpc,method,params}`，并放入 `pending`。响应回来时 `dispatch()` 根据 id 找到 pending，通过 `settle()` resolve/reject。超时由 `REQUEST_TIMEOUT_MS` 控制，默认至少 30 秒，环境变量默认值为 120 秒。

事件流程中，后端发送 `{"method":"event","params":...}`。`dispatch()` 识别后交给 `publish()`。如果事件是 `gateway.ready`，客户端标记 ready 并清掉启动超时。UI 尚未调用 `drain()` 时，事件进入 `bufferedEvents`；订阅后再通过 `emit('event', ev)` 分发，避免 gateway 早于 React/Ink 监听器就绪时丢事件。

## 关键函数的高层作用

`start()` 是 transport 切换总入口，承担“旧连接收尾”和“新连接启动”的一致性控制。

`request()` 是最重要的业务入口。上层不需要知道当前使用 stdio 还是 WebSocket，也不需要管理 request id、超时和 pending map。

`dispatch()` 是协议入口，负责区分 RPC response 和 async event。它不处理业务语义，只做路由。

`publish()` 处理事件订阅时序，尤其是 `gateway.ready` 与 UI 初始化之间的竞态。

`handleTransportExit()` 把子进程退出、WebSocket close、启动错误统一成 pending rejection 和 `exit` 事件。

`ensureAttachedWebSocket()` 负责 attach 模式的懒重连和连接等待，是防止 WebSocket 尚未 open 时直接发送失败的关键。

`startReadyTimer()` 在 gateway 长时间未发 `gateway.ready` 时发布 `gateway.start_timeout`，并附带日志尾部，帮助 UI 展示“Python 错误、依赖缺失、配置解析失败”等启动问题。

`redactUrl()`、`truncateLine()`、`getLogTail()` 属于诊断与安全辅助：它们让日志可读，同时避免 token 泄漏或超长行撑爆界面。

## 修改风险

最大风险是破坏 JSON-RPC 兼容性。`tui_gateway/entry.py` 和 `tui_gateway/ws.py` 都假设请求/响应结构一致；改动 `id`、`method`、换行 framing、事件包装方式，会影响所有 TUI RPC。

第二类风险是生命周期竞态。文件里大量 identity guard 用于忽略旧子进程、旧 WebSocket 的迟到 `exit/close/error`。如果简化这些判断，可能出现新 gateway 被旧 transport 的事件误杀、pending 请求被错误拒绝、启动 timer 被错误清理等问题。

第三类风险是事件丢失。`gateway.ready` 可能早于 React hook 订阅；`bufferedEvents` 和 `drain()` 保证启动事件、早期 stderr、早期 exit 不丢。改动订阅时序时要特别验证自动恢复、session resume 和启动失败 UI。

第四类风险是挂起请求。`resetStartupState()`、`kill()`、`handleTransportExit()` 都显式 `rejectPending()`，避免 Promise 永久等待。新增 transport 或重连逻辑时必须保留这个不变量。

第五类风险是凭据泄漏。attach URL 和 sidecar URL 可能带 bearer token；任何新增日志都应经过 `redactUrl()` 或同等处理。

最后，`GatewayClient` 是 TUI 的共享基础设施，不只是聊天提交使用。补全、slash 命令、模型选择、会话管理、配置同步和审批流都依赖它。修改时应优先跑 `ui-tui/src/__tests__/gatewayClient.test.ts` 以及涉及 `createGatewayEventHandler`、`useSubmission`、`useCompletion` 的测试；根据当前片段推断，这些测试覆盖了多数传输和事件边界。
