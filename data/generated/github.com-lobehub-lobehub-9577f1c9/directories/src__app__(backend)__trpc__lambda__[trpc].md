# 目录：src/app/(backend)/trpc/lambda/[trpc]

## 它负责什么

`src/app/(backend)/trpc/lambda/[trpc]` 是 LobeHub 后端 tRPC “lambda” 通道的 Next.js Route Handler 入口。目录里只有一个文件：

- `route.ts`

它把浏览器、桌面端或其他 HTTP 客户端发到 `/trpc/lambda/...` 的请求交给 `@trpc/server/adapters/fetch` 的 `fetchRequestHandler` 处理，再由 `lambdaRouter` 分发到具体业务 router。

可以把它理解成一个很薄的 HTTP 网关层：

1. 接收 Next.js App Router 的 `GET` / `POST` 请求。
2. 为 tRPC 准备可读取的 `Request`。
3. 创建本次请求的 `LambdaContext`，包含用户身份、请求来源、trace 信息、响应头容器等。
4. 指定 tRPC endpoint 为 `/trpc/lambda`。
5. 挂载总 router：`lambdaRouter`。
6. 统一处理 tRPC 错误日志和响应 metadata。

它本身不写业务逻辑，业务逻辑集中在 `src/server/routers/lambda/**` 和部分 `src/business/server/lambda-routers/**` 中。

## 关键组成

### `route.ts`

核心代码结构是：

```ts
const handler = (req: NextRequest) => {
  const preparedReq = prepareRequestForTRPC(req);

  return fetchRequestHandler({
    createContext: () => createLambdaContext(req),
    endpoint: '/trpc/lambda',
    onError: ({ error, path, type }) => { ... },
    req: preparedReq,
    responseMeta: createResponseMeta,
    router: lambdaRouter,
  });
};

export { handler as GET, handler as POST };
```

它导出两个 HTTP 方法：

- `GET`
- `POST`

这两个方法都复用同一个 `handler`，说明该入口同时支持 tRPC 的 query 请求和 mutation/batch 请求。实际 HTTP 方法如何被 tRPC 使用，由 `fetchRequestHandler` 和客户端 link 决定。

### `fetchRequestHandler`

来自：

```ts
import { fetchRequestHandler } from '@trpc/server/adapters/fetch';
```

这是 tRPC 在 Fetch API 环境里的 HTTP 适配器。Next.js Route Handler 的请求对象可以被转换成标准 `Request` 风格处理，因此这里用 fetch adapter，而不是 Express adapter 或 Node HTTP adapter。

它需要几个关键参数：

- `req`：当前 HTTP 请求。
- `router`：tRPC 总路由，这里是 `lambdaRouter`。
- `endpoint`：客户端访问的基础路径，这里固定为 `/trpc/lambda`。
- `createContext`：为每次请求生成上下文。
- `responseMeta`：把上下文或错误转成响应头等 metadata。
- `onError`：统一错误日志处理。

### `prepareRequestForTRPC`

来自：

```ts
import { prepareRequestForTRPC } from '@/libs/trpc/utils/request-adapter';
```

它的实现很简单：

```ts
export function prepareRequestForTRPC(req: NextRequest): Request {
  return req.clone();
}
```

代码注释说明这是为了解决 Next.js 16 下请求 body stream 可能已经被内部机制读取或锁定的问题。tRPC 需要读取请求体，如果直接使用原始 `NextRequest`，可能触发类似 “Response body object should not be disturbed or locked” 的错误。

所以这里先 `clone()`，给 tRPC 一个独立的 body stream。

### `createLambdaContext`

来自：

```ts
import { createLambdaContext } from '@/libs/trpc/lambda/context';
```

它负责把 HTTP 请求转换成 tRPC context。根据当前片段，它会收集和判断：

- `userAgent`
- `clientIp`
- `marketAccessToken`，来自 cookie `mp_token`
- `traceContext`，来自请求头里的 trace 信息
- `userId`
- `oidcAuth`
- `resHeaders`

认证路径大致是：

1. 开发环境下，如果请求带 `lobe-auth-dev-backend-api: 1` 或启用 `ENABLE_MOCK_DEV_USER`，直接使用 `MOCK_DEV_USER_ID`。
2. 如果存在 `X-API-Key`，先校验 API key 格式、数据库记录、启用状态和过期时间；成功则使用 API key 对应的 `userId`。
3. 如果启用 OIDC，尝试读取自定义 OIDC header，校验 JWT，并检查用户状态。
4. 最后尝试 Better Auth session。
5. 都失败时返回未登录上下文，`userId` 可能为 `undefined` 或 `null`。

这意味着 `route.ts` 不直接判断用户是否登录，只负责创建上下文。真正要求登录的接口会在 router procedure 层使用 `authedProcedure`、`userAuth` 等中间件拦截。

### `createResponseMeta`

来自：

```ts
import { createResponseMeta } from '@/libs/trpc/utils/responseMeta';
```

它负责给 tRPC 响应补充 header。当前实现有两个重点：

1. 如果 context 里有 `resHeaders`，会转发到最终响应。
2. 如果 tRPC 错误里有 `UNAUTHORIZED`，会设置桌面端需要识别的认证 header：

```ts
headers.set(AUTH_REQUIRED_HEADER, 'true');
```

这让桌面端的后端代理逻辑可以区分“确实需要登录”的 401 和其他类型的 401，例如无效 API key。

### `lambdaRouter`

来自：

```ts
import { lambdaRouter } from '@/server/routers/lambda';
```

这是 `/trpc/lambda` 下的总业务路由，定义在：

```ts
src/server/routers/lambda/index.ts
```

它通过：

```ts
export const lambdaRouter = router({
  agent: agentRouter,
  aiChat: aiChatRouter,
  config: configRouter,
  message: messageRouter,
  session: sessionRouter,
  user: userRouter,
  ...
});
```

把大量业务模块挂到 tRPC namespace 下。比如：

- `user.getUserState`
- `config.getGlobalConfig`
- `message.*`
- `session.*`
- `market.*`
- `knowledgeBase.*`
- `aiProvider.*`
- `plugin.*`
- `upload.*`

这些路径最终都会通过当前目录的 `route.ts` 入口进入。

`lambdaRouter` 还导出类型：

```ts
export type LambdaRouter = typeof lambdaRouter;
```

客户端用这个类型生成类型安全的 tRPC client。

### `@/libs/trpc/lambda`

相关初始化在：

```ts
src/libs/trpc/lambda/init.ts
src/libs/trpc/lambda/index.ts
```

`init.ts` 使用：

```ts
initTRPC.context<LambdaContext>().create({
  transformer: superjson,
  errorFormatter(...)
})
```

重点有两个：

- `context<LambdaContext>()`：规定所有 lambda tRPC procedure 都能拿到统一的 `LambdaContext`。
- `transformer: superjson`：让 Date、Map 等非普通 JSON 数据可以在 tRPC 中可靠序列化。

`index.ts` 暴露了常用构造器：

- `router`
- `publicProcedure`
- `authedProcedure`
- `heteroAuthedProcedure`
- `createCallerFactory`

其中：

```ts
const baseProcedure = trpc.procedure.use(openTelemetry);
export const publicProcedure = baseProcedure;
export const authedProcedure = baseProcedure.use(oidcAuth).use(userAuth);
```

说明每个 lambda procedure 默认都会走 OpenTelemetry 中间件；需要登录的接口再叠加 OIDC 和用户认证中间件。

## 上下游关系

### 上游：客户端 tRPC 调用

主要客户端入口是：

```ts
src/libs/trpc/client/lambda.ts
```

它创建：

```ts
export const lambdaClient = createTRPCClient<LambdaRouter>({ links });
export const lambdaQuery = createTRPCReact<LambdaRouter>();
export const lambdaQueryClient = lambdaQuery.createClient({ links });
```

客户端 URL 是：

```ts
url: withElectronProtocolIfElectron('/trpc/lambda')
```

也就是说，Web 环境会请求 `/trpc/lambda`；桌面环境可能通过 Electron 自定义协议转换请求地址。

客户端还配置了：

- `httpBatchLink`
- `httpLink`
- `splitLink`
- `superjson`
- `credentials: 'include'`
- 动态 auth headers
- 401 错误处理

其中部分初始加载接口会跳过 batch：

```ts
const initialLoadProcedures = new Set(['user.getUserState', 'config.getGlobalConfig']);
```

根据当前片段推断，像 `user.getUserState`、`config.getGlobalConfig` 这类首屏关键接口会单独请求，以降低初始加载延迟；普通接口则可以 batch 到同一个 tRPC HTTP 请求里。

### 当前入口：Next.js Route Handler

当前目录对应 App Router 路径：

```txt
src/app/(backend)/trpc/lambda/[trpc]/route.ts
```

其中 `(backend)` 是 Next.js route group，不会出现在 URL 中；`[trpc]` 是动态段，用于承接 tRPC procedure 路径。因此实际 URL 形态是：

```txt
/trpc/lambda/某个.tRPC.path
```

例如根据客户端路径推断，可能出现：

```txt
/trpc/lambda/user.getUserState
/trpc/lambda/config.getGlobalConfig
/trpc/lambda/message.someProcedure
```

如果是 batch 请求，tRPC 还会在查询参数或请求体中携带多个 operation。

### 下游：业务 router

`route.ts` 下游直接连接：

```ts
lambdaRouter
```

而 `lambdaRouter` 再连接大量领域 router，例如：

- `agentRouter`
- `aiChatRouter`
- `configRouter`
- `fileRouter`
- `knowledgeRouter`
- `marketRouter`
- `messageRouter`
- `sessionRouter`
- `topicRouter`
- `uploadRouter`
- `userRouter`
- `subscriptionRouter`
- `topUpRouter`

这些业务 router 通常会继续调用：

- database model
- server service
- external API SDK
- auth middleware
- observability middleware
- business package 下的 router

当前入口并不知道这些业务细节，它只负责把请求送进统一 tRPC 管道。

### 相邻入口

同级目录还有：

```txt
src/app/(backend)/trpc/async/[trpc]/route.ts
src/app/(backend)/trpc/mobile/[trpc]/route.ts
src/app/(backend)/trpc/tools/[trpc]/route.ts
```

这说明项目不只有一个 tRPC 通道，而是按场景拆分：

- `lambda`：主业务后端 tRPC。
- `mobile`：移动端相关 tRPC。
- `async`：异步任务或异步路由相关 tRPC。
- `tools`：工具调用相关 tRPC。

当前目录只负责 `lambda` 通道，不要把所有 tRPC 请求都归到这里。

## 运行/调用流程

一个典型调用流程如下：

1. 前端代码通过 `lambdaClient`、`lambdaQuery` 或 `lambdaQueryClient` 调用某个 procedure。
2. `src/libs/trpc/client/lambda.ts` 根据 procedure 名称决定使用 `httpLink` 还是 `httpBatchLink`。
3. 请求发往 `/trpc/lambda`，并携带 cookie、认证 header、可能的 provider 信息等。
4. Next.js 根据 App Router 文件结构命中：

   ```txt
   src/app/(backend)/trpc/lambda/[trpc]/route.ts
   ```

5. `GET` 或 `POST` 调用同一个 `handler(req)`。
6. `handler` 先执行：

   ```ts
   const preparedReq = prepareRequestForTRPC(req);
   ```

   也就是克隆请求，避免 Next.js 16 body stream 被锁定的问题。

7. `handler` 调用 `fetchRequestHandler`。
8. tRPC 在处理请求前调用：

   ```ts
   createContext: () => createLambdaContext(req)
   ```

9. `createLambdaContext` 从请求中解析 IP、UA、cookie、trace header，并按 API key、OIDC、Better Auth 等顺序尝试得到 `userId`。
10. tRPC 根据 URL path 和 body 找到 `lambdaRouter` 下对应 procedure。
11. procedure 执行自己的 middleware，例如 `openTelemetry`、`oidcAuth`、`userAuth`、`serverDatabase` 等。
12. 业务 router 调用 server service、database model 或外部服务。
13. 如果成功，tRPC 使用 `superjson` 序列化结果返回。
14. 如果失败，`onError` 处理日志：

    - `UNAUTHORIZED` 不打印，因为这是正常的未登录状态，前端会展示登录提示。
    - 其他错误打印 path、type 和错误详情。

15. `createResponseMeta` 根据 context 和错误补充响应头，例如认证失败时设置 `AUTH_REQUIRED_HEADER`。
16. 客户端收到响应后，`errorHandlingLink` 根据状态码处理 UI 行为；非 market 的 401 可能触发 logout 和登录提示，market 的 401 会发出 market auth 事件。

## 小白阅读顺序

1. 先读当前目录的入口：

   ```txt
   src/app/(backend)/trpc/lambda/[trpc]/route.ts
   ```

   目标是理解：这个文件只做“HTTP 请求进入 tRPC”的适配，不做具体业务。

2. 再读请求克隆逻辑：

   ```txt
   src/libs/trpc/utils/request-adapter.ts
   ```

   这里解释了为什么 Next.js 16 下要 `req.clone()`。

3. 接着读 context 创建：

   ```txt
   src/libs/trpc/lambda/context.ts
   ```

   重点看 `createLambdaContext`，理解用户身份是怎么进入 tRPC context 的。

4. 然后读 tRPC 初始化：

   ```txt
   src/libs/trpc/lambda/init.ts
   src/libs/trpc/lambda/index.ts
   ```

   重点理解 `router`、`publicProcedure`、`authedProcedure` 的区别。

5. 再读总 router：

   ```txt
   src/server/routers/lambda/index.ts
   ```

   不需要一开始就点进每个业务 router。先看它挂了哪些 namespace，比如 `user`、`message`、`session`、`market`。

6. 最后读客户端：

   ```txt
   src/libs/trpc/client/lambda.ts
   ```

   重点看请求发到哪里、是否 batch、如何带认证头、401 如何处理。

读完这几处，就能建立完整链路：客户端 typed procedure 调用 -> `/trpc/lambda` HTTP 请求 -> Next.js route handler -> tRPC context -> `lambdaRouter` -> 业务 procedure -> 响应 metadata -> 客户端错误处理。

## 常见误区

1. **误以为 `[trpc]` 文件夹里会有很多业务代码**

   这里其实只有 `route.ts`。业务不在这个目录里，而在 `src/server/routers/lambda/**` 和 `src/business/server/lambda-routers/**`。

2. **误以为 `route.ts` 负责鉴权判断**

   `route.ts` 只调用 `createLambdaContext` 构造上下文。是否允许访问由具体 procedure 决定。使用 `publicProcedure` 的接口可以未登录访问；使用 `authedProcedure` 的接口会走认证中间件。

3. **误删 `prepareRequestForTRPC(req)`**

   这个克隆请求的步骤看起来多余，但它是为了解决 Next.js 16 请求体 stream 被消费或锁定的问题。直接把原始 `NextRequest` 交给 tRPC，可能在 POST 或 batch 请求中出错。

4. **误以为所有 401 都会打印后端错误日志**

   `onError` 明确过滤了 `UNAUTHORIZED`：

   ```ts
   if (error.code === 'UNAUTHORIZED') return;
   ```

   未登录是正常业务状态，前端会处理登录提示。后端只对其他错误打印日志。

5. **误以为 `/trpc/lambda` 只服务 Web**

   客户端使用 `withElectronProtocolIfElectron('/trpc/lambda')`，说明桌面端也会走这个通道，只是请求协议可能被 Electron 包装。

6. **误以为 `lambdaRouter` 只包含 server/routers/lambda 下的文件**

   `lambdaRouter` 还引入了 `src/business/server/lambda-routers/**` 下的业务 router，例如 `subscriptionRouter`、`topUpRouter`、`referralRouter` 等。阅读总 router 时要注意 import 来源。

7. **误以为 context 里一定有 `userId`**

   `createLambdaContext` 支持未登录请求。`userId` 可能是有效字符串，也可能是 `undefined` 或 `null`。业务代码如果需要用户身份，应使用 `authedProcedure` 或相关 middleware，而不是直接假设 `ctx.userId` 一定存在。

8. **误以为客户端所有请求都会 batch**

   `src/libs/trpc/client/lambda.ts` 使用 `splitLink`，部分首屏或慢接口会跳过 batch，例如 `user.getUserState`、`config.getGlobalConfig`、`market.getAssistantList`。所以排查网络请求时，看到有些接口单独发请求是正常现象。

9. **误以为 `responseMeta` 只是普通 header 转发**

   它还会在 tRPC 发生 `UNAUTHORIZED` 时设置桌面端识别用的认证 header。这影响桌面端后端代理和登录状态处理，不能只按 Web 行为理解。

10. **误以为新增 lambda API 需要改当前目录**

   通常不需要。新增业务接口一般是在 `src/server/routers/lambda/**` 中新增或修改 router，并在 `src/server/routers/lambda/index.ts` 挂载。当前 `route.ts` 只有在 tRPC HTTP 网关行为变化时才需要改。
