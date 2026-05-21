# 目录：komga/src/main/kotlin/org/gotson/komga/interfaces

## 它负责什么

`org.gotson.komga.interfaces` 是 Komga 后端的“接口适配层”，负责把外部世界的请求、事件入口、定时触发和命令行操作，转换成对 `domain`、`application`、`infrastructure` 层的调用。

从目录结构看，它不是业务规则的核心实现层，而是边界层：HTTP REST/API、OPDS/WebPub 输出、MVC 首页、SSE 推送、启动后调度任务、命令行 runner 都集中在这里。它的主要职责包括：

- 接收客户端 HTTP 请求，例如书籍页面、原始文件、WebPub manifest、OPDS 等。
- 做权限、内容限制、请求参数校验、HTTP 缓存协商、响应头设置。
- 把请求转给领域仓库和领域服务，例如 `BookRepository`、`MediaRepository`、`BookLifecycle`、`BookAnalyzer`。
- 把领域事件转换成 SSE 消息，推送给前端。
- 在应用启动时执行初始化、定时扫描、清理、索引等任务。
- 提供非 Web 入口，例如用户列表、密码重置等 app runner。

简单理解：`interfaces` 是 Komga 后端面对“用户、浏览器、客户端、系统启动事件”的入口集合。

## 关键组成

`komga/src/main/kotlin/org/gotson/komga/interfaces/api` 是 API 层的主体。直接文件包括 `CommonBookController.kt`、`ContentRestrictionChecker.kt`、`OpdsGenerator.kt`、`Utils.kt`、`WebPubGenerator.kt`，并包含 `dto`、`kobo`、`kosync`、`opds`、`persistence`、`rest` 等子目录。  
其中 `CommonBookController` 是一个很典型的代表：它是 `@RestController`，通过 `@GetMapping`、`@PutMapping` 暴露书籍页面、原始页面、WebPub manifest、阅读进度等接口。它注入 `MediaRepository`、`BookRepository`、`BookDtoRepository`、`BookLifecycle`、`BookAnalyzer`、`ContentRestrictionChecker` 等对象，说明 API 层本身不直接解析书籍文件，而是协调仓库、服务和转换器。

`ContentRestrictionChecker` 从命名看负责内容访问限制检查。`CommonBookController` 在返回 manifest、页面内容前都会调用 `contentRestrictionChecker.checkContentRestriction(...)`，这是接口层保护业务数据的关键步骤之一。

`WebPubGenerator` 和 `OpdsGenerator` 负责把内部书籍、系列、媒体等数据转换成外部协议需要的表现形式。`CommonBookController` 中根据 `MediaProfile.DIVINA`、`MediaProfile.PDF`、`MediaProfile.EPUB` 分流到不同的 WebPub manifest 生成逻辑，说明 Komga 会按媒体类型输出不同阅读协议结构。

`komga/src/main/kotlin/org/gotson/komga/interfaces/mvc` 是传统 MVC 页面入口。`IndexController` 使用 `@Controller` 和 `@GetMapping("/")` 返回 `index` 视图，并把 `servletContext.contextPath` 形成的 `baseUrl` 放入 `Model`。这通常服务于前端单页应用的入口 HTML。`ResourceNotFoundController` 从命名看处理资源未找到场景。

`komga/src/main/kotlin/org/gotson/komga/interfaces/sse` 负责 Server-Sent Events。`SseController` 通过 `@GetMapping("sse/v1/events")` 创建 `SseEmitter`，维护当前连接用户；通过 `@EventListener` 监听 `DomainEvent`，把 `LibraryAdded`、`SeriesUpdated`、`BookDeleted`、`ReadProgressChanged`、`ThumbnailBookAdded`、`UserDeleted` 等领域事件转换成前端可消费的 SSE 事件。它还用 `@Scheduled` 定期发送 heartbeat 和任务队列状态。

`komga/src/main/kotlin/org/gotson/komga/interfaces/scheduler` 是应用启动和周期性后台任务入口。代表文件 `PeriodicScannerController` 在 `ApplicationReadyEvent` 后执行两件事：对设置了 `scanOnStartup` 的 library 发出扫描任务；把所有 library 交给 `LibraryScanScheduler.scheduleScan(...)` 注册周期扫描。该目录还包含 `AuthenticationActivityCleanupController`、`InitialUserController`、`MetricsPublisherController`、`SearchIndexController`，分别对应清理、初始用户、指标发布、搜索索引等后台流程。

`komga/src/main/kotlin/org/gotson/komga/interfaces/apprunner` 包含 `ListUsersRunner.kt`、`PasswordResetRunner.kt`，根据当前片段推断，它们是 Spring Boot 启动时可执行的命令行任务，用于运维类操作。

## 上下游关系

上游调用者主要有几类：

- 浏览器或前端应用访问 `/`，进入 `mvc/IndexController`。
- Web、移动端、OPDS、Kobo、KOSync 等客户端调用 `api` 下的 REST 或协议接口。
- 前端建立 `sse/v1/events` 长连接，接收后端事件。
- Spring Boot 生命周期事件触发 `scheduler` 中的控制器。
- 命令行参数或运行模式触发 `apprunner` 中的 runner。

下游依赖主要落在三个内部层：

- `domain`：例如 `Book`、`Media`、`MediaProfile`、`DomainEvent`、`KomgaUser`，以及 `BookRepository`、`MediaRepository`、`ReadProgressRepository`、`SeriesMetadataRepository` 等仓库接口。
- `application`：例如 `LibraryScanScheduler`、`TaskEmitter`、`TasksRepository`，负责调度和任务队列。
- `infrastructure`：例如 `KomgaPrincipal`、`ContentDetector`、`OpenApiConfiguration`、`getMediaTypeOrDefault`、`toFilePath`，提供安全、Web、媒体类型、OpenAPI、路径转换等技术能力。

因此 `interfaces` 的位置很清楚：它依赖应用服务和领域模型，但领域层不应该反向依赖它。它把外部协议细节限制在边界处，避免污染核心业务模型。

## 运行/调用流程

以获取书籍页面为例，`CommonBookController` 的流程大致是：

1. Spring MVC 根据 URL 匹配到 controller 方法，例如书籍页或原始页接口。
2. 方法从路径参数取得 `bookId`、`pageNumber`，从认证上下文取得 `KomgaPrincipal`。
3. 通过 `BookRepository`、`MediaRepository` 查询书籍和媒体信息。
4. 使用 `ServletWebRequest.checkNotModified(...)` 判断客户端缓存是否仍有效；如果未修改，返回 `304 NOT_MODIFIED`。
5. 调用 `ContentRestrictionChecker` 检查当前用户是否允许访问该书。
6. 对 PDF、图片转换格式、Accept header 做内容协商和参数校验。
7. 调用 `BookLifecycle.getBookPage(...)` 或 `BookAnalyzer.getPageContentRaw(...)` 获取内容。
8. 设置 `Content-Disposition`、`Content-Type`、缓存相关响应头，返回 `ResponseEntity`。
9. 对页码越界、转换失败、媒体未分析、文件丢失等异常转换成合适的 HTTP 状态码。

以 SSE 为例，流程是：

1. 前端请求 `sse/v1/events`。
2. `SseController.sse(...)` 创建 `SseEmitter`，并把 emitter 和当前 `KomgaUser` 记录在内存 map 中。
3. 领域层发布 `DomainEvent`。
4. `SseController.handleSseEvent(...)` 监听事件并匹配具体类型。
5. Controller 创建对应 DTO，例如 `BookSseDto`、`LibrarySseDto`、`ReadProgressSseDto`。
6. `emitSse(...)` 按 `adminOnly` 或 `userIdOnly` 过滤连接用户。
7. 通过 `SseEmitter.event().name(...).data(..., MediaType.APPLICATION_JSON)` 推送给前端。
8. 定时 heartbeat 保持连接活跃；应用停止时通过 `SmartLifecycle.stop()` 关闭所有连接。

以启动扫描为例，`PeriodicScannerController` 在 `ApplicationReadyEvent` 后读取全部 library。设置了 `scanOnStartup` 的 library 会通过 `TaskEmitter.scanLibrary(...)` 投递扫描任务；所有 library 都会交给 `LibraryScanScheduler.scheduleScan(...)` 注册周期扫描。

## 小白阅读顺序

建议先从 `komga/src/main/kotlin/org/gotson/komga/interfaces/mvc/IndexController.kt` 开始。这个文件很短，可以快速理解 Spring `@Controller`、`@GetMapping`、`Model` 和视图返回值在项目中的用法。

第二步看 `komga/src/main/kotlin/org/gotson/komga/interfaces/scheduler/PeriodicScannerController.kt`。它展示了接口层不一定都是 HTTP，也可以是应用生命周期事件入口。这里能看到 `ApplicationReadyEvent`、`TaskEmitter`、`LibraryScanScheduler` 的关系。

第三步看 `komga/src/main/kotlin/org/gotson/komga/interfaces/sse/SseController.kt`。这个文件能帮助理解 Komga 如何把领域事件推给前端。重点看 `sse(...)`、`handleSseEvent(...)`、`emitSse(...)` 三个方法。

第四步再看 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/CommonBookController.kt`。它较长，但代表性最强。阅读时不要一开始陷入每个 endpoint 的细节，先抓住公共模式：查仓库、验权限、处理缓存、调用服务、设置 HTTP 响应、转换异常。

第五步扩展到 `api/rest`、`api/opds`、`api/kobo`、`api/kosync`、`api/dto`。根据当前目录命名推断，这些子目录分别承载不同客户端协议、REST 资源控制器和数据传输对象。读这些目录时，可以按“URL 入口 -> DTO -> service/repository 调用 -> 返回响应”的路线跟踪。

## 常见误区

第一个误区是把 `interfaces` 当成业务核心层。实际上这里更多是适配外部输入输出，核心业务通常在 `domain` 和 `application`。例如书籍页面内容不是 `CommonBookController` 自己解析出来的，而是交给 `BookLifecycle`、`BookAnalyzer` 等服务。

第二个误区是认为 controller 只负责转发请求。Komga 的接口层还承担了不少边界职责，例如权限注解 `@PreAuthorize`、`ContentRestrictionChecker` 内容限制、HTTP 缓存协商、媒体类型协商、异常到 HTTP 状态码的映射、响应头构造等。这些属于 Web/API 边界逻辑，不宜下沉到领域层。

第三个误区是忽略 SSE 的用户过滤。`SseController.emitSse(...)` 不只是广播，它会根据 `adminOnly` 和 `userIdOnly` 过滤连接。比如任务队列状态只发给管理员，阅读进度变化只发给对应用户。

第四个误区是把 `scheduler` 理解成底层定时器实现。该目录里的类更像“调度入口控制器”，真正的扫描计划和任务执行在 `application.scheduler`、`application.tasks` 等下游模块。

第五个误区是看到 `api` 下有 `opds`、`kobo`、`kosync` 就以为它们是独立应用。根据当前目录结构，它们仍在同一个 Spring Boot 后端中，只是面向不同外部协议或客户端的接口分组。
