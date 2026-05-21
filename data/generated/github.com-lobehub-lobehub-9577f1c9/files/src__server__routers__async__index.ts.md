# 文件：src/server/routers/async/index.ts

## 它负责什么

这个文件是 `async` 这组 TRPC 子路由的聚合入口。它把 `document`、`file`、`image`、`ragEval`、`video` 这几个子 router 组装成一个对外暴露的 `asyncRouter`，并额外挂了一个最简单的 `healthcheck` 查询接口，用来确认服务存活。

它同时还是类型和调用器能力的导出入口：

- `export type AsyncRouter = typeof asyncRouter` 用于给客户端和 caller 提供完整类型信息。
- `export { createAsyncCaller, createAsyncServerClient } from './caller'` 把异步调用封装直接往外透出，方便上层直接复用。

## 关键组成

1. `import { asyncRouter as router, publicProcedure } from '@/libs/trpc/async'`
   这里的 `router` 是 TRPC 的 router 工厂别名，`publicProcedure` 是不带鉴权的基础 procedure。

2. 子路由挂载
   - `documentRouter`
   - `fileRouter`
   - `imageRouter`
   - `ragEvalRouter`
   - `videoRouter`

   这些模块共同定义了 `async` 这组接口的业务面。

3. `healthcheck`
   - `publicProcedure.query(() => "i'm live!")`
   - 这是一个轻量探活接口，常用于连通性检查、部署验证、运行时排障。

4. 类型与 caller 导出
   - `AsyncRouter`
   - `UnifiedAsyncCaller`
   - `createAsyncCaller`
   - `createAsyncServerClient`

   这一层把“路由定义”和“如何从服务端调用这套路由”连成一条线。

## 上下游关系

上游主要有两类：

- `src/libs/trpc/async/index.ts`
  这里提供 `asyncRouter`、`publicProcedure`、`asyncAuthedProcedure`、`createAsyncCallerFactory` 等基础能力。  
  根据当前片段推断，这个文件更像是 `async` 域的 TRPC 运行时封装层：定义 procedure、中间件、数据库上下文和 caller 工厂。

- `src/app/(backend)/trpc/async/[trpc]/route.ts`
  根据目录和 `rg` 命中结果，这里是 `/trpc/async` 的 HTTP 入口，会把 `asyncRouter` 挂到 Next.js 的后端路由上。也就是说，这个文件定义“有哪些 procedure”，而真正对外服务的是这个 App Router 路由。

下游主要有三类消费方：

- `src/server/routers/async/caller.ts`
  它使用 `asyncRouter` 生成 `UnifiedAsyncCaller` 的类型，并通过 HTTP 客户端去调用 `/trpc/async`。

- `src/server/services/chunk/index.ts`
  这里按需动态导入 `createAsyncCaller`，说明它把这套路由当成服务端内部能力在复用。

- `src/server/routers/lambda/image/index.ts`、`src/server/routers/lambda/ragEval.ts`
  这些地方也直接调用 `createAsyncCaller`，说明 `async` 路由是跨模块的通用能力层，不只是一个单独页面或接口文件。

## 运行/调用流程

1. Next.js 的 `/trpc/async/[trpc]` 入口收到请求后，把请求转给 `asyncRouter`。
2. `asyncRouter` 由本文件组合出来，内部包含各个子域路由和 `healthcheck`。
3. 如果请求命中 `file`、`image` 之类的子路由，就继续下钻到对应模块执行具体 procedure。
4. 如果上层代码需要服务端内部调用，会走 `createAsyncCaller({ userId })`。
5. `createAsyncCaller` 先通过 `createAsyncServerClient(userId)` 构造一个带内部鉴权头和加密用户标识的 TRPC HTTP 客户端。
6. 之后它用 `Proxy` 把 `caller.xxx.yyy()` 这种链式访问转成对远端 procedure 的 `mutate(...)` 调用。

根据当前片段推断，这套设计的目标不是“本地直调用函数”，而是统一通过 HTTP client 访问同一套路由，这样可以复用鉴权、上下文和中间件逻辑。

## 小白阅读顺序

1. 先看这个文件，确认 `async` 域有哪些子路由。
2. 再看 `src/libs/trpc/async/index.ts`，理解 `publicProcedure`、`asyncAuthedProcedure`、`createAsyncCallerFactory` 的来源。
3. 再看 `src/server/routers/async/caller.ts`，理解为什么要绕一层 HTTP client，以及 `UnifiedAsyncCaller` 怎么来的。
4. 接着看 `src/app/(backend)/trpc/async/[trpc]/route.ts`，把路由注册和真实对外入口接起来。
5. 最后按业务需要挑一个子路由看，比如 `file.ts` 或 `image.ts`，理解具体 procedure 如何组织。

## 常见误区

1. 把 `asyncRouter` 当成“异步任务队列”。
   它不是 job system，而是 TRPC 路由集合。

2. 把 `createAsyncCaller` 当成本地函数调用。
   它本质上是 HTTP client + Proxy 包装，最后仍然会打到 `/trpc/async`。

3. 忽略 `healthcheck` 的作用。
   它虽然简单，但在部署和连通性排查里很实用。

4. 以为所有子路由都需要鉴权。
   这里同时存在 `publicProcedure` 和子模块里使用的 `asyncAuthedProcedure`，权限边界是分开的。

5. 只看这个文件就以为看完了业务。
   这里主要是总装配，真正的业务逻辑分散在 `document.ts`、`file.ts`、`image.ts`、`ragEval.ts`、`video.ts` 里。
