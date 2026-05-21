# 目录：src/server/agent-hono

## 它负责什么

`src/server/agent-hono` 是 `/api/agent/*` 这一组服务端 HTTP 入口的 Hono 路由层。它不是前端页面，也不是 tRPC router，而是挂在 Next.js App Router 下的轻量 API 子应用：`src/app/(backend)/api/agent/[[...route]]/route.ts` 把 `GET`、`POST` 请求统一交给 `app.fetch(request)`，再由这里的 Hono `app` 按路径分发。

它主要负责三类事情：

1. 启动和推进 AI Agent 后台运行流程，例如 `POST /api/agent` 创建一次 agent operation，`POST /api/agent/run` 执行单个 step。
2. 接收异步系统回调，例如 QStash 回调、agent-gateway 工具结果、message gateway 状态变化。
3. 承接外部聊天平台和 Messenger 集成的 webhook/OAuth/install 路由，例如 Slack、Discord、Telegram、QQ、飞书、微信等平台入口。

这个目录本身更像“HTTP 适配层”：做路由、鉴权、请求体校验、调用服务、返回响应。真正的 agent 编排、数据库读写、平台消息处理，大多在 `src/server/services/*` 和 `src/server/modules/*` 中完成。

## 关键组成

`index.ts` 是总入口。它创建 `new Hono().basePath('/api/agent')`，然后注册所有 `/api/agent/*` 路由。注释里明确说明它由 `src/app/(backend)/api/agent/[[...route]]/route.ts` 这个 Next.js optional catch-all 挂载，并且允许旧的静态 `route.ts` 文件逐步迁移到 Hono：已有静态路由优先，删除旧路由后再在这里添加 handler。

`handlers/` 是业务处理器目录，代表文件包括：

- `execAgent.ts`：处理 `POST /api/agent`。读取 `{ userId, agentId | slug, prompt, appContext?, autoStart?, existingMessageIds? }`，校验必填字段后创建 `AiAgentService`，调用 `aiAgentService.execAgent(...)`，返回 `operationId` 等执行结果。
- `runStep.ts`：处理 `POST /api/agent/run`。读取 `operationId`、`stepIndex`、`context`、人工输入或工具审批信息，先通过 `AgentRuntimeCoordinator` 从 Redis operation metadata 中查 `userId`，再创建 `AgentRuntimeService` 执行 `executeStep(...)`。如果 step 被其他实例锁住，会返回 `429` 和 `Retry-After`，让 QStash 稍后重试。
- `toolResult.ts`：处理 `POST /api/agent/tool-result`。用 `zod` 校验 gateway 传来的工具执行结果，然后写入 Redis list：`tool_result:${toolCallId}`，并设置 120 秒 TTL。注释说明服务端 agent loop 会通过 `BLPOP` 等待这个结果继续运行。
- `gatewayCallback.ts`：处理 `POST /api/agent/gateway/callback`。接收外部 message gateway 的连接状态变化。它的鉴权写在 handler 内部，因为当 `MESSAGE_GATEWAY_ENABLED !== '1'` 时要先直接 `204` 忽略旧回调，避免关闭网关后还被陈旧回调覆盖本地状态。
- `platformWebhook.ts`：处理 `POST /api/agent/webhooks/:platform/:appId?`。它不自己解析平台消息，而是把原始 `Request` 交给 `getBotMessageRouter().getWebhookHandler(platform, appId)`。
- `messengerWebhook.ts`：处理 `POST /api/agent/messenger/webhooks/:platform`。它面向“共享 Messenger bot”，由 `getMessengerRouter()` 按 platform 分发。
- 其他 handler 如 `gatewayCron.ts`、`gatewayStart.ts`、`botCallback.ts`、`finalizeAbandoned.ts`、`messengerInstall.ts`、`messengerOAuthCallback.ts`，分别覆盖 cron 保活、非 Vercel 启动、bot 回调、遗留任务收尾、Messenger 安装和 OAuth 回跳。

`middlewares/` 是鉴权中间件目录：

- `qstashAuth.ts`：要求请求带有效 QStash signature。它先用 `c.req.text()` 读取原始 body，再调用 `verifyQStashSignature(c.req.raw, rawBody)`。
- `qstashOrApiKeyAuth.ts`：允许 QStash signature 或 `Authorization: Bearer <AGENT_EXEC_API_KEY>` 二选一通过，主要用于 `execAgent`。
- `serviceTokenAuth.ts`：要求 `Authorization: Bearer <AGENT_GATEWAY_SERVICE_TOKEN>`，用于 agent-gateway 可信调用，例如 `/tool-result` 和 `/finalize-abandoned`。
- `bearerSecretAuth.ts`：通用 Bearer secret 工厂，按请求时动态取 secret，例如 `/gateway` 使用 `CRON_SECRET`，`/gateway/start` 使用 `KEY_VAULTS_SECRET`。

## 上下游关系

上游入口是 Next.js API route：`src/app/(backend)/api/agent/[[...route]]/route.ts`。这个文件很薄，只导入 `@/server/agent-hono`，然后把 `GET` 和 `POST` 都绑定到同一个 `handler`。

调用方和触发来源有多种：

- 内部/外部可信调用方可以通过 `POST /api/agent` 触发 agent 执行。代码搜索显示 `AiAgentService.execAgent` 也被 tRPC router、OpenAPI service、task runner、agent eval 等服务直接调用；而 Hono 这里只是 REST 入口之一。
- QStash 会调用 `/api/agent/run` 推进 step，也会调用 `/api/agent/webhooks/bot-callback` 等回调。
- agent-gateway 会调用 `/api/agent/tool-result` 把客户端或网关侧工具执行结果送回服务端。
- Vercel cron 或非 Vercel 启动器会调用 `/api/agent/gateway`、`/api/agent/gateway/start` 维护 message gateway 运行状态。
- 聊天平台会调用 `/api/agent/webhooks/:platform/:appId?`，真实平台签名校验根据当前片段推断由各平台 handler 负责，依据是 `platformWebhook.ts` 注释中写明“platform is responsible for verifying its own signature”。
- Messenger 安装和 webhook 入口会被前端功能、OAuth 平台、聊天平台共同触发，例如功能入口里会链接到 `/api/agent/messenger/slack/install`、`/api/agent/messenger/discord/install`。

下游主要是：

- `@/database/core/db-adaptor` 的 `getServerDB()`，用于构造服务层实例。
- `@/server/services/aiAgent` 的 `AiAgentService`，负责创建/恢复 agent operation。
- `@/server/services/agentRuntime` 的 `AgentRuntimeService`，负责执行单步 agent runtime。
- `@/server/modules/AgentRuntime` 和其 Redis 相关模块，负责 operation metadata、锁、工具结果等待等运行态能力。
- `@/server/services/bot`、`@/server/services/messenger`、`@/server/services/gateway`，负责 bot 平台、Messenger 和 gateway 状态管理。

## 运行/调用流程

一次普通 agent 执行可以按下面理解：

1. 调用方请求 `POST /api/agent`，请求先进入 Next.js catch-all，再进入 Hono `index.ts`。
2. `qstashOrApiKeyAuth()` 验证 QStash 签名或 `AGENT_EXEC_API_KEY`。
3. `execAgent` 解析 JSON，要求有 `userId`、`prompt`，并且 `agentId` 和 `slug` 至少一个存在。
4. `execAgent` 创建 `AiAgentService(serverDB, userId)`，调用 `execAgent(...)`，返回 `operationId`、执行信息和 `executionTime`。
5. 后续 step 通常由 QStash 调用 `POST /api/agent/run`。
6. `/run` 先经过 `qstashAuth()`，再由 `runStep` 从 Redis metadata 查 `userId`，创建 `AgentRuntimeService`，调用 `executeStep(...)`。
7. 如果执行中需要外部工具结果，gateway 通过 `POST /api/agent/tool-result` 写 Redis list；runtime 侧等待并消费该结果。
8. `runStep` 返回当前状态：是否完成、是否等待人工输入、是否等待审批、是否调度下一步、总步数、总成本等。

消息平台 webhook 流程则更短：平台请求 `/api/agent/webhooks/:platform/:appId?`，Hono 提取 path 参数，然后交给 `BotMessageRouter`；共享 Messenger bot 请求 `/api/agent/messenger/webhooks/:platform`，交给 `MessengerRouter`。这个目录不承载平台协议细节，只负责把原始请求转交给对应 router。

## 小白阅读顺序

建议先读 `src/app/(backend)/api/agent/[[...route]]/route.ts`，确认 Hono app 是如何接入 Next.js 的。这个文件只有几行，能先建立“所有 `/api/agent/*` 请求都会进 Hono”的入口概念。

第二步读 `src/server/agent-hono/index.ts`。不要一开始钻进每个 handler，先把路由表看一遍，按路径把功能分成 agent 执行、gateway、bot webhook、messenger 四组。

第三步读 `middlewares/qstashAuth.ts`、`qstashOrApiKeyAuth.ts`、`serviceTokenAuth.ts`、`bearerSecretAuth.ts`。这些文件很短，但能解释为什么不同端点返回 `401`、`503`，以及为什么某些请求必须有 QStash signature，另一些只接受 service token。

第四步读 `handlers/execAgent.ts` 和 `handlers/runStep.ts`。这两个文件是 agent 执行主线：一个负责启动 operation，一个负责推进 step。

第五步读 `handlers/toolResult.ts`。它能补上“工具执行结果如何回到 agent runtime”的异步链路，尤其是 Redis key `tool_result:${toolCallId}` 的作用。

最后再按兴趣读 `platformWebhook.ts`、`messengerWebhook.ts`、`gatewayCallback.ts`。它们适合理解外部消息系统如何接入，但业务细节要继续跳到 `src/server/services/bot`、`src/server/services/messenger`、`src/server/services/gateway`。

## 常见误区

不要把 `src/server/agent-hono` 当成 agent 的核心执行引擎。这里主要是 HTTP 路由和适配层，核心执行逻辑在 `AiAgentService`、`AgentRuntimeService`、`AgentRuntimeCoordinator` 等服务/模块里。

不要以为所有 `/api/agent/*` 都使用同一种鉴权。`POST /api/agent` 允许 QStash 或 API key；`POST /api/agent/run` 强制 QStash；`/tool-result` 使用 `AGENT_GATEWAY_SERVICE_TOKEN`；`/gateway` 使用 `CRON_SECRET`；平台 webhook 的签名校验根据当前片段推断在平台 handler 内完成，而不是统一在 Hono middleware 中完成。

不要忽略 Hono body 读取方式。`qstashAuth` 和 `qstashOrApiKeyAuth` 会先调用 `c.req.text()` 读取原始 body 用于签名校验，注释说明 Hono 的 body cache 允许下游 handler 继续调用 `c.req.json()`。如果不了解这一点，容易误以为下游 JSON 解析会失败。

不要把 `platformWebhook` 和 `messengerWebhook` 混为一谈。`/api/agent/webhooks/:platform/:appId?` 是 per-user/per-application 的 Bot Channels；`/api/agent/messenger/webhooks/:platform` 是共享 Messenger bot，按消息发送者和已绑定 agent 路由。

不要认为 `gatewayCallback` 没有鉴权。它确实没有挂 route-level middleware，但 handler 内部有 `MESSAGE_GATEWAY_SERVICE_TOKEN` 校验；这样写是为了在 gateway 功能关闭时优先 `204` 静默忽略旧回调。

不要只看 `index.ts` 就判断完整行为。`index.ts` 只能告诉你路径和中间件；请求体字段、错误码、Redis 写入、service 调用、特殊短路逻辑都分散在各 handler 中。
