# 子系统：next/src/server/api

## 解决什么问题

`next/src/server/api` 是这个 Next.js 应用的类型安全后端 API 层，基于 tRPC 组织服务端路由、请求上下文和权限边界。它把前端页面、React hooks 与数据库操作连接起来：前端通过 `src/utils/api.ts` 生成的 `api.agent.*` hooks 发起请求，Next API 路由 `src/pages/api/trpc/[trpc].ts` 将请求交给 `appRouter`，再由本目录内的 router 执行业务逻辑。

从当前代码看，这个子系统目前主要服务 Agent 历史记录能力：创建 Agent、保存任务快照、查询当前用户的 Agent 列表、按 id 读取 Agent 与任务、软删除 Agent。它不是 Agent 自动执行、对话推理或工具调用的核心实现；那些运行期逻辑更多分布在 `src/services/agent/*`、`src/hooks/useAgent.ts` 和前端状态管理中。本目录更像“持久化 API 和访问控制层”。

## 相关目录和文件

`src/server/api/trpc.ts` 定义 tRPC 基础设施，包括请求上下文、`createTRPCRouter`、`publicProcedure`、`protectedProcedure`。这里会把 NextAuth session 和 Prisma client 注入到 resolver 的 `ctx` 中。

`src/server/api/root.ts` 是 API 总路由入口，目前只挂载了 `agent: agentRouter`，并导出 `AppRouter` 类型，供前端类型推导使用。

`src/server/api/routers/agentRouter.ts` 是当前唯一业务 router，封装 Agent 的创建、保存、查询和删除。

与它直接协作的目录包括：`src/pages/api/trpc/[trpc].ts` 负责把 tRPC router 暴露为 Next API endpoint；`src/utils/api.ts` 负责生成前端 `api` 客户端；`src/pages/_app.tsx` 使用 `api.withTRPC` 包装应用；`src/hooks/useAgent.ts`、`src/components/drawer/LeftSidebar.tsx`、`src/pages/agent/index.tsx` 是主要调用方。数据模型来自 `prisma/schema.prisma` 中的 `Agent`、`AgentTask`、`User`。认证依赖位于 `src/server/auth/*`，数据库连接位于 `src/server/db.ts`。

## 核心对象

`createTRPCContext` 是每次 tRPC 请求的上下文工厂。它从 Next 请求/响应对象中读取 server session，并返回包含 `session` 和 `prisma` 的上下文。业务 resolver 通过 `ctx.session` 判断用户，通过 `ctx.prisma` 访问数据库。

`createTRPCRouter` 是 router 构造器，所有子路由都应通过它创建，以继承统一的 transformer、context 和错误格式。

`publicProcedure` 表示无需登录即可调用的 procedure。当前 `agentRouter.findById` 使用它，因此任何知道 Agent id 的请求都可以读取未删除 Agent 及其 tasks。是否符合产品预期需要结合页面分享逻辑判断；根据当前片段推断，它可能用于公开访问某个 Agent 运行结果，因为查询条件没有限制 `userId`。

`protectedProcedure` 通过 `enforceUserIsAuthed` 中间件要求存在 `ctx.session.user`。当前 `create`、`save`、`getAll`、`deleteById` 都使用它，确保写入和个人列表读取必须登录。

`agentRouter` 是核心业务路由。`create` 接收 `goal`，尝试用 OpenAI 生成短名称，失败或未配置 key 时退回使用 goal；`save` 校验 Agent 属于当前用户后批量写入 `AgentTask`；`getAll` 返回当前用户最近 20 个未删除 Agent；`findById` 返回单个 Agent 及按创建时间升序排列的 tasks；`deleteById` 通过写入 `deleteDate` 做软删除。

## 运行流程

前端组件调用 `api.agent.create.useMutation`、`api.agent.getAll.useQuery` 等 hooks。`src/utils/api.ts` 中的 `httpBatchLink` 会把请求发送到 `/api/trpc`，并使用 `superjson` 做序列化。`src/pages/api/trpc/[trpc].ts` 通过 `createNextApiHandler` 接收请求，绑定 `appRouter` 和 `createTRPCContext`。

请求进入服务端后，`createTRPCContext` 先读取 session，再把 session 与 Prisma 放入 ctx。然后 tRPC 根据路径分派到 `appRouter.agent.*`。如果 procedure 是 `protectedProcedure`，会先执行登录校验；通过后进入具体 resolver。resolver 使用 Zod schema 校验输入，例如 `createAgentParser`、`saveAgentParser`，然后执行 Prisma 查询或写入，结果再经 tRPC 返回给前端 React Query 缓存。

## 上下游依赖

上游调用方主要是前端 UI 和 hooks：`src/hooks/useAgent.ts` 创建和保存 Agent；`src/components/drawer/LeftSidebar.tsx` 读取 Agent 列表；`src/pages/agent/index.tsx` 查询、展示和删除单个 Agent。`src/pages/_app.tsx` 提供 tRPC React 集成，使这些 hooks 可以在组件中工作。

下游依赖包括 NextAuth、Prisma、MySQL、Zod、OpenAI SDK 和环境变量。`protectedProcedure` 依赖 `src/server/auth` 返回正确 session；所有数据读写依赖 `src/server/db.ts` 暴露的 Prisma client；Agent 和任务字段必须与 `prisma/schema.prisma` 中的 `Agent`、`AgentTask` 保持一致。`generateAgentName` 依赖 `env.OPENAI_API_KEY`，但它是可选增强能力，不应阻断 Agent 创建。

## 修改时最容易踩的坑

第一，权限边界不要混淆。`findById` 当前是公开接口，只按 `id` 和 `deleteDate` 查询，不校验所有者；如果新增敏感字段或任务内容包含私密信息，应重新评估是否改成 `protectedProcedure` 或加入分享权限模型。

第二，`save` 目前是追加写入任务，不会清空旧 tasks，也没有去重逻辑，且 `sort` 固定为 `0`。如果前端多次保存同一个 Agent，可能产生重复任务；如果后续依赖排序，应补齐稳定排序字段或改用事务更新。

第三，注意 Prisma 使用方式不完全一致：`create` 使用 `ctx.prisma`，`save` 里直接导入 `prisma`。这不一定是 bug，但测试、mock 或多租户上下文会更难统一。新增 resolver 时建议优先沿用 `ctx.prisma`。

第四，OpenAI 生成名称在请求链路内同步执行，失败会吞掉错误并回退，但延迟仍会影响 `create`。如果创建性能变重要，可以考虑异步补全名称或加超时策略。

第五，`protectedProcedure` 保证 `ctx.session.user` 存在，但业务代码仍使用可选链。新增代码不要因此误以为 userId 可能为空；真正需要处理的是 session user 是否包含 `id` 字段，以及 NextAuth 类型声明是否完整。

## 推荐阅读顺序

先读 `src/pages/api/trpc/[trpc].ts`，理解 Next API 如何接入 tRPC。然后读 `src/server/api/trpc.ts`，掌握 context、router、public/protected procedure 的基础约定。第三步读 `src/server/api/root.ts`，看 API 命名空间如何挂载。第四步读 `src/server/api/routers/agentRouter.ts`，按 `create`、`save`、`getAll`、`findById`、`deleteById` 理解业务边界。最后对照 `src/utils/api.ts`、`src/hooks/useAgent.ts`、`src/pages/agent/index.tsx` 和 `prisma/schema.prisma`，把前端调用、服务端 resolver、数据库模型串起来。
