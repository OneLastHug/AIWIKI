# 子系统：next/src/server/api/routers

## 解决什么问题

`next/src/server/api/routers` 是后端 tRPC 业务路由目录，负责把具体业务能力组织成可被前端类型安全调用的 API。当前目录只有 `agentRouter.ts`，因此这个子系统的核心职责可以概括为：提供 Agent 的创建、保存运行结果、列表查询、详情查询和软删除能力。

它不是 HTTP handler 本身，也不直接决定请求 URL。它定义的是 tRPC router 内部的过程，即 `agent.create`、`agent.save`、`agent.getAll`、`agent.findById`、`agent.deleteById` 这些可调用端点。真正的 Next.js API 入口在 `next/src/pages/api/trpc/[trpc].ts`，那里把 `appRouter` 接到 `createNextApiHandler` 上。`routers` 目录只关心业务过程、输入校验、鉴权过程选择、数据库读写和少量外部服务调用。

## 相关目录和文件

`next/src/server/api/routers/agentRouter.ts` 是当前目录的主体文件，定义 Agent 相关业务路由。

`next/src/server/api/root.ts` 是路由聚合层，将 `agentRouter` 挂到 `appRouter` 的 `agent` 命名空间下。前端最终看到的是 `api.agent.*`，这个命名来自这里。

`next/src/server/api/trpc.ts` 是 tRPC 基础设施层，定义 `createTRPCRouter`、`publicProcedure`、`protectedProcedure` 和请求上下文。`agentRouter.ts` 依赖这些对象来创建 router，并区分公开接口和登录后接口。

`next/src/pages/api/trpc/[trpc].ts` 是 Next.js API 路由入口，负责把 `appRouter`、`createTRPCContext` 交给 tRPC 的 Next adapter。

`next/src/server/auth`、`next/src/pages/api/auth/[...nextauth].ts` 提供会话来源。`protectedProcedure` 会基于 `ctx.session.user` 判断调用方是否已登录。

`next/src/server/db` 提供 Prisma 客户端。`agentRouter.ts` 中既通过 `ctx.prisma` 访问数据库，也直接导入了 `prisma`。这两种用法在当前代码中混用。

`next/src/types/message`、`next/src/types/task` 提供任务消息结构和任务类型常量，主要服务于 `agent.save` 对输入任务列表的校验和落库。

前端调用侧主要在 `next/src/hooks/useAgent.ts`、`next/src/pages/agent/index.tsx`、`next/src/components/drawer/LeftSidebar.tsx`。这些位置通过 `api.agent.*.useQuery` 或 `useMutation` 消费本目录暴露的过程。

## 核心对象

`agentRouter` 是本目录最核心的导出对象。它由 `createTRPCRouter` 创建，内部包含五个过程。

`createAgentParser` 是 `agent.create` 的输入 schema，当前只要求传入 `goal: string`。`CreateAgentProps` 是由 Zod schema 推导出的 TypeScript 类型。

`saveAgentParser` 是 `agent.save` 的输入 schema，要求传入 `id: string` 和 `tasks: messageSchema[]`。它把前端产生的执行消息转换为可写入 `agentTask` 表的数据。

`generateAgentName(goal)` 是创建 Agent 时的辅助函数。它在存在 `OPENAI_API_KEY` 时调用 OpenAI chat completion，用用户目标生成一个简短名称；失败或没有 key 时返回 `undefined`，调用方会回退到原始 `goal`。

`protectedProcedure` 用于需要登录的过程，包括 `create`、`save`、`getAll`、`deleteById`。这些接口都会依赖 `ctx.session.user.id` 做用户隔离。

`publicProcedure` 当前只用于 `findById`。这意味着只要知道 Agent id，就可以读取未软删除 Agent 及其 tasks。根据当前片段推断，这可能是为了支持分享或公开查看历史运行记录；依据是 `findById` 没有校验 `userId`，只检查 `deleteDate: null`。

## 运行流程

请求从前端 `api.agent.*` 调用开始。tRPC client 会把调用发送到 Next.js API 路由 `next/src/pages/api/trpc/[trpc].ts`，该入口使用 `createNextApiHandler` 接收请求。

请求进入后，`createTRPCContext` 会执行。它通过 `getServerAuthSession` 从 NextAuth 获取当前 session，并把 `session` 与 `prisma` 注入上下文。随后 tRPC 根据调用路径找到 `appRouter` 中的 `agentRouter`。

以 `agent.create` 为例，流程是先通过 `createAgentParser` 校验输入，再由 `protectedProcedure` 确认用户已登录，然后尝试调用 `generateAgentName` 生成名称，最后创建 `agent` 记录，写入 `name`、`goal` 和 `userId`。

`agent.save` 会先校验 Agent 是否属于当前用户，再把输入的 tasks 映射为多条 `agentTask.create`。如果 task 类型是 `MESSAGE_TYPE_TASK`，会额外保存 `status`。当前实现使用 `Promise.all` 并发写入任务，完成后返回原 Agent。

`agent.getAll` 查询当前用户最近创建的 20 个未删除 Agent，按 `createDate` 倒序排列。`agent.findById` 查询单个未删除 Agent，并按 `createDate` 正序包含其 tasks。`agent.deleteById` 不物理删除数据，而是用 `deleteDate = new Date()` 做软删除。

## 上下游依赖

上游入口是 tRPC 的 Next API handler 和 `appRouter` 聚合层。`routers` 目录不直接暴露 REST URL，而是被 `root.ts` 收编成一个类型化 API 树。

鉴权上游来自 NextAuth session。所有 `protectedProcedure` 都依赖 `ctx.session.user` 存在，并进一步使用 `ctx.session.user.id` 限定用户数据范围。

数据下游是 Prisma 管理的 `agent` 与 `agentTask` 数据模型。根据当前片段推断，Agent 至少包含 `id`、`name`、`goal`、`userId`、`createDate`、`deleteDate` 等字段；AgentTask 至少包含 `agentId`、`type`、`status`、`info`、`value`、`sort`、`createDate` 等字段。依据是 `agentRouter.ts` 中的 create、findMany、findFirstOrThrow、updateMany 和 include tasks 用法。

外部服务下游是 OpenAI SDK。`generateAgentName` 依赖 `env.OPENAI_API_KEY` 和模型 `gpt-3.5-turbo`，只影响名称生成，不影响 Agent 创建主流程，因为失败会回退到用户输入的 goal。

前端下游主要是 Agent 创建/保存 hook、侧边栏列表和 Agent 页面详情。由于 tRPC 会从 `AppRouter` 推导类型，后端过程名称、输入 schema、返回结构变化会直接影响这些调用点的类型检查和运行行为。

## 修改时最容易踩的坑

第一，`findById` 是 `publicProcedure`。如果新增敏感字段 include，或希望 Agent 详情只允许拥有者访问，需要同时调整鉴权过程和前端访问逻辑，否则会扩大公开数据面。

第二，`agent.save` 直接批量追加 tasks，没有先清理旧任务，也没有事务包裹。重复保存同一个 Agent 可能产生重复任务；部分写入失败时也可能留下不完整数据。涉及保存语义时应优先确认产品期望，是追加、覆盖，还是幂等更新。

第三，当前文件混用了 `ctx.prisma` 和直接导入的 `prisma`。这在功能上通常可运行，但测试、上下文替换和事务扩展会更难。新增代码最好优先沿用 `ctx.prisma`，除非有明确理由。

第四，`generateAgentName` 在请求链路中同步等待外部模型返回。OpenAI 变慢会拖慢 `agent.create`。它虽然有异常兜底，但没有超时控制；修改这里时要注意创建 Agent 的核心路径不应被命名生成强依赖阻塞。

第五，输入校验只校验结构，不校验字符串长度、空白 goal、tasks 数量等业务限制。若前端传入极长 goal 或大量 tasks，可能造成成本、延迟或数据库压力问题。

第六，软删除只在部分查询中通过 `deleteDate: null` 过滤。新增查询时必须显式考虑是否排除软删除数据，否则删除后的 Agent 可能重新出现在某些视图中。

## 推荐阅读顺序

1. 先读 `next/src/server/api/trpc.ts`，理解 `ctx`、`publicProcedure`、`protectedProcedure` 的含义。
2. 再读 `next/src/server/api/root.ts`，看 `agentRouter` 如何进入 `appRouter`。
3. 然后读 `next/src/server/api/routers/agentRouter.ts`，重点看每个 procedure 的输入 schema、鉴权类型和 Prisma 查询条件。
4. 接着读 `next/src/pages/api/trpc/[trpc].ts`，确认这些过程如何被 Next.js API handler 暴露。
5. 最后读调用侧 `next/src/hooks/useAgent.ts`、`next/src/pages/agent/index.tsx`、`next/src/components/drawer/LeftSidebar.tsx`，把后端过程和实际页面行为对应起来。
