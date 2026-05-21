# 目录：komga/src/test/kotlin

## 它负责什么

`komga/src/test/kotlin` 是 Komga 后端 Kotlin 测试代码的主体目录，覆盖从纯领域模型、领域服务、数据库 DAO、文件/元数据解析、搜索索引，到 REST/Kobo/OPDS/KOSync API 的行为验证。它不是单一类型的“单元测试目录”，而是混合了：

- 纯 Kotlin/JVM 逻辑测试，例如 `domain/model/*Test.kt`、部分 `infrastructure/metadata/*Test.kt`。
- Spring Boot 集成测试，例如 `domain/service/*Test.kt`、`infrastructure/jooq/**/*Test.kt`。
- Web/API 集成测试，例如 `interfaces/api/rest/*Test.kt`、`interfaces/api/kobo/KoboControllerTest.kt`。
- 架构规则测试，例如 `architecture/*Test.kt`，用 ArchUnit 把代码分层约束变成可执行测试。

从目录形态看，它的核心价值是：把 Komga 的 DDD 分层、持久化行为、外部接口契约和文件格式解析能力固定下来，防止重构或功能迭代破坏已有语义。

## 关键组成

直接包结构从 `org/gotson/komga` 展开，主要分为以下几类。

`AutowiringTest.kt` 是根级 Spring 上下文冒烟测试。它使用 `@SpringBootTest` 启动应用测试上下文，并注入 `List<DataSource>`、`List<DSLContext>`，验证应用能用测试属性启动，并且存在 4 个 datasource/DSL context。这个测试说明 Komga 测试环境不只是内存对象测试，还会真实组装数据库访问层。

`Utils.kt` 提供一个很小的测试扩展函数：`Map<Series, List<Book>>.toScanResult()`，用于把扫描得到的 series/book 映射快速转成 `ScanResult`。它服务于领域服务测试里的扫描/导入场景。

`architecture` 目录包含 ArchUnit 规则测试。`DomainDrivenDesignRulesTest.kt` 约束 `domain.model` 不依赖 `infrastructure`、`interfaces`、`domain.persistence`、`domain.service`，并要求名字包含 `Controller` 的类位于 `interfaces` 包。`SlicesIsolationRulesTest.kt` 约束 `interfaces` 下不同 slice 互不依赖。`CodingRulesTest.kt`、`NamingConventionTest.kt` 还会检查通用编码规则和命名约定。这里的测试不是测业务结果，而是测源码结构。

`domain/model` 是领域对象和搜索条件的测试区，例如 `AuthorTest.kt`、`BookMetadataTest.kt`、`SeriesMetadataTest.kt`、`KomgaUserTest.kt`、`ContentRestrictionsTest.kt`、`BookSearchTest.kt`、`SeriesSearchTest.kt`。这类测试通常不需要完整 Spring 上下文，重点验证模型默认值、约束、排序、搜索条件组合、语言标签、分页/过滤等领域语义。

`domain/service` 是业务生命周期和领域服务测试区，例如 `BookLifecycleTest.kt`、`SeriesLifecycleTest.kt`、`LibraryLifecycleTest.kt`、`BookImporterTest.kt`、`FileSystemScannerTest.kt`、`MetadataAggregatorTest.kt`、`ReadListMatcherTest.kt`、`SyncPointLifecycleTest.kt`。这些测试经常使用 `@SpringBootTest` 注入 repository/lifecycle/service，并用 `MockkBean`、`SpykBean` 替换或监控局部依赖。比如 `BookLifecycleTest.kt` 会插入 library/user/series/book，模拟 `BookAnalyzer.analyze()` 返回新的 `Media`，再断言阅读进度、文件删除、sidecar thumbnail 清理等副作用。

`infrastructure` 是适配层测试。`infrastructure/jooq/main` 覆盖主数据库 DAO，例如 `BookDaoTest.kt`、`SeriesDaoTest.kt`、`LibraryDaoTest.kt`、`ReadProgressDaoTest.kt`、`ServerSettingsDaoTest.kt`；`infrastructure/jooq/tasks/TasksDaoTest.kt` 覆盖任务库。`BookDaoTest.kt` 展示了典型模式：先通过 repository 插入 library/series，测试 `insert`、`update`、`findByIdOrNull`、`findAll`、搜索条件、按 library/series 查询、`deleteAll` 等 DAO 行为，并在 `AfterEach` 清理数据。

`infrastructure/mediacontainer` 测试媒体容器解析，包括 `divina` 的 rar/zip extractor、`epub` 的 `NavTest.kt`、`NcxTest.kt`、`OpfTest.kt`、`pdf/PdfExtractorTest.kt`。这些测试依赖 `komga/src/test/resources/archives`、`epub`、`pdf` 等测试样本，关注文件格式兼容性。

`infrastructure/metadata` 测试元数据来源，例如 ComicRack、EPUB、Mylar、本地封面、ISBN barcode。对应 DTO 测试位于 `comicrack/dto`、`mylar/dto`。它们验证 XML/EPUB/图片条码等外部格式能被转换为 Komga 内部元数据。

`infrastructure/search` 测试多语言 analyzer、NGram analyzer、搜索索引生命周期。根据当前片段推断，这里主要保障全文搜索、分词、索引创建/更新/删除的行为。

`interfaces` 是接口层测试。`interfaces/api/rest` 覆盖 REST controller，典型文件有 `BookControllerTest.kt`、`SeriesControllerTest.kt`、`LibraryControllerTest.kt`、`UserControllerTest.kt`、`SettingsControllerTest.kt`、`OAuth2ControllerTest.kt`。这些测试通常使用 `@SpringBootTest` 加 `@AutoConfigureMockMvc`，通过 `MockMvc` 发起 HTTP 请求并断言状态码和 JSON。`BookControllerTest.kt` 中可以看到有限用户、内容分级限制、共享库权限、书籍分页/查询等 API 行为。`MockSpringSecurity.kt` 提供测试用安全上下文注解/工具，例如 `WithMockCustomUser`。`interfaces/api/kobo`、`kosync`、`opds` 分别测试 Kobo 同步、KOReader 同步和 OPDS 接口；`interfaces/mvc` 覆盖传统 MVC 控制器，如资源不存在页面。

测试资源不在目标目录内，但与它强相关：`komga/src/test/resources/application-test.yml` 配置测试数据库文件位于临时目录，并启用 Flyway；`application-memorydb.yml` 提供 memorydb profile；`junit-platform.properties` 设置 `junit.jupiter.testinstance.lifecycle.default=per_class`，所以测试类可使用非静态的 `@BeforeAll`/`@AfterAll` 风格。`archives`、`barcode`、`epub`、`hashpage`、`pdf` 是文件解析和哈希测试的样本资产。

## 上下游关系

上游是生产代码和测试配置：`komga/src/main/kotlin` 下的 domain、application、infrastructure、interfaces 实现；`komga/src/test/resources` 下的 Spring/JUnit 配置和样本文件；`komga/build.gradle.kts` 中的测试依赖。当前片段能确认测试依赖包括 `spring-boot-starter-test`、`spring-security-test`、`springmockk`、`mockk`、`jimfs`、`archunit-junit5`。

下游是 Gradle/JUnit 执行链和 CI 质量门禁。测试类被 JUnit 5 发现后，普通测试直接执行断言；`@SpringBootTest` 测试会加载 Spring 容器、数据源、JOOQ DSLContext、repository、service；`@AutoConfigureMockMvc` 测试会额外装配 MockMvc 和安全过滤链；ArchUnit 测试会扫描 `Application` 所在包的生产类并检查依赖规则。

从业务依赖方向看，测试目录反向观察了所有生产层：

- `domain/model` 测模型自洽，不应依赖外层。
- `domain/service` 测领域服务如何调用 repository、analyzer、scanner、lifecycle。
- `infrastructure/jooq` 测 repository/DAO 对 SQLite/JOOQ 映射的正确性。
- `interfaces/api` 测 controller、security、DTO、service、repository 组合后的 HTTP 契约。
- `architecture` 反过来约束生产代码不能越层依赖。

## 运行/调用流程

整体运行通常通过 Gradle 的 test 任务触发，例如 `./gradlew :komga:test`。单个类可用 JUnit/Gradle filter，例如 `./gradlew :komga:test --tests org.gotson.komga.interfaces.api.rest.BookControllerTest`。

典型 Spring 集成测试流程是：

1. JUnit 发现 `*Test.kt`。
2. 遇到 `@SpringBootTest` 后启动 Komga 测试 ApplicationContext。
3. 测试配置加载临时 SQLite 数据库路径，Flyway 迁移创建 schema。
4. 构造函数注入 repository、DAO、lifecycle、MockMvc 等依赖。
5. `@BeforeAll` 插入基础数据，例如 library、user、series。
6. 测试体执行业务动作，例如调用 lifecycle、DAO、MockMvc HTTP 请求。
7. 使用 AssertJ、MockMvc matcher、MockK verify 断言结果。
8. `@AfterEach`/`@AfterAll` 清理库、用户、书籍、系列、阅读进度等数据。

典型非 Spring 测试流程更轻：直接构造领域模型、解析样本文件或 mock 外部对象，然后断言返回值。这类测试包括元数据 DTO、EPUB navigation、文件扫描规则、部分模型规则等。

架构测试流程不同：ArchUnit 读取生产 classpath，排除 test class，然后按包规则检查依赖方向、命名、通用编码约束。如果某个 controller 放错包、domain model 依赖 infrastructure，即使业务测试通过，架构测试仍会失败。

## 小白阅读顺序

1. 先看 `komga/src/test/kotlin/org/gotson/komga/AutowiringTest.kt`，理解测试环境会启动完整 Spring 上下文，并且 Komga 有多组 DataSource/DSLContext。

2. 再看 `komga/src/test/resources/application-test.yml` 和 `junit-platform.properties`，理解测试数据库、Flyway、JUnit 生命周期的默认设置。虽然它们不在目标目录，但解释了大量测试为什么能用 `@BeforeAll` 操作实例字段。

3. 看 `architecture/DomainDrivenDesignRulesTest.kt` 和 `architecture/SlicesIsolationRulesTest.kt`，先建立 Komga 的分层边界：domain model 不能依赖外层，interfaces slice 之间不能互相引用。

4. 看 `domain/model/BookMetadataTest.kt`、`SeriesMetadataTest.kt`、`KomgaUserTest.kt` 这一类简单模型测试，熟悉领域对象的默认值、copy/update 风格和 AssertJ 断言方式。

5. 看 `infrastructure/jooq/main/BookDaoTest.kt` 或 `SeriesDaoTest.kt`，理解 repository/DAO 测试如何准备 library/series，再验证数据库 CRUD 和搜索条件。

6. 看 `domain/service/BookLifecycleTest.kt`、`SeriesLifecycleTest.kt`、`LibraryLifecycleTest.kt`，理解业务生命周期如何串联 repository、文件系统、媒体分析、阅读进度和元数据。

7. 最后看 `interfaces/api/rest/BookControllerTest.kt`、`LibraryControllerTest.kt`、`UserControllerTest.kt`，理解 MockMvc 如何验证权限、内容限制、HTTP 状态码和 JSON 结构。

## 常见误区

不要把这个目录理解成“只测 controller”。实际上它覆盖了从纯模型到数据库、文件格式、搜索、API、架构规则的多层测试，是 Komga 后端行为规格的一部分。

不要以为所有测试都是快速单元测试。大量 `@SpringBootTest` 会启动 Spring 上下文和临时 SQLite/Flyway 环境，运行成本明显高于普通 Kotlin 测试。修改 DAO、repository、配置或 security 时，这些集成测试更能暴露问题。

不要忽略清理逻辑。很多测试通过 `@BeforeAll` 插入共享基础数据，再用 `@AfterEach` 或 `@AfterAll` 删除 series、library、user、read progress。新增测试如果漏清理，容易污染同类后续用例。

不要绕过 lifecycle 直接改 repository，除非测试目标就是 DAO。接口层和领域服务测试往往刻意调用 `SeriesLifecycle`、`BookLifecycle`、`LibraryLifecycle`，因为这些 service 会维护 metadata、media、thumbnail、read progress、权限等副作用。

不要把 ArchUnit 测试当成可有可无。`architecture` 目录把 DDD 约束写成测试，新增包、移动 controller、在 domain model 中引入 infrastructure 依赖，都可能触发失败。

不要随意替换测试 fixture。`komga/src/test/resources/archives`、`epub`、`pdf`、`barcode`、`hashpage` 中的文件用于覆盖真实格式差异，比如 encrypted archive、rar4/rar5、不同 zip 压缩算法、EPUB OPF/NCX/NAV、图片 hash。删除或压缩这些资源可能让解析类测试失去代表性。

不要误读 `@WithMockCustomUser`。它不是生产认证逻辑本身，而是接口测试里构造安全上下文的工具；真正要验证的是 controller 在不同角色、共享库、年龄限制、内容限制下返回的 HTTP 结果。
