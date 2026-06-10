# 文件：packages/agent/src/agent.ts

## 一句话定位
`packages/agent/src/agent.ts` 定义了一个带状态的 `Agent` 封装类，它把低层的模型流式调用、工具执行、事件分发、消息队列和运行态管理串成一个可复用的上层接口。根据当前片段推断，它是 `@earendil-works/pi-agent` 这一层最核心的编排入口。

## 它暴露/定义了什么
这个文件主要暴露 `Agent` 类，以及 `AgentOptions` 配置类型，并转出 `QueueMode`。类本身保存当前 transcript、模型、thinking 配置、工具列表、会话标识和运行中的 abort 信号，还内置了 steering/follow-up 两个消息队列。内部还定义了 `PendingMessageQueue`、`createMutableAgentState`、`defaultConvertToLlm`、`EMPTY_USAGE`、`DEFAULT_MODEL` 等支撑结构，但它们都是为了支撑 `Agent` 的生命周期。

## 谁调用它
从仓库引用看，调用者主要是上层应用和测试：`packages/agent/src/index.ts` 直接导出它；`packages/coding-agent/src/core/sdk.ts` 会 `new Agent(...)`；`packages/coding-agent` 的测试、e2e 和 README 示例也都以它为入口。换句话说，外部通常不会直接碰 `agent-loop.ts`，而是通过 `Agent` 的 `prompt()`、`continue()`、`steer()`、`followUp()` 等方法驱动它。

## 它调用谁
`Agent` 的核心执行依赖 `./agent-loop.ts` 里的 `runAgentLoop` 和 `runAgentLoopContinue`，真正的模型流式请求默认走 `@earendil-works/pi-ai` 的 `streamSimple`。它还把大量配置透传给 `AgentLoopConfig`：例如 `convertToLlm`、`transformContext`、`beforeToolCall`、`afterToolCall`、`prepareNextTurn`、`getApiKey`、`thinkingBudgets`、`transport` 等。事件和状态类型来自 `./types.ts`。

## 核心流程
1. 构造时把初始 state 拷贝进可变状态对象，并初始化两个队列。
2. `prompt()` 先做输入归一化，再通过 `runWithLifecycle()` 包一层运行壳，调用 `runAgentLoop()` 开始新一轮对话。
3. `continue()` 则在已有 transcript 基础上决定是先消费 steering 队列、follow-up 队列，还是直接调用 `runAgentLoopContinue()`。
4. `runWithLifecycle()` 负责创建 `AbortController`、标记 `isStreaming`、处理异常、最后统一 `finishRun()`。
5. `processEvents()` 是状态同步核心：把 `message_start / update / end`、`tool_execution_start / end`、`turn_end`、`agent_end` 转成内部 state 变化，同时同步通知所有订阅者。
6. 出错时 `handleRunFailure()` 会伪造一条带 `errorMessage` 的 assistant 消息，把失败也包装成完整事件序列，避免调用方只看到“中断”而没有收尾。

## 关键函数的高层作用
`prompt()` 和 `continue()` 是对外主入口；`runPromptMessages()`、`runContinuation()` 只是分别包住两种 loop 启动方式。`createLoopConfig()` 决定每一轮请求要带哪些上下文、队列策略和钩子。`processEvents()` 是这个类最关键的状态机函数，决定 transcript、streamingMessage、pendingToolCalls、errorMessage 如何变化。`subscribe()` 则提供生命周期观察点，适合 TUI、日志和会话管理层挂监听。

## 修改风险
这个文件的改动风险很高，因为它处在“上层 API”和“底层 loop”之间。最容易出问题的点有：事件顺序一旦变了，订阅者和 UI 会错乱；`finishRun()`、`activeRun` 和 abort 处理如果不一致，会出现卡住或重复运行；队列 drain 逻辑一旦改动，会直接影响 steering/follow-up 的语义；`createMutableAgentState()` 如果不再做浅拷贝，外部传入数组可能被意外共享。根据当前片段推断，任何看似局部的改动都可能影响整个 agent 会话语义，最好把回归重点放在 `prompt()`、`continue()`、异常收尾和事件监听顺序上。
