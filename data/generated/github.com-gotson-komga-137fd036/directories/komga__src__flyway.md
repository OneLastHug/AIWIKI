# 目录：komga/src/flyway

## 它负责什么

`komga/src/flyway` 是 Komga 后端的数据库迁移源码集，专门给 Flyway 使用。它不承载业务服务代码，而是描述“数据库结构如何从一个版本演进到下一个版本”。

这个目录主要负责两件事：

1. 主业务数据库的 schema 演进：书库、用户、系列、书籍、媒体页、阅读进度、缩略图、元数据、API key、同步点、客户端设置等表结构都在这里逐步建立和修改。
2. tasks 辅助数据库的 schema 初始化：任务队列表 `TASK` 位于单独的 tasks 数据库中，由 `resources/tasks/migration/sqlite` 下的迁移负责。

从文件数量看，当前目录包含主库 SQL 迁移 85 个、主库 Kotlin/Java-style Flyway 迁移 5 个、tasks SQL 迁移 1 个。主库迁移从 `V20200706141854__initial_migration.sql` 开始，最近的迁移包括 `V20250108115503__user_roles.sql`、`V20250108172343__koreader_hash.sql`、`V20250205151235__client_settings.sql`、`V20250730173126__remove_temp_string_table.sql` 等。

## 关键组成

这个目录的结构可以按“迁移目标数据库”和“迁移实现形式”来理解：

`komga/src/flyway/resources/db/migration/sqlite`

这是主业务 SQLite 数据库的 SQL 迁移目录。大部分数据库变化都在这里，文件名遵循 Flyway 版本迁移格式：

`V时间戳__说明.sql`

例如：

`V20200706141854__initial_migration.sql` 是初始建表迁移，创建了 `LIBRARY`、`USER`、`SERIES`、`SERIES_METADATA`、`BOOK`、`MEDIA`、`MEDIA_PAGE`、`MEDIA_FILE`、`BOOK_METADATA`、`READ_PROGRESS`、`COLLECTION` 等核心表。

后续 SQL 迁移负责增加字段、索引、表、清理旧结构或调整模型。例如从文件名可以看到缩略图、readlist、metadata fields、full text search、sidecars、trash bin、library settings、server settings、epub、syncpoint、user roles、client settings 等演进主题。

`komga/src/flyway/kotlin/db/migration/sqlite`

这是主业务数据库的 Kotlin 迁移目录。这里的文件同样遵循 Flyway 的版本命名，但扩展名是 `.kt`，类名也与文件名一致，例如：

`V20230801104436__fix_incorrect_language_codes.kt`

`V20240422132621__fix_read_progress_locators.kt`

这些迁移继承 `org.flywaydb.core.api.migration.BaseJavaMigration`，实现 `migrate(context: Context)`。它们适合处理纯 SQL 不方便表达的数据修复逻辑，比如读取旧数据、解析 JSON、压缩或解压二进制内容、批量更新修正结果。

以 `V20240422132621__fix_read_progress_locators.kt` 为例，它从 `READ_PROGRESS` 中读取非空 `locator`，用 `GZIPInputStream` 解压，再用 Jackson 解析 JSON，修正 `href` 字段，最后重新 gzip 后批量写回。这个逻辑如果用 SQL 写会非常别扭，因此放在 Kotlin 迁移中更合理。

以 `V20230801104436__fix_incorrect_language_codes.kt` 为例，它读取 `SERIES_METADATA.LANGUAGE`，通过 ICU4J 的 `ULocale.forLanguageTag` 标准化语言标签，然后批量更新错误值。

`komga/src/flyway/resources/tasks/migration/sqlite`

这是 tasks 辅助数据库的 SQL 迁移目录。当前只有：

`V20231013114850__tasks.sql`

它创建 `TASK` 表和 `idx__tasks__owner_group_id` 索引。`TASK` 表包含任务 ID、优先级、分组、任务类名、简化类型、payload、owner、创建时间、修改时间等字段。它支撑应用内部任务队列或后台任务持久化。

## 上下游关系

上游是 Flyway、Spring Boot、Gradle 和 SQLite/JDBC。

项目在 `komga/build.gradle.kts` 中引入了 `org.flywaydb.flyway` 插件和 `org.flywaydb:flyway-core` 依赖，并配置了一个独立的 `flyway` source set。这个 source set 会把 `komga/src/flyway/kotlin` 与 `komga/src/flyway/resources` 编译、打包进可被 Flyway 扫描的 classpath 中。

主库运行时迁移由 Spring Boot Flyway 自动集成触发。`komga/src/main/resources/application.yml` 中配置：

`spring.flyway.enabled: true`

`spring.flyway.locations: classpath:db/migration/{vendor}`

`spring.flyway.mixed: true`

其中 `{vendor}` 在 SQLite 下会解析到 `sqlite`，因此主库会扫描 `classpath:db/migration/sqlite`。`mixed: true` 表示允许 SQL 迁移和 Java/Kotlin 迁移混合存在，这也是该目录同时放 `.sql` 和 `.kt` 迁移的基础。

tasks 辅助库不走 Spring Boot 默认主数据源迁移。`komga/src/main/kotlin/org/gotson/komga/infrastructure/datasource/FlywaySecondaryMigrationInitializer.kt` 手动配置 Flyway，指定：

`classpath:tasks/migration/sqlite`

并使用 `tasksDataSourceRW` 执行 `migrate()`。这是因为 Spring Boot 默认只迁移 primary datasource，而 tasks 数据库是另一个 datasource。

下游主要有两类：

一类是运行时 DAO 和业务代码。例如 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/tasks/TasksDao.kt` 使用 `org.gotson.komga.jooq.tasks.Tables.TASK` 访问 tasks 数据库，并通过 `@DependsOn("flywaySecondaryMigrationInitializer")` 确保 tasks 数据库迁移先完成。

另一类是 jOOQ 代码生成。`komga/build.gradle.kts` 中定义了 `flywayMigrateMain` 和 `flywayMigrateTasks` 两个 Gradle 任务，先用这些迁移在 `build/generated/flyway/main/database.sqlite`、`build/generated/flyway/tasks/tasks.sqlite` 中生成临时 SQLite 数据库，再让 jOOQ 根据迁移后的数据库结构生成 `org.gotson.komga.jooq.main` 和 `org.gotson.komga.jooq.tasks` 代码。

## 运行/调用流程

主业务数据库的大致流程是：

1. 应用启动，Spring Boot 创建 primary datasource。
2. Spring Boot Flyway 自动读取 `application.yml` 中的 `spring.flyway` 配置。
3. Flyway 扫描 `classpath:db/migration/sqlite`。
4. Flyway 按版本号顺序执行 `V...__.sql` 和 Kotlin `BaseJavaMigration`。
5. 迁移完成后，应用的 DAO、Repository、Service 才能假定数据库 schema 已经是当前版本。

根据当前片段推断，主库迁移的执行早于大多数依赖数据库结构的业务组件初始化；依据是 Spring Boot Flyway 自动迁移通常发生在 datasource 初始化之后、业务 bean 正式使用数据库之前，并且项目在 `application.yml` 中启用了默认 Flyway。

tasks 数据库的流程稍有不同：

1. Spring 创建 `FlywaySecondaryMigrationInitializer`。
2. 该组件注入 `tasksDataSourceRW`。
3. `afterPropertiesSet()` 中手动构造 Flyway。
4. Flyway 扫描 `classpath:tasks/migration/sqlite`。
5. 执行 `V20231013114850__tasks.sql` 创建 `TASK` 表和索引。
6. `TasksDao` 通过 `@DependsOn("flywaySecondaryMigrationInitializer")` 等待迁移完成，然后再访问 `Tables.TASK`。

构建期 jOOQ 生成流程是另一条线：

1. Gradle 执行 `generateJooq` 或 `generateTasksJooq`。
2. 对应任务依赖 `flywayMigrateMain` 或 `flywayMigrateTasks`。
3. Flyway 先把迁移应用到 build 目录下的临时 SQLite 文件。
4. jOOQ 读取临时数据库 schema。
5. 生成类型安全的表、字段、记录类，供 Kotlin DAO 使用。

这里要注意：同一批迁移既服务运行时真实数据库，也服务构建期 jOOQ 代码生成。因此迁移文件一旦写错，影响不只是应用升级，也可能直接导致编译或代码生成失败。

## 小白阅读顺序

建议先从 `komga/build.gradle.kts` 的 Flyway 和 jOOQ 配置开始读，重点看 `sqliteUrls`、`sqliteMigrationDirs`、`flywayMigrateMain`、`flywayMigrateTasks`、`jooq`、`sourceSets` 这些块。这样能先理解“为什么这个目录不是 main，却仍然会参与编译和运行”。

第二步读 `komga/src/main/resources/application.yml` 的 `spring.flyway` 配置，理解主数据库运行时如何找到 `classpath:db/migration/{vendor}`。

第三步读 `komga/src/flyway/resources/db/migration/sqlite/V20200706141854__initial_migration.sql`。这是整个数据库模型的地基，里面能看到 Komga 最早的核心概念：`LIBRARY`、`USER`、`SERIES`、`BOOK`、`MEDIA`、`READ_PROGRESS`、`COLLECTION`。

第四步按时间挑几个 SQL 迁移看，不需要一口气读完 85 个。可以优先看文件名比较有业务含义的迁移，例如 metadata、readlist、thumbnail、library settings、server settings、apikey、syncpoint、client settings。读的时候关注每个迁移是“加表”、“加列”、“建索引”、“搬数据”还是“清理旧结构”。

第五步读 Kotlin 迁移，例如 `V20230801104436__fix_incorrect_language_codes.kt` 和 `V20240422132621__fix_read_progress_locators.kt`。重点看 `BaseJavaMigration`、`Context`、`JdbcTemplate`、`SingleConnectionDataSource` 的组合方式，以及为什么这些迁移没有写成普通 SQL。

第六步读 tasks 相关链路：先看 `komga/src/flyway/resources/tasks/migration/sqlite/V20231013114850__tasks.sql`，再看 `FlywaySecondaryMigrationInitializer.kt`，最后看 `TasksDao.kt`。这条线能帮助理解 Komga 为什么有主库和 tasks 库两个迁移入口。

## 常见误区

不要以为 `komga/src/flyway` 是普通业务源码目录。它是专门给 Flyway source set 使用的迁移目录，Kotlin 文件也不是普通 service 或 repository，而是数据库升级脚本。

不要随意修改已经发布过的旧迁移。Flyway 会记录已执行迁移的 checksum。历史迁移一旦改动，已有用户数据库升级时可能出现 checksum mismatch。通常应该新增一个更高版本号的迁移来修正问题，而不是回头改旧文件。

不要忽略文件名顺序。Flyway 依赖 `V版本号__描述` 判断执行顺序。这里使用时间戳作为版本号，例如 `V20240422132621__fix_read_progress_locators.kt`。版本号必须全局有序且不能重复。

不要以为 SQL 迁移和 Kotlin 迁移会分开执行。`mixed = true` 明确允许二者混用，它们会一起参与同一条版本序列。Kotlin 类名、文件名和 Flyway 版本命名需要保持一致，否则扫描和执行可能出问题。

不要把主库迁移和 tasks 库迁移混在一起。主库路径是 `db/migration/sqlite`，tasks 库路径是 `tasks/migration/sqlite`。前者由 Spring Boot 默认 Flyway 处理，后者由 `FlywaySecondaryMigrationInitializer` 手动处理。

不要忘记 jOOQ 也依赖这些迁移。新增或修改数据库结构后，构建期的 `generateJooq`、`generateTasksJooq` 会通过 Flyway 先生成临时数据库，再生成 jOOQ 类型。迁移脚本的错误可能表现为运行时升级失败，也可能表现为 jOOQ 生成失败或 DAO 编译失败。

不要把 Kotlin 迁移写成依赖完整 Spring 容器的业务代码。当前 Kotlin 迁移只使用 Flyway `Context` 提供的 JDBC connection，再包装成 `JdbcTemplate` 操作数据库。这种方式更适合迁移脚本，因为迁移执行时不应依赖复杂业务 bean 的生命周期和当前领域模型。
