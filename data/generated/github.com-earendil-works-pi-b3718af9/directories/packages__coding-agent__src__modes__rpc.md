# 子系统：packages/coding-agent/src/modes/rpc

## 解决什么问题

`packages/coding-agent/src/modes/rpc` 提供 coding-agent 的无界面、可嵌入运行模式。它把原本面向终端交互的 agent 会话能力包装成基于 stdin/stdout 的 JSONL 协议：外部程序向 stdin 写入一行 JSON 命令，agent 在 stdout 持续输出事件、扩展 UI 请求和命令响应。

它解决的核心问题是“让其他 Node 程序或宿主应用以进程方式控制 coding-agent”。相比 `interactive` 模式依赖 TUI、`print` 模式偏一次性执行，`rpc` 模式适合长期会话、流式事件监听、模型切换、上下文压缩、执行 bash、切换/克隆 session、枚举 slash command 等程序化场景。

这个目录不是业务智能本身，而是协议适配层：真正的会话、模型、工具、扩展、持久化仍由 `core` 层承担；`rpc` 负责把这些能力映射为稳定的命令、响应和事件格式。

## 相关目录和文件

`packages/coding-agent/src/modes/rpc/rpc-mode.ts` 是服务端入口，导出 `runRpcMode(runtimeHost)`，负责接管 stdout、绑定当前 `AgentSession`、读取 stdin JSONL、分发命令、输出事件和响应。

`packages/coding-agent/src/modes/rpc/rpc-client.ts` 是客户端封装，`RpcClient` 会 spawn 一个 `node dist/cli.js --mode rpc` 子进程，并提供 `prompt()`、`getState()`、`setModel()`、`bash()`、`clone()` 等 typed API。

`packages/coding-agent/src/modes/rpc/rpc-types.ts` 定义协议面，包括 `RpcCommand`、`RpcResponse`、`RpcSessionState`、`RpcExtensionUIRequest`、`RpcExtensionUIResponse`、`RpcSlashCommand`。

`packages/coding-agent/src/modes/rpc/jsonl.ts` 负责严格 JSONL framing：序列化时每条 JSON 后追加 `\n`，读取时只按 LF 拆行，不使用 Node `readline`，避免合法 JSON 字符串里的 Unicode 行分隔符被误拆。

邻近入口主要在 `packages/coding-agent/src/main.ts` 和 `packages/coding-agent/src/cli/args.ts`：CLI 参数支持 `--mode rpc`，主流程检测到该模式后调用 `runRpcMode(runtime)`。`packages/coding-agent/src/modes/index.ts` 和 `packages/coding-agent/src/index.ts` 对外重新导出 RPC client、mode 和类型。

测试分布在 `packages/coding-agent/test/rpc.test.ts`、`rpc-client-process-exit.test.ts`、`rpc-client-clone.test.ts`、`rpc-jsonl.test.ts`、`rpc-prompt-response-semantics.test.ts`，覆盖协议、进程退出、JSONL 边界和 prompt 响应语义。

## 核心对象

`RpcCommand` 是输入协议的中心。它按功能分组：提示类命令包括 `prompt`、`steer`、`follow_up`、`abort`、`new_session`；状态和模型类包括 `get_state`、`set_model`、`cycle_model`、`get_available_models`；会话类包括 `switch_session`、`fork`、`clone`、`get_messages`、`get_last_assistant_text`；还包括压缩、自动重试、bash、slash command 枚举等能力。多数命令带可选 `id`，用于客户端关联响应。

`RpcResponse` 是命令结果。成功响应包含 `type: "response"`、`command`、`success: true`，有些命令额外带 `data`；失败响应统一为 `success: false` 和 `error`。注意 agent 运行中的流式输出不是 `RpcResponse`，而是直接转发 `AgentSession` 事件。

`RpcClient` 是进程级 SDK。它维护 `pendingRequests`，为每次请求生成 `req_N` id，写入 JSONL 到子进程 stdin，并在 stdout 中匹配同 id 的 `response`。未匹配为 response 的 JSON 会被当作 `AgentEvent` 广播给 `onEvent()` 监听器。

`runRpcMode` 是服务端调度器。它持有当前 `session`，并在 `new_session`、`switch_session`、`fork`、`clone` 后调用 `rebindSession()`，重新绑定扩展、事件订阅和 backpressure 处理。

`ExtensionUIContext` 的 RPC 实现也在 `rpc-mode.ts` 中。扩展调用 `select`、`confirm`、`input`、`editor` 等 UI 能力时，RPC 模式输出 `extension_ui_request`；宿主随后发送 `extension_ui_response` 回来。部分 TUI 专属能力，如自定义 footer/header、theme switching、terminal input、working indicator，在 RPC 模式中被降级为空实现或返回不支持。

## 运行流程

外部调用 `RpcClient.start()` 时，客户端启动 `node dist/cli.js --mode rpc`，可追加 `--provider`、`--model` 和自定义 args。子进程 stdout 由 `attachJsonlLineReader()` 解析，stderr 被收集并转发，方便错误诊断。

CLI 主流程解析到 `mode === "rpc"` 后构建 `AgentSessionRuntime`，调用 `runRpcMode(runtime)`。RPC 模式先 `takeOverStdout()`，确保 stdout 只输出协议 JSONL；普通日志或调试输出不应污染 stdout。随后它创建 `output()` 方法，用 `serializeJsonLine()` 写 raw stdout。

启动时 `rebindSession()` 会绑定扩展上下文，注册 `commandContextActions`，并订阅 session 事件。任何 agent 事件都会直接 `output(event)`。同时它订阅 agent 侧通知，在必要时等待 raw stdout backpressure，避免高速输出时丢失或乱序。

stdin 每读到一行，先 JSON.parse。解析失败会输出 `command: "parse"` 的错误响应。如果对象是 `extension_ui_response`，就从 `pendingExtensionRequests` 找对应等待者并 resolve。否则按 `RpcCommand` 进入 `handleCommand()`。

大部分命令是同步等待核心 session 方法完成后返回响应，例如 `get_state`、`set_model`、`compact`、`bash`、`export_html`。`prompt` 比较特殊：它会立即启动 `session.prompt()`，但只有 preflight 成功后才输出成功响应；后续模型流式内容通过 session event 输出，客户端通常配合 `waitForIdle()` 或 `collectEvents()` 等待 `agent_end`。

进程关闭由 stdin end、扩展 shutdown handler 或 SIGTERM/SIGHUP 触发。关闭时会取消订阅、dispose runtime、暂停 stdin，并在非 SIGTERM 情况下 flush stdout。信号处理还会调用 `killTrackedDetachedChildren()` 清理被跟踪的 detached 子进程。

## 上下游依赖

上游入口是 CLI 参数和主流程：`packages/coding-agent/src/cli/args.ts` 允许 `--mode rpc`，`packages/coding-agent/src/main.ts` 负责模式路由。对外 API 通过 `packages/coding-agent/src/modes/index.ts` 和 `packages/coding-agent/src/index.ts` 暴露。

核心下游是 `AgentSessionRuntime` 与 `AgentSession`。RPC 命令最终调用 session 的 `prompt`、`steer`、`followUp`、`compact`、`executeBash`、`exportToHtml`、`setModel`、`cycleModel`、`switchSession`、`fork` 等能力。模型数据来自 `session.modelRegistry`，消息与分支信息来自 session 和 `sessionManager`，slash command 列表来自 `extensionRunner`、`promptTemplates`、`resourceLoader.getSkills()`。

外部类型依赖包括 `@earendil-works/pi-agent-core` 的 `AgentEvent`、`AgentMessage`、`ThinkingLevel`，以及 `@earendil-works/pi-ai` 的 `ImageContent`、`Model`。底层 Node API 使用 `child_process.spawn`、`stream.Readable`、`StringDecoder`、`crypto.randomUUID` 和进程信号。

## 修改时最容易踩的坑

第一，stdout 必须保持协议纯净。RPC 模式用 `takeOverStdout()`、`writeRawStdout()`、`flushRawStdout()` 是为了保证 stdout 只出现 JSONL。调试输出、扩展日志或启动噪声如果写到 stdout，会破坏客户端解析；这类内容应走 stderr 或受 output guard 管理。

第二，JSONL 只能按 `\n` 拆行。`jsonl.ts` 明确不使用 `readline`，因为 JSON 字符串内部可能含有其他 Unicode 分隔符。修改 framing 时要同步考虑 `rpc-jsonl.test.ts`。

第三，新增命令要同时改三处：`RpcCommand` 输入类型、`RpcResponse` 输出类型、`runRpcMode()` 的 `handleCommand()`；如果要暴露 SDK，还要在 `RpcClient` 加方法。漏掉任一处都会造成类型表面完整但运行不可用。

第四，`prompt` 的响应语义不同于普通命令。它不是等整个 agent 完成才返回，而是在 preflight 成功后响应，真正输出通过事件流传递。客户端等待完成应看 `agent_end`，不是只等 `prompt()` promise。

第五，session 变更后必须重新绑定。`new_session`、`switch_session`、`fork`、`clone` 都可能替换当前 session；如果忘记 `rebindSession()`，事件订阅、扩展上下文和后续命令会指向旧 session。

第六，扩展 UI 在 RPC 模式不是完整 TUI。新增扩展 UI 能力时，要明确它是否能通过 JSON request/response 表达；不能表达的功能应保持降级行为，而不是假装支持。

第七，客户端要处理子进程异常。`RpcClient` 会收集 stderr、在 exit/error/stdin error 时 reject pending requests；新增长耗时命令或新事件类型时，不要绕开 `pendingRequests` 和超时机制。

## 推荐阅读顺序

1. 先读 `packages/coding-agent/src/modes/rpc/rpc-types.ts`，建立协议词汇表：有哪些命令、响应、扩展 UI 消息和 session state。
2. 再读 `packages/coding-agent/src/modes/rpc/jsonl.ts`，理解为什么 RPC 协议是一行一个 JSON，以及严格 LF framing 的边界。
3. 接着读 `packages/coding-agent/src/modes/rpc/rpc-mode.ts`，重点看 `runRpcMode()`、`rebindSession()`、`handleCommand()`、`handleInputLine()` 和 shutdown 逻辑。
4. 然后读 `packages/coding-agent/src/modes/rpc/rpc-client.ts`，理解外部程序如何启动子进程、发送命令、匹配响应、监听事件。
5. 最后补看 `packages/coding-agent/src/main.ts` 的 mode routing、`packages/coding-agent/src/modes/index.ts` 的导出，以及 `packages/coding-agent/test/rpc*.test.ts` 中对协议行为的约束。
