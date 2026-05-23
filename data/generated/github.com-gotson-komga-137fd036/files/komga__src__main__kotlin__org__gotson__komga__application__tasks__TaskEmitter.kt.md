# 文件：komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskEmitter.kt

## 它负责什么

`TaskEmitter.kt` 定义了 Spring Bean `TaskEmitter`，它是 Komga 后台任务系统里的“任务生产者/投递入口”。

它本身不执行扫描、分析、转码、索引重建等耗时动作，而是把这些动作包装成 `Task` 子类对象，保存到 `TasksRepository`，然后通过 `ApplicationEventPublisher` 发布 `TaskAddedEvent`，通知后续任务处理链路“有新任务了”。

可以把它理解为后台任务队列的统一门面：

- 外部模块想做“扫描书库”，调用 `scanLibrary(...)`。
- 想分析一本书，调用 `analyzeBook(...)`。
- 想生成封面缩略图，调用 `generateBookThumbnail(...)`。
- 想刷新元数据、重建索引、导入图书、删除文件，也都通过这里提交。
- 真正执行任务的是同目录下的 `TaskHandler.kt`，而不是 `TaskEmitter.kt`。

这个文件的核心价值在于：把业务意图转换成标准化的 `Task`，并统一处理日志、入队、事件通知。

## 关键组成

### 1. `TaskEmitter` 类

`TaskEmitter` 使用 `@Service` 标记，是 Spring 管理的服务类：

```kotlin
@Service
class TaskEmitter(
  private val bookRepository: BookRepository,
  private val bookConverter: BookConverter,
  private val tasksRepository: TasksRepository,
  private val eventPublisher: ApplicationEventPublisher,
)
```

它依赖四个对象：

- `BookRepository`：用于查询图书，尤其是批量找出需要分析、补 hash、补页 hash 的书。
- `BookConverter`：用于找出扩展名不匹配、可转换为 CBZ 的图书。
- `TasksRepository`：任务队列/任务仓库接口，`TaskEmitter` 最终会把任务保存到这里。
- `ApplicationEventPublisher`：Spring 事件发布器，用来发布 `TaskAddedEvent`。

这里要注意，`TaskEmitter` 不是单纯的“包装器”。部分方法会先查询数据库或领域服务，再把查询结果映射成一批任务。

### 2. 单任务提交：`submitTask`

文件末尾有私有方法：

```kotlin
private fun submitTask(task: Task) {
  logger.info { "Sending task: $task" }
  tasksRepository.save(task)
  eventPublisher.publishEvent(TaskAddedEvent)
}
```

这是所有单个任务的最终出口。它做三件事：

1. 记录日志。
2. 调用 `tasksRepository.save(task)` 保存任务。
3. 发布 `TaskAddedEvent`。

所以，例如：

```kotlin
fun scanLibrary(
  libraryId: String,
  scanDeep: Boolean = false,
  priority: Int = DEFAULT_PRIORITY,
) {
  submitTask(Task.ScanLibrary(libraryId, scanDeep, priority))
}
```

调用 `scanLibrary` 时，不会立刻扫描目录，而是创建一个 `Task.ScanLibrary`，然后送入任务仓库。

### 3. 批量任务提交：`submitTasks`

另一个私有方法负责批量任务：

```kotlin
private fun submitTasks(tasks: Collection<Task>) {
  logger.info { "Sending tasks: $tasks" }
  tasksRepository.save(tasks)
  eventPublisher.publishEvent(TaskAddedEvent)
}
```

批量方法也只发布一次 `TaskAddedEvent`。例如批量分析书籍：

```kotlin
fun analyzeBook(
  books: Collection<Book>,
  priority: Int = DEFAULT_PRIORITY,
) {
  books
    .map { Task.AnalyzeBook(it.id, priority, it.seriesId) }
    .let { submitTasks(it) }
}
```

这说明 `TaskEmitter` 倾向于先构造完整任务集合，再统一保存和通知。

### 4. 任务类型来自 `Task.kt`

同目录的 `Task.kt` 定义了密封类 `Task` 以及各种具体任务类型：

- `Task.ScanLibrary`
- `Task.EmptyTrash`
- `Task.AnalyzeBook`
- `Task.GenerateBookThumbnail`
- `Task.RefreshBookMetadata`
- `Task.RefreshSeriesMetadata`
- `Task.AggregateSeriesMetadata`
- `Task.ImportBook`
- `Task.ConvertBook`
- `Task.RepairExtension`
- `Task.HashBook`
- `Task.HashBookPages`
- `Task.HashBookKoreader`
- `Task.RebuildIndex`
- `Task.UpgradeIndex`
- `Task.DeleteBook`
- `Task.DeleteSeries`
- `Task.FindBookThumbnailsToRegenerate`

`TaskEmitter.kt` 基本就是这些 `Task` 类型的工厂和投递器。

`Task.kt` 里还定义了优先级常量：

```kotlin
const val HIGHEST_PRIORITY = 8
const val HIGH_PRIORITY = 6
const val DEFAULT_PRIORITY = 4
const val LOW_PRIORITY = 2
const val LOWEST_PRIORITY = 0
```

`TaskEmitter` 默认使用 `DEFAULT_PRIORITY`，部分后台补全任务会使用 `LOWEST_PRIORITY` 或调用方传入的优先级。

### 5. 分组字段 `groupId`

部分任务构造时会传 `groupId`，例如：

```kotlin
Task.AnalyzeBook(it.id, groupId = it.seriesId)
Task.ConvertBook(it.id, priority, it.seriesId)
Task.RefreshBookMetadata(book.id, capabilities, priority, book.seriesId)
```

`groupId` 在 `Task.kt` 的基类中定义：

```kotlin
sealed class Task(
  val priority: Int = DEFAULT_PRIORITY,
  val groupId: String? = null,
)
```

根据当前片段推断，`groupId` 用于任务队列调度时识别同一系列相关任务，避免或控制同一组任务的并发执行。依据是 `AnalyzeBook`、`ConvertBook`、`RefreshBookMetadata`、`ImportBook` 等和某个 series 强相关的任务都会传入 `seriesId` 作为 `groupId`。

## 上下游关系

### 上游：谁会调用 `TaskEmitter`

从当前阅读到的上下文看，`TaskEmitter` 至少被这些模块调用：

- `komga/src/main/kotlin/org/gotson/komga/application/scheduler/LibraryScanScheduler.kt`
- `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskHandler.kt`

其中 `TaskHandler.kt` 是非常重要的上游兼下游。它执行某个任务后，经常会继续通过 `TaskEmitter` 派发后续任务，形成任务链。

例如 `TaskHandler` 执行 `Task.ScanLibrary` 时，会：

1. 通过 `libraryContentLifecycle.scanRootFolder(...)` 扫描书库。
2. 调用 `taskEmitter.analyzeUnknownAndOutdatedBooks(library)`。
3. 调用 `taskEmitter.repairExtensions(library, LOW_PRIORITY)`。
4. 调用 `taskEmitter.findBooksToConvert(library, LOWEST_PRIORITY)`。
5. 调用 `taskEmitter.findBooksWithMissingPageHash(library, LOWEST_PRIORITY)`。
6. 调用 `taskEmitter.findDuplicatePagesToDelete(library, LOWEST_PRIORITY)`。
7. 调用 `taskEmitter.hashBooksWithoutHash(library)`。
8. 调用 `taskEmitter.hashBooksWithoutHashKoreader(library)`。

这说明 `TaskEmitter` 不只服务外部入口，也服务任务内部的“后续任务编排”。

### 下游：任务保存与事件通知

`TaskEmitter` 的直接下游是：

- `TasksRepository`
- `TaskAddedEvent`
- 后续消费 `TaskAddedEvent` 的任务处理机制

`TasksRepository` 是同目录下的接口 `komga/src/main/kotlin/org/gotson/komga/application/tasks/TasksRepository.kt`。从 `TaskEmitter` 的调用方式可以看出，它至少提供两个保存入口：

```kotlin
tasksRepository.save(task)
tasksRepository.save(tasks)
```

`TaskEmitter` 保存任务后，会发布：

```kotlin
eventPublisher.publishEvent(TaskAddedEvent)
```

`TaskAddedEvent.kt` 文件很小，按文件名和用法看，它是一个任务新增事件，用来触发任务处理器检查队列。

根据当前片段推断，`TaskProcessor.kt` 负责监听或响应这类事件，并从 `TasksRepository` 取出任务交给 `TaskHandler` 执行。依据是同目录存在 `TaskProcessor.kt`，且 `TaskHandler` 公开了 `handleTask(task: Task)`。

### 领域服务关系

`TaskEmitter` 自己只直接使用少量领域能力：

- `BookRepository`：筛选需要处理的书。
- `BookConverter`：筛选扩展名不匹配的书。
- `TasksRepository`：保存任务。
- `ApplicationEventPublisher`：通知任务系统。

真正的业务执行在 `TaskHandler.kt` 中，那里会调用：

- `LibraryContentLifecycle`
- `BookLifecycle`
- `BookMetadataLifecycle`
- `SeriesMetadataLifecycle`
- `LocalArtworkLifecycle`
- `BookImporter`
- `BookConverter`
- `BookPageEditor`
- `SearchIndexLifecycle`
- `PageHashLifecycle`

这体现了一个明确分层：`TaskEmitter` 负责“发任务”，`TaskHandler` 负责“做任务”。

## 运行/调用流程

### 典型流程一：扫描书库

调用入口：

```kotlin
taskEmitter.scanLibrary(libraryId, scanDeep, priority)
```

`TaskEmitter` 做的事：

1. 创建 `Task.ScanLibrary(libraryId, scanDeep, priority)`。
2. 调用 `submitTask(...)`。
3. 保存到 `TasksRepository`。
4. 发布 `TaskAddedEvent`。

后续根据 `TaskHandler.kt` 的逻辑，执行 `Task.ScanLibrary` 时会：

1. 查询书库是否存在。
2. 调用 `libraryContentLifecycle.scanRootFolder(library, task.scanDeep)` 扫描根目录。
3. 扫描完成后继续派发多个低优先级补充任务：
   - 分析 unknown/outdated 图书。
   - 修复扩展名。
   - 查找可转换图书。
   - 查找缺失页面 hash 的图书。
   - 查找可删除重复页。
   - 补充文件 hash。
   - 补充 Koreader hash。

所以扫描书库不是一个孤立动作，而是一个任务链的起点。

### 典型流程二：分析未知或过期图书

入口：

```kotlin
fun analyzeUnknownAndOutdatedBooks(library: Library)
```

它会先查询 `BookRepository.findAll(...)`，条件是：

- 图书属于当前 library。
- `Media.Status` 是 `UNKNOWN` 或 `OUTDATED`。

排序方式是：

```kotlin
Sort.by(Sort.Order.asc("seriesId"), Sort.Order.asc("number"))
```

然后把每本书映射成：

```kotlin
Task.AnalyzeBook(it.id, groupId = it.seriesId)
```

最后批量提交。

这里有两个细节：

- 它不是让数据库或生命周期服务直接分析，而是先筛选出书，再发任务。
- 按 `seriesId` 和 `number` 排序，说明系统希望分析任务尽量按系列和册序稳定处理。

### 典型流程三：分析单本书后的后续任务

`TaskEmitter` 提交 `Task.AnalyzeBook`：

```kotlin
Task.AnalyzeBook(book.id, priority, book.seriesId)
```

`TaskHandler` 执行分析后：

```kotlin
val actions = bookLifecycle.analyzeAndPersist(book)
if (actions.contains(BookAction.GENERATE_THUMBNAIL)) taskEmitter.generateBookThumbnail(...)
if (actions.contains(BookAction.REFRESH_METADATA)) taskEmitter.refreshBookMetadata(...)
```

也就是说，分析任务执行完可能继续产生：

- `Task.GenerateBookThumbnail`
- `Task.RefreshBookMetadata`

`TaskEmitter` 在这里承担“二次派发”的角色。

### 典型流程四：刷新书籍元数据到刷新系列元数据

`TaskEmitter.refreshBookMetadata(book, capabilities, priority)` 会提交：

```kotlin
Task.RefreshBookMetadata(book.id, capabilities, priority, book.seriesId)
```

`TaskHandler` 执行后：

1. 调用 `bookMetadataLifecycle.refreshMetadata(book, task.capabilities)`。
2. 再调用 `taskEmitter.refreshSeriesMetadata(book.seriesId, priority = task.priority - 1)`。

接着 `Task.RefreshSeriesMetadata` 执行后，又会：

1. 调用 `seriesMetadataLifecycle.refreshMetadata(series)`。
2. 派发 `taskEmitter.aggregateSeriesMetadata(series.id, priority = task.priority)`。

所以元数据刷新链路大致是：

```text
RefreshBookMetadata
-> RefreshSeriesMetadata
-> AggregateSeriesMetadata
```

这也是为什么 `TaskEmitter` 里有许多看似简单的包装方法：它们被任务执行器反复用于串联后续工作。

### 典型流程五：补 hash / 页面 hash / Koreader hash

`TaskEmitter` 有三类 hash 相关方法：

```kotlin
hashBooksWithoutHash(library)
hashBooksWithoutHashKoreader(library)
findBooksWithMissingPageHash(library, priority)
```

前两个会根据 library 配置决定是否启用：

```kotlin
if (library.hashFiles) ...
if (library.hashKoreader) ...
```

然后查询需要补 hash 的书，提交低优先级任务：

```kotlin
Task.HashBook(it.id, LOWEST_PRIORITY)
Task.HashBookKoreader(it.id, LOWEST_PRIORITY)
```

`findBooksWithMissingPageHash` 则先提交一个查找任务：

```kotlin
Task.FindBooksWithMissingPageHash(library.id, priority)
```

真正查找缺失页面 hash 的逻辑在 `TaskHandler` 中调用 `pageHashLifecycle.getBookIdsWithMissingPageHash(library)`，然后再通过 `taskEmitter.hashBookPages(...)` 派发具体图书的 `Task.HashBookPages`。

这里的设计是两阶段的：

1. 先发“查找哪些书需要处理”的任务。
2. 查找任务执行后，再发“处理具体书”的任务。

### 典型流程六：导入图书

入口：

```kotlin
fun importBook(
  sourceFile: String,
  seriesId: String,
  copyMode: CopyMode,
  destinationName: String?,
  upgradeBookId: String?,
  priority: Int = DEFAULT_PRIORITY,
)
```

它提交：

```kotlin
Task.ImportBook(sourceFile, seriesId, copyMode, destinationName, upgradeBookId, priority)
```

`TaskHandler` 执行导入后，会：

1. 查询目标 series。
2. 调用 `bookImporter.importBook(...)`。
3. 导入成功后调用 `taskEmitter.analyzeBook(importedBook, priority = task.priority + 1)`。

所以导入之后会自动进入分析流程。

## 小白阅读顺序

1. 先读 `komga/src/main/kotlin/org/gotson/komga/application/tasks/Task.kt`  
   这里定义了所有任务类型、优先级、`uniqueId` 和 `groupId`。如果不先知道有哪些 `Task`，读 `TaskEmitter.kt` 会觉得全是包装方法。

2. 再读 `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskEmitter.kt`  
   重点看每个公开方法如何把业务参数转换成 `Task.Xxx`。不要急着追业务实现，先理解“这里负责发什么任务”。

3. 接着读 `TaskEmitter.kt` 末尾的 `submitTask` 和 `submitTasks`  
   这是全文件的真正出口。所有公开方法最后都归到这两个私有方法：保存任务，然后发布 `TaskAddedEvent`。

4. 然后读 `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskHandler.kt`  
   这里能看到每种 `Task` 被执行时具体做什么，以及执行后是否继续通过 `TaskEmitter` 派发新任务。

5. 最后再读 `TasksRepository.kt`、`TaskProcessor.kt`、`TaskAddedEvent.kt`  
   这几个文件能补齐任务队列如何存储、如何被唤醒、如何被消费的机制。根据当前片段推断，`TaskProcessor` 是连接 `TasksRepository` 和 `TaskHandler` 的调度组件。

## 常见误区

### 误区一：以为 `TaskEmitter` 会直接执行业务逻辑

`TaskEmitter` 不会真正扫描书库、生成缩略图、刷新元数据或删除文件。它只创建任务并提交。真正执行在 `TaskHandler.kt`。

例如：

```kotlin
generateBookThumbnail(bookId)
```

只是提交 `Task.GenerateBookThumbnail`，不是马上生成缩略图。

### 误区二：忽略 `TaskAddedEvent`

`tasksRepository.save(...)` 只是把任务放进仓库。后面的：

```kotlin
eventPublisher.publishEvent(TaskAddedEvent)
```

同样关键。它负责通知任务系统有新任务可处理。如果只保存任务但不发事件，任务可能不会及时被消费。

### 误区三：以为所有方法都是简单包装

大部分方法确实只是包装 `Task`，但不是全部。

例如：

```kotlin
analyzeUnknownAndOutdatedBooks(library)
```

会先查数据库，筛选 `Media.Status.UNKNOWN` 和 `Media.Status.OUTDATED` 的书，再批量提交分析任务。

```kotlin
repairExtensions(library)
```

会先判断 `library.repairExtensions`，再通过 `bookConverter.getMismatchedExtensionBooks(library)` 找出需要修复扩展名的书。

```kotlin
hashBooksWithoutHash(library)
```

会先判断 `library.hashFiles`，再查询缺失 hash 的图书。

这些方法已经包含了轻量的“任务发现”逻辑。

### 误区四：忽略优先级的变化

`TaskEmitter` 默认使用 `DEFAULT_PRIORITY`，但任务链中会主动调整优先级。

例如 `TaskHandler` 执行 `AnalyzeBook` 后，如果需要生成缩略图，会提交：

```kotlin
taskEmitter.generateBookThumbnail(book.id, priority = task.priority + 1)
```

刷新书籍元数据后，会提交：

```kotlin
taskEmitter.refreshSeriesMetadata(book.seriesId, priority = task.priority - 1)
```

所以优先级不是固定值，而是任务编排的一部分。

### 误区五：忽略 library 配置开关

某些任务是否提交取决于 `Library` 配置：

```kotlin
if (library.hashFiles) ...
if (library.hashKoreader) ...
if (library.repairExtensions) ...
```

因此，不是每次扫描书库都会补 hash、修复扩展名或执行 Koreader hash。要结合 `Library` 实例的配置理解行为。

### 误区六：把 `groupId` 当成业务 ID 本身

`groupId` 通常传 `seriesId`，但它不是任务的主标识。任务真正的去重/唯一标识来自每个 `Task` 子类的 `uniqueId`。

例如：

```kotlin
Task.AnalyzeBook(bookId, priority, groupId = seriesId)
```

其中：

- `bookId` 决定分析哪本书。
- `uniqueId` 是 `ANALYZE_BOOK_$bookId`。
- `groupId` 是 `seriesId`，更像调度分组信息。

根据当前片段推断，`groupId` 是给任务队列调度使用的，而不是业务查询用的主键。

### 误区七：认为 `scanLibrary` 完成就代表所有后续处理完成

`scanLibrary` 只提交扫描任务。扫描任务执行完后，还会派发分析、转码发现、页面 hash、重复页清理、文件 hash 等后续任务。因此“扫描完成”和“所有书库维护任务完成”不是同一个概念。
