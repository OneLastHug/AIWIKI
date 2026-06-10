# 子系统：next/src/pages/api

## 解决什么问题

`next/src/pages/api` 是这个 Next.js 前端应用的服务端 API 入口层，负责把浏览器请求接入到后端逻辑，但它本身不承载主要业务实现。当前目录只有两个入口：`api/auth/[...nextauth].ts` 处理登录、会话、OAuth 回调等认证请求；`api/trpc/[trpc].ts` 处理类型安全的 tRPC RPC 请求。也就是说，这个目录更像“HTTP 适配层”：把 Next.js API Route 的 `req`、`res` 转交给 NextAuth 或 tRPC，再由 `server/auth`、`server/api`、Prisma 和业务路由完成实际工作。

从仓库结构看，应用仍使用 Pages Router 风格的 API Routes，而不是 `app/api` 的 Route Handler。前端页面、hooks 和组件通过 `next-auth/react`、`utils/api.ts` 间接访问这里，不直接手写大量 `fetch("/api/...")`。

## 相关目录和文件

`next/src/pages/api/auth/[...nextauth].ts` 是 NextAuth catch-all 路由。`[...nextauth]` 会覆盖 `/api/auth/signin`、`/api/auth/session`、OAuth callback、signout 等 NextAuth 约定路径。它导入 `server/auth` 中的 `authOptions(req, res)`，再调用 `NextAuth(req, res, options)`。

`next/src/pages/api/trpc/[trpc].ts` 是 tRPC catch-all 路由。客户端在 `next/src/utils/api.ts` 中配置 `httpBatchLink` 指向 `/api/trpc`，最终由这里的 `createNextApiHandler` 接收请求。

认证配置集中在 `next/src/server/auth/index.ts`、`next/src/server/auth/auth.ts`、`next/src/server/auth/local-auth.ts`。tRPC 的上下文和过程定义集中在 `next/src/server/api/trpc.ts`，根路由在 `next/src/server/api/root.ts`，目前挂载的业务路由是 `next/src/server/api/routers/agentRouter.ts`。

前端消费侧主要包括 `next/src/pages/_app.tsx`、`next/src/hooks/useAuth.ts`、`next/src/hooks/useAgent.ts`、`next/src/components/drawer/LeftSidebar.tsx`、`next/src/pages/agent/index.tsx` 等。

## 核心对象

`authOptions` 是认证子系统的核心配置函数。它根据 `req`、`res` 生成 NextAuth 配置，并合并通用配置与环境相关配置。通用部分使用 `PrismaAdapter(prisma)` 持久化用户、账号和会话，并在 `session` callback 中把 `accessToken`、`user.id`、`superAdmin`、`organizations` 注入到会话对象。生产认证提供方定义在 `server/auth/auth.ts`，包含 Google、GitHub、Discord；开发环境配置在 `server/auth/local-auth.ts`，通过 Credentials provider 创建本地测试用户和 cookie session。

`appRouter` 是 tRPC API 的根路由对象，目前只暴露 `agent`。`createTRPCContext` 是每个 tRPC 请求的上下文工厂，会调用 `getServerAuthSession({ req, res })` 获取当前会话，并把 `session` 与 `prisma` 放进 `ctx`。`publicProcedure` 和 `protectedProcedure` 是路由实现时使用的过程基类，其中 `protectedProcedure` 会通过中间件校验 `ctx.session.user`，失败时抛出 `UNAUTHORIZED`。

`agentRouter` 是当前最重要的业务路由，包含 `create`、`save`、`getAll`、`findById`、`deleteById`。其中多数写操作和用户私有查询使用 `protectedProcedure`，`findById` 使用 `publicProcedure`，这意味着只要知道 agent id 就可以查询未删除 agent 及其任务；这是设计选择，也可能是后续审计点。

## 运行流程

认证流程从浏览器或组件调用开始。`SessionProvider` 在 `next/src/pages/_app.tsx` 包裹全应用，组件通过 `useSession`、`signIn`、`signOut` 或项目封装的 `useAuth` 发起认证相关操作。请求命中 `/api/auth/*` 后进入 `pages/api/auth/[...nextauth].ts`，NextAuth 根据 `authOptions(req, res)` 选择 OAuth provider 或开发 Credentials provider，并通过 Prisma 写入或读取 `User`、`Account`、`Session` 等表。之后前端再次调用 `useSession` 时，会拿到经过 callback 扩展后的 session。

tRPC 流程从 `utils/api.ts` 创建的 `api` 对象开始。`api.withTRPC(...)` 把 tRPC 能力注入应用，组件或 hook 使用类似 `api.agent.create.useMutation`、`api.agent.getAll.useQuery` 的方式调用。请求被批量发送到 `/api/trpc`，进入 `pages/api/trpc/[trpc].ts`。handler 使用 `appRouter` 匹配具体过程，使用 `createTRPCContext` 生成上下文，再进入 `agentRouter` 的 query 或 mutation。业务逻辑通过 `ctx.prisma` 或直接导入的 `prisma` 访问数据库，必要时还会调用 OpenAI SDK 生成 agent 名称。

## 上下游依赖

上游主要是前端页面、组件和 hooks。认证上游包括 `useAuth`、登录页、侧边栏账号区域和依赖 `useSession` 的工具组件。tRPC 上游包括 `useAgent`、agent 页面、左侧历史列表等，它们通过 `utils/api.ts` 的类型安全客户端访问 `/api/trpc`。

下游包括 NextAuth、tRPC、Prisma、数据库、环境变量和外部 OAuth/OpenAI 服务。数据库模型在 `next/prisma/schema.prisma` 中，认证依赖 `User`、`Account`、`Session`、`OrganizationUser` 等模型，agent API 依赖 `Agent`、`AgentTask`。环境变量由 `next/src/env/schema.mjs`、`next/src/env/server.mjs` 校验和导出，关键项包括 `DATABASE_URL`、`NEXTAUTH_SECRET`、`NEXTAUTH_URL`、OAuth client id/secret、`OPENAI_API_KEY` 等。外部服务地址或 OAuth 站点在文档中不展开，统一可理解为 `[URL已移除]`。

## 修改时最容易踩的坑

第一，`pages/api` 文件只是入口，不应把大量业务逻辑塞进这里。新增 tRPC 能力时，优先在 `server/api/routers` 下新增 router，再挂到 `server/api/root.ts`，而不是在 `pages/api/trpc/[trpc].ts` 里分支处理。

第二，认证配置是运行时依赖 `req`、`res` 的函数，不是静态对象。`authOptions(req, res)` 会影响开发 Credentials 登录、cookie、session callback 等行为，改动时要同时理解 `server/auth/index.ts` 和 `local-auth.ts`。

第三，`protectedProcedure` 只保证有登录用户，不自动保证资源归属。像 `deleteById` 使用 `userId` 过滤是正确方向；如果新增按 id 查询或修改接口，需要显式加 `userId`、`deleteDate` 等条件，否则可能越权。

第四，`findById` 当前是公开过程。根据当前片段推断，这是为了分享或直接访问 agent 结果页，但它会返回任务列表。若要改为私有，需要同步调整前端未登录访问体验。

第五，`agentRouter.create` 会在有 `OPENAI_API_KEY` 时调用 OpenAI SDK，失败后降级使用原始 goal。修改这里时要保持失败不阻断创建流程，否则外部服务波动会影响核心保存能力。

第六，`utils/api.ts` 的 `superjson` 必须与服务端 `server/api/trpc.ts` 的 transformer 保持一致，否则日期等复杂类型序列化可能出现不一致。

## 推荐阅读顺序

1. 先读 `next/src/pages/api/auth/[...nextauth].ts` 和 `next/src/pages/api/trpc/[trpc].ts`，建立“入口很薄”的整体印象。
2. 再读 `next/src/utils/api.ts` 和 `next/src/pages/_app.tsx`，理解前端如何接入 tRPC 与 SessionProvider。
3. 接着读 `next/src/server/auth/index.ts`、`next/src/server/auth/auth.ts`、`next/src/server/auth/local-auth.ts`，掌握认证配置、PrismaAdapter 和开发登录差异。
4. 然后读 `next/src/server/api/trpc.ts`、`next/src/server/api/root.ts`，理解 context、router、procedure 的分层。
5. 最后读 `next/src/server/api/routers/agentRouter.ts`，结合 `next/prisma/schema.prisma` 中的 `Agent`、`AgentTask`、`User`、`Session` 模型，看一次完整业务请求如何落到数据库。
