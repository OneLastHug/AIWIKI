# 目录：src/app/(backend)/trpc

## 它负责什么

`src/app/(backend)/trpc` 是 LobeHub 在 Next.js App Router 后端中的 tRPC HTTP 入口目录。它本身不承载具体业务逻辑，而是把浏览器、桌面端、移动端或内部异步任务发来的 HTTP 请求接入 `@trpc/server/adapters/fetch`，再分发给 `src/server/routers/*` 中真正的业务 router。

可以把它理解成“tRPC 网关层”：

- 接收 `/trpc/lambda/*`、`/trpc/async/*`、`/trpc/mobile/*`、`/trpc/tools/*` 请求。
- 克隆 `NextRequest`，规避 Next.js 16 中 request body stream 被内部消费后导致 tRPC 无法读取的问题。
- 创建对应的 tRPC context，例如用户身份、IP、User-Agent、trace context、API Key/OIDC/Better Auth 认证信息。
- 绑定对应 root router，例如 `lambdaRouter`、`asyncRouter`、`mobileRouter`、`toolsRouter`。
- 统一处理错误日志和响应 metadata，例如认证失败时追加桌面端可识别的 `X-Auth-Required` 类 header。

目录结构很薄：

```txt
src/app/(backend)/trpc
├── async/[trpc]/route.ts
├── lambda/[trpc]/route.ts
├── mobile/[trpc]/route.ts
├── tools/[trpc]/route.ts
└── trpc.test.ts
```

这里的 `[trpc]` 是 Next.js 动态路由段，实际 tRPC procedure path 会继续挂在这个动态段下，例如客户端调用 `lambdaClient.user.getUserState.query()` 时，请求会打到 `/trpc/lambda/user.getUserState` 或批处理形式的相近 URL。

## 关键组成

`lambda/[trpc]/route.ts` 是主 Web/桌面业务 API 入口。它引入 `lambdaRouter`，endpoint 设置为 `/trpc/lambda`，context 使用 `createLambdaContext(req)`。该 context 会尝试从请求中解析用户身份，支持开发态 mock 用户、`X-API-Key`、OIDC header、Better Auth session、cookie 中的 `mp_token`、traceparent 追踪上下文、客户端 IP 和 User-Agent。`UNAUTHORIZED` 错误在这里被视为常规登录态失效，不会额外打印成服务端异常日志。

`async/[trpc]/route.ts` 是异步任务相关入口。它引入 `asyncRouter`，endpoint 为 `/trpc/async`，context 使用 `createAsyncRouteContext(req)`。这个 context 要求请求同时带有标准 `Authorization` header 和 LobeHub 自定义认证 header，然后通过 `KeyVaultsGateKeeper` 解密后取出 `userId`。它还显式设置 `allowBatching: false`，注释说明是为了避免请求间相互干扰。根据当前片段推断，`async` 入口更多服务于文档、文件、图片、视频、RAG Eval 等后台异步处理流程，而不是普通前台页面的高频查询。

`mobile/[trpc]/route.ts` 是移动端 API 入口。它复用 `createLambdaContext(req)`，但绑定的是 `mobileRouter`。`mobileRouter` 并不是全量业务 router，而是从 `lambda` 业务 router 中挑选移动端实际需要的模块，例如 `agent`、`aiAgent`、`aiChat`、`config`、`file`、`message`、`session`、`topic`、`upload`、`user`，并额外接入移动端订阅相关 router。它的定位是“移动端裁剪版 lambda API”。

`tools/[trpc]/route.ts` 是工具调用相关入口。它也复用 `createLambdaContext(req)`，但绑定 `toolsRouter`。`toolsRouter` 下主要包含 `klavis`、`market`、`mcp`、`search` 和 `healthcheck`。前端 `src/services/mcp.ts`、`src/services/search.ts` 会通过 `toolsClient` 调它，用于云端 MCP、搜索、市场工具等能力。

`trpc.test.ts` 只做结构性守护：断言 `async`、`lambda`、`mobile`、`tools` 四个 route 目录存在。这个测试不验证业务行为，而是防止关键 tRPC 入口目录被误删或重命名。

四个 `route.ts` 都有共同骨架：

```ts
const handler = (req: NextRequest) => {
  const preparedReq = prepareRequestForTRPC(req);

  return fetchRequestHandler({
    createContext: () => ...,
    endpoint: '/trpc/...',
    onError: ...,
    req: preparedReq,
    responseMeta: createResponseMeta,
    router: ...Router,
  });
};

export { handler as GET, handler as POST };
```

其中 `GET` 和 `POST` 都导出同一个 handler，说明 tRPC 查询和变更最终都由 `fetchRequestHandler` 统一解析。

## 上下游关系

上游主要是客户端 tRPC client 和各类 service 层。

普通业务前端通过 `src/libs/trpc/client/lambda.ts` 创建 `lambdaClient`，URL 指向 `withElectronProtocolIfElectron('/trpc/lambda')`。大量 `src/services/*` 模块会 import `lambdaClient`，例如 `src/services/user/index.ts` 调 `lambdaClient.user.getUserState.query()`，`src/services/session/index.ts` 调 `lambdaClient.session.createSession.mutate()`，`src/services/file/index.ts` 调 `lambdaClient.file.*`。

工具相关前端通过 `src/libs/trpc/client/tools.ts` 创建 `toolsClient`，URL 指向 `/trpc/tools`。它会动态注入 `createHeaderWithAuth()` 生成的认证 header，并对 market API 的 401 做专门事件通知。

异步任务客户端通过 `src/libs/trpc/client/async.ts` 创建 `asyncClient`，URL 指向 `/trpc/async`，使用 `httpBatchLink` 和 `superjson`。不过服务端入口里 `allowBatching: false`，说明客户端链路和服务端入口之间对批处理能力有额外约束；根据当前片段推断，实际异步调用可能依赖特定 header 或服务端调用封装。

下游是 `src/server/routers/*`：

- `src/server/routers/lambda/index.ts` 聚合绝大多数 Web/桌面业务模块，例如 `agent`、`message`、`session`、`topic`、`file`、`document`、`market`、`user`，以及云业务的 `subscription`、`spend`、`topUp` 等。
- `src/server/routers/async/index.ts` 聚合 `document`、`file`、`image`、`ragEval`、`video`。
- `src/server/routers/mobile/index.ts` 从 lambda 业务中裁剪移动端需要的 router。
- `src/server/routers/tools/index.ts` 聚合工具生态相关 router。

更下游通常是 `src/server/services`、`src/server/modules`、数据库 model/repository、外部服务 SDK、对象存储、搜索服务、模型运行时等。`src/app/(backend)/trpc` 不直接访问数据库；数据库访问一般发生在 context/middleware 或具体业务 router/service 中。

## 运行/调用流程

一次典型的 `lambda` 请求流程如下：

1. 前端 service 调用 `lambdaClient.xxx.yyy.query()` 或 `.mutate()`。
2. `lambdaClient` 使用 `@trpc/client` 将 procedure path、输入参数、认证 header、cookie 等组装成 HTTP 请求，发往 `/trpc/lambda`。
3. Next.js App Router 命中 `src/app/(backend)/trpc/lambda/[trpc]/route.ts`。
4. `handler(req)` 调用 `prepareRequestForTRPC(req)`，通过 `req.clone()` 得到新的 `Request`，避免 body stream 被锁定。
5. `fetchRequestHandler` 开始处理请求，先调用 `createLambdaContext(req)`。
6. `createLambdaContext` 尝试解析用户身份：开发态 mock、API Key、OIDC、Better Auth session。它还收集 `clientIp`、`userAgent`、`marketAccessToken`、`traceContext`，并创建 `resHeaders`。
7. tRPC 根据 URL 中的 procedure path，从 `lambdaRouter` 找到对应子 router 和 procedure。
8. procedure 执行自己的输入校验、中间件、业务服务和数据库操作。
9. `createResponseMeta` 检查 context 中的 `resHeaders` 和 tRPC errors。如果出现 `UNAUTHORIZED`，会设置认证所需 header，方便桌面端代理区分“真实登录失效”和普通 401。
10. 响应返回前端，客户端 error link 可能进一步处理 401，例如触发登录跳转或 market auth 事件。

`tools` 和 `mobile` 流程与 `lambda` 基本一致，差异是 root router 不同。`async` 流程差异更明显：它使用 `createAsyncRouteContext`，要求请求携带加密后的 LobeChat 授权 header，解密得到 `userId`，并禁用 tRPC batching。

## 小白阅读顺序

建议先读 `src/app/(backend)/trpc/lambda/[trpc]/route.ts`。这是最典型、最容易理解的入口：一个 `handler`，一个 `fetchRequestHandler`，一个 `lambdaRouter`，一个 `createLambdaContext`。

第二步读 `src/libs/trpc/utils/request-adapter.ts`。这个文件很短，只做 `req.clone()`，但它解释了为什么每个 route 都要先准备 `preparedReq`。这是理解 Next.js 16 兼容处理的关键。

第三步读 `src/libs/trpc/utils/responseMeta.ts`。它能帮助你理解 tRPC 响应不只是 body，还会根据 context 和错误状态附加 header，尤其是桌面端认证相关 header。

第四步读 `src/libs/trpc/lambda/context.ts`。这里是 `lambda/mobile/tools` 三类入口共享的身份上下文创建逻辑。先抓住主线：开发态 mock -> API Key -> OIDC -> Better Auth session。不要一开始陷入每个认证工具函数的实现。

第五步读 `src/server/routers/lambda/index.ts`。不要逐个打开所有业务 router，只看它如何把很多业务模块聚合成 `lambdaRouter`。这一步能建立“URL procedure path 到业务模块”的映射感。

第六步再对比 `async/[trpc]/route.ts`、`mobile/[trpc]/route.ts`、`tools/[trpc]/route.ts`。重点看它们和 `lambda` 的差异：context 是否相同、router 是否裁剪、endpoint 是什么、错误处理有什么不同。

最后再读客户端：`src/libs/trpc/client/lambda.ts`、`src/libs/trpc/client/tools.ts`、`src/libs/trpc/client/async.ts`。读完你就能把“前端调用方法名”和“后端 route 文件”连起来。

## 常见误区

第一个误区是把 `src/app/(backend)/trpc` 当成业务 API 实现目录。实际上它只是 HTTP 适配层，真正的业务 procedure 在 `src/server/routers/*`，更深的业务逻辑通常在 `src/server/services`、数据库 model 或外部服务模块里。

第二个误区是认为四个入口只是路径不同。它们的职责边界不同：`lambda` 是主业务全集，`mobile` 是移动端裁剪集，`tools` 是工具生态入口，`async` 是异步任务入口，并且 `async` 的 context 和 batching 策略都不同。

第三个误区是忽略 `prepareRequestForTRPC(req)`。看起来只是 `req.clone()`，但注释说明这是为了解决 Next.js 16 中 body stream 可能被内部机制消费或锁定的问题。如果移除，POST mutation 在某些场景下可能出现 tRPC 读取 body 失败。

第四个误区是以为认证只在业务 procedure 里做。实际上 `createLambdaContext` 已经负责解析各种认证来源，并把 `userId`、`oidcAuth`、`marketAccessToken` 等放进 context。后续 `authedProcedure`、`userAuth`、`oidcAuth` 等中间件再基于 context 决定是否允许访问。

第五个误区是把 `UNAUTHORIZED` 都视为服务端异常。`lambda` 入口特意过滤了 `UNAUTHORIZED` 日志，因为登录失效是正常用户状态；客户端还会根据 401 做登出、跳转或 market auth 事件处理。

第六个误区是只看 Next.js route，不看客户端 URL。`lambdaClient`、`toolsClient`、`asyncClient` 分别指向 `/trpc/lambda`、`/trpc/tools`、`/trpc/async`，这决定了同名 procedure 应该落在哪个 root router 下面。调试“找不到 procedure”时，既要看后端 router 是否注册，也要看客户端用的是哪个 client。
