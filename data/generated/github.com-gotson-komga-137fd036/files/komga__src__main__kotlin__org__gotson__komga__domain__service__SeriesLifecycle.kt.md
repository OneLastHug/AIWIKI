# 文件：komga/src/main/kotlin/org/gotson/komga/domain/service/SeriesLifecycle.kt

## 它负责什么

`SeriesLifecycle` 是 Komga 领域层里负责“系列（Series）生命周期编排”的服务类。它本身不是数据库表模型，也不是 HTTP Controller，而是把一组与 `Series` 相关的业务动作串起来：创建系列、给系列添加书籍、排序书籍、删除系列、维护阅读进度、获取或维护系列封面、删除系列文件夹等。

它的核心职责可以概括为三类：

1. **维护 Series 与关联实体的一致性**
   例如创建 series 时同时创建 `SeriesMetadata` 和 `BookMetadataAggregation`；删除 series 时同时删除书籍、阅读进度、集合关系、缩略图、元数据聚合等。

2. **把 series 级操作下沉到 book 级操作**
   例如 `deleteMany` 会委托 `BookLifecycle.deleteMany` 删除该系列下的所有书；`deleteSeriesFiles` 会逐本调用 `bookLifecycle.deleteBookFiles` 删除书籍文件。

3. **发布领域事件和触发后续任务**
   例如创建 series 后发布 `DomainEvent.SeriesAdded`；添加书籍后发布 `DomainEvent.BookAdded`；排序导致书籍编号元数据变化时，通过 `TaskEmitter.refreshBookMetadata` 触发元数据刷新。

它位于 `org.gotson.komga.domain.service` 包下，符合该目录其他 `*Lifecycle` 类的风格：不是单一 Repository 包装，而是负责领域动作的事务、关联数据、事件和任务编排。

## 关键组成

这个类被 `@Service` 标记，因此由 Spring 容器管理。构造函数注入了大量 Repository 和服务，说明它的职责横跨多个聚合边界：

- `LibraryRepository`：读取库配置，例如系列封面策略 `Library.SeriesCover`。
- `BookRepository`：查询、插入、排序、删除 series 下的书籍。
- `BookLifecycle`：复用 book 级生命周期逻辑，例如删除书籍、获取书籍封面。
- `MediaRepository`：创建书籍媒体记录，读取页数用于阅读进度完成状态。
- `BookMetadataRepository`：维护每本书的编号、排序编号等元数据。
- `SeriesRepository`：创建、更新、删除 series 主记录。
- `ThumbnailSeriesRepository`：维护 series 封面/海报。
- `SeriesMetadataRepository`：维护 series 元数据。
- `BookMetadataAggregationRepository`：维护 series 级的书籍元数据聚合。
- `SeriesCollectionRepository`：删除 series 时从所有 collection 中移除。
- `ReadProgressRepository`：维护用户阅读进度。
- `TaskEmitter`：触发异步任务，例如刷新书籍或系列元数据。
- `ApplicationEventPublisher`：发布领域事件。
- `TransactionTemplate`：显式包裹多表写操作。
- `HistoricalEventRepository`：记录文件夹删除等历史事件。

主要方法如下：

- `sortBooks(series)`：按书名自然排序，更新 `Book.number`，并在未锁定时同步更新 `BookMetadata.number` 和 `BookMetadata.numberSort`。
- `addBooks(series, booksToAdd)`：把一批书加入 series，同时创建 `Media` 和 `BookMetadata`。
- `createSeries(series)`：插入 series，并初始化 `SeriesMetadata` 与 `BookMetadataAggregation`。
- `softDeleteMany(series)`：软删除 series，同时软删除其下 books。
- `deleteMany(series)`：硬删除 series 及其关联数据。
- `markReadProgressCompleted(seriesId, user)`：把 series 下未完成的书籍全部标记为已读。
- `deleteReadProgress(seriesId, user)`：删除某用户在该 series 下的阅读进度。
- `getSelectedThumbnail(seriesId)`：获取当前选中的 series 封面，并在封面失效时做 housekeeping。
- `getThumbnailBytesByThumbnailId(thumbnailId)`：按 thumbnail id 读取封面字节。
- `getThumbnailBytes(seriesId, userId)`：获取 series 封面；没有显式封面时按库配置回退到某本书的封面。
- `addThumbnailForSeries(thumbnail, markSelected)`：添加 series 封面，并根据策略决定是否选中。
- `deleteThumbnailForSeries(thumbnail)`：只允许删除用户上传的封面。
- `deleteSeriesFiles(series)`：删除 series 对应文件夹、书籍文件、sidecar 封面，并软删除 series。
- `thumbnailsHouseKeeping(seriesId)`：清理不存在的封面记录，修复多个选中或没有选中的异常状态。

文件顶部还有两个辅助定义：

- `logger`：KotlinLogging 日志对象。
- `natSortComparator`：来自 `net.greypanther.natsort.CaseInsensitiveSimpleNaturalComparator`，用于大小写不敏感的自然排序。

`sortBooks` 中还使用 `stripAccents()` 和空白正则，把书名做排序前规范化：去除重音、合并连续空白、再自然排序。这能让类似 `Book 2`、`Book 10` 的顺序更符合用户预期。

## 上下游关系

上游调用者主要有几类。

`LibraryContentLifecycle` 是最重要的上游之一。扫描库目录时，如果发现新 series，会调用 `seriesLifecycle.createSeries(newSeries)`，随后 `seriesLifecycle.addBooks(createdSeries, newBooks)`；当书籍增删变化后，会调用 `seriesLifecycle.sortBooks(it)` 并触发 `taskEmitter.refreshSeriesMetadata(it.id)`。这说明 `SeriesLifecycle` 是库扫描结果落库时的核心落点。

`BookImporter` 在导入书籍后调用 `seriesLifecycle.sortBooks(series)`，保证新导入的书插入后，整个系列的编号和排序重新归一。

`LibraryLifecycle` 删除整个 library 时，会先找出该 library 下所有 series，然后调用 `seriesLifecycle.deleteMany(series)`。所以 series 删除逻辑也服务于 library 删除流程。

`TaskHandler` 在处理异步任务时会调用 `deleteSeriesFiles(series)`。例如 `Task.DeleteSeries` 直接删除 series 文件；`Task.DeleteBook` 遇到 `book.oneshot` 时，也会删除整个 oneshot 对应的 series 文件。这说明文件系统删除不是 Controller 直接做，而是通过任务系统进入领域服务。

`SeriesController` 是 REST API 上游。它会调用：

- `getThumbnailBytes(seriesId, userId)` 返回 series poster。
- `getThumbnailBytesByThumbnailId(thumbnailId)` 返回指定 poster。
- `markReadProgressCompleted(seriesId, principal.user)` 标记整个 series 已读。
- `deleteReadProgress(seriesId, principal.user)` 标记整个 series 未读。

`LocalArtworkLifecycle` 会把本地 artwork provider 找到的 series 图片交给 `addThumbnailForSeries`。

`SeriesCollectionLifecycle` 会调用 `getThumbnailBytes`，拿多个 series 封面生成 collection mosaic。

下游则主要是各种 Repository、`BookLifecycle`、`TaskEmitter` 和事件系统。也就是说，`SeriesLifecycle` 处在 Controller/扫描/任务系统与底层持久化之间，是“领域用例编排层”。

## 运行/调用流程

以扫描库发现新 series 为例，典型流程是：

1. `LibraryContentLifecycle.scanRootFolder` 分析文件系统，得到一个新的 `Series` 和一组 `Book`。
2. 调用 `SeriesLifecycle.createSeries(newSeries)`。
3. `createSeries` 在事务里插入：
   - `Series`
   - 默认 `SeriesMetadata`
   - 空的 `BookMetadataAggregation`
4. 事务结束后发布 `DomainEvent.SeriesAdded(series)`。
5. 调用 `SeriesLifecycle.addBooks(createdSeries, newBooks)`。
6. `addBooks` 先检查每本书的 `libraryId` 必须和 series 相同。
7. 在事务里插入 books，并为每本书创建：
   - `Media(bookId = it.id)`
   - `BookMetadata(title = it.name, number = it.number.toString(), numberSort = it.number.toFloat(), bookId = it.id)`
8. 事务结束后逐本发布 `DomainEvent.BookAdded(book)`。
9. 后续会进入 `sortBooks`，重新计算书籍顺序和元数据编号。
10. 需要时再由 `TaskEmitter` 触发 series 元数据刷新、书籍元数据刷新等异步任务。

以 `sortBooks(series)` 为例，它的逻辑比较关键：

1. 查询该 series 下所有 books。
2. 查询这些 books 对应的 metadata。
3. 按 `book.name` 排序，排序前做：
   - `trim()`
   - `stripAccents()`
   - 连续空白替换成单个空格
   - 使用自然排序 comparator
4. 按排序结果更新 `Book.number`，从 `1` 开始。
5. 对应的 `BookMetadata` 如果没有锁定编号字段，则更新：
   - `number`
   - `numberSort`
6. 如果 metadata 编号发生变化，调用 `taskEmitter.refreshBookMetadata(book, setOf(NUMBER, NUMBER_SORT))`。
7. 最后更新 series 的 `bookCount`。

这里有一个容易忽略的点：`Book.number` 总是会按排序结果更新，但 `BookMetadata.number` 和 `BookMetadata.numberSort` 会尊重 `numberLock`、`numberSortLock`。也就是说用户或外部元数据锁定的字段不会被自动排序覆盖。

以获取封面 `getThumbnailBytes(seriesId, userId)` 为例：

1. 先调用 `getSelectedThumbnail(seriesId)` 查找显式选中的 series 封面。
2. 如果找到，则读取 thumbnail 字节：
   - `thumbnail.thumbnail != null` 时直接返回数据库里的字节。
   - `thumbnail.url != null` 时从文件路径读取。
3. 如果没有选中封面，则读取 series 和 library。
4. 根据 `library.seriesCover` 决定用哪本书的封面：
   - `FIRST`
   - `FIRST_UNREAD_OR_FIRST`
   - `FIRST_UNREAD_OR_LAST`
   - `LAST`
5. 找到 book id 后委托 `bookLifecycle.getThumbnailBytes(bookId)`。
6. 如果所有路径都失败，返回 `null`。

以删除文件 `deleteSeriesFiles(series)` 为例：

1. 如果 series 路径不存在，记录日志后返回。
2. 如果 series 路径不可写，记录日志后返回。
3. 查询该 series 的 `SIDECAR` 类型 thumbnails，筛出真实存在且可写的文件。
4. 遍历 series 下所有 books，调用 `bookLifecycle.deleteBookFiles(it)`。
5. 删除 sidecar thumbnail 文件。
6. 如果 series 文件夹存在且已经为空，则删除文件夹。
7. 文件夹删除成功后写入 `HistoricalEvent.SeriesFolderDeleted`。
8. 最后调用 `softDeleteMany(listOf(series))`，把 series 和 books 标记为软删除。

## 小白阅读顺序

建议按下面顺序读：

1. 先看构造函数注入项  
   这能快速判断这个类影响哪些数据表和领域对象。重点看 `SeriesRepository`、`BookRepository`、`BookLifecycle`、`ThumbnailSeriesRepository`、`TaskEmitter`、`ApplicationEventPublisher`。

2. 再看 `createSeries` 和 `addBooks`  
   这两个方法最容易理解，展示了 series 创建时需要配套创建哪些关联数据。

3. 接着看 `sortBooks`  
   这是文件中业务密度最高的方法，涉及自然排序、编号同步、metadata lock、任务触发和 series 书籍数量更新。

4. 然后看 `deleteMany`、`softDeleteMany`、`deleteSeriesFiles`  
   这三者能帮助理解 Komga 对“删除”的区分：数据库硬删、软删除、文件系统删除不是一回事。

5. 再看阅读进度方法  
   `markReadProgressCompleted` 和 `deleteReadProgress` 比较独立，适合理解 user + series + book progress 的关系。

6. 最后看 thumbnail 相关方法  
   `getThumbnailBytes`、`addThumbnailForSeries`、`thumbnailsHouseKeeping` 需要结合 `Library.SeriesCover`、`ThumbnailSeries.Type`、sidecar 文件概念一起读。

如果要继续追上下文，优先看这些文件：

- `komga/src/main/kotlin/org/gotson/komga/domain/service/LibraryContentLifecycle.kt`
- `komga/src/main/kotlin/org/gotson/komga/domain/service/BookLifecycle.kt`
- `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskHandler.kt`
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/SeriesController.kt`
- `komga/src/main/kotlin/org/gotson/komga/domain/model/Series.kt`
- `komga/src/main/kotlin/org/gotson/komga/domain/model/ThumbnailSeries.kt`

## 常见误区

1. **误以为 `SeriesLifecycle` 只是 `SeriesRepository` 的包装**

   不是。它会同时操作 series、book、media、metadata、thumbnail、read progress、collection、historical event，并发布事件、触发任务。它是领域用例编排层。

2. **误以为 `sortBooks` 只改显示顺序**

   `sortBooks` 不只更新 `Book.number`，还会在 metadata 未锁定时更新 `BookMetadata.number` 和 `BookMetadata.numberSort`，并可能触发书籍元数据刷新任务。

3. **误以为删除 series 一定会删除文件**

   `deleteMany` 是数据库层面的硬删除关联数据；`softDeleteMany` 是标记软删除；`deleteSeriesFiles` 才涉及真实文件系统删除，并且删除后调用软删除。三者语义不同。

4. **误以为 `deleteSeriesFiles` 总会删除 series 文件夹**

   它只有在路径存在、可写，并且删除书籍文件和 sidecar 后目录为空时，才会删除 series 文件夹。否则只会做能做的部分并记录日志。

5. **误以为 series 封面一定来自 `ThumbnailSeries`**

   `getThumbnailBytes` 会优先使用选中的 `ThumbnailSeries`，但如果没有，则根据 library 的 `seriesCover` 策略回退到某本 book 的封面。

6. **误以为 thumbnail housekeeping 是定时全局清理**

   在当前文件中，`thumbnailsHouseKeeping(seriesId)` 是被 `getSelectedThumbnail` 触发的局部修复逻辑。它会清理不存在的封面记录，并修正“多个 selected”或“没有 selected”的状态。

7. **误以为阅读进度是 series 表上的字段**

   `markReadProgressCompleted` 和 `deleteReadProgress` 都是先找到 series 下的 book ids，再对每本书的 `ReadProgress` 操作。series 级阅读进度是由 book 级进度聚合出来的操作视角。

8. **误以为所有写操作都在事务中**

   多表创建和删除多数使用 `transactionTemplate.executeWithoutResult` 包住，例如 `createSeries`、`addBooks`、`deleteMany`。但一些方法如 `sortBooks`、thumbnail 操作、阅读进度操作并没有显式整体事务包裹。根据当前片段推断，这些操作依赖各 Repository 方法自身的事务或接受分步更新语义；依据是该文件中只有部分方法显式使用 `TransactionTemplate`。
