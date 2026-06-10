# 目录：next/prisma

## 它负责什么

`next/prisma` 是 Next.js 应用的数据模型与 Prisma ORM 配置目录。它不包含业务代码本身，而是定义数据库结构、Prisma Client 的生成依据，以及本地数据库类型切换脚本。整个目录的核心是 `schema.prisma`：它声明了 `generator client`、`datasource db`，并描述应用会持久化哪些实体。

从当前片段看，这个目录服务于三类主要数据：

第一类是认证与会话数据，包括 `User`、`Account`、`Session`、`VerificationToken`。这些模型配合 `@next-auth/prisma-adapter` 使用，是 NextAuth 登录、第三方账号绑定、session 查询的数据库基础。

第二类是组织和授权上下文，包括 `Organization`、`OrganizationUser`、`OAuthCredentials`。其中 `OrganizationUser` 把用户和组织关联起来，并保存 `role`；`OAuthCredentials` 保存第三方 OAuth 安装或授权流程中的状态、回调地址、加密 token 字段等。

第三类是 AgentGPT 自身的运行数据，包括 `Agent`、`AgentTask`、`Run`、`NewRun`、`Task`。其中 `Agent` 和 `AgentTask` 是当前业务读写最直接的模型，用于保存用户创建的 agent、目标、任务消息、任务状态和软删除时间。

## 直接子目录地图

`next/prisma` 当前没有直接子目录，是一个扁平目录。它下面主要有三类文件：

`schema.prisma` 是数据库 schema 主文件，也是 `prisma generate`、`prisma db push`、`prisma migrate deploy` 等命令读取的关键入口。

`useSqlite.sh` 是数据库方言切换辅助脚本，会备份当前 `schema.prisma` 为 `schema.prisma.mysql`，再把 provider 从 `mysql` 替换为 `sqlite`，并移除 MySQL 专属字段注解，例如 `@db.Text`、`@db.VarChar(...)`，同时把 `Json` 替换成 `String`。根据当前片段推断，它主要用于本地或轻量环境测试，而不是生产主路径。

`useMysql.sh` 是反向恢复脚本，会删除当前 `schema.prisma`，再把 `schema.prisma.mysql` 移回 `schema.prisma`。这意味着使用 SQLite 脚本后，目录里可能临时出现 `schema.prisma.mysql`，但它被 `.gitignore` 的 `schema.prisma*` 模式忽略。

## 关键入口

最关键的入口是 `next/prisma/schema.prisma`。文件顶部的 `generator client { provider = "prisma-client-js" }` 决定项目生成 JavaScript/TypeScript Prisma Client；`datasource db` 使用 `env("DATABASE_URL")` 读取数据库连接，默认 provider 是 `mysql`，并设置 `relationMode = "prisma"`。

运行入口在 `next/package.json` 和 `next/entrypoint.sh`。`next/package.json` 的 `postinstall` 会执行 `prisma generate`，表示依赖安装后自动根据 `schema.prisma` 生成 Prisma Client。`next/entrypoint.sh` 会等待数据库可用，然后执行 `npx prisma migrate deploy --name init`、`npx prisma db push`，最后再执行 `npx prisma generate`。从这个流程看，容器启动时会尝试确保数据库结构和 Prisma Client 都处于可用状态。

代码侧的 Prisma Client 入口是 `next/src/server/db.ts`。这里创建并导出 `prisma` 单例：开发环境下把 client 缓存在 `globalThis.prisma`，避免 Next.js 热更新反复创建连接；日志策略则在开发环境输出 `query`、`error`、`warn`，生产环境只保留 `error`。

## 主流程位置

认证主流程在 `next/src/server/auth/index.ts`。这里通过 `PrismaAdapter(prisma)` 把 NextAuth 接到 Prisma 上，因此 `User`、`Account`、`Session`、`VerificationToken` 这些模型不是孤立存在的表定义，而是 NextAuth adapter 会直接使用的持久化层。`session` callback 中还会读取 `prisma.session.findFirstOrThrow` 和 `prisma.organizationUser.findMany`，把 session token、用户 id、`superAdmin`、组织列表和角色写入前端可见的 session 对象。

Agent 数据主流程在 `next/src/server/api/routers/agentRouter.ts`。`create` mutation 会写入 `ctx.prisma.agent.create`，保存用户目标和生成出的 agent 名称；`save` mutation 会先按 `id` 和 `userId` 查找 `Agent`，再把消息数组写成多条 `AgentTask`；`getAll` 查询当前用户未软删除的 agent；`findById` 会带上 `tasks` 关联并按创建时间排序；`deleteById` 不是物理删除，而是写入 `deleteDate`。

环境变量校验在 `next/src/env/schema.mjs`。其中 `DATABASE_URL` 被声明为必须符合 URL 格式，这说明 `schema.prisma` 的 datasource 并不单独决定连接是否有效，应用启动还依赖环境 schema 的校验。

## 推荐阅读顺序

建议先读 `next/prisma/schema.prisma` 的顶部配置，明确 provider、`DATABASE_URL`、Prisma Client 生成方式。然后按模型分组阅读：先看 NextAuth 相关的 `User`、`Account`、`Session`、`VerificationToken`，再看组织相关的 `Organization`、`OrganizationUser`、`OAuthCredentials`，最后看业务运行相关的 `Agent`、`AgentTask`、`Run`、`NewRun`、`Task`。

接着读 `next/src/server/db.ts`，理解应用如何创建 Prisma Client，以及为什么开发环境需要全局缓存。

之后读 `next/src/server/auth/index.ts`，把 schema 中的认证表和实际 session 生成逻辑对应起来。这里能看到 `OrganizationUser` 为什么会被放进 session，也能理解 `superAdmin` 字段的用途。

最后读 `next/src/server/api/routers/agentRouter.ts`，观察 `Agent`、`AgentTask` 的真实业务读写路径。读完这里，再回头看 `schema.prisma` 里的索引，例如 `@@index([userId, deleteDate, createDate])`、`@@index([agentId])`，会更容易理解它们为什么存在。

## 常见误区

不要把 `next/prisma` 理解成“迁移目录”。当前目录里没有 `migrations` 子目录，核心是 schema 和数据库切换脚本。实际启动脚本虽然调用了 `prisma migrate deploy`，但从当前目录结构看，仓库片段没有提供完整迁移历史；因此数据库结构更像是依赖 `schema.prisma` 和 `prisma db push` 同步。

不要认为所有模型都在当前业务代码中同等活跃。`Agent`、`AgentTask`、`User`、`Session`、`OrganizationUser` 在已查看代码中有直接读写；`Run`、`NewRun`、`Task` 从 schema 看属于 agent 运行记录相关模型，但在当前检索片段里没有看到主要调用点。根据当前片段推断，它们可能是旧版、迁移中或预留的新运行结构，判断时应继续结合更深层 router/service 代码。

不要随意运行 `useSqlite.sh`。它会原地改写 `schema.prisma`，并生成 `schema.prisma.mysql` 备份；虽然这是设计好的切换脚本，但会改变当前工作区中的 Prisma schema。学习源码时只需要知道它的作用，不应把它当成普通启动步骤。

不要忽略 `relationMode = "prisma"`。这表示关系约束的处理方式更依赖 Prisma 层，而不是完全交给数据库外键行为。阅读 `onDelete: Cascade`、`@relation`、索引和唯一约束时，要结合 Prisma 的关系模式理解。

不要只看 `schema.prisma` 就推断所有业务行为。比如 `deleteDate` 只是字段定义，真正的软删除语义体现在 `agentRouter.deleteById` 写入时间，以及 `getAll`、`findById` 查询时过滤 `deleteDate: null`。数据模型负责提供结构，主流程仍然要回到 `next/src/server/...` 的调用点确认。
