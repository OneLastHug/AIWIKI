# 文件：komga/src/test/kotlin/org/gotson/komga/domain/service/BookImporterTest.kt

## 它负责什么

`BookImporterTest.kt` 是 `BookImporter` 的集成测试文件，用来验证“把一个漫画书文件导入到某个 series 中”这条领域流程是否正确。

这里测试的不是单纯的文件复制，而是一整套业务动作：

- 源文件是否存在；
- 目标文件是否已经存在；
- 源文件是否位于已有 Komga library 内部；
- 导入后是否创建新的 `Book`；
- 导入后 series 内书籍是否重新排序；
- 同名 sidecar 文件是否一起复制或移动；
- 使用 `destinationName` 时，主文件和 sidecar 是否被重命名；
- 使用 `upgradeBookId` 升级已有书籍时，旧书籍、旧文件、旧 sidecar 是否被替换；
- 升级时是否保留 metadata、用户上传缩略图、阅读进度、read list 引用；
- 导入失败时是否抛出预期异常。

它位于测试目录 `komga/src/test/kotlin/org/gotson/komga/domain/service/BookImporterTest.kt`，对应的被测实现是 `komga/src/main/kotlin/org/gotson/komga/domain/service/BookImporter.kt`。

这个测试文件本质上在保护 `BookImporter.importBook(...)` 的领域契约：导入一本书不仅要处理文件系统，还要同步数据库中的 `Book`、`Media`、`BookMetadata`、`ThumbnailBook`、`ReadProgress`、`ReadList`、`HistoricalEvent` 等相关状态。

## 关键组成

### 测试类与 Spring 上下文

文件中的测试类是：

```kotlin
@SpringBootTest
class BookImporterTest(...)
```

使用 `@SpringBootTest` 说明它会启动 Spring 测试上下文，注入真实的领域服务和 repository，而不是只测一个孤立对象。因此这些测试更接近“领域集成测试”。

构造函数中注入了大量依赖：

- `BookImporter`：被测对象，核心方法是 `importBook(...)`。
- `BookRepository`：验证导入后的书籍是否创建、旧书是否删除。
- `BookLifecycle`：用于测试前构造缩略图、阅读进度等领域状态。
- `ReadProgressRepository`：验证升级后阅读进度是否迁移。
- `LibraryRepository`：用于创建 library，并测试“源文件不能在已有 library 内部”。
- `SeriesRepository`、`SeriesLifecycle`：创建 series、加入 books、排序 books。
- `MediaRepository`：验证导入或升级后的媒体状态。
- `BookMetadataRepository`：验证升级后 metadata 是否保留。
- `KomgaUserRepository`：创建测试用户，用于阅读进度。
- `ReadListRepository`、`ReadListLifecycle`：验证 read list 中旧 book id 是否替换为新 book id。

这说明 `BookImporter` 不是一个纯文件工具，而是领域层服务，导入动作会牵动多个聚合和持久化对象。

### 测试数据

测试类顶部定义了固定的基础数据：

```kotlin
private val library = makeLibrary("lib", "file:/library")
private val user1 = KomgaUser("user1@example.org", "")
private val user2 = KomgaUser("user2@example.org", "")
```

`makeLibrary`、`makeBook`、`makeSeries` 来自 `komga/src/test/kotlin/org/gotson/komga/domain/model/Utils.kt`，是测试用工厂函数。它们会快速构造领域对象，避免每个测试都手写完整对象。

`user1` 和 `user2` 主要用于阅读进度迁移测试。

### Mock 的 `TaskEmitter`

测试类中有：

```kotlin
@MockkBean
private lateinit var mockTackReceiver: TaskEmitter
```

这里变量名写成了 `mockTackReceiver`，但类型是 `TaskEmitter`。它被 mock 掉，是因为导入 sidecar 后会触发异步任务：

- `refreshBookMetadata(...)`
- `refreshBookLocalArtwork(...)`

在 `@BeforeEach` 中：

```kotlin
every { mockTackReceiver.refreshBookMetadata(any<Book>(), any(), any()) } just Runs
every { mockTackReceiver.refreshBookLocalArtwork(any<Book>(), any()) } just Runs
```

这表示测试不真的执行刷新任务，只验证它是否被调用。例如 sidecar 是图片时，会断言：

```kotlin
verify(exactly = 2) { mockTackReceiver.refreshBookLocalArtwork(any<Book>()) }
```

这对应 `BookImporter.kt` 中的逻辑：导入 sidecar 后，如果类型是 `Sidecar.Type.ARTWORK`，就调用 `taskEmitter.refreshBookLocalArtwork(importedBook)`。

### 文件系统模拟：Jimfs

多数测试使用：

```kotlin
Jimfs.newFileSystem(Configuration.unix()).use { fs -> ... }
```

`Jimfs` 是 Google 提供的内存文件系统。它让测试可以创建 `/source`、`/dest`、`/library/series` 这类路径，而不污染真实磁盘。

例如：

```kotlin
val sourceDir = fs.getPath("/source").createDirectory()
val sourceFile = sourceDir.resolve("source.cbz").createFile()
val destDir = fs.getPath("/dest").createDirectory()
```

这些文件和目录都只存在于测试的内存文件系统里。测试结束后，`use` 会关闭文件系统，资源自动释放。

### 生命周期清理

`@BeforeAll` 中插入基础 library 和用户：

```kotlin
libraryRepository.insert(library)
userRepository.insert(user1)
userRepository.insert(user2)
```

`@AfterAll` 中清空部分 repository：

```kotlin
libraryRepository.deleteAll()
readProgressRepository.deleteAll()
userRepository.deleteAll()
```

`@AfterEach` 中删除所有 series：

```kotlin
seriesLifecycle.deleteMany(seriesRepository.findAll())
```

这里的清理很重要。因为这是集成测试，会写入测试数据库；如果不清理，后一个测试可能受到前一个测试的 series、book、media、metadata 影响。

### 测试场景一：源文件不存在

测试名：

```kotlin
given non-existent source file when importing then exception is thrown
```

输入：

```kotlin
val sourceFile = Paths.get("/non-existent")
bookImporter.importBook(sourceFile, makeSeries("a series"), CopyMode.COPY)
```

断言：

```kotlin
assertThat(thrown).hasCauseInstanceOf(FileNotFoundException::class.java)
```

对应 `BookImporter.importBook(...)` 开头的校验：

```kotlin
if (sourceFile.notExists()) throw FileNotFoundException(...)
```

这里断言的是 `hasCauseInstanceOf`，说明异常可能经过 `withCode(...)` 包装，外层异常不是直接的 `FileNotFoundException`，但 cause 是它。

### 测试场景二：目标文件已存在

测试名：

```kotlin
given existing target when importing then exception is thrown
```

它创建：

- `/source/source.cbz`
- `/dest/source.cbz`

然后把 series 的 URL 指向 `/dest`。导入时目标路径也会是 `/dest/source.cbz`，因此应该失败。

断言：

```kotlin
assertThat(thrown).hasCauseInstanceOf(FileAlreadyExistsException::class.java)
```

对应实现中的：

```kotlin
destFile.exists() -> throw FileAlreadyExistsException(...)
```

### 测试场景三：使用 destinationName 后目标文件已存在

测试名：

```kotlin
given existing target when importing with destination name then exception is thrown
```

源文件是：

```kotlin
/source/source.cbz
```

目标目录中已有：

```kotlin
/dest/dest.cbz
```

导入时传入：

```kotlin
destinationName = "dest"
```

所以目标文件会被计算为：

```text
/dest/dest.cbz
```

因为它已存在，所以抛出 `FileAlreadyExistsException`。

这个测试说明：`destinationName` 只替换文件名，不改变扩展名。`source.cbz` 加上 `destinationName = "dest"` 后，目标是 `dest.cbz`。

### 测试场景四：源文件属于已有 library

测试名：

```kotlin
given source file part of a Komga library when importing then exception is thrown
```

它创建一个 library：

```kotlin
val libraryJimfs = makeLibrary("jimfs", url = sourceDir.toUri().toURL())
libraryRepository.insert(libraryJimfs)
```

然后源文件位于该 library 根目录下：

```kotlin
/source/source.cbz
```

导入时应抛出：

```kotlin
PathContainedInPath
```

对应实现：

```kotlin
libraryRepository.findAll().forEach { library ->
  if (sourceFile.startsWith(library.path)) throw PathContainedInPath(...)
}
```

这条规则的业务含义是：不能从 Komga 已管理的 library 里拿文件再导入到另一个 series，避免同一个实体被重复管理或引发路径冲突。

### 测试场景五：普通导入后创建 book 并重新排序

测试名：

```kotlin
given book when importing then book is imported and series is sorted
```

准备已有 books：

```kotlin
makeBook("1")
makeBook("3")
```

源文件是：

```kotlin
/source/2.cbz
```

导入后，series 中应该有三本书，按 number 排序后是：

```text
1, 2, 3
```

测试断言新书：

```kotlin
assertThat(number).isEqualTo(2)
assertThat(name).isEqualTo("2")
```

还验证新书对应的 media 状态：

```kotlin
assertThat(newMedia.status).isEqualTo(Media.Status.UNKNOWN)
```

这表示普通导入只是把文件纳入系统，媒体分析尚未完成，所以状态是 `UNKNOWN`。

### 测试场景六：导入 book 时同时导入 sidecars

测试名：

```kotlin
given book with sidecars when importing then book and sidecars are imported
```

源目录里创建：

```text
book 2.cbz
book 2.jpg
BOOK 2-1.jpg
```

导入后断言目标目录存在：

```text
book 2.cbz
book 2.jpg
BOOK 2-1.jpg
```

还断言：

```kotlin
verify(exactly = 2) { mockTackReceiver.refreshBookLocalArtwork(any<Book>()) }
```

这说明这两个 jpg 被识别为 book artwork sidecar，并触发本地封面刷新。

根据 `FileSystemScanner.scanBookSidecars(...)` 的实现，它会拿书籍文件名去掉扩展名作为 `bookBaseName`，扫描同目录中匹配 sidecar 规则的文件，并构造 `Sidecar`。所以 `book 2.jpg` 和 `BOOK 2-1.jpg` 会被当作 `book 2.cbz` 的附属文件。

### 测试场景七：使用 destinationName 时 sidecars 也重命名

测试名：

```kotlin
given book with sidecars when importing with destination name then book and sidecars are imported
```

源文件仍然是：

```text
book 2.cbz
book 2.jpg
BOOK 2-1.jpg
```

导入时：

```kotlin
destinationName = "book 5"
```

导入后目标目录应该有：

```text
book 5.cbz
book 5.jpg
book 5-1.jpg
```

这里要注意大小写变化：`BOOK 2-1.jpg` 变成了 `book 5-1.jpg`。因为实现里用的是：

```kotlin
replace(sourceFile.nameWithoutExtension, destinationName, true)
```

第三个参数 `true` 表示忽略大小写替换。因此 `BOOK 2` 也会被替换成 `book 5`。

### 测试场景八：升级已有 book 时删除旧文件和 sidecars

测试名：

```kotlin
given existing book when importing with upgrade then existing book and sidecars are deleted
```

旧 book 文件是：

```text
/library/series/4.cbz
/library/series/4.jpg
/library/series/4-1.jpg
```

被升级的 book 领域对象名称是 `"2"`，但 URL 指向 `4.cbz`。导入新文件：

```text
/source/source.cbz
```

调用：

```kotlin
bookImporter.importBook(sourceFile, series, CopyMode.MOVE, upgradeBookId = bookToUpgrade.id)
```

断言包括：

- series 里仍然是 3 本书；
- 旧 book id 已不存在；
- 新 book id 不等于旧 book id；
- 新 media 状态是 `OUTDATED`；
- 源文件被移动后不存在；
- 旧主文件和旧 sidecar 都被删除。

`Media.Status.OUTDATED` 的含义是：升级后保留了旧 media 信息，但新文件内容需要重新分析，所以标记为过期。

### 测试场景九：升级时保留 metadata 和用户上传缩略图

测试名：

```kotlin
given existing book with metadata when importing with upgrade then metadata is kept
```

测试先修改旧 book 的 metadata：

```kotlin
summary = "a summary"
number = "HS"
numberLock = true
numberSort = 100F
numberSortLock = true
```

还添加用户上传缩略图：

```kotlin
ThumbnailBook.Type.USER_UPLOADED
```

升级后断言新 book 的 metadata 仍然保留这些字段，并且缩略图仍然存在，类型还是 `USER_UPLOADED`。

对应 `BookImporter.kt` 中升级逻辑：

```kotlin
metadataRepository.update(it.copy(bookId = importedBook.id))
thumbnailBookRepository.update(deleted.copy(bookId = importedBook.id))
```

也就是说，它不是复制一份新 metadata，而是把旧 metadata 记录的 `bookId` 改成新 book id。

### 测试场景十：升级且目标同名时替换原文件

测试名：

```kotlin
given existing book when importing with upgrade and same name then existing book is replaced
```

旧文件：

```text
/library/series/2.cbz
```

源文件：

```text
/source/source.cbz
```

导入时：

```kotlin
CopyMode.COPY
destinationName = "2"
upgradeBookId = bookToUpgrade.id
```

目标文件会是：

```text
/library/series/2.cbz
```

这正好等于旧 book 的路径。普通导入遇到目标存在会失败，但升级时允许先删除旧文件再写入新文件。

测试断言：

```kotlin
assertThat(sourceFile).exists()
```

因为这里用的是 `CopyMode.COPY`，所以源文件不会消失。

这个测试保护了一个很关键的分支：当 `destFile == bookToUpgrade.path` 时，导入器应该把旧文件删掉并继续，而不是误判为目标已存在。

### 测试场景十一：升级时保留阅读进度

测试名：

```kotlin
given book with read progress when importing with upgrade then read progress is kept
```

测试先让旧 book 有 10 页 media 信息：

```kotlin
pages = (1..10).map { BookPage("$it", "image/jpeg") }
pageCount = 10
```

然后设置两个用户的阅读进度：

```kotlin
bookLifecycle.markReadProgressCompleted(bookToUpgrade.id, user1)
bookLifecycle.markReadProgress(bookToUpgrade, user2, 4)
```

升级后读取新 book 的 progress：

```kotlin
val progress = readProgressRepository.findAllByBookId(books[0].id)
```

断言：

- `user1` 仍然是 completed；
- `user2` 仍然在 page 4，且未完成。

对应实现：

```kotlin
readProgressRepository
  .findAllByBookId(bookToUpgrade.id)
  .map { it.copy(bookId = importedBook.id) }
  .forEach { readProgressRepository.save(it) }
```

这说明阅读进度会从旧 book id 迁移到新 book id。

### 测试场景十二：升级时替换 read list 中的 book id

测试名：

```kotlin
given book part of a read list when importing with upgrade then imported book replaces upgraded book in the read list
```

测试创建一个 read list：

```kotlin
ReadList(
  name = "readlist",
  bookIds = listOf(bookToUpgrade.id).toIndexedMap(),
)
```

升级后断言 read list 中的唯一 book id 变成新导入 book 的 id：

```kotlin
assertThat(bookIds[0]).isEqualTo(books[0].id)
```

对应实现：

```kotlin
readListRepository
  .findAllContainingBookId(bookToUpgrade.id, filterOnLibraryIds = null)
  .forEach { rl ->
    readListRepository.update(
      rl.copy(
        bookIds =
          rl.bookIds.values
            .map { if (it == bookToUpgrade.id) importedBook.id else it }
            .toIndexedMap(),
      ),
    )
  }
```

这里使用 `toIndexedMap()` 是为了保留 read list 中书籍的顺序结构。它不是简单的 set 替换，而是保持列表位置不变，只替换对应 id。

## 上下游关系

### 上游：谁会调用这类能力

根据当前片段推断，`BookImporter.importBook(...)` 是领域服务方法，通常会被应用层、API 层或任务层调用，用于处理用户上传、导入外部文件、升级已有 book 等场景。这个测试文件没有直接展示控制器或任务调用方，所以这里不能断言具体入口类。

可以确定的是，测试直接调用：

```kotlin
bookImporter.importBook(sourceFile, series, copyMode, destinationName, upgradeBookId)
```

也就是说上游至少需要提供：

- `sourceFile: Path`：要导入的源文件；
- `series: Series`：目标 series；
- `copyMode: CopyMode`：导入方式；
- `destinationName: String?`：可选目标文件名；
- `upgradeBookId: String?`：可选，被升级的旧 book id。

### 下游：`BookImporter` 会影响哪些模块

从测试和实现可以看出，下游主要有几类。

第一类是文件系统：

- 检查源文件是否存在；
- 计算目标文件路径；
- 复制、移动或硬链接主文件；
- 扫描并复制、移动或硬链接 sidecar；
- 升级时删除旧主文件和旧 sidecar。

第二类是领域数据库：

- `BookRepository`：查询旧书、验证新书；
- `SeriesLifecycle`：把新书加入 series，并重新排序；
- `MediaRepository`：创建或迁移 media，升级时标记为 `OUTDATED`；
- `BookMetadataRepository`：升级时迁移 metadata；
- `ThumbnailBookRepository`：升级时迁移用户上传缩略图；
- `ReadProgressRepository`：升级时迁移阅读进度；
- `ReadListRepository`：升级时替换 read list 中的 book id；
- `LibraryRepository`：导入前检查源文件是否位于已有 library；
- `SidecarRepository`：保存导入后的 sidecar 记录；
- `HistoricalEventRepository`：记录导入、删除旧文件等历史事件。

第三类是异步任务与事件：

- `TaskEmitter.refreshBookLocalArtwork(...)`：导入 artwork sidecar 后刷新本地封面；
- `TaskEmitter.refreshBookMetadata(...)`：导入 metadata sidecar 后刷新 metadata；
- `ApplicationEventPublisher.publishEvent(...)`：发布 `DomainEvent.BookImported`，成功或失败都会发布。

测试文件主要 mock 了 `TaskEmitter`，没有直接断言 `ApplicationEventPublisher` 和 `HistoricalEventRepository` 的行为。

## 运行/调用流程

以普通导入为例，核心流程可以按下面理解。

1. 测试用 `Jimfs` 创建内存文件系统，例如 `/source/2.cbz` 和 `/library/series`。
2. 测试用 `makeSeries(...)` 构造目标 series，并通过 `seriesLifecycle.createSeries(...)` 保存。
3. 如果需要已有书籍，就用 `makeBook(...)` 构造，再通过 `seriesLifecycle.addBooks(...)` 加入 series。
4. 调用 `bookImporter.importBook(...)`。
5. `BookImporter` 检查源文件是否存在。
6. `BookImporter` 检查源文件是否位于已有 library 内部。
7. 如果传入 `upgradeBookId`，查找旧 book，并确认旧 book 属于目标 series。
8. 根据 series 路径和 `destinationName` 计算目标主文件路径。
9. 调用 `fileSystemScanner.scanBookSidecars(sourceFile)` 找到源文件旁边的 sidecar。
10. 如果目标文件已存在，普通导入抛异常；如果是升级且目标就是旧 book 文件，则允许删除旧文件。
11. 如果是升级，扫描并删除旧 book 的 sidecar。
12. 根据 `CopyMode` 执行 `MOVE`、`COPY` 或 `HARDLINK`。
13. 调用 `fileSystemScanner.scanFile(destFile)` 把目标文件扫描成新的 `Book`。
14. 用 `seriesLifecycle.addBooks(series, listOf(importedBook))` 把新书加入 series。
15. 如果是升级，则把旧 book 的 media、metadata、用户上传缩略图、阅读进度、read list 引用迁移到新 book。
16. 删除旧 book。
17. 调用 `seriesLifecycle.sortBooks(series)` 重新排序。
18. 对导入的 sidecar，根据类型触发 `TaskEmitter` 刷新任务，并保存 sidecar 记录。
19. 插入历史事件，发布 `DomainEvent.BookImported`。
20. 返回新导入的 `Book`。

测试文件中的每个 `@Test` 都是在这个流程中挑一个关键分支进行断言。

## 小白阅读顺序

建议按下面顺序读。

第一步，先看测试类顶部的依赖注入。重点理解为什么测试需要 `BookImporter`、`SeriesLifecycle`、`BookRepository`、`MediaRepository`、`BookMetadataRepository`、`ReadProgressRepository`、`ReadListRepository`。这些依赖基本就是导入一本书会影响的全部领域对象。

第二步，看 `@BeforeAll`、`@AfterAll`、`@BeforeEach`、`@AfterEach`。这里能理解测试环境如何准备、如何清理，以及为什么 `TaskEmitter` 要 mock。

第三步，先读前三个异常测试：

- `given non-existent source file when importing then exception is thrown`
- `given existing target when importing then exception is thrown`
- `given existing target when importing with destination name then exception is thrown`

它们最简单，可以帮助你理解 `sourceFile`、`destDir`、`destinationName` 和 `CopyMode.COPY` 的基本关系。

第四步，读：

```kotlin
given source file part of a Komga library when importing then exception is thrown
```

这一段能理解 Komga 为什么不允许导入已有 library 内部的文件。

第五步，读普通成功导入：

```kotlin
given book when importing then book is imported and series is sorted
```

这是最核心的 happy path。重点看导入前 series 有 `1` 和 `3`，导入 `2.cbz` 后变成 `1`、`2`、`3`。

第六步，读 sidecar 相关两个测试。重点理解同名 jpg 如何跟随主文件导入，以及 `destinationName` 如何同时影响主文件和 sidecar。

第七步，读升级相关测试。顺序建议是：

1. `given existing book when importing with upgrade then existing book and sidecars are deleted`
2. `given existing book with metadata when importing with upgrade then metadata is kept`
3. `given existing book when importing with upgrade and same name then existing book is replaced`
4. `given book with read progress when importing with upgrade then read progress is kept`
5. `given book part of a read list when importing with upgrade then imported book replaces upgraded book in the read list`

升级逻辑是这个测试文件最复杂的部分。要抓住一个核心点：升级不是修改旧 book，而是导入一个新 book，然后把旧 book 的相关业务数据迁移到新 book，最后删除旧 book。

第八步，再回头读 `BookImporter.kt` 的 `importBook(...)`。此时测试场景已经熟悉，再看实现会更容易对应上每个分支。

## 常见误区

### 误区一：以为 `BookImporter` 只是复制文件

不是。它会复制、移动或硬链接文件，但这只是第一层。真正重要的是它还会创建新的 `Book`、加入 series、排序、迁移 media、metadata、thumbnail、read progress、read list，并触发任务和领域事件。

### 误区二：以为升级会保留旧 book id

测试明确断言：

```kotlin
assertThat(books[2].id).isNotEqualTo(bookToUpgrade.id)
assertThat(bookRepository.findByIdOrNull(bookToUpgrade.id)).isNull()
```

升级时会生成新 book，旧 book 会被删除。被保留的是旧 book 上的相关业务数据，而不是旧 book 记录本身。

### 误区三：以为 `CopyMode.MOVE` 和 `CopyMode.COPY` 对数据库行为不同

从测试看，它们主要影响源文件是否还存在：

- `CopyMode.MOVE` 后，`sourceFile` 不存在；
- `CopyMode.COPY` 后，`sourceFile` 仍存在。

但导入后的领域动作，例如创建新 book、排序、迁移数据等，仍然会发生。

### 误区四：以为目标文件存在时一定失败

普通导入时目标文件存在会失败。但升级时有一个特殊情况：如果目标文件正好是被升级 book 的旧文件路径，导入器会先删除旧文件，再写入新文件。

这就是测试：

```kotlin
given existing book when importing with upgrade and same name then existing book is replaced
```

要保护的行为。

### 误区五：以为 sidecar 只复制文件，不触发后续处理

测试中验证了：

```kotlin
verify(exactly = 2) { mockTackReceiver.refreshBookLocalArtwork(any<Book>()) }
```

说明 artwork sidecar 导入后会触发封面刷新任务。根据 `BookImporter.kt`，metadata sidecar 也会触发 `refreshBookMetadata(...)`。

### 误区六：以为 `destinationName` 只影响主文件

不是。`destinationName` 也会影响 sidecar 文件名。例如：

```text
book 2.cbz    -> book 5.cbz
book 2.jpg    -> book 5.jpg
BOOK 2-1.jpg  -> book 5-1.jpg
```

实现里使用忽略大小写的 `replace(...)`，所以大写的 `BOOK 2` 也会被替换。

### 误区七：以为测试里的文件路径都是真实磁盘路径

大部分测试使用 `Jimfs` 创建内存文件系统。比如 `/source/source.cbz`、`/library/series/2.cbz` 是测试内存中的路径，不会真的写到机器根目录。

只有第一个不存在文件测试用了：

```kotlin
Paths.get("/non-existent")
```

它只是为了触发不存在文件异常。

### 误区八：忽略 `seriesLifecycle.sortBooks(series)`

导入后排序是核心行为之一。测试不是只检查新书存在，还检查原来的 `1` 和 `3` 位置正确，新导入的 `2` 插入中间。对于漫画书库来说，排序错误会直接影响阅读顺序，所以这个断言很重要。

### 误区九：以为 read list 会自动跟随 book 删除

测试说明 read list 需要显式替换旧 book id：

```kotlin
assertThat(bookIds[0]).isEqualTo(books[0].id)
```

如果只删除旧 book，不更新 read list，那么 read list 会引用一个不存在的 book。`BookImporter` 在升级时主动处理了这个关系。

### 误区十：以为 metadata 和 thumbnail 是重新分析出来的

升级测试里，metadata 和用户上传 thumbnail 是迁移过来的，不是重新分析出来的。特别是用户上传缩略图属于用户手工数据，如果升级时丢失，会破坏用户编辑结果，所以测试专门保护这一点。
