# 文件：komga/src/test/kotlin/org/gotson/komga/domain/service/TransientBookLifecycleTest.kt

## 它负责什么

`TransientBookLifecycleTest.kt` 是 `TransientBookLifecycle.getMetadata` 的 Spring 集成测试文件，重点验证“临时书籍”在导入前分析元数据时，如何根据书内元数据匹配已有 `Series`，并提取卷号/排序号。

这里的“临时书籍”对应生产模型 `TransientBook`，它不是已经入库的正式 `Book`，而是导入流程中扫描到、等待分析和归类的书籍文件。生产代码中，`TransientBookLifecycle.analyzeAndPersist` 会先调用 `BookAnalyzer` 分析媒体信息，再调用 `getMetadata` 推断：

- `number`：书籍在系列中的排序号，来自 `BookMetadataProvider.getBookMetadataFromBook(...).numberSort`
- `seriesId`：匹配到的已有系列 ID，来自 `SeriesMetadataFromBookProvider.getSeriesMetadataFromBook(...).title` 再查 `SeriesRepository`

这个测试文件不测试完整扫描、文件分析、页面读取等行为，而是把焦点压缩在 `getMetadata` 的匹配规则上：当 metadata provider 返回某个系列名时，系统应该优先做精确匹配；当系列名为空或空白时，不应该误匹配任何系列。

## 关键组成

测试类：

`TransientBookLifecycleTest`

它使用 `@SpringBootTest` 启动 Spring 测试上下文，因此这不是纯单元测试，而是带有真实 Spring Bean、真实 repository/lifecycle 协作的集成测试。构造函数注入了四个核心依赖：

- `SeriesLifecycle`：用于在测试前创建、测试后删除系列。
- `SeriesRepository`：用于查询当前已创建的系列，主要配合清理数据。
- `LibraryRepository`：用于插入和删除测试用 library。
- `TransientBookLifecycle`：被测对象，测试直接调用它的 `getMetadata` 方法。

测试中还有一个特殊依赖：

`@SpykBean private lateinit var mockProvider: ComicInfoProvider`

`@SpykBean` 会把 Spring 容器中的 `ComicInfoProvider` 替换成 spy bean。它仍然是应用上下文的一部分，但测试可以用 MockK 的 `every { ... } returns ...` 覆盖指定方法的返回值。

这里 mock 的两个方法分别是：

- `ComicInfoProvider.getBookMetadataFromBook(any())`
- `ComicInfoProvider.getSeriesMetadataFromBook(any(), any())`

它们对应生产接口：

- `BookMetadataProvider`
- `SeriesMetadataFromBookProvider`

生产代码中 `TransientBookLifecycle` 接收的是 provider 列表，而不是直接依赖 `ComicInfoProvider`。测试选择 spy `ComicInfoProvider`，是因为它是实际参与 Spring 注入的 metadata provider 之一。

测试生命周期方法：

`setup library`

在 `@BeforeAll` 中调用 `libraryRepository.insert(library)`，先创建一个测试 library。后续创建 series 时都使用同一个 `library.id`。

`teardown`

在 `@AfterAll` 中调用 `libraryRepository.deleteAll()`，删除所有 library。

`cleanup`

在 `@AfterEach` 中调用：

`seriesLifecycle.deleteMany(seriesRepository.findAll())`

每个测试结束后清空已创建的 series，避免测试之间互相污染。注意 library 只在整个测试类开始和结束时处理，series 则每个测试后处理。

测试数据工厂：

- `makeLibrary()`：创建测试用 library。
- `makeSeries(...)`：创建测试用 series。
- `makeBook("whatever")`：创建测试用 book。
- `Media()`：创建空媒体信息。
- `TransientBook(makeBook("whatever"), Media())`：构造临时书籍对象。

被测返回值：

`val (seriesId, number) = transientBookLifecycle.getMetadata(book)`

`getMetadata` 返回 `Pair<String?, Float?>`，第一个值是匹配到的 `seriesId`，第二个值是 `numberSort`。

三个测试用例：

`when getting metadata for transient book then the most specific series name is matched first`

这个用例创建三个系列：

- `Batman and Robin`
- `Batman`
- `Batman and Robin (2022)`

然后 mock provider 返回：

- book metadata 的 `numberSort = 15F`
- series metadata 的 `title = "BATMAN"`

最后断言：

- `seriesId` 等于 `Batman` 这个精确系列的 ID
- `number` 等于 `15F`

这个测试实际保护的是“精确匹配优先于包含匹配”。如果生产逻辑只做 contains 搜索，`BATMAN` 可能匹配到 `Batman and Robin`、`Batman`、`Batman and Robin (2022)` 等多个系列，结果依赖仓库返回顺序，容易错配。当前生产逻辑会先用 `SearchOperator.Is` 做精确查找，有精确结果就直接取第一个精确结果；只有精确结果为空时，才退回 `SearchOperator.Contains`。

`when getting metadata for transient book without series then no series is matched`

这个用例仍然创建相同的三个系列，但 mock provider 返回：

- book metadata 没有 `numberSort`
- series metadata 的 `title = null`

最后断言：

- `seriesId == null`
- `number == null`

它验证当 provider 没有提供系列标题时，`getMetadata` 不应该进行任何 series 匹配，也不应该返回偶然命中的系列。

`when getting metadata for transient book with blank series then no series is matched`

这个用例与第二个类似，但 series metadata 的 `title` 返回 `" "`，也就是空白字符串。

生产代码中对 title 做了：

`title?.ifBlank { null }`

因此空白字符串会被转成 `null`，不会进入后续搜索条件。最后同样断言：

- `seriesId == null`
- `number == null`

这个用例保护的是空白 metadata 的边界行为，避免因为空字符串或空白字符串触发宽泛查询。

## 上下游关系

上游入口主要在 REST 导入流程中。

`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/TransientBooksController.kt`

该控制器提供 `api/v1/transient-books` 下的接口，且要求 `ADMIN` 权限。

相关入口包括：

- `scanTransientBooks`：调用 `transientBookLifecycle.scanAndPersist(request.path)`，扫描某个文件夹中的临时书籍。
- `analyzeTransientBook`：根据 transient book ID 从 `TransientBookRepository` 查出对象，然后调用 `transientBookLifecycle.analyzeAndPersist(it)`。
- `getPageByTransientBookId`：调用 `transientBookLifecycle.getBookPage(...)` 获取临时书籍页面内容。

本测试覆盖的是 `analyzeTransientBook` 背后会间接使用的 metadata 推断逻辑。具体链路是：

`TransientBooksController.analyzeTransientBook`
调用 `TransientBookRepository.findByIdOrNull(id)`
再调用 `TransientBookLifecycle.analyzeAndPersist`
然后 `analyzeAndPersist` 调用 `BookAnalyzer.analyze`
接着调用 `TransientBookLifecycle.getMetadata`
最后保存带有 `TransientBook.Metadata(number, seriesId)` 的 transient book。

被测类位于：

`komga/src/main/kotlin/org/gotson/komga/domain/service/TransientBookLifecycle.kt`

它的核心依赖包括：

- `TransientBookRepository`：保存扫描和分析后的 transient book。
- `BookAnalyzer`：分析书籍媒体信息，也负责页面内容读取。
- `FileSystemScanner`：扫描目录，找到可导入书籍。
- `LibraryRepository`：用于校验扫描路径不能位于已有 library 内。
- `SeriesRepository`：根据 metadata 推断出的系列名查询已有系列。
- `SeriesMetadataFromBookProvider` 列表：从书籍内容中提取系列 metadata。
- `BookMetadataProvider` 列表：从书籍内容中提取书籍 metadata。
- `ImageType pdfImageType`：读取 PDF 页面时决定返回媒体类型。

被测方法 `getMetadata` 的下游是 `SeriesRepository.findAll(...)`。它构造两类搜索条件：

- 精确匹配：`SearchCondition.Title(SearchOperator.Is(it))`
- 包含匹配：`SearchCondition.Title(SearchOperator.Contains(it))`

并且使用：

`SearchContext.ofAnonymousUser()`

说明这里的匹配不依赖当前登录用户上下文，而是在导入分析阶段用匿名搜索上下文做内部查询。

元数据 provider 的上游接口位于：

`komga/src/main/kotlin/org/gotson/komga/infrastructure/metadata/BookMetadataProvider.kt`

`BookMetadataProvider` 暴露：

`fun getBookMetadataFromBook(book: BookWithMedia): BookMetadataPatch?`

并带有：

`val capabilities: Set<BookMetadataPatchCapability>`

`TransientBookLifecycle` 在构造时会过滤 book metadata provider：

`bookMetadataProviders.filter { it.capabilities.contains(BookMetadataPatchCapability.NUMBER_SORT) }`

所以只有声明支持 `NUMBER_SORT` 的 provider 才会参与 `numberSort` 提取。

另一个接口位于：

`komga/src/main/kotlin/org/gotson/komga/infrastructure/metadata/SeriesMetadataFromBookProvider.kt`

`SeriesMetadataFromBookProvider` 暴露：

`fun getSeriesMetadataFromBook(book: BookWithMedia, appendVolumeToTitle: Boolean): SeriesMetadataPatch?`

并带有：

`val supportsAppendVolume: Boolean`

生产代码中，如果 provider 支持 `appendVolumeToTitle`，会先用 `true` 调一次，再用 `false` 调一次。这样可以得到多个候选系列名，例如“系列名 + 卷信息”和“原始系列名”。测试中 mock 使用 `any()` 覆盖第二个参数，因此不关心具体传入的是 `true` 还是 `false`。

模型关系：

`komga/src/main/kotlin/org/gotson/komga/domain/model/TransientBook.kt`

`TransientBook` 包含：

- `book: Book`
- `media: Media`
- `metadata: Metadata = Metadata()`

其中 `Metadata` 包含：

- `number: Float?`
- `seriesId: String?`

扩展函数：

`fun TransientBook.toBookWithMedia() = BookWithMedia(book, media)`

`getMetadata` 一开始就把 `TransientBook` 转成 `BookWithMedia`，因为 metadata provider 处理的是 `BookWithMedia`，不是 `TransientBook` 本身。

## 运行/调用流程

以第一个测试为例，完整流程如下：

1. 测试启动 Spring 上下文，构造真实的 `TransientBookLifecycle`、repository 和 lifecycle bean。
2. `@BeforeAll` 插入一个测试 library。
3. 测试方法创建三个 series，并通过 `seriesLifecycle.createSeries(...)` 持久化。
4. 测试构造一个 `TransientBook`，内部 book 名称是 `whatever`，media 是空 `Media()`。
5. 测试用 MockK 覆盖 `ComicInfoProvider.getBookMetadataFromBook`，让它返回带 `numberSort = 15F` 的 `BookMetadataPatch`。
6. 测试用 MockK 覆盖 `ComicInfoProvider.getSeriesMetadataFromBook`，让它返回 `title = "BATMAN"` 的 `SeriesMetadataPatch`。
7. 调用 `transientBookLifecycle.getMetadata(book)`。
8. `getMetadata` 把 `TransientBook` 转为 `BookWithMedia`。
9. `getMetadata` 遍历支持 `NUMBER_SORT` 的 `BookMetadataProvider`，取第一个非空 `numberSort`，得到 `15F`。
10. `getMetadata` 遍历 `SeriesMetadataFromBookProvider`，收集非空、非空白的 series title，得到候选名 `BATMAN`。
11. `getMetadata` 先构造 exact search，也就是 `Title(Is("BATMAN"))`。
12. `SeriesRepository.findAll(...)` 找到精确匹配的 `Batman` 系列。
13. 因为 exact match 不为空，生产代码不会再走 contains search。
14. `getMetadata` 返回 `seriesExact.id to 15F`。
15. 测试断言返回的 `seriesId` 是 `Batman` 的 ID，`number` 是 `15F`。
16. `@AfterEach` 删除本次测试创建的 series。

第二、第三个测试的流程相同，但 metadata provider 返回的 series title 分别是 `null` 和 `" "`。生产代码收集候选名时会过滤掉这些值，因此：

- `seriesNamesFromMetadata.isNotEmpty()` 为 false
- 不执行 `SeriesRepository` 搜索
- `series` 为 null
- 返回 `null to null`

这里要注意，第二、第三个测试仍然创建了三个 series。这样做是为了证明：即使数据库中存在可能被匹配的系列，只要 metadata 没有给出有效 title，`getMetadata` 也不会随便猜一个 series。

## 小白阅读顺序

1. 先读测试文件本身：`komga/src/test/kotlin/org/gotson/komga/domain/service/TransientBookLifecycleTest.kt`

   重点看三个 `@Test` 方法的共同结构：创建 series、构造 `TransientBook`、mock metadata provider、调用 `getMetadata`、断言结果。

2. 再读被测生产类：`komga/src/main/kotlin/org/gotson/komga/domain/service/TransientBookLifecycle.kt`

   重点看 `getMetadata`，理解它分成两条线：一条取 `numberSort`，一条取 `series title` 并匹配 `Series`。

3. 接着读模型：`komga/src/main/kotlin/org/gotson/komga/domain/model/TransientBook.kt`

   理解 `TransientBook` 为什么有 `book`、`media` 和 `metadata` 三部分，以及为什么需要 `toBookWithMedia()`。

4. 然后读 provider 接口：`BookMetadataProvider.kt` 和 `SeriesMetadataFromBookProvider.kt`

   重点理解 `getMetadata` 不是自己解析 ComicInfo、EPUB 或 barcode，而是把解析工作交给多个 provider。

5. 最后读 REST 入口：`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/TransientBooksController.kt`

   重点看 `analyzeTransientBook`，它解释了这个测试覆盖的逻辑在真实 API 中什么时候发生。

## 常见误区

1. 误以为这个测试在测试 `ComicInfoProvider` 的解析能力。

   实际不是。`ComicInfoProvider` 在这里被 `@SpykBean` 包装，并且关键方法返回值被 MockK 固定了。测试不关心 ComicInfo XML 怎么解析，只关心 `TransientBookLifecycle.getMetadata` 拿到 provider 结果后怎么处理。

2. 误以为 `getMetadata` 会创建新系列。

   不会。它只根据已有 `Series` 做匹配，返回已有 `series.id`。如果找不到匹配项，就返回 `null`。创建 series 是测试准备数据时通过 `SeriesLifecycle.createSeries` 做的，不是 `getMetadata` 做的。

3. 误以为 contains 匹配优先。

   生产逻辑是先 exact，再 contains。第一个测试专门防止 `"BATMAN"` 被错误匹配到 `Batman and Robin` 或 `Batman and Robin (2022)`。只有 exact search 没有结果时，才会退回 contains search。

4. 误以为空白字符串也是有效系列名。

   `getMetadata` 对 provider 返回的 title 调用了 `ifBlank { null }`。所以 `""`、`" "` 这类空白值都会被当作没有系列名处理，不会进入查询条件。

5. 误以为所有 `BookMetadataProvider` 都会参与 `numberSort` 提取。

   `TransientBookLifecycle` 构造时会过滤 provider，只保留 `capabilities` 包含 `BookMetadataPatchCapability.NUMBER_SORT` 的 provider。也就是说，某个 provider 即使实现了 `getBookMetadataFromBook`，如果没有声明支持 `NUMBER_SORT`，它也不会被这里用于提取 `number`。

6. 误以为 `TransientBook` 已经是正式导入的 `Book`。

   `TransientBook` 是导入前的临时对象，主要用于扫描、分析、预览和导入前归类。它包含 `Book` 和 `Media`，但还有自己的 `TransientBook.Metadata`，用于保存分析阶段推断出来的 `number` 和 `seriesId`。

7. 误以为 `Media()` 是真实分析结果。

   测试中构造 `TransientBook(makeBook("whatever"), Media())` 只是为了满足类型要求。由于 provider 方法被 mock，测试不需要真实媒体页、文件列表或 archive 内容。

8. 误以为这三个测试是纯内存逻辑测试。

   它们使用 `@SpringBootTest`，并通过 repository/lifecycle 创建和删除 library、series。也就是说，它们依赖 Spring 测试上下文和仓库实现，比普通 mock-only 单元测试更接近集成测试。

9. 误以为 `SeriesMetadataFromBookProvider.getSeriesMetadataFromBook` 只会被调用一次。

   根据当前生产代码，如果 provider 的 `supportsAppendVolume` 为 true，`getMetadata` 会先用 `appendVolumeToTitle = true` 调一次，再用 `false` 调一次；如果不支持，则只会用 `false` 调用。测试中使用 `any()` 匹配第二个参数，因此没有绑定具体调用次数和参数值。

10. 误以为返回的 `number` 来自 `SeriesMetadataPatch`。

   `number` 来自 `BookMetadataPatch.numberSort`，也就是 book metadata；`seriesId` 来自 `SeriesMetadataPatch.title` 匹配已有 series。两个值来源不同，只是在 `getMetadata` 的返回值中被组合成一个 `Pair<String?, Float?>`。
