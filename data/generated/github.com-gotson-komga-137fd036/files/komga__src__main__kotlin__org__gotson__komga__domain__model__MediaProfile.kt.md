# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/MediaProfile.kt

## 它负责什么

`MediaProfile.kt` 定义了 Komga 领域模型里的媒体“档案/形态”枚举：

```kotlin
enum class MediaProfile {
  DIVINA,
  PDF,
  EPUB,
}
```

它本身没有方法、属性或复杂逻辑，只负责表达一本书的媒体内容属于哪一类处理模型：

- `DIVINA`：面向图片序列类出版物，典型来源是 `cbz`、`cbr` 这类漫画压缩包。
- `PDF`：PDF 文件。
- `EPUB`：EPUB 电子书。

这个枚举的价值不在文件自身的代码量，而在它作为全仓库共享的分类轴：媒体分析、页面读取、封面提取、WebPub manifest 生成、搜索过滤、同步逻辑、前端筛选都会围绕它做分支。

## 关键组成

### `MediaProfile`

`MediaProfile` 是 `org.gotson.komga.domain.model` 包下的 Kotlin `enum class`。它没有 import，说明它不依赖任何外部类型，是一个纯领域枚举。

三个枚举值分别是：

`DIVINA`

表示图片型阅读内容。它和 W3C/Readium 生态里的 Divina 概念相关，在 Komga 中主要对应图片页集合。根据 `MediaType.kt`，这些 MIME 类型会归到 `DIVINA`：

- `application/zip`，对应 `cbz`
- `application/x-rar-compressed`，对应 `cbr`
- `application/x-rar-compressed; version=4`
- `application/x-rar-compressed; version=5`

`PDF`

表示 PDF 内容。根据 `MediaType.kt`，`application/pdf` 会归到 `PDF`。

`EPUB`

表示 EPUB 内容。根据 `MediaType.kt`，`application/epub+zip` 会归到 `EPUB`。

### 和 `MediaType` 的关系

`MediaProfile` 不是直接从文件扩展名判断出来的，而是由 `MediaType` 绑定：

```kotlin
enum class MediaType(
  val type: String,
  val profile: MediaProfile,
  val fileExtension: String,
  val exportType: String = type,
)
```

也就是说：

- `MediaType` 表示更具体的媒体类型，例如 `ZIP`、`RAR_4`、`EPUB`、`PDF`。
- `MediaProfile` 表示更高层的处理分类，例如 `DIVINA`、`PDF`、`EPUB`。
- 多个 `MediaType` 可以共享一个 `MediaProfile`，例如各种 ZIP/RAR 漫画格式都归为 `DIVINA`。

`MediaType.matchingMediaProfile(mediaProfile)` 会反向找出某个 profile 下所有具体媒体类型。这在搜索过滤里很重要。

### 和 `Media` 的关系

`Media.kt` 中有一个延迟计算属性：

```kotlin
@delegate:Transient
val profile: MediaProfile? by lazy { MediaType.fromMediaType(mediaType)?.profile }
```

这说明数据库或领域对象里主要保存的是 `mediaType: String?`，例如 `application/pdf`。当业务代码需要知道该怎么处理这本书时，再通过 `MediaType.fromMediaType(mediaType)?.profile` 推导出 `MediaProfile`。

这里返回值是可空的 `MediaProfile?`，原因是 `mediaType` 可能为空，或者字符串无法匹配已知的 `MediaType`。调用方通常需要处理 `null`，例如返回不支持、媒体未就绪或 404。

## 上下游关系

### 上游：媒体检测结果

上游主要来自内容检测和媒体分析流程。

在 `komga/src/main/kotlin/org/gotson/komga/domain/service/BookAnalyzer.kt` 中，`analyze` 方法先调用 `contentDetector.detectMediaType(book.path)` 检测文件媒体类型，然后使用：

```kotlin
MediaType.fromMediaType(it)
```

把检测出的 MIME 字符串转换为 `MediaType`。如果转换失败，会返回 `Media(status = Media.Status.UNSUPPORTED, comment = "ERR_1001")`。

转换成功后，再通过 `mediaType.profile` 进入不同分析分支：

```kotlin
when (mediaType.profile) {
  MediaProfile.DIVINA -> analyzeDivina(book, mediaType, analyzeDimensions)
  MediaProfile.PDF -> analyzePdf(book, analyzeDimensions)
  MediaProfile.EPUB -> analyzeEpub(book, analyzeDimensions)
}
```

所以 `MediaProfile` 是“检测到文件类型之后，选择分析管线之前”的关键分流点。

### 下游：分析器和读取器

`BookAnalyzer.kt` 在多个地方根据 `MediaProfile` 选择不同实现。

分析阶段：

- `DIVINA` 调用 `analyzeDivina`
- `PDF` 调用 `analyzePdf`
- `EPUB` 调用 `analyzeEpub`

封面/海报阶段：

- `DIVINA` 从压缩包图片页中取 poster。
- `PDF` 把第一页渲染成图片。
- `EPUB` 优先读取 EPUB cover；如果 EPUB 兼容 Divina，再尝试按图片序列取 poster。

页面内容读取阶段：

- `DIVINA` 从压缩包 entry 读取图片文件。
- `PDF` 调用 PDF extractor，把指定页渲染为图片字节。
- `EPUB` 只有在 `epubDivinaCompatible` 为 true 时，才按 entry 读取页面；否则抛出 `MediaUnsupportedException`。
- `null` 会抛出 `MediaNotReadyException`。

PDF 动态页面阶段：

`getPdfPagesDynamic(media)` 会先检查：

```kotlin
if (media.profile != MediaProfile.PDF) throw MediaUnsupportedException(...)
```

说明某些 PDF 页面信息不是直接用原始 `media.pages` 展示，而是需要动态转换为图片页视角。

### 下游：API 层

在 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/CommonBookController.kt` 中，`getWebPubManifestInternal` 会根据媒体 profile 分发到不同 manifest 生成方法：

- `MediaProfile.DIVINA` -> `getWebPubManifestDivinaInternal`
- `MediaProfile.PDF` -> `getWebPubManifestPdfInternal`
- `MediaProfile.EPUB` -> `getWebPubManifestEpubInternal`

同时，具体的 EPUB/PDF manifest 接口会校验 `bookDto.media.mediaProfile` 是否匹配请求的 profile。例如请求 EPUB manifest 时，如果实际不是 `EPUB`，就返回 `BAD_REQUEST`。

这说明 `MediaProfile` 不只是内部分析标记，也会影响外部 API 的可访问路径和响应类型。

### 下游：搜索过滤

在 `komga/src/main/kotlin/org/gotson/komga/domain/model/SearchCondition.kt` 中，有一个同名嵌套搜索条件：

```kotlin
data class MediaProfile(
  @JsonProperty("mediaProfile")
  val operator: SearchOperator.Equality<org.gotson.komga.domain.model.MediaProfile>,
) : Book
```

注意这里的 `SearchCondition.MediaProfile` 是搜索条件类，和 `org.gotson.komga.domain.model.MediaProfile` 枚举同名，但不是同一个类型。

在 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/BookSearchHelper.kt` 中，这个搜索条件会被翻译为对 `MEDIA.MEDIA_TYPE` 字段的 SQL 条件：

```kotlin
field.`in`(MediaType.matchingMediaProfile(searchCondition.operator.value).map { it.type }.toSet())
```

也就是说，数据库里并不一定直接存 `DIVINA`、`PDF`、`EPUB`，而是存具体 MIME 类型。搜索 `MediaProfile.DIVINA` 时，会转换成搜索所有属于 `DIVINA` 的具体 `mediaType`，例如 ZIP/RAR 相关类型。

### 下游：前端和 OpenAPI

搜索结果显示，前端也有对应定义：

- `komga-webui/src/types/enum-books.ts`
- `komga-webui/src/views/BrowseBooks.vue`
- `komga-webui/src/views/BrowseSeries.vue`

前端会用 `MediaProfile` 枚举生成媒体 profile 筛选项。后端 OpenAPI 文档中也出现了 `MediaProfile` schema，说明它是 API 契约的一部分，不只是后端内部实现细节。

### 其他使用点

根据当前片段，`MediaProfile` 还参与：

- `IsbnBarcodeProvider.kt`：EPUB 会跳过某些 ISBN 条码逻辑。
- `KoreaderSyncController.kt`：KOReader 同步时，`DIVINA`/`PDF` 和 `EPUB` 的进度表示方式不同。
- `BookLifecycle.kt`、`TransientBookLifecycle.kt`、`SyncPointLifecycle.kt`：生命周期和同步点逻辑中会按 profile 做不同处理。
- `WebPubGenerator.kt`、`OpdsController.kt`：对外阅读协议和目录输出中根据 profile 生成不同资源结构。

## 运行/调用流程

一个典型流程可以按下面理解：

1. 用户把书籍文件加入书库，例如 `.cbz`、`.cbr`、`.pdf`、`.epub`。
2. `BookAnalyzer.analyze` 调用 `contentDetector.detectMediaType(book.path)` 检测文件 MIME 类型。
3. 检测结果通过 `MediaType.fromMediaType(...)` 转换为具体 `MediaType`。
4. `MediaType` 自带 `profile` 属性，于是得到 `MediaProfile.DIVINA`、`MediaProfile.PDF` 或 `MediaProfile.EPUB`。
5. `BookAnalyzer` 根据 `mediaType.profile` 进入不同分析方法：
   - 图片压缩包走 `analyzeDivina`
   - PDF 走 `analyzePdf`
   - EPUB 走 `analyzeEpub`
6. 分析完成后，`Media` 保存具体 `mediaType` 字符串和页面、文件、状态等信息。
7. 之后业务代码通过 `media.profile` 懒加载推导 profile。
8. 用户阅读、请求封面、获取页面、生成 WebPub manifest、OPDS 输出或 KOReader 同步时，各服务继续根据 `MediaProfile` 选择不同逻辑。
9. 用户在前端按媒体 profile 筛选时，前端传 `mediaProfile` 搜索条件，后端再通过 `MediaType.matchingMediaProfile` 转换成具体 MIME 类型查询。

可以把它理解为一条链：

`文件内容` -> `MIME mediaType` -> `MediaType` -> `MediaProfile` -> `对应分析/阅读/API/搜索逻辑`

## 小白阅读顺序

建议按这个顺序读源码：

1. 先读 `komga/src/main/kotlin/org/gotson/komga/domain/model/MediaProfile.kt`

   先记住只有三个值：`DIVINA`、`PDF`、`EPUB`。不要急着找复杂逻辑，这个文件本身就是一个分类定义。

2. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/model/MediaType.kt`

   这里能看到具体 MIME 类型如何映射到 `MediaProfile`。这是理解 `MediaProfile` 的关键，因为 profile 的来源不是文件名，而是 `MediaType.profile`。

3. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/model/Media.kt`

   重点看 `profile` 属性：

   ```kotlin
   val profile: MediaProfile? by lazy { MediaType.fromMediaType(mediaType)?.profile }
   ```

   这说明 `Media` 对象平时拿 `mediaType` 保存具体格式，需要时再推导 profile。

4. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/service/BookAnalyzer.kt`

   重点看 `analyze`、`getPoster`、`getPageContent`、`getPdfPagesDynamic`。这些地方能看到 `MediaProfile` 如何真正影响处理流程。

5. 再读 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/CommonBookController.kt`

   看 API 如何根据 profile 分发 WebPub manifest，以及如何拒绝 profile 不匹配的请求。

6. 最后读搜索相关文件：

   - `komga/src/main/kotlin/org/gotson/komga/domain/model/SearchCondition.kt`
   - `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/BookSearchHelper.kt`

   这里能理解“按 profile 搜索”为什么最终会变成“按多个 mediaType 查询”。

## 常见误区

### 误区一：以为 `MediaProfile` 等同于文件扩展名

不是。`MediaProfile` 是处理模型，不是扩展名。

例如 `.cbz`、`.cbr` 虽然扩展名不同，具体 MIME 类型也可能不同，但都可以归到 `MediaProfile.DIVINA`。代码中真正绑定关系在 `MediaType.kt`，不是 `MediaProfile.kt`。

### 误区二：以为数据库一定直接保存 `DIVINA`、`PDF`、`EPUB`

根据 `Media.kt` 和 `BookSearchHelper.kt` 的片段看，核心 `Media` 里保存的是 `mediaType: String?`，例如 `application/pdf`。`profile` 是通过 `MediaType.fromMediaType(mediaType)?.profile` 推导出来的。

搜索 `MediaProfile` 时，后端也会把它转换成一组具体 `MediaType.type` 去查 `MEDIA.MEDIA_TYPE` 字段。

### 误区三：以为所有 EPUB 都能像图片页一样读取

不是。`BookAnalyzer.getPageContent` 中对 EPUB 有额外判断：

```kotlin
if (book.media.epubDivinaCompatible)
  epubExtractor.getEntryStream(...)
else
  throw MediaUnsupportedException(...)
```

也就是说，`EPUB` profile 只说明它是 EPUB 处理模型，但具体能不能按“页图片 entry”读取，还要看 `epubDivinaCompatible`。

### 误区四：忽略 `MediaProfile?` 的 `null` 情况

`Media.profile` 是可空的。只要 `mediaType` 为空或无法匹配 `MediaType`，profile 就是 `null`。

不少调用方显式处理了 `null`，例如：

- `CommonBookController` 中 profile 为 `null` 时抛出 `NOT_FOUND`。
- `BookAnalyzer.getPoster` 中 `null -> null`。
- `BookAnalyzer.getPageContent` 中 `null -> throw MediaNotReadyException()`。

所以新增调用逻辑时不能默认 `media.profile!!` 一定安全。

### 误区五：以为 `SearchCondition.MediaProfile` 就是这个 enum

`SearchCondition.kt` 里也有一个 `data class MediaProfile`，但它是搜索条件类型，不是枚举本身。为了避免命名冲突，代码里使用了完整限定名：

```kotlin
org.gotson.komga.domain.model.MediaProfile
```

读代码时要区分：

- `org.gotson.komga.domain.model.MediaProfile`：本文件定义的枚举。
- `SearchCondition.MediaProfile`：搜索条件类，用于表达“按媒体 profile 过滤”。

### 误区六：新增 profile 只改这个文件就够了

不够。虽然本文件只需要加一个枚举值，但 `MediaProfile` 已经被多个 `when` 分支穷尽匹配。新增值时至少要同步检查：

- `MediaType.kt`：新 MIME 类型如何映射到 profile。
- `BookAnalyzer.kt`：如何分析、取封面、读页面。
- `CommonBookController.kt` 和 `WebPubGenerator.kt`：API manifest 如何生成。
- `BookSearchHelper.kt`：搜索转换是否仍然正确。
- 前端 `komga-webui/src/types/enum-books.ts`：筛选枚举是否同步。
- OpenAPI 文档和测试：API 契约是否变化。

这个文件看起来很小，但它是媒体处理体系里的核心分类枚举。
