# 文件：komga/src/main/kotlin/org/gotson/komga/domain/service/LibraryContentLifecycle.kt

## 它负责什么

`LibraryContentLifecycle` 是 Komga 中“书库内容生命周期”的核心协调服务。它不直接解析漫画文件内容，而是把 `FileSystemScanner` 扫描到的文件系统结果，同步到领域模型和数据库状态中。

它主要负责这些事情：

1. 扫描一个 `Library` 的根目录。
2. 根据磁盘上的目录和文件，新增、更新、软删除 `Series` 和 `Book`。
3. 识别文件变化，必要时把已有 `Media` 标记为 `OUTDATED`，让后续分析任务重新处理。
4. 处理 sidecar 文件变化，例如本地元数据文件、本地封面/ artwork 文件。
5. 尝试把“重新出现”的书籍或系列与已软删除的数据匹配，从而恢复阅读进度、元数据、缩略图、阅读列表、合集关系等用户数据。
6. 在扫描结束后按配置清空垃圾桶，或清理空合集、空阅读列表。
7. 发布领域事件，例如 `DomainEvent.LibraryUpdated`、`DomainEvent.LibraryScanned`。

从架构位置看，它位于 `domain.service` 层，是“扫描任务”和“领域生命周期服务/持久化仓库”之间的编排者。

它本身不是底层扫描器，也不是单个 `Book` 或 `Series` 的业务实现者。它更像一个总控流程：拿到扫描结果后，判断每个系列、每本书、每个 sidecar 应该被新增、更新、删除、恢复，或者触发后续异步任务。

## 关键组成

### 类与依赖

文件中定义了一个 Spring `@Service`：

```kotlin
class LibraryContentLifecycle(...)
```

构造函数注入了大量依赖，说明它是一个聚合型服务。

主要依赖可以分为几类：

1. 扫描输入：
   - `FileSystemScanner`

2. 持久化仓库：
   - `SeriesRepository`
   - `BookRepository`
   - `LibraryRepository`
   - `MediaRepository`
   - `SidecarRepository`
   - `BookMetadataRepository`
   - `SeriesMetadataRepository`
   - `ReadListRepository`
   - `ReadProgressRepository`
   - `SeriesCollectionRepository`
   - `ThumbnailBookRepository`
   - `ThumbnailSeriesRepository`

3. 领域生命周期服务：
   - `BookLifecycle`
   - `SeriesLifecycle`
   - `SeriesCollectionLifecycle`
   - `ReadListLifecycle`

4. 任务调度：
   - `TaskEmitter`

5. 配置与基础设施：
   - `KomgaSettingsProvider`
   - `Hasher`
   - `TransactionTemplate`
   - `ApplicationEventPublisher`

这些 import 说明该文件虽然只有一个类，但它连接了书库扫描、书籍生命周期、元数据、缩略图、阅读进度、合集、阅读列表、sidecar、任务系统和领域事件。

Kotlin 文件没有显式 export 机制。对外暴露的主要 public 方法是：

```kotlin
fun scanRootFolder(library: Library, scanDeep: Boolean = false)
fun emptyTrash(library: Library)
```

其余恢复和清理逻辑是 private 方法：

```kotlin
private fun tryRestoreSeries(newSeries: Series, newBooks: List<Book>)
private fun tryRestoreBooks(newBooks: List<Book>)
private fun cleanupEmptySets()
```

### `scanRootFolder`

这是最核心的方法。

输入：

```kotlin
library: Library
scanDeep: Boolean = false
```

`library` 提供扫描根目录和扫描配置，例如：

- `library.root`
- `library.scanForceModifiedTime`
- `library.oneshotsDirectory`
- `library.scanCbx`
- `library.scanPdf`
- `library.scanEpub`
- `library.scanDirectoryExclusions`
- `library.emptyTrashAfterScan`

`scanDeep` 控制是否对已有系列强制深入检查书籍列表。默认情况下，如果系列目录修改时间没变，系统倾向于跳过深层更新；开启 `scanDeep` 后，即使系列层面没有明显变化，也会进一步检查书籍。

方法内部流程大致是：

1. 调用 `fileSystemScanner.scanRootFolder(...)` 扫描磁盘。
2. 如果根目录不可访问，捕获 `DirectoryNotFoundException`，把 `Library.unavailableDate` 设置为当前时间并发布 `LibraryUpdated` 事件，然后继续抛出异常。
3. 如果之前书库不可用，但这次扫描成功，则清空 `unavailableDate` 并发布更新事件。
4. 把扫描得到的 `Series` 和 `Book` 全部补上 `libraryId`。
5. 找出磁盘上已经不存在的系列，调用 `seriesLifecycle.softDeleteMany(...)` 软删除。
6. 找出磁盘上已经不存在的书，调用 `bookLifecycle.softDeleteMany(...)` 软删除。
7. 对扫描到的每个系列：
   - 如果数据库中不存在，则创建系列、添加书籍、尝试恢复软删除数据。
   - 如果数据库中已存在，则检查系列是否变化、书籍是否变化、是否需要新增书籍或重置媒体状态。
8. 对发生书籍增删变化的系列，执行排序并触发元数据刷新。
9. 处理 sidecar 文件变化，触发对应的本地 artwork 或 metadata 刷新任务。
10. 删除数据库中已经不存在于磁盘的 sidecar 记录。
11. 根据 `library.emptyTrashAfterScan` 决定清空垃圾桶或仅清理空集合。
12. 发布 `DomainEvent.LibraryScanned(library)`。

### `tryRestoreSeries`

这个 private 方法负责“新扫描到的系列是否其实是以前删除过的系列”。

匹配条件写在注释中：

- 新系列和已删除候选系列拥有相同数量的书。
- 所有书能通过文件大小和文件哈希匹配。

实际代码先用书籍数量和文件大小过滤候选：

```kotlin
newBooks.size == deletedBooks.size
bookSizes.containsAll(deletedBooksSizes)
deletedBooksSizes.containsAll(bookSizes)
deletedBooks.all { it.fileHash.isNotBlank() }
```

如果有候选，就给新书计算 hash，然后比较新旧书籍 hash 集合是否一致。

匹配成功后，会在事务中恢复这些内容：

- 系列元数据：
  - 如果旧元数据的 `titleLock` 为 true，则保留旧标题。
  - 否则使用新系列已有标题。
  - `titleSort` 也按 `titleSortLock` 类似处理。
- 用户上传的系列缩略图：
  - `ThumbnailSeries.Type.USER_UPLOADED`
- 合集中的系列引用：
  - 把旧 `seriesId` 替换为新 `seriesId`
- 书籍级别数据：
  - 调用 `tryRestoreBooks(newBooksWithHash)`
- 删除旧的软删除系列：
  - `seriesLifecycle.deleteMany(listOf(match.first))`

这个设计的意图是：当用户把书库目录移动、重命名，或者删除后又重新放回，只要文件内容能匹配，就尽量保留用户资产，而不是把它当成完全陌生的新系列。

### `tryRestoreBooks`

这个 private 方法负责“新扫描到的书是否其实是以前删除过的书”。

匹配步骤是：

1. 根据文件大小查找已删除书籍候选：

```kotlin
bookRepository.findAllDeletedByFileSize(bookToAdd.fileSize)
```

2. 过滤掉没有 `fileHash` 的候选。
3. 如果新书没有 hash，则计算 hash 并更新数据库。
4. 用 `fileHash` 精确匹配。
5. 匹配成功后，在事务中恢复相关数据。

恢复内容包括：

- `Media`
  - `mediaRepository.copy(match.id, bookToAdd.id)`
- 缩略图：
  - `ThumbnailBook.Type.GENERATED`
  - `ThumbnailBook.Type.USER_UPLOADED`
- 书籍元数据：
  - 如果旧标题被锁定，则保留旧标题。
  - 如果旧标题未锁定，则使用新书标题，并触发只刷新 `TITLE` 的元数据任务。
- 阅读进度：
  - `ReadProgress`
- 阅读列表引用：
  - 把阅读列表中的旧 `bookId` 替换成新 `bookId`
- 删除旧软删除书：
  - `bookLifecycle.deleteOne(match)`

这里尤其要注意：恢复不是简单“把旧书改成新路径”，而是把旧书上的用户数据复制或迁移到新书记录上，再删除旧软删除记录。

### `emptyTrash`

`emptyTrash(library: Library)` 是另一个对外方法。

它做的是永久删除当前书库中已经软删除的系列和书籍：

1. 查询该 `library.id` 下所有 `Deleted == true` 的系列。
2. 调用 `seriesLifecycle.deleteMany(seriesToDelete)` 永久删除。
3. 查询该 `library.id` 下所有 `Deleted == true` 的书籍。
4. 调用 `bookLifecycle.deleteMany(booksToDelete)` 永久删除。
5. 对受影响的系列重新排序。
6. 调用 `cleanupEmptySets()` 清理空集合。

它既可以被扫描流程内部调用，也可以被任务系统单独调用。

### `cleanupEmptySets`

这个方法根据全局设置清理空合集和空阅读列表：

```kotlin
if (komgaSettingsProvider.deleteEmptyCollections) {
  collectionLifecycle.deleteEmptyCollections()
}

if (komgaSettingsProvider.deleteEmptyReadLists) {
  readListLifecycle.deleteEmptyReadLists()
}
```

它不会无条件删除空集合，而是尊重配置项。

## 上下游关系

### 上游：谁调用它

根据调用方 `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskHandler.kt`，`LibraryContentLifecycle` 主要由任务系统调用。

当任务是：

```kotlin
Task.ScanLibrary
```

`TaskHandler` 会：

```kotlin
libraryContentLifecycle.scanRootFolder(library, task.scanDeep)
```

扫描完成后，`TaskHandler` 还会继续发出一系列后续任务，例如：

- `analyzeUnknownAndOutdatedBooks(library)`
- `repairExtensions(library, LOW_PRIORITY)`
- `findBooksToConvert(library, LOWEST_PRIORITY)`
- `findBooksWithMissingPageHash(library, LOWEST_PRIORITY)`
- `findDuplicatePagesToDelete(library, LOWEST_PRIORITY)`
- `hashBooksWithoutHash(library)`
- `hashBooksWithoutHashKoreader(library)`

这说明 `scanRootFolder` 只是“发现和同步文件系统状态”的阶段。真正解析书籍、生成页面、补 hash、转换格式等工作在扫描之后由任务系统继续调度。

当任务是：

```kotlin
Task.EmptyTrash
```

`TaskHandler` 会调用：

```kotlin
libraryContentLifecycle.emptyTrash(library)
```

另外，`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/LibraryController.kt` 中也能看到清空垃圾桶接口会通过 `TaskEmitter.emptyTrash(...)` 发出任务，最终仍进入 `TaskHandler` 和 `LibraryContentLifecycle.emptyTrash(...)`。

### 下游：它调用谁

`LibraryContentLifecycle` 的下游很丰富。

扫描输入来自：

- `FileSystemScanner.scanRootFolder(...)`

领域对象创建、排序、删除交给：

- `SeriesLifecycle.createSeries(...)`
- `SeriesLifecycle.addBooks(...)`
- `SeriesLifecycle.softDeleteMany(...)`
- `SeriesLifecycle.sortBooks(...)`
- `SeriesLifecycle.deleteMany(...)`
- `BookLifecycle.softDeleteMany(...)`
- `BookLifecycle.deleteOne(...)`
- `BookLifecycle.deleteMany(...)`

数据库查询和更新交给各类 repository：

- `seriesRepository`
- `bookRepository`
- `libraryRepository`
- `mediaRepository`
- `sidecarRepository`
- `bookMetadataRepository`
- `seriesMetadataRepository`
- `readProgressRepository`
- `readListRepository`
- `collectionRepository`
- `thumbnailBookRepository`
- `thumbnailSeriesRepository`

后续异步工作交给：

- `TaskEmitter.refreshSeriesMetadata(...)`
- `TaskEmitter.refreshSeriesLocalArtwork(...)`
- `TaskEmitter.refreshBookLocalArtwork(...)`
- `TaskEmitter.refreshBookMetadata(...)`

事件通知交给：

- `ApplicationEventPublisher.publishEvent(...)`

文件内容身份判断依赖：

- `Hasher.computeHash(...)`

事务边界依赖：

- `TransactionTemplate.executeWithoutResult { ... }`

### 与 `FileSystemScanner` 的关系

`FileSystemScanner` 负责遍历真实文件系统，把目录、书籍文件和 sidecar 文件转换成领域层可理解的 `ScanResult`。

它会根据配置扫描这些扩展：

- CBX 相关：`cbz`、`zip`、`cbr`、`rar`
- `pdf`
- `epub`

它还会处理：

- 隐藏目录/文件跳过。
- 目录排除规则。
- `oneshotsDirectory` 逻辑。
- sidecar 文件预匹配。
- 目录修改时间策略。

`LibraryContentLifecycle` 不关心如何 walk 文件树，而是消费 `ScanResult.series` 和 `ScanResult.sidecars`，并决定如何更新数据库。

## 运行/调用流程

一次典型的书库扫描流程如下：

1. 用户、调度器或系统触发扫描任务。
2. 任务系统产生 `Task.ScanLibrary`。
3. `TaskHandler.handleTask(...)` 收到任务。
4. `TaskHandler` 通过 `libraryRepository.findByIdOrNull(task.libraryId)` 找到书库。
5. 调用：

```kotlin
libraryContentLifecycle.scanRootFolder(library, task.scanDeep)
```

6. `LibraryContentLifecycle` 调用：

```kotlin
fileSystemScanner.scanRootFolder(...)
```

传入书库根路径和扫描配置。

7. 如果根目录不可访问：
   - 设置 `library.unavailableDate = LocalDateTime.now()`
   - 更新 `LibraryRepository`
   - 发布 `DomainEvent.LibraryUpdated`
   - 抛出 `DirectoryNotFoundException`

8. 如果扫描成功且书库之前是 unavailable：
   - 清空 `unavailableDate`
   - 更新书库
   - 发布 `DomainEvent.LibraryUpdated`

9. 把扫描结果中的 `Series`、`Book` 绑定到当前 `library.id`。

10. 处理磁盘上不存在的系列：
    - 若扫描结果没有任何系列，则软删除该书库下所有现有系列。
    - 否则找出 URL 不在扫描结果中的系列并软删除。

11. 处理磁盘上不存在的书：
    - 找出 URL 不在扫描结果中的书并软删除。
    - 收集受影响的系列，后续重新排序和刷新元数据。

12. 遍历扫描到的系列：

    如果是新系列：

    - `seriesLifecycle.createSeries(newSeries)`
    - `seriesLifecycle.addBooks(createdSeries, newBooks)`
    - `tryRestoreSeries(createdSeries, newBooks)`
    - `tryRestoreBooks(newBooks)`
    - 加入待排序和刷新列表

    如果是已存在系列：

    - 判断目录修改时间是否变化。
    - 判断系列是否处于 deleted 状态。
    - 判断该系列是否刚发生过书籍删除。
    - 如变化，更新 `fileLastModified` 并清空 `deletedDate`。
    - 如果 `scanDeep == true` 或系列发生变化：
      - 查询已有书籍。
      - 对 URL 匹配的已有书，比较 `fileLastModified`。
      - 如果文件大小相同且旧 hash 不为空，计算新文件 hash。
      - 如果 hash 一样，只更新书籍的修改时间、大小、hash。
      - 如果 hash 不一样，把 `Media.status` 改成 `OUTDATED`，并更新书籍信息。
      - 找出新增书籍并加入系列。
      - 对新增书尝试恢复软删除数据。
      - 加入待排序和刷新列表。

13. 对所有待处理系列去重后：

```kotlin
seriesLifecycle.sortBooks(it)
taskEmitter.refreshSeriesMetadata(it.id)
```

14. 处理 sidecar：

    如果 sidecar 是系列级别：

    - `Sidecar.Type.ARTWORK` 触发 `refreshSeriesLocalArtwork`
    - `Sidecar.Type.METADATA` 触发 `refreshSeriesMetadata`

    如果 sidecar 是书籍级别：

    - `Sidecar.Type.ARTWORK` 触发 `refreshBookLocalArtwork`
    - `Sidecar.Type.METADATA` 触发 `refreshBookMetadata`

    处理后保存 sidecar 记录。

15. 删除数据库中不再存在于扫描结果里的 sidecar 记录。

16. 扫描末尾根据书库配置：

    如果 `library.emptyTrashAfterScan == true`：

    ```kotlin
    emptyTrash(library)
    ```

    否则：

    ```kotlin
    cleanupEmptySets()
    ```

17. 记录扫描耗时。

18. 发布：

```kotlin
DomainEvent.LibraryScanned(library)
```

19. 回到 `TaskHandler`，继续发出分析、修复、转换、hash、页面重复检查等后续任务。

## 小白阅读顺序

建议按下面顺序读，不要一上来就陷进所有 repository 细节里。

1. 先读 `scanRootFolder(...)` 的大结构。

   重点看注释和几个大块：

   - 扫描文件系统。
   - 处理根目录不可用。
   - 软删除消失的系列。
   - 软删除消失的书。
   - 遍历扫描到的新/旧系列。
   - 处理 sidecar。
   - 清空垃圾桶或清理空集合。
   - 发布 `LibraryScanned` 事件。

2. 再读 `FileSystemScanner.scanRootFolder(...)`。

   路径：`komga/src/main/kotlin/org/gotson/komga/domain/service/FileSystemScanner.kt`

   这里帮助理解 `scanResult.series` 和 `scanResult.sidecars` 是怎么来的。尤其注意它输出的是“磁盘当前状态”，不是数据库状态。

3. 回到 `scanRootFolder(...)`，重点理解“扫描结果”和“数据库已有记录”的对比。

   核心判断依据主要是：

   - `library.id`
   - `url`
   - `fileLastModified`
   - `fileSize`
   - `fileHash`
   - `deletedDate`

4. 读 `tryRestoreBooks(...)`。

   这是理解“软删除为什么不是立刻永久删除”的关键。它解释了为什么 Komga 能在文件重新出现时恢复阅读进度、缩略图、元数据和阅读列表引用。

5. 读 `tryRestoreSeries(...)`。

   这一段比 `tryRestoreBooks(...)` 更复杂，因为系列恢复还涉及合集、系列元数据和系列缩略图。先理解书籍恢复，再理解系列恢复会容易很多。

6. 最后读 `emptyTrash(...)` 和 `cleanupEmptySets()`。

   它们是扫描后清理逻辑。这里可以帮助理解软删除和永久删除的边界。

7. 再看调用方 `TaskHandler`。

   路径：`komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskHandler.kt`

   重点看 `Task.ScanLibrary` 分支。你会发现扫描之后还有一批任务会继续执行，因此不要误以为 `LibraryContentLifecycle` 完成了书籍分析、封面生成、元数据聚合等所有工作。

## 常见误区

1. 误以为 `LibraryContentLifecycle` 负责扫描文件树。

   实际扫描文件树的是 `FileSystemScanner`。`LibraryContentLifecycle` 负责消费扫描结果，并把磁盘状态同步到数据库和任务系统。

2. 误以为文件不存在就立即永久删除。

   这里首先调用的是 `softDeleteMany(...)`。系列和书籍先进入软删除状态，后续还有机会通过 hash 匹配恢复用户数据。真正永久删除发生在 `emptyTrash(...)` 中。

3. 误以为只要文件修改时间变了就一定重新分析媒体。

   代码中有一个优化：如果文件大小相同、旧 hash 不为空，会计算新文件 hash。若 hash 和旧 hash 一致，只更新书籍的时间、大小和 hash，不把 `Media` 标记为 `OUTDATED`。只有 hash 不一致或无法确认时，才会重置媒体状态。

4. 误以为 `scanDeep` 是“扫描更多文件类型”。

   文件类型由 `library.scanCbx`、`library.scanPdf`、`library.scanEpub` 控制。`scanDeep` 的作用是对已有系列更深入地检查书籍列表，即使系列目录本身没有被判断为变化。

5. 误以为 sidecar 会直接在这里解析并应用内容。

   这里主要做 sidecar 变更检测和任务触发。例如本地 artwork 变化会触发 `refreshSeriesLocalArtwork` 或 `refreshBookLocalArtwork`，元数据 sidecar 变化会触发对应 metadata refresh。具体解析和应用不在这个文件里完成。

6. 误以为恢复系列只看目录名或路径。

   `tryRestoreSeries(...)` 的恢复依据不是名称，而是书籍数量、文件大小和文件 hash。这样即使目录重命名，只要内容一致，也可能恢复旧数据。

7. 误以为恢复书籍只看文件名。

   `tryRestoreBooks(...)` 先按文件大小找候选，再用 `fileHash` 精确匹配。文件名不是核心依据。

8. 误以为删除空合集和空阅读列表总会发生。

   `cleanupEmptySets()` 会检查配置：

   - `komgaSettingsProvider.deleteEmptyCollections`
   - `komgaSettingsProvider.deleteEmptyReadLists`

   只有配置允许时才删除。

9. 误以为 `LibraryScanned` 表示所有后续处理都完成了。

   `DomainEvent.LibraryScanned(library)` 只表示这个扫描同步流程结束。根据 `TaskHandler` 的逻辑，扫描后还会排队执行分析未知/过期书籍、修复扩展名、转换检查、页面 hash、重复页面等任务。

10. 误以为所有数据库更新都在一个大事务里。

   这个文件只在关键恢复或媒体状态更新时使用 `TransactionTemplate` 包住局部操作，例如恢复书籍数据、恢复系列数据、更新媒体状态和书籍状态。整个 `scanRootFolder(...)` 并不是一个从头到尾的大事务。这样设计可以减少长事务风险，但也意味着阅读时要注意每个小事务的边界。
