# 文件：packages/desktop/src/process/services/database/schema.ts
## 一句话定位
这个文件是桌面端 SQLite 数据库的“基线定义 + 版本管理”入口，负责把旧数据库拉到统一的 v26 结构，并用 `user_version` 记录迁移状态。根据当前片段推断，它是 `packages/desktop/src/process/services/database` 里最靠前的 schema 层，给后续迁移和启动流程提供统一起点。

## 它暴露/定义了什么
它导出 4 个核心能力：`initSchema(db)` 负责创建基础表、索引和 SQLite 运行参数；`getDatabaseVersion(db)` / `setDatabaseVersion(db, version)` 负责读写 SQLite 内置的 `user_version`；`CURRENT_DB_VERSION` 定义当前 schema 版本为 `26`。从内容看，`initSchema` 覆盖了 `users`、`conversations`、`messages`、`teams`、`mailbox`、`team_tasks` 六张主表，以及对应索引和外键约束。

## 谁调用它
直接调用者是 `packages/desktop/src/process/services/database/runLegacyDatabaseMigrations.ts`，它会在打开旧版 `aionui.db` 后先执行 `initSchema`，再读取版本并决定是否跑增量迁移。间接调用链来自 `packages/desktop/src/process/utils/initStorage.ts`：启动时先走 `migrateLegacyData()`，其中再进入旧库迁移，确保后端启动前数据库已经处于 v26 基线。`migrations.ts` 也明确把 “v0 -> v1 初始 schema” 交给了这里处理。

## 它调用谁
这个文件本身不依赖复杂业务模块，主要调用的是传入的 `ISqliteDriver` 接口方法：`pragma()`、`exec()`、以及版本读写所需的 `pragma('user_version')`。也就是说，它不关心具体驱动是 `BetterSqlite3Driver` 还是别的实现，只要求底层能执行 SQLite pragma 和 SQL 语句。外层流程里，`runLegacyDatabaseMigrations` 会在这里之后再调用 `runMigrations()` 和 `setDatabaseVersion()`，但那属于调用链的下游，不是本文件内部职责。

## 核心流程
`initSchema` 的流程很固定：先打开外键约束、设置 `busy_timeout`，再尽量启用 WAL，失败则降级并继续。随后按顺序建表和建索引，表之间通过外键串起来，形成 `users -> conversations -> messages`、`users -> teams -> mailbox/team_tasks` 这样的层级结构。最后打日志表示 schema 初始化完成。版本函数则很轻：`getDatabaseVersion` 读取 `user_version`，异常时返回 `0`；`setDatabaseVersion` 直接写入版本号；`CURRENT_DB_VERSION` 作为迁移阈值被外层逻辑对比使用。

## 关键函数的高层作用
`initSchema` 是最关键的函数，作用不是“做一次迁移”，而是“定义数据库应该长什么样”。它把账户、会话、消息、团队协作、团队邮箱和任务这些核心业务对象一次性落到 SQLite 中，并把删除级联、唯一约束、状态枚举约束一起固化。`getDatabaseVersion` 和 `setDatabaseVersion` 是迁移编排的配套工具，避免外层自己解析数据库元数据。`CURRENT_DB_VERSION` 则是整个桌面端旧库升级的锚点，一旦改动，迁移脚本和启动逻辑都要同步。

## 修改风险
这里的改动风险很高，因为它直接决定历史数据库能否平滑打开。新增或修改字段时，最容易出问题的是旧数据兼容、外键约束、索引缺失，以及 `CURRENT_DB_VERSION` 与 `migrations.ts` 不一致导致的迁移分支错误。`journal_mode = WAL` 和 `busy_timeout` 也属于运行时敏感项，改错可能放大“database is locked”或同步性能问题。另一个隐性风险是表结构和后端 Rust/其它消费者的实体定义不一致，表面能建库，实际读写会在启动后才暴露。
