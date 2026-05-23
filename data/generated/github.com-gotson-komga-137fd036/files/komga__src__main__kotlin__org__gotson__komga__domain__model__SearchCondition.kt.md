# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/SearchCondition.kt

## 它负责什么

`SearchCondition.kt` 定义了 Komga 领域层里的“结构化搜索条件模型”。它本身不执行搜索，也不直接生成 SQL，而是提供一套可序列化、可组合、类型受限的条件树，用来描述“我要按哪些字段、用什么运算符筛选 Book 或 Series”。

它解决的核心问题是：前端、REST/OPDS 接口、领域服务、DAO 查询层之间需要一种统一的查询表达方式。比如：

- 查询某个 library 下的所有未删除书籍；
- 查询 title 包含某个词的 series；
- 查询 readStatus 为 `IN_PROGRESS` 的 book；
- 查询 tag、author、genre、ageRating 等元数据条件；
- 用 `allOf` 表示多个条件同时满足，用 `anyOf` 表示多个条件满足任意一个。

这个文件是“查询条件的领域语言”，真正把它翻译成数据库查询的是 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/BookSearchHelper.kt` 和 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/SeriesSearchHelper.kt`。

## 关键组成

这个文件的外层是 `class SearchCondition`，里面集中放置多个嵌套类型。它更像一个命名空间，所有条件都以 `SearchCondition.Xxx` 的方式引用。

第一组核心类型是两个 sealed interface：

```kotlin
@JsonTypeInfo(use = JsonTypeInfo.Id.DEDUCTION)
sealed interface Book

@JsonTypeInfo(use = JsonTypeInfo.Id.DEDUCTION)
sealed interface Series
```

`Book` 表示“可用于书籍搜索的条件”，`Series` 表示“可用于系列搜索的条件”。一个条件类可以只实现其中一个接口，也可以同时实现两个接口。例如：

- `SeriesId` 只实现 `Book`，因为 book 可以按所属 series 过滤；
- `CollectionId` 只实现 `Series`，因为 collection 关联的是 series；
- `LibraryId` 同时实现 `Book` 和 `Series`，因为 book 和 series 都有 library 维度；
- `Title` 同时实现 `Book` 和 `Series`，两者都能按标题搜索；
- `MediaStatus` 只实现 `Book`，因为 media 状态属于具体 book；
- `SeriesStatus` 只实现 `Series`，因为它来自 series metadata。

`@JsonTypeInfo(use = JsonTypeInfo.Id.DEDUCTION)` 是这里非常关键的 Jackson 配置。它表示反序列化时不是靠显式的 `type` 字段判断条件类型，而是通过 JSON 字段形状推断。比如请求体里出现 `{"libraryId": ...}`，Jackson 可以推断这是 `SearchCondition.LibraryId`；出现 `{"anyOf": [...]}`，则推断为 `AnyOfBook` 或 `AnyOfSeries`，具体取决于目标类型是 `SearchCondition.Book` 还是 `SearchCondition.Series`。

第二组是逻辑组合条件：

```kotlin
data class AnyOfBook(
  @JsonProperty("anyOf")
  val conditions: List<Book>,
) : Book

data class AllOfBook(
  @JsonProperty("allOf")
  val conditions: List<Book>,
) : Book

data class AnyOfSeries(
  @JsonProperty("anyOf")
  val conditions: List<Series>,
) : Series

data class AllOfSeries(
  @JsonProperty("allOf")
  val conditions: List<Series>,
) : Series
```

它们负责构造条件树：

- `AllOfBook` / `AllOfSeries`：相当于 SQL 里的 `AND`；
- `AnyOfBook` / `AnyOfSeries`：相当于 SQL 里的 `OR`。

这些类还提供了 `vararg` 构造函数，方便 Kotlin 代码直接写：

```kotlin
SearchCondition.AllOfBook(
  SearchCondition.LibraryId(SearchOperator.Is(library.id)),
  SearchCondition.Deleted(SearchOperator.IsFalse),
)
```

而不用手动创建 `listOf(...)`。

第三组是字段条件。每个字段条件通常由两部分组成：

1. 条件名，例如 `LibraryId`、`Title`、`ReleaseDate`；
2. 对应的 `SearchOperator` 类型，例如 equality、string、date、boolean、numeric。

例如：

```kotlin
data class Title(
  @JsonProperty("title")
  val operator: SearchOperator.StringOp,
) : Book, Series
```

这表示 `title` 字段支持字符串类运算符，例如 `is`、`isNot`、`contains`、`beginsWith` 等。具体运算符定义在 `komga/src/main/kotlin/org/gotson/komga/domain/model/SearchOperator.kt`。

再例如：

```kotlin
data class Deleted(
  @JsonProperty("deleted")
  val operator: SearchOperator.Boolean,
) : Book, Series
```

`Deleted` 使用布尔运算符，只支持 `isTrue` / `isFalse` 这种语义。到了 jOOQ 查询层，book 的 `Deleted` 会被翻译为 `BOOK.DELETED_DATE is null / is not null`，series 的 `Deleted` 会被翻译为 `SERIES.DELETED_DATE is null / is not null`。

第四组是带 nullable 语义的匹配对象。

`AuthorMatch`：

```kotlin
@JsonInclude(JsonInclude.Include.NON_NULL)
data class AuthorMatch(
  val name: String? = null,
  val role: String? = null,
)
```

它用于 `Author` 条件：

```kotlin
data class Author(
  @JsonProperty("author")
  val operator: SearchOperator.Equality<AuthorMatch>,
) : Book, Series
```

`AuthorMatch` 可以只按作者名匹配，也可以只按角色匹配，或者同时按 name 和 role 匹配。`@JsonInclude(JsonInclude.Include.NON_NULL)` 让序列化时省略 null 字段，避免 JSON 里出现无意义的空字段。

`PosterMatch`：

```kotlin
@JsonInclude(JsonInclude.Include.NON_NULL)
data class PosterMatch(
  val type: Type? = null,
  val selected: Boolean? = null,
)
```

它用于 `Poster` 条件，只作用于 `Book`。`PosterMatch.Type` 枚举包含：

- `GENERATED`
- `SIDECAR`
- `USER_UPLOADED`

根据 `BookSearchHelper` 的实现，`PosterMatch` 最终会映射到 `THUMBNAIL_BOOK` 表，根据 thumbnail type 和 selected 状态筛选 book。

## 上下游关系

上游主要有三类。

第一类是 REST 控制器。比如 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/BookController.kt` 会根据请求参数拼出 `BookSearch`，内部包含 `SearchCondition.AllOfBook`、`AnyOfBook`、`LibraryId`、`MediaStatus`、`ReadStatus`、`Tag`、`ReleaseDate` 等条件。`SeriesController.kt`、`ReadListController.kt`、`SeriesCollectionController.kt` 也大量构造这些条件。

第二类是 OPDS 控制器。`komga/src/main/kotlin/org/gotson/komga/interfaces/api/opds/v1/OpdsController.kt` 和 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/opds/v2/Opds2Controller.kt` 会用这些条件构造 OPDS feed 所需的过滤查询，例如只查 `Media.Status.READY`、未删除、正在阅读、属于某个 library 的条目。

第三类是领域服务。例如 `LibraryContentLifecycle.kt`、`BookLifecycle.kt`、`SyncPointLifecycle.kt`、`TransientBookLifecycle.kt` 会在内部业务流程里构造条件，用于查找被删除内容、查找候选 series、同步进度相关 book 等。

中间包装层是两个搜索请求模型：

- `komga/src/main/kotlin/org/gotson/komga/domain/model/BookSearch.kt`
- `komga/src/main/kotlin/org/gotson/komga/domain/model/SeriesSearch.kt`

`BookSearch` 结构很薄：

```kotlin
data class BookSearch(
  val condition: SearchCondition.Book? = null,
  val fullTextSearch: String? = null,
)
```

`SeriesSearch` 类似，只是额外保留了一个带 `@Deprecated` 的 `regexSearch`，注释说明它只用于向后兼容，推荐使用 `SearchOperator.BeginsWith`。

下游主要是查询转换层：

- `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/BookSearchHelper.kt`
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/SeriesSearchHelper.kt`

这两个 helper 接收 `SearchCondition.Book?` 或 `SearchCondition.Series?`，再结合 `SearchContext`，生成：

```kotlin
Pair<Condition, Set<RequiredJoin>>
```

其中：

- `Condition` 是 jOOQ 的 SQL 条件；
- `RequiredJoin` 表示为了执行该条件必须补哪些 join，比如 `BookMetadata`、`SeriesMetadata`、`Media`、`ReadProgress`、`BookMetadataAggregation` 等。

再往下是 DAO，例如：

- `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/BookDao.kt`
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/SeriesDao.kt`
- `BookDtoDao.kt`
- `SeriesDtoDao.kt`

它们调用 helper，把结构化条件接入实际数据库查询。

## 运行/调用流程

典型调用流程可以按“构造条件树 -> 包装搜索对象 -> 转换为 SQL 条件 -> DAO 查询”理解。

以 book 查询为例：

1. 控制器或服务层构造 `SearchCondition.Book` 条件树。

   例如根据当前片段推断，一个常见结构是：

   ```kotlin
   SearchCondition.AllOfBook(
     SearchCondition.LibraryId(SearchOperator.Is(libraryId)),
     SearchCondition.MediaStatus(SearchOperator.Is(Media.Status.READY)),
     SearchCondition.Deleted(SearchOperator.IsFalse),
   )
   ```

   依据是 `BookController.kt`、`OpdsController.kt`、`Opds2Controller.kt` 中大量使用 `AllOfBook` 组合 library、media status、deleted 等条件。

2. 条件树被放进 `BookSearch`。

   ```kotlin
   BookSearch(condition = ...)
   ```

3. repository 或 DAO 收到 `BookSearch`，取出 `search.condition`。

   `BookDtoDao.kt` 中会调用：

   ```kotlin
   BookSearchHelper(context).toCondition(search.condition)
   ```

4. `BookSearchHelper` 先把搜索条件转换成 jOOQ `Condition`，再把 `SearchContext` 中的内容限制和授权 library 限制合并进去。

   它的 `toCondition(searchCondition)` 会做两件事：

   - `base = toCondition()`：根据 `context.restrictions` 和 `context.libraryIds` 生成基础限制；
   - `search = toConditionInternal(searchCondition)`：根据调用方传入的条件树生成查询条件；
   - 最后 `search.first.and(base.first)`，也就是用户搜索条件永远还要叠加权限和内容限制。

5. `toConditionInternal` 递归处理条件树。

   `AllOfBook` 会 fold 所有子条件，用 `.and(...)` 合并；`AnyOfBook` 会 fold 所有子条件，用 `.or(...)` 合并。`SeriesSearchHelper` 对 `AllOfSeries` 和 `AnyOfSeries` 也是同样模式。

6. 叶子条件被映射到具体表字段或子查询。

   例如 book：

   - `LibraryId` -> `Tables.BOOK.LIBRARY_ID`
   - `SeriesId` -> `Tables.BOOK.SERIES_ID`
   - `Title` -> `Tables.BOOK_METADATA.TITLE`，需要 `RequiredJoin.BookMetadata`
   - `MediaStatus` -> `Tables.MEDIA.STATUS`，需要 `RequiredJoin.Media`
   - `ReadStatus` -> `Tables.READ_PROGRESS.COMPLETED`，需要当前 `context.userId`
   - `Tag` -> 查询 `BOOK_METADATA_TAG`
   - `Author` -> 查询 `BOOK_METADATA_AUTHOR`
   - `Poster` -> 查询 `THUMBNAIL_BOOK`

   series：

   - `LibraryId` -> `Tables.SERIES.LIBRARY_ID`
   - `Title` -> `Tables.SERIES_METADATA.TITLE`
   - `TitleSort` -> `Tables.SERIES_METADATA.TITLE_SORT`
   - `SeriesStatus` -> `Tables.SERIES_METADATA.STATUS`
   - `ReadStatus` -> `Tables.READ_PROGRESS_SERIES.READ_COUNT`
   - `ReleaseDate` -> `Tables.BOOK_METADATA_AGGREGATION.RELEASE_DATE`
   - `Tag` -> 同时查 series metadata tag 和 book metadata aggregation tag
   - `Author` -> 查 `BOOK_METADATA_AGGREGATION_AUTHOR`
   - `Genre` -> 查 `SERIES_METADATA_GENRE`
   - `SharingLabel` -> 查 `SERIES_METADATA_SHARING`
   - `Complete` -> 比较 `SERIES_METADATA.TOTAL_BOOK_COUNT` 和 `SERIES.BOOK_COUNT`

7. DAO 根据返回的 `Condition` 和 `RequiredJoin` 构造最终 SQL，执行分页、排序和映射。

这个流程说明 `SearchCondition.kt` 是查询系统的“语法层”，`SearchOperator.kt` 是“运算符层”，`BookSearchHelper.kt` / `SeriesSearchHelper.kt` 是“解释器层”。

## 小白阅读顺序

建议先看 `SearchCondition.kt` 的两个接口：

```kotlin
sealed interface Book
sealed interface Series
```

先理解为什么同一个条件系统要分成 book 条件和 series 条件。判断方法很简单：看每个 data class 后面实现了哪些接口。比如 `ReadListId : Book` 就说明 read list 过滤只用于 book；`CollectionId : Series` 就说明 collection 过滤只用于 series。

第二步看 `AnyOfBook`、`AllOfBook`、`AnyOfSeries`、`AllOfSeries`。这四个类型是理解整个文件的入口。它们让条件可以嵌套，形成树，而不是只能平铺几个字段。

第三步看 `SearchOperator.kt`。`SearchCondition` 只描述“哪个字段”，`SearchOperator` 描述“怎么比较”。例如 `Title` 使用 `SearchOperator.StringOp`，所以它可以 contains、beginsWith；`Deleted` 使用 `SearchOperator.Boolean`，所以只能 true/false；`ReleaseDate` 使用 `SearchOperator.Date`，所以可以 before、after、isInTheLast。

第四步看 `BookSearch.kt` 和 `SeriesSearch.kt`。这两个文件会告诉你条件树如何进入搜索请求对象。它们很短，但能把“条件模型”和“接口请求体/仓储查询参数”连起来。

第五步看 `BookSearchHelper.kt`。先只看 `when (searchCondition)` 结构，不必一开始钻进每个 SQL 子查询。重点观察：

- `AllOfBook` 怎么变成 AND；
- `AnyOfBook` 怎么变成 OR；
- 每个叶子条件对应哪个数据库字段；
- 哪些条件需要 `RequiredJoin`。

第六步再看 `SeriesSearchHelper.kt`，对照 `BookSearchHelper.kt` 看差异。series 查询有更多聚合元数据，比如 `BOOK_METADATA_AGGREGATION`、`READ_PROGRESS_SERIES`、`SERIES_METADATA`，这能帮助理解 Komga 为什么把 book 和 series 搜索条件分开建模。

最后再回头看控制器，例如 `BookController.kt`、`SeriesController.kt`、`Opds2Controller.kt`。这时你会看到业务接口只是把请求参数翻译成 `SearchCondition` 条件树，然后交给仓储层处理。

## 常见误区

第一个误区：以为 `SearchCondition.kt` 会执行查询。它不会。这个文件只定义条件数据结构，不依赖 jOOQ，也不出现数据库表。真正执行或生成 SQL 条件的是 `BookSearchHelper.kt` 和 `SeriesSearchHelper.kt`。

第二个误区：以为 `Book` 和 `Series` 是实体模型。这里的 `SearchCondition.Book` 和 `SearchCondition.Series` 不是 `Book.kt` 或 `Series.kt` 里的业务实体，而是两个 sealed interface，用来限制某个搜索条件能用于 book 查询还是 series 查询。

第三个误区：以为 `AnyOfBook` 和 `AllOfBook` 可以和 `AnyOfSeries`、`AllOfSeries` 混用。它们不能随便混。`AnyOfBook` 的 `conditions` 类型是 `List<Book>`，只能放 book 条件；`AnyOfSeries` 的 `conditions` 类型是 `List<Series>`，只能放 series 条件。这个设计让很多错误在 Kotlin 类型层面就被挡住。

第四个误区：以为所有字段条件都能同时用于 book 和 series。并不是。是否可用要看类实现了哪个接口。例如：

- `MediaStatus` 只用于 book；
- `MediaProfile` 只用于 book；
- `Poster` 只用于 book；
- `CollectionId` 只用于 series；
- `Publisher`、`Language`、`Genre`、`AgeRating` 只用于 series；
- `LibraryId`、`Deleted`、`OneShot`、`Title`、`ReleaseDate`、`Tag`、`ReadStatus`、`Author` 可用于两者。

第五个误区：以为 `@JsonProperty("title")` 只是改字段名。它还参与了 Jackson 的 deduction 反序列化。因为 `Book` 和 `Series` 使用 `JsonTypeInfo.Id.DEDUCTION`，JSON 里的字段名形状会帮助 Jackson 判断具体是哪一个 data class。

第六个误区：以为 `ReadStatus` 是一个简单字段过滤。实际上 `ReadStatus` 依赖 `SearchContext.userId`。在 `BookSearchHelper.kt` 和 `SeriesSearchHelper.kt` 中，如果没有 userId，会记录警告并返回 `DSL.falseCondition()`。原因是阅读状态是按用户计算的，没有用户上下文就无法判断 unread/read/in progress。

第七个误区：以为 nullable operator 和普通 equality 一样。`Tag`、`Genre`、`SharingLabel`、`AgeRating` 使用的是 nullable 版本的 operator，例如 `EqualityNullable` 或 `NumericNullable`，因此支持 `isNull`、`isNotNull` 这类语义。普通 `Equality<T>` 不支持这些空值判断。

第八个误区：以为 `AuthorMatch(name = null, role = null)` 会匹配所有作者。根据 `BookSearchHelper.kt` 和 `SeriesSearchHelper.kt` 的处理，如果 `AuthorMatch` 的 `name` 和 `role` 都是 null，会返回 `DSL.noCondition()`，也就是不添加过滤条件。`PosterMatch` 对 `type` 和 `selected` 都为 null 的情况也是类似处理。

第九个误区：以为 `Deleted(false)` 对应数据库里的 boolean false。实际实现里 deleted 是通过删除时间字段判断的：`IsFalse` 对应 `DELETED_DATE is null`，`IsTrue` 对应 `DELETED_DATE is not null`。book 和 series 都是这个思路。

第十个误区：以为 `SearchCondition` 和 `fullTextSearch` 是一套机制。`BookSearch` / `SeriesSearch` 同时有 `condition` 和 `fullTextSearch` 字段，但 `SearchCondition.kt` 只负责结构化条件。全文搜索是另一个入口，不在这个文件中定义。
