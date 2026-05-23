# 目录：src/server/workflows-hono

## 它负责什么

`src/server/workflows-hono` 是后端异步工作流的 Hono 入口层，主要把 `/api/workflows/*` 这一组 POST 请求统一接入到 Hono app，再分发给不同业务域的 workflow 或 webhook handler。它本身不是业务算法的集中地，而更像“工作流 HTTP 适配层”：负责路由挂载、QStash 签名校验、Upstash Workflow `serve`/`serveMany` 接入，以及把请求委托给 `src/server/services/*` 或 `src/server/workflows/*` 中的真实业务实现。

从当前片段看，这个目录覆盖三类流程：`agent-signal` 的信号工作流与定时调度、`memory-user-memory` 的用户记忆提取流水线、`task` 的任务调度和心跳类 webhook。Next.js 侧入口在 `src/app/(backend)/api/workflows/[[...route]]/route.ts`，它只导入 `@/server/workflows-hono` 并把 `POST` 请求交给 `app.fetch(request)`。因此这个目录是 `/api/workflows` 下 Hono 化 workflow 的总入口，但不是所有 workflow 的唯一实现位置；例如 `agent-eval-run` 仍分散在 `src/app/(backend)/api/workflows/agent-eval-run/*/route.ts` 和 `src/server/workflows/agentEvalRun`。

## 直接子目录地图

`agent-signal` 负责 Agent Signal 相关 workflow endpoint。它的 `index.ts` 挂载两个方向：`/cron-hourly-nightly-self-review` 是受 `qstashAuth()` 保护的 QStash cron handler，用于批量派发 nightly review source event；`/run` 使用 `@upstash/workflow/hono` 的 `serve` 包装 `runAgentSignalWorkflow`，进入真正的 Agent Signal workflow 执行逻辑。

`memory-user-memory` 负责用户记忆抽取和画像更新的 Upstash Workflow 路由。它的 `index.ts` 下面挂了 hourly 入口、persona writing 更新入口，以及 chat topic 分层处理管线：按用户、按用户 topic、按 topic batch、按单 topic 逐层推进。实际阶段文件在 `memory-user-memory/workflows`。

`task` 负责任务运行器相关 webhook。它的 `index.ts` 注册 `on-topic-complete`、`heartbeat-tick`、`schedule-dispatch`、`schedule-execute`、`watchdog`。这些 handler 多数是薄适配层，校验 payload 后调用 `src/server/services/taskRunner/*` 或任务模型服务。

`middlewares` 目前放的是 `qstashAuth.ts`，用于普通 QStash webhook 的签名校验。注释明确提醒：Upstash Workflow 的 `serve()` 端点应使用 workflow SDK 自带校验，而不是这个中间件。

此外根部还有 `qstashClient.ts`，封装 `createWorkflowQstashClient()`，把 `QSTASH_TOKEN` 和从 `parseMemoryExtractionConfig()` 解析出的额外 headers 注入 Upstash QStash client，供 Workflow 中间步骤或受部署保护的环境使用。

## 关键入口

总入口是 `src/server/workflows-hono/index.ts`。它创建 `new Hono().basePath('/api/workflows')`，然后依次挂载：

`/agent-signal` 到 `src/server/workflows-hono/agent-signal/index.ts`；

`/memory-user-memory` 到 `src/server/workflows-hono/memory-user-memory/index.ts`；

`/task` 到 `src/server/workflows-hono/task/index.ts`。

Next.js 暴露层是 `src/app/(backend)/api/workflows/[[...route]]/route.ts`。这个文件没有业务逻辑，只声明 `export const POST = (request: Request) => app.fetch(request)`。所以阅读路由时要从 Next catch-all route 跳到 Hono app，再看各子 app 的 `index.ts`。

`qstashAuth()` 是普通 webhook 的关键中间件入口。它在存在 `QSTASH_CURRENT_SIGNING_KEY` 时读取原始 body，并调用 `verifyQStashSignature`；本地或 Electron 等未配置 signing key 的环境会跳过校验。根据当前片段推断，这个设计是为了让同一套 endpoint 同时支持生产 QStash 回调和本地调试，依据是注释中明确写到 dev/electron 会跳过校验。

## 主流程位置

Agent Signal 的主执行流不在本目录深处，而在 `src/server/workflows/agentSignal/run.ts`。`src/server/workflows-hono/agent-signal/index.ts` 的 `/run` 只是通过 `serve<AgentSignalWorkflowRunPayload>((context) => runAgentSignalWorkflow(context))` 把 Upstash Workflow context 交过去。定时扫描入口在 `src/server/workflows-hono/agent-signal/handlers/scheduleNightlyReview.ts`，它读取分页 cursor、limit、targetLimit、whitelist，创建 `createServerNightlyReviewScheduleService(db)`，再派发 nightly review 请求。

用户记忆的主流程集中在 `src/server/workflows-hono/memory-user-memory/workflows`。`hourly.ts` 是小时级 cron 起点；`processUsers.ts` 负责获取用户批次并推进下一页；`processUserTopics.ts` 处理某用户的 topic 批次；`processTopics.ts` 进一步 fan-out 到单 topic；`processTopic.ts` 是单 topic 级别的具体处理 workflow；`personaUpdate.ts` 则是 writing persona 更新管线。这里大量使用 `context.run`、`context.invoke` 或 QStash publish 来把长任务拆成可重试步骤。

Task 的主流程位置在 `src/server/workflows-hono/task/handlers` 和 `src/server/services/taskRunner` 之间。`scheduleDispatch.ts` 是中心调度扫描器：读取 schedule-mode tasks，按 cron pattern、timezone、last heartbeat 判断是否到期，然后在队列模式下 fan-out 到 `/api/workflows/task/schedule-execute`；本地模式则直接调用 `runScheduleTick`。`scheduleExecute.ts`、`heartbeatTick.ts` 是单任务执行适配层，分别委托 `runScheduleTick`、`runHeartbeatTick`。`onTopicComplete.ts` 和 `watchdog.ts` 则处理 topic 完成回调与看门狗类检查。

## 推荐阅读顺序

建议先读 `src/app/(backend)/api/workflows/[[...route]]/route.ts`，确认 Next.js 如何把请求交给 Hono。然后读 `src/server/workflows-hono/index.ts`，建立 `/api/workflows` 下的三大分支地图。

第二步读三个子目录的 `index.ts`：`agent-signal/index.ts`、`memory-user-memory/index.ts`、`task/index.ts`。这一步只看 endpoint 名称、是否用 `qstashAuth()`、是否用 `serve` 或 `serveMany`，不要急着进入每个 handler。

第三步按兴趣进入主流程：如果看 Agent Signal，接着读 `agent-signal/handlers/scheduleNightlyReview.ts` 和 `src/server/workflows/agentSignal/run.ts`；如果看用户记忆，按 `hourly.ts`、`processUsers.ts`、`processUserTopics.ts`、`processTopics.ts`、`processTopic.ts` 的顺序读；如果看任务调度，先读 `task/handlers/scheduleDispatch.ts`，再读 `scheduleExecute.ts`、`heartbeatTick.ts` 以及对应的 `src/server/services/taskRunner`。

最后再读 `middlewares/qstashAuth.ts` 和 `qstashClient.ts`，理解安全边界和 Upstash client 的共享配置。这两个文件更偏基础设施，先读会缺少业务触发场景。

## 常见误区

第一个误区是把 `src/server/workflows-hono` 当成所有 workflow 的业务实现目录。实际上它主要是 Hono transport 层；很多核心逻辑在 `src/server/services`、`src/server/workflows`、数据库模型或专门 service 中。

第二个误区是认为所有 `/api/workflows` 都由这个 Hono catch-all 接管。当前片段显示，`agent-eval-run` 仍有独立的 Next route 文件，例如 `src/app/(backend)/api/workflows/agent-eval-run/*/route.ts`。所以排查 workflow 时要先看具体路径是否落在 Hono catch-all 的子路由里。

第三个误区是混用 `qstashAuth()` 和 Upstash Workflow `serve()` 的认证方式。注释说明普通一次性 QStash webhook 使用 `qstashAuth()`；而 Workflow 多步骤 endpoint 使用 `@upstash/workflow/hono` 的内建机制。

第四个误区是忽略 `serveMany`。`memory-user-memory/index.ts` 对 `/pipelines/chat-topic/process-topic` 使用 `serveMany`，原因是 `context.invoke(processTopicWorkflow)` 会改写 URL 最后一段为 workflowId，需要靠 `serveMany` 按 final segment 分派。这里如果改成普通 `serve`，根据当前注释推断，子 workflow 调度会找不到正确处理器。
