# 子系统：next/src/pages/api/trpc

## 解决什么问题

`next/src/pages/api/trpc` 是这个 Next.js 应用的 tRPC HTTP 入口目录。它把浏览器或 SSR 侧发往 `/api/trpc` 的请求交给后端的 `appRouter` 处理，并为每次请求创建统一的运行上下文。目标目录本身不承载具体业务逻辑，而是一个适配层：负责把 Next.js Pages Router 的 API Route 机制，与 `@trpc/server/adapters/next` 提供的请求处理器连接起来。

从当前代码看，目录内只有 `next/src/pages/api/trpc/[trpc].ts`。这里的 `[trpc].ts` 是 Next.js 动态路由文件，可以接住 tRPC 客户端按过程路径发起的请求，例如客户端通过 `api.agent.getAll.useQuery()` 调用时，最终会被 `httpBatchLink` 发送到 `/api/trpc` 下，由这个入口分发到 `agent` 子路由。

这个子系统解决的核心问题是：前端不需要手写 REST endpoint，也不需要单独维护接口类型；后端在 `server/api` 定义 router 和 procedure，前端通过 `utils/api.ts` 直接获得类型安全的 React Query hooks。`pages/api/trpc` 则是这条链路上的唯一 HTTP 网关。

## 相关目录和文件

`next/src/pages/api/trpc/[trpc].ts` 是入口文件。它导入 `createNextApiHandler`，并把 `router` 指向 `appRouter`，把 `createContext` 指向 `createTRPCContext`。开发环境下还配置了 `onError`，当 tRPC 过程失败时输出包含 path 和 message 的错误日志。

`next/src/server/api/root.ts` 是后端 tRPC 根路由定义。当前 `appRouter` 只挂载了一个命名空间：`agent: agentRouter`。同时它导出 `AppRouter` 类型，供前端推断输入输出类型。

`next/src/server/api/trpc.ts` 是 tRPC 服务端基础设施。它创建请求上下文、初始化 `initTRPC`、配置 `superjson` transformer、定义 `createTRPCRouter`、`publicProcedure` 和 `protectedProcedure`。目标目录入口依赖它来生成每次请求的 `ctx`。

`next/src/server/api/routers/agentRouter.ts` 是当前主要业务 router。它定义 `agent.create`、`agent.save`、`agent.getAll`、`agent.findById`、`agent.deleteById` 等过程，覆盖 Agent 的创建、保存任务、查询列表、按 id 查询、软删除。

`next/src/utils/api.ts` 是前端 tRPC 客户端入口。它使用 `createTRPCNext<AppRouter>` 创建 `api` 对象，通过 `httpBatchLink` 把请求发送到 `/api/trpc`，并使用同样的 `superjson` 做序列化兼容。

`next/src/server/auth/index.ts` 提供 `getServerAuthSession`。`createTRPCContext` 会调用它，从 NextAuth 获取当前请求的 session，并把 session 注入到 tRPC context。

`next/src/server/db.ts` 提供全局复用的 PrismaClient。tRPC context 会把 `prisma` 注入给 procedure 使用，业务 router 中也直接导入了 `prisma`。

## 核心对象

`createNextApiHandler` 是 API Route 与 tRPC 的桥接器。`[trpc].ts` 默认导出的就是它返回的 Next.js handler。请求进入 `/api/trpc` 后，handler 负责解析 tRPC path、输入、批处理格式、HTTP method，并调用对应 procedure。

`appRouter` 是整个服务端 API 的根路由。当前结构是 `{ agent: agentRouter }`，因此外部可调用的过程都位于 `agent.*` 命名空间下。前端的 `api.agent.*` 类型和 hook 都由这个对象推导出来。

`createTRPCContext` 是每次请求的上下文工厂。它从 `CreateNextContextOptions` 中取出 `req`、`res`，调用 `getServerAuthSession` 获取 NextAuth session，然后返回包含 `session` 和 `prisma` 的 context。所有 procedure 都通过 `ctx` 访问登录态和数据库能力。

`createTRPCRouter` 是创建 router 的统一函数，来自 `initTRPC.context<typeof createTRPCContext>().create()`。新增业务 router 时应复用它，而不是重新初始化一套 tRPC。

`publicProcedure` 表示不强制登录的过程。当前 `agent.findById` 使用它，因此根据当前片段推断，单个 Agent 详情可能允许未登录访问，至少服务端未在 tRPC 层强制校验用户身份。

`protectedProcedure` 表示必须登录的过程。它通过 `enforceUserIsAuthed` middleware 检查 `ctx.session` 和 `ctx.session.user`，否则抛出 `TRPCError({ code: "UNAUTHORIZED" })`。`agent.create`、`agent.save`、`agent.getAll`、`agent.deleteById` 都使用它。

`api` 是前端暴露的类型安全客户端对象。它来自 `next/src/utils/api.ts`，包装了 React Query hooks，并绑定到 `AppRouter` 类型。

## 运行流程

前端页面或 hook 调用 `api.agent.xxx.useQuery()` 或 `api.agent.xxx.useMutation()`。例如 `next/src/components/drawer/LeftSidebar.tsx` 调用 `api.agent.getAll.useQuery()`，`next/src/hooks/useAgent.ts` 调用 `api.agent.create.useMutation()` 和 `api.agent.save.useMutation()`，`next/src/pages/agent/index.tsx` 调用 `findById` 和 `deleteById`。

`tRPC` 客户端根据 `utils/api.ts` 的配置，使用 `httpBatchLink` 把请求发送到 `/api/trpc`。浏览器环境使用相对路径；SSR 或服务端环境会根据 `VERCEL_URL` 或 `PORT` 拼接 base URL。由于 `ssr: false`，这里默认不等待 tRPC query 完成后再做服务端渲染。

请求到达 `next/src/pages/api/trpc/[trpc].ts` 后，`createNextApiHandler` 使用 `appRouter` 查找过程路径，例如 `agent.getAll`。在执行 procedure 前，它调用 `createTRPCContext` 生成 context。这个过程会读取 NextAuth session，并把 `session`、`prisma` 放入 `ctx`。

如果目标 procedure 是 `protectedProcedure`，middleware 会先确认用户已登录。通过后，业务逻辑读取 `ctx.session.user.id` 作为数据归属条件，并通过 Prisma 查询或写入数据库。如果是 `publicProcedure`，则直接进入业务逻辑，但仍然可以访问可选的 `ctx.session`。

结果会经过 `superjson` 序列化返回给客户端。前端 `api` hooks 收到响应后，交给 React Query 管理 loading、cache、error 等状态。

## 上下游依赖

上游调用方主要是前端页面、组件和 hooks。当前可见调用点包括 `next/src/pages/agent/index.tsx`、`next/src/components/drawer/LeftSidebar.tsx`、`next/src/hooks/useAgent.ts`。它们并不直接访问 `/api/trpc`，而是通过 `next/src/utils/api.ts` 生成的 `api` 对象调用。

本目录直接依赖 `next/src/server/api/root.ts` 暴露的 `appRouter`，也依赖 `next/src/server/api/trpc.ts` 暴露的 `createTRPCContext`。换句话说，`pages/api/trpc` 只负责接线；路由树和上下文都在 `server/api` 中定义。

认证依赖 NextAuth。`createTRPCContext` 间接调用 `next/src/server/auth/index.ts` 的 `getServerAuthSession`，后者会组合生产或开发环境的 auth options，并通过 Prisma Adapter 读写用户、session 和组织关系。

数据访问依赖 Prisma。`next/src/server/db.ts` 创建并复用 `PrismaClient`，开发环境下开启 query、error、warn 日志，生产环境只记录 error。Agent router 使用 Prisma 访问 `agent`、`agentTask` 等模型。

外部模型服务依赖 OpenAI SDK。`agent.create` 内部会调用 `generateAgentName`，在存在 `OPENAI_API_KEY` 时用 OpenAI Chat Completions 生成 Agent 名称；失败时会降级为使用用户输入的 goal。这里不属于入口目录职责，但它是当前 tRPC 请求链路可能触发的外部依赖。

## 修改时最容易踩的坑

不要把业务逻辑写进 `next/src/pages/api/trpc/[trpc].ts`。这个文件应保持为薄入口；新增 API 能力应放到 `next/src/server/api/routers` 下的 router 中，再挂载到 `next/src/server/api/root.ts`。

新增 router 后必须更新 `appRouter`。前端 `api.xxx` 的类型来自 `AppRouter`，如果只创建了 router 文件但没有挂到 `appRouter`，客户端不会出现对应命名空间，请求也无法被服务端分发。

服务端和客户端 transformer 要保持一致。当前服务端 `server/api/trpc.ts` 和客户端 `utils/api.ts` 都使用 `superjson`。如果一边修改、一边不改，日期、复杂对象或特殊类型的序列化可能出现不一致。

认证边界要在 procedure 类型上表达清楚。需要用户身份的操作应使用 `protectedProcedure`，不要只在业务代码里读取 `ctx.session?.user?.id` 后假设它存在。尤其是写入、删除、列表查询这类用户私有数据操作，应优先使用 `protectedProcedure`。

注意 `ctx.prisma` 与直接导入 `prisma` 的混用。`agentRouter.ts` 中 `create` 使用 `ctx.prisma`，其他过程多处直接使用导入的 `prisma`。这在运行上通常可行，但测试或替换 context 时会降低一致性。修改时应意识到这两种访问路径的差异。

`findById` 当前是 `publicProcedure`，并且只按 `id` 和 `deleteDate: null` 查询，没有校验 `userId`。如果 Agent 详情不应公开，这是一个需要特别审视的权限点。根据当前片段推断，它可能是有意支持分享或公开查看；判断依据是该过程明确没有使用 `protectedProcedure`。

`save` 会为传入 tasks 批量创建 `agentTask`，但没有看到清理旧任务或去重逻辑。修改保存语义时要确认调用方期望是“追加任务”还是“覆盖任务”，否则容易产生重复记录。

开发环境错误日志只在 `env.NODE_ENV === "development"` 下启用。生产环境不会通过 `onError` 输出同样的 tRPC path 诊断信息，排查线上问题时需要依赖其他日志机制。

## 推荐阅读顺序

1. 先读 `next/src/pages/api/trpc/[trpc].ts`，理解这个目录只是 Next.js API Route 到 tRPC 的入口。
2. 再读 `next/src/server/api/trpc.ts`，掌握 context、router 工厂、public/protected procedure 的定义。
3. 接着读 `next/src/server/api/root.ts`，确认当前暴露了哪些业务命名空间。
4. 然后读 `next/src/server/api/routers/agentRouter.ts`，理解当前实际的 tRPC 业务能力和权限分布。
5. 再读 `next/src/utils/api.ts`，看前端如何生成 `api` hooks、如何把请求指向 `/api/trpc`。
6. 最后按调用链查看 `next/src/hooks/useAgent.ts`、`next/src/components/drawer/LeftSidebar.tsx`、`next/src/pages/agent/index.tsx`，把用户界面上的操作和 `agent.*` procedure 对应起来。
