# 文件：komga/src/main/kotlin/org/gotson/komga/interfaces/scheduler/MetricsPublisherController.kt

## 它负责什么

`MetricsPublisherController.kt` 负责把 Komga 应用内的一些业务统计数据发布到 Micrometer 指标系统中，供 Actuator、Prometheus 或其他监控后端采集。

它主要做两类事情：

1. 在应用启动完成后，读取数据库中的当前统计值，初始化所有业务指标。
2. 在部分领域事件 `DomainEvent` 发生时，增量更新或重新拉取相关指标。

这个类位于 `interfaces.scheduler` 包下，但它不是传统意义上的定时任务控制器。它更像是一个“指标发布器”：通过 Spring 事件监听机制响应应用生命周期事件和领域事件。

它被 `@Component` 标记，所以会被 Spring 自动注册为 Bean；同时被 `@Profile("!test")` 标记，表示测试 profile 下不会启用，避免测试环境注册真实指标或影响测试隔离。

## 关键组成

### 包与依赖

文件包名是：

`org.gotson.komga.interfaces.scheduler`

主要 import 可以分成几组：

- Micrometer 指标 API：
  - `Counter`
  - `Gauge`
  - `MeterRegistry`
  - `MultiGauge`
  - `Tags`
  - `Timer`

- Spring 事件与组件注解：
  - `ApplicationReadyEvent`
  - `EventListener`
  - `Profile`
  - `Component`

- Komga 领域与持久层：
  - `DomainEvent`
  - `LibraryRepository`
  - `BookRepository`
  - `SeriesRepository`
  - `SeriesCollectionRepository`
  - `ReadListRepository`
  - `SidecarRepository`

- Java 并发原子值：
  - `AtomicLong`

这里没有普通意义上的 Kotlin `export`。但文件中有两个顶层 `const val` 是对外可见的常量，可以被其他文件 import 使用：

```kotlin
const val METER_TASKS_EXECUTION = "komga.tasks.execution"
const val METER_TASKS_FAILURE = "komga.tasks.failure"
```

根据仓库中调用关系，`komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskHandler.kt` 会 import 这两个常量，用于记录任务执行耗时和失败次数。

### 指标名称常量

文件顶部定义了一批私有业务实体名：

```kotlin
private const val LIBRARIES = "libraries"
private const val SERIES = "series"
private const val BOOKS = "books"
private const val BOOKS_FILESIZE = "books.filesize"
private const val COLLECTIONS = "collections"
private const val READLISTS = "readlists"
private const val SIDECARS = "sidecars"
```

这些字符串会拼到 Micrometer 指标名里，例如：

- `komga.libraries`
- `komga.series`
- `komga.books`
- `komga.books.filesize`
- `komga.collections`
- `komga.readlists`
- `komga.sidecars`

其中 `books.filesize` 的单位是 `bytes`，其余大多数是 `count`。

### 任务指标常量

```kotlin
const val METER_TASKS_EXECUTION = "komga.tasks.execution"
const val METER_TASKS_FAILURE = "komga.tasks.failure"
```

这两个常量虽然定义在本文件中，但实际记录发生在 `TaskHandler`：

- `komga.tasks.execution`：通过 `Timer` 记录不同任务类型的执行耗时。
- `komga.tasks.failure`：通过 `Counter` 记录不同任务类型的失败次数。

本文件的 `init` 块会先向 `MeterRegistry` 注册这两个基础 meter：

```kotlin
Timer
  .builder(METER_TASKS_EXECUTION)
  .description("Task execution time")
  .register(meterRegistry)

Counter
  .builder(METER_TASKS_FAILURE)
  .description("Count of failed tasks")
  .register(meterRegistry)
```

后续 `TaskHandler` 再用同名指标并带上 `type` 标签写入数据，例如不同任务类名会成为 `type` 标签值。

### 构造函数依赖

`MetricsPublisherController` 构造函数注入了多个 repository：

```kotlin
class MetricsPublisherController(
  private val libraryRepository: LibraryRepository,
  private val bookRepository: BookRepository,
  private val seriesRepository: SeriesRepository,
  private val collectionRepository: SeriesCollectionRepository,
  private val readListRepository: ReadListRepository,
  private val sidecarRepository: SidecarRepository,
  private val meterRegistry: MeterRegistry,
)
```

这些 repository 是指标的数据来源：

- `LibraryRepository.count()`：统计 library 总数。
- `SeriesCollectionRepository.count()`：统计 collection 总数。
- `ReadListRepository.count()`：统计 read list 总数。
- `SeriesRepository.countGroupedByLibraryId()`：按 library 统计 series 数量。
- `BookRepository.countGroupedByLibraryId()`：按 library 统计 book 数量。
- `BookRepository.getFilesizeGroupedByLibraryId()`：按 library 统计 book 文件大小总和。
- `SidecarRepository.countGroupedByLibraryId()`：按 library 统计 sidecar 数量。

根据当前片段和 `rg` 结果推断，这些接口的具体实现主要在 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main` 下的 DAO 中，例如 `BookDao.kt`、`SeriesDao.kt`、`SidecarDao.kt`。

### 分组指标与非分组指标

这个类把指标分成两类：

```kotlin
private final val entitiesMultiTag = listOf(SERIES, BOOKS, BOOKS_FILESIZE, SIDECARS)
private final val entitiesNoTags = listOf(LIBRARIES, COLLECTIONS, READLISTS)
private final val allEntities = entitiesMultiTag + entitiesNoTags
```

`entitiesMultiTag` 表示需要按 `library` 标签分组的指标：

- `series`
- `books`
- `books.filesize`
- `sidecars`

例如 `komga.books{library="xxx"}` 表示某个 library 下的书籍数量。

`entitiesNoTags` 表示没有标签的全局总数指标：

- `libraries`
- `collections`
- `readlists`

这些只是全局数量，例如 `komga.libraries`。

### `MultiGauge`

```kotlin
val multiGauges =
  entitiesMultiTag.associateWith { entity ->
    MultiGauge
      .builder("komga.$entity")
      .description("The number of $entity")
      .baseUnit("count")
      .register(meterRegistry)
  }
```

`MultiGauge` 适合动态多行指标。这里每一个 library 会对应一行 `Row`，并通过 `Tags.of("library", it.key)` 添加标签。

例如：

```kotlin
Row.of(Tags.of("library", it.key), it.value)
```

含义是：以 library id 作为标签值，指标值是该 library 下的数量。

### `Gauge` + `AtomicLong`

```kotlin
val noTagGauges =
  entitiesNoTags.associateWith { entity ->
    AtomicLong(0).also { value ->
      Gauge
        .builder("komga.$entity", value) { value.get().toDouble() }
        .description("The number of $entity")
        .baseUnit("count")
        .register(meterRegistry)
    }
  }
```

没有标签的指标使用 `AtomicLong` 保存当前值。Micrometer 的 `Gauge` 不主动累加，它每次被采集时会调用 lambda 读取当前值：

```kotlin
{ value.get().toDouble() }
```

所以这里的 `AtomicLong` 是实际承载数值的对象。事件发生时，代码会对它 `incrementAndGet()`、`decrementAndGet()` 或 `set(...)`。

### 文件大小指标 `bookFileSizeGauge`

```kotlin
val bookFileSizeGauge =
  MultiGauge
    .builder("komga.$BOOKS_FILESIZE")
    .description("The cumulated filesize of books")
    .baseUnit("bytes")
    .register(meterRegistry)
```

这个指标专门统计每个 library 下 book 文件总大小，单位是 `bytes`。

需要注意：`BOOKS_FILESIZE` 同时出现在 `entitiesMultiTag` 中，因此 `multiGauges` 初始化时也会为 `komga.books.filesize` 创建一个 `MultiGauge`。但在 `pushMetricsCount` 的实际分支中，`BOOKS_FILESIZE` 使用的是单独的 `bookFileSizeGauge`，而不是 `multiGauges[BOOKS_FILESIZE]`。根据当前片段看，单独定义它的目的主要是给文件大小指标设置更准确的描述和单位。

## 上下游关系

### 上游：领域事件

本文件监听 `DomainEvent`：

```kotlin
@EventListener
private fun pushMetricsOnEvent(event: DomainEvent)
```

`DomainEvent` 定义在：

`komga/src/main/kotlin/org/gotson/komga/domain/model/DomainEvent.kt`

它是一个 `sealed class`，包含很多业务事件，例如：

- `LibraryAdded`
- `LibraryDeleted`
- `LibraryScanned`
- `SeriesAdded`
- `BookAdded`
- `CollectionAdded`
- `ReadListAdded`
- `UserDeleted`

本文件只处理其中一部分事件：

- `LibraryScanned`
- `LibraryAdded`
- `LibraryDeleted`
- `CollectionAdded`
- `CollectionDeleted`
- `ReadListAdded`
- `ReadListDeleted`

其他事件全部进入：

```kotlin
else -> Unit
```

也就是不更新指标。

根据调用关系，部分事件由这些生命周期服务发布：

- `LibraryContentLifecycle` 发布 `DomainEvent.LibraryScanned`
- `SeriesCollectionLifecycle` 发布 `DomainEvent.CollectionAdded`
- `ReadListLifecycle` 发布 `DomainEvent.ReadListAdded`

删除事件也会由对应生命周期或服务层发布；当前读取片段中没有完整展开所有发布方，但 `DomainEvent` 本身定义了这些事件类型。

### 上游：应用启动事件

本文件还监听 Spring Boot 的应用就绪事件：

```kotlin
@EventListener(ApplicationReadyEvent::class)
fun pushAllMetrics()
```

当应用启动完成后，会调用：

```kotlin
allEntities.forEach { pushMetricsCount(it) }
```

这一步非常关键，因为事件监听只能处理启动之后发生的变化。应用启动时必须先从数据库读取一次完整状态，否则 gauge 初始值会停留在 `0`。

### 上游：Repository / DAO

`pushMetricsCount` 从 repository 拉取统计数据：

```kotlin
libraryRepository.count()
collectionRepository.count()
readListRepository.count()
seriesRepository.countGroupedByLibraryId()
bookRepository.countGroupedByLibraryId()
bookRepository.getFilesizeGroupedByLibraryId()
sidecarRepository.countGroupedByLibraryId()
```

这些 repository 属于 domain persistence 抽象。具体数据库查询逻辑不在本文件中，而是在 infrastructure 层，例如 jOOQ DAO。

这说明本文件不直接关心数据库表结构，只关心“能拿到哪些统计结果”。

### 下游：Micrometer / MeterRegistry

最终所有指标都会注册或更新到：

```kotlin
MeterRegistry
```

`MeterRegistry` 是 Micrometer 的核心入口。应用如果配置了 Spring Actuator、Prometheus registry 等，外部监控系统就可以采集这些指标。

下游指标包括：

- `komga.libraries`
- `komga.collections`
- `komga.readlists`
- `komga.series`
- `komga.books`
- `komga.books.filesize`
- `komga.sidecars`
- `komga.tasks.execution`
- `komga.tasks.failure`

其中 `series`、`books`、`books.filesize`、`sidecars` 会带 `library` 标签。

### 旁路关系：`TaskHandler`

本文件定义的两个任务指标常量被 `TaskHandler` 使用：

`komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskHandler.kt`

根据搜索结果，`TaskHandler` 中有类似逻辑：

- 任务完成后，用 `meterRegistry.timer(METER_TASKS_EXECUTION, "type", task.javaClass.simpleName)` 记录耗时。
- 任务失败时，用 `meterRegistry.counter(METER_TASKS_FAILURE, "type", task.javaClass.simpleName)` 增加失败计数。

所以 `MetricsPublisherController` 不负责执行任务，也不负责捕获任务异常；它只是提供并预注册这两个 meter 名称。

## 运行/调用流程

### 1. Spring 创建 Bean

应用启动时，Spring 扫描到：

```kotlin
@Component
class MetricsPublisherController
```

如果当前 profile 不是 `test`，就会创建这个 Bean，并注入所有 repository 和 `MeterRegistry`。

### 2. 初始化任务指标

构造完成时执行 `init` 块：

```kotlin
init {
  Timer.builder(METER_TASKS_EXECUTION)...
  Counter.builder(METER_TASKS_FAILURE)...
}
```

这一步注册：

- `komga.tasks.execution`
- `komga.tasks.failure`

这些是任务系统用的指标。

### 3. 初始化业务 Gauge 对象

类属性初始化时，会创建：

- `multiGauges`
- `noTagGauges`
- `bookFileSizeGauge`

其中 `noTagGauges` 内部的 `AtomicLong` 初始值都是 `0`。

### 4. 应用启动完成后推送全量指标

Spring 发布 `ApplicationReadyEvent` 后，调用：

```kotlin
pushAllMetrics()
```

它遍历：

```kotlin
allEntities
```

实际包含：

- `series`
- `books`
- `books.filesize`
- `sidecars`
- `libraries`
- `collections`
- `readlists`

然后逐个调用：

```kotlin
pushMetricsCount(entity)
```

### 5. `pushMetricsCount` 根据实体类型读取统计值

核心分支是：

```kotlin
private fun pushMetricsCount(entity: String) {
  when (entity) {
    LIBRARIES -> noTagGauges[LIBRARIES]?.set(libraryRepository.count())
    COLLECTIONS -> noTagGauges[COLLECTIONS]?.set(collectionRepository.count())
    READLISTS -> noTagGauges[READLISTS]?.set(readListRepository.count())

    SERIES -> multiGauges[SERIES]?.register(...)
    BOOKS -> multiGauges[BOOKS]?.register(...)
    BOOKS_FILESIZE -> bookFileSizeGauge.register(...)
    SIDECARS -> multiGauges[SIDECARS]?.register(...)
  }
}
```

对于无标签指标，直接设置 `AtomicLong`：

```kotlin
set(...)
```

对于分 library 指标，重新注册一批 `Row`：

```kotlin
register(rows, true)
```

第二个参数 `true` 表示覆盖已有 rows。这样如果某个 library 被删除或某类数据变成 0，旧的行可以被新的集合替换，避免残留过期标签行。

### 6. 领域事件发生时局部更新指标

当 Spring 发布 `DomainEvent` 后，`pushMetricsOnEvent` 被调用。

#### `LibraryScanned`

```kotlin
is DomainEvent.LibraryScanned -> entitiesMultiTag.forEach { pushMetricsCount(it) }
```

扫描 library 后，series、books、filesize、sidecars 都可能变化，所以这里刷新所有按 library 分组的指标。

#### `LibraryAdded`

```kotlin
is DomainEvent.LibraryAdded -> noTagGauges[LIBRARIES]?.incrementAndGet()
```

新增 library 时，只把 `komga.libraries` 加 1。

#### `LibraryDeleted`

```kotlin
is DomainEvent.LibraryDeleted -> {
  noTagGauges[LIBRARIES]?.decrementAndGet()
  entitiesMultiTag.forEach { pushMetricsCount(it) }
}
```

删除 library 时：

1. 全局 library 数量减 1。
2. 重新统计所有按 library 分组的指标。

第二步很重要，因为被删除的 library 对应的 `series`、`books`、`books.filesize`、`sidecars` 标签行需要消失。

#### `CollectionAdded` / `CollectionDeleted`

```kotlin
is DomainEvent.CollectionAdded -> noTagGauges[COLLECTIONS]?.incrementAndGet()
is DomainEvent.CollectionDeleted -> noTagGauges[COLLECTIONS]?.decrementAndGet()
```

collection 没有按 library 分组，所以只做加减。

#### `ReadListAdded` / `ReadListDeleted`

```kotlin
is DomainEvent.ReadListAdded -> noTagGauges[READLISTS]?.incrementAndGet()
is DomainEvent.ReadListDeleted -> noTagGauges[READLISTS]?.decrementAndGet()
```

read list 同样只维护全局数量。

#### 其他事件

```kotlin
else -> Unit
```

例如 `BookAdded`、`BookDeleted`、`SeriesAdded`、`SeriesDeleted` 并不会直接触发指标更新。根据当前片段推断，Komga 更依赖 `LibraryScanned` 这种扫描完成事件来批量刷新 library 下的内容统计，而不是对每一个 book/series 事件做细粒度更新。

## 小白阅读顺序

1. 先看文件顶部的常量，理解最终会生成哪些指标名：
   - `LIBRARIES`
   - `SERIES`
   - `BOOKS`
   - `BOOKS_FILESIZE`
   - `COLLECTIONS`
   - `READLISTS`
   - `SIDECARS`
   - `METER_TASKS_EXECUTION`
   - `METER_TASKS_FAILURE`

2. 再看类注解：
   - `@Profile("!test")`
   - `@Component`

   先明确这个类是 Spring Bean，而且测试环境不启用。

3. 接着看构造函数参数，理解数据从哪里来：
   - 各种 repository 提供统计数据。
   - `MeterRegistry` 负责注册和暴露指标。

4. 然后看 `entitiesMultiTag` 和 `entitiesNoTags`：

   ```kotlin
   private final val entitiesMultiTag = listOf(SERIES, BOOKS, BOOKS_FILESIZE, SIDECARS)
   private final val entitiesNoTags = listOf(LIBRARIES, COLLECTIONS, READLISTS)
   ```

   这是理解全文件的关键分界线：一类指标按 library 分组，一类指标是全局总数。

5. 再看 `multiGauges`、`noTagGauges`、`bookFileSizeGauge`：

   - `MultiGauge`：一组带标签的 gauge。
   - `Gauge + AtomicLong`：一个全局数值。
   - `bookFileSizeGauge`：特殊的文件大小统计，单位是 bytes。

6. 然后看 `pushAllMetrics()`：

   ```kotlin
   @EventListener(ApplicationReadyEvent::class)
   fun pushAllMetrics()
   ```

   这是启动后的全量初始化入口。

7. 最后看 `pushMetricsOnEvent(event: DomainEvent)` 和 `pushMetricsCount(entity: String)`：

   - `pushMetricsOnEvent` 决定“什么时候更新”。
   - `pushMetricsCount` 决定“怎么计算并写入指标”。

理解这两个函数后，这个文件的主逻辑基本就读完了。

## 常见误区

1. 不要把这个类理解成定时任务。

   它在 `interfaces.scheduler` 包下，但它没有 `@Scheduled`。它靠 Spring 事件驱动，包括 `ApplicationReadyEvent` 和 `DomainEvent`。

2. 不要以为所有领域事件都会更新指标。

   `DomainEvent` 中定义了很多事件，但本文件只处理少数几个。比如 `BookAdded`、`BookDeleted`、`SeriesAdded`、`SeriesDeleted` 在这里不会直接更新 `komga.books` 或 `komga.series`。

3. 不要把 `Gauge` 理解成会自动累加的计数器。

   `Gauge` 只是暴露当前值。这里的当前值存在 `AtomicLong` 中，事件发生时由代码手动 `incrementAndGet()`、`decrementAndGet()` 或 `set(...)`。

4. `Counter` 和 `Gauge` 的语义不同。

   `komga.tasks.failure` 是 `Counter`，表示失败次数，只会增长。

   `komga.libraries`、`komga.collections`、`komga.readlists` 是 `Gauge`，表示当前数量，可以增加也可以减少。

5. `MultiGauge.register(rows, true)` 的 `true` 很重要。

   它表示用新的 rows 覆盖旧 rows。对于按 library 分组的指标，如果 library 被删除，这样可以避免旧 library 标签继续残留在监控数据中。

6. `BOOKS_FILESIZE` 虽然在 `entitiesMultiTag` 中，但实际更新时走的是 `bookFileSizeGauge`。

   `multiGauges` 初始化时会包含 `BOOKS_FILESIZE`，不过 `pushMetricsCount` 对 `BOOKS_FILESIZE` 的分支使用的是单独定义的 `bookFileSizeGauge`，因为它需要 `bytes` 作为单位，并且描述是累计文件大小。

7. `@Profile("!test")` 不是装饰性注解。

   测试环境中这个 Bean 不会启用。如果在测试里找不到这些指标监听逻辑，不一定是配置错了，而是 profile 条件主动排除了它。

8. 这个文件不直接决定指标如何被外部访问。

   它只注册到 `MeterRegistry`。指标最终是否能通过 `/actuator/prometheus` 或其他端点访问，取决于 Spring Boot Actuator、Micrometer registry 和应用配置。
