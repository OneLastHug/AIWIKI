# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/ReadListRequest.kt

## 它负责什么

`ReadListRequest.kt` 定义了一组“阅读列表导入/匹配请求”的领域模型，主要用于把外部来源的阅读列表，例如 ComicRack 的 `.cbl` ReadingList，转换成 Komga 内部可以理解、可以匹配数据库书籍的结构。

它不是最终保存到数据库的阅读列表实体。最终实体是同目录下的 `ReadList.kt` 中的 `ReadList`，包含 `name`、`summary`、`ordered`、`bookIds`、`id`、审计时间等字段。而 `ReadListRequest.kt` 里的类型更像一个导入前的中间表示：先描述“用户想创建的阅读列表叫什么、包含哪些书”，再描述“这些请求中的书在当前库里匹配到了哪些候选 series/book”。

从调用关系看，这个文件服务于 `POST /readlists/match/comicrack` 这类“先上传 ComicRack 列表并检查匹配结果”的流程，而不是直接创建 `ReadList`。

## 关键组成

### `ReadListRequest`

```kotlin
data class ReadListRequest(
  val name: String,
  val books: List<ReadListRequestBook>,
)
```

这是一次创建阅读列表请求的顶层对象。

字段含义：

- `name: String`：请求创建的阅读列表名称，来自外部列表的名称，例如 ComicRack ReadingList 的 `Name`。
- `books: List<ReadListRequestBook>`：列表中每一本书的请求信息。

它只保存“请求要找什么”，不保存匹配结果，也不保存最终阅读列表的 `bookIds`。

### `ReadListRequestBook`

```kotlin
data class ReadListRequestBook(
  val series: Set<String>,
  val number: String,
)
```

表示外部列表中的一本书。

字段含义：

- `series: Set<String>`：可能的 series 名称集合。
- `number: String`：书籍编号。

这里 `series` 使用 `Set<String>` 而不是单个 `String`，是因为 ComicRack 导入时会根据 `series` 和 `volume` 推导出多个候选 series 名称。`ReadListProvider` 中会构造：

```kotlin
val series = setOfNotNull(
  computeSeriesFromSeriesAndVolume(it.series, it.volume),
  it.series?.ifBlank { null },
)
```

也就是说，同一本外部书籍可能同时尝试匹配“带 volume 规则推导出的标题”和“原始 series 标题”。

### `ReadListRequestMatch`

```kotlin
data class ReadListRequestMatch(
  val readListMatch: ReadListMatch,
  val requests: Collection<ReadListRequestBookMatches>,
  val errorCode: String = "",
)
```

表示整个阅读列表请求的匹配结果。

字段含义：

- `readListMatch`：阅读列表名称层面的匹配信息，例如名称是否重复。
- `requests`：每一本请求书籍的匹配结果集合。
- `errorCode`：整体错误码，默认空字符串。

当前读到的 `ReadListMatcher` 中返回 `ReadListRequestMatch(readListMatch, matches)`，没有显式设置顶层 `errorCode`，所以它通常保持默认值。根据当前片段推断，这个字段是为接口统一错误结构或未来扩展保留的。

### `ReadListMatch`

```kotlin
data class ReadListMatch(
  val name: String,
  val errorCode: String = "",
)
```

表示阅读列表名称本身的匹配状态。

`ReadListMatcher.matchReadListRequest` 会调用 `readListRepository.existsByName(request.name)`。如果已有同名阅读列表，就返回：

```kotlin
ReadListMatch(request.name, "ERR_1009")
```

否则返回：

```kotlin
ReadListMatch(request.name)
```

所以 `ERR_1009` 在这里表示阅读列表名称冲突。该模型本身不抛异常，而是把错误码作为匹配结果的一部分返回给前端，让前端可以展示“这个列表名已经存在”之类的信息。

### `ReadListRequestBookMatches`

```kotlin
data class ReadListRequestBookMatches(
  val request: ReadListRequestBook,
  val matches: Map<ReadListRequestBookMatchSeries, Collection<ReadListRequestBookMatchBook>>,
)
```

表示“某一本请求书籍”对应的匹配结果。

字段含义：

- `request`：原始请求书籍，即外部列表里要找的 series 和 number。
- `matches`：按匹配到的 series 分组的候选书籍。

`matches` 的 key 是 `ReadListRequestBookMatchSeries`，value 是这个 series 下匹配到的 `ReadListRequestBookMatchBook` 集合。这样设计的好处是：同一个请求项可以匹配到多个 series，而每个 series 下又可以有一个或多个 book 候选。

### `ReadListRequestBookMatchSeries`

```kotlin
data class ReadListRequestBookMatchSeries(
  val id: String,
  val title: String,
  val releaseDate: LocalDate?,
)
```

表示匹配到的 series 候选。

字段含义：

- `id: String`：Komga 内部 series id。
- `title: String`：series 标题。
- `releaseDate: LocalDate?`：聚合得到的发布日期，可以为空。

这是本文件唯一引入 `java.time.LocalDate` 的原因。它不是请求输入字段，而是匹配结果中给用户辅助判断候选 series 的上下文信息。

### `ReadListRequestBookMatchBook`

```kotlin
data class ReadListRequestBookMatchBook(
  val id: String,
  val number: String,
  val title: String,
)
```

表示匹配到的 book 候选。

字段含义：

- `id: String`：Komga 内部 book id。
- `number: String`：书籍编号。
- `title: String`：书籍标题。

这个对象也不是外部输入，而是数据库匹配结果。

## 上下游关系

### 上游：ComicRack `.cbl` 导入

主要上游在 `komga/src/main/kotlin/org/gotson/komga/infrastructure/metadata/comicrack/ReadListProvider.kt`。

`ReadListProvider.importFromCbl(cbl: ByteArray)` 会：

1. 使用 `XmlMapper` 把上传的 CBL XML 解析成 `ReadingList` DTO。
2. 校验 `readingList.name` 不能为空。
3. 校验 `readingList.books` 不能为空。
4. 遍历每个外部 book，要求 `series` 非空且 `number` 不为 `null`。
5. 计算候选 series 名称集合。
6. 创建 `ReadListRequestBook(series, number)`。
7. 返回 `ReadListRequest(name = readingList.name!!, books = books)`。

相关异常包括：

- `ERR_1015`：解析 ComicRack ReadingList 失败。
- `ERR_1030`：ReadingList 缺少 `Name`。
- `ERR_1029`：ReadingList 不包含任何 `Book`。
- `ERR_1031`：某个 Book 缺少 series 或 number。

所以 `ReadListRequest.kt` 的输入可信度不是完全裸奔的，ComicRack provider 已经做了基础格式校验。

### 中游：领域匹配服务

主要中游在 `komga/src/main/kotlin/org/gotson/komga/domain/service/ReadListMatcher.kt`。

`ReadListMatcher.matchReadListRequest(request: ReadListRequest)` 会处理两个层面的匹配：

1. 阅读列表名称匹配：通过 `ReadListRepository.existsByName(request.name)` 检查是否重名。
2. 请求书籍匹配：通过 `ReadListRequestRepository.matchBookRequests(request.books)` 查找每个请求项对应的数据库候选书籍。

最终组装：

```kotlin
ReadListRequestMatch(readListMatch, matches)
```

也就是说，`ReadListRequest.kt` 中的类型既是服务输入，也是服务输出的一部分。

### 下游：数据库查询实现

主要下游在 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/ReadListRequestDao.kt`。

`ReadListRequestDao.matchBookRequests` 实现了 `ReadListRequestRepository`，接收：

```kotlin
Collection<ReadListRequestBook>
```

并返回：

```kotlin
Collection<ReadListRequestBookMatches>
```

它的核心做法是：

1. 把请求中的每个 `ReadListRequestBook` 展开成临时表行。
2. 如果一个请求书籍有多个 series 候选，就会展开成多行。
3. 用请求的 `series` 去匹配 `SERIES_METADATA.TITLE`，并使用 `noCase()` 做大小写不敏感匹配。
4. 用请求的 `number` 去匹配 `BOOK_METADATA.NUMBER`。
5. 对编号匹配使用 `ltrim(..., "0")`，因此 `001` 和 `1` 这类编号可以匹配。
6. 查询结果按请求索引分组，再构造 `ReadListRequestBookMatches`。
7. 每个请求即使没有匹配结果，也会返回一个 `matches = emptyMap()` 的结果对象。

这个 DAO 会生成：

- `ReadListRequestBookMatchSeries(id, title, releaseDate)`
- `ReadListRequestBookMatchBook(id, number, title)`

因此 `ReadListRequest.kt` 中的 match 类型直接承载数据库查询结果。

### 下游：REST 接口 DTO

REST 暴露层相关文件包括：

- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/ReadListController.kt`
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/ReadListRequestMatchDto.kt`

`ReadListController` 中的入口是：

```kotlin
@PostMapping("match/comicrack", consumes = [MediaType.MULTIPART_FORM_DATA_VALUE])
fun matchComicRackList(
  @RequestParam("file") file: MultipartFile,
): ReadListRequestMatchDto =
  readListLifecycle.matchComicRackList(file.bytes).toDto()
```

也就是说，客户端上传文件后，最终拿到的是 DTO，而不是 domain model 本身。

`ReadListRequestMatchDto.kt` 会把 domain model 转成接口输出结构：

- `ReadListRequestMatch` -> `ReadListRequestMatchDto`
- `ReadListMatch` -> `ReadListMatchDto`
- `ReadListRequestBook` -> `ReadListRequestBookDto`
- `ReadListRequestBookMatchSeries` -> `ReadListRequestBookMatchSeriesDto`
- `ReadListRequestBookMatchBook` -> `ReadListRequestBookMatchBookDto`

其中 `releaseDate` 使用：

```kotlin
@JsonFormat(pattern = "yyyy-MM-dd")
```

所以接口输出日期格式为 `yyyy-MM-dd`。

## 运行/调用流程

一次 ComicRack 阅读列表匹配的大致流程如下：

1. 管理员调用 REST 接口 `POST /readlists/match/comicrack`，上传 multipart 文件字段 `file`。
2. `ReadListController.matchComicRackList` 读取 `file.bytes`。
3. Controller 调用 `readListLifecycle.matchComicRackList(file.bytes)`。
4. 根据引用位置可知，`ReadListLifecycle.matchComicRackList` 会先调用 `ReadListProvider.importFromCbl`，把 CBL 内容转成 `ReadListRequest`。
5. `ReadListProvider` 校验 XML、列表名、书籍条目，然后为每个外部 book 生成 `ReadListRequestBook`。
6. `ReadListLifecycle` 把 `ReadListRequest` 交给 `ReadListMatcher.matchReadListRequest`。
7. `ReadListMatcher` 检查目标阅读列表名称是否已经存在：
   - 如果重名，`ReadListMatch.errorCode = "ERR_1009"`。
   - 如果不重名，`ReadListMatch.errorCode = ""`。
8. `ReadListMatcher` 调用 `ReadListRequestRepository.matchBookRequests(request.books)`。
9. `ReadListRequestDao` 使用 JOOQ 构造临时请求表，把请求 series/number 和数据库中的 series/book metadata 匹配。
10. DAO 返回每个请求项的候选 series/book 分组。
11. `ReadListMatcher` 组装 `ReadListRequestMatch`。
12. Controller 调用 `.toDto()` 转换为 `ReadListRequestMatchDto`。
13. REST 接口返回给前端，前端可以让用户确认哪些候选书籍应该进入最终阅读列表。

需要注意：这个流程只是“match”，不是“create”。真正创建阅读列表的接口在同一个 controller 中另有 `@PostMapping`，接收 `ReadListCreationDto`，然后构造 `ReadList` 并调用 `readListLifecycle.addReadList(...)`。

## 小白阅读顺序

1. 先读 `komga/src/main/kotlin/org/gotson/komga/domain/model/ReadListRequest.kt`  
   重点看清楚哪些类是请求输入，哪些类是匹配输出。`ReadListRequest` 和 `ReadListRequestBook` 是外部导入后的请求；`ReadListRequestMatch`、`ReadListMatch`、`ReadListRequestBookMatches`、`ReadListRequestBookMatchSeries`、`ReadListRequestBookMatchBook` 是匹配结果。

2. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/model/ReadList.kt`  
   对比 `ReadListRequest` 和 `ReadList`。前者是“想创建什么以及匹配到了什么”，后者是“系统里真正保存的阅读列表”。

3. 然后读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/metadata/comicrack/ReadListProvider.kt`  
   看 `ReadListRequest` 是如何从 ComicRack CBL 文件来的。这里能解释为什么 `ReadListRequestBook.series` 是 `Set<String>`，以及为什么有一堆 `ERR_10xx` 错误码。

4. 接着读 `komga/src/main/kotlin/org/gotson/komga/domain/service/ReadListMatcher.kt`  
   这里是领域层的核心编排：检查阅读列表名是否冲突，然后把书籍请求交给 repository 匹配。

5. 再读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/ReadListRequestDao.kt`  
   这里是最具体的匹配逻辑。重点看 `values(*requestsAsRows.toTypedArray())` 如何把请求变成临时表，以及 `SERIES_METADATA`、`BOOK`、`BOOK_METADATA`、`BOOK_METADATA_AGGREGATION` 如何参与匹配。

6. 最后读 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/ReadListRequestMatchDto.kt` 和 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/ReadListController.kt`  
   看 domain model 如何变成 REST 输出，以及哪个接口触发这一整条链路。

## 常见误区

1. 不要把 `ReadListRequest` 当成最终的阅读列表实体。  
   最终实体是 `ReadList`，里面有 `bookIds`、`ordered`、`summary`、`id`、审计时间等字段。`ReadListRequest` 只是导入和匹配阶段的请求模型。

2. `ReadListRequestBook.series` 不是“这本书属于多个系列”的业务含义。  
   它更准确地说是“为了匹配同一本外部书籍，尝试使用的多个 series 名称候选”。这些候选可能来自 ComicRack 的 `Series` 和 `Volume` 组合推导。

3. `ReadListRequestMatch.errorCode` 和 `ReadListMatch.errorCode` 不是一回事。  
   `ReadListMatch.errorCode` 当前用于表达阅读列表名称是否冲突，例如 `ERR_1009`。顶层 `ReadListRequestMatch.errorCode` 在当前读到的主流程中没有被显式设置，默认是空字符串。根据当前片段推断，它可能是为了整体请求级错误预留的字段。

4. 匹配结果为空不一定是异常。  
   `ReadListRequestDao.matchBookRequests` 会对每个请求项返回一个 `ReadListRequestBookMatches`。如果没匹配到数据库里的书，`matches` 是空 map，而不是抛异常。

5. 编号匹配不是简单字符串完全相等。  
   DAO 中使用 `ltrim(number, "0")`，说明 `001` 和 `1` 这类编号可以被视为相同。同时还用了 `noCase()`，说明匹配时考虑了大小写不敏感。

6. 这个文件没有业务方法，不代表它不重要。  
   它定义的是跨层传递的数据契约：ComicRack provider 生成它，domain service 消费并返回它，JOOQ DAO 生产其内部匹配结果，REST DTO 再把它暴露给客户端。字段一旦改变，会影响导入、匹配、接口输出多个层面。

7. `releaseDate` 属于匹配结果的 series 信息，不属于请求输入。  
   外部 CBL 请求里并没有要求传入 `releaseDate`。它来自数据库聚合表 `BOOK_METADATA_AGGREGATION`，用于帮助用户区分同名或相似 series 候选。
