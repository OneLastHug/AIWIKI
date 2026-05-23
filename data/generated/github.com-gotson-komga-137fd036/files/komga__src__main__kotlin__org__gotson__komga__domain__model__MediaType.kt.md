# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/MediaType.kt

## 它负责什么

`MediaType.kt` 定义 Komga 领域层自己的媒体类型枚举 `MediaType`。它把“文件被识别出来的 MIME 类型字符串”转换成 Komga 内部可理解的书籍媒体分类，并附带几个关键元数据：

- 这个媒体类型的原始 MIME 字符串，例如 `application/zip`、`application/pdf`。
- 它属于哪一种阅读/发布 profile，例如 `DIVINA`、`PDF`、`EPUB`。
- 它对应的默认文件扩展名，例如 `cbz`、`cbr`、`epub`、`pdf`。
- 对外导出或 OPDS/WebPub acquisition link 使用的 MIME 类型，例如 ZIP 漫画包内部识别为 `application/zip`，但导出时使用更语义化的 `application/vnd.comicbook+zip`。

可以把它理解为 Komga 对“书籍容器格式”的统一字典。扫描、分析、搜索、转换、API 输出等模块都不用到处硬编码 MIME 字符串，而是通过这个枚举获得稳定的领域含义。

## 关键组成

这个文件没有 `import`，说明它只依赖同包下的 `MediaProfile`。`MediaProfile` 定义在 `komga/src/main/kotlin/org/gotson/komga/domain/model/MediaProfile.kt`，目前只有三个值：

- `DIVINA`
- `PDF`
- `EPUB`

`MediaType` 枚举构造函数有四个属性：

```kotlin
enum class MediaType(
  val type: String,
  val profile: MediaProfile,
  val fileExtension: String,
  val exportType: String = type,
)
```

各字段含义如下：

- `type`：Komga 内部匹配和持久化使用的媒体类型字符串。`Media.mediaType` 存的就是这类字符串。
- `profile`：决定后续使用哪条处理路径。比如 `DIVINA` 走漫画图片容器逻辑，`PDF` 走 PDF 逻辑，`EPUB` 走 EPUB 逻辑。
- `fileExtension`：这个媒体类型对应的常见文件扩展名，转换、导出、命名时会用到。
- `exportType`：对外暴露时使用的媒体类型，默认等于 `type`。只有部分格式需要更换为更标准或更业务化的导出 MIME。

当前枚举值如下：

- `ZIP("application/zip", MediaProfile.DIVINA, "cbz", "application/vnd.comicbook+zip")`
- `RAR_GENERIC("application/x-rar-compressed", MediaProfile.DIVINA, "cbr", "application/vnd.comicbook-rar")`
- `RAR_4("application/x-rar-compressed; version=4", MediaProfile.DIVINA, "cbr", "application/vnd.comicbook-rar")`
- `RAR_5("application/x-rar-compressed; version=5", MediaProfile.DIVINA, "cbr", "application/vnd.comicbook-rar")`
- `EPUB("application/epub+zip", MediaProfile.EPUB, "epub")`
- `PDF("application/pdf", MediaProfile.PDF, "pdf")`

这里有两个容易忽略的点：

第一，ZIP 在 Komga 里被归入 `DIVINA`，对应漫画/图片序列类阅读模型，默认扩展名是 `cbz`，而不是普通 `.zip`。

第二，RAR 分成了 `RAR_GENERIC`、`RAR_4`、`RAR_5`。它们的 `type` 不完全一样，但都属于 `DIVINA`，默认扩展名都是 `cbr`，导出类型也都统一成 `application/vnd.comicbook-rar`。

文件底部的 `companion object` 提供两个工具函数：

```kotlin
fun fromMediaType(mediaType: String?): MediaType? =
  entries.firstOrNull { it.type == mediaType }
```

这个函数把字符串转换成枚举值。找不到时返回 `null`，不会抛异常。

```kotlin
fun matchingMediaProfile(mediaProfile: MediaProfile): Collection<MediaType> =
  entries.filter { it.profile == mediaProfile }
```

这个函数按 `MediaProfile` 反查所有匹配的 `MediaType`。例如传入 `MediaProfile.DIVINA` 会返回 ZIP 和几个 RAR 类型。

## 上下游关系

上游主要是文件内容检测和书籍分析流程。

在 `komga/src/main/kotlin/org/gotson/komga/domain/service/BookAnalyzer.kt` 中，`BookAnalyzer.analyze()` 会先通过 `contentDetector.detectMediaType(book.path)` 检测文件 MIME，然后调用：

```kotlin
MediaType.fromMediaType(it)
```

如果检测出的字符串无法匹配 `MediaType`，就返回一个 `Media(status = UNSUPPORTED, mediaType = it, comment = "ERR_1001")`。也就是说，`MediaType.kt` 实际上定义了 Komga 当前支持的书籍容器格式边界。

匹配成功后，`BookAnalyzer` 会根据 `mediaType.profile` 分流：

- `MediaProfile.DIVINA` -> `analyzeDivina(...)`
- `MediaProfile.PDF` -> `analyzePdf(...)`
- `MediaProfile.EPUB` -> `analyzeEpub(...)`

这说明 `profile` 是后续分析器选择的关键字段。

领域模型 `komga/src/main/kotlin/org/gotson/komga/domain/model/Media.kt` 也依赖它：

```kotlin
val profile: MediaProfile? by lazy {
  MediaType.fromMediaType(mediaType)?.profile
}
```

`Media` 本身只保存字符串形式的 `mediaType`，但通过 `MediaType.fromMediaType()` 可以懒加载出领域分类 `profile`。如果 `mediaType` 是未知字符串，`profile` 就是 `null`。

下游调用比较多，典型有几类。

第一类是 API DTO。`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/BookDto.kt` 里的 `MediaDto` 会根据 `mediaType` 派生出 `mediaProfile`：

```kotlin
val mediaProfile: String by lazy {
  MediaType.fromMediaType(mediaType)?.profile?.name ?: ""
}
```

这会影响 REST API 返回给前端的媒体 profile 信息。

第二类是 WebPub/OPDS 输出。`komga/src/main/kotlin/org/gotson/komga/interfaces/api/WebPubGenerator.kt` 中会把 `BookDto.media.mediaType` 转成 Komga 的 `MediaType`，然后用于生成 manifest link 和 acquisition link：

- `komgaMediaType?.profile` 决定最合适的 manifest 类型。
- `komgaMediaType?.exportType ?: media.mediaType` 决定下载链接对外声明的 MIME 类型。

所以 `exportType` 的存在主要服务于对外协议和客户端兼容性，而不只是内部识别。

第三类是搜索条件。`komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/BookSearchHelper.kt` 中处理 `SearchCondition.MediaProfile` 时，会调用：

```kotlin
MediaType.matchingMediaProfile(searchCondition.operator.value)
```

然后把返回的多个 `type` 转成 SQL `in` 或 `notIn` 条件。也就是说，用户搜索“媒体 profile 是 DIVINA”时，底层不是查一个字段值，而是查 `MEDIA.MEDIA_TYPE` 是否属于 ZIP/RAR 这些具体类型集合。

第四类是媒体容器提取器和转换器。调用方搜索结果显示：

- `komga/src/main/kotlin/org/gotson/komga/infrastructure/mediacontainer/divina/ZipExtractor.kt` 使用 `MediaType.ZIP.type` 声明支持的类型。
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/mediacontainer/divina/RarExtractor.kt` 使用 `MediaType.RAR_GENERIC.type`、`MediaType.RAR_4.type`。
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/mediacontainer/divina/Rar5Extractor.kt` 使用 `MediaType.RAR_5.type`。
- `komga/src/main/kotlin/org/gotson/komga/domain/service/BookConverter.kt` 使用 RAR/ZIP/PDF/EPUB 类型判断可转换格式。
- `komga/src/main/kotlin/org/gotson/komga/domain/service/PageHashLifecycle.kt` 把 `MediaType.ZIP.type` 作为可做页面哈希的媒体类型之一。
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/metadata/epub/EpubMetadataProvider.kt` 用 `MediaType.EPUB.type` 限定只处理 EPUB。

根据当前片段推断，`MediaType.kt` 是领域层的“格式注册表”：新增一种书籍容器格式时，只改提取器还不够，通常还要在这里补充枚举值，并确认分析、搜索、导出、转换等下游是否支持。

## 运行/调用流程

典型流程可以按“扫描一本书”来理解：

1. Komga 扫描到一个书籍文件，例如 `.cbz`、`.cbr`、`.epub`、`.pdf`。
2. `BookAnalyzer.analyze()` 调用 `ContentDetector.detectMediaType(...)` 得到 MIME 字符串。
3. `MediaType.fromMediaType(...)` 尝试把字符串映射到枚举。
4. 如果映射失败，生成 `Media.Status.UNSUPPORTED`，并记录原始 `mediaType` 字符串。
5. 如果映射成功，读取该枚举的 `profile`。
6. 根据 `profile` 分发到对应分析逻辑：
   - ZIP/RAR -> `DIVINA` 分支，按图片序列或漫画容器处理。
   - PDF -> `PDF` 分支。
   - EPUB -> `EPUB` 分支。
7. 分析结果保存为 `Media`，其中 `mediaType` 仍然是字符串，例如 `application/pdf`。
8. API 返回书籍信息时，`MediaDto.mediaProfile` 再通过 `MediaType.fromMediaType(mediaType)` 推导出 `PDF`、`EPUB` 或 `DIVINA`。
9. WebPub/OPDS 输出下载链接时，如果能识别成 `MediaType`，就优先使用枚举上的 `exportType`。这会让 CBZ/CBR 对外显示为更贴近漫画书语义的 MIME 类型。
10. 用户按媒体 profile 搜索时，`matchingMediaProfile()` 把一个 profile 展开成多个底层 MIME 字符串，再交给 jOOQ 生成数据库查询条件。

还有一个特殊分支：`BookAnalyzer` 检测到文件扩展名是 `epub`，但 MIME 检测结果不是 `MediaType.EPUB` 时，会额外调用 `epubExtractor.isEpub(book.path)`。如果确认它实际上是 EPUB，就把 `mediaType` 修正为 `MediaType.EPUB`；如果不是，就标记为错误。这说明 `MediaType` 虽然以 MIME 为主，但 Komga 在某些场景也会结合文件扩展名修正检测结果。

## 小白阅读顺序

建议按下面顺序读：

1. 先读 `komga/src/main/kotlin/org/gotson/komga/domain/model/MediaProfile.kt`  
   这个文件很小，先知道 Komga 把媒体阅读模型分成 `DIVINA`、`PDF`、`EPUB` 三类。

2. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/model/MediaType.kt`  
   重点看每个枚举值的四个参数：`type`、`profile`、`fileExtension`、`exportType`。读完要能回答：为什么 ZIP 是 `DIVINA`，为什么 ZIP 的导出类型不是 `application/zip`。

3. 接着读 `komga/src/main/kotlin/org/gotson/komga/domain/model/Media.kt`  
   关注 `mediaType` 是字符串，而 `profile` 是通过 `MediaType.fromMediaType(mediaType)` 懒加载出来的。这能帮助理解为什么数据库和 DTO 里经常看到字符串，而业务判断又会回到枚举。

4. 然后读 `komga/src/main/kotlin/org/gotson/komga/domain/service/BookAnalyzer.kt` 的 `analyze()`  
   这是最关键的入口。它展示了文件检测结果如何进入 `MediaType`，以及 `profile` 如何决定后续分析路径。

5. 再读 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/BookDto.kt` 里的 `MediaDto`  
   看 API 如何把内部 `mediaType` 转成前端可读的 `mediaProfile`。

6. 最后读 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/WebPubGenerator.kt` 和 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/BookSearchHelper.kt`  
   前者帮助理解 `exportType` 的价值，后者帮助理解 `matchingMediaProfile()` 为什么存在。

## 常见误区

一个常见误区是把 `org.gotson.komga.domain.model.MediaType` 和 Spring 的 `org.springframework.http.MediaType` 混在一起。Komga 这个文件里的 `MediaType` 是领域枚举，用来描述书籍容器格式；Spring 的 `MediaType` 是 HTTP 层用来设置 `Content-Type`、`produces`、`consumes` 的类型。代码里有些文件会同时出现二者，所以经常会用别名，例如 `WebPubGenerator.kt` 中把 Komga 的类型导入为 `KomgaMediaType`。

第二个误区是认为 `type` 和 `exportType` 永远相同。实际上 ZIP、RAR 的内部识别类型和对外导出类型不同。内部检测到 ZIP 是 `application/zip`，但作为漫画书下载时更适合暴露为 `application/vnd.comicbook+zip`。如果新增格式时忽略 `exportType`，可能会导致 OPDS/WebPub 客户端识别不准确。

第三个误区是认为 `MediaProfile` 和 `MediaType` 是一对一关系。不是。`MediaProfile.DIVINA` 对应多个 `MediaType`，包括 ZIP、RAR generic、RAR v4、RAR v5。`matchingMediaProfile()` 正是为这种“一类 profile 对应多个底层媒体类型”的情况服务的。

第四个误区是认为 `fileExtension` 是检测依据。当前目标文件只是声明默认扩展名；真正的检测来自 `ContentDetector.detectMediaType(...)`。不过 `BookAnalyzer` 对 EPUB 有扩展名辅助修正逻辑，所以扩展名不是完全无关，而是在特定异常场景下参与判断。

第五个误区是以为 `fromMediaType()` 找不到值会报错。它返回的是 nullable：`MediaType?`。调用方必须处理 `null`。例如 `BookAnalyzer` 找不到就标记 `UNSUPPORTED`，`MediaDto` 找不到就返回空字符串，`WebPubGenerator` 找不到就回退使用原始 `media.mediaType`。

第六个误区是新增枚举值后就算完整支持了新格式。根据当前片段推断，新增格式至少还要考虑这些位置：内容检测是否会产出对应 MIME、是否有 extractor/analyzer、`MediaProfile` 是否合适、API 输出是否正确、搜索条件是否应包含它、转换和导出是否支持它。`MediaType.kt` 是入口字典，不是完整实现。
