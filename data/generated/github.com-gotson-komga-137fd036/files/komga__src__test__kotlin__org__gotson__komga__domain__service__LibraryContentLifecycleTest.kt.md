# 文件：komga/src/test/kotlin/org/gotson/komga/domain/service/LibraryContentLifecycleTest.kt

## 它负责什么

`LibraryContentLifecycleTest.kt` 是 `LibraryContentLifecycle` 的领域级集成测试文件。它不直接测试真实文件系统扫描，而是通过 mock `FileSystemScanner`、`BookAnalyzer`、`Hasher`、`TaskEmitter`，把“扫描结果”伪造成不同的文件变化场景，然后用真实的 repository 和 lifecycle 服务验证数据库状态是否符合预期。

它覆盖的核心问题是：当图书库目录被扫描后，Komga 如何判断 series/book 是新增、删除、恢复、重命名、移动，如何保留或重置已有的媒体分析结果、缩略图、元数据、阅读进度、阅读列表和合集关系。

可以把它理解成 `LibraryContentLifecycle.scanRootFolder()` 的行为规格文档。这里的测试重点不是“怎么遍历磁盘”，而是“扫描结果进入领域层后，生命周期服务应该如何更新系统状态”。

## 关键组成

这个测试类位于包 `org.gotson.komga.domain.service`，使用 `@SpringBootTest` 启动 Spring 测试上下文。构造函数注入大量真实组件，包括：

- `SeriesRepository`、`BookRepository`、`LibraryRepository`、`MediaRepository`：验证 series、book、media 的持久化结果。
- `BookMetadataRepository`、`SeriesMetadataRepository`：验证书籍和系列元数据在恢复、重命名时是否正确保留或刷新。
- `ReadProgressRepository`、`ReadListRepository`、`SeriesCollectionRepository`：验证用户阅读进度、阅读列表、合集关系是否随实体迁移。
- `LibraryContentLifecycle`：本文件最主要的被测对象。
- `BookLifecycle`、`SeriesLifecycle`、`LibraryLifecycle`、`ReadListLifecycle`、`SeriesCollectionLifecycle`、`KomgaUserLifecycle`：用于搭建测试数据、触发分析、清理数据或验证关联行为。
- `SeriesDtoRepository`：用于从用户视角验证 series 的阅读状态汇总，例如目录重命名后 `booksReadCount` 是否仍正确。
- `ThumbnailBookRepository`：验证书籍缩略图迁移行为。

被 mock 的 Bean 有：

- `FileSystemScanner`：用 `scanRootFolder()` 返回测试构造的扫描结果。
- `BookAnalyzer`：模拟书籍分析结果，产生 `Media`。
- `Hasher`：模拟文件 hash，用于判断新文件和已删除旧实体是否其实是同一个内容。
- `TaskEmitter`：验证是否触发元数据刷新任务，例如 `refreshBookMetadata()`、`refreshSeriesMetadata()`。

测试数据主要来自 `makeLibrary()`、`makeSeries()`、`makeBook()`、`makeBookPage()` 等测试工厂函数。`mapOf(series to books).toScanResult()` 用来把伪造的 series/book 映射转换成 `ScanResult`，让 mock scanner 看起来像真的扫到了磁盘内容。

测试类有几个嵌套分组：

- `Scan`：基础扫描、新增、删除、文件修改、hash 判断、异常、自动清空回收站。
- `Restore`：文件删除后再次出现，是否恢复旧实体的附属数据。
- `FileRename`：单个文件重命名后，是否通过 hash 识别并保留旧书籍数据。
- `FileMoveToAnotherFolder`：书籍从一个 series 文件夹移动到另一个 series 文件夹后，是否保留媒体、阅读进度、阅读列表、元数据。
- `RenameFolder`：整个 series 文件夹重命名后，是否恢复 series 级别的数据。
- `EmptyTrash`：显式清空回收站后，软删除数据是否永久删除，排序和空集合清理是否正确。

## 上下游关系

上游是扫描入口 `LibraryContentLifecycle.scanRootFolder(library)`。在真实运行中，它会调用 `FileSystemScanner.scanRootFolder(...)` 扫描 library 根目录，得到 `ScanResult`。在本测试中，这一步被 mock 掉，测试直接控制扫描返回值。

核心被测实现位于 `komga/src/main/kotlin/org/gotson/komga/domain/service/LibraryContentLifecycle.kt`。根据当前片段，它的大致逻辑是：

1. 调用 `fileSystemScanner.scanRootFolder(...)` 获取扫描到的 series、book、sidecar。
2. 将扫描结果补上当前 `library.id`。
3. 找出数据库中存在但扫描结果中不存在的 series/book，执行软删除。
4. 对扫描到的新 series：
   - 如果数据库中没有同 URL 的未删除 series，则创建 series、添加 books，并尝试恢复旧 series/book。
   - 如果已存在，则根据 `fileLastModified`、删除过 book 的 series URL、`scanDeep` 等条件决定是否更新书籍列表。
5. 对已存在但文件修改时间变化的 book：
   - 如果文件大小相同且旧 book 有 hash，会重新计算 hash。
   - hash 相同则保留 media 状态。
   - hash 不同或无法确认则把 media 标记为 `Media.Status.OUTDATED`，并重置或更新 `fileHash`。
6. 新增的 book 会进入 `tryRestoreBooks()`，用 file size + hash 匹配已软删除 book，把 media、缩略图、元数据、阅读进度、阅读列表迁移到新 book。
7. 新增的 series 会进入 `tryRestoreSeries()`，用 book 数量、file size、hash 集合匹配已软删除 series，把 series 元数据、用户上传缩略图、合集关系迁移到新 series，并进一步恢复 books。
8. 扫描结束后，对受影响的 series 排序并触发 `taskEmitter.refreshSeriesMetadata()`。
9. 如果 library 配置 `emptyTrashAfterScan = true`，调用 `emptyTrash(library)` 永久删除软删除内容；否则清理空的 collection/read list。

下游主要是 repository 中的持久化状态和异步任务触发：

- `SeriesRepository` / `BookRepository`：series/book 是否新增、软删除、恢复、永久删除。
- `MediaRepository`：media 是否保留、是否标记为 `OUTDATED`。
- `BookMetadataRepository` / `SeriesMetadataRepository`：title 是否跟随文件名/目录名更新，锁定字段是否保留。
- `ThumbnailBookRepository` / series thumbnail 相关能力：生成缩略图、用户上传缩略图、sidecar 缩略图的迁移策略。
- `ReadProgressRepository`：重命名或移动后阅读进度是否还指向新 book。
- `ReadListRepository`：read list 中旧 book id 是否替换为新 book id。
- `SeriesCollectionRepository`：collection 中旧 series id 是否替换为新 series id。
- `TaskEmitter`：是否触发精准的元数据刷新任务。

## 运行/调用流程

测试整体都遵循类似的 given/when/then 结构。

第一步是创建 library，并插入 `libraryRepository`：

```kotlin
val library = makeLibrary()
libraryRepository.insert(library)
```

第二步是配置 `mockScanner.scanRootFolder(any())` 返回一组或多组扫描结果。很多测试使用 `returnsMany(...)`，表示连续多次扫描返回不同状态。例如首次扫描有 `book1` 和 `book2`，第二次扫描只剩 `book1`，就模拟了 `book2` 被从磁盘删除。

第三步是调用一次或多次：

```kotlin
libraryContentLifecycle.scanRootFolder(library)
```

这个调用会真正执行领域逻辑，除了文件系统扫描本身被 mock，其他 repository 更新基本是真实发生的。

第四步通过 repository 查询结果并断言：

- `seriesRepository.findAll()` 看 series 数量、名称、`deletedDate`。
- `bookRepository.findAll()` 看 book 数量、名称、排序号、`deletedDate`、`fileHash`。
- `mediaRepository.findById(book.id)` 看 media 状态是否为 `READY` 或 `OUTDATED`。
- `bookMetadataRepository.findById(id)` 看标题、锁定字段、标签等是否保留。
- `readProgressRepository.findByBookIdAndUserIdOrNull(...)` 看阅读进度是否迁移。
- `readListRepository.findAllContainingBookId(...)` 看 read list 是否仍包含新 book。
- `collectionRepository.findAllContainingSeriesId(...)` 看 collection 是否仍包含新 series。
- `verify { mockTaskEmitter... }` 或 `verify { mockHasher... }` 看是否触发对应副作用。

几个关键流程可以重点理解：

新增文件流程：第一次扫描只有 `book1`，第二次扫描有 `book1`、`book2`。测试断言 series 仍为 1 个，book 变成 2 个，说明同 series 下新增文件会被追加，而不是重建 series。

删除文件流程：第一次扫描有 `book1`、`book2`，第二次只有 `book1`。测试断言 `book2.deletedDate != null`，说明删除默认是软删除，不是直接从数据库移除。

文件修改流程：同 URL 的 book 再次扫描时，如果 `fileLastModified` 变化，会更新 book。若无法证明内容相同，media 会被标为 `OUTDATED`。如果旧 book 有 `fileHash`，且新文件大小相同，会调用 `Hasher.computeHash()`；hash 相同则保留 `Media.Status.READY`，hash 不同则标记过期。

恢复流程：先删除，再扫描回来。`tryRestoreBooks()` 会用 file size 和 hash 匹配已删除 book。匹配成功后，新 book 会继承旧 book 的 media、元数据、阅读进度、read list 关系、部分缩略图。测试中特别验证了用户上传缩略图、标签、`Media.Status.READY` 等不会丢失。

文件重命名流程：旧文件消失、新文件出现，URL 变了，但 file size 和 hash 相同。领域逻辑会把它识别为“同一本书的新实体”，迁移旧数据后删除旧软删除实体。测试还验证了一个细节：`ThumbnailBook.Type.GENERATED` 会保留，`ThumbnailBook.Type.SIDECAR` 不保留，因为 sidecar 和旧路径绑定，文件名变了后不能直接复用。

移动到另一个文件夹流程：book 从 `series1` URL 移到 `series2` URL。测试断言 `series1` 少一本，`series2` 多一本，但 book 的 media、阅读进度、read list、元数据都能迁移。这本质上仍依赖软删除 + 新增 + hash 恢复机制。

目录重命名流程：整个 series 文件夹从 `series1` 变成 `series2`，book 内容不变。`tryRestoreSeries()` 会先用 book 数量和 file size 筛选，再用 hash 集合确认。匹配后，series 级别的元数据、用户上传缩略图、collection 关系会迁移到新 series，旧 series 被删除。若 series title/titleSort 被锁定，保留旧值；未锁定时，title 跟随新目录名。

清空回收站流程：`emptyTrash(library)` 会永久删除已软删除的 series 和 book，并重新排序剩余 books。若 collection 或 read list 只包含已删除元素，清空后也会被清理。

## 小白阅读顺序

建议先读测试文件开头的 imports 和构造函数注入。这里能看出它不是单元测试，而是带 Spring 上下文的领域集成测试。重点识别哪些是真实 repository，哪些是 `@MockkBean`。

然后读 `@BeforeAll`、`@BeforeEach`、`@AfterEach`、`@AfterAll`。这些生命周期方法说明测试环境如何准备用户、默认 mock 元数据刷新任务、每个测试后如何删除 library。理解清理逻辑很重要，因为很多断言默认仓库是干净的。

接着读 `Scan` 分组。它是基础：新增、删除、修改、hash、media 过期、两个 library 隔离、扫描异常、自动清空回收站。读完这一组，基本能理解 `scanRootFolder()` 的主干。

再读 `Restore` 和 `FileRename`。这两组是本文件最重要的业务价值：Komga 不能因为用户移动或重命名文件就丢失阅读进度、封面、元数据。注意测试里通常会先手动给旧 book 设置 `fileHash = "sameHash"`，再让 mock hasher 返回相同 hash，这就是恢复识别成立的关键。

然后读 `FileMoveToAnotherFolder`。它和文件重命名相似，但多了 series 归属变化。适合用来理解 book 的身份不是简单由 URL 决定，内容 hash 可以帮助把旧数据迁移到新位置。

再读 `RenameFolder`。这是 series 级别恢复，对应 `tryRestoreSeries()`。重点看 collection、series metadata、series read progress 汇总和 title lock 的处理。

最后读 `EmptyTrash`。这组测试解释了软删除和永久删除的边界：扫描默认只是标记删除，`emptyTrash()` 才真正移除，并且要维护排序和集合清理。

读完测试后，再对照 `komga/src/main/kotlin/org/gotson/komga/domain/service/LibraryContentLifecycle.kt` 中的 `scanRootFolder()`、`tryRestoreBooks()`、`tryRestoreSeries()`、`emptyTrash()`。测试里的每一组场景基本都能映射到这些方法中的一个分支。

## 常见误区

第一个误区是把“文件删除”理解成数据库立刻删除。这里大多数扫描删除都是软删除，通过 `deletedDate` 标记。这样后续文件恢复、重命名、移动时，系统才有机会用 hash 找回旧数据。只有 `emptyTrash()` 或 `emptyTrashAfterScan = true` 时，才会永久删除。

第二个误区是认为 book 的身份只由文件路径或 URL 决定。测试反复证明，路径变化会先表现为旧 book 消失、新 book 出现，但系统可以通过 file size + file hash 把它们识别为同一本书，从而迁移 media、metadata、read progress、read list 等数据。

第三个误区是认为只要文件修改时间变了，media 一定要重做。实际逻辑更细：如果文件大小相同、旧 book 有 hash，并且新 hash 和旧 hash 相同，media 可以保持 `READY`。如果大小不同或 hash 不同，media 才会被标记为 `OUTDATED`。

第四个误区是忽略 metadata lock。文件或目录重命名后，未锁定的 title 会跟随新文件名或目录名，并可能触发 `refreshBookMetadata(..., setOf(BookMetadataPatchCapability.TITLE))`。但如果 `titleLock` 或 `titleSortLock` 为 true，旧的用户编辑值会保留，测试也验证不会为锁定标题触发不必要的 title 刷新。

第五个误区是认为所有缩略图都能迁移。书籍重命名时，测试明确断言 `GENERATED` 缩略图会保留，但 `SIDECAR` 缩略图不会保留。根据当前片段推断，原因是 sidecar 缩略图来自旁置文件，和旧路径/旧文件名关联，重命名后应重新发现或刷新，而不是盲目复制。

第六个误区是忽略 library 隔离。`given 2 libraries...` 的测试说明，扫描一个 library 并删除它的所有内容，不应影响另一个 library 的 series/book。判断删除范围必须带上 `library.id`，不能全局按 URL 或名称误删。

第七个误区是把 `DirectoryNotFoundException` 当成普通空扫描。测试中根目录不可访问时，期望抛出异常，并且已有 series/book 不被软删除。也就是说，“扫描结果为空”和“目录访问失败”是两种完全不同的状态：前者表示磁盘确实没有内容，后者表示无法确认磁盘状态，不能破坏已有数据。

第八个误区是忽略排序副作用。删除 book 或清空回收站后，`seriesLifecycle.sortBooks()` 会让剩余 book 的 `number` 重新连续。`EmptyTrash` 中删除 `book1` 后，`book2` 变成 number 1，`book3` 变成 number 2，说明生命周期服务不只是增删记录，还要维护阅读顺序。
