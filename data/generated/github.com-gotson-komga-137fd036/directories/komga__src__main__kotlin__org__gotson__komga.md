# 目录：komga/src/main/kotlin/org/gotson/komga

## 它负责什么

`komga/src/main/kotlin/org/gotson/komga` 是 Komga 后端 Kotlin/Spring Boot 应用的主源码包，承担从应用启动、HTTP/API 接入、业务规则、数据访问抽象，到基础设施实现的主要职责。入口文件是 `Application.kt`，它使用 `@SpringBootApplication` 启动 Spring 容器，用 `@EnableScheduling` 开启定时任务能力，并在 `main` 中先执行 `checkTempDirectory()`，再设置 jOOQ 的日志/提示开关，最后调用 `runApplication<Application>(*args)`。

从目录结构看，这里采用比较清晰的分层方式：外部请求进入 `interfaces`，业务行为落到 `domain`，异步任务和事件由 `application` 编排，数据库、缓存、安全、媒体解析、搜索、Web 配置等技术细节放在 `infrastructure`。因此这个目录可以理解为 Komga 服务端的“后端主体”。

## 关键组成

`Application.kt` 是 Spring Boot 启动入口，代码很薄，不承载业务逻辑。它的作用是把当前包及其子包纳入组件扫描范围，并启用调度。

`domain` 是业务核心层。其下的 `model` 包含主要领域对象，例如 `Library`、`Book`、`Series`、`ReadList`、`KomgaUser`、`Media`、`BookMetadata`、`SeriesMetadata`、`ReadProgress`、`SyncPoint`、`ThumbnailBook` 等；`persistence` 定义仓储接口，例如 `LibraryRepository`、`BookRepository`、`SeriesRepository`、`ReadProgressRepository`、`KomgaUserRepository`、`ThumbnailSeriesRepository` 等；`service` 放业务生命周期和领域服务，例如 `LibraryLifecycle`、`BookLifecycle`、`BookImporter`、`FileSystemScanner`、`MetadataAggregator`、`MetadataApplier`、`PageHashLifecycle`、`ReadListLifecycle`、`SeriesLifecycle` 等。

`interfaces` 是外部入口层。`interfaces/api/rest` 下有大量 REST Controller，例如 `LibraryController.kt`、`BookController.kt`、`SeriesController.kt`、`UserController.kt`、`SettingsController.kt`、`TaskController.kt` 等；`interfaces/api/opds`、`interfaces/api/kobo`、`interfaces/api/kosync` 说明系统还提供 OPDS、Kobo、KOReader Sync 等面向阅读器或协议客户端的接口；`interfaces/sse`、`interfaces/scheduler`、`interfaces/mvc`、`interfaces/apprunner` 则分别对应服务端推送、调度入口、MVC 页面或应用启动后运行逻辑。

`application` 是应用编排层。直接子目录包括 `events`、`scheduler`、`tasks`。从 `LibraryController.kt` 可见，接口层会注入 `TaskEmitter`，通过 `scanLibrary`、`analyzeBook`、`refreshBookMetadata`、`refreshBookLocalArtwork`、`refreshSeriesLocalArtwork`、`emptyTrash` 等方法把耗时操作交给任务系统，并使用 `HIGHEST_PRIORITY`、`HIGH_PRIORITY` 控制任务优先级。

`infrastructure` 是技术实现层。它包含 `configuration`、`datasource`、`jooq`、`security`、`web`、`image`、`mediacontainer`、`metadata`、`search`、`cache`、`transaction`、`validation`、`openapi`、`kobo`、`sidecar`、`xml` 等子包。根据当前片段推断，这些包分别负责配置绑定、数据库连接、jOOQ 实现、安全认证、Web 工具、图片处理、漫画/电子书容器解析、元数据导入、搜索索引、缓存和事务等横切能力。

`language` 是一个单独的顶层包，根据名称推断可能与语言、区域或文本规范化能力有关；本次未展开读取，不能进一步确认细节。

## 上下游关系

上游主要是 HTTP 客户端、Web 前端、OPDS/Kobo/KOReader 客户端、定时任务触发器和应用启动事件。它们通过 `interfaces` 层进入系统，最终调用业务服务或任务发射器。

以 `interfaces/api/rest/LibraryController.kt` 为例，`GET /api/v1/libraries` 会根据 `KomgaPrincipal` 中的当前用户权限决定查询全部 library，还是只查询 `sharedLibrariesIds` 中允许访问的 library。它依赖 `LibraryRepository` 读取数据，并通过 `toDto()` 把 domain 对象转换成 API DTO。创建、修改、删除 library 时，Controller 不直接操作数据库，而是调用 `LibraryLifecycle.addLibrary`、`LibraryLifecycle.updateLibrary`、`LibraryLifecycle.deleteLibrary`，说明业务约束被集中放在 lifecycle 服务里。

下游主要是仓储接口、任务系统和基础设施实现。`domain/persistence` 定义的 repository 接口是领域层对数据存取的抽象，具体实现很可能位于 `infrastructure/jooq` 或相关 datasource 包。`infrastructure/security` 提供 `KomgaPrincipal` 等认证上下文；`infrastructure/web` 提供 `filePathToUrl` 这类 Web/路径转换工具；`infrastructure/openapi` 提供接口文档标签配置。

## 运行/调用流程

应用启动流程大致是：执行 `Application.kt` 的 `main`，先检查临时目录，再关闭 jOOQ logo/tips，随后启动 Spring Boot。由于 `Application` 标注了 `@SpringBootApplication`，Spring 会扫描 `org.gotson.komga` 下面的组件、配置、Controller、Service、Repository 实现等。`@EnableScheduling` 让 `application/scheduler` 或 `interfaces/scheduler` 中的定时逻辑可以被 Spring 调度。

一次典型 REST 调用流程可以按 `LibraryController.kt` 理解：请求进入 `@RestController`，路由由 `@RequestMapping`、`@GetMapping`、`@PostMapping` 等注解匹配；认证信息通过 `@AuthenticationPrincipal KomgaPrincipal` 注入；权限通过 `@PreAuthorize("hasRole('ADMIN')")` 或手动判断控制；输入 DTO 通过 `@Valid @RequestBody` 校验；Controller 调用 `LibraryRepository` 或 `LibraryLifecycle`；返回时把 domain model 转成 DTO。对于扫描、分析、刷新元数据、清空回收站这类耗时操作，Controller 返回 `202 ACCEPTED`，实际工作交给 `TaskEmitter` 异步执行。

一次后台扫描/导入流程根据当前片段推断大致是：用户或调度器触发扫描任务，`TaskEmitter.scanLibrary` 发出任务，任务层调用 `FileSystemScanner`、`BookImporter`、`BookAnalyzer`、`MetadataAggregator`、`MetadataApplier` 等 domain service，必要时再通过 `infrastructure/mediacontainer`、`infrastructure/image`、`infrastructure/metadata` 解析文件、图片和元数据，最后经 repository 写入数据库并可能发布事件。

## 小白阅读顺序

1. 先读 `Application.kt`，确认这是一个 Spring Boot 应用，入口本身很薄，真正逻辑都在子包。

2. 再看 `interfaces/api/rest/LibraryController.kt`。它比较适合作为入门样本：能看到路由注解、权限控制、DTO 转换、repository 查询、lifecycle 调用和异步任务发射。

3. 接着看 `domain/model/Library.kt`、`domain/model/Book.kt`、`domain/model/Series.kt`。先理解核心业务对象：库、书、系列，是 Komga 后端最重要的概念。

4. 然后看 `domain/service/LibraryLifecycle.kt`、`BookLifecycle.kt`、`FileSystemScanner.kt`、`BookImporter.kt`。这些文件会解释“创建书库后如何扫描文件、如何导入书籍、如何维护生命周期”。

5. 再看 `domain/persistence/LibraryRepository.kt`、`BookRepository.kt`、`SeriesRepository.kt`，理解业务层如何抽象数据访问。之后再进入 `infrastructure/jooq` 找具体数据库实现，会更容易看懂。

6. 最后按兴趣读协议和基础设施：想理解外部 API 就读 `interfaces/api/rest`、`interfaces/api/opds`、`interfaces/api/kobo`；想理解安全就读 `infrastructure/security`；想理解文件格式就读 `infrastructure/mediacontainer`；想理解配置就读 `infrastructure/configuration/KomgaProperties.kt`、`StaticConfiguration.kt` 等。

## 常见误区

不要把 `interfaces` 当成业务核心。Controller 里虽然有一些参数拼装、异常转换和权限判断，但核心规则应优先去 `domain/service` 和 `domain/model` 找。例如 `LibraryController.kt` 创建 library 时只是把 `LibraryCreationDto` 转成 `Library`，真正的路径校验、重名校验、生命周期副作用由 `LibraryLifecycle` 承担。

不要以为 `domain/persistence` 就是数据库实现。这个包从命名和文件列表看更像仓储接口层，具体 SQL、jOOQ、事务或数据源细节应在 `infrastructure` 下查找。

不要忽略异步任务。扫描书库、分析书籍、刷新元数据、清空回收站都不是简单同步执行；`LibraryController.kt` 中这些接口会通过 `TaskEmitter` 投递任务并返回 `ACCEPTED`。阅读相关功能时要继续追到 `application/tasks`，否则会误以为 Controller 已经完成全部工作。

不要把 `Application.kt` 看得过重。它只是启动和全局启用调度的入口，不是应用架构的核心说明书。真正的架构线索在包划分、Controller 注入对象、domain service 命名和 infrastructure 子包职责中。

不要把 API DTO 和 domain model 混为一谈。`LibraryController.kt` 明确使用 `LibraryCreationDto`、`LibraryUpdateDto`、`LibraryDto` 和 `toDomain`、`toDto` 转换，说明接口输入输出与内部业务对象有边界。阅读时应分清“对外协议字段”和“内部领域字段”。
