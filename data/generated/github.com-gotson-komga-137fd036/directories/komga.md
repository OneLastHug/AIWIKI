# 目录：komga

## 它负责什么

`komga` 是整个仓库里的后端主应用模块，核心职责是提供 Komga 服务器端能力：启动 Spring Boot 应用、暴露 HTTP/API 接口、管理漫画/图书媒体库、扫描文件系统、解析媒体文件、维护元数据、读书进度、用户与权限、搜索索引、任务调度，以及把前端构建产物作为静态资源提供出去。

从 `komga/build.gradle.kts` 可以看出它是 Kotlin + Spring Boot 应用，运行目标是 JVM 17。它依赖 `spring-boot-starter-web`、`spring-boot-starter-security`、`spring-boot-starter-jooq`、`spring-boot-starter-actuator`、`springdoc-openapi`、`flyway`、`sqlite-jdbc`、`lucene`、`tika`、`pdfbox`、`thumbnailator`、`zxing` 等库。也就是说，这个目录不是单纯的 API 层，而是后端完整业务服务。

`application.yml` 里默认服务端口是 `25600`，默认配置目录是 `${user.home}/.komga`，主数据库文件是 `${komga.config-dir}/database.sqlite`，任务数据库是 `${komga.config-dir}/tasks.sqlite`，Lucene 索引目录是 `${komga.config-dir}/lucene`。这说明 Komga 默认是一个本地持久化、自带 SQLite 数据库和索引目录的服务端程序。

## 关键组成

`komga/src/main/kotlin/org/gotson/komga/Application.kt` 是启动入口。它标注了 `@SpringBootApplication` 和 `@EnableScheduling`，`main` 函数会先执行 `checkTempDirectory()`，再设置 jOOQ 的系统属性，最后调用 `runApplication<Application>(*args)` 启动 Spring 容器。

`domain` 是领域层，包含三类内容：

`domain/model` 放核心领域模型，例如 `Library`、`Book`、`Series`、`Media`、`ReadList`、`ReadProgress`、`KomgaUser`、`ApiKey`、`ThumbnailBook`、`PageHash`、`SearchCondition` 等。这里定义“系统认识什么”。

`domain/persistence` 放仓储接口，例如 `LibraryRepository`、`BookRepository`、`SeriesRepository`、`KomgaUserRepository`、`ReadProgressRepository`、`ThumbnailBookRepository`、`PageHashRepository` 等。这里定义领域层需要什么数据访问能力，但不关心具体 SQL 怎么写。

`domain/service` 放业务服务和生命周期对象，例如 `LibraryLifecycle`、`BookLifecycle`、`SeriesLifecycle`、`LibraryContentLifecycle`、`FileSystemScanner`、`BookAnalyzer`、`BookImporter`、`MetadataAggregator`、`ReadListLifecycle`、`PageHashLifecycle` 等。这里是“添加媒体库、扫描文件、导入书籍、分析元数据、更新封面/进度”等核心业务发生的地方。

`interfaces` 是外部接口层。`interfaces/api/rest` 下有大量 REST Controller，例如 `LibraryController`、`BookController`、`SeriesController`、`ReadListController`、`UserController`、`SettingsController`、`TaskController`、`FontsController` 等。`LibraryController` 的代码显示，它通过 `@RestController` 和 `@RequestMapping("api/v1/libraries")` 暴露媒体库 API，并注入 `TaskEmitter`、`LibraryLifecycle`、`LibraryRepository`、`BookRepository`、`SeriesRepository` 来完成查询和变更。`interfaces/api/opds`、`interfaces/api/kobo`、`interfaces/api/kosync` 则服务 OPDS、Kobo、KOReader 同步等外部阅读客户端协议。`interfaces/mvc/IndexController.kt` 用于前端页面入口，根据当前片段推断，它和 `build.gradle.kts` 中复制 `komga-webui/dist` 到 `src/main/resources/public/` 的逻辑一起，负责让后端托管 Web UI。

`infrastructure` 是基础设施实现层。它包含 `datasource`、`jooq`、`security`、`search`、`mediacontainer`、`metadata`、`image`、`kobo`、`web`、`configuration` 等子包。根据包名和依赖可以判断：`datasource` 配置 SQLite 数据源和 Flyway 迁移；`jooq/main`、`jooq/tasks` 是仓储接口背后的 SQL/jOOQ 实现；`mediacontainer` 负责识别和抽取 EPUB、PDF、ZIP/RAR 等媒体容器；`metadata` 读取 ComicInfo、EPUB、Mylar、本地封面、ISBN 条码等元数据；`search` 负责 Lucene 索引；`security` 负责登录、角色、会话、OAuth2、API key 等。

`application` 更偏应用编排。`application/tasks` 有 `Task`、`TaskEmitter`、`TaskProcessor`、`TaskHandler`、`TasksRepository` 等，表示后台任务系统；`application/scheduler/LibraryScanScheduler.kt` 表示定时扫描；`application/events` 里有异步事件配置。

`resources` 提供运行配置、数据库迁移、静态资源和内置字体。`komga/src/main/resources/application.yml` 是主配置；`application-dev.yml`、`application-docker.yml`、`application-localdb.yml` 是不同运行场景的配置；`src/flyway` 和资源里的迁移位置共同服务数据库 schema 演进；`embeddedFonts` 提供内置字体资源。

## 上下游关系

上游入口主要有三类。

第一类是用户或前端 Web UI 发起的 HTTP 请求，请求进入 `interfaces/api/rest`、`interfaces/mvc`、`interfaces/sse`。REST Controller 做认证、参数校验、DTO 转换，然后调用领域服务或仓储接口。

第二类是外部阅读客户端，例如 OPDS 客户端、Kobo 设备、KOReader 同步客户端。它们进入 `interfaces/api/opds`、`interfaces/api/kobo`、`interfaces/api/kosync`，再复用同一套领域模型、仓储和媒体读取能力。

第三类是后台调度和事件。`@EnableScheduling` 启用 Spring 调度，`interfaces/scheduler`、`application/scheduler`、`application/tasks` 会触发媒体库扫描、搜索索引维护、清理认证活动、初始用户创建、指标发布等后台流程。

下游依赖主要包括：

SQLite 数据库：主库保存媒体库、书籍、系列、用户、阅读进度、缩略图等信息；任务库保存后台任务状态。

文件系统：媒体库根目录、配置目录、日志目录、字体目录、Lucene 索引目录都依赖本地路径。

媒体解析库：Tika、PDFBox、Junrar、nightcompress、ImageIO、Thumbnailator 等负责识别文件、读取页面、生成封面和缩略图。

搜索引擎：Lucene 负责书籍/系列等内容检索。

前端模块：`komga/build.gradle.kts` 中的 `npmInstall`、`npmBuild`、`copyWebDist`、`prepareThymeLeaf` 会构建 `komga-webui`，并把产物放到 `komga/src/main/resources/public/`，因此后端打包时会包含 Web UI。

## 运行/调用流程

启动流程大致是：

1. JVM 运行 `org.gotson.komga.ApplicationKt.main`。
2. `main` 检查临时目录，关闭 jOOQ logo/tips。
3. Spring Boot 扫描 `org.gotson.komga` 包下的组件，加载配置、数据源、安全、Web、调度、jOOQ、Lucene、媒体解析等 Bean。
4. Flyway 根据 `spring.flyway.locations: classpath:db/migration/{vendor}` 执行数据库迁移。
5. Web 服务监听 `25600` 端口，静态 Web UI、REST API、OPDS/Kobo/KOReader API、SSE 等接口开始可用。
6. 调度器和任务处理器开始处理周期性扫描、索引、清理等后台任务。

以创建媒体库为例，`LibraryController` 接收 `POST /api/v1/libraries` 请求，要求管理员权限，DTO 是 `LibraryCreationDto`。Controller 把 DTO 转成领域对象 `Library`，并调用 `LibraryLifecycle.addLibrary`。根据当前片段推断，`LibraryLifecycle` 会校验路径、名称、父子路径冲突等业务规则，然后通过 `LibraryRepository` 持久化，再可能通过 `TaskEmitter` 发出扫描任务，让后台任务系统开始导入该库中的书籍。

以扫描导入为例，请求或调度触发任务后，`application/tasks` 负责排队和处理；领域层的 `FileSystemScanner`、`BookImporter`、`BookAnalyzer`、`MetadataAggregator` 等读取文件系统和媒体文件；基础设施层的 `mediacontainer`、`metadata`、`image` 完成格式识别、元数据读取、封面/页面分析；最后通过 `domain/persistence` 接口和 `infrastructure/jooq` DAO 写入 SQLite，并更新 Lucene 索引或缩略图等派生数据。

## 小白阅读顺序

建议先看 `komga/build.gradle.kts`，理解这是一个 Spring Boot Kotlin 后端，并注意它和 `komga-webui` 的构建关系。

第二步看 `komga/src/main/resources/application.yml`，掌握默认端口、配置目录、数据库文件、Lucene 目录、Flyway、Actuator、Springdoc 等运行配置。

第三步看 `komga/src/main/kotlin/org/gotson/komga/Application.kt`，确认应用启动点和调度开关。

第四步看 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/LibraryController.kt`、`BookController.kt`、`SeriesController.kt`，从 HTTP API 入口理解 Controller 如何调用领域服务和仓储。

第五步看 `domain/model/Library.kt`、`Book.kt`、`Series.kt`、`Media.kt`，建立核心数据概念。

第六步看 `domain/service/LibraryLifecycle.kt`、`FileSystemScanner.kt`、`BookAnalyzer.kt`、`BookImporter.kt`，理解媒体库扫描和书籍导入这条主线。

第七步再进入 `infrastructure/jooq/main`，看 DAO 如何实现 `domain/persistence` 中的仓储接口。不要一开始就钻 SQL，否则容易被表结构和查询细节淹没。

第八步按兴趣阅读扩展协议：Web API 看 `interfaces/api/rest`，OPDS 看 `interfaces/api/opds`，Kobo 看 `interfaces/api/kobo`，KOReader 同步看 `interfaces/api/kosync`。

## 常见误区

不要把 `komga` 理解成只有 API 层。它同时包含领域模型、业务服务、数据库访问实现、媒体解析、安全配置、搜索索引、后台任务、静态前端托管，是后端主模块。

不要认为 `domain/persistence` 里就是数据库实现。这里主要是仓储接口；真正的 jOOQ/SQLite 实现集中在 `infrastructure/jooq/main` 和 `infrastructure/jooq/tasks`。

不要忽略 `komga-webui`。虽然目标目录是 `komga`，但 `komga/build.gradle.kts` 明确会执行前端构建，并把 `komga-webui/dist` 复制进 `komga/src/main/resources/public/`，所以最终服务器包会同时提供 API 和 Web UI。

不要把扫描流程等同于一次同步 HTTP 调用。媒体库扫描、索引更新、缩略图生成等很多操作会通过 `application/tasks` 和 scheduler 异步执行。

不要把所有客户端都看成浏览器。该模块同时服务普通 Web UI、REST API、OPDS 阅读器、Kobo、KOReader 等不同调用方，很多接口设计是为了兼容阅读设备或同步协议。

不要只看 Controller 来判断业务规则。Controller 多数负责入口、权限、DTO 和状态码；真正的规则通常在 `domain/service/*Lifecycle.kt`、扫描器、导入器和聚合器里。
