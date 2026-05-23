# 目录：komga/src/test/kotlin/org/gotson/komga/infrastructure

## 它负责什么

`komga/src/test/kotlin/org/gotson/komga/infrastructure` 是 Komga 后端 `infrastructure` 层的测试目录，主要验证“技术适配层”是否能正确支撑领域层和接口层。这里测试的不是单一业务用例，而是数据库访问、搜索索引、媒体文件解析、元数据导入、Kobo 转换、Web 请求参数兼容等基础能力。

从目录结构看，它对应主代码目录 `komga/src/main/kotlin/org/gotson/komga/infrastructure` 下的多个子模块。测试覆盖面大致分为三类：

第一类是 Spring 集成测试，例如 `datasource/DataSourcesConfigurationTest.kt`、`jooq/main/*DaoTest.kt`、`search/SearchIndexLifecycleTest.kt`、`kobo/KepubConverterTest.kt`。这些测试会启动 Spring 上下文，注入真实 Bean，验证配置、DAO、生命周期组件之间的配合。

第二类是偏单元的解析/转换测试，例如 `mediacontainer/epub/OpfTest.kt`、`metadata/comicrack/ComicInfoProviderTest.kt`、`web/BracketParamsRequestWrapperTest.kt`。这类测试通常构造输入对象或读取测试资源，验证某个函数或 Provider 的输出。

第三类是搜索分析器与工具类测试，例如 `search/MultilingualAnalyzerTest.kt`、`search/MultilingualNGramAnalyzerTest.kt`、`search/Utils.kt`、`jooq/TestUtils.kt`。它们确保底层分词、时间断言容差等行为稳定。

## 关键组成

`datasource` 目录目前有 `DataSourcesConfigurationTest.kt`，对应主代码 `DataSourcesConfiguration.kt`。它测试 SQLite 数据源在不同 profile 下的 Bean 关系：默认 WAL 模式中读写数据源和只读数据源应是不同实例；`test`、`memorydb` profile 下内存数据库的 RW/RO 数据源应是同一实例。这个测试关注的是 Spring Bean 装配结果，而不是 SQL 读写本身。

`jooq` 是最大的一组测试。`jooq/main` 下有 `BookDaoTest.kt`、`LibraryDaoTest.kt`、`SeriesDaoTest.kt`、`ReadProgressDaoTest.kt`、`ServerSettingsDaoTest.kt` 等，基本对应主代码里的 JOOQ DAO。以 `LibraryDaoTest.kt` 为例，它注入 `LibraryDao`，验证 `insert`、`update`、`delete`、`deleteAll`、`findAll` 等操作，并检查 `createdDate`、`lastModifiedDate`、导入开关、扫描配置、封面策略等字段是否正确持久化。`jooq/tasks/TasksDaoTest.kt` 则对应任务库相关 DAO。`jooq/TestUtils.kt` 提供 `offset`，用于断言时间字段在 3 秒容差内。

`search` 目录覆盖 Lucene 搜索能力。`MultilingualAnalyzerTest.kt` 验证 `MultiLingualAnalyzer` 对英文、重音字符、ISBN、单字母、中文、日文假名/片假名、韩文的分词结果。`SearchIndexLifecycleTest.kt` 是更高层的集成测试：它注入 `LibraryLifecycle`、`SeriesLifecycle`、`BookLifecycle`、`SeriesCollectionLifecycle`、`ReadListLifecycle`、多个 Repository、`SearchIndexLifecycle` 和 `LuceneHelper`，通过领域生命周期事件验证 Book、Series、Collection、ReadList 等实体被创建、更新、删除时，Lucene 索引能同步新增、更新或移除。

`kobo` 目录测试 Kobo 相关基础设施。`KepubConverterTest.kt` 注入 `KepubConverter`，用临时目录创建假的 `kepubify` 可执行文件，验证非 EPUB、已是 KEPUB、源文件不存在等非法输入会抛出 `IllegalArgumentException`，以及存在源文件但 dummy converter 无法真正转换时返回 `null`。`KomgaSyncTokenGeneratorTest.kt` 根据文件名可判断是验证 Kobo 同步 token 生成逻辑，具体细节需继续阅读该文件才能确认。

`mediacontainer` 目录测试文件容器解析。`epub` 下的 `OpfTest.kt` 使用 `ClassPathResource("epub/clash.opf")` 和 Jsoup XML parser，调用 `processOpfGuide`，验证 OPF guide/landmarks 能转成 `EpubTocEntry`，并且在有无目录前缀时路径都正确。`NavTest.kt`、`NcxTest.kt` 应分别覆盖 EPUB nav 和 NCX 目录解析。`divina` 下有 `RarExtractorTest.kt`、`ZipExtractorTest.kt`，`pdf` 下有 `PdfExtractorTest.kt`，根据当前片段推断它们验证不同媒体容器的页面/条目提取能力，依据是目录名和测试类名均与 extractor 对应。

`metadata` 目录测试元数据 Provider 和 DTO。`comicrack/ComicInfoProviderTest.kt` 是代表文件：它 mock `XmlMapper` 和 `BookAnalyzer`，构造 `ComicInfo`，然后验证 `ComicInfoProvider.getBookMetadataFromBook` 输出的 `BookMetadataPatch`。测试点包括标题、摘要、卷号、排序号、发布日期、ISBN、阅读列表、链接、标签大小写规范化，以及 StoryArc/StoryArcNumber 长度不一致或非法数字时的容错。其他子目录包括 `barcode`、`epub`、`localartwork`、`mylar`，分别对应 ISBN 条码、EPUB 元数据、本地封面、Mylar series 元数据。

`web` 目录目前有 `BracketParamsRequestWrapperTest.kt`。它使用 `MockHttpServletRequest` 验证 `BracketParamsRequestWrapper` 对 `param` 和 `param[]` 两种参数名的兼容：参数名统一成不带括号的形式，`getParameter` 会把两个来源的值合并成逗号字符串，`getParameterValues` 会返回合并数组，空参数返回 `null` 或空集合。

## 上下游关系

上游主要是领域模型、领域服务和测试资源。测试里频繁使用 `org.gotson.komga.domain.model` 下的 `makeBook`、`makeLibrary`、`makeSeries`、`BookWithMedia`、`Media`、`Library`、`SeriesCollection` 等对象，也会调用 `domain.service` 中的 `BookLifecycle`、`SeriesLifecycle`、`LibraryLifecycle`。这说明 infrastructure 测试不是孤立验证工具函数，而是在确认基础设施能承接领域层发出的读写、事件和解析需求。

中间层是被测 infrastructure 组件，包括 `DataSourcesConfiguration`、各类 JOOQ DAO、`SearchIndexLifecycle`、`LuceneHelper`、`MultiLingualAnalyzer`、`KepubConverter`、`ComicInfoProvider`、`processOpfGuide`、`BracketParamsRequestWrapper` 等。

下游则是实际外部技术：SQLite/JOOQ 数据库、Lucene 索引、EPUB/CBZ/PDF/RAR/ZIP 文件结构、XML 元数据、HTTP Servlet request、外部 `kepubify` 命令。测试通过 Spring、MockK、临时目录、ClassPath 测试资源和 mock 对象，把这些外部依赖控制在可重复的测试环境里。

## 运行/调用流程

典型 Spring 集成测试流程是：启动 `@SpringBootTest` 上下文，按构造函数或字段注入 Bean，构造领域对象，调用 DAO 或 lifecycle，再断言数据库、索引或返回值。例如 `SearchIndexLifecycleTest.kt` 在 `@BeforeAll` 中插入 library，并用 `MockkBean` 替换 `ApplicationEventPublisher`。当领域服务发布 `DomainEvent` 时，mock 会捕获事件并直接调用 `searchIndexLifecycle.consumeEvents`，随后通过 `luceneHelper.searchEntitiesIds` 验证索引内容。

典型 DAO 测试流程是：构造领域实体，调用 `insert`，再通过 `findById`、`findAll`、`count` 验证持久化结果；更新时先读取已持久化对象，`copy` 修改字段，再调用 `update`；清理阶段常用 `@AfterEach` 删除数据并断言 count 为 0。`LibraryDaoTest.kt` 就是这种模式。

典型解析类测试流程是：准备 XML、OPF、请求参数或 metadata DTO，调用 provider/parser/wrapper，再断言领域模型或 patch 对象。`ComicInfoProviderTest.kt` 通过 mock `XmlMapper.readValue` 直接返回构造好的 `ComicInfo`，因此测试重点放在 ComicInfo 到 Komga 领域补丁的映射规则，而不是 XML 反序列化本身。

## 小白阅读顺序

建议先读 `web/BracketParamsRequestWrapperTest.kt`。它依赖少，输入输出直观，能快速理解这个测试目录的风格：given/when/then 注释、AssertJ 断言、JUnit nested 分组。

第二步读 `search/MultilingualAnalyzerTest.kt`。它不需要理解 Spring 或数据库，只要看输入文本和 token 输出，就能明白 Komga 对多语言搜索的基础要求。

第三步读 `metadata/comicrack/ComicInfoProviderTest.kt`。这里开始接触领域模型映射，重点看 `ComicInfo` 字段如何变成 `BookMetadataPatch`，尤其是 ISBN、链接、标签、阅读列表的清洗和容错。

第四步读 `jooq/main/LibraryDaoTest.kt`。它能代表 JOOQ DAO 测试模式：插入、更新、删除、查询，以及时间字段断言。读完后再按需要看 `BookDaoTest.kt`、`SeriesDaoTest.kt`、`ReadProgressDaoTest.kt` 等。

第五步读 `search/SearchIndexLifecycleTest.kt`。这是跨 Repository、Lifecycle、DomainEvent、Lucene 的集成测试，适合在理解领域对象和 DAO 后阅读。重点不是每个断言，而是“领域事件如何驱动索引更新”。

最后读 `datasource/DataSourcesConfigurationTest.kt`、`kobo/KepubConverterTest.kt`、`mediacontainer/*`。这些更偏具体技术适配：数据库 profile、外部转换器、EPUB/PDF/压缩包解析。

## 常见误区

不要把这个目录理解成业务用例测试。它主要验证基础设施是否可靠，比如数据库字段是否落库、Lucene 索引是否随事件变化、文件元数据是否能解析成领域补丁。

不要以为所有测试都是单元测试。带 `@SpringBootTest` 的文件会启动 Spring 上下文，测试 Bean 装配和真实组件协作；而 `BracketParamsRequestWrapperTest.kt`、`MultilingualAnalyzerTest.kt` 这类更接近轻量单元测试。

不要忽略 profile 差异。`DataSourcesConfigurationTest.kt` 明确说明默认 WAL 模式和 `memorydb` 模式下数据源实例关系不同，这会影响测试数据库连接、事务和读写分离的理解。

不要把 mock 当成被测目标。比如 `ComicInfoProviderTest.kt` mock 了 `XmlMapper` 和 `BookAnalyzer`，因此它验证的是 `ComicInfoProvider` 的映射逻辑，不是 XML 文件读取是否成功。

不要只看文件名就判断覆盖充分。根据当前片段推断，`mediacontainer/divina`、`mediacontainer/pdf`、`metadata/mylar` 等目录分别测试对应解析器或 Provider，但具体边界条件仍需阅读各测试文件确认。文件名能提供模块地图，不能替代测试内容。

不要漏看测试数据来源。EPUB 相关测试使用 classpath 资源，例如 `epub/clash.opf`；Kobo 测试使用 `@TempDir` 创建临时文件；Web 测试使用 `MockHttpServletRequest`。理解这些输入来源，才能判断测试是在模拟真实文件、真实 Spring Bean，还是纯内存对象。
