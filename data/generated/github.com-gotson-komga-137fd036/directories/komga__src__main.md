# 目录：komga/src/main

## 它负责什么

`komga/src/main` 是 Komga 服务端主程序目录，承载 Spring Boot/Kotlin 后端的运行时代码与资源配置。它不是单一功能模块，而是完整后端应用的入口层：从 `Application.kt` 启动 Spring 容器，到 REST/OPDS/Kobo/KOReader/SSE 接口暴露，再到领域模型、业务服务、SQLite/jOOQ 持久化、媒体解析、元数据读取、搜索索引、安全认证、后台任务调度等。

从目录结构看，它采用接近分层架构的组织方式：

- `org.gotson.komga.domain` 定义核心领域对象、仓储接口和业务生命周期服务。
- `org.gotson.komga.infrastructure` 放实现细节，如数据库、jOOQ DAO、安全、搜索、媒体容器解析、图片处理、配置等。
- `org.gotson.komga.interfaces` 面向外部输入输出，包括 HTTP API、MVC 首页、SSE、定时/启动控制器、命令行 runner。
- `org.gotson.komga.application` 放应用层事件、任务队列和扫描调度。
- `resources` 放 `application*.yml`、启动 banner、内置字体资源。

因此，阅读这个目录时应把它理解为“Komga 后端主体”，而不是某个普通业务子包。

## 关键组成

启动入口是 `komga/src/main/kotlin/org/gotson/komga/Application.kt`。它声明 `@SpringBootApplication` 和 `@EnableScheduling`，启动前调用 `checkTempDirectory()`，并关闭 jOOQ logo/tips，然后通过 `runApplication<Application>(*args)` 拉起整个 Spring Boot 应用。

配置集中在 `komga/src/main/resources/application.yml` 和各 profile 配置。默认配置设置了 `komga.config-dir`、主数据库 `database.sqlite`、任务数据库 `tasks.sqlite`、Lucene 目录、字体目录、Flyway 迁移位置、Jackson 行为、Actuator、端口 `25600` 等。`application-dev.yml` 使用内存 SQLite、调试日志和端口 `8080`；`application-docker.yml` 主要配置 Kobo kepubify 路径；`application-localdb.yml` 切换本地 workspace 数据库文件。

`infrastructure/configuration/KomgaProperties.kt` 将 `komga.*` 配置绑定成类型化属性，并在初始化时尝试创建数据库与任务数据库父目录。这里定义了数据库池、SQLite journal mode、Lucene analyzer、CORS、Kobo、字体目录等基础运行参数。

数据库入口在 `infrastructure/datasource/DataSourcesConfiguration.kt`。它为主业务库和任务库分别创建读写数据源：`sqliteDataSourceRW`、`sqliteDataSourceRO`、`tasksDataSourceRW`、`tasksDataSourceRO`。当 SQLite 使用 WAL 且不是内存库时，会拆分读写连接池；写池最大连接数强制或倾向于 1，符合 SQLite 写入模型。

安全入口是 `infrastructure/security/SecurityConfiguration.kt`。它定义多个 `SecurityFilterChain`：主链覆盖 `/api/**`、`/opds/**`、`/sse/**`、OAuth2 和 Actuator；Kobo 链覆盖 `/kobo/**`；KOReader/KOSync 链覆盖 `/koreader/**`。默认大多数 API 需要登录，`/api/v1/claim`、OAuth2 provider 列表、部分字体/资源、OPDS auth、KOReader 创建用户等被放行。权限角色来自 `UserRoles`，并启用了方法级 `@PreAuthorize`。

对外接口主要在 `interfaces`。`interfaces/api/rest` 是普通 Web UI/客户端使用的 JSON REST API，例如 `LibraryController`、`BookController`、`SeriesController`、`UserController`、`TaskController`。`interfaces/api/opds` 提供 OPDS v1/v2。`interfaces/api/kobo` 和 `interfaces/api/kosync` 分别适配 Kobo 与 KOReader 同步。`interfaces/sse/SseController.kt` 负责服务端事件推送。`interfaces/mvc/IndexController.kt` 返回前端入口模板 `index`。

领域层在 `domain`。`domain/model` 包含 `Library`、`Series`、`Book`、`ReadList`、`KomgaUser`、`ReadProgress`、`DomainEvent` 等核心对象；`domain/persistence` 是仓储接口；`domain/service` 是业务生命周期和处理服务，如 `LibraryLifecycle`、`BookLifecycle`、`SeriesLifecycle`、`FileSystemScanner`、`MetadataAggregator`。

持久化实现主要在 `infrastructure/jooq/main` 和 `infrastructure/jooq/tasks`。例如 `LibraryDao` 实现 `LibraryRepository`，通过 jOOQ 查询 `LIBRARY`、`USER_LIBRARY_SHARING`、`LIBRARY_EXCLUSIONS` 等表，并把数据库 record 转为领域对象 `Library`。

后台任务在 `application/tasks`。`TaskEmitter` 负责投递任务，`TaskProcessor` 监听 `TaskAddedEvent` 和 `ApplicationReadyEvent`，从 `TasksRepository` 取出任务交给 `TaskHandler` 处理，并按 `KomgaSettingsProvider.taskPoolSize` 调整线程池。扫描调度在 `application/scheduler/LibraryScanScheduler.kt`，根据 `Library.ScanInterval` 注册 fixed-rate 扫描任务。

资源目录还包含 `embeddedFonts/OpenDyslexic` 字体文件，供 EPUB/阅读器资源接口或前端阅读体验使用。

## 上下游关系

上游输入主要来自 HTTP 请求、启动事件、定时任务和配置文件。用户或客户端请求先进入 `interfaces` 下的 Controller，再经过 Spring Security 鉴权，随后调用 `domain/service` 或 `domain/persistence`。业务服务处理领域规则后，通过仓储接口读写数据；实际存储由 `infrastructure/jooq` 的 DAO 完成。

以下游看，主数据库和任务数据库是核心状态存储；Lucene 是搜索索引；本地文件系统是漫画、电子书、封面、字体和配置文件的来源；SSE 是向前端推送状态变化的通道；OPDS、Kobo、KOReader 是面向第三方阅读客户端的协议适配层。

一个典型链路是 `LibraryController.addLibrary()` 接收 `LibraryCreationDto`，转换为领域对象 `Library`，调用 `LibraryLifecycle.addLibrary()`。后者校验目录存在、名称不重复、路径不互相包含，然后通过 `LibraryRepository.insert()` 保存，再通过 `TaskEmitter.scanLibrary()` 投递扫描任务，并发布 `DomainEvent.LibraryAdded`。事件会被 `SseController` 监听并推送给已连接用户。

## 运行/调用流程

应用启动时，`Application.kt` 先做临时目录检查，随后 Spring Boot 扫描 `org.gotson.komga` 包下的组件。配置绑定到 `KomgaProperties`，数据源、jOOQ、Security、Lucene、Web、OpenAPI 等基础 Bean 被创建。Flyway 根据 `application.yml` 中的 `classpath:db/migration/{vendor}` 执行迁移；虽然迁移文件不在本次 `komga/src/main/resources` 直接列表中出现，根据当前片段推断，它们可能来自同模块其他资源生成目录、依赖资源或构建时产物，依据是配置明确启用了 Flyway 且指定了 classpath migration 位置。

请求进入后，Spring Security 按 URL 匹配不同 filter chain。普通 API 经过主链，Kobo 和 KOReader 分别走专用认证过滤器。Controller 通常只做参数接收、权限注解、DTO 转换和异常到 HTTP 状态码的映射，真正业务变化放在 `domain/service`。

后台任务流程是：业务代码或调度器调用 `TaskEmitter` 写入任务；`TaskProcessor` 在应用 ready 或收到 `TaskAddedEvent` 后检查队列；它按线程池大小从 `TasksRepository.takeFirst()` 取任务，交给 `TaskHandler.handleTask()`，完成后删除任务并继续拉取。定时扫描由 `LibraryScanScheduler.scheduleScan()` 将不同 `scanInterval` 转为 `Duration`，周期性投递扫描任务。

事件通知流程是：业务服务发布 `DomainEvent`；`SseController.handleSseEvent()` 将领域事件转换成前端事件名和 DTO，例如 `LibraryAdded`、`BookChanged`、`ReadProgressChanged`、`TaskQueueStatus`；再按管理员、用户 ID 等条件过滤连接并发送。

## 小白阅读顺序

1. 先看 `Application.kt`，理解这是一个启用定时任务的 Spring Boot 应用。
2. 再看 `resources/application.yml` 和 `KomgaProperties.kt`，建立“配置项如何进入代码”的概念。
3. 阅读 `SecurityConfiguration.kt`，搞清楚 `/api/**`、`/opds/**`、`/kobo/**`、`/koreader/**` 分别如何鉴权。
4. 从一个业务闭环入手，推荐 `interfaces/api/rest/LibraryController.kt`、`domain/service/LibraryLifecycle.kt`、`infrastructure/jooq/main/LibraryDao.kt` 连起来读。
5. 再看 `application/tasks/TaskProcessor.kt` 和 `application/scheduler/LibraryScanScheduler.kt`，理解扫描、分析、元数据刷新这类耗时任务为什么不是直接在请求线程里完成。
6. 最后扩展到 `domain/model`、`infrastructure/mediacontainer`、`infrastructure/metadata`、`infrastructure/search`，分别理解书籍模型、文件解析、元数据来源和搜索索引。

## 常见误区

不要把 `interfaces` 理解成“只有接口定义”。在这个项目里它是外部接口层，包含真实 Controller、DTO、SSE、MVC 和 runner。

不要以为 Controller 直接完成所有业务。以 `LibraryController` 为例，它主要负责 HTTP 映射、DTO 转换和错误码，路径合法性、重复名称、扫描任务触发、事件发布都在 `LibraryLifecycle` 等服务里。

不要把 `domain/persistence` 当成数据库实现。这里是仓储抽象；真正 SQL/jOOQ 实现在 `infrastructure/jooq/main` 和 `infrastructure/jooq/tasks`。

不要忽略任务数据库。Komga 不只使用一个 SQLite 主库，`application.yml` 同时配置了 `komga.database.file` 和 `komga.tasks-db.file`，任务队列有独立数据源和 DAO。

不要把 `application-dev.yml` 的端口和数据库当成生产默认值。默认端口来自 `application.yml` 的 `25600`，开发 profile 才使用 `8080` 和内存数据库。

不要认为所有事件都会广播给所有用户。`SseController` 对部分事件做了 `adminOnly` 或 `userIdOnly` 过滤，例如任务队列状态只推给管理员，阅读进度只推给对应用户。
