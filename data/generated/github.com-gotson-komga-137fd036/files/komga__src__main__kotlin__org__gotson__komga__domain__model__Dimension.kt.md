# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/Dimension.kt

## 它负责什么

`Dimension.kt` 定义了 Komga 领域模型中最小的“尺寸”值对象：

```kotlin
data class Dimension(
  val width: Int,
  val height: Int,
)
```

它只表达两个信息：`width` 和 `height`。在仓库中，它主要用于描述图片、漫画页、PDF 页面、封面缩略图等媒体对象的宽高。

这个文件属于包 `org.gotson.komga.domain.model`，也就是说它不是某个基础设施模块的私有工具，而是领域层可复用的数据结构。上层 REST controller、领域服务、JOOQ DAO、图片分析器、PDF 提取器都会围绕它传递尺寸信息。

它本身不负责读取图片、不负责计算比例、不负责校验尺寸合法性，也不关心单位。单位由使用场景决定：普通图片通常是像素宽高，PDF 页面在 `PdfExtractor.getPages` 中来自 `page.cropBox.width/height`，根据当前片段可判断更接近 PDF 页面坐标尺寸；而渲染后的 PDF 图片尺寸会经过 `PdfExtractor.scaleDimension` 按配置分辨率缩放。

## 关键组成

`Dimension` 是一个 Kotlin `data class`，字段如下：

- `width: Int`：宽度。
- `height: Int`：高度。

因为它是 `data class`，Kotlin 会自动生成这些能力：

- `equals` / `hashCode`：按 `width`、`height` 两个字段比较。
- `toString`：输出类似 `Dimension(width=800, height=1200)`。
- `copy`：可以复制并替换某个字段。
- component 解构函数：可用于结构化解构。

文件中没有显式 `import`。这是因为它只使用 Kotlin 基础类型 `Int`，并且位于领域模型包中，不依赖任何其他类。

这个类没有默认值，也没有 nullable 字段。因此凡是构造 `Dimension` 的地方都必须提供完整的宽高。不过在很多上层模型里，`Dimension` 本身是可空的，例如 `BookPage.dimension: Dimension?`、`MediaContainerEntry.dimension: Dimension?`，表示某些媒体条目可能没有被分析出尺寸。

## 上下游关系

`Dimension` 的上游是“尺寸来源”，也就是负责从真实媒体中读出宽高的代码。典型来源包括：

- `komga/src/main/kotlin/org/gotson/komga/infrastructure/image/ImageAnalyzer.kt`  
  `ImageAnalyzer.getDimension(stream)` 使用 `ImageIO` 获取图片第 0 帧的 `width` 和 `height`，成功时返回 `Dimension(reader.getWidth(0), reader.getHeight(0))`，失败时返回 `null`。

- `komga/src/main/kotlin/org/gotson/komga/infrastructure/mediacontainer/pdf/PdfExtractor.kt`  
  `PdfExtractor.getPages(path, analyzeDimensions)` 在需要分析尺寸时，从 PDF 页面的 `cropBox` 读取宽高并构造 `Dimension`。`PdfExtractor.scaleDimension(dimension)` 会按 PDF 渲染分辨率计算缩放后的新 `Dimension`。

- REST controller 中的上传逻辑  
  `BookController`、`SeriesController`、`ReadListController`、`SeriesCollectionController` 在用户上传封面或缩略图时，会通过 `imageAnalyzer.getDimension(file.inputStream.buffered())` 获取尺寸；如果失败，会使用 `Dimension(0, 0)` 兜底。

它的下游是“保存或使用尺寸的模型”和“持久化层”。典型承载对象包括：

- `BookPage`：页面模型，字段是 `dimension: Dimension? = null`。
- `BookPageNumbered`：带页码的页面模型，继承 `BookPage`，同样携带可空尺寸。
- `MediaContainerEntry`：媒体容器内条目，尺寸可为空。
- `ThumbnailBook`、`ThumbnailSeries`、`ThumbnailReadList`、`ThumbnailSeriesCollection`：各类缩略图模型，尺寸是非空 `Dimension`。
- `MediaDao`：将 `BookPage.dimension?.width`、`BookPage.dimension?.height` 写入 `MEDIA_PAGE.WIDTH`、`MEDIA_PAGE.HEIGHT`；读取时如果两个字段都非空，则重建 `Dimension(width, height)`。
- 各类 `Thumbnail*Dao`：将缩略图的 `dimension.width`、`dimension.height` 写入对应缩略图表的 `WIDTH`、`HEIGHT`，读取时构造非空 `Dimension(width, height)`。

从关系上看，`Dimension` 是领域层和基础设施层之间传递宽高数据的标准格式。基础设施层负责“怎么读到尺寸”，领域模型负责“把尺寸作为业务对象的一部分保存下来”。

## 运行/调用流程

一个典型的图像类漫画包分析流程如下：

1. `BookAnalyzer.analyze(book, analyzeDimensions)` 被调用。
2. 它先用 `ContentDetector` 判断媒体类型。
3. 如果是 DIVINA 类媒体，会调用对应 `DivinaExtractor.getEntries(book.path, analyzeDimensions)`。
4. extractor 返回一组 `MediaContainerEntry`，其中每个 entry 可能带有 `dimension: Dimension?`。
5. `BookAnalyzer.analyzeDivina` 把图片 entry 转成 `BookPage(fileName, mediaType, dimension, fileSize)`。
6. `MediaDao.insertPages` 持久化页面时，把 `page.dimension?.width` 和 `page.dimension?.height` 写入数据库。
7. 后续读取媒体信息时，`MediaDao.MediaPageRecord.toDomain()` 如果发现 `width` 和 `height` 都存在，就构造 `Dimension(width, height)` 放回 `BookPage`。

PDF 分析流程稍有不同：

1. `BookAnalyzer.analyzePdf(book, analyzeDimensions)` 调用 `pdfExtractor.getPages(book.path, analyzeDimensions)`。
2. `PdfExtractor` 遍历 PDF 页。
3. 如果 `analyzeDimensions == true`，就用 `page.cropBox.width.roundToInt()` 和 `page.cropBox.height.roundToInt()` 构造 `Dimension`。
4. 每页被映射为 `BookPage(it.name, "", it.dimension)`。
5. 后续同样交给 `MediaDao` 保存。

缩略图生成流程如下：

1. `BookAnalyzer.generateThumbnail(book)` 获取封面内容。
2. `ImageConverter.resizeImageToByteArray(...)` 生成缩略图字节。
3. `imageAnalyzer.getDimension(thumbnail.inputStream())` 读取缩略图实际宽高。
4. 如果读取失败，使用 `Dimension(0, 0)`。
5. 构造 `ThumbnailBook(dimension = ...)`。
6. `ThumbnailBookDao.insert` 或 `update` 将宽高写入缩略图表。

因此，`Dimension` 不出现在流程控制里，它更像一枚“数据令牌”：由分析器生成，被领域对象携带，再由 DAO 拆成数据库字段保存。

## 小白阅读顺序

建议按下面顺序阅读：

1. 先读 `komga/src/main/kotlin/org/gotson/komga/domain/model/Dimension.kt`  
   只需要确认它是一个 `width + height` 的不可变值对象。

2. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/model/BookPage.kt`  
   这里能看到页面如何持有 `Dimension?`，也能理解为什么页面尺寸可能为空：有些分析过程可能不读取尺寸，或读取失败。

3. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/model/ThumbnailBook.kt`、`ThumbnailSeries.kt`、`ThumbnailReadList.kt`、`ThumbnailSeriesCollection.kt`  
   这些模型里 `dimension` 是非空的，说明缩略图在领域模型中被要求必须有尺寸。如果无法真实读取，上层会用 `Dimension(0, 0)` 补齐。

4. 接着读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/image/ImageAnalyzer.kt`  
   这里能看到普通图片尺寸是怎么从 `InputStream` 里读出来的。

5. 再读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/mediacontainer/pdf/PdfExtractor.kt`  
   这里能看到 PDF 页面尺寸和缩放尺寸的来源。

6. 最后读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/MediaDao.kt` 和 `ThumbnailBookDao.kt`  
   这里能理解 `Dimension` 如何映射到数据库中的 `WIDTH`、`HEIGHT` 两个字段，以及读取时如何重新组装回领域对象。

按这个顺序读，可以先理解数据结构，再理解谁生产它、谁消费它、它如何落库。

## 常见误区

第一个误区：以为 `Dimension` 一定表示像素。  
对普通图片和缩略图来说，它通常表示像素宽高；但在 `PdfExtractor.getPages` 中，它来自 PDF 页面的 `cropBox`。只有经过 PDF 渲染或缩放后的图片尺寸，才更接近最终图像像素尺寸。阅读时要结合来源判断单位。

第二个误区：以为 `Dimension` 会保证宽高合法。  
它没有任何校验逻辑。`width` 和 `height` 是 `Int`，理论上可以是 `0`、负数或异常值。仓库中确实存在 `Dimension(0, 0)` 作为读取失败时的兜底值。因此不要把非空 `Dimension` 等同于“尺寸有效”。

第三个误区：以为页面一定有尺寸。  
`BookPage.dimension` 和 `MediaContainerEntry.dimension` 都是 nullable。比如分析时 `analyzeDimensions` 为 `false`，或者图片读取失败，就可能没有尺寸。处理页面尺寸时必须考虑 `null`。

第四个误区：以为缩略图尺寸也可为空。  
缩略图领域模型中的 `dimension` 是非空字段，例如 `ThumbnailBook.dimension: Dimension`。如果上游无法读取真实尺寸，controller 或 service 会构造 `Dimension(0, 0)`。所以缩略图尺寸“非空”只代表字段存在，不代表真实有效。

第五个误区：把它当成行为对象。  
`Dimension` 没有缩放、旋转、比例判断、方向判断等行为。类似 `scaleDimension` 这样的逻辑放在 `PdfExtractor` 中，而不是 `Dimension` 内部。它在当前设计中是纯数据载体。

第六个误区：忽略它对持久化字段的影响。  
数据库并不直接保存一个 `Dimension` 对象，而是拆成 `WIDTH` 和 `HEIGHT`。`MediaDao` 对页面尺寸的读取逻辑要求两个字段都非空才重建 `Dimension`；如果只有一个字段存在，则领域层拿到的是 `null`。缩略图 DAO 则按非空尺寸处理，会直接用 `Dimension(width, height)` 构造对象。
