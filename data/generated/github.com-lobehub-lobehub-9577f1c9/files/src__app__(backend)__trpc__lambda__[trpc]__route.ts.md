# 文件：src/app/(backend)/trpc/lambda/[trpc]/route.ts

## 它负责什么

这个文件是 LobeHub 后端 tRPC “lambda” 通道的 Next.js Route Handler 入口。

它把来自 Next.js App Router 的 HTTP 请求接入 `@trpc/server/adapters/fetch`，并交给 `lambdaRouter` 里的各个业务 router 处理。换句话说，前端或客户端访问类似 `/trpc/lambda/...` 的接口时，最终会先进入这里，然后由 tRPC 根据路径分发到 `src/server/routers/lambda/index.ts` 中注册的具体过程。

它本身不写业务逻辑，也不直接查询数据库。它主要做四件事：

1. 接收 `GET` 和 `POST` 请求。
2. 准备一个可被 tRPC 安全读取的 `Request`。
3. 为每次请求创建 tRPC context，也就是认证、用户、headers、trace 等上下文。
4. 配置错误日志、响应元信息和根 router。

## 关键组成

### `fetchRequestHandler`

```ts
import { fetchRequestHandler } from '@trpc/server/adapters/fetch';
```

这是 tRPC 提供的 Fetch API 适配器。Next.js Route Handler 使用的是 Web `Request` / `Response` 模型，所以这里选择 `fetchRequestHandler`，而不是 Node HTTP 适配器。

它接收一个配置对象，核心字段包括：

- `req`：当前请求对象。
- `router`：tRPC 根 router。
- `endpoint`：当前 tRPC endpoint。
- `createContext`：为每次请求创建上下文。
- `responseMeta`：定制响应 headers。
- `onError`：统一错误处理。

### `NextRequest`

```ts
import { type NextRequest } from 'next/server';
```

`handler` 的入参类型是 `NextRequest`。它是 Next.js 对标准 Web Request 的扩展，提供 cookies、nextUrl 等 Next.js 能力。当前文件里主要把它作为请求对象传给上下文创建函数和请求适配函数。

### `prepareRequestForTRPC`

```ts
const preparedReq = prepareRequestForTRPC(req);
```

它来自：

```ts
@/libs/trpc/utils/request-adapter
```

该函数目前的核心逻辑是：

```ts
return req.clone();
```

这里的注释很关键：Next.js 16 中，请求 body stream 可能被 Next.js 内部机制读取或锁定，导致 tRPC 再读 body 时出现类似：

```text
Response body object should not be disturbed or locked
```

所以这里先 clone 一份请求，让 tRPC 使用独立的 body stream。

这说明 `route.ts` 不直接把原始 `req` 给 tRPC，而是使用 `preparedReq`：

```ts
req: preparedReq,
```

但创建 context 时仍然使用原始 `req`：

```ts
createContext: () => createLambdaContext(req),
```

这是因为 context 主要读 headers、cookie、IP、认证信息等，不一定需要消费 body。

### `createLambdaContext`

```ts
import { createLambdaContext } from '@/libs/trpc/lambda/context';
```

这是 lambda tRPC 请求的上下文创建函数。根据已读到的代码，它会从请求中提取并构造这些信息：

- `userId`
- `clientIp`
- `userAgent`
- `marketAccessToken`
- `traceContext`
- `oidcAuth`
- `resHeaders`

它支持多种认证来源：

- 开发环境调试 header：`lobe-auth-dev-backend-api`
- mock 开发用户：`ENABLE_MOCK_DEV_USER`
- API Key header：`X-API-Key`
- OIDC header：`LOBE_CHAT_OIDC_AUTH_HEADER`
- 根据当前片段推断，后续还可能继续处理普通登录态或 NextAuth 会话，因为文件导入了 `auth`，但当前阅读片段未覆盖函数后半段。

`createLambdaContext` 返回的 context 会传给所有 lambda router procedure。业务 procedure 可以通过 context 判断当前用户、读取 token、设置响应 header，或者关联链路追踪上下文。

### `createResponseMeta`

```ts
import { createResponseMeta } from '@/libs/trpc/utils/responseMeta';
```

它用于给 tRPC 响应补充 metadata，尤其是 headers。

根据相邻文件，它做两件事：

1. 如果 context 里有 `resHeaders`，就把这些 headers 合并到响应中。
2. 如果 tRPC 错误里存在 `UNAUTHORIZED`，就设置桌面端识别用的认证 header：

```ts
AUTH_REQUIRED_HEADER: true
```

这让桌面端的 `BackendProxyProtocolManager` 能区分“真的需要重新登录”和其他类型的 401 错误。

### `lambdaRouter`

```ts
import { lambdaRouter } from '@/server/routers/lambda';
```

这是 tRPC lambda 通道的根 router。它在 `src/server/routers/lambda/index.ts` 中聚合了大量业务 router，例如：

- `agent`
- `aiChat`
- `aiModel`
- `apiKey`
- `config`
- `file`
- `knowledge`
- `message`
- `plugin`
- `session`
- `topic`
- `user`
- `usage`
- `upload`
- `subscription`
- `topUp`

还包含一个简单的公开健康检查：

```ts
healthcheck: publicProcedure.query(() => "i'm live!")
```

因此，`route.ts` 是 HTTP 层入口，`lambdaRouter` 是业务过程注册表。

### `handler`

```ts
const handler = (req: NextRequest) => {
  const preparedReq = prepareRequestForTRPC(req);

  return fetchRequestHandler({
    createContext: () => createLambdaContext(req),
    endpoint: '/trpc/lambda',
    onError: ({ error, path, type }) => {
      if (error.code === 'UNAUTHORIZED') return;

      console.info(`Error in tRPC handler (lambda) on path: ${path}, type: ${type}`);
      console.error(error);
    },
    req: preparedReq,
    responseMeta: createResponseMeta,
    router: lambdaRouter,
  });
};
```

这是整个文件的主体。

它没有使用 `async`，因为 `fetchRequestHandler` 本身会处理异步流程，并返回 `Response` 或 `Promise<Response>`。

### `GET` / `POST` 导出

```ts
export { handler as GET, handler as POST };
```

Next.js App Router 通过命名导出识别 HTTP method handler。这里把同一个 `handler` 同时导出为 `GET` 和 `POST`。

这符合 tRPC 的使用方式：

- `query` 类请求可能通过 `GET` 调用。
- `mutation` 或批量请求通常通过 `POST` 调用。

## 上下游关系

### 上游：Next.js 路由系统和 HTTP 客户端

这个文件位于：

```text
src/app/(backend)/trpc/lambda/[trpc]/route.ts
```

在 Next.js App Router 中，`route.ts` 表示一个 Route Handler。路径里的 `[trpc]` 是动态段，用于承接 tRPC 的 procedure 路径。

根据当前文件的 `endpoint: '/trpc/lambda'` 可以看出，这个入口服务的是 `/trpc/lambda` 这一组 tRPC API。

上游可能包括：

- Web SPA 前端中的 tRPC client。
- Electron 桌面端代理到后端的请求。
- 其他服务端或客户端调用 LobeHub API。
- 使用 `X-API-Key` 的 API 调用方。
- 使用 OIDC header 的集成调用方。

“具体由哪个前端文件调用”当前没有继续查调用方，因此这里属于根据路径和 tRPC 结构推断。

### 当前层：HTTP 到 tRPC 的适配层

`route.ts` 位于 Next.js HTTP 层和 tRPC 业务 router 之间。它不关心具体业务，只负责把请求包装成 tRPC 能理解的格式。

它连接了四类基础设施：

- Next.js route handler：`GET` / `POST`
- tRPC fetch adapter：`fetchRequestHandler`
- 请求上下文：`createLambdaContext`
- 根业务 router：`lambdaRouter`

### 下游：`lambdaRouter`

请求进入 `fetchRequestHandler` 后，会根据 tRPC path 分发到 `lambdaRouter` 中的具体 router。

例如，根据 `src/server/routers/lambda/index.ts` 的注册结构，路径大致会映射到：

```text
/trpc/lambda/user.xxx
/trpc/lambda/session.xxx
/trpc/lambda/message.xxx
/trpc/lambda/file.xxx
/trpc/lambda/knowledge.xxx
/trpc/lambda/aiChat.xxx
```

具体 path 格式由 tRPC client 和服务端 router 命名共同决定。

### 下游：认证、数据库、OIDC、API Key

`route.ts` 本身不直接认证，但它调用的 `createLambdaContext` 会接触这些模块：

- `@/auth`
- `@/database/core/db-adaptor`
- `@/database/models/apiKey`
- `@/envs/auth`
- `@/libs/oidc-provider/access-control`
- `@/libs/oidc-provider/jwt`
- `@/utils/apiKey`
- `@/libs/observability/traceparent`

这意味着一次 tRPC 请求在真正进入业务 router 前，可能已经完成：

- API Key 校验。
- OIDC JWT 校验。
- 用户是否被禁用或删除的检查。
- `mp_token` cookie 读取。
- `traceparent` 链路上下文提取。
- 客户端 IP 和 User-Agent 提取。

## 运行/调用流程

1. 客户端发起请求到 `/trpc/lambda/...`。

2. Next.js 根据文件路径匹配到：

```text
src/app/(backend)/trpc/lambda/[trpc]/route.ts
```

3. 如果是 `GET` 请求，执行：

```ts
GET(req)
```

如果是 `POST` 请求，执行：

```ts
POST(req)
```

两者实际都是同一个 `handler`。

4. `handler` 先调用：

```ts
prepareRequestForTRPC(req)
```

得到 `preparedReq`。这一步通过 `req.clone()` 规避 Next.js 16 中 body stream 被提前消费或锁定的问题。

5. `handler` 调用：

```ts
fetchRequestHandler({...})
```

并传入 tRPC 所需配置。

6. tRPC 在处理请求前调用：

```ts
createContext: () => createLambdaContext(req)
```

生成 `LambdaContext`。

这一步会读取请求 headers、cookie、IP、User-Agent、API Key、OIDC token、trace context 等信息。

7. tRPC 根据请求 path 在 `lambdaRouter` 中找到对应 procedure。

例如根据当前 router 注册结构，可能进入：

```ts
lambdaRouter.user
lambdaRouter.message
lambdaRouter.file
lambdaRouter.knowledge
lambdaRouter.aiChat
```

8. 具体 procedure 执行业务逻辑。它可以读取 context，例如：

```ts
ctx.userId
ctx.clientIp
ctx.marketAccessToken
ctx.resHeaders
```

9. 如果 procedure 正常返回，tRPC 生成响应。

10. 如果 procedure 抛错，进入 `onError`。

这里有一个特殊处理：

```ts
if (error.code === 'UNAUTHORIZED') return;
```

`UNAUTHORIZED` 不打印错误日志，因为这是正常业务状态，前端会提示用户登录。其他错误会输出：

```ts
console.info(...)
console.error(error)
```

11. 响应返回前，tRPC 调用：

```ts
responseMeta: createResponseMeta
```

它可能把 context 中的 headers 带到响应上，也可能在认证失败时加上桌面端识别用的 `AUTH_REQUIRED_HEADER`。

12. 最终返回标准 `Response` 给 Next.js，再由 Next.js 返回给客户端。

## 小白阅读顺序

1. 先看文件底部：

```ts
export { handler as GET, handler as POST };
```

理解这是 Next.js Route Handler，负责处理 HTTP `GET` 和 `POST`。

2. 再看 `handler` 函数整体结构。

重点不是每个配置项的细节，而是先记住：

```ts
NextRequest -> prepareRequestForTRPC -> fetchRequestHandler -> lambdaRouter
```

3. 接着看：

```ts
router: lambdaRouter
```

打开：

```text
src/server/routers/lambda/index.ts
```

理解这个 endpoint 背后挂了很多业务 router。`route.ts` 只是入口，真正业务在这些 router 里。

4. 然后看：

```ts
createContext: () => createLambdaContext(req)
```

打开：

```text
src/libs/trpc/lambda/context.ts
```

重点看它往 context 里塞了什么：

- 用户身份
- API Key 身份
- OIDC 信息
- IP
- User-Agent
- cookie token
- trace context
- response headers

小白要特别注意：tRPC procedure 里常见的 `ctx.userId`，来源就在这里。

5. 再看：

```ts
prepareRequestForTRPC(req)
```

打开：

```text
src/libs/trpc/utils/request-adapter.ts
```

理解为什么要 clone request。这里和业务无关，是 Next.js 16 + stream 读取机制相关的兼容处理。

6. 最后看：

```ts
responseMeta: createResponseMeta
```

打开：

```text
src/libs/trpc/utils/responseMeta.ts
```

理解响应 header 是如何被统一附加的，尤其是认证失败时给桌面端看的 `AUTH_REQUIRED_HEADER`。

## 常见误区

### 误区一：以为这个文件里有业务逻辑

这个文件没有具体业务逻辑。它不会处理聊天、文件、知识库、用户设置等业务。它只是 tRPC lambda endpoint 的 HTTP 入口。

真正业务在：

```text
src/server/routers/lambda/
```

以及被它导入的各个 router 中。

### 误区二：以为 `[trpc]` 动态段就是某个单独参数

在普通 Next.js 页面里，`[id]` 常常表示一个明确的路由参数。但 tRPC endpoint 中，动态段更多是为了让 Next.js 把 tRPC 的 procedure path 转交给 tRPC adapter。

也就是说，路径解析的主要工作不是这个文件自己做，而是交给：

```ts
fetchRequestHandler
```

### 误区三：以为 `req` 和 `preparedReq` 没区别

这里有两个请求对象：

```ts
const preparedReq = prepareRequestForTRPC(req);
```

`tRPC` 实际读取的是：

```ts
req: preparedReq
```

但 context 创建使用的是：

```ts
createLambdaContext(req)
```

这不是随意写法。`preparedReq` 是 clone 出来的请求，用于让 tRPC 安全读取 body；原始 `req` 用来读取 headers、cookie 等上下文信息。

### 误区四：以为 `UNAUTHORIZED` 不算错误

`UNAUTHORIZED` 当然是 tRPC 错误，但这里不打印日志：

```ts
if (error.code === 'UNAUTHORIZED') return;
```

原因是未登录或登录过期是正常用户状态，不应该污染服务端错误日志。前端或桌面端会根据响应自行处理登录提示。

同时，`createResponseMeta` 仍可能为 `UNAUTHORIZED` 添加认证相关 header，所以“不打印日志”不等于“不处理”。

### 误区五：以为所有认证都在业务 router 里做

认证信息的提取主要发生在 `createLambdaContext`。业务 router 通常通过 context 使用认证结果，比如读取 `ctx.userId`，或者依赖 protected procedure 判断是否登录。

因此排查认证问题时，不应该只看某个业务 router，也要看：

```text
src/libs/trpc/lambda/context.ts
```

### 误区六：以为 `endpoint: '/trpc/lambda'` 是随便写的

这个 endpoint 要和客户端 tRPC 配置、Next.js 路由路径保持一致。它告诉 tRPC 当前 API 的基础路径是什么。

如果路径、客户端配置和文件系统路由不一致，可能出现请求打不到对应 handler、procedure path 解析错误、或客户端调用 404 等问题。

### 误区七：把 `responseMeta` 当成普通业务返回值

`responseMeta` 不是 procedure 的返回数据。它控制的是 HTTP 响应层面的 metadata，尤其是 headers。

比如 context 中的 `resHeaders` 可以通过这里带到最终响应；认证错误时的特殊 header 也在这里统一设置。

### 误区八：忽略这个文件对桌面端的影响

虽然路径在 `src/app/(backend)` 下，看起来像 Web 后端入口，但 `createResponseMeta` 明确引用了：

```ts
@lobechat/desktop-bridge
```

这说明该 tRPC endpoint 的响应行为也服务于桌面端场景。特别是认证失败 header，可能会影响 Electron 端如何判断登录状态。
