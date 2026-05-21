# 目录：komga/src/main/kotlin/org

## 它负责什么

`komga/src/main/kotlin/org` 是 Komga 后端 Kotlin 源码的 JVM 包根目录。它下面实际只有一条业务包路径：`org/gotson/komga`，对应 Kotlin 包名 `org.gotson.komga`。从当前片段看，这里承载的是 Komga 服务端的核心应用：启动 Spring Boot 应用、暴露 REST/OPDS/Kobo/KOReader 等接口、管理书库与书籍生命周期、处理扫描和分析任务、读写数据库、做认证授权、解析媒体文件、生成封面与索引。

入口文件是 `komga/src/main/kotlin/org/gotson/komga/Application.kt`。它使用 `@SpringBootApplication` 启动 Spring 容器，用 `@EnableScheduling` 开启定时任务；`main` 函数启动前会调用 `checkTempDirectory()` 检查临时目录，并设置 jOOQ 的系统属性，然后执行 `runApplication<Application>(*args)`。因此这个目录不是普通工具包，而是整个后端应用的主包根。

整体结构接近分层架构：

- `application`：应用层事件、调度和异步任务队列。
- `domain`：核心领域模型、仓储接口、领域服务。
- `infrastructure`：数据库、Web、安全、搜索、文件解析、图片处理等技术实现。
- `interfaces`：对外入口，包括 REST API、MVC、SSE、调度控制器和命令行 runner。
- `language`：Kotlin 语言层面的扩展工具。

## 关键组成

`komga/src/main/kotlin/org/gotson/komga/Application.kt` 是服务端启动点。它本身很薄，真正的功能通过 Spring 扫描 `org.gotson.komga` 包下的 `@Service`、`@Configuration`、`@RestController` 等组件组装起来。

`application` 负责应用级任务编排。`application/tasks/TaskEmitter.kt` 是任务入口，提供 `scanLibrary`、`analyzeBook`、`refreshBookMetadata`、`rebuildIndex`、`convertBookToCbz` 等方法，把用户操作或系统事件转换成 `Task` 并提交到 `TasksRepository`。`application/tasks/TaskProcessor.kt` 负责消费任务：应用启动后先 `disown()` 重置未完成任务，再根据 `KomgaSettingsProvider.taskPoolSize` 创建线程池，监听 `TaskAddedEvent` 和 `ApplicationReadyEvent`，从任务库 `takeFirst()` 取任务交给 `TaskHandler` 执行，完成后删除队列记录。这个层次把“请求来了”与“耗时工作真正执行”解耦。

`domain/model` 是业务对象集合，例如 `Library`、`Series`、`Book`、`Media`、`ReadList`、`ReadProgress`、`KomgaUser`、`ApiKey`、`DomainEvent` 等。这里定义 Komga 关心的概念，而不是 HTTP 或数据库细节。`domain/persistence` 定义仓储接口，例如 `BookRepository`、`LibraryRepository`、`SeriesRepository`、`MediaRepository`、`ReadProgressRepository` 等。`domain/service` 是业务规则实现区域，例如 `LibraryLifecycle`、`LibraryContentLifecycle`、`BookLifecycle`、`SeriesLifecycle`、`BookAnalyzer`、`MetadataAggregator`、`MetadataApplier`。

`domain/service/LibraryContentLifecycle.kt` 是理解扫描流程的代表文件。它的 `scanRootFolder` 会调用 `FileSystemScanner` 扫描书库目录；当目录不存在时标记 `Library.unavailableDate` 并发布 `DomainEvent.LibraryUpdated`。扫描成功后，它会对比磁盘结果和数据库状态：软删除不存在的 series/book，新增新 series/book，检测文件时间和 hash 变化，必要时把 `Media.status` 标成 `OUTDATED`。它还会处理 sidecar 文件，触发本地封面或元数据刷新任务，并在扫描结束后按设置清空回收站或清理空集合/书单，最后发布 `DomainEvent.LibraryScanned`。

`infrastructure` 是技术适配层。`infrastructure/configuration/KomgaProperties.kt` 定义 `komga.*` 配置项，例如数据库文件、任务数据库、CORS、Lucene 索引目录、Kobo 同步限制、字体目录等，并在初始化后尝试创建数据库目录。`infrastructure/security/SecurityConfiguration.kt` 定义多条 Spring Security filter chain：主链覆盖 `/api/**`、`/opds/**`、`/sse/**`、OAuth2 路径和 actuator；另有 `/kobo/**` 和 `/koreader/**` 专用认证链。API key 认证通过 `ApiKeyAuthenticationFilter` 接入，REST 默认使用 `X-API-Key`，Kobo 从 URL 提取 token，KOReader 使用 `X-Auth-User` 请求头。

`infrastructure/jooq/main` 是数据库访问实现区，文件名如 `BookDao.kt`、`SeriesDao.kt`、`LibraryDao.kt`、`ReadListDao.kt`、`KomgaUserDao.kt`。根据当前目录和命名推断，这些 DAO 实现了 `domain/persistence` 中的仓储接口，并用 jOOQ 访问主数据库。`infrastructure/search` 负责 Lucene 搜索索引；`infrastructure/mediacontainer`、`metadata`、`image`、`hash` 分别处理媒体容器识别、元数据读取、图片分析转换和 hash 计算。

`interfaces` 是外部交互层。`interfaces/api/rest` 中有大量 `*Controller.kt`，例如 `LibraryController.kt`、`BookController.kt`、`SeriesController.kt`、`ReadListController.kt`、`UserController.kt`、`TaskController.kt`。`LibraryController.kt` 暴露 `/api/v1/libraries`，支持列出、创建、更新、删除书库，并通过 `TaskEmitter` 提交扫描、分析、刷新元数据等后台任务。`interfaces/api/opds`、`interfaces/api/kobo`、`interfaces/api/kosync` 对应不同客户端协议；`interfaces/sse` 用于服务端事件推送；`interfaces/mvc` 处理 Web UI 首页和资源未找到场景；`interfaces/scheduler` 放置定时/启动类控制器。

## 上下游关系

上游入口主要有四类：

1. Web/API 请求进入 `interfaces/api/rest`、`interfaces/api/opds`、`interfaces/api/kobo`、`interfaces/api/kosync`。
2. 浏览器页面或静态资源相关请求进入 `interfaces/mvc`。
3. 应用启动、定时任务、设置变化等内部事件进入 `application` 和 `interfaces/scheduler`。
4. 命令行参数或应用 runner 进入 `interfaces/apprunner`，例如用户列表、密码重置等运维动作。

中间层由 `domain/service` 承接业务动作。Controller 通常不会直接写复杂业务逻辑，而是调用 `LibraryLifecycle`、`BookLifecycle`、`SeriesLifecycle`、`TaskEmitter` 或各类 repository。比如 `LibraryController.addLibrary` 把 `LibraryCreationDto` 转成 `Library` 领域对象，再调用 `libraryLifecycle.addLibrary`；`libraryScan` 不直接扫描文件系统，而是调用 `taskEmitter.scanLibrary` 提交后台任务。

下游依赖集中在 `infrastructure`：

- 持久化下游：`infrastructure/jooq/main` 和 `infrastructure/jooq/tasks` 访问主库和任务库。
- 搜索下游：`infrastructure/search` 维护 Lucene 索引。
- 文件系统下游：`domain/service/FileSystemScanner` 与媒体容器、图片、hash、metadata 组件协作。
- Web 下游：`infrastructure/web` 配置 MVC、过滤器、参数解析、ETag、请求日志等。
- 安全下游：`infrastructure/security` 处理 session、basic auth、remember-me、OAuth2、API key、角色授权。
- 外部客户端适配：`infrastructure/kobo`、`interfaces/api/kobo` 面向 Kobo；`interfaces/api/kosync` 面向 KOReader/KOSync。

根据当前片段推断，依赖方向大体是：`interfaces` 调用 `application` 或 `domain`，`domain` 依赖仓储抽象和少量技术服务，`infrastructure` 实现仓储和框架配置，Spring 容器负责注入。需要注意，Komga 并不是严格的“纯领域层不碰任何基础设施”的六边形架构，`domain/service/LibraryContentLifecycle.kt` 中也注入了 `KomgaSettingsProvider`、`Hasher`、`TaskEmitter`、`ApplicationEventPublisher`、`TransactionTemplate` 等组件，说明这里更偏实用型分层。

## 运行/调用流程

启动流程从 `Application.kt` 开始。应用先检查临时目录，关闭 jOOQ logo/tips，然后启动 Spring Boot。Spring 扫描 `org.gotson.komga` 下的配置、服务、控制器和仓储实现。`KomgaProperties` 绑定 `komga.*` 配置并创建数据库目录；`SecurityConfiguration` 建立安全过滤链；任务处理器 `TaskProcessor` 初始化时重置未完成任务，应用 ready 后开始消费任务。

以“用户点击扫描书库”为例，调用链大致如下：

1. 前端或客户端请求 `POST /api/v1/libraries/{libraryId}/scan`。
2. `interfaces/api/rest/LibraryController.kt` 中的 `libraryScan` 检查书库是否存在。
3. Controller 调用 `TaskEmitter.scanLibrary(library.id, deep, HIGHEST_PRIORITY)`。
4. `TaskEmitter` 创建 `Task.ScanLibrary` 并保存到 `TasksRepository`，同时发布任务新增事件。
5. `TaskProcessor` 监听到 `TaskAddedEvent`，从任务库取出可用任务。
6. `TaskHandler` 执行具体任务。根据当前片段推断，扫描任务最终会调用 `LibraryContentLifecycle.scanRootFolder`。
7. `scanRootFolder` 调用 `FileSystemScanner` 读取磁盘，和 `SeriesRepository`、`BookRepository`、`MediaRepository` 等数据库状态比对。
8. 它新增、更新或软删除 series/book，必要时提交 `refreshSeriesMetadata`、`refreshBookMetadata`、`refreshBookLocalArtwork` 等后续任务。
9. 扫描结束发布 `DomainEvent.LibraryScanned`，供其他监听器或 SSE/索引刷新等机制继续反应。

以普通 REST 查询为例，流程更短：请求先经过 `SecurityConfiguration` 的认证和授权，进入对应 `*Controller`，Controller 读取 `KomgaPrincipal` 判断用户权限，再调用 repository 查询并通过 `dto.toDto()` 转成响应对象。比如 `LibraryController.getLibraries` 会根据用户是否能访问全部书库，选择 `libraryRepository.findAll()` 或 `findAllByIds(principal.user.sharedLibrariesIds)`，并且只有管理员返回 root 路径信息。

## 小白阅读顺序

建议先读 `komga/src/main/kotlin/org/gotson/komga/Application.kt`，确认这是 Spring Boot 后端入口，理解自动扫描和调度启用的位置。

第二步读 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/LibraryController.kt`。它是最容易理解的业务入口：路径清楚、HTTP 方法清楚、能看到 DTO 转领域对象、权限注解、异常到 HTTP 状态码的转换，以及如何把耗时操作交给 `TaskEmitter`。

第三步读 `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskEmitter.kt` 和 `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskProcessor.kt`。理解 Komga 为什么大量操作不是同步完成，而是进入任务队列。看懂这两个文件后，再看扫描、分析、缩略图、元数据刷新会容易很多。

第四步读 `komga/src/main/kotlin/org/gotson/komga/domain/model/Library.kt`、`Book.kt`、`Series.kt`、`Media.kt` 等核心模型。先理解“书库-系列-书籍-媒体文件”的关系，再看其他 ReadList、ReadProgress、Thumbnail、Metadata。

第五步读 `komga/src/main/kotlin/org/gotson/komga/domain/service/LibraryContentLifecycle.kt`。这是书库扫描的主干逻辑，包含文件系统扫描、数据库对比、软删除、恢复已删除项目、sidecar 处理、清空回收站、发布领域事件等关键概念。

第六步再进入 `infrastructure`。先看 `infrastructure/configuration/KomgaProperties.kt` 理解配置项，再看 `infrastructure/security/SecurityConfiguration.kt` 理解哪些接口开放、哪些需要认证、Kobo/KOReader 为什么有独立认证链。最后按需求看 `infrastructure/jooq/main` 中对应 DAO、`infrastructure/search` 中 Lucene、`infrastructure/metadata` 中元数据提供者。

## 常见误区

不要把 `komga/src/main/kotlin/org` 理解成一个功能模块。它只是 JVM 包根，真正的业务包是 `org.gotson.komga`，下面才按应用层、领域层、基础设施层、接口层划分。

不要以为 Controller 里完成了所有业务。以 `LibraryController` 为例，它主要做 HTTP 参数、权限、DTO 转换和任务提交；真正的扫描、删除、恢复、元数据刷新在 `domain/service` 和 `application/tasks` 中完成。

不要把扫描书库理解成一次同步请求。`POST /api/v1/libraries/{libraryId}/scan` 返回 `202 ACCEPTED`，表示任务被接受；后续由 `TaskProcessor` 在线程池中异步处理。查看扫描效果时应关注任务队列、事件、数据库状态，而不是只看 Controller 返回值。

不要把 `domain/persistence` 当成数据库实现。这里更像仓储抽象；具体 jOOQ DAO 在 `infrastructure/jooq/main` 等目录中。读数据库逻辑时需要从 repository 接口跳到对应 DAO。

不要忽略软删除。`LibraryContentLifecycle.scanRootFolder` 对磁盘上消失的 series/book 先做 soft delete，并有 `tryRestoreSeries`、`tryRestoreBooks` 用文件大小和 hash 尝试恢复元数据、阅读进度、缩略图、书单引用。直接查“当前存在的文件”可能解释不了数据库中 deleted 记录的用途。

不要把安全规则只看成一个登录配置。`SecurityConfiguration` 有多条 filter chain：普通 API/OPDS/SSE、Kobo、KOReader 的认证方式不同；部分接口如 `/api/v1/claim`、`/api/v1/oauth2/providers`、字体资源、OPDS auth 文档允许匿名访问，但具体业务方法内部还可能继续检查权限。

不要把 `infrastructure` 当成“低价值工具代码”。这里包含数据库连接、Flyway/jOOQ、Lucene、媒体解析、图片转换、Kobo 代理、安全过滤器、Web MVC 配置等运行时关键能力。很多领域服务能工作，是因为这些基础设施 Bean 被 Spring 注入进来了。
