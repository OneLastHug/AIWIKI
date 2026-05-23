# 目录：komga/src/main/kotlin/org/gotson/komga/application/scheduler

## 它负责什么
这个目录目前只有一个核心文件 `LibraryScanScheduler.kt`，职责非常集中：把“库的周期性扫描”注册成 Spring 的定时任务，并在库配置变化时重建对应任务。

它不是扫描逻辑本身，而是“调度层”：
- 接收 `Library` 对象里的 `scanInterval`
- 根据间隔把扫描任务挂到 `TaskScheduler`
- 记录每个库对应的 `ScheduledTask`
- 让 Actuator 的 `/actuator/scheduledtasks` 能看到这些任务

从调用链上看，它更像一个调度适配器，真正干活的是 `TaskEmitter.scanLibrary(...)` 之后进入的任务系统。

## 关键组成
目录里只有一个文件，但它内部有几块关键结构：

- `LibraryScanScheduler`
  - 标注为 `@Service`，说明它是 Spring 管理的应用服务
  - 构造参数里注入了 `TaskScheduler` 和 `TaskEmitter`
  - 实现了 `ScheduledTaskHolder`，这点主要是为了管理端可见性

- `registry: ConcurrentHashMap<String, ScheduledTask>`
  - 用 `library.id` 作为 key
  - 保存每个库当前对应的周期任务
  - 先删后建，保证同一个库不会叠着多个扫描任务

- `registrar: ScheduledTaskRegistrar`
  - 绑定外部注入的 `TaskScheduler`
  - 通过 `scheduleFixedRateTask(...)` 注册固定频率任务

- `scheduleScan(library: Library)`
  - 核心方法
  - 先取消旧任务，再按 `scanInterval` 重新注册
  - 如果 `scanInterval == DISABLED`，则不注册新任务

- `toDuration()`
  - 把 `Library.ScanInterval` 转成 `Duration`
  - `DISABLED` 会直接抛异常，但实际在 `scheduleScan` 前已过滤掉

## 上下游关系
上游主要有两处：

1. `komga/src/main/kotlin/org/gotson/komga/interfaces/scheduler/PeriodicScannerController.kt`
   - 在 `ApplicationReadyEvent` 之后读取全部库
   - 对每个库调用 `libraryScanScheduler.scheduleScan(it)`
   - 这就是应用启动后的批量初始化入口

2. `komga/src/main/kotlin/org/gotson/komga/domain/service/LibraryLifecycle.kt`
   - 更新库时，如果 `scanInterval` 发生变化，就调用 `scheduleScan(toUpdate)`
   - 这保证运行期修改配置后，定时任务能及时重建

下游主要是：

1. `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskEmitter.kt`
   - `scheduleScan` 内部并不执行扫描
   - 它只是调用 `taskEmitter.scanLibrary(library.id)`，把扫描请求放进任务系统
   - 这意味着周期任务和实际扫描执行是解耦的

2. Spring 调度基础设施
   - `komga/src/main/kotlin/org/gotson/komga/Application.kt` 上有 `@EnableScheduling`
   - 说明整个应用的调度能力是开启的
   - `ScheduledTaskHolder` 让 Actuator 也能枚举这些任务

## 运行/调用流程
可以把这条链路理解成三段：

1. 应用启动
   - `Application.kt` 开启 scheduling
   - `PeriodicScannerController` 监听 `ApplicationReadyEvent`
   - 它遍历所有库，调用 `scheduleScan(...)`

2. 注册任务
   - `LibraryScanScheduler.scheduleScan(...)` 先按 `library.id` 清理旧任务
   - 如果间隔不是 `DISABLED`
   - 就创建一个 `FixedRateTask`
   - 到点后打印日志并调用 `taskEmitter.scanLibrary(library.id)`

3. 运行时更新
   - `LibraryLifecycle.updateLibrary(...)` 发现 `scanInterval` 有变化
   - 再次调用 `scheduleScan(...)`
   - 旧任务取消，新任务按新间隔生效

根据当前片段推断，这套设计的意图是：库扫描的“调度配置”跟“扫描执行队列”分层，调度器只负责触发，不负责业务细节。

## 小白阅读顺序
建议按这个顺序读：

1. `komga/src/main/kotlin/org/gotson/komga/domain/model/Library.kt`
   - 先看 `ScanInterval` 枚举，理解调度粒度有哪些

2. `komga/src/main/kotlin/org/gotson/komga/application/scheduler/LibraryScanScheduler.kt`
   - 这是本目录的主体
   - 看它如何把库配置变成定时任务

3. `komga/src/main/kotlin/org/gotson/komga/interfaces/scheduler/PeriodicScannerController.kt`
   - 看启动时如何批量初始化任务

4. `komga/src/main/kotlin/org/gotson/komga/domain/service/LibraryLifecycle.kt`
   - 看库更新时如何触发重建

5. `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskEmitter.kt`
   - 看 `scanLibrary` 最终把任务交给谁

## 常见误区
- 误以为 `LibraryScanScheduler` 直接扫描文件。实际上它只负责“定时触发”，真正的扫描在 `TaskEmitter.scanLibrary(...)` 之后。
- 误以为 `ScheduledTaskHolder` 是调度的核心。它主要是管理和可观测性用途，方便 Actuator 展示任务。
- 误以为 `DISABLED` 也会被转换成 `Duration`。不会，`scheduleScan(...)` 已先拦截，`toDuration()` 只是辅助转换。
- 误以为新增库后一定自动进入周期扫描。根据当前代码，启动时会批量注册，运行期是否补注册要看创建路径；`addLibrary(...)` 里只做了立即扫描，没有直接调用 `scheduleScan(...)`。
- 误以为修改了 `scanInterval` 但旧任务会自动替换。实际上是 `registry.remove(library.id)?.cancel(false)` 先取消旧任务，再重新注册，新旧切换是手动完成的。
