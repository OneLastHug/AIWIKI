# 文件：komga/src/main/kotlin/org/gotson/komga/domain/service/ReadListMatcher.kt

## 它负责什么

`ReadListMatcher.kt` 定义了领域服务 `ReadListMatcher`，职责是对一个待导入的阅读列表请求 `ReadListRequest` 做“预匹配”。

这里的“匹配”不是直接创建 `ReadList`，而是在真正导入前回答两个问题：

1. 这个阅读列表名称是否已经存在。
2. 请求里的每一本书，在当前库中可能对应哪些 series 和 book。

它返回的是 `ReadListRequestMatch`，也就是一个匹配结果对象，供上层 API 展示给前端或导入流程继续使用。

典型场景是用户上传 ComicRack `.cbl` 阅读列表文件后，系统先解析出一个 `ReadListRequest`，再通过 `ReadListMatcher` 检查这个导入请求能否和现有 Komga 数据匹配。

## 关键组成

目标文件内容很短，主要由以下部分组成。

`package org.gotson.komga.domain.service`

说明它位于 domain service 层。它不是 REST 层，也不是数据库 DAO 层，而是领域逻辑协调层。

导入的领域模型包括：

- `ReadListRequest`：导入阅读列表的请求对象，包含 `name` 和 `books`。
- `ReadListMatch`：阅读列表自身的匹配结果，目前主要记录名称和错误码。
- `ReadListRequestMatch`：完整匹配结果，包含列表名匹配和书籍匹配集合。

导入的持久化接口包括：

- `ReadListRepository`：用于查询现有阅读列表，比如判断名称是否存在。
- `ReadListRequestRepository`：用于对请求中的书籍条目执行匹配。

类定义：

```kotlin
@Service
class ReadListMatcher(
  private val readListRepository: ReadListRepository,
  private val readListRequestRepository: ReadListRequestRepository,
)
```

`@Service` 表示它是 Spring 管理的服务 Bean。构造函数注入两个 repository，说明这个类本身不直接访问数据库实现，而是依赖领域持久化接口。

核心方法：

```kotlin
fun matchReadListRequest(request: ReadListRequest): ReadListRequestMatch
```

它接收一个 `ReadListRequest`，返回 `ReadListRequestMatch`。

方法内部第一步记录日志：

```kotlin
logger.info { "Trying to match $request" }
```

第二步判断阅读列表名称是否冲突：

```kotlin
val readListMatch =
  if (readListRepository.existsByName(request.name))
    ReadListMatch(request.name, "ERR_1009")
  else
    ReadListMatch(request.name)
```

如果已有同名阅读列表，则返回带错误码 `ERR_1009` 的 `ReadListMatch`；否则返回无错误码的 `ReadListMatch`。结合 `ReadListRequest.kt` 中 `ReadListMatch` 的定义：

```kotlin
data class ReadListMatch(
  val name: String,
  val errorCode: String = "",
)
```

可以看出空字符串代表没有错误。

第三步匹配请求里的书籍：

```kotlin
val matches = readListRequestRepository.matchBookRequests(request.books)
```

这里把 `request.books` 交给 `ReadListRequestRepository`，具体匹配逻辑不在 `ReadListMatcher` 中实现。根据接口定义：

```kotlin
interface ReadListRequestRepository {
  fun matchBookRequests(requests: Collection<ReadListRequestBook>): Collection<ReadListRequestBookMatches>
}
```

它会把多个 `ReadListRequestBook` 转成多个 `ReadListRequestBookMatches`。

最后组合返回：

```kotlin
return ReadListRequestMatch(readListMatch, matches)
```

`ReadListRequestMatch` 的结构在 `komga/src/main/kotlin/org/gotson/komga/domain/model/ReadListRequest.kt` 中：

```kotlin
data class ReadListRequestMatch(
  val readListMatch: ReadListMatch,
  val requests: Collection<ReadListRequestBookMatches>,
  val errorCode: String = "",
)
```

也就是说，最终结果有三层：

- 整体请求级别错误：`ReadListRequestMatch.errorCode`
- 阅读列表名称级别错误：`ReadListMatch.errorCode`
- 每个书籍请求的候选匹配：`ReadListRequestBookMatches.matches`

在当前目标文件中，`ReadListMatcher` 只设置 `ReadListMatch.errorCode`，没有设置 `ReadListRequestMatch.errorCode`。

## 上下游关系

上游调用方主要是 `ReadListLifecycle`。

在 `komga/src/main/kotlin/org/gotson/komga/domain/service/ReadListLifecycle.kt` 中有：

```kotlin
fun matchComicRackList(fileContent: ByteArray): ReadListRequestMatch {
  val request = readListProvider.importFromCbl(fileContent)

  return readListMatcher.matchReadListRequest(request)
}
```

这说明完整上游流程是：

1. 上层传入 ComicRack `.cbl` 文件内容 `fileContent`。
2. `ReadListProvider.importFromCbl(fileContent)` 把文件解析成 `ReadListRequest`。
3. `ReadListLifecycle` 调用 `ReadListMatcher.matchReadListRequest(request)`。
4. 返回 `ReadListRequestMatch`。

`ReadListProvider` 位于 `komga/src/main/kotlin/org/gotson/komga/infrastructure/metadata/comicrack/ReadListProvider.kt`。根据搜索结果，它会导入：

- `ReadListRequest`
- `ReadListRequestBook`

并在 `importFromCbl(cbl: ByteArray): ReadListRequest` 中把 ComicRack ReadingList 转为领域请求对象。它还会把每个书籍条目构造成：

```kotlin
ReadListRequestBook(series, it.number!!.trim())
```

根据当前片段推断，ComicRack `.cbl` 中的书籍至少会提供 series 信息和 number 信息，这正好对应：

```kotlin
data class ReadListRequestBook(
  val series: Set<String>,
  val number: String,
)
```

更上层是 REST API。搜索结果显示 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/ReadListController.kt` 中存在对 `ReadListRequestMatchDto` 的使用，并在约第 275 行返回 `ReadListRequestMatchDto`。由于命令预算限制没有完整展开 controller 注解，不能确认具体 HTTP 路径；根据当前片段推断，它提供了一个读取列表导入匹配的接口，把领域对象转换成 DTO 返回给客户端。

下游依赖有两个。

第一个是 `ReadListRepository`，目标文件只使用：

```kotlin
existsByName(request.name)
```

其接口定义在 `komga/src/main/kotlin/org/gotson/komga/domain/persistence/ReadListRepository.kt`，用于判断数据库中是否已有同名阅读列表。搜索结果显示 jOOQ 实现在 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/ReadListDao.kt` 中实现了 `existsByName`。

第二个是 `ReadListRequestRepository`，目标文件使用：

```kotlin
matchBookRequests(request.books)
```

其接口定义在 `komga/src/main/kotlin/org/gotson/komga/domain/persistence/ReadListRequestRepository.kt`，jOOQ 实现在 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/ReadListRequestDao.kt`。搜索结果显示该 DAO 会构造：

- `ReadListRequestBookMatches`
- `ReadListRequestBookMatchSeries`
- `ReadListRequestBookMatchBook`

这说明具体的“书籍请求如何匹配现有 series/book”是在 infrastructure 层通过数据库查询完成的，`ReadListMatcher` 只负责协调和结果组装。

DTO 下游在 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/ReadListRequestMatchDto.kt`。搜索结果显示其中有：

- `ReadListRequestMatch.toDto()`
- `ReadListMatch.toDto()`
- `ReadListRequestBook.toDto()`
- `ReadListRequestBookMatchSeriesDto`
- `ReadListRequestBookMatchBookDto`

也就是说 `ReadListMatcher` 返回的领域模型会被 REST 层转换成 API 响应结构。

## 运行/调用流程

可以按一次 `.cbl` 导入预匹配来理解。

1. 用户或客户端上传 ComicRack 阅读列表文件。
2. REST 层的 `ReadListController` 接收请求。
3. Controller 调用 `ReadListLifecycle.matchComicRackList(fileContent)`。
4. `ReadListLifecycle` 使用 `ReadListProvider.importFromCbl(fileContent)` 解析文件。
5. `ReadListProvider` 返回 `ReadListRequest`，结构大致是：

```kotlin
ReadListRequest(
  name = "...",
  books = listOf(
    ReadListRequestBook(series = setOf(...), number = "...")
  )
)
```

6. `ReadListLifecycle` 把 `ReadListRequest` 传给 `ReadListMatcher.matchReadListRequest(request)`。
7. `ReadListMatcher` 先写日志：

```kotlin
Trying to match $request
```

8. `ReadListMatcher` 调用 `readListRepository.existsByName(request.name)`。

如果名称已经存在，生成：

```kotlin
ReadListMatch(request.name, "ERR_1009")
```

如果名称不存在，生成：

```kotlin
ReadListMatch(request.name)
```

9. `ReadListMatcher` 调用 `readListRequestRepository.matchBookRequests(request.books)`。

这里会对每个请求书籍寻找候选匹配。返回的每个 `ReadListRequestBookMatches` 包含：

```kotlin
data class ReadListRequestBookMatches(
  val request: ReadListRequestBook,
  val matches: Map<ReadListRequestBookMatchSeries, Collection<ReadListRequestBookMatchBook>>,
)
```

这个结构的含义是：一个请求条目可能匹配到多个 series，每个 series 下又可能有多个 book 候选。

10. `ReadListMatcher` 返回完整结果：

```kotlin
ReadListRequestMatch(readListMatch, matches)
```

11. REST DTO 层把领域结果转换成 `ReadListRequestMatchDto` 返回给客户端。

这个流程中，`ReadListMatcher` 的定位很清楚：它不是解析器，不负责读取 `.cbl`；也不是 DAO，不负责编写 SQL；也不是最终创建阅读列表的生命周期方法。它负责把“列表级校验”和“书籍级匹配”合并成一个领域结果。

## 小白阅读顺序

建议按下面顺序读，不要一开始就跳进 DAO。

第一步，读目标文件 `komga/src/main/kotlin/org/gotson/komga/domain/service/ReadListMatcher.kt`。

先看它只有一个公开方法 `matchReadListRequest`。理解两个动作：

- 检查列表名是否重复。
- 匹配列表里的书籍。

第二步，读模型文件 `komga/src/main/kotlin/org/gotson/komga/domain/model/ReadListRequest.kt`。

重点看这些 data class：

- `ReadListRequest`
- `ReadListRequestBook`
- `ReadListRequestMatch`
- `ReadListMatch`
- `ReadListRequestBookMatches`
- `ReadListRequestBookMatchSeries`
- `ReadListRequestBookMatchBook`

这一步要搞清楚输入和输出结构。尤其是 `ReadListRequestBookMatches.matches` 是一个 `Map<Series, Collection<Book>>`，它表达的是“一个请求条目可以对应多个 series，每个 series 下有多个 book 候选”。

第三步，读接口 `komga/src/main/kotlin/org/gotson/komga/domain/persistence/ReadListRepository.kt` 和 `komga/src/main/kotlin/org/gotson/komga/domain/persistence/ReadListRequestRepository.kt`。

这里只需要看两个方法：

```kotlin
fun existsByName(name: String): Boolean
fun matchBookRequests(requests: Collection<ReadListRequestBook>): Collection<ReadListRequestBookMatches>
```

这能帮助理解 `ReadListMatcher` 为什么这么薄：它把数据库细节交给 repository。

第四步，读上游 `komga/src/main/kotlin/org/gotson/komga/domain/service/ReadListLifecycle.kt` 中的 `matchComicRackList`。

这个方法告诉你 `ReadListMatcher` 是怎么被业务流程调用的：`.cbl` 文件先被 `ReadListProvider` 解析，再进入 matcher。

第五步，再读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/metadata/comicrack/ReadListProvider.kt`。

这里可以理解 `ReadListRequest` 从哪里来。它负责把 ComicRack ReadingList 转成 Komga 的领域请求。

第六步，如果想深入匹配算法，再读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/ReadListRequestDao.kt`。

这里才是 `matchBookRequests` 的具体实现位置。目标文件不包含 SQL 或复杂匹配规则，所以不要在 `ReadListMatcher.kt` 里寻找这些细节。

## 常见误区

误区一：以为 `ReadListMatcher` 会创建阅读列表。

它不会创建 `ReadList`，也不会写入数据库。它只是返回 `ReadListRequestMatch`，用于预览或校验导入结果。真正创建、更新、删除阅读列表的逻辑应在 `ReadListLifecycle` 及相关 repository/DAO 中寻找。

误区二：以为 `ERR_1009` 是整个请求失败。

在目标文件中，`ERR_1009` 被放在 `ReadListMatch(request.name, "ERR_1009")` 里，也就是阅读列表名称匹配结果的错误码。`ReadListRequestMatch` 自己还有一个 `errorCode` 字段，但目标文件没有设置它。因此这里更准确地说是“列表名冲突错误”，不是整个匹配方法抛异常或直接失败。

误区三：以为书籍匹配逻辑在 `ReadListMatcher.kt`。

目标文件只调用：

```kotlin
readListRequestRepository.matchBookRequests(request.books)
```

具体怎么根据 series、number 找到候选 book，不在这个文件中。应继续查看 `ReadListRequestRepository` 的实现，也就是 jOOQ 层的 `ReadListRequestDao`。

误区四：忽略 `ReadListRequestBook.series` 是 `Set<String>`。

请求书籍的 series 不是单个字符串，而是 `Set<String>`。这表示同一个书籍请求可能带有多个 series 名称候选。根据当前片段推断，这可能来自 ComicRack 数据中对 series/title 的兼容处理。阅读匹配结果时，不要默认一个请求只会匹配一个 series。

误区五：把 `ReadListMatcher` 当成 REST DTO 转换器。

DTO 转换在 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/ReadListRequestMatchDto.kt`。`ReadListMatcher` 返回领域模型，不知道 API 响应格式，也不负责 JSON 字段结构。

误区六：认为 `@Service` 意味着这里应该包含所有业务细节。

在这个项目结构里，`@Service` 的 `ReadListMatcher` 更像一个领域协调器。它用 repository 接口组合几个判断，把结果整理成领域对象。具体解析在 `ReadListProvider`，具体数据库匹配在 `ReadListRequestDao`，API 输出在 DTO 层。理解这种分层，比只盯着一个文件更重要。
