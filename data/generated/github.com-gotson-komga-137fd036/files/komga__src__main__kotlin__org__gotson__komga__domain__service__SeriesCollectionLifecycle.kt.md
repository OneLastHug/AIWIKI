# 文件：komga/src/main/kotlin/org/gotson/komga/domain/service/SeriesCollectionLifecycle.kt

## 它负责什么

`SeriesCollectionLifecycle.kt` 定义了领域服务 `SeriesCollectionLifecycle`，负责“系列集合”的生命周期操作。这里的 `SeriesCollection` 可以理解为一组 `Series` 的集合，类似用户或元数据驱动的“合集”。

它主要处理四类事情：

1. 集合本身的增删改：
   - 创建 collection
   - 更新 collection
   - 删除 collection
   - 自动创建 collection 并把 series 加进去
   - 删除空 collection

2. collection poster，也就是集合封面缩略图：
   - 添加用户上传的 collection 缩略图
   - 标记某张缩略图为选中
   - 删除缩略图
   - 删除后自动修复选中状态

3. collection 缩略图兜底生成：
   - 如果用户没有选中封面，则取集合中若干 series 的封面
   - 交给 `MosaicGenerator` 生成拼图封面

4. 发布领域事件：
   - `DomainEvent.CollectionAdded`
   - `DomainEvent.CollectionUpdated`
   - `DomainEvent.CollectionDeleted`
   - `DomainEvent.ThumbnailSeriesCollectionAdded`
   - `DomainEvent.ThumbnailSeriesCollectionDeleted`

这个文件不直接处理 HTTP 请求，也不直接写 SQL。它位于 domain service 层，作为 REST controller、元数据刷新流程、库扫描清理流程和 persistence repository 之间的业务编排层。

## 关键组成

### `SeriesCollectionLifecycle`

类声明：

```kotlin
@Service
class SeriesCollectionLifecycle(...)
```

它是 Spring 管理的服务类，通过构造函数注入依赖：

- `SeriesCollectionRepository`
  - 负责 collection 的持久化读写。
  - 目标文件中通过它执行 `insert`、`update`、`delete`、`findByIdOrNull`、`findByNameOrNull`、`existsByName`、`findAllEmpty` 等操作。

- `ThumbnailSeriesCollectionRepository`
  - 负责 collection 缩略图的持久化读写。
  - 目标文件中通过它查找选中缩略图、插入用户上传缩略图、删除缩略图、批量删除缩略图、标记选中缩略图。

- `SeriesLifecycle`
  - 用来获取单个 `Series` 的缩略图字节。
  - 在 collection 没有选中封面时，`SeriesCollectionLifecycle` 会调用 `seriesLifecycle.getThumbnailBytes(seriesId, userId)` 来取 series 封面，再生成合集拼图。

- `MosaicGenerator`
  - 用若干图片生成拼图封面。
  - 在 collection 没有用户选择的 poster 时作为兜底封面生成器。

- `ApplicationEventPublisher`
  - Spring 事件发布器。
  - 用于发布 `DomainEvent`，通知搜索索引、缓存、前端订阅或其他监听者。

- `TransactionTemplate`
  - 编程式事务工具。
  - 用于删除 collection 和删除空 collection 这类包含多个 repository 操作的流程。

### `addCollection(collection: SeriesCollection)`

职责：新增 collection。

核心逻辑：

1. 打日志。
2. 检查 collection 名称是否已存在：

```kotlin
if (collectionRepository.existsByName(collection.name))
  throw DuplicateNameException("Collection name already exists")
```

3. 插入 collection。
4. 发布 `DomainEvent.CollectionAdded(collection)`。
5. 重新从 repository 读取并返回 collection：

```kotlin
return collectionRepository.findByIdOrNull(collection.id)!!
```

注意点：

- 方法带有 `@Transactional`。
- 会抛出 `DuplicateNameException`。
- 返回的是重新查询后的对象，而不是直接返回传入参数。根据当前片段推断，这可能是为了拿到 DAO 层补齐或规范化后的字段，比如审计时间、排序关联等。

### `updateCollection(toUpdate: SeriesCollection)`

职责：更新已有 collection。

核心逻辑：

1. 根据 `toUpdate.id` 查找已有 collection。
2. 如果不存在，抛出：

```kotlin
IllegalArgumentException("Cannot update collection that does not exist")
```

3. 如果名称发生变化，并且新名称已存在，则抛出 `DuplicateNameException`。
4. 调用 `collectionRepository.update(toUpdate)`。
5. 发布 `DomainEvent.CollectionUpdated(toUpdate)`。

名称重复判断有一个细节：

```kotlin
if (!existing.name.equals(toUpdate.name, true) && collectionRepository.existsByName(toUpdate.name))
```

这里 `equals(..., true)` 表示忽略大小写比较。也就是说，如果只是大小写变化，例如 `Marvel` 改成 `marvel`，不会触发重复名称检查；如果改成另一个已存在的名称，则会抛异常。

### `deleteCollection(collection: SeriesCollection)`

职责：删除一个 collection 及其缩略图。

核心逻辑：

```kotlin
transactionTemplate.executeWithoutResult {
  thumbnailSeriesCollectionRepository.deleteByCollectionId(collection.id)
  collectionRepository.delete(collection.id)
}
eventPublisher.publishEvent(DomainEvent.CollectionDeleted(collection))
```

它先在事务里删除 collection 的所有 poster，再删除 collection 本身。事务完成后发布 `CollectionDeleted` 事件。

注意：这里没有 `@Transactional` 注解，而是显式使用 `TransactionTemplate`。这说明作者希望把“删缩略图 + 删 collection”包成一个明确的事务块。

### `addSeriesToCollection(collectionName: String, series: Series)`

职责：根据 collection 名称把某个 series 加入 collection。如果 collection 不存在，则自动创建。

这是元数据导入相关流程会用到的方法。

逻辑分两种情况：

1. collection 已存在：
   - 如果 `existing.seriesIds` 已经包含 `series.id`，只打 debug 日志，不重复添加。
   - 否则创建一个 copy，把 `series.id` 追加到 `seriesIds`，再调用 `updateCollection`。

```kotlin
existing.copy(seriesIds = existing.seriesIds + series.id)
```

2. collection 不存在：
   - 创建新的 `SeriesCollection`。
   - 名称为 `collectionName`。
   - `seriesIds` 初始只包含当前 `series.id`。
   - 调用 `addCollection`。

这个方法本身有 `@Transactional`，内部调用了同类的 `addCollection` / `updateCollection`。在 Kotlin/Spring 中，同类内部方法调用不会经过 Spring AOP 代理，但因为外层方法已经有事务，这里仍然有事务上下文。需要注意的是，内部方法上的额外 AOP 语义不会因为自调用重新生效。

### `deleteEmptyCollections()`

职责：删除所有空 collection。

核心逻辑：

1. 调用 `collectionRepository.findAllEmpty()` 找出空 collection。
2. 在事务内：
   - 批量删除这些 collection 的缩略图。
   - 批量删除这些 collection。
3. 对每个被删除的 collection 发布 `DomainEvent.CollectionDeleted`。

调用方在 `LibraryContentLifecycle.cleanupEmptySets()` 中。当设置项 `komgaSettingsProvider.deleteEmptyCollections` 为 true 时，库扫描或清理之后会自动删除空 collection。

### `addThumbnail(thumbnail: ThumbnailSeriesCollection)`

职责：添加 collection poster。

当前代码只处理一种类型：

```kotlin
ThumbnailSeriesCollection.Type.USER_UPLOADED
```

逻辑：

1. 如果是 `USER_UPLOADED`：
   - 插入 thumbnail。
   - 如果 `thumbnail.selected == true`，调用 `markSelected(thumbnail)` 标记为选中。
2. 发布 `DomainEvent.ThumbnailSeriesCollectionAdded(thumbnail)`。
3. 返回 thumbnail。

根据当前片段推断，`ThumbnailSeriesCollection` 目前至少支持用户上传类型；如果未来扩展 generated 类型，这里的 `when` 需要增加分支。

### `markSelectedThumbnail(thumbnail: ThumbnailSeriesCollection)`

职责：把某张 collection 缩略图设为选中。

逻辑：

```kotlin
thumbnailSeriesCollectionRepository.markSelected(thumbnail)
eventPublisher.publishEvent(DomainEvent.ThumbnailSeriesCollectionAdded(thumbnail.copy(selected = true)))
```

这里事件名是 `ThumbnailSeriesCollectionAdded`，不是 `Updated`。从 `DomainEvent.kt` 看，collection thumbnail 只有 `Added` 和 `Deleted` 两类事件，没有专门的 updated 事件。因此“标记选中”也复用 added 事件通知外部刷新。

### `deleteThumbnail(thumbnail: ThumbnailSeriesCollection)`

职责：删除某张 collection 缩略图。

逻辑：

1. 删除 thumbnail。
2. 调用 `thumbnailsHouseKeeping(thumbnail.collectionId)` 修复选中状态。
3. 发布 `DomainEvent.ThumbnailSeriesCollectionDeleted(thumbnail)`。

这里的 housekeeping 很关键：如果删除的是当前选中的 poster，系统需要尽量保证剩余 poster 中仍有一个被选中。

### `getThumbnailBytes(thumbnailId: String)`

职责：按 thumbnail id 直接取二进制图片。

```kotlin
fun getThumbnailBytes(thumbnailId: String): ByteArray? =
  thumbnailSeriesCollectionRepository.findByIdOrNull(thumbnailId)?.thumbnail
```

这是给类似 `GET /api/v1/collections/{id}/thumbnails/{thumbnailId}` 这种接口用的。

注意：这个方法只根据 thumbnail id 查图。调用方需要先确保用户对 collection 有访问权限。`SeriesCollectionController.getCollectionThumbnailById()` 先通过 `collectionRepository.findByIdOrNull(id, authorizedLibraryIds, restrictions)` 验证 collection 可见，再调用该方法。

### `getThumbnailBytes(collection: SeriesCollection, userId: String)`

职责：获取 collection 的最终展示封面。

流程：

1. 优先查找 collection 已选中的用户上传 poster：

```kotlin
thumbnailSeriesCollectionRepository.findSelectedByCollectionIdOrNull(collection.id)?.let {
  return it.thumbnail
}
```

2. 如果没有选中 poster，则从 collection 的 `seriesIds` 中取最多 4 个 id，并重复补足到 4 个。

```kotlin
val ids =
  with(mutableListOf<String>()) {
    while (size < 4) {
      this += collection.seriesIds.take(4)
    }
    this.take(4)
  }
```

比如：

- `seriesIds = [A, B, C, D, E]`，最终取 `[A, B, C, D]`
- `seriesIds = [A, B]`，最终取 `[A, B, A, B]`
- `seriesIds = [A]`，最终取 `[A, A, A, A]`

3. 对这些 series id 调用：

```kotlin
seriesLifecycle.getThumbnailBytes(it, userId)
```

4. 过滤掉拿不到的图片：

```kotlin
mapNotNull
```

5. 调用 `mosaicGenerator.createMosaic(images)` 生成拼图封面。

需要特别注意：如果 `collection.seriesIds` 是空列表，`while (size < 4)` 中每次追加的都是空列表，`size` 永远不会增加，会形成无限循环。目标文件没有在这里做空 collection 防护。根据当前片段推断，正常接口路径可能不会对空 collection 请求缩略图，或者上游通过删除空 collection / 数据约束降低出现概率；但从单函数角度看，这是一个需要阅读者警惕的边界条件。

### `thumbnailsHouseKeeping(collectionId: String)`

职责：维护 collection thumbnail 的选中状态。

逻辑：

1. 查出 collection 下所有 thumbnail。
2. 找出 `selected == true` 的项。
3. 如果选中的数量大于 1：
   - 调用 `markSelected(selected[0])`，保留第一个为选中。
4. 如果没有任何选中项，但还有 thumbnail：
   - 调用 `markSelected(all.first())`，自动选择第一张。

这个方法是 `private`，只在 `deleteThumbnail` 之后调用。它不会在添加 thumbnail 后统一清理，因为添加时如果 `selected == true`，repository 的 `markSelected` 应该会负责取消其他选中项。这个行为需要结合具体 DAO 实现才能完全确认。

## 上下游关系

### 上游调用方

主要上游有三类。

第一类是 REST API：`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/SeriesCollectionController.kt`。

它把 HTTP 请求转成领域服务调用：

- `POST /api/v1/collections`
  - 调用 `collectionLifecycle.addCollection(...)`
  - 用于创建 collection。

- `PATCH /api/v1/collections/{id}`
  - 先查已有 collection。
  - 根据 `CollectionUpdateDto` 复制出新对象。
  - 调用 `collectionLifecycle.updateCollection(updated)`。

- `DELETE /api/v1/collections/{id}`
  - 先查 collection。
  - 调用 `collectionLifecycle.deleteCollection(it)`。

- `GET /api/v1/collections/{id}/thumbnail`
  - 查 collection 并做权限过滤。
  - 调用 `collectionLifecycle.getThumbnailBytes(collection, principal.user.id)`。

- `POST /api/v1/collections/{id}/thumbnails`
  - 接收 multipart 图片。
  - 用 `ContentDetector` 判断是不是图片。
  - 用 `ImageAnalyzer` 获取尺寸。
  - 构造 `ThumbnailSeriesCollection`。
  - 调用 `collectionLifecycle.addThumbnail(...)`。

- `PUT /api/v1/collections/{id}/thumbnails/{thumbnailId}/selected`
  - 调用 `collectionLifecycle.markSelectedThumbnail(it)`。

- `DELETE /api/v1/collections/{id}/thumbnails/{thumbnailId}`
  - 调用 `collectionLifecycle.deleteThumbnail(it)`。

第二类是元数据刷新流程：`komga/src/main/kotlin/org/gotson/komga/domain/service/SeriesMetadataLifecycle.kt`。

在 `refreshMetadata(series)` 中，如果某个 metadata provider 支持处理 `MetadataPatchTarget.COLLECTION`，代码会从 book 中提取 collection 名称：

```kotlin
patches.flatMap { it.collections }.distinct().forEach { collection ->
  collectionLifecycle.addSeriesToCollection(collection, series)
}
```

也就是说，ComicInfo 或其他元数据中的 collections 字段可以自动创建 collection，并把当前 series 加进去。

第三类是库内容清理流程：`komga/src/main/kotlin/org/gotson/komga/domain/service/LibraryContentLifecycle.kt`。

在 `cleanupEmptySets()` 中：

```kotlin
if (komgaSettingsProvider.deleteEmptyCollections) {
  collectionLifecycle.deleteEmptyCollections()
}
```

如果设置开启，扫描/清理后会删除空 collection。这个逻辑和 `ReadListLifecycle.deleteEmptyReadLists()` 是并行概念。

### 下游依赖

`SeriesCollectionLifecycle` 的下游主要是 repository、图片生成器、领域事件系统。

- `SeriesCollectionRepository`
  - 定义在 `komga/src/main/kotlin/org/gotson/komga/domain/persistence/SeriesCollectionRepository.kt`。
  - 提供 collection 查询、插入、更新、删除、按名称查找、查空 collection、按名称判重等能力。

- `ThumbnailSeriesCollectionRepository`
  - 定义在 `komga/src/main/kotlin/org/gotson/komga/domain/persistence/ThumbnailSeriesCollectionRepository.kt`。
  - 提供 collection poster 的查询、插入、删除、批量删除、选中状态维护。

- `SeriesLifecycle`
  - `SeriesCollectionLifecycle` 不自己知道如何生成 series 封面，而是委托给 `SeriesLifecycle.getThumbnailBytes(seriesId, userId)`。

- `MosaicGenerator`
  - 接收若干图片字节，返回拼图封面字节。
  - 它把“没有用户上传 collection poster 时如何展示合集封面”这件事抽象出去。

- `ApplicationEventPublisher`
  - 发布 `DomainEvent`。
  - 从 `DomainEvent.kt` 可见，collection 相关事件包括 `CollectionAdded`、`CollectionUpdated`、`CollectionDeleted`、`ThumbnailSeriesCollectionAdded`、`ThumbnailSeriesCollectionDeleted`。
  - 搜索索引等组件会监听这些事件，例如 `SearchIndexLifecycle` 中会处理 `DomainEvent.CollectionAdded`。

### 相关模型

`SeriesCollection` 定义在 `komga/src/main/kotlin/org/gotson/komga/domain/model/SeriesCollection.kt`：

```kotlin
data class SeriesCollection(
  val name: String,
  val ordered: Boolean = false,
  val seriesIds: List<String> = emptyList(),
  val id: String = TsidCreator.getTsid256().toString(),
  override val createdDate: LocalDateTime = LocalDateTime.now(),
  override val lastModifiedDate: LocalDateTime = createdDate,
  val filtered: Boolean = false,
) : Auditable
```

关键字段：

- `name`
  - collection 名称。
  - 在新增和改名时会做重复检查。

- `ordered`
  - 表示 collection 是否手动排序。
  - REST controller 在查询 collection 内 series 时会根据它决定排序字段：
    - `ordered == true`：按 `collection.number`
    - `ordered == false`：按 `metadata.titleSort`

- `seriesIds`
  - collection 包含的 series id 列表。
  - `addSeriesToCollection` 会向这里追加 series id。
  - `getThumbnailBytes(collection, userId)` 会从这里取 series 封面生成拼图。

- `filtered`
  - 注释说明：表示 `seriesIds` 被过滤过，并不完整。
  - 这通常和权限过滤或库过滤有关。根据 repository 接口注释，`findByIdOrNull` 和 `findAll` 可以按 library/restrictions 过滤 collection 中的 series id。

## 运行/调用流程

### 创建 collection

典型流程：

1. 管理员调用 REST API 创建 collection。
2. `SeriesCollectionController.createCollection()` 把请求 DTO 转成 `SeriesCollection`。
3. 调用 `SeriesCollectionLifecycle.addCollection()`。
4. lifecycle 检查名称重复。
5. repository 插入 collection。
6. 发布 `DomainEvent.CollectionAdded`。
7. 重新查询 collection 并返回。
8. controller 转成 `CollectionDto` 返回给客户端。

如果名称重复，`addCollection` 抛出 `DuplicateNameException`，controller 捕获后转成 HTTP 400。

### 更新 collection

典型流程：

1. 管理员调用 PATCH API。
2. controller 先用 repository 查出已有 collection。
3. 用请求中的可选字段覆盖已有对象：
   - `name`
   - `ordered`
   - `seriesIds`
4. 调用 `SeriesCollectionLifecycle.updateCollection(updated)`。
5. lifecycle 校验 collection 是否存在。
6. 如果改名且新名称重复，抛出 `DuplicateNameException`。
7. repository 更新 collection。
8. 发布 `DomainEvent.CollectionUpdated`。

### 删除 collection

典型流程：

1. 管理员调用 DELETE API。
2. controller 查出 collection。
3. 调用 `SeriesCollectionLifecycle.deleteCollection(collection)`。
4. lifecycle 在事务里先删 poster，再删 collection。
5. 事务结束后发布 `DomainEvent.CollectionDeleted`。

这里先删缩略图再删 collection，是为了避免 collection 删除后留下孤立 poster 数据。

### 元数据自动加入 collection

典型流程：

1. 库扫描或文件变化后触发 series metadata refresh。
2. `SeriesMetadataLifecycle.refreshMetadata(series)` 从书籍元数据中提取 collection 名称。
3. 对每个 collection 名称调用：

```kotlin
collectionLifecycle.addSeriesToCollection(collection, series)
```

4. 如果 collection 已存在：
   - 已包含该 series：什么都不做。
   - 未包含该 series：追加 series id 并更新 collection。
5. 如果 collection 不存在：
   - 自动创建 collection。
   - 初始包含当前 series。

这解释了为什么 `SeriesCollectionLifecycle` 里有一个“按名称添加 series”的方法，而不是只提供显式的 create/update：collection 不一定只由用户手动维护，也可以从元数据自动产生。

### 获取 collection 封面

典型流程：

1. 客户端请求 `GET /api/v1/collections/{id}/thumbnail`。
2. controller 按用户权限查 collection。
3. 调用 `collectionLifecycle.getThumbnailBytes(collection, userId)`。
4. lifecycle 先找选中的用户上传 poster。
5. 如果有，直接返回该图片。
6. 如果没有，从 collection 的 series 中取最多 4 个 series id。
7. 逐个取 series 封面。
8. 调用 `MosaicGenerator.createMosaic(images)` 生成拼图。
9. controller 以 `image/jpeg` 返回。

### 添加 collection poster

典型流程：

1. 管理员上传图片。
2. controller 用 `ContentDetector` 检查 media type。
3. 如果不是图片，返回 HTTP 415。
4. controller 用 `ImageAnalyzer` 读取尺寸。
5. 构造 `ThumbnailSeriesCollection`，类型为 `USER_UPLOADED`。
6. 调用 `collectionLifecycle.addThumbnail(thumbnail)`。
7. lifecycle 插入 thumbnail。
8. 如果请求参数 `selected == true`，标记为选中。
9. 发布 `ThumbnailSeriesCollectionAdded`。

### 删除 collection poster

典型流程：

1. 管理员删除某张 poster。
2. controller 查 collection 和 thumbnail。
3. 调用 `collectionLifecycle.deleteThumbnail(thumbnail)`。
4. lifecycle 删除 thumbnail。
5. 调用 `thumbnailsHouseKeeping(collectionId)`。
6. 如果剩余 poster 中没有选中项，自动选择第一张。
7. 如果剩余 poster 中有多个选中项，保留第一个。
8. 发布 `ThumbnailSeriesCollectionDeleted`。

## 小白阅读顺序

1. 先读 `SeriesCollection.kt`
   - 理解 `SeriesCollection` 是什么。
   - 重点看 `name`、`ordered`、`seriesIds`、`filtered`。
   - 明白 collection 本质上是一个带名称的 series id 列表。

2. 再读 `SeriesCollectionRepository.kt`
   - 看 domain service 能对 collection 做哪些持久化操作。
   - 重点看 `findByIdOrNull` 的过滤参数、`findAllEmpty`、`findByNameOrNull`、`existsByName`、`delete`。

3. 再读目标文件 `SeriesCollectionLifecycle.kt`
   - 先看构造函数依赖。
   - 再按方法顺序读：
     - `addCollection`
     - `updateCollection`
     - `deleteCollection`
     - `addSeriesToCollection`
     - `deleteEmptyCollections`
     - thumbnail 相关方法
     - `getThumbnailBytes`
     - `thumbnailsHouseKeeping`

4. 然后读 `SeriesCollectionController.kt`
   - 目的是理解这些 lifecycle 方法如何暴露成 REST API。
   - 重点看 create、update、delete、thumbnail 上传、thumbnail 选择、thumbnail 删除。

5. 再读 `SeriesMetadataLifecycle.kt`
   - 重点看 `refreshMetadata(series)` 中 `collectionLifecycle.addSeriesToCollection(collection, series)` 的调用。
   - 这能帮助理解 collection 为什么会被自动创建。

6. 最后读 `LibraryContentLifecycle.kt`
   - 重点看 `cleanupEmptySets()`。
   - 理解空 collection 的自动清理是扫描/清理流程的一部分，并受 `komgaSettingsProvider.deleteEmptyCollections` 控制。

如果想对照类似实现，可以读 `ReadListLifecycle.kt`。它和 `SeriesCollectionLifecycle` 结构非常相似：read list 对应 book 列表，collection 对应 series 列表；两者都有新增、更新、删除、删除空集合、缩略图上传、选中 poster、拼图封面生成等逻辑。

## 常见误区

1. 误以为 `SeriesCollectionLifecycle` 是 API controller。

它不是 controller，不处理路由、HTTP 状态码、权限注解或 multipart 解析。HTTP 层在 `SeriesCollectionController.kt`，目标文件是 domain service，负责业务规则和事件发布。

2. 误以为 collection 只能由用户手动创建。

不是。`SeriesMetadataLifecycle` 会根据元数据中的 collections 字段调用 `addSeriesToCollection`，自动创建 collection 或把 series 加入已有 collection。

3. 误以为删除 collection 只删 collection 表记录。

实际删除时还会先删 collection 关联的 thumbnails：

```kotlin
thumbnailSeriesCollectionRepository.deleteByCollectionId(collection.id)
collectionRepository.delete(collection.id)
```

这两个操作在同一个 `TransactionTemplate` 事务块里。

4. 误以为 collection poster 一定来自用户上传。

不是。优先使用选中的用户上传 poster；如果没有，`getThumbnailBytes(collection, userId)` 会从 collection 内的 series 封面生成 mosaic 拼图。

5. 误以为 `markSelectedThumbnail` 会发布 “updated” 事件。

`DomainEvent.kt` 中没有 `ThumbnailSeriesCollectionUpdated`。标记选中时复用的是：

```kotlin
DomainEvent.ThumbnailSeriesCollectionAdded(thumbnail.copy(selected = true))
```

因此事件名里的 `Added` 在这里更像“thumbnail 相关状态需要刷新”的通知，而不只是新增。

6. 误以为 collection 名称重复检查完全大小写敏感。

更新时判断当前名称是否变化使用了忽略大小写比较：

```kotlin
existing.name.equals(toUpdate.name, true)
```

所以只改大小写不会触发 `existsByName` 检查。但新增时直接调用 `existsByName(collection.name)`，是否大小写敏感取决于 repository/数据库实现，单看当前文件无法完全确定。

7. 误以为 `getThumbnailBytes(collection, userId)` 对空 collection 安全。

这个方法在没有选中 poster 时，会用 `while (size < 4)` 重复填充 `collection.seriesIds.take(4)`。如果 `seriesIds` 为空，循环无法增长，存在无限循环风险。根据当前片段推断，作者可能假设调用该方法时 collection 非空，或者依赖空 collection 清理流程降低概率；但目标文件本身没有显式防护。

8. 误以为 `addThumbnail` 会处理所有 thumbnail 类型。

当前 `when` 只处理 `ThumbnailSeriesCollection.Type.USER_UPLOADED`。如果模型将来增加其他类型，需要回到这里补逻辑。否则新增类型可能只发布事件，不会真正插入 repository，具体还要看 Kotlin `when` 是否因 enum/sealed 类型变更触发编译检查。

9. 误以为 controller 里的事件发布都在 lifecycle 之外。

大多数 collection 相关事件由 lifecycle 发布。但在 `SeriesCollectionController.markCollectionThumbnailSelected()` 中，controller 调用 `collectionLifecycle.markSelectedThumbnail(it)` 后，又手动发布了一次 `DomainEvent.ThumbnailSeriesCollectionAdded(it.copy(selected = true))`。而 lifecycle 方法内部已经发布同类事件。根据当前片段判断，这里可能导致重复事件通知；是否有意为之需要结合事件监听方行为进一步确认。
