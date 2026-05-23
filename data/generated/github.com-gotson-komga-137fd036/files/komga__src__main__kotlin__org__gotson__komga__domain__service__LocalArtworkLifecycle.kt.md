# 文件：komga/src/main/kotlin/org/gotson/komga/domain/service/LocalArtworkLifecycle.kt

## 它负责什么

`LocalArtworkLifecycle.kt` 定义了领域服务 `LocalArtworkLifecycle`，负责在后台任务要求“刷新本地封面/缩略图”时，把文件系统中的本地 artwork 导入到 Komga 的缩略图体系里。

这里的“本地 artwork”不是用户通过 API 上传的封面，也不是系统从书籍内容页生成的封面，而是放在书籍文件或系列目录旁边的 sidecar 图片文件。例如：

- 书籍旁边与书籍同名的图片，如 `Book.cbz` 对应 `Book.jpg`、`Book-1.png`
- 系列目录下的固定名称图片，如 `cover.jpg`、`folder.png`、`poster.webp`

这个类本身不负责扫描文件名、不负责判断图片格式、不负责解析尺寸，也不直接写数据库。它只做生命周期编排：

1. 根据 `Book` 或 `Series` 找到所属 `Library`
2. 检查该库是否开启 `importLocalArtwork`
3. 委托 `LocalArtworkProvider` 从文件系统发现本地缩略图
4. 委托 `BookLifecycle` 或 `SeriesLifecycle` 把缩略图加入系统
5. 根据 provider 标记的 `selected` 决定是否尝试选中该缩略图

可以把它理解成“本地 artwork 导入流程的领域层入口”。

## 关键组成

### `LocalArtworkLifecycle`

类声明：

```kotlin
@Service
class LocalArtworkLifecycle(
  private val libraryRepository: LibraryRepository,
  private val bookLifecycle: BookLifecycle,
  private val seriesLifecycle: SeriesLifecycle,
  private val localArtworkProvider: LocalArtworkProvider,
)
```

它是 Spring `@Service`，由容器注入依赖。依赖可以分成三类：

- `LibraryRepository`：读取书籍或系列所属的 `Library` 配置
- `BookLifecycle`、`SeriesLifecycle`：复用已有缩略图入库、选中、事件发布逻辑
- `LocalArtworkProvider`：实际从文件系统发现本地 artwork，并组装成 `ThumbnailBook` 或 `ThumbnailSeries`

### `refreshLocalArtwork(book: Book)`

这是书籍级本地 artwork 刷新入口。

核心逻辑：

```kotlin
fun refreshLocalArtwork(book: Book) {
  logger.info { "Refresh local artwork for book: $book" }
  val library = libraryRepository.findById(book.libraryId)

  if (library.importLocalArtwork)
    localArtworkProvider.getBookThumbnails(book).forEach {
      bookLifecycle.addThumbnailForBook(it, if (it.selected) MarkSelectedPreference.IF_NONE_OR_GENERATED else MarkSelectedPreference.NO)
    }
  else
    logger.info { "Library is not set to import local artwork, skipping" }
}
```

流程很短，但有几个关键点：

- 先通过 `book.libraryId` 找到库配置
- 只有 `library.importLocalArtwork == true` 才会继续导入
- `localArtworkProvider.getBookThumbnails(book)` 返回的是一组 `ThumbnailBook`
- 每个返回项都会交给 `bookLifecycle.addThumbnailForBook`
- 如果 provider 给出的缩略图 `it.selected == true`，则传入 `MarkSelectedPreference.IF_NONE_OR_GENERATED`
- 如果 `it.selected == false`，则传入 `MarkSelectedPreference.NO`

这里没有直接把 `selected = true` 写进数据库，而是把“是否允许选中”的策略交给 `BookLifecycle`。

### `refreshLocalArtwork(series: Series)`

这是系列级本地 artwork 刷新入口。

核心逻辑：

```kotlin
fun refreshLocalArtwork(series: Series) {
  logger.info { "Refresh local artwork for series: $series" }
  val library = libraryRepository.findById(series.libraryId)

  if (library.importLocalArtwork)
    localArtworkProvider.getSeriesThumbnails(series).forEach {
      seriesLifecycle.addThumbnailForSeries(it, if (it.selected) MarkSelectedPreference.IF_NONE_OR_GENERATED else MarkSelectedPreference.NO)
    }
  else
    logger.info { "Library is not set to import local artwork, skipping" }
}
```

它和书籍版本结构一致，只是类型从 `Book` 换成 `Series`，下游从 `BookLifecycle` 换成 `SeriesLifecycle`。

### `MarkSelectedPreference`

`LocalArtworkLifecycle` 使用的选择策略来自 `komga/src/main/kotlin/org/gotson/komga/domain/model/MarkSelectedPreference.kt`：

```kotlin
enum class MarkSelectedPreference {
  NO,
  YES,
  IF_NONE_OR_GENERATED,
}
```

在本文件中只用到两种：

- `IF_NONE_OR_GENERATED`：允许在特定条件下把新缩略图设为选中
- `NO`：只添加缩略图，不把它设为选中

对于书籍来说，`BookLifecycle.addThumbnailForBook` 中的 `IF_NONE_OR_GENERATED` 条件是：

- 当前没有选中的缩略图，或者
- 当前选中的缩略图类型是 `GENERATED`

这意味着本地 sidecar artwork 可以替代系统自动生成的封面，但不会轻易覆盖用户已有的非生成封面。

对于系列来说，`SeriesLifecycle.addThumbnailForSeries` 中的 `IF_NONE_OR_GENERATED` 条件更简单：

- 当前系列没有选中的缩略图

根据当前片段推断，系列缩略图没有像书籍那样区分“当前选中的是 generated”后再替换的逻辑，依据是 `SeriesLifecycle.addThumbnailForSeries` 中只检查 `findSelectedBySeriesIdOrNull(thumbnail.seriesId) == null`。

## 上下游关系

### 上游调用方

`LocalArtworkLifecycle` 的直接调用方在 `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskHandler.kt`。

相关任务分支包括：

```kotlin
is Task.RefreshBookLocalArtwork ->
  bookRepository.findByIdOrNull(task.bookId)?.let { book ->
    localArtworkLifecycle.refreshLocalArtwork(book)
  }

is Task.RefreshSeriesLocalArtwork ->
  seriesRepository.findByIdOrNull(task.seriesId)?.let { series ->
    localArtworkLifecycle.refreshLocalArtwork(series)
  }
```

也就是说，这个类通常不是被 REST Controller 直接调用，而是由后台任务系统触发。任务里只有 `bookId` 或 `seriesId`，`TaskHandler` 先从 repository 查出领域对象，再交给 `LocalArtworkLifecycle`。

上游链路大致是：

`Task.RefreshBookLocalArtwork` / `Task.RefreshSeriesLocalArtwork`
-> `TaskHandler`
-> `LocalArtworkLifecycle.refreshLocalArtwork(...)`

### 配置来源

是否导入本地 artwork 由 `Library.importLocalArtwork` 控制，定义在 `komga/src/main/kotlin/org/gotson/komga/domain/model/Library.kt`：

```kotlin
val importLocalArtwork: Boolean = true
```

默认值是 `true`。

REST 层也暴露了这个配置，例如：

- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/LibraryCreationDto.kt`
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/LibraryUpdateDto.kt`
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/LibraryController.kt`

这说明用户或 API 可以在库配置里关闭本地 artwork 导入。关闭后，本类会记录日志并跳过，不会调用 provider，也不会改动缩略图。

### 下游：`LocalArtworkProvider`

`LocalArtworkLifecycle` 不自己找文件，而是调用 `komga/src/main/kotlin/org/gotson/komga/infrastructure/metadata/localartwork/LocalArtworkProvider.kt`。

书籍本地缩略图查找逻辑：

```kotlin
fun getBookThumbnails(book: Book): List<ThumbnailBook>
```

它会：

- 获取 `book.path`
- 取书籍文件名去掉扩展名作为 `baseName`
- 在书籍所在目录 `bookPath.parent` 里列文件
- 匹配同名或 `同名-数字` 的图片文件
- 限制扩展名为 `png`、`jpeg`、`jpg`、`tbn`、`webp`、`gif`
- 通过 `ContentDetector` 确认媒体类型是图片
- 通过 `ImageAnalyzer` 获取尺寸
- 组装成 `ThumbnailBook(type = ThumbnailBook.Type.SIDECAR)`

书籍文件名匹配模式大致是：

```kotlin
"${Regex.escape(baseName)}(-\\d+)?"
```

所以如果书籍是 `Batman 001.cbz`，可能匹配：

- `Batman 001.jpg`
- `Batman 001-1.jpg`
- `Batman 001-2.png`

系列本地缩略图查找逻辑：

```kotlin
fun getSeriesThumbnails(series: Series): List<ThumbnailSeries>
```

它会：

- 如果 `series.oneshot == true`，直接返回空列表
- 在 `series.path` 目录下列文件
- 文件名必须是 `cover`、`default`、`folder`、`poster`、`series` 之一
- 扩展名必须是支持的图片扩展名
- 媒体类型必须确认为图片
- 组装成 `ThumbnailSeries(type = ThumbnailSeries.Type.SIDECAR)`

因此，`LocalArtworkLifecycle` 的“刷新”能力依赖 provider 对 sidecar 文件命名规则的实现。

### 下游：`BookLifecycle`

书籍缩略图最终通过 `BookLifecycle.addThumbnailForBook` 保存。

对于 `ThumbnailBook.Type.SIDECAR`，它会：

- 查找同一本书下已有的 sidecar 缩略图
- 如果已有缩略图的 `url` 与新缩略图相同，则删除旧记录
- 插入新的缩略图，插入时先把 `selected` 置为 `false`
- 根据 `MarkSelectedPreference` 决定是否 mark selected
- 如果没有选中，则执行 `thumbnailsHouseKeeping(bookId)`
- 发布 `DomainEvent.ThumbnailBookAdded`

这意味着刷新同一个本地 artwork 文件时，不是简单重复插入无限多条，而是会按相同 `url` 清理旧 sidecar 记录后再插入。

### 下游：`SeriesLifecycle`

系列缩略图最终通过 `SeriesLifecycle.addThumbnailForSeries` 保存。

它会：

- 如果新缩略图有 `url`，查找同一系列下相同 `url` 的缩略图并删除
- 插入新缩略图，插入时先把 `selected` 置为 `false`
- 根据 `MarkSelectedPreference` 决定是否 mark selected
- 发布 `DomainEvent.ThumbnailSeriesAdded`

和书籍类似，系列本地 artwork 刷新也会避免同一 URL 的 sidecar 记录重复堆积。

## 运行/调用流程

以书籍为例，完整流程可以这样理解：

1. 后台任务系统产生 `Task.RefreshBookLocalArtwork`
2. `TaskHandler` 根据 `task.bookId` 调用 `bookRepository.findByIdOrNull`
3. 如果书籍存在，调用 `localArtworkLifecycle.refreshLocalArtwork(book)`
4. `LocalArtworkLifecycle` 记录日志：开始刷新该书籍的 local artwork
5. 通过 `libraryRepository.findById(book.libraryId)` 找到所属库
6. 如果 `library.importLocalArtwork == false`，记录日志并结束
7. 如果开启导入，调用 `localArtworkProvider.getBookThumbnails(book)`
8. `LocalArtworkProvider` 到书籍文件所在目录查找匹配的 sidecar 图片
9. provider 把每个匹配文件包装为 `ThumbnailBook`
10. `LocalArtworkLifecycle` 遍历这些 `ThumbnailBook`
11. 对第一个 provider 标记为 `selected` 的缩略图，传入 `MarkSelectedPreference.IF_NONE_OR_GENERATED`
12. 对其他缩略图，传入 `MarkSelectedPreference.NO`
13. `BookLifecycle.addThumbnailForBook` 删除相同 URL 的旧 sidecar 缩略图
14. 插入新缩略图
15. 根据策略决定是否设为选中
16. 发布 `DomainEvent.ThumbnailBookAdded`

系列流程类似，只是任务、repository、provider 和 lifecycle 都换成系列版本：

`Task.RefreshSeriesLocalArtwork`
-> `TaskHandler`
-> `seriesRepository.findByIdOrNull`
-> `LocalArtworkLifecycle.refreshLocalArtwork(series)`
-> `Library.importLocalArtwork` 判断
-> `LocalArtworkProvider.getSeriesThumbnails(series)`
-> `SeriesLifecycle.addThumbnailForSeries`

需要注意，provider 中系列 artwork 对 `oneshot` 有特殊处理：

```kotlin
if (series.oneshot) {
  logger.debug { "Disabled for oneshot series, skipping" }
  return emptyList()
}
```

所以即使 `LocalArtworkLifecycle` 调用了 `getSeriesThumbnails(series)`，oneshot 系列也不会产生系列级本地缩略图。

## 小白阅读顺序

建议按下面顺序读源码：

1. 先读 `komga/src/main/kotlin/org/gotson/komga/domain/service/LocalArtworkLifecycle.kt`

   这个文件最短，能先建立主流程：查库配置、判断 `importLocalArtwork`、调用 provider、调用 lifecycle 保存。

2. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/model/Library.kt`

   重点看 `importLocalArtwork` 字段。它解释了为什么 `LocalArtworkLifecycle` 每次都要先查 `Library`，也说明这个行为是库级开关。

3. 再读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/metadata/localartwork/LocalArtworkProvider.kt`

   重点看两个方法：

   - `getBookThumbnails(book: Book)`
   - `getSeriesThumbnails(series: Series)`

   这里能看到真正的文件命名规则、支持的图片扩展名、sidecar 类型、尺寸分析等细节。

4. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/service/BookLifecycle.kt`

   重点看 `addThumbnailForBook`。这里解释为什么本文件只传 `MarkSelectedPreference`，不自己操作数据库和事件。

5. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/service/SeriesLifecycle.kt`

   重点看 `addThumbnailForSeries`。对比书籍逻辑，可以发现两者的选中策略略有差异。

6. 最后读 `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskHandler.kt`

   重点看 `Task.RefreshBookLocalArtwork` 和 `Task.RefreshSeriesLocalArtwork` 分支。这里能理解这个服务是被后台任务调用，而不是普通业务代码随时直接调用。

## 常见误区

### 误区一：以为 `LocalArtworkLifecycle` 会扫描文件系统

它不直接扫描。文件系统扫描发生在 `LocalArtworkProvider`。本类只是编排流程。

具体分工是：

- `LocalArtworkLifecycle`：判断是否允许导入，并组织调用
- `LocalArtworkProvider`：查找本地图片文件，构造 `ThumbnailBook` / `ThumbnailSeries`
- `BookLifecycle` / `SeriesLifecycle`：保存缩略图、处理选中状态、发布事件

### 误区二：以为 `selected = true` 一定会让缩略图变成当前封面

不一定。

`LocalArtworkProvider` 会用 `mapIndexed` 把第一个发现的 artwork 标记为 `selected = true`。但 `LocalArtworkLifecycle` 并不会直接信任这个字段写库，而是把它转换成 `MarkSelectedPreference.IF_NONE_OR_GENERATED`。

对于书籍，只有当前没有选中缩略图，或者当前选中的是自动生成缩略图时，本地 artwork 才会被设为选中。

对于系列，只有当前没有选中缩略图时，本地 artwork 才会被设为选中。

### 误区三：以为关闭 `importLocalArtwork` 会删除已有本地封面

不会。

`library.importLocalArtwork == false` 时，本类只是跳过刷新：

```kotlin
logger.info { "Library is not set to import local artwork, skipping" }
```

它不会删除已有缩略图，也不会触发 housekeeping。关闭这个配置的含义是“不再导入本地 artwork”，不是“清理已经导入的 artwork”。

### 误区四：以为书籍和系列 artwork 的命名规则一样

不一样。

书籍 artwork 是围绕书籍文件名匹配：

- `BookName.jpg`
- `BookName-1.jpg`
- `BookName-2.png`

系列 artwork 是固定文件名：

- `cover.jpg`
- `default.png`
- `folder.webp`
- `poster.jpg`
- `series.png`

这些规则在 `LocalArtworkProvider` 里，不在 `LocalArtworkLifecycle` 里。

### 误区五：以为所有系列都会导入系列级本地 artwork

不是。`LocalArtworkProvider.getSeriesThumbnails` 对 `series.oneshot` 做了跳过处理。oneshot 系列直接返回空列表。

所以从 `LocalArtworkLifecycle` 看，似乎所有 `Series` 都会尝试刷新；但根据当前片段可知，oneshot 系列在 provider 层被禁用。

### 误区六：以为刷新会产生重复的同 URL 缩略图

通常不会。

`BookLifecycle.addThumbnailForBook` 和 `SeriesLifecycle.addThumbnailForSeries` 都会在插入前删除相同 `url` 的旧记录。也就是说，同一个本地 sidecar 文件再次刷新时，会替换旧记录，而不是无限追加同一个 URL 的记录。

### 误区七：以为这个类处理用户上传封面

不处理。

用户上传封面通常是 `ThumbnailBook.Type.USER_UPLOADED` 或对应系列上传类型相关逻辑。`LocalArtworkLifecycle` 导入的是 provider 生成的 `SIDECAR` 类型缩略图，也就是本地伴随文件。
