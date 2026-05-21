# 目录：src/libs/trpc/lambda

## 它负责什么

`src/libs/trpc/lambda` 是 LobeHub 后端 tRPC “lambda 入口”的基础设施层。它不直接实现业务接口，而是为 `src/server/routers/lambda`、`src/server/routers/mobile`、`src/server/routers/tools` 等路由提供统一的：

- tRPC 初始化配置：`trpc`、`router`、`createCallerFactory`
- 请求上下文构建：`createLambdaContext`
- 基础 procedure：`publicProcedure`、`authedProcedure`、`heteroAuthedProcedure`
- 可复用中间件：数据库、OIDC、异构 Agent 操作鉴权、Market SDK、遥测开关等

可以把它理解成“tRPC 路由的地基”：业务 router 只关心输入输出和服务调用，而认证、上下文、OpenTelemetry、数据库注入等横切逻辑都先在这里定义好。

从命名看，`lambda` 更偏向服务端函数式 API 的 tRPC 运行环境，不是前端客户端，也不是具体业务模块。

## 关键组成

`context.ts` 负责把一次 `NextRequest` 转成 tRPC 可用的 `LambdaContext`。

核心导出有：

- `AuthContext`：定义上下文中可能出现的字段，如 `userId`、`oidcAuth`、`marketAccessToken`、`clientIp`、`userAgent`、`traceContext`、`resHeaders`
- `createContextInner`：测试和服务端内部调用使用的上下文构造函数，不依赖真实 `NextRequest`
- `LambdaContext`：`createContextInner` 的返回类型
- `createLambdaContext`：真实 HTTP 请求入口使用的上下文构造函数

`createLambdaContext` 做了几类事情：

- 读取开发调试用户：开发环境下支持 `lobe-auth-dev-backend-api` 或 `ENABLE_MOCK_DEV_USER`
- 提取请求信息：`user-agent`、`x-forwarded-for`、`x-real-ip`
- 从 cookie 中读取 `mp_token`，作为 Market 访问 token
- 从请求头中提取 trace context，用于链路追踪父子关系
- 支持 `X-API-Key` 鉴权：通过 `ApiKeyModel.findByKey` 校验 key 格式、启用状态、过期状态，并异步更新 last used
- 支持 OIDC 鉴权：读取 `LOBE_CHAT_OIDC_AUTH_HEADER`，使用 `validateOIDCJWT` 校验 JWT，并通过 `assertOIDCUserActive` 确认用户仍可用

根据当前片段推断，`context.ts` 后半段还会继续处理常规登录态，因为文件引入了 `auth`、`jwtPayload` 等字段，且 `authedProcedure` 后续会依赖 `ctx.userId`。依据是 `AuthContext` 中保留了 `jwtPayload` 和 `userId`，并且大量业务 router 使用 `authedProcedure` 作为普通登录用户入口。

`init.ts` 负责 tRPC 根实例初始化。

它通过：

```ts
initTRPC.context<LambdaContext>().create(...)
```

创建统一的 `trpc` 对象，并配置了两件关键能力：

- `transformer: superjson`：让 tRPC 可以序列化更复杂的数据类型，而不是只支持普通 JSON
- `errorFormatter`：如果错误的 `cause` 中带有 `data`，会把它挂到返回 shape 的 `data.errorData` 上，方便客户端拿到结构化错误信息

`index.ts` 是这个目录最重要的对外入口。

它导出：

- `router = trpc.router`
- `publicProcedure`
- `authedProcedure`
- `heteroAuthedProcedure`
- `createCallerFactory`

其中 procedure 的链路是：

- `publicProcedure = trpc.procedure.use(openTelemetry)`
- `authedProcedure = publicProcedure.use(oidcAuth).use(userAuth)`
- `heteroAuthedProcedure = publicProcedure.use(heteroOperationAuth).use(userAuth)`

这说明所有 lambda tRPC procedure 默认都会先经过 `openTelemetry`。需要登录的接口再追加 `oidcAuth` 和通用 `userAuth`。异构 Agent 的 ingest / finish 类接口则使用专门的 `heteroOperationAuth`，避免普通用户 token 和异构操作 token 混用。

`middleware/` 下是可组合的 tRPC middleware：

- `serverDatabase.ts`：调用 `getServerDB()`，向 `ctx` 注入 `serverDB`
- `oidcAuth.ts`：如果 `ctx.oidcAuth` 存在，则把 `ctx.userId` 设置为 `ctx.oidcAuth.sub`；但会拒绝 `purpose === 'hetero-operation'` 的 token
- `heteroOperationAuth.ts`：只接受 `purpose === 'hetero-operation'` 的 OIDC token，否则抛出 `UNAUTHORIZED`
- `telemetry.ts`：根据环境变量和用户设置计算 `ctx.telemetryEnabled`
- `marketUserInfo.ts`：依赖 `serverDB` 和 `userId`，查询用户邮箱、昵称等信息，生成 `marketUserInfo`，并优先使用数据库中的 Market access token
- `marketSDK.ts`：基于 `marketAccessToken` 和 `marketUserInfo` 创建 `MarketService`，向上下文注入 `marketService` 和兼容字段 `marketSDK`
- `middleware/index.ts`：重新导出这些 middleware，方便业务 router 统一引用

## 上下游关系

上游入口主要是 Next.js route handler。

已看到的调用方包括：

- `src/app/(backend)/trpc/lambda/[trpc]/route.ts`
- `src/app/(backend)/trpc/mobile/[trpc]/route.ts`
- `src/app/(backend)/trpc/tools/[trpc]/route.ts`

这些入口会把请求交给 tRPC handler，并使用 `createLambdaContext(req)` 生成上下文。也就是说，HTTP 请求真正进入业务 router 前，先经过本目录提供的 context 构建逻辑。

业务下游主要是 `src/server/routers/**`。

典型引用方式包括：

```ts
import { authedProcedure, publicProcedure, router } from '@/libs/trpc/lambda';
import { serverDatabase } from '@/libs/trpc/lambda/middleware';
```

例如：

- `src/server/routers/lambda/config/index.ts` 使用 `publicProcedure`
- `src/server/routers/lambda/message.ts` 同时使用 `publicProcedure` 和 `authedProcedure`
- `src/server/routers/lambda/user.ts`、`agent.ts`、`file.ts`、`task.ts` 等使用 `authedProcedure.use(serverDatabase)`
- `src/server/routers/tools/mcp.ts` 使用 `serverDatabase` 和 `telemetry`
- `src/server/routers/tools/market.ts` 使用 `marketUserInfo`、`marketSDK`、`requireMarketAuth`
- `src/server/routers/lambda/aiAgent.ts` 使用 `heteroAuthedProcedure`

还有一种上游是服务端内部直接调用 tRPC router。比如 `src/app/(backend)/webapi/create-image/comfyui/route.ts` 使用 `createCallerFactory(lambdaRouter)` 创建 server-side caller。这类调用不经过浏览器请求，但仍可以复用同一套 router 和 context 类型。

测试中也大量使用：

```ts
createCallerFactory(...)
createContextInner(...)
```

这说明 `createContextInner` 是为了让单元测试绕开真实 `NextRequest`，直接构造 `userId`、`marketAccessToken` 等上下文字段。

## 运行/调用流程

一次常规 lambda tRPC 请求大致流程如下：

1. 客户端请求 `/trpc/lambda/[trpc]`、`/trpc/mobile/[trpc]` 或 `/trpc/tools/[trpc]` 之类的后端入口。

2. Next.js route handler 调用 tRPC 的请求处理器，并传入：
   - 对应 router，例如 `lambdaRouter`
   - `createContext: () => createLambdaContext(req)`

3. `createLambdaContext` 从请求中提取基础信息：
   - IP：优先 `x-forwarded-for`，其次 `x-real-ip`
   - User-Agent：`user-agent`
   - Market token：cookie 里的 `mp_token`
   - Trace context：从请求头解析链路追踪信息

4. `createLambdaContext` 处理认证来源：
   - 开发环境可返回 mock user
   - 如果存在 `X-API-Key`，优先校验 API key；失败时不会继续 fallback 到其他认证方式，而是返回 `userId: null`
   - 如果启用 OIDC 且存在 OIDC header，则校验 JWT，并确认用户未被禁用或删除
   - 根据当前片段推断，后续还会尝试常规登录态认证，最终把 `userId` 放入 context

5. tRPC 找到目标 procedure。

6. 所有 procedure 先经过 `openTelemetry`，记录调用链路和观测信息。

7. 如果是 `publicProcedure`，业务 resolver 可以直接执行。注意 public 不等于一定没有用户，只是“不强制登录”。

8. 如果是 `authedProcedure`：
   - 先经过 `oidcAuth`
   - `oidcAuth` 会把普通 OIDC token 转换成 `ctx.userId`
   - 如果 token 是 `hetero-operation`，会被拒绝
   - 再经过 `userAuth`，由通用鉴权中间件确认用户确实已登录

9. 如果是 `heteroAuthedProcedure`：
   - 必须存在 `ctx.oidcAuth.purpose === 'hetero-operation'`
   - 其他 token，包括普通用户 OIDC token，都会被拒绝
   - 然后同样经过 `userAuth`

10. 业务 router 可以继续追加中间件。例如：
    - `.use(serverDatabase)` 注入 `ctx.serverDB`
    - `.use(telemetry)` 注入 `ctx.telemetryEnabled`
    - `.use(marketUserInfo).use(marketSDK)` 注入 Market 用户信息和服务实例

一个典型业务组合是：

```ts
const someProcedure = authedProcedure
  .use(serverDatabase)
  .use(async ({ ctx, next }) => {
    // 基于 ctx.userId 和 ctx.serverDB 构造业务 model/service
    return next({ ctx: { ... } });
  });
```

这体现了本目录的设计思想：基础设施中间件只负责补齐上下文，业务 router 再基于上下文创建自己的 model 或 service。

## 小白阅读顺序

1. 先读 `src/libs/trpc/lambda/index.ts`

   这是最短也最核心的入口。先理解 `router`、`publicProcedure`、`authedProcedure`、`heteroAuthedProcedure` 是怎么导出的。读完这里，就能看懂业务 router 为什么都从 `@/libs/trpc/lambda` 导入这些名字。

2. 再读 `src/libs/trpc/lambda/init.ts`

   重点看 `initTRPC.context<LambdaContext>()`、`superjson` 和 `errorFormatter`。这里决定了整个 lambda tRPC 的类型上下文、序列化方式和错误返回形态。

3. 然后读 `src/libs/trpc/lambda/context.ts`

   这是最复杂的文件。建议按“请求信息提取 -> API key -> OIDC -> 普通登录态”的顺序看。不要一开始陷入每个 auth helper 的实现细节，先理解它最终要产出的是 `LambdaContext`。

4. 接着读 `middleware/serverDatabase.ts`

   这是最简单的 middleware：拿到数据库连接，塞进 `ctx.serverDB`。读它可以帮助理解 tRPC middleware 的 `opts.next({ ctx: ... })` 模式。

5. 再读 `middleware/oidcAuth.ts` 和 `middleware/heteroOperationAuth.ts`

   这两个文件要对照看。普通登录接口拒绝 `hetero-operation` token；异构操作接口只接受 `hetero-operation` token。它们共同保证 token 的使用边界。

6. 最后读 Market 和 telemetry 相关 middleware

   推荐顺序是：
   - `marketUserInfo.ts`
   - `marketSDK.ts`
   - `telemetry.ts`

   这些文件依赖前面的 `userId`、`serverDB` 等上下文。理解了基础 middleware 后再看会轻松很多。

7. 找业务调用方验证理解

   可以看 `src/server/routers/lambda/user.ts`、`src/server/routers/lambda/message.ts`、`src/server/routers/tools/market.ts` 这类文件。它们展示了业务 router 如何组合 `authedProcedure`、`serverDatabase`、`marketSDK` 等能力。

## 常见误区

1. 误以为 `publicProcedure` 一定没有用户信息

   `publicProcedure` 的意思是“不强制登录”，不是“禁止登录”。如果请求本身带了有效认证信息，`createLambdaContext` 仍可能把 `userId` 放进 `ctx`。所以 public resolver 里看到 `ctx.userId` 并不奇怪。

2. 误以为 `oidcAuth` 会负责所有登录校验

   `oidcAuth` 主要处理 `ctx.oidcAuth` 到 `ctx.userId` 的转换，并过滤不该用于普通接口的 `hetero-operation` token。真正“必须登录”的强制校验还要看后面的 `userAuth`。所以 `authedProcedure` 是 `.use(oidcAuth).use(userAuth)`，两者职责不同。

3. 忽略 middleware 的顺序

   `telemetry` 需要 `serverDB` 和 `userId` 才能读取用户设置；`marketUserInfo` 也需要先有 `serverDB`；`marketSDK` 又依赖 `marketUserInfo` 产出的用户信息。顺序错了，ctx 字段就可能不存在。

4. 误把异构 Agent token 当成普通登录 token

   `hetero-operation` token 是专门给异构 Agent ingest / finish 场景使用的。普通 `authedProcedure` 会拒绝它；`heteroAuthedProcedure` 又只接受它。这是有意设计的隔离，避免长时效、窄用途 token 被拿去访问普通用户接口。

5. 误以为 API key 失败后会自动尝试 Cookie/OIDC 登录

   当前片段显示，如果请求带了 `X-API-Key`，但 API key 校验失败，会直接返回 `userId: null`，并记录“rejecting request without fallback auth”。也就是说，带了错误 API key 反而不会继续走其他认证方式。

6. 误以为 `serverDatabase` 是全局自动注入的

   不是。基础 `publicProcedure` 和 `authedProcedure` 只包含 OpenTelemetry 和认证相关逻辑。业务 resolver 如果要用数据库，需要显式 `.use(serverDatabase)`，否则 `ctx.serverDB` 不一定存在。

7. 误以为 Market 的 token 只来自 cookie

   `createLambdaContext` 会从 cookie 读取 `mp_token`，但 `marketUserInfo` 中会优先读取数据库里 `user_settings.market.accessToken`，数据库 token 优先级高于 cookie token。

8. 误把 `createContextInner` 当成生产入口

   `createContextInner` 是内部构造函数，适合测试或 server-side caller 手动创建上下文。真实 HTTP 请求入口应该使用 `createLambdaContext(request)`，因为它会解析 headers、cookies、trace、API key、OIDC 等请求级信息。
