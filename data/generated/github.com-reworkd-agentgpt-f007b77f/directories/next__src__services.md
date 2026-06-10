# 子系统：next/src/services

## 解决什么问题

`next/src/services` 是前端应用的“服务层”和 Agent 执行编排层。它把页面、hooks、Zustand store 与后端 HTTP API、流式响应、OAuth 安装流程隔开，让 UI 不直接拼接请求、处理鉴权 header 或理解 Agent 任务生命周期。

这个目录承担两类职责。第一类是通用网络访问能力：`api-utils.ts` 基于 `axios` 封装简单的 `get`、`post`、`delete_` 和 `withRetries`；`fetch-utils.ts` 基于原生 `fetch` 和 `zod` 做带 schema 校验的请求；`stream-utils.ts` 专门处理 `text/event-stream` 风格的流式文本。第二类是 Agent 业务编排：`agent` 子目录负责从目标生成任务、分析任务、执行任务、写入消息、更新任务状态、保存历史，以及支持暂停、停止、聊天和总结。

根据当前片段推断，这一层主要运行在 Next.js 客户端侧，因为它依赖 `next-auth` session、`localStorage` 间接状态、Zustand store、React hooks 提供的 `agentUtils`，并读取 `env.NEXT_PUBLIC_BACKEND_URL` 这类公开环境变量。

## 相关目录和文件

`next/src/services/api-utils.ts` 是较早或偏 Agent API 使用的请求封装，返回未校验的泛型数据，并支持从 `Session` 中取 `accessToken`。`next/src/services/fetch-utils.ts` 是更严格的请求封装，调用方必须传入 `zod` schema，响应会经过 `schema.parse`。`next/src/services/stream-utils.ts` 负责 POST 后端并逐块读取文本流，供任务执行、聊天、总结使用。

`next/src/services/agent` 是核心区域。`autonomous-agent.ts` 是 Agent 主循环；`agent-api.ts` 封装 `/api/agent/start`、`/api/agent/create`、`/api/agent/analyze` 等非流式端点；`agent-run-model.tsx` 定义运行模型接口和默认实现；`message-service.ts` 负责把业务事件转成 UI 消息；`analysis.ts` 定义任务分析结果类型。`agent-work` 下的类把一次运行拆成可执行的 work item，例如 `StartGoalWork`、`AnalyzeTaskWork`、`ExecuteTaskWork`、`ChatWork`、`SummarizeWork`。

旁支服务包括 `next/src/services/api/org.ts` 的 `OrganizationApi`，用于读取组织用户；`next/src/services/workflow/oauthApi.ts` 的 `OauthApi`，用于安装、卸载和查询第三方 provider 连接状态。

上游调用主要来自 `next/src/pages/index.tsx`、`next/src/hooks/useModels.ts`、`next/src/hooks/useTools.ts`、`next/src/hooks/useSID.ts`。状态依赖主要在 `next/src/stores/agentStore.ts`、`next/src/stores/taskStore.ts`、`next/src/stores` 中的 message store。

## 核心对象

`AutonomousAgent` 是最重要的协调者。它持有 `AgentRunModel`、`MessageService`、`AgentApi`、`ModelSettings` 和可选 `Session`，内部维护 `workLog` 队列。它不直接渲染 UI，也不直接持久化数据库，而是通过模型、消息服务和 API 对象间接完成这些动作。

`AgentRunModel` 是运行状态抽象，定义了 `getGoal`、`getLifecycle`、`setLifecycle`、`getRemainingTasks`、`getCurrentTask`、`updateTaskStatus`、`updateTaskResult`、`getCompletedTasks`、`addTask` 等方法。默认实现 `DefaultAgentRunModel` 实际读写 `useAgentStore` 和 `useTaskStore`，因此 Agent 的状态变化会反映到前端界面。

`AgentApi` 是 Agent 与后端的普通 JSON API 边界。它负责组装 `RequestBody`，携带 `goal`、`model_settings`、`run_id`，并维护后端返回的 `runId`。它还通过 `agentUtils.createAgent` 和 `agentUtils.saveAgent` 接入 tRPC/Prisma 风格的本地 Agent 历史保存逻辑。

`MessageService` 是消息适配器。它把目标、任务开始、任务跳过、分析动作、错误等转换成 `Message`，并通过构造函数传入的 `renderMessage` 或 `useMessageStore.updateMessage` 推送到 UI。错误处理也集中在这里，包括 axios 网络错误、409、422、429、403、404 等状态码的翻译。

`AgentWork` 是一个小型命令接口，包含 `run`、`conclude`、`next`、`onError`。具体 work class 把 Agent 主循环拆成阶段：启动目标、分析任务、执行任务、聊天、总结等。

## 运行流程

首页 `next/src/pages/index.tsx` 中，用户输入 goal 后会创建 `DefaultAgentRunModel`、`MessageService`、`AgentApi` 和 `AutonomousAgent`，然后调用 `newAgent.run()`。

`AutonomousAgent.run()` 先把 lifecycle 设为 `running`，初始 `workLog` 中有 `StartGoalWork`。`StartGoalWork.run()` 会发送 goal 消息，调用 `AgentApi.getInitialTasks()` 请求 `/api/agent/start`，并创建持久化 Agent 记录；`conclude()` 再把后端返回的任务逐个写入消息流和 task store。

当 `workLog` 为空时，`addTasksIfWorklogEmpty()` 会从 `AgentRunModel.getCurrentTask()` 取出第一个 `started` 任务，并加入 `AnalyzeTaskWork`。分析阶段把任务状态改成 `executing`，调用 `/api/agent/analyze`，同时带上当前激活工具名。分析完成后，`MessageService.sendAnalysisMessage()` 会生成“搜索、Wikipedia、图片、代码或普通响应”等系统提示。随后 `AnalyzeTaskWork.next()` 创建 `ExecuteTaskWork`。

`ExecuteTaskWork` 会发送一条执行消息，然后通过 `streamText("/api/agent/execute", ...)` 接收流式文本。每收到一段文本，就累加到 `executionMessage.info`，更新 task result，并更新 message store。流结束后保存消息，把任务状态改为 `completed`。主循环随后继续找下一个 `started` 任务，直到没有任务可执行，最后 `stopAgent()`。

聊天和总结不是常规任务链的一部分。`AutonomousAgent.chat()` 会在必要时暂停当前运行，执行 `ChatWork`，请求 `/api/agent/chat` 并流式更新回答。`summarize()` 执行 `SummarizeWork`，把已完成任务的结果发送到 `/api/agent/summarize`。

## 上下游依赖

上游是页面与 hooks。`next/src/pages/index.tsx` 负责创建 Agent 实例并触发运行；`useModels` 通过 `fetch-utils.get` 读取 `/api/models`；`useTools` 读取 `/api/agent/tools` 并把激活工具写入 `useAgentStore`；`useSID` 使用 `OauthApi` 查询、安装和卸载 SID 连接。

下游是后端 API 和本地状态。HTTP 请求统一指向 `env.NEXT_PUBLIC_BACKEND_URL`，鉴权来自 `Session.accessToken`，组织上下文可通过 `X-Organization-Id` 传递。Agent 的持久化历史依赖 `useAgent()` 返回的 `createAgent`、`saveAgent`，其实现连接 `next/src/server/api/routers/agentRouter.ts`。运行时状态依赖 Zustand：`useAgentStore` 保存 lifecycle、agent、thinking 状态和激活工具；`useTaskStore` 保存任务；message store 保存对话消息。

外部服务相关代码集中在 `OauthApi`。它根据 provider 拼接认证、卸载、信息查询路径，并在安装时构造 redirect 地址。文档中不展开真实外部地址，只需知道它会把浏览器导向后端返回的安装 URL。

## 修改时最容易踩的坑

第一，`api-utils.ts` 和 `fetch-utils.ts` 名字相近但语义不同。前者用 `axios`，不做响应 schema 校验，参数接收 `Session`；后者用 `fetch`，强制 `zod` 校验，参数接收 `accessToken` 和 `organizationId`。新增接口时要按调用场景选择，否则错误处理和类型保障会不一致。

第二，Agent lifecycle 是协作式停止。`streamText` 的 `shouldClose` 只在读流循环中检查，`AutonomousAgent.run()` 也会在 work 之间检查 lifecycle。修改暂停、停止逻辑时，要同时考虑 `running`、`pausing`、`paused`、`stopped`，否则容易出现 UI 显示暂停但流仍在写消息的情况。

第三，`AgentApi.runId` 只在首次普通 POST 返回后记录。流式执行、聊天、总结都依赖这个 `runId`。如果调整启动流程，必须保证 `/api/agent/start` 或其他前置请求能先建立 run id，否则后续执行请求可能缺少上下文。

第四，`MessageService` 与 task store 是分离的。发送消息不等于添加任务；`createTaskMessages()` 同时调用 `messageService.startTask()` 和 `model.addTask()`。新增任务入口时如果只做其中一边，界面消息和执行队列会不同步。

第五，`CreateTaskWork` 当前在片段中没有被主循环引用。根据当前片段推断，它可能是旧的或未接入的“追加任务”阶段。修改任务生成策略前，应先确认产品预期和历史提交，避免误以为每个任务完成后都会自动调用 `/api/agent/create`。

第六，`stream-utils.ts` 对 409 会解析后端错误并抛出 `detail`，其他非 ok 状态没有统一处理。调用方虽然有 `onError`，但不同请求封装的错误形态不同，新增错误分支时要兼容 axios error、普通 `Error` 和后端结构化错误。

## 推荐阅读顺序

1. 先读 `next/src/pages/index.tsx`，理解 Agent 是如何从用户输入被创建和启动的。
2. 再读 `next/src/services/agent/autonomous-agent.ts`，掌握主循环、暂停、停止、聊天和总结入口。
3. 接着读 `next/src/services/agent/agent-run-model.tsx`、`next/src/stores/agentStore.ts`、`next/src/stores/taskStore.ts`，明确状态实际存放在哪里。
4. 然后读 `next/src/services/agent/agent-api.ts` 和 `next/src/utils/interfaces.ts`，理解发给后端的请求体结构、`run_id` 与模型设置。
5. 继续读 `next/src/services/agent/agent-work/start-task-work.ts`、`analyze-task-work.ts`、`execute-task-work.ts`，按运行阶段串起来看。
6. 最后读 `next/src/services/stream-utils.ts`、`fetch-utils.ts`、`api-utils.ts`、`workflow/oauthApi.ts`、`api/org.ts`，补齐网络访问、流式读取、OAuth 与组织 API 的边界。
