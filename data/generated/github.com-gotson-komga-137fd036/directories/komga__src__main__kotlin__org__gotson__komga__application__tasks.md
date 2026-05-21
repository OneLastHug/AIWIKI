# 目录：komga/src/main/kotlin/org/gotson/komga/application/tasks

## 它负责什么

`komga/src/main/kotlin/org/gotson/komga/application/tasks` 是 Komga 后端的应用层任务队列模块。它不直接暴露业务 API，也不保存具体业务数据，而是把“耗时、可异步、可串联”的操作抽象成 `Task`，再通过队列持久化、事件唤醒、线程池执行和业务服务分发来完成后台工作。

典型任务包括：

- 扫描 library：`Task.ScanLibrary`
- 分析 book：`Task.AnalyzeBook`
- 生成 book 缩略图：`Task.GenerateBookThumbnail`
- 刷新 book / series 元数据：`Task.RefreshBookMetadata`、`Task.RefreshSeriesMetadata`
- 聚合 series 元数据：`Task.AggregateSeriesMetadata`
- 导入、转换、修复扩展名：`Task.ImportBook`、`Task.ConvertBook`、`Task.RepairExtension`
- 计算文件 hash、页面 hash、Koreader hash：`Task.HashBook`、`Task.HashBookPages`、`Task.HashBookKoreader`
- 删除重复页面、清空回收站、删除 book / series 文件
- 重建或升级搜索索引：`Task.RebuildIndex`、`Task.UpgradeIndex`
- 查找需要重新生成缩略图的 book：`Task.FindBookThumbnailsToRegenerate`

这个目录的核心职责可以概括为：定义任务类型，接收任务入队，监听任务可用事件，从持久化队列取出任务，并调用 domain / infrastructure 层服务执行真正的业务动作。

## 关键组成

`Task.kt` 定义所有任务类型。

它是一个 Kotlin `sealed class Task`，基础字段有：

- `priority: Int`：任务优先级，常量包括 `HIGHEST_PRIORITY = 8`、`HIGH_PRIORITY = 6`、`DEFAULT_PRIORITY = 4`、`LOW_PRIORITY = 2`、`LOWEST_PRIORITY = 0`。
- `groupId: String?`：任务分组，用于限制同组任务并发。比如同一个 series 下的分析、转换、导入、元数据刷新任务通常会带 series id 作为 `groupId`。
- `uniqueId: String`：每个任务的唯一键，用于队列去重和更新。例如 `ANALYZE_BOOK_$bookId`、`SCAN_LIBRARY_${libraryId}_DEEP_$scanDeep`。

这些任务类只描述“要做什么”和必要参数，不执行业务逻辑。比如 `Task.ImportBook` 保存 `sourceFile`、`seriesId`、`copyMode`、`destinationName`、`upgradeBookId`；`Task.RebuildIndex` 保存可选的 `entities: Set<LuceneEntity>?`。

`TaskEmitter.kt` 是任务生产者门面。

它是 Spring `@Service`，对外提供更语义化的方法，例如 `scanLibrary`、`analyzeBook`、`refreshBookMetadata`、`importBook`、`rebuildIndex`。调用方不用直接构造任务并操作队列，而是调用 `TaskEmitter`。

`TaskEmitter` 做三类事情：

- 把业务对象转换成任务对象，例如 `Book` 转成 `Task.AnalyzeBook(book.id, priority, book.seriesId)`。
- 批量查询并生成任务，例如 `analyzeUnknownAndOutdatedBooks(library)` 会通过 `BookRepository.findAll` 找出 `UNKNOWN` 或 `OUTDATED` 的 book，再批量提交 `AnalyzeBook`。
- 保存任务后发布 `TaskAddedEvent`，唤醒处理器。

`TaskAddedEvent.kt` 只是一个事件标记：

```kotlin
data object TaskAddedEvent
```

它没有字段，作用是告诉 Spring 事件系统：“有新任务入队了”。

`TasksRepository.kt` 是队列仓储接口。

它位于 application 层，只定义能力，不关心底层数据库细节。主要方法包括：

- `hasAvailable()`：是否有可执行任务。
- `takeFirst(owner)`：取出第一个可执行任务，并用当前线程名作为 owner。
- `findAll()`、`findAllGroupedByOwner()`、`count()`、`countBySimpleType()`：查询队列状态。
- `save(task)`、`save(tasks)`：入队。
- `delete(taskId)`、`deleteAll()`、`deleteAllWithoutOwner()`：删除任务。
- `disown()`：清除已有 owner，通常用于服务重启后恢复未完成任务。

`TaskProcessor.kt` 是任务调度器。

它也是 Spring `@Service`，内部创建 `ThreadPoolTaskExecutor`，线程名前缀是 `taskProcessor-`，核心线程数来自 `KomgaSettingsProvider.taskPoolSize`。

关键行为：

- 初始化时执行 `tasksRepository.disown()`，把上次进程退出时被某个线程占用但未完成的任务重新放回队列。
- 监听 `SettingChangedEvent.TaskPoolSize`，动态调整线程池大小。
- 监听 `TaskAddedEvent` 和 `ApplicationReadyEvent`，调用 `processAvailableTask()`。
- 根据线程池可用容量，从 `TasksRepository.takeFirst()` 取任务，交给 `TaskHandler.handleTask(task)`。
- 任务执行完后调用 `tasksRepository.delete(task.uniqueId)` 删除队列记录，然后递归触发下一轮处理。

`TaskHandler.kt` 是任务执行分发器。

它接收一个 `Task`，通过 `when (task)` 匹配具体任务类型，并调用对应的 domain service 或 infrastructure service。它本身不做底层文件扫描、元数据解析、索引构建等具体业务，而是把任务转交给已有生命周期服务，例如：

- `LibraryContentLifecycle`
- `BookLifecycle`
- `BookMetadataLifecycle`
- `SeriesLifecycle`
- `SeriesMetadataLifecycle`
- `LocalArtworkLifecycle`
- `BookImporter`
- `BookConverter`
- `BookPageEditor`
- `SearchIndexLifecycle`
- `PageHashLifecycle`

它还负责日志、耗时统计和失败计数。成功时用 `MeterRegistry.timer(METER_TASKS_EXECUTION, "type", task.javaClass.simpleName)` 记录耗时；异常时记录日志并增加 `METER_TASKS_FAILURE` counter。

## 上下游关系

上游主要是会产生后台任务的接口、调度器和领域服务。

根据调用方搜索，`TaskEmitter` 被这些位置使用：

- REST 接口：`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/BookController.kt`、`LibraryController.kt`、`SeriesController.kt`、`PageHashController.kt`
- 调度入口：`komga/src/main/kotlin/org/gotson/komga/application/scheduler/LibraryScanScheduler.kt`
- scheduler interface：`komga/src/main/kotlin/org/gotson/komga/interfaces/scheduler/PeriodicScannerController.kt`、`SearchIndexController.kt`
- domain service：`BookImporter.kt`、`LibraryContentLifecycle.kt`、`SeriesLifecycle.kt`、`LibraryLifecycle.kt`

这说明任务系统不是只服务 HTTP 请求，也服务定时扫描、搜索索引维护、导入后的后续处理、删除后的清理等内部流程。

下游主要是两类。

第一类是业务执行服务，由 `TaskHandler` 调用：

- library 扫描、清空回收站：`LibraryContentLifecycle`
- book 分析、hash、缩略图：`BookLifecycle`
- book 元数据刷新：`BookMetadataLifecycle`
- series 元数据刷新和聚合：`SeriesMetadataLifecycle`
- 本地 artwork：`LocalArtworkLifecycle`
- 导入：`BookImporter`
- 转换和扩展名修复：`BookConverter`
- 删除重复页面：`BookPageEditor`
- 搜索索引：`SearchIndexLifecycle`
- 页面 hash 查询：`PageHashLifecycle`

第二类是队列持久化实现，在邻近 infrastructure 目录中：

`komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/tasks/TasksDao.kt` 实现了 `TasksRepository`。它把任务序列化为 JSON payload，并保存任务 class 名、simple type、priority、group id、id 等字段。保存时使用 `onDuplicateKeyUpdate()`，所以相同 `uniqueId` 的任务不会无限重复堆积，而是更新已有记录。

对外可见性方面：

- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/TaskController.kt` 提供 `DELETE api/v1/tasks`，管理员可清除未被 owner 占用的排队任务。
- `komga/src/main/kotlin/org/gotson/komga/interfaces/sse/SseController.kt` 每 10 秒调用 `tasksRepository.countBySimpleType()`，向管理员 SSE 推送 `TaskQueueStatus`，用于展示任务队列数量和类型分布。

## 运行/调用流程

一个典型流程是“用户或调度器触发扫描 library”。

1. 上游调用 `TaskEmitter.scanLibrary(libraryId, scanDeep, priority)`。
2. `TaskEmitter` 构造 `Task.ScanLibrary`，调用 `tasksRepository.save(task)`。
3. `TaskEmitter` 发布 `TaskAddedEvent`。
4. `TaskProcessor` 监听到 `TaskAddedEvent`，进入 `processAvailableTask()`。
5. `TaskProcessor` 根据线程池容量调用 `tasksRepository.takeFirst()`。
6. `TasksDao.takeFirst()` 从数据库中选出可用任务，排序规则是 `priority desc`，然后按 `LAST_MODIFIED_DATE` 较早者优先。
7. `TasksDao` 给该任务设置 `OWNER = 当前线程名`，表示任务已被某个 worker 领取。
8. `TaskProcessor` 调用 `TaskHandler.handleTask(task)`。
9. `TaskHandler` 匹配到 `Task.ScanLibrary`，加载 library，调用 `libraryContentLifecycle.scanRootFolder(library, task.scanDeep)`。
10. 扫描后，`TaskHandler` 继续通过 `TaskEmitter` 派生更多后续任务：分析 unknown/outdated book、修复扩展名、查找可转换 book、查找缺失页面 hash、查找可自动删除的重复页面、计算文件 hash、计算 Koreader hash。
11. 每个派生任务再次保存到队列并发布 `TaskAddedEvent`。
12. 当前任务成功后，`TaskProcessor` 调用 `tasksRepository.delete(task.uniqueId)` 删除它，再继续处理下一个可用任务。

这里要特别注意 `groupId`。

`TasksDao` 的 `tasksAvailableCondition` 会排除那些 `GROUP_ID` 已经被其他 owner 占用的任务。换句话说，如果某个 series 的一个任务正在执行，同一 `groupId` 的其他任务暂时不会被并发领取。这样可以减少同一 series 下导入、转换、分析、刷新元数据等操作互相踩踏的风险。

另一个典型流程是“分析 book 后触发后续任务”。

`TaskHandler` 处理 `Task.AnalyzeBook` 时，会调用 `bookLifecycle.analyzeAndPersist(book)`，返回一组 `BookAction`。如果包含 `GENERATE_THUMBNAIL`，就提交 `GenerateBookThumbnail`；如果包含 `REFRESH_METADATA`，就提交 `RefreshBookMetadata`。这体现了这个模块的链式任务模型：任务执行结果可以继续产生下一批任务。

元数据刷新也类似：

- `RefreshBookMetadata` 执行后，会触发 `refreshSeriesMetadata(book.seriesId, priority = task.priority - 1)`。
- `RefreshSeriesMetadata` 执行后，会触发 `aggregateSeriesMetadata(series.id, priority = task.priority)`。
- 最终由 `AggregateSeriesMetadata` 聚合 series 层面的元数据。

## 小白阅读顺序

建议按下面顺序读，不要一开始就跳进所有业务 service。

1. 先读 `Task.kt`。  
   目标是建立任务清单：Komga 后台有哪些异步任务，每个任务带哪些参数，哪些任务有 `groupId`，哪些任务用 `uniqueId` 去重。

2. 再读 `TasksRepository.kt`。  
   它定义队列抽象。先理解“保存、领取、删除、查询、清 owner”这些操作，不用急着看 SQL。

3. 再读 `TaskEmitter.kt`。  
   看它如何把外部调用转成任务，尤其关注 `submitTask` 和 `submitTasks`：保存任务之后一定会发布 `TaskAddedEvent`。

4. 再读 `TaskProcessor.kt`。  
   重点看三个点：启动时 `disown()`，事件监听 `TaskAddedEvent` / `ApplicationReadyEvent`，以及 `takeAndProcess()` 的领取、执行、删除、继续处理流程。

5. 再读 `TaskHandler.kt`。  
   把它当成任务路由表看。每个 `is Task.Xxx ->` 分支都告诉你这个任务最终调用哪个 domain service。这里不需要一次性展开所有 service，只要先知道任务流向。

6. 最后读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/tasks/TasksDao.kt`。  
   这是理解持久化队列细节的关键：任务如何 JSON 序列化，如何按优先级排序，如何用 `OWNER` 领取，如何用 `GROUP_ID` 防止同组并发，如何用 `onDuplicateKeyUpdate()` 去重更新。

如果还想看外部入口，可以补读：

- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/TaskController.kt`：管理员如何清队列。
- `komga/src/main/kotlin/org/gotson/komga/interfaces/sse/SseController.kt`：前端如何知道任务队列状态。
- `komga/src/main/kotlin/org/gotson/komga/application/scheduler/LibraryScanScheduler.kt`：定时扫描如何触发任务。

## 常见误区

第一，`Task` 不是业务逻辑实现。

`Task.kt` 只是任务数据模型。比如 `Task.ConvertBook` 不会转换文件，真正转换发生在 `TaskHandler` 调用 `bookConverter.convertToCbz(book)` 时。

第二，`TaskEmitter` 不执行任务。

`TaskEmitter` 的职责是入队和发布事件。看到 `taskEmitter.generateBookThumbnail(...)` 时，不代表缩略图马上在当前调用栈中生成，而是创建一个 `Task.GenerateBookThumbnail` 等待 `TaskProcessor` 异步领取。

第三，优先级不是唯一调度规则。

任务先按 `PRIORITY desc` 排序，但 `GROUP_ID` 和 `OWNER` 也会影响能否被领取。高优先级任务如果和正在执行的同组任务冲突，也可能暂时不可用。

第四，`uniqueId` 会带来去重语义。

`TasksDao.save()` 使用 `onDuplicateKeyUpdate()`。因此相同 `uniqueId` 的任务再次提交时，会更新已有队列记录，而不是新增一条完全重复的任务。比如同一本 book 的 `ANALYZE_BOOK_$bookId` 多次提交，队列里通常只保留一条最新状态。

第五，`deleteAllWithoutOwner()` 不是杀死正在执行的任务。

`TaskController.emptyTaskQueue()` 调用的是 `tasksRepository.deleteAllWithoutOwner()`，只删除 `OWNER is null` 的待执行任务。已经被线程领取、正在执行的任务不会被这个接口直接删除。

第六，服务重启后未完成任务不会永远卡住。

`TaskProcessor.afterPropertiesSet()` 会调用 `tasksRepository.disown()`，把有 owner 的任务 owner 清空。根据当前片段推断，这是为了处理进程异常退出或重启时，数据库里还标记为“被某线程占用”的任务，让它们重新变成可领取状态。依据是 `disown()` 更新 `OWNER` 为 null，且日志显示 “Reset tasks that were not finished”。

第七，任务失败不会自动删除。

`TaskHandler.handleTask()` 捕获异常后只记录错误并增加失败指标；删除动作在 `TaskProcessor.takeAndProcess()` 中 `handleTask(task)` 返回后执行。由于异常被 `TaskHandler` 内部吞掉，当前实现下失败任务也会走到删除逻辑。也就是说，这里更像“记录失败并结束任务”，不是“失败后自动重试”。这点阅读时容易误判。
