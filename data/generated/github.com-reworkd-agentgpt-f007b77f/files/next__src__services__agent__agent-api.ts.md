# 文件：next/src/services/agent/agent-api.ts

## 一句话定位

`next/src/services/agent/agent-api.ts` 是前端 Agent 运行层的 API 门面：它把“目标、模型设置、会话、运行 ID、持久化工具”等上下文封装起来，为 `AutonomousAgent` 的各类 work 提供创建 Agent、保存消息、生成任务、分析任务这些高层能力。

## 它暴露/定义了什么

该文件主要定义并导出 `AgentApi` 类，同时定义内部类型 `ApiProps`。

`ApiProps` 由 `RequestBody` 中的 `model_settings`、`goal` 组成，并额外携带可选 `session` 和必需的 `agentUtils`。其中 `agentUtils` 来自 `next/src/hooks/useAgent.ts`，用于通过 tRPC 创建和保存数据库里的 Agent 记录。

`AgentApi` 实例内部维护两个运行期状态：

- `agentId`：数据库中 Agent 记录的 id，用于后续保存消息。
- `runId`：后端 agent 接口返回的 `run_id`，用于把多次 `/api/agent/*` 请求串成同一次运行上下文。

它暴露的方法包括 `createAgent()`、`saveMessages()`、`getInitialTasks()`、`getAdditionalTasks()`、`analyzeTask()`。真正发请求的通用逻辑收敛在私有方法 `post<T>()` 中。

## 谁调用它

直接实例化发生在 `next/src/pages/index.tsx`。用户提交 goal 后，页面创建 `DefaultAgentRunModel`、`MessageService` 和 `AgentApi`，再把 `AgentApi` 注入 `AutonomousAgent`。

运行过程中，`AgentApi` 主要被 `next/src/services/agent/autonomous-agent.ts` 管理的 work 对象调用：

- `StartGoalWork` 调用 `getInitialTasks()`、`createAgent()`、`saveMessages()`。
- `AnalyzeTaskWork` 调用 `analyzeTask()` 和 `saveMessages()`。
- `CreateTaskWork` 调用 `getAdditionalTasks()` 和 `saveMessages()`。

根据当前片段推断，其他 work 如执行、总结、聊天可能通过相邻服务调用不同接口，但目标文件中只覆盖任务启动、任务创建和任务分析这几类能力。

## 它调用谁

`AgentApi` 对外部依赖较集中：

- 调用 `agentUtils.createAgent()` 创建持久化 Agent 记录。
- 调用 `agentUtils.saveAgent()` 保存当前 Agent 的 `tasks`，这里的 `tasks` 实际上传入的是前端消息数组 `Message[]`。
- 调用 `apiUtils.post()` 向后端 API 发请求。
- 调用 `useAgentStore.getState().setIsAgentThinking()` 控制全局“Agent 正在思考”的 UI 状态。
- 调用 `useAgentStore.getState().tools` 读取当前启用工具名称，并传给任务分析接口。
- 依赖 `RequestBody`、`Message`、`Analysis`、`Session` 等类型约束请求和响应结构。

它访问的后端路径包括 `/api/agent/start`、`/api/agent/create`、`/api/agent/analyze`。

## 核心流程

一次典型运行从 `pages/index.tsx` 开始：用户输入 goal 后创建 `AgentApi`，再创建 `AutonomousAgent` 并执行 `run()`。

`AutonomousAgent` 初始 work 是 `StartGoalWork`。该 work 先通过 `messageService` 生成 goal 消息，然后调用 `AgentApi.getInitialTasks()` 请求后端基于 goal 生成初始任务。随后调用 `createAgent()`，如果登录态允许，会通过 `agentUtils` 在数据库中创建 Agent 记录，并把返回 id 存入 `agentId`。之后 `saveMessages()` 会把 goal 消息和后续任务消息保存到该 Agent 记录。

当任务进入执行前分析阶段，`AnalyzeTaskWork` 调用 `analyzeTask(task)`。该方法把当前任务文本和 store 中启用的 `tool_names` 发送到 `/api/agent/analyze`，后端返回 `Analysis`，再由 work 转成前端消息并保存。

任务执行完成后，`CreateTaskWork` 调用 `getAdditionalTasks()`，把当前任务、剩余任务、已完成任务和执行结果传给 `/api/agent/create`，让后端决定是否追加新任务。

所有这些后端请求都经过 `post<T>()`。它会统一拼出 `RequestBody`，附带 `model_settings`、`goal`、已有 `run_id` 和具体接口数据；请求期间设置 `isAgentThinking=true`，结束后在 `finally` 中恢复为 `false`。第一次请求返回的 `run_id` 会被保存到实例上，之后继续复用。

## 关键函数的高层作用

`createAgent()` 负责确保当前运行有一个可持久化的 Agent 记录。它有幂等保护：如果 `agentId` 已存在就直接返回，避免重复创建。未登录时 `useAgent()` 里的实现可能返回 `undefined`，因此这里也允许没有 `agentId` 的运行。

`saveMessages(messages)` 是前端消息到数据库 Agent 记录的保存入口。它依赖已有 `agentId`，没有 id 时静默跳过，因此匿名运行或创建失败不会阻塞主流程。

`getInitialTasks()` 用 goal 和模型设置请求初始任务列表，返回 `newTasks`。

`getAdditionalTasks(tasks, result)` 用当前任务执行结果以及任务队列上下文，请求后端生成追加任务。它承担的是任务规划续写，而不是执行任务本身。

`analyzeTask(task)` 请求后端分析任务，并把当前工具列表作为 `tool_names` 传入，说明任务分析结果可能会决定后续使用哪些工具或执行策略。

`post<T>()` 是该文件最核心的基础设施函数。它统一请求体结构、会话传递、`run_id` 续接和 thinking 状态切换，是所有 Agent 后端调用的一致入口。

## 修改风险

最大风险是破坏 `runId` 语义。`run_id` 只在第一次后端响应后写入，之后请求复用它；如果改成每次覆盖、漏传或提前生成，可能导致后端无法把 start、analyze、create 归到同一次运行。

第二个风险是 `isAgentThinking` 状态竞争。当前 `post()` 每次请求结束都会设为 `false`，如果未来引入并发 Agent 请求，较早完成的请求可能提前关闭 thinking 状态。现有流程大多串行，因此问题不明显。

第三个风险是持久化依赖 `agentId`。`saveMessages()` 在没有 `agentId` 时静默跳过，这是为了兼容未登录或创建失败场景；如果改成抛错，可能让匿名用户或登录状态异常时的 Agent 运行中断。

第四个风险是请求字段契约。`getAdditionalTasks()` 发送的是 `last_task`、`tasks`、`completed_tasks`、`result`；`analyzeTask()` 发送的是 `task` 和 `tool_names`。这些字段需要与后端 `/api/agent/*` 路由保持一致，改名或调整结构会直接影响任务生成和分析。

第五个风险是它混合了 API 调用与 UI store 状态。`AgentApi` 名义上是 API 层，但直接写 `useAgentStore`，因此重构到服务端、测试环境或非 React 生命周期中使用时，需要处理 Zustand store 依赖。
