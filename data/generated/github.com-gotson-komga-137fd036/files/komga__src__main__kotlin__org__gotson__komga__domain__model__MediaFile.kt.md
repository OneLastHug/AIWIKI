# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/MediaFile.kt

## 它负责什么

`MediaFile.kt` 定义了领域模型 `MediaFile`，用于描述一本书的媒体容器中“不是页面主体，或需要作为资源清单记录”的文件条目。它位于 `org.gotson.komga.domain.model` 包下，是 Komga 领域层的一部分。

源码非常短：

```kotlin
data class MediaFile(
  val fileName: String,
  val mediaType: String? = null,
  val subType: SubType? = null,
  val fileSize: Long? = null,
) {
  enum class SubType {
    EPUB_PAGE,
    EPUB_ASSET,
  }
}
```

从调用方看，`MediaFile` 主要承担两类职责：

1. 普通归档漫画、PDF 等媒体分析时，记录容器中非页面文件，例如 `ComicInfo.xml`、其他辅助文件。
2. EPUB 分析时，记录 EPUB manifest/spine 中的资源，并通过 `subType` 区分阅读顺序页面和静态资源。

它不是“文件读取器”，也不直接访问磁盘；它只是保存文件元信息的不可变数据结构。

## 关键组成

`MediaFile` 是 Kotlin `data class`，天然具备 `equals`、`hashCode`、`toString`、`copy` 和解构能力。仓库里确实使用了 `copy`，例如 `EpubExtractor.getResources` 会先构造 EPUB 资源列表，再用 `resource.copy(fileSize = ...)` 补上压缩包条目的文件大小。

字段含义如下：

`fileName: String`

表示媒体容器内的文件路径或文件名。对于普通容器，来自容器条目的 `name`；对于 EPUB，通常是经过 `normalizeHref` 处理后的 EPUB 内部路径，例如 spine 页面或 manifest 资源路径。

这个字段是必填的，因为后续很多逻辑都依赖它查找资源、生成 URL 或持久化数据库记录。例如 `WebPubGenerator` 会把它拼到 `/books/{id}/resource/{fileName}` 后面，作为 Web Publication 的 `href`。

`mediaType: String? = null`

表示 MIME type，例如 `application/xhtml+xml`、`application/xml` 等。它是可空的，因为扫描容器时可能无法识别某些文件类型。`BookAnalyzer` 中会把无法识别媒体类型的非页面文件汇总成错误注释 `ERR_1007 [...]`，但仍然可以把已分析的书籍标记为可用。

`subType: SubType? = null`

表示更细的文件分类。目前只定义了 EPUB 相关分类：

```kotlin
enum class SubType {
  EPUB_PAGE,
  EPUB_ASSET,
}
```

普通容器生成的 `MediaFile` 通常不设置 `subType`，也就是 `null`。EPUB 解析时才会设置：

`EPUB_PAGE` 表示 EPUB spine 中的阅读顺序页面。

`EPUB_ASSET` 表示不在 spine 中的 manifest 资源，例如图片、样式、字体、元数据文件等。

`fileSize: Long? = null`

表示容器内该文件的大小。它也是可空的，因为某些压缩条目可能无法提供大小，或者来源没有填充该信息。EPUB 解析中，`EpubExtractor.getResources` 会从 zip entries 中匹配 `fileName`，如果条目大小不是 `ArchiveEntry.SIZE_UNKNOWN`，就写入 `fileSize`。

需要注意，EPUB 的某些后续算法依赖 `fileSize`。例如 `computePositionsFromKoboSpan` 中根据 `file.fileSize!!` 计算 Kobo span 在文件内的 progression。因此上游在进入这类逻辑前通常会过滤或检查缺失资源，例如 `BookAnalyzer.analyzeEpub` 会把 `epubExtractor.getResources(epub)` 按 `fileSize != null` 分成 `resources` 和 `missingResources`。

## 上下游关系

上游创建者主要有两个。

第一个是 `komga/src/main/kotlin/org/gotson/komga/domain/service/BookAnalyzer.kt`。

普通媒体分析流程里，`BookAnalyzer` 会把容器中非页面的 `others` 转成 `MediaFile`：

```kotlin
val files = others.map { MediaFile(fileName = it.name, mediaType = it.mediaType, fileSize = it.fileSize) }
```

这里没有设置 `subType`，说明这些文件只是普通附属文件，不参与 EPUB 阅读顺序/资源分类。

第二个是 `komga/src/main/kotlin/org/gotson/komga/infrastructure/mediacontainer/epub/EpubExtractor.kt`。

`EpubExtractor.getResources` 会读取 EPUB 的 OPF spine 和 manifest。spine 中的条目被建模为：

```kotlin
MediaFile(
  normalizeHref(...),
  page.mediaType,
  MediaFile.SubType.EPUB_PAGE,
)
```

manifest 中不属于 spine 的条目被建模为：

```kotlin
MediaFile(
  normalizeHref(...),
  it.mediaType,
  MediaFile.SubType.EPUB_ASSET,
)
```

随后再结合 zip entries 给每个 `MediaFile` 补 `fileSize`。

中游聚合模型是 `komga/src/main/kotlin/org/gotson/komga/domain/model/Media.kt`。它有字段：

```kotlin
val files: List<MediaFile> = emptyList()
```

也就是说 `MediaFile` 不是单独流转的顶层实体，而是挂在 `Media` 上，作为一本书的媒体分析结果的一部分。

持久化层是 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/MediaDao.kt`。其中 `MediaFileRecord.toDomain()` 会从数据库记录恢复领域模型：

```kotlin
MediaFile(
  fileName = fileName,
  mediaType = mediaType,
  subType = subType?.let { MediaFile.SubType.valueOf(it) },
  fileSize = fileSize,
)
```

这说明 `subType` 在数据库中大概率以字符串形式保存，例如 `"EPUB_PAGE"`、`"EPUB_ASSET"`，读取时再用 `valueOf` 转回枚举。

下游消费者主要包括 EPUB/WebPub 相关逻辑。

`komga/src/main/kotlin/org/gotson/komga/interfaces/api/WebPubGenerator.kt` 会根据 `subType` 把 `media.files` 拆成 Web Publication 的 `readingOrder` 和 `resources`：

```kotlin
media.files.filter { it.subType == MediaFile.SubType.EPUB_PAGE }
```

用于生成阅读顺序。

```kotlin
media.files.filter { it.subType == MediaFile.SubType.EPUB_ASSET }
```

用于生成资源列表。

`EpubExtractor` 内部也会继续使用 `MediaFile`。例如 `isKepub` 会只检查 `EPUB_PAGE` 文件，读取这些 XHTML 页面里是否包含 `koboSpan`。`computePositions` 也会先过滤出 `EPUB_PAGE`，再计算 EPUB 阅读位置。

## 运行/调用流程

普通非 EPUB 媒体的大致流程是：

1. `BookAnalyzer.analyze` 检测书籍容器类型。
2. 容器条目被分成页面文件和其他文件。
3. 页面文件转换为 `BookPage`，其他文件转换为 `MediaFile`。
4. `MediaFile` 被放入 `Media.files`。
5. `MediaDao` 将 `Media.files` 持久化到数据库。
6. 后续读取媒体信息时，`MediaDao` 再把数据库记录恢复成 `MediaFile`。

这条路径下，`subType` 通常是 `null`。它只表示“这个文件属于媒体容器，但不是页面列表中的页面”。

EPUB 的流程更复杂：

1. `BookAnalyzer.analyzeEpub` 打开 EPUB 包。
2. 调用 `EpubExtractor.getResources(epub)`。
3. `getResources` 从 OPF 的 `spine` 取出阅读顺序页面，创建 `subType = EPUB_PAGE` 的 `MediaFile`。
4. `getResources` 从 manifest 中取出不在 spine 的资源，创建 `subType = EPUB_ASSET` 的 `MediaFile`。
5. `getResources` 遍历 zip entries，根据内部文件路径匹配 `fileName`，给资源补 `fileSize`。
6. `BookAnalyzer.analyzeEpub` 根据 `fileSize != null` 区分可用资源和缺失大小的资源。
7. EPUB 检测、KEPUB 判断、位置计算、WebPub 输出等逻辑继续使用这些 `MediaFile`。
8. `WebPubGenerator` 把 `EPUB_PAGE` 输出到 `readingOrder`，把 `EPUB_ASSET` 输出到 `resources`。

因此，`MediaFile` 在 EPUB 场景中不仅是“附属文件列表”，还是构建 WebPub 阅读结构的基础数据。

## 小白阅读顺序

建议按下面顺序阅读：

1. 先读 `komga/src/main/kotlin/org/gotson/komga/domain/model/MediaFile.kt`。

   重点看四个字段：`fileName`、`mediaType`、`subType`、`fileSize`。这个文件本身没有业务逻辑，不要期待在这里看到扫描、解析或数据库代码。

2. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/model/Media.kt`。

   目标是理解 `MediaFile` 是挂在 `Media.files` 上的。Komga 不是单独管理一堆 `MediaFile`，而是把它们作为一本书媒体分析结果的一部分。

3. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/service/BookAnalyzer.kt` 中普通分析和 `analyzeEpub` 相关片段。

   这里能看到 `MediaFile` 是如何被创建并塞进 `Media` 的。普通容器只填文件名、媒体类型、大小；EPUB 会走专门的资源解析流程。

4. 再读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/mediacontainer/epub/EpubExtractor.kt` 的 `getResources`、`isKepub`、`computePositions`。

   这里是理解 `SubType.EPUB_PAGE` 和 `SubType.EPUB_ASSET` 的关键。尤其要注意 spine 和 manifest 的区别：spine 决定阅读顺序，manifest 是 EPUB 声明的资源总表。

5. 最后读 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/WebPubGenerator.kt`。

   这里能看到为什么 `subType` 很重要：它直接决定 WebPub 输出中的 `readingOrder` 和 `resources`。

6. 如果想理解持久化，再读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/MediaDao.kt`。

   重点看 `MediaFileRecord.toDomain()`，以及保存 `files` 的相关逻辑。它说明 `MediaFile` 会被数据库保存和恢复，而不是只存在于内存中。

## 常见误区

误区一：把 `MediaFile` 理解成真实磁盘文件对象。

它不是 `java.io.File` 或 `Path`，也没有打开、读取、写入文件的能力。它只是领域层里的元信息载体。真正读取 EPUB zip entry 的逻辑在 `EpubExtractor` 和相关 util 中。

误区二：认为 `fileName` 一定只是短文件名。

在 EPUB 场景中，`fileName` 通常是 EPUB 包内的相对路径，可能包含目录。下游会用它从 zip 中查 entry，也会用它生成资源 URL。因此它更像“容器内部路径”，不是简单的 basename。

误区三：认为 `mediaType` 必定存在。

`mediaType` 是可空字段。普通容器分析时，如果某些非页面文件无法识别媒体类型，仍可能生成 `MediaFile`。`BookAnalyzer` 会把这些无法识别的条目汇总到错误说明里，而不是因为某个附属文件缺少 MIME type 就完全放弃整本书。

误区四：认为 `subType` 对所有媒体类型都有意义。

目前 `SubType` 只有 EPUB 相关枚举。普通漫画归档中的 `MediaFile` 多数没有 `subType`。如果看到 `subType == null`，不一定表示数据坏了；它可能只是非 EPUB 或普通附属文件。

误区五：把 `EPUB_PAGE` 等同于 Komga 的 `BookPage`。

二者不是同一个概念。`BookPage` 更偏向 Komga 阅读器中的页面模型，包含尺寸、hash 等页面信息；`MediaFile.SubType.EPUB_PAGE` 表示 EPUB spine 中的 XHTML/资源条目，是 EPUB 阅读顺序里的资源文件。EPUB 页面可能是可重排文本，不一定等价于一张图片页。

误区六：忽略 `fileSize` 的可空性。

`fileSize` 虽然可空，但 EPUB 的部分位置计算逻辑会用到它。上游通常会过滤缺失大小的资源；如果新增调用方直接对 `fileSize!!` 做非空断言，需要确认输入已经经过类似过滤，否则可能引入运行时异常。

误区七：随意修改 `SubType` 枚举名。

`MediaDao` 通过 `MediaFile.SubType.valueOf(it)` 从数据库字符串恢复枚举。如果重命名 `EPUB_PAGE` 或 `EPUB_ASSET`，旧数据库中的字符串可能无法反序列化。新增或修改枚举时需要同时考虑数据库兼容、迁移和 WebPub 输出逻辑。
