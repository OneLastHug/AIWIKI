# 文件：komga/src/test/kotlin/org/gotson/komga/domain/service/SeriesLifecycleTest.kt

## 它负责什么

`SeriesLifecycleTest.kt` 是 `SeriesLifecycle` 领域服务的集成测试文件。它通过 `@SpringBootTest` 启动 Spring 测试上下文，验证“系列（Series）生命周期”中的几个关键行为：

1. 系列内书籍排序是否符合自然排序规则。
2. 添加、删除书籍后，书籍序号是否能重新连续排列。
3. 创建系列、向系列添加书籍时，相关数据库写入是否具有事务一致性。
4. 系列缩略图删除接口是否只允许删除用户上传的缩略图。
5. 删除系列文件时，是否正确处理书籍文件、书籍 sidecar 缩略图、系列 sidecar 缩略图、无关文件、目录不存在等边界场景。

它不是单纯的单元测试，而是更接近领域层集成测试：测试中使用真实 repository、真实 `SeriesLifecycle`，同时用 `@SpykBean` 局部替换部分 Spring Bean，以便模拟异常或验证调用。

被测核心实现位于 `komga/src/main/kotlin/org/gotson/komga/domain/service/SeriesLifecycle.kt`。

## 关键组成

这个测试类的包名是：

`org.gotson.komga.domain.service`

说明它位于领域服务测试层，和被测类 `SeriesLifecycle` 同包。这样测试可以直接围绕领域服务的公开方法组织，而不是从 REST API 或扫描任务入口间接触发。

主要 import 可以分成几类：

- 测试框架：`org.junit.jupiter.api.Test`、`@Nested`、`@BeforeAll`、`@AfterAll`、`@AfterEach`
- Spring 测试：`@SpringBootTest`、`@Autowired`
- Mock/Spy：`com.ninjasquad.springmockk.SpykBean`、`io.mockk.every`、`io.mockk.verify`
- 断言：`AssertJ` 的 `assertThat`、`catchThrowable`
- 文件系统模拟：`Jimfs`、`Configuration.unix()`、`Files`、`Paths`
- 领域模型：`BookMetadata`、`Dimension`、`Media`、`ThumbnailBook`、`ThumbnailSeries`、`makeBook`、`makeLibrary`、`makeSeries`
- 持久化接口：`SeriesRepository`、`BookRepository`、`LibraryRepository`、`MediaRepository`、`BookMetadataRepository`、`SeriesMetadataRepository`、`BookMetadataAggregationRepository`、`ThumbnailBookRepository`、`ThumbnailSeriesRepository`
- 数据访问异常：`org.jooq.exception.DataAccessException`

测试类构造函数中注入了这些真实 Bean：

- `seriesLifecycle`
- `seriesRepository`
- `bookRepository`
- `libraryRepository`
- `thumbnailSeriesRepository`
- `thumbnailBookRepository`

这些 Bean 用于执行真实业务逻辑，并在断言阶段查询数据库状态。

测试类中还定义了几个 `@SpykBean`：

- `bookLifecycle`
- `seriesMetadataRepository`
- `bookMetadataAggregationRepository`
- `mediaRepository`
- `bookMetadataRepository`

`@SpykBean` 的作用是保留原始 Bean 的真实行为，但允许测试用 `every { ... } throws ...` 修改某些调用的行为。例如事务测试中会让 `seriesMetadataRepository.insert(any())` 抛出 `DataAccessException`，以验证 `createSeries` 整体回滚。

测试数据的基础库对象是：

`private val library = makeLibrary()`

生命周期钩子负责准备和清理测试环境：

- `@BeforeAll setup library`：插入一个测试 library，因为 series 和 book 都需要关联 `libraryId`。
- `@AfterAll teardown library`：删除所有 library。
- `@AfterEach clear repository`：通过 `seriesLifecycle.deleteMany(seriesRepository.findAll())` 删除每个测试创建的 series 及其相关数据。

这里的清理方式比较重要：它没有直接调用 repository 批量清表，而是走 `SeriesLifecycle.deleteMany`，让测试环境尽量符合真实领域删除流程。

核心测试可以分成五组。

第一组是排序测试：

- `given series with unordered books when saving then books are ordered with natural sort`
- `given series when removing a book then remaining books are indexed in sequence`
- `given series when adding a book then all books are indexed in sequence`

这些测试验证 `seriesLifecycle.sortBooks(series)`。实现中排序逻辑会对书名做：

- `trim()`
- `stripAccents()`
- 多个空白压缩为单个空格
- 使用 `CaseInsensitiveSimpleNaturalComparator` 做自然排序

因此 `"boôk 05"` 会按去重音后的 `"book 05"` 参与排序，`"book  002"` 会按自然数字顺序排在 `"book 1"` 后面。

排序后测试断言两件事：

- `Book.number` 连续递增。
- `bookRepository.findAllBySeriesId(...).sortedBy { it.number }` 的书名顺序符合预期。

第二组是事务测试，放在内部类：

`@Nested inner class Transactions`

它验证两个业务方法的事务边界：

- `createSeries(series)`
- `addBooks(series, books)`

`createSeries` 在实现中会在一个事务里写入：

- `seriesRepository.insert(series)`
- `seriesMetadataRepository.insert(SeriesMetadata(...))`
- `bookMetadataAggregationRepository.insert(BookMetadataAggregation(...))`

所以测试分别模拟 `seriesMetadataRepository.insert` 和 `bookMetadataAggregationRepository.insert` 抛错，然后断言：

- 捕获到异常。
- `bookMetadataAggregationRepository.count()` 为 0。
- `seriesMetadataRepository.count()` 为 0。
- `seriesRepository.count()` 为 0。

这说明只要其中一步失败，整个 series 创建应该回滚。

`addBooks` 在实现中会在一个事务里写入：

- `bookRepository.insert(toAdd)`
- `mediaRepository.insert(...)`
- `bookMetadataRepository.insert(...)`

测试分别模拟 `mediaRepository.insert` 和 `bookMetadataRepository.insert` 抛错，然后断言：

- media 没有留下。
- book metadata 没有留下。
- book 没有留下。

这保证“书籍主体、媒体记录、书籍元数据”不会出现半成功状态。

第三组是缩略图删除限制：

`given a sidecar thumbnail when deleting then IllegarlArgumentException is thrown`

测试创建一个 `ThumbnailSeries.Type.SIDECAR` 类型的系列缩略图，然后调用：

`seriesLifecycle.deleteThumbnailForSeries(thumbnail)`

实现中对应逻辑是：

`require(thumbnail.type == ThumbnailSeries.Type.USER_UPLOADED)`

所以 sidecar 缩略图不允许通过这个方法删除，只能删除用户上传类型的缩略图。测试断言抛出 `IllegalArgumentException`。

注意测试名里 `IllegarlArgumentException` 有拼写错误，应该是 `IllegalArgumentException`，但这只是测试显示名称，不影响执行。

第四组是删除系列文件：

- `given a series when deleting series then series directory is deleted`
- `given a series with a series sidecar when deleting series then series directory is deleted`
- `given a series directory with unrelated files when deleting series then series directory should not be deleted`
- `given a non-existent series directory when deleting series then it returns`
- `given a series and a non-existent sidecar file when deleting series then series should be deleted`

这些测试都围绕：

`seriesLifecycle.deleteSeriesFiles(series)`

它们使用 `Jimfs.newFileSystem(Configuration.unix())` 创建内存文件系统，避免真实修改本地磁盘。测试会创建 `/root/series` 目录、书籍文件、sidecar 缩略图文件，再把这些路径转换为 URL 写入 `Series`、`Book`、`ThumbnailBook`、`ThumbnailSeries`。

`deleteSeriesFiles` 的实现逻辑大致是：

1. 如果 `series.path` 不存在，直接返回。
2. 如果 `series.path` 不可写，直接返回。
3. 查询系列 sidecar 缩略图，找出存在且可写的文件路径。
4. 查询系列下所有 book，逐个调用 `bookLifecycle.deleteBookFiles(it)` 删除书籍文件及书籍相关 sidecar。
5. 删除系列 sidecar 缩略图文件。
6. 如果 series 目录还存在且已经为空，则删除目录，并写入 `HistoricalEvent.SeriesFolderDeleted`。
7. 最后调用 `softDeleteMany(listOf(series))`，把系列标记为软删除。

测试分别验证：

- 只有书籍文件和书籍 sidecar 时，目录最后为空，应删除目录。
- 同时有系列 sidecar 时，也应删除目录。
- 如果目录里有无关文件 `file.txt`，只删除 Komga 管理的文件，目录和无关文件保留。
- 如果系列路径不存在，方法直接返回，并且不会调用 `bookLifecycle.softDeleteMany(any())`。
- 如果数据库里记录了一个系列 sidecar，但文件实际不存在，不应阻止目录删除。

## 上下游关系

这个测试文件的直接上游是领域模型构造器和 Spring 测试上下文。

测试通过 `makeLibrary()`、`makeSeries()`、`makeBook()` 构造领域对象。这些工厂函数位于领域模型测试辅助代码中，作用是快速创建带默认值的 `Library`、`Series`、`Book`，避免每个测试手动填写大量无关字段。

测试还依赖真实 repository，包括：

- `LibraryRepository`
- `SeriesRepository`
- `BookRepository`
- `MediaRepository`
- `BookMetadataRepository`
- `SeriesMetadataRepository`
- `BookMetadataAggregationRepository`
- `ThumbnailBookRepository`
- `ThumbnailSeriesRepository`

这些 repository 是领域层和数据库之间的持久化边界。测试通过它们插入准备数据、查询结果、统计记录数，从而验证业务方法对数据库的影响。

直接被测对象是：

`komga/src/main/kotlin/org/gotson/komga/domain/service/SeriesLifecycle.kt`

`SeriesLifecycle` 自身又依赖多个下游服务和设施：

- `BookLifecycle`：用于删除书籍、软删除书籍、读取书籍缩略图等。
- `TaskEmitter`：在排序更新元数据编号后触发元数据刷新任务。
- `ApplicationEventPublisher`：发布 `DomainEvent.SeriesAdded`、`DomainEvent.BookAdded`、`DomainEvent.SeriesDeleted` 等事件。
- `TransactionTemplate`：包裹创建系列、添加书籍、删除系列等事务操作。
- `HistoricalEventRepository`：删除空系列目录后记录历史事件。
- `ReadProgressRepository`、`SeriesCollectionRepository`：在删除 series 时清理阅读进度和合集关系。

这个测试文件主要覆盖 `SeriesLifecycle` 中偏底层、偏数据一致性的行为。更高层的调用方包括：

- `BookImporter`：导入书籍后会调用 `seriesLifecycle.addBooks(...)` 和 `seriesLifecycle.sortBooks(...)`。
- `LibraryContentLifecycle`：扫描或刷新库内容时，会创建新 series、向已有 series 添加 book、重新排序 series 下的 book。
- REST、OPDS、Kobo 等接口测试中也大量使用 `seriesLifecycle.createSeries(...)` 和 `seriesLifecycle.addBooks(...)` 来准备测试数据。

根据当前片段推断，`SeriesLifecycle` 是 Komga 中管理“系列及其书籍集合”的核心领域服务之一：扫描、导入、API 查询、索引测试都依赖它创建出一致的 series/book/media/metadata 数据结构。

## 运行/调用流程

阅读这个测试文件时，可以按测试实际执行流程理解。

测试类启动时，Spring Boot 会创建完整应用测试上下文，并注入真实的 `SeriesLifecycle` 和 repository。

每个测试共享同一个 `library` 对象。测试套件开始时：

1. `setup library` 调用 `libraryRepository.insert(library)`。
2. 后续测试创建的 series 和 book 都使用 `library.id`。

以“创建系列并排序书籍”为例，调用流程是：

1. 测试用 `makeBook(...)` 创建若干未持久化的 `Book`。
2. 用 `makeSeries(...)` 创建一个 `Series`。
3. 调用 `seriesLifecycle.createSeries(series)`。
4. `SeriesLifecycle.createSeries` 在事务中插入 series、series metadata、book metadata aggregation。
5. 调用 `seriesLifecycle.addBooks(createdSeries, books)`。
6. `SeriesLifecycle.addBooks` 检查 book 和 series 是否属于同一个 library。
7. 给每个 book 设置 `seriesId = series.id`。
8. 在事务中插入 book、media、book metadata。
9. 调用 `seriesLifecycle.sortBooks(createdSeries)`。
10. `sortBooks` 从 `bookRepository` 取出该 series 下所有 book。
11. 读取对应 book metadata。
12. 按清洗后的书名做自然排序。
13. 更新每个 book 的 `number`。
14. 如果 metadata 的编号字段没有锁定，则更新 metadata 的 `number` 和 `numberSort`。
15. 如果 metadata 编号发生变化，则通过 `taskEmitter.refreshBookMetadata(...)` 触发刷新。
16. 更新 series 的 `bookCount`。
17. 测试再从 repository 查询结果并断言顺序。

事务测试的流程是：

1. 准备 series 或 book。
2. 使用 `every { 某repository.insert(...) } throws DataAccessException("")` 强行制造数据库异常。
3. 调用被测方法。
4. 用 `catchThrowable` 捕获异常。
5. 查询各 repository 的 count。
6. 断言没有留下部分写入的数据。

删除系列文件测试的流程是：

1. 用 Jimfs 创建内存文件系统。
2. 在内存文件系统中创建 series 目录、book 文件、sidecar 文件。
3. 把文件路径转换成 URL，写入 series/book/thumbnail 对象。
4. 调用 `seriesLifecycle.createSeries(series)` 插入 series。
5. 调用 `seriesLifecycle.addBooks(series, books)` 插入 book、media、metadata。
6. 按需插入 `ThumbnailBook` 或 `ThumbnailSeries` sidecar 记录。
7. 调用 `seriesLifecycle.deleteSeriesFiles(series)`。
8. 用 `Files.exists(...)`、`Files.notExists(...)` 验证文件和目录是否符合预期。

每个测试结束后：

`clear repository` 会调用 `seriesLifecycle.deleteMany(seriesRepository.findAll())`

它会删除 series 及其关联 book、read progress、collection 关系、thumbnail、metadata、aggregation，避免测试之间互相污染。

## 小白阅读顺序

建议先不要从所有 import 开始看，而是按业务动作读。

第一步，先看类声明：

`@SpringBootTest class SeriesLifecycleTest(...)`

确认这是 Spring 集成测试，不是纯 Mock 单元测试。构造函数里 `@Autowired` 的是真实 Bean，类属性中 `@SpykBean` 的是可被局部 mock 的真实 Bean。

第二步，看测试数据准备：

- `private val library = makeLibrary()`
- `setup library`
- `teardown library`
- `clear repository`

理解为什么每个 series/book 都必须有 `libraryId`，以及为什么清理时走 `seriesLifecycle.deleteMany(...)`。

第三步，看前三个排序测试。

先读：

`given series with unordered books when saving then books are ordered with natural sort`

这个测试最能说明 `sortBooks` 的核心目的：不是简单字符串排序，而是经过 trim、去重音、空白规范化和自然数字排序后，再把 `number` 写成连续序号。

再读删除和添加书籍的两个测试：

- 删除 `"book 2"` 后，剩余 `"book 1"`、`"book 3"`、`"book 4"` 的 number 应变成 `1, 2, 3`。
- 添加 `"book 3"` 后，`"book 1"` 到 `"book 5"` 应变成连续 `1..5`。

这两个测试说明 `number` 是重新计算的展示顺序，不是永久不变的插入顺序。

第四步，看 `Transactions` 内部类。

重点看 `every { ... } throws DataAccessException("")` 和后面的 count 断言。这里测试的是事务原子性：series 不能只插入主体却缺 metadata；book 也不能只插入主体却缺 media 或 metadata。

第五步，看缩略图删除测试。

`deleteThumbnailForSeries` 只允许删除 `USER_UPLOADED` 类型。`SIDECAR` 来自文件系统旁置图片，不能通过普通删除上传缩略图的接口删除。

第六步，看 Jimfs 文件删除测试。

这部分代码较长，但结构都一样：

- 建目录。
- 建文件。
- 创建领域对象。
- 插入数据库记录。
- 调 `deleteSeriesFiles`。
- 断言文件系统结果。

小白可以先只看测试名和最后的 `then` 断言，理解每个测试场景的期望，再回头看 `given` 中构造了哪些文件和 thumbnail 记录。

最后再打开 `SeriesLifecycle.kt` 对照阅读以下方法：

- `sortBooks`
- `addBooks`
- `createSeries`
- `deleteThumbnailForSeries`
- `deleteSeriesFiles`
- `deleteMany`

这样能把测试断言和真实实现连起来。

## 常见误区

第一个误区：以为这是纯单元测试。

它使用了 `@SpringBootTest`，大部分 repository 和 `SeriesLifecycle` 都是真实 Spring Bean。`@SpykBean` 只是对部分 Bean 做“可观察、可局部替换”的包装，不代表整个测试都在 mock 环境中运行。

第二个误区：以为 `sortBooks` 只更新 `Book.number`。

根据 `SeriesLifecycle.kt`，`sortBooks` 还会读取和更新 `BookMetadata`。如果 metadata 的 `numberLock` 或 `numberSortLock` 没锁定，就会同步更新 `number` 和 `numberSort`。如果编号变化，还会触发 `taskEmitter.refreshBookMetadata(...)`。本测试主要断言 `Book.number`，但真实影响更宽。

第三个误区：以为书籍排序按原始文件名直接字典序排列。

实现会先对书名做清洗：去首尾空格、去重音、合并连续空白，再用自然排序比较器。所以 `"book  002"` 不会被简单当成普通字符串排到奇怪位置，`"boôk 05"` 也会按去重音后的值参与排序。

第四个误区：以为 `addBooks` 只插入 book。

`addBooks` 同时插入三类数据：`Book`、`Media`、`BookMetadata`。事务测试就是为了防止这三类数据出现不一致。例如 book 插入成功但 metadata 插入失败，会导致后续扫描、展示或排序异常。

第五个误区：以为 `createSeries` 只插入 series。

`createSeries` 同时创建 `SeriesMetadata` 和 `BookMetadataAggregation`。所以事务测试模拟 metadata 或 aggregation 插入失败时，要求 series 主记录也回滚。

第六个误区：以为删除系列文件一定会删除整个目录。

`deleteSeriesFiles` 只会在目录最终为空时删除目录。如果目录里有 Komga 不管理的文件，比如测试中的 `file.txt`，则目录必须保留。这个行为避免误删用户放在系列目录里的其他文件。

第七个误区：以为 sidecar thumbnail 和用户上传 thumbnail 删除规则一样。

`deleteThumbnailForSeries` 明确只允许删除 `ThumbnailSeries.Type.USER_UPLOADED`。`SIDECAR` 是文件系统中的旁置资源，测试保证调用这个方法删除 sidecar 会抛 `IllegalArgumentException`。

第八个误区：忽略 Jimfs 的作用。

测试里的 `/root/series` 不是机器上的真实路径，而是 Jimfs 创建的内存文件系统路径。这样可以安全验证文件删除逻辑，不会污染开发机或 CI 的真实文件系统。

第九个误区：看到 `deleteSeriesFiles` 最后调用 `softDeleteMany`，就以为非空目录也不会影响数据库状态。

从实现看，只要路径存在且可写，方法会删除受管理文件，然后无论目录是否因为无关文件而保留，最后都会调用 `softDeleteMany(listOf(series))`。也就是说文件系统目录是否删除，和 series 是否软删除，是两个相关但不同的结果。测试主要断言文件系统行为，没有展开断言软删除字段。

第十个误区：把 `clear repository` 当成简单清表。

`clear repository` 调的是 `seriesLifecycle.deleteMany(...)`。这会走领域删除流程，包括删除关联 book、read progress、collection 关系、thumbnail、metadata、aggregation 等。这样测试隔离更贴近真实业务，但也意味着如果 `deleteMany` 本身有问题，可能影响多个测试的清理结果。
