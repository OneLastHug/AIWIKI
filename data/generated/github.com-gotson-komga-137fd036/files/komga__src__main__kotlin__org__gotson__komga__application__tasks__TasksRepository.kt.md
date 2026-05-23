# 文件：komga/src/main/kotlin/org/gotson/komga/application/tasks/TasksRepository.kt

## 它负责什么

`TasksRepository.kt` 定义了 Komga 后台任务队列的仓储接口 `TasksRepository`。它本身不包含数据库实现，也不处理具体任务逻辑，而是规定“任务队列应该支持哪些操作”。

这个接口位于应用层 `org.gotson.komga.application.tasks`，作用是把任务系统的上层逻辑和底层持久化方式隔离开：

- `TaskEmitter` 负责创建任务，并通过 `TasksRepository.save(...)` 放入队列。
- `TaskProcessor` 负责从队列中取任务，通过 `TasksRepository.takeFirst(...)` 领取任务。
- `TaskHandler` 负责真正执行任务。
- `TasksDao` 负责把 `TasksRepository` 接口落到数据库表上。
- REST/SSE 接口通过它查询或清理任务队列状态。

可以把 `TasksRepository` 理解成 Komga 内部后台任务队列的“最小合同”：应用层只关心保存、领取、统计、删除、释放任务，不关心任务存在内存、数据库还是其他存储中。

## 关键组成

`TasksRepository` 是一个 Kotlin interface，声明的方法可以分成几类。

第一类是任务可用性和领取：

```kotlin
fun hasAvailable(): Boolean

fun takeFirst(owner: String = Thread.currentThread().name): Task?
```

`hasAvailable()` 用来判断当前队列中是否存在可以被处理的任务。它不是简单判断“有没有任务”，而是判断“有没有可领取的任务”。根据实现类 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/tasks/TasksDao.kt`，可领取任务需要满足：

- `OWNER` 为空，说明还没有线程领取；
- 如果任务有 `GROUP_ID`，则同一个 `GROUP_ID` 中不能已经有任务正在被其他 owner 处理。

`takeFirst(owner)` 从队列中领取一个任务，默认 owner 是当前线程名 `Thread.currentThread().name`。这个 owner 字段用于标记“这个任务已经被某个处理线程拿走了”。实现中会按 `PRIORITY` 降序、`LAST_MODIFIED_DATE` 升序选择一个任务，然后更新它的 `OWNER`。

第二类是查询任务：

```kotlin
fun findAll(): List<Task>

fun findAllGroupedByOwner(): Map<String?, List<Task>>
```

`findAll()` 返回所有任务对象。`findAllGroupedByOwner()` 按 owner 分组返回任务列表，key 可以是 `null`，表示尚未被线程领取的任务。

从 `TasksDao` 的实现看，任务在数据库中保存的是 class 名和 JSON payload，读取时通过 `ObjectMapper.readValue(...)` 加 `Class.forName(...)` 反序列化回 `Task` 子类。如果某个任务反序列化失败，会记录错误并跳过该任务。

第三类是统计：

```kotlin
fun count(): Int

fun countBySimpleType(): Map<String, Int>
```

`count()` 返回任务总数。`countBySimpleType()` 按任务简单类型统计数量，例如 `ScanLibrary`、`AnalyzeBook`、`GenerateBookThumbnail` 等。这个统计结果会被 SSE 层用于向管理员推送任务队列状态。

第四类是保存任务：

```kotlin
fun save(task: Task)

fun save(tasks: Collection<Task>)
```

`save(task)` 保存单个任务，`save(tasks)` 批量保存任务。根据 `TasksDao` 的实现，保存采用 insert + on duplicate key update 的语义：任务的主键是 `Task.uniqueId`，如果同一个任务已经存在，不会新增重复任务，而是更新 `groupId`、`priority`、`class`、`simpleType`、`payload`、`lastModifiedDate`。

这点很重要：任务队列通过 `uniqueId` 实现了去重。比如同一本书的 `AnalyzeBook` 任务，`uniqueId` 是 `ANALYZE_BOOK_$bookId`，重复提交时会覆盖更新，而不是堆出多个相同任务。

第五类是删除和释放任务：

```kotlin
fun delete(taskId: String)

fun deleteAll()

fun deleteAllWithoutOwner(): Int

fun disown(): Int
```

`delete(taskId)` 删除指定任务，通常在任务成功处理后调用。

`deleteAll()` 删除全部任务，属于强清理。

`deleteAllWithoutOwner()` 删除所有 owner 为空的任务，也就是“还没被处理线程领取的排队任务”。REST 控制器 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/TaskController.kt` 的 `DELETE api/v1/tasks` 调用的就是它，因此接口描述里的“Clear task queue / Cancel all tasks queued”实际只取消尚未领取的任务，不会直接删除正在执行的任务。

`disown()` 把所有非空 owner 清空。`TaskProcessor.afterPropertiesSet()` 启动时会调用它，目的是服务重启后恢复那些上次已经被领取但没处理完的任务。否则这些任务会一直带着旧 owner，被认为正在处理中，从而无法再次领取。

## 上下游关系

上游主要是任务生产者 `TaskEmitter`。

`komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskEmitter.kt` 负责根据业务场景创建不同的 `Task` 子类，例如：

- 扫描库：`Task.ScanLibrary`
- 分析书籍：`Task.AnalyzeBook`
- 生成封面缩略图：`Task.GenerateBookThumbnail`
- 刷新书籍元数据：`Task.RefreshBookMetadata`
- 刷新系列元数据：`Task.RefreshSeriesMetadata`
- 转换书籍：`Task.ConvertBook`
- 重建搜索索引：`Task.RebuildIndex`
- 删除书籍或系列：`Task.DeleteBook`、`Task.DeleteSeries`

这些任务类型定义在 `komga/src/main/kotlin/org/gotson/komga/application/tasks/Task.kt` 中。`Task` 是 sealed class，每个子类都提供自己的 `uniqueId`，并可以设置 `priority` 和可选 `groupId`。

根据当前片段推断，`TaskEmitter` 内部的提交方法会调用 `tasksRepository.save(...)`，并通过 `ApplicationEventPublisher` 发布 `TaskAddedEvent`，依据是它注入了 `TasksRepository` 和 `ApplicationEventPublisher`，且 `TaskProcessor` 明确监听 `TaskAddedEvent` 来触发处理。

下游主要有四类。

第一类是任务处理器 `TaskProcessor`。

`komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskProcessor.kt` 注入 `TasksRepository`，启动时调用 `disown()`，运行时监听 `TaskAddedEvent` 和 `ApplicationReadyEvent`，然后通过 `hasAvailable()` 和 `takeFirst()` 从队列取任务。任务处理完成后调用 `delete(task.uniqueId)` 移除队列记录。

第二类是任务执行器 `TaskHandler`。

`TaskProcessor` 取到 `Task` 后交给 `taskHandler.handleTask(task)`。`TasksRepository` 不关心任务如何执行，只负责取出任务对象。

第三类是持久化实现 `TasksDao`。

`komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/tasks/TasksDao.kt` 是 `TasksRepository` 的 JOOQ 实现。它使用 `tasksDslContextRW` 和 `tasksDslContextRO` 区分读写 DSLContext，操作任务数据库表 `Tables.TASK`。任务内容以 JSON payload 存储，任务类型以 class 全名和 simple type 存储。

第四类是对外接口和实时状态推送。

`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/TaskController.kt` 暴露管理员接口 `DELETE api/v1/tasks`，通过 `deleteAllWithoutOwner()` 清理未领取任务。

`komga/src/main/kotlin/org/gotson/komga/interfaces/sse/SseController.kt` 每 10 秒调用 `countBySimpleType()`，把任务总数和按类型统计结果包装成 `TaskQueueSseDto`，通过 SSE 事件 `TaskQueueStatus` 推送给管理员用户。

## 运行/调用流程

一个典型流程如下。

1. 某个业务动作需要后台处理，例如扫描 library、分析 book、生成 thumbnail。
2. 业务代码调用 `TaskEmitter` 的对应方法。
3. `TaskEmitter` 创建具体的 `Task` 子类对象。
4. `TaskEmitter` 通过 `TasksRepository.save(...)` 保存任务。
5. 根据当前片段推断，保存后会发布 `TaskAddedEvent`，触发 `TaskProcessor.processAvailableTask()`。
6. `TaskProcessor` 判断 `processTasks` 是否开启。
7. 如果线程池大小是 1，就提交一个 `takeAndProcess()`；如果线程池大于 1，就在 `hasAvailable()` 为 true 且活跃线程数小于 core pool size 时继续分发处理。
8. `takeAndProcess()` 调用 `tasksRepository.takeFirst()`。
9. `TasksDao.takeFirst()` 查询可用任务，按优先级和修改时间排序，取第一条。
10. 取到任务后，`TasksDao` 把该任务的 `OWNER` 更新为当前线程名。
11. `TaskProcessor` 调用 `taskHandler.handleTask(task)` 执行任务。
12. 执行完成后调用 `tasksRepository.delete(task.uniqueId)` 删除队列中的任务。
13. 删除后再次调用 `processAvailableTask()`，继续处理后续任务。

这里的并发控制重点在 `owner` 和 `groupId`。

`owner` 表示任务是否已经被某个线程领取。`groupId` 表示某些任务需要按组串行执行。比如 `AnalyzeBook`、`RefreshBookMetadata`、`ConvertBook` 等任务通常使用 series id 作为 groupId，这样可以避免同一 series 下多个相关任务并发执行导致状态冲突。

根据 `TasksDao` 的 `tasksAvailableCondition`，如果某个 `GROUP_ID` 已经存在 owner 非空的任务，那么同组其他任务暂时不可领取。没有 `GROUP_ID` 的任务不受这个限制。

优先级由 `Task.kt` 中的常量表示：

```kotlin
const val HIGHEST_PRIORITY = 8
const val HIGH_PRIORITY = 6
const val DEFAULT_PRIORITY = 4
const val LOW_PRIORITY = 2
const val LOWEST_PRIORITY = 0
```

`takeFirst()` 会优先取 `PRIORITY` 更高的任务；同优先级下，再按 `LAST_MODIFIED_DATE` 更早的任务优先。

## 小白阅读顺序

建议按下面顺序阅读，不要一开始就看数据库实现。

1. 先看 `komga/src/main/kotlin/org/gotson/komga/application/tasks/TasksRepository.kt`  
   理解它只是接口，负责定义队列能力：保存、领取、统计、删除、释放 owner。

2. 再看 `komga/src/main/kotlin/org/gotson/komga/application/tasks/Task.kt`  
   理解系统里有哪些任务类型，以及每个任务如何通过 `uniqueId` 去重，通过 `priority` 排优先级，通过 `groupId` 做组内串行。

3. 然后看 `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskEmitter.kt`  
   重点看业务如何把“扫描库”“分析书”“刷新元数据”等动作转成 `Task` 对象并保存到仓储。

4. 接着看 `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskProcessor.kt`  
   重点看任务如何被领取、执行、删除，以及启动时为什么要调用 `disown()`。

5. 最后看 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/tasks/TasksDao.kt`  
   这一步再理解数据库层：JOOQ 查询、JSON 序列化、`OWNER` 字段、`GROUP_ID` 条件、批量保存、on duplicate update。

6. 如果还想看外部表现，再看 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/TaskController.kt` 和 `komga/src/main/kotlin/org/gotson/komga/interfaces/sse/SseController.kt`  
   它们展示了任务队列如何被管理员清理，以及任务数量如何实时推送到前端。

## 常见误区

第一个误区：以为 `TasksRepository` 是普通 CRUD 仓储。

它不只是保存和删除任务。`takeFirst()`、`disown()`、`deleteAllWithoutOwner()` 都体现了后台队列语义。它更接近一个持久化任务队列接口，而不是普通实体 repository。

第二个误区：以为 `hasAvailable()` 等于“数据库里有任务”。

从 `TasksDao` 实现看，可用任务必须没有 owner，并且不能被同组正在执行的任务阻塞。因此数据库中有任务时，`hasAvailable()` 仍然可能返回 false。

第三个误区：以为多线程处理只靠线程池控制。

线程池只控制并发数量，真正避免重复领取和同组并发的是任务表中的 `OWNER` 和 `GROUP_ID` 逻辑。`TaskProcessor` 调用 `takeFirst()`，`TasksDao` 再根据可用条件选任务并写入 owner。

第四个误区：以为删除任务队列会停止正在执行的任务。

REST 接口调用的是 `deleteAllWithoutOwner()`，只删除 owner 为空的任务，也就是还在排队、未被线程领取的任务。已经被领取并正在执行的任务 owner 非空，不会被这个接口直接删除。

第五个误区：以为重复提交任务会创建重复记录。

`TasksDao.toQuery()` 使用 `onDuplicateKeyUpdate()`，而任务 ID 来自 `Task.uniqueId`。同一个 `uniqueId` 的任务重复保存时会更新原记录，而不是插入重复任务。

第六个误区：忽略 `disown()` 的恢复作用。

应用异常退出时，可能有任务已经被设置了 owner，但没有执行完成或没有被删除。下次启动时 `TaskProcessor.afterPropertiesSet()` 调用 `disown()`，把这些任务重新变成可领取状态。这是任务队列具备重启恢复能力的关键。

第七个误区：把 `Task` 的 `groupId` 当成业务 ID 展示字段。

`groupId` 主要用于调度约束，不是 UI 展示或权限判断字段。它的意义是“这些任务不能并发处理”，常见取值可能是 series id、library id 或其他业务分组 ID，具体取决于任务类型。
