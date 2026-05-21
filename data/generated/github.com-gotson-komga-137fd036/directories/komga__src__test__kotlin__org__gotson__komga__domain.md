# 目录：komga/src/test/kotlin/org/gotson/komga/domain

## 它负责什么

`komga/src/test/kotlin/org/gotson/komga/domain` 是 Komga 领域层的测试目录，主要验证 `org.gotson.komga.domain` 包下的领域模型和领域服务是否符合业务规则。它不是应用入口，也不直接提供运行时功能，而是通过 JUnit 5、AssertJ、MockK、Spring Boot Test、Jimfs 等测试工具，把核心领域行为固定下来，防止后续改动破坏书籍、系列、图书馆、用户、元数据、扫描、导入、生命周期管理等规则。

从结构看，它分成两个直接子目录：

- `model`：偏向纯领域对象、值对象、查询条件、校验器、扩展函数的单元测试。
- `service`：偏向领域服务、生命周期服务、导入扫描流程、元数据处理流程的集成或半集成测试。

这个目录的价值在于说明 Komga 的核心业务并不只靠数据库或 API 层保证，而是在领域层就有明确规则。例如 `BookMetadataTest` 验证 `BookMetadata` 创建时会修剪 `title`、`number` 的首尾空白；`MetadataAggregatorTest` 验证多本书的元数据聚合时如何选择摘要、发布日期、作者和标签；`BookImporterTest` 验证导入书籍时的文件冲突、路径归属、sidecar 文件复制、系列排序、媒体状态初始化等行为。

## 关键组成

`model` 子目录覆盖领域模型的基础规则：

- `AuthorTest.kt`：验证作者对象的规范化行为，通常涉及姓名、角色等字段的清理或等价判断。
- `BCP47TagValidatorTest.kt`：验证语言标签校验逻辑，围绕 BCP 47 language tag 的合法性。
- `BookMetadataTest.kt`：验证 `BookMetadata` 创建后字段会被标准化，例如 `title`、`number` 去除首尾空白。
- `BookSearchTest.kt`、`SeriesSearchTest.kt`：验证书籍和系列搜索条件对象的行为，通常用于持久化查询或服务层过滤。
- `ContentRestrictionsTest.kt`：验证内容访问限制模型。
- `KomgaUserTest.kt`：验证用户领域对象，例如邮箱、角色、权限、偏好等规则。
- `PageHashTest.kt`：验证页面哈希模型，可能用于重复页、相似页或缓存判断。
- `ProxyExtensionTest.kt`：验证代理相关扩展逻辑。
- `SeriesMetadataTest.kt`：验证系列元数据的字段规范化与业务规则。
- `Utils.kt`：提供测试工厂函数，如 `makeBook`、`makeSeries`、`makeLibrary`、`makeBookPage`，用于快速构造领域对象。这里使用 `TsidCreator` 生成测试 id，并通过 `URL("file:/...")` 构造文件型资源地址。

`service` 子目录覆盖领域服务流程：

- `BookAnalyzerTest.kt`：测试书籍分析逻辑，通常涉及媒体信息、页面、缩略图或文件内容解析结果。
- `BookImporterTest.kt`：测试书籍导入流程，是该目录中代表性较强的集成测试。它使用 `@SpringBootTest` 注入 `BookImporter`、`BookRepository`、`SeriesLifecycle`、`MediaRepository` 等真实 Bean，并用 `Jimfs` 创建内存文件系统模拟源文件和目标图书馆目录。
- `BookLifecycleTest.kt`、`SeriesLifecycleTest.kt`、`LibraryLifecycleTest.kt`、`LibraryContentLifecycleTest.kt`：测试书籍、系列、图书馆及其内容的创建、删除、排序、关联、级联清理等生命周期行为。
- `FileSystemScannerTest.kt`：测试文件系统扫描如何发现、更新或移除图书馆内容。
- `KomgaUserLifecycleTest.kt`：测试用户创建、更新、删除等生命周期规则。
- `MetadataAggregatorTest.kt`：测试 `MetadataAggregator` 如何把多本书的 `BookMetadata` 聚合成系列级或汇总级信息。样例中可见：作者和标签会去重；发布日期取更早的日期；摘要优先取有摘要的书，并记录对应的 `summaryNumber`。
- `MetadataApplierTest.kt`：测试元数据应用逻辑，即外部或聚合后的元数据如何写回领域对象。
- `ReadListMatcherTest.kt`：测试阅读列表和书籍、系列之间的匹配逻辑。
- `SyncPointLifecycleTest.kt`：测试同步点生命周期，可能服务于 OPDS、设备同步或外部客户端同步。
- `TransientBookLifecycleTest.kt`：测试临时书籍生命周期，通常和未正式入库、导入前分析或一次性处理相关。

## 上下游关系

这个测试目录的上游是生产代码中的领域模型和领域服务，主要位于同名包对应的 `komga/src/main/kotlin/org/gotson/komga/domain`。测试文件通过相同包名 `org.gotson.komga.domain.model` 或 `org.gotson.komga.domain.service` 直接访问领域类，因此很多测试像是领域层的“可执行规格”。

`model` 测试的直接上游是 `Book`、`Series`、`Library`、`BookMetadata`、`SeriesMetadata`、`Author`、`KomgaUser`、`BookSearch`、`SeriesSearch` 等领域类。它们通常不需要 Spring 容器，直接构造对象并断言字段、集合、校验结果或派生属性。

`service` 测试的上游更复杂，除了领域服务本身，还依赖 repository、event/task 组件和文件系统。以 `BookImporterTest.kt` 为例，它注入了 `BookImporter`、`BookRepository`、`BookLifecycle`、`ReadProgressRepository`、`LibraryRepository`、`SeriesRepository`、`SeriesLifecycle`、`MediaRepository`、`BookMetadataRepository`、`KomgaUserRepository`、`ReadListRepository`、`ReadListLifecycle`。这说明 `BookImporter` 不是简单复制文件，而是会影响书籍记录、系列排序、媒体状态、阅读进度、元数据、阅读列表以及后台任务。

下游方面，这些测试通常由 Gradle 测试任务调用，例如针对 `komga` 模块运行单元测试或集成测试。它们不被生产代码调用，但会影响开发者能否安全修改领域逻辑。若修改 `BookMetadata` 的初始化规则、`MetadataAggregator` 的聚合策略、`BookImporter` 的导入流程，相关测试会成为第一层反馈。

## 运行/调用流程

从单个模型测试看，流程比较直接：

1. 在测试方法中构造领域对象，例如 `BookMetadata(title = "  title  ", number = "  number  ", numberSort = 1F)`。
2. 领域对象的构造器、`init` 块、属性 setter 或扩展逻辑执行标准化。
3. 测试使用 `assertThat` 验证结果，例如 `metadata.title` 等于 `"title"`，`metadata.number` 等于 `"number"`。

从服务测试看，流程更接近真实业务链路。以 `BookImporterTest.kt` 为例：

1. `@SpringBootTest` 启动 Spring 测试上下文，注入真实领域服务和 repository。
2. `@BeforeAll` 创建基础数据，例如测试图书馆 `library` 和两个 `KomgaUser`。
3. `@BeforeEach` 用 `MockkBean` 设置 `TaskEmitter` 的行为，避免测试真的触发复杂后台任务，同时可以验证任务是否被调用。
4. 测试中用 `Jimfs.newFileSystem(Configuration.unix())` 创建内存文件系统，构造 `/source`、`/dest`、`/library/series` 等路径。
5. 调用领域服务，例如 `bookImporter.importBook(sourceFile, series, CopyMode.COPY)`。
6. 断言结果：文件是否存在、异常类型是否正确、repository 中的书籍数量和排序是否正确、`Media.Status` 是否为 `UNKNOWN`、sidecar 图片是否被复制、任务是否被触发。
7. `@AfterEach` 或 `@AfterAll` 清理 repository，避免测试之间互相污染。

`MetadataAggregatorTest.kt` 的调用流程则是纯服务单元测试：构造多个 `BookMetadata`，调用 `aggregator.aggregate(metadatas)`，再断言聚合结果。它不启动 Spring，也不访问数据库，适合快速理解单个领域算法。

## 小白阅读顺序

建议先读 `model/Utils.kt`。这个文件虽然不是测试用例，但它告诉你测试里常见的 `Book`、`Series`、`Library` 是怎么构造出来的。看到 `makeBook`、`makeSeries`、`makeLibrary` 后，再读其他测试会更容易理解对象之间的关系。

第二步读简单模型测试，例如 `model/BookMetadataTest.kt`、`model/SeriesMetadataTest.kt`、`model/AuthorTest.kt`。这些文件通常只有少量断言，适合熟悉 Komga 领域对象的基本约束：字段清理、默认值、集合去重、校验规则等。

第三步读搜索和权限相关测试，例如 `model/BookSearchTest.kt`、`model/SeriesSearchTest.kt`、`model/ContentRestrictionsTest.kt`、`model/KomgaUserTest.kt`。这些测试能帮助理解“用户能看什么”“查询条件如何表达”“搜索对象如何传给后续 repository 或服务”。

第四步读纯服务测试 `service/MetadataAggregatorTest.kt`、`service/ReadListMatcherTest.kt`、`service/MetadataApplierTest.kt`。这些文件通常业务含义强，但环境依赖较少，适合学习领域服务如何组合模型。

第五步再读生命周期和导入扫描类测试，例如 `service/BookImporterTest.kt`、`service/FileSystemScannerTest.kt`、`service/BookLifecycleTest.kt`、`service/SeriesLifecycleTest.kt`、`service/LibraryLifecycleTest.kt`。这些测试涉及 Spring 上下文、repository、文件系统、任务发送器和清理流程，信息量更大，但也最接近 Komga 的真实核心业务。

最后再看 `service/SyncPointLifecycleTest.kt`、`service/TransientBookLifecycleTest.kt` 等较专门的测试。根据当前片段推断，它们对应较具体的同步或临时资源场景，适合在理解主线的图书馆、系列、书籍流程之后再阅读。

## 常见误区

第一个误区是把这个目录当成生产代码入口。它实际上是测试规格目录，真正业务实现不在这里。阅读时应把测试名、构造数据和断言当成需求描述，再回到生产代码中找对应实现。

第二个误区是只看 `model`，忽略 `service`。Komga 的领域规则并不都写在单个 data class 里。导入、扫描、生命周期、元数据应用这类规则往往跨越多个 repository 和服务，必须结合 `service` 测试理解。

第三个误区是认为 `BookImporterTest.kt` 只是在测文件复制。根据测试片段，它还会验证源文件不存在、目标文件已存在、源文件是否位于已有 Komga library 内、导入后系列排序、媒体状态初始化、sidecar 图片导入、后台任务触发等行为。文件操作只是表象，核心是“导入一本书会如何改变领域状态”。

第四个误区是忽略测试工具对理解代码的帮助。`Jimfs` 表示测试在内存文件系统中模拟真实路径，不依赖本机磁盘；`MockkBean TaskEmitter` 表示测试关注任务是否被请求，而不是任务真实执行；`@SpringBootTest` 表示部分服务测试依赖完整 Spring 容器和真实 Bean 协作。

第五个误区是把 `Utils.kt` 里的默认值当成生产默认值。它们是测试工厂函数，例如默认 `libraryId = ""`、`seriesId = ""`、`URL("file:/...")`，主要是为了让测试数据构造更轻量，不一定代表真实业务创建对象时的完整流程。

第六个误区是读测试时忽略测试方法名。这个目录中的测试方法大量使用 Kotlin 反引号命名，例如 `given book when importing then book is imported and series is sorted`。这些名字本身就是 Given-When-Then 规格：给定什么条件，调用什么行为，应该得到什么结果。读懂方法名，通常就已经掌握了该测试的一半意图。
