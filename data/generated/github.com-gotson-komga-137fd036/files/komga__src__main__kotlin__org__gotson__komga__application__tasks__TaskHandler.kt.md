# 文件：komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskHandler.kt

## 它负责什么

`TaskHandler.kt` 是 Komga 后台任务系统里的“执行分发器”。它本身不负责排队、不负责并发调度，也不直接决定什么时候跑任务；它只负责接收一个已经取出的 `Task`，根据任务的具体子类型调用对应的领域服务完成实际工作。

从职责上看，它位于 application 层，连接两类对象：

- 上游：`TaskProcessor` 从 `TasksRepository` 取出任务后调用 `taskHandler.handleTask(task)`。
- 下游：各种 domain lifecycle/service，例如 `LibraryContentLifecycle`、`BookLifecycle`、`BookMetadataLifecycle`、`SeriesMetadataLifecycle`、`BookImporter`、`BookConverter`、`SearchIndexLifecycle`、`PageHashLifecycle` 等。

这个文件的核心方法只有一个：`handleTask(task: Task)`。它围绕一个 `when (task)` 分支，把不同后台任务映射到具体操作，并在必要时通过 `TaskEmitter` 投递后续任务，形成任务链。

它还负责两类横切逻辑：

- 日志：任务开始、完成耗时、失败异常。
- 指标：通过 Micrometer `MeterRegistry` 记录 `METER_TASKS_EXECUTION` 和 `METER_TASKS_FAILURE`。

## 关键组成

`TaskHandler` 是一个 Spring `@Service`，构造函数注入了大量协作者。可以按用途分成几组理解。

第一组是任务系统组件：

- `TaskEmitter`：用于在当前任务执行后继续提交新任务。
- `MeterRegistry`：记录任务执行耗时和失败次数。

第二组是仓储对象：

- `LibraryRepository`
- `BookRepository`
- `SeriesRepository`

这些仓储主要用于把 `Task` 里携带的 ID 转成领域对象。例如 `Task.AnalyzeBook` 只有 `bookId`，真正执行前要先 `bookRepository.findByIdOrNull(task.bookId)`。

第三组是领域服务和生命周期服务：

- `LibraryContentLifecycle`：处理库扫描、清空回收站。
- `BookLifecycle`：分析书籍、生成缩略图、删除文件、计算 hash 等。
- `BookMetadataLifecycle`：刷新书籍元数据。
- `SeriesLifecycle`：删除系列文件。
- `SeriesMetadataLifecycle`：刷新和聚合系列元数据。
- `LocalArtworkLifecycle`：刷新本地封面/图片。
- `BookImporter`：导入书籍文件。
- `BookConverter`：转换 CBZ、修复扩展名、查找可转换书籍。
- `BookPageEditor`：删除重复或已 hash 的页面。
- `SearchIndexLifecycle`：重建或升级搜索索引。
- `PageHashLifecycle`：查找缺失页面 hash 的书籍、查找可自动删除的重复页。

`TaskHandler` 本身不包含复杂算法，它的价值在于把 `Task` 的语义和领域服务调用编排起来。

主要分支包括：

- `Task.ScanLibrary`：扫描库目录，然后触发分析未知/过期书籍、修复扩展名、查找可转换书籍、补页面 hash、删除重复页、补文件 hash 等后续任务。
- `Task.AnalyzeBook`：分析书籍媒体信息，依据返回的 `BookAction` 决定是否继续生成缩略图、刷新元数据。
- `Task.RefreshBookMetadata`：刷新书籍元数据，然后触发对应 series 的元数据刷新。
- `Task.RefreshSeriesMetadata`：刷新系列元数据，然后触发聚合系列元数据。
- `Task.ImportBook`：把源文件导入到指定 series，导入成功后继续分析新书。
- `Task.ConvertBook`、`Task.RepairExtension`：调用 `BookConverter` 做格式转换或扩展名修复。
- `Task.HashBook`、`Task.HashBookKoreader`、`Task.HashBookPages`：不同粒度的 hash 任务。
- `Task.RebuildIndex`、`Task.UpgradeIndex`：搜索索引维护。
- `Task.DeleteBook`、`Task.DeleteSeries`：删除书籍或系列文件。
- `Task.FindBookThumbnailsToRegenerate`：查找需要重新生成缩略图的书籍，并批量投递缩略图任务。

## 上下游关系

上游主要在同目录的几个文件里：

- `komga/src/main/kotlin/org/gotson/komga/application/tasks/Task.kt` 定义所有任务类型。它是 sealed class，所以 `TaskHandler` 的 `when (task)` 能枚举所有已知任务。
- `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskEmitter.kt` 负责创建并提交任务。它把业务入口包装成方法，例如 `scanLibrary`、`analyzeBook`、`refreshBookMetadata`、`rebuildIndex` 等。
- `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskProcessor.kt` 负责监听 `TaskAddedEvent` 和 `ApplicationReadyEvent`，从 `TasksRepository` 取任务，然后调用 `TaskHandler.handleTask(task)`。
- `komga/src/main/kotlin/org/gotson/komga/application/tasks/TasksRepository.kt` 根据当前片段推断是任务队列/任务存储抽象，`TaskProcessor` 使用它的 `takeFirst()`、`delete()`、`hasAvailable()`、`disown()` 等方法。

下游则是 domain 和 infrastructure 层：

- 对库的操作下发到 `LibraryContentLifecycle`。
- 对书籍文件、媒体分析、缩略图、hash、删除的操作下发到 `BookLifecycle`、`BookPageEditor`、`BookConverter`。
- 对元数据的操作下发到 `BookMetadataLifecycle`、`SeriesMetadataLifecycle`。
- 对系列文件删除下发到 `SeriesLifecycle`。
- 对本地图片刷新下发到 `LocalArtworkLifecycle`。
- 对搜索索引维护下发到 `SearchIndexLifecycle`。
- 对页面 hash 相关查找下发到 `PageHashLifecycle`。

这个文件和 `TaskEmitter` 之间存在双向配合关系：

- 外部通常通过 `TaskEmitter` 提交初始任务。
- `TaskHandler` 执行某些任务时，又通过 `TaskEmitter` 提交后续任务。

例如 `ScanLibrary` 不是只扫描目录，它还会投递一串后续维护任务；`RefreshBookMetadata` 后会投递 `RefreshSeriesMetadata`；`RefreshSeriesMetadata` 后会投递 `AggregateSeriesMetadata`。

## 运行/调用流程

典型流程可以按下面顺序理解：

1. 某个业务入口调用 `TaskEmitter`，例如提交 `Task.ScanLibrary`。
2. `TaskEmitter` 把任务放入 `TasksRepository`，并发布 `TaskAddedEvent`。
3. `TaskProcessor` 监听到事件后，根据线程池状态从 `TasksRepository` 取出可执行任务。
4. `TaskProcessor.takeAndProcess()` 调用 `taskHandler.handleTask(task)`。
5. `TaskHandler` 记录开始日志：`Executing task: $task`。
6. `TaskHandler` 使用 `measureTime` 包裹 `when (task)` 分发逻辑。
7. 对需要实体对象的任务，先用 repository 按 ID 查询；如果不存在，多数分支会写 warn 日志并跳过。
8. 调用对应 lifecycle/service 执行业务逻辑。
9. 如果当前任务产生后续工作，通过 `TaskEmitter` 继续投递新任务。
10. 成功结束后记录执行耗时，并通过 `meterRegistry.timer(...).record(...)` 写入任务耗时指标。
11. 如果执行中抛出异常，`catch` 会记录 error 日志，并通过 `meterRegistry.counter(...).increment()` 写入失败指标。
12. `TaskProcessor` 在 `handleTask` 返回后删除队列里的任务，然后继续尝试处理下一个任务。

这里有一个重要细节：`TaskHandler` 捕获异常后没有重新抛出。也就是说，从 `TaskProcessor` 视角看，`handleTask` 总是正常返回；随后 `TaskProcessor` 会删除该任务。根据当前片段判断，失败任务不会在这里自动重试，失败只会被记录日志和指标。

几个典型任务链：

`ScanLibrary`：

1. 查找 library。
2. `libraryContentLifecycle.scanRootFolder(library, task.scanDeep)`。
3. 投递分析未知/过期书籍任务。
4. 投递修复扩展名任务。
5. 投递转换 CBZ 任务。
6. 投递补页面 hash、删除重复页、补文件 hash、补 Koreader hash 等任务。

`AnalyzeBook`：

1. 查找 book。
2. `bookLifecycle.analyzeAndPersist(book)`。
3. 如果返回 `BookAction.GENERATE_THUMBNAIL`，投递 `GenerateBookThumbnail`。
4. 如果返回 `BookAction.REFRESH_METADATA`，投递 `RefreshBookMetadata`。

`RefreshBookMetadata`：

1. 查找 book。
2. `bookMetadataLifecycle.refreshMetadata(book, task.capabilities)`。
3. 投递 `RefreshSeriesMetadata(book.seriesId, priority = task.priority - 1)`。

`RefreshSeriesMetadata`：

1. 查找 series。
2. `seriesMetadataLifecycle.refreshMetadata(series)`。
3. 投递 `AggregateSeriesMetadata(series.id, priority = task.priority)`。

`ImportBook`：

1. 查找目标 series。
2. `bookImporter.importBook(Paths.get(task.sourceFile), series, task.copyMode, task.destinationName, task.upgradeBookId)`。
3. 对导入后的 book 投递 `AnalyzeBook`。

## 小白阅读顺序

建议不要一上来就逐行看 `TaskHandler.kt`，否则会被很多服务名淹没。更好的顺序是：

1. 先看 `komga/src/main/kotlin/org/gotson/komga/application/tasks/Task.kt`  
   这里定义了所有任务类型、任务参数、`uniqueId`、`priority`、`groupId`。理解 `Task` 是什么，后面分支才容易看懂。

2. 再看 `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskEmitter.kt`  
   这里解释任务是怎么被创建出来的。比如外部不会直接 new 很多 `Task`，而是调用 `taskEmitter.scanLibrary(...)`、`taskEmitter.analyzeBook(...)` 这类方法。

3. 接着看 `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskProcessor.kt`  
   这里说明任务什么时候被执行、线程池怎么参与、为什么最后会调用 `TaskHandler.handleTask(task)`。

4. 最后回到 `TaskHandler.kt`  
   重点看 `when (task)`。可以先按业务域分组读：扫描库、书籍分析、元数据、封面、本地 artwork、导入转换、hash、索引、删除。

5. 如果还想深入，再跳到具体 lifecycle/service  
   例如想知道“分析书籍”到底做什么，就去看 `BookLifecycle.analyzeAndPersist`；想知道“刷新元数据”到底怎么合并，就去看 `BookMetadataLifecycle` 和 `SeriesMetadataLifecycle`。

读 `TaskHandler.kt` 时，可以把它当成一张后台任务流程图，而不是算法文件。它的关键不是某一行 Kotlin 语法，而是“一个任务会调用哪个服务，以及会不会继续产生新任务”。

## 常见误区

第一个误区：以为 `TaskHandler` 是任务队列。  
它不是队列，也不负责保存任务。任务保存和取出由 `TasksRepository` 配合 `TaskProcessor` 完成。`TaskHandler` 只执行已经拿到的单个任务。

第二个误区：以为所有任务都是独立的。  
很多任务会产生后续任务。例如扫描库之后会投递分析、转换、hash、删除重复页等任务；刷新书籍元数据后会刷新系列元数据；刷新系列元数据后还会聚合系列元数据。

第三个误区：忽略 `priority` 的变化。  
`Task.kt` 里定义了 `HIGHEST_PRIORITY = 8` 到 `LOWEST_PRIORITY = 0`。在 `TaskHandler` 中，有些后续任务会使用 `task.priority + 1`，有些会使用 `task.priority - 1`，有些保持相同优先级。这个变化表达了任务链中不同步骤的相对优先级。

第四个误区：以为实体不存在会抛异常。  
多数任务在找不到 library、book、series 时只是记录 warn 日志，例如 `Cannot execute task ...: Book does not exist`，然后跳过。但也有少数分支没有完全相同的 warn 行，比如 `DeleteBook` 找不到 book 时不会显式 warn；并且 `oneshot` 删除路径里用了 `seriesRepository.findByIdOrNull(book.seriesId)!!`，这里默认 series 必须存在。

第五个误区：以为失败任务会自动重试。  
`handleTask` 的最外层捕获了 `Exception`，记录失败指标后不再抛出。结合 `TaskProcessor` 的逻辑，`handleTask` 返回后任务会被从队列删除。根据当前片段判断，这里没有自动重试机制。

第六个误区：把 `BookAction` 当成任务。  
`BookAction` 不是 `Task`，它是领域服务返回的动作提示。比如 `bookLifecycle.analyzeAndPersist(book)` 返回的 actions 中包含 `GENERATE_THUMBNAIL`，`TaskHandler` 才把它转成真正的 `Task.GenerateBookThumbnail`。

第七个误区：认为 `ScanLibrary` 只做扫描。  
在这个文件里，`ScanLibrary` 是一个复合入口。扫描目录只是第一步，后面还会触发一批维护类任务，所以它更像“扫描并安排库后处理流程”。
