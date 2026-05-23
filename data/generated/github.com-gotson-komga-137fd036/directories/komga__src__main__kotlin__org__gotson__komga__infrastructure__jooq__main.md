# 目录：`komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main`

## 它负责什么

这个目录是 Komga 的主数据库持久化实现层，核心任务是把领域层的仓库接口落到 jOOQ 查询上。根据当前片段推断，这里几乎每个 `*Dao.kt` 都是一个 Spring `@Component`，实现 `domain.persistence` 里的某个 repository 接口，然后直接访问生成的 jOOQ 表对象 `org.gotson.komga.jooq.main.Tables`。

它的职责不是业务编排，而是把“怎么查、怎么分页、怎么 join、怎么批量删改”这些 SQL 细节封装起来。典型例子有：

- `BookDao`、`SeriesDao`：实体级读写、分页搜索、批量处理
- `ReferentialDao`：作者、流派、标签这类“参考数据”查询
- `BookCommonDao`：更复杂的组合查询，比如 On Deck
- `*DtoDao`：直接产出 DTO 形状的查询结果
- `Thumbnail*Dao`：缩略图相关持久化
- `ServerSettingsDao`、`SyncPointDao`、`PageHashDao` 等：其他基础表操作

## 关键组成

这个目录里最关键的不是单个 DAO，而是它们共享的一套模式。

首先是基类 `SplitDslDaoBase`。它把写库 `dslRW` 和读库 `_dslRO` 分开，并且在当前事务是可写事务时，让 `dslRO` 自动切到 `dslRW`。也就是说，名字像“RO”，但实际是否走只读连接，要看事务上下文。这一点很容易误解。

其次是具体 DAO 的分工：

- `BookDao`：围绕 `BOOK`、`BOOK_METADATA`、`MEDIA`、`READ_PROGRESS` 做查找、分页、排序、批量过滤
- `SeriesDao`：围绕 `SERIES`、`SERIES_METADATA`、`READ_PROGRESS_SERIES` 做系列查询和 CRUD
- `ReferentialDao`：围绕作者、标签、流派、语言、共享标签等做聚合查询，包含大量 `selectDistinct`、`leftJoin`、`fetchCount`
- `BookCommonDao`：用 CTE 和自连接解决“第一本未读书”这类更复杂的关系问题
- `*DtoDao`：不是为了实体增删改，而是为了给接口层直接提供更适合返回的读模型

再往下看，这些类普遍依赖：

- `Tables` 和 jOOQ 生成的 record
- `BookSearchHelper`、`SeriesSearchHelper`、`RequiredJoin` 这类查询构造辅助
- `withTempTable` 处理大批量 `IN` 条件
- `toDomain()` 把数据库记录转成领域模型

## 上下游关系

上游一般是接口层和应用层。`ReferentialController` 直接注入 `ReferentialRepository`；`BookDao`、`SeriesDao` 则常被 `TaskHandler`、`BookImporter`、`SeriesController`、`CommonBookController`、`SseController` 等通过仓库接口调用。也就是说，这一层对外暴露的是“仓库能力”，不是 SQL。

下游是 jOOQ 和主库 schema。这里的 DAO 直接读写：

- `org.gotson.komga.jooq.main.Tables`
- 生成的 records，如 `BookRecord`、`SeriesRecord`
- 生成的字段和关联表

所以它的下游很“数据库化”，上游很“领域化”。中间的桥梁就是 repository 接口和 domain model 的转换。

## 运行/调用流程

典型流程是：

1. Controller 或 service 注入 repository 接口，例如 `ReferentialRepository`、`BookRepository`、`SeriesRepository`
2. Spring 运行时把接口绑定到这里的 `*Dao` 实现
3. DAO 用 `dslRO` 或 `dslRW` 构造 jOOQ 查询
4. 查询通过 `fetchInto(...)`、`fetchOneInto(...)`、`fetchCount(...)` 等取回结果
5. 通过 `toDomain()` 转成领域对象，或者在 `*DtoDao` 里直接拼成 DTO 所需结构
6. 返回给上层用于 API 响应、任务处理或内部服务逻辑

几个有代表性的执行细节：

- `BookDao.findAll(...)` 和 `SeriesDao.findAll(...)` 都会先根据搜索条件补 join，再做分页和排序
- `ReferentialDao.findAuthorsByName(...)` 先拼出动态条件，再单独 `fetchCount(query)` 做总数，最后返回 `PageImpl`
- `BookCommonDao.getBooksOnDeckQuery(...)` 用 CTE + 自连接找“每个系列里最早的未读书”
- 批量操作会用 `withTempTable(...)`，避免超长 `IN (...)`

## 小白阅读顺序

1. 先看 `SplitDslDaoBase.kt`，搞清楚读写 DSLContext 的切换规则
2. 再看 `BookDao.kt` 或 `SeriesDao.kt`，这些是最标准的实体 DAO，最能看懂基本套路
3. 接着看 `ReferentialDao.kt`，理解复杂查询、分页、过滤、联表的写法
4. 然后看 `BookCommonDao.kt`，它能帮助你理解 CTE、别名、自连接这类高级 SQL 组织方式
5. 最后再按兴趣看 `*DtoDao.kt` 和 `Thumbnail*Dao.kt`，它们能补全“读模型”和“资源型表”的做法

如果你只想快速建立直觉，优先看 `BookDao.kt`、`SeriesDao.kt`、`ReferentialDao.kt`、`SplitDslDaoBase.kt` 这四个文件就够了。

## 常见误区

- 误以为这里是业务层。不是，这里主要是持久化实现，业务规则大多在 domain service 和 application 层。
- 误以为 `dslRO` 一定只读。根据 `SplitDslDaoBase.kt`，在活动写事务里它会切到 `dslRW`。
- 误以为所有 DAO 都是在维护实体表。实际上 `BookCommonDao`、`ReferentialDao`、很多 `*DtoDao` 更像查询装配器，不是标准 CRUD。
- 误以为分页查询只要 `limit/offset` 就行。这里很多地方还要单独 `fetchCount(query)`，而且 join 条件会影响总数。
- 误以为 `main` 是应用启动入口。这里的 `main` 更像“主库 schema 的 jOOQ 持久化目录”，不是程序入口。

如果要把这目录当成学习起点，最有效的方法不是逐个背 DAO 名字，而是先认清它们共同依赖的基类、表对象和 repository 接口，再看一两个代表性查询是怎么从接口层一路落到 SQL 的。
