# 文件：packages/agent/src/agent-loop.ts

## 一句话定位

`packages/agent/src/agent-loop.ts` 是 `packages/agent` 的底层 agent 执行循环：它把用户消息、LLM 流式响应、工具调用、工具结果、插队消息和停止条件串成一个可事件化消费的运行过程。

## 它暴露/定义了什么

这个文件主要导出 5 个公开 API：

- `AgentEventSink`：事件接收函数类型，用于把 `AgentEvent` 推给上层。
- `agentLoop()`：面向事件流消费者的入口，会把新 prompt 加入上下文，并返回 `EventStream<AgentEvent, AgentMessage[]>`。
- `agentLoopContinue()`：继续已有上下文的事件流入口，常用于 retry 或已有 user/toolResult 后继续运行。
- `runAgentLoop()`：`async` 版本的新 prompt 运行入口，上层传入 `emit` 回调接收事件。
- `runAgentLoopContinue()`：`async` 版本的 continuation 入口。

文件内部还定义了核心私有流程函数 `runLoop()`、`streamAssistantResponse()`、`executeToolCalls()` 及一组工具调用准备、执行、收尾和事件发送辅助函数。

## 谁调用它

直接调用者主要在 `packages/agent` 内部：

- `packages/agent/src/agent.ts` 的 `Agent` 类调用 `runAgentLoop()` 处理新 prompt，调用 `runAgentLoopContinue()` 处理继续执行。
- `packages/agent/src/harness/agent-harness.ts` 的 `AgentHarness` 直接调用 `runAgentLoop()`，用于测试/脚手架式运行。
- `packages/agent/src/index.ts` 重新导出本文件，因此包外用户也可以通过 `@earendil-works/pi-agent` 的公开入口使用这些循环 API。
- `packages/agent/test/agent-loop.test.ts` 直接测试 `agentLoop()`、`agentLoopContinue()` 的事件流行为。

根据当前片段推断，生产主路径更偏向 `Agent` 类封装；`agentLoop()` 这种直接返回 `EventStream` 的 API 更适合库消费者或测试场景。

## 它调用谁

它依赖 `@earendil-works/pi-ai` 提供的基础能力：

- `EventStream`：包装 agent 事件流和最终结果。
- `streamSimple`：默认 LLM 流式调用函数。
- `validateToolArguments`：按工具 schema 校验 LLM 生成的工具参数。
- `Context`、`AssistantMessage`、`ToolResultMessage` 等消息类型。

它还通过 `AgentLoopConfig` 调用上层注入的扩展点，包括 `convertToLlm`、`transformContext`、`getApiKey`、`shouldStopAfterTurn`、`prepareNextTurn`、`getSteeringMessages`、`getFollowUpMessages`、`beforeToolCall`、`afterToolCall`。工具执行本身调用 `AgentTool.execute()`，并通过工具的 update callback 转成 `tool_execution_update` 事件。

## 核心流程

新 prompt 路径从 `runAgentLoop()` 开始：复制 prompt 到 `newMessages`，构造追加了 prompt 的 `currentContext`，依次发出 `agent_start`、`turn_start`、prompt 的 `message_start/message_end`，然后进入 `runLoop()`。

`runLoop()` 是真正的调度器。它有外层循环和内层循环：内层循环负责“有工具调用或有 steering message 时继续下一轮”；外层循环负责“agent 本来要停下时，再检查 follow-up queue”。每一轮会先注入 `getSteeringMessages()` 得到的消息，再调用 `streamAssistantResponse()` 生成 assistant 消息。若 assistant 的 `stopReason` 是 `error` 或 `aborted`，直接发 `turn_end` 和 `agent_end` 结束。

如果 assistant 消息里有 `toolCall`，`executeToolCalls()` 会按配置选择串行或并行执行。执行结果转成 `toolResult` 消息，追加到 `currentContext.messages` 和 `newMessages`，再发 `turn_end`。之后 `prepareNextTurn()` 可替换下一轮上下文、模型或 thinking level；`shouldStopAfterTurn()` 可优雅结束；否则继续拉取 steering/follow-up 消息决定是否再请求 LLM。

## 关键函数的高层作用

`agentLoop()` 和 `agentLoopContinue()` 是事件流包装层：创建 `EventStream`，异步调用对应 `run*` 函数，把每个事件 `push` 出去，并在完成时 `end(messages)`。

`runAgentLoop()` 和 `runAgentLoopContinue()` 是可 await 的低层入口：它们只负责初始化新消息集合、做 continuation 合法性检查、发启动事件，然后委托给 `runLoop()`。

`runLoop()` 是文件的中心状态机，维护 `currentContext`、当前 `config`、`pendingMessages`、工具调用循环和退出条件。它决定什么时候向 LLM 发请求、什么时候执行工具、什么时候插入用户中途输入、什么时候结束 agent。

`streamAssistantResponse()` 是 LLM 边界层：先可选执行 `transformContext()`，再用 `convertToLlm()` 把 `AgentMessage[]` 转成 provider 可理解的消息，构造 `Context`，动态解析 API key，然后消费 `streamSimple` 或自定义 `streamFn` 的事件。它会把 partial assistant message 放入上下文，并随着 text/thinking/toolcall delta 更新上下文最后一条消息。

`executeToolCalls()` 是工具调度入口：如果全局 `toolExecution` 是 `sequential`，或任一工具声明 `executionMode: "sequential"`，就走串行；否则并行执行。串行模式逐个工具准备、执行、收尾、发结果；并行模式先准备所有可执行工具，再 `Promise.all`，但最终仍按原工具调用顺序发 `toolResult` 消息。

`prepareToolCall()` 负责查找工具、应用 `prepareArguments()`、校验参数、执行 `beforeToolCall()` 阻断逻辑和 abort 检查。`executePreparedToolCall()` 只负责调用工具并收集 update 事件。`finalizeExecutedToolCall()` 允许 `afterToolCall()` 修改工具结果、错误标记或 `terminate`。其他如 `createErrorToolResult()`、`createToolResultMessage()`、`emitToolResultMessage()` 都是结果和事件包装辅助函数。

## 修改风险

最高风险是事件顺序。上层 `Agent`、harness 和测试很可能依赖 `agent_start`、`turn_start`、`message_start/update/end`、`tool_execution_*`、`turn_end`、`agent_end` 的顺序；调整任一 emit 时机都可能破坏 UI 状态机、日志回放或测试断言。

第二个风险是上下文变异。`streamAssistantResponse()` 会把 partial assistant message 先 push 到 `context.messages`，再不断替换最后一条；工具结果也会追加到 `currentContext.messages`。如果改成不可变结构或改变追加时机，`prepareNextTurn()`、`convertToLlm()` 和后续工具调用看到的上下文都会变化。

第三个风险是工具并发语义。并行执行虽然并发调用工具，但结果消息按原顺序发出；串行工具或全局串行配置会改变副作用顺序。改动 `executeToolCallsParallel()`、`shouldTerminateToolBatch()` 或 abort 处理，可能影响具有副作用的工具、终止工具和用户取消行为。

第四个风险是配置回调契约。`convertToLlm`、`transformContext`、`shouldStopAfterTurn` 等注释要求“不应 throw”，但本文件没有全面兜底；若在这里新增抛错路径，可能导致没有正常 `agent_end` 事件。修改时应补充 `packages/agent/test/agent-loop.test.ts` 中覆盖事件顺序、工具错误、abort、steering/follow-up、prepareNextTurn 和 continuation 的测试。
