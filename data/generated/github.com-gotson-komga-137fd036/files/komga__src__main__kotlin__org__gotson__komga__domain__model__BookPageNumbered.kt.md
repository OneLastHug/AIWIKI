# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/BookPageNumbered.kt

## 它负责什么

`BookPageNumbered.kt` 定义了领域模型 `BookPageNumbered`，它表示“带页码的书籍页面”。

在 Komga 的领域模型里，基础页面信息由 `BookPage` 表达：文件名、媒体类型、尺寸、哈希、文件大小。`BookPageNumbered` 在这些基础信息之上额外增加 `pageNumber: Int`，用于在业务流程中精确定位“这是一本书里的第几页”。

这个类本身不负责读取图片、不负责解析漫画压缩包、不负责数据库查询，也不负责删除页面。它只是一个轻量数据载体，主要服务于需要“页面内容身份 + 页面序号”同时存在的场景，例如：

- 根据页面哈希找到重复页；
- 把某些匹配到的页面加入删除任务；
- 删除时校验页面是否仍然位于预期页码；
- 记录“删除了第几页”的历史事件；
- 如果删除的是第一页，触发重新生成封面缩略图。

目标文件内容很短：

```kotlin
class BookPageNumbered(
  fileName: String,
  mediaType: String,
  dimension: Dimension? = null,
  fileHash: String = "",
  fileSize: Long? = null,
  val pageNumber: Int,
) : BookPage(...)
```

可以把它理解成：`BookPage` 是“页面本身的元信息”，`BookPageNumbered` 是“页面元信息 + 在书中的位置”。

## 关键组成

`BookPageNumbered` 位于包：

```kotlin
package org.gotson.komga.domain.model
```

它没有显式 `import`，因为它使用的 `BookPage` 和 `Dimension` 都在同一个包 `org.gotson.komga.domain.model` 下。

构造参数分为两类。

第一类是继承自 `BookPage` 的页面基础信息：

```kotlin
fileName: String
mediaType: String
dimension: Dimension? = null
fileHash: String = ""
fileSize: Long? = null
```

这些字段通过父类构造器传给 `BookPage`：

```kotlin
) : BookPage(
    fileName = fileName,
    mediaType = mediaType,
    dimension = dimension,
    fileHash = fileHash,
    fileSize = fileSize,
  )
```

父类 `BookPage` 定义在 `komga/src/main/kotlin/org/gotson/komga/domain/model/BookPage.kt`，字段含义大致如下：

- `fileName`：页面在媒体容器中的文件名，比如压缩包里的图片文件名；
- `mediaType`：页面文件的媒体类型，例如图片 MIME 类型；
- `dimension`：页面宽高，类型是 `Dimension?`，可为空；
- `fileHash`：页面文件哈希，默认空字符串；
- `fileSize`：页面文件大小，类型是 `Long?`，可为空。

`Dimension` 定义在 `komga/src/main/kotlin/org/gotson/komga/domain/model/Dimension.kt`：

```kotlin
data class Dimension(
  val width: Int,
  val height: Int,
)
```

第二类是 `BookPageNumbered` 自己新增的字段：

```kotlin
val pageNumber: Int
```

它没有默认值，说明调用方创建 `BookPageNumbered` 时必须明确提供页码。

此外，类中重写了 `toString()`：

```kotlin
override fun toString(): String =
  "BookPageNumbered(fileName='$fileName', mediaType='$mediaType', dimension=$dimension, fileHash='$fileHash', fileSize=$fileSize, pageNumber=$pageNumber)"
```

这个输出主要用于日志和调试。比如 `BookPageEditor` 删除页面时会打印 `Pages to delete: $pagesToDelete`，此时 `BookPageNumbered.toString()` 可以把文件名、哈希、页码等关键信息展示出来。

一个重要细节是：`BookPageNumbered` 不是 `data class`。因此它不会自动生成基于属性的 `equals()` / `hashCode()` / `copy()`。父类 `BookPage` 自己提供了一个 `copy()`，但返回类型是 `BookPage`，不是 `BookPageNumbered`。这意味着如果业务要保留 `pageNumber`，不能直接依赖父类 `copy()` 来复制出带页码对象。

## 上下游关系

上游主要有两类：数据库查询层和 REST 控制器层。

第一类上游是 `PageHashDao`，路径是 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/PageHashDao.kt`。

其中 `findMatchesByKnownHashAction(...)` 会从页面哈希表和已知哈希表中查出匹配页面，并构造 `BookPageNumbered`：

```kotlin
BookPageNumbered(
  fileName = it.value2(),
  pageNumber = it.value3() + 1,
  fileHash = it.value4(),
  mediaType = it.value5(),
  fileSize = it.value6(),
)
```

这里非常关键：数据库里的 `p.NUMBER` 看起来是从 `0` 开始的页序号，而领域对象里的 `pageNumber` 使用 `it.value3() + 1`，也就是转成从 `1` 开始的页码。

第二类上游是 `PageHashController`，路径是 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/PageHashController.kt`。

当用户或 API 请求删除某个页面哈希对应的匹配页时，控制器会把 `PageHashMatchDto` 或查询结果转换成 `BookPageNumbered`：

```kotlin
BookPageNumbered(
  fileName = it.fileName,
  mediaType = it.mediaType,
  fileHash = pageHash,
  fileSize = it.fileSize,
  pageNumber = it.pageNumber,
)
```

或者：

```kotlin
BookPageNumbered(
  fileName = matchDto.fileName,
  mediaType = matchDto.mediaType,
  fileHash = pageHash,
  fileSize = matchDto.fileSize,
  pageNumber = matchDto.pageNumber,
)
```

下游主要是任务系统、页面编辑服务和历史事件。

任务系统中，`Task.RemoveHashedPages` 定义在 `komga/src/main/kotlin/org/gotson/komga/application/tasks/Task.kt`：

```kotlin
class RemoveHashedPages(
  val bookId: String,
  val pages: Collection<BookPageNumbered>,
  priority: Int = DEFAULT_PRIORITY,
) : Task(priority)
```

它把“一本书 ID + 一组待删除的带页码页面”封装成后台任务。

核心消费方是 `BookPageEditor`，路径是 `komga/src/main/kotlin/org/gotson/komga/domain/service/BookPageEditor.kt`。它的方法签名是：

```kotlin
fun removeHashedPages(
  book: Book,
  pagesToDelete: Collection<BookPageNumbered>,
): BookAction?
```

删除时它会遍历当前媒体的 `media.pages`，并用 `BookPageNumbered` 里的多个字段共同确认要删除的是同一页：

```kotlin
candidate.fileHash == page.fileHash &&
candidate.mediaType == page.mediaType &&
candidate.fileName == page.fileName &&
candidate.pageNumber == index + 1
```

这里再次说明 `BookPageNumbered.pageNumber` 是从 `1` 开始的，因为当前列表下标 `index` 是从 `0` 开始，所以比较时使用 `index + 1`。

历史事件消费方是 `HistoricalEvent.DuplicatePageDeleted`，定义在 `komga/src/main/kotlin/org/gotson/komga/domain/model/HistoricalEvent.kt`：

```kotlin
class DuplicatePageDeleted(
  book: Book,
  page: BookPageNumbered,
)
```

它会把 `page.pageNumber` 写入事件属性：

```kotlin
"page number" to page.pageNumber.toString()
```

所以 `BookPageNumbered` 也承担了审计记录中的页码来源角色。

## 运行/调用流程

围绕 `BookPageNumbered` 的典型流程可以按“页面哈希匹配并删除重复页”来理解。

第一步，系统已经为书籍页面计算过哈希，并把页面信息存在数据库中。页面基础信息包括文件名、媒体类型、文件大小、哈希，以及数据库里的页面序号。

第二步，`PageHashDao.findMatchesByKnownHashAction(...)` 查询哪些页面哈希命中了某些已知动作，例如自动删除。查询结果会被转换为：

```kotlin
Map<String, Collection<BookPageNumbered>>
```

其中 `String` 是 `bookId`，`Collection<BookPageNumbered>` 是这本书里需要处理的页面集合。

在这个转换过程中，数据库页序号会被转为领域层页码：

```kotlin
pageNumber = it.value3() + 1
```

第三步，任务系统把这些页面打包成 `Task.RemoveHashedPages`。这个任务携带：

- `bookId`：要处理哪一本书；
- `pages`：要删除哪些带页码页面。

第四步，业务服务 `BookPageEditor.removeHashedPages(...)` 执行实际删除前会做校验。它不会只看 `pageNumber`，也不会只看 `fileHash`，而是同时比较：

- `fileHash`
- `mediaType`
- `fileName`
- `pageNumber`

其中 `pageNumber` 和当前 `media.pages` 的下标通过 `index + 1` 对齐。

这样做的目的，是避免书籍在扫描、替换、重新排序之后，错误删除了“哈希相同但位置或文件名不符合预期”的页面。根据当前片段推断，这是一种偏保守的安全校验，因为删除页面属于破坏性操作，需要确认目标仍然是原先匹配到的页面。

第五步，如果校验通过，`BookPageEditor` 会生成一个删除了指定页面的新临时 ZIP 文件，然后替换原书籍文件、重新扫描媒体信息、恢复页面哈希，并更新数据库。

第六步，删除完成后，每个被删除的 `BookPageNumbered` 会生成一条历史事件：

```kotlin
HistoricalEvent.DuplicatePageDeleted(book, it)
```

这个事件记录书籍路径和页码。

第七步，如果删除的页面中包含第一页：

```kotlin
return if (pagesToDelete.any { it.pageNumber == 1 }) BookAction.GENERATE_THUMBNAIL else null
```

服务会返回 `BookAction.GENERATE_THUMBNAIL`，表示后续需要重新生成封面缩略图。原因是第一页通常可能被用作封面或缩略图来源，删除第一页后旧缩略图可能已经不准确。

## 小白阅读顺序

建议按下面顺序读，不要一开始就跳到删除 ZIP 的实现细节里。

第一步，先读当前文件：

`komga/src/main/kotlin/org/gotson/komga/domain/model/BookPageNumbered.kt`

重点看它只做了一件事：继承 `BookPage`，增加 `pageNumber`。

第二步，读父类：

`komga/src/main/kotlin/org/gotson/komga/domain/model/BookPage.kt`

重点理解 `BookPage` 的字段，也就是“页面基础身份”由哪些信息组成。顺便注意 `BookPage.copy()` 返回的是 `BookPage`，不是 `BookPageNumbered`。

第三步，读尺寸模型：

`komga/src/main/kotlin/org/gotson/komga/domain/model/Dimension.kt`

这个文件很简单，只是宽高数据结构。读完后就知道 `dimension` 为什么可以为空，以及它不参与页码定位。

第四步，读创建来源：

`komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/PageHashDao.kt`

重点看 `findMatchesByKnownHashAction(...)` 中 `BookPageNumbered` 的构造方式，尤其是：

```kotlin
pageNumber = it.value3() + 1
```

这能帮助你建立“数据库页序号可能是 0-based，领域页码是 1-based”的概念。

第五步，读 API 手动删除入口：

`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/PageHashController.kt`

重点看控制器如何把 `PageHashMatchDto` 转成 `BookPageNumbered`，再交给任务系统。这里能看到它不仅服务自动删除，也服务用户通过 API 删除某个匹配页。

第六步，读任务定义：

`komga/src/main/kotlin/org/gotson/komga/application/tasks/Task.kt`

找到 `Task.RemoveHashedPages`，理解 `BookPageNumbered` 是如何被后台任务携带的。

第七步，读真正消费逻辑：

`komga/src/main/kotlin/org/gotson/komga/domain/service/BookPageEditor.kt`

重点看 `removeHashedPages(...)` 里的匹配条件：

```kotlin
candidate.fileHash == page.fileHash &&
candidate.mediaType == page.mediaType &&
candidate.fileName == page.fileName &&
candidate.pageNumber == index + 1
```

这段代码是理解 `BookPageNumbered` 价值的核心：它让删除逻辑既能识别页面内容，也能确认页面位置。

第八步，读历史事件：

`komga/src/main/kotlin/org/gotson/komga/domain/model/HistoricalEvent.kt`

找到 `DuplicatePageDeleted`，看 `pageNumber` 如何被写进审计事件。

## 常见误区

误区一：以为 `BookPageNumbered` 是普通 `BookPage` 的完全替代品。

不是。`BookPageNumbered` 是在需要页码时使用的增强类型。很多普通媒体页面列表仍然可以只用 `BookPage`。例如 `media.pages` 里通常是页面基础信息，删除候选才需要额外携带 `pageNumber`。

误区二：以为 `pageNumber` 是从 `0` 开始。

从当前调用片段看，`BookPageNumbered.pageNumber` 在领域层按从 `1` 开始使用。证据有两个：

- `PageHashDao` 构造时使用 `pageNumber = it.value3() + 1`；
- `BookPageEditor` 比较时使用 `candidate.pageNumber == index + 1`。

所以阅读这个类时应把 `pageNumber = 1` 理解为第一页，而不是下标 `0`。

误区三：以为只要 `fileHash` 相同就能删除页面。

实际删除逻辑不是只比较 `fileHash`。`BookPageEditor` 同时比较 `fileHash`、`mediaType`、`fileName` 和 `pageNumber`。这是为了降低误删风险。尤其在同一本书中可能存在重复页、同哈希页，单靠哈希不足以表达“我要删的是当前这个位置上的页面”。

误区四：以为 `dimension` 是必填字段。

`dimension` 类型是 `Dimension? = null`，说明它可以没有。页面哈希删除流程里构造 `BookPageNumbered` 时，很多地方并没有传入 `dimension`。因此不能假设所有 `BookPageNumbered` 都有宽高信息。

误区五：以为 `fileHash` 一定非空。

`fileHash` 默认值是空字符串：

```kotlin
fileHash: String = ""
```

不过在页面哈希删除相关流程里，通常会传入实际哈希。父类 `BookPage.restoreHashFrom(...)` 里也能看到代码会检查 `fileHash.isNotBlank()`。所以更准确的理解是：类型允许空哈希，但依赖哈希匹配的业务通常需要非空哈希。

误区六：以为它是 `data class`，可以自然按值比较。

`BookPageNumbered` 是普通 `class`，不是 `data class`。Kotlin 不会自动为它生成按字段比较的 `equals()`。因此如果你看到集合查找或去重逻辑，不要默认它能按字段值判断相等。当前删除逻辑就是手动逐字段比较，而不是直接写 `candidate == page`。

误区七：忽略父类 `copy()` 的返回类型。

`BookPage` 有 `copy()`，但它返回的是 `BookPage`：

```kotlin
fun copy(...) = BookPage(...)
```

如果对一个 `BookPageNumbered` 调用继承来的 `copy()`，结果不会保留 `pageNumber`，也不会返回 `BookPageNumbered`。当前代码中恢复哈希的扩展函数 `restoreHashFrom(...)` 操作的是 `Collection<BookPage>`，这对普通页面列表是合理的，但不能把它当作“复制带页码页面”的工具。

误区八：把 API 的页码规则和内部页码规则混为一谈。

仓库里其他控制器存在不同 API 入口的页码适配，例如有的 REST 参数可能通过 `zeroBasedIndex` 转换，有的 OPDS v1 入口会 `pageNumber + 1`。但就 `BookPageNumbered` 当前使用链路而言，它在领域服务中按 `1-based pageNumber` 使用。阅读时要区分“外部 API 参数如何兼容”和“领域对象内部如何表达页码”。
