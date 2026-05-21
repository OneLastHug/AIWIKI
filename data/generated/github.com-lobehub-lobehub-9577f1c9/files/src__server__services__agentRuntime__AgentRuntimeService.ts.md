# 文件：src/server/services/agentRuntime/AgentRuntimeService.ts

## 它负责什么

`AgentRuntimeService.ts` 是服务端 Agent 执行链路的核心编排服务。它不直接实现某一个具体模型、工具或队列，而是把这些能力串起来，负责一个 Agent operation 从“创建、调度、执行单步、继续下一步、暂停等待人工、完成、失败、追踪、回调通知”的完整生命周期。

可以把它理解为服务端 Agent Runtime 的“总控层”：

- 创建一次 Agent 执行任务，即 `createOperation`
- 把任务状态交给 `AgentRuntimeCoordinator` 保存
- 通过 `QueueService` 调度 `/api/agent/run` 来执行步骤
- 每一步调用 `@lobechat/agent-runtime` 的 `AgentRuntime.step`
- 在步骤前后触发 hooks、Agent Signal、stream events
- 处理人工干预，包括工具审批、拒绝、人工输入、选择
- 处理中断、错误、完成状态
- 记录执行快照，用于 tracing / debugging
- 为测试提供同步执行入口 `executeSync`

这个文件本身更像“运行时业务编排器”，而不是底层 Runtime。真正的 Agent 状态机、消息生成、工具调用细节主要来自 `@lobechat/agent-runtime`、`RuntimeExecutors`、`ToolExecutionService`、`CompletionLifecycle`、`HumanInterventionHandler` 等下游模块。

## 关键组成

### `formatErrorForState`

`formatErrorForState(error)` 用于把不同来源的错误统一转换成 `ChatMessageError` 结构。

它处理三类错误：

- 带 `errorType` 的 LLM / Provider 错误
- 标准 `Error` 对象
- 其他未知错误

最终结果会写入 Agent state 的 `error` 字段，使前端、hooks、trace、completion 逻辑都能用统一格式读取错误。

### `toAgentSignalSnapshotEvents`

`toAgentSignalSnapshotEvents` 用于把 `emitAgentSignalSourceEvent` 的返回结果转换成 trace snapshot 里的事件。

如果 signal emission 不存在，或被 dedupe，则返回空数组。否则调用 `toAgentSignalTraceEvents`，把 source、signals、actions、results 转成可记录的 trace events。

### `AgentRuntimeServiceOptions`

`AgentRuntimeServiceOptions` 是构造服务时的依赖注入配置，主要用于测试、替换运行策略或接入上层服务：

- `agentFactory`：自定义 Agent 实例创建逻辑。默认是 `new GeneralChatAgent(config)`，但可以注入其他 Agent，例如 GraphAgent。
- `coordinatorOptions`：传给 `AgentRuntimeCoordinator` 的配置。
- `execSubAgentTask`：执行子 Agent 任务的回调。注释说明它由 `AiAgentService` 注入，用来避免 `RuntimeExecutors` 和 `AiAgentService` 循环依赖。
- `queueService`：自定义队列服务。传 `null` 可以禁用队列，常用于同步测试。
- `snapshotStore`：执行 trace 的存储实现。
- `streamEventManager`：自定义 stream 事件管理器，测试中可使用内存实现。

### `AgentRuntimeService` 类字段

核心字段可以按职责分成几组：

运行状态与调度：

- `coordinator: AgentRuntimeCoordinator`
- `streamManager: IStreamEventManager`
- `queueService: QueueService | null`

执行能力：

- `agentFactory`
- `execSubAgentTaskCallback`
- `toolExecutionService: ToolExecutionService`

生命周期与辅助服务：

- `completionLifecycle: CompletionLifecycle`
- `humanIntervention: HumanInterventionHandler`
- `traceRecorder: OperationTraceRecorder`

数据库与用户上下文：

- `serverDB: LobeChatDatabase`
- `userId: string`
- `messageModel: MessageModel`

`baseURL` 是一个 getter，用来拼出 Agent API 的服务端地址：

```ts
process.env.AGENT_RUNTIME_BASE_URL || appEnv.APP_URL || '[URL已移除]'
```

然后拼接 `/api/agent`。后续队列调度会把 endpoint 设置成 `${this.baseURL}/run`。

### constructor

构造函数完成依赖装配：

1. 初始化 `streamManager`
2. 初始化 `AgentRuntimeCoordinator`
3. 初始化 `QueueService`
4. 初始化 `OperationTraceRecorder`
5. 保存自定义 `agentFactory` 和 `execSubAgentTask`
6. 初始化 `MessageModel`
7. 初始化 `CompletionLifecycle`
8. 初始化 `HumanInterventionHandler`
9. 初始化 `BuiltinToolsExecutor`
10. 初始化 `ToolExecutionService`
11. 调用 `setupLocalExecutionCallback`

这里有一个重要设计：`QueueService` 可能有不同实现。如果底层是 `LocalQueueServiceImpl`，就通过 callback 把本地队列消息直接接到 `executeStep`，避免必须经过 HTTP。

### `setupLocalExecutionCallback`

这个方法专门处理本地队列模式。

当 `queueService.getImpl()` 是 `LocalQueueServiceImpl` 时，注册一个 callback：

```ts
impl.setExecutionCallback(async (operationId, stepIndex, context) => {
  await this.executeStep({ context, operationId, stepIndex });
});
```

也就是说，本地模式下，调度消息不会真的请求 `/api/agent/run`，而是通过回调直接执行当前进程内的 `executeStep`。

### `interruptOperation`

`interruptOperation(operationId)` 用于中断运行中的 operation。

流程是：

1. 从 coordinator 读取 Agent state
2. 如果 state 不存在，返回 `false`
3. 如果已经是 `done`、`error`、`interrupted`，返回 `false`
4. 否则把状态更新为 `interrupted`
5. 返回 `true`

注意注释中明确说明：它不能中断正在进行中的 LLM 请求，只能在下一次 step boundary 生效。也就是说，如果用户点了停止，当前模型请求可能仍会跑完，但后续状态会被标记为中断。

### `createOperation`

`createOperation(params)` 是创建 Agent operation 的入口。

它做的事情非常多，是理解本文件的第一重点。

主要流程：

1. 从参数中取出 operation、agent、model、context、tools、hooks、userMemory、appContext 等信息。
2. 调用 `completionLifecycle.recordStart`，写入初始 operation 持久化记录。
3. 检查 abort signal。
4. 构造 `initialState`。
5. 调用 `coordinator.createAgentOperation` 创建 operation 元信息。
6. 调用 `coordinator.saveAgentState` 保存初始 Agent state。
7. 如果有 hooks，注册到 `hookDispatcher`，并把序列化后的 hooks 写入 state metadata。
8. 如果 `autoStart` 为真且有队列服务，则调度第一步执行。
9. 返回 `{ success, operationId, messageId, autoStarted }`。

`initialState` 是这个方法最重要的数据结构之一。它包含：

- `createdAt`
- `initialContext`
- `messages`
- `metadata`
- `maxSteps`
- `modelRuntimeConfig`
- `operationId`
- `operationToolSet`
- `status: 'idle'`
- `stepCount`
- `tools`
- `toolExecutorMap`
- `toolManifestMap`
- `toolSourceMap`
- `userInterventionConfig`

其中 `metadata` 承载了大量运行上下文，例如：

- `activeDeviceId`
- `agentConfig`
- `botContext`
- `botPlatformContext`
- `deviceAccessPolicy`
- `discordContext`
- `evalContext`
- `modelRuntimeConfig`
- `stream`
- `operationSkillSet`
- `userMemory`
- `userTimezone`
- `workingDirectory`
- `appContext` 展开的字段

这里可以看出，`metadata` 是跨步骤保存上下文的主要载体。

### `executeStep`

`executeStep(params)` 是本文件最核心的方法，也是整个 Agent Runtime 服务端执行的关键。

它执行一个 step，而不是一次完整对话。一次 operation 可能会执行多个 step，每次 step 结束后根据状态决定是否调度下一步。

主要流程如下：

1. 从参数中读取 `operationId`、`stepIndex`、`context`、人工干预相关参数。
2. 调用 `coordinator.tryClaimStep` 获取分布式锁，避免 QStash 重试或多实例导致重复执行。
3. 发布 `step_start` stream event。
4. 从 coordinator 加载当前 Agent state。
5. 如果当前 step 已经完成，即 `agentState.stepCount > stepIndex`，直接跳过。
6. 如果 operation 已经是终态，触发 completion signal 和 hooks 后返回。
7. 触发 `runtime.before_step` Agent Signal 和 `beforeStep` hook。
8. 调用 `createAgentRuntime` 创建 `AgentRuntime` 实例。
9. 如果有人类输入、工具审批或拒绝信息，交给 `HumanInterventionHandler.process` 更新 state 和 context。
10. 如果缺少 `activeDeviceId`，调用 `computeDeviceContext` 从历史 tool messages 中推导设备上下文。
11. 调用 `runtime.step(currentState, currentContext)` 真正执行一步。
12. 再次加载最新 state，检查执行期间是否被标记为 `interrupted`。
13. 调用 `coordinator.saveStepResult` 保存 step 结果。
14. 调用 `shouldContinueExecution` 判断是否继续。
15. 发布 `step_complete` stream event。
16. 通过 `buildStepPresentation` 生成 step 展示信息。
17. 触发 `runtime.after_step` Agent Signal 和 `afterStep` hook。
18. 调用 `traceRecorder.appendStep` 追加 trace snapshot。
19. 如果 afterStep hooks 需要跨步追踪，则把 `_stepTracking` 写回 state metadata。
20. 如果还要继续，调度下一步。
21. 如果不继续，计算完成原因，触发 completion signal、completion hooks，并 finalize trace。
22. 出错时进入 catch，写 error event、error state、completion hooks 和失败 trace。
23. finally 中释放 step lock。

这个方法体现了服务端 Agent 执行的几个关键原则：

- 每一步都需要抢锁，避免重复执行。
- 状态保存在 coordinator，而不是只放内存。
- step 是可恢复、可重试、可追踪的基本单位。
- hooks、signals、stream、trace 都围绕 step 边界触发。
- LLM 调用本身不可随时打断，但状态可以在边界处中断。

### `getOperationStatus`

`getOperationStatus(params)` 用于查询 operation 当前状态。

它会同时读取：

- `coordinator.loadAgentState(operationId)`
- `coordinator.getOperationMetadata(operationId)`

如果 `includeHistory` 为真，还会读取：

- execution history
- recent stream events

返回结构里包含：

- `currentState`：对外暴露的核心 state 字段
- `executionHistory`
- `recentEvents`
- `metadata`
- `stats`
- `hasError`
- `isActive`
- `isCompleted`
- `needsHumanInput`

这个方法适合前端或外部 API 查询任务状态。

### `getPendingInterventions`

`getPendingInterventions(params)` 用来查询等待人工干预的 operation。

支持两种查询方式：

- 指定 `operationId`
- 指定 `userId`，再从 active operations 中筛选属于该用户的 operation

它只返回 `state.status === 'waiting_for_human'` 的任务，并根据 state 中的 pending 字段判断干预类型：

- `pendingToolsCalling`：工具审批
- `pendingHumanPrompt`：人工输入
- `pendingHumanSelect`：人工选择

### `startExecution`

`startExecution(params)` 用于显式启动一个已经创建但尚未执行的 operation。

它会：

1. 检查 operation metadata 是否存在。
2. 读取当前 state。
3. 防止重复启动 `running`、`done`、`error` 状态的 operation。
4. 如果没有传入 context，就构造一个默认 `AgentRuntimeContext`。
5. 把 state 改成 `running`。
6. 通过队列调度 `${this.baseURL}/run`。
7. 返回调度结果。

它和 `createOperation(autoStart: true)` 的区别是：`createOperation` 可以创建后立即启动；`startExecution` 是给 `autoStart: false` 或延迟启动场景使用。

### `processHumanIntervention`

`processHumanIntervention(params)` 并不直接处理人工输入，而是把人工干预信息调度到下一次 `executeStep`。

它会把这些字段塞进 queue message 的 `payload`：

- `approvedToolCall`
- `humanInput`
- `rejectAndContinue`
- `rejectionReason`
- `toolMessageId`

然后高优先级调度对应 step。

真正更新 state 和 context 的逻辑在 `executeStep` 里的：

```ts
this.humanIntervention.process(...)
```

### `createAgentRuntime`

`createAgentRuntime` 是创建实际 runtime 的私有方法。

它主要做三件事。

第一，读取模型上下文窗口大小：

```ts
getModelPropertyWithFallback(model, 'contextWindowTokens', provider)
```

第二，创建 Agent：

- 如果注入了 `agentFactory`，使用自定义 Agent。
- 否则默认创建 `GeneralChatAgent`。

传给 Agent 的 `generalConfig` 包含：

- `agentConfig`
- `compressionConfig`
- `dynamicInterventionAudits`
- `modelRuntimeConfig`
- `operationId`
- `userId`

第三，构造 `RuntimeExecutorContext` 并创建 `AgentRuntime`：

```ts
const runtime = new AgentRuntime(agent as any, {
  executors: createRuntimeExecutors(executorContext),
});
```

这里的 `createRuntimeExecutors` 是工具执行、流式输出、数据库消息、子任务调用等能力接入 Runtime 的关键桥梁。

### `createDefaultSnapshotStore`

这个方法按环境决定是否启用 trace snapshot 存储：

- `ENABLE_AGENT_S3_TRACING=1`：尝试创建 `S3SnapshotStore`
- `NODE_ENV=development`：尝试创建 `FileSnapshotStore`
- 其他情况：返回 `null`

所以生产环境默认不一定记录本地 trace，除非启用了 S3 tracing。

### `computeDeviceContext`

`computeDeviceContext(state)` 用于在 step 边界从数据库消息中推导设备上下文。

它会查询当前 agent/thread/topic 下的消息：

```ts
this.messageModel.query({
  agentId,
  threadId,
  topicId,
})
```

然后用 `findInMessages` 查找 role 为 `tool` 的消息，读取：

- `pluginState.metadata.activeDeviceId`
- `pluginState.metadata.devicePlatform`
- `pluginState.metadata.deviceSystemInfo`

根据当前片段推断，这用于设备控制类工具或多设备场景：如果运行上下文里没有明确 `activeDeviceId`，服务端会从历史工具消息中找最近一次激活设备的信息。

### `shouldContinueExecution`

`shouldContinueExecution(state, context)` 判断当前 operation 是否还应该继续下一步。

停止条件包括：

- `state.status === 'done'`
- `state.status === 'waiting_for_human'`
- `state.status === 'error'`
- `state.status === 'interrupted'`
- 成本超限且策略是 `stop`
- 没有 `nextContext`

注意：`maxSteps` 不在这里重复判断，注释说明它由 `runtime.step()` 的状态机处理。

### `calculateStepDelay`

`calculateStepDelay(stepResult)` 决定下一步调度延迟。

默认是 `50ms`。

如果本步有 `tool_result`，延迟增加到 `100ms`。

如果本步有 `error` event，使用简单 backoff，最多 `1000ms`。

### `calculatePriority`

`calculatePriority(stepResult)` 决定下一步队列优先级。

当前实现基本返回 `normal`，只有 `waiting_for_human` 时返回 `high`。但因为 `waiting_for_human` 会让 `shouldContinueExecution` 返回 false，所以这个分支在正常继续调度路径里可能较少触发。根据当前片段推断，它可能是为后续扩展或历史逻辑保留。

### `determineCompletionReason`

`determineCompletionReason(state)` 把最终 state 转成完成原因：

- `done`
- `error`
- `interrupted`
- `waiting_for_human`
- `max_steps`
- `cost_limit`

如果都不匹配，默认返回 `done`。

这个 reason 会传给：

- `completionLifecycle.emitSignalEvents`
- `completionLifecycle.dispatchHooks`
- `traceRecorder.finalize`

### `executeSync`

`executeSync(operationId, options)` 是同步执行入口，主要用于测试或不依赖队列的场景。

它会：

1. 读取初始 state。
2. 构造初始 context。
3. 从当前 `stepCount` 开始循环执行 `executeStep`。
4. 每步后更新 state 和 context。
5. 遇到 `done`、`error`、`interrupted`、`waiting_for_human` 或 `shouldContinueExecution` 为 false 时停止。
6. 如果超过 `maxSteps`，手动触发 completion signal 和 hooks。

注意：`executeSync` 复用了 `executeStep`，所以同步模式也会走锁、hooks、trace、signals 等大部分逻辑。

### `getCoordinator`

`getCoordinator()` 返回内部的 `AgentRuntimeCoordinator`，注释标明主要用于测试。

## 上下游关系

### 上游调用者

根据当前文件注释和方法设计，可以确定或推断的上游有几类。

第一类是 Agent API 路由。`createOperation` 和 `executeStep` 都围绕 `/api/agent/run` 调度，`baseURL` 明确拼接了 `/api/agent`，队列 endpoint 使用 `${this.baseURL}/run`。因此根据当前片段推断，某个 API route 会接收队列请求并调用 `executeStep`。

第二类是 `AiAgentService`。文件注释明确写到：

```ts
Injected by AiAgentService to wire up the exec_task / exec_tasks executors
```

说明 `AiAgentService` 会创建 `AgentRuntimeService`，并注入 `execSubAgentTask`，让 RuntimeExecutors 可以执行子 Agent 任务。

第三类是测试。`AgentRuntimeServiceOptions`、`executeSync`、`getCoordinator`、`queueService: null`、`streamEventManager` 注入等设计都明显服务于测试场景。同目录存在 `AgentRuntimeService.test.ts`，但本次没有展开测试文件内容。

第四类是人工干预 API 或 UI 交互入口。`processHumanIntervention` 接收 approve / reject / input / select 等 action，说明上游应该有接口把用户审批或输入转发到这里。

### 下游依赖

这个文件的下游依赖非常多，按职责可分为：

Agent Runtime 核心：

- `@lobechat/agent-runtime`
- `AgentRuntime`
- `GeneralChatAgent`
- `Agent`
- `AgentState`
- `AgentRuntimeContext`

状态协调与事件：

- `AgentRuntimeCoordinator`
- `createStreamEventManager`
- `IStreamEventManager`

队列调度：

- `QueueService`
- `LocalQueueServiceImpl`

工具执行：

- `ToolExecutionService`
- `BuiltinToolsExecutor`
- `mcpService`
- `createRuntimeExecutors`

生命周期与人工干预：

- `CompletionLifecycle`
- `HumanInterventionHandler`
- `hookDispatcher`

数据库：

- `MessageModel`
- `LobeChatDatabase`

Tracing：

- `OperationTraceRecorder`
- `ISnapshotStore`
- `S3SnapshotStore`
- `FileSnapshotStore`

Agent Signal：

- `emitAgentSignalSourceEvent`
- `toAgentSignalTraceEvents`

模型元信息：

- `getModelPropertyWithFallback`

错误类型：

- `AgentRuntimeErrorType`
- `ChatErrorType`
- `ChatMessageError`

### 数据流关系

一次 operation 的主要数据流是：

```text
上游服务/API
  -> AgentRuntimeService.createOperation
  -> AgentRuntimeCoordinator 保存 operation metadata 和 AgentState
  -> QueueService 调度 /api/agent/run
  -> AgentRuntimeService.executeStep
  -> AgentRuntime.step
  -> RuntimeExecutors / ToolExecutionService / MCP / BuiltinTools
  -> saveStepResult
  -> stream events / hooks / agent signal / trace
  -> 如果继续，QueueService 调度下一步
  -> 如果结束，CompletionLifecycle 收尾
```

## 运行/调用流程

### 创建并自动执行

典型流程是：

```text
1. 上游创建 AgentRuntimeService
2. 调用 createOperation({ autoStart: true, ... })
3. recordStart 写入 operation 起始记录
4. coordinator.createAgentOperation 创建 operation
5. coordinator.saveAgentState 保存初始 state
6. 注册 hooks
7. QueueService.scheduleMessage 调度 stepIndex = initialStepCount
8. 队列请求 /api/agent/run，或本地队列 callback 直接调用 executeStep
```

### 执行单步

单步执行流程是：

```text
1. executeStep 收到 operationId + stepIndex + context
2. tryClaimStep 获取分布式锁
3. publish step_start
4. loadAgentState
5. 跳过重复 step 或终态 operation
6. beforeStep signal + hook
7. createAgentRuntime
8. 处理人工干预输入
9. 补全 device context
10. runtime.step
11. 检查是否被中断
12. saveStepResult
13. publish step_complete
14. afterStep signal + hook
15. append trace step
16. 判断是否调度下一步
17. 如果结束，emit completion signal + dispatch hooks + finalize trace
18. releaseStepLock
```

### 多步继续执行

`runtime.step` 返回 `stepResult.nextContext`。如果：

- state 不是 `done`
- 不是 `waiting_for_human`
- 不是 `error`
- 不是 `interrupted`
- 没有触发停止型成本限制
- 存在 `nextContext`

那么 `shouldContinueExecution` 返回 `true`，服务会调度下一步：

```ts
stepIndex + 1
```

也就是说，Agent 的多轮推理、工具调用、工具结果处理，不是在一个大函数里循环到底，而是通过队列把每个 step 拆开执行。

### 人工干预流程

人工干预不是直接修改当前运行中的 LLM 调用，而是基于 step 边界继续：

```text
1. Runtime 进入 waiting_for_human
2. getPendingInterventions 可以查到待处理项
3. 用户审批、拒绝或输入
4. 上游调用 processHumanIntervention
5. processHumanIntervention 高优先级调度对应 step
6. executeStep 读取 payload
7. HumanInterventionHandler.process 更新 state/context
8. runtime.step 继续执行
```

### 中断流程

```text
1. 用户或上游调用 interruptOperation
2. state.status 被改成 interrupted
3. 如果当前没有执行中的 step，后续 executeStep 会直接跳过
4. 如果当前正在 LLM 调用中，等待 runtime.step 返回
5. executeStep 再次 loadAgentState
6. 如果发现 latestState.status === 'interrupted'，把 stepResult.newState.status 改成 interrupted
7. completionLifecycle 按 interrupted reason 收尾
```

### 错误流程

如果 `executeStep` 中任何主要逻辑抛错：

```text
1. formatErrorForState 统一错误格式
2. 尝试发布 error stream event
3. 尝试读取当前 state
4. 构造 finalStateWithError
5. 尝试保存 error state
6. emitSignalEvents(reason = error)
7. dispatchHooks(reason = error)
8. traceRecorder.finalize，写入失败 step 信息
9. 重新 throw error
10. finally 释放 step lock
```

这里有一个值得注意的细节：即使 Redis 或其他基础设施异常，代码也会尽量构造 minimal error state，保证 completion callbacks 和 webhooks 能拿到有用信息。

## 小白阅读顺序

建议按下面顺序读，不要从上到下一次性硬啃。

第一步，先看类的构造函数。

重点理解 `AgentRuntimeService` 不是单独干活，而是装配这些对象：

- `AgentRuntimeCoordinator`
- `QueueService`
- `CompletionLifecycle`
- `HumanInterventionHandler`
- `OperationTraceRecorder`
- `ToolExecutionService`

理解这些字段后，后面的流程会清晰很多。

第二步，看 `createOperation`。

重点看它如何构造 `initialState`。这里能看到一个 operation 初始时有哪些核心数据：

- messages
- metadata
- modelRuntimeConfig
- operationToolSet
- status
- stepCount
- tools
- userInterventionConfig

如果只理解一个对象，优先理解 `AgentState` 的形状。

第三步，看 `executeStep` 的主干。

先不要纠结每个 hook 和 signal 的细节，先抓住主线：

```text
抢锁 -> 加载 state -> 创建 runtime -> 处理人工干预 -> runtime.step -> 保存结果 -> 判断是否继续 -> 调度下一步或收尾
```

第四步，看 `createAgentRuntime`。

这个方法解释了 Agent Runtime 最终是怎么被创建出来的：

- `GeneralChatAgent`
- `AgentRuntime`
- `createRuntimeExecutors`

尤其要注意 `RuntimeExecutorContext`，它把数据库、stream、工具服务、子任务回调等全部传给 executors。

第五步，看终止逻辑。

重点读：

- `shouldContinueExecution`
- `determineCompletionReason`
- `interruptOperation`
- `executeStep` catch 分支

这几个方法决定 operation 何时停止、如何停止、失败时怎么收尾。

第六步，再看辅助入口。

包括：

- `getOperationStatus`
- `getPendingInterventions`
- `startExecution`
- `processHumanIntervention`
- `executeSync`

这些方法是围绕主执行链路提供的查询、启动、人工恢复和测试能力。

## 常见误区

### 误区一：以为 `createOperation` 会直接执行 Agent

`createOperation` 主要是创建 operation 和保存初始状态。真正执行发生在 `executeStep`。

如果 `autoStart` 为 true，它只是通过 `QueueService.scheduleMessage` 调度第一步，不是在当前调用栈里直接跑完整 Agent。

本地队列模式下看起来像“直接执行”，但那是 `LocalQueueServiceImpl` callback 把队列消息接回了 `executeStep`。

### 误区二：以为一次 operation 等于一次函数调用

这里的 operation 是多 step 的。每个 step 可能产生新的 `nextContext`，再通过队列调度下一 step。

所以完整执行链路可能是：

```text
createOperation
  -> executeStep 0
  -> executeStep 1
  -> executeStep 2
  -> completion
```

而不是一次 `runtime.step` 结束全部逻辑。

### 误区三：以为 `AgentRuntimeService` 负责具体工具逻辑

它不直接实现具体工具。它创建 `ToolExecutionService`，并通过 `createRuntimeExecutors(executorContext)` 把工具执行能力传给 `AgentRuntime`。

具体工具如何执行，要继续看：

- `src/server/modules/AgentRuntime/RuntimeExecutors`
- `src/server/services/toolExecution`
- builtin tools 相关包
- MCP service

### 误区四：以为中断能立刻取消 LLM 请求

文件注释明确说不能取消 in-flight LLM call。`interruptOperation` 只是把 state 标记成 `interrupted`。

真正停止发生在 step 边界：

- 下一次 step 开始时发现已经 interrupted
- 或当前 `runtime.step` 返回后再次检查 latest state

### 误区五：忽略 step lock

`executeStep` 一开始会 `tryClaimStep(operationId, stepIndex, 35)`。

这是为了防止队列重试、多实例并发、延迟消息导致同一个 step 被重复执行。读这个文件时必须把“分布式锁 + stepIndex 幂等检查”看成执行安全性的核心部分。

### 误区六：把 hooks、signals、stream events 混为一谈

它们用途不同：

- stream events：面向实时状态流，例如 `step_start`、`step_complete`、`error`
- hooks：外部扩展点，例如 `beforeStep`、`afterStep`、completion hooks
- Agent Signal：用于内部事件源、编排和观测
- trace snapshot：用于记录执行过程，方便调试和回放

`executeStep` 会在多个位置同时处理这些系统，但它们不是同一个东西。

### 误区七：以为 `waiting_for_human` 是错误状态

`waiting_for_human` 是正常暂停状态，不是失败。

`shouldContinueExecution` 遇到它会返回 false，因为需要等待用户输入或审批。之后由 `processHumanIntervention` 调度恢复执行。

### 误区八：忽略 `metadata` 的重要性

很多上下文都藏在 `AgentState.metadata` 里，包括：

- agentId
- topicId
- threadId
- userId
- stream
- modelRuntimeConfig
- bot context
- device context
- hooks
- queue retry config
- user memory
- timezone
- working directory

阅读执行链路时，如果某个信息“突然出现”，通常应先检查它是否来自 `metadata`。

### 误区九：以为 tracing 总是开启

`createDefaultSnapshotStore` 显示 tracing 存储依赖环境：

- S3 tracing 需要 `ENABLE_AGENT_S3_TRACING=1`
- development 下尝试 FileSnapshotStore
- 其他情况返回 `null`

所以不能假设所有环境都会落 trace 文件或 S3 snapshot。

### 误区十：以为 `executeSync` 是另一套执行逻辑

`executeSync` 只是同步循环调用 `executeStep`。它不是绕过 Runtime 的简化实现。

因此测试中使用 `executeSync` 时，仍然会走大部分真实逻辑，包括：

- step lock
- runtime.step
- hooks
- completion lifecycle
- trace recorder
- shouldContinueExecution
