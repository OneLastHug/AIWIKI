# 项目整体介绍

Komga 是一个面向漫画、manga、BD、杂志和电子书的媒体服务器。这个结论直接来自 `README.md` 的项目说明：“Komga is a media server for your comics, mangas, BDs, magazines and eBooks.” 仓库中的功能列表进一步说明它不是单纯的文件浏览器，而是一个带 Web UI、多用户权限、元数据、阅读进度、阅读器、对外协议和后台媒体处理能力的个人媒体管理系统。

## 它解决什么问题

从 README 功能和源码结构看，Komga 主要解决“把本地书籍文件组织成可浏览、可阅读、可同步的服务”的问题。用户把文件夹配置成 library，系统扫描文件系统，把目录和文件识别为 `Series`、`Book`、`Media` 等领域对象，然后通过 Web UI、REST API、OPDS、Kobo Sync、KOReader Sync 等入口提供访问。它还会处理许多媒体库长期运行时会遇到的细节：导入嵌入元数据、编辑 series/book 元数据、生成缩略图、检测重复文件和重复页面、记录阅读进度、管理多用户访问范围、根据年龄和标签限制内容、下载文件或合集、导入外部书籍、导入 ComicRack `cbl` 阅读列表。

项目的核心对象可以从 `komga/src/main/kotlin/org/gotson/komga/domain/model` 直接看到：`Library` 表示库，`Series` 表示系列或目录层级中的作品集合，`Book` 表示单本书籍文件，`Media` 表示文件分析后的媒体信息，`BookMetadata` 和 `SeriesMetadata` 表示可编辑或导入的元数据，`ReadList` 和 `SeriesCollection` 表示组织方式，`ReadProgress` 表示用户阅读状态，`KomgaUser` 和 `UserRoles` 表示账号与权限，`ThumbnailBook`、`ThumbnailSeries` 等表示封面和缩略图。初学者读源码时，可以先把这些模型看成系统的名词表。

## 仓库由哪几部分组成

`DEVELOPING.md` 明确说 Komga 由 3 个项目组成：`komga` 是 Spring Boot 后端服务器，托管 API，并在运行时提供前端静态资源；`komga-webui` 是 VueJS 前端，在编译时构建并由后端服务；`komga-tray` 是一个显示 tray-icon 的轻量桌面包装层。这个说明和构建文件互相印证：根目录 `settings.gradle` 只 `include 'komga'` 与 `include 'komga-tray'`，说明 Gradle 直接管理后端与托盘模块；`komga-webui/package.json` 则说明前端是 npm/Vue CLI 项目；`komga/build.gradle.kts` 中的 `npmInstall`、`npmBuild`、`copyWebDist`、`prepareThymeLeaf` 任务把前端构建产物复制进 `komga/src/main/resources/public/`，再由后端运行时提供。

后端 `komga` 是最大模块。入口文件 `Application.kt` 使用 `@SpringBootApplication` 和 `@EnableScheduling`，启动前调用 `checkTempDirectory()`，设置 jOOQ 的系统属性，再执行 `runApplication<Application>(*args)`。这意味着多数运行逻辑由 Spring 扫描 Bean、装配配置、启动 Web 容器和调度器完成。后端源码按包分为 `domain`、`application`、`infrastructure`、`interfaces`、`language`。测试目录 `komga/src/test/kotlin/org/gotson/komga/architecture` 中的 ArchUnit 规则要求 domain model 不依赖 infrastructure、interfaces、domain persistence 和 domain service，并要求名字含 `Controller` 的类位于 `interfaces` 包。这是理解分层的强证据。

前端 `komga-webui` 是 Vue 2 应用。`package.json` 使用 `vue` 2.6、`vue-router` 3、`vuex` 3、`vuetify` 2、`axios`、`vue-i18n`、`vuelidate` 等依赖。`src/main.ts` 注册大量 Komga 插件，如 `komga-books`、`komga-libraries`、`komga-series`、`komga-sse`、`komga-tasks`、`komga-users`，然后挂载 `App.vue`。`src/router.ts` 定义 dashboard、settings、libraries、series、book、readlists、collections、reader、search、import 等页面。`src/services` 中的服务类把界面操作转换成 `/api/v1/...` HTTP 请求，`komga-libraries.service.ts` 是很典型的例子。

托盘模块 `komga-tray` 依赖 `project(":komga")`，`build.gradle.kts` 设置 `mainClass = "org.gotson.komga.DesktopApplicationKt"`，并使用 JetBrains Compose Desktop 与 Conveyor。`DesktopApplication.kt` 继承后端 `Application`，用 `SpringApplicationBuilder` 非 headless 启动，设置 macOS UI 和 jOOQ 属性；如果端口占用或启动异常，会调用 `showErrorDialog`。`TrayIconRunner.kt` 则在非 test profile 下作为 `ApplicationRunner` 异步启动系统托盘，菜单项包括打开 Komga、显示日志、显示配置目录和退出。根据这些文件可以判断，托盘层不是另一套业务逻辑，而是桌面启动和系统托盘体验的包装。

## 核心能力如何落在源码里

浏览库、系列和书籍的 REST API 主要在 `interfaces/api/rest`，例如 `LibraryController.kt`、`SeriesController.kt`、`BookController.kt`、`ReadListController.kt`、`SeriesCollectionController.kt`。这些控制器负责 HTTP 映射、认证主体、DTO 转换、分页参数和错误状态。真正的业务变化通常交给 `domain/service` 下的生命周期类，例如 `LibraryLifecycle`、`LibraryContentLifecycle`、`BookLifecycle`、`SeriesLifecycle`、`BookMetadataLifecycle`、`SeriesMetadataLifecycle`。持久化通过 `domain/persistence` 中的接口表达，再由 `infrastructure/jooq/main` 下的 DAO 实现。

媒体扫描和处理是项目的中心路径。`LibraryLifecycle.addLibrary()` 在验证目录存在、目录可读、名称不重复、路径不互相包含后插入库，并调用 `TaskEmitter.scanLibrary()` 提交扫描任务。`FileSystemScanner.scanRootFolder()` 使用 `Files.walkFileTree` 遍历目录，按配置支持 `cbz`、`zip`、`cbr`、`rar`、`pdf`、`epub`，并识别 sidecar 文件。`TaskHandler` 处理 `Task.ScanLibrary` 时调用 `LibraryContentLifecycle.scanRootFolder()`，随后继续提交分析未知或过期书籍、修复扩展名、转换 CBZ、补页面 hash、查找重复页面、文件 hash、KOReader hash 等任务。这个链路说明 Komga 把耗时工作放入任务队列，而不是直接阻塞用户请求。

实时反馈通过 SSE 提供。`SseController.kt` 暴露 `sse/v1/events`，保存每个 `SseEmitter` 与用户的对应关系，并监听 `DomainEvent`。当 library、series、book、read list、collection、read progress、thumbnail、user 等事件发生时，它按事件类型发送不同名称的 SSE 消息；另外定时发送 heartbeat 和任务队列状态。前端的 `komga-sse.plugin.ts` 注册 `komgaSse` Vuex 模块，保存任务数量和按类型统计。根据这些文件可以确定，后台任务状态和实体变化会通过事件流反馈到 Web UI。

## 初学者切入点

如果你刚开始阅读，不建议从所有控制器或所有 DAO 同时展开。更有效的路线是：先读 `README.md` 和 `DEVELOPING.md`，确认产品目标和本地开发方式；再读 `Application.kt`、`application.yml`、`KomgaProperties.kt`，理解启动、配置目录、SQLite 文件、Lucene 目录和默认端口；然后选一条业务主线，例如“创建 library 并扫描文件”。这条线可以从 `LibraryController.addLibrary()` 进入 `LibraryLifecycle.addLibrary()`，再到 `TaskEmitter.scanLibrary()`、`TaskProcessor.processAvailableTask()`、`TaskHandler.handleTask()`、`LibraryContentLifecycle.scanRootFolder()` 和 `FileSystemScanner.scanRootFolder()`。

第二条适合前端读者的路线是从 `komga-webui/src/main.ts` 开始，看插件如何把服务挂到 Vue 原型上，再读 `router.ts` 中的页面结构，最后进入 `services/komga-libraries.service.ts` 或 `services/komga-books.service.ts`，把页面操作和后端 REST API 对上。第三条适合数据库和后端读者的路线是读 `komga/src/flyway/resources/db/migration/sqlite/V20200706141854__initial_migration.sql`、`DataSourcesConfiguration.kt`、`FlywaySecondaryMigrationInitializer.kt` 和 `infrastructure/jooq/main/*Dao.kt`，理解 schema、迁移和查询实现。

需要注意的是，项目同时服务 Web UI、OPDS、Kobo 和 KOReader，不同接口包之间有隔离要求。`SlicesIsolationRulesTest.kt` 中的规则要求 `interfaces.(*)` 不互相依赖。也就是说，读 REST 控制器时不要自然假设它直接复用 OPDS 或 Kobo 控制器；更常见的复用点应该在 domain service、persistence、infrastructure helper 或通用 generator 上。
