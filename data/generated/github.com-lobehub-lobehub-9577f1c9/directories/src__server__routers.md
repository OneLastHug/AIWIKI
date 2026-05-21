# 目录：src/server/routers

## 它负责什么

`src/server/routers` 是 LobeHub 服务端 TRPC API 的路由层。它的职责不是直接实现所有业务，而是把“客户端或服务端内部调用发来的 RPC 请求”映射到具体领域 router，再由 router 调用数据库模型、服务类或外部能力。

从目录结构看，它按调用场景拆成四类入口：

- `lambda/`：主业务 TRPC 路由集合，对应大多数 Web/桌面端在线业务 API。
- `async/`：异步任务相关路由，面向文件解析、图片、视频、RAG Eval 等可能较重的后台处理。
- `tools/`：工具能力路由，例如搜索、MCP、Klavis、market。
- `mobile/`：移动端专用聚合路由，只暴露移动端实际使用的 router 子集。

这些入口最终被 Next.js 后端 route handler 挂载到不同 TRPC endpoint，例如：

- `src/app/(backend)/trpc/lambda/[trpc]/route.ts` 使用 `lambdaRouter`
- `src/app/(backend)/trpc/async/[trpc]/route.ts` 使用 `asyncRouter`
- `src/app/(backend)/trpc/tools/[trpc]/route.ts` 使用 `toolsRouter`
- `src/app/(backend)/trpc/mobile/[trpc]/route.ts` 使用 `mobileRouter`

所以可以把这里理解为“后端 API 的总配线板”：请求先进入 Next.js API route，再交给对应根 router，最后分派到领域 procedure。

## 关键组成

`lambda/index.ts` 是主入口。它从同目录导入大量领域 router，并通过：

```ts
export const lambdaRouter = router({
  agent: agentRouter,
  message: messageRouter,
  session: sessionRouter,
  topic: topicRouter,
  file: fileRouter,
  ...
});
```

组合成完整的 `lambdaRouter`。其中包括会话、消息、智能体、模型供应商、文件、知识库、任务、通知、分享、生成任务、用户记忆等核心业务。它还引入了部分 `@/business/server/lambda-routers/*` 下的商业化或云服务相关 router，例如 `subscriptionRouter`、`spendRouter`、`topUpRouter`、`referralRouter`。

`async/index.ts` 是异步能力入口，组合了：

- `documentRouter`
- `fileRouter`
- `imageRouter`
- `ragEvalRouter`
- `videoRouter`

它使用的是 `@/libs/trpc/async` 里的 `asyncRouter` 和 `asyncAuthedProcedure` 体系。`async/caller.ts` 还提供 `createAsyncServerClient` 和 `createAsyncCaller`，用于服务端内部通过 HTTP 调用 `/trpc/async`。这里会签发 internal JWT，并通过 `LOBE_CHAT_AUTH_HEADER` 传递加密后的 `userId`。根据当前片段推断，这种设计是为了让后台任务或服务端流程能复用异步 TRPC API，而不是直接跨层调用内部实现。

`tools/index.ts` 是工具 API 入口，组合：

- `klavisRouter`
- `marketRouter`
- `mcpRouter`
- `searchRouter`

抽样看到 `tools/search.ts` 中的 procedure 基本调用 `searchService`，例如 `query`、`webSearch`、`crawlPages`。这类 router 更像是“工具服务 facade”，负责鉴权、输入校验和转发到服务层。

`mobile/index.ts` 是移动端裁剪版入口。它复用许多 `lambda/` 下已有 router，例如 `agentRouter`、`messageRouter`、`sessionRouter`、`fileRouter`、`topicRouter`，但不会把完整 `lambdaRouter` 暴露给移动端。它还加入了 `@/business/server/mobile-routers/mobileSubscription`。这说明移动端 API 面向兼容和最小暴露面，而不是直接等同 Web 端。

每个领域 router 通常遵循 TRPC 模式：

- 用 `router({...})` 定义一组 procedure。
- 用 `publicProcedure`、`authedProcedure` 或异步体系的 `asyncAuthedProcedure` 控制访问权限。
- 用 `zod` 定义输入 schema。
- 在 procedure 中调用模型层或服务层。
- 返回业务数据，或抛出 `TRPCError`。

例如 `lambda/session.ts` 中定义了 `sessionProcedure`：

```ts
const sessionProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
  const { ctx } = opts;

  return opts.next({
    ctx: {
      sessionGroupModel: new SessionGroupModel(ctx.serverDB, ctx.userId),
      sessionModel: new SessionModel(ctx.serverDB, ctx.userId),
    },
  });
});
```

这个模式很重要：router 不在每个 procedure 里重复初始化模型，而是通过 middleware 把 `sessionModel`、`sessionGroupModel` 注入到 `ctx`，后续 procedure 直接使用 `ctx.sessionModel`。

## 上下游关系

上游主要有三类：

1. 前端或移动端 TRPC client  
   根据当前片段推断，Web/桌面端会调用 `/trpc/lambda`，移动端调用 `/trpc/mobile`，工具相关功能调用 `/trpc/tools`。具体 client 封装不在本次片段中展开，但 route handler 已经说明了这些 router 的 HTTP 挂载点。

2. 服务端内部调用  
   `src/libs/trpc/mock.ts` 会用 `lambdaRouter` 创建 caller；`src/app/(backend)/webapi/create-image/comfyui/route.ts` 也导入 `lambdaRouter` 并通过 `createCallerFactory` 调用。这说明 router 不只服务浏览器请求，也可被同进程服务端逻辑复用。

3. 异步服务端调用  
   `async/caller.ts` 用 `createTRPCClient<AsyncRouter>` 通过 HTTP 调用 `appEnv.INTERNAL_APP_URL + '/trpc/async'`。这类调用会带 internal JWT 和加密用户信息，适合后台工作流或跨运行环境调用。

下游则主要包括：

- `@/database/models/*`：数据库模型层，例如 `SessionModel`、`SessionGroupModel`、`ChatGroupModel`。
- `@/server/services/*`：服务层，例如 `searchService`。
- `@/database/schemas` 和 `@/types/*`：输入输出结构、业务类型、schema。
- `@/libs/trpc/*`：TRPC 初始化、鉴权、中间件、上下文构造。
- `@/business/server/*`：商业化或特定部署场景的 server router。

router 层位于中间：上接 API endpoint 和 caller，下接 service/model。它通常不应该承载复杂领域算法，而应该负责 API 边界上的输入校验、鉴权、上下文注入、错误包装和调用编排。

## 运行/调用流程

典型 `lambda` 调用流程如下：

1. 客户端请求 `/trpc/lambda/session.getSessions` 这类 TRPC procedure。
2. Next.js route handler `src/app/(backend)/trpc/lambda/[trpc]/route.ts` 接住请求。
3. route handler 把请求交给 `lambdaRouter`。
4. `lambdaRouter` 根据路径找到 `sessionRouter.getSessions`。
5. procedure 先经过 `authedProcedure`，执行 OpenTelemetry、OIDC、用户鉴权等中间件。
6. `serverDatabase` middleware 把数据库连接放入 `ctx.serverDB`。
7. `sessionProcedure` middleware 初始化 `SessionModel`，放入 `ctx.sessionModel`。
8. `getSessions` 用 `zod` 校验输入，然后调用 `ctx.sessionModel.query(...)`。
9. 结果经 TRPC 序列化返回给调用方。

典型 `tools` 调用流程略轻：

1. 请求进入 `/trpc/tools/search.query`。
2. `toolsRouter` 分派到 `searchRouter.query`。
3. `authedProcedure` 做鉴权。
4. `zod` 校验 `{ query, optionalParams }`。
5. procedure 调用 `searchService.query(...)`。
6. 返回搜索结果。

典型 `async` 内部调用流程更特殊：

1. 某个服务端流程调用 `createAsyncCaller({ userId })`。
2. `createAsyncServerClient` 签发 internal JWT，并把加密用户信息写进 header。
3. 它创建指向 `/trpc/async` 的 TRPC HTTP client。
4. `createAsyncCaller` 用 `Proxy` 伪装成 `caller.file.parseFileToChunks(...)` 这类调用形式。
5. 实际执行时走 HTTP 的 `mutate`，由 `asyncRouter` 分派到对应异步 procedure。

这里的 `async/caller.ts` 有一个值得注意的点：它的代理调用当前只检查 `procedure.mutate`，因此从当前片段看，它主要面向 mutation 型异步任务。若未来要通过这个 caller 调 query，需要确认是否已有额外封装或需要扩展。

## 小白阅读顺序

1. 先读 `src/server/routers/lambda/index.ts`  
   这是主地图。不要一开始扎进几十个业务文件，先看它把哪些领域挂到了 API 上，理解 `agent`、`message`、`session`、`file`、`knowledgeBase` 等名字对应的 API 命名空间。

2. 再读 `src/libs/trpc/lambda/index.ts`  
   重点看 `router`、`publicProcedure`、`authedProcedure` 的来源。理解 procedure 不是普通函数，它带着 TRPC 的鉴权、中间件和上下文机制。

3. 读一个中等复杂度的业务 router，例如 `src/server/routers/lambda/session.ts`  
   重点观察：`zod` 输入校验、`serverDatabase` 注入数据库、middleware 注入 model、procedure 调用 model。这个文件还有 deprecated 注释，可以帮助理解旧 `session` 和新 `agent` 的迁移关系。

4. 读 `src/server/routers/tools/index.ts` 和 `src/server/routers/tools/search.ts`  
   这组代码更短，适合理解“router 调 service”的模式。和 `session.ts` 对比，可以看到有些 router 下游是数据库模型，有些是服务对象。

5. 读 `src/server/routers/async/index.ts` 和 `src/server/routers/async/caller.ts`  
   这里能理解异步任务为什么单独拆 endpoint，以及服务端如何通过 internal JWT 调用异步 TRPC。

6. 最后读 `src/server/routers/mobile/index.ts`  
   它不是全新业务，而是复用 `lambda` router 的移动端子集。读它能理解“同一业务 router 可以被不同根 router 组合”的设计。

## 常见误区

1. 误以为 `src/server/routers` 是所有业务实现所在地  
   实际上它主要是 API 边界层。真正的数据操作多在 `@/database/models/*`，复杂外部能力多在 `@/server/services/*`。router 负责把请求安全、清晰地转到这些下游。

2. 误以为 `lambdaRouter`、`mobileRouter`、`toolsRouter`、`asyncRouter` 是同一个入口  
   它们分别挂在不同 endpoint，面向不同调用场景。尤其 `mobileRouter` 是裁剪后的 API 面，不等价于完整 `lambdaRouter`。

3. 看到 `publicProcedure` 就认为完全无用户上下文  
   `publicProcedure` 表示不强制登录，但 procedure 内仍可能读取 `ctx.userId`。例如 `session.getGroupedSessions` 会在没有 `userId` 时返回空数据，有 `userId` 时再查库。

4. 忽略 middleware 注入的 `ctx`  
   很多 model 并不是全局可用的，而是通过类似 `sessionProcedure = authedProcedure.use(serverDatabase).use(...)` 注入。读 procedure 时要先往上看它基于哪个 base procedure。

5. 误把 `async/caller.ts` 当成本地函数调用  
   它表面上提供 `caller.xxx.yyy()` 的写法，但实际通过 TRPC HTTP client 请求 `/trpc/async`。这会涉及 URL、header、internal JWT、Vercel protection bypass 等运行环境配置。

6. 认为新增 router 只要写一个文件就完成  
   通常还要在对应 `index.ts` 根 router 中注册，否则 endpoint 不会暴露。若是移动端能力，还要判断是否应加入 `mobile/index.ts`；若是异步任务，则应使用 `@/libs/trpc/async` 的 procedure 体系。

7. 忽略 deprecated 注释  
   例如 `lambda/session.ts` 标注 session router 是 legacy，agent CRUD 应迁移到 `agentRouter`。学习或改动时不能只看函数还能用，还要看注释中表达的架构方向。
