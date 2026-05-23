# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/DomainEvent.kt

## 它负责什么

`komga/src/main/kotlin/org/gotson/komga/domain/model/DomainEvent.kt` 定义了 Komga 后端领域层使用的一组“领域事件”类型。

它本身不执行业务逻辑，也不直接访问数据库、网络或文件系统；它的职责是把“某个领域对象发生了什么变化”包装成强类型事件，交给 Spring 的事件机制分发给下游监听器。

从调用方可以看出，业务服务在完成数据库变更后会调用：

`eventPublisher.publishEvent(DomainEvent.Xxx(...))`

然后监听方通过 `@EventListener` 接收 `DomainEvent`，根据具体子类型执行后续动作，例如：

- 向前端 SSE 推送实体变化；
- 更新 Lucene 搜索索引；
- 刷新或调整指标；
- 通知某个用户会话过期；
- 把导入结果推送给管理员。

因此，这个文件可以理解为 Komga 后端内部的“事件协议表”：它统一列出系统中哪些领域变化值得被广播，以及每种变化携带哪些最小数据。

## 关键组成

这个文件位于包：

`org.gotson.komga.domain.model`

唯一显式 import 是：

`java.net.URL`

因为 `BookImported` 事件需要携带导入源文件 `sourceFile: URL`。

核心定义是：

```kotlin
sealed class DomainEvent
```

`sealed class` 表示所有合法子类型都定义在同一个编译边界内。这里所有事件都作为 `DomainEvent` 的嵌套 `data class` 出现。这样下游在 `when (event)` 中匹配事件时，Kotlin 可以知道当前事件集合是封闭的，有利于写出穷尽式分支。

这个文件没有 TypeScript/JavaScript 意义上的 `export`。在 Kotlin 中，顶层声明默认是 public；其他包通过 import：

`import org.gotson.komga.domain.model.DomainEvent`

即可使用 `DomainEvent.LibraryAdded`、`DomainEvent.BookUpdated` 等嵌套事件类。

事件大致分为几组。

第一组是 Library 事件：

- `LibraryAdded(val library: Library)`
- `LibraryUpdated(val library: Library)`
- `LibraryDeleted(val library: Library)`
- `LibraryScanned(val library: Library)`

它们描述书库的新增、更新、删除和扫描完成。`LibraryScanned` 比较特殊：在 `SseController` 中它不会推送前端 SSE，但在指标监听器里会触发实体数量统计刷新。

第二组是 Series 事件：

- `SeriesAdded(val series: Series)`
- `SeriesUpdated(val series: Series)`
- `SeriesDeleted(val series: Series)`

它们描述系列的新增、更新和删除。搜索索引监听器会据此新增、更新或删除 `LuceneEntity.Series` 文档；SSE 监听器会把它们映射成 `SeriesAdded`、`SeriesChanged`、`SeriesDeleted` 这类前端事件名。

第三组是 Book 事件：

- `BookAdded(val book: Book)`
- `BookUpdated(val book: Book)`
- `BookDeleted(val book: Book)`
- `BookImported(val book: Book?, val sourceFile: URL, val success: Boolean, val message: String? = null)`

前三个描述书籍实体本身的生命周期变化。`BookImported` 描述导入任务结果，允许 `book` 为 null，因为导入失败时不一定生成了书籍实体；它还携带源文件 URL、是否成功和可选消息。`SseController` 中 `BookImported` 会以 `adminOnly = true` 推送，说明这是偏管理端的通知。

第四组是 Collection 事件：

- `CollectionAdded(val collection: SeriesCollection)`
- `CollectionUpdated(val collection: SeriesCollection)`
- `CollectionDeleted(val collection: SeriesCollection)`

这里的 `SeriesCollection` 是 Komga 的系列合集。它会影响 SSE 推送和搜索索引中的 `LuceneEntity.Collection`。

第五组是 ReadList 事件：

- `ReadListAdded(val readList: ReadList)`
- `ReadListUpdated(val readList: ReadList)`
- `ReadListDeleted(val readList: ReadList)`

ReadList 是阅读列表。SSE 下发时会带上 `readList.id` 和书籍 id 列表；搜索索引监听器也会根据它们维护 ReadList 文档。

第六组是阅读进度事件：

- `ReadProgressChanged(val progress: ReadProgress)`
- `ReadProgressDeleted(val progress: ReadProgress)`
- `ReadProgressSeriesChanged(val seriesId: String, val userId: String)`
- `ReadProgressSeriesDeleted(val seriesId: String, val userId: String)`

前两个是单本书维度的阅读进度变化，携带完整 `ReadProgress`。后两个是系列维度的聚合事件，只携带 `seriesId` 和 `userId`。从 `SeriesLifecycle` 的调用看，当批量标记某个系列已读或删除某个系列的阅读进度时，代码会先逐本发布 `ReadProgressChanged` / `ReadProgressDeleted`，再发布系列级别事件，方便前端或其他监听器做更粗粒度刷新。

第七组是缩略图事件：

- `ThumbnailBookAdded(val thumbnail: ThumbnailBook)`
- `ThumbnailBookDeleted(val thumbnail: ThumbnailBook)`
- `ThumbnailSeriesAdded(val thumbnail: ThumbnailSeries)`
- `ThumbnailSeriesDeleted(val thumbnail: ThumbnailSeries)`
- `ThumbnailSeriesCollectionAdded(val thumbnail: ThumbnailSeriesCollection)`
- `ThumbnailSeriesCollectionDeleted(val thumbnail: ThumbnailSeriesCollection)`
- `ThumbnailReadListAdded(val thumbnail: ThumbnailReadList)`
- `ThumbnailReadListDeleted(val thumbnail: ThumbnailReadList)`

它们分别对应书籍、系列、合集、阅读列表的缩略图新增或删除。SSE 监听器会把这些事件转换为前端可以识别的缩略图刷新消息，并携带 selected 状态。

第八组是用户事件：

- `UserUpdated(val user: KomgaUser, val expireSession: Boolean)`
- `UserDeleted(val user: KomgaUser)`

`UserUpdated` 除了用户对象，还包含 `expireSession` 标志。`SseController` 中只有当 `expireSession == true` 时才会推送 `SessionExpired`；`UserDeleted` 则总是给对应用户推送会话过期事件。

## 上下游关系

上游主要是领域服务和部分 REST 控制器。它们完成实际业务变更后发布事件。

典型发布方包括：

- `komga/src/main/kotlin/org/gotson/komga/domain/service/LibraryLifecycle.kt`
- `komga/src/main/kotlin/org/gotson/komga/domain/service/SeriesLifecycle.kt`
- `komga/src/main/kotlin/org/gotson/komga/domain/service/BookLifecycle.kt`
- `komga/src/main/kotlin/org/gotson/komga/domain/service/ReadListLifecycle.kt`
- `komga/src/main/kotlin/org/gotson/komga/domain/service/SeriesCollectionLifecycle.kt`
- `komga/src/main/kotlin/org/gotson/komga/domain/service/BookImporter.kt`
- `komga/src/main/kotlin/org/gotson/komga/domain/service/KomgaUserLifecycle.kt`
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/BookController.kt`
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/SeriesController.kt`
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/ReadListController.kt`
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/SeriesCollectionController.kt`

例如 `SeriesLifecycle` 在创建书籍相关记录后，会对每个新增的 `Book` 发布 `DomainEvent.BookAdded(it)`；创建系列后发布 `DomainEvent.SeriesAdded(series)`；删除系列后发布 `DomainEvent.SeriesDeleted(it)`；批量修改阅读进度后发布 `ReadProgressChanged` 和 `ReadProgressSeriesChanged`。

下游主要是事件监听器。

最明显的是 `komga/src/main/kotlin/org/gotson/komga/interfaces/sse/SseController.kt`。它有：

```kotlin
@EventListener
fun handleSseEvent(event: DomainEvent)
```

这个方法通过 `when (event)` 把领域事件转换成 SSE 事件名和 DTO，再推送给前端连接。比如：

- `DomainEvent.LibraryAdded` -> `"LibraryAdded"`
- `DomainEvent.LibraryUpdated` -> `"LibraryChanged"`
- `DomainEvent.BookUpdated` -> `"BookChanged"`
- `DomainEvent.ReadProgressChanged` -> `"ReadProgressChanged"`
- `DomainEvent.UserDeleted` -> `"SessionExpired"`

注意领域事件名和 SSE 事件名并不总是一一同名，例如 `LibraryUpdated` 被映射为 `LibraryChanged`，`BookUpdated` 被映射为 `BookChanged`。领域层表达“发生了什么”，接口层表达“通知前端怎么刷新”。

另一个重要下游是 `komga/src/main/kotlin/org/gotson/komga/infrastructure/search/SearchIndexLifecycle.kt`。它同样通过 `@EventListener` 接收 `DomainEvent`，但只关心会影响搜索索引的事件：

- `SeriesAdded` / `SeriesUpdated` / `SeriesDeleted`
- `BookAdded` / `BookUpdated` / `BookDeleted`
- `ReadListAdded` / `ReadListUpdated` / `ReadListDeleted`
- `CollectionAdded` / `CollectionUpdated` / `CollectionDeleted`

其他事件通过 `else -> Unit` 忽略。根据当前片段推断，缩略图、用户、阅读进度、导入结果等事件不需要进入全文搜索索引，所以搜索监听器不处理它们。

还有 `komga/src/main/kotlin/org/gotson/komga/interfaces/scheduler/MetricsPublisherController.kt` 会监听部分事件更新指标。它关注 `LibraryScanned`、`LibraryAdded`、`LibraryDeleted`、`CollectionAdded`、`CollectionDeleted`、`ReadListAdded`、`ReadListDeleted` 等，用来维护或刷新计数类指标。

## 运行/调用流程

一个典型流程可以按“业务变更 -> 发布事件 -> 多个监听器响应”来理解。

以新增系列为例：

1. 业务入口调用 `SeriesLifecycle.createSeries(series)`。
2. `SeriesLifecycle` 在事务中插入 `series`、初始化 `SeriesMetadata`、初始化 `BookMetadataAggregation`。
3. 事务完成后调用 `eventPublisher.publishEvent(DomainEvent.SeriesAdded(series))`。
4. Spring 事件系统把这个 `DomainEvent.SeriesAdded` 分发给所有匹配的 `@EventListener`。
5. `SseController.handleSseEvent` 收到事件，匹配到 `SeriesAdded`，推送 `"SeriesAdded"`，数据里包含 `series.id` 和 `series.libraryId`。
6. `SearchIndexLifecycle.consumeEvents` 收到事件，查询对应 series 的 DTO，转换成 Lucene 文档后调用 `addEntity(it)`。
7. 其他监听器如果关心这个事件，也可以同时响应；不关心则忽略。

以书籍导入为例：

1. `BookImporter` 执行导入。
2. 如果成功，发布 `DomainEvent.BookImported(importedBook, sourceFile.toUri().toURL(), success = true)`。
3. 如果失败，发布 `DomainEvent.BookImported(null, sourceFile.toUri().toURL(), success = false, msg)`。
4. `SseController` 把它转换成 `"BookImported"`，并且 `adminOnly = true`，只推送给管理员相关 SSE 连接。
5. 搜索索引监听器不处理 `BookImported`。如果导入过程中真的创建了 `Book`，根据当前片段推断，书籍新增本身还会通过其他流程发布 `BookAdded` 或后续更新事件；`BookImported` 主要承担“导入结果通知”的职责。

以阅读进度批量变更为例：

1. `SeriesLifecycle.markReadProgressCompleted(seriesId, user)` 查询系列下所有需要更新的书籍。
2. 为每本书构造并保存 `ReadProgress`。
3. 对每条进度发布 `DomainEvent.ReadProgressChanged(it)`。
4. 再发布一次 `DomainEvent.ReadProgressSeriesChanged(seriesId, user.id)`。
5. `SseController` 对单本进度事件推送 `"ReadProgressChanged"`，对系列聚合事件推送 `"ReadProgressSeriesChanged"`，并且都限制到对应 `userIdOnly`。
6. 搜索索引监听器不处理阅读进度事件，因为它们不影响公共搜索文档。

这个流程里有一个重要设计点：`DomainEvent.kt` 只定义事件形状，不决定谁监听、如何处理、是否异步、是否事务后执行。这些由 Spring 事件机制和具体监听器实现决定。

## 小白阅读顺序

建议先读 `DomainEvent.kt` 本身，不要急着看所有调用方。先把事件按实体分组：Library、Series、Book、Collection、ReadList、ReadProgress、Thumbnail、User。

第二步看 `komga/src/main/kotlin/org/gotson/komga/domain/service/SeriesLifecycle.kt`。这个文件展示了事件通常在哪里发布：先在事务里改数据库，再在事务外或事务后附近调用 `eventPublisher.publishEvent(...)`。重点看 `BookAdded`、`SeriesAdded`、`SeriesUpdated`、`SeriesDeleted`、`ReadProgressChanged` 这些事件。

第三步看 `komga/src/main/kotlin/org/gotson/komga/interfaces/sse/SseController.kt` 的 `handleSseEvent`。这里能直观看到领域事件如何变成前端实时通知。读的时候要留意事件名映射，例如 `BookUpdated` 对应前端 `"BookChanged"`，并不是简单照搬类名。

第四步看 `komga/src/main/kotlin/org/gotson/komga/infrastructure/search/SearchIndexLifecycle.kt` 的 `consumeEvents`。这里能理解为什么事件比直接调用索引服务更解耦：业务服务只说“BookUpdated 了”，搜索模块自己决定如何重新取 DTO、转换文档、更新 Lucene。

第五步再按兴趣看其他发布者，比如 `BookLifecycle.kt`、`ReadListLifecycle.kt`、`SeriesCollectionLifecycle.kt`、`KomgaUserLifecycle.kt`。这时你会发现 `DomainEvent` 是横跨多个业务模块的通知语言，而不是某一个功能的私有类型。

## 常见误区

误区一：把 `DomainEvent` 当成数据库实体。

它不是数据库表模型，也没有持久化注解。虽然事件里携带 `Library`、`Book`、`Series` 等领域对象，但事件本身只是运行时消息，用来通知其他组件。

误区二：以为所有事件都会推送给前端。

不是。`SseController` 确实处理了大多数事件，但例如 `LibraryScanned` 在 SSE 中是 `Unit`，不会推送。搜索索引也只处理部分实体增删改事件。每个下游监听器会选择自己关心的事件。

误区三：以为事件类名等于前端事件名。

不完全相等。`LibraryUpdated` 会变成 `"LibraryChanged"`，`SeriesUpdated` 会变成 `"SeriesChanged"`，`BookUpdated` 会变成 `"BookChanged"`。领域层命名面向业务语义，接口层命名面向客户端订阅协议。

误区四：忽略 `BookImported.book` 可以为 null。

`BookImported` 的 `book: Book?` 是可空的，因为导入失败时没有成功创建书籍。下游处理时必须使用安全访问，例如 `event.book?.id`。`SseController` 正是这样做的。

误区五：认为 `sealed class` 会自动处理所有事件副作用。

`sealed class` 只限制和组织类型集合，不会自动发布、监听或执行任何逻辑。事件是否被发布取决于上游是否调用 `eventPublisher.publishEvent`；事件产生什么效果取决于是否有监听器处理它。

误区六：新增事件只改 `DomainEvent.kt` 就够了。

通常不够。新增一种 `DomainEvent` 后，至少要检查几个下游：`SseController` 是否需要推送前端，`SearchIndexLifecycle` 是否需要更新索引，`MetricsPublisherController` 是否需要更新指标，相关测试是否需要覆盖。因为 `DomainEvent` 是跨模块协议，新增事件意味着要确认所有消费者的行为。

误区七：把事件携带的对象理解为“最新一定完整”的快照。

很多事件确实携带领域对象，但下游不一定直接使用它的全部字段。例如搜索索引监听器在 `BookUpdated` 后会重新通过 repository 查询 DTO，再转换为搜索文档；SSE 监听器通常只取 id、libraryId、seriesId 等轻量字段。根据当前片段推断，事件携带对象更多是为了提供定位信息和必要上下文，而不是要求所有下游都完全依赖这个对象快照。
