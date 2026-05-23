# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/Media.kt

## 它负责什么

`Media.kt` 定义了 Komga 领域层里的 `Media` 数据模型，用来描述一本 `Book` 对应的“媒体分析结果”。这里的“媒体”不是封面图片，而是书籍文件本身被解析后的结构化信息：文件类型、处理状态、页列表、附属文件、EPUB 扩展信息、页数、错误说明以及审计时间。

在业务上，`Media` 是 `Book` 能否被阅读、生成缩略图、导出、转换、同步阅读进度、通过 OPDS/WebPub 暴露资源的基础数据。扫描书籍后，系统会先为书创建一个空的 `Media(bookId = book.id)`；后续 `BookAnalyzer` 读取真实文件，识别 ZIP/RAR/PDF/EPUB 等格式，再把分析结果写回 `MediaRepository`。

这个文件本身不做 IO、不访问数据库、不解析压缩包，也不直接处理图片。它只负责承载领域状态，并提供一个派生属性 `profile`，让上层代码能快速知道当前媒体属于 `DIVINA`、`PDF` 还是 `EPUB`。

## 关键组成

`Media` 是一个 Kotlin `data class`：

```kotlin
data class Media(...) : Auditable
```

它实现了同目录的 `Auditable` 接口，因此必须提供：

- `createdDate: LocalDateTime`
- `lastModifiedDate: LocalDateTime`

这两个字段用于记录媒体记录创建和最后修改时间。默认情况下，`lastModifiedDate` 等于 `createdDate`。

核心字段可以分成几组理解。

第一组是状态和类型：

- `status: Status = Status.UNKNOWN`
- `mediaType: String? = null`
- `comment: String? = null`
- `profile: MediaProfile?`

`status` 表示分析状态，定义在内部枚举 `Status` 中：

- `UNKNOWN`：默认状态，通常表示还没有完成分析。
- `ERROR`：分析或读取过程中发生错误。
- `READY`：媒体已经成功分析，可以用于阅读、缩略图、导出等流程。
- `UNSUPPORTED`：识别到不支持的媒体类型或无法用当前提取器处理。
- `OUTDATED`：媒体信息过期，需要重新分析或刷新。

`mediaType` 保存 MIME 类型字符串，例如同目录 `MediaType.kt` 中定义的：

- `application/zip`
- `application/x-rar-compressed`
- `application/x-rar-compressed; version=4`
- `application/x-rar-compressed; version=5`
- `application/epub+zip`
- `application/pdf`

`comment` 通常保存分析过程中的错误码或警告摘要，例如 `BookAnalyzer` 中会写入 `ERR_1001`、`ERR_1033 [...]` 等。

`profile` 不是构造参数，而是派生属性：

```kotlin
@delegate:Transient
val profile: MediaProfile? by lazy { MediaType.fromMediaType(mediaType)?.profile }
```

它通过 `MediaType.fromMediaType(mediaType)` 查表得到 `MediaProfile`。目前同目录 `MediaProfile.kt` 只有三类：

- `DIVINA`：漫画/图片序列类容器，例如 CBZ/CBR。
- `PDF`
- `EPUB`

`@delegate:Transient` 表示这个 `lazy` 委托不参与序列化/持久化。数据库里保存的是 `mediaType`，`profile` 每次由 `mediaType` 推导出来。

第二组是页面与文件结构：

- `pages: List<BookPage> = emptyList()`
- `pageCount: Int = pages.size`
- `files: List<MediaFile> = emptyList()`

`pages` 是可阅读页面列表。相邻文件 `BookPage.kt` 定义了页面的文件名、页面媒体类型、尺寸、哈希、文件大小：

```kotlin
open class BookPage(
  val fileName: String,
  val mediaType: String,
  val dimension: Dimension? = null,
  val fileHash: String = "",
  val fileSize: Long? = null,
)
```

对于 ZIP/RAR 这类 `DIVINA` 媒体，`pages` 通常是压缩包中的图片文件。对于 EPUB，`pages` 只在 EPUB 可转换为 Divina 风格页面时有实际页面列表；否则 `pageCount` 可能来自 EPUB 自身的分页计算。对于 PDF，`BookAnalyzer.analyzePdf` 会生成 `BookPage` 列表，但页面内容可能由 PDF 提取器动态生成。

`pageCount` 默认等于 `pages.size`，但不是永远等于 `pages.size`。这是阅读者容易忽略的一点。EPUB 的 `pageCount` 可能通过 `epubExtractor.computePageCount(epub)` 得到，而 `pages` 为空或只表示 Divina 兼容页面。因此业务代码如果关心“总页数”，应该看 `pageCount`；如果关心“可直接枚举的页面资源”，才看 `pages`。

`files` 保存非页面资源或 EPUB 资源。相邻文件 `MediaFile.kt` 中定义：

```kotlin
data class MediaFile(
  val fileName: String,
  val mediaType: String? = null,
  val subType: SubType? = null,
  val fileSize: Long? = null,
)
```

`SubType` 目前有：

- `EPUB_PAGE`
- `EPUB_ASSET`

在 API 层生成 WebPub 或提供 EPUB 资源时，会通过 `media.files` 查找对应资源。

第三组是扩展信息：

- `extension: MediaExtension? = null`
- `epubDivinaCompatible: Boolean = false`
- `epubIsKepub: Boolean = false`

`MediaExtension` 是同目录 `MediaExtension.kt` 中的标记接口。当前主要实现是 `MediaExtensionEpub`，包含 EPUB 的目录、landmarks、page list、固定布局标记、R2 positions 等：

```kotlin
data class MediaExtensionEpub(
  val toc: List<EpubTocEntry> = emptyList(),
  val landmarks: List<EpubTocEntry> = emptyList(),
  val pageList: List<EpubTocEntry> = emptyList(),
  val isFixedLayout: Boolean = false,
  val positions: List<R2Locator> = emptyList(),
) : MediaExtension
```

`ProxyExtension` 用于延迟或代理扩展类型判断。持久化层 `MediaDao` 读取扩展字段时会反序列化 `MediaExtension`；某些场景只需要知道扩展类型，可能用 `ProxyExtension` 代表。

`epubDivinaCompatible` 表示 EPUB 是否可以按 Divina/页面流方式处理。`BookAnalyzer.analyzeEpub` 中，如果 `epubExtractor.getDivinaPages(...)` 返回非空页面列表，就会把它置为 `true`。

`epubIsKepub` 表示 EPUB 是否已经是 Kobo 的 KEPUB 格式。`KepubConverter` 会检查它，避免重复转换。

第四组是关联关系和审计字段：

- `bookId: String = ""`
- `createdDate: LocalDateTime = LocalDateTime.now()`
- `lastModifiedDate: LocalDateTime = createdDate`

`bookId` 是 `Media` 对应的书籍 ID。在持久化层里，`media.bookId` 会写入 `MEDIA.BOOK_ID`，并用于关联 `MEDIA_PAGE`、`MEDIA_FILE` 等表。

`toString()` 被手写覆盖，只输出状态、媒体类型、说明、书籍 ID、时间字段，没有输出 `pages`、`files`、`extension`。这样日志更简洁，也避免大型页面列表把日志撑爆。

## 上下游关系

上游主要有三个来源。

第一，`SeriesLifecycle.addBooks` 在新书加入系列时创建初始媒体记录：

```kotlin
mediaRepository.insert(toAdd.map { Media(bookId = it.id) })
```

这时的 `Media` 基本是空壳：`status = UNKNOWN`，`mediaType = null`，`pages = emptyList()`，`pageCount = 0`。它表示“这本书已经存在，但媒体还未分析完成”。

第二，`BookAnalyzer.analyze` 是填充 `Media` 的核心上游。它通过 `ContentDetector` 判断文件 MIME 类型，再映射到 `MediaType`。如果 MIME 类型不在 `MediaType.kt` 的枚举中，就返回：

```kotlin
Media(mediaType = it, status = Media.Status.UNSUPPORTED, comment = "ERR_1001", bookId = book.id)
```

如果识别成功，则根据 `mediaType.profile` 分派到：

- `analyzeDivina`
- `analyzePdf`
- `analyzeEpub`

`analyzeDivina` 会从 ZIP/RAR 等容器中取出条目，把图片条目变成 `BookPage`，其他条目变成 `MediaFile`。如果没有任何页面，会返回 `ERROR`。

`analyzePdf` 会通过 `PdfExtractor` 得到 PDF 页面列表，返回 `Media(status = READY, pages = pages)`。

`analyzeEpub` 会读取 EPUB 资源、目录、landmarks、page list、positions、Divina 兼容页面等信息，返回带 `MediaExtensionEpub` 的 `Media`。它还会设置 `epubDivinaCompatible`、`epubIsKepub` 和更复杂的 `pageCount`。

第三，转换、编辑、哈希等服务会基于旧 `Media` 产生新 `Media`。例如 `BookAnalyzer.hashPages` 会为页面补充哈希后返回 `book.media.copy(pages = hashedPages)`；`BookConverter`、`BookPageEditor` 会在转换文件后分析新文件，再把旧页面哈希恢复到新媒体上。

下游主要包括持久化、阅读、API、元数据、缩略图、转换等模块。

持久化下游是 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/MediaDao.kt`。它实现 `MediaRepository`，负责把 `Media` 写入多张表：

- `MEDIA`：保存 `bookId`、`status`、`mediaType`、`comment`、`pageCount`、EPUB 标志、扩展类型和值等主信息。
- `MEDIA_PAGE`：保存 `media.pages` 中的每个 `BookPage`。
- `MEDIA_FILE`：保存 `media.files` 中的每个 `MediaFile`。

读取时，`MediaDao.findById(bookId)` 会把主表、页面表、文件表重新组装成领域对象 `Media`。

阅读和页面访问下游集中在 `BookAnalyzer`、`BookLifecycle`、`CommonBookController`、`BookController` 等地方。它们会检查：

- `media.status == Media.Status.READY`
- `media.profile`
- `media.pageCount`
- `media.pages[number - 1]`
- `media.files`
- `media.mediaType`

例如 `BookAnalyzer.getPageContent` 会根据 `media.profile` 决定使用 Divina 提取器、PDF 提取器还是 EPUB 提取器。API 控制器会用 `media.profile` 判断请求是否适配 EPUB/PDF 页面接口。

元数据下游也依赖它。比如 `EpubMetadataProvider` 会先判断：

```kotlin
book.media.mediaType == MediaType.EPUB.type
```

再尝试从 EPUB 中读取元数据。`IsbnBarcodeProvider` 会跳过 EPUB 类型，并根据 `book.media.pageCount` 决定扫描页码范围。

发布和同步下游包括 OPDS、WebPub、Kobo、KOReader 同步等。`WebPubGenerator` 会根据 `media.profile`、`media.extension`、`media.files`、`media.epubDivinaCompatible` 构造可阅读资源。`KepubConverter` 会检查 `media.mediaType == MediaType.EPUB.type` 且 `!media.epubIsKepub` 后才转换。

## 运行/调用流程

一个典型流程可以这样理解。

1. 扫描到新书文件后，系统创建 `Book`。
2. `SeriesLifecycle.addBooks` 同时插入一条初始 `Media(bookId = book.id)`。
3. 后台任务或生命周期服务触发分析。
4. `BookAnalyzer.analyze(book, analyzeDimensions)` 开始读取文件。
5. `ContentDetector.detectMediaType(book.path)` 识别 MIME 类型。
6. `MediaType.fromMediaType(...)` 把 MIME 字符串映射到系统支持的媒体枚举。
7. 根据 `MediaType.profile` 进入不同分析分支：
   - `DIVINA`：解析 ZIP/RAR 条目，图片进入 `pages`，其他文件进入 `files`。
   - `PDF`：解析 PDF 页，生成 `BookPage` 列表。
   - `EPUB`：解析 EPUB 资源、导航、阅读位置、Divina 兼容页面和扩展信息。
8. 分析结果返回一个新的 `Media`，通常状态为 `READY`，失败则为 `ERROR` 或 `UNSUPPORTED`。
9. 生命周期服务通过 `MediaRepository.update` 或相关方法保存结果。
10. `MediaDao` 将 `Media` 拆分写入 `MEDIA`、`MEDIA_PAGE`、`MEDIA_FILE`。
11. 用户阅读、请求页面、生成缩略图、导出、转换、OPDS/WebPub/Kobo 同步时，再通过 `mediaRepository.findById(bookId)` 读取 `Media`。
12. 下游根据 `status`、`profile`、`pageCount`、`pages`、`files`、`extension` 决定具体行为。

这里最关键的判断点是 `profile`。它不是单独存储的字段，而是由 `mediaType` 动态推导。也就是说，`mediaType` 是底层事实，`profile` 是业务分组视角。

例如：

```kotlin
MediaType.EPUB.type == "application/epub+zip"
MediaType.EPUB.profile == MediaProfile.EPUB
```

当 `media.mediaType` 是 `application/epub+zip` 时，`media.profile` 才会是 `MediaProfile.EPUB`。

## 小白阅读顺序

建议先读 `Media.kt` 本身，重点看构造参数和 `Status` 枚举。这个文件短，但信息密度很高。先不要急着理解所有 EPUB 字段，只要知道它们是媒体分析结果的一部分。

第二步读同目录的 `Auditable.kt`。它解释了为什么 `Media` 需要 `createdDate` 和 `lastModifiedDate`。

第三步读 `MediaType.kt` 和 `MediaProfile.kt`。这两个文件解释 `mediaType` 和 `profile` 的关系。理解这点后，后面看到 `when (media.profile)` 就不会迷糊。

第四步读 `BookPage.kt` 和 `MediaFile.kt`。这两个类型分别解释 `pages` 和 `files`。可以简单记成：`BookPage` 是阅读页，`MediaFile` 是资源文件或非页面文件。

第五步读 `MediaExtension.kt`。重点看 `MediaExtensionEpub`，它说明 EPUB 为什么需要额外保存目录、landmarks、page list、positions 等结构。

第六步读 `BookAnalyzer.kt`。这是理解 `Media` 从哪里来的最重要文件。建议重点看 `analyze`、`analyzeDivina`、`analyzePdf`、`analyzeEpub` 四个方法。

第七步读 `MediaDao.kt`。这里能看到 `Media` 如何被拆成数据库表，又如何从数据库记录组装回领域对象。

第八步再抽看调用方，例如 `BookLifecycle.kt`、`CommonBookController.kt`、`WebPubGenerator.kt`、`BookConverter.kt`。这些文件能帮助理解 `Media` 被消费的方式：阅读页面、生成缩略图、生成 WebPub、转换书籍格式等。

## 常见误区

第一个误区：以为 `Media` 表示图片或视频媒体。  
在 Komga 这里，`Media` 表示“一本书文件的媒体分析结果”。它描述的是书籍容器、页面、资源、格式和状态，不是单个图片文件。

第二个误区：以为 `pageCount` 永远等于 `pages.size`。  
构造函数默认让 `pageCount = pages.size`，但调用方可以显式传入不同值。EPUB 就是典型例子：如果 EPUB 没有 Divina 页面列表，`pages` 可能为空，但 `pageCount` 仍然通过 EPUB 位置计算得到。业务代码要根据需求选择 `pageCount` 或 `pages`。

第三个误区：以为 `profile` 是数据库字段。  
`profile` 是懒加载派生属性，由 `mediaType` 通过 `MediaType.fromMediaType(mediaType)?.profile` 得出。持久化时主要保存的是 `mediaType`，不是 `profile`。

第四个误区：以为 `READY` 代表没有任何问题。  
`READY` 表示媒体主体可用，但 `comment` 仍可能包含警告或部分资源缺失信息。例如 EPUB 分析时，目录或资源解析失败可能记录错误码，但整体仍可进入 `READY`。

第五个误区：以为 `files` 和 `pages` 是重复数据。  
`pages` 是阅读页列表，通常用于页面访问、页数、哈希、尺寸等逻辑。`files` 是附属资源列表，例如 EPUB assets、EPUB page resource 或 Divina 容器里的非图片文件。WebPub、EPUB 资源接口等会依赖 `files`。

第六个误区：忽略 `bookId` 默认值是空字符串。  
`Media()` 可以构造出没有关联书籍的对象，但正常持久化和业务使用都应该有有效 `bookId`。新书加入时会创建 `Media(bookId = it.id)`；`BookAnalyzer.analyze` 最终也会 `.copy(bookId = book.id)`。

第七个误区：以为 `Media.Status.UNSUPPORTED` 和 `ERROR` 一样。  
`UNSUPPORTED` 通常表示系统识别到该类型不支持，或者没有对应提取器；`ERROR` 表示尝试分析过程中发生异常、文件损坏、无页面、权限问题等。两者对排错含义不同。

第八个误区：认为 EPUB 只看 `mediaType` 就够了。  
EPUB 还有 `epubDivinaCompatible`、`epubIsKepub` 和 `MediaExtensionEpub`。这些字段会影响页面流、Kobo 转换、WebPub 生成、阅读位置等逻辑。对于 EPUB，下游通常不只判断 `media.profile == MediaProfile.EPUB`，还会继续看这些 EPUB 专属字段。
