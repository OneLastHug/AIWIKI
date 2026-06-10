# 文件：next/prisma/schema.prisma

## 一句话定位

`next/prisma/schema.prisma` 是 Next 应用的数据契约中心：它定义 Prisma Client 的生成方式、MySQL 数据源，以及 AgentGPT 在认证、组织、OAuth 凭据、Agent 运行记录和任务持久化上的数据库模型。

## 它暴露/定义了什么

这个文件首先定义 `generator client`，让 Prisma 生成 `@prisma/client`，供服务端 TypeScript 代码以 `prisma.user`、`prisma.agent`、`prisma.agentTask` 等 delegate 形式访问数据库。`datasource db` 指向 `DATABASE_URL`，数据库类型为 `mysql`，并设置 `relationMode = "prisma"`，说明关系约束主要由 Prisma 层管理，而不是完全依赖数据库外键。

模型大体分四组：

`Account`、`Session`、`User`、`VerificationToken` 是 NextAuth 适配器需要的核心表。`User` 额外扩展了 `superAdmin`、`createDate`、`organizations` 等业务字段。

`Organization`、`OrganizationUser` 表示组织与用户的多对多关系，`OrganizationUser.role` 保存成员角色，软删除字段使用 `delete_date`。

`OAuthCredentials` 保存第三方 OAuth 安装或授权流程中的状态、回调地址、加密 token、scope 和过期时间。它没有显式 Prisma relation，更多像按 `user_id`、`organization_id` 手工关联的凭据表。

`Agent`、`AgentTask`、`Run`、`NewRun`、`Task` 是 AgentGPT 业务数据。当前代码主要使用 `Agent` 和 `AgentTask`；`NewRun` 映射到数据库表 `agent_run`，`Task` 映射到 `agent_task`，根据当前片段推断，它们可能是新旧运行记录模型并存或迁移中的结构，依据是 `AgentTask` 未使用 `@@map`，而 `Task` 显式映射到同名业务表 `agent_task`。

## 谁调用它

直接读取该文件的是 Prisma 工具链：安装、生成 client、迁移或数据库同步时，Prisma CLI 会根据这里生成 `@prisma/client` 类型和查询 API。

运行时代码不直接 import `schema.prisma`，而是通过生成物间接依赖它。`next/src/server/db.ts` 创建 `PrismaClient` 实例并导出 `prisma`。`next/src/server/auth/index.ts` 把这个实例交给 `PrismaAdapter(prisma)`，因此 NextAuth 会按照 `Account`、`Session`、`User`、`VerificationToken` 的结构读写认证数据。`next/src/server/api/routers/agentRouter.ts` 通过 `ctx.prisma.agent.create`、`prisma.agentTask.create`、`prisma.agent.findMany` 等调用 Agent 相关模型。前端 `next/src/hooks/useAgent.ts` 只 import `Agent as PrismaAgent` 类型，也依赖这个 schema 生成的类型定义。

另外，`next/prisma/useMysql.sh`、`next/prisma/useSqlite.sh` 会操作 schema 文件，用于在不同数据库 schema 之间切换；这是部署或本地开发层面的调用关系。

## 它调用谁

`schema.prisma` 本身是声明式配置，不主动调用代码。它依赖的是 Prisma 运行时和数据库：`generator client` 调用 Prisma 的 `prisma-client-js` 生成器，`datasource db` 通过环境变量 `DATABASE_URL` 连接 MySQL。运行时的真实查询由生成的 Prisma Client 发起，再落到 MySQL 表、索引、唯一约束和 Prisma 关系解析上。

从模型关系看，`Account.user`、`Session.user`、`Agent.user`、`AgentTask.agent`、`Run.user`、`Task.run`、`OrganizationUser.user`、`OrganizationUser.organization` 定义了 Prisma 层的关联路径。带 `onDelete: Cascade` 的关系会影响用户或 agent 删除时的关联数据处理语义。

## 核心流程

认证流程中，用户登录后 NextAuth Prisma Adapter 会按标准模型写入或更新 `User`、`Account`、`Session`。随后 `authOptions` 的 `session` callback 会用 `prisma.session.findFirstOrThrow` 找到该用户最新 session，并用 `prisma.organizationUser.findMany({ include: { organization: true } })` 加载组织成员关系，最终把 `accessToken`、`user.id`、`superAdmin`、`organizations` 挂到 session 上。

Agent 保存流程中，前端通过 tRPC 调用 `agentRouter.create`，服务端先生成或回退 agent 名称，再写入 `Agent`，字段包括 `name`、`goal`、`userId`。执行完成后，`agentRouter.save` 会校验 agent 属于当前用户，然后把消息数组逐条写成 `AgentTask`，保存 `type`、`status`、`info`、`value` 等内容。历史列表通过 `Agent.deleteDate = null` 做软删除过滤，详情页通过 `include: { tasks: ... }` 拉取任务时间线。

组织和 OAuth 凭据流程在当前片段中只看到 schema 和 session callback 的组织读取；`OAuthCredentials` 的写入方未在已读片段中出现，因此只能根据字段推断它服务于外部 provider 的授权状态和 token 存储。

## 关键函数的高层作用

这个文件没有传统意义上的函数。它的“核心接口”是模型定义和生成后的 Prisma delegate。

`PrismaClient` 是 schema 生成的统一数据库入口，由 `next/src/server/db.ts` 包装成全局复用实例，避免开发热更新时重复创建连接。

`PrismaAdapter(prisma)` 使用 `Account`、`Session`、`User`、`VerificationToken` 的字段约定实现 NextAuth 的用户、账号、session、验证 token 持久化。

`agent`、`agentTask` delegate 是业务侧最关键的生成接口：`agent.create/findMany/findFirstOrThrow/updateMany` 负责 agent 生命周期，`agentTask.create` 负责保存执行过程中的消息与任务记录。

`OrganizationUser` 的 relation delegate 让 session callback 能通过 `include.organization` 一次拿到组织名称和角色，这是用户权限上下文的来源之一。

## 修改风险

最高风险是改动 NextAuth 标准模型字段。`Account`、`Session`、`User`、`VerificationToken` 的字段名、唯一索引和关系如果不兼容 `@next-auth/prisma-adapter`，登录、session 查询、账号绑定和本地开发登录都会受影响。

第二类风险是关系和删除语义。`Account`、`Session`、`Agent`、`AgentTask` 使用 `onDelete: Cascade`，更改 relation、外键字段或 `relationMode` 后，用户删除、agent 删除、任务清理可能出现孤儿数据或意外级联。由于当前 datasource 使用 `relationMode = "prisma"`，不要假设数据库层一定存在完整外键约束。

第三类风险是命名风格混杂。旧模型使用 `userId/createDate/deleteDate`，组织和 OAuth、新运行模型使用 `user_id/create_date/delete_date` 并配合 `@@map` 或 `@map`。改名时不仅要迁移数据库列，还要同步所有 Prisma 查询代码和生成类型，否则 TypeScript 编译和运行查询都会失败。

第四类风险是 `AgentTask` 与 `Task` 的表意接近。`AgentTask` 是当前 agent 历史消息使用的模型；`Task` 则映射到数据库表 `agent_task` 并关联 `NewRun`。如果新增迁移或重命名表，容易把两套任务模型混在一起，导致历史详情、运行记录或迁移脚本读写错表。

第五类风险是索引和查询性能。`agentRouter.getAll` 依赖 `userId/deleteDate/createDate` 过滤排序，`findById` 会按 agent 拉取 tasks 并按 `createDate` 排序。删除这些索引或改变字段类型，会直接影响侧边栏历史列表和 agent 详情页性能。
