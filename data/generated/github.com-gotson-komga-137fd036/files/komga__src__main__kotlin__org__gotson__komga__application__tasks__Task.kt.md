# 文件：komga/src/main/kotlin/org/gotson/komga/application/tasks/Task.kt

## 它负责什么

`Task.kt` 定义了 Komga 后台任务系统里的“任务数据模型”。它不真正执行任务，也不决定任务什么时候被处理；它只负责把各种后台工作抽象成统一的 `Task` 类型，并为每个任务提供调度系统需要的基础属性：

- `priority`：任务优先级，数字越高通常越优先。
- `groupId`：任务分组标识，用于把相关任务归到同一组，常见是 `seriesId`。
- `uniqueId`：任务唯一标识，用于队列去重、持久化、领取和删除。
- 具体任务参数：例如 `bookId`、`libraryId`、`seriesId`、`scanDeep`、`pages`、`entities` 等。

这个文件位于 `org.gotson.komga.application.tasks` 包，是应用层任务队列的核心类型定义。周边文件 `TaskEmitter.kt` 负责创建并提交这些任务，`TaskProcessor.kt` 负责从队列取任务，`TaskHandler.kt` 负责按任务类型执行真实业务逻辑，`TasksRepository.kt` 负责保存和领取任务。

可以把 `Task.kt` 理解成后台任务系统的“任务清单”和“任务协议”：所有生产者、消费者、仓库实现都围绕这里声明的 `Task` 子类协作。

## 关键组成

文件顶部定义了 5 个优先级常量：

```kotlin
const val HIGHEST_PRIORITY = 8
const val HIGH_PRIORITY = 6
const val DEFAULT_PRIORITY = 4
const val LOW_PRIORITY = 2
const val LOWEST_PRIORITY = 0
```

这些常量用于控制任务处理顺序。比如扫描书库后派生出来的一些维护任务会使用较低优先级，避免抢占更重要的用户操作。

核心类型是：

```kotlin
sealed class Task(
  val priority: Int = DEFAULT_PRIORITY,
  val groupId: String? = null,
) {
  abstract val uniqueId: String
}
```

这里使用 Kotlin 的 `sealed class`，表示 `Task` 的所有具体子类都定义在同一个文件内。这样 `TaskHandler` 在 `when (task)` 分支处理任务时，可以获得相对完整的类型覆盖能力：新增任务类型时，处理器通常也需要新增对应分支。

`Task` 的每个子类都代表一种后台动作，主要可以分为几类。

第一类是书库级任务：

- `ScanLibrary`：扫描某个 library，参数是 `libraryId` 和 `scanDeep`。
- `FindBooksToConvert`：查找某个 library 中需要转换的书。
- `FindBooksWithMissingPageHash`：查找缺少页面 hash 的书。
- `FindDuplicatePagesToDelete`：查找可自动删除的重复页面。
- `EmptyTrash`：清空某个 library 的回收站。

这些任务的 `uniqueId` 通常包含 `libraryId`，例如 `SCAN_LIBRARY_${libraryId}_DEEP_$scanDeep`，表示同一书库、同一扫描深度的扫描任务可以被识别为同一个任务。

第二类是书籍级任务：

- `AnalyzeBook`：分析书籍，通常用于识别媒体状态、页面、元数据后续动作。
- `GenerateBookThumbnail`：生成书籍缩略图。
- `RefreshBookMetadata`：刷新书籍元数据。
- `HashBook`：计算书籍文件 hash。
- `HashBookPages`：计算书籍页面 hash。
- `HashBookKoreader`：计算 KOReader 相关 hash。
- `RefreshBookLocalArtwork`：刷新书籍本地图片资源。
- `ConvertBook`：转换书籍格式，例如转换为 CBZ。
- `RepairExtension`：修复文件扩展名。
- `RemoveHashedPages`：删除指定的已 hash 页面。
- `DeleteBook`：删除书籍文件。

这些任务大多以 `bookId` 为核心参数，`uniqueId` 也通常以任务名加 `bookId` 构成，例如 `ANALYZE_BOOK_$bookId`、`HASH_BOOK_$bookId`。

第三类是系列级任务：

- `RefreshSeriesMetadata`：刷新系列元数据。
- `AggregateSeriesMetadata`：聚合系列元数据。
- `RefreshSeriesLocalArtwork`：刷新系列本地图片资源。
- `ImportBook`：向指定系列导入书籍。
- `DeleteSeries`：删除系列文件。

其中部分任务会把 `groupId` 设置为 `seriesId`，例如 `RefreshSeriesMetadata`、`AggregateSeriesMetadata`、`ImportBook`。书籍相关任务如 `AnalyzeBook`、`RefreshBookMetadata`、`ConvertBook`、`RepairExtension` 也会由调用方传入 `groupId`，通常就是书籍所属的 `seriesId`。这说明队列系统很可能用 `groupId` 控制同一系列内任务的并发或排序；根据当前片段推断，依据是 `Task` 基类内有 `groupId`，多个任务显式传入 `seriesId`，并且 `TasksRepository` 提供了 `findAllGroupedByOwner()` 这类队列观测方法，但具体排序/互斥逻辑不在当前文件中。

第四类是搜索索引任务：

- `RebuildIndex`：重建 Lucene 索引，可指定 `entities: Set<LuceneEntity>?`。
- `UpgradeIndex`：升级索引。

`RebuildIndex` 的 `uniqueId` 固定为 `REBUILD_INDEX`，不包含 `entities`。这意味着无论重建哪些实体，在队列去重层面都可能被视为同一个重建索引任务。根据当前片段推断，这是有意设计：索引重建是全局维护动作，不希望重复排入多个相同类型任务。

第五类是批量发现类任务：

- `FindBookThumbnailsToRegenerate`：查找需要重新生成缩略图的书籍。
- 参数 `forBiggerResultOnly` 表示是否只针对更大结果重新生成。

需要注意的是，它的 `uniqueId` 是固定的 `FIND_BOOK_THUMBNAILS_TO_REGENERATE`，没有包含 `forBiggerResultOnly`。这意味着不同参数值的该任务在唯一标识上不区分。根据当前片段推断，如果任务仓库按 `uniqueId` 去重，那么同一时间队列中可能只能存在一个这类查找任务。

每个任务子类还重写了 `toString()`。这些字符串主要用于日志，例如 `TaskHandler` 中会记录：

```kotlin
logger.info { "Executing task: $task" }
```

因此 `toString()` 的内容直接影响后台任务日志的可读性。

## 上下游关系

上游主要是 `TaskEmitter.kt`。它是任务创建入口，提供更符合业务语义的方法，然后内部构造 `Task` 子类。例如：

- `scanLibrary()` 创建 `Task.ScanLibrary`。
- `emptyTrash()` 创建 `Task.EmptyTrash`。
- `analyzeBook()` 创建 `Task.AnalyzeBook`。
- `generateBookThumbnail()` 创建 `Task.GenerateBookThumbnail`。
- `refreshBookMetadata()` 创建 `Task.RefreshBookMetadata`。
- `convertBookToCbz()` 把一批 `Book` 映射为多个 `Task.ConvertBook`。
- `repairExtensions()` 查出扩展名不匹配的书，再映射为 `Task.RepairExtension`。
- `rebuildIndex()` 创建 `Task.RebuildIndex`。
- `upgradeIndex()` 创建 `Task.UpgradeIndex`。

`TaskEmitter` 依赖 `TasksRepository` 和 `ApplicationEventPublisher`。从命名和当前片段可以看出，它负责保存任务并发布 `TaskAddedEvent`；但提交函数 `submitTask` / `submitTasks` 的具体实现不在已读取片段内，因此这里只能根据当前片段推断。

中游是 `TasksRepository.kt`。它是任务队列的仓库接口，围绕 `Task` 提供这些能力：

- `hasAvailable()`：判断是否有可处理任务。
- `takeFirst(owner: String = Thread.currentThread().name)`：领取第一个可用任务。
- `findAll()`：查询全部任务。
- `findAllGroupedByOwner()`：按 owner 分组查看任务。
- `count()` / `countBySimpleType()`：统计任务数量。
- `save(task)` / `save(tasks)`：保存任务。
- `delete(taskId)`：按任务 ID 删除。
- `deleteAll()`、`deleteAllWithoutOwner()`、`disown()`：清理或释放任务归属。

这里的 `delete(taskId)` 与 `Task.uniqueId` 直接相关，因为 `TaskProcessor` 处理完任务后调用的是 `tasksRepository.delete(task.uniqueId)`。所以 `uniqueId` 不只是展示字段，而是队列生命周期中的关键主键或业务键。

下游是 `TaskProcessor.kt` 和 `TaskHandler.kt`。

`TaskProcessor` 负责调度执行：

- 应用启动后调用 `tasksRepository.disown()`，把之前未完成的任务释放出来。
- 监听 `TaskAddedEvent` 和 `ApplicationReadyEvent`。
- 有任务时通过线程池执行 `takeAndProcess()`。
- `takeAndProcess()` 里调用 `tasksRepository.takeFirst()` 领取任务。
- 领取成功后交给 `taskHandler.handleTask(task)`。
- 处理完成后调用 `tasksRepository.delete(task.uniqueId)` 从队列删除。
- 然后再次调用 `processAvailableTask()` 继续消费队列。

`TaskHandler` 负责真正执行业务逻辑。它对 `Task` 做 `when` 分发：

- `Task.ScanLibrary` 调用 `libraryContentLifecycle.scanRootFolder()`，然后继续派发分析、修复扩展名、转换、页面 hash、重复页面删除、文件 hash 等后续任务。
- `Task.AnalyzeBook` 调用 `bookLifecycle.analyzeAndPersist()`，再根据返回的 `BookAction` 决定是否派发生成缩略图、刷新元数据任务。
- `Task.RefreshBookMetadata` 调用 `bookMetadataLifecycle.refreshMetadata()`，然后派发 `RefreshSeriesMetadata`。
- `Task.RefreshSeriesMetadata` 调用 `seriesMetadataLifecycle.refreshMetadata()`，然后派发 `AggregateSeriesMetadata`。
- `Task.ImportBook` 调用 `bookImporter.importBook()`，导入成功后派发 `AnalyzeBook`。
- `Task.RemoveHashedPages` 调用 `bookPageEditor.removeHashedPages()`，如果需要则派发 `GenerateBookThumbnail`。
- `Task.RebuildIndex` / `Task.UpgradeIndex` 调用 `searchIndexLifecycle`。
- `Task.DeleteBook` / `Task.DeleteSeries` 调用对应 lifecycle 删除文件。

这说明 `Task.kt` 是任务系统的类型中心；`TaskEmitter` 是任务生产者；`TasksRepository` 是队列存储；`TaskProcessor` 是消费者调度器；`TaskHandler` 是任务执行器。

## 运行/调用流程

一个典型流程可以从扫描书库开始理解。

外部某处调用 `TaskEmitter.scanLibrary(libraryId, scanDeep, priority)`，它创建：

```kotlin
Task.ScanLibrary(libraryId, scanDeep, priority)
```

任务被保存到 `TasksRepository`，随后发布 `TaskAddedEvent`。`TaskProcessor` 监听到事件后检查是否允许处理任务，并根据线程池容量调用 `takeAndProcess()`。

`takeAndProcess()` 从 `TasksRepository.takeFirst()` 领取一个任务。如果拿到的是 `Task.ScanLibrary`，则交给 `TaskHandler.handleTask()`。`TaskHandler` 在 `when` 分支中找到 `Task.ScanLibrary`，先按 `libraryId` 查询书库，找到后执行：

```kotlin
libraryContentLifecycle.scanRootFolder(library, task.scanDeep)
```

扫描完成后，它不会在当前方法里直接做所有后续工作，而是通过 `TaskEmitter` 继续派发多个后续任务，例如：

- `AnalyzeBook`
- `RepairExtension`
- `FindBooksToConvert`
- `FindBooksWithMissingPageHash`
- `FindDuplicatePagesToDelete`
- `HashBook`
- `HashBookKoreader`

这些后续任务会再次进入同一个任务队列，由 `TaskProcessor` 后续消费。这样设计的好处是：一次扫描不会把所有耗时工作塞进单个同步流程，而是拆成可排队、可去重、可按优先级处理的后台任务链。

另一个典型流程是分析书籍：

`Task.AnalyzeBook` 被处理时，`TaskHandler` 调用 `bookLifecycle.analyzeAndPersist(book)`。这个方法返回一组 `BookAction`。如果包含 `GENERATE_THUMBNAIL`，就派发 `GenerateBookThumbnail`；如果包含 `REFRESH_METADATA`，就派发 `RefreshBookMetadata`。后者执行完成后又会派发 `RefreshSeriesMetadata`，再进一步派发 `AggregateSeriesMetadata`。

所以 `Task` 不是简单的一次性命令列表，而是可以组成链式后台工作流：

```text
AnalyzeBook
  -> GenerateBookThumbnail
  -> RefreshBookMetadata
       -> RefreshSeriesMetadata
            -> AggregateSeriesMetadata
```

导入书籍也是类似：

```text
ImportBook
  -> bookImporter.importBook(...)
  -> AnalyzeBook
       -> 后续分析派生任务
```

删除任务则更偏终止动作：

- `DeleteBook` 根据书籍是否 `oneshot`，选择删除整个 series 文件或单本 book 文件。
- `DeleteSeries` 直接删除 series 文件。

索引任务则进入搜索基础设施：

```text
RebuildIndex -> searchIndexLifecycle.rebuildIndex(entities)
UpgradeIndex -> searchIndexLifecycle.upgradeIndex()
```

任务执行过程中，`TaskHandler` 会用 Micrometer 记录执行耗时和失败次数，指标标签中的任务类型来自 `task.javaClass.simpleName`。因此每个 `Task` 子类名也会影响监控维度。

## 小白阅读顺序

建议先读 `Task.kt` 的顶部：

1. 先看优先级常量：`HIGHEST_PRIORITY`、`HIGH_PRIORITY`、`DEFAULT_PRIORITY`、`LOW_PRIORITY`、`LOWEST_PRIORITY`。
2. 再看 `sealed class Task` 的构造参数：`priority` 和 `groupId`。
3. 然后理解 `abstract val uniqueId`：每个任务必须自己定义唯一 ID。

接着按业务对象分类读任务子类，不要从上到下死记。

先看书库级任务：

- `ScanLibrary`
- `FindBooksToConvert`
- `FindBooksWithMissingPageHash`
- `FindDuplicatePagesToDelete`
- `EmptyTrash`

这些任务的共同点是都有 `libraryId`。

再看书籍级任务：

- `AnalyzeBook`
- `GenerateBookThumbnail`
- `RefreshBookMetadata`
- `HashBook`
- `HashBookPages`
- `HashBookKoreader`
- `ConvertBook`
- `RepairExtension`
- `RemoveHashedPages`
- `DeleteBook`

这些任务的共同点是基本围绕 `bookId`。

然后看系列级任务：

- `RefreshSeriesMetadata`
- `AggregateSeriesMetadata`
- `RefreshSeriesLocalArtwork`
- `ImportBook`
- `DeleteSeries`

这些任务的共同点是围绕 `seriesId`，部分还把 `seriesId` 作为 `groupId`。

最后再看全局维护任务：

- `RebuildIndex`
- `UpgradeIndex`
- `FindBookThumbnailsToRegenerate`

读完 `Task.kt` 后，建议按这个顺序读邻近文件：

1. `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskEmitter.kt`  
   看任务是在哪里被创建、哪些业务方法会提交哪些 `Task`。

2. `komga/src/main/kotlin/org/gotson/komga/application/tasks/TasksRepository.kt`  
   看任务队列需要支持哪些操作，尤其是 `takeFirst()`、`save()`、`delete()`、`disown()`。

3. `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskProcessor.kt`  
   看任务如何被线程池消费，何时响应 `TaskAddedEvent`，处理完如何删除。

4. `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskHandler.kt`  
   看每种 `Task` 最终对应什么业务逻辑，以及哪些任务会派生出新的任务。

如果只想快速建立全局图，可以记住这一条主线：

```text
TaskEmitter 创建 Task
-> TasksRepository 保存 Task
-> TaskAddedEvent 唤醒 TaskProcessor
-> TaskProcessor takeFirst 领取 Task
-> TaskHandler when 分发执行
-> 执行完成后按 uniqueId 删除 Task
```

## 常见误区

第一个误区：把 `Task.kt` 当成任务执行代码。

`Task.kt` 只定义任务类型和参数，不执行扫描、导入、删除、索引等动作。真正执行逻辑在 `TaskHandler.kt`。例如 `Task.ScanLibrary` 只是保存 `libraryId` 和 `scanDeep`，真正扫描发生在 `libraryContentLifecycle.scanRootFolder()`。

第二个误区：认为 `priority` 会在 `Task.kt` 里生效。

`priority` 只是任务对象上的字段。排序、领取、并发控制应由 `TasksRepository` 的具体实现和 `TaskProcessor` 配合完成。当前文件没有任何排序逻辑。

第三个误区：忽略 `uniqueId` 的重要性。

`uniqueId` 不是普通日志字段。`TaskProcessor` 处理完任务后用 `tasksRepository.delete(task.uniqueId)` 删除任务。很多任务的 `uniqueId` 还体现了去重策略，例如 `RebuildIndex` 固定为 `REBUILD_INDEX`，`UpgradeIndex` 固定为 `UPGRADE_INDEX`，而书籍任务通常包含 `bookId`。

第四个误区：以为所有任务都带 `groupId`。

并不是。`Task` 基类允许 `groupId` 为空。只有部分任务传入分组，例如 `AnalyzeBook`、`RefreshBookMetadata`、`RefreshSeriesMetadata`、`AggregateSeriesMetadata`、`ImportBook`、`ConvertBook`、`RepairExtension`。根据当前片段看，分组主要围绕 `seriesId`，但具体如何利用分组需要继续看 `TasksRepository` 的实现。

第五个误区：认为 `sealed class` 只是语法风格。

这里使用 `sealed class` 很关键。它让 `TaskHandler` 可以用一个 `when (task)` 集中处理所有任务类型。新增任务子类时，不能只改 `Task.kt`，还必须考虑：

- `TaskEmitter.kt` 是否需要新增提交入口。
- `TaskHandler.kt` 是否需要新增执行分支。
- `TasksRepository` 的序列化/持久化实现是否能识别新类型。
- 监控指标是否会出现新的 `task.javaClass.simpleName` 标签。
- `uniqueId` 是否会和已有任务冲突。

第六个误区：以为 `toString()` 无关紧要。

这些 `toString()` 会进入任务执行日志。后台任务出错时，日志中显示的任务参数依赖这里的实现。如果新增任务时 `toString()` 写得不完整，排查问题会更困难。

第七个误区：忽略任务链。

很多任务执行后会继续派发新任务。比如 `ScanLibrary` 会派发分析、修复、转换、hash、重复页面清理等任务；`RefreshBookMetadata` 会派发 `RefreshSeriesMetadata`；`RefreshSeriesMetadata` 又会派发 `AggregateSeriesMetadata`。所以理解 Komga 后台任务时，不要只看单个任务，要看它会不会产生下游任务。

第八个误区：把固定 `uniqueId` 的任务当成参数敏感任务。

`RebuildIndex` 的 `uniqueId` 不包含 `entities`，`FindBookThumbnailsToRegenerate` 的 `uniqueId` 不包含 `forBiggerResultOnly`。如果仓库实现按 `uniqueId` 去重，那么这些任务的不同参数版本可能不能并存。根据当前片段推断，这是队列层有意压缩全局维护任务的一种方式，但具体行为仍要以 `TasksRepository` 实现为准。
