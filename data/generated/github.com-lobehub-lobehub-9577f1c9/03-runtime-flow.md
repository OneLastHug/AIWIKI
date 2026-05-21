# 运行时流程与关键调用链

## 启动与构建入口

从 `package.json` 看，生产构建不是单一 `next build`。根脚本 `build` 依次运行 `build:spa`、`build:spa:copy`、`build:next`。`build:spa:raw` 使用 Vite 构建并输出到 `dist/desktop` 或 `dist/mobile`，生产 base 默认是 `/_spa/`；`build:spa:copy` 调 `scripts/copySpaBuild.mts` 和 `scripts/generateSpaTemplates.mts`，根据脚本名和 `src/app/spa/[variants]/[[...path]]/route.ts` 中的 `spaHtmlTemplates` 导入可推断，它会把 Vite 构建结果复制到 Next 可服务的位置，并生成可被 Next route 导入的 HTML 模板。随后 `build:next` 执行 `next build`，生成服务端部分。

开发模式分两类。`dev:next` 是 `next dev -p 3010`，`dev:spa` 是 `vite --port 9876`，`dev` 调用 `scripts/devStartupSequence.mts`。`vite.config.ts` 中的插件会在开发态打印 Debug Proxy URL：线上 `app.lobehub.com` 的 `_dangerous_local_dev_proxy` 指向本地 Vite 服务。`src/spa/entry.web.tsx` 中也检查 `window.__DEBUG_PROXY__` 或路径是否以 `/_dangerous_local_dev_proxy` 开头，并把 React Router 的 basename 设为该代理路径。由此可确认：本地 SPA 能在代理路径下工作，避免 React Router 路径错位。

## SPA HTML 与配置注入

浏览器访问 SPA 页面时，Next 的 `src/app/spa/[variants]/[[...path]]/route.ts` 是关键入口。`generateStaticParams` 会为 `en-US`、`zh-CN` 和移动/桌面变体生成静态参数。`GET` 中先用 `RouteVariants.deserializeVariants` 解析 locale 与 `isMobile`，然后调用 `getServerGlobalConfig()`、`getServerFeatureFlagsValue()`、`buildAnalyticsConfig()`、`buildClientEnv()` 构造 `SPAServerConfig`。随后 `getTemplate(isMobile)` 获取 HTML：开发态从 `[URL已移除] fetch Vite HTML 并重写 script/link URL，生产态导入 `desktopHtmlTemplate` 或 `mobileHtmlTemplate`。最后替换 `window.__SERVER_CONFIG__ = undefined; /* SERVER_CONFIG */` 占位符，并注入 SEO meta，返回 `content-type: text/html; charset=utf-8`。

前端入口收到 HTML 后，`src/spa/entry.web.tsx`、`entry.mobile.tsx`、`entry.desktop.tsx` 或 `entry.popup.tsx` 会 import `../initialize`，创建 React root，再用 `createAppRouter(routes)` 生成 React Router。`src/initialize.ts` 会启用 Immer patches/mapset、注册 dayjs 插件、监听 Vite chunk preload error 和 unhandled rejection，并在 `__DEV__` 下启用 `react-scan`。`createAppRouter` 在 `src/utils/router.tsx` 中定义，它用 `RouterRoot` 包住所有路由。`RouterRoot` 内部挂载 `SPAGlobalProvider`、`BusinessGlobalProvider`、`NavigatorRegistrar` 和 `Outlet`。

`SPAGlobalProvider` 是客户端初始化的中心。它读取 `window.__SERVER_CONFIG__`，把 `serverConfig.config` 和 `featureFlags` 交给 `ServerConfigStoreProvider`，再挂载 `QueryProvider`、`AuthProvider`、`StoreInitialization`、主题、Locale、ModalHost、ToastHost、ContextMenuHost、Analytics 等。`StoreInitialization` 会调用全局 store 的系统状态初始化、服务端版本检查、`useServerConfigStore.useInitServerConfig()`、用户状态初始化、内置 inbox agent 初始化，并把移动端状态写入 global store。

## 配置加载流

首次 HTML 已经注入一份 `window.__SERVER_CONFIG__`，但前端仍会通过 store 再取运行时配置。`src/store/serverConfig/action.ts` 的 `useInitServerConfig` 使用 `useOnlyFetchOnceSWR` 调 `globalService.getGlobalConfig()`。`src/services/global.ts` 中 `getGlobalConfig` 调 `lambdaClient.config.getGlobalConfig.query()`。`lambdaClient` 在 `src/libs/trpc/client/lambda.ts` 中配置 URL `/trpc/lambda`、superjson transformer、带 cookie 的 fetch、动态鉴权 header 和 401 处理。

服务端配置的生成在 `src/server/globalConfig/index.ts`。它读取 `appEnv`、`authEnv`、`fileEnv`、`imageEnv`、`knowledgeEnv`、`langfuseEnv`、`toolsEnv` 等环境封装，调用 `genServerAiProvidersConfig` 生成 provider 配置，解析默认 Agent、文件配置、系统 Agent、SSO providers、记忆抽取公开配置，并根据环境变量决定是否启用市场可信客户端、上传到服务器、视觉理解、Klavis、Langfuse 等。这个文件是“环境变量如何变成客户端可见配置”的主证据。

## 普通请求与数据流

普通业务请求的主链路可以概括为：React UI 或 zustand action -> `src/services/*` -> `lambdaClient` -> `/trpc/lambda` -> `lambdaRouter` -> 具体 router -> service -> database model/repository -> Drizzle/PostgreSQL。以全局配置为例，上文已经展示了 store 到 service 到 tRPC 的路径。以后端入口看，`src/app/(backend)/trpc/lambda/[trpc]/route.ts` 用 `fetchRequestHandler` 处理 GET/POST，请求会先经过 `prepareRequestForTRPC`，context 由 `createLambdaContext(req)` 生成，router 是 `lambdaRouter`，错误通过 `onError` 过滤未授权后打印。

`createLambdaContext` 位于 `src/libs/trpc/lambda/context.ts`，它会处理开发 mock user、提取 `user-agent`、client IP、cookie 中的 `mp_token`、trace context、`X-API-Key`、OIDC header、Better Auth session 等。API key 会通过 `ApiKeyModel.findByKey` 查数据库并更新 last used；OIDC token 会验证 JWT 并检查用户状态；普通 Web 登录会走 `auth()`。因此 router 层拿到的 ctx 不只是 userId，还可能包含 market access token、OIDC payload、traceContext、resHeaders。

`src/server/routers/lambda/index.ts` 聚合大量领域 router。具体 router 通常使用 `publicProcedure`、`authedProcedure` 或 `heteroAuthedProcedure`。`src/libs/trpc/lambda/index.ts` 显示 `authedProcedure` 是基础 procedure 加 openTelemetry、OIDC auth 和 userAuth；`heteroAuthedProcedure` 则用于异构 Agent ingest/finish 这类需要 `hetero-operation` JWT 的接口。根据当前文件推断，router 是权限、schema 和请求编排层，service 是业务执行层。

## Agent 执行流

Agent 执行是本仓库最复杂的运行链路。入口之一是 `src/server/routers/lambda/aiAgent.ts`，其中 `ExecAgentSchema` 定义 agentId/slug、prompt、appContext、clientRuntime、deviceId、fileIds、parentMessageId、resumeApproval、trigger、userInterventionConfig 等。router 调用 `ctx.aiAgentService.execAgent(...)`。`AiAgentService` 构造时持有多个 database model 和服务，包括 `AgentModel`、`MessageModel`、`TaskModel`、`ThreadModel`、`TopicModel`、`AgentRuntimeService`、`MarketService`、`KlavisService`。

`AiAgentService.execAgent` 的注释给出核心架构：`execAgent({ agentId | slug, prompt }) -> AgentModel.getAgentConfig -> ServerMechaModule.AgentToolsEngine -> ServerMechaModule.ContextEngineering -> AgentRuntimeService.createOperation(...)`。真实代码还会合并内置 Agent runtime config，按 page/task scope 注入 `PageAgentIdentifier` 或 `TaskIdentifier`，处理 resume/human approval，创建或复用 topic，处理附件和消息，准备工具集、模型运行配置、用户记忆、设备上下文、hook 和队列参数。最终创建 operation 并根据 `autoStart` 决定是否启动。

`AgentRuntimeService.createOperation` 会先通过 `CompletionLifecycle.recordStart` 记录 `agent_operations` 起始信息，然后调用 `coordinator.createAgentOperation` 和 `coordinator.saveAgentState` 保存初始 state。若有外部 hooks，则注册到 `hookDispatcher` 并把序列化 hook 写入 state metadata。如果 `autoStart` 且有 queue service，它会调 `queueService.scheduleMessage`，endpoint 是 `${baseURL}/run`，baseURL 默认来自 `AGENT_RUNTIME_BASE_URL`、`appEnv.APP_URL` 或 `[URL已移除] `/api/agent/run`。

队列实现有两种。`src/server/services/queue/impls/index.ts` 中 `isQueueAgentRuntimeEnabled` 读取 `appEnv.enableQueueAgentRuntime`，注释说明由 `AGENT_RUNTIME_MODE=queue` 控制。启用时使用 `QStashQueueServiceImpl`，需要 `QSTASH_TOKEN`，通过 `@upstash/qstash` 发布 JSON 到 endpoint；默认使用 `LocalQueueServiceImpl`，以 `setTimeout` 调用 `AgentRuntimeService` 注入的本地 callback。根据当前文件推断，生产可用 QStash 分散步骤执行，本地开发不依赖外部队列。

`/api/agent/run` 由 `src/server/agent-hono/index.ts` 注册，Next catch-all `src/app/(backend)/api/agent/[[...route]]/route.ts` 把请求转给 Hono app。`AgentRuntimeService.executeStep` 执行单步：先通过 coordinator 抢占 step lock，发布 `step_start`，加载 state，跳过终止态或重复 step，派发 beforeStep hook 和 Agent Signal，创建 Agent Runtime，处理 human intervention，计算设备上下文，调用 `runtime.step(currentState, currentContext)`，保存 step result，发布 `step_complete`，记录 trace，派发 afterStep hook，并用 `shouldContinueExecution` 决定是否调度下一步。结束条件包括 done、error、interrupted、human intervention 等，具体判断逻辑可继续读该文件后半段。

## 数据库与持久化流

数据库连接从 `packages/database/src/core/db-adaptor.ts` 进入，`getServerDB()` 懒加载并缓存 DB 实例，`serverDB` 直接初始化。`packages/database/src/core/web-server.ts` 负责真实连接：测试环境返回 mock；缺少 `KEY_VAULTS_SECRET` 或 `DATABASE_URL` 会抛错；`DATABASE_DRIVER === 'node'` 时使用 `pg` 的 `NodePool` 和 `drizzle-orm/node-postgres`；否则使用 Neon serverless `NeonPool` 和 `drizzle-orm/neon-serverless`。两种 pool 都注册 error listener，避免 idle client 错误导致进程崩溃。

schema 从 `packages/database/src/schemas/index.ts` 统一导出，覆盖 agent、apiKey、asyncTask、chatGroup、file、generation、message、notification、oidc、session、task、topic、user、userMemories 等。model 层在 `packages/database/src/models/`，例如 `ApiKeyModel` 被 tRPC context 用于 API key 鉴权，`AgentModel`、`MessageModel`、`TaskModel`、`ThreadModel`、`TopicModel` 被 `AiAgentService` 使用。根据当前文件推断，数据库 model 是业务服务最常用的持久化入口，repository 用于更复杂或跨领域查询。

## 后台、Webhook 与外部平台

除 tRPC 外，`src/server/agent-hono/index.ts` 显示 `/api/agent/*` 还支持 gateway、tool result、finalize abandoned、bot callback、platform webhook、messenger install/oauth/webhook 等路径。`src/app/(backend)/api/webhooks/*` 还存在 video provider、Casdoor、Logto、memory extraction、agent eval workflow 等 route。结合 `@chat-adapter/*` 依赖和 `src/server/services/bot`、`src/server/services/gateway`，可以判断项目支持把 Agent 接入外部消息平台和后台任务系统；具体平台行为需要继续阅读各 webhook handler 和 service。

## 依据

本页依据 `package.json`、`vite.config.ts`、`src/spa/entry.*.tsx`、`src/initialize.ts`、`src/utils/router.tsx`、`src/layout/SPAGlobalProvider/index.tsx`、`src/layout/GlobalProvider/StoreInitialization.tsx`、`src/app/spa/[variants]/[[...path]]/route.ts`、`src/libs/trpc/client/lambda.ts`、`src/app/(backend)/trpc/lambda/[trpc]/route.ts`、`src/libs/trpc/lambda/context.ts`、`src/server/routers/lambda/index.ts`、`src/server/routers/lambda/aiAgent.ts`、`src/server/services/aiAgent/index.ts`、`src/server/services/agentRuntime/AgentRuntimeService.ts`、`src/server/services/queue/*`、`src/server/agent-hono/index.ts`、`packages/database/src/core/*` 整理。
