# 架构和模块边界

Komga 的架构可以从两个层面理解：仓库级别的三项目组织，以及后端主模块内部的分层。仓库级别由 `DEVELOPING.md` 明确说明：`komga` 是 Spring Boot backend server，托管 APIs，也在运行时服务前端静态资源；`komga-webui` 是 VueJS frontend，编译时构建；`komga-tray` 是显示 tray-icon 的轻量 desktop wrapper。根目录 `settings.gradle` 只把 `komga` 和 `komga-tray` 纳入 Gradle 多项目，前端由 `komga-webui/package.json` 管理，并通过后端 Gradle 任务构建。这种组织方式意味着“服务端业务”集中在 `komga`，“浏览器界面”集中在 `komga-webui`，“桌面启动体验”集中在 `komga-tray`。

## 后端主分层

`komga/src/main/kotlin/org/gotson/komga` 下的主要包是 `domain`、`application`、`infrastructure`、`interfaces`、`language`。根据目录名、类职责和 ArchUnit 规则，可以把它理解为一种偏 DDD 的分层结构。`domain` 放领域模型、仓储接口和领域服务；`application` 放应用级任务、调度器和事件配置；`infrastructure` 放数据库、搜索、图片、媒体容器、元数据解析、安全、Web 配置等技术实现；`interfaces` 放 HTTP/API/SSE/MVC/scheduler/app runner 等外部入口；`language` 提供语言工具。

这个判断有测试规则作为依据。`DomainDrivenDesignRulesTest.kt` 要求 `..domain..model..` 中的类不依赖 `..infrastructure..`、`..interfaces..`、`..domain.persistence..` 和 `..domain.service..`。它还要求名称包含 `Controller` 的类必须位于 `..interfaces..` 包。`SlicesIsolationRulesTest.kt` 要求 `..interfaces.(*)..` 这些 interface slices 之间不互相依赖。这些规则不是注释，而是测试，会约束后续开发。因此读架构时应把 `domain/model` 当成最内层，`interfaces` 当成外部适配入口，`infrastructure` 当成技术适配层。

## `domain`：业务名词和业务操作

`domain/model` 是系统名词表，包含 `Library`、`Series`、`Book`、`Media`、`BookMetadata`、`SeriesMetadata`、`ReadList`、`SeriesCollection`、`ReadProgress`、`KomgaUser`、`ApiKey`、`ThumbnailBook`、`PageHash`、`DomainEvent` 等。初学者应优先理解这些类型，而不是直接陷入 SQL 或控制器细节。`domain/persistence` 是仓储抽象，例如 `BookRepository`、`LibraryRepository`、`SeriesRepository`、`ReadProgressRepository`、`KomgaUserRepository`、`PageHashRepository`。它们定义领域层需要什么数据操作，但不直接暴露 SQLite 或 jOOQ。

`domain/service` 是核心业务流程所在地。`LibraryLifecycle` 管理 library 的新增、更新、删除，检查目录存在、目录类型、名称重复和路径包含关系，并在新增或配置变化时提交扫描、hash、转换等任务。`FileSystemScanner` 负责遍历文件系统，把目录和文件识别为 series、book 和 sidecar。`BookLifecycle`、`SeriesLifecycle`、`LibraryContentLifecycle`、`BookMetadataLifecycle`、`SeriesMetadataLifecycle`、`BookImporter`、`BookConverter`、`PageHashLifecycle`、`ReadListLifecycle` 等分别承载分析、导入、转换、删除、元数据、页面 hash、阅读列表等业务。这里的服务通常由控制器或任务处理器调用。

## `application`：任务和调度

`application/tasks` 是后台工作系统的中心。`Task` 定义可执行任务，`TaskEmitter` 把业务意图转换成任务，例如 `scanLibrary`、`analyzeBook`、`refreshBookMetadata`、`generateBookThumbnail`、`rebuildIndex`。`TasksRepository` 负责任务队列持久化抽象。`TaskProcessor` 在 `afterPropertiesSet()` 中重置未完成任务所有权，随后监听 `TaskAddedEvent` 和 `ApplicationReadyEvent`，按 `KomgaSettingsProvider.taskPoolSize` 创建的线程池取任务执行。`TaskHandler` 是分派器，根据 `Task` 子类型调用 `LibraryContentLifecycle`、`BookLifecycle`、`BookMetadataLifecycle`、`SearchIndexLifecycle`、`PageHashLifecycle` 等服务，并记录 Micrometer 指标。

`application/scheduler/LibraryScanScheduler.kt` 管理周期扫描。它持有 libraryId 到 `ScheduledTask` 的注册表，如果 library 的 `scanInterval` 不是 `DISABLED`，就按固定间隔提交 `taskEmitter.scanLibrary(library.id)`。`interfaces/scheduler/PeriodicScannerController.kt` 在 `ApplicationReadyEvent` 时读取所有 library：启用了 `scanOnStartup` 的立即提交扫描，所有 library 都根据配置注册周期扫描。根据这些文件可以确定，扫描入口既可以来自用户 REST 请求，也可以来自启动事件和周期调度。

## `infrastructure`：技术实现和适配

`infrastructure/datasource` 负责 SQLite 数据源和任务库迁移。`DataSourcesConfiguration.kt` 使用 Hikari 和 SQLite JDBC 创建主库/任务库读写数据源；`FlywaySecondaryMigrationInitializer.kt` 为任务库手工执行 Flyway 迁移。`infrastructure/jooq` 负责 jOOQ 查询实现，`main` 下是一批 DAO，`tasks` 下是任务队列数据库相关实现，顶层 helper 处理搜索条件、排序、临时表和 DSL 公共逻辑。`komga/src/flyway` 保存 schema 演进，说明数据库结构不是由 ORM 自动生成，而是由迁移脚本管理。

`infrastructure/mediacontainer` 处理媒体容器。文件名显示它支持 `divina` 压缩包提取、`epub` 结构解析和 `pdf` 提取，并有 `ContentDetector`、`TikaConfiguration`。`infrastructure/metadata` 下有 ComicRack、EPUB、Mylar、barcode ISBN、local artwork、oneshot 等 provider。`infrastructure/image` 处理图片分析、转换和 mosaic；`infrastructure/search` 使用 Lucene 管理索引、analyzer、commit 和重建；`infrastructure/security` 配置 REST/API key/OAuth2/Kobo/KOReader 的认证授权；`infrastructure/web` 配置 MVC、静态资源、缓存、request wrapper、argument resolver 和有效 server settings。

## `interfaces`：外部入口

`interfaces/api/rest` 是 Web UI 的主要 REST 入口，包含 library、series、book、read list、collection、settings、users、tasks、fonts、page hash、history、login、OAuth2、claim、sync point、transient books 等控制器。`LibraryController.kt` 是典型结构：认证主体来自 `@AuthenticationPrincipal KomgaPrincipal`，管理员动作通过 `@PreAuthorize("hasRole('ADMIN')")` 保护，DTO 转换后调用 `LibraryLifecycle` 或 `TaskEmitter`。`BookController.kt` 更复杂，除分页列表外还负责阅读资源、封面、进度、导入、元数据等一系列书籍相关 API。

`interfaces/api/opds` 提供 OPDS v1/v2，`interfaces/api/kobo` 提供 Kobo 同步，`interfaces/api/kosync` 提供 KOReader Sync。`interfaces/sse/SseController.kt` 通过 `SseEmitter` 推送 domain event 和任务队列状态。`interfaces/mvc/IndexController.kt` 返回前端 `index` 模板，把 `baseUrl` 交给前端。`interfaces/scheduler` 中的类虽然名字是 controller，但不是 HTTP controller，而是监听启动事件或定时行为的 Spring component；根据 ArchUnit 规则，它们仍归入 interfaces 包。

## 前端和后端的依赖方向

前端 `komga-webui` 通过 `axios` 调 REST API。`http.plugin.ts` 创建带 `baseURL: urls.origin`、`withCredentials: true`、`X-Requested-With` header 的 HTTP client，并把 ISO 日期字符串转换为 `Date`。各 `komga-*.service.ts` 封装具体端点，例如 `komga-libraries.service.ts` 调 `/api/v1/libraries`、`/api/v1/libraries/{id}/scan`、`/metadata/refresh`、`/empty-trash`。`main.ts` 把这些 service 通过 Vue plugin 注册给组件使用。前端依赖后端 API 的 DTO 类型定义在 `src/types`，但不会直接依赖 Kotlin 代码。

后端服务前端静态资源的边界在 `komga/build.gradle.kts` 与 `WebMvcConfiguration.kt`。构建时 `prepareThymeLeaf` 会把前端 `dist/index.html` 注入 Thymeleaf 标签并复制到 `komga/src/main/resources/public/`。运行时 `WebMvcConfiguration` 为 `/index.html`、favicon、manifest、`css`、`fonts`、`img`、`js` 配置资源处理。`IndexController` 用 Thymeleaf 返回首页。根据当前文件推断，生产运行时浏览器先拿到后端提供的 SPA，再由 SPA 继续访问同源 API。

## 扩展点

最直接的扩展点是新增 REST 功能：通常要在 `interfaces/api/rest` 加控制器或端点，在 `domain/service` 中放业务流程，在 `domain/persistence` 加仓储方法，并在 `infrastructure/jooq` 实现查询。新增长耗时操作时，应优先考虑增加 `Task`、`TaskEmitter` 方法和 `TaskHandler` 分支，保持 HTTP 请求快速返回。新增媒体格式或元数据来源时，应查看 `infrastructure/mediacontainer`、`infrastructure/metadata` 中现有 provider/extractor 模式，并补充对应测试。新增前端页面时，应从 `router.ts`、`src/views`、`src/services`、`src/plugins` 和 `src/types` 同步扩展，确保服务调用和状态管理路径一致。

需要谨慎的边界是接口 slice 之间的依赖。ArchUnit 规则要求 `interfaces.(*)` 不互相依赖，说明 REST、OPDS、Kobo、SSE、scheduler 等入口不应直接互相调用。共享能力应下沉到 domain 或 infrastructure。另一个边界是 `domain/model` 的纯净性，不能为了方便把数据库、HTTP 或 Spring 细节放进模型层。
