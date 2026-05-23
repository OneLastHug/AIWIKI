# 文件：komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskAddedEvent.kt

## 它负责什么

`TaskAddedEvent.kt` 定义了一个非常小但关键的应用事件：

```kotlin
package org.gotson.komga.application.tasks

data object TaskAddedEvent
```

它的职责不是描述任务内容，也不是执行任务，而是作为“有新任务加入队列”的通知信号。换句话说，当系统把一个或多个 `Task` 保存到任务仓库后，会发布 `TaskAddedEvent`，从而唤醒任务处理器去检查队列并开始消费任务。

这个文件位于 `org.gotson.komga.application.tasks` 包下，和 `Task`、`TaskEmitter`、`TaskProcessor`、`TaskHandler`、`TasksRepository` 同属任务调度模块。它是任务系统中“入队”和“处理”之间的桥接事件。

## 关键组成

这个文件只有两个组成部分。

第一部分是包声明：

```kotlin
package org.gotson.komga.application.tasks
```

它把 `TaskAddedEvent` 放在应用层任务模块中。由于 `TaskEmitter` 和 `TaskProcessor` 也在同一个包内，它们使用 `TaskAddedEvent` 时不需要额外 import。

第二部分是事件对象本身：

```kotlin
data object TaskAddedEvent
```

这里使用的是 Kotlin 的 `data object`，表示一个全局唯一的单例对象，并且具备适合数据对象的 `toString`、`equals`、`hashCode` 表现。对这个场景来说，事件不携带任何字段，因此用单例对象比定义普通 class 更合适。

它不包含：

- 任务 ID；
- 任务类型；
- 优先级；
- 创建时间；
- 队列名称；
- 处理状态。

这些信息都不属于 `TaskAddedEvent`。真正的任务数据保存在 `TasksRepository` 中，任务类型定义在 `Task.kt` 中，处理逻辑由 `TaskProcessor` 和 `TaskHandler` 完成。

## 上下游关系

上游是 `TaskEmitter`。

`TaskEmitter` 是任务提交入口，提供了大量面向业务语义的方法，例如：

- `scanLibrary`
- `emptyTrash`
- `analyzeBook`
- `generateBookThumbnail`
- `refreshBookMetadata`
- `refreshSeriesMetadata`
- `importBook`
- `rebuildIndex`
- `deleteBook`
- `findBookThumbnailsToRegenerate`

这些方法最终都会调用内部的 `submitTask` 或 `submitTasks`。在 `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskEmitter.kt` 中可以看到核心发布逻辑：

```kotlin
private fun submitTask(task: Task) {
  logger.info { "Sending task: $task" }
  tasksRepository.save(task)
  eventPublisher.publishEvent(TaskAddedEvent)
}

private fun submitTasks(tasks: Collection<Task>) {
  logger.info { "Sending tasks: $tasks" }
  tasksRepository.save(tasks)
  eventPublisher.publishEvent(TaskAddedEvent)
}
```

也就是说，`TaskAddedEvent` 总是在任务保存到 `TasksRepository` 之后发布。这个顺序很重要：监听者收到事件后，可以立即去仓库中取任务。

下游是 `TaskProcessor`。

在 `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskProcessor.kt` 中，`TaskProcessor.processAvailableTask` 同时监听两个事件：

```kotlin
@EventListener(TaskAddedEvent::class, ApplicationReadyEvent::class)
fun processAvailableTask()
```

这表示任务处理器会在两种情况下尝试处理任务：

- Spring 应用启动完成时，即 `ApplicationReadyEvent`；
- 有新任务加入时，即 `TaskAddedEvent`。

因此，`TaskAddedEvent` 的作用可以概括为：通知 `TaskProcessor` 队列可能有新任务了，应该尝试消费。

中间的持久化抽象是 `TasksRepository`，定义在 `komga/src/main/kotlin/org/gotson/komga/application/tasks/TasksRepository.kt`。它提供：

- `save(task: Task)`
- `save(tasks: Collection<Task>)`
- `hasAvailable()`
- `takeFirst(owner: String = Thread.currentThread().name)`
- `delete(taskId: String)`
- `disown()`
- `count()`
- `findAll()`

`TaskAddedEvent` 本身不访问 `TasksRepository`，但它的语义依赖这个仓库：事件只表示“仓库里刚刚保存过任务”，真正要处理什么仍然由仓库决定。

## 运行/调用流程

典型流程如下。

第一步，外部业务调用 `TaskEmitter`。

例如 REST Controller、Scheduler、Domain Service 都可能注入 `TaskEmitter`。从搜索结果看，调用来源包括：

- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/BookController.kt`
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/LibraryController.kt`
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/SeriesController.kt`
- `komga/src/main/kotlin/org/gotson/komga/interfaces/scheduler/PeriodicScannerController.kt`
- `komga/src/main/kotlin/org/gotson/komga/application/scheduler/LibraryScanScheduler.kt`
- `komga/src/main/kotlin/org/gotson/komga/domain/service/LibraryLifecycle.kt`
- `komga/src/main/kotlin/org/gotson/komga/domain/service/BookImporter.kt`
- `komga/src/main/kotlin/org/gotson/komga/domain/service/SeriesLifecycle.kt`
- `komga/src/main/kotlin/org/gotson/komga/domain/service/LibraryContentLifecycle.kt`

这些调用方不直接处理后台任务，而是把任务提交给 `TaskEmitter`。

第二步，`TaskEmitter` 构造具体的 `Task`。

具体任务类型定义在 `komga/src/main/kotlin/org/gotson/komga/application/tasks/Task.kt`。它是一个 sealed class，下面有很多子类，例如：

- `Task.ScanLibrary`
- `Task.EmptyTrash`
- `Task.AnalyzeBook`
- `Task.GenerateBookThumbnail`
- `Task.RefreshBookMetadata`
- `Task.RefreshSeriesMetadata`
- `Task.ImportBook`
- `Task.ConvertBook`
- `Task.RebuildIndex`
- `Task.DeleteBook`

每个任务都有 `priority`，部分任务有 `groupId`，每个任务都有 `uniqueId`。测试 `TaskProcessorTest` 说明相同任务会因为唯一 ID 去重，且高优先级任务会先执行。这个去重和排序行为根据当前片段推断主要由 `TasksRepository` 的具体实现负责，因为接口中只有 `save`、`takeFirst` 等方法，目标片段没有展示底层实现。

第三步，`TaskEmitter` 保存任务并发布 `TaskAddedEvent`。

单个任务走：

```kotlin
tasksRepository.save(task)
eventPublisher.publishEvent(TaskAddedEvent)
```

多个任务走：

```kotlin
tasksRepository.save(tasks)
eventPublisher.publishEvent(TaskAddedEvent)
```

注意，无论提交一个任务还是一批任务，都只发布同一个无载荷事件。事件只是“触发检查队列”，不是“逐个任务发送消息”。

第四步，Spring 事件机制调用 `TaskProcessor.processAvailableTask`。

`TaskProcessor` 使用 `@EventListener(TaskAddedEvent::class, ApplicationReadyEvent::class)` 监听事件。收到 `TaskAddedEvent` 后，它会先检查 `processTasks` 标志。如果当前允许处理任务，就根据线程池状态决定提交多少个 `takeAndProcess` 到 executor。

核心逻辑是：

- 如果线程池大小是 1，就提交一次 `takeAndProcess()`；
- 如果线程池大小大于 1，就在有可用任务且活跃线程数小于核心线程数时循环提交；
- 如果 `processTasks` 为 false，则只记录日志，不处理。

第五步，`TaskProcessor.takeAndProcess` 从仓库拿任务。

`takeAndProcess` 会调用：

```kotlin
val task = tasksRepository.takeFirst()
```

如果拿到任务，就交给 `TaskHandler.handleTask(task)`。处理完成后，调用：

```kotlin
tasksRepository.delete(task.uniqueId)
processAvailableTask()
```

最后这次递归式调用很关键：它让处理器在完成一个任务后继续检查队列，而不是只处理事件触发时的第一个任务。

第六步，`TaskHandler` 执行业务逻辑。

`TaskHandler` 根据 `when (task)` 分发到不同服务。例如：

- `Task.ScanLibrary` 调用 `libraryContentLifecycle.scanRootFolder`，然后继续发出分析、修复、转换、哈希等后续任务；
- `Task.AnalyzeBook` 调用 `bookLifecycle.analyzeAndPersist`，并根据返回的 `BookAction` 决定是否继续提交缩略图生成或元数据刷新任务；
- `Task.RefreshBookMetadata` 调用 `bookMetadataLifecycle.refreshMetadata`，随后提交系列元数据刷新任务；
- `Task.RebuildIndex` 调用 `searchIndexLifecycle.rebuildIndex`；
- `Task.ImportBook` 调用 `bookImporter.importBook`，随后提交 `analyzeBook`。

这说明 `TaskAddedEvent` 触发的不是单次孤立处理，而是整个后台任务链路的推进。

## 小白阅读顺序

建议按下面顺序阅读，不要一开始就陷入 `TaskHandler` 的大量业务分支。

1. 先看 `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskAddedEvent.kt`

   明确它只是一个无字段单例事件，作用是通知“有任务加入”。

2. 再看 `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskEmitter.kt` 的底部

   重点看 `submitTask` 和 `submitTasks`。这两个方法解释了 `TaskAddedEvent` 何时发布：任务保存之后发布。

3. 再看 `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskProcessor.kt`

   重点看 `@EventListener(TaskAddedEvent::class, ApplicationReadyEvent::class)`、`processAvailableTask`、`takeAndProcess`。这里能看懂事件如何唤醒任务执行器。

4. 再看 `komga/src/main/kotlin/org/gotson/komga/application/tasks/TasksRepository.kt`

   这个接口说明任务队列具备保存、取出、删除、统计、重置 owner 等能力。它是事件和实际任务之间的存储层抽象。

5. 再看 `komga/src/main/kotlin/org/gotson/komga/application/tasks/Task.kt`

   这里定义了所有任务类型、优先级常量、`uniqueId`、`groupId`。理解它后，才能看懂队列中到底有哪些任务。

6. 最后看 `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskHandler.kt`

   这个文件业务分支很多，适合在理解任务调度框架后再读。它回答的是“每种任务具体做什么”。

7. 如果想验证行为，再看 `komga/src/test/kotlin/org/gotson/komga/application/tasks/TaskProcessorTest.kt`

   其中两个测试说明了任务系统的两个重要行为：相似任务只执行一次，高优先级任务先执行。

## 常见误区

第一个误区：以为 `TaskAddedEvent` 携带任务数据。

它不携带任何任务字段。任务数据保存在 `TasksRepository`，任务结构定义在 `Task.kt`。`TaskAddedEvent` 只是一个通知信号。

第二个误区：以为发布一次 `TaskAddedEvent` 只会处理一个任务。

不一定。`TaskProcessor.processAvailableTask` 会根据线程池大小和 `tasksRepository.hasAvailable()` 决定是否并发拉取多个任务。并且每个任务完成后还会再次调用 `processAvailableTask()`，继续推进队列。

第三个误区：以为没有 `TaskAddedEvent`，启动时就不会处理历史任务。

`TaskProcessor` 同时监听 `ApplicationReadyEvent`。应用启动完成时也会调用 `processAvailableTask()`。此外，`afterPropertiesSet` 中还会调用 `tasksRepository.disown()` 重置未完成任务的 owner，然后将 `processTasks` 设为 true。根据当前片段推断，这是为了让应用重启后遗留的未完成任务重新变成可处理状态。

第四个误区：以为 `TaskAddedEvent` 是领域事件。

它更像应用层内部事件，而不是领域模型事件。它位于 `org.gotson.komga.application.tasks` 包，发布者是 `TaskEmitter`，监听者是 `TaskProcessor`，语义集中在后台任务调度，不直接表达漫画库、书籍、系列等领域事实。

第五个误区：以为 `data object` 是为了存储状态。

这里使用 `data object` 不是为了保存数据，而是因为事件没有 payload，只需要一个唯一实例即可。它的存在意义是类型本身：Spring 通过事件对象的类型匹配监听器。

第六个误区：以为任务执行入口在 `TaskAddedEvent.kt`。

真正执行入口在 `TaskProcessor.processAvailableTask` 和 `TaskHandler.handleTask`。`TaskAddedEvent.kt` 只是定义了一个事件类型。读代码时如果只看这个文件，会觉得它“什么都没做”，但它在 Spring 事件机制里承担触发器角色。

第七个误区：以为 `TaskEmitter` 发布事件前后顺序无所谓。

这里必须先 `tasksRepository.save(...)`，再 `eventPublisher.publishEvent(TaskAddedEvent)`。如果顺序反过来，监听器收到事件时可能还取不到任务。当前实现的顺序保证了事件触发处理时，队列状态已经更新。
