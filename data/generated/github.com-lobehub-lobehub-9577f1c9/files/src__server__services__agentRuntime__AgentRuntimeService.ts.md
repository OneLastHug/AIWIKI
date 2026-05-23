# 文件：src/server/services/agentRuntime/AgentRuntimeService.ts

## 一句话定位

`AgentRuntimeService` 是服务端 Agent 任务执行的总编排入口：它把一次 Agent 运行抽象成 `operation`，负责创建运行状态、按 step 调度执行、处理人工介入/中断、触发 hooks、写入 trace，并在完成或失败时收尾通知。

## 它暴露/定义了什么

文件主要定义了 `AgentRuntimeServiceOptions` 和 `AgentRuntimeService`。`AgentRuntimeServiceOptions` 支持注入 `agentFactory`、`coordinatorOptions`、`execSubAgentTask`、`queueService`、`snapshotStore`、`streamEventManager`，说明这个类既用于生产运行，也明显服务于测试和替代运行时实现。

`AgentRuntimeService` 对外的核心能力包括：`createOperation` 创建任务、`executeStep` 执行单个 step、`interruptOperation` 中断任务、`startExecution` 手动启动任务、`executeSync` 同步执行、`getOperationStatus` 查询状态、`getPendingInterventions` 查询待处理人工介入、`processHumanIntervention` 处理人工输入或工具审批。后几个函数名称来自同文件调用关系和外部路由调用，根据当前片段推断其具体实现位于文件后半段。

## 谁调用它

主要调用方有三类。

第一类是业务服务 `src/server/services/aiAgent/index.ts`。`AiAgentService` 在构造时持有 `AgentRuntimeService`，在 `execAgent` 流程末尾调用 `createOperation` 创建并启动 Agent 任务，在取消任务时调用 `interruptOperation`。

第二类是 API/router 层 `src/server/routers/lambda/aiAgent.ts`。它把前端或客户端请求转发为运行时操作，例如 `getOperationStatus`、`getPendingInterventions`、`processHumanIntervention`、`startExecution`。

第三类是异步执行入口和兼容入口，例如 `src/server/agent-hono/handlers/runStep.ts` 会实例化服务并调用 `executeStep`，OpenAPI responses 服务和评测服务也会直接创建它，用于同步执行、评测运行或中断评测任务。

## 它调用谁

它向下调用的核心模块包括 `@lobechat/agent-runtime` 的 `AgentRuntime`、`GeneralChatAgent`，这是实际执行 Agent step 的运行时；`AgentRuntimeCoordinator` 管理 operation 状态、分布式 step lock、状态保存和事件；`QueueService` 负责把下一步投递到本地队列或 QStash 风格的 HTTP 队列；`ToolExecutionService`、`BuiltinToolsExecutor`、`mcpService` 负责工具执行；`CompletionLifecycle` 负责开始/完成生命周期持久化、完成 hooks 和 signal；`HumanInterventionHandler` 负责人工介入状态变换；`OperationTraceRecorder` 负责写 agent tracing snapshot；`hookDispatcher` 和 `emitAgentSignalSourceEvent` 负责 runtime hooks 与 Agent Signal 事件。

它还使用 `MessageModel` 和数据库连接读取/补充消息相关上下文，例如设备上下文；使用 `dynamicInterventionAudits`、`getModelPropertyWithFallback`、`createRuntimeExecutors` 等辅助运行时配置。

## 核心流程

创建阶段由 `createOperation` 完成。它先通过 `CompletionLifecycle.recordStart` 记录 operation 起点，再组装初始 `AgentState`：包含初始消息、模型配置、工具集合、app 上下文、设备信息、用户记忆、队列重试参数、最大 step 数等。随后调用 `coordinator.createAgentOperation` 和 `saveAgentState` 保存状态；如果传入 hooks，会注册到 `hookDispatcher` 并序列化进 state metadata。若 `autoStart` 为真且有 `queueService`，它会调度第一个 step 到 `${baseURL}/run`。

执行阶段由 `executeStep` 负责。它先用 `coordinator.tryClaimStep` 获取分布式锁，避免 QStash 重试或多实例重复执行同一步；然后发布 `step_start` 流事件，读取 `AgentState`，对已完成 step、终态 operation 做早退出。正式运行前会触发 `runtime.before_step` signal 和 `beforeStep` hook，创建 `AgentRuntime`，处理人工输入或工具审批，必要时从历史消息计算设备上下文。核心执行点是 `runtime.step(currentState, currentContext)`。

step 完成后，服务会再次检查是否被中断，将结果保存到 coordinator，构造 step 展示摘要，触发 `runtime.after_step` signal 和 `afterStep` hook，追加 trace snapshot。随后根据 `shouldContinueExecution` 判断是否继续：若继续，则计算延迟和优先级并调度下一 step；若不继续，则通过 `CompletionLifecycle` 发送完成 signal、dispatch 完成 hooks，并 finalize trace。异常路径会格式化错误、尽力发布 error 事件、保存 error state、触发完成/错误 hooks，并把失败 snapshot 收束到规范路径。

## 关键函数的高层作用

`constructor` 负责依赖装配：选择 stream manager、coordinator、queue、trace recorder、message model、completion lifecycle、human intervention、tool execution service，并为本地队列注入执行回调。

`createOperation` 是 operation 生命周期入口，重点是持久化初始状态、注册 hooks、可选自动调度首个 step。

`executeStep` 是最关键函数，承担幂等锁、状态读取、hook/signal、runtime step 执行、状态保存、trace、下一步调度和完成收尾。

`interruptOperation` 不会强杀正在进行的 LLM 请求，而是把 operation 状态标记为 `interrupted`，让运行在 step 边界或 step 返回后停止。

`formatErrorForState` 是错误归一化辅助函数，把不同来源的异常转成 `ChatMessageError` 结构。`toAgentSignalSnapshotEvents` 是 trace 辅助函数，把 Agent Signal emission 转成 snapshot 可记录事件。

## 修改风险

最大风险是破坏 step 幂等和状态机。`tryClaimStep`、`stepCount > stepIndex`、终态早退出共同防止重复扣费、重复工具调用和重复消息写入，修改 `executeStep` 的顺序时要非常谨慎。

第二个风险是队列与本地执行模式差异。`QueueService` 可能是本地实现，也可能是远端 HTTP 调度；`baseURL`、`scheduleMessage`、`LocalQueueServiceImpl` 回调都会影响异步任务能否继续推进。

第三个风险是 hooks、Agent Signal、trace 的一致性。这里的 before/after/completion/error 分支都在给外部系统、评测、bot 回调和 tracing 提供观测点；少发、重复发或异常吞吐策略变化，都会导致 UI 状态、评测结果或调试快照不一致。

第四个风险是 metadata 兼容。`AgentState.metadata` 聚合了 agent、topic、thread、tool、device、memory、queue、eval 等多域字段，很多执行器通过这些字段做 fallback。重命名、裁剪或移动字段，可能不会在本文件直接报错，但会让工具执行、子 Agent、设备工具或评测链路失效。

第五个风险是错误路径。代码明显为 Redis/QStash/持久化失败做了兜底，尤其失败 snapshot finalize 和 completion hooks 不能轻易删除，否则失败任务会变得不可观测，调用方也可能无法收到完成信号。
