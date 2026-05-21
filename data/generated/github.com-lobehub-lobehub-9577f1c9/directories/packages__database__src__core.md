# 目录：packages/database/src/core

## 它负责什么

`packages/database/src/core` 是 `@lobechat/database` 包里“创建数据库实例”的核心入口层。它不定义表结构，也不写具体业务查询，而是把运行环境、数据库驱动、Drizzle schema、迁移能力和测试数据库封装成统一的 `LobeChatDatabase` 对象，供上层 models、repositories、server services、routers 使用。

这个目录可以理解为数据库包的“连接工厂”：

- 生产/服务端运行时：通过 `getServerDB()` 或 `serverDB` 拿到 Drizzle 数据库实例。
- 测试运行时：通过 `getTestDB()` 拿到 PGlite 内存数据库或真实 PostgreSQL 测试库。
- 驱动选择：根据 `DATABASE_DRIVER` 在 Neon serverless 和 `node-postgres` 之间切换。
- schema 装配：统一引入 `packages/database/src/schemas` 下导出的所有表和关系。

## 关键组成

`db-adaptor.ts`

这是对外最常用的服务端 DB 适配层。它导出两个东西：

- `getServerDB(): Promise<LobeChatDatabase>`
- `serverDB`

`getServerDB()` 内部维护一个模块级缓存 `cachedDB`。第一次调用时执行 `getDBInstance()` 创建数据库实例，之后直接返回缓存，避免每次 import 或每次业务调用都重新初始化连接池。

`serverDB = getDBInstance()` 是同步创建的实例，适合迁移脚本这类需要直接拿数据库对象的场景。需要注意的是，它在模块加载时就会初始化数据库，因此对环境变量要求更强。

`web-server.ts`

这是实际创建数据库实例的地方。核心函数是 `getDBInstance()`。

它的逻辑大致是：

1. 如果 `NODE_ENV === 'test'`，直接返回空对象 `{} as LobeChatDatabase`，避免普通单元测试因为没有数据库环境而失败。
2. 检查 `KEY_VAULTS_SECRET`，缺失则抛错。虽然这个值不是连接数据库本身必需的，但在 LobeHub 服务端语境里，数据库模型会涉及密钥加密/解密，所以这里把它作为 DB 初始化前置条件。
3. 检查 `DATABASE_URL`，缺失则抛错。
4. 如果 `DATABASE_DRIVER === 'node'`，使用 `pg.Pool` + `drizzle-orm/node-postgres`。
5. 否则默认使用 `@neondatabase/serverless` 的 `Pool` + `drizzle-orm/neon-serverless`。
6. 如果 `MIGRATION_DB === '1'`，为 Neon serverless 配置 `ws` 作为 WebSocket 构造器，主要服务于迁移脚本等 Node 环境。

两个连接池都会监听 `error` 事件，并把 idle client 的错误记录到日志而不是让 Node 进程因未处理的 pool error 崩溃。这一点是生产稳定性逻辑，不是普通样板代码。

`getTestDB.ts`

这是测试数据库工厂。它根据 `TEST_SERVER_DB` 分成两种模式：

- `TEST_SERVER_DB === '1'`：使用真实 PostgreSQL 测试库，连接串来自 `DATABASE_TEST_URL`，驱动是 `node-postgres`，并执行完整 Drizzle migration。
- 默认模式：使用 `@electric-sql/pglite` 创建本地内存/嵌入式 PostgreSQL 风格数据库，并启用 `vector` 扩展。

PGlite 模式没有直接调用 Drizzle 的标准 migrator，而是手动读取 `migrations` 文件，并跳过包含 `pg_search` 或 `bm25` 的 SQL。原因是这些能力对 PGlite 不兼容。它仍然会手动维护 `"drizzle"."__drizzle_migrations"` 表，把 migration hash 写进去，模拟迁移已执行状态。

`type.ts` 邻近上下文

`LobeChatDatabase` 在 `packages/database/src/type.ts` 中定义为：

```ts
NeonDatabase<LobeChatDatabaseSchema>
```

但 `getDBInstance()` 在 `DATABASE_DRIVER === 'node'` 时实际返回的是 node-postgres Drizzle 实例。根据当前片段推断，这里依赖 Drizzle 两个数据库实例在业务层常用 API 上足够兼容，因此用统一类型简化上层调用；测试代码里也多处通过 `as unknown as LobeChatDatabase` 做兼容转换。

## 上下游关系

上游输入主要来自环境配置和 schema：

- `src/config/db.ts` 提供 `serverDBEnv`，包含 `DATABASE_URL`、`DATABASE_TEST_URL`、`DATABASE_DRIVER`、`KEY_VAULTS_SECRET` 等。
- `packages/database/src/schemas/index.ts` 聚合导出所有数据库 schema，例如 `agent`、`message`、`session`、`user`、`rag`、`task`、`generation` 等。
- `packages/database/migrations` 是 `getTestDB()` 和迁移脚本读取的迁移目录。

下游使用主要有三类：

- 包入口：`packages/database/src/index.ts` 导出 `./core/db-adaptor`，所以 `@lobechat/database` 可以拿到 `getServerDB` / `serverDB`。
- 服务端入口：`packages/database/src/server/index.ts` 专门 re-export `getServerDB` 和 `serverDB`，上层可通过 `@/database/server` 使用。
- 测试入口：`@lobechat/database/test-utils` 指向 `packages/database/tests/test-utils.ts`，它导出 `../src/core/getTestDB`。

典型调用方包括：

- `src/server/services/taskRunner/scheduleTick.ts` 中调用 `getServerDB()`，再实例化 `TaskModel`、`BriefModel`、`TaskTopicModel`、`TaskRunnerService`。
- `scripts/migrateServerDB/index.ts` 动态 import `packages/database/src/server` 中的 `serverDB`，然后根据 `DATABASE_DRIVER` 选择 `nodeMigrate` 或 `neonMigrate`。
- 多个 repository / service integration tests 通过 `getTestDB()` 获取测试数据库，再插入 users、files、documents、sessions 等测试数据。

## 运行/调用流程

生产服务端的常见路径是：

1. 业务代码调用 `getServerDB()`。
2. `db-adaptor.ts` 检查 `cachedDB`。
3. 第一次调用时进入 `getDBInstance()`。
4. `web-server.ts` 检查环境变量。
5. 根据 `DATABASE_DRIVER` 创建 Neon 或 node-postgres Drizzle 实例。
6. 绑定 schema 后返回统一的 `LobeChatDatabase`。
7. 上层 model/repository 使用 `db.query.xxx`、`db.insert()`、`db.select()`、`db.transaction()` 等 Drizzle API。

迁移脚本路径略有不同：

1. `scripts/migrateServerDB/index.ts` 读取 `.env`、`.env.[env]`、`.env.[env].local`。
2. 动态导入 `serverDB`。
3. 因为 `serverDB` 是同步常量，导入时立即执行 `getDBInstance()`。
4. 根据 `DATABASE_DRIVER` 使用对应 migrator 执行 `packages/database/migrations`。

测试路径是：

1. 测试文件调用 `getTestDB()`。
2. 如果 `TEST_SERVER_DB=1`，连接 `DATABASE_TEST_URL` 并执行真实 PostgreSQL migration。
3. 否则创建 PGlite，并手动应用兼容的 migration。
4. 返回缓存的测试 DB，后续测试复用同一个实例。

## 小白阅读顺序

1. 先看 `packages/database/src/core/db-adaptor.ts`  
   这里最短，能先理解“外部到底怎么拿 DB”。

2. 再看 `packages/database/src/core/web-server.ts`  
   重点关注 `getDBInstance()`，理解 Neon、node-postgres、环境变量和连接池错误处理。

3. 接着看 `src/config/db.ts`  
   明确 `DATABASE_DRIVER` 默认是 `neon`，以及 `DATABASE_URL`、`DATABASE_TEST_URL`、`KEY_VAULTS_SECRET` 从哪里来。

4. 再看 `packages/database/src/type.ts` 和 `packages/database/src/schemas/index.ts`  
   前者解释 DB 类型，后者解释 schema 是如何整体注入 Drizzle 的。

5. 然后看 `packages/database/src/core/getTestDB.ts`  
   理解为什么测试分 PGlite 和真实 PostgreSQL 两套。

6. 最后看调用方，例如 `src/server/services/taskRunner/scheduleTick.ts` 或某个 repository test  
   这样能看到 DB 实例如何进入 model/service，并参与真实业务流程。

## 常见误区

- 不要把 `core` 理解成“数据库业务核心”。它不负责用户、会话、消息、文件等业务查询；那些在 `models`、`repositories`、`server/services` 里。这里负责的是 DB 实例创建和测试 DB 装配。

- `getServerDB()` 和 `serverDB` 不完全等价。`getServerDB()` 是懒加载并缓存，适合普通服务端业务；`serverDB` 在模块导入时就初始化，更适合迁移脚本等明确需要立即连接数据库的场景。

- `NODE_ENV === 'test'` 下 `getDBInstance()` 返回空对象，并不代表所有测试都能用它访问数据库。真正需要数据库能力的测试应使用 `getTestDB()`。

- `LobeChatDatabase` 类型名虽然来自 Neon Drizzle 类型，但运行时可能是 node-postgres Drizzle 实例。根据当前片段推断，项目把它们当作同一类 Drizzle 查询接口来使用。

- PGlite 测试模式不是完整 PostgreSQL。`getTestDB()` 明确跳过 `pg_search`、`bm25` 相关 SQL，所以涉及全文搜索扩展或特殊索引能力的测试，可能需要 `TEST_SERVER_DB=1` 的真实数据库模式。

- `KEY_VAULTS_SECRET` 缺失会阻止 DB 初始化。新手可能只配置 `DATABASE_URL`，但在这个项目里服务端 DB 初始化还会检查密钥配置，因为上层模型会处理加密数据。
