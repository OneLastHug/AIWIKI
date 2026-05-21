# 目录：komga/src/test/kotlin/org/gotson

## 它负责什么

`komga/src/test/kotlin/org/gotson` 是 Komga 后端 Kotlin 测试代码的根目录，对应生产代码包名 `org.gotson.komga`。它不是业务运行入口，而是用来验证 Spring Boot 应用装配、领域模型、领域服务、数据库访问、元数据解析、媒体容器解析、搜索、Web/API 接口以及架构边界是否符合预期。

从目录结构看，它基本沿用了生产代码的分层方式：`domain` 测领域规则，`infrastructure` 测数据库和外部格式适配，`interfaces` 测 REST/OPDS/Kobo/Koreader 等接口层，`application` 测应用任务处理，`architecture` 用 ArchUnit 固化代码架构约束。顶层还有 `AutowiringTest.kt` 和 `Utils.kt`，分别验证 Spring 上下文能否按测试配置启动，以及提供测试辅助扩展函数。

## 关键组成

`komga/src/test/kotlin/org/gotson/komga/AutowiringTest.kt` 是最顶层的 Spring Boot 冒烟测试。它使用 `@SpringBootTest` 启动完整应用上下文，并注入 `List<DataSource>` 与 `List<DSLContext>`，断言测试环境下有 4 个数据源和 4 个 jOOQ 上下文。这说明 Komga 的测试环境不是只测单个内存对象，而会覆盖多数据源配置和 jOOQ 持久层装配。

`komga/src/test/kotlin/org/gotson/komga/Utils.kt` 很小，只定义了 `Map<Series, List<Book>>.toScanResult()`，把扫描得到的 `Series -> Book` 映射包装成 `ScanResult`。它服务于扫描、导入类测试，减少重复构造领域对象的样板代码。

`komga/src/test/kotlin/org/gotson/komga/architecture` 是架构约束测试目录。`DomainDrivenDesignRulesTest.kt` 使用 ArchUnit 的 `@AnalyzeClasses(packagesOf = [Application::class], importOptions = [DoNotIncludeTests])` 扫描生产代码，要求 `domain.model` 不依赖 `infrastructure`、`interfaces`、`domain.persistence`、`domain.service`，并要求名字包含 `Controller` 的类位于 `interfaces` 包下。`SlicesIsolationRulesTest.kt` 则要求 `interfaces.(*)` 下的不同接口切片不能互相依赖。这个目录的价值是防止架构腐化，而不是验证单个函数返回值。

`komga/src/test/kotlin/org/gotson/komga/domain/model` 覆盖纯领域模型，例如 `AuthorTest.kt`、`BookMetadataTest.kt`、`SeriesMetadataTest.kt`、`ContentRestrictionsTest.kt`、`KomgaUserTest.kt`、`PageHashTest.kt`、`BookSearchTest.kt`、`SeriesSearchTest.kt` 等。这里通常不需要完整 Spring 上下文，重点是对象构造、校验、搜索条件、内容限制、元数据归一化等规则。

`komga/src/test/kotlin/org/gotson/komga/domain/service` 覆盖领域服务和生命周期。以 `BookLifecycleTest.kt` 为代表，它通过 `@SpringBootTest` 注入 `BookRepository`、`LibraryRepository`、`SeriesRepository`、`ReadProgressRepository`、`MediaRepository`、`KomgaUserRepository`、`ThumbnailBookRepository` 等仓储，再用 `@SpykBean` 观察 `BookLifecycle`，用 `@MockkBean` 替换 `BookAnalyzer`。测试内容包括重新分析书籍后阅读进度是否保留或重置、删除书籍文件时是否处理 sidecar 缩略图、文件不存在时是否短路等。这个目录反映 Komga 的核心业务行为：扫描、导入、分析、生命周期管理、用户和库管理。

`komga/src/test/kotlin/org/gotson/komga/infrastructure` 是基础设施适配层测试，范围很广。`jooq/main` 下的 `BookDaoTest.kt`、`SeriesDaoTest.kt`、`LibraryDaoTest.kt`、`MediaDaoTest.kt` 等验证 DAO 的 insert、update、find、search、delete 行为；`jooq/tasks` 验证任务表访问；`datasource` 验证数据源配置；`metadata` 验证 ComicRack、EPUB、Mylar、本地图片、ISBN 条码等元数据来源；`mediacontainer` 验证 zip、rar、epub、pdf 容器解析；`search` 验证多语言分析器和索引生命周期；`kobo` 验证 Kobo 同步相关转换和 token。

`komga/src/test/kotlin/org/gotson/komga/interfaces` 是接口层测试。`interfaces/api/rest` 下有大量 Controller 测试，例如 `BookControllerTest.kt`、`SeriesControllerTest.kt`、`LibraryControllerTest.kt`、`UserControllerTest.kt`、`SettingsControllerTest.kt` 等。以 `BookControllerTest.kt` 为例，它使用 `@SpringBootTest`、`@AutoConfigureMockMvc`、`MockMvc` 和自定义 `WithMockCustomUser` 测试 `/api/v1/books` 等接口，覆盖库权限、年龄限制、内容过滤、HTTP 状态码和 JSON 返回结构。`interfaces/api/kobo`、`interfaces/api/kosync`、`interfaces/api/opds` 分别对应 Kobo、KOReader Sync、OPDS API；`interfaces/mvc` 则覆盖 MVC 资源找不到等页面层行为。

## 上下游关系

这个测试目录的上游主要是生产代码 `komga/src/main/kotlin/org/gotson/komga`、测试资源和 Spring 测试配置。测试类通过 import 直接依赖生产包里的 `domain.model`、`domain.service`、`domain.persistence`、`infrastructure.jooq`、`interfaces.api` 等类型，也依赖 JUnit 5、AssertJ、MockK、Spring Boot Test、MockMvc、ArchUnit、Jimfs、jOOQ 等测试框架或辅助库。

它的下游是构建系统和 CI。根据当前片段推断，这些测试会被 Gradle 的 test 任务发现并执行，依据是文件命名普遍以 `Test.kt` 结尾，并使用 JUnit 5 的 `@Test`、`@Nested`、`@ParameterizedTest`、ArchUnit 的 `@ArchTest` 等标准测试入口。

从依赖方向看，测试代码可以跨层调用很多生产组件，以便构造场景；但生产代码不能依赖测试代码。架构测试还会反过来约束生产代码的包依赖，例如领域模型不能知道接口层和基础设施层，接口切片之间不能互相调用。

## 运行/调用流程

典型单元或集成测试流程是：测试框架发现 `*Test.kt` 类，JUnit 创建测试实例，Spring 测试类通过 `@SpringBootTest` 启动应用上下文并注入依赖，`@BeforeAll` 或 `@BeforeEach` 写入基础数据，测试方法执行业务动作，最后用 AssertJ 或 MockMvc 断言结果，并在 `@AfterEach`、`@AfterAll` 中清理数据。

以 DAO 测试为例，`BookDaoTest.kt` 先插入 `Library` 和 `Series`，再调用 `bookDao.insert()`、`bookDao.update()`、`bookDao.findByIdOrNull()`、`bookDao.findAll()` 等方法，最后检查字段、数量、分页搜索结果和删除效果。它验证的是数据库映射和仓储行为。

以接口测试为例，`BookControllerTest.kt` 先通过 repository 和 lifecycle 创建库、系列、书籍、用户，再通过 `mockMvc.get("/api/v1/books")` 请求 REST API，断言 `status { isOk() }`、`jsonPath("$.content.length()")`、`jsonPath("$.content[0].name")` 等。这类测试覆盖了 Controller、权限、安全上下文、领域服务和持久层的组合效果。

以元数据测试为例，`ComicInfoProviderTest.kt` 直接 mock `XmlMapper` 和 `BookAnalyzer`，构造 `ComicInfo` DTO，调用 `ComicInfoProvider.getBookMetadataFromBook()`，断言生成的 `BookMetadataPatch` 中标题、摘要、编号、发布日期、ISBN、read lists、links、tags 是否符合规则。这类测试更接近适配器逻辑单测。

架构测试流程不同：ArchUnit 扫描生产类字节码，按声明规则检查依赖关系和命名位置。如果有人把 Controller 放到非 `interfaces` 包，或者让 `domain.model` 依赖 `infrastructure`，测试会失败。

## 小白阅读顺序

1. 先看 `komga/src/test/kotlin/org/gotson/komga/AutowiringTest.kt`，理解测试如何启动 Spring Boot，以及项目为什么有多个 `DataSource` 和 `DSLContext`。

2. 再看 `komga/src/test/kotlin/org/gotson/komga/architecture/DomainDrivenDesignRulesTest.kt` 和 `komga/src/test/kotlin/org/gotson/komga/architecture/SlicesIsolationRulesTest.kt`，先建立 Komga 的分层边界：`domain` 是核心，`infrastructure` 是实现细节，`interfaces` 是外部入口。

3. 接着看 `domain/model` 下的简单测试，例如 `AuthorTest.kt`、`BookMetadataTest.kt`、`SeriesMetadataTest.kt`。这些测试通常更短，适合理解领域对象和规则。

4. 然后读 `domain/service`，推荐从 `BookLifecycleTest.kt`、`LibraryLifecycleTest.kt`、`SeriesLifecycleTest.kt` 入手。这里能看到“库、系列、书籍、媒体、阅读进度、缩略图”等核心概念如何串起来。

5. 再读 `infrastructure/jooq/main` 的 DAO 测试，例如 `BookDaoTest.kt`、`SeriesDaoTest.kt`、`LibraryDaoTest.kt`，理解领域仓储如何落到数据库。

6. 最后读 `interfaces/api/rest` 的 Controller 测试，例如 `BookControllerTest.kt`、`LibraryControllerTest.kt`、`UserControllerTest.kt`。这时再看 MockMvc 断言，就能把 HTTP API、权限、领域服务和数据库行为联系起来。

## 常见误区

不要把这个目录理解成“纯单元测试集合”。其中很多测试使用 `@SpringBootTest`，会启动 Spring 上下文并访问真实测试数据源，因此更接近集成测试。

不要认为 `architecture` 目录是在测试业务功能。它测试的是代码结构规则，例如包依赖、Controller 放置位置、接口切片隔离。这些测试失败通常意味着架构边界被破坏，而不是某个 API 返回值错了。

不要只看 Controller 测试就理解业务逻辑。`interfaces/api/rest` 验证的是外部表现和权限过滤，真正的生命周期规则通常在 `domain/service` 测试里，例如分析书籍、删除文件、更新阅读进度、导入扫描结果等。

不要忽略测试辅助函数和工厂方法。大量测试依赖 `makeBook`、`makeSeries`、`makeLibrary`、`makeBookPage`、`toScanResult()` 这类构造工具。阅读测试时应先分清哪些是场景数据构造，哪些才是被测行为。

不要把 mock 当成真实行为。比如 `BookLifecycleTest.kt` 中 `BookAnalyzer` 被 `@MockkBean` 替换，测试关心的是 lifecycle 在分析结果返回后如何持久化和调整阅读进度，而不是压缩包或 EPUB 的真实解析过程。真实解析逻辑通常在 `infrastructure/mediacontainer` 或 `infrastructure/metadata` 的测试中覆盖。
