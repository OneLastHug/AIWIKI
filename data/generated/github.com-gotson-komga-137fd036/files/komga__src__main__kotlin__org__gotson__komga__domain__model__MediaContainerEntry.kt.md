# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/MediaContainerEntry.kt

## 它负责什么

`MediaContainerEntry.kt` 定义了领域模型 `MediaContainerEntry`，用于描述“媒体容器内部的一个条目”。

这里的“媒体容器”可以理解为一本书文件的外壳，例如：

- ZIP/CBZ 压缩包里的某个文件；
- RAR/CBR 压缩包里的某个文件；
- PDF 里的某一页；
- 其他被解析器枚举出来的内部资源。

它不是最终持久化的书页模型，也不是前端 API DTO，而是媒体分析阶段的中间数据结构。解析器先把容器内部能看到的内容统一表示成 `MediaContainerEntry`，后续 `BookAnalyzer` 再根据这些条目的 `mediaType`、`dimension`、`fileSize` 等信息，把它们转换成 `BookPage` 或 `MediaFile`，最终组成 `Media`。

文件内容非常小：

```kotlin
package org.gotson.komga.domain.model

data class MediaContainerEntry(
  val name: String,
  val mediaType: String? = null,
  val comment: String? = null,
  val dimension: Dimension? = null,
  val fileSize: Long? = null,
)
```

它的核心职责可以概括为：用统一格式承接不同媒体解析器提取出来的“内部条目元数据”。

## 关键组成

`MediaContainerEntry` 是 Kotlin `data class`。这意味着 Kotlin 会自动为它生成 `equals`、`hashCode`、`toString`、`copy`、`componentN` 等常用方法，适合用来做不可变数据载体。

字段说明如下。

`name: String`

条目名称，唯一的必填字段。对于压缩包来说通常是内部文件路径或文件名，例如 `chapter1/page001.jpg`；对于 PDF 来说，`PdfExtractor` 使用页码字符串，例如 `"1"`、`"2"`。后续转换成 `BookPage` 或 `MediaFile` 时，这个字段会成为页面文件名或资源文件名。

`mediaType: String? = null`

条目的 MIME 类型，例如图片可能是 `image/jpeg`、`image/png`。ZIP/RAR 解析器会通过 `ContentDetector.detectMediaType` 检测它。PDF 页条目没有直接设置 `mediaType`，因为 PDF 页不是容器里的真实图片文件，而是可渲染页面。

这个字段可为空有两个含义：一是当前解析器不提供该信息；二是解析失败或无法识别。`BookAnalyzer` 会用 `mediaType` 判断哪些条目是页面图片，哪些是其他资源。

`comment: String? = null`

条目级别的备注或错误信息。ZIP/RAR 解析器在分析某个内部条目失败时，会捕获异常并创建 `MediaContainerEntry(name = ..., comment = e.message)`。注意它不是全局媒体错误，而是某个条目的局部分析信息。

在当前看到的调用片段里，`BookAnalyzer` 主要根据 `mediaType.isNullOrBlank()` 汇总错误条目名称，并形成 `ERR_1007 [...]` 这样的媒体级备注；`comment` 字段本身并没有在该片段中直接进入最终错误摘要。根据当前片段推断，`comment` 更多用于保留局部异常信息，便于日志或未来扩展。

`dimension: Dimension? = null`

条目的尺寸信息，类型是同包下的 `Dimension`：

```kotlin
data class Dimension(
  val width: Int,
  val height: Int,
)
```

对于图片条目，ZIP/RAR 解析器只有在 `analyzeDimensions == true` 且 `contentDetector.isImage(mediaType)` 时才会调用 `ImageAnalyzer.getDimension` 读取尺寸。对于 PDF，`PdfExtractor` 在需要分析尺寸时根据页面的 `cropBox` 生成 `Dimension(width, height)`。

它可为空，表示没有分析尺寸、条目不是图片、解析器不支持该信息，或分析失败。

`fileSize: Long? = null`

条目的文件大小。ZIP 解析器会检查 `ArchiveEntry.SIZE_UNKNOWN`，未知时保持 `null`；RAR 解析器使用 `entry.fullUnpackSize`。PDF 页条目没有设置 `fileSize`。

这个字段后续会传递给 `BookPage` 或 `MediaFile`，用于保存页面或资源的大小信息。

## 上下游关系

上游主要是媒体容器解析器。

`komga/src/main/kotlin/org/gotson/komga/infrastructure/mediacontainer/divina/DivinaExtractor.kt` 定义了统一接口：

```kotlin
fun getEntries(
  path: Path,
  analyzeDimensions: Boolean,
): List<MediaContainerEntry>
```

也就是说，只要是 Divina 类媒体容器解析器，都要把内部条目输出为 `List<MediaContainerEntry>`。

典型实现包括：

- `komga/src/main/kotlin/org/gotson/komga/infrastructure/mediacontainer/divina/ZipExtractor.kt`
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/mediacontainer/divina/RarExtractor.kt`
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/mediacontainer/divina/Rar5Extractor.kt`
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/mediacontainer/pdf/PdfExtractor.kt`

`ZipExtractor` 的流程是：打开 ZIP，过滤目录，遍历文件条目，检测 `mediaType`，必要时分析图片尺寸，读取 `fileSize`，然后创建：

```kotlin
MediaContainerEntry(
  name = entry.name,
  mediaType = mediaType,
  dimension = dimension,
  fileSize = fileSize,
)
```

如果单个条目分析失败，则创建：

```kotlin
MediaContainerEntry(name = entry.name, comment = e.message)
```

`RarExtractor` 的逻辑类似，只是底层使用 RAR 库读取条目，并且会拒绝加密 RAR、多卷 RAR 等不支持的容器。

`PdfExtractor` 不枚举文件，而是枚举 PDF 页：

```kotlin
MediaContainerEntry(name = "${index + 1}", dimension = dimension)
```

这里 `name` 是页码，`dimension` 来自 PDF 页面裁剪框，`mediaType` 和 `fileSize` 不设置。

下游主要是 `komga/src/main/kotlin/org/gotson/komga/domain/service/BookAnalyzer.kt`。

在 `BookAnalyzer` 的分析流程中，`MediaContainerEntry` 会被分成页面和其他文件。根据当前片段可以确认：

- 图片类条目会转成 `BookPage(fileName = it.name, mediaType = it.mediaType!!, dimension = it.dimension, fileSize = it.fileSize)`；
- 非页面资源会转成 `MediaFile(fileName = it.name, mediaType = it.mediaType, fileSize = it.fileSize)`；
- 如果没有任何页面，返回 `Media(status = Media.Status.ERROR, comment = "ERR_1006")`；
- 如果存在无法识别的其他条目，会生成 `ERR_1007 [...]` 摘要；
- 最终成功时返回 `Media(status = Media.Status.READY, pages = pages, files = files, comment = entriesErrorSummary)`。

最终聚合模型是 `komga/src/main/kotlin/org/gotson/komga/domain/model/Media.kt`：

```kotlin
data class Media(
  val status: Status = Status.UNKNOWN,
  val mediaType: String? = null,
  val pages: List<BookPage> = emptyList(),
  val pageCount: Int = pages.size,
  val files: List<MediaFile> = emptyList(),
  val comment: String? = null,
  ...
)
```

所以 `MediaContainerEntry` 位于“底层文件解析器”和“领域媒体模型 `Media`”之间，是一个过渡层模型。

## 运行/调用流程

一次典型的 CBZ/ZIP 漫画分析流程可以按下面理解。

第一步，系统识别书籍文件的容器类型，选择对应解析器，例如 `ZipExtractor`。

第二步，`BookAnalyzer` 或其协作对象调用解析器的 `getEntries(path, analyzeDimensions)`。

第三步，`ZipExtractor` 打开压缩包，遍历每个非目录条目。

第四步，对每个条目执行内容检测：

```kotlin
val mediaType = contentDetector.detectMediaType(stream)
```

如果配置要求分析尺寸，并且该条目是图片，则继续读取宽高：

```kotlin
if (analyzeDimensions && contentDetector.isImage(mediaType))
  imageAnalyzer.getDimension(stream)
else
  null
```

第五步，把检测结果包装成 `MediaContainerEntry`。如果条目解析失败，也不会立刻让整个容器失败，而是为该条目生成带 `comment` 的 `MediaContainerEntry`，同时记录 warning 日志。

第六步，解析器对条目按自然排序排序：

```kotlin
.sortedWith(compareBy(natSortComparator) { it.name })
```

这对漫画页顺序很重要，例如希望 `page2.jpg` 排在 `page10.jpg` 前面。

第七步，`BookAnalyzer` 接收 `List<MediaContainerEntry>`，根据 MIME 类型把图片条目转换成 `BookPage`，把其他条目转换成 `MediaFile`。

第八步，`BookAnalyzer` 返回 `Media`。此时 `MediaContainerEntry` 的生命周期基本结束，后续系统主要使用 `Media.pages`、`Media.files`、`Media.status`、`Media.comment` 等正式领域数据。

PDF 流程略有不同。`PdfExtractor` 的 `getPages` 直接按页数生成 `MediaContainerEntry`，`name` 是页码字符串，`dimension` 来自 PDF 页面尺寸。后续仍然可以复用“条目列表转页面列表”的思想，只是 PDF 页不是 ZIP/RAR 中的真实内部文件。

## 小白阅读顺序

建议按下面顺序阅读，不要一开始就陷入所有媒体格式细节。

第一步，先看 `komga/src/main/kotlin/org/gotson/komga/domain/model/MediaContainerEntry.kt`。重点理解它只是一个数据载体，不包含业务方法。

第二步，看 `komga/src/main/kotlin/org/gotson/komga/domain/model/Dimension.kt`。这样可以明白 `dimension` 只是宽高，没有 DPI、旋转、页边距等复杂概念。

第三步，看 `komga/src/main/kotlin/org/gotson/komga/domain/model/Media.kt`。这是最终媒体分析结果，里面的 `pages`、`files`、`status`、`comment` 是 `MediaContainerEntry` 最终要流向的地方。

第四步，看 `komga/src/main/kotlin/org/gotson/komga/infrastructure/mediacontainer/divina/DivinaExtractor.kt`。它定义了解析器共同契约：输入一个文件路径，输出 `List<MediaContainerEntry>`。

第五步，选一个具体实现看，例如 `komga/src/main/kotlin/org/gotson/komga/infrastructure/mediacontainer/divina/ZipExtractor.kt`。这个最直观：压缩包条目到 `MediaContainerEntry` 的映射几乎是一一对应的。

第六步，看 `komga/src/main/kotlin/org/gotson/komga/domain/service/BookAnalyzer.kt` 中处理 entries 的片段。重点关注 `MediaContainerEntry` 怎样被转换成 `BookPage`、`MediaFile` 和 `Media`。

第七步，再回头看 `PdfExtractor`。这时会更容易理解：虽然 PDF 没有“内部图片文件名”这种结构，但系统仍然用 `MediaContainerEntry` 抽象每一页，保证下游处理模型统一。

## 常见误区

误区一：把 `MediaContainerEntry` 当成数据库实体。

它不是 DAO、Entity 或 JOOQ 记录，也没有 ID、创建时间、修改时间。它只是媒体分析阶段的临时领域数据。真正进入 `Media` 聚合后，系统才会围绕 `Media.pages`、`Media.files` 等结构做后续处理和持久化。

误区二：认为 `name` 一定是文件名。

在 ZIP/RAR 中，`name` 通常是压缩包内部文件名或路径；但在 PDF 中，`name` 是页码字符串，例如 `"1"`。所以更准确的理解是“容器内部条目的标识名”，而不是严格意义上的本地文件名。

误区三：认为 `mediaType` 必定存在。

`mediaType` 是可空字段。解析器可能不提供，检测可能失败，PDF 页也不会像图片文件那样天然带 MIME 类型。下游代码在把图片条目转换为 `BookPage` 时使用了 `it.mediaType!!`，说明能走到该分支的条目应当已经被上游分类为图片；不要在不了解分类逻辑的情况下随意构造 `mediaType = null` 的页面条目。

误区四：认为 `comment` 会直接展示给用户。

从当前看到的片段看，ZIP/RAR 解析失败时会把异常消息放进 `comment`，但 `BookAnalyzer` 汇总错误时主要检查 `mediaType` 是否为空，并把条目名称汇总成 `ERR_1007 [...]`。因此不能简单断言 `comment` 一定会进入最终 API 响应。根据当前片段推断，它更像条目级诊断信息，而不是稳定的用户展示字段。

误区五：认为 `dimension` 一定表示图片像素尺寸。

对图片条目，`dimension` 通常来自图片分析器，语义接近像素宽高；对 PDF，`dimension` 来自页面 `cropBox` 的宽高取整。PDF 的这个尺寸不一定等价于最终渲染出的图片像素大小，因为渲染还可能受分辨率、缩放等参数影响。

误区六：认为 `fileSize` 一定可用。

压缩格式可能无法提供大小，例如 ZIP 里遇到 `ArchiveEntry.SIZE_UNKNOWN` 时会设为 `null`。PDF 页也没有在 `MediaContainerEntry` 上设置 `fileSize`。因此下游展示或计算时必须接受 `fileSize` 为空。

误区七：忽略排序。

`MediaContainerEntry` 自身不负责排序，但 ZIP/RAR 解析器会在返回前按自然顺序排序。漫画阅读顺序高度依赖这个排序。如果新增解析器，也需要注意返回条目的顺序是否符合阅读预期。
