# 子系统：src/server/routers

## 解决什么问题

`src/server/routers` 是 LobeHub 服务端 tRPC API 的路由层，负责把前端、移动端、工具调用、异步任务等请求组织成类型安全的 procedure。它本身不是业务模型层，也不是数据库访问层，而是“请求入口编排层”：校验输入、选择鉴权方式、注入数据库与领域模型、调用 `src/server/services` 或 `src/database/models`，再把结果以 tRPC 的 query / mutation 形式暴露出去。

这个目录的核心价值是把庞大的服务端能力按调用场景拆分：主应用走 `lambda`，异步文件、图片、视频等重任务走 `async`，移动端走精简版 `mobile`，内置工具或外部工具调用走 `tools`。因此它既是后端 API 的公共边界，也是前后端类型契约的重要来源。

## 相关目录和文件

`src/server/routers/lambda/index.ts` 是主聚合入口，导出 `lambdaRouter` 和 `LambdaRouter`。它汇总聊天、消息、会话、文件、知识库、市场、用户、模型、任务、生成、视频、Agent 等大量领域 router，并额外接入 `@/business/server/lambda-routers/*` 下的商业化路由，例如订阅、充值、用量相关能力。

`src/server/routers/async/index.ts` 导出 `asyncRouter`，聚合 `document`、`file`、`image`、`ragEval`、`video` 等偏异步处理的路由，并从 `caller.ts` 导出 `createAsyncCaller`、`createAsyncServerClient` 等内部调用工具。

`src/server/routers/mobile/index.ts` 导出 `mobileRouter`，注释明确说明它只包含移动端实际使用的 router。它大量复用 `lambda` 下的领域 router，同时加入 `@/business/server/mobile-routers/mobileSubscription`。

`src/server/routers/tools/index.ts` 导出 `toolsRouter`，面向工具相关能力，当前聚合 `klavis`、`market`、`mcp`、`search` 等 router。

`src/server/routers/lambda/_helpers/resolveContext.ts` 和 `_schema/context.ts` 是共享上下文解析与输入 schema。`lambda/_template.ts` 展示了新建 router 的推荐结构：使用 `authedProcedure`、`serverDatabase` 中间件，把 model 注入 `ctx`，再在 procedure 中调用。

真正挂载到 HTTP 的位置在 `src/app/(backend)/trpc/lambda/[trpc]/route.ts`、`src/app/(backend)/trpc/async/[trpc]/route.ts`、`src/app/(backend)/trpc/mobile/[trpc]/route.ts`、`src/app/(backend)/trpc/tools/[trpc]/route.ts`。这些 route 文件把对应 router 交给 tRPC handler。

## 核心对象

`lambdaRouter` 是主应用服务端 API 的总入口。它的 key 会成为 tRPC 调用路径的一部分，例如 `message`、`session`、`file`、`knowledgeBase`、`aiAgent` 等。新增主应用 API 时，通常需要在领域文件中导出 `xxxRouter`，再注册到 `lambda/index.ts`。

`asyncRouter` 面向异步或耗时任务。根据当前片段推断，它服务于文档解析、文件处理、图片生成、视频任务、RAG 评测等可能需要独立执行环境或服务端内部 caller 的能力，依据是 `async/index.ts` 聚合的领域和 `async/caller.ts` 导出的 server client。

`mobileRouter` 是移动端 API 面。它不是重新实现一套逻辑，而是挑选复用 `lambda` router 的一部分，减少移动端暴露面和打包/调用范围。

`toolsRouter` 是工具调用 API 面。它仍使用 `@/libs/trpc/lambda` 的 `router` 和 `publicProcedure`，但目录语义更偏向 agent/tool 生态，比如 MCP、搜索、市场工具。

`authedProcedure`、`publicProcedure`、`router` 来自 `@/libs/trpc/lambda` 或 `@/libs/trpc/async`，决定 procedure 是否需要登录、使用哪个 tRPC 实例。`serverDatabase` 中间件来自 `@/libs/trpc/lambda/middleware`，用于把 `serverDB` 放进 `ctx`。

领域 router 内部常见核心对象是 model、repository、service。例如 `message.ts` 中的 `MessageModel`、`TopicShareModel`、`CompressionRepository`、`FileService`、`MessageService`，通过中间件注入到 `ctx` 后被 procedure 使用。

## 运行流程

一次典型的主应用请求会先进入 `src/app/(backend)/trpc/lambda/[trpc]/route.ts`，该 route 把请求交给 tRPC，并指定 `lambdaRouter`。tRPC 根据路径找到对应领域 router 和 procedure，例如 `message.getMessages` 或 `sessionGroup.updateSessionGroup`。

进入 procedure 前，链式中间件会先处理上下文。需要登录的接口使用 `authedProcedure`，公共接口使用 `publicProcedure`。需要数据库的接口继续 `.use(serverDatabase)`，之后领域级中间件创建 model、service、repository，并通过 `opts.next({ ctx: {...} })` 合并进上下文。

procedure 本体通常先用 `zod` 或共享 schema 校验输入，再调用 model/service。简单 CRUD 多数直接调用 model，例如 `sessionGroupRouter` 调用 `SessionGroupModel` 的 `create`、`query`、`update`、`delete`。复杂业务则进入 service，例如 `messageRouter` 把消息创建、压缩、文件关联等逻辑交给 `MessageService`。

如果是公开分享等特殊访问场景，procedure 会在内部自行分支。例如 `message.getMessages` 支持 `topicShareId`，有分享 ID 时通过 `TopicShareModel.findByShareIdWithAccessCheck` 查找 owner，再用 owner 的用户上下文读取消息；没有分享 ID 时则要求 `ctx.userId` 存在。

## 上下游依赖

上游主要是四类入口：Next.js App Router 下的 tRPC HTTP route、SPA/移动端通过 tRPC client 发起的请求、服务端内部 caller、以及部分 webapi route。例如 `src/app/(backend)/webapi/create-image/comfyui/route.ts` 会通过 `createCallerFactory(lambdaRouter)` 内部调用主 router。

下游主要是数据库模型、服务层、仓储层和共享类型。数据库模型位于 `src/database/models`，schema 可能来自 `src/database/schemas`；服务层位于 `src/server/services`；商业化 router 来自 `@/business/server/*`；共享输入类型可能来自 `@lobechat/types` 或本地 `_schema`。路由层还依赖 `@trpc/server` 的 `TRPCError`、`zod` 输入校验，以及 `@/libs/trpc/*` 提供的 tRPC 基础设施。

从数据流看，router 不应该承载大量业务状态变更细节。它更像边界适配器：把 HTTP/tRPC 上下文、登录用户、数据库连接、输入参数转换成服务层和模型层能处理的调用。

## 修改时最容易踩的坑

第一，新增主应用 router 只写领域文件但忘记注册到 `src/server/routers/lambda/index.ts`，前端会拿不到调用路径。若移动端也需要，还要显式加入 `src/server/routers/mobile/index.ts`，不能假设移动端自动继承主 router。

第二，混用 `publicProcedure` 和 `authedProcedure` 容易造成权限漏洞。公开接口必须在 procedure 内部做精确访问控制，例如分享 ID、ownerId、匿名访问边界；普通用户数据接口应默认走 `authedProcedure`。

第三，不要在每个 procedure 里反复 `new Model(ctx.serverDB, ctx.userId)`。本仓库约定用领域级 procedure 中间件注入 model/service 到 `ctx`。例外是确实要切换 userId 的场景，例如公开分享读取 owner 数据。

第四，输入 schema 要稳定。tRPC 类型会影响前端调用方，随意改字段名、可选性或返回结构会造成跨端破坏。共享上下文参数优先复用 `_schema/context.ts` 这类公共 schema。

第五，`lambda`、`async`、`tools` 使用的 tRPC 实例不同。异步 router 应使用 `@/libs/trpc/async`，不要直接照搬 `lambda` 的 import。根据当前片段推断，这关系到异步运行环境、caller 初始化和鉴权上下文。

第六，错误处理要保留 tRPC 语义。已是 `TRPCError` 的错误应继续抛出，其他异常再包装为合适 code，避免前端无法区分未授权、未找到和服务端异常。

## 推荐阅读顺序

1. 先读 `src/app/(backend)/trpc/lambda/[trpc]/route.ts`，理解 HTTP 请求如何进入 tRPC。
2. 再读 `src/server/routers/lambda/index.ts`，建立主应用 API 地图。
3. 阅读 `src/server/routers/lambda/_template.ts`，掌握单个领域 router 的推荐写法。
4. 选择一个简单 router，如 `src/server/routers/lambda/sessionGroup.ts`，理解 model 注入、输入校验和 CRUD procedure。
5. 再读一个复杂 router，如 `src/server/routers/lambda/message.ts`，观察 service、repository、公开访问、上下文解析如何组合。
6. 最后横向阅读 `src/server/routers/async/index.ts`、`src/server/routers/mobile/index.ts`、`src/server/routers/tools/index.ts`，理解同一套后端能力如何按调用场景拆成多个 API 面。
