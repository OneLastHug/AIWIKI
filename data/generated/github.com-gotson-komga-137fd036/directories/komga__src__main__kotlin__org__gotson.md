# 目录：komga/src/main/kotlin/org/gotson

## 它负责什么

`komga/src/main/kotlin/org/gotson` 是 Komga 后端 Kotlin 主源码的根包。它下面实际承载的是 `org.gotson.komga` 应用包，也就是一个基于 Spring Boot 的漫画/电子书媒体服务器后端：负责启动应用、暴露 REST/SSE/MVC 接口、组织领域模型和业务服务、访问数据库、解析媒体文件、处理后台任务、安全认证、搜索、缩略图、元数据、Kobo/KOReader 等客户端协议适配。

入口文件是 `komga/src/main/kotlin/org/gotson/komga/Application.kt`。它使用 `@SpringBootApplication` 启动 Spring 容器，用 `@EnableScheduling` 开启调度任务；`main` 函数启动前会调用 `checkTempDirectory()` 检查临时目录，并设置 jOOQ 的运行参数，再执行 `runApplication<Application>(*args)`。

从目录形态看，这里不是一个“工具函数集合”，而是后端应用主体。整体架构接近分层/六边形风格：`interfaces` 接收外部请求，`domain` 表达业务核心，`infrastructure` 提供技术实现，`application` 编排后台任务和应用级事件。

## 关键组成

`komga/src/main/kotlin/org/gotson/komga/Application.kt` 是启动入口。它只做少量启动前准备，把真正的组件发现、依赖注入、HTTP 服务、调度任务交给 Spring Boot。

`komga/src/main/kotlin/org/gotson/komga/domain` 是领域层。`domain/model` 放核心业务对象，例如 `Book`、`Series`、`Library`、`Media`、`ReadProgress`、`ThumbnailBook`、`KomgaUser`、`SearchCondition`、`DomainEvent` 等；`domain/service` 放业务服务，例如 `BookLifecycle`、`BookAnalyzer`、`BookImporter`、`LibraryLifecycle`、`SeriesLifecycle`、`MetadataAggregator`、`ReadListLifecycle`、`SyncPointLifecycle` 等；`domain/persistence` 放仓储接口，例如 `BookRepository`、`LibraryRepository`、`MediaRepository`、`ReadProgressRepository` 等。这里的重点是“业务含义”，而不是 HTTP 或数据库细节。

`komga/src/main/kotlin/org/gotson/komga/interfaces` 是外部接口层。`interfaces/api/rest` 中有主要 REST Controller，例如 `BookController`、`SeriesController`、`ReadListController`、`UserController`、`SettingsController`、`LoginController` 等；`interfaces/api/rest/dto` 放 REST DTO 和转换逻辑；`interfaces/sse` 负责服务端事件推送；`interfaces/mvc` 负责前端页面入口和资源找不到处理；`interfaces/scheduler` 放定时/启动型控制器；`interfaces/apprunner` 处理命令行式运行器，如用户列表、密码重置。

`komga/src/main/kotlin/org/gotson/komga/infrastructure` 是基础设施层。它包含 `jooq` 数据访问实现、`datasource` 数据源、`security` 安全认证、`mediacontainer` 媒体容器解析、`image` 图片分析/转换、`search` 搜索索引、`metadata` 元数据、`cache` 缓存、`configuration` 配置、`web` Web 过滤/工具、`openapi` 文档配置、`transaction` 事务支持等。典型文件 `infrastructure/jooq/main/BookDao.kt` 实现 `domain/persistence/BookRepository`，使用 jOOQ 的 `DSLContext` 查询数据库，并把数据库记录转换成领域对象。

`komga/src/main/kotlin/org/gotson/komga/application` 是应用编排层。`application/tasks` 中的 `TaskProcessor`、`TaskHandler`、`TaskEmitter`、`TasksRepository` 负责后台任务队列；`application/events` 配置异步 Spring 事件；`application/scheduler` 处理库扫描等定时行为。这一层连接“用户请求产生任务”和“领域服务实际执行任务”。

`komga/src/main/kotlin/org/gotson/komga/language` 是较小的语言/时间相关工具包，例如当前时区转换等辅助能力。

## 上下游关系

上游入口主要有四类：HTTP REST 请求、SSE 连接、MVC 页面请求、定时/启动任务。REST 请求进入 `interfaces/api/rest/*Controller.kt`，例如 `BookController` 通过 `@GetMapping`、`@PostMapping` 暴露 `/api/v1/books`、`/api/v1/books/list` 等接口。Controller 负责读取请求参数、拿到 `KomgaPrincipal` 当前用户、组装搜索条件、分页排序、调用仓储或领域服务，然后返回 DTO。

中游是领域层。以 `BookController` 为例，它依赖 `BookLifecycle`、`BookAnalyzer`、`BookRepository`、`BookMetadataRepository`、`MediaRepository`、`ReadListRepository` 等。简单查询可能直接走 DTO Repository 或领域 Repository；涉及状态变化、缩略图生成、媒体分析、阅读进度调整时，会进入 `BookLifecycle` 这类领域服务。`BookLifecycle` 会在事务中更新 `Media`、`ReadProgress`、`ThumbnailBook` 等，并通过 `ApplicationEventPublisher` 发布 `DomainEvent.BookUpdated`、`DomainEvent.ThumbnailBookAdded` 等事件。

下游主要是基础设施层。`domain/persistence` 只是接口，真正落库由 `infrastructure/jooq/main/*Dao.kt` 实现。比如 `BookDao` 实现 `BookRepository`，内部维护 `Tables.BOOK`、`Tables.MEDIA`、`Tables.BOOK_METADATA`、`Tables.READ_PROGRESS` 等 jOOQ 表对象；查询时根据 `SearchCondition` 和 `SearchContext` 生成条件、必要 join、分页、排序，然后映射回 `Book`。媒体文件解析则下沉到 `infrastructure/mediacontainer`，图片处理下沉到 `infrastructure/image`，安全身份下沉到 `infrastructure/security`。

还有一条异步链路：接口或领域服务通过 `TaskEmitter` 投递任务，`TaskProcessor` 监听 `TaskAddedEvent` 和 `ApplicationReadyEvent`，从 `TasksRepository` 取任务并交给 `TaskHandler`。`TaskProcessor` 会根据 `KomgaSettingsProvider.taskPoolSize` 配置线程池大小，并在启动时把未完成任务重置为可处理状态。

## 运行/调用流程

应用启动流程是：执行 `Application.kt` 的 `main`，检查临时目录，设置 jOOQ 参数，启动 Spring Boot。由于 `@SpringBootApplication` 会扫描 `org.gotson.komga` 下的组件，`@RestController`、`@Service`、`@Component`、配置类、DAO 等都会注册进容器；`@EnableScheduling` 让调度相关组件生效。

一次典型“查询书籍列表”的流程是：客户端请求 `POST /api/v1/books/list`，进入 `interfaces/api/rest/BookController.kt` 的 `getBooks`；方法读取 `BookSearch`、分页参数和当前用户；如果没有显式排序且有全文搜索，会默认按 `relevance` 排序；然后调用 `bookDtoRepository.findAll(search, SearchContext(principal.user), pageRequest)`；结果再做 `restrictUrl(!principal.user.isAdmin)`，非管理员会被限制返回路径信息；最后返回分页 DTO。

一次典型“分析或更新书籍”的流程是：接口、扫描器或任务系统拿到 `Book` 后调用 `domain/service/BookLifecycle.kt`。`analyzeAndPersist` 会调用 `BookAnalyzer.analyze` 解析媒体信息；如果页数变化，会调整已有阅读进度；再更新 `Media`，发布 `DomainEvent.BookUpdated`。如果媒体状态为 `READY`，它返回后续动作集合，例如生成缩略图、刷新元数据。根据当前片段推断，这些动作通常由任务系统继续排队执行，依据是 `BookController` 引入了 `TaskEmitter` 和任务优先级常量，而 `BookLifecycle` 返回的是 `BookAction` 集合。

后台任务流程是：任务被加入 `TasksRepository` 后触发 `TaskAddedEvent`；`TaskProcessor.processAvailableTask()` 检查是否允许处理以及线程池容量；调用 `takeFirst()` 获取任务，交给 `TaskHandler.handleTask(task)`；任务完成后从队列删除，并继续尝试处理下一项。应用启动完成也会触发一次处理，因此重启后残留任务可以继续执行。

## 小白阅读顺序

1. 先读 `komga/src/main/kotlin/org/gotson/komga/Application.kt`，理解这是 Spring Boot 应用，入口很薄，实际逻辑靠组件扫描装配。

2. 再看目录结构：`interfaces` 是入口，`domain` 是业务，`infrastructure` 是技术实现，`application` 是后台编排。先建立这个分层地图，比一开始钻进某个 DAO 更重要。

3. 读一个完整接口样本：`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/BookController.kt`。关注构造函数注入了哪些服务和仓储、方法上的 `@GetMapping`/`@PostMapping`、`@AuthenticationPrincipal`、分页参数、DTO 返回。

4. 读一个领域服务样本：`komga/src/main/kotlin/org/gotson/komga/domain/service/BookLifecycle.kt`。重点看它如何组合仓储、事务、媒体分析、缩略图、事件发布。这里能看出 Komga 的业务状态变化主要在哪里发生。

5. 读一个仓储接口和实现的配对：例如 `domain/persistence/BookRepository.kt` 与 `infrastructure/jooq/main/BookDao.kt`。理解“领域层依赖接口，基础设施层实现接口”的方向。

6. 最后读 `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskProcessor.kt`，理解扫描、分析、缩略图、索引等耗时工作为什么不会全塞在 HTTP 请求线程里。

## 常见误区

不要把 `org/gotson` 当成很多独立模块。当前目标下真正的主包是 `org.gotson.komga`，`org/gotson` 只是包路径前缀。

不要以为 Controller 是业务核心。`interfaces/api/rest/*Controller.kt` 很多代码看起来最长，但它主要负责协议适配、参数处理、权限上下文和 DTO。真正改变业务状态的逻辑通常在 `domain/service/*Lifecycle.kt`、分析器、导入器和任务处理链中。

不要把 `domain/persistence` 理解为数据库实现。它们是仓储接口；jOOQ 查询、表 join、读写数据源区分等实现细节在 `infrastructure/jooq` 下。看调用关系时应该从接口看意图，再到 DAO 看实现。

不要忽略事件和任务。Komga 很多操作不是“请求进来立即全部做完”，而是通过 `DomainEvent`、`TaskEmitter`、`TaskProcessor`、scheduler 组合完成。阅读扫描、媒体分析、缩略图、搜索索引相关功能时，要顺着异步链路找。

不要把 DTO 和领域模型混用。`interfaces/api/rest/dto` 面向 HTTP 响应和请求，`domain/model` 面向业务内部。两者名称可能相似，例如 `BookDto` 和 `Book`，但职责不同。

不要只看 `BookController` 的前半段就下结论。它同时处理列表、详情、内容读取、缩略图、阅读进度、导入等多个主题；学习时建议按一个端点一路追踪到 service、repository、dao，而不是横向扫完整个文件。
