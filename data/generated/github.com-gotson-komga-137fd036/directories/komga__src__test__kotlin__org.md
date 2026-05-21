# 目录：komga/src/test/kotlin/org

## 它负责什么

`komga/src/test/kotlin/org` 是 Komga 后端 Kotlin 测试代码的根包目录，实际测试主体位于 `org.gotson.komga` 包下。它的职责不是提供业务功能，而是用自动化测试验证 `komga/src/main/kotlin/org/gotson/komga` 中的应用层、领域层、基础设施层和接口层是否按预期工作。

从目录结构看，这里的测试基本跟主源码的分层一一对应：主源码有 `application`、`domain`、`infrastructure`、`interfaces`，测试目录也按同样包名组织。这说明项目希望测试读者可以用“测试包路径等于被测包路径”的方式定位代码。

这个目录覆盖的测试类型比较全面：

- Spring 上下文装配测试，例如 `org/gotson/komga/AutowiringTest.kt`。
- 架构约束测试，例如 `org/gotson/komga/architecture/DomainDrivenDesignRulesTest.kt`。
- 领域模型和领域服务测试，例如 `domain/model`、`domain/service`。
- JOOQ 数据访问测试，例如 `infrastructure/jooq/main`、`infrastructure/jooq/tasks`。
- 文件格式、元数据、搜索、Kobo、Web 包装器等基础设施测试，例如 `infrastructure/metadata/comicrack/ComicInfoProviderTest.kt`。
- REST、OPDS、Kobo、KOReader Sync、MVC 等接口测试，例如 `interfaces/api/rest/BookControllerTest.kt`。

根目录下还有一个小工具文件 `org/gotson/komga/Utils.kt`，提供 `Map<Series, List<Book>>.toScanResult()` 扩展函数，用于把测试中的系列到书籍映射快速转成 `ScanResult`，减少测试准备代码。

## 关键组成

`org/gotson/komga/AutowiringTest.kt` 是最顶层的集成测试之一。它使用 `@SpringBootTest` 启动 Spring Boot 测试上下文，并注入 `List<DataSource>` 与 `List<DSLContext>`。其中一个测试只检查应用能否在测试配置下启动，另一个测试断言应用中有 4 个 datasource 和 4 个 jOOQ `DSLContext`。这类测试通常用于发现配置、Bean 装配、数据源声明或 profile 配置错误。

`org/gotson/komga/architecture` 是架构规则测试目录，使用 ArchUnit。`DomainDrivenDesignRulesTest.kt` 通过 `@AnalyzeClasses(packagesOf = [Application::class], importOptions = [DoNotIncludeTests])` 扫描主应用代码，并声明两类规则：领域模型包 `..domain..model..` 不能依赖 `infrastructure`、`interfaces`、`domain.persistence`、`domain.service`；名称包含 `Controller` 的类应该位于 `interfaces` 包。这个目录的作用是把项目分层约束变成可执行测试，防止后续开发无意打破 DDD 边界。

`org/gotson/komga/domain/model` 主要测试领域对象自身的规则，比如作者、书籍元数据、系列元数据、搜索条件、内容限制、用户、页哈希、BCP47 语言标签等。它们更接近纯单元测试，重点通常是值对象、数据模型、校验、排序、解析、匹配逻辑。

`org/gotson/komga/domain/service` 测试领域服务，例如 `BookLifecycleTest.kt`、`SeriesLifecycleTest.kt`、`LibraryLifecycleTest.kt`、`BookAnalyzerTest.kt`、`MetadataAggregatorTest.kt`。这类测试常使用 `@SpringBootTest` 注入 repository 和 lifecycle service，再用 `MockkBean` 或 `SpykBean` 替换部分协作者。以 `BookLifecycleTest.kt` 为例，它验证重新分析书籍后阅读进度如何保留或重置、删除书籍文件时是否连带删除 sidecar 缩略图、文件不存在时是否跳过软删除等。这说明领域服务测试不仅关注内存对象，还会覆盖数据库状态、文件系统副作用和跨 repository 协作。

`org/gotson/komga/infrastructure/jooq` 是数据访问层测试，`main` 子目录数量最多。代表文件 `BookDaoTest.kt` 使用 `@SpringBootTest` 注入 `BookDao`、`SeriesRepository`、`LibraryRepository`，在 `BeforeAll` 准备 library 和 series，在 `AfterEach` 清空 book，再验证 insert、update、findById、findAll、search、按 library 或 series 查询、deleteAll 等行为。这类测试用于保证 jOOQ DAO 与数据库 schema、领域模型映射、分页搜索条件之间保持一致。

`org/gotson/komga/infrastructure/metadata` 测试元数据读取器。`ComicInfoProviderTest.kt` 是典型例子：它 mock `XmlMapper` 和 `BookAnalyzer`，构造 `ComicInfo` DTO，再断言 `ComicInfoProvider.getBookMetadataFromBook()` 输出的 `BookMetadataPatch` 是否正确填充标题、摘要、编号、排序号、发布日期、ISBN、read list、链接和标签。这里更偏向纯单元测试，核心是输入格式到领域补丁对象的转换规则。

`org/gotson/komga/infrastructure/mediacontainer` 测试压缩包、EPUB、PDF 等媒体容器解析逻辑，包括 `divina`、`epub`、`pdf`。这些测试关注外部文件格式的解析结果，帮助保证漫画、电子书、导航文件、OPF/NCX 等资源能被正确识别。

`org/gotson/komga/infrastructure/search` 测试搜索相关组件，例如多语言 analyzer、ngram analyzer、搜索索引生命周期。它们对应主源码中的 `infrastructure/search`，用于验证索引、分词、搜索生命周期行为。

`org/gotson/komga/interfaces/api/rest` 是 REST API 测试密集区。代表文件 `BookControllerTest.kt` 使用 `@SpringBootTest` 和 `@AutoConfigureMockMvc` 注入 `MockMvc`、repository、lifecycle service。它通过 `mockMvc.get`、`patch`、`delete` 等方式请求 `/api/v1/books` 等接口，并断言 HTTP 状态、JSON 路径、权限限制和内容过滤。测试中还能看到自定义用户注解 `@WithMockCustomUser`，用于模拟不同 library 权限、年龄分级限制等访问场景。

`org/gotson/komga/interfaces/api/kobo`、`interfaces/api/kosync`、`interfaces/api/opds` 分别测试 Kobo、KOReader Sync、OPDS 协议接口。它们和普通 REST Controller 一样属于接口层，但更偏向第三方阅读器或协议适配。

`org/gotson/komga/application/tasks` 测试任务处理逻辑，对应主源码 `application/tasks`。根据当前片段推断，它位于应用层与领域层之间，主要验证后台任务如何被处理、分派或执行，依据是测试目录与主源码目录均存在 `application/tasks`，且有 `TaskProcessorTest.kt`。

## 上下游关系

这个测试目录的上游是主源码目录 `komga/src/main/kotlin/org/gotson/komga`。测试代码通过相同包结构引用和验证主代码中的类，例如 `domain.service.BookLifecycle`、`domain.persistence.BookRepository`、`infrastructure.jooq.main.BookDao`、`interfaces.api.rest.BookController` 等。

测试代码还依赖若干测试框架和基础设施：

- JUnit 5：使用 `@Test`、`@Nested`、`@BeforeAll`、`@AfterEach`、`@ParameterizedTest` 等组织测试。
- AssertJ：使用 `assertThat`、`assertThatNoException`、`catchThrowable` 等表达断言。
- Spring Boot Test：使用 `@SpringBootTest` 启动真实应用上下文。
- Spring MockMvc：接口层测试通过 `MockMvc` 发起模拟 HTTP 请求。
- MockK / springmockk：使用 `mockk`、`every`、`verify`、`@MockkBean`、`@SpykBean` 替换或监视 Bean。
- ArchUnit：用于架构约束测试。
- Jimfs：在 `BookLifecycleTest.kt` 中创建内存文件系统，避免直接操作真实磁盘。
- jOOQ：DAO 测试通过 `DSLContext`、DAO、repository 验证数据库访问行为。

从依赖方向看，测试可以依赖主代码的所有层，但架构测试会反过来约束主代码的层间依赖。也就是说，普通测试负责验证行为，`architecture` 目录负责验证“代码形状”。

## 运行/调用流程

通常一次测试运行会由 Gradle 或 IDE 触发，测试框架扫描 `komga/src/test/kotlin/org` 下的 JUnit 5 测试类，然后按注解和 Spring 配置执行。

对于纯单元测试，例如 `ComicInfoProviderTest.kt` 这一类，流程大致是：测试方法构造输入对象或 mock 返回值，直接调用被测类方法，然后用 AssertJ 验证返回对象。这类测试启动成本较低，不一定需要 Spring 上下文。

对于 Spring 集成测试，例如 `AutowiringTest.kt`、`BookLifecycleTest.kt`、`BookDaoTest.kt`、`BookControllerTest.kt`，流程更重：`@SpringBootTest` 启动应用测试上下文，创建 datasource、repository、service、controller 等 Bean；测试类通过构造函数注入或字段注入拿到依赖；`BeforeAll` 准备基础数据，测试方法执行业务操作或 HTTP 请求，最后 `AfterEach`、`AfterAll` 清理数据库或相关状态。

以 `BookControllerTest.kt` 为例，运行时先准备 library 和 user，再通过 lifecycle service 创建 series、book、metadata 等数据。随后 `MockMvc` 模拟访问 `/api/v1/books` 或某个 book 详情接口。请求进入接口层 Controller，再经过安全上下文、权限过滤、领域服务或 repository 查询，最终返回 JSON。测试断言 HTTP 状态码和 JSON 内容，从而覆盖“接口层 -> 应用/领域服务 -> 持久化层 -> 响应 DTO”的完整链路。

以 `BookDaoTest.kt` 为例，流程更靠近数据库：测试先插入 library 和 series，随后直接调用 `bookDao.insert`、`bookDao.update`、`bookDao.findByIdOrNull`、`bookDao.findAll`。断言重点是字段是否持久化、时间戳是否更新、搜索条件是否生效、删除后 count 是否为 0。

以 `DomainDrivenDesignRulesTest.kt` 为例，运行流程不同于业务测试：ArchUnit 先导入主应用类，不包含测试类；然后执行声明式架构规则。如果某个 domain model 直接依赖 infrastructure 或 interfaces，测试会失败。这类失败通常不是业务逻辑错误，而是分层边界被破坏。

## 小白阅读顺序

建议先从 `org/gotson/komga/AutowiringTest.kt` 开始。它代码最短，可以帮助你理解项目测试如何启动 Spring Boot，以及项目至少配置了多个 datasource 和 jOOQ context。

第二步读 `org/gotson/komga/architecture/DomainDrivenDesignRulesTest.kt`。这个文件能快速告诉你 Komga 后端的分层观念：`domain.model` 应该保持干净，Controller 应该属于 `interfaces`。理解这个规则后，再看其他目录会更容易判断某个类为什么放在那里。

第三步读 `org/gotson/komga/domain/model` 中的简单测试，例如 `AuthorTest.kt`、`BookMetadataTest.kt`、`SeriesSearchTest.kt`。这些测试通常不需要太多 Spring 背景，适合用来熟悉领域对象的字段、校验和业务概念。

第四步读 `org/gotson/komga/domain/service/BookLifecycleTest.kt` 或同目录其他 lifecycle 测试。这里会看到 repository、service、mock、文件系统、阅读进度、媒体分析等真实业务流程，是理解核心领域行为的入口。

第五步读 `org/gotson/komga/infrastructure/jooq/main/BookDaoTest.kt`。它展示领域对象如何落库、如何查询、如何被搜索条件过滤。读完后再看其他 DAO 测试，会发现大多数都有类似的“准备数据 -> 调 DAO -> 断言持久化结果”结构。

第六步读 `org/gotson/komga/interfaces/api/rest/BookControllerTest.kt`。这个文件较长，但价值很高，因为它从 HTTP API 视角串起了用户权限、内容限制、领域数据和返回 JSON。建议不要一口气读完整文件，而是先挑 `LimitedUser`、`RestrictedContent` 这类 `@Nested` 分组阅读。

最后再按兴趣阅读基础设施专项测试：如果关心元数据解析，读 `infrastructure/metadata/comicrack/ComicInfoProviderTest.kt`；如果关心 EPUB/PDF/压缩包，读 `infrastructure/mediacontainer`；如果关心搜索，读 `infrastructure/search`；如果关心第三方阅读器协议，读 `interfaces/api/kobo`、`interfaces/api/kosync`、`interfaces/api/opds`。

## 常见误区

不要把 `komga/src/test/kotlin/org` 理解成一个业务模块。它只是测试源码根包，真正的包结构从 `org/gotson/komga` 开始，且主要用于镜像主源码目录。

不要以为所有测试都是单元测试。这里大量文件使用 `@SpringBootTest`，会启动 Spring 上下文，并可能访问测试数据库、jOOQ、repository、MockMvc。阅读这类测试时，要把它当成集成测试看待。

不要忽略 `architecture` 目录。它不是“测试测试代码风格”的辅助目录，而是在保护主代码架构边界。比如领域模型不能依赖 infrastructure，这对理解 Komga 的 DDD 分层非常关键。

不要只看 Controller 测试就推断业务规则都写在 Controller 里。`BookControllerTest.kt` 等接口测试只是从 HTTP 入口验证行为，真正的数据准备和业务变化通常通过 `SeriesLifecycle`、`BookLifecycle`、repository、metadata repository 等下游组件完成。

不要误解 `makeBook`、`makeSeries`、`makeLibrary` 这类函数。它们是测试数据工厂，用来减少样板代码，不代表生产代码中对象只能这样创建。

不要忽略清理逻辑。许多测试在 `AfterEach` 或 `AfterAll` 中删除 book、series、library、user。如果新增或阅读测试时发现状态互相污染，优先检查清理逻辑，而不是马上怀疑被测业务代码。

不要把 mock 行为和真实行为混在一起。例如 `BookLifecycleTest.kt` 中 `@MockkBean BookAnalyzer` 可以让测试控制媒体分析结果；这说明测试关注的是 `BookLifecycle` 在“分析结果已知”时如何更新状态，而不是验证真实文件分析器。

不要认为 DAO 测试只是在测 getter/setter。像 `BookDaoTest.kt` 这类测试验证的是数据库字段映射、时间戳处理、搜索条件转换、分页查询、删除行为等持久化契约。它们失败时，往往意味着 schema、jOOQ 映射或 repository 行为发生了破坏。
