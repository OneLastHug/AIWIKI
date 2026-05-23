# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/ReadStatus.kt

## 它负责什么

`ReadStatus.kt` 定义了 Komga 领域模型中的阅读状态枚举：

```kotlin
enum class ReadStatus {
  UNREAD,
  READ,
  IN_PROGRESS,
}
```

它本身不包含业务逻辑，只提供三个稳定的领域取值，用来描述“某个用户对书籍或系列的阅读状态”。在仓库中，它主要服务于搜索、筛选、REST API 查询参数、OPDS 入口以及数据库查询条件生成。

这个文件位于 `org.gotson.komga.domain.model` 包下，说明它属于核心领域模型，而不是某个接口层或数据库层的私有概念。上层接口可以接收它，下层查询层可以解释它，但状态名本身由领域层统一定义。

## 关键组成

`ReadStatus` 有三个枚举值：

`UNREAD`

表示未读。对单本书而言，当前用户没有对应的阅读进度记录。根据 `BookSearchHelper.kt` 的查询逻辑，书籍未读对应 `READ_PROGRESS.COMPLETED` 为 `null`。

对系列而言，未读表示当前用户对该系列没有聚合阅读记录。根据 `SeriesSearchHelper.kt` 的查询逻辑，系列未读对应 `READ_PROGRESS_SERIES.READ_COUNT` 为 `null`。

`READ`

表示已读。对单本书而言，当前用户的阅读进度存在，并且 `ReadProgress.completed == true`。

`ReadProgress.kt` 中可以看到阅读进度模型包含：

```kotlin
val page: Int
val completed: Boolean
val readDate: LocalDateTime
```

所以 `READ` 并不是由页码直接判断，而是由 `completed` 布尔值判断。

对系列而言，`READ` 表示系列内已读书籍数等于系列书籍总数，即 `READ_PROGRESS_SERIES.READ_COUNT == SERIES.BOOK_COUNT`。

`IN_PROGRESS`

表示阅读中。对单本书而言，当前用户有阅读进度记录，但 `completed == false`。

对系列而言，阅读中表示当前用户读过系列中的一部分书，但未读完整个系列。根据当前片段，判断条件是 `READ_PROGRESS_SERIES.READ_COUNT != SERIES.BOOK_COUNT`。这个判断建立在有阅读进度聚合记录的前提下；如果没有记录，会落入 `UNREAD`。

## 上下游关系

上游主要来自接口层和搜索条件构建。

REST API 中多个 Controller 会把请求参数 `read_status` 解析为 `List<ReadStatus>`，例如：

`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/BookController.kt`

其中 `read_status` 参数会被转换为搜索条件：

```kotlin
SearchCondition.ReadStatus(SearchOperator.Is(it))
```

类似使用也出现在：

`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/SeriesController.kt`、`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/ReadListController.kt`、`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/SeriesCollectionController.kt`

OPDS 接口也会使用该状态，尤其是筛选继续阅读内容时使用 `ReadStatus.IN_PROGRESS`，相关文件包括：

`komga/src/main/kotlin/org/gotson/komga/interfaces/api/opds/v1/OpdsController.kt`、`komga/src/main/kotlin/org/gotson/komga/interfaces/api/opds/v2/Opds2Controller.kt`

中间层是搜索模型。

`komga/src/main/kotlin/org/gotson/komga/domain/model/SearchCondition.kt` 中定义了一个同名但不同层次的搜索条件类：

```kotlin
data class ReadStatus(
  @JsonProperty("readStatus")
  val operator: SearchOperator.Equality<org.gotson.komga.domain.model.ReadStatus>,
) : Book,
  Series
```

这里要注意两个 `ReadStatus`：

`org.gotson.komga.domain.model.ReadStatus` 是当前文件里的枚举。

`SearchCondition.ReadStatus` 是搜索条件类型，里面包了一层 `SearchOperator.Equality<ReadStatus>`。

下游主要是 JOOQ 查询翻译层。

`komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/BookSearchHelper.kt` 负责把书籍搜索里的阅读状态转换成 SQL 条件。

对书籍：

`Is(UNREAD)` 转为 `READ_PROGRESS.COMPLETED is null`

`Is(READ)` 转为 `READ_PROGRESS.COMPLETED is true`

`Is(IN_PROGRESS)` 转为 `READ_PROGRESS.COMPLETED is false`

`IsNot(UNREAD)` 转为 `READ_PROGRESS.COMPLETED is not null`

`IsNot(READ)` 转为 `READ_PROGRESS.COMPLETED is null or false`

`IsNot(IN_PROGRESS)` 转为 `READ_PROGRESS.COMPLETED is true or null`

`komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/SeriesSearchHelper.kt` 负责系列搜索里的阅读状态转换。

对系列：

`Is(UNREAD)` 转为 `READ_PROGRESS_SERIES.READ_COUNT is null`

`Is(READ)` 转为 `READ_PROGRESS_SERIES.READ_COUNT == SERIES.BOOK_COUNT`

`Is(IN_PROGRESS)` 转为 `READ_PROGRESS_SERIES.READ_COUNT != SERIES.BOOK_COUNT`

`IsNot(UNREAD)` 转为 `READ_PROGRESS_SERIES.READ_COUNT is not null`

`IsNot(READ)` 转为 `READ_PROGRESS_SERIES.READ_COUNT != SERIES.BOOK_COUNT or null`

`IsNot(IN_PROGRESS)` 转为 `READ_PROGRESS_SERIES.READ_COUNT == SERIES.BOOK_COUNT or null`

此外，查询阅读状态时需要用户上下文。两个 helper 都检查 `context.userId`：如果没有 `userId`，会记录 warning，并返回 `DSL.falseCondition()`。这说明阅读状态是“用户相关”的状态，不是书籍或系列自身的全局属性。

## 运行/调用流程

一个典型的书籍列表按阅读状态筛选流程如下：

1. 客户端请求接口，例如传入查询参数 `read_status=IN_PROGRESS`。
2. Spring MVC 将请求参数绑定为 `ReadStatus.IN_PROGRESS`。由于它是 Kotlin enum，参数值需要匹配枚举名。
3. Controller 把该枚举包装成搜索条件：`SearchCondition.ReadStatus(SearchOperator.Is(ReadStatus.IN_PROGRESS))`。
4. 搜索对象继续传入 DAO 或查询服务。
5. `BookSearchHelper.kt` 看到 `SearchCondition.ReadStatus`。
6. helper 检查 `SearchContext` 中是否有 `userId`。
7. 有 `userId` 时，查询层 join 当前用户的 `READ_PROGRESS`。
8. `IN_PROGRESS` 被翻译成 `READ_PROGRESS.COMPLETED is false`。
9. 数据库返回符合条件的书籍。

系列筛选流程类似，但判断对象不是单本书的 `completed` 字段，而是系列阅读聚合表中的 `READ_COUNT` 与 `SERIES.BOOK_COUNT`。

根据当前片段推断，`ReadProgress` 是更底层的实际阅读记录，`ReadStatus` 是面向搜索和接口表达的归纳状态。依据是 `ReadProgress.kt` 保存了 `bookId`、`userId`、`page`、`completed` 等实际进度字段，而 `ReadStatus.kt` 只保存枚举值，真正解释枚举含义的是 `BookSearchHelper.kt` 和 `SeriesSearchHelper.kt`。

## 小白阅读顺序

建议先读当前文件：

`komga/src/main/kotlin/org/gotson/komga/domain/model/ReadStatus.kt`

先明确只有三个状态：`UNREAD`、`READ`、`IN_PROGRESS`。不要急着猜它们怎么计算，因为这个文件只定义“有哪些状态”。

第二步读实际进度模型：

`komga/src/main/kotlin/org/gotson/komga/domain/model/ReadProgress.kt`

重点看 `bookId`、`userId`、`page`、`completed`。这里能理解为什么阅读状态是用户相关的，也能理解单本书的 `READ` 和 `IN_PROGRESS` 最终依赖 `completed` 字段。

第三步读搜索条件：

`komga/src/main/kotlin/org/gotson/komga/domain/model/SearchCondition.kt`

重点看 `SearchCondition.ReadStatus`。这里说明当前枚举不会直接拿去查数据库，而是被包装成一个带操作符的搜索条件，例如 `Is(READ)` 或 `IsNot(UNREAD)`。

第四步读书籍查询翻译：

`komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/BookSearchHelper.kt`

重点看 `SearchCondition.ReadStatus` 分支。这里最直观地解释了单本书的三种状态如何映射到 `READ_PROGRESS.COMPLETED`。

第五步读系列查询翻译：

`komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/SeriesSearchHelper.kt`

重点看 `READ_PROGRESS_SERIES.READ_COUNT` 和 `SERIES.BOOK_COUNT` 的比较。这里能理解为什么“系列已读”不是简单的布尔值，而是“已读数量等于总数量”。

最后再看接口调用方：

`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/BookController.kt`、`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/SeriesController.kt`、`komga/src/main/kotlin/org/gotson/komga/interfaces/api/opds/v1/OpdsController.kt`、`komga/src/main/kotlin/org/gotson/komga/interfaces/api/opds/v2/Opds2Controller.kt`

这些文件可以帮助你理解 `ReadStatus` 如何暴露给 API，以及为什么前端或 OPDS 客户端可以用它来筛选内容。

## 常见误区

误区一：以为 `ReadStatus` 自己会计算阅读状态。

不会。当前文件只是 enum 定义，没有方法、属性或计算逻辑。真正的状态解释发生在查询 helper 中。

误区二：以为 `READ`、`UNREAD`、`IN_PROGRESS` 是书籍自身属性。

不是。它们是用户相关状态。相同一本书，对用户 A 可以是 `READ`，对用户 B 可以是 `UNREAD`。这也是为什么 `BookSearchHelper.kt` 和 `SeriesSearchHelper.kt` 在没有 `context.userId` 时直接返回 false 条件。

误区三：以为 `UNREAD` 等于 `completed == false`。

对单本书来说不是。根据 `BookSearchHelper.kt`，`UNREAD` 是 `READ_PROGRESS.COMPLETED is null`，表示没有阅读进度记录；`IN_PROGRESS` 才是 `completed == false`。

误区四：以为系列的 `IN_PROGRESS` 和书籍的 `IN_PROGRESS` 判断方式完全一样。

不一样。单本书看 `READ_PROGRESS.COMPLETED`；系列看 `READ_PROGRESS_SERIES.READ_COUNT` 和 `SERIES.BOOK_COUNT`。系列 `READ` 表示读完该系列全部书籍，`IN_PROGRESS` 表示读过但没读完全部。

误区五：忽略 `SearchCondition.ReadStatus` 和 `ReadStatus` 的命名差异。

`ReadStatus.kt` 里的 `ReadStatus` 是枚举。`SearchCondition.kt` 里的 `ReadStatus` 是搜索条件 data class。后者通过完整类型 `org.gotson.komga.domain.model.ReadStatus` 引用前者，避免名字冲突。阅读代码时要根据上下文区分。

误区六：以为 API 参数可以随便传小写值。

从当前 Kotlin enum 定义看，标准枚举名是 `UNREAD`、`READ`、`IN_PROGRESS`。Controller 中参数类型是 `List<ReadStatus>`，通常需要传入能被 Spring 转换为该枚举的值。是否有额外大小写转换配置，当前片段没有证据；根据当前片段推断，应优先使用枚举原名。
