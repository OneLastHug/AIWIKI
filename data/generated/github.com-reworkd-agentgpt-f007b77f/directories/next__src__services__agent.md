# 子系统：next/src/services/agent

## 解决什么问题

`next/src/services/agent` 是前端 Agent 运行时的编排层。它不直接实现大模型推理，而是在浏览器端维护一次 Agent run 的生命周期、任务队列、消息展示、后端 API 调用、流式结果更新和错误处理。可以把它理解为 AgentGPT 的“前端执行引擎”：页面输入一个 goal 后，这里负责把 goal 转成初始任务、逐个分析任务、执行任务、把输出写回 UI，并在暂停、停止、聊天、总结等交互中保持状态一致。

这个目录位于 UI 与后端 Agent API 之间。向上服务 `next/src/pages/index.tsx`、`next/src/components/index/chat.tsx`、`next/src/components/console/SummarizeButton.tsx` 等交互组件；向下调用由 `NEXT_PUBLIC_BACKEND_URL` 指向的后端接口，例如 `/api/agent/start`、`/api/agent/analyze`、`/api/agent/execute`、`/api/agent/create`、`/api/agent/chat`、`/api/agent/summarize`。根据当前片段推断，真正的 Agent 推理和工具执行在 Python 后端 `platform/reworkd_platform/web/api/agent/views.py` 及其服务层中完成，依据是前端通过 `api-utils.ts`、`stream-utils.ts` 拼接后端基础地址并发起请求。

## 相关目录和文件

`next/src/services/agent/autonomous-agent.ts` 是核心调度器，负责 Agent 生命周期和 `AgentWork` 工作项队列。`next/src/services/agent/agent-run-model.tsx` 抽象一次运行所需的 goal、任务列表和生命周期，默认实现 `DefaultAgentRunModel` 把状态落到 Zustand store。`next/src/services/agent/agent-api.ts` 封装非流式 Agent API 请求，并负责保存 `runId`、创建持久化 Agent、保存消息。

`next/src/services/agent/message-service.ts` 是消息写入和错误消息转换层，向 `messageStore` 写入 goal、system、task、error 等消息。`next/src/services/agent/analysis.ts` 定义后端分析返回的 `Analysis` 类型，包括 `reason`、`search`、`wikipedia`、`image`、`code` 等动作。

`next/src/services/agent/agent-work/*` 是一组可执行工作单元：`start-task-work.ts` 负责启动 goal 并生成初始任务；`analyze-task-work.ts` 分析当前任务；`execute-task-work.ts` 流式执行任务；`create-task-work.ts` 根据执行结果生成更多任务；`chat-work.ts` 在已有任务结果上追加聊天；`summarize-work.ts` 汇总已完成结果。需要注意，当前 `execute-task-work.ts` 完成后没有接上 `CreateTaskWork`，因此额外任务生成逻辑存在但未从主链路自动触发；这是根据 `next()` 返回值和 `AutonomousAgent.run()` 队列推进逻辑推断的。

## 核心对象

`AutonomousAgent` 是本目录最重要的对象。它持有 `AgentRunModel`、`MessageService`、`AgentApi`、`ModelSettings` 和可选 `Session`，内部维护 `workLog: AgentWork[]`。`run()` 会把生命周期置为 `running`，不断取出队首工作项执行、收尾、追加下一个工作项，并在队列为空时从当前任务生成 `AnalyzeTaskWork`。当没有任务可做时，它将 Agent 停止。

`AgentWork` 是工作项协议，包含 `run()`、`conclude()`、`next()`、`onError()`。这种设计把“执行副作用”和“执行后更新 UI/保存消息”拆开，使暂停时可以延迟执行 `conclude()`。`StartGoalWork`、`AnalyzeTaskWork`、`ExecuteTaskWork`、`ChatWork`、`SummarizeWork` 都实现这个协议。

`AgentApi` 管理请求体公共字段：`goal`、`model_settings`、`run_id`。首次后端响应返回 `run_id` 后会保存在实例上，后续分析、执行、聊天、总结共用同一次 run。它还通过 `useAgentStore.setIsAgentThinking` 控制“思考中”状态，并通过 `useAgent()` 暴露的 tRPC mutation 保存 Agent 和消息。

`DefaultAgentRunModel` 是 `AgentRunModel` 的 Zustand 适配器。它从 `useTaskStore` 读取 `started` 任务作为 remaining tasks，把第一个 remaining task 作为 current task，并通过 `updateTaskStatus`、`updateTaskResult` 更新任务状态和结果。

## 运行流程

用户在首页输入 goal 后，`next/src/pages/index.tsx` 创建 `DefaultAgentRunModel`、`MessageService`、`AgentApi` 和 `AutonomousAgent`，随后调用 `newAgent.run()`。

第一次进入 `run()` 时，`workLog` 初始包含 `StartGoalWork`。它先发送 goal 消息，再请求 `/api/agent/start` 获取初始任务，随后如用户已登录则通过 tRPC `agent.create` 创建数据库中的 Agent，并保存 goal 消息。`conclude()` 会把初始任务逐条渲染到 UI，同时加入 `taskStore`。

当工作队列为空时，`AutonomousAgent.addTasksIfWorklogEmpty()` 会取 `model.getCurrentTask()`，也就是第一个 `started` 任务，并创建 `AnalyzeTaskWork`。分析阶段把任务状态改为 `executing`，请求 `/api/agent/analyze`，把当前启用工具名也传给后端。分析完成后，`MessageService.sendAnalysisMessage()` 根据 action 生成系统提示，例如搜索、Wikipedia、图片、代码或普通生成。

如果分析成功，`AnalyzeTaskWork.next()` 生成 `ExecuteTaskWork`。执行阶段通过 `streamText()` 请求 `/api/agent/execute`，接收 text/event-stream，并在每个文本 chunk 到达时追加到 message 的 `info` 字段，同时更新任务 result。流结束后保存消息，并把任务状态改为 `completed`。队列再次为空后，调度器会寻找下一个 `started` 任务，直到没有剩余任务，最后 `stopAgent()`。

聊天和总结不是主任务循环的一部分。`agent.chat(message)` 会在必要时暂停 Agent，然后通过 `/api/agent/chat` 基于已完成任务结果流式生成回复。`agent.summarize()` 会在 Agent 停止后，通过 `/api/agent/summarize` 汇总已有任务结果。

## 上下游依赖

上游 UI 主要包括 `next/src/pages/index.tsx` 的启动逻辑、`next/src/components/index/chat.tsx` 的聊天输入和 Agent 控制、`next/src/components/console/SummarizeButton.tsx` 的总结入口。状态层依赖 `next/src/stores/agentStore.ts`、`next/src/stores/taskStore.ts`、`next/src/stores/messageStore.ts`，分别保存生命周期和工具、任务队列、聊天窗口消息。

API 层依赖 `next/src/services/api-utils.ts` 和 `next/src/services/stream-utils.ts`。前者使用 axios 处理普通 POST，并注入 session access token；后者使用 fetch 读取流式响应。请求体类型来自 `next/src/utils/interfaces.ts`，模型设置通过 `toApiModelSettings()` 转成后端需要的 `language`、`model`、`temperature`、`max_tokens` 等字段。

持久化依赖 `next/src/hooks/useAgent.ts` 和 `next/src/server/api/routers/agentRouter.ts`。前端通过 tRPC 调用 `agent.create`、`agent.save`，后端 Next API router 使用 Prisma 创建 `Agent` 和 `AgentTask` 记录。真正执行 Agent 任务的外部后端入口根据当前片段是 `platform/reworkd_platform/web/api/agent/views.py`，它提供 start、analyze、execute、create、summarize、chat、tools 等接口。

## 修改时最容易踩的坑

第一，生命周期不是局部变量，而是存放在 `useAgentStore` 中。`AutonomousAgent`、UI 控件、流式请求关闭条件都读取同一份状态，修改 `running`、`pausing`、`paused`、`stopped` 的语义时必须同步检查暂停、停止、聊天和总结。

第二，任务身份字段有 `id` 和 `taskId` 两套。`taskStore.updateTask()` 同时比较 `task.id === updatedTask.id` 和 `task.taskId == updatedTask.taskId`，而不同消息创建路径使用 `uuid.v4` 或 `uuid.v1`。改任务更新逻辑时很容易导致流式结果写不到原任务上。

第三，`run()` 把 `work.run()` 和 `work.conclude()` 分开，并在暂停时用 `lastConclusion` 延迟收尾。新增 `AgentWork` 时不要把所有副作用都塞进 `run()`，否则暂停恢复后可能漏保存消息或重复渲染。

第四，`AgentApi.post()` 会设置 `isAgentThinking`，但 `execute`、`chat`、`summarize` 直接调用 `streamText()`，没有经过 `AgentApi.post()`。如果统一 loading 行为，需要同时处理普通请求和流式请求。

第五，`CreateTaskWork` 当前没有自然接入主执行链路。若希望任务执行后自动生成新任务，需要明确让 `ExecuteTaskWork.next()` 或调度器接入它，并注意避免无限任务增长和重复保存。

第六，保存 Agent 消息只在已登录时生效。`useAgent()` 中未认证会让 `createAgent` 返回 `undefined`，`saveAgent` 也不会发送 mutation；本地 UI 仍可运行，但不会持久化。

## 推荐阅读顺序

1. 先读 `next/src/pages/index.tsx` 中创建 `AutonomousAgent` 的代码，理解对象如何被装配。
2. 再读 `next/src/services/agent/autonomous-agent.ts`，把生命周期、队列和暂停恢复逻辑看清楚。
3. 接着读 `next/src/services/agent/agent-work/agent-work.ts` 及 `start-task-work.ts`、`analyze-task-work.ts`、`execute-task-work.ts`，掌握主任务链路。
4. 然后读 `next/src/services/agent/agent-api.ts`、`next/src/services/stream-utils.ts`、`next/src/services/api-utils.ts`，理解普通请求与流式请求的差异。
5. 最后读 `next/src/services/agent/message-service.ts`、`next/src/stores/agentStore.ts`、`next/src/stores/taskStore.ts`、`next/src/stores/messageStore.ts`，确认 UI 消息和任务状态如何落地。
