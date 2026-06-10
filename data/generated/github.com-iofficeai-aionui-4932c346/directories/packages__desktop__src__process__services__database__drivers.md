# 子系统：packages/desktop/src/process/services/database/drivers

## 解决什么问题

这个目录提供的是“SQLite 访问抽象层”。它把具体数据库实现 `better-sqlite3` 包装成统一接口 `ISqliteDriver`，让上层的 schema 初始化、迁移执行、旧库升级等逻辑不直接依赖第三方库的 API 细节，而是只面对少量稳定的方法：`prepare`、`exec`、`pragma`、`transaction`、`close`。

根据当前片段推断，这一层的核心价值有三点：一是隔离数据库库的实现差异，二是让迁移代码可测试、可替换，三是把数据库生命周期管理收束到统一入口，避免上层到处散落 `new BetterSqlite3(...)` 和手工关闭连接。

## 相关目录和文件

目录内当前只有两个文件：

- `packages/desktop/src/process/services/database/drivers/ISqliteDriver.ts`
- `packages/desktop/src/process/services/database/drivers/BetterSqlite3Driver.ts`

它们对应的上层协作文件主要在同级目录和更上层：

- `packages/desktop/src/process/services/database/schema.ts`：用 `ISqliteDriver` 初始化表结构、索引和 `user_version`
- `packages/desktop/src/process/services/database/migrations.ts`：用同一个接口执行版本迁移和回滚
- `packages/desktop/src/process/services/database/runLegacyDatabaseMigrations.ts`：启动时为旧版数据库做一次性升级
- `packages/desktop/src/process/utils/initStorage.ts`：在启动流程里触发旧库迁移
- 另外还依赖第三方包 `better-sqlite3`

## 核心对象

- `IStatement`：对预编译语句的最小抽象，暴露 `get`、`all`、`run` 三类操作。
- `ISqliteDriver`：数据库驱动接口，定义了 `prepare`、`exec`、`pragma`、`transaction`、`close`。
- `BetterSqlite3Statement`：`IStatement` 的适配器，把 `better-sqlite3` 的 `Statement` 包装起来。
- `BetterSqlite3Driver`：`ISqliteDriver` 的具体实现，内部持有 `better-sqlite3` 的 `Database` 实例。

这里的设计很薄，不承载业务语义，只做 API 适配。业务语义实际上在 `schema.ts` 和 `migrations.ts` 里。

## 运行流程

启动时，`initStorage.ts` 会调用 `runLegacyDatabaseMigrations()`。这段流程会先检查旧库文件是否存在；如果不存在就直接跳过。若存在，则创建 `BetterSqlite3Driver`，然后按顺序做三件事：

1. 调用 `initSchema(driver)`，确保基础表结构和关键 pragma 到位。
2. 读取当前数据库版本，再与 `CURRENT_DB_VERSION` 比较，必要时执行 `runMigrations(driver, currentVersion, CURRENT_DB_VERSION)`，最后写回版本号。
3. 执行 `ensureSystemUser(driver)`，补齐系统默认用户。

整个过程结束后，无论成功还是失败，驱动都会在 `finally` 中关闭连接。也就是说，这个目录提供的驱动对象是“短生命周期、任务型”的，不是常驻单例。

## 上下游依赖

上游依赖主要是运行环境和第三方 SQLite 实现：

- 直接依赖 `better-sqlite3`
- 间接依赖 `@process/utils` 提供的数据目录和目录创建能力
- 依赖 SQLite 自身的 `pragma`、事务、`user_version`、外键约束等能力

下游则是数据库服务层的其余模块：

- `schema.ts` 依靠 `ISqliteDriver` 创建 `users`、`conversations`、`messages`、`teams`、`mailbox`、`team_tasks` 等表
- `migrations.ts` 依靠同一接口执行版本升级、回滚和外键检查
- `runLegacyDatabaseMigrations.ts` 依靠 `BetterSqlite3Driver` 对旧版 `aionui.db` 做一次性迁移
- `initStorage.ts` 把这套逻辑接到应用启动链路里

## 修改时最容易踩的坑

- 只改 `BetterSqlite3Driver` 不改 `ISqliteDriver`，会让上层抽象和实现脱节。
- `transaction` 的返回类型和参数透传要保持兼容，否则 `migrations.ts` 里的事务包装会出问题。
- `pragma('foreign_keys = OFF')` 和事务的配合很敏感，迁移代码已经假设它们在事务外切换。
- 迁移文件里有不少“表重建”式回滚，改 schema 时要同时检查 `down()` 是否仍然成立。
- `runLegacyDatabaseMigrations()` 只适合旧库升级，不应被当成通用数据库入口。
- 新增迁移后，除了写 migration 本身，还要同步更新 `CURRENT_DB_VERSION` 和迁移列表，否则版本逻辑会失真。
- `ensureSystemUser()` 依赖 `users` 表已有 `jwt_secret` 列和默认字段顺序，改表结构时要一起校验。

## 推荐阅读顺序

1. 先看 `packages/desktop/src/process/services/database/drivers/ISqliteDriver.ts`，建立接口边界。
2. 再看 `packages/desktop/src/process/services/database/drivers/BetterSqlite3Driver.ts`，理解具体适配方式。
3. 接着看 `packages/desktop/src/process/services/database/schema.ts`，确认初始化时驱动如何被消费。
4. 然后看 `packages/desktop/src/process/services/database/migrations.ts`，理解版本迁移和回滚机制。
5. 最后看 `packages/desktop/src/process/services/database/runLegacyDatabaseMigrations.ts` 和 `packages/desktop/src/process/utils/initStorage.ts`，把这个目录放回启动链路中理解。
