# 文件：packages/coding-agent/src/modes/rpc/rpc-mode.ts
## 一句话定位
这是 `coding-agent` 的 RPC 运行模式入口，负责把 `AgentSessionRuntime` 包装成一套基于 stdin/stdout 的 JSON 协议服务，让外部程序可以用命令驱动会话、接收事件，并通过 RPC 方式交互扩展 UI。根据当前片段推断，它属于模式分发层中的一个执行器：当进程以 `rpc` 模式启动时由上层入口调用。

## 它暴露/定义了什么
这个文件主要暴露一个核心函数 `runRpcMode(runtimeHost)`，返回 `Promise<never>`，说明它会接管进程并长期驻留，不会正常返回。除此之外，它还从 `rpc-types.ts` 重新导出了一组 RPC 协议类型，包括 `RpcCommand`、`RpcResponse`、`RpcSessionState`、`RpcExtensionUIRequest`、`RpcExtensionUIResponse` 等，供外部或其他模块复用协议定义。

## 谁调用它
根据当前片段推断，调用者是 `coding-agent` 的上层模式入口或 CLI 启动分发逻辑，也就是在选择 `rpc` 模式时把当前 `AgentSessionRuntime` 传进来。这个文件本身不负责决定何时进入 RPC 模式，只负责一旦进入就把会话变成可被外部协议控制的服务端。

## 它调用谁
它直接依赖并驱动 `AgentSessionRuntime`、当前 `session` 以及 session 上的一系列能力：`prompt`、`steer`、`followUp`、`abort`、`setModel`、`compact`、`executeBash`、`exportToHtml`、`switchSession`、`fork` 等。它还调用 `output-guard.ts` 里的 `takeOverStdout`、`writeRawStdout`、`flushRawStdout`、`waitForRawStdoutBackpressure` 来保证 stdout 只输出协议数据；调用 `attachJsonlLineReader`、`serializeJsonLine` 来读写 JSONL；调用 `killTrackedDetachedChildren` 处理退出时的子进程清理。扩展 UI 则通过 `createExtensionUIContext()` 提供给 `session.bindExtensions()`。

## 核心流程
它的主流程是三段式。

第一段是启动和绑定：`takeOverStdout()` 先接管标准输出，随后 `rebindSession()` 把当前 `session` 绑定成 RPC 模式，并注入一套 `uiContext`、`commandContextActions`、`shutdownHandler`、`onError`。这里同时订阅 session 事件流，把事件原样通过 `output()` 写到 stdout；还订阅 agent 的 backpressure 信号，避免输出堆积。

第二段是命令循环：`attachJsonlLineReader(process.stdin, ...)` 持续读取一行一个 JSON 的输入，`handleInputLine()` 先解析输入，再区分两类数据。若是 `extension_ui_response`，就找到 `pendingExtensionRequests` 中对应请求并完成 Promise；若是普通 `RpcCommand`，则交给 `handleCommand()` 分发。`handleCommand()` 按 `command.type` 处理所有 RPC 操作：提示词提交、模型切换、思考等级、compaction、bash、session 导航、消息读取、命令列表查询等，并统一用 `success()` / `error()` 回传结构化响应。

第三段是退出收尾：它注册 `SIGTERM` 和非 Windows 下的 `SIGHUP`，收到信号后先杀掉托管的 detached 子进程，再走 `shutdown()`。`shutdown()` 会取消订阅、释放 runtime、暂停 stdin、必要时 flush stdout，然后 `process.exit()`。stdin 结束时也会触发同样的退出流程。

## 关键函数的高层作用
`runRpcMode()` 是总入口，负责把运行时变成 RPC 服务。`rebindSession()` 是状态重连点，任何新会话、切换会话、fork 之后都要重新绑定事件和 UI 上下文，否则外部看到的事件会错位。`handleCommand()` 是协议路由器，决定每个命令如何映射到 session 能力。`createExtensionUIContext()` 则是 RPC 模式下的 UI 适配层，把对话框、通知、标题、编辑器等交互翻译成 `extension_ui_request` 消息。`createDialogPromise()` 是其中最关键的辅助逻辑，负责把带 timeout / abort signal 的交互请求包装成 Promise，并在收到对应 `extension_ui_response` 后完成解析。

## 修改风险
这个文件是协议边界，改动风险高。最主要的风险是 RPC 协议不兼容：一旦 `RpcCommand`、响应字段、`extension_ui_request` 事件格式变化，外部集成方会直接失效。其次是 stdout 污染风险，这里假设 stdout 只承载 JSONL，如果混入调试日志或非协议输出，客户端就会解析失败。第三是状态重绑定风险：`new_session`、`switch_session`、`fork` 后必须及时 `rebindSession()`，否则事件订阅、UI 上下文和当前会话会错配。第四是并发和清理风险：`pendingExtensionRequests`、信号清理、backpressure 处理如果漏掉，容易出现悬挂 Promise、卡住退出或重复响应。修改时应优先保持命令名、响应结构、退出语义和事件顺序稳定。
