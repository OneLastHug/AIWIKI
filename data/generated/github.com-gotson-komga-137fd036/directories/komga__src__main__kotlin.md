# 目录：komga/src/main/kotlin

## 它负责什么

`komga/src/main/kotlin` 是 Komga 服务端的 Kotlin 主源码目录，包根为 `org.gotson.komga`。从目录结构和入口文件看，它承载的是一个 Spring Boot 后端应用：负责启动服务、暴露 REST/OPDS/Kobo/Koreader 等接口、执行业务生命周期、访问数据库、处理文件与媒体内容、维护搜索索引、安全认证、定时任务和服务端事件推送。

入口是 `komga/src/main/kotlin/org/gotson/komga/Application.kt`。该文件使用 `@SpringBootApplication` 启动 Spring 容器，使用 `@EnableScheduling` 开启定时任务，`main` 中先调用 `checkTempDirectory()` 检查临时目录，再设置 jOOQ 的 `org.jooq.no-logo`、`org.jooq.no-tips`，最后 `runApplication<Application>(*args)` 启动应用。

从文件数量看，主包下约有这些规模：`domain` 110 个 Kotlin 文件、`infrastructure` 159 个、`interfaces` 151 个、`application` 8 个。也就是说，这个目录不是单一模块，而是 Komga 后端的核心分层实现。

## 关键组成

`org/gotson/komga/application` 是应用层。它包含 `events`、`scheduler`、`tasks` 等子目录，偏向跨业务流程的编排。例如 `TaskEmitter`、任务优先级、异步事件配置等会被接口层或领域服务调用。`BookController.kt` 中就注入了 `TaskEmitter`，说明某些 API 操作不会只同步完成，而会派发后台任务。

`org/gotson/komga/domain` 是领域层，分为 `model`、`persistence`、`service`。`model` 放核心业务对象和搜索条件，例如从 `BookController.kt` 的 import 可见有 `BookSearch`、`Dimension`、`DomainEvent`、`Media`、`ReadStatus`、`SearchCondition`、`SearchContext`、`ThumbnailBook` 等。`persistence` 定义领域仓储接口，例如 `BookRepository.kt`、`LibraryRepository.kt`、`SeriesRepository.kt`、`ReadListRepository.kt`、`KomgaUserRepository.kt`、`MediaRepository.kt`、`ThumbnailBookRepository.kt`。`service` 放领域服务，文件包括 `BookAnalyzer.kt`、`BookImporter.kt`、`BookLifecycle.kt`、`LibraryLifecycle.kt`、`SeriesLifecycle.kt`、`MetadataAggregator.kt`、`MetadataApplier.kt`、`ReadListLifecycle.kt`、`FileSystemScanner.kt` 等。根据当前片段推断，领域层负责“书籍、系列、书库、阅读列表、元数据、导入扫描、缩略图、阅读进度”等核心规则。

`org/gotson/komga/infrastructure` 是基础设施层，给领域层和接口层提供技术实现。子目录覆盖面很广：`configuration`、`datasource`、`jooq`、`security`、`web`、`image`、`mediacontainer`、`metadata`、`search`、`cache`、`transaction`、`xml`、`kobo`、`sidecar` 等。代表配置包括 `DataSourcesConfiguration.kt`、`KomgaJooqConfiguration.kt`、`SecurityConfiguration.kt`、`CorsConfiguration.kt`、`LuceneConfiguration.kt`、`WebMvcConfiguration.kt`、`OpenApiConfiguration.kt`。从这些命名可以看出，数据库访问主要围绕 jOOQ，搜索使用 Lucene，认证授权由 Spring Security 承担。

`org/gotson/komga/interfaces` 是外部接口层。`interfaces/api/rest` 暴露常规 REST API，例如 `BookController.kt`、`LibraryController.kt`、`SeriesController.kt`、`UserController.kt`、`SettingsController.kt`、`TaskController.kt`。`interfaces/api/opds` 提供 OPDS v1/v2；`interfaces/api/kobo` 提供 Kobo 接口；`interfaces/api/kosync` 提供 Koreader 同步；`interfaces/mvc` 包含 `IndexController.kt` 等页面入口；`interfaces/sse` 提供服务端事件推送；`interfaces/scheduler` 放由调度触发的控制器，例如 `PeriodicScannerController.kt`、`SearchIndexController.kt`、`InitialUserController.kt`。

## 上下游关系

上游入口主要是 HTTP 请求、定时任务和 Spring 事件。HTTP 请求进入 `interfaces/api/rest`、`interfaces/api/opds`、`interfaces/api/kobo`、`interfaces/api/kosync` 等控制器；定时任务由 `@EnableScheduling` 启用后进入 `interfaces/scheduler`；内部事件由 `application/events` 处理。

接口层向下依赖领域层和应用层。以 `BookController.kt` 为例，它注入 `BookAnalyzer`、`BookLifecycle`、`BookRepository`、`BookMetadataRepository`、`MediaRepository`、`ReadListRepository`、`ThumbnailBookRepository`、`BookDtoRepository`、`CommonBookController`、`ContentRestrictionChecker`、`WebPubGenerator`、`ApplicationEventPublisher` 等。它一方面直接查询 DTO 仓储返回页面数据，另一方面调用生命周期服务或分析器处理业务动作。

领域层向下依赖仓储抽象和基础设施能力。`domain/persistence` 里的仓储接口表达“需要保存或查询什么”，实际数据库实现根据当前目录结构应在 `infrastructure/jooq` 或 `interfaces/api/persistence` 等位置完成。这里要注意：`interfaces/api/persistence` 中的 `BookDtoRepository.kt`、`SeriesDtoRepository.kt` 更像面向 API 返回模型的查询仓储，不等同于领域层的 `BookRepository.kt`。

基础设施层是技术下游：数据库、Lucene、图片处理、媒体容器解析、Tika、XML、HTTP filter、安全 session、OAuth2、CORS、OpenAPI 等都在这里落地。领域层不应该反过来关心 Controller 的 URL 或 DTO 细节。

## 运行/调用流程

应用启动流程大致是：执行 `Application.kt` 的 `main`，先检查临时目录，然后关闭 jOOQ logo/tips，再启动 Spring Boot；Spring 扫描 `org.gotson.komga` 下的组件，加载安全、数据源、jOOQ、Web、OpenAPI、Lucene、事务、过滤器等配置；由于启用了 `@EnableScheduling`，调度相关组件也会开始工作。

一个典型的 REST 查询流程可以从 `BookController.kt` 理解。请求进入如 `POST api/v1/books/list`，Spring Security 将当前用户注入为 `KomgaPrincipal`，Controller 接收 `BookSearch`、分页参数和排序参数。如果请求没有显式排序但有全文搜索，则默认按 `relevance` 排序；如果传入 `unpaged=true`，会使用 `UnpagedSorted`。随后 Controller 调用 `bookDtoRepository.findAll(search, SearchContext(principal.user), pageRequest)` 查询，再对结果执行 `restrictUrl(!principal.user.isAdmin)`，也就是非管理员用户会被限制部分 URL 信息。

旧接口 `GET api/v1/books` 已标记 `@Deprecated("use /v1/books/list instead")`，它会把 query 参数转换成 `BookSearch`，再走类似的查询路径。这说明新版 API 更倾向用结构化搜索对象，而不是散落的查询参数。

涉及修改、导入、分析、缩略图、阅读进度、事件通知的流程，根据当前片段推断，会从 Controller 调用 `BookLifecycle`、`BookAnalyzer`、`TaskEmitter`、`ApplicationEventPublisher` 等组件，进一步触发领域服务、后台任务和事件监听器。

## 小白阅读顺序

第一步读 `komga/src/main/kotlin/org/gotson/komga/Application.kt`，先确认这是 Spring Boot 应用，以及调度任务是全局启用的。

第二步看 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/BookController.kt`、`LibraryController.kt`、`SeriesController.kt`。这些文件最接近用户操作，能快速理解 Komga 对外提供哪些资源：books、libraries、series、read lists、users、settings、tasks。

第三步看 `komga/src/main/kotlin/org/gotson/komga/domain/model`。这里定义业务语言，读懂 `BookSearch`、`Media`、`ReadStatus`、`SearchCondition` 这类模型后，再看 Controller 会顺很多。

第四步看 `komga/src/main/kotlin/org/gotson/komga/domain/service`。优先读 `BookLifecycle.kt`、`LibraryLifecycle.kt`、`SeriesLifecycle.kt`、`FileSystemScanner.kt`、`MetadataAggregator.kt`，它们更能解释“书库扫描、书籍导入、元数据聚合、生命周期更新”这些核心动作。

第五步看 `komga/src/main/kotlin/org/gotson/komga/domain/persistence` 和 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq`。前者告诉你业务需要哪些仓储能力，后者帮助你理解数据库访问如何实现。

第六步再看 `komga/src/main/kotlin/org/gotson/komga/infrastructure/security`、`infrastructure/web`、`interfaces/api/opds`、`interfaces/api/kobo`。这些属于横切能力或协议适配，适合在理解主业务后补充。

## 常见误区

不要把 `interfaces` 理解成“前端”。这里的 `interfaces` 是后端对外接口层，包括 REST、OPDS、Kobo、Koreader Sync、MVC、SSE、scheduler 等入口。

不要把 `domain/persistence` 和 `interfaces/api/persistence` 混为一谈。前者是领域仓储抽象，例如 `BookRepository.kt`；后者从命名看更偏 API DTO 查询，例如 `BookDtoRepository.kt`，服务的是接口返回形态。

不要以为 Controller 只做简单转发。`BookController.kt` 中有搜索条件组装、分页排序处理、权限相关 URL 裁剪、缓存/响应相关工具调用、任务派发和事件发布依赖。阅读时要区分“请求适配逻辑”和“真正业务生命周期逻辑”。

不要跳过 `infrastructure/configuration`、`infrastructure/security`、`infrastructure/web`。很多运行时行为不是写在业务服务里，而是由 Spring 配置、Filter、Security chain、消息转换器、CORS、Session、OpenAPI 配置共同决定。

不要从数据库实现开始读。Komga 的业务概念较多，直接看 jOOQ 或表结构容易迷失。更合适的路径是先看 API，再看领域模型和生命周期服务，最后回到底层持久化实现。
