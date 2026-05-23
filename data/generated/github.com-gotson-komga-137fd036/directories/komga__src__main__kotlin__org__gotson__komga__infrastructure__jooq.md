# 目录：komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq

## 它负责什么

这个目录是 Komga 的 jOOQ 持久化实现层，主要职责是把领域层的 Repository 接口落到 SQLite 数据库查询、写入、批处理和分页检索上。它位于 `infrastructure`，说明它不是业务规则本身，而是业务对象与数据库表之间的适配层。

它处理两类数据库上下文：

主数据库：由 `dslContextRW`、`dslContextRO` 访问，保存书籍、系列、元数据、缩略图、阅读进度、用户、设置等核心数据。具体实现集中在 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main`。

任务数据库：由 `tasksDslContextRW`、`tasksDslContextRO` 访问，保存后台任务队列。具体实现是 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/tasks/TasksDao.kt`。

这个目录还负责复杂搜索条件的 SQL 生成，例如书籍搜索、系列搜索、内容限制、阅读状态、标签、作者、馆藏、阅读列表、集合等条件如何转换为 jOOQ `Condition` 和必要的 join 信息。

## 关键组成

`KomgaJooqConfiguration.kt` 是配置入口。它创建四个 `DSLContext` Bean：主库读写 `dslContextRW`、主库只读 `dslContextRO`、任务库读写 `tasksDslContextRW`、任务库只读 `tasksDslContextRO`。所有 context 都使用 `SQLDialect.SQLITE`，并通过 `TransactionAwareDataSourceProxy` 接入 Spring 事务。

`SplitDslDaoBase.kt` 是 DAO 基类。它保存 `dslRW` 和 `_dslRO`，并暴露 `dslRO` 属性。注意这里的 `dslRO` 不是永远走只读连接：如果当前存在非只读事务，它会返回 `dslRW`。这能避免同一事务内写后读却读到只读连接旧状态的问题。

`main` 子目录是主库 DAO 集合，例如 `BookDao.kt`、`SeriesDao.kt`、`LibraryDao.kt`、`MediaDao.kt`、`ReadProgressDao.kt`、`ThumbnailBookDao.kt` 等。它们通常实现 `org.gotson.komga.domain.persistence` 下的接口，或者实现 `interfaces/api/persistence` 下的 DTO Repository。

`tasks` 子目录目前核心是 `TasksDao.kt`，实现 `org.gotson.komga.application.tasks.TasksRepository`。它管理后台任务的保存、领取、分组统计、删除和释放 owner。

`BookSearchHelper.kt` 和 `SeriesSearchHelper.kt` 负责把 `SearchCondition.Book`、`SearchCondition.Series` 转成 jOOQ 查询条件。返回值不是单个 `Condition`，而是 `Pair<Condition, Set<RequiredJoin>>`，因为部分过滤条件依赖额外表，例如 book metadata、series metadata、media、read progress、read list、collection。

`RequiredJoin.kt` 是搜索 helper 和 DAO 之间的协议。helper 不直接改查询结构，只声明需要哪些 join；DAO 在构造 SQL 时遍历 `RequiredJoin` 并补上对应的 `innerJoin` 或 `leftJoin`。

`SearchOperatorUtils.kt` 是操作符转换工具，把领域层的 `SearchOperator` 转换成 jOOQ 条件，例如 `Is`、`IsNot`、`Contains`、`Before`、`After`、数值比较、布尔判断等。

`ContentRestrictionsSearchHelper.kt` 把内容限制转换为 SQL 条件，覆盖年龄分级和共享标签的 allow / exclude 逻辑，并在需要时声明 `RequiredJoin.SeriesMetadata`。

`Utils.kt` 放通用扩展：排序转换 `Sort.toOrderBy`、大小写/排序辅助、SQLite 自定义函数 `udfStripAccents`、内容限制 `toCondition`、JSON GZIP 序列化/反序列化、read list 和 collection 的表别名函数。

`TempTable.kt` 用临时表承载大量字符串集合。对于 `seriesIds`、URL 集合、批量删除 ID 等场景，直接拼很长的 `IN (...)` 不稳定，所以它创建临时表并用子查询参与过滤。

`UnpagedSorted.kt` 是一个特殊 `Pageable`，表示“不分页但保留排序”。

## 上下游关系

上游主要是领域服务、接口层控制器和任务系统。比如 `BookRepository` 被 `BookLifecycle`、`BookImporter`、`BookController`、`CommonBookController`、`TaskHandler` 等调用；`SeriesRepository` 被 `SeriesLifecycle`、`LibraryLifecycle`、`SeriesController` 等调用；`TasksRepository` 被 `TaskProcessor`、`TaskEmitter`、`TaskController`、`SseController` 等调用。

中间契约是 Repository 接口，例如 `komga/src/main/kotlin/org/gotson/komga/domain/persistence/BookRepository.kt`、`SeriesRepository.kt` 和 `komga/src/main/kotlin/org/gotson/komga/application/tasks/TasksRepository.kt`。业务层只依赖接口，不关心 jOOQ。

下游是 jOOQ 生成的表对象，例如 `org.gotson.komga.jooq.main.Tables` 和 `org.gotson.komga.jooq.tasks.Tables`。DAO 通过这些类型安全的表、字段、record 完成 SQL 构造，并把 record 映射回领域模型，例如 `BookRecord.toDomain()`、`SeriesRecord.toDomain()`。

根据当前片段推断，数据库 schema 和 jOOQ 生成代码不在该目录手写维护，而是由迁移/生成流程产生；依据是 DAO 引用了 `org.gotson.komga.jooq.main.Tables`、`org.gotson.komga.jooq.tasks.Tables` 这类生成包。

## 运行/调用流程

一次典型的书籍搜索流程是：接口层或服务层调用 `BookRepository.findAll(searchCondition, searchContext, pageable)`，Spring 注入到实现类 `BookDao`。`BookDao` 创建 `BookSearchHelper(searchContext)`，调用 `toCondition(searchCondition)`。helper 先合并基础限制，包括 `SearchContext.restrictions` 和 `SearchContext.libraryIds`，再递归解析 `AllOfBook`、`AnyOfBook`、标题、删除状态、发布日期、阅读状态、媒体状态、标签、作者、poster、read list 等条件。

helper 返回 `Condition` 和 `RequiredJoin` 集合。`BookDao` 先构造 count 查询，再构造 items 查询；两次都会遍历 `RequiredJoin`，例如 `BookMetadata` join `BOOK_METADATA`，`Media` join `MEDIA`，`ReadProgress(userId)` left join `READ_PROGRESS` 并加 `USER_ID`，`ReadList(readListId)` 使用 `rlbAlias` 生成 read list book 的别名表。最后应用 `where(condition)`、排序、分页，再 `fetchInto(b)` 并映射成 `Book`。

系列搜索类似。`SeriesDao.findAll` 使用 `SeriesSearchHelper`，根据 `RequiredJoin.Collection`、`BookMetadataAggregation`、`SeriesMetadata`、`ReadProgress` 补 join，再 `selectDistinct(*s.fields())` 查询系列。这里使用 `distinct` 是因为 join 聚合或多值表时可能产生重复系列。

写入流程更直接。以 `SeriesDao.insert` 为例，它用 `dslRW.insertInto(s).set(...).execute()`。批量场景会结合 `TempTable` 或 jOOQ batch，例如任务保存 `TasksDao.save(tasks)` 会把每个 `Task` 转为 upsert query，再按 `batchSize` 分块执行。

任务领取流程在 `TasksDao.takeFirst(owner)` 中比较典型：先用 `tasksAvailableCondition` 找到未被 owner 占用、且同 group 没有其他 owner 的任务，按 priority 降序和修改时间排序取一条，反序列化 payload 为 `Task`，再更新该任务的 `OWNER` 为当前 owner。

## 小白阅读顺序

先读 `KomgaJooqConfiguration.kt`，理解为什么有主库/任务库、读写/只读四个 `DSLContext`。

再读 `SplitDslDaoBase.kt`，这是理解所有 DAO 为什么同时拿 `dslRW` 和 `dslRO` 的关键。

接着读 `RequiredJoin.kt`、`SearchOperatorUtils.kt`、`ContentRestrictionsSearchHelper.kt`，先建立“搜索条件如何变 SQL 条件”的基础概念。

然后读 `BookSearchHelper.kt` 和 `SeriesSearchHelper.kt`。不要试图一口气记住所有分支，重点看它们如何递归处理 `AllOf` / `AnyOf`，以及什么时候返回额外的 `RequiredJoin`。

之后读 `BookDao.kt` 的 `findAll(searchCondition, searchContext, pageable)` 和 `SeriesDao.kt` 的同名方法。这两个方法展示了 helper 的结果如何真正变成 count、join、where、order、limit、offset。

再看几个简单 DAO，例如 `LibraryDao.kt`、`MediaDao.kt`、`ServerSettingsDao.kt`，熟悉普通 CRUD 模式。

最后读 `TasksDao.kt`，它使用独立 tasks 数据库，并展示 JSON payload、任务 owner、批量 upsert 这类和主库实体不同的访问模式。

## 常见误区

不要把 `dslRO` 理解成一定连接只读库。`SplitDslDaoBase` 会在非只读事务中让 `dslRO` 返回 `dslRW`，所以 DAO 代码里看似读操作也可能在事务内走读写 context。

不要以为搜索 helper 会直接修改 SQL join。helper 只返回 `RequiredJoin`，真正 join 哪张表由 `BookDao`、`SeriesDao` 决定。这是一种把“条件解析”和“查询组装”分开的设计。

不要忽略 `SearchContext`。同一个 `SearchCondition` 在不同用户、不同授权 library、不同内容限制下会生成不同结果。尤其阅读状态依赖 `context.userId`，没有 userId 时 helper 会返回 `falseCondition` 并记录 warning。

不要把 `ContentRestrictions.toCondition()` 和 `ContentRestrictionsSearchHelper` 混为一谈。前者在 `Utils.kt` 中直接返回 `Condition`，后者额外返回所需 join；搜索 helper 继承的是后者。

不要随便把大集合直接塞进 `IN` 条件。这个目录已经提供 `TempTable.withTempTable`，用于 URL、ID 等大量字符串集合，避免 SQL 过长或参数过多。

不要认为 `main` 下所有 DAO 都只服务领域层。有些 DAO 是 API DTO 或外部接口适配，例如 `BookDtoDao.kt`、`SeriesDtoDao.kt`、`KoboDtoDao.kt`，它们服务接口层的读模型，不一定等同于领域 Repository。
