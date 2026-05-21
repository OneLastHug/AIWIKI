# 目录：komga/src/main/kotlin/org/gotson/komga/application

## 它负责什么

`komga/src/main/kotlin/org/gotson/komga/application` 是 Komga 后端的应用编排层，核心职责不是直接实现“扫描文件、解析图书、写入索引、生成缩略图”等业务细节，而是把这些耗时或可异步执行的动作封装成后台任务，排队、调度、消费，并把任务分发给 domain 和 infrastructure 层完成。

这个目录可以理解为“后台任务中枢”：

- `events`：配置 Spring 事件的异步分发方式。
- `scheduler`：负责周期性触发图书库扫描。
- `tasks`：定义任务模型、任务入队、任务消费、任务执行和任务仓储接口。

它承接来自 REST API、内部定时器、生命周期服务、搜索索引控制器等入口的请求，把同步调用转成后台任务。例如用户在接口里点击“重新扫描 library”，接口层不会直接扫描目录，而是调用 `TaskEmitter.scanLibrary(...)` 入队一个 `Task.ScanLibrary`，后续由 `TaskProcessor` 取出并交给 `TaskHandler` 执行。

## 关键组成

`events/AsynchronousSpringEventsConfig.kt` 配置了名为 `applicationEventMulticaster` 的 Spring 事件广播器。它只在非 `test` profile 下生效，并把 `SimpleApplicationEventMulticaster` 的 executor 设置为 Spring 的 `applicationTaskExecutor`。这意味着普通 Spring application event 可以异步派发，避免事件监听器阻塞发布方。需要注意，测试环境下这个配置不启用，通常是为了让测试行为更可控。

`scheduler/LibraryScanScheduler.kt` 是周期扫描图书库的调度器。它依赖 Spring `TaskScheduler` 和本目录的 `TaskEmitter`。内部用 `ConcurrentHashMap<String, ScheduledTask>` 维护 `libraryId -> ScheduledTask` 的注册表。`scheduleScan(library)` 每次都会先取消该 library 旧的计划任务，如果 `library.scanInterval` 不是 `DISABLED`，再按固定频率注册新任务。真正触发时只做一件事：记录日志并调用 `taskEmitter.scanLibrary(library.id)`。它还实现了 `ScheduledTaskHolder`，因此 `/actuator/scheduledtasks` 可以展示这些动态注册的任务。

`tasks/Task.kt` 定义后台任务的 sealed class 层级。所有任务都有 `priority`、可选 `groupId`，以及必须实现的 `uniqueId`。`uniqueId` 用来标识任务唯一性，避免同类同目标任务重复堆积。优先级常量包括 `HIGHEST_PRIORITY = 8`、`HIGH_PRIORITY = 6`、`DEFAULT_PRIORITY = 4`、`LOW_PRIORITY = 2`、`LOWEST_PRIORITY = 0`。从已读片段和 `TaskHandler` 的分支看，任务覆盖了 library 扫描、查找待转换图书、查找缺页哈希图书、删除重复页、清空回收站、分析图书、生成缩略图、刷新 book/series 元数据、刷新本地 artwork、导入图书、转换 CBZ、修复扩展名、哈希文件、重建/升级搜索索引、删除 book/series、查找需要重新生成的缩略图等。

`tasks/TaskEmitter.kt` 是任务入口服务。外部模块基本不直接构造和保存任务，而是调用它提供的语义化方法，例如 `scanLibrary`、`analyzeBook`、`refreshBookMetadata`、`importBook`、`rebuildIndex`。它会把业务参数转换成具体 `Task`，调用 `TasksRepository.save(...)` 保存，然后发布 `TaskAddedEvent`。对于批量任务，它会一次性保存集合后发布同一个事件。这个类也会在入队前做少量业务筛选，例如 `hashBooksWithoutHash(library)` 会先检查 `library.hashFiles`，再查询缺 hash 的书并生成 `Task.HashBook`。

`tasks/TaskAddedEvent.kt` 是一个很小的事件对象，使用 `data object TaskAddedEvent` 表示“有新任务可处理”。它不携带任务内容，任务内容在 `TasksRepository` 里，事件只起到唤醒处理器的作用。

`tasks/TaskProcessor.kt` 是任务消费者。启动时实现 `InitializingBean.afterPropertiesSet()`，先调用 `tasksRepository.disown()` 重置那些上次运行中被某个 owner 认领但未完成的任务，然后把 `processTasks` 置为 `true`。它监听两个事件：`TaskAddedEvent` 和 `ApplicationReadyEvent`。当事件到来时，如果允许处理任务，就根据线程池容量调用 `takeAndProcess()`。线程池来自 `ThreadPoolTaskExecutorBuilder`，线程名前缀是 `taskProcessor-`，核心线程数来自 `KomgaSettingsProvider.taskPoolSize`，并且监听 `SettingChangedEvent.TaskPoolSize` 动态调整。

`tasks/TaskHandler.kt` 是任务执行器，也是最接近业务流程编排的类。`handleTask(task)` 内部用 `when (task)` 匹配不同 `Task` 子类，然后调用对应的 domain service 或 infrastructure lifecycle。它会记录执行耗时到 Micrometer timer `METER_TASKS_EXECUTION`，失败时记录日志并递增 `METER_TASKS_FAILURE` counter。它不会把异常继续抛给 `TaskProcessor`，而是在本层吞掉并记录指标。

`tasks/TasksRepository.kt` 是任务队列仓储接口，定义了 `hasAvailable()`、`takeFirst(owner)`、`findAll()`、`findAllGroupedByOwner()`、`count()`、`countBySimpleType()`、`save(...)`、`delete(...)`、`deleteAll()`、`deleteAllWithoutOwner()`、`disown()` 等方法。根据当前片段推断，具体实现不在该目录内，而是在邻近 infrastructure 或 persistence 模块中；依据是本目录只出现接口，`TaskProcessor`、`TaskEmitter` 都只依赖接口而不关心存储细节。

## 上下游关系

上游主要来自 interfaces 和 domain 层。

REST API 控制器会调用 `TaskEmitter`：例如 `interfaces/api/rest/LibraryController.kt` 触发 `scanLibrary`、`emptyTrash`、批量分析和刷新元数据；`BookController.kt` 触发单本分析、刷新元数据、导入、删除、缩略图重生成；`SeriesController.kt` 触发系列相关的分析、刷新和删除；`PageHashController.kt` 触发重复页删除。调度入口也会调用它：`interfaces/scheduler/PeriodicScannerController.kt` 用 `LibraryScanScheduler` 注册周期扫描，也可直接触发扫描；`interfaces/scheduler/SearchIndexController.kt` 用 `TaskEmitter.rebuildIndex(...)` 和 `upgradeIndex(...)` 处理搜索索引维护。

domain 层也会反向使用应用任务编排。例如 `domain/service/LibraryLifecycle.kt` 在新增或更新 library 后触发扫描、哈希、转换、修复扩展名等任务；`LibraryContentLifecycle.kt` 在扫描过程中发现 sidecar 或变更后触发 book/series 元数据与 artwork 刷新；`BookImporter.kt` 在导入 sidecar 后触发刷新；`SeriesLifecycle.kt` 在系列结构变化时触发书籍元数据刷新。

下游则主要是 domain service 和 infrastructure lifecycle。`TaskHandler` 会调用 `LibraryContentLifecycle`、`BookLifecycle`、`BookMetadataLifecycle`、`SeriesLifecycle`、`SeriesMetadataLifecycle`、`LocalArtworkLifecycle`、`BookImporter`、`BookConverter`、`BookPageEditor`、`PageHashLifecycle`、`SearchIndexLifecycle`，以及 `BookRepository`、`LibraryRepository`、`SeriesRepository` 查实体是否存在。

因此这个目录处在 interfaces/domain 和具体业务服务之间：上游发出“要做什么”，这里决定“排队、何时做、按什么顺序做”，下游负责“怎么做”。

## 运行/调用流程

典型流程是：

1. 外部入口调用 `TaskEmitter`，例如 `taskEmitter.scanLibrary(library.id, deep, HIGHEST_PRIORITY)`。
2. `TaskEmitter` 构造具体任务，例如 `Task.ScanLibrary(libraryId, scanDeep, priority)`。
3. `TaskEmitter.submitTask(...)` 调用 `tasksRepository.save(task)` 保存任务，然后发布 `TaskAddedEvent`。
4. `TaskProcessor` 监听到 `TaskAddedEvent`，检查 `processTasks` 和线程池状态。
5. `TaskProcessor.takeAndProcess()` 调用 `tasksRepository.takeFirst(owner)` 认领一个可用任务。
6. `TaskProcessor` 把任务交给 `TaskHandler.handleTask(task)`。
7. `TaskHandler` 根据任务类型调用具体服务。
8. 执行成功后，`TaskProcessor` 调用 `tasksRepository.delete(task.uniqueId)` 删除队列项，并再次调用 `processAvailableTask()` 尝试继续消费后续任务。

扫描 library 是一个很能体现编排关系的例子。`Task.ScanLibrary` 被执行时，`TaskHandler` 先通过 `libraryRepository.findByIdOrNull(...)` 找 library；存在则调用 `libraryContentLifecycle.scanRootFolder(library, task.scanDeep)` 真正扫描目录。扫描完成后，它不会在当前调用栈里继续同步完成所有后处理，而是通过 `TaskEmitter` 再派生一批后续任务：分析 unknown/outdated 图书、修复扩展名、查找待转换图书、查找缺页哈希图书、查找可自动删除的重复页、补文件 hash、补 Koreader hash。这形成了一个任务链。

另一个例子是分析图书：`Task.AnalyzeBook` 执行 `bookLifecycle.analyzeAndPersist(book)` 后得到 `BookAction` 集合。如果结果包含 `GENERATE_THUMBNAIL`，就继续入队 `GenerateBookThumbnail`；如果包含 `REFRESH_METADATA`，就继续入队 `RefreshBookMetadata`。`RefreshBookMetadata` 完成后又会触发 `RefreshSeriesMetadata`，后者完成后触发 `AggregateSeriesMetadata`。这说明任务系统不只是异步执行器，也承担了跨实体后处理流程的串联。

周期扫描的流程稍有不同。`LibraryScanScheduler.scheduleScan(library)` 注册的是定时器，但定时器触发时仍然只入队 `Task.ScanLibrary`，不直接执行扫描。这样手动扫描、library 生命周期触发扫描、周期扫描最终都汇入同一套任务队列和处理逻辑。

## 小白阅读顺序

建议先读 `tasks/Task.kt`，理解系统里有哪些后台任务，以及 `priority`、`groupId`、`uniqueId` 的含义。这里是任务系统的“词汇表”。

第二步读 `tasks/TaskEmitter.kt`。重点看每个 public 方法如何把业务语言转换为 `Task`，以及 `submitTask`、`submitTasks` 如何统一保存任务并发布 `TaskAddedEvent`。读完它以后，就能理解外部为什么很少直接操作 `TasksRepository`。

第三步读 `tasks/TaskProcessor.kt`。重点看 `@EventListener(TaskAddedEvent::class, ApplicationReadyEvent::class)`、线程池大小、`takeAndProcess()`、任务删除和递归继续处理。这里回答的是“任务什么时候被拿出来跑”。

第四步读 `tasks/TaskHandler.kt`。这是最长也最重要的编排文件。不要一开始逐行抠所有分支，可以按实体类型分组看：library 相关、book 相关、series 相关、索引相关、删除相关。重点观察它如何调用 domain service，以及哪些任务会继续派生新任务。

第五步读 `scheduler/LibraryScanScheduler.kt`，理解周期任务如何注册和取消，以及它为什么只调用 `TaskEmitter.scanLibrary(...)`。

最后读 `events/AsynchronousSpringEventsConfig.kt` 和 `tasks/TasksRepository.kt`。前者帮助理解事件异步化，后者帮助理解任务存储接口边界。若要继续深入，可以再找 `TasksRepository` 的具体实现，查看任务如何排序、如何持久化、`owner` 如何避免并发重复消费。

## 常见误区

第一个误区是把 `TaskEmitter` 当成执行器。它只是入队器，真正执行在 `TaskHandler`，消费调度在 `TaskProcessor`。

第二个误区是以为 `TaskAddedEvent` 携带任务详情。它只是一个唤醒信号，任务详情保存在 `TasksRepository`。因此监听器收到事件后还要调用 `takeFirst()` 从仓储取任务。

第三个误区是认为 `priority` 越高一定会马上执行。优先级会影响仓储取任务的顺序，但实际并发还受 `taskPoolSize`、当前活跃线程数、`TasksRepository` 实现、任务是否已被 owner 认领等因素影响。根据当前片段推断，排序和去重细节在 `TasksRepository` 的具体实现中。

第四个误区是忽略任务链。很多任务执行后会继续产生任务，例如扫描 library 后派生分析、转换、哈希、重复页清理；刷新 book metadata 后派生 series metadata 刷新；series metadata 刷新后派生聚合。阅读时要顺着 `taskEmitter.*` 调用继续追踪。

第五个误区是把 `LibraryScanScheduler` 看成扫描实现。它只是周期触发器，真正扫描仍由 `Task.ScanLibrary` 经 `TaskHandler` 调用 `LibraryContentLifecycle.scanRootFolder(...)` 完成。

第六个误区是忽略测试 profile 差异。`AsynchronousSpringEventsConfig` 在 `!test` 下才启用，所以测试环境中的事件派发行为可能和生产运行时不同。对于调试任务触发时序，这一点很重要。

第七个误区是认为任务失败会自动重试。`TaskHandler.handleTask` 捕获异常、记录失败指标，但从当前片段看不到重试入队逻辑；`TaskProcessor` 在 `handleTask` 返回后仍会删除该任务。因此是否有重试需要继续查看 `TasksRepository` 实现或更外层机制，不能仅凭这里假设。
