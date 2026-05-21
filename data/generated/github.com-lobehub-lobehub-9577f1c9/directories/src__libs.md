# 目录：src/libs

## 它负责什么

`src/libs` 是 LobeHub 在 `src` 层的“基础库适配层”。它不直接承载聊天、知识库、设置页这类业务 UI，而是把外部库、运行环境差异、服务端基础设施和项目内部约定包装成统一入口，供 `src/services`、`src/routes`、`src/features`、`src/app/(backend)`、`packages/*` 等上层代码调用。

可以把它理解成几类能力的集合：

1. 外部 SDK 的项目化封装：例如 `better-auth`、`oidc-provider`、`ioredis`、`@upstash/qstash`、`@trpc/client`、`react-pdf`。
2. Next.js 与 SPA/Vite 的兼容层：例如 `src/libs/next/*` 和 `src/libs/router/*`，让业务代码用统一 API，而不用关心当前运行在 Next App Router、Vite SPA、Desktop 还是浏览器。
3. 服务端通信基础设施：例如 `src/libs/trpc` 负责客户端 tRPC 调用、服务端 tRPC context、鉴权、中间件和响应元数据。
4. 认证与授权基础设施：例如 `src/libs/better-auth` 管 Better Auth 配置和客户端 API，`src/libs/oidc-provider` 管 OIDC Provider、JWT、访问控制和 HTTP 适配。
5. 通用数据与内容处理工具：例如 `src/libs/editor` 处理编辑器 JSON，`src/libs/document-loaders` 定义文档加载类型，`src/libs/swr` 封装 SWR 行为。

它的定位接近“技术中台 glue code”：上游是具体业务、服务和页面，下游是第三方库、环境变量、数据库、Redis、认证协议、浏览器/桌面运行时。

## 关键组成

`src/libs/trpc` 是最核心的通信库之一。`src/libs/trpc/client/index.ts` 导出 `asyncClient`，并转出 `lambda`、`tools` 等客户端。`src/libs/trpc/client/lambda.ts` 创建 `lambdaClient`、`lambdaQuery`、`lambdaQueryClient`，内部使用 `createTRPCClient`、`createTRPCReact`、`httpBatchLink`、`httpLink`、`splitLink` 和 `superjson`。它还包含 401 错误处理、Market API 鉴权事件、桌面端协议适配 `withElectronProtocolIfElectron('/trpc/lambda')`，以及为请求动态注入 `createHeaderWithAuth()` 生成的认证头。服务端侧的 `src/libs/trpc/lambda/context.ts`、`async/context.ts` 等文件负责从请求里解析 session、API Key、OIDC token、内部 JWT、用户 ID 和 trace context。

`src/libs/better-auth` 封装 Better Auth。`auth-client.ts` 通过 `createAuthClient` 导出 `signIn`、`signOut`、`signUp`、`useSession`、`resetPassword`、`changeEmail`、`linkSocial` 等前端认证 API。`define-config.ts` 负责服务端 Better Auth 配置：接入 Drizzle 数据库、email/password、magic link、email OTP、generic OAuth、admin、passkey、Expo、secondary storage、邮件模板、用户初始化 hook，以及 Clerk 迁移来的 bcrypt 密码兼容验证。`constants.ts` 定义内置 SSO provider，如 `apple`、`google`、`github`、`cognito`、`microsoft`，并提供 provider alias 映射。

`src/libs/oidc-provider` 是 LobeHub 自己作为 OIDC Provider 时的实现。`config.ts` 定义默认 OIDC clients，包括 `lobehub-desktop`、`lobehub-mobile`、`lobehub-cli`、`lobehub-market`，并声明 `openid`、`profile`、`email`、`offline_access` 等 scope 和 claims。`provider.ts` 使用 `oidc-provider` 创建 Provider，接入 `DrizzleAdapter`、JWKS、cookie keys、device flow、client-based CORS、interaction policy 和用户访问控制。`jwt.ts`、`access-control.ts` 则服务于 OIDC token 校验和用户状态检查。

`src/libs/redis` 是 Redis 抽象层。`manager.ts` 提供 `initializeRedis`、`resetRedisClient`、`createRedisWithPrefix`、`initializeRedisWithPrefix` 等能力，内部用单例和 `initPromise` 避免并发初始化时创建多个连接。`redis.ts` 的 `IoRedisRedisProvider` 基于 `ioredis` 实现 `get`、`set`、`setex`、`del`、`exists`、`expire`、`ttl`、`incr`、`decr`、`mget` 等基础操作。它还支持 `DISABLE_REDIS` 环境变量关闭 Redis。

`src/libs/next` 和 `src/libs/router` 是运行时兼容层。业务代码里大量使用 `@/libs/next/dynamic`、`@/libs/next/Image`、`@/libs/router/Link`、`@/libs/router/navigation`，而不是直接写死 `next/link`、`next/image` 或 `react-router-dom`。这样同一套业务组件可以在 Next、Vite SPA、Desktop 等环境间复用。

`src/libs/swr` 封装 SWR。调用方常见于 `src/features/User/DataStatistics.tsx`、`src/routes/(main)/settings/stats/*`、`src/features/PageEditor/History/*` 等，用 `useClientDataSWR`、`useActionSWR`、`useOnlyFetchOnceSWR`、`mutate` 等统一数据获取和缓存刷新。

`src/libs/editor` 是编辑器数据工具集。`isValidEditorData.ts` 判断 Lexical 风格 editor JSON 是否具有 `root`、`root.type === 'root'` 和非空 `children`。`hasMeaningfulEditorContent.ts` 判断内容是否有实际文本或非普通段落节点，避免把空编辑器内容当成有效内容。`normalizeDiffNodes.ts` 将带 `type: 'diff'`、`diffType` 的历史 diff 节点还原成原始内容形态，供文档历史、页面编辑器等逻辑使用。

`src/libs/document-loaders` 定义文档加载抽象。`file.ts` 列出支持作为文本读取的扩展名，如 `txt`、`md`、`json`、`ts`、`tsx`、`py`、`sql` 等。`types.ts` 定义 `DocumentChunk` 和 `FileLoaderType`，供 RAG、知识库或文件解析链路使用。根据当前片段推断，真正的 loader 实现位于 `src/libs/document-loaders/loaders`，入口由 `index.ts` 转出。

其他子目录也各有边界：`analytics` 封装 server analytics 和产品使用事件；`observability` 处理 `traceparent` 注入/提取；`qstash` 封装 QStash client、workflow client 和签名校验；`pdfjs` 配置 `react-pdf` 的 worker 路径；`mcp` 定义 MCP client/types；`klavis` 根据当前片段推断用于启动或对接外部 MCP/工具进程；`trusted-client` 用于基于当前 session 生成可信 client token，调用方包括 Market OIDC 相关 route。

## 上下游关系

上游调用方主要分四层。

第一层是前端页面和功能组件。`src/routes/(main)`、`src/routes/(mobile)`、`src/features/*` 会导入 `@/libs/next/*`、`@/libs/router/*`、`@/libs/swr`、`@/libs/trpc/client`、`@/libs/better-auth/auth-client`。例如设置页、统计页、PageEditor、SkillStore、Conversation、SharePdf 都通过这些封装完成跳转、懒加载、图片渲染、数据请求和认证操作。

第二层是客户端 service。`src/services/*` 大量通过 `lambdaClient` 调用后端 tRPC router，例如 `agent.ts`、`message/index.ts`、`document/index.ts`、`generation.ts`、`plugin/index.ts`、`user/index.ts`。这些 service 通常再被 zustand store 或 feature hook 使用。

第三层是后端 route。`src/app/(backend)/trpc/lambda/[trpc]/route.ts`、`async/[trpc]/route.ts`、`mobile/[trpc]/route.ts`、`tools/[trpc]/route.ts` 使用 `src/libs/trpc` 创建 context、适配请求、生成 response meta。`src/app/(backend)/oidc/[...oidc]/route.ts` 使用 OIDC HTTP adapter。`src/app/(backend)/api/workflows/*` 和 `src/server/workflows*` 使用 `qstashClient` 或 `workflowClient`。

第四层是 shared packages。比如 `packages/builtin-tool-*` 会导入 `lambdaClient`、`toolsClient`，`packages/openapi` 会复用 OIDC JWT 校验和访问控制，`packages/types` 会引用 `MCPErrorType`。

下游依赖则包括 Better Auth、oidc-provider、tRPC、SWR、ioredis、QStash、react-pdf、debug、superjson、数据库模型、环境变量模块、业务配置和服务端 service。

## 运行/调用流程

典型前端 tRPC 调用流程是：

组件或 service 调用 `lambdaClient.xxx.query/mutate`，进入 `src/libs/trpc/client/lambda.ts`。client 根据 procedure 名称决定是否 batch，构造请求到 `/trpc/lambda`。请求前动态调用 `createHeaderWithAuth()` 注入认证头；桌面端还会经过 `withElectronProtocolIfElectron` 适配协议。服务端 route 收到请求后使用 `createLambdaContext` 解析 API Key、OIDC token 或 Better Auth session，生成包含 `userId`、`resHeaders`、`traceContext` 等字段的 context，再进入对应 tRPC router。响应回来后，客户端 error link 会处理 401：普通 LobeHub session 失效时触发登出和登录提示，Market API 失效时只发出 `market-unauthorized` 事件。

典型认证流程是：

登录、注册、重置密码等页面调用 `src/libs/better-auth/auth-client.ts` 导出的 `signIn`、`signUp`、`requestPasswordReset` 等方法。服务端 Better Auth 配置由 `define-config.ts` 组装，使用 Drizzle adapter 写入数据库，并通过 `EmailService` 发送验证、重置、magic link、OTP 邮件。用户创建后，`databaseHooks.user.create.after` 调用 `UserService.initUser()` 初始化业务用户数据。SSO provider 由 `initBetterAuthSSOProviders()` 根据 `AUTH_SSO_PROVIDERS` 读取并校验环境变量。

典型 OIDC 流程是：

Desktop、Mobile、CLI 或 Marketplace 作为 OIDC client 访问 LobeHub Provider。`createOIDCProvider(db)` 读取默认 clients、scope、claims、JWKS、cookie key 和 Drizzle adapter，处理 authorization code、refresh token、device code 等流程。后续 API 请求中，如果带 OIDC auth header，`validateOIDCJWT` 和 `assertOIDCUserActive` 会在中间件或 tRPC context 中校验 token 和用户状态。

典型缓存流程是：

服务端需要 Redis 时调用 `initializeRedis(config)`。`RedisManager` 会检查 `DISABLE_REDIS` 和配置开关，创建 `IoRedisRedisProvider`，连接、`ping`，之后复用单例。需要不同 key prefix 的场景使用 `initializeRedisWithPrefix(config, prefix)`，避免频繁创建连接。

## 小白阅读顺序

建议先从入口和调用面看，而不是一开始钻进所有第三方 SDK 配置。

1. 先看 `src/libs/trpc/client/index.ts` 和 `src/libs/trpc/client/lambda.ts`，理解前端到后端的主通信方式。
2. 再看 `src/app/(backend)/trpc/lambda/[trpc]/route.ts` 的调用关系，然后回到 `src/libs/trpc/lambda/context.ts`，理解请求如何变成 tRPC context。
3. 看 `src/libs/better-auth/auth-client.ts`，再看 `src/libs/better-auth/define-config.ts`，把“前端登录 API”和“服务端认证配置”对应起来。
4. 看 `src/libs/next/index.ts`、`src/libs/next/Image.tsx`、`src/libs/router/index.ts`、`src/libs/router/navigation.ts`，理解为什么业务代码不直接依赖 Next 或 React Router。
5. 看 `src/libs/swr/index.ts` 和一两个调用方，例如 `src/features/User/DataStatistics.tsx` 或 `src/features/PageEditor/History/index.tsx`，理解数据读取的惯用写法。
6. 最后按需看专项基础设施：需要缓存看 `redis`，需要桌面/CLI 登录看 `oidc-provider`，需要文档解析看 `document-loaders`，需要编辑器历史看 `editor`，需要异步任务看 `qstash`。

## 常见误区

不要把 `src/libs` 当成业务层。这里的代码通常不应该知道“聊天页面怎么展示”“设置页怎么布局”，它只提供可复用基础能力。真正业务逻辑应在 `src/features`、`src/services`、`src/store`、`src/server/services` 或 router 中完成。

不要在业务代码里随意绕过这些封装直接导入第三方库。例如直接用 `next/link`、`next/image`、`next/navigation`，可能破坏 Vite SPA 或 Desktop 环境兼容；直接创建 tRPC client，可能漏掉认证头、错误处理、batch 策略和桌面协议适配；直接连 Redis，可能绕过单例管理造成连接泄漏。

不要混淆 Better Auth 和 OIDC Provider。`better-auth` 主要服务 LobeHub 自身用户登录、注册、session、SSO；`oidc-provider` 则是 LobeHub 对外充当身份提供方，给 Desktop、Mobile、CLI、Marketplace 等 client 发放 OIDC token。它们都和认证有关，但处在不同协议位置。

不要以为 `lambdaClient` 只用于浏览器页面。调用方显示，`packages/builtin-tool-*`、`src/services/*`、部分 feature 和 route 都会复用它。它是前端/工具侧访问后端 lambda tRPC router 的统一入口。

不要忽略环境变量对行为的影响。`DISABLE_REDIS` 会关闭 Redis，`AUTH_SSO_PROVIDERS` 会决定启用哪些 SSO，`APP_URL` 会影响 passkey、OAuth callback、OIDC redirect，`ENABLE_TELEMETRY` 会影响 trace 注入和指标记录。读 `src/libs` 时必须同时留意 `src/envs/*`、`src/config/*` 这些邻近上下文。
