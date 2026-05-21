# 目录：komga/src/main/kotlin/org/gotson/komga/interfaces/api

## 它负责什么

`org.gotson.komga.interfaces.api` 是 Komga 后端的 HTTP API 接口层，负责把外部客户端请求转换成领域层操作，并把领域对象转换成不同协议需要的响应格式。它不是核心业务模型所在目录，也不是数据库底层实现目录，而是 Spring MVC `@RestController`、API DTO、接口层查询 repository、协议生成器和权限辅助组件的集合。

从目录结构看，它覆盖四类对外接口：

- 普通 Web/移动客户端使用的 REST API：`rest`
- OPDS 1.2 / OPDS 2 订阅与阅读接口：`opds`
- Kobo 设备兼容接口：`kobo`
- KOReader 阅读进度同步接口：`kosync`

根目录中的 `CommonBookController.kt`、`ContentRestrictionChecker.kt`、`WebPubGenerator.kt`、`OpdsGenerator.kt`、`Utils.kt` 则提供跨协议复用能力，例如下载书籍文件、读取页面、读取 EPUB 内部资源、生成 Web Publication Manifest、检查用户内容访问限制、设置缓存相关响应头等。

## 关键组成

`rest` 是主 REST API 层，包含 `BookController.kt`、`SeriesController.kt`、`LibraryController.kt`、`ReadListController.kt`、`UserController.kt`、`SettingsController.kt` 等控制器。它们通过 `@GetMapping`、`@PostMapping`、`@PutMapping`、`@PatchMapping`、`@DeleteMapping` 暴露 `/api/v1/...` 路由。以 `BookController.kt` 为例，它处理书籍列表、最新书籍、元数据更新、页面、缩略图、导入批次、阅读进度等能力，依赖 `BookDtoRepository` 查询面向 API 的 DTO，依赖 `BookLifecycle` 执行业务动作，依赖 `BookAnalyzer`、`MediaRepository`、`ContentDetector` 等完成媒体内容读取与类型判断。

`rest/dto` 是 REST 层数据契约目录，数量最多，包含 `BookDto.kt`、`SeriesDto.kt`、`LibraryDto.kt`、`ReadProgressUpdateDto.kt`、`SettingsDto.kt`、`UserDto.kt` 等。这里的 DTO 不是领域模型本身，而是接口响应或请求体的稳定结构。部分 DTO 还带有转换函数，例如 `toDto`、`patch`、`restrictUrl`，用于把领域对象、安全约束和 API 形态衔接起来。

`persistence` 是接口层查询仓库，包含 `BookDtoRepository.kt`、`SeriesDtoRepository.kt`、`ReadProgressDtoRepository.kt`、`HistoricalEventDtoRepository.kt` 等。根据当前片段推断，这些 repository 主要用于组合查询和投影成 API DTO，避免 controller 直接拼装复杂数据库结果；依据是 `BookController.kt` 中大量通过 `BookDtoRepository.findAll(...)` 返回 `Page<BookDto>`。

`CommonBookController.kt` 是跨 REST、OPDS、WebPub 的书籍内容公共控制器。它提供 `/api/v1/books/{bookId}/pages/{pageNumber}/raw`、`/opds/v2/books/{bookId}/pages/{pageNumber}/raw`、`/api/v1/books/{bookId}/resource/{*resource}`、`/api/v1/books/{bookId}/file`、`/api/v1/books/{bookId}/progression` 等能力。它的特点是同一个方法可以服务不同协议路径，内部统一做权限检查、媒体 profile 判断、缓存校验、文件流式输出、异常到 HTTP 状态码的转换。

`ContentRestrictionChecker.kt` 是接口层权限守门组件。它根据 `KomgaUser` 的 library 权限、年龄分级限制和 sharing labels 判断是否允许访问 `BookDto`、`Book`、`bookId` 或 `SeriesDto`。它抛出 `ResponseStatusException(HttpStatus.FORBIDDEN)` 或 `NOT_FOUND`，因此 controller 可以把权限判断当成前置步骤。

`WebPubGenerator.kt` 负责生成 Readium/Web Publication 风格的 manifest。它根据 `MediaProfile.DIVINA`、`PDF`、`EPUB` 生成不同的 `readingOrder`、`resources`、`toc`、`landmarks` 和 `pageList`。例如 DIVINA/PDF 会把页面映射成 page link，EPUB 会把 `MediaFile.SubType.EPUB_PAGE` 和 `EPUB_ASSET` 映射成资源链接，并读取 `MediaExtensionEpub` 中的目录、landmark、页列表。

`opds` 下有 `OpdsCommonController.kt` 以及 `opds/v1/OpdsController.kt`、`opds/v2/Opds2Controller.kt`。`OpdsCommonController.kt` 抽样显示它处理 `/opds/v1.2/books/{bookId}/thumbnail` 和 `/opds/v2/books/{bookId}/thumbnail`，先用 `ContentRestrictionChecker` 检查权限，再从 `BookLifecycle` 获取原始缩略图，必要时用 `ImageConverter` 转成 JPEG。

`kobo` 是 Kobo 设备兼容层。`KoboController.kt` 的路由前缀是 `/kobo/{authToken}/`，它依赖 `KoboProxy`、`KepubConverter`、`SyncPointLifecycle`、`KoboDtoRepository`、`CommonBookController` 等。代码注释说明 Kobo 设备请求会带 `authToken`，Komga 通过 API key 和 session cookie 支持后续请求。它还维护一个 Caffeine 缓存用于临时 kepub 文件，过期后删除文件。

`kosync` 是 KOReader 同步接口。`KoreaderSyncController.kt` 路由前缀是 `/koreader`，提供 `users/auth`、`syncs/progress/{bookHash}`、`syncs/progress` 等接口。它把 KOReader 的 progress 字符串和 Komga 内部的 `R2Progression` / `R2Locator` 互相转换：PDF/DIVINA 主要按页码处理，EPUB 则解析 `DocFragment[...]` 或 `#_doc_fragment_...`，再通过 `MediaExtensionEpub.positions` 找到 href。

## 上下游关系

上游是 HTTP 客户端，包括浏览器前端、移动客户端、OPDS 阅读器、Kobo 设备、KOReader。请求进入 Spring MVC controller 后，接口层会读取 `@AuthenticationPrincipal KomgaPrincipal`、路径参数、查询参数和请求体 DTO。

下游主要分三类：

- 领域仓库：`BookRepository`、`MediaRepository`、`SeriesMetadataRepository`、`ReadProgressRepository`、`ThumbnailBookRepository` 等，用于读取领域对象和媒体分析结果。
- 领域服务：`BookLifecycle`、`BookAnalyzer`、`SyncPointLifecycle` 等，用于执行阅读进度更新、页面读取、缩略图读取、文件内容读取、同步点处理等业务动作。
- 基础设施：`ImageConverter`、`ImageAnalyzer`、`ContentDetector`、`KoboProxy`、`KepubConverter`、`OpenApiConfiguration`、安全组件等，用于格式转换、媒体类型识别、Kobo 代理、OpenAPI 标注和认证授权。

这一层的设计重点是“接口适配”：领域层不需要知道 Kobo、OPDS、WebPub、KOReader 的具体 JSON 形状；这些协议差异集中在 `interfaces/api` 下处理。

## 运行/调用流程

普通 REST 查询流程大致是：客户端请求 `/api/v1/books/list`，`BookController.getBooks` 接收 `BookSearch` 和分页参数，构造 `PageRequest` 或 `UnpagedSorted`，调用 `BookDtoRepository.findAll(search, SearchContext(principal.user), pageRequest)`，最后对结果执行 `restrictUrl(!principal.user.isAdmin)` 并返回 `Page<BookDto>`。

读取书页流程大致是：客户端请求 `/api/v1/books/{bookId}/pages/{pageNumber}` 或相关 OPDS 路径，controller 进入公共逻辑，先通过 `BookRepository` / `MediaRepository` 找到书籍和媒体，使用 `ServletWebRequest.checkNotModified` 判断缓存是否命中，再调用 `ContentRestrictionChecker`。如果需要原始页，走 `BookAnalyzer.getPageContentRaw`；如果需要图片转换，走 `BookLifecycle.getBookPage` 并根据 `convert=jpeg/png` 转换。最后响应设置 `Content-Disposition`、`Content-Type`、last-modified/etag 类缓存头。

下载书籍文件流程是：`CommonBookController.downloadBookFile` 先检查 `@PreAuthorize("hasRole('FILE_DOWNLOAD')")`，再检查内容权限，读取 `FileSystemResource(book.path)`，用 `StreamingResponseBody` 流式复制到响应输出流，避免一次性把大文件全部放入内存。

WebPub manifest 流程是：controller 调用 `getWebPubManifestInternal`，根据 `MediaType.fromMediaType(media.mediaType)?.profile` 分派到 DIVINA、PDF 或 EPUB。随后 `WebPubGenerator` 生成 `WPPublicationDto`：基础元数据来自 `BookDto` 和 `SeriesMetadata`，阅读顺序来自页面、PDF 页数或 EPUB 文件列表，缩略图通过 `/api/v1/books/{bookId}/thumbnail` 链接暴露。

KOReader 同步流程是：KOReader 用书籍 hash 请求进度，`KoreaderSyncController` 通过 `BookRepository.findAllByHashKoreader` 找唯一书籍，再读 `ReadProgressRepository`。更新时，它把 KOReader 的 progress 转为 `R2Progression`，调用 `BookLifecycle.markProgression(book, principal.user, r2Progression)` 保存。

## 小白阅读顺序

建议先读 `ContentRestrictionChecker.kt`。它短小但很关键，能帮助理解为什么很多接口一开始都要检查 library 权限、年龄分级和 sharing labels。

第二步读 `CommonBookController.kt`。这里集中体现 Komga 如何处理书籍页面、原始资源、EPUB resource、文件下载和阅读 progression。读完它，再看其他 controller 会容易很多，因为许多协议入口只是复用它。

第三步读 `rest/BookController.kt`。它是 REST API 的代表文件，能看到搜索、分页、DTO repository、领域 lifecycle、OpenAPI 注解、权限注解如何组合。

第四步读 `WebPubGenerator.kt` 和 `dto/WepPub.kt`。这部分能理解 Komga 如何把内部书籍媒体结构转换为 Readium/WebPub 的 manifest。

第五步按兴趣选择协议：如果关心订阅阅读器，读 `opds/OpdsCommonController.kt`、`opds/v1/OpdsController.kt`、`opds/v2/Opds2Controller.kt`；如果关心 Kobo，读 `kobo/KoboController.kt` 和 `kobo/dto`；如果关心 KOReader，同步逻辑集中在 `kosync/KoreaderSyncController.kt`。

最后再回头看 `rest/dto` 和 `persistence`。DTO 和查询仓库数量很多，不建议一开始逐个读；应当在理解某个 controller 的请求/响应时按需跳转。

## 常见误区

不要把 `interfaces/api/persistence` 误认为整个系统的数据库基础设施层。它更像 API 投影查询层，面向接口 DTO 组织数据；真正的领域持久化接口在 `org.gotson.komga.domain.persistence`。

不要认为所有接口都只服务 `/api/v1`。`CommonBookController.kt` 同时挂了 `/api/v1`、`/opds/v1.2`、`/opds/v2` 等路径；同一段读取文件或页面的逻辑会被 REST、OPDS、WebPub 复用。

不要跳过 `ContentRestrictionChecker`。很多接口即使已经认证，也还要检查用户是否有目标 library 权限，以及是否受内容分级限制。认证成功不等于能访问所有书籍。

不要把 `BookDto` 当作领域模型 `Book`。`BookDto` 是 API 输出形态，可能包含 series title、metadata、media 摘要、受限 URL 等接口需要的信息；真正的领域对象和服务在 `domain` 包下。

不要以为 EPUB、PDF、漫画图片页走完全相同的读取方式。代码中多处根据 `MediaProfile.DIVINA`、`PDF`、`EPUB` 分支处理：PDF 可返回 raw PDF 页，DIVINA 偏页面图片序列，EPUB 还要处理内部资源、目录、landmarks 和位置列表。

不要忽略缓存与响应头。读取页面、EPUB resource、文件下载等逻辑会设置 `Content-Disposition`、`Content-Type`、`Content-Security-Policy`、not-modified 相关头；这些是阅读器兼容性和性能的一部分，不只是“返回 bytes”这么简单。
