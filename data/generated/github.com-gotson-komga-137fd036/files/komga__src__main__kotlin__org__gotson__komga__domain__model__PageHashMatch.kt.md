# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/PageHashMatch.kt

## 它负责什么

`PageHashMatch.kt` 定义了领域模型 `PageHashMatch`，用于表示“某个页面哈希在书库中命中的一张具体页面”。

在 Komga 的重复页面检测逻辑里，页面会被计算出 `fileHash`。当系统按某个 hash 查询匹配项时，需要返回这个 hash 对应的所有实际页面位置，例如：

- 属于哪本书：`bookId`
- 书文件所在位置：`url`
- 是第几页：`pageNumber`
- 页面文件名：`fileName`
- 页面文件大小：`fileSize`
- 页面媒体类型：`mediaType`

因此，`PageHashMatch` 不是“哈希本身”的模型，而是“哈希命中结果”的模型。它把数据库中的 `MEDIA_PAGE` 和 `BOOK` 信息组装成一个更适合领域层、接口层使用的对象。

源码非常短：

```kotlin
package org.gotson.komga.domain.model

import java.net.URL

data class PageHashMatch(
  val bookId: String,
  val url: URL,
  val pageNumber: Int,
  val fileName: String,
  val fileSize: Long,
  val mediaType: String,
)
```

它位于 `org.gotson.komga.domain.model` 包下，属于领域模型层。

## 关键组成

`PageHashMatch` 是 Kotlin 的 `data class`。这意味着编译器会自动为它生成常用方法，例如 `equals`、`hashCode`、`toString`、`copy`，以及解构声明所需的 `componentN` 方法。它本身没有业务方法，主要职责是承载数据。

字段含义如下：

`bookId: String`

表示命中页面所属的书籍 ID。这个值来自数据库中的页面记录，具体在 `PageHashDao.findMatchesByHash` 中从 `MEDIA_PAGE.BOOK_ID` 读取。

`url: URL`

表示书籍文件的 URL。这里使用的是 `java.net.URL`，不是普通字符串。它在 DAO 层由数据库中的 `BOOK.URL` 字段转换而来：

```kotlin
url = URL(it.value2())
```

到了 REST DTO 层时，又会通过 `url.toFilePath()` 转换成字符串路径返回给 API 调用方。

`pageNumber: Int`

表示页面页码。需要注意，数据库里页面编号使用的是从 `0` 开始的数字，而 `PageHashMatch.pageNumber` 使用的是面向用户和上层业务的从 `1` 开始的页码。

在 `PageHashDao.findMatchesByHash` 中可以看到转换：

```kotlin
pageNumber = it.value3() + 1
```

所以如果数据库中的 `MEDIA_PAGE.NUMBER` 是 `0`，领域模型中的 `pageNumber` 会是 `1`。

`fileName: String`

表示页面文件名，例如压缩包里的图片文件名。它来自 `MEDIA_PAGE.FILE_NAME`。

`fileSize: Long`

表示该页面文件大小，来自 `MEDIA_PAGE.FILE_SIZE`。它会被用于展示，也会在删除重复页时重新构造 `BookPageNumbered`。

`mediaType: String`

表示页面媒体类型，来自 `MEDIA_PAGE.MEDIA_TYPE`，例如图片 MIME 类型。接口层和删除任务都会继续传递这个字段。

## 上下游关系

`PageHashMatch` 位于领域模型层，但它的实际使用路径跨越了持久化层、服务层和 REST 接口层。

上游主要是数据库查询实现：

- `komga/src/main/kotlin/org/gotson/komga/domain/persistence/PageHashRepository.kt`
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/PageHashDao.kt`

`PageHashRepository` 声明了方法：

```kotlin
fun findMatchesByHash(
  pageHash: String,
  pageable: Pageable,
): Page<PageHashMatch>
```

这说明从领域接口角度看，按页面 hash 查询匹配结果时，返回的是分页的 `PageHashMatch`。

真正构造 `PageHashMatch` 的位置在 `PageHashDao.findMatchesByHash`。该方法查询 `MEDIA_PAGE` 表，并左连接 `BOOK` 表：

```kotlin
.select(p.BOOK_ID, b.URL, p.NUMBER, p.FILE_NAME, p.FILE_SIZE, p.MEDIA_TYPE)
.from(p)
.leftJoin(b)
.on(p.BOOK_ID.eq(b.ID))
.where(p.FILE_HASH.eq(pageHash))
```

然后把查询结果映射成 `PageHashMatch`：

```kotlin
PageHashMatch(
  bookId = it.value1(),
  url = URL(it.value2()),
  pageNumber = it.value3() + 1,
  fileName = it.value4(),
  fileSize = it.value5(),
  mediaType = it.value6(),
)
```

下游主要有两类。

第一类是 REST API 展示和操作：

- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/PageHashController.kt`
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/PageHashMatchDto.kt`

`PageHashController.getPageHashMatches` 会调用 `pageHashRepository.findMatchesByHash`，再将 `PageHashMatch` 转成 `PageHashMatchDto` 返回：

```kotlin
pageHashRepository
  .findMatchesByHash(pageHash, page)
  .map { it.toDto() }
```

DTO 转换逻辑在 `PageHashMatchDto.kt`：

```kotlin
fun PageHashMatch.toDto() =
  PageHashMatchDto(
    bookId = bookId,
    url = url.toFilePath(),
    pageNumber = pageNumber,
    fileName = fileName,
    fileSize = fileSize,
    mediaType = mediaType,
  )
```

这里可以看出，领域层保留 `URL` 类型，接口层输出字符串形式的路径。

第二类是页面哈希生命周期服务：

- `komga/src/main/kotlin/org/gotson/komga/domain/service/PageHashLifecycle.kt`

`PageHashLifecycle.getPage` 会通过 hash 找到第一个匹配页面，然后读取对应书籍和页面内容：

```kotlin
val match = pageHashRepository.findMatchesByHash(pageHash, Pageable.ofSize(1)).firstOrNull() ?: return null
val book = bookRepository.findByIdOrNull(match.bookId) ?: return null

return bookLifecycle.getBookPage(book, match.pageNumber, resizeTo = resizeTo)
```

这说明 `PageHashMatch.bookId` 和 `PageHashMatch.pageNumber` 是后续定位实际页面内容的关键字段。

此外，`PageHashController.deleteDuplicatePagesByPageHash` 和 `deleteSingleMatchByPageHash` 会把 `PageHashMatch` 或对应 DTO 转换成 `BookPageNumbered`，再交给 `TaskEmitter.removeDuplicatePages` 执行删除重复页面任务。

相关模型还有：

- `komga/src/main/kotlin/org/gotson/komga/domain/model/PageHash.kt`
- `komga/src/main/kotlin/org/gotson/komga/domain/model/PageHashKnown.kt`
- `komga/src/main/kotlin/org/gotson/komga/domain/model/PageHashUnknown.kt`
- `komga/src/main/kotlin/org/gotson/komga/domain/model/BookPageNumbered.kt`

它们和 `PageHashMatch` 的关系可以这样理解：

`PageHash` 是 hash 基类，表示一个页面哈希值和可选大小。

`PageHashKnown` 表示已经被管理员或系统标记过的重复页面 hash，并携带处理动作，例如 `DELETE_AUTO`、`DELETE_MANUAL`、`IGNORE`。

`PageHashUnknown` 表示系统发现的未知重复 hash，通常是还没有被管理员确认处理策略的重复页面。

`PageHashMatch` 表示某个 hash 实际匹配到了哪些书、哪些页。

`BookPageNumbered` 表示可以被书籍页面处理逻辑使用的“带页码页面”，删除重复页时会由 `PageHashMatch` 转换而来。

## 运行/调用流程

典型调用流程可以分成“查看重复页”和“删除重复页”两条线。

查看重复页流程：

1. 管理端调用 REST 接口 `GET api/v1/page-hashes/{pageHash}`。
2. 请求进入 `PageHashController.getPageHashMatches`。
3. Controller 调用 `pageHashRepository.findMatchesByHash(pageHash, page)`。
4. `PageHashRepository` 的实现类 `PageHashDao` 执行 jOOQ 查询。
5. 查询 `MEDIA_PAGE` 表中 `FILE_HASH` 等于目标 hash 的页面。
6. 通过 `BOOK_ID` 左连接 `BOOK` 表，取得书籍 URL。
7. 每条数据库记录被转换成一个 `PageHashMatch`。
8. `PageHashMatch` 再通过 `toDto()` 转成 `PageHashMatchDto`。
9. REST API 返回分页结果给前端或调用方。

其中最关键的转换是：

```kotlin
MEDIA_PAGE + BOOK -> PageHashMatch -> PageHashMatchDto
```

获取重复页缩略图或页面内容的流程：

1. `PageHashLifecycle.getPage(pageHash, resizeTo)` 被调用。
2. 它用 `findMatchesByHash(pageHash, Pageable.ofSize(1))` 找到第一个匹配项。
3. 通过 `match.bookId` 查询书籍。
4. 通过 `match.pageNumber` 调用 `bookLifecycle.getBookPage` 获取实际页面内容。
5. 返回 `TypedBytes`，可用于生成或返回缩略图。

删除全部重复页流程：

1. 管理端调用 `POST api/v1/page-hashes/{pageHash}/delete-all`。
2. `PageHashController.deleteDuplicatePagesByPageHash` 查询该 hash 的全部匹配项。
3. Controller 按 `bookId` 分组。
4. 每个 `PageHashMatch` 被转换成 `BookPageNumbered`。
5. 调用 `taskEmitter.removeDuplicatePages(toRemove)` 发出删除任务。

转换时会保留这些信息：

```kotlin
BookPageNumbered(
  fileName = it.fileName,
  mediaType = it.mediaType,
  fileHash = pageHash,
  fileSize = it.fileSize,
  pageNumber = it.pageNumber,
)
```

删除单个匹配页流程：

1. 管理端调用 `POST api/v1/page-hashes/{pageHash}/delete-match`。
2. 请求体传入 `PageHashMatchDto`。
3. Controller 从 DTO 构造一个 `BookPageNumbered`。
4. 调用 `taskEmitter.removeDuplicatePages(bookId, pages)` 删除指定书籍中的指定页面。

根据当前片段推断，`PageHashMatch` 本身不负责校验“这个 match 是否真的属于传入的 pageHash”。在删除单个匹配页接口中，Controller 直接使用请求路径里的 `pageHash` 和请求体里的 `matchDto` 组装删除任务。实际安全性更多依赖接口权限、调用方行为以及后续任务处理逻辑。

## 小白阅读顺序

建议按下面顺序阅读，能更容易理解这个文件在系统里的位置。

第一步，先看当前文件：

`komga/src/main/kotlin/org/gotson/komga/domain/model/PageHashMatch.kt`

重点理解它只是一个 `data class`，没有主动逻辑，只负责描述“某个 hash 命中的页面”。

第二步，看同目录的哈希模型：

`komga/src/main/kotlin/org/gotson/komga/domain/model/PageHash.kt`

这里能看到页面 hash 的基础结构：`hash` 和 `size`。注意 `size` 如果传入负数会被归一为 `null`。

`komga/src/main/kotlin/org/gotson/komga/domain/model/PageHashKnown.kt`

这里能看到“已知重复 hash”的处理动作：`DELETE_AUTO`、`DELETE_MANUAL`、`IGNORE`。它还带有 `deleteCount`、`matchCount`、审计时间等信息。

`komga/src/main/kotlin/org/gotson/komga/domain/model/PageHashUnknown.kt`

这里能看到“未知重复 hash”的简单结构，主要是 `hash`、`size` 和 `matchCount`。

第三步，看仓储接口：

`komga/src/main/kotlin/org/gotson/komga/domain/persistence/PageHashRepository.kt`

重点看 `findMatchesByHash` 的签名。它告诉你，`PageHashMatch` 是通过“按 hash 查匹配项”这个仓储能力返回给上层的。

第四步，看 DAO 实现：

`komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/PageHashDao.kt`

重点看 `findMatchesByHash`。这里能看到字段来源、数据库表、排序分页、以及 `pageNumber = it.value3() + 1` 这个页码转换。

第五步，看 REST DTO：

`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/PageHashMatchDto.kt`

重点看 `PageHashMatch.toDto()`。这里能看到 `URL` 被转换成文件路径字符串，说明领域模型和 API 输出模型不是完全相同的类型。

第六步，看 Controller：

`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/PageHashController.kt`

重点看三个方法：

- `getPageHashMatches`
- `deleteDuplicatePagesByPageHash`
- `deleteSingleMatchByPageHash`

它们展示了 `PageHashMatch` 如何被 API 查询、展示，以及如何参与删除重复页面任务。

第七步，看服务层：

`komga/src/main/kotlin/org/gotson/komga/domain/service/PageHashLifecycle.kt`

重点看 `getPage` 和 `createOrUpdate`。这里能理解 `PageHashMatch` 如何帮助系统从一个 hash 定位到实际书籍页面，并用于生成已知 hash 的缩略图。

## 常见误区

误区一：以为 `PageHashMatch` 表示一个 hash。

实际上它表示的是“某个 hash 的一次命中结果”。一个 hash 可以对应多个 `PageHashMatch`，因为同一张重复图片可能出现在多本书或同一本书的多个页面里。真正表示 hash 本身的模型是 `PageHash`、`PageHashKnown`、`PageHashUnknown`。

误区二：以为 `pageNumber` 是数据库原始页码。

不是。数据库中的 `MEDIA_PAGE.NUMBER` 根据 DAO 代码看是从 `0` 开始的，而 `PageHashMatch.pageNumber` 是 `it.value3() + 1` 之后的结果。也就是说，它是面向业务和用户的从 `1` 开始的页码。后续 `bookLifecycle.getBookPage(book, match.pageNumber, ...)` 也直接使用这个页码。

误区三：以为 `url` 会原样返回给前端。

领域模型中 `url` 是 `java.net.URL` 类型，但 REST DTO 中会转换成字符串：

```kotlin
url = url.toFilePath()
```

所以 API 调用方看到的是 `PageHashMatchDto.url: String`，不是 Java/Kotlin 的 `URL` 对象。

误区四：以为这个文件里应该有查库逻辑。

`PageHashMatch.kt` 位于 `domain.model`，只定义数据结构。查库逻辑在 `PageHashDao.kt`，接口声明在 `PageHashRepository.kt`，HTTP 暴露在 `PageHashController.kt`。这是典型的分层设计：模型不直接依赖数据库和 Web 框架。

误区五：以为 `fileSize` 是书籍文件大小。

这里的 `fileSize` 来自 `MEDIA_PAGE.FILE_SIZE`，表示页面文件大小，不是整本书归档文件的大小。它在重复页面识别和删除任务中用于精确描述某一页。

误区六：以为 `mediaType` 一定是书籍媒体类型。

这里的 `mediaType` 同样来自 `MEDIA_PAGE.MEDIA_TYPE`，更准确地说是页面文件的媒体类型，例如某张图片的类型，而不是整本书文件的类型。

误区七：以为 `PageHashMatch` 控制删除行为。

它不决定是否删除，也不包含删除策略。删除策略属于 `PageHashKnown.Action`，例如 `DELETE_AUTO`。`PageHashMatch` 只提供定位页面所需的数据。真正触发删除的是 `PageHashController` 调用 `TaskEmitter.removeDuplicatePages`，或者 `PageHashLifecycle.getBookPagesToDeleteAutomatically` 根据已知 hash 动作查出待删页面。

误区八：忽略 `bookId` 的重要性。

重复页面删除不是只靠页码就能完成的。相同页码可能出现在不同书里，所以必须结合 `bookId`。这也是 `deleteDuplicatePagesByPageHash` 会先按 `bookId` 分组的原因。

误区九：把 `PageHashMatchDto` 当成领域模型。

`PageHashMatchDto` 是接口层对象，负责对外传输。`PageHashMatch` 是领域模型，负责在领域层表达匹配结果。二者字段类似，但类型和用途不同，尤其是 `url` 字段：领域层是 `URL`，接口层是 `String`。

误区十：认为 `PageHashMatch` 可以单独判断重复页是否“未知”或“已知”。

不能。`PageHashMatch` 不保存 `hash` 字段，也不保存 `action`。它通常是由 `findMatchesByHash(pageHash, pageable)` 在已知某个 `pageHash` 的前提下查出来的。是否已知、是否自动删除，需要结合 `PageHashKnown`、`PageHashUnknown` 或调用入口来判断。
