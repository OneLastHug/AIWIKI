# 目录：src/server/routers/lambda

## 它负责什么

`src/server/routers/lambda` 是 LobeHub 后端主 tRPC API 的领域路由集合。它把聊天、会话、智能体、模型供应商、文件、知识库、生成任务、市场、用户配置等服务端能力，按业务域拆成多个 router 文件，最后由 `src/server/routers/lambda/index.ts` 聚合成根路由 `lambdaRouter`。

从入口看，这里的 API 主要挂在 `/trpc/lambda` 这条 tRPC 通道上。调用链上游包括：

- 浏览器/桌面/CLI 客户端：例如 `src/libs/trpc/client/lambda.ts` 使用 `/trpc/lambda`。
- Next.js 后端路由：`src/app/(backend)/trpc/lambda/[trpc]/route.ts` 引入 `lambdaRouter` 与 `createLambdaContext`。
- 服务端内部调用：例如 `src/app/(backend)/webapi/create-image/comfyui/route.ts` 通过 `createCallerFactory(lambdaRouter)` 直接调用 router。
- 测试：大量 `__tests__` 文件也通过 `createCallerFactory` 构造 caller。

因此，这个目录不是某一个业务模块，而是“lambda tRPC 后端 API 层”的主目录。它的职责是把 HTTP/tRPC 请求转换成有类型的过程调用，并在 procedure 中连接数据库模型、业务服务和运行时配置。

## 关键组成

### `index.ts`：根聚合入口

`src/server/routers/lambda/index.ts` 是最重要的入口。它：

- 从 `@/libs/trpc/lambda` 引入 `router` 和 `publicProcedure`。
- 引入本目录下的各个领域 router，例如 `agentRouter`、`aiChatRouter`、`fileRouter`、`messageRouter`、`sessionRouter`、`userRouter` 等。
- 引入商业能力 router，例如 `@/business/server/lambda-routers/subscription`、`spend`、`topUp`、`referral` 等。
- 导出：

```ts
export const lambdaRouter = router({ ... });
export type LambdaRouter = typeof lambdaRouter;
```

聚合后的命名空间决定了客户端调用路径。例如 `lambdaRouter` 中有：

- `agent: agentRouter`
- `aiChat: aiChatRouter`
- `message: messageRouter`
- `config: configRouter`
- `market: marketRouter`
- `healthcheck: publicProcedure.query(() => "i'm live!")`

所以 tRPC 客户端通常会以类似 `lambdaClient.message.xxx`、`lambdaClient.config.getGlobalConfig` 这样的方式访问。

### 领域 router 文件

目录下大部分 `.ts` 文件都是一个业务域的 router，例如：

- 会话与聊天：`session.ts`、`sessionGroup.ts`、`topic.ts`、`message.ts`、`thread.ts`、`aiChat.ts`
- Agent 相关：`agent.ts`、`agentGroup.ts`、`agentDocument.ts`、`agentSkills.ts`、`agentNotify.ts`、`agentSignal.ts`、`aiAgent.ts`
- 模型与供应商：`aiModel.ts`、`aiProvider.ts`
- 文件与知识库：`file.ts`、`document.ts`、`chunk.ts`、`knowledge.ts`、`knowledgeBase.ts`、`notebook.ts`、`search.ts`
- 生成能力：`generation.ts`、`generationBatch.ts`、`generationTopic.ts`、`image/`、`video/`、`comfyui.ts`
- 用户与系统：`user.ts`、`userMemory.ts`、`userMemories.ts`、`apiKey.ts`、`usage.ts`、`device.ts`、`notification.ts`、`config/`
- 导入导出与分享：`importer.ts`、`exporter.ts`、`share.ts`
- 市场：`market/`
- 其他集成：`plugin.ts`、`oauthDeviceFlow.ts`、`klavis.ts`、`messenger.ts`、`botMessage.ts`

典型 router 文件会从 `@/libs/trpc/lambda` 导入：

- `router`：创建 tRPC router。
- `publicProcedure`：不强制登录的 procedure。
- `authedProcedure`：需要用户身份的 procedure。
- `heteroAuthedProcedure`：异构 agent 操作相关的特殊鉴权 procedure，见 `aiAgent.ts` 的 import。

很多 router 还会引入：

```ts
import { serverDatabase } from '@/libs/trpc/lambda/middleware';
```

然后通过 middleware 把 `serverDB` 注入 `ctx`，再构造对应 Model。

### `_template.ts`：router 写法模板

`_template.ts` 展示了一个典型领域 router 的组织方式。它以 `sessionGroupRouter` 为例：

- 用 `authedProcedure.use(serverDatabase)` 构造领域 procedure。
- 在 middleware 中创建 `SessionGroupModel` 并注入 `ctx.sessionGroupModel`。
- 用 `zod` 校验输入。
- 暴露 `createSessionGroup`、`getSessionGroup`、`removeSessionGroup`、`updateSessionGroup` 等 mutation/query。

这说明本目录的常见风格是：

1. procedure 层负责鉴权、输入校验、组装上下文。
2. 数据操作委托给 `database/models` 中的 Model。
3. router 不直接写大量 SQL，而是调用模型或服务层。

### `config/`：运行时配置 router

`config/index.ts` 是一个比较典型的公开配置 router。它导出 `configRouter`，包含：

- `getDefaultAgentConfig`
- `getGlobalConfig`
- `...businessConfigEndpoints`

`getGlobalConfig` 会并行读取：

- `getServerGlobalConfig()`
- `getServerFeatureFlagsStateFromRuntimeConfig(ctx.userId || undefined)`
- `getActiveBillboard()`

其中 `getActiveBillboard()` 会在 `EdgeConfig.isEnabled()` 时读取公告栏配置，并用 `normalizeBillboard` / `normalizeBillboardItem` 做轻量结构校验。失败时只记录 debug 日志并返回 `null`，避免配置系统异常影响主流程。

### `_helpers/` 与 `_schema/`

目录下还有公共辅助与输入结构：

- `_helpers/resolveContext.ts`
- `_schema/context.ts`
- `_schema/documentHistory.ts`

根据命名和测试文件推断，这些文件用于在多个 router 之间复用上下文解析逻辑与 zod/schema 定义，避免每个业务 router 重复实现相同的输入结构或上下文转换。

### 子目录 router

几个子目录代表较复杂的业务域：

- `market/`：市场相关 router，包含 `agent.ts`、`agentGroup.ts`、`skill.ts`、`social.ts`、`user.ts`、`oidc.ts`、`creds.ts` 等。
- `image/`：图片生成相关，含 `index.ts`、`utils.ts` 和测试。
- `video/`：视频生成相关，含 `index.ts`、`error.ts` 和测试。
- `config/`：系统配置 router。
- `__tests__/`：本目录主 router 的单元测试集合。

## 上下游关系

### 上游：请求如何进来

主要入口链路是：

1. 客户端 tRPC client 请求 `/trpc/lambda`。
2. Next.js route `src/app/(backend)/trpc/lambda/[trpc]/route.ts` 接收请求。
3. route 引入 `createLambdaContext` 创建上下文。
4. route 引入 `lambdaRouter` 作为 tRPC 根 router。
5. tRPC 根据路径分发到具体子 router 和 procedure。

从搜索结果看，`apps/cli/src/api/client.ts` 也会请求 `${serverUrl}/trpc/lambda`，桌面端测试中也出现 `lobe-backend://app/trpc/lambda/...`。这说明同一个 `lambdaRouter` 服务于 Web、桌面、CLI 等多个入口。

### 中游：tRPC 基础设施

`@/libs/trpc/lambda/index.ts` 定义了本目录最常用的基础对象：

- `router = trpc.router`
- `publicProcedure = baseProcedure`
- `authedProcedure = baseProcedure.use(oidcAuth).use(userAuth)`
- `heteroAuthedProcedure = baseProcedure.use(heteroOperationAuth).use(userAuth)`
- `createCallerFactory = trpc.createCallerFactory`

其中 `baseProcedure` 统一挂了 `openTelemetry`，所以无论公开接口还是登录接口，都会经过可观测性中间件。

`createLambdaContext` 位于 `src/libs/trpc/lambda/context.ts`，负责从 `NextRequest` 中提取：

- `userId`
- `clientIp`
- `userAgent`
- `marketAccessToken`
- `traceContext`
- `oidcAuth`
- `resHeaders`

它支持多种认证来源：

- 开发环境 mock 用户。
- `X-API-Key` 请求头。
- OIDC JWT。
- 根据当前片段可见，后续还会继续 fallback 到其他 auth 机制，例如项目中的 `auth`。

### 下游：数据库、模型、服务

多数业务 router 会继续调用：

- `@/database/models/*`
- `@/database/schemas`
- `@/server/*` 服务
- `@/business/server/lambda-routers/*`
- 第三方或平台 SDK，例如 market、EdgeConfig、ComfyUI、Klavis 等

数据库连接通常通过 `serverDatabase` middleware 注入：

```ts
export const serverDatabase = trpc.middleware(async (opts) => {
  const serverDB = await getServerDB();

  return opts.next({
    ctx: { serverDB },
  });
});
```

然后业务 router 再基于 `ctx.serverDB` 和 `ctx.userId` 创建领域 Model。这样做的好处是：鉴权、数据库连接、模型注入都有明确层次，不会散落在每个 procedure 的主体逻辑里。

### 横向关系：business routers

`index.ts` 还从 `@/business/server/lambda-routers/*` 引入商业功能 router，例如：

- `accountDeletionRouter`
- `referralRouter`
- `spendRouter`
- `subscriptionRouter`
- `taskTemplateRouter`
- `topUpRouter`

这说明开源主仓与商业功能之间通过根 router 做组合。阅读时要注意：`lambdaRouter` 的完整 API 面并不只来自 `src/server/routers/lambda`，还有 `business/server/lambda-routers` 的扩展。

## 运行/调用流程

以一个普通登录接口为例，流程大致如下：

1. 前端或 CLI 通过 tRPC client 请求 `/trpc/lambda/message.someProcedure`。
2. Next.js route `src/app/(backend)/trpc/lambda/[trpc]/route.ts` 接住请求。
3. `createLambdaContext(request)` 从请求头、cookie、API Key、OIDC、session 等信息中解析出 `ctx`。
4. tRPC 进入 `lambdaRouter`。
5. `lambdaRouter` 根据第一段命名空间找到子 router，例如 `messageRouter`。
6. procedure 如果使用 `authedProcedure`，会先经过 `oidcAuth`、`userAuth` 等认证中间件。
7. procedure 如果使用 `serverDatabase`，会调用 `getServerDB()` 并把 `serverDB` 放进 `ctx`。
8. 领域 middleware 可能继续创建 Model，例如 `new SessionGroupModel(ctx.serverDB, ctx.userId)`。
9. procedure 用 `zod` 校验输入，然后调用 Model 或服务函数。
10. 返回值经 tRPC 序列化后返回客户端。

以 `config.getGlobalConfig` 这种公开接口为例，流程略有不同：

1. 使用 `publicProcedure`，不强制用户登录。
2. 但 `ctx.userId` 如果能从请求中解析出来，仍然可以参与 feature flag 计算。
3. 它并行读取 server config、feature flags、billboard。
4. 返回统一的 `GlobalRuntimeConfig`。

以服务端内部调用为例：

1. 后端 route 引入 `createCallerFactory`。
2. 用 `createCallerFactory(lambdaRouter)` 创建 caller。
3. 传入 context 后直接调用某个 procedure。
4. 这种调用不经过浏览器 HTTP client，但仍复用同一套 router 逻辑。

## 小白阅读顺序

1. 先读 `src/server/routers/lambda/index.ts`  
   目标是建立地图：有哪些业务域、每个域在根 router 里的命名空间叫什么。不要一开始钻进单个大文件。

2. 再读 `src/libs/trpc/lambda/index.ts`  
   理解 `router`、`publicProcedure`、`authedProcedure`、`heteroAuthedProcedure` 的区别。这里决定了每个接口是否需要登录、是否带特殊鉴权、是否统一接入 telemetry。

3. 再读 `src/libs/trpc/lambda/context.ts`  
   重点看 `createLambdaContext` 如何从请求里得到 `userId`、`marketAccessToken`、`traceContext` 等。很多 router 里使用的 `ctx.userId` 并不是凭空来的。

4. 再读 `src/libs/trpc/lambda/middleware/serverDatabase.ts`  
   理解 `ctx.serverDB` 是如何注入的。后面读业务 router 时，看到 `authedProcedure.use(serverDatabase)` 就知道它获得了数据库连接。

5. 读 `_template.ts` 或一个简单 router，例如 `sessionGroup.ts`  
   这类文件最适合入门：结构短，能看到 zod input、query/mutation、Model 调用、返回值。

6. 读 `config/index.ts`  
   这是公开配置接口的代表，能看到非登录接口如何读取 server config、feature flags、EdgeConfig。

7. 最后按业务兴趣读复杂 router  
   如果关注聊天，读 `message.ts`、`topic.ts`、`session.ts`、`aiChat.ts`。如果关注 Agent，读 `agent.ts`、`aiAgent.ts`、`agentDocument.ts`、`agentSignal.ts`。如果关注知识库，读 `file.ts`、`document.ts`、`chunk.ts`、`knowledgeBase.ts`。

## 常见误区

1. 不要把 `lambda` 理解成一定部署在 AWS Lambda  
   这里的 `lambda` 更像是 LobeHub 对主 tRPC 后端通道的命名。实际入口是 Next.js route `/trpc/lambda`，也可被桌面端、CLI、服务端 caller 复用。

2. 不要以为一个 router 文件等于一个 REST 路径  
   tRPC 是按 router namespace 和 procedure name 调用的。`message.ts` 不是 `/message` REST controller，而是会被挂到 `lambdaRouter.message` 下面。

3. `publicProcedure` 不等于“无上下文”  
   `publicProcedure` 只是不强制登录。`createLambdaContext` 仍然可能解析出 `userId`、`marketAccessToken`、`clientIp`、`traceContext`。公开接口也可以根据可选用户态返回不同配置。

4. `authedProcedure` 只解决身份，不自动提供数据库  
   要使用数据库，router 通常还需要 `.use(serverDatabase)`。否则 `ctx` 里不会自动有 `serverDB`。

5. 不要在 procedure 主体里重复 new Model  
   本目录的推荐模式是通过 procedure middleware 注入领域 Model，例如 `_template.ts` 里的 `sessionProcedure`。这样 procedure 主体只关注输入、调用和返回。

6. 根 router 的 API 面不只来自当前目录  
   `lambdaRouter` 还混入了 `@/business/server/lambda-routers/*`。如果只看 `src/server/routers/lambda`，会漏掉订阅、充值、消费、推荐等商业功能接口。

7. `_schema/` 不是数据库 schema  
   这里的 `_schema` 更偏 router 输入/上下文相关 schema。数据库表结构在 `database/schemas` 或相关 package 中。

8. 测试不是集中在一个文件  
   这个目录下有大量按领域拆分的测试，例如 `__tests__/message.test.ts`、`__tests__/aiAgent.test.ts`、`config/index.test.ts`、`image/index.test.ts`、`video/error.test.ts`。排查某个接口时，应优先找同名或相邻测试文件。

9. 根据当前片段推断，错误处理风格并不完全统一  
   `trpc-router` 技能文档建议用 `TRPCError` 包装错误并返回 `{ data, success: true }` 等结构，但已读到的 `_template.ts` 中有些 procedure 直接返回 `id` 或 Model 结果。阅读具体业务时要以当前文件实际返回值为准，不要假设所有 router 都有统一响应壳。

10. `configRouter` 的容错是有意设计  
   `getActiveBillboard()` 读取 EdgeConfig 失败或 payload 校验失败时返回 `null`，而不是抛错。这类配置接口通常优先保证主应用能启动和渲染。
