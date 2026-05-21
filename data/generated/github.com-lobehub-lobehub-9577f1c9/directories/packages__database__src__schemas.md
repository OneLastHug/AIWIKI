# 目录：packages/database/src/schemas

## 它负责什么

`packages/database/src/schemas` 是 LobeHub 数据库包的 Drizzle ORM schema 层，负责把业务概念映射成 PostgreSQL 表、字段、索引、主外键、插入/查询类型以及部分 Drizzle 关系声明。它不是具体业务服务层，也不是迁移文件目录；它更像数据库结构的“源码定义中心”。

从当前目录入口看，`index.ts` 将所有 schema 模块统一导出，供 `packages/database` 内部模型、仓储、服务，以及上层 `src/server`、TRPC、异步任务等模块引用。实际 SQL 迁移通常由 Drizzle 配置和迁移工具根据这些定义生成或维护，迁移文件不在本目录内。

## 关键组成

`_helpers.ts` 是列定义工具集，封装常用 PostgreSQL 类型和时间字段：

- `timestamptz(name)`：带时区的 timestamp。
- `varchar255(name)`：长度 255 的 varchar。
- `createdAt()`、`updatedAt()`、`accessedAt()`：标准时间列。
- `timestamps`：同时包含 `accessedAt`、`createdAt`、`updatedAt` 的对象，供表定义中展开。
- `amountNumeric(name)`：统一金额数值列，使用 `numeric`，精度为 `20,6`，并以 number 模式返回。

`index.ts` 是公共出口，集中 `export * from './xxx'`。目前覆盖的业务域很广，包括：

- Agent 相关：`agent.ts`、`agentSkill.ts`、`agentOperations.ts`、`agentCronJob.ts`、`agentDocuments.ts`、`agentEvals.ts`。
- AI 基础设施和供应商：`aiInfra.ts`、`agentBotProvider.ts`、`systemBotProvider.ts`。
- 用户与权限：`user.ts`、`rbac.ts`、`apiKey.ts`、`betterAuth.ts`、`nextauth.ts`、`oidc.ts`。
- 会话与消息：`session.ts`、`topic.ts`、`message.ts`、`chatGroup.ts`。
- 文件、知识库、RAG：`file.ts`、`rag.ts`、`ragEvals.ts`、`documentHistory.ts`。
- 生成任务：`generation.ts`、`asyncTask.ts`、`task.ts`、`notification.ts`。
- Messenger 集成：`messengerAccountLink.ts`、`messengerInstallation.ts`。
- 用户记忆：`userMemories/index.ts`、`userMemories/persona.ts`。

`relations.ts` 是关系集中定义文件。它既定义了若干多对多连接表，也声明了 Drizzle `relations()` 关系图。当前可见的连接表包括：

- `agentsToSessions`：Agent 与 Session 的多对多关系。
- `filesToSessions`：File 与 Session 的多对多关系。
- `fileChunks`：File 与 RAG chunk 的关联。

这些表普遍包含 `userId`，并通过 `references(..., { onDelete: 'cascade' })` 绑定用户或父实体，体现出“用户隔离 + 级联删除”的设计倾向。

## 上下游关系

上游主要是业务模型设计和 Drizzle/PostgreSQL 类型系统。开发者在这里定义表结构，例如 `pgTable`、`text`、`uuid`、`varchar`、`index`、`primaryKey`、`references` 等。`_helpers.ts` 则提供跨表复用的字段约定，避免时间字段、金额字段在各处写法不一致。

下游主要有三类：

第一类是数据库迁移。根据本仓库 Drizzle 约定推断，schema 变更会影响迁移 SQL 的生成和审查。新增字段、表、索引、外键时，不能只改 schema，还要确保迁移文件与线上数据兼容。

第二类是数据库访问层。仓储、模型、服务会从这里导入表对象，例如 `users`、`sessions`、`messages`、`files`、`chunks` 等，然后用 Drizzle 的 `db.select().from(...).where(...)` 查询。项目约定更偏向显式 `select`、`leftJoin`、`groupBy`，而不是依赖 Drizzle relational query 的 `db.query.xxx.findMany({ with: ... })`。

第三类是类型系统。很多 schema 文件通常会导出 `$inferSelect`、`$inferInsert` 或 `createInsertSchema` 生成的类型/校验结构。当前片段中能看到 `NewFileChunkItem = typeof fileChunks.$inferInsert`，说明 schema 同时承担数据库结构和 TypeScript 数据形状来源的职责。

## 运行/调用流程

典型流程可以这样理解：

1. 某个业务模块需要持久化数据，例如消息、文件、知识库、Agent、用户权限。
2. 对应 schema 文件用 Drizzle `pgTable` 定义表名、字段、默认值、索引、主键和外键。
3. `index.ts` 统一导出这些表对象，调用方通过 `packages/database` 的入口或相对模块拿到表定义。
4. 数据访问层使用表对象构造 SQL，例如 `db.select().from(messages)`、`leftJoin(files, ...)`、`where(eq(...))`。
5. 如果涉及实体间关系，数据库层通常依赖真实外键和连接表；`relations.ts` 提供 Drizzle 层面的关系描述，便于类型和关系表达。
6. 当 schema 发生结构变化时，迁移系统需要生成/维护对应 SQL，使真实 PostgreSQL 表结构与 TypeScript schema 保持一致。

以 `relations.ts` 中的消息相关关系为例，`messagesRelations` 将 `messages` 关联到 `sessions`、`topics`、`threads`、`messageGroups`、父消息、翻译和文件连接表。也就是说，消息本身不是孤立表，而是聊天会话、主题线程、附件和多语言翻译的中心节点之一。

以文件/RAG 相关关系为例，`filesRelations` 连接了消息附件、会话附件、Agent 文件、文档、生成结果、分块任务和嵌入任务；`fileChunks` 再把文件与 `chunks` 关联起来。根据当前片段推断，文件表是知识库、RAG、生成产物和聊天附件之间的重要枢纽。

## 小白阅读顺序

建议先读 `index.ts`。它能最快告诉你这个目录有哪些 schema 模块，以及数据库大致覆盖了哪些业务域。

第二步读 `_helpers.ts`。先理解时间字段、金额字段、varchar helper 这些基础积木，因为很多表都会复用它们。尤其要注意 `timestamps` 不只是 `createdAt` 和 `updatedAt`，还包含 `accessedAt`。

第三步读用户与认证相关文件，例如 `user.ts`、`betterAuth.ts`、`nextauth.ts`、`oidc.ts`、`rbac.ts`。这些通常是其他业务表外键的根。

第四步读聊天主链路：`session.ts`、`topic.ts`、`message.ts`、`agent.ts`。理解 Session、Topic、Message、Agent 之间的关系后，再看 `relations.ts` 会容易很多。

第五步读文件和知识库链路：`file.ts`、`rag.ts`、`documentHistory.ts`、`agentDocuments.ts`。这部分解释了文件如何进入知识库、如何分块、如何和 Agent 或 Topic 关联。

第六步按兴趣阅读扩展域：`generation.ts`、`asyncTask.ts`、`agentEvals.ts`、`ragEvals.ts`、`messengerAccountLink.ts`、`userMemories`。这些更像建立在主业务模型之上的高级功能。

## 常见误区

不要把 `relations()` 当成数据库外键本身。真正的约束来自字段上的 `references()`、`primaryKey()`、`index()` 等定义；`relations()` 更多是 Drizzle 关系图和类型层辅助。

不要新增 schema 文件后忘记改 `index.ts`。如果没有从入口导出，下游模块可能无法统一导入，迁移或类型引用也容易出现割裂。

不要以为改了 schema 就完成数据库变更。结构变更还需要迁移文件配合，尤其是线上已有数据时，要考虑默认值、nullable、回填、索引创建成本和级联删除影响。

不要滥用 Drizzle relational query 的 `with:`。根据本仓库约定，查询层更推荐显式 `db.select()`、`leftJoin()` 和必要时拆成多次简单查询，这样 SQL 更可控，也更容易排查性能问题。

不要忽略 `userId`。许多连接表和业务表都携带 `userId`，这不仅是普通字段，也关系到数据隔离、查询过滤、级联删除和索引设计。

不要随意改变 helper 的语义。比如 `timestamps` 当前包含 `accessedAt`，如果某张表只需要创建/更新时间，就应确认是否该单独使用 `createdAt()`、`updatedAt()`，而不是机械展开 `timestamps`。

不要只看单个表文件。这个目录的真实价值在“表之间的图结构”：消息、会话、文件、Agent、知识库、任务、用户权限互相连接。阅读时要结合 `relations.ts` 和外键字段一起看，才能理解数据模型的完整边界。
