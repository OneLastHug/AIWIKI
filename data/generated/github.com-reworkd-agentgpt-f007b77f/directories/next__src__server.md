# 子系统：next/src/server

## 解决什么问题

`next/src/server` 是 Next.js 应用的服务端边界，主要负责三件事：数据库访问、用户认证会话、类型安全 API。它把 Prisma、NextAuth、tRPC 组合成一个后端运行层，让前端页面、hooks 和 API route 不直接处理数据库连接、鉴权细节或请求上下文。

从当前片段看，这个目录更像 T3 Stack 风格的后端核心：`pages/api/trpc/[trpc].ts` 只负责把请求交给 `appRouter`，真正的业务路由、鉴权中间件和 Prisma 上下文都集中在 `next/src/server/api`；`pages/api/auth/[...nextauth].ts` 则把 NextAuth 的配置委托给 `next/src/server/auth`。

## 相关目录和文件

`next/src/server/db.ts` 定义全局复用的 `prisma` 实例。开发环境下它把 PrismaClient 挂到 `globalThis`，避免 Next.js 热重载时反复创建数据库连接；生产环境则直接创建实例，并按环境控制 Prisma 日志级别。

`next/src/server/auth/index.ts` 是认证配置的聚合层。它创建 `PrismaAdapter(prisma)`，合并通用配置和环境相关配置，并导出 `authOptions` 与 `getServerAuthSession`。其中 session callback 会补充 `session.accessToken`、`session.user.id`、`superAdmin` 和 organizations。

`next/src/server/auth/auth.ts` 是生产 OAuth provider 配置，包含 Google、GitHub、Discord，并设置登录页为 `/signin`。`next/src/server/auth/local-auth.ts` 提供 development 下的本地 Credentials 登录逻辑，根据当前片段推断，它用于绕过外部 OAuth，直接创建或读取本地用户与 session。

`next/src/server/api/trpc.ts` 初始化 tRPC，创建请求上下文、序列化器、公共 procedure 和受保护 procedure。`next/src/server/api/root.ts` 聚合子路由，目前暴露 `agent`。`next/src/server/api/routers/agentRouter.ts` 是 Agent 业务路由，包含创建、保存任务、列表、按 id 查询和软删除。

## 核心对象

`prisma` 是整个服务端的数据访问入口，来自 `next/src/server/db.ts`。它被认证适配器、tRPC context 和业务路由共同使用。

`authOptions(req, res)` 是 NextAuth 的最终配置函数。它会根据 `env.NEXT_PUBLIC_VERCEL_ENV === "development"` 在 `local-auth` 与 `auth.ts` 的 provider 配置之间切换，并通过 `lodash/merge` 合并 `commonOptions`。

`getServerAuthSession(ctx)` 是服务端获取 session 的统一封装，避免各处重复导入和计算 `authOptions`。

`createTRPCContext(opts)` 是每个 tRPC 请求的上下文工厂。它从 Next.js request/response 中读取 session，并返回 `{ session, prisma }`，使 router 内部可以通过 `ctx.session` 和 `ctx.prisma` 访问认证与数据库。

`publicProcedure` 和 `protectedProcedure` 是 API 权限边界。前者允许匿名访问，后者通过 `enforceUserIsAuthed` 检查 `ctx.session.user`，失败时抛出 `TRPCError({ code: "UNAUTHORIZED" })`。

`appRouter` 是 tRPC 的根路由类型来源，`AppRouter` 会被前端 `next/src/utils/api.ts` 用来推导输入输出类型。

`agentRouter` 是当前最主要的业务路由。它使用 zod 校验输入，使用 Prisma 操作 `agent` 与 `agentTask`，并在创建 Agent 时可调用 OpenAI SDK 根据 goal 生成短名称。

## 运行流程

浏览器端通过 `next/src/utils/api.ts` 创建的 tRPC client 访问 `/api/trpc`。请求进入 `next/src/pages/api/trpc/[trpc].ts`，由 `createNextApiHandler` 调用 `appRouter` 和 `createTRPCContext`。

`createTRPCContext` 先调用 `getServerAuthSession`。后者进入 `next/src/server/auth/index.ts`，根据当前环境组装 NextAuth 配置，通过 PrismaAdapter 从数据库读取用户、session、organization 关系，并把业务需要的字段塞回 session。

随后 tRPC procedure 执行业务逻辑。如果调用的是 `protectedProcedure`，会先检查 session 是否存在；例如 `agent.create` 会根据输入 goal 创建 Agent，并把 `userId` 设为当前用户 id。`agent.save` 会先确认 Agent 属于当前用户，再批量写入任务。`agent.getAll` 只返回当前用户未软删除的最近 20 个 Agent。`agent.findById` 是 public procedure，会按 id 查询未删除 Agent 并包含 tasks。`agent.deleteById` 通过设置 `deleteDate` 做软删除。

认证请求则走 `/api/auth/[...nextauth]`。该 API route 调用 `NextAuth(req, res, authOptions(req, res))`，最终还是回到 `next/src/server/auth` 的配置。

## 上下游依赖

上游入口主要是 Next.js API routes：`next/src/pages/api/trpc/[trpc].ts`、`next/src/pages/api/auth/[...nextauth].ts`，以及服务端页面 `next/src/pages/signin.tsx` 中对 `authOptions` 的使用。

下游依赖包括 `@prisma/client`、`@next-auth/prisma-adapter`、`next-auth`、`@trpc/server`、`superjson`、`zod`、`openai` 和环境配置 `next/src/env/server.mjs`、`next/src/env/schema.mjs`。业务类型依赖 `next/src/types/message.ts`、`next/src/types/task.ts`，其中 `messageSchema` 和 `MESSAGE_TYPE_TASK` 决定 Agent task 的写入结构。

横向依赖是前端数据层。`next/src/utils/api.ts` 通过 `AppRouter` 获得端到端类型；`next/src/hooks/useAgent.ts` 引用 `CreateAgentProps`、`SaveAgentProps`，说明 router 的输入类型会外溢到客户端调用代码。

## 修改时最容易踩的坑

第一，`authOptions` 在 `index.ts` 中会原地 `merge(commonOptions, options)`。如果后续给 `commonOptions` 增加可变对象，要注意多次请求之间的共享状态风险。

第二，`protectedProcedure` 只保证 `ctx.session.user` 非空，但业务代码仍要显式按 `userId` 限定数据范围。`agent.save`、`getAll`、`deleteById` 已经这样做；新增接口时不要只依赖“用户已登录”。

第三，`agent.findById` 是 public procedure。它不会验证 Agent 归属，只过滤 `deleteDate: null`。如果 Agent 内容不应公开，这里需要改为受保护 procedure 或增加访问控制。

第四，`agentRouter.ts` 同时使用 `ctx.prisma` 和直接导入的 `prisma`。两者当前指向同一个实例，但测试或替换 context 时会降低可控性。新增逻辑建议优先使用 `ctx.prisma`。

第五，session callback 使用 `findFirstOrThrow` 查询 session。若数据库中 session 状态异常，登录态解析可能直接失败。改动 NextAuth adapter 或 session 存储时要同步验证这里。

第六，`generateAgentName` 依赖 `OPENAI_API_KEY`，失败时静默回退到 goal。调用方不能假设 name 一定是模型生成结果。

## 推荐阅读顺序

先读 `next/src/server/db.ts`，理解 Prisma 单例如何被全局复用。然后读 `next/src/server/auth/index.ts`，重点看 `commonOptions.callbacks.session` 和环境分流。接着读 `next/src/server/api/trpc.ts`，掌握 context、`publicProcedure`、`protectedProcedure` 的边界。之后读 `next/src/server/api/root.ts`，确认路由聚合方式。最后读 `next/src/server/api/routers/agentRouter.ts`，把前面的数据库、认证、tRPC procedure 如何落到业务操作上串起来。
