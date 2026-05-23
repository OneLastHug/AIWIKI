# 目录：komga/src/main/kotlin/org/gotson/komga/interfaces/scheduler

## 它负责什么

`komga/src/main/kotlin/org/gotson/komga/interfaces/scheduler` 是 Komga 的“后台调度接口层”。这里的类不处理 HTTP 请求，也不是业务逻辑的最终执行者，而是把 Spring Boot 生命周期事件、Spring Scheduling 定时器、领域事件转换成应用层任务或指标更新。

从分层上看，它位于 `interfaces` 包下，职责接近“入口适配器”：监听外部时机，例如应用启动完成、固定时间间隔、领域事件发生，然后调用 `application` 或 `domain` 层服务完成后续动作。

这个目录主要覆盖五类事情：

1. 应用启动后创建初始用户。
2. 应用启动后触发或安排资料库扫描。
3. 应用启动后检查 Lucene 搜索索引是否存在或需要升级。
4. 定期清理较旧的认证活动记录。
5. 向 Micrometer 注册并刷新 Komga 运行指标。

所有类基本都受 Spring Profile 控制，常见的是 `@Profile("!test")`，表示测试环境不启用这些自动后台行为，避免测试被定时任务、启动事件或外部状态干扰。

## 关键组成

`AuthenticationActivityCleanupController.kt`

这个类是一个真正的定时任务入口：

```kotlin
@Scheduled(fixedRate = 86_400_000)
fun cleanup()
```

它每天运行一次，计算 UTC 时间下一个月以前的时间点：

```kotlin
LocalDateTime.now(ZoneId.of("Z")).minusMonths(1)
```

然后调用 `AuthenticationActivityRepository.deleteOlderThan(olderThan)` 删除旧认证活动记录。这里的 repository 位于 domain persistence 层，说明 scheduler 只负责触发清理，不直接操作数据库细节。

需要注意的是，这里的 `fixedRate = 86_400_000` 是毫秒值，即 24 小时。它不是 cron 表达式，也不保证“每天某个固定时刻”执行，而是按上一次启动后的固定频率执行。

`InitialUserController.kt`

这个文件同时包含一个启动监听器和两组初始用户配置。

`InitialUserController` 在 `ApplicationReadyEvent` 后执行：

```kotlin
fun createInitialUserOnStartupIfNoneExist()
```

它只在满足 `@Profile("!test & noclaim")` 时启用。逻辑是：如果 `KomgaUserLifecycle.countUsers()` 返回 0，就创建配置中提供的 `initialUsers`。

同文件中有两个 configuration：

`InitialUsersDevConfiguration` 在 `dev` profile 下提供两个固定用户：

```kotlin
admin@example.org / admin
user@example.org / user
```

其中 admin 拥有全部 `UserRoles`。

`InitialUsersProdConfiguration` 在非 `dev` profile 下提供一个 admin 用户，密码使用 `RandomStringUtils.secure().nextAlphanumeric(12)` 生成。启动日志会打印初始账号和密码，这是首次初始化场景下的重要入口。

`MetricsPublisherController.kt`

这是指标发布器，依赖 Micrometer 的 `MeterRegistry`，同时依赖多个 repository：

- `LibraryRepository`
- `BookRepository`
- `SeriesRepository`
- `SeriesCollectionRepository`
- `ReadListRepository`
- `SidecarRepository`

它在初始化时注册两个任务相关指标：

```kotlin
METER_TASKS_EXECUTION = "komga.tasks.execution"
METER_TASKS_FAILURE = "komga.tasks.failure"
```

并维护多类实体指标：

- `komga.libraries`
- `komga.series`
- `komga.books`
- `komga.books.filesize`
- `komga.collections`
- `komga.readlists`
- `komga.sidecars`

其中 `libraries`、`collections`、`readlists` 是无 tag 的 `Gauge`，用 `AtomicLong` 保存当前值；`series`、`books`、`books.filesize`、`sidecars` 是按 `library` tag 分组的 `MultiGauge`。

它监听两类事件：

第一类是 `ApplicationReadyEvent`，启动完成后执行 `pushAllMetrics()`，把所有指标从数据库 repository 重新统计一次。

第二类是 `DomainEvent`，例如 `LibraryAdded`、`LibraryDeleted`、`CollectionAdded`、`ReadListDeleted`、`LibraryScanned` 等。部分事件直接对 `AtomicLong` 做加减，资料库扫描完成或删除资料库时，则重新按 library 统计多 tag 指标。

`PeriodicScannerController.kt`

这个类负责资料库扫描的启动触发和周期调度。

它有两个 `ApplicationReadyEvent` 监听方法：

```kotlin
fun scanOnStartup()
fun scheduleScans()
```

`scanOnStartup()` 会读取 `LibraryRepository.findAll()`，过滤出 `scanOnStartup == true` 的资料库，然后调用：

```kotlin
taskEmitter.scanLibrary(it.id)
```

也就是说，启动扫描不是在 controller 里直接扫描文件系统，而是投递一个 `Task.ScanLibrary`。

`scheduleScans()` 会对所有资料库调用：

```kotlin
libraryScanScheduler.scheduleScan(it)
```

`LibraryScanScheduler` 位于 `komga/src/main/kotlin/org/gotson/komga/application/scheduler/LibraryScanScheduler.kt`，它会根据 `Library.scanInterval` 动态注册 fixed-rate task。支持的间隔包括 `HOURLY`、`EVERY_6H`、`EVERY_12H`、`DAILY`、`WEEKLY`，如果是 `DISABLED` 就不注册周期扫描。

`SearchIndexController.kt`

这个类负责启动时检查 Lucene 搜索索引。

在 `ApplicationReadyEvent` 后执行：

```kotlin
fun createIndexIfNoneExist()
```

它先调用 `LuceneHelper.indexExists()`。如果索引不存在，就以最高优先级投递重建索引任务：

```kotlin
taskEmitter.rebuildIndex(HIGHEST_PRIORITY)
```

如果索引存在，则读取版本：

```kotlin
val indexVersion = luceneHelper.getIndexVersion()
```

根据版本做兼容处理：

- `indexVersion < 6`：先投递 `upgradeIndex(HIGHEST_PRIORITY)`，再重建 `LuceneEntity.Series`。
- `indexVersion < 8`：只重建 `LuceneEntity.Series`。

根据当前片段推断，版本小于 6 时涉及 Lucene 9.x 升级，所以需要先升级索引结构，再重建部分实体索引；版本 6 到 7 之间只需要补重建 series 索引。

## 上下游关系

上游主要有三类：

第一类是 Spring Boot 生命周期事件。`ApplicationReadyEvent` 是这个目录最重要的触发源，应用完全启动后，多个 controller 会开始执行初始化动作，包括创建初始用户、推送指标、扫描资料库、安排周期扫描、检查搜索索引。

第二类是 Spring Scheduling。`Application.kt` 上有 `@EnableScheduling`，因此 `@Scheduled` 和动态注册的 scheduled task 才会生效。`AuthenticationActivityCleanupController` 使用注解式 `@Scheduled`，`LibraryScanScheduler` 使用 `TaskScheduler` 和 `ScheduledTaskRegistrar` 动态注册任务。

第三类是领域事件 `DomainEvent`。`MetricsPublisherController` 监听 `DomainEvent.LibraryScanned`、`LibraryAdded`、`LibraryDeleted`、`CollectionAdded`、`CollectionDeleted`、`ReadListAdded`、`ReadListDeleted` 等事件，用来刷新或增减指标。

下游主要有四类：

`TaskEmitter`：位于 `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskEmitter.kt`。它是后台任务投递入口，负责把 `Task.ScanLibrary`、`Task.RebuildIndex`、`Task.UpgradeIndex` 等任务保存到 `TasksRepository`，再发布 `TaskAddedEvent`。后续实际执行由任务处理器消费。

`LibraryScanScheduler`：位于 application scheduler 层，负责按资料库的 `scanInterval` 注册、取消、替换周期扫描任务。

`KomgaUserLifecycle`：由 `InitialUserController` 调用，用于创建初始用户。这说明创建用户属于 domain/service 生命周期逻辑，不放在 scheduler 内部实现。

各类 repository：例如 `LibraryRepository`、`BookRepository`、`AuthenticationActivityRepository` 等。scheduler 层通过这些 repository 查询统计数据或触发清理，但不关心底层 jOOQ、SQL 或存储细节。

## 运行/调用流程

应用启动时，`Application.main()` 调用 `runApplication<Application>()`。由于 `Application` 标注了 `@SpringBootApplication` 和 `@EnableScheduling`，Spring 会扫描组件、启用调度能力，并在应用准备完成后发布 `ApplicationReadyEvent`。

启动完成后，多个监听器并行处于可触发状态：

`InitialUserController.createInitialUserOnStartupIfNoneExist()` 检查用户数量。如果数据库中没有用户，就从 `initialUsers` bean 读取初始用户列表并调用 `KomgaUserLifecycle.createUser()` 创建。

`PeriodicScannerController.scanOnStartup()` 读取所有资料库，找出设置了 `scanOnStartup` 的资料库，对每个资料库调用 `TaskEmitter.scanLibrary()`。`TaskEmitter` 会保存任务并发布 `TaskAddedEvent`，后续由任务系统执行实际扫描。

`PeriodicScannerController.scheduleScans()` 同样读取所有资料库，但它不是立即扫描，而是调用 `LibraryScanScheduler.scheduleScan()`。后者会先取消同一个 library 已有的注册任务，再根据 `scanInterval` 决定是否注册新的 fixed-rate task。周期触发时，再调用 `TaskEmitter.scanLibrary()`。

`SearchIndexController.createIndexIfNoneExist()` 检查 Lucene 索引。如果没有索引，投递完整重建任务；如果有索引但版本过旧，投递升级或局部重建任务。

`MetricsPublisherController.pushAllMetrics()` 在启动后统计所有实体数量和文件大小，并注册/刷新 Micrometer gauge。之后当领域事件发生时，`pushMetricsOnEvent()` 会局部更新指标。

应用运行期间，`AuthenticationActivityCleanupController.cleanup()` 每 24 小时触发一次，删除 UTC 时间一个月以前的认证活动记录。

资料库扫描完成后，domain service 会发布 `DomainEvent.LibraryScanned`。`MetricsPublisherController` 收到该事件后，会重新统计 `series`、`books`、`books.filesize`、`sidecars` 这些按资料库分组的指标。

## 小白阅读顺序

建议先读 `Application.kt`，确认项目启用了 `@EnableScheduling`。否则单看 scheduler 目录会不清楚 `@Scheduled` 和动态任务为什么能运行。

第二步读 `PeriodicScannerController.kt`，这是最容易理解的入口：启动后查资料库，然后要么立即投递扫描任务，要么安排周期扫描。读完它再看 `komga/src/main/kotlin/org/gotson/komga/application/scheduler/LibraryScanScheduler.kt`，可以理解“启动监听器”和“真正调度器”的分工。

第三步读 `TaskEmitter.kt` 里和本目录相关的方法，重点看 `scanLibrary()`、`rebuildIndex()`、`upgradeIndex()` 以及私有的 `submitTask()`。这能帮助理解 scheduler 目录大多只是“投递任务”，不是“执行任务”。

第四步读 `SearchIndexController.kt`，理解启动时如何维护 Lucene 索引。这里涉及 `LuceneHelper`、`LuceneEntity` 和任务优先级 `HIGHEST_PRIORITY`，是搜索基础设施与任务系统的连接点。

第五步读 `MetricsPublisherController.kt`。这个文件稍复杂，重点抓住两条线：启动时全量统计；领域事件发生时增量或局部刷新。对 Micrometer 不熟的话，可以先只理解 `Gauge` 表示当前值，`MultiGauge` 表示带 tag 的一组当前值。

第六步读 `InitialUserController.kt` 和 `AuthenticationActivityCleanupController.kt`。前者是首次启动初始化账号，后者是周期清理旧认证记录，逻辑都比较独立。

## 常见误区

不要把这里的 `Controller` 理解成 REST Controller。它们没有 `@RestController`，也没有路由映射；这里的 controller 更像 Spring 事件和调度任务的入口适配器。

不要以为 `PeriodicScannerController` 直接扫描文件。它只是调用 `TaskEmitter.scanLibrary()` 投递任务，实际扫描逻辑在任务处理和 domain service 中。

不要忽略 `@Profile`。多数类是 `@Profile("!test")`，测试环境默认不会启用；`InitialUserController` 还要求 `noclaim` profile。阅读行为时必须把 profile 条件算进去，否则会误判某些逻辑“一定会运行”。

不要把 `fixedRate = 86_400_000` 当作每天凌晨执行。它表示每 86,400,000 毫秒执行一次，第一次执行时间和应用启动、调度器初始化有关。

不要认为所有指标都会在每个事件后全量刷新。`MetricsPublisherController` 对 `libraries`、`collections`、`readlists` 多数时候只是加减计数；只有启动、资料库扫描、资料库删除等场景才会重新统计部分分组指标。

不要忽略动态调度的取消逻辑。`LibraryScanScheduler.scheduleScan(library)` 会先 `registry.remove(library.id)?.cancel(false)`，再根据新的 `scanInterval` 注册任务。这意味着资料库配置变更后可以替换旧的周期扫描计划。

不要以为初始 admin 密码固定。`dev` profile 下是固定的 `admin`，但非 `dev` profile 下会生成 12 位随机密码，并通过日志输出。实际部署时应从启动日志中读取首次密码。
