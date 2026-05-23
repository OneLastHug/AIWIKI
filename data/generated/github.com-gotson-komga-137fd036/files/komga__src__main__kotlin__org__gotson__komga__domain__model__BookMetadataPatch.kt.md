# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/BookMetadataPatch.kt

## 它负责什么

`BookMetadataPatch.kt` 定义了“书籍元数据补丁”的领域模型，也就是外部元数据来源解析出一部分书籍信息后，用来表达“这些字段可以尝试更新到现有 `BookMetadata` 上”的数据结构。

它不负责真正更新数据库，也不负责解析 EPUB、ComicInfo.xml 或条形码。它的职责更窄：

1. 用 `BookMetadataPatch` 承载可更新的书籍元数据字段。
2. 用 `BookMetadataPatch.ReadListEntry` 承载由书籍元数据推导出的阅读列表归属。
3. 用 `BookMetadataPatchCapability` 描述某个元数据 provider 能提供哪些能力，或者某个刷新任务只想刷新哪些字段。

可以把它理解为领域层里的“更新意图对象”：provider 说“我找到了 title、summary、authors、isbn 等信息”，后续服务再根据锁定状态、资料库设置和任务能力决定是否应用。

## 关键组成

目标文件代码很短，位于包：

`org.gotson.komga.domain.model`

它只显式 import 了：

`java.time.LocalDate`

这是因为 `BookMetadataPatch.releaseDate` 使用 `LocalDate?` 表示书籍发布日期。

核心类型有两个。

第一个是 `data class BookMetadataPatch`：

```kotlin
data class BookMetadataPatch(
  val title: String? = null,
  val summary: String? = null,
  val number: String? = null,
  val numberSort: Float? = null,
  val releaseDate: LocalDate? = null,
  val authors: List<Author>? = null,
  val isbn: String? = null,
  val links: List<WebLink>? = null,
  val tags: Set<String>? = null,
  val readLists: List<ReadListEntry> = emptyList(),
)
```

这些字段大体对应 `BookMetadata` 中真实持久化的书籍元数据字段：

`title`：书籍标题。  
`summary`：简介。  
`number`：卷号、册号或系列内编号的字符串形式。  
`numberSort`：用于排序的数字形式编号。  
`releaseDate`：发布日期。  
`authors`：作者列表，类型是同包下的 `Author`。  
`isbn`：ISBN。  
`links`：网页链接列表，类型是同包下的 `WebLink`。  
`tags`：标签集合。  
`readLists`：从元数据中提取出的阅读列表条目。

这里最重要的设计是：大多数字段都是可空类型，并且默认值是 `null`。在后续应用逻辑里，`null` 通常表示“这个 provider 没有提供该字段，不要改原值”，而不是“把原字段清空”。这一点由 `MetadataApplier` 的 `getIfNotLocked` 体现：只有 `patched != null` 且字段未锁定时，才用 patch 值替换原值。

`readLists` 是例外，它默认是 `emptyList()`，不是 `null`。这是因为阅读列表不是直接合并进 `BookMetadata` 的字段，而是在 `BookMetadataLifecycle` 中单独处理：当资料库允许处理 `MetadataPatchTarget.READLIST` 时，会遍历 `patch?.readLists`，调用 `ReadListLifecycle.addBookToReadList(...)`。

第二个组成是内部数据类 `ReadListEntry`：

```kotlin
data class ReadListEntry(
  val name: String,
  val number: Int? = null,
)
```

它表示“这本书属于某个阅读列表”，并可选带上在该阅读列表中的编号。

例如 `ComicInfoProvider` 会从 `ComicInfo.xml` 的 `alternateSeries`、`alternateNumber`、`storyArc`、`storyArcNumber` 等字段构造 `BookMetadataPatch.ReadListEntry`。如果有阅读顺序编号，就填 `number`；没有编号则只填列表名。

第三个组成是 `enum class BookMetadataPatchCapability`：

```kotlin
enum class BookMetadataPatchCapability {
  TITLE,
  SUMMARY,
  NUMBER,
  NUMBER_SORT,
  RELEASE_DATE,
  AUTHORS,
  TAGS,
  ISBN,
  READ_LISTS,
  THUMBNAILS,
  LINKS,
}
```

它描述 provider 或任务层面对书籍元数据刷新的能力范围。

例如：

`ComicInfoProvider` 声明支持 `TITLE`、`SUMMARY`、`NUMBER`、`NUMBER_SORT`、`RELEASE_DATE`、`AUTHORS`、`READ_LISTS`、`LINKS`。  
`EpubMetadataProvider` 声明支持 `TITLE`、`SUMMARY`、`RELEASE_DATE`、`AUTHORS`、`ISBN`。  
`IsbnBarcodeProvider` 根据搜索结果显示只支持 `ISBN`。  
`TaskEmitter.refreshBookMetadata(...)` 默认传入 `BookMetadataPatchCapability.entries.toSet()`，表示刷新全部能力。

注意枚举里有 `THUMBNAILS`，但 `BookMetadataPatch` 本身没有 thumbnail 字段。根据当前片段推断，这是因为“能力枚举”服务于元数据刷新任务的选择范围，可能覆盖与书籍元数据刷新相关但不一定落在 `BookMetadataPatch` 数据类里的事项；具体缩略图刷新逻辑不在本文件中。

## 上下游关系

上游主要是各种 `BookMetadataProvider` 实现。接口位于：

`komga/src/main/kotlin/org/gotson/komga/infrastructure/metadata/BookMetadataProvider.kt`

接口定义为：

```kotlin
interface BookMetadataProvider : MetadataProvider {
  val capabilities: Set<BookMetadataPatchCapability>

  fun getBookMetadataFromBook(book: BookWithMedia): BookMetadataPatch?
}
```

这说明每个 provider 需要声明自己能提供哪些 `BookMetadataPatchCapability`，并从 `BookWithMedia` 中尝试解析出 `BookMetadataPatch?`。

典型上游之一是：

`komga/src/main/kotlin/org/gotson/komga/infrastructure/metadata/comicrack/ComicInfoProvider.kt`

它读取 `ComicInfo.xml`，把 XML 中的 title、summary、number、release date、authors、links、tags、gtin/isbn、story arc 等信息转成 `BookMetadataPatch`。

另一个上游是：

`komga/src/main/kotlin/org/gotson/komga/infrastructure/metadata/epub/EpubMetadataProvider.kt`

它从 EPUB 的 OPF metadata 中读取 title、description、date、creator、identifier、collection index 等信息，然后返回 `BookMetadataPatch`。

下游主要是：

`komga/src/main/kotlin/org/gotson/komga/domain/service/BookMetadataLifecycle.kt`

它在 `refreshMetadata(book, capabilities)` 中遍历所有 `BookMetadataProvider`，根据请求的 capabilities 和 provider 的 capabilities 做交集判断。如果交集为空，就跳过该 provider；否则调用 `provider.getBookMetadataFromBook(...)` 获取 patch。

真正把 patch 应用到现有 `BookMetadata` 的逻辑在：

`komga/src/main/kotlin/org/gotson/komga/domain/service/MetadataApplier.kt`

`MetadataApplier.apply(patch: BookMetadataPatch, metadata: BookMetadata)` 会调用 `metadata.copy(...)` 生成新的 `BookMetadata`。每个字段都经过 `getIfNotLocked(original, patched, lock)`：

```kotlin
if (patched != null && !lock) patched else original
```

因此 `BookMetadataPatch` 的含义不是“强制覆盖”，而是“如果 provider 提供了值，并且用户没有锁定该字段，则更新”。

持久化下游是：

`BookMetadataRepository.update(patched)`

事件下游是：

`DomainEvent.BookUpdated(book)`

当 `BookMetadataLifecycle.refreshMetadata(...)` 认为有书籍元数据处理过后，会发布书籍更新事件。

阅读列表下游是：

`ReadListLifecycle.addBookToReadList(readList.name, book, readList.number)`

这条路径不经过 `MetadataApplier`，因为 `readLists` 不是 `BookMetadata` 的字段。

## 运行/调用流程

一次典型的书籍元数据刷新流程如下。

1. 某处业务触发刷新书籍元数据任务。

例如 `TaskEmitter.refreshBookMetadata(book, capabilities, priority)` 会提交 `Task.RefreshBookMetadata`。如果调用方没有指定 capabilities，默认使用 `BookMetadataPatchCapability.entries.toSet()`，也就是全部能力。

2. 任务执行到领域服务。

`BookMetadataLifecycle.refreshMetadata(book, capabilities)` 接收书籍对象和希望刷新的能力集合。

3. 服务读取上下文数据。

它通过 `mediaRepository.findById(book.id)` 找到媒体信息，通过 `libraryRepository.findById(book.libraryId)` 找到资料库设置。随后遍历注入进来的所有 `BookMetadataProvider`。

4. 根据能力过滤 provider。

每个 provider 都有 `capabilities`。如果请求的 capabilities 和 provider 的 capabilities 没有交集，就跳过。

例如只请求 `ISBN` 时，`IsbnBarcodeProvider` 这类 provider 可能会参与，而只支持 title/summary 的 provider 如果不支持 ISBN 就会被跳过。

5. 根据资料库设置判断是否处理。

`BookMetadataLifecycle` 会检查 provider 是否应该处理 `MetadataPatchTarget.BOOK` 或 `MetadataPatchTarget.READLIST`。如果资料库没有启用对应 provider 的导入行为，也会跳过。

6. provider 生成 `BookMetadataPatch?`。

例如 `ComicInfoProvider` 会从 `ComicInfo.xml` 中解析字段并返回：

```kotlin
BookMetadataPatch(
  title = ...,
  summary = ...,
  number = ...,
  numberSort = ...,
  releaseDate = ...,
  authors = ...,
  readLists = ...,
  links = ...,
  tags = ...,
  isbn = ...,
)
```

如果没有可用来源，provider 可以返回 `null`。

7. 如果处理书籍元数据，则应用 patch。

`BookMetadataLifecycle.handlePatchForBookMetadata(...)` 读取当前 `BookMetadata`，调用：

`metadataApplier.apply(bPatch, it)`

这一步会逐字段检查：

字段 patch 值不是 `null`。  
对应字段没有被 lock。  
满足两者才替换原值。

例如 `titleLock == true` 时，即使 `patch.title` 有值，也不会覆盖现有标题。

8. 更新仓库。

应用后的 `BookMetadata` 通过 `bookMetadataRepository.update(patched)` 保存。

9. 如果处理阅读列表，则单独添加书籍到阅读列表。

`patch?.readLists?.forEach { readList -> readListLifecycle.addBookToReadList(...) }`

这里的 `ReadListEntry.number` 会作为书籍在阅读列表中的可选编号传入。

10. 发布更新事件。

如果本轮处理过书籍元数据，`BookMetadataLifecycle` 会发布 `DomainEvent.BookUpdated(book)`。

## 小白阅读顺序

建议按下面顺序读，不要一开始就追所有 provider。

1. 先读 `komga/src/main/kotlin/org/gotson/komga/domain/model/BookMetadataPatch.kt`

先明确 `BookMetadataPatch` 只是一个补丁对象，不是数据库实体。重点看字段的可空设计，以及 `ReadListEntry` 和 `BookMetadataPatchCapability`。

2. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/model/BookMetadata.kt`

对照 `BookMetadataPatch` 和 `BookMetadata` 的字段。你会发现 `BookMetadata` 有真实的字段值和 lock 字段，例如 `titleLock`、`summaryLock`、`numberLock`、`isbnLock` 等；而 `BookMetadataPatch` 只有“候选新值”。

3. 接着读 `komga/src/main/kotlin/org/gotson/komga/domain/service/MetadataApplier.kt`

这是理解 patch 语义的关键。`getIfNotLocked` 说明了 `null` 不覆盖、lock 不覆盖。读完这里，就能理解为什么 provider 返回空字段不会清掉用户已有信息。

4. 然后读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/metadata/BookMetadataProvider.kt`

这是上游契约。任何书籍元数据来源都需要说明自己的 `capabilities`，并返回 `BookMetadataPatch?`。

5. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/service/BookMetadataLifecycle.kt`

这里串起完整流程：过滤 provider、读取 patch、应用到书籍元数据、处理阅读列表、发布事件。

6. 最后抽样读 provider。

优先读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/metadata/comicrack/ComicInfoProvider.kt`，因为它填的字段最多，包括 `readLists`、`links`、`tags`。再读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/metadata/epub/EpubMetadataProvider.kt`，它更适合理解 EPUB metadata 到 patch 的转换。

## 常见误区

误区一：以为 `BookMetadataPatch` 是数据库实体。

它不是。真正的书籍元数据模型是 `BookMetadata`，持久化更新也发生在 `BookMetadataRepository.update(...)`。`BookMetadataPatch` 只是 provider 输出的候选更新内容。

误区二：以为 `null` 表示清空字段。

在当前应用逻辑中不是。`MetadataApplier.getIfNotLocked` 只有在 `patched != null` 时才替换原字段。所以 `patch.summary = null` 的意思是“没有提供 summary 更新”，不是“把 summary 清空”。

误区三：忽略 lock 字段。

即使 patch 中有值，只要 `BookMetadata` 对应字段 lock 为 `true`，也不会被覆盖。例如 `titleLock` 为真时，provider 解析出的 `title` 不会生效。

误区四：以为 `readLists` 会进入 `BookMetadata`。

`readLists` 不在 `BookMetadata.copy(...)` 中处理。它在 `BookMetadataLifecycle` 中通过 `ReadListLifecycle.addBookToReadList(...)` 单独处理。也就是说它属于“由书籍元数据导入过程附带产生的阅读列表关系”，不是书籍元数据表自身字段。

误区五：以为 `BookMetadataPatchCapability` 和 `BookMetadataPatch` 字段一一对应。

大部分是对应的，比如 `TITLE` 对 `title`，`ISBN` 对 `isbn`，`LINKS` 对 `links`。但并不完全一一对应，例如枚举里有 `THUMBNAILS`，而 `BookMetadataPatch` 没有 `thumbnails` 字段。根据当前片段推断，capability 更像任务和 provider 的能力筛选语言，不完全等同于 patch 数据结构字段列表。

误区六：以为 provider 只要存在就一定会执行。

`BookMetadataLifecycle` 会先检查请求 capabilities 和 provider capabilities 是否有交集，还会检查资料库是否允许该 provider 处理 `BOOK` 或 `READLIST` 目标。两层条件都影响 provider 是否参与。

误区七：以为 `BookMetadataPatchCapability.READ_LISTS` 会影响普通 metadata 合并。

`READ_LISTS` 主要用于 provider 能力筛选和阅读列表导入流程。普通书籍字段合并由 `MetadataApplier.apply(BookMetadataPatch, BookMetadata)` 负责，而该方法没有处理 `readLists`。
