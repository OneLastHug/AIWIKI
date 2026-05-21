# 目录：`src/server/services/agentRuntime`

## 它负责什么

这个目录是服务端“Agent 运行时编排层”。它不直接实现模型推理，而是把一次 Agent 运行拆成可管理的服务流程：创建 operation、推进 step、处理中断、接入人工介入、记录 trace、派发 hooks、以及在队列/同步模式之间切换。

从代码上看，核心入口是 [`AgentRuntimeService.ts`](./src/server/services/agentRuntime/AgentRuntimeService.ts)，它把 `@lobechat/agent-runtime` 的通用运行时，和仓库内的数据库、队列、消息模型、tool 执行、Agent Signal、tracing 这些服务串起来。`index.ts` 只是做导出聚合。

## 关键组成

- [`AgentRuntimeService.ts`](./src/server/services/agentRuntime/AgentRuntimeService.ts)：主编排器。负责 `createOperation`、`executeStep`、`startExecution`、`processHumanIntervention`、`executeSync`、`interruptOperation` 等。
- [`CompletionLifecycle.ts`](./src/server/services/agentRuntime/CompletionLifecycle.ts)：负责 operation 的开始/结束持久化和完成态收口。根据代码注释，它掌管 `agent_operations` 的起止记录，并在终态时触发 signal/hook 收尾。
- [`HumanInterventionHandler.ts`](./src/server/services/agentRuntime/HumanInterventionHandler.ts)：处理 `approve / reject / input / select` 这类人工介入，把用户决策折回到下一步上下文。
- [`OperationTraceRecorder.ts`](./src/server/services/agentRuntime/OperationTraceRecorder.ts)：负责运行过程的 snapshot/trace 记录，和 `ISnapshotStore` 对接。
- [`AbandonOperationService.ts`](./src/server/services/agentRuntime/AbandonOperationService.ts)` + `[`abort.ts`](./src/server/services/agentRuntime/abort.ts)：处理终止/中断语义。
- [`stepPresentation.ts`](./src/server/services/agentRuntime/stepPresentation.ts)：把 stepResult 整理成可展示、可日志化的摘要数据。
- [`hooks/`](./src/server/services/agentRuntime/hooks)：外部 lifecycle hook 系统。`HookDispatcher` 负责本地派发，`types.ts` 定义 hook 事件和 webhook 序列化结构。
- `types.ts`：定义运行参数、operation 状态、step 生命周期回调、completion reason、tool set 等核心类型。

## 上下游关系

上游输入主要来自三类地方：

1. 调用方构造 `OperationCreationParams`，把 `agentConfig`、`modelRuntimeConfig`、`toolSet`、`initialContext`、`appContext` 这些运行信息传进来。
2. 队列/worker 驱动 step 推进。`startExecution()` 会把执行请求交给 `QueueService`，最后打到 `.../api/agent/run`。
3. 人工介入和外部回调。`processHumanIntervention()` 把审批/输入/拒绝信息重新排队，`executeStep()` 会在 step 边界合并这些信息。

下游则是它调用的基础设施：

- `AgentRuntimeCoordinator` 和 `createStreamEventManager()`：管理 operation state、step lock、stream event。
- `ToolExecutionService` / `BuiltinToolsExecutor` / `mcpService`：真正执行工具调用。
- `MessageModel`：从消息表中回查 device 上下文。
- `emitAgentSignalSourceEvent()` / `toAgentSignalTraceEvents()`：把运行事件转成 Agent Signal trace。
- `hookDispatcher`：触发本地 hook 或序列化后的 webhook。
- `@lobechat/agent-runtime` 里的 `AgentRuntime`、`GeneralChatAgent`、`findInMessages`：承担通用运行时和消息遍历能力。

根据当前片段推断，这个目录是 `src/server/modules/AgentRuntime` 之上的业务服务层，下一层才是通用 runtime 和具体 executor。

## 运行/调用流程

1. `createOperation()` 先写入 operation 起始记录，再初始化 `AgentState`，把 `metadata`、`toolSet`、`userMemory`、`appContext` 等塞进去。
2. 如果配置了外部 hooks，就通过 `hookDispatcher.register()` 注册，并把可序列化部分写回 state metadata。
3. 如果 `autoStart` 为真，进入 `startExecution()`：更新状态为 `running`，然后通过 `QueueService` 调度 `/api/agent/run`。
4. worker 进到 `executeStep()` 后，先抢分布式锁，避免重复 step。
5. 读取最新 state，先跑 `beforeStep` signal/hook，再通过 `createAgentRuntime()` 构造 `Agent` 和 `AgentRuntime`。
6. 如有人工介入参数，交给 `HumanInterventionHandler` 合并进当前 state/context。
7. 必要时从数据库消息里补 device context，然后执行 `runtime.step()`。
8. step 结束后保存结果、生成 step presentation、发 `step_complete` 事件、记录 trace，最后由 `CompletionLifecycle` 决定是否进入终态收口。
9. `executeSync()` 则是绕过队列，循环调用 `executeStep()`，适合测试或同步执行场景。

## 小白阅读顺序

1. 先看 [`index.ts`](./src/server/services/agentRuntime/index.ts)，确认这个目录对外导出了什么。
2. 再看 [`types.ts`](./src/server/services/agentRuntime/types.ts)，把参数、状态、completion reason 这些名词看懂。
3. 接着读 [`AgentRuntimeService.ts`](./src/server/services/agentRuntime/AgentRuntimeService.ts) 的 `createOperation()`、`startExecution()`、`executeStep()`、`executeSync()`，这是主线。
4. 然后补 [`CompletionLifecycle.ts`](./src/server/services/agentRuntime/CompletionLifecycle.ts) 和 [`HumanInterventionHandler.ts`](./src/server/services/agentRuntime/HumanInterventionHandler.ts)，理解收尾和人工介入。
5. 最后看 [`hooks/types.ts`](./src/server/services/agentRuntime/hooks/types.ts) 与 [`hooks/HookDispatcher.ts`](./src/server/services/agentRuntime/hooks/HookDispatcher.ts)，理解外部扩展点。

## 常见误区

- 把这个目录当成“模型实现层”。它其实是调度和编排层，真正的推理在 `@lobechat/agent-runtime`。
- 只看 `createOperation()` 不看 `executeStep()`。前者只是建档，后者才是一次运行的核心。
- 忽略队列语义。这里同时支持异步队列和 `executeSync()`，两条路径的状态推进方式不一样。
- 只关注 LLM，不关注人工介入。`waiting_for_human` 是一条明确的终态分支，不是异常分支。
- 忽略 hooks 和 signal。这个目录对外扩展很多，运行时事件不是只给日志看的，还会进入 webhook、trace 和 agent signal 体系。
- 误以为 `stepPresentation.ts` 只是展示层。它其实也在统一日志摘要、token/cost 统计和 step 结果语义。
