# 目录：src/app/(backend)/trpc/lambda

## 它负责什么

`src/app/(backend)/trpc/lambda` 是 LobeHub 后端 tRPC Lambda API 的 Next.js App Router 入口目录。它本身不承载具体业务逻辑，而是把来自 HTTP 的 `GET` / `POST` 请求接入 tRPC，并交给 `src/server/routers/lambda/index.ts` 聚合出来的 `lambdaRouter` 执行业务 procedure。

这个目录当前只有一个实际文件：

```txt
src/app/(backend)/trpc/lambda/
└── [trpc]/
    └── route.ts
```

`[trpc]` 是 Next.js 动态路由段，用来匹配 `/trpc/lambda/*` 形式的 tRPC 调用路径。比如前端调用某个 tRPC procedure 时，请求会进入这个 route handler，再由 tRPC 根据 path 分发到 `lambdaRouter` 中的具体子 router，例如 `message.*`、`session.*`、`aiChat.*`、`config.*` 等。

可以把它理解成一层“HTTP 到 tRPC 的网关”：

```txt
HTTP Request
  -> Next.js route.ts
  -> @trpc/server/adapters/fetch
  -> createLambdaContext
  -> lambdaRouter
  -> 具体业务 router / procedure
  -> HTTP Response
```

## 关键组成

### `[trpc]/route.ts`

核心文件是 `src/app/(backend)/trpc/lambda/[trpc]/route.ts`。它导入了几类关键依赖：

```ts
import { fetchRequestHandler } from '@trpc/server/adapters/fetch';
import { type NextRequest } from 'next/server';

import { createLambdaContext } from '@/libs/trpc/lambda/context';
import { prepareRequestForTRPC } from '@/libs/trpc/utils/request-adapter';
import { createResponseMeta } from '@/libs/trpc/utils/responseMeta';
import { lambdaRouter } from '@/server/routers/lambda';
```

这些 import 分别对应不同职责：

`fetchRequestHandler`  
来自 `@trpc/server/adapters/fetch`，是 tRPC 对 Fetch API / Next.js route handler 的适配器。它负责读取请求、解析 tRPC path/input、执行 router procedure，并生成响应。

`NextRequest`  
Next.js App Router 的请求类型。这里的 handler 接收 `NextRequest`，说明该文件是标准 Next.js 后端 route handler。

`createLambdaContext`  
来自 `src/libs/trpc/lambda/context.ts`。它为每次请求创建 tRPC `ctx`，包括 `userId`、`clientIp`、`userAgent`、`marketAccessToken`、`traceContext`、`oidcAuth`、`resHeaders` 等信息。后续业务 procedure 会通过 `ctx` 判断登录态、访问数据库、做鉴权或记录链路信息。

`prepareRequestForTRPC`  
用于把原始 `NextRequest` 转换成适合 tRPC 消费的请求。代码注释提到它是为了规避 Next.js 16 中 body stream 被内部机制消费后出现 `"Response body object should not be disturbed or locked"` 的问题。也就是说，这里不是简单把 `req` 原样传给 tRPC，而是先做一层请求体安全适配。

`createResponseMeta`  
用于配置 tRPC 响应元信息。根据命名推断，它可能统一设置响应 header、缓存策略或从 `ctx.resHeaders` 取出需要返回给客户端的 header。当前片段只看到它被传给 `responseMeta`，具体行为需要查看 `src/libs/trpc/utils/responseMeta` 才能完全确认。

`lambdaRouter`  
来自 `src/server/routers/lambda/index.ts`，是所有 Lambda tRPC 业务 router 的总入口。`route.ts` 不知道每个业务 procedure 的细节，只把请求交给这个总 router。

### `handler`

`route.ts` 中只有一个主要函数：

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
```

它做了五件事：

1. 接收 Next.js 的 `NextRequest`。
2. 调用 `prepareRequestForTRPC(req)`，生成给 tRPC 使用的请求对象。
3. 使用 `fetchRequestHandler` 启动 tRPC 请求处理。
4. 为本次请求绑定 `createLambdaContext(req)`。
5. 把所有 procedure 分发交给 `lambdaRouter`。

最后文件导出：

```ts
export { handler as GET, handler as POST };
```

这表示同一套 tRPC handler 同时支持 `GET` 和 `POST`。tRPC 通常会用 `GET` 承载 query，也会用 `POST` 承载 mutation 或批量请求，具体取决于客户端调用方式和 tRPC 配置。

### `lambdaRouter`

`src/server/routers/lambda/index.ts` 是这个目录最重要的下游。它通过：

```ts
export const lambdaRouter = router({
  agent: agentRouter,
  aiChat: aiChatRouter,
  message: messageRouter,
  session: sessionRouter,
  user: userRouter,
  healthcheck: publicProcedure.query(() => "i'm live!"),
  ...
});
```

聚合了大量业务 router。

例如：

```txt
lambdaRouter.message       -> src/server/routers/lambda/message.ts
lambdaRouter.session       -> src/server/routers/lambda/session.ts
lambdaRouter.config        -> src/server/routers/lambda/config/index.ts
lambdaRouter.aiAgent       -> src/server/routers/lambda/aiAgent.ts
lambdaRouter.market        -> src/server/routers/lambda/market/index.ts
```

因此，请求 path 与 router key 是对应的。根据当前片段推断，请求 `message.someProcedure` 会先进入 `/trpc/lambda/[trpc]/route.ts`，再由 `lambdaRouter.message` 分发到 `messageRouter` 中的 `someProcedure`。

### `src/libs/trpc/lambda/index.ts`

这个文件定义了业务 router 编写时使用的基础构件：

```ts
export const router = trpc.router;
export const publicProcedure = baseProcedure;
export const authedProcedure = baseProcedure.use(oidcAuth).use(userAuth);
export const heteroAuthedProcedure = baseProcedure.use(heteroOperationAuth).use(userAuth);
export const createCallerFactory = trpc.createCallerFactory;
```

关键点是：

`publicProcedure`  
公开 procedure，不强制用户登录，但仍会经过 `openTelemetry` 中间件。

`authedProcedure`  
需要登录态的 procedure。它会经过 `oidcAuth` 和 `userAuth`，也就是先处理 OIDC 相关鉴权，再确认用户身份。

`heteroAuthedProcedure`  
用于 heterogeneous agent 相关的 ingest / finish 场景，需要 `hetero-operation` JWT，再进入 `userAuth`。

这说明 `route.ts` 只负责接入，真正的“这个 API 是否需要登录”不是在 route 层判断，而是在具体 router 的 procedure 层通过 `publicProcedure` / `authedProcedure` / `heteroAuthedProcedure` 决定。

### `src/libs/trpc/lambda/init.ts`

这里初始化 tRPC：

```ts
export const trpc = initTRPC.context<LambdaContext>().create({
  errorFormatter(...) { ... },
  transformer: superjson,
});
```

它做了两件重要事情：

`context<LambdaContext>()`  
声明所有 Lambda tRPC procedure 的 `ctx` 类型都来自 `LambdaContext`。这就是为什么业务 router 中可以类型安全地访问 `ctx.userId`、`ctx.resHeaders` 等字段。

`transformer: superjson`  
使用 `superjson` 作为序列化器。它比普通 JSON 更适合传输 `Date`、`Map` 等复杂数据类型。前后端都理解这个 transformer 时，数据类型可以更自然地往返。

`errorFormatter`  
如果 `error.cause` 中带有 `data` 字段，就把它追加到响应的 `shape.data.errorData`。这为业务错误提供了额外结构化信息通道。

### `src/libs/trpc/lambda/context.ts`

`createLambdaContext(request)` 是上下文创建核心。它会按顺序处理多种身份来源：

1. 开发环境 debug / mock user。
2. 请求基础信息：`user-agent`、客户端 IP、cookie 中的 `mp_token`、trace context。
3. `X-API-Key` 鉴权。
4. OIDC 鉴权。
5. Better Auth session 鉴权。
6. 如果都失败，返回没有有效 `userId` 的 context。

最终返回的 context 类型大致包括：

```ts
interface AuthContext {
  clientIp?: string | null;
  jwtPayload?: ClientSecretPayload | null;
  marketAccessToken?: string;
  oidcAuth?: OIDCAuth | null;
  resHeaders?: Headers;
  traceContext?: OtContext;
  userAgent?: string;
  userId?: string | null;
}
```

注意，`createLambdaContext` 本身通常不会直接抛出“未登录”错误。它更像是尽力解析身份，把结果放进 `ctx.userId`。真正是否允许继续访问，由后续 middleware / procedure 决定，例如 `userAuth`。

## 上下游关系

### 上游：谁会调用这个目录

上游主要是 HTTP 客户端和前端 tRPC client。

典型来源包括：

```txt
浏览器 SPA
桌面端渲染进程
移动端入口
CLI 或其他内部调用方
第三方/自动化客户端，若使用 X-API-Key
```

它们最终会请求：

```txt
/trpc/lambda
/trpc/lambda/<procedure path>
```

具体 URL 形态由 tRPC client 生成。这个目录只关心入口 endpoint 是：

```ts
endpoint: '/trpc/lambda'
```

### 下游：它把请求交给谁

第一层下游是 tRPC fetch adapter：

```ts
fetchRequestHandler(...)
```

第二层下游是上下文创建：

```ts
createLambdaContext(req)
```

第三层下游是业务总 router：

```ts
lambdaRouter
```

第四层下游才是具体业务 router，例如：

```txt
src/server/routers/lambda/agent.ts
src/server/routers/lambda/aiChat.ts
src/server/routers/lambda/message.ts
src/server/routers/lambda/session.ts
src/server/routers/lambda/user.ts
src/server/routers/lambda/file.ts
src/server/routers/lambda/config/index.ts
src/server/routers/lambda/market/index.ts
```

再往下，业务 router 通常会调用：

```txt
src/database/models/*
src/server/services/*
src/services/*
packages/*
外部模型服务、存储服务、鉴权服务等
```

根据当前片段和项目约定推断，`route.ts` 不直接接触数据库，也不直接创建业务 model。数据库注入、model 初始化和业务校验应在具体 router / middleware 中完成。

## 运行/调用流程

一次请求的大致流程如下：

1. 客户端发起 tRPC 请求到 `/trpc/lambda` 或其动态 path。
2. Next.js App Router 命中 `src/app/(backend)/trpc/lambda/[trpc]/route.ts`。
3. `handler(req)` 被调用。由于文件导出了 `GET` 和 `POST`，两类 HTTP 方法都会进入同一个 handler。
4. `prepareRequestForTRPC(req)` 克隆或适配请求，避免 body stream 被重复消费。
5. `fetchRequestHandler` 开始处理 tRPC 请求。
6. tRPC 调用 `createContext: () => createLambdaContext(req)`。
7. `createLambdaContext` 从请求头、cookie、API key、OIDC token、Better Auth session 等来源解析用户身份与请求元信息。
8. tRPC 根据请求 path 在 `lambdaRouter` 中找到对应子 router 和 procedure。
9. procedure 根据自己使用的基础过程决定鉴权策略：
   - `publicProcedure`：公开访问。
   - `authedProcedure`：需要用户登录。
   - `heteroAuthedProcedure`：用于特定 hetero agent 操作令牌场景。
10. 业务 procedure 执行数据库、服务或外部 API 调用。
11. 如果成功，tRPC 使用 `superjson` 序列化结果。
12. 如果失败，`onError` 处理日志：
   - `UNAUTHORIZED` 被认为是正常登录态问题，不额外打印。
   - 其他错误会输出 path、type 和错误对象。
13. `createResponseMeta` 参与生成响应元信息。
14. 最终返回 HTTP Response。

其中最容易忽略的是第 6 步和第 9 步：context 创建和鉴权不是同一个概念。`createLambdaContext` 负责“识别你是谁”，`authedProcedure` / middleware 负责“你是否被允许访问”。

## 小白阅读顺序

建议按下面顺序读，不要一上来钻进几十个业务 router：

1. `src/app/(backend)/trpc/lambda/[trpc]/route.ts`  
   先理解 HTTP 请求如何进入 tRPC。重点看 `fetchRequestHandler` 的配置项：`router`、`createContext`、`endpoint`、`onError`、`responseMeta`。

2. `src/server/routers/lambda/index.ts`  
   看 `lambdaRouter` 如何聚合业务模块。这里像 API 目录表，可以知道系统有哪些后端能力，例如 `message`、`session`、`file`、`aiChat`、`agent`、`config`。

3. `src/libs/trpc/lambda/init.ts`  
   理解 tRPC 的基础配置：`LambdaContext`、`superjson`、`errorFormatter`。

4. `src/libs/trpc/lambda/index.ts`  
   理解业务 router 写法中最常见的 `router`、`publicProcedure`、`authedProcedure`、`heteroAuthedProcedure` 从哪里来。

5. `src/libs/trpc/lambda/context.ts`  
   再看请求身份如何被解析。这里信息较多，建议重点抓主线：开发 mock、API key、OIDC、Better Auth、trace、cookie、IP、user-agent。

6. 挑一个简单业务 router 读  
   例如 `config`、`user`、`session` 这类模块通常能帮助理解 procedure 如何使用 `ctx`。读的时候重点看它使用的是 `publicProcedure` 还是 `authedProcedure`，以及 input schema、数据库 model、返回结构。

7. 最后再读复杂业务 router  
   例如 `aiAgent`、`agentDocument`、`generation`、`market` 等。这些通常涉及更多服务、队列、模型调用或外部系统，不适合作为第一站。

## 常见误区

### 误区一：以为这个目录实现了所有 TRPC API

不是。`src/app/(backend)/trpc/lambda` 只是 HTTP 入口。真正的 API 列表在 `src/server/routers/lambda/index.ts`，具体逻辑在各个子 router 文件中。

### 误区二：以为 `[trpc]` 目录里会有很多业务文件

不会。这里的 `[trpc]` 是 Next.js 动态路由段，不是业务分类目录。它的作用是让一组 tRPC path 都能被同一个 route handler 捕获。

### 误区三：以为 `createLambdaContext` 完成了所有鉴权

`createLambdaContext` 主要是创建上下文并解析身份。是否必须登录，通常由 procedure 使用的 middleware 决定。比如 `publicProcedure` 可以不登录，`authedProcedure` 会要求登录用户。

### 误区四：看到 `GET` 和 `POST` 都导出，以为业务接口都是 REST 风格

这里不是传统 REST controller。`GET` / `POST` 只是 tRPC HTTP transport 的方法入口。真正的业务动作由 tRPC path 和 procedure 类型决定，例如 `query` 或 `mutation`。

### 误区五：以为 `lambdaRouter` 只服务 serverless Lambda

目录和变量名叫 `lambda`，但在代码结构里它更像“后端 tRPC API 的主 router 命名空间”。它运行在 Next.js route handler 里，是否部署到真正的 Lambda/Serverless 环境取决于部署配置，不能仅凭目录名判断。

### 误区六：忽略 `prepareRequestForTRPC`

这行代码看似只是适配，但注释说明它是在处理 Next.js 16 body stream 相关问题。如果绕过它直接把原始 `req` 传入 tRPC，可能在某些请求体已被内部机制消费的情况下触发 stream locked / disturbed 类错误。

### 误区七：以为 `UNAUTHORIZED` 不打印就是没报错

`onError` 明确过滤了 `UNAUTHORIZED`，因为未登录是正常前端流程的一部分。它不打印额外日志，不代表请求成功，而是避免把正常登录态问题刷成后端错误日志。

### 误区八：新增业务 API 时改这个目录

通常不应该改 `src/app/(backend)/trpc/lambda/[trpc]/route.ts`。新增业务 API 应该在 `src/server/routers/lambda/<domain>.ts` 新建或修改 router，然后在 `src/server/routers/lambda/index.ts` 注册到 `lambdaRouter`。只有当要改变整个 tRPC HTTP 入口行为，例如统一错误日志、请求适配、响应元信息、context 创建方式时，才需要考虑改这个目录。
