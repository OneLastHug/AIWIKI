# 运行时流程

本文把 Komga 的启动、配置加载、HTTP 请求、后台任务、扫描和前端数据流串起来。除非特别说明，内容依据 `Application.kt`、`application.yml`、`DEVELOPING.md`、`SecurityConfiguration.kt`、`DataSourcesConfiguration.kt`、`TaskProcessor.kt`、`TaskHandler.kt`、`LibraryController.kt`、`SseController.kt`、前端入口和构建配置。部分跨类调用未完整展开时，会标注“根据当前文件推断”。

## 启动主线

服务端入口是 `komga/src/main/kotlin/org/gotson/komga/Application.kt`。`main(args)` 首先调用 `checkTempDirectory()`，然后设置 `org.jooq.no-logo` 和 `org.jooq.no-tips` 系统属性，最后执行 `runApplication<Application>(*args)`。`Application` 类上有 `@SpringBootApplication` 和 `@EnableScheduling`，所以启动时 Spring Boot 会扫描 Bean、创建 Web 容器、加载配置、启用调度任务。默认端口在 `application.yml` 中是 `25600`；`application-dev.yml` 在 dev profile 下把端口改为 `8080`。开发文档建议后端常用 `SPRING_PROFILES_ACTIVE=dev` 或 `./gradlew bootRun --args='--spring.profiles.active=dev'`。

桌面托盘入口是 `komga-tray/src/main/kotlin/org/gotson/komga/DesktopApplication.kt`。它定义 `DesktopApplication : Application()` 并使用 `SpringApplicationBuilder(DesktopApplication::class.java).headless(false).run(*args)` 启动同一个后端应用。它设置 `apple.awt.UIElement`，并捕获启动异常：如果原因是 `PortInUseException`，显示端口占用错误；其他异常显示通用错误和堆栈。`TrayIconRunner.kt` 在非 test profile 下作为 `ApplicationRunner` 异步运行 Compose Desktop tray，菜单会打开本地 Komga URL、日志文件、配置目录或退出应用。根据这些文件可以确定，托盘版的运行流是“先启动 Spring Boot，再显示系统托盘”，而不是单独运行一套服务。

## 配置加载和外部配置

默认配置在 `komga/src/main/resources/application.yml`。关键配置包括：`komga.config-dir` 默认为 `${user.home}/.komga`，主数据库是 `${komga.config-dir}/database.sqlite`，任务数据库是 `${komga.config-dir}/tasks.sqlite`，Lucene 数据目录是 `${komga.config-dir}/lucene`，字体目录是 `${komga.config-dir}/fonts`，日志写入 `${komga.config-dir}/logs/komga.log`。Spring 还通过 `spring.config.import` 导入 `optional:file:${komga.config-dir}/application.yml`、`.yaml`、`.properties`，所以运行环境可以通过配置目录覆盖默认值。

`KomgaProperties.kt` 使用 `@ConfigurationProperties(prefix = "komga")` 绑定 `komga.*` 配置，并在 `@PostConstruct` 中尝试创建数据库文件和任务数据库文件所在目录。它包含 page hashing、EPUB Divina 阈值、OAuth2 账号创建、OIDC email 验证、数据库、任务数据库、CORS、Lucene、Kobo、fonts 等配置对象。`KomgaSettingsProvider.kt` 则从 `ServerSettingsDao` 读取运行时可变设置，如删除空 collection/read list、remember-me key、remember-me 时长、缩略图大小、任务线程池大小、server port、context path、Kobo proxy、Kobo port、kepubify path。`WebServerConfiguration.kt` 会读取 `settingsProvider.serverPort` 和 `serverContextPath` 动态定制 Web server。也就是说，Komga 同时有“配置文件中的 komga properties”和“数据库中的 server settings”两类配置来源。

## 数据库和迁移流程

Spring 启动后会创建数据源。`DataSourcesConfiguration.kt` 根据 `KomgaProperties.database` 创建主库读写池 `sqliteDataSourceRW`，根据 WAL 和内存库判断是否创建独立只读池 `sqliteDataSourceRO`；任务数据库同理创建 `tasksDataSourceRW` 和 `tasksDataSourceRO`。主数据库使用 `SqliteUdfDataSource`，任务库使用 `SQLiteDataSource`。如果数据库文件是内存模式，pool size 固定为 1；如果启用 WAL，读写可能分离，写池仍限制为 1。

主库 Flyway 迁移由 Spring Boot 对 primary datasource 执行，迁移位置在 `application.yml` 中是 `classpath:db/migration/{vendor}`。任务库不是 primary datasource，所以 `FlywaySecondaryMigrationInitializer.kt` 实现 `InitializingBean`，启动时手工配置 `Flyway.locations("classpath:tasks/migration/sqlite")` 并调用 `migrate()`。仓库中 `komga/src/flyway/resources/db/migration/sqlite` 有大量主库 SQL 迁移，`komga/src/flyway/kotlin/db/migration/sqlite` 有 Kotlin 迁移，`komga/src/flyway/resources/tasks/migration/sqlite/V20231013114850__tasks.sql` 是任务库迁移。根据这些文件可以判断，启动早期需要完成数据库 schema 准备，后续 repository/DAO 才能正常读写。

## HTTP 请求和安全过滤

`SecurityConfiguration.kt` 是请求进入业务前的重要关口。普通 API 链匹配 `/api/**`、`/opds/**`、`/sse/**`、OAuth2 路径和 actuator endpoint。它允许匿名访问 health、claim、OAuth2 provider、部分 client settings、字体资源、OPDS auth、KOReader 用户创建等端点；其他 `/api/**`、`/opds/**`、`/sse/**` 需要认证。actuator 除 health 外要求 ADMIN。该链启用 CORS、禁用 CSRF、使用 HTTP Basic、session、remember-me、OAuth2 login、API key filter，并为 OPDS v2 设置特定 authentication entry point。另有 `/kobo/**` 链和 `/koreader/**` 链，分别通过 API key converter 和特定角色保护。

典型 REST 请求可以看 `LibraryController.kt`。`GET /api/v1/libraries` 根据当前 `KomgaPrincipal` 判断用户能否访问所有 library，否则只查共享 library，然后映射为 DTO。`POST /api/v1/libraries` 需要 ADMIN，接收 `LibraryCreationDto`，转换成 `Library`，调用 `LibraryLifecycle.addLibrary()`。`PATCH /api/v1/libraries/{libraryId}` 查出已有 library，按传入字段构造更新对象，再调用 `LibraryLifecycle.updateLibrary()`。`POST /api/v1/libraries/{libraryId}/scan` 需要 ADMIN，查到 library 后调用 `taskEmitter.scanLibrary(library.id, deep, HIGHEST_PRIORITY)`，返回 `202 ACCEPTED`。这说明控制器倾向于做边界校验、DTO 转换和任务提交，耗时业务交给领域服务或任务系统。

## 后台任务执行流

任务从 `TaskEmitter` 进入队列。`TaskEmitter.scanLibrary()` 会创建 `Task.ScanLibrary` 并提交；其他方法会提交分析、hash、转换、生成缩略图、刷新元数据、导入、重建索引、删除等任务。`TaskProcessor` 持有 `ThreadPoolTaskExecutor`，线程池核心大小来自 `KomgaSettingsProvider.taskPoolSize`。初始化时它调用 `tasksRepository.disown()` 重置未完成任务，然后允许处理任务。它监听 `TaskAddedEvent` 和 `ApplicationReadyEvent`，如果单线程就执行一次 `takeAndProcess()`，如果多线程则在有可用任务且活跃线程未满时循环提交。

`takeAndProcess()` 从 `tasksRepository.takeFirst()` 获取第一个可用任务，交给 `TaskHandler.handleTask(task)`，处理完成后从队列删除，然后递归触发下一轮处理。`TaskHandler` 是后台业务调度的关键调用链。例如处理 `Task.ScanLibrary` 时，它查 library，调用 `libraryContentLifecycle.scanRootFolder(library, task.scanDeep)`，然后继续用 `TaskEmitter` 提交分析未知和过期书籍、修复扩展名、转换 CBZ、查缺失页面 hash、查重复页面、文件 hash、KOReader hash 等后续任务。处理 `Task.AnalyzeBook` 时调用 `bookLifecycle.analyzeAndPersist(book)`，根据返回的 `BookAction` 再提交生成缩略图或刷新元数据任务。处理 `Task.RefreshBookMetadata` 后会提交 series metadata 刷新，处理 `Task.RefreshSeriesMetadata` 后会提交聚合。任务失败会记录错误并增加 Micrometer failure counter。

## Library 扫描和媒体识别

创建或更新 library 时，扫描任务通常由 `LibraryLifecycle` 触发。`addLibrary()` 会先验证 root 存在、是目录、名称不重复、路径不和已有 library 互相包含；插入 repository 后调用 `taskEmitter.scanLibrary(library.id)` 并发布 `DomainEvent.LibraryAdded`。`updateLibrary()` 在配置变化时可能重新安排扫描调度，某些字段变化会触发重新扫描；开启 hash、page hash、repair extensions、convert to cbz 等选项时也会提交相应任务。

实际文件系统遍历在 `FileSystemScanner.scanRootFolder()`。它根据 library 配置决定扫描扩展名：CBX 包括 `cbz`、`zip`、`cbr`、`rar`，另有 `pdf` 和 `epub`。它用 `Files.walkFileTree` 递归遍历 root，跳过点号目录和匹配排除规则的目录。访问目录时记录潜在 `Series`；访问文件时，如果扩展名匹配则构造 `Book`，同时用 sidecar consumers 识别 series sidecar 和 book sidecar 候选。目录访问结束时，如果该目录有 books，就把它变成 scanned series；如果目录属于 oneshots 配置，则每本书成为 oneshot series。最后返回 `ScanResult(scannedSeries, scannedSidecars)`。根据当前文件推断，`LibraryContentLifecycle.scanRootFolder()` 会把这个扫描结果与数据库中已有 series/book/media 做增删改同步。

## 前端加载和请求流

生产构建时，`komga/build.gradle.kts` 的 `npmBuild` 会在 `komga-webui` 执行 `npm run build`，`copyWebDist` 把 `dist` 复制到 `komga/src/main/resources/public/`，`prepareThymeLeaf` 修改 `index.html` 中的资源路径并注入 Thymeleaf 属性。运行时 `WebMvcConfiguration.kt` 提供 `/index.html`、favicon、manifest 和 `css/fonts/img/js` 静态资源；`IndexController.kt` 响应 `/`，把 `baseUrl` 放入 model 并返回 `index`。根据当前文件推断，浏览器访问根路径后获得 Vue SPA，再由前端路由接管页面导航。

前端入口 `komga-webui/src/main.ts` 注册 `httpPlugin`、logger、settings、filesystem、series、collections、readlists、books、referential、claim、users、libraries、sse、tasks、sync points、OAuth2、login、page hashes、metrics、history、announcements、releases、fonts 等插件，并挂载 Vue Router、Vuex、Vuetify、i18n。`http.plugin.ts` 创建 Axios client，使用同源 base URL、携带 cookie，并把响应中的 ISO 日期字符串递归转为 `Date`。`router.ts` 定义 dashboard、settings、libraries、series、book、readlists、collections、search、import、reader 等页面，并用 guard 控制 admin 页面和无 library 状态。服务类如 `komga-libraries.service.ts` 把页面操作转换成 `/api/v1/libraries`、`/{id}/scan`、`/{id}/metadata/refresh` 等请求。

## 事件和 SSE 流

领域服务会发布 `DomainEvent`，例如 `LibraryLifecycle.addLibrary()` 发布 `DomainEvent.LibraryAdded`。`SseController.kt` 监听所有 `DomainEvent`，按类型向已连接的 `SseEmitter` 发送事件：library、series、book、read list、collection、read progress、thumbnail、user/session 等都有对应事件名。它还每 15 秒发送 heartbeat，每 10 秒给管理员发送任务队列统计 `TaskQueueStatus`。连接端点是 `sse/v1/events`，认证主体用于把 emitter 和 `KomgaUser` 关联，以便 admin only 或 userId only 过滤。前端 `komga-sse.plugin.ts` 注册 `komgaSse` Vuex 模块，保存 `taskCount` 和 `taskCountByType`。根据这些文件可以确定，后台任务和实体变化通过 Spring event 到 SSE，再进入前端状态。

## 启动后的自动任务

`PeriodicScannerController.kt` 监听 `ApplicationReadyEvent`。启动完成后，它先查所有 library，过滤 `scanOnStartup` 为 true 的 library 并调用 `taskEmitter.scanLibrary(it.id)`；另一个监听方法对所有 library 调用 `libraryScanScheduler.scheduleScan(it)`。`LibraryScanScheduler.kt` 根据 `Library.ScanInterval` 把 HOURLY、EVERY_6H、EVERY_12H、DAILY、WEEKLY 转为固定间隔；`DISABLED` 不安排任务。这个流程说明，即使没有用户手工点击扫描，Komga 也可能在启动后或定时器触发时产生扫描任务。
