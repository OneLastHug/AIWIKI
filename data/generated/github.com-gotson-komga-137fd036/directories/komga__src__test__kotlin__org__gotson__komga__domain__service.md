# 目录：komga/src/test/kotlin/org/gotson/komga/domain/service

## 它负责什么

这个目录不是业务实现，而是 `domain/service` 层的测试集合，主要用 `@SpringBootTest`、`MockkBean`、`SpykBean`、`Jimfs` 和仓库层数据来验证各个 service 的真实行为。  
从文件名看，它覆盖了 `BookAnalyzer`、`BookImporter`、`BookLifecycle`、`FileSystemScanner`、`KomgaUserLifecycle`、`LibraryContentLifecycle`、`LibraryLifecycle`、`MetadataAggregator`、`MetadataApplier`、`ReadListMatcher`、`SeriesLifecycle`、`SyncPointLifecycle`、`TransientBookLifecycle` 等服务。  
所以它的职责可以概括为：用接近集成测试的方式，检查 service 在文件系统、数据库仓库、阅读进度、元数据、系列/书籍/库生命周期上的规则是否成立。

## 关键组成

这里的核心不是“通用工具”，而是按服务一对一组织的测试类。直接子文件包括 `BookLifecycleTest.kt`、`LibraryLifecycleTest.kt`、`BookImporterTest.kt`、`MetadataAggregatorTest.kt` 等 13 个测试文件。

从片段里能看到几类典型依赖：

- Spring 测试注入：`@SpringBootTest`、`@Autowired`
- Mock/Spy：`@MockkBean`、`@SpykBean`
- 仓库层：`BookRepository`、`LibraryRepository`、`SeriesRepository`、`MediaRepository`、`ReadProgressRepository`、`ThumbnailBookRepository` 等
- 域模型工厂：`makeBook`、`makeSeries`、`makeLibrary`
- 文件系统测试：`Jimfs`、`TempDir`、`Files`、`Path`
- 断言与异常：`assertThat`、`catchThrowable`

其中 `MetadataAggregatorTest` 是明显的纯单元测试，直接 `MetadataAggregator()` 实例化；而 `BookLifecycleTest`、`BookImporterTest`、`LibraryLifecycleTest` 这类则更接近带上下文的行为测试。

## 上下游关系

上游是 `komga/src/main/kotlin/org/gotson/komga/domain/service` 下的生产代码，以及 `domain/model`、`domain/persistence`、`application/tasks` 等依赖。  
下游是这些测试本身对业务规则的“验收”：它们不向外提供 API，但会直接约束 service 的实现方式和副作用。

从已读片段可以明确几个映射：

- `BookLifecycleTest` 约束 `BookLifecycle` 在分析、删除文件、读进度修正上的行为，并通过 `BookAnalyzer`、`MediaRepository`、`ReadProgressRepository`、`ThumbnailBookRepository` 验证副作用。
- `LibraryLifecycleTest` 约束 `LibraryLifecycle` 的新增/更新校验，重点是路径存在性、目录合法性、名字重复、路径包含关系。
- `BookImporterTest` 约束 `BookImporter` 的导入流程，重点是源文件、目标冲突、库路径冲突，以及对 `TaskEmitter` 的调用。
- `MetadataAggregatorTest` 直接验证聚合规则，属于纯算法层，不依赖 Spring。

根据当前片段推断，这个目录是 domain service 层最主要的行为测试入口，其他模块改动如果碰到书籍导入、扫描、元数据、库生命周期，通常都会先撞到这里的断言。

## 运行/调用流程

典型流程很固定：

1. 先准备测试上下文，注入 service 和 repository。
2. 在 `@BeforeAll` 或 `@BeforeEach` 里插入库、用户、系列等基础数据。
3. 用 `makeBook`、`makeSeries`、`makeLibrary` 构造域对象，必要时借助 `Jimfs` 或 `@TempDir` 创建临时文件系统。
4. 调用目标 service，比如 `bookLifecycle.analyzeAndPersist(...)`、`libraryLifecycle.addLibrary(...)`、`bookImporter.importBook(...)`。
5. 断言仓库状态、文件是否被删除/创建、异常类型是否符合预期，或者 Mock/Spy 是否被调用。
6. 在 `@AfterEach`、`@AfterAll` 清理仓库和临时数据。

`BookLifecycleTest` 里还能看到更完整的链路：先造系列和书，再人为把 `Media` 标记成 `OUTDATED`，接着 mock `BookAnalyzer.analyze(...)`，最后检查 `ReadProgressRepository` 里的进度是否按页数变化被重置或保留。  
这说明这里的测试不是只看返回值，而是重点看“业务状态是否被正确改写”。

## 小白阅读顺序

建议按这个顺序看：

1. `MetadataAggregatorTest.kt`，先理解最纯的聚合规则，没有 Spring 干扰。
2. `LibraryLifecycleTest.kt`，看库的新增/更新校验，能快速建立“service 如何做防线”的直觉。
3. `BookImporterTest.kt`，理解导入流程、文件系统冲突和任务触发。
4. `BookLifecycleTest.kt`，看书籍分析、读进度、删除文件这些核心副作用。
5. 再看 `FileSystemScannerTest.kt`、`SeriesLifecycleTest.kt`、`LibraryContentLifecycleTest.kt`、`SyncPointLifecycleTest.kt` 等偏流程型测试。
6. 最后补 `MetadataApplierTest.kt`、`ReadListMatcherTest.kt`、`TransientBookLifecycleTest.kt`、`KomgaUserLifecycleTest.kt`，把周边规则补齐。

## 常见误区

- 容易把这里当成业务实现目录，其实它是测试目录，真正逻辑在 `komga/src/main/kotlin/org/gotson/komga/domain/service`。
- 容易只看断言不看 fixture。这个目录大量依赖仓库初始化、临时文件系统和 model 工厂，fixture 才是行为的前提。
- 容易忽略 `MockkBean` 和 `SpykBean` 的作用。它们不是装饰，通常是为了把外部协作者隔离开，或只替换局部行为。
- 容易把所有测试都当成同一种级别。实际上这里既有纯单元测试，比如 `MetadataAggregatorTest`，也有接近集成测试的 Spring 上下文测试。
- 容易只关注返回值，忽略副作用。这个目录最重要的断言往往是仓库内容、文件是否被删、读进度是否被重建、任务是否被触发。
