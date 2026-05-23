# 文件：komga/src/main/kotlin/org/gotson/komga/interfaces/scheduler/PeriodicScannerController.kt

## 它负责什么

`PeriodicScannerController.kt` 是 Komga 启动后初始化“书库扫描”的调度入口。它本身不执行扫描逻辑，也不直接访问文件系统，而是在 Spring Boot 应用启动完成后，根据每个 `Library` 的配置做两件事：

1. 对开启了 `scanOnStartup` 的书库，立即提交一次扫描任务。
2. 对所有书库，根据各自的 `scanInterval` 配置注册周期扫描任务。

这个类位于 `interfaces/scheduler` 包下，说明它更像是“应用边界层的启动控制器”：监听 Spring 生命周期事件，然后把具体工作交给 application 层的服务。

它只在非测试环境启用：

```kotlin
@Profile("!test")
@Component
class PeriodicScannerController(...)
```

因此测试 profile 下不会自动触发启动扫描或周期任务注册，避免测试运行时产生后台任务干扰。

## 关键组成

### 包与定位

文件包名是：

```kotlin
package org.gotson.komga.interfaces.scheduler
```

`interfaces` 表示它处于系统边界层，`scheduler` 表示它处理的是调度类入口，而不是业务规则本身。

### 主要依赖

该类通过构造函数注入三个对象：

```kotlin
private val taskEmitter: TaskEmitter
private val libraryRepository: LibraryRepository
private val libraryScanScheduler: LibraryScanScheduler
```

它们分别承担不同职责。

`TaskEmitter` 来自 `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskEmitter.kt`，用于提交异步任务。这里调用的是：

```kotlin
taskEmitter.scanLibrary(it.id)
```

也就是说，真正的扫描不是在 `PeriodicScannerController` 内部同步执行，而是被包装成 `Task.ScanLibrary` 之类的任务交给任务系统处理。

`LibraryRepository` 来自 `komga/src/main/kotlin/org/gotson/komga/domain/persistence/LibraryRepository.kt`，提供书库读取能力。这里用到的是：

```kotlin
libraryRepository.findAll()
```

它返回所有 `Library` 聚合对象。`PeriodicScannerController` 依赖这些对象上的 `scanOnStartup`、`scanInterval`、`id`、`name` 等字段来决定后续动作。

`LibraryScanScheduler` 来自 `komga/src/main/kotlin/org/gotson/komga/application/scheduler/LibraryScanScheduler.kt`，负责真正注册周期任务。`PeriodicScannerController` 调用：

```kotlin
libraryScanScheduler.scheduleScan(it)
```

具体定时频率、任务取消、任务注册都在 `LibraryScanScheduler` 内完成。

### 日志对象

文件顶部定义了 Kotlin Logging logger：

```kotlin
private val logger = KotlinLogging.logger {}
```

这里只在启动扫描时记录日志：

```kotlin
logger.info { "Scan on startup for library: ${it.name}" }
```

周期扫描的日志不在本文件中，而是在 `LibraryScanScheduler` 内记录：

```kotlin
logger.info { "Periodic scan for library: ${library.name}" }
```

这也体现了职责分离：本文件记录“启动时扫描”，调度器记录“周期扫描”。

### `scanOnStartup()`

方法定义：

```kotlin
@EventListener(classes = [ApplicationReadyEvent::class])
fun scanOnStartup()
```

它监听 `ApplicationReadyEvent`。这个事件在 Spring Boot 应用启动完成、准备好接收请求时发布。

方法逻辑是：

```kotlin
libraryRepository
  .findAll()
  .filter { it.scanOnStartup }
  .forEach {
    logger.info { "Scan on startup for library: ${it.name}" }
    taskEmitter.scanLibrary(it.id)
  }
```

含义如下：

1. 从仓库读取所有书库。
2. 只保留 `scanOnStartup == true` 的书库。
3. 对每个符合条件的书库打印日志。
4. 调用 `taskEmitter.scanLibrary(libraryId)` 提交扫描任务。

这里需要注意，“启动时扫描”是一次性行为，取决于每个书库的 `scanOnStartup` 配置。

### `scheduleScans()`

方法定义：

```kotlin
@EventListener(classes = [ApplicationReadyEvent::class])
fun scheduleScans()
```

它同样监听 `ApplicationReadyEvent`。

方法逻辑是：

```kotlin
libraryRepository
  .findAll()
  .forEach { libraryScanScheduler.scheduleScan(it) }
```

含义如下：

1. 读取所有书库。
2. 不过滤 `scanOnStartup`。
3. 每个书库都交给 `LibraryScanScheduler.scheduleScan(library)` 处理。

是否真的注册定时任务，不由本方法判断，而由 `LibraryScanScheduler` 根据 `library.scanInterval` 判断。

在 `LibraryScanScheduler` 中可以看到：

```kotlin
if (library.scanInterval != DISABLED) {
  registrar.scheduleFixedRateTask(...)
}
```

也就是说，即使 `PeriodicScannerController` 把所有书库都传过去，`scanInterval == DISABLED` 的书库也不会被注册周期扫描。

## 上下游关系

### 上游：Spring Boot 启动事件

`PeriodicScannerController` 的直接触发源是 Spring 的 `ApplicationReadyEvent`。

两个方法都标注了：

```kotlin
@EventListener(classes = [ApplicationReadyEvent::class])
```

因此它不需要被普通业务代码显式调用。Spring 容器创建该组件后，在应用启动完成时自动调用这两个监听方法。

这类代码的入口不在 REST API，也不在命令行，而在框架生命周期里。读代码时如果只搜索普通函数调用，可能找不到直接调用方。

### 上游：书库配置来源

该类读取的是 `LibraryRepository.findAll()` 返回的书库数据。书库模型中相关字段包括：

```kotlin
scanOnStartup: Boolean
scanInterval: Library.ScanInterval
```

从仓库搜索结果可见，这些字段还出现在：

`komga/src/main/kotlin/org/gotson/komga/domain/model/Library.kt`  
`komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/LibraryDao.kt`  
`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/LibraryDto.kt`  
`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/LibraryCreationDto.kt`  
`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/LibraryUpdateDto.kt`  
`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/LibraryController.kt`

这些路径说明，`scanOnStartup` 和 `scanInterval` 是书库配置的一部分：可以通过 API DTO 创建、更新、返回，也会通过 `LibraryDao` 持久化到数据库。

根据当前片段推断，用户在管理书库时设置的“启动时扫描”和“扫描间隔”，最终会保存到 `Library`，应用启动时再由 `PeriodicScannerController` 读取并生效。依据是相关字段同时出现在 DTO、REST controller、DAO、domain model 与本文件中。

### 下游：任务系统

启动扫描的下游是 `TaskEmitter`。

`PeriodicScannerController` 调用：

```kotlin
taskEmitter.scanLibrary(it.id)
```

在 `TaskEmitter` 中对应方法是：

```kotlin
fun scanLibrary(
  libraryId: String,
  scanDeep: Boolean = false,
  priority: Int = DEFAULT_PRIORITY,
) {
  submitTask(Task.ScanLibrary(libraryId, scanDeep, priority))
}
```

这说明本文件只是发出“扫描某个书库”的任务，不决定扫描深度、任务执行线程、扫描具体算法。默认情况下，`scanDeep` 是 `false`，优先级是 `DEFAULT_PRIORITY`。

### 下游：定时任务注册器

周期扫描的下游是 `LibraryScanScheduler`。

`LibraryScanScheduler.scheduleScan(library)` 的核心行为是：

1. 先从内部 registry 中移除该书库已有定时任务。
2. 如果存在旧任务，则取消。
3. 如果 `library.scanInterval != DISABLED`，注册新的 fixed-rate task。
4. 定时触发时调用 `taskEmitter.scanLibrary(library.id)`。

它内部使用：

```kotlin
ConcurrentHashMap<String, ScheduledTask>
ScheduledTaskRegistrar
TaskScheduler
FixedRateTask
```

因此，周期扫描任务是按书库 ID 维护的，每个书库最多对应一个当前有效的定时扫描任务。

### 旁路关系：书库更新后的重新调度

搜索结果显示 `komga/src/main/kotlin/org/gotson/komga/domain/service/LibraryLifecycle.kt` 中也调用了：

```kotlin
libraryScanScheduler.scheduleScan(toUpdate)
```

并且附近逻辑与 `scanInterval` 变化有关。根据当前片段推断，当书库扫描间隔配置被更新时，系统会重新调度该书库的周期扫描任务。依据是搜索结果显示 `LibraryLifecycle` 中存在：

```kotlin
if (current.scanInterval != toUpdate.scanInterval)
  libraryScanScheduler.scheduleScan(toUpdate)
```

所以 `PeriodicScannerController` 负责“应用启动时注册已有书库任务”，而 `LibraryLifecycle` 负责“运行期间配置变化后的重新注册”。

## 运行/调用流程

### 应用启动阶段

应用启动后，Spring Boot 发布 `ApplicationReadyEvent`。

因为 `PeriodicScannerController` 是 `@Component`，并且当前 profile 不是 `test`，Spring 会创建这个 bean，并在事件发布时调用两个监听方法。

流程可以理解为：

```text
Spring Boot application ready
        |
        v
ApplicationReadyEvent
        |
        +--> PeriodicScannerController.scanOnStartup()
        |
        +--> PeriodicScannerController.scheduleScans()
```

这两个方法监听的是同一个事件。代码本身没有显式指定执行顺序，因此不应假设它们一定按源码顺序执行。对于当前逻辑来说，顺序通常不影响结果：一个负责提交立即扫描任务，一个负责注册未来的周期扫描任务。

### 启动时扫描流程

`scanOnStartup()` 的运行链路是：

```text
ApplicationReadyEvent
        |
        v
PeriodicScannerController.scanOnStartup()
        |
        v
libraryRepository.findAll()
        |
        v
filter { library.scanOnStartup }
        |
        v
taskEmitter.scanLibrary(library.id)
        |
        v
Task.ScanLibrary 被提交到任务系统
```

如果某个书库设置了 `scanOnStartup = true`，应用每次启动完成后都会为它提交一次扫描任务。

如果设置为 `false`，它不会被这个方法提交启动扫描任务。

### 周期扫描注册流程

`scheduleScans()` 的运行链路是：

```text
ApplicationReadyEvent
        |
        v
PeriodicScannerController.scheduleScans()
        |
        v
libraryRepository.findAll()
        |
        v
libraryScanScheduler.scheduleScan(library)
        |
        v
根据 library.scanInterval 注册或跳过定时任务
```

进入 `LibraryScanScheduler` 后：

```text
scheduleScan(library)
        |
        v
registry.remove(library.id)?.cancel(false)
        |
        v
scanInterval == DISABLED ?
        |
        +--> 是：不注册新任务
        |
        +--> 否：注册 FixedRateTask
                    |
                    v
              到点后调用 taskEmitter.scanLibrary(library.id)
```

周期时间由 `Library.ScanInterval.toDuration()` 转换：

```text
HOURLY      -> 1 小时
EVERY_6H    -> 6 小时
EVERY_12H   -> 12 小时
DAILY       -> 1 天
WEEKLY      -> 7 天
DISABLED    -> 不应该转换成 Duration
```

`DISABLED` 在 `LibraryScanScheduler` 中会提前排除；如果误调用 `toDuration()`，会抛出 `IllegalArgumentException`。

### 启动扫描与周期扫描的区别

`scanOnStartup` 和 `scanInterval` 是两个不同概念。

`scanOnStartup` 控制的是“应用启动完成后是否立刻扫描一次”。

`scanInterval` 控制的是“之后是否按固定频率重复扫描”。

因此可能出现这些组合：

```text
scanOnStartup = true,  scanInterval = EVERY_6H
启动后立即扫描一次，并注册每 6 小时扫描一次。

scanOnStartup = true,  scanInterval = DISABLED
启动后立即扫描一次，但不注册周期扫描。

scanOnStartup = false, scanInterval = DAILY
启动时不立即扫描，但注册每天扫描一次。

scanOnStartup = false, scanInterval = DISABLED
启动时不扫描，也不注册周期扫描。
```

这也是理解本文件最重要的一点：它处理了两个相互独立但都发生在启动阶段的扫描入口。

## 小白阅读顺序

建议按下面顺序阅读，不要一开始就深入任务执行细节。

第一步，先读 `PeriodicScannerController.kt` 本身。

重点看两个方法：

```kotlin
scanOnStartup()
scheduleScans()
```

先建立直觉：这个类只监听应用启动事件，然后把工作转交给其他服务。

第二步，读 `LibraryRepository`。

路径是：

`komga/src/main/kotlin/org/gotson/komga/domain/persistence/LibraryRepository.kt`

重点看：

```kotlin
fun findAll(): Collection<Library>
```

明白本文件的所有判断都来自数据库中的书库配置，而不是硬编码配置。

第三步，读 `Library` 模型。

路径是：

`komga/src/main/kotlin/org/gotson/komga/domain/model/Library.kt`

重点找这些字段：

```kotlin
scanOnStartup
scanInterval
ScanInterval
```

理解每个书库自身携带扫描策略。

第四步，读 `TaskEmitter.scanLibrary()`。

路径是：

`komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskEmitter.kt`

重点看：

```kotlin
fun scanLibrary(...)
submitTask(Task.ScanLibrary(...))
```

这一步是为了明白：controller 没有执行扫描，只是提交任务。

第五步，读 `LibraryScanScheduler.scheduleScan()`。

路径是：

`komga/src/main/kotlin/org/gotson/komga/application/scheduler/LibraryScanScheduler.kt`

重点看：

```kotlin
registry.remove(library.id)?.cancel(false)
if (library.scanInterval != DISABLED) { ... }
scheduleFixedRateTask(...)
```

这一步能理解周期任务如何注册、如何替换旧任务、如何避免重复注册。

第六步，再看 API 和持久化路径。

可以从这些文件理解配置是怎么被用户设置、保存、读取的：

`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/LibraryCreationDto.kt`  
`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/LibraryUpdateDto.kt`  
`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/LibraryController.kt`  
`komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/LibraryDao.kt`

这些不是理解本文件的第一优先级，但有助于串起“用户配置 -> 数据库存储 -> 启动读取 -> 任务注册”的完整链路。

## 常见误区

### 误区一：以为这个类会直接扫描文件

`PeriodicScannerController` 不扫描文件，不遍历目录，也不解析漫画文件。它只是调用：

```kotlin
taskEmitter.scanLibrary(it.id)
```

真正扫描逻辑在任务处理链路的更下游。

### 误区二：以为 `scheduleScans()` 只处理启用周期扫描的书库

`scheduleScans()` 对所有书库都会调用：

```kotlin
libraryScanScheduler.scheduleScan(it)
```

是否跳过由 `LibraryScanScheduler` 判断。`scanInterval == DISABLED` 的书库会在 scheduler 层被排除。

这种设计让 controller 保持简单：它只负责“把所有已有书库交给调度器初始化”。

### 误区三：把 `scanOnStartup` 和 `scanInterval` 混为一谈

这两个配置互不等价。

`scanOnStartup` 是启动时的一次性扫描开关。

`scanInterval` 是周期扫描频率。

一个书库可以启动时扫描但不周期扫描，也可以不启动扫描但周期扫描。

### 误区四：以为两个 `@EventListener` 一定有固定执行顺序

两个方法都监听 `ApplicationReadyEvent`，但代码没有显式声明顺序，例如没有看到 `@Order`。

因此阅读时不要依赖“源码中谁写在前面谁先执行”的假设。当前逻辑本身也不应该依赖这个顺序。

### 误区五：忽略 `@Profile("!test")`

这个注解很重要：

```kotlin
@Profile("!test")
```

它表示测试 profile 下不会启用这个组件。如果在测试中发现启动扫描或周期扫描没有发生，不一定是代码坏了，可能是 profile 使这个 bean 没有加载。

### 误区六：以为周期任务只在启动时能注册

`PeriodicScannerController` 的确只负责启动时注册已有书库的周期任务。但搜索结果显示，`LibraryLifecycle` 中也会在 `scanInterval` 变化时调用 `libraryScanScheduler.scheduleScan(toUpdate)`。

因此整体系统里，周期扫描注册至少有两个入口：

```text
应用启动：PeriodicScannerController.scheduleScans()
配置更新：LibraryLifecycle 调用 LibraryScanScheduler.scheduleScan(...)
```

前者解决“已有配置启动时生效”，后者解决“运行时修改配置后生效”。

### 误区七：以为定时任务会无限叠加

在 `LibraryScanScheduler.scheduleScan(library)` 中，注册新任务前会先执行：

```kotlin
registry.remove(library.id)?.cancel(false)
```

这意味着同一个书库重新调度时，会先取消旧任务，再按新配置注册。它不是每次调用都无脑新增一个定时任务。

### 误区八：以为 `DISABLED` 只是一个很长的间隔

`DISABLED` 不是特殊时长，而是“不注册周期扫描”。在 `LibraryScanScheduler` 中，只有当：

```kotlin
library.scanInterval != DISABLED
```

时才会创建 fixed-rate task。

而 `DISABLED` 转换成 `Duration` 会抛异常，说明代码明确不把它当成合法时间间隔处理。
