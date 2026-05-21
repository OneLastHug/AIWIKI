# 文件：src/server/routers/lambda/aiAgent.ts

## 它负责什么

`src/server/routers/lambda/aiAgent.ts` 是 LobeHub 后端 lambda tRPC 中和“AI Agent 执行”相关的核心路由文件。它导出 `aiAgentRouter`，并在 `src/server/routers/lambda/index.ts` 中以 `aiAgent: aiAgentRouter` 注册到根路由 `lambdaRouter`，因此前端或其他客户端最终会通过 `lambdaClient.aiAgent.xxx` 调用这里的 procedure。

这个文件的职责不是单纯“调用大模型”。更准确地说，它是 AI Agent 运行系统的后端入口层，负责：

1. 定义 tRPC 输入协议：使用 `zod` 定义 `execAgent`、`execSubAgentTask`、`processHumanIntervention`、`heteroIngest` 等接口的请求结构。
2. 做认证和上下文装配：通过 `authedProcedure.use(serverDatabase)` 或 `heteroAuthedProcedure.use(serverDatabase)` 注入数据库、用户态服务和模型实例。
3. 编排 agent 执行请求：把来自 SPA、desktop、CLI、bot、eval 等入口的请求转交给 `AiAgentService`、`AgentRuntimeService`、`AiChatService`、`HeterogeneousAgentService`。
4. 管理任务线程状态：创建 `Thread`、写入初始 user message、轮询任务状态、同步 Redis 实时状态到 PostgreSQL、更新完成/失败/取消状态。
5. 处理人工干预：把工具调用审批、拒绝、用户输入、选择等动作交给 runtime 继续执行。
6. 接入异构 agent：通过 `heteroIngest` / `heteroFinish` 接收 `claude-code`、`codex` 这类外部 CLI agent 的事件流和终态通知。

可以把它理解为“Agent 后端 API 门面”：复杂业务大多在 service/model 层，router 层负责输入校验、权限边界、服务装配、错误转换，以及少量必须贴近 API 的状态协调。

## 关键组成

### import 结构

这个文件的 import 可以分成几组看：

第一组是协议和运行时类型：

- `AgentStreamEvent` 来自 `@lobechat/agent-gateway-client`，用于异构 agent 的事件流结构。
- `parse` 来自 `@lobechat/conversation-flow`，在 `getSubAgentTaskStatus` 中把 thread messages 解析成 UI 更容易消费的 `flatList`。
- `TaskCurrentActivity`、`TaskStatusResult`、`RequestTrigger`、`ThreadStatus`、`ThreadType`、`UserInterventionConfigSchema` 来自 `@lobechat/types`，用于任务状态、线程状态、触发来源和人工干预配置。
- `TRPCError`、`z` 分别用于 tRPC 错误和输入校验。
- `debug` 用 `lobe-server:ai-agent-router` 命名空间记录后端日志。
- `pMap` 用在 `execAgents` 批量执行中控制并发。

第二组是数据库模型：

- `MessageModel`
- `TaskModel`
- `TaskTopicModel`
- `ThreadModel`
- `TopicModel`

这些模型负责直接读写消息、任务、任务话题、线程、话题等表。特别是 `createClientTaskThread`、`createClientGroupAgentTaskThread`、`getSubAgentTaskStatus`、`updateClientTaskThreadStatus` 会直接使用 model 层。

第三组是 tRPC 基础设施：

- `authedProcedure`
- `heteroAuthedProcedure`
- `router`
- `serverDatabase`

普通用户态接口走 `authedProcedure + serverDatabase`。异构 agent 事件回传走 `heteroAuthedProcedure + serverDatabase`，注释里明确说它需要 `hetero-operation` JWT，普通用户 token 会被拒绝。

第四组是服务层：

- `AgentRuntimeService`
- `AiAgentService`
- `AiChatService`
- `HeterogeneousAgentService`
- `TaskLifecycleService`

其中 `AiAgentService` 是 agent 执行相关的主服务，`AgentRuntimeService` 管运行时操作状态和人工干预，`HeterogeneousAgentService` 管外部 CLI agent 的事件接入，`AiChatService` 用于执行后同步 messages/topics，`TaskLifecycleService` 用于异构 agent 完成后推进任务生命周期。

### 工具函数

`extractTaskErrorMessage(error)` 和 `formatTaskError(error)` 用来规范化任务错误。

Agent runtime 或 Redis 中的错误对象可能有多层嵌套，例如：

- `body.error.message`
- `body.message`
- `error.error.message`
- `error.message`
- `message`
- `type`
- `errorType`
- `name`

`extractTaskErrorMessage` 会按优先级找出可读字符串，并排除 `"[object Object]"` 和 `"error"` 这种无意义文本。`formatTaskError` 则把 `Error`、字符串、普通对象等统一转成可保存到 thread metadata 的对象。这个逻辑主要服务于 `getSubAgentTaskStatus`，避免前端看到不可读的错误结构。

### Zod Schema

文件前半部分定义了大量接口 schema。重点包括：

- `GetOperationStatusSchema`：查询 operation 状态，包含 `operationId`、`includeHistory`、`historyLimit`。
- `ProcessHumanInterventionSchema`：处理人工干预，支持 `approve`、`reject`、`reject_continue`、`input`、`select`。
- `GetPendingInterventionsSchema`：查询待处理人工干预，要求 `operationId` 或 `userId` 至少一个存在。
- `StartExecutionSchema`：启动已创建的 operation。
- `ExecAgentSchema`：执行单个 agent 的主入口 schema。
- `ExecGroupAgentSchema`：群组会话中执行 supervisor agent。
- `ExecAgentsSchema`：批量执行多个 agent。
- `ExecSubAgentTaskSchema`：执行子 agent 任务。
- `CreateClientTaskThreadSchema`：desktop client 本地执行任务前，先在服务端创建 thread。
- `CreateClientGroupAgentTaskThreadSchema`：群组模式下为 client-side 子任务创建 thread。
- `UpdateClientTaskThreadStatusSchema`：client-side 任务执行结束后回写 thread 状态。
- `InterruptTaskSchema`：按 `threadId` 或 `operationId` 中断任务。
- `AgentStreamEventSchema`、`HeteroIngestSchema`、`HeteroFinishSchema`：异构 agent 事件接入和完成通知。

其中 `ExecAgentSchema` 最关键。它支持 `agentId` 或 `slug` 二选一，包含 `prompt`、`appContext`、`autoStart`、`clientRuntime`、`deviceId`、`existingMessageIds`、`fileIds`、`parentMessageId`、`resumeApproval`、`trigger`、`userInterventionConfig` 等字段。这里能看出 `execAgent` 不只是“发一条 prompt”，还要兼容文件附件、消息续写、人工审批恢复、desktop 本地工具、OpenAPI/CLI/eval 等不同触发源。

### Procedure 上下文

文件中定义了两个 procedure 基座。

`aiAgentProcedure` 面向普通已登录用户：

```ts
const aiAgentProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
  ...
});
```

它往 `ctx` 注入：

- `agentRuntimeService`
- `aiAgentService`
- `aiChatService`
- `heterogeneousAgentService`
- `messageModel`
- `threadModel`
- `topicModel`

所以大多数 route handler 不自己 new 数据库连接，而是使用这个增强后的 `ctx`。

`heteroAgentProcedure` 面向异构 agent 回调：

```ts
const heteroAgentProcedure = heteroAuthedProcedure.use(serverDatabase).use(async (opts) => {
  ...
});
```

它只注入 `heterogeneousAgentService`。这说明 `heteroIngest` / `heteroFinish` 是一个更窄的安全边界：外部 producer 只允许回传运行事件和完成状态，不获得普通用户态完整 API 能力。

### export

文件导出：

```ts
export const aiAgentRouter = router({ ... });
```

它在 `src/server/routers/lambda/index.ts` 中被注册为：

```ts
aiAgent: aiAgentRouter
```

因此客户端路径是 `lambdaClient.aiAgent.<procedure>`。例如 `src/services/aiAgent.ts` 中的 `AiAgentService` 客户端封装会调用：

- `lambdaClient.aiAgent.execAgent.mutate(...)`
- `lambdaClient.aiAgent.execSubAgentTask.mutate(...)`
- `lambdaClient.aiAgent.getSubAgentTaskStatus.query(...)`
- `lambdaClient.aiAgent.interruptTask.mutate(...)`
- `lambdaClient.aiAgent.createClientTaskThread.mutate(...)`
- `lambdaClient.aiAgent.createClientGroupAgentTaskThread.mutate(...)`
- `lambdaClient.aiAgent.updateClientTaskThreadStatus.mutate(...)`
- `lambdaClient.aiAgent.refreshGatewayToken.query(...)`

根据当前片段推断，`refreshGatewayToken` 也在同一个 router 文件的后续部分或相邻改动中实现；依据是客户端 service 已明确通过 `lambdaClient.aiAgent.refreshGatewayToken` 调用它，而根路由注册的 namespace 就是本文件导出的 `aiAgentRouter`。

## 上下游关系

### 上游调用方

直接上游主要有三类。

第一类是浏览器/桌面端 service 封装：`src/services/aiAgent.ts`。它把 tRPC 调用包装成前端可用的 `aiAgentService`，例如：

- `execAgentTask` 调 `aiAgent.execAgent`
- `execSubAgentTask` 调 `aiAgent.execSubAgentTask`
- `getSubAgentTaskStatus` 调 `aiAgent.getSubAgentTaskStatus`
- `interruptTask` 调 `aiAgent.interruptTask`
- `createClientTaskThread` 调 `aiAgent.createClientTaskThread`
- `updateClientTaskThreadStatus` 调 `aiAgent.updateClientTaskThreadStatus`

第二类是 chat store / agent orchestration。搜索结果显示这些路径会使用客户端 `aiAgentService`：

- `src/store/chat/slices/aiChat/actions/gateway.ts`
- `src/store/chat/agents/createAgentExecutors.ts`
- `src/store/chat/agents/GroupOrchestration/createGroupOrchestrationExecutors.ts`
- `src/store/chat/slices/aiAgent/actions/groupOrchestration.ts`
- `src/store/chat/slices/aiAgent/actions/agentGroup.ts`

这些调用方负责 UI 侧发起 agent 任务、轮询子任务状态、中断任务、处理 gateway token 等。

第三类是服务端内部调用。搜索结果显示 `AiAgentService` 也被这些服务直接使用：

- `src/server/services/agentEvalRun/index.ts`
- `src/server/agent-hono/handlers/execAgent.ts`
- `src/server/services/taskRunner/index.ts`
- `src/server/services/bot/AgentBridgeService.ts`
- `src/server/services/bot/BotMessageRouter.ts`
- `src/server/services/messenger/MessengerRouter.ts`
- `src/server/routers/lambda/agentNotify.ts`

这些不一定经过本 router，但它们共享同一个下游核心服务 `AiAgentService`，说明 agent 执行能力既服务于 Web UI，也服务于 bot、评测、任务 runner、通知等后端场景。

### 下游服务和模型

`aiAgent.ts` 的主要下游是：

- `AiAgentService`：真正创建/执行 agent operation、群组 agent、子 agent 任务、中断任务。
- `AgentRuntimeService`：查询 operation 状态、启动 operation、处理人工干预。
- `AiChatService`：在 `execGroupAgent` 后同步 messages/topics 给前端。
- `HeterogeneousAgentService`：处理 `heteroIngest` 和 `heteroFinish`。
- `TaskLifecycleService`：异构 agent 完成后调用 `onTopicComplete` 推进 task/topic 生命周期。
- `MessageModel`：创建 user message、查询 thread messages、更新任务 message 内容。
- `ThreadModel`：创建 isolation thread、查询 thread、更新 thread 状态和 metadata。
- `TaskTopicModel` / `TaskModel`：在异构 agent 完成时查找 task topic 和 task，用于生命周期回调。
- `TopicModel`：被注入到 ctx，当前已读片段中没有看到核心使用点，可能供后续接口或历史逻辑使用。

### 与 Agent Gateway / Redis / PostgreSQL 的关系

这个 router 同时面对三种状态来源：

- PostgreSQL：`Thread`、`Message`、`TaskTopic` 等持久状态。
- Redis / runtime state：`AgentRuntimeService.getOperationStatus` 返回的实时 operation 状态。
- Agent Gateway WebSocket：异构 agent 的 stream event 会通过 `HeterogeneousAgentService` 重新发布给订阅者。

`getSubAgentTaskStatus` 中的注释尤其重要：Thread 表是持久事实来源，但 active task 会尝试从 Redis 补充实时状态。如果 QStash 队列模式下 lifecycle callback 没触发，它会在轮询时把 Redis 中的 token、cost、stepCount、error 等指标同步回 Thread metadata。

## 运行/调用流程

### 普通单 agent 执行：`execAgent`

典型流程如下：

1. 前端或客户端调用 `lambdaClient.aiAgent.execAgent.mutate(...)`。
2. tRPC 进入 `aiAgentProcedure`，完成登录校验、数据库注入，并创建 `AiAgentService` 等 ctx 服务。
3. `ExecAgentSchema` 校验输入，要求 `agentId` 或 `slug` 至少一个存在。
4. handler 解构 `agentId`、`slug`、`prompt`、`appContext`、`autoStart`、`clientRuntime`、`deviceId`、`existingMessageIds`、`fileIds`、`parentMessageId`、`resumeApproval` 等参数。
5. 调用 `ctx.aiAgentService.execAgent(...)`。
6. 如果传入 `parentMessageId`，router 会设置 `resume: true`，表示这是重新生成、继续执行或人工审批恢复，不再创建新的 user message。
7. 如果没有显式 `trigger`，默认使用 `RequestTrigger.Chat`。
8. service 返回 operation 信息，例如 `operationId`、`autoStarted` 等，前端再通过 gateway/SSE/WS 或轮询追踪后续状态。

这里的 router 不直接拼 prompt、不直接调用模型，也不直接处理流式输出。它只是把经过校验的请求转换成 service 层所需的执行参数。

### 批量执行：`execAgents`

`execAgents` 接收 `tasks` 数组，每个元素复用 `ExecAgentSchema`。它内部定义 `executeTask`，逐个调用 `ctx.aiAgentService.execAgent(...)`。

并发控制使用 `pMap`：

- `parallel: true` 时 concurrency 为 `5`
- `parallel: false` 时 concurrency 为 `1`

每个任务失败不会直接让整个 mutation 抛错，而是返回一个带 `success: false`、`error`、`taskIndex` 的结果。最终返回：

- `results`
- `success`
- `summary.total`
- `summary.succeeded`
- `summary.failed`

这适合批量触发多个 agent 任务，并让调用方自己处理部分失败。

### 群组 agent：`execGroupAgent`

`execGroupAgent` 面向 group chat 的 supervisor agent。注释说明它把多个步骤包成一次调用：

1. 创建 topic，如果需要。
2. 创建 user message。
3. 创建 assistant placeholder。
4. 触发 supervisor agent 执行。
5. 返回 `operationId` 和 UI 同步所需 messages/topics。

实际 handler 先调用 `ctx.aiAgentService.execGroupAgent(...)`，再调用 `ctx.aiChatService.getMessagesAndTopics(...)` 获取最新消息和话题。返回值会把执行结果与 messages/topics 合并，前端可通过 `success` 判断是否继续连接流。

### 子 agent 任务：`execSubAgentTask`

`execSubAgentTask` 支持两种模式：

- Group mode：传 `groupId`，由 supervisor 把任务委派给 worker/sub-agent。
- Single Agent mode：不传 `groupId`，普通单 agent 也可以开 isolation thread 执行子任务。

它接收 `agentId`、`topicId`、`parentMessageId`、`instruction`、`title`、`timeout`，然后转交给 `ctx.aiAgentService.execSubAgentTask(...)`。真正的 thread 创建、operation 创建和执行逻辑主要在 service 层。

### client-side task thread：`createClientTaskThread`

这个接口用于 desktop 端 `runInClient=true` 的场景：服务端只创建任务上下文，不执行任务，执行发生在本地客户端。

流程是：

1. 创建 `Thread`：
   - `type: ThreadType.Isolation`
   - `status: ThreadStatus.Processing`
   - `sourceMessageId: parentMessageId`
   - `metadata: { clientMode: true, startedAt }`
2. 创建初始 user message：
   - `role: 'user'`
   - `content: instruction`
   - `threadId: thread.id`
   - `parentId: parentMessageId`
3. 并行查询：
   - 当前 thread 内 messages
   - 主会话 messages
4. 返回 `threadId`、`userMessageId`、`threadMessages`、`messages`、`startedAt`。

`createClientGroupAgentTaskThread` 是它的群组版本。关键差异是 group 场景下 thread/message 使用 `subAgentId` 作为执行 agent，并且查询消息时刻意不按 `agentId` 过滤，以便包含 supervisor 与 worker 的跨 agent 上下文。

### 子任务状态轮询：`getSubAgentTaskStatus`

这是文件中逻辑最密集的接口之一。

流程大致是：

1. 根据 `threadId` 查 `Thread`，不存在则抛 `NOT_FOUND`。
2. 把 `ThreadStatus` 映射成 `TaskStatusResult['status']`：
   - `Completed` -> `completed`
   - `Failed` -> `failed`
   - `Cancel` -> `cancel`
   - 其他 active/pending/inReview/todo/processing -> `processing`
3. 从 `thread.metadata.operationId` 找 runtime operation。
4. 如果任务仍在 processing，尝试调用 `ctx.agentRuntimeService.getOperationStatus(...)` 获取 Redis 实时状态。
5. 如果 Redis 状态存在：
   - 同步 token、tool calls、cost、message count、step count 到 Thread metadata。
   - 如果 runtime 已完成，把 Thread 更新为 `ThreadStatus.Completed`。
   - 如果 runtime 有错误，把错误格式化后写入 metadata，并把 Thread 更新为 `ThreadStatus.Failed`。
   - 如果仍在执行，只更新指标 metadata。
6. 重新读取 Thread，拿到更新后的 status/metadata。
7. 查询 thread messages，并用 `parse(threadMessages)` 解析成 conversation-flow 的消息结构。
8. 如果任务完成或失败，从最后一条 assistant message 取 `resultContent`。
9. 如果任务仍在执行，根据最后一条 message 推断 `currentActivity`：
   - 最后一条是 tool message：`tool_result`
   - assistant message 带 tools：`tool_calling`
   - assistant message 无 tools：`generating`
10. 组装 `TaskStatusResult` 返回，包括 `status`、`result`、`messages`、`currentActivity`、`usage`、`cost`、`error`、`taskDetail` 等。

这个接口既是状态查询 API，也是 QStash 模式下的“补偿性状态同步器”。

### 中断任务：`interruptTask`

`interruptTask` 要求 `threadId` 或 `operationId` 至少一个存在。handler 调用 `ctx.aiAgentService.interruptTask({ operationId, threadId })`。

它对两个业务错误做了 tRPC 转换：

- `"Thread not found"` -> `TRPCError` `NOT_FOUND`
- `"Operation ID not found"` -> `TRPCError` `BAD_REQUEST`

其他错误继续抛出。

### 人工干预：`processHumanIntervention`

这个接口处理 runtime 暂停等待人类决策的情况。

支持动作：

- `approve`：必须带 `data.approvedToolCall`。
- `reject`：拒绝工具调用，默认 reason 是 `"Tool call rejected by user"`。
- `reject_continue`：拒绝但继续让 LLM 根据拒绝原因往下走。
- `input`：必须带 `data.input`。
- `select`：必须带 `data.selection`。

handler 会把输入转换成 `interventionParams`，再调用：

```ts
ctx.agentRuntimeService.processHumanIntervention(interventionParams)
```

返回中包含 `scheduledMessageId`，表示继续执行时安排的消息 ID。

### 异构 agent：`heteroIngest` 和 `heteroFinish`

`heteroIngest` 接收外部 producer 批量上报的 `AgentStreamEvent`。支持的 `agentType` 是：

- `claude-code`
- `codex`

它要求 `operationId` 和 `topicId`。注释里强调 `topicId` 必传，因为 operationId 反查 topic 不可靠。handler 调用 `ctx.heterogeneousAgentService.heteroIngest(...)`，成功后返回 `{ ack: true }`。

`heteroFinish` 是异构 agent 的终态回调，接收：

- `agentType`
- `operationId`
- `topicId`
- `result: success | error | cancelled`
- `error`
- `sessionId`

它先调用 `ctx.heterogeneousAgentService.heteroFinish(...)`，确保 renderer 订阅者能收到最终 `agent_runtime_end`。然后它会尝试推进 task lifecycle：

1. 通过 `TaskTopicModel.findByTopicId(topicId)` 找 task topic。
2. 如果 topic 还不是 `canceled`、`completed`、`failed`、`timeout` 这些终态，则继续。
3. 通过 `TaskModel.findById(taskTopic.taskId)` 找 task。
4. 根据 `result` 映射 reason：
   - `success` -> `done`
   - `cancelled` -> `interrupted`
   - `error` -> `error`
5. 调用 `TaskLifecycleService.onTopicComplete(...)`。

这段 lifecycle 更新被包在内部 `try/catch` 中，失败只记录日志，不影响 `heteroFinish` 返回 ack。原因是 CLI 已经结束，若这里失败导致重试，可能产生重复副作用。代码还特别防止重复调用非幂等的 `onTopicComplete`。

### client-side 完成回写：`updateClientTaskThreadStatus`

这个接口用于 desktop client 本地执行任务完成后回写服务端状态。

它会：

1. 查找 `Thread`。
2. 根据 `completionReason` 映射 `ThreadStatus`：
   - `done` -> `Completed`
   - `error` -> `Failed`
   - `interrupted` -> `Cancel`
3. 计算 `completedAt` 和 `duration`。
4. 更新 Thread metadata，包括 cost、messages、steps、tokens、toolCalls、error 等指标。
5. 如果有 `resultContent` 且 thread 有 `sourceMessageId`，会更新源 task message 的 content。

根据当前片段推断，后续还会返回更新后的状态或成功标记；依据是该接口是 mutation，且客户端 `src/services/aiAgent.ts` 有对应封装用于任务完成后的 UI/数据库同步。

## 小白阅读顺序

1. 先看 `src/server/routers/lambda/index.ts`，确认 `aiAgentRouter` 是如何挂到 `lambdaRouter.aiAgent` 上的。这样能理解为什么客户端路径是 `lambdaClient.aiAgent.xxx`。

2. 再看 `src/services/aiAgent.ts`。这是前端/客户端对 tRPC 的包装，比 router 更接近真实调用方式。建议先找这些方法：
   - `execAgentTask`
   - `execSubAgentTask`
   - `getSubAgentTaskStatus`
   - `interruptTask`
   - `createClientTaskThread`
   - `updateClientTaskThreadStatus`

3. 回到 `src/server/routers/lambda/aiAgent.ts`，先读顶部 import，按“类型/模型/tRPC/服务”四组理解依赖，不要一行行硬背。

4. 读所有 `z.object(...)` schema，重点看字段名和注释。这个文件的业务边界很大程度体现在 schema 里：哪些字段可选、哪些字段互斥、哪些场景需要 `parentMessageId`、哪些场景需要 `toolMessageId`。

5. 读 `aiAgentProcedure` 和 `heteroAgentProcedure`。理解普通用户请求和异构 agent 回调请求的权限边界不同。

6. 读主路径 `execAgent`。这是最核心入口，重点看它如何把 router input 转成 `AiAgentService.execAgent` 参数。

7. 读任务相关路径：
   - `execSubAgentTask`
   - `getSubAgentTaskStatus`
   - `interruptTask`
   - `updateClientTaskThreadStatus`

   这一组能帮助你理解 `Thread`、`Message`、`operationId`、Redis runtime state 之间的关系。

8. 最后读异构 agent：
   - `AgentStreamEventSchema`
   - `heteroIngest`
   - `heteroFinish`

   这部分和普通 LLM 执行链路不同，重点是“外部 CLI agent 产生事件，服务端接收并转发/落生命周期”。

9. 如果要继续深入，再看下游：
   - `src/server/services/aiAgent/index.ts`
   - `src/server/services/agentRuntime`
   - `src/server/services/heterogeneousAgent`
   - `src/database/models/thread`
   - `src/database/models/message`

## 常见误区

1. 不要把 `aiAgent.ts` 理解成“真正执行模型调用的地方”。它是 tRPC router 层，真正的执行逻辑主要在 `AiAgentService` 和 `AgentRuntimeService`。

2. 不要忽略 `parentMessageId` 的含义。在 `execAgent` 中，只要有 `parentMessageId`，router 就会传 `resume: true`，表示这是 regeneration、continue 或 human approval resume，不应再创建新的 user message。

3. 不要把 `ThreadStatus` 和 `TaskStatusResult['status']` 混为一谈。数据库里的 thread 状态有 `Processing`、`InReview`、`Todo`、`Completed`、`Failed`、`Cancel` 等；对前端任务状态会再映射成 `processing`、`completed`、`failed`、`cancel`。

4. 不要认为 `getSubAgentTaskStatus` 只是读数据库。它会在 processing 时尝试读取 Redis runtime 状态，并把实时指标补写回 Thread metadata。这个接口有“查询 + 补偿同步”的双重作用。

5. 不要在 group mode 的消息查询中随便加 `agentId` 过滤。`createClientGroupAgentTaskThread` 的注释明确说明，群组 thread 里可能同时存在 supervisor 和 worker 的消息，按单个 agentId 过滤会漏上下文。

6. 不要把 `heteroIngest` 当成普通登录用户接口。它走 `heteroAgentProcedure`，需要专门的 `hetero-operation` JWT，安全边界和 `aiAgentProcedure` 不一样。

7. 不要假设 `heteroFinish` 只会调用一次。代码里专门做了终态检查，因为 cancelled 信号、正常退出、网络重试都可能导致重复 finish；而 `TaskLifecycleService.onTopicComplete` 不是完全幂等的。

8. 不要把 `clientRuntime: 'desktop'` 当成普通字段。它关系到 `executor: 'client'` 的工具是否能通过 Agent Gateway 分发回桌面端执行，例如 local-system 或 stdio MCP。

9. 不要忽视 `userInterventionConfig`。对于 CLI、cron、bot 这类 headless 客户端，可以传 `{ approvalMode: 'headless' }`，避免工具调用一直等待人工审批。

10. 不要只看成功路径。这个文件大量使用 `TRPCError` 把业务错误转换成客户端可理解的错误码，例如 `NOT_FOUND`、`BAD_REQUEST`、`INTERNAL_SERVER_ERROR`。阅读时要把错误映射也当成 API 契约的一部分。
