# 目录：komga/src/main/kotlin/org/gotson/komga/domain/model

## 它负责什么
这个目录是 Komga 的领域模型层，集中放了“业务对象 + 值对象 + 查询 DSL + 事件”的定义。它不负责具体的数据库访问或接口处理，而是给上层的 REST、SSE、任务调度、搜索索引、Jooq DAO 提供统一的数据结构。  
从当前文件看，这里既有核心实体 `Book`、`Series`、`Library`、`KomgaUser`、`ReadProgress`，也有支撑这些实体的元数据与展示对象，如 `BookMetadata`、`SeriesMetadata`、`Media`、`ThumbnailBook` 等。另一个很重要的部分是搜索条件树 `SearchCondition` / `SearchOperator`，它把“查询意图”抽象成可序列化的模型，供控制层和持久层共同使用。

## 关键组成
1. 核心实体：`Book`、`Series`、`Library`、`KomgaUser`、`ReadProgress`、`Media`。这些对象都实现了 `Auditable`，统一带 `createdDate` 和 `lastModifiedDate`。
2. 元数据对象：`BookMetadata`、`SeriesMetadata`、`BookPage`、`MediaFile`、`Author`、`WebLink`、`AlternateTitle`。它们描述内容属性、排序信息、锁定状态、页信息和外部链接。
3. 展示与附件对象：`ThumbnailBook`、`ThumbnailSeries`、`ThumbnailSeriesCollection`、`ThumbnailReadList`。它们保存缩略图二进制、来源类型、尺寸、是否选中等信息。
4. 查询 DSL：`SearchCondition`、`SearchOperator`、`BookSearch`、`SeriesSearch`、`SearchContext`、`SearchField`、`SearchField`。其中 `SearchCondition` 用“Book / Series 两棵条件树”区分两类搜索域。
5. 事件模型：`DomainEvent`。它把库、书、系列、阅读进度、缩略图、用户变化统一成事件对象。
6. 其他支撑类型：`ContentRestrictions`、`AgeRestriction`、`UserRoles`、`ReadStatus`、`MediaProfile`、`MediaType`、`SyncPoint`、`KomgaSyncToken`、`R2Locator`、`R2Progression`、`Dimension` 等，用于权限、阅读状态、同步和媒体识别。

## 上下游关系
上游主要是接口层和应用服务层。比如 `SeriesController`、`ReadListController`、`TaskEmitter` 会构造 `SearchCondition`；`ContentRestrictionChecker`、`SearchContext` 会把当前用户权限带入查询；`KomgaOAuth2UserServiceConfiguration` 会创建 `KomgaUser`。  
下游主要是 Jooq DAO、搜索索引、SSE 和生命周期服务。`BookSearchHelper`、`SeriesSearchHelper` 把 `SearchCondition` 翻译成 SQL 条件；`SearchIndexLifecycle` 和 `SseController` 消费 `DomainEvent`；`BookDao`、`SeriesDtoDao`、`ReadProgressDao` 等把这些模型映射到表数据和 DTO。根据当前片段推断，这个目录里的模型是“接口层、服务层、持久层”之间的公共契约。

## 运行/调用流程
1. 请求进入 REST 控制器后，控制器会把筛选参数组装成 `BookSearch` 或 `SeriesSearch`，内部核心是 `SearchCondition`。
2. `SearchContext(user)` 会把当前用户的 `id`、`restrictions`、可访问库列表带入查询，DAO 侧据此决定是否加权限过滤。
3. `BookSearchHelper` 和 `SeriesSearchHelper` 将条件树转成 Jooq `Condition`，再查出对应的书、系列或聚合 DTO。
4. 扫描、导入、更新、删除等业务动作会创建或修改 `Book`、`Series`、`Media`、`Metadata`，随后发布 `DomainEvent`。
5. `SearchIndexLifecycle` 用事件更新 Lucene 索引，`SseController` 用事件推送前端通知，缩略图生命周期服务则处理 `Thumbnail*` 对象的增删改。

## 小白阅读顺序
1. 先看 `Auditable.kt`，理解所有对象为何都有时间戳。
2. 再看 `Book.kt`、`Series.kt`、`Library.kt`、`KomgaUser.kt`，建立主实体地图。
3. 接着看 `BookMetadata.kt`、`SeriesMetadata.kt`、`Media.kt`、`BookPage.kt`，理解一本书和一个系列“内部装了什么”。
4. 然后看 `SearchOperator.kt`、`SearchCondition.kt`、`BookSearch.kt`、`SeriesSearch.kt`、`SearchContext.kt`，理解查询 DSL。
5. 最后看 `DomainEvent.kt` 和 `Thumbnail*.kt`，把事件流和资源附件补齐。
6. 想看真实调用，再回到 `interfaces/api/rest`、`application/tasks`、`infrastructure/jooq`、`infrastructure/search`、`interfaces/sse` 这几层。

## 常见误区
1. 以为这些文件只是“数据类堆放区”。实际上它们定义的是跨层契约，很多控制器、DAO、索引器都依赖它们。
2. 以为 `SearchCondition` 只是前端筛选参数。它同时是查询表达式树，后端 DAO 直接消费它。
3. 以为 `DomainEvent` 只是日志。它实际上驱动了 SSE 通知和搜索索引更新。
4. 忽略 `SearchContext` 的权限信息。查询结果是否可见，常常取决于这里带入的用户和库范围。
5. 把 `Book`、`Series` 和 `BookMetadata`、`SeriesMetadata` 混为一谈。前者是目录实体，后者是内容描述与锁定字段。
6. 以为缩略图对象只是图片容器。它们还记录类型、选择状态、尺寸和归属对象 ID，属于业务数据的一部分。
