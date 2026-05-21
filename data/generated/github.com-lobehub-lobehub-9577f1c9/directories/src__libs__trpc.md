# 目录：src/libs/trpc

## 它负责什么

`src/libs/trpc` 是这套代码里 tRPC 的“基础设施层”，负责把前端/服务端调用、鉴权、上下文、观测、错误处理和请求适配统一起来。它不是某个业务模块，而是所有 tRPC router 的公共底座。

从结构上看，它分成两条主链路：

- `lambda`：主业务链路，服务于大部分用户态 API。见 [lambda/index.ts](./src/libs/trpc/lambda/index.ts)。
- `async`：异步/后台链路，走内部 JWT + 加密用户标识，主要用于服务器到服务器的调用。见 [async/index.ts](./src/libs/trpc/async/index.ts)。

另外还有客户端封装、middleware、工具函数和测试/Mock 入口。

## 关键组成

1. `src/libs/trpc/lambda/*`
   - [context.ts](./src/libs/trpc/lambda/context.ts)：构建请求上下文，处理 API Key、OIDC、Better Auth、market cookie、trace context 等。
   - [init.ts](./src/libs/trpc/lambda/init.ts)：初始化 `trpc`，统一 `superjson` 和错误格式化。
   - [index.ts](./src/libs/trpc/lambda/index.ts)：导出 `router`、`publicProcedure`、`authedProcedure`、`heteroAuthedProcedure` 等基建。
   - `middleware/*`：拆出 `userAuth`、`oidcAuth`、`serverDatabase`、`telemetry`、`marketUserInfo`、`marketSDK`、`heteroOperationAuth`。

2. `src/libs/trpc/async/*`
   - [context.ts](./src/libs/trpc/async/context.ts)：只保留 `authorizationToken`、`userId`、`serverDB` 这类异步链路所需字段。
   - [asyncAuth.ts](./src/libs/trpc/async/asyncAuth.ts)：验证内部 JWT，并校验数据库中的用户。
   - [index.ts](./src/libs/trpc/async/index.ts)：给异步路由提供 `asyncRouter`、`asyncAuthedProcedure`。

3. `src/libs/trpc/client/*`
   - [client/index.ts](./src/libs/trpc/client/index.ts)：统一导出 `asyncClient`、`lambdaClient`、`toolsClient`。
   - `lambda.ts`：主客户端，带 401 处理、market 401 事件派发、动态注入 auth header。
   - `async.ts`：异步客户端，指向 `/trpc/async`。
   - `tools.ts`：工具链路客户端，指向 `/trpc/tools`。

4. `src/libs/trpc/utils/*`
   - [internalJwt.ts](./src/libs/trpc/utils/internalJwt.ts)：签发/校验内部 JWT、用户 JWT、hetero-operation JWT。
   - [request-adapter.ts](./src/libs/trpc/utils/request-adapter.ts)：克隆 Next.js `Request`，规避 body 被锁定。
   - [responseMeta.ts](./src/libs/trpc/utils/responseMeta.ts)：补充响应头，尤其是 `AUTH_REQUIRED_HEADER`。

5. `src/libs/trpc/mock.ts`
   - 提供测试用 `createCaller`，给 server-side test 直接调用 router。

## 上下游关系

上游入口主要是 Next.js route handler：

- [src/app/(backend)/trpc/lambda/[trpc]/route.ts](./src/app/(backend)/trpc/lambda/[trpc]/route.ts)
- [src/app/(backend)/trpc/async/[trpc]/route.ts](./src/app/(backend)/trpc/async/[trpc]/route.ts)
- [src/app/(backend)/trpc/mobile/[trpc]/route.ts](./src/app/(backend)/trpc/mobile/[trpc]/route.ts)
- [src/app/(backend)/trpc/tools/[trpc]/route.ts](./src/app/(backend)/trpc/tools/[trpc]/route.ts)

它们都用 `fetchRequestHandler`，并统一复用：

- `prepareRequestForTRPC`
- `createResponseMeta`
- 对应的 `createLambdaContext` 或 `createAsyncRouteContext`

下游则是具体 router 与业务代码：

- `src/server/routers/lambda/*`
- `src/server/routers/async/*`
- `src/server/routers/tools/*`
- `src/server/services/*`
- `src/services/*`、`src/store/*`、`src/routes/*`、`src/features/*`

根据当前片段推断，`lambdaClient` 是最广泛的前端调用入口；`async` 则主要被服务端 `createAsyncCaller` 使用，用于跨层异步任务。

## 运行/调用流程

1. 浏览器或服务端代码调用 `lambdaClient` / `toolsClient` / `asyncClient`。
2. Next.js route handler 接到请求后，先通过 `prepareRequestForTRPC()` 克隆请求体。
3. `fetchRequestHandler` 创建对应上下文：
   - `lambda`：`createLambdaContext()` 解析 API Key、OIDC、Better Auth、market cookie、trace 信息。
   - `async`：`createAsyncRouteContext()` 要求标准 `Authorization` 和加密后的 `LOBE_CHAT_AUTH_HEADER`，再解密得到 `userId`。
4. router 进入 base procedure：
   - `lambda` 默认挂 `openTelemetry`
   - `lambda authedProcedure` 再叠 `oidcAuth` / `userAuth`
   - `asyncAuthedProcedure` 先查 DB，再跑 `asyncAuth`
5. `responseMeta()` 在错误场景补 `AUTH_REQUIRED_HEADER`，让桌面端能区分真正的登录失效。
6. 客户端侧的 `lambda.ts` / `tools.ts` 会对 401 做额外处理，尤其是 market 401 事件派发。

## 小白阅读顺序

1. 先看 [lambda/index.ts](./src/libs/trpc/lambda/index.ts)，理解主 router 的基类怎么定义。
2. 再看 [lambda/context.ts](./src/libs/trpc/lambda/context.ts)，搞清楚“请求来了以后先认谁”。
3. 接着看 [lambda/middleware/index.ts](./src/libs/trpc/lambda/middleware/index.ts) 和各 middleware，理解鉴权顺序。
4. 再看 [async/index.ts](./src/libs/trpc/async/index.ts) 与 [async/asyncAuth.ts](./src/libs/trpc/async/asyncAuth.ts)，对比异步链路和主链路差异。
5. 然后看 [client/index.ts](./src/libs/trpc/client/index.ts) 及 `lambda.ts`，理解前端怎么接入。
6. 最后回到 [src/app/(backend)/trpc/*/route.ts](./src/app/(backend)/trpc/lambda/[trpc]/route.ts)，把“入口 -> context -> middleware -> router”串起来。

## 常见误区

- 把 `lambda` 和 `async` 当成同一种 tRPC 入口。前者是主业务 API，后者是内部异步调用，鉴权方式完全不同。
- 忽略 middleware 顺序。比如 `marketSDK` 依赖 `marketUserInfo`，`userAuth` 依赖前面的 `oidcAuth` 先把 `userId` 放进上下文。
- 以为 `async` 只要有用户 ID 就行。实际上它还要通过 `validateInternalJWT()` 证明请求确实来自内部调用。
- 忘记 `createResponseMeta()` 的桌面端兼容意义。`UNAUTHORIZED` 不只是一个错误码，它还会影响客户端是否弹登录态处理。
- 在 Next.js route handler 里直接用原始 `req`。这里专门用 `prepareRequestForTRPC()`，就是为了避免 body stream 被锁定。
- 只看客户端代码，不看 `src/server/routers/*`。这里的真正能力边界是 router 和 middleware，不是 `createTRPCClient()` 本身。
