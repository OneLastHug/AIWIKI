# 目录：packages/database/src/schemas

## 它负责什么

`packages/database/src/schemas` 是 `@lobechat/database` 包里的数据库结构定义层，核心职责是用 Drizzle ORM 描述 PostgreSQL 表、字段、索引、外键、关联关系和类型推导。它不是业务查询层，也不是迁移文件目录，而是“数据库模型的源头”：应用里的 repository、model、service、迁移生成流程都会围绕这些 schema 定义理解数据库形状。

这个目录里的文件大多按业务域平铺组织，例如 agent、message、session、topic、file、rag、generation、auth、rbac 等。每个 schema 文件通常包含一组相关表的 `pgTable` 定义，并导出 Drizzle 推导出的插入类型、查询类型或 zod insert schema。字段命名采用数据库侧的 snake_case，例如 `user_id`、`created_at`；TypeScript 侧通常使用 camelCase 属性，例如 `userId`、`createdAt`。

从当前片段看，这里同时承担两类职责：一类是具体业务表定义，例如 `agent.ts`、`message.ts`、`file.ts`；另一类是横向聚合与关系声明，例如 `index.ts`、`relations.ts`、`_helpers.ts`。因此阅读时不要把它当作普通 “models” 目录逐个文件扫完，而应先看入口与公共模式，再按业务链路进入对应 schema。

## 直接子目录地图

当前目标目录的直接子目录很少，主要是平铺文件结构：

`packages/database/src/schemas/userMemories`：用户记忆相关 schema 的小型子域目录。它包含 `index.ts` 和 `persona.ts`，说明 user memory 这块已经从主平铺层里拆出一层，便于后续扩展多个记忆类型或相关表。根据当前片段推断，这个子目录是对“用户长期记忆/人格信息”一类数据结构的聚合入口，依据是根目录 `index.ts` 通过 `export * from './userMemories'` 统一导出它。

除了 `userMemories`，其他 schema 基本都在 `packages/database/src/schemas` 根层直接放置。这个选择让核心业务域一眼可见，也让 `index.ts` 作为总出口保持简单。

## 关键入口

`packages/database/src/schemas/index.ts` 是最重要的聚合入口。它通过连续的 `export * from './xxx'` 把各业务 schema、关系定义和子目录统一导出。其他包或数据库初始化代码通常不需要逐个引入叶子 schema，而是从这个入口拿到完整 schema 集合。要理解“系统到底有哪些数据库域”，先读这个文件最有效。

`packages/database/src/schemas/_helpers.ts` 是公共字段工具入口。根据项目的 Drizzle 规范，这里提供 `timestamptz(name)`、`createdAt()`、`updatedAt()`、`accessedAt()` 和 `timestamps` 等复用字段定义。大量业务表会通过 `...timestamps` 统一拥有标准时间列。学习 schema 时遇到 `...timestamps` 不应把它当作语法魔法，它只是公共列片段的展开。

`packages/database/src/schemas/relations.ts` 是跨表关系入口。它集中声明 Drizzle 的 `relations(...)`，并且还定义了一些典型 junction table，例如 `agents_to_sessions`、`files_to_sessions`、`file_chunks`。这类表本质上连接多个业务域，放在单一业务文件里容易造成循环依赖或语义不清，所以集中在 `relations.ts` 比较合理。

若要找认证相关表，可以从 `betterAuth.ts`、`nextauth.ts`、`oidc.ts`、`user.ts` 开始；找聊天主链路，则从 `session.ts`、`topic.ts`、`message.ts`、`agent.ts` 开始；找知识库和 RAG，则从 `file.ts`、`rag.ts`、`ragEvals.ts`、`agentDocuments.ts` 开始。

## 主流程位置

数据库 schema 的主流程可以概括为：业务域 schema 文件定义表结构，`relations.ts` 补充跨表关联和连接表，`index.ts` 汇总导出，Drizzle 配置和迁移工具读取这些导出来生成或校验数据库结构，运行时的 repository/model 层再基于这些表对象构造查询。

在写表结构时，典型流程是使用 `pgTable` 定义表名、字段、外键和索引。例如实体表会有 `id`、`userId`、配置类 `jsonb` 字段，以及 `...timestamps`；多对多关系会使用 `primaryKey({ columns: [...] })` 组合主键；外键通常通过 `.references(() => users.id, { onDelete: 'cascade' })` 指向上游表。项目规范要求查询侧优先使用 `db.select().from(...).leftJoin(...)` 这类显式 builder，而不是依赖 `db.query.*` 的 relational API。因此 `relations.ts` 更多是 schema 元信息和关系表达，并不意味着业务查询一定会通过 `with:` 自动展开。

从路径角色看，`agent.ts`、`message.ts`、`session.ts`、`topic.ts` 组成聊天和智能体核心数据；`file.ts`、`rag.ts`、`documentHistory.ts`、`agentDocuments.ts` 支撑文件、文档、知识库和向量/RAG；`generation.ts` 负责生成任务结果一类数据；`asyncTask.ts`、`task.ts` 表示后台任务；`apiKey.ts`、`rbac.ts`、`user.ts`、`betterAuth.ts` 等提供账户、权限、认证支撑；`agentEvals.ts`、`ragEvals.ts` 是评测相关结构。

## 推荐阅读顺序

第一步读 `packages/database/src/schemas/index.ts`。它是目录地图，能快速建立有哪些业务域的全局印象。

第二步读 `packages/database/src/schemas/_helpers.ts`。先理解时间字段、公共 helper 和类型习惯，后面看每个表时就不会被重复字段干扰。

第三步读聊天主链路：`user.ts`、`session.ts`、`topic.ts`、`message.ts`、`agent.ts`。这条链路覆盖用户、会话、主题、消息、智能体，是理解 LobeHub 数据模型的主干。

第四步读 `packages/database/src/schemas/relations.ts`。在已经知道主要实体后，再看关系定义会更清楚，例如 agent 与 session、file 与 session、message 与 file、document 与 chunk 之间怎样连接。

第五步按兴趣进入扩展域：知识库看 `file.ts`、`rag.ts`、`agentDocuments.ts`；认证看 `betterAuth.ts`、`nextauth.ts`、`oidc.ts`；权限看 `rbac.ts`；评测看 `agentEvals.ts`、`ragEvals.ts`；后台任务看 `asyncTask.ts`、`task.ts`。

## 常见误区

不要把 `packages/database/src/schemas` 理解成迁移目录。这里是 schema 源定义，迁移文件通常在数据库包的 migrations 相关目录中生成和维护。改 schema 不等于数据库已经自动更新，仍需要配套迁移流程。

不要逐文件从上到下硬读。这个目录是业务域平铺，叶子文件很多；overview 阶段应该先抓 `index.ts`、`_helpers.ts`、`relations.ts`，再沿业务链路进入具体表。

不要忽略 `relations.ts` 中的 junction table。像 `agents_to_sessions`、`files_to_sessions`、`file_chunks` 这类表虽然不属于单一业务实体，却是主流程查询和数据清理的重要连接点。

不要把 Drizzle 的 `relations(...)` 等同于推荐的业务查询方式。根据项目规范，运行时查询更偏向显式 `db.select()`、`leftJoin`、`where`、`groupBy`，避免复杂 relational API 带来的 SQL 不透明问题。

不要在新增字段时只看单个 schema 文件。外键、索引、`onDelete` 行为、类型导出、insert schema、关联关系、迁移文件都可能需要同步考虑。尤其是用户级数据通常需要 `userId` 与相关索引，否则多租户隔离和查询性能都容易出问题。
