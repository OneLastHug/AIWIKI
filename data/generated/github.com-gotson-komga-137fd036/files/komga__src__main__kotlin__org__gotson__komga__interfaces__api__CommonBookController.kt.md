# 文件：komga/src/main/kotlin/org/gotson/komga/interfaces/api/CommonBookController.kt

## 它负责什么

`CommonBookController.kt` 是 Komga 后端里“书籍内容输出”的共享控制器。它位于 `org.gotson.komga.interfaces.api` 包下，用 Spring MVC 暴露一部分直接 endpoint，同时也把一些跨接口复用的逻辑封装成 `Internal` 方法，供 REST API、OPDS v1、OPDS v2、Kobo API 等不同入口调用。

它主要负责以下几类能力：

1. 生成书籍的 WebPub / Readium manifest  
   根据书籍媒体类型选择 EPUB、PDF、DIVINA 三种 profile，对外返回 `WPPublicationDto`。

2. 输出书籍页面  
   支持普通页面图片、原始页面内容、PDF 特殊内容协商、JPEG/PNG 转换，以及 HTTP 缓存判断。

3. 输出 EPUB 内部资源  
   例如 XHTML 页面、图片、CSS、字体等资源，对字体资源做了特殊的免登录放行处理。

4. 下载原始书籍文件  
   通过 `StreamingResponseBody` 流式传输本地文件，避免一次性把整本书读入内存。

5. 读取和更新阅读进度  
   提供 Readium/OPDS 方向的 progression API，用 `R2Progression` 表示阅读进度。

这个类可以理解为“书籍阅读内容的底层网关”：上层 controller 负责 URL 形态、协议差异和文档注解；它负责真正把 `Book`、`Media`、权限、文件内容、响应头、异常映射组织起来。

## 关键组成

### 顶层常量

文件顶部有两个私有变量：

`logger` 使用 `KotlinLogging.logger {}` 创建日志器，主要在文件不存在时记录 warning。

`FONT_EXTENSIONS` 是 EPUB 资源访问时使用的字体扩展名白名单：

```kotlin
private val FONT_EXTENSIONS = listOf("otf", "woff", "woff2", "eot", "ttf", "svg")
```

它用于判断 `getBookEpubResource` 请求的资源是不是字体。这里把 `svg` 也当作字体扩展处理，应该是为了兼容 EPUB 内可能存在的 SVG font 或相关字体资源。

### 构造注入的依赖

`CommonBookController` 通过构造函数注入多个领域层、持久层和接口层组件：

`MediaRepository`：读取书籍媒体分析结果，例如媒体类型、页数、文件列表、EPUB extension、最后修改时间等。

`BookRepository`：读取 `Book` 聚合，主要提供书籍路径、名称、所属库、所属系列等信息。

`BookDtoRepository`：读取面向 API 输出的 `BookDto`，manifest 生成时需要更完整的 DTO 信息，例如元数据、作者、系列等。

`SeriesMetadataRepository`：读取系列元数据，manifest 和内容限制校验都会用到。

`BookLifecycle`：提供较高层的书籍操作，例如获取转换后的页面、标记 progression。

`BookAnalyzer`：偏底层的媒体内容读取能力，例如读取原始页面、读取 EPUB 内部文件。

`ContentRestrictionChecker`：统一检查当前用户是否有权限访问某本书，包括 library 权限和内容限制。

`ContentDetector`：根据 media type 推断文件扩展名，用于响应里的 `Content-Disposition` 文件名。

`ReadProgressRepository`：读取已有阅读进度。

这些依赖可以看出这个类不负责“分析书籍”或“转换图片”的具体实现，而是把请求参数转成领域服务调用，并把结果转成 HTTP 响应。

### WebPub manifest 相关方法

`getWebPubManifestInternal(principal, bookId, webPubGenerator)` 是通用入口。它先通过 `mediaRepository.findByIdOrNull(bookId)` 找媒体信息，再根据 `MediaType.fromMediaType(media.mediaType)?.profile` 分派到三种具体方法：

`getWebPubManifestDivinaInternal`：生成 DIVINA manifest，通常面向漫画/图片序列类媒体。

`getWebPubManifestPdfInternal`：生成 PDF profile manifest。

`getWebPubManifestEpubInternal`：生成 EPUB profile manifest。

如果媒体类型无法识别 profile，会抛出 `404 Book analysis failed`。这表示书籍可能存在，但媒体分析结果不可用或不完整。

三个具体方法的共同模式是：

1. 用 `bookDtoRepository.findByIdOrNull(bookId, principal.user.id)` 读取当前用户视角下的 `BookDto`。
2. 校验 profile 是否匹配。EPUB 和 PDF 方法会显式检查 `bookDto.media.mediaProfile`，不匹配时返回 `400 BAD_REQUEST`。
3. 调用 `contentRestrictionChecker.checkContentRestriction(principal.user, bookDto)` 做访问控制。
4. 调用 `webPubGenerator.toManifestEpub`、`toManifestPdf` 或 `toManifestDivina` 组装返回对象。

`WebPubGenerator.kt` 里可以看到具体 manifest 生成逻辑：它会构造 `metadata`、`readingOrder`、`resources`、`toc`、`landmarks`、`pageList` 等字段。对 EPUB 来说，`readingOrder` 来自 `media.files` 中 `EPUB_PAGE` 类型文件；对 PDF 来说，`readingOrder` 指向每一页的 `/raw` 地址；对 DIVINA 来说，`readingOrder` 指向页面图片地址，并可能为非推荐图片格式增加 JPEG alternate 链接。

### 页面读取相关方法

`getBookPageInternal` 是普通页面读取的核心方法，供 REST、OPDS v1、OPDS v2 调用。它接收：

`bookId`：书籍 ID。

`pageNumber`：页码。注意这里期望的是内部页码语义，调用方可能会先做 `+1` 转换。

`convertTo`：可选转换格式，只允许 `jpeg`、`png`、空字符串或 `null`。

`request`：`ServletWebRequest`，用于处理 `If-Modified-Since` 之类缓存请求。

`principal`：当前登录用户。

`acceptHeaders`：可选的 `Accept` 请求头列表，用于 PDF 的有限内容协商。

它的流程是：

1. 通过 `bookRepository.findByIdOrNull(bookId)` 找书籍，不存在返回 `404`。
2. 通过 `mediaRepository.findById(bookId)` 找媒体分析结果。
3. 用 `request.checkNotModified(getBookLastModified(media))` 判断客户端缓存是否仍有效。若未修改，返回 `304 NOT_MODIFIED`，响应体为空字节数组。
4. 调用 `contentRestrictionChecker.checkContentRestriction(principal.user, book)` 做权限检查。
5. 如果媒体 profile 是 `PDF`，并且 `Accept` 头里有更具体的 `application/pdf`，则返回原始 PDF 页，即调用 `getBookPageRawInternal`。
6. 否则解析 `convertTo`，调用 `bookLifecycle.getBookPage(book, pageNumber, convertFormat)` 获取页面字节。
7. 组装 `ResponseEntity<ByteArray>`，设置 `Content-Disposition: inline`、`Content-Type`、缓存相关 header，并返回页面 bytes。

异常处理也很明确：

`IndexOutOfBoundsException` 转成 `400 Page number does not exist`。

`ImageConversionException` 转成 `404`，说明转换失败时被当成页面内容不可得。

`MediaNotReadyException` 转成 `404 Book analysis failed`。

`NoSuchFileException` 记录 warning，再转成 `404 File not found, it may have moved`。

### 原始页面读取

`getBookPageRawByNumber` 是直接暴露的 endpoint：

```kotlin
GET api/v1/books/{bookId}/pages/{pageNumber}/raw
GET opds/v2/books/{bookId}/pages/{pageNumber}/raw
```

它带有 `@PreAuthorize("hasRole('PAGE_STREAMING')")`，说明用户必须有页面流式读取权限。

它内部还是先查 `Book` 和 `Media`，处理 HTTP 缓存，做内容限制检查，然后调用 `getBookPageRawInternal(book, media, pageNumber)`。

`getBookPageRawInternal` 使用 `bookAnalyzer.getPageContentRaw(BookWithMedia(book, media), pageNumber)` 读取原始页面内容。这里和 `getBookPageInternal` 的差别是：普通页面读取走 `BookLifecycle.getBookPage`，可能涉及图片转换；原始页面读取走 `BookAnalyzer`，倾向于返回媒体容器里的原始内容。

它额外捕获 `MediaUnsupportedException` 并返回 `400`，表示当前媒体类型不支持原始页面读取。

### EPUB 资源读取

`getBookEpubResource` 暴露两个地址：

```kotlin
GET api/v1/books/{bookId}/resource/{*resource}
GET opds/v2/books/{bookId}/resource/{*resource}
```

它用于从 EPUB 内部取资源，比如章节 XHTML、图片、CSS、字体等。

这个方法有一个值得注意的安全逻辑：

```kotlin
val isFont = FONT_EXTENSIONS.contains(FilenameUtils.getExtension(resourceName).lowercase())

if (!isFont && principal == null) throw ResponseStatusException(HttpStatus.UNAUTHORIZED)
```

也就是说，非字体资源必须登录；字体资源允许匿名访问。根据当前片段推断，这可能是为了解决浏览器渲染 EPUB 页面时字体资源加载不携带认证信息的问题。依据是：它只对 `FONT_EXTENSIONS` 放宽 `principal == null` 限制，而非字体仍要求用户身份。

后续流程是：

1. 去掉路径开头的 `/`，得到 `resourceName`。
2. 判断是否字体。
3. 查 `Book` 和 `Media`。
4. 处理 `304 NOT_MODIFIED`，并设置 `Content-Security-Policy: script-src 'none'; object-src 'none';`。
5. 要求媒体 profile 必须是 `EPUB`，否则返回 `400`。
6. 非字体资源检查内容访问权限。
7. 在 `media.files` 中查找对应文件名，找不到返回 `404`。
8. 用 `bookAnalyzer.getFileContent(BookWithMedia(book, media), resourceName)` 读取 EPUB 容器内文件内容。
9. 返回 bytes，设置 inline 文件名、内容类型、CSP 和缓存 header。

这里的 CSP 很关键：EPUB 是用户上传或来自书籍文件的 HTML/CSS/资源集合，返回内部资源时禁用 script 和 object 可以降低脚本执行风险。

### 下载原始书籍文件

`downloadBookFile` 暴露多个路径：

```kotlin
GET api/v1/books/{bookId}/file
GET api/v1/books/{bookId}/file/*
GET opds/v1.2/books/{bookId}/file/*
GET opds/v2/books/{bookId}/file
GET opds/v2/books/{bookId}/file/*
```

它需要 `@PreAuthorize("hasRole('FILE_DOWNLOAD')")`，说明下载原文件和在线读取页面是两种不同权限。

实际逻辑在 `getBookFileInternal(principal, bookId)`：

1. 查书籍。
2. 检查内容访问权限。
3. 查媒体信息，用于设置 `Content-Type`。
4. 用 `FileSystemResource(book.path)` 指向本地书籍文件。
5. 如果文件不存在，抛 `FileNotFoundException`。
6. 构造 `StreamingResponseBody`，使用 `IOUtils.copyLarge` 以 8192 字节 buffer 从输入流拷贝到响应输出流。
7. 设置 `Content-Disposition: attachment`，文件名为 `book.path.name`。
8. 设置 `contentLength` 和响应体。

这里使用 `StreamingResponseBody` 的意义是避免大文件下载时占用过多内存。响应体不是 `ByteArray`，而是在 HTTP 输出过程中边读边写。

### 阅读进度 API

`getBookProgression` 暴露：

```kotlin
GET api/v1/books/{bookId}/progression
GET opds/v2/books/{bookId}/progression
```

它返回 `MEDIATYPE_PROGRESSION_JSON_VALUE`，也就是 Readium/OPDS 相关 progression 格式。

流程：

1. 查书籍，不存在返回 `404`。
2. 检查内容访问权限。
3. 用 `readProgressRepository.findByBookIdAndUserIdOrNull(bookId, principal.user.id)` 查当前用户进度。
4. 有进度则返回 `200 OK` 和 `it.toR2Progression()`。
5. 没有进度则返回 `204 No Content`。

`updateBookProgression` 暴露：

```kotlin
PUT api/v1/books/{bookId}/progression
PUT opds/v2/books/{bookId}/progression
```

它接收请求体 `R2Progression`，成功时 `204 NO_CONTENT`。

核心调用是：

```kotlin
bookLifecycle.markProgression(book, principal.user, progression)
```

异常映射如下：

`IllegalStateException` 转成 `409 CONFLICT`，表示当前书籍或进度状态冲突。

`IllegalArgumentException` 转成 `400 BAD_REQUEST`，表示 progression 请求内容非法。

## 上下游关系

### 上游调用方

这个类既有直接暴露的 Spring endpoint，也有被其他 controller 注入后调用的 internal 方法。

主要调用方包括：

`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/BookController.kt`：REST API 的书籍页面、manifest 入口。比如 `getBookPageByNumber` 会调用 `commonBookController.getBookPageInternal(...)`；`getBookWebPubManifest` 会调用 `getWebPubManifestInternal(...)`。

`komga/src/main/kotlin/org/gotson/komga/interfaces/api/opds/v2/Opds2Controller.kt`：OPDS v2 的页面和 manifest 入口。它使用同一套 internal 方法，但 URL 前缀、produces media type 和生成器可能不同。

`komga/src/main/kotlin/org/gotson/komga/interfaces/api/opds/v1/OpdsController.kt`：OPDS v1 的页面读取入口。它调用 `getBookPageInternal(bookId, pageNumber + 1, ...)`，说明 OPDS v1 入口传入的页码可能是 0-based，进入 common 层前转为 1-based。

`komga/src/main/kotlin/org/gotson/komga/interfaces/api/kobo/KoboController.kt`：Kobo 相关下载逻辑。在某些分支下直接调用 `commonBookController.getBookFileInternal(principal, bookId)` 下载原书文件。

### 下游依赖

`BookRepository` 和 `MediaRepository` 是最核心的数据读取依赖。几乎所有方法都会先拿 `Book` 或 `Media`。

`BookDtoRepository` 只在生成 manifest 时使用，因为 manifest 需要 API DTO 级别的数据，而不是纯领域模型。

`SeriesMetadataRepository` 在 manifest 生成和内容限制里都会间接或直接使用。manifest 需要系列元数据填充 publication metadata；内容限制需要年龄分级和 sharing labels。

`ContentRestrictionChecker.kt` 是权限判断的统一入口。它会检查用户是否可以访问书籍所在 library，以及用户限制策略是否允许访问该系列的年龄分级和标签。

`WebPubGenerator.kt` 是 manifest 的实际组装者。`CommonBookController` 不直接拼 manifest 结构，而是把 `BookDto`、`Media`、`SeriesMetadata` 传给 generator。

`BookLifecycle` 是较高层的书籍业务服务。页面转换和 progression 更新都通过它完成。

`BookAnalyzer` 是更底层的媒体分析/读取组件。原始页面读取、EPUB 内部文件读取依赖它。

`ContentDetector` 和 `getMediaTypeOrDefault` 负责把底层 media type 转成 HTTP 响应里的扩展名和 `Content-Type`。

`Utils.kt` 提供缓存相关工具：

```kotlin
fun getBookLastModified(media: Media) = media.lastModifiedDate.toInstant(ZoneOffset.UTC).toEpochMilli()

fun ResponseEntity.BodyBuilder.setNotModified(media: Media): ResponseEntity.BodyBuilder =
  this.setCachePrivate().lastModified(getBookLastModified(media))
```

所以本文件里多处 `.setNotModified(media)` 实际会设置 private cache 和 last-modified header。

## 运行/调用流程

### 读取普通页面

以 REST API `GET api/v1/books/{bookId}/pages/{pageNumber}` 为例，流程是：

1. `BookController.getBookPageByNumber` 接收请求参数。
2. 如果 `zero_based=true`，调用前把 `pageNumber + 1`，否则保持原页码。
3. 如果 `contentNegotiation=true`，把 `Accept` header 传给 `CommonBookController.getBookPageInternal`。
4. `getBookPageInternal` 查询 `Book` 和 `Media`。
5. 检查 `If-Modified-Since`，若未修改直接返回 `304`。
6. 调用 `ContentRestrictionChecker` 验证用户是否能访问该书。
7. 如果是 PDF 且客户端更偏好 `application/pdf`，返回 raw PDF page。
8. 否则解析 `convert=jpeg|png`。
9. 调用 `BookLifecycle.getBookPage` 获取页面内容。
10. 返回 `ResponseEntity<ByteArray>`，包含 `Content-Type`、inline 文件名、缓存 header 和页面 bytes。

### 读取原始页面

以 `GET api/v1/books/{bookId}/pages/{pageNumber}/raw` 为例：

1. Spring Security 要求用户有 `PAGE_STREAMING` 角色。
2. 查 `Book` 和 `Media`。
3. 检查缓存。
4. 检查内容访问权限。
5. 调用 `BookAnalyzer.getPageContentRaw(BookWithMedia(book, media), pageNumber)`。
6. 按原始内容 media type 返回 bytes。

这个流程不会走图片转换参数，目标是尽量返回容器里的原始页内容。

### 生成 manifest

以 `GET api/v1/books/{bookId}/manifest` 为例：

1. `BookController` 调用 `getWebPubManifestInternal(principal, bookId, webPubGenerator)`。
2. common 层先查 `Media`。
3. 根据 `media.mediaType` 推断 `MediaProfile`。
4. 分派到 EPUB、PDF 或 DIVINA 方法。
5. 具体方法读取 `BookDto`、校验 profile、检查内容限制。
6. 调用 `WebPubGenerator` 生成 `WPPublicationDto`。
7. REST 层根据 `manifest.mediaType` 设置响应 `Content-Type`。

OPDS v2 入口也是类似流程，但传入的 generator 是 `opdsGenerator`。根据当前片段推断，`OpdsGenerator` 应该继承或兼容 `WebPubGenerator` 的能力，用于生成 OPDS flavored publication JSON。依据是 `CommonBookController` 的参数类型是 `WebPubGenerator`，而 `Opds2Controller` 传入了 `opdsGenerator`。

### 读取 EPUB 内部资源

以 `GET api/v1/books/{bookId}/resource/{*resource}` 为例：

1. 去掉 resource 前导 `/`。
2. 根据扩展名判断是否字体。
3. 非字体资源要求已认证用户；字体资源可以没有 `principal`。
4. 查 `Book` 和 `Media`。
5. 检查缓存，未修改则返回 `304`，同时设置 CSP。
6. 要求 `media.profile == MediaProfile.EPUB`。
7. 非字体资源检查内容访问权限。
8. 在 `media.files` 中确认资源存在。
9. 用 `BookAnalyzer.getFileContent` 从 EPUB 内取出 bytes。
10. 返回 inline 响应，并设置 `Content-Security-Policy: script-src 'none'; object-src 'none';`。

### 下载文件

以 `GET api/v1/books/{bookId}/file` 为例：

1. Spring Security 要求 `FILE_DOWNLOAD` 角色。
2. 查 `Book`。
3. 检查内容访问权限。
4. 查 `Media` 用于响应类型。
5. 用 `FileSystemResource(book.path)` 打开本地文件。
6. 通过 `StreamingResponseBody` 流式写入响应。
7. 返回 `attachment` 下载响应。

### 获取和更新 progression

获取 progression：

1. 查 `Book`。
2. 检查内容访问权限。
3. 查当前用户的 read progress。
4. 有则转成 `R2Progression` 返回；无则 `204`。

更新 progression：

1. 查 `Book`。
2. 检查内容访问权限。
3. 调用 `BookLifecycle.markProgression`。
4. 根据异常返回 `409` 或 `400`。
5. 成功返回 `204`。

## 小白阅读顺序

1. 先看类声明和构造函数  
   从 `class CommonBookController(...)` 开始，理解它依赖哪些 repository、service 和 checker。这样能先建立“它只是编排层，不是底层实现层”的认识。

2. 再看 `getBookPageInternal`  
   这是最典型的方法，包含查书、查媒体、缓存、权限、内容协商、格式转换、异常映射、响应头设置。读懂它，基本就读懂了这个类的风格。

3. 接着看 `getBookPageRawByNumber` 和 `getBookPageRawInternal`  
   对比普通页面和 raw 页面有什么不同：一个走 `BookLifecycle.getBookPage`，一个走 `BookAnalyzer.getPageContentRaw`。

4. 再看 manifest 相关方法  
   从 `getWebPubManifestInternal` 看分派逻辑，再分别看 EPUB、PDF、DIVINA 三个 internal 方法。然后去 `WebPubGenerator.kt` 看 `toManifestEpub`、`toManifestPdf`、`toManifestDivina` 如何组装 reading order 和 resources。

5. 然后看 `getBookEpubResource`  
   重点理解 `principal` 可空、字体放行、EPUB profile 校验、CSP header。这个方法比普通页面读取更容易涉及安全问题。

6. 最后看 `downloadBookFile`、`getBookFileInternal`、progression 方法  
   下载文件主要看流式响应；progression 主要看读取和更新阅读进度的异常映射。

7. 配合阅读调用方  
   建议看 `BookController.kt` 的页面和 manifest endpoint，再看 `Opds2Controller.kt` 对同一 internal 方法的调用。这样能理解为什么这个类叫 `Common`：它服务多个协议入口。

## 常见误区

1. 误以为 `CommonBookController` 只服务 REST API  
   实际上它同时服务 REST、OPDS v1、OPDS v2、Kobo 等入口。直接暴露的 endpoint 只是其中一部分，很多核心方法是给其他 controller 复用的。

2. 误以为所有方法都有 `@GetMapping` 才是接口  
   `getBookPageInternal`、`getWebPubManifestInternal`、`getBookFileInternal` 没有直接映射 URL，但它们被其他 controller 调用，是实际请求链路里的核心逻辑。

3. 误以为 `bookId` 查到 `Book` 就代表可以访问  
   不是。几乎所有内容输出前都要调用 `contentRestrictionChecker.checkContentRestriction`。它不仅检查 library 权限，也会根据用户限制策略检查年龄分级和 sharing labels。

4. 误以为页码始终同一种基准  
   不同入口可能传入不同页码语义。REST 的 `zero_based` 参数会影响传给 common 层的页码；OPDS v1 调用处有 `pageNumber + 1`；OPDS v2 直接传 `pageNumber`。阅读时要看调用方是否转换过页码。

5. 误以为 `convert` 支持任意图片格式  
   `getBookPageInternal` 只接受 `jpeg` 和 `png`。其他值会返回 `400 Invalid conversion format`。

6. 误以为 PDF 页面一定返回图片  
   当书籍是 PDF 且 `Accept` header 更偏好 `application/pdf` 时，`getBookPageInternal` 会调用 `getBookPageRawInternal` 返回 raw PDF page。这是一个有限的服务端内容协商逻辑。

7. 误以为 EPUB 资源都必须登录  
   非字体资源必须有 `principal`，但字体扩展名在 `FONT_EXTENSIONS` 中的资源允许匿名请求。根据当前片段推断，这是为了让浏览器中的 EPUB 页面能正常加载字体。

8. 误以为 EPUB 内部 HTML 可以正常执行脚本  
   `getBookEpubResource` 设置了 `Content-Security-Policy: script-src 'none'; object-src 'none';`，明确禁止脚本和 object。这是处理用户内容时的重要安全边界。

9. 误以为文件下载会一次性读入内存  
   `getBookFileInternal` 返回的是 `StreamingResponseBody`，通过 `IOUtils.copyLarge` 流式复制本地文件到响应输出流。页面和 EPUB 资源才是 `ByteArray` 响应。

10. 误以为 `404 Book analysis failed` 一定表示书不存在  
   这个错误在 `MediaNotReadyException` 或 media profile 无法识别时也会出现。它更准确的含义是：书籍媒体分析结果不可用、未完成或不支持当前操作。
