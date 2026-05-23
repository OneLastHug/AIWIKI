# 文件：komga/src/main/kotlin/org/gotson/komga/interfaces/scheduler/SearchIndexController.kt

## 它负责什么

`SearchIndexController.kt` 是 Komga 启动阶段的 Lucene 搜索索引检查器。它不直接执行索引重建，也不直接写 Lucene 文档，而是在 Spring Boot 应用启动完成后判断当前 Lucene 索引是否存在、版本是否过旧，然后通过 `TaskEmitter` 投递高优先级后台任务。

它的职责可以概括为三件事：

1. 应用启动后检查 Lucene 索引目录中是否已经存在索引。
2. 如果索引不存在，触发一次完整索引重建。
3. 如果索引存在但版本低于当前预期版本，触发升级或局部重建任务。

这个类位于 `interfaces/scheduler` 包下，说明它属于“接口层的调度/启动触发器”，而不是搜索基础设施本身。真正的 Lucene 操作由 `komga/src/main/kotlin/org/gotson/komga/infrastructure/search/LuceneHelper.kt` 和 `komga/src/main/kotlin/org/gotson/komga/infrastructure/search/SearchIndexLifecycle.kt` 负责。

## 关键组成

这个文件的包名是：

```kotlin
package org.gotson.komga.interfaces.scheduler
```

它通过 Spring 注解注册为组件：

```kotlin
@Profile("!test")
@Component
class SearchIndexController(...)
```

`@Component` 表示它会被 Spring 容器扫描并实例化。`@Profile("!test")` 表示在 `test` profile 下不会启用，避免测试环境启动时自动触发真实的索引检查和后台任务。

构造函数注入了两个依赖：

```kotlin
private val luceneHelper: LuceneHelper
private val taskEmitter: TaskEmitter
```

`LuceneHelper` 来自 `org.gotson.komga.infrastructure.search.LuceneHelper`，用于读取 Lucene 索引状态，例如：

- `indexExists()`：判断 Lucene 索引是否存在。
- `getIndexVersion()`：读取当前索引版本。

`TaskEmitter` 来自 `org.gotson.komga.application.tasks.TaskEmitter`，用于提交后台任务。这个文件中用到两个方法：

- `rebuildIndex(priority, entities)`：提交索引重建任务。
- `upgradeIndex(priority)`：提交索引升级任务。

文件中还导入了：

```kotlin
import org.gotson.komga.application.tasks.HIGHEST_PRIORITY
import org.gotson.komga.infrastructure.search.LuceneEntity
```

`HIGHEST_PRIORITY` 定义在 `komga/src/main/kotlin/org/gotson/komga/application/tasks/Task.kt`，值为 `8`。这里使用最高优先级，说明索引启动修复任务被认为比普通后台任务更重要。

`LuceneEntity` 定义在 `komga/src/main/kotlin/org/gotson/komga/infrastructure/search/LuceneEntity.kt`，它枚举了可索引的实体类型：

```kotlin
Book
Series
Collection
ReadList
```

但 `SearchIndexController.kt` 中只显式使用了 `LuceneEntity.Series`，表示某些历史版本升级后只需要重建 `Series` 相关索引。

核心方法是：

```kotlin
@EventListener(ApplicationReadyEvent::class)
fun createIndexIfNoneExist()
```

`ApplicationReadyEvent` 是 Spring Boot 在应用准备好接受请求后发布的事件。这个方法监听该事件，因此它会在应用启动完成后自动执行一次。

核心逻辑如下：

```kotlin
if (!luceneHelper.indexExists()) {
  logger.info { "Lucene index not found, trigger rebuild" }
  taskEmitter.rebuildIndex(HIGHEST_PRIORITY)
} else {
  val indexVersion = luceneHelper.getIndexVersion()
  logger.info { "Lucene index version: $indexVersion" }
  when {
    indexVersion < 6 -> {
      taskEmitter.upgradeIndex(HIGHEST_PRIORITY)
      taskEmitter.rebuildIndex(HIGHEST_PRIORITY, setOf(LuceneEntity.Series))
    }

    indexVersion < 8 -> taskEmitter.rebuildIndex(HIGHEST_PRIORITY, setOf(LuceneEntity.Series))
  }
}
```

这里有三个分支：

1. 没有索引：提交完整重建任务。
2. 索引版本小于 `6`：先提交 Lucene 索引格式升级任务，再提交 `Series` 索引重建任务。
3. 索引版本小于 `8`：只提交 `Series` 索引重建任务。

根据 `SearchIndexLifecycle.kt` 中的当前实现，系统当前索引版本常量是：

```kotlin
private const val INDEX_VERSION = 8
```

因此 `SearchIndexController.kt` 的 `indexVersion < 8` 判断是在处理旧版本索引迁移到当前版本的兼容逻辑。

## 上下游关系

上游是 Spring Boot 启动事件。

当应用启动完成后，Spring 发布 `ApplicationReadyEvent`。`SearchIndexController.createIndexIfNoneExist()` 因为标注了 `@EventListener(ApplicationReadyEvent::class)`，会被自动调用。

同目录中还有类似的启动型 scheduler 控制器，例如 `komga/src/main/kotlin/org/gotson/komga/interfaces/scheduler/PeriodicScannerController.kt`。它同样监听 `ApplicationReadyEvent`，启动后根据 library 配置触发扫描或注册周期扫描任务。这说明 `interfaces/scheduler` 目录主要放“启动时或定时触发应用任务”的适配器代码。

`SearchIndexController.kt` 的直接下游是 `TaskEmitter`。

在 `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskEmitter.kt` 中，对应方法是：

```kotlin
fun rebuildIndex(
  priority: Int = DEFAULT_PRIORITY,
  entities: Set<LuceneEntity>? = null,
) {
  submitTask(Task.RebuildIndex(entities, priority))
}

fun upgradeIndex(priority: Int = DEFAULT_PRIORITY) {
  submitTask(Task.UpgradeIndex(priority))
}
```

也就是说，`SearchIndexController.kt` 并不调用 `SearchIndexLifecycle.rebuildIndex()` 或 `LuceneHelper.upgradeIndex()`。它只是创建任务：

- `Task.RebuildIndex`
- `Task.UpgradeIndex`

这些任务后续由任务系统消费执行。

再往下游看，真正处理索引生命周期的是 `komga/src/main/kotlin/org/gotson/komga/infrastructure/search/SearchIndexLifecycle.kt`。其中有：

```kotlin
fun upgradeIndex() {
  luceneHelper.upgradeIndex()
  luceneHelper.setIndexVersion(INDEX_VERSION)
}

fun rebuildIndex(entities: Set<LuceneEntity>? = null) {
  val targetEntities = entities ?: LuceneEntity.entries.toSet()
  ...
  luceneHelper.setIndexVersion(INDEX_VERSION)
}
```

`SearchIndexLifecycle.rebuildIndex()` 会根据传入的 `entities` 决定重建全部实体索引，还是只重建某些实体索引。如果 `entities == null`，就重建 `LuceneEntity.entries.toSet()`，也就是 `Book`、`Series`、`Collection`、`ReadList` 全部类型。

`LuceneHelper` 是更底层的 Lucene 操作封装。相关方法包括：

```kotlin
fun indexExists(): Boolean = DirectoryReader.indexExists(directory)
```

```kotlin
fun getIndexVersion(): Int {
  ...
  return ... ?: 1
}
```

```kotlin
fun upgradeIndex() {
  IndexUpgrader(directory, IndexWriterConfig(indexAnalyzer), true).upgrade()
  logger.info { "Lucene index upgraded" }
}
```

这里有一个重要细节：`getIndexVersion()` 如果读不到版本文档，会返回 `1`。因此老索引即使没有显式版本记录，也会被当作版本 `1` 处理，从而进入 `indexVersion < 6` 的升级分支。

## 运行/调用流程

一次典型启动流程如下：

1. Komga 应用启动。
2. Spring Boot 完成应用初始化，发布 `ApplicationReadyEvent`。
3. `SearchIndexController.createIndexIfNoneExist()` 被调用。
4. 方法先调用 `luceneHelper.indexExists()`。
5. 如果返回 `false`，说明索引不存在：
   - 记录日志 `"Lucene index not found, trigger rebuild"`。
   - 调用 `taskEmitter.rebuildIndex(HIGHEST_PRIORITY)`。
   - 因为没有传 `entities`，后续会重建全部 Lucene 实体索引。
6. 如果返回 `true`，说明索引存在：
   - 调用 `luceneHelper.getIndexVersion()`。
   - 记录日志 `"Lucene index version: $indexVersion"`。
   - 根据版本号判断是否需要修复。

版本判断的含义如下：

```kotlin
indexVersion < 6
```

这个分支会提交两个任务：

```kotlin
taskEmitter.upgradeIndex(HIGHEST_PRIORITY)
taskEmitter.rebuildIndex(HIGHEST_PRIORITY, setOf(LuceneEntity.Series))
```

根据注释：

```kotlin
// upgrade index to Lucene 9.x
```

这个分支用于非常旧的索引版本。它不仅需要升级 Lucene 索引底层格式，还需要重建 `Series` 实体索引。

```kotlin
indexVersion < 8
```

这个分支只提交：

```kotlin
taskEmitter.rebuildIndex(HIGHEST_PRIORITY, setOf(LuceneEntity.Series))
```

说明版本 `6` 到 `7` 的索引不需要 Lucene 格式升级，但需要刷新 `Series` 类型的索引内容。根据当前片段推断，版本 `8` 的变更主要影响 `Series` 文档结构或字段内容；依据是 `SearchIndexController.kt` 只对 `LuceneEntity.Series` 做局部重建，而 `SearchIndexLifecycle.kt` 中当前全局 `INDEX_VERSION` 是 `8`。

当任务执行到 `SearchIndexLifecycle.rebuildIndex(setOf(LuceneEntity.Series))` 时，它会：

1. 将目标实体限定为 `Series`。
2. 通过 `seriesDtoRepository.findAll(p)` 分页读取 series 数据。
3. 将每个 `SeriesDto` 转换成 Lucene `Document`。
4. 删除旧的 `type = "series"` 文档。
5. 批量写入新的 series 文档。
6. 调用 `luceneHelper.setIndexVersion(INDEX_VERSION)`，把版本写成 `8`。

如果是完整重建，则会对 `Book`、`Series`、`Collection`、`ReadList` 都执行类似流程。

## 小白阅读顺序

建议按下面顺序阅读，不要一开始就钻进 Lucene 细节。

第一步，先看 `SearchIndexController.kt` 本身。

重点看这几个点：

- `@Profile("!test")`
- `@Component`
- `@EventListener(ApplicationReadyEvent::class)`
- `luceneHelper.indexExists()`
- `luceneHelper.getIndexVersion()`
- `taskEmitter.rebuildIndex(...)`
- `taskEmitter.upgradeIndex(...)`

读完后先建立一个印象：这个类只是“启动时检查并发任务”，不是“执行索引”。

第二步，看 `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskEmitter.kt`。

重点找：

```kotlin
fun rebuildIndex(...)
fun upgradeIndex(...)
```

你会发现它只是把请求包装成任务：

```kotlin
Task.RebuildIndex(...)
Task.UpgradeIndex(...)
```

这一步能帮助理解 Komga 的架构习惯：很多耗时操作不会在控制器里直接执行，而是进入任务系统。

第三步，看 `komga/src/main/kotlin/org/gotson/komga/infrastructure/search/SearchIndexLifecycle.kt`。

重点看：

```kotlin
private const val INDEX_VERSION = 8
fun upgradeIndex()
fun rebuildIndex(entities: Set<LuceneEntity>? = null)
```

这里才是真正的“索引生命周期”实现。它负责决定重建哪些实体、如何分页读取数据、如何转换成 Lucene 文档、如何写入版本号。

第四步，看 `komga/src/main/kotlin/org/gotson/komga/infrastructure/search/LuceneHelper.kt`。

重点看：

```kotlin
fun indexExists()
fun getIndexVersion()
fun setIndexVersion(version: Int)
fun upgradeIndex()
fun addDocuments(...)
fun deleteDocuments(...)
```

这一步能看到 Lucene 的底层操作封装，包括 `DirectoryReader`、`IndexUpgrader`、`IndexWriter`、`SearcherManager` 等。

第五步，看 `komga/src/main/kotlin/org/gotson/komga/infrastructure/search/LuceneEntity.kt`。

重点理解 `LuceneEntity` 枚举：

```kotlin
Book
Series
Collection
ReadList
```

以及每种实体的：

- `type`
- `id`
- `defaultFields`

这会帮助你理解为什么 `SearchIndexController.kt` 中可以写：

```kotlin
setOf(LuceneEntity.Series)
```

这不是随便传字符串，而是在用统一的索引实体枚举限定重建范围。

## 常见误区

误区一：以为 `SearchIndexController.kt` 会直接重建索引。

实际上它不会直接写 Lucene，也不会直接读取数据库实体。它只负责在启动时检查状态，然后通过 `TaskEmitter` 投递后台任务。真正重建索引的是 `SearchIndexLifecycle.rebuildIndex()`，真正操作 Lucene 的是 `LuceneHelper`。

误区二：以为 `createIndexIfNoneExist()` 只在没有索引时才工作。

方法名叫 `createIndexIfNoneExist`，但实际逻辑不止“没有索引就创建”。它还会检查索引版本，并在版本低于 `6` 或 `8` 时触发升级或局部重建。因此这个方法也承担了启动时索引迁移的职责。

误区三：以为 `indexVersion < 8` 会重建全部索引。

不会。代码中明确传入了：

```kotlin
setOf(LuceneEntity.Series)
```

这表示只重建 `Series` 类型的索引。只有 `taskEmitter.rebuildIndex(HIGHEST_PRIORITY)` 这种没有传 `entities` 的调用，才会在后续 `SearchIndexLifecycle` 中被解释为重建全部实体。

误区四：以为 `upgradeIndex()` 和 `rebuildIndex()` 是同一件事。

它们不是同一层面的操作。`upgradeIndex()` 对应 Lucene 底层索引格式升级，`LuceneHelper.upgradeIndex()` 内部使用的是 `IndexUpgrader`。`rebuildIndex()` 则是从 Komga 的业务数据重新生成 Lucene 文档。版本小于 `6` 时两个都要做；版本小于 `8` 但不小于 `6` 时只需要重建 `Series`。

误区五：忽略 `@Profile("!test")`。

这个注解决定了测试环境不会启用该组件。如果你在测试里期待启动时自动触发索引重建，可能会发现它没有执行。原因不是事件没发布，而是这个 bean 在 `test` profile 下根本没有注册。

误区六：以为索引版本来自配置文件。

根据当前代码，索引版本不是从 application 配置读取的，而是写在 Lucene 索引自身中。`LuceneHelper.setIndexVersion(version)` 会写入一个带有 `type = "index_version"` 的 Lucene 文档；`getIndexVersion()` 会搜索这个文档并读取 `index_version` 字段。如果读不到，默认返回 `1`。

误区七：以为 `ApplicationReadyEvent` 发生在应用刚开始启动时。

`ApplicationReadyEvent` 是 Spring Boot 启动流程后期事件，表示应用已经准备好。这个选择很关键，因为索引检查可能依赖已经初始化好的 Lucene、任务系统、数据库访问能力等组件。
