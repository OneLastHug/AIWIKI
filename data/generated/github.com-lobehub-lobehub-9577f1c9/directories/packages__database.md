# 目录：packages/database

## 它负责什么

`packages/database` 是 LobeHub monorepo 里的数据库基础包，包名是 `@lobechat/database`。它不是单纯的“数据库连接工具”，而是把数据库相关的几层都集中在一起：Drizzle schema、数据库类型、服务端 DB 实例、领域 model、跨表 repository、migration、测试工具。

从 `package.json` 看，它对外主要暴露三个入口：

- `@lobechat/database` → `src/index.ts`
- `@lobechat/database/schemas` → `src/schemas/index.ts`
- `@lobechat/database/test-utils` → `tests/test-utils.ts`

`src/index.ts` 当前导出的是 `core/db-adaptor`、`repositories/compression`、`type`、`utils/idGenerator`。也就是说，普通业务代码如果从根包导入，拿到的是 DB 适配器、部分 repository、类型和 ID 工具；如果要拿完整表定义，需要走 `@lobechat/database/schemas`。

根据当前片段推断，它在整体调用链中的位置大致是：

`React UI → Store Actions → Client Service → TRPC / API → Server Service → packages/database Model / Repository → PostgreSQL`

它的核心职责是把 PostgreSQL 的表结构和 Drizzle 查询封装成业务可用的数据库访问层，避免上层服务到处手写 SQL 或重复理解表关系。

## 关键组成

第一层是 `src/schemas/`。这是数据库表结构定义层，`src/schemas/index.ts` 统一导出大量 schema，包括 `agent`、`message`、`session`、`topic`、`user`、`rag`、`aiInfra`、`rbac`、`task`、`notification`、`betterAuth` 等。以 `src/schemas/message.ts` 为例，它定义了 `messages`、`messageGroups`、`messagePlugins`、`messageTTS`、`messageTranslates` 等聊天消息相关表，并使用 Drizzle 的 `pgTable`、`index`、`uniqueIndex`、`references`、`jsonb` 等能力描述字段、索引和外键。这里还会用 `createInsertSchema` 生成插入 schema，用 `$inferInsert` / `$inferSelect` 导出类型。

第二层是 `src/type.ts`。它把 `./schemas` 整体作为 `LobeChatDatabaseSchema`，并定义 `LobeChatDatabase = NeonDatabase<LobeChatDatabaseSchema>`。这让后面的 model 和 repository 都能拿到带 schema 类型的 Drizzle DB 实例。`Transaction` 类型也从 `LobeChatDatabase['transaction']` 里推导出来，供事务方法复用。

第三层是 `src/core/`。`src/core/db-adaptor.ts` 是服务端数据库实例入口。`getServerDB()` 会缓存一个 `LobeChatDatabase`，首次调用时通过 `getDBInstance()` 创建实例；`serverDB` 则是直接执行 `getDBInstance()` 得到的实例。根据当前片段推断，真正决定连接 Neon、PGlite 或其他运行环境的逻辑在 `src/core/web-server.ts`，本次没有展开阅读。

第四层是 `src/models/`。这是更贴近单个领域对象的数据库访问层，文件很多，例如 `message.ts`、`agent.ts`、`topic.ts`、`session.ts`、`user.ts`、`file.ts`、`document.ts`、`aiModel.ts`、`aiProvider.ts`、`task.ts` 等。以 `MessageModel` 为例，构造函数接收 `db` 和 `userId`，内部所有查询都会围绕当前用户隔离数据。它导入 `messages`、`messagePlugins`、`messageGroups`、`topics`、`threads`、`files`、`chunks`、`embeddings` 等 schema，说明消息查询不只是读 `messages` 表，还会处理文件、RAG chunk、插件调用、线程、话题等关联数据。

第五层是 `src/repositories/`。repository 通常比 model 更“聚合”，服务某个页面或业务视图。比如 `HomeRepository` 负责侧边栏 agent 列表，它同时查询 `agents`、`agentsToSessions`、`sessions`、`chatGroups`、`sessionGroups`，再把结果归类成 `pinned`、`groups`、`ungrouped`。`AiInfraRepos` 则组合 `AiProviderModel` 和 `AiModelModel`，再融合 `model-bank` 的内置 provider/model 配置与用户数据库配置，生成前端聊天页可用的 provider 和 model 列表。

第六层是 `migrations/`。目录下从 `0000_init.sql` 一直到 `0102_add_agent_operations_table.sql`，并有 `migrations/meta` 保存 Drizzle snapshot 和 journal。迁移覆盖了认证、pgvector、知识库、RAG eval、AI infra、图片/视频生成、RBAC、group chat、user memory、document、agent task、notification、messenger、agent operations 等长期演进。

第七层是测试相关文件。`tests/setup-db.ts`、`tests/test-utils.ts`、`vitest.config.mts`、`vitest.config.server.mts` 以及大量 `src/models/__tests__`、`src/repositories/**/__tests__` 表明这个包的 model/repository 查询逻辑有较多单元测试。`package.json` 里测试依赖包括 `@electric-sql/pglite` 和 `fake-indexeddb`，说明部分测试可能使用轻量本地数据库或浏览器存储模拟环境。

## 上下游关系

上游是 PostgreSQL / Neon 和 Drizzle ORM。`LobeChatDatabase` 类型来自 `drizzle-orm/neon-serverless` 的 `NeonDatabase`，schema 用 `drizzle-orm/pg-core` 定义，查询用 `eq`、`and`、`inArray`、`sql`、`desc`、`asc` 等 Drizzle 表达式组合。

平级依赖包括多个 LobeHub 内部包，例如 `@lobechat/types`、`@lobechat/const`、`@lobechat/utils`、`@lobechat/business-const`、`@lobechat/business-model-bank`、`model-bank`。这说明数据库层并不是完全“纯基础设施”，它会引用业务类型和模型配置。例如 `AiInfraRepos` 会加载内置模型列表，再合并数据库里的用户自定义 provider/model。

下游主要是 `src/server/services`、`src/server/routers`、API route、CLI 或后台任务等服务端代码。根据项目结构和当前片段推断，上层一般不会直接操作裸 SQL，而是实例化类似 `new MessageModel(db, userId)`、`new HomeRepository(db, userId)`、`new AiInfraRepos(db, userId, providerConfigs)` 这样的类，然后调用方法拿业务结果。

它还向外暴露 `@lobechat/database/schemas`，这类入口通常会被迁移、测试、数据库工具或少量底层服务使用，用于直接引用表定义。

## 运行/调用流程

一个典型服务端调用流程可以这样理解：

1. 服务端代码从 `@lobechat/database` 或 `@lobechat/database/server` 获取 `serverDB` / `getServerDB()`。
2. DB 实例由 `src/core/db-adaptor.ts` 调用 `getDBInstance()` 创建，并按 `LobeChatDatabase` 类型绑定全部 schema。
3. 服务拿到当前 `userId` 后，创建对应 model 或 repository。
4. model/repository 使用 Drizzle 查询 schema 表，并通过 `where(eq(table.userId, this.userId))` 这类条件隔离用户数据。
5. 查询结果会在数据库层被整理成上层业务类型。例如 `HomeRepository.getSidebarAgentList()` 不只是返回表行，而是返回 `SidebarAgentListResponse`，其中已经按置顶、分组、未分组处理好。
6. 上层 server service / TRPC router 再把这些结果返回给 client service，最终进入 store 和 UI。

以消息为例，`MessageModel` 的输入是聊天消息相关参数，内部会拆分消息主表字段与关系字段，可能写入 `messages`，也可能同步写 `messagePlugins`、`messageTTS`、`messageTranslates`、`messagesFiles`、RAG 查询关系等。它还包含 `touchTopicUpdatedAt` 这样的内部方法，在事务中更新关联 topic 的时间戳，确保列表排序和消息变更联动。

以首页侧边栏为例，`HomeRepository.getSidebarAgentList()` 会分别查 agent、chat group、session group，再调用内部的 `processAgentList()` 统一成 sidebar item。这里体现了 repository 的价值：上层页面只关心“侧边栏要显示什么”，不需要知道 agent 与 session、chat group、folder 的表结构差异。

## 小白阅读顺序

1. 先看 `packages/database/package.json`  
   理解这个包对外暴露什么、依赖什么、测试怎么跑。重点关注 `exports`，不要误以为所有内部文件都是公共 API。

2. 再看 `src/type.ts`  
   这里最短，但很关键。它告诉你整个包使用 `typeof schema` 作为 Drizzle 数据库类型来源，后续所有 model/repository 的 `db` 都基于这个类型。

3. 再看 `src/schemas/index.ts`  
   先从导出列表建立“数据库有哪些业务域”的地图，不要一开始钻进某个大 schema。

4. 选择一个熟悉领域的 schema，例如 `src/schemas/message.ts` 或 `src/schemas/user.ts`  
   重点看 `pgTable`、字段、外键、索引、`createInsertSchema`、`$inferSelect`。这一步是在学习“表长什么样”。

5. 再看对应 model，例如 `src/models/message.ts`  
   重点看构造函数、公开方法、事务、关联查询和返回类型。这一步是在学习“表怎么被业务使用”。

6. 最后看 repository，例如 `src/repositories/home/index.ts` 或 `src/repositories/aiInfra/index.ts`  
   repository 更接近页面或业务视图，适合理解多个 model/schema 如何被组合成一个业务响应。

7. 有改表需求时再看 `migrations/`  
   migration 文件很多，不建议从头顺读。应该结合某个 schema 的演进去查相关 migration，例如 message、document、agent task、notification 等。

## 常见误区

第一个误区是把 `schemas`、`models`、`repositories` 混为一谈。`schemas` 定义表，`models` 封装单领域读写，`repositories` 组合多个领域形成业务视图。三者层级不同，读代码时要分清。

第二个误区是以为 `@lobechat/database` 根入口导出了所有数据库能力。实际根入口只导出了少量内容；完整 schema 要从 `@lobechat/database/schemas` 走，服务端入口还有 `src/server/index.ts` 导出的 `getServerDB`、`serverDB`。

第三个误区是忽略 `userId`。大量 model/repository 都在构造函数里绑定 `userId`，查询时用它做隔离。阅读或新增查询时，如果忘了用户条件，风险通常比 SQL 写错更大。

第四个误区是只看主表。比如聊天消息不只有 `messages`，还包括插件、TTS、翻译、文件、RAG 查询、message group、thread、topic 等关联表。上层看到的一条消息，可能来自多张表聚合。

第五个误区是把 repository 当成“简单 DAO”。例如 `AiInfraRepos` 不只是查数据库，它还会合并内置 `model-bank`、用户自定义模型、provider 默认配置，并注入搜索能力默认值。这类 repository 已经包含明显的业务规则。

第六个误区是随意改 migration。`migrations/meta` 保存 Drizzle snapshot 和 journal，migration 顺序也承载历史演进。改 schema 后不能只改 TypeScript 表定义，还要按项目的 Drizzle migration 规范生成和检查 SQL。

第七个误区是忽略测试入口。这个包有大量 model/repository 测试，且 `package.json` 区分 `test:client-db` 和 `test:server-db`。如果修改数据库查询逻辑，优先跑目标测试文件，而不是直接跑全量测试。
