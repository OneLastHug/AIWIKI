# 目录：komga/src/test/kotlin/org/gotson/komga

## 它负责什么

`komga/src/test/kotlin/org/gotson/komga` 是 Komga 后端 Kotlin 测试代码的根目录，对应生产代码包 `org.gotson.komga`。它不承载业务实现，而是用 JUnit 5、Spring Boot Test、AssertJ、MockK、ArchUnit、Spring Security Test、MockMvc 等工具验证后端应用的正确性。

从目录分布看，这里既有普通单元/组件测试，也有加载完整 Spring 上下文的集成测试。测试目标大致分为几类：应用能否正常启动和装配、架构约束是否被破坏、领域模型和领域服务行为是否正确、JOOQ DAO 与数据库访问是否正确、媒体容器和元数据解析是否正确、搜索索引是否正常，以及 REST、OPDS、Kobo、KOReader 等接口层是否按权限和协议返回预期结果。

`komga/build.gradle.kts` 中测试依赖包含 `spring-boot-starter-test`、`spring-security-test`、`springmockk`、`mockk`、`jimfs`、`archunit-junit5`，测试任务使用 `useJUnitPlatform()`。这说明该目录的测试主线是 JUnit 5 平台上的 Spring 集成测试，而不是单纯的 Kotlin 函数级测试。

## 关键组成

根目录下的 `AutowiringTest.kt` 是一个很小但很重要的启动校验。它使用 `@SpringBootTest` 加载测试配置，断言应用能正常启动，并检查 `DataSource` 与 `DSLContext` 都有 4 个实例。根据当前片段推断，这与 Komga 内部多数据源/多 JOOQ context 配置有关，至少测试环境要求四套 DSL 上下文正确注册。

`Utils.kt` 提供测试辅助扩展 `Map<Series, List<Book>>.toScanResult()`，把扫描得到的 `Series -> Books` 映射转换成 `ScanResult`，主要服务于领域扫描/导入相关测试。

`architecture` 目录使用 ArchUnit 做“架构测试”，不是验证某个函数结果，而是验证代码组织规则。`CodingRulesTest.kt` 禁止生产代码访问标准输出、抛通用异常、使用 JodaTime、使用 `java.util.logging` 和字段注入；同文件里的测试代码规则还禁止测试依赖 `org.junit.jupiter.api.Assertions`，引导测试统一使用 AssertJ 等断言风格。`DomainDrivenDesignRulesTest.kt` 约束 `domain.model` 不依赖 `infrastructure`、`interfaces`、`domain.persistence`、`domain.service`，并要求名字包含 `Controller` 的类位于 `interfaces` 包。`SlicesIsolationRulesTest.kt` 要求 `interfaces` 下不同 slice 之间不要互相依赖。`NamingConventionTest.kt` 虽未展开阅读，但从命名看也是架构/命名规则的一部分。

`domain/model` 覆盖领域模型本身，例如 `AuthorTest.kt`、`BookMetadataTest.kt`、`SeriesMetadataTest.kt`、`KomgaUserTest.kt`、`ContentRestrictionsTest.kt`、`PageHashTest.kt`、`BookSearchTest.kt`、`SeriesSearchTest.kt`。这类测试通常不需要完整 Web 层，重点验证值对象、搜索条件、权限限制、元数据合并或规范化逻辑。

`domain/service` 覆盖核心业务服务，例如 `BookAnalyzerTest.kt`、`BookImporterTest.kt`、`BookLifecycleTest.kt`、`FileSystemScannerTest.kt`、`LibraryLifecycleTest.kt`、`SeriesLifecycleTest.kt`、`MetadataAggregatorTest.kt`、`MetadataApplierTest.kt`。代表文件 `BookAnalyzerTest.kt` 使用 `@SpringBootTest`，注入 `KomgaProperties`，并用 `@SpykBean` 包装 `BookAnalyzer` 和 `EpubExtractor`。它通过 `ClassPathResource` 读取测试资源中的 rar、zip、epub 等文件，验证媒体类型识别、页面提取、错误状态、EPUB TOC/landmark/page list 失败时的降级行为。这说明领域服务测试会触达真实资源文件和部分真实 Spring bean。

`infrastructure` 是基础设施适配层测试。`infrastructure/jooq/main` 下有大量 DAO 测试，如 `BookDaoTest.kt`、`LibraryDaoTest.kt`、`SeriesDaoTest.kt`、`MediaDaoTest.kt`、`ReadProgressDaoTest.kt`、`ServerSettingsDaoTest.kt` 等。代表文件 `BookDaoTest.kt` 使用 `@SpringBootTest` 注入 `BookDao`、`SeriesRepository`、`LibraryRepository`，在 `@BeforeAll` 准备 library/series，在 `@AfterEach` 清理 book，在 `@AfterAll` 清理上游数据，验证 insert、update、find、search、delete 等数据库行为。`infrastructure/mediacontainer` 测试 epub、pdf、zip、rar 解析；`infrastructure/metadata` 测试 ComicRack、EPUB、Mylar、本地封面、ISBN 条码等元数据来源；`infrastructure/search` 测试多语言分析器、NGram 分析器和搜索索引生命周期；`infrastructure/kobo` 测试 Kobo 相关转换与同步 token；`infrastructure/datasource` 测试数据源配置。

`interfaces` 是接口层测试。`interfaces/api/rest` 覆盖 REST 控制器，例如 `BookControllerTest.kt`、`LibraryControllerTest.kt`、`SeriesControllerTest.kt`、`UserControllerTest.kt`、`SettingsControllerTest.kt`、`ApiKeyTest.kt` 等。代表文件 `BookControllerTest.kt` 使用 `@SpringBootTest` 和 `@AutoConfigureMockMvc`，注入 repository、lifecycle service 和 `MockMvc`，通过 `mockMvc.get/delete/patch` 请求 `/api/v1/books` 等端点，并结合 `@WithMockCustomUser` 验证共享库权限、年龄分级限制、HTTP 状态码和 JSON 响应。`interfaces/api/opds`、`interfaces/api/kobo`、`interfaces/api/kosync` 分别覆盖外部阅读器/同步协议接口；`interfaces/mvc` 覆盖传统 MVC 资源找不到等行为。

## 上下游关系

这个测试目录的直接上游是生产代码包 `komga/src/main/kotlin/org/gotson/komga` 以及测试资源目录。测试会导入领域模型如 `Book`、`Series`、`Media`、`KomgaUser`，调用领域服务如 `BookAnalyzer`、`SeriesLifecycle`、`LibraryLifecycle`、`BookLifecycle`，访问持久化接口如 `BookRepository`、`SeriesRepository`、`LibraryRepository`，也会直接测试基础设施实现如 `BookDao`、EPUB/PDF/ZIP/RAR extractor、metadata provider 和 search lifecycle。

下游主要是 Gradle 的 test 任务和 CI 质量门禁。由于存在 ArchUnit 测试，开发者即使业务功能正确，只要违反包依赖、命名、注入方式或编码规则，也会在测试阶段失败。由于大量接口测试使用 `MockMvc` 和 Spring Security 测试注解，权限模型、内容限制、控制器参数解析和 JSON 响应结构也会被测试套件约束。

横向关系上，测试代码按 DDD 分层映射生产结构：`domain` 测领域规则，`infrastructure` 测外部技术实现，`interfaces` 测 HTTP/协议入口，`application` 测任务处理等应用层编排，`architecture` 测分层边界本身。这种结构让读者可以从测试目录反推出生产代码的分层方式。

## 运行/调用流程

典型运行入口是 Gradle 测试任务。根据 `komga/build.gradle.kts`，测试运行在 JUnit Platform 上。执行测试时，JUnit 发现 `*Test.kt` 类；遇到 `@SpringBootTest` 时启动 Spring Boot 测试上下文；遇到 `@AutoConfigureMockMvc` 时配置 `MockMvc`；遇到 ArchUnit 的 `@AnalyzeClasses` 和 `@ArchTest` 时扫描 `Application::class` 所在生产包，并应用架构规则。

以 DAO 测试为例，流程通常是：启动 Spring 上下文，注入 DAO/repository，`@BeforeAll` 创建上游必要数据，测试方法执行 insert/update/find/search/delete，使用 AssertJ 断言结果，`@AfterEach` 清理本测试产生的数据，最后 `@AfterAll` 清理共享前置数据。

以 REST 控制器测试为例，流程通常是：准备 library、series、book、user 等领域数据，通过自定义安全注解或 Spring Security mock user 设置当前用户身份，调用 `MockMvc` 发起 HTTP 请求，再断言状态码、JSON path、响应头或权限结果。它关注的是接口行为，不只是服务函数返回值。

以媒体分析测试为例，流程是：从 classpath 读取真实样例文件，构造 `Book`，调用 `BookAnalyzer.analyze()`，断言 `Media.Status`、`mediaType`、页数、扩展字段或错误注释。部分测试会用 MockK/SpringMockK 让 `EpubExtractor` 的某个方法抛异常，以验证系统是否能降级而不是整体失败。

## 小白阅读顺序

建议先读 `AutowiringTest.kt`，理解测试环境会启动完整 Spring 应用，并且 Komga 有多数据源/JOOQ context 的基础配置。

第二步读 `architecture/CodingRulesTest.kt`、`architecture/DomainDrivenDesignRulesTest.kt`、`architecture/SlicesIsolationRulesTest.kt`。这些文件比业务测试短，但能快速建立项目边界：领域模型不能反向依赖基础设施和接口层，Controller 必须在 interfaces 层，不同接口 slice 不应互相依赖。

第三步读 `domain/model` 下的模型测试，例如 `BookMetadataTest.kt`、`SeriesMetadataTest.kt`、`ContentRestrictionsTest.kt`。这些测试通常最接近业务概念，依赖少，适合理解 Komga 的书籍、系列、用户、限制规则和搜索条件。

第四步读 `domain/service/BookAnalyzerTest.kt`、`BookLifecycleTest.kt`、`LibraryLifecycleTest.kt`、`SeriesLifecycleTest.kt`。这里开始出现服务编排、文件分析、生命周期创建/删除等核心行为，是理解“书库扫描到数据库对象”的关键。

第五步读 `infrastructure/jooq/main/BookDaoTest.kt` 或相近 DAO 测试。重点看测试如何准备 library/series，如何调用 repository/DAO，如何清理数据。这能帮助理解领域对象如何落库。

第六步读 `interfaces/api/rest/BookControllerTest.kt`、`LibraryControllerTest.kt`、`SeriesControllerTest.kt`。这里能看到 HTTP API、权限、内容限制和 JSON 响应的最终表现。读完接口测试后，再回头看生产 controller/service，会更容易把请求链路串起来。

## 常见误区

不要把这个目录理解成“纯单元测试”。大量测试使用 `@SpringBootTest`，会加载 Spring 上下文、真实 bean、数据库配置或测试资源，更接近集成测试。阅读时要注意测试成本和上下文依赖。

不要忽略 `architecture` 目录。它不是辅助代码，而是项目设计规则的自动化表达。新增生产代码如果违反 DDD 包依赖或接口 slice 隔离，即使业务测试通过，也可能被这些测试拦下。

不要认为 `interfaces/api/rest` 只是在测 JSON 字段。以 `BookControllerTest.kt` 为例，它同时覆盖共享库权限、年龄分级限制、repository 数据准备、lifecycle service 行为和 HTTP 状态码，是端到端接口行为的压缩验证。

不要在 DAO 测试中只看单个方法断言。很多 DAO 测试依赖 `@BeforeAll`、`@AfterEach`、`@AfterAll` 的数据生命周期。若忽略清理逻辑，容易误判测试之间是否隔离。

不要把 `domain/model` 的测试看成低价值测试。领域模型测试往往最能说明业务规则，例如元数据、搜索条件、用户限制和内容过滤，这些规则会被 service、DAO 查询和 controller 权限共同复用。

不要把 `Utils.kt` 这类小工具当成生产 API。它位于 `src/test/kotlin`，只服务测试构造数据，例如把 `Map<Series, List<Book>>` 转成 `ScanResult`，不应从生产代码依赖它。
