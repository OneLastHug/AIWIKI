# 目录：komga/src/test

## 它负责什么

`komga/src/test` 是 Komga 后端模块的测试目录，主要用于验证应用在测试环境下的启动、领域模型规则、业务服务行为、基础设施适配、数据库访问、搜索索引、媒体解析、元数据解析以及 HTTP API 行为。

从目录结构看，它不是某个单独功能的测试集合，而是整个 `komga` Spring Boot 应用的测试套件。测试代码放在 `komga/src/test/kotlin`，测试配置和样本资源放在 `komga/src/test/resources`。包名从 `org.gotson.komga` 开始，基本镜像主代码的分层结构：`domain`、`application`、`infrastructure`、`interfaces`，再加上 `architecture` 这种专门用于架构约束的测试包。

这个目录承担几类职责：

1. 验证 Spring Boot 应用能在测试 profile 下正常加载，例如 `AutowiringTest.kt`。
2. 验证领域模型和领域服务的纯业务逻辑，例如 `domain/model`、`domain/service` 下的测试。
3. 验证数据库 DAO、jOOQ 查询、数据源配置和迁移行为，例如 `infrastructure/jooq`、`infrastructure/datasource`。
4. 验证外部格式解析能力，例如 EPUB、PDF、RAR、ZIP、ComicInfo、Mylar、ISBN barcode 等。
5. 验证 REST、OPDS、Kobo、KOReader Sync 等接口层行为，例如 `interfaces/api/rest`、`interfaces/api/opds`、`interfaces/api/kobo`。
6. 通过 ArchUnit 固化代码架构规则，防止包依赖和命名边界被破坏，例如 `architecture/DomainDrivenDesignRulesTest.kt`。

## 关键组成

`komga/src/test/kotlin/org/gotson/komga/AutowiringTest.kt` 是一个很小但很关键的 Spring Boot 集成测试。它使用 `@SpringBootTest` 启动应用上下文，并注入 `List<DataSource>` 和 `List<DSLContext>`。其中一个测试只要求应用能加载，另一个测试断言 `dataSources` 和 `dslContexts` 都是 4 个。这说明 Komga 在测试环境下不只使用一个数据库上下文，而是预期存在多组数据源和 jOOQ 上下文。这个测试可以看作“测试环境总装检查”。

`komga/src/test/kotlin/org/gotson/komga/Utils.kt` 提供了一个测试辅助扩展函数：

```kotlin
fun Map<Series, List<Book>>.toScanResult() = ScanResult(this, emptyList())
```

它把 `Map<Series, List<Book>>` 快速包装成 `ScanResult`。这类工具一般服务于扫描、导入、生命周期类测试，减少构造领域对象时的样板代码。

`komga/src/test/kotlin/org/gotson/komga/architecture` 是架构规则测试目录。代表文件 `DomainDrivenDesignRulesTest.kt` 使用 ArchUnit，并通过 `@AnalyzeClasses(packagesOf = [Application::class], importOptions = [ImportOption.DoNotIncludeTests::class])` 分析主应用代码，但排除测试代码。它包含两条规则：第一，`..domain..model..` 下的类不能依赖 `..infrastructure..`、`..interfaces..`、`..domain.persistence..`、`..domain.service..` 等包；第二，名字包含 `Controller` 的类必须位于 `..interfaces..` 包下。这说明项目有明确的 DDD 分层约束：领域模型要保持干净，接口层控制器不能散落到其他层。

`komga/src/test/kotlin/org/gotson/komga/domain/model` 主要测试领域对象和值对象，例如 `AuthorTest.kt`、`BookMetadataTest.kt`、`SeriesMetadataTest.kt`、`PageHashTest.kt`、`ContentRestrictionsTest.kt`、`KomgaUserTest.kt`。这类测试通常不需要完整 Spring 容器，重点是验证构造、归一化、比较、校验、搜索条件对象等规则。

`komga/src/test/kotlin/org/gotson/komga/domain/service` 覆盖领域服务和业务流程，例如 `BookAnalyzerTest.kt`、`BookImporterTest.kt`、`FileSystemScannerTest.kt`、`LibraryLifecycleTest.kt`、`BookLifecycleTest.kt`、`SeriesLifecycleTest.kt`、`MetadataAggregatorTest.kt`、`MetadataApplierTest.kt`、`ReadListMatcherTest.kt`。这些测试更接近 Komga 的核心业务：扫描文件系统、分析书籍、导入媒体、维护 library/series/book 生命周期、聚合和应用元数据、匹配阅读列表等。

`komga/src/test/kotlin/org/gotson/komga/infrastructure/jooq` 是数据库访问层测试。`main` 子目录下有大量 DAO 测试，例如 `BookDaoTest.kt`、`SeriesDaoTest.kt`、`LibraryDaoTest.kt`、`ReadListDaoTest.kt`、`ReadProgressDaoTest.kt`、`KomgaUserDaoTest.kt`、`ServerSettingsDaoTest.kt`。`tasks` 子目录下有 `TasksDaoTest.kt`。根据文件名和测试配置推断，这些测试会在测试数据库上跑 Flyway 迁移，再通过 jOOQ 的 `DSLContext` 验证数据读写、搜索、分页、排序、聚合等行为。

`komga/src/test/kotlin/org/gotson/komga/infrastructure/mediacontainer` 负责媒体容器解析相关测试。`divina` 下有 `RarExtractorTest.kt`、`ZipExtractorTest.kt`，`epub` 下有 `NavTest.kt`、`NcxTest.kt`、`OpfTest.kt`，`pdf` 下有 `PdfExtractorTest.kt`。这些测试依赖 `komga/src/test/resources` 下的样本文件，例如 `archives`、`epub`、`pdf`。

`komga/src/test/kotlin/org/gotson/komga/infrastructure/metadata` 覆盖元数据来源解析：`barcode/IsbnBarcodeProviderTest.kt`、`comicrack/ComicInfoProviderTest.kt`、`comicrack/ReadListProviderTest.kt`、`epub/EpubMetadataProviderTest.kt`、`localartwork/LocalArtworkProviderTest.kt`、`mylar/MylarSeriesProviderTest.kt`。这些测试对应 Komga 从文件内嵌信息、旁路文件、条码、EPUB 元数据、ComicRack XML、Mylar 信息中提取业务元数据的能力。

`komga/src/test/kotlin/org/gotson/komga/interfaces/api` 是接口层测试。它分为 `rest`、`opds`、`kobo`、`kosync` 等子目录，说明 Komga 对外暴露多套协议或 API：常规 REST API、OPDS、Kobo 同步、KOReader Sync。`interfaces/api/rest/MockSpringSecurity.kt` 是 REST 测试的安全上下文辅助文件，用来模拟认证和授权场景。

`komga/src/test/resources/application-test.yml` 是主要测试 profile 配置。它把 `application.version` 设置为 `TESTING`，配置 `komga.database.file` 和 `komga.tasks-db.file` 为临时目录下带随机 UUID 的 SQLite 文件，并启用 Flyway。日志中 `org.gotson.komga` 为 `DEBUG`。这说明默认测试更偏向真实 SQLite 文件数据库，而不是简单 mock。

`komga/src/test/resources/application-memorydb.yml` 是内存数据库配置，把主数据库和任务数据库指向 SQLite memory URI：`file:database?mode=memory` 和 `file:tasks?mode=memory`。它适合更轻量的测试场景，但是否被具体测试启用，需要继续查看对应测试注解才能确认。

`komga/src/test/resources/junit-platform.properties` 设置：

```properties
junit.jupiter.testinstance.lifecycle.default=per_class
```

这表示 JUnit Jupiter 默认每个测试类只创建一个实例，而不是每个测试方法创建一个实例。Kotlin 构造器注入、昂贵资源初始化、Spring 测试上下文复用等场景都会受这个设置影响。

构建脚本 `komga/build.gradle.kts` 中与测试相关的依赖包括 `spring-boot-starter-test`、`spring-security-test`、`springmockk`、`mockk`、`jimfs`、`archunit-junit5`，并使用 `useJUnitPlatform()`。这说明测试技术栈是 JUnit 5 + AssertJ/Spring Test + MockK + Spring Security Test + ArchUnit，部分文件系统测试可能使用 Google Jimfs 提供内存文件系统。

## 上下游关系

上游输入主要有三类。

第一类是主代码。测试包名直接对应主代码分层，例如 `domain/service/BookImporterTest.kt` 对应书籍导入服务，`infrastructure/jooq/main/BookDaoTest.kt` 对应数据库 DAO，`interfaces/api/rest/BookControllerTest.kt` 对应 REST 控制器。测试通过实例化对象、启动 Spring 上下文、注入 Bean 或调用 HTTP 测试工具来驱动主代码。

第二类是测试配置。`application-test.yml`、`application-memorydb.yml` 和 `junit-platform.properties` 决定测试运行时的数据库、Flyway、日志和 JUnit 生命周期。尤其是数据库文件路径使用 `${java.io.tmpdir}` 和 `${random.uuid}`，可以降低测试之间互相污染的概率。

第三类是样本资源。`resources/archives`、`resources/barcode`、`resources/epub`、`resources/hashpage`、`resources/io`、`resources/pdf` 等目录为媒体解析、元数据读取、哈希计算、文件系统扫描等测试提供真实或精简样本。

下游输出不是生产代码，而是测试结果和架构反馈。普通单元测试失败通常表示业务规则或解析逻辑被破坏；DAO 测试失败可能表示数据库 schema、jOOQ 查询或迁移逻辑不一致；接口测试失败说明 API 合约、认证授权或序列化响应有变化；ArchUnit 测试失败则说明代码依赖方向或包命名规则被破坏。

这个测试目录和主工程的关系很紧：它不只是验证函数结果，还在持续约束 Komga 的整体架构。例如 `DomainDrivenDesignRulesTest.kt` 明确要求 `domain.model` 不能依赖基础设施和接口层，这会阻止开发者把数据库、Web、Spring Controller 等概念引入核心领域模型。

## 运行/调用流程

从 Gradle 角度，`komga/build.gradle.kts` 中测试任务使用 `useJUnitPlatform()`，因此 JUnit 5 平台会发现并执行 `src/test/kotlin` 下的测试类。测试依赖包含 Spring Boot Test、Spring Security Test、MockK、ArchUnit、Jimfs 等，运行时会按测试类上的注解决定是普通 JVM 测试、Spring 集成测试、架构测试，还是接口层测试。

典型流程可以理解为：

1. Gradle 启动 `test` 任务。
2. JUnit Platform 根据 classpath 扫描测试类。
3. `junit-platform.properties` 生效，测试实例生命周期默认为 `per_class`。
4. 如果测试使用 `@SpringBootTest`，Spring Boot 会加载应用上下文，并读取测试 profile 下的配置。
5. `application-test.yml` 配置测试数据库、任务数据库、Flyway 和日志。
6. 数据访问测试通过 DAO 或 `DSLContext` 操作数据库，验证读写结果。
7. 服务测试调用 domain/application service，可能配合 mock、临时文件系统或样本资源。
8. 接口测试通过 Spring MVC/Web 测试设施和安全 mock 调用 Controller。
9. 架构测试通过 ArchUnit 分析主代码字节码，检查包依赖和命名规则。

以 `AutowiringTest.kt` 为例，它启动完整 Spring Boot 测试上下文，然后要求应用能加载，并断言存在 4 个 `DataSource` 和 4 个 `DSLContext`。这个流程验证的不是业务细节，而是测试环境下 Bean 装配是否完整，尤其是多数据源和 jOOQ 配置是否符合预期。

以 `architecture/DomainDrivenDesignRulesTest.kt` 为例，它不会启动业务流程，而是扫描主应用包下的类。它把“领域模型不能依赖基础设施/接口层”这种设计原则变成自动化测试。如果某个开发者在 `domain.model` 中 import 了 `infrastructure` 包里的类，这个测试就会失败。

## 小白阅读顺序

建议先从根部三个文件看起：`komga/src/test/resources/application-test.yml`、`komga/src/test/resources/application-memorydb.yml`、`komga/src/test/resources/junit-platform.properties`。它们解释了测试为什么会使用 SQLite 临时数据库、什么时候可能使用内存库，以及 JUnit 实例生命周期为什么是 per-class。

第二步看 `komga/src/test/kotlin/org/gotson/komga/AutowiringTest.kt`。这个文件短，但能帮助你理解 Komga 测试不是纯单元测试集合，而是会启动 Spring Boot 上下文，并且应用内部有多数据源、多 `DSLContext` 的设计。

第三步看 `komga/src/test/kotlin/org/gotson/komga/architecture/DomainDrivenDesignRulesTest.kt`，再浏览同目录下的 `CodingRulesTest.kt`、`NamingConventionTest.kt`、`SlicesIsolationRulesTest.kt`。这些文件告诉你项目希望维持怎样的架构边界，比直接看业务测试更容易建立整体地图。

第四步看 `domain/model`。这里通常是最容易理解的测试，重点是领域对象的属性、校验、归一化和搜索条件。比如可以从 `AuthorTest.kt`、`BookMetadataTest.kt`、`SeriesMetadataTest.kt` 这类文件开始。

第五步看 `domain/service`。这里开始进入业务流程，建议按 Komga 的核心业务顺序读：`FileSystemScannerTest.kt`、`BookAnalyzerTest.kt`、`BookImporterTest.kt`、`LibraryLifecycleTest.kt`、`SeriesLifecycleTest.kt`、`BookLifecycleTest.kt`、`MetadataAggregatorTest.kt`、`MetadataApplierTest.kt`。

第六步看 `infrastructure/mediacontainer` 和 `infrastructure/metadata`。它们能帮助你理解 Komga 如何从真实文件里读取内容和元数据。配合 `resources/epub`、`resources/pdf`、`resources/archives`、`resources/barcode` 看，会更容易把测试输入和断言联系起来。

第七步看 `infrastructure/jooq/main`。这部分文件多，适合在理解领域模型之后阅读。建议从 `LibraryDaoTest.kt`、`SeriesDaoTest.kt`、`BookDaoTest.kt` 开始，再看 `ReadProgressDaoTest.kt`、`ReadListDaoTest.kt`、`BookSearchTest.kt`、`SeriesSearchTest.kt`。

最后看 `interfaces/api/rest`、`interfaces/api/opds`、`interfaces/api/kobo`、`interfaces/api/kosync`。接口层测试往往需要你已经理解领域对象、数据库状态、安全上下文和序列化格式，否则容易只看到一堆请求和断言，不知道背后的业务含义。

## 常见误区

第一个误区是把 `komga/src/test` 当成纯单元测试目录。实际上这里有不少集成测试，会启动 Spring Boot、连接 SQLite、运行 Flyway、注入 jOOQ `DSLContext`，也会测试 HTTP Controller 和安全行为。读这些测试时要区分“无 Spring 的模型测试”和“带完整上下文的集成测试”。

第二个误区是忽略 `application-test.yml`。很多测试行为不是写在测试类里的，而是来自测试 profile 配置。例如数据库路径、任务数据库路径、Flyway 是否启用、日志级别都在这里。看到 DAO 或 Spring 测试时，应先确认它使用的是文件 SQLite、内存 SQLite，还是 mock。

第三个误区是只看 `domain/service`，不看 `architecture`。`architecture` 目录里的 ArchUnit 测试表达了项目的长期约束：领域模型不能依赖基础设施和接口层，Controller 应该位于 interfaces 包。这些规则解释了为什么某些类放在特定包里，也解释了为什么业务对象不能随意引用 Spring、Web 或数据库类。

第四个误区是认为 `resources` 只是普通 fixture。这里的 `archives`、`epub`、`pdf`、`barcode`、`hashpage` 等资源直接影响媒体解析、元数据读取、哈希计算和文件扫描测试。修改或删除这些样本资源，可能导致看似无关的解析测试失败。

第五个误区是混淆 `domain/model/BookSearchTest.kt` 和 `infrastructure/jooq/main/BookSearchTest.kt`。前者更可能测试搜索条件、领域查询对象或模型规则；后者更可能测试数据库查询实现。类似地，`SeriesSearchTest.kt` 也在 domain 和 jOOQ 层各有一个版本，阅读时要注意所在包名。

第六个误区是忽略 `junit-platform.properties` 中的 `per_class`。JUnit 默认通常是每个方法创建测试实例，但这里改成每个类一个实例。测试类中的共享状态、构造器注入、初始化成本和方法之间的状态清理都可能受影响。读测试时如果看到成员变量被多个测试方法使用，不要直接套用默认 JUnit 生命周期来理解。

第七个误区是看到 `AutowiringTest.kt` 断言 4 个 `DataSource` 和 4 个 `DSLContext` 就认为它在测试业务。它真正测试的是应用上下文和基础设施装配，尤其是多数据库上下文是否完整。业务正确性要去 `domain/service`、`infrastructure/jooq` 和 `interfaces/api` 下找对应测试。
