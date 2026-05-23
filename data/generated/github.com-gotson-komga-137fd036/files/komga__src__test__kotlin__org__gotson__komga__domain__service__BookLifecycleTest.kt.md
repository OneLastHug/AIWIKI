# 文件：komga/src/test/kotlin/org/gotson/komga/domain/service/BookLifecycleTest.kt

## 它负责什么

`BookLifecycleTest.kt` 是 `BookLifecycle` 领域服务的集成测试文件。它不直接实现业务功能，而是通过真实 Spring Boot 测试上下文、真实 repository、部分 mock/spy，验证 `BookLifecycle` 在几类关键场景下是否保持正确行为：

1. 书籍重新分析后，阅读进度是否按页数变化正确调整。
2. 删除书籍文件时，书籍本体、sidecar 缩略图文件、空的父目录是否被正确处理。
3. 标记阅读进度时，普通分页书籍、PDF、EPUB 的校验规则是否正确。
4. 使用 Readium/Kobo 风格的 `R2Progression` 更新进度时，旧进度、非法位置、EPUB 资源匹配等边界是否被拦截。

这个测试覆盖的是 `org.gotson.komga.domain.service.BookLifecycle` 中比较容易出错的生命周期逻辑：分析、阅读进度、文件删除、EPUB 定位。

## 关键组成

文件顶部使用 `@SpringBootTest`，说明它不是纯单元测试，而是加载 Spring 应用上下文后运行。构造函数注入了多个真实 repository 和服务：

- `BookRepository`：查询和持久化 `Book`。
- `LibraryRepository`：创建测试用 library。
- `SeriesRepository`、`SeriesLifecycle`：创建 series，并把 book 加入 series。
- `ReadProgressRepository`：检查阅读进度是否保存、重置或删除。
- `MediaRepository`：直接修改 book 对应的 `Media` 状态、页数、类型、EPUB 扩展信息。
- `KomgaUserRepository`：准备测试用户。
- `ThumbnailBookRepository`：准备 sidecar 缩略图记录。

被测对象是：

```kotlin
@SpykBean
private lateinit var bookLifecycle: BookLifecycle
```

这里用的是 `SpykBean`，也就是 Spring 容器里的真实 `BookLifecycle`，但允许对其方法调用做 verify。例如测试“文件不存在时不应 soft delete”时，会验证 `bookLifecycle.softDeleteMany(any())` 没有被调用。

`BookAnalyzer` 则是：

```kotlin
@MockkBean
private lateinit var mockAnalyzer: BookAnalyzer
```

原因是重新分析书籍时，测试不关心真实文件解析器怎么读 CBZ、PDF、EPUB，只关心 `BookLifecycle.analyzeAndPersist` 拿到新的 `Media` 后如何处理数据库状态。因此通过 MockK 的 `every { mockAnalyzer.analyze(any(), any()) } returns ...` 控制分析结果。

测试中常用的工厂函数包括：

- `makeLibrary()`
- `makeSeries(...)`
- `makeBook(...)`
- `makeBookPage(...)`

这些函数用于快速构造领域模型，避免测试被大量样板字段淹没。

生命周期钩子有三个：

```kotlin
@BeforeAll
fun `setup library`() { ... }

@AfterAll
fun teardown() { ... }

@AfterEach
fun `clear repository`() { ... }
```

`setup library` 会插入一个 library 和两个用户 `user1`、`user2`。`teardown` 清理 library、阅读进度和用户。`clear repository` 每个测试后通过 `seriesLifecycle.deleteMany(seriesRepository.findAll())` 清理 series 及其关联书籍，保证测试之间尽量隔离。

主要测试块可以分成三组。

第一组是 `analyzeAndPersist` 与阅读进度调整：

- `given outdated book with different number of pages than before when analyzing then existing incomplete read progress is reset to 1`
- `given outdated book with same number of pages than before when analyzing then existing read progress is kept`

它们先构造一个已有 book，把原 media 设置为 `Media.Status.OUTDATED`，并设置旧的 `pageCount`。然后为两个用户分别创建已完成和未完成阅读进度。重新分析后，如果新旧页数不同：

- 已完成进度会被调整到新书的最后一页。
- 未完成进度会被重置到第 1 页。
- `completed` 状态会保留其语义：完成的仍完成，未完成的仍未完成。

对应实现位于 `BookLifecycle.analyzeAndPersist`。根据当前片段可见，它会先调用 `bookAnalyzer.analyze(book, library.analyzeDimensions)` 得到新 `Media`，然后在事务中比较旧 `Media` 和新 `Media` 的 `pageCount`。只有旧状态为 `OUTDATED` 且页数变化时，才调整阅读进度。

第二组是 `deleteBookFiles` 文件删除行为：

- 有 book 文件和 sidecar 时，二者都应删除。
- book 文件不存在时，方法直接返回，不调用 `softDeleteMany`。
- sidecar 记录存在但某个 sidecar 文件不存在时，不应阻止 book 删除。
- 目录里只有这本书时，删除书籍后父目录也应删除。
- 目录里还有无关文件时，只删除 book 文件，不删除父目录和无关文件。

这些测试使用 `Jimfs.newFileSystem(Configuration.unix())` 创建内存文件系统，避免操作真实磁盘。测试通过 `Files.createDirectory`、`Files.createFile` 构造目录、书籍文件和 sidecar 文件，再用 `Files.exists`、`Files.notExists` 断言删除结果。

第三组是嵌套类 `Progression`，集中测试 `BookLifecycle.markProgression`：

```kotlin
@Nested
inner class Progression
```

它的 `@BeforeEach` 每次都创建一个 series 和一本 book。这个分组里定义了：

```kotlin
private val device = R2Device("abc", "device")
```

以及 EPUB 资源列表：

```kotlin
private val epubResources =
  listOf(
    MediaFile("ch1.xhtml", "application/xhtml+xml"),
    MediaFile("ch2.xhtml", "application/xhtml+xml"),
    MediaFile("ch3.xhtml", "application/xhtml+xml"),
  )
```

辅助方法 `makeEpubPositions()` 会为每个 XHTML 章节生成 10 个 `R2Locator`，形成 EPUB 阅读位置表。它模拟 EPUB 分段阅读定位：每个资源有多个 progression，对应不同 position。

`Progression` 下的测试覆盖：

- 新提交的进度时间比已保存进度更旧时，抛出 `IllegalStateException`。
- Divina 或 PDF 类型书籍的 `position` 超出 `pageCount` 时，抛出 `IllegalArgumentException`。
- EPUB 的 `href` 不在 `media.files` 中时，抛出 `IllegalArgumentException`。
- EPUB 没有 `location.progression` 时，抛出 `IllegalArgumentException`。
- EPUB 没有 `MediaExtensionEpub` 扩展信息时，抛出 `IllegalArgumentException`。
- EPUB 使用精确 position 更新进度时成功。
- EPUB 使用偏移过的 progression 更新进度时也成功，说明实现支持在相邻位置中寻找可接受匹配。

## 上下游关系

这个测试文件的直接上游是测试框架和 Spring 测试环境：

- JUnit 5：`@Test`、`@Nested`、`@BeforeAll`、`@AfterAll`、`@BeforeEach`、`@AfterEach`。
- JUnit Params：`@ParameterizedTest`、`@ValueSource`。
- AssertJ：`assertThat`、`assertThatNoException`、`catchThrowable`。
- MockK + springmockk：`@MockkBean`、`@SpykBean`、`every`、`verify`。
- Jimfs：内存文件系统，用于模拟文件删除。

它的核心下游是 `BookLifecycle`：

- `BookLifecycle.analyzeAndPersist(book)`
- `BookLifecycle.markReadProgress(book, user, page)`
- `BookLifecycle.markReadProgressCompleted(bookId, user)`
- `BookLifecycle.markProgression(book, user, progress)`
- `BookLifecycle.deleteBookFiles(book)`
- `BookLifecycle.softDeleteMany(books)`

从当前片段可以看到，`BookLifecycle` 本身再往下依赖：

- `BookAnalyzer`：分析书籍、生成媒体信息、读取页面、生成缩略图。
- `MediaRepository`：保存和查询 `Media`。
- `ReadProgressRepository`：保存、查询、删除阅读进度。
- `ThumbnailBookRepository`：查询 sidecar 缩略图和清理缩略图记录。
- `BookRepository`：更新 book 状态，例如软删除。
- `LibraryRepository`：读取 library 配置，例如是否分析尺寸。
- `HistoricalEventRepository`：记录文件或目录被删除的历史事件。
- `ApplicationEventPublisher`：发布 `DomainEvent`，例如 book 更新、阅读进度变化。

测试中的领域模型来自 `org.gotson.komga.domain.model`：

- `BookPage`
- `Dimension`
- `KomgaUser`
- `Media`
- `MediaExtensionEpub`
- `MediaFile`
- `R2Device`
- `R2Locator`
- `R2Progression`
- `ThumbnailBook`

`R2Progression` 和 `R2Locator` 体现了阅读器进度同步场景。普通 CBZ/PDF 可以用页码定位，而 EPUB 需要用 `href`、`progression`、`MediaExtensionEpub.positions` 共同换算成 Komga 内部的阅读进度。

## 运行/调用流程

阅读进度重置场景的流程如下：

1. 测试通过 `makeSeries` 和 `makeBook` 创建 series 和 book。
2. 调用 `seriesLifecycle.createSeries(series)` 插入 series。
3. 调用 `seriesLifecycle.addBooks(created, books)` 添加 book。
4. 从 `bookRepository.findAll().first()` 取出刚创建的 book。
5. 通过 `mediaRepository.findById(book.id)` 找到旧 media。
6. 把旧 media 改成 `Media.Status.OUTDATED`，并设置旧 `pageCount`。
7. 调用 `bookLifecycle.markReadProgressCompleted(book.id, user1)` 创建已完成进度。
8. 调用 `bookLifecycle.markReadProgress(book, user2, 4)` 创建未完成进度。
9. mock `BookAnalyzer.analyze` 返回新的 `Media`。
10. 调用 `bookLifecycle.analyzeAndPersist(book)`。
11. 最后从 `readProgressRepository` 查询并断言进度是否被保留或调整。

这里的核心规则是：只有旧 media 是 `OUTDATED` 且页数发生变化时，才需要修正已有阅读进度。完成进度会移动到新总页数，未完成进度会回到第 1 页。页数不变时，已有进度数量保持不变。

删除文件场景的流程如下：

1. 用 Jimfs 创建内存文件系统。
2. 构造 `/root/series/book1.cbz` 等测试文件。
3. 如有 sidecar，则创建 `ThumbnailBook(type = SIDECAR, url = sidecarPath.toUri().toURL(), ...)`。
4. 插入 series、book、thumbnail 记录。
5. 调用 `bookLifecycle.deleteBookFiles(book)`。
6. 断言 book 文件、sidecar 文件、父目录是否存在。

根据 `BookLifecycle.deleteBookFiles` 的实现片段，真实流程是：

1. 如果 `book.path.notExists()`，直接返回。
2. 如果 `book.path` 不可写，直接返回。
3. 从 `thumbnailBookRepository` 找到该书所有 `SIDECAR` 缩略图。
4. 只保留存在且可写的 sidecar 路径。
5. 删除 book 文件。
6. 删除可删除的 sidecar 文件。
7. 如果 book 的父目录已经为空，则删除父目录。
8. 调用 `softDeleteMany(listOf(book))`，把 book 标记为软删除。
9. 删除文件或目录时还会写入 `HistoricalEvent`。

注意，测试“某个 sidecar 文件不存在”时，最后断言 `Files.notExists(seriesPath)`。这是因为 book 文件和存在的 sidecar 删除后，另一个 sidecar 本来就不存在，父目录最终为空，所以父目录也会被删除。

`Progression` 场景的流程如下：

1. 每个测试先创建一本 book。
2. 修改该 book 的 `Media`，设置 `status = READY`、`mediaType`、`pageCount`、`files` 或 `extension`。
3. 构造 `R2Progression(modified, device, locator)`。
4. 调用 `bookLifecycle.markProgression(book, user1, progress)`。
5. 根据输入是否合法，断言抛异常或保存成功。

普通 PDF/Divina 的重点是 `locator.locations.position` 必须在 `1..media.pageCount` 之间。EPUB 的重点更复杂：

- `locator.href` 必须能对应 `media.files` 里的资源。
- `locator.locations.progression` 必须存在。
- `MediaExtensionEpub` 必须存在，因为它提供可匹配的 `positions`。
- 如果 progression 不是精确匹配，实现会尝试找相邻位置，并保存传入 locator 的同时补齐/修正部分字段。

## 小白阅读顺序

建议先不要从测试文件第一行开始硬读，而是按业务概念分层阅读。

第一步，先理解 `BookLifecycleTest.kt` 的测试夹具。重点看构造函数注入了哪些 repository 和 service，再看 `@SpykBean bookLifecycle`、`@MockkBean mockAnalyzer`。这能帮助你区分“真实被测对象”和“被替换掉的外部依赖”。

第二步，读 `@BeforeAll`、`@AfterAll`、`@AfterEach`。这三个方法解释了为什么每个测试里都可以直接使用同一个 `library`、`user1`、`user2`，以及为什么每个测试结束后不会残留 series/book 数据。

第三步，读前两个 `analyzeAndPersist` 测试。它们最容易理解：旧书页数 10，新分析后页数可能变成 2 或仍是 10。通过对比两个测试，可以把 `OUTDATED + pageCount changed` 这个核心条件记住。

第四步，打开 `komga/src/main/kotlin/org/gotson/komga/domain/service/BookLifecycle.kt`，对应阅读 `analyzeAndPersist`。看测试如何驱动实现里的这段逻辑：旧 media 是 `OUTDATED` 且页数不同，就把阅读进度批量调整后保存。

第五步，读 `deleteBookFiles` 相关测试。这里不要只看断言，要注意 Jimfs 创建的目录结构。建议在纸上画出：

```text
/root
  /series
    book1.cbz
    sidecar1.png
    file.txt
```

不同测试的差异就是目录里是否还有 sidecar 或无关文件。理解这个结构后，父目录是否会被删除就很直观。

第六步，再读 `Progression` 嵌套类。这个部分需要先知道 EPUB 不是简单按页码保存进度，而是按资源 `href` 和资源内部 `progression` 定位。`makeEpubPositions()` 是理解 EPUB 测试的关键，它为 `ch1.xhtml`、`ch2.xhtml`、`ch3.xhtml` 各生成 10 个位置。

第七步，回到 `BookLifecycle.markProgression`。对照测试名阅读实现的几个 `require` / `check`：

- 进度时间不能比已有进度旧。
- PDF/Divina 页码不能越界。
- EPUB href 必须存在。
- EPUB progression 必须存在。
- EPUB extension 必须存在。
- EPUB progression 可以精确匹配，也可以在一定情况下落到相邻位置。

## 常见误区

第一个误区是把这个文件当成纯单元测试。它使用了 `@SpringBootTest`，repository 和大部分服务都是真实 Spring Bean，只有 `BookAnalyzer` 被 mock，`BookLifecycle` 是 spy。也就是说，它更接近领域服务集成测试。

第二个误区是认为 `analyzeAndPersist` 会在任何重新分析时清空阅读进度。实际不是。根据测试和实现片段，只有旧 `Media` 是 `OUTDATED` 且新旧 `pageCount` 不一致时，才调整阅读进度。页数相同则保留。

第三个误区是认为页数变化后所有用户进度都重置到第 1 页。测试明确区分了已完成和未完成：已完成进度会调整到新书最后一页，并保持 `completed = true`；未完成进度才会回到第 1 页，并保持 `completed = false`。

第四个误区是把 `deleteBookFiles` 理解为只删除数据库记录。这个方法首先操作文件系统，删除真实 book 文件和 sidecar 文件，然后在必要时删除空父目录，最后才调用 `softDeleteMany` 把 book 软删除。文件不存在时，它甚至不会调用 `softDeleteMany`。

第五个误区是认为 sidecar 记录不存在或 sidecar 文件缺失会导致删除失败。测试显示，缺失的 sidecar 文件会被忽略；只要 book 文件能删除，流程会继续，并在父目录为空时删除父目录。

第六个误区是忽略父目录删除条件。父目录只有在删除 book 和可删除 sidecar 后为空时才会被删除。如果目录里还有 `file.txt` 这种无关文件，父目录必须保留。

第七个误区是把 EPUB 进度当作普通页码。`markProgression` 对 EPUB 使用 `href`、`locations.progression` 和 `MediaExtensionEpub.positions` 做匹配。没有 EPUB extension 时无法换算进度，所以会抛出 `"Epub extension not found"`。

第八个误区是认为客户端传来的 EPUB `totalProgression` 可以被完全信任。根据当前 `BookLifecycle` 片段，保存时会使用匹配到的 position 里的 `totalProgression`，并注释说明 Kobo 传来的 total progression 可能是错的。因此测试主要构造可信的 `MediaExtensionEpub.positions`，让服务端用自己的位置表来校准。

第九个误区是忽略时间顺序校验。`markProgression` 会检查新进度的 `modified` 是否晚于已有阅读进度的 `readDate`。如果客户端同步了一个更旧的进度，会抛出 `"Progression is older than existing"`，避免旧设备状态覆盖新进度。

第十个误区是把 `mediaType = "application/zip"` 简单理解为 ZIP 文件。这里在 Komga 语境中，它通常代表 Divina/图片归档类漫画书；测试中与 `application/pdf` 一起验证的是“按页码定位”的媒体类型，而 EPUB 走另一套资源定位逻辑。
