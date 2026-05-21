# 目录：src/server

## 它负责什么

`src/server` 是 LobeHub 的服务端业务中枢，位于 Next.js 后端路由和数据库/外部系统之间。它不直接负责前端页面渲染，而是集中承载这些职责：

1. 组织 tRPC 后端 API：`src/server/routers` 把不同业务域拆成 `lambda`、`async`、`mobile`、`tools` 等路由树。
2. 封装服务端业务逻辑：`src/server/services` 按领域提供 `MessageService`、`FileService`、`TaskService`、`AgentRuntimeService` 等服务类或函数。
3. 管理服务端配置：`globalConfig`、`featureFlags`、`runtimeConfig` 将环境变量、Redis 运行时配置、默认模型配置等整理成前端或后端可消费的结构。
4. 提供 Agent 和 Workflow HTTP 入口：`agent-hono`、`workflows-hono` 使用 `Hono` 组织 `/api/agent/*`、`/api/workflows/*` 这类非普通 tRPC 的服务端端点。
5. 对接底层模块和第三方能力：`modules` 放偏基础设施或能力适配，例如 `ModelRuntime`、`AgentRuntime`、`S3`、`GitHub`、`KeyVaultsEncrypt` 等。

简单说，`src/server` 是“API 编排层 + 服务端业务层 + 运行时配置层”。前端不会直接操作数据库，而是通过 `src/services` 客户端服务或 tRPC 调用进入这里，再由这里调用数据库模型、仓储、队列、对象存储、模型运行时或外部平台。

## 关键组成

`routers` 是最明显的入口层。`src/server/routers/lambda/index.ts` 聚合了大量业务 router，例如 `agent`、`message`、`file`、`session`、`topic`、`aiAgent`、`aiChat`、`generation`、`knowledgeBase`、`market`、`usage`、`user` 等，还接入了 `@/business/server/lambda-routers/*` 中的商业化 router，如 `subscription`、`spend`、`topUp`。这说明开源核心和 cloud/business 扩展会在 server router 层合流。

`src/server/routers/async/index.ts` 是异步任务相关路由，当前聚合 `document`、`file`、`image`、`ragEval`、`video`，并导出 `createAsyncCaller`、`createAsyncServerClient`。根据当前片段推断，它用于较重或异步化的处理场景，例如文档、文件、图片、视频、RAG 评测。

`src/server/routers/tools/index.ts` 是工具调用相关 tRPC 分组，包含 `klavis`、`market`、`mcp`、`search`。它和普通业务 API 分离，便于 Agent 或工具系统按工具域访问。

`src/server/routers/mobile/index.ts` 是移动端专用 router。它复用许多 `lambda` router，例如 `agentRouter`、`messageRouter`、`sessionRouter`、`fileRouter`，但只暴露移动端实际使用的集合，并额外接入 `mobileSubscriptionRouter`。

`services` 是业务逻辑层。以 `src/server/services/message/index.ts` 为例，`MessageService` 构造时接收 `LobeChatDatabase` 和 `userId`，内部组合 `MessageModel`、`FileService`、`CompressionRepository`。它负责“创建/更新/删除消息后是否重新查询消息列表”“文件 URL 后处理”“压缩消息组”等跨模型业务逻辑。对应的 `src/server/routers/lambda/message.ts` 则负责输入校验、鉴权中间件、注入 `serverDatabase`，然后调用 `ctx.messageService` 或 `ctx.messageModel`。

`globalConfig` 负责生成服务端全局配置。`getServerGlobalConfig` 会读取 `appEnv`、`authEnv`、`fileEnv`、`imageEnv`、`knowledgeEnv`、`toolsEnv` 等环境配置，生成 AI Provider、默认 Agent、认证开关、文件上传、视觉理解、SSO、telemetry、systemAgent 等配置。

`featureFlags` 负责服务端功能开关。它定义 `RuntimeConfigDomain`，通过 `CompositeRuntimeConfigProvider` 组合 `RedisRuntimeConfigProvider` 和 `EnvRuntimeConfigProvider`：优先读取 Redis 发布的运行时配置，同时以环境变量作为 fallback，并支持按用户覆盖 feature flag。

`runtimeConfig` 是运行时配置基础设施的导出口，当前 `index.ts` 只导出 `providers` 和 `types`。它被 `featureFlags` 等模块复用。

`agent-hono` 是 Agent 专用 HTTP 应用。`src/server/agent-hono/index.ts` 创建 `new Hono().basePath('/api/agent')`，注册 `POST /`、`POST /run`、`POST /tool-result`、`POST /finalize-abandoned`、`GET /gateway`、`POST /gateway/start`、webhook、messenger OAuth 等路径，并挂载 `qstashAuth`、`serviceTokenAuth`、`bearerSecretAuth` 等中间件。

`workflows-hono` 是 workflow 入口。`src/server/workflows-hono/index.ts` 以 `/api/workflows` 为 base path，并挂载 `agent-signal`、`memory-user-memory`、`task` 三组 workflow。

顶层还有 `manifest.ts`、`metadata.ts`、`sitemap.ts`、`translation.ts` 及对应测试文件，说明 `src/server` 也包含一部分服务端生成站点元信息、清单、翻译或 sitemap 的工具逻辑。

## 上下游关系

上游主要来自三类入口：

1. Next.js 后端路由：`src/app/(backend)` 下的 API、webapi、trpc、oidc 等路由会进入服务端逻辑。根据 `agent-hono` 注释，`/api/agent/*` 通过 Next.js optional catch-all 挂载到 Hono app。
2. 客户端服务层：前端通常通过 `src/services` 或 store action 调 tRPC，而不是直接 import `src/server/services`。
3. 定时任务、队列和 webhook：`agent-hono`、`workflows-hono` 中能看到 QStash、cron、gateway callback、bot webhook、messenger webhook 等入口。

下游主要是：

1. 数据库模型和仓储：例如 `MessageService` 调用 `MessageModel`、`CompressionRepository`；这些通常来自 `@/database/models/*` 或 `@lobechat/database`。
2. 外部服务和运行时：例如 Agent Gateway、QStash、模型供应商、S3、Klavis、MCP、搜索服务、OIDC、邮件服务等。
3. 业务扩展包：`lambdaRouter` 引入 `@/business/server/lambda-routers/*`，说明商业化能力通过 alias 覆盖或扩展进入主路由。

可以把关系理解成：

```text
React UI / Mobile / Webhook / Cron
  -> Next.js route 或 tRPC client
  -> src/server/routers 或 Hono app
  -> src/server/services
  -> database models / repositories / modules / external APIs
```

## 运行/调用流程

以消息更新为例，典型流程是：

```text
前端触发 message.update
  -> tRPC 进入 src/server/routers/lambda/message.ts
  -> messageProcedure 执行 authedProcedure + serverDatabase
  -> ctx 注入 messageModel、fileService、messageService
  -> zod 校验 input
  -> resolveContext 补齐 agentId/sessionId/topicId 等上下文
  -> ctx.messageService.updateMessage(...)
  -> MessageService 调用 MessageModel 更新数据库
  -> 必要时重新 query 消息列表
  -> 返回给 tRPC 客户端
```

这里 router 主要做“协议层”的事情：鉴权、数据库上下文、中间件、输入 schema、错误形态、调用服务。Service 主要做“业务层”的事情：组合多个 model/repository，处理更新后的查询、文件 URL、压缩消息、事务或跨实体逻辑。

以配置读取为例，流程大致是：

```text
客户端请求 config router
  -> server/globalConfig/getServerGlobalConfig
  -> 读取 envs、business const、provider config
  -> parse 默认 Agent、文件配置、SSO、systemAgent
  -> 返回 GlobalServerConfig
```

以 feature flag 为例：

```text
调用 getServerFeatureFlagsStateFromRuntimeConfig(userId)
  -> getMergedFeatureFlags(userId)
  -> RedisRuntimeConfigProvider 读取全局发布配置
  -> EnvRuntimeConfigProvider 作为 fallback
  -> 如果有 userId，再读取用户级 override
  -> merge DEFAULT_FEATURE_FLAGS
  -> mapFeatureFlagsEnvToState
```

以 Agent HTTP 任务为例：

```text
POST /api/agent
  -> agent-hono
  -> qstashOrApiKeyAuth
  -> execAgent handler

POST /api/agent/run
  -> qstashAuth
  -> runStep handler

POST /api/agent/tool-result
  -> serviceTokenAuth
  -> toolResult handler
```

这类入口不是普通页面 API，更像后台任务、队列回调、Agent Gateway、外部平台 webhook 的控制面。

## 小白阅读顺序

1. 先看 `src/server/routers/lambda/index.ts`  
   这是主 tRPC router 地图。先不用深入每个 router，只要记住业务域如何被挂到根路由上。

2. 再看一个具体 router，例如 `src/server/routers/lambda/message.ts`  
   重点看 `authedProcedure`、`serverDatabase`、`z.object(...).input(...)`、`.query`、`.mutation`、`ctx.messageService` 这些模式。看懂一个 router 后，其他业务 router 会很相似。

3. 接着看对应 service，例如 `src/server/services/message/index.ts`  
   重点理解 service 如何组合 `Model`、`Repository`、其他 service，以及为什么业务逻辑不直接堆在 router 里。

4. 然后看 `src/server/globalConfig/index.ts`  
   它能帮助你理解环境变量、默认配置、AI Provider、认证能力、文件能力等是怎么暴露给应用的。

5. 再看 `src/server/featureFlags/index.ts` 和 `src/server/runtimeConfig`  
   这部分解释了“运行中可变配置”与“环境变量默认值”的关系。

6. 最后看 `src/server/agent-hono/index.ts`、`src/server/workflows-hono/index.ts`  
   它们适合在你已经理解 tRPC 之后阅读，因为它们处理的是 Agent、队列、workflow、webhook 这些更后台化的入口。

## 常见误区

1. 不要把 `src/server/routers` 当成业务逻辑最终归宿。router 应该偏薄，主要负责 API 形状、鉴权、输入校验和调用 service；复杂业务通常应下沉到 `src/server/services`。

2. 不要以为所有后端接口都是 tRPC。`agent-hono` 和 `workflows-hono` 说明项目也使用 Hono 来承接 Agent、workflow、webhook、cron、gateway callback 等 HTTP 入口。

3. 不要忽略 `mobileRouter`。移动端不是直接暴露完整 `lambdaRouter`，而是选择性复用部分 lambda router，并加入移动端专用订阅能力。

4. 不要把 `modules` 和 `services` 混为一谈。根据目录命名和当前片段推断，`modules` 更偏底层能力适配或基础设施封装，`services` 更偏业务用例编排。

5. 不要只看开源目录。`lambdaRouter` 明确 import 了 `@/business/server/lambda-routers/*`，说明商业化或 cloud 扩展会通过业务目录合入服务端路由。阅读实际行为时，要注意 alias 和覆盖机制。

6. 不要绕过 runtime config。`featureFlags` 并非只读环境变量，它会通过 Redis runtime config、环境变量 fallback、用户 override 合并得到最终状态。调试功能开关时要同时考虑全局配置、用户覆盖和默认值。

7. 不要让前端直接依赖 `src/server/services`。正常边界应是前端 store/client service 调 tRPC 或 HTTP API，服务端 router 再调用 server service。这样才能保持鉴权、数据库上下文和输入校验的一致性。
