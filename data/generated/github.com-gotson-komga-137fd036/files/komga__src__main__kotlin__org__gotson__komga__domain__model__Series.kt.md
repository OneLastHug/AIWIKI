# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/Series.kt

## 它负责什么

`Series.kt` 定义了 Komga 领域层里的 `Series` 模型，也就是“系列”这一核心业务实体。它代表一个漫画/书籍系列在系统中的基础身份、文件系统位置、所属库、书籍数量、删除状态和审计时间。

这个文件本身不包含复杂业务逻辑，重点是承载数据和提供一个从 `URL` 转换出的本地 `Path` 访问方式。可以把它理解为领域模型中的“系列主表对象”：扫描文件系统时会创建它，数据库读取时会还原它，服务层和接口层再围绕它做元数据、封面、书籍、阅读进度、删除等操作。

它和 `SeriesMetadata` 要区分开：

- `Series`：偏系统层和文件层，记录系列的目录/文件位置、ID、所属 library、删除状态、书籍数量等。
- `SeriesMetadata`：偏内容层，记录标题、简介、出版商、语言、标签、阅读方向、状态、锁定字段等用户可见或可编辑的元数据。

## 关键组成

### 包与 import

文件位于领域模型包：

`org.gotson.komga.domain.model`

它引入了这些依赖：

- `com.github.f4b6a3.tsid.TsidCreator`：用于生成默认 `id`。这里使用 `getTsid256().toString()`，说明 Komga 的实体 ID 不是数据库自增 ID，而是应用层生成的 TSID 字符串。
- `java.net.URL`：保存系列对应的文件 URL。
- `java.nio.file.Path`：提供本地文件系统路径类型。
- `java.time.LocalDateTime`：保存文件修改时间、删除时间、创建时间、更新时间。
- `kotlin.io.path.toPath`：把 `URI` 转成 `Path`。

### `data class Series`

核心定义如下：

```kotlin
data class Series(
  val name: String,
  val url: URL,
  val fileLastModified: LocalDateTime,
  val id: String = TsidCreator.getTsid256().toString(),
  val libraryId: String = "",
  val bookCount: Int = 0,
  val deletedDate: LocalDateTime? = null,
  val oneshot: Boolean = false,
  override val createdDate: LocalDateTime = LocalDateTime.now(),
  override val lastModifiedDate: LocalDateTime = createdDate,
) : Auditable
```

字段含义：

- `name`：系列名称。扫描目录时通常来自目录名；如果是 oneshot，则可能来自书籍名。
- `url`：系列在文件系统中的 URL。普通系列一般是目录 URL；oneshot 系列可能指向单本书文件 URL。
- `fileLastModified`：文件系统层面记录到的最后修改时间，用于判断扫描后是否需要更新。
- `id`：系列唯一 ID，默认由 `TsidCreator` 生成。
- `libraryId`：所属书库 ID。新扫描出来的临时对象初始为空，进入库内容生命周期流程后会绑定具体 library。
- `bookCount`：系列下书籍数量。领域对象保留这个统计值，数据库读取时会回填。
- `deletedDate`：软删除时间。为 `null` 表示未删除。
- `oneshot`：是否是单本作品模式。oneshot 不是普通“目录即系列”的结构，而是把单个书籍文件视为一个系列。
- `createdDate`：审计创建时间，来自 `Auditable`。
- `lastModifiedDate`：审计更新时间，默认等于 `createdDate`。

### `Auditable`

`Series` 实现了 `Auditable`，该接口只要求两个字段：

```kotlin
interface Auditable {
  val createdDate: LocalDateTime
  val lastModifiedDate: LocalDateTime
}
```

这说明 `Series` 需要参与统一的创建/更新时间管理。类似的 `Book`、`Library`、`SeriesMetadata` 也遵循同样风格。

### `path`

类体中只有一个派生属性：

```kotlin
@delegate:Transient
val path: Path by lazy { this.url.toURI().toPath() }
```

它的作用是把 `url` 转换为本地 `Path`，方便服务层直接操作文件系统。

这里有两个关键点：

- `by lazy`：只有第一次访问 `path` 时才执行转换，避免每次构造 `Series` 都立即转路径。
- `@delegate:Transient`：标记 lazy 委托字段不参与序列化/持久化。因为 `path` 可以由 `url` 推导出来，不应该作为独立状态保存。

## 上下游关系

### 上游：文件系统扫描创建 `Series`

`Series` 的主要创建入口之一在 `komga/src/main/kotlin/org/gotson/komga/domain/service/FileSystemScanner.kt`。

扫描目录时，`preVisitDirectory` 会为每个目录先创建一个临时 `Series`：

```kotlin
Series(
  name = dir.name.ifBlank { dir.pathString },
  url = dir.toUri().toURL(),
  fileLastModified = attrs.getUpdatedTime(),
)
```

也就是说，在普通模式下，一个目录天然会被视作候选系列。但它最终是否成为有效系列，要等 `postVisitDirectory` 确认该目录下存在可识别书籍文件。

当目录下有书籍时，扫描器会把 `Series` 和该目录下的 `Book` 列表放入结果：

```kotlin
scannedSeries[series] = books
```

如果配置了 oneshot 目录，并且当前目录路径命中 oneshot 规则，扫描器会为每本书单独创建一个 `Series`：

```kotlin
Series(
  name = book.name,
  url = book.url,
  fileLastModified = book.fileLastModified,
  oneshot = true,
)
```

这解释了为什么 `Series.url` 不一定永远指向目录：在 oneshot 场景中，它可以指向单个书籍文件。

### 同级模型：`Book`

`komga/src/main/kotlin/org/gotson/komga/domain/model/Book.kt` 和 `Series.kt` 很相似，也有：

- `name`
- `url`
- `fileLastModified`
- `id`
- `libraryId`
- `deletedDate`
- `oneshot`
- `createdDate`
- `lastModifiedDate`
- `path`

但 `Book` 额外包含书籍级字段：

- `fileSize`
- `fileHash`
- `fileHashKoreader`
- `number`
- `seriesId`

对应关系是：`Series` 是容器或聚合根级对象，`Book` 是属于某个系列的具体书籍文件。`Book.seriesId` 指向 `Series.id`。

### 同级模型：`Library`

`komga/src/main/kotlin/org/gotson/komga/domain/model/Library.kt` 代表书库根目录和扫描配置。它有 `root: URL` 和派生 `path: Path`，结构上和 `Series.url/path` 类似。

`Library` 的配置会影响 `Series` 的创建和后续处理，例如：

- `oneshotsDirectory`：决定是否把单本书当作独立系列。
- `scanForceModifiedTime`：影响扫描时 `Series.fileLastModified` 是否取目录和书籍中的最大修改时间。
- `seriesCover`：影响系列封面选择策略。
- `importComicInfoSeries`、`importEpubSeries`、`importMylarSeries` 等：影响系列元数据导入。

### 下游：数据库持久化

`komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/SeriesDao.kt` 负责把数据库记录转回领域对象。其 `SeriesRecord.toDomain()` 会填充：

```kotlin
Series(
  name = name,
  url = URL(url),
  fileLastModified = fileLastModified,
  id = id,
  libraryId = libraryId,
  bookCount = bookCount,
  deletedDate = deletedDate,
  oneshot = oneshot,
  createdDate = createdDate.toCurrentTimeZone(),
  lastModifiedDate = lastModifiedDate.toCurrentTimeZone(),
)
```

这说明 `Series` 的字段基本都能直接映射到数据库中的 series 记录。`bookCount` 也由 DAO 回填，而不是由 `Series` 自己动态计算。

### 下游：生命周期服务

根据当前片段推断，`Series` 的生命周期主要由 `komga/src/main/kotlin/org/gotson/komga/domain/service/LibraryContentLifecycle.kt` 和 `komga/src/main/kotlin/org/gotson/komga/domain/service/SeriesLifecycle.kt` 处理。

依据是调用方中可以看到：

- `LibraryContentLifecycle` 会根据扫描结果查找已有系列：`findNotDeletedByLibraryIdAndUrlOrNull(library.id, newSeries.url)`。
- 它会比较 `fileLastModified`、`deletedDate`、`url` 等字段，判断系列是否变化。
- `SeriesLifecycle` 会根据 `series.id` 找书籍、软删除、硬删除、处理缩略图、删除系列文件等。
- `SeriesController` 暴露系列相关 API，例如获取封面、更新元数据、分析书籍、删除系列文件等。

### 下游：搜索和 DTO

搜索层中存在 `LuceneEntity.Series`，并且 `SearchIndexLifecycle` 会在 `DomainEvent.SeriesUpdated` 时更新 series 搜索文档，在 `DomainEvent.SeriesDeleted` 时删除索引。接口层通常不会直接把 `Series` 原样暴露给前端，而是通过 DTO repository，例如 `SeriesDtoDao`、`SeriesDtoRepository` 组合更多信息后返回。

## 运行/调用流程

一个典型流程可以这样理解：

1. 用户配置一个 `Library`，其中包含根目录 `root` 和扫描规则。
2. 扫描器 `FileSystemScanner` 从 library 根目录开始遍历文件系统。
3. 每进入一个目录，扫描器先创建候选 `Series`，其中 `name` 来自目录名，`url` 来自目录 URI，`fileLastModified` 来自文件系统属性。
4. 扫描器继续遍历文件。如果发现支持的漫画/书籍文件，会创建 `Book`，并按父目录归组。
5. 目录遍历结束时，如果该目录下有书籍，候选 `Series` 才会进入扫描结果。
6. 如果命中 oneshot 规则，则每本书会被包装成一个 `oneshot = true` 的 `Series`，并且 `Series.url` 指向该书籍文件。
7. `LibraryContentLifecycle` 接收扫描结果，和数据库中已有系列对比。对比依据包括 `libraryId`、`url`、`fileLastModified`、删除状态等。
8. 新系列会被持久化；已有系列如果修改时间变化，会触发后续书籍、元数据、封面等更新流程。
9. 持久化层 `SeriesDao` 从数据库读取时，用 `SeriesRecord.toDomain()` 重建 `Series` 对象。
10. 上层服务和接口通过 `SeriesRepository`、`BookRepository`、`SeriesMetadataRepository`、`ThumbnailSeriesRepository` 等仓储围绕 `series.id` 做查询和更新。
11. 当系列更新或删除时，领域事件如 `DomainEvent.SeriesUpdated`、`DomainEvent.SeriesDeleted` 会被搜索索引等下游组件消费。

从对象职责看，`Series` 不负责“如何扫描”“如何保存”“如何生成封面”“如何搜索”。它只保存这些流程共同依赖的核心状态。

## 小白阅读顺序

建议按下面顺序阅读，比较容易建立全局理解：

1. 先读 `komga/src/main/kotlin/org/gotson/komga/domain/model/Series.kt`  
   只关注字段：`name`、`url`、`fileLastModified`、`id`、`libraryId`、`bookCount`、`deletedDate`、`oneshot`、`path`。

2. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/model/Book.kt`  
   对比 `Book` 和 `Series` 的相似结构，理解一个系列下有多本书，书籍通过 `seriesId` 归属到系列。

3. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/model/Library.kt`  
   理解 library 是扫描入口，`Series` 是扫描出来的中间/结果对象之一。重点看 `oneshotsDirectory`、`scanForceModifiedTime`、`seriesCover` 等配置。

4. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/model/SeriesMetadata.kt`  
   区分基础实体 `Series` 和内容元数据 `SeriesMetadata`。前者偏文件和系统状态，后者偏展示和编辑信息。

5. 然后读 `komga/src/main/kotlin/org/gotson/komga/domain/service/FileSystemScanner.kt` 中创建 `Series` 的片段  
   重点看普通目录如何变成系列，以及 oneshot 如何把单本书变成系列。

6. 最后读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/SeriesDao.kt` 的 `toDomain()`  
   看数据库记录如何被还原成 `Series`，确认哪些字段是持久化字段，哪些字段是派生字段。

## 常见误区

### 误区一：以为 `Series.name` 就是最终展示标题

不一定。`Series.name` 通常来自目录名或书籍名，是基础文件系统名称。真正用于展示、搜索和用户编辑的标题信息，更多会来自 `SeriesMetadata.title`、`titleSort` 等字段。`Series` 和 `SeriesMetadata` 是两个不同模型。

### 误区二：以为 `Series.url` 永远指向目录

普通系列通常是目录 URL，但 oneshot 系列可能指向具体书籍文件。因为扫描器在 oneshot 模式下会这样创建：

```kotlin
Series(
  name = book.name,
  url = book.url,
  fileLastModified = book.fileLastModified,
  oneshot = true,
)
```

所以处理 `Series.path` 时不要盲目假设它一定是目录。

### 误区三：以为 `bookCount` 是实时计算属性

`bookCount` 是构造参数里的普通字段，默认值为 `0`。从 `SeriesDao.toDomain()` 看，它会从数据库记录中回填。它不是通过访问 `BookRepository` 动态计算出来的属性。

### 误区四：以为 `path` 是独立保存的字段

`path` 是由 `url` 懒加载推导出来的：

```kotlin
val path: Path by lazy { this.url.toURI().toPath() }
```

它不是主状态。真正需要保存或传递的是 `url`。`@delegate:Transient` 也说明 lazy delegate 不应作为序列化状态处理。

### 误区五：以为 `deletedDate` 表示文件已经不存在

`deletedDate` 表示系统中的软删除状态，不一定等同于文件系统当前绝对不存在。扫描、回收站、重新出现、硬删除等流程会围绕它做判断。根据当前片段推断，`LibraryContentLifecycle` 会把 `deletedDate` 和扫描结果一起用于判断系列是否变化或恢复。

### 误区六：以为 `Series` 会自己维护书籍列表

`Series` 中没有 `books: List<Book>`。它只通过 `id` 和 `bookCount` 表达和书籍的关系。真正查询书籍要走 `BookRepository.findAllBySeriesId(series.id)` 这类仓储方法。这样可以避免领域对象过重，也方便数据库分页、权限过滤和搜索组合。

### 误区七：忽略 `fileLastModified` 和审计时间的区别

`fileLastModified` 是文件系统来源的修改时间，用于扫描变化检测；`createdDate` 和 `lastModifiedDate` 是应用/数据库层的审计时间。它们不是同一类时间，不应该混用。
