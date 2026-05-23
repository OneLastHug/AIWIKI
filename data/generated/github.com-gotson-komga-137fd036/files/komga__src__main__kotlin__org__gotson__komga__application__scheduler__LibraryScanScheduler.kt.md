# 文件：komga/src/main/kotlin/org/gotson/komga/application/scheduler/LibraryScanScheduler.kt

## 它负责什么
这个文件定义了 `LibraryScanScheduler`，作用是把某个 `Library` 的“周期性扫描”注册到 Spring 的调度体系里。它不是实际执行扫描逻辑的地方，而是负责“按间隔定时触发扫描任务”，触发后再交给 `TaskEmitter.scanLibrary(...)` 去真正投递扫描任务。

从行为上看，它解决的是两件事：

1. 根据 `Library.scanInterval` 为每个库建立定时扫描。
2. 当库配置变化时，能取消旧任务并重新注册新任务。

## 关键组成
核心结构很简单：

- `class LibraryScanScheduler(...) : ScheduledTaskHolder`  
  作为 Spring 服务组件，并实现 `ScheduledTaskHolder`，这样 `/actuator/scheduledtasks` 可以看到它登记的任务。
- `registry: ConcurrentHashMap<String, ScheduledTask>`  
  以 `library.id` 为 key，保存每个库当前对应的定时任务，方便更新时先取消旧任务。
- `registrar: ScheduledTaskRegistrar`  
  绑定外部注入的 `TaskScheduler`，真正负责注册 fixed-rate 任务。
- `scheduleScan(library: Library)`  
  这是主入口。先移除旧任务，再根据 `library.scanInterval` 决定是否重新注册。
- `Library.ScanInterval.toDuration()`  
  把枚举值转换成 `Duration`。支持 `HOURLY`、`EVERY_6H`、`EVERY_12H`、`DAILY`、`WEEKLY`，`DISABLED` 会直接抛异常，避免误用。

## 上下游关系
上游主要有三个：

- `PeriodicScannerController`：在 `ApplicationReadyEvent` 后遍历所有库，调用 `libraryScanScheduler.scheduleScan(it)`，让系统启动后就把周期扫描任务补齐。
- `LibraryLifecycle.updateLibrary(...)`：如果库的 `scanInterval` 变了，会重新调用 `scheduleScan(toUpdate)`，保证调度配置跟数据库中的库配置一致。
- `Library`：`scanInterval` 是调度策略的来源，默认值是 `EVERY_6H`，见 `Library.kt`。

下游主要是：

- `TaskEmitter.scanLibrary(library.id)`：真正把“扫描库”任务投递到任务系统里。这个文件不扫描文件本身，只负责定时触发。
- Spring Actuator：由于实现了 `ScheduledTaskHolder`，调度任务可以被 `/actuator/scheduledtasks` 观察到。

## 运行/调用流程
可以把流程理解成三层：

1. 应用启动后，`PeriodicScannerController.scheduleScans()` 读取所有库。
2. 对每个库调用 `LibraryScanScheduler.scheduleScan(library)`。
3. `scheduleScan` 先取消该库旧的定时任务，再看 `library.scanInterval`：
   - 如果是 `DISABLED`，不再新建任务；
   - 如果是其他值，就按对应 `Duration` 注册 `FixedRateTask`。
4. 到了执行时刻，任务只做一件事：记录日志，然后调用 `taskEmitter.scanLibrary(library.id)`。

更新库时也会走同样路径：`LibraryLifecycle.updateLibrary(...)` 发现 `scanInterval` 变化后，重新调度；如果库的路径、扫描格式等变化，则额外触发一次立即扫描。

## 小白阅读顺序
建议按这个顺序看：

1. 先看 `komga/src/main/kotlin/org/gotson/komga/domain/model/Library.kt`，理解 `scanInterval` 和 `scanOnStartup` 的含义。
2. 再看本文件 `LibraryScanScheduler.kt`，把“定时任务注册”这层逻辑看明白。
3. 接着看 `komga/src/main/kotlin/org/gotson/komga/interfaces/scheduler/PeriodicScannerController.kt`，理解启动时如何补齐调度。
4. 再看 `komga/src/main/kotlin/org/gotson/komga/domain/service/LibraryLifecycle.kt`，理解库更新时为何要重建调度。
5. 最后看 `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskEmitter.kt` 里的 `scanLibrary(...)`，确认调度触发后真正进入哪个任务系统。

## 常见误区
- 容易把这个类误认为“扫描实现”，其实它只是“定时触发器”，真正扫描由 `TaskEmitter` 负责。
- `scheduleScan(library)` 不是纯新增，它会先 `cancel(false)` 旧任务，所以同一个库重复调用时，旧调度会被替换。
- `DISABLED` 不是“注册一个空任务”，而是直接不注册。
- `FixedRateTask` 这里的初始延迟和周期都用同一个 `scanInterval.toDuration()`，也就是说它是固定频率重复执行，不是单次延迟后再跑一次。
- `registry` 只是内存中的任务索引，不是持久化配置；应用重启后，仍然要靠启动时的 `scheduleScans()` 重新恢复。
