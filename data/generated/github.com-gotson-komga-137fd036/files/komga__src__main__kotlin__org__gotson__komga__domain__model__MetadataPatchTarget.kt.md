# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/MetadataPatchTarget.kt

## 它负责什么

`MetadataPatchTarget.kt` 定义了一个非常小但很关键的领域枚举：

```kotlin
enum class MetadataPatchTarget {
  BOOK,
  SERIES,
  READLIST,
  COLLECTION,
}
```

它的职责是表达“某个元数据补丁要作用到哪一种业务目标上”。在 Komga 的元数据导入流程里，一个 metadata provider 可能能从同一份外部数据里提取多类信息，例如：

- 书籍自身元数据：标题、摘要、作者、ISBN、标签等；
- 系列元数据：系列标题、出版社、语言、题材、阅读方向等；
- 阅读列表关系：把某本书加入某个 read list；
- 收藏集合关系：把某个 series 加入某个 collection。

`MetadataPatchTarget` 不保存补丁内容，也不执行补丁应用。它只作为一个“目标类型参数”，传给 provider 的判断函数，让 provider 根据当前 `Library` 的配置决定是否处理某一类补丁。

换句话说，它是元数据导入系统中的一个开关维度：同一个 provider 是否应该处理 `BOOK`、`SERIES`、`READLIST` 或 `COLLECTION`，由 `MetadataPatchTarget` 和 `Library` 配置共同决定。

## 关键组成

这个文件位于包：

```kotlin
package org.gotson.komga.domain.model
```

没有额外 import，说明它不依赖其他模型或基础设施类。枚举本身在 Kotlin 中默认是 `public`，因此可被其他包直接引用。

四个枚举值分别代表四种元数据补丁目标：

`BOOK`

表示补丁作用于书籍级元数据。典型下游是 `BookMetadataLifecycle` 中刷新单本书 metadata 的流程。provider 返回 `BookMetadataPatch` 后，系统会通过 `MetadataApplier` 合并到已有的 `BookMetadata`，再由 `BookMetadataRepository` 更新持久化数据。

相关模型是 `komga/src/main/kotlin/org/gotson/komga/domain/model/BookMetadataPatch.kt`。它包含 `title`、`summary`、`number`、`numberSort`、`releaseDate`、`authors`、`isbn`、`links`、`tags` 等字段，还包含 `readLists` 字段，但 `readLists` 的应用目标会由 `READLIST` 控制。

`SERIES`

表示补丁作用于系列级元数据。典型下游是 `SeriesMetadataLifecycle`。provider 返回 `SeriesMetadataPatch` 后，系统把它应用到 `SeriesMetadata` 上。

相关模型是 `komga/src/main/kotlin/org/gotson/komga/domain/model/SeriesMetadataPatch.kt`，字段包括 `title`、`titleSort`、`status`、`summary`、`readingDirection`、`publisher`、`ageRating`、`language`、`genres`、`totalBookCount`、`collections`。

`READLIST`

表示从书籍元数据来源中提取阅读列表关系。它不是修改书籍 metadata 字段本身，而是让 `BookMetadataLifecycle` 调用 `ReadListLifecycle.addBookToReadList(...)`，把当前 `Book` 加入对应 read list。

这个目标和 `BookMetadataPatch.readLists` 强相关。也就是说，一个 provider 可能读取同一份书籍 sidecar 元数据，既能更新书籍字段，也能更新 read list 关系；是否处理这两部分分别由 `BOOK` 和 `READLIST` 控制。

`COLLECTION`

表示从系列元数据来源中提取 collection 关系。它不是修改 `SeriesMetadata` 字段本身，而是让 `SeriesMetadataLifecycle` 调用 `SeriesCollectionLifecycle.addSeriesToCollection(...)`，把当前 `Series` 加入 collection。

这个目标和 `SeriesMetadataPatch.collections` 强相关。provider 可以同时提供系列元数据和 collection 归属；是否处理这两部分分别由 `SERIES` 和 `COLLECTION` 控制。

## 上下游关系

上游调用者主要是两个 domain service：

`komga/src/main/kotlin/org/gotson/komga/domain/service/BookMetadataLifecycle.kt`

这个服务在刷新书籍 metadata 时，会对每个 `BookMetadataProvider` 判断：

```kotlin
provider.shouldLibraryHandlePatch(library, MetadataPatchTarget.BOOK)
provider.shouldLibraryHandlePatch(library, MetadataPatchTarget.READLIST)
```

如果 provider 对 `BOOK` 或 `READLIST` 都不应该处理，就跳过该 provider。

如果允许 `BOOK`，会把 `BookMetadataPatch` 应用到书籍 metadata：

```kotlin
handlePatchForBookMetadata(patch, book)
```

如果允许 `READLIST`，会读取 patch 里的 `readLists`，逐个调用：

```kotlin
readListLifecycle.addBookToReadList(readList.name, book, readList.number)
```

`komga/src/main/kotlin/org/gotson/komga/domain/service/SeriesMetadataLifecycle.kt`

这个服务有两类 provider：

- `SeriesMetadataFromBookProvider`：从 book 中提取 series metadata，例如从每本书的内嵌元数据聚合系列信息；
- `SeriesMetadataProvider`：直接从 series 级来源提取 metadata，例如 series 目录里的 sidecar 文件。

它会判断：

```kotlin
provider.shouldLibraryHandlePatch(library, MetadataPatchTarget.SERIES)
provider.shouldLibraryHandlePatch(library, MetadataPatchTarget.COLLECTION)
```

如果允许 `SERIES`，会把 `SeriesMetadataPatch` 应用到系列 metadata。对于从 book 聚合出来的多个 patch，代码会先做聚合，例如最常见标题、最高年龄分级、合并 genres 等，再应用到 series。

如果允许 `COLLECTION`，会读取 patch 里的 `collections`，逐个调用：

```kotlin
collectionLifecycle.addSeriesToCollection(collection, series)
```

下游实现接口是：

`komga/src/main/kotlin/org/gotson/komga/infrastructure/metadata/MetadataProvider.kt`

其中核心方法是：

```kotlin
fun shouldLibraryHandlePatch(
  library: Library,
  target: MetadataPatchTarget,
): Boolean
```

所有元数据 provider 都通过这个方法接收 `MetadataPatchTarget`，再结合 `Library` 上的导入配置返回 `true` 或 `false`。

典型 provider 行为如下：

`komga/src/main/kotlin/org/gotson/komga/infrastructure/metadata/comicrack/ComicInfoProvider.kt`

它对四种目标都有明确映射：

```kotlin
MetadataPatchTarget.BOOK -> library.importComicInfoBook
MetadataPatchTarget.SERIES -> library.importComicInfoSeries
MetadataPatchTarget.READLIST -> library.importComicInfoReadList
MetadataPatchTarget.COLLECTION -> library.importComicInfoCollection
```

这说明 ComicInfo 是能力最完整的一类 provider：同一份 `ComicInfo.xml` 可能影响 book、series、read list 和 collection。

`komga/src/main/kotlin/org/gotson/komga/infrastructure/metadata/epub/EpubMetadataProvider.kt`

它只处理：

```kotlin
MetadataPatchTarget.BOOK -> library.importEpubBook
MetadataPatchTarget.SERIES -> library.importEpubSeries
else -> false
```

也就是说 EPUB 元数据来源不会处理 read list 和 collection。

`komga/src/main/kotlin/org/gotson/komga/infrastructure/metadata/barcode/IsbnBarcodeProvider.kt`

它只处理：

```kotlin
MetadataPatchTarget.BOOK -> library.importBarcodeIsbn
else -> false
```

这个 provider 的目标更窄，只给 book metadata 补 ISBN。

`komga/src/main/kotlin/org/gotson/komga/infrastructure/metadata/mylar/MylarSeriesProvider.kt`

它只处理：

```kotlin
MetadataPatchTarget.SERIES -> library.importMylarSeries
else -> false
```

说明 Mylar 来源只负责 series metadata，不负责 book、read list 或 collection。

`komga/src/main/kotlin/org/gotson/komga/infrastructure/metadata/oneshot/OneShotSeriesProvider.kt`

根据当前片段推断，它也是 series 级 provider，因为引用处显示它的 `shouldLibraryHandlePatch` 返回 `target == MetadataPatchTarget.SERIES`。

## 运行/调用流程

以刷新一本书为例，流程大致是：

1. 业务代码触发 `BookMetadataLifecycle.refreshMetadata(book, capabilities)`。
2. 服务读取当前书籍的 `Media` 和所属 `Library`。
3. 遍历所有 `BookMetadataProvider`。
4. 先检查 provider 是否支持请求的 `BookMetadataPatchCapability`。
5. 再调用 `shouldLibraryHandlePatch(library, MetadataPatchTarget.BOOK)` 和 `shouldLibraryHandlePatch(library, MetadataPatchTarget.READLIST)`。
6. 如果两个目标都不允许，跳过 provider。
7. 否则调用 `provider.getBookMetadataFromBook(BookWithMedia(book, media))` 得到 `BookMetadataPatch?`。
8. 如果 `BOOK` 允许，把 patch 应用到 `BookMetadataRepository` 中的现有 metadata。
9. 如果 `READLIST` 允许，把 patch 里的 `readLists` 转换成 read list 关系。
10. 如果 book metadata 被处理过，发布 `DomainEvent.BookUpdated(book)`。

以刷新一个系列为例，流程大致是：

1. 业务代码触发 `SeriesMetadataLifecycle.refreshMetadata(series)`。
2. 服务读取当前 series 所属 `Library`。
3. 先遍历 `SeriesMetadataFromBookProvider`。
4. 对每个 provider 判断是否允许 `SERIES` 或 `COLLECTION`。
5. 如果允许，遍历 series 下所有 book，从每本书提取 `SeriesMetadataPatch`。
6. 如果 `SERIES` 允许，把多个 patch 聚合后应用到 `SeriesMetadataRepository`。
7. 如果 `COLLECTION` 允许，把 patch 中的 `collections` 转换成 series collection 关系。
8. 再遍历 `SeriesMetadataProvider`，判断是否允许 `SERIES`。
9. 如果允许，直接从 series 级来源读取 `SeriesMetadataPatch` 并应用。
10. 如果 series metadata 被处理过，发布 `DomainEvent.SeriesUpdated(series)`。

在这些流程里，`MetadataPatchTarget` 的作用点非常集中：它不参与提取、不参与合并、不参与持久化，只参与“这个 provider 对这个 library 是否应该处理这类目标”的判断。

## 小白阅读顺序

建议按下面顺序阅读：

1. 先看 `komga/src/main/kotlin/org/gotson/komga/domain/model/MetadataPatchTarget.kt`

   只需要理解四个枚举值：`BOOK`、`SERIES`、`READLIST`、`COLLECTION`。这是后面所有判断的分类基础。

2. 再看 `komga/src/main/kotlin/org/gotson/komga/infrastructure/metadata/MetadataProvider.kt`

   重点看 `shouldLibraryHandlePatch(library, target)`。这个接口解释了为什么枚举需要存在：provider 通过它对不同目标返回不同开关结果。

3. 再看 `komga/src/main/kotlin/org/gotson/komga/domain/service/BookMetadataLifecycle.kt`

   重点看 `refreshMetadata` 中对 `MetadataPatchTarget.BOOK` 和 `MetadataPatchTarget.READLIST` 的判断。这里能看到同一个 `BookMetadataPatch` 被拆成两类效果：更新 book metadata、维护 read list 关系。

4. 再看 `komga/src/main/kotlin/org/gotson/komga/domain/service/SeriesMetadataLifecycle.kt`

   重点看 `MetadataPatchTarget.SERIES` 和 `MetadataPatchTarget.COLLECTION`。这里能看到 series metadata 更新和 collection 关系维护是分开的。

5. 然后看具体 provider，例如 `ComicInfoProvider.kt`

   `ComicInfoProvider` 最适合入门，因为它覆盖四个枚举值，能直观看到每个 target 对应 `Library` 上哪个导入配置。

6. 最后看较窄的 provider，例如 `EpubMetadataProvider.kt`、`IsbnBarcodeProvider.kt`、`MylarSeriesProvider.kt`

   这些 provider 展示了一个常见模式：不支持的 target 直接返回 `false`。这能帮助理解 `MetadataPatchTarget` 是能力过滤和配置过滤的一部分。

## 常见误区

误区一：以为 `MetadataPatchTarget` 是补丁数据本身。

它不是。真正的补丁数据在 `BookMetadataPatch` 和 `SeriesMetadataPatch`。`MetadataPatchTarget` 只是说明当前要问 provider：“你是否应该处理这种目标？”

误区二：以为 `READLIST` 和 `COLLECTION` 是普通 metadata 字段。

它们更像关系更新目标。`READLIST` 最终会调用 `ReadListLifecycle`，把 book 加入 read list；`COLLECTION` 最终会调用 `SeriesCollectionLifecycle`，把 series 加入 collection。它们不是简单地写入 `BookMetadataRepository` 或 `SeriesMetadataRepository` 的普通字段。

误区三：以为一个 provider 只对应一个 target。

不一定。`ComicInfoProvider` 可以同时支持 `BOOK`、`SERIES`、`READLIST`、`COLLECTION`。而 `IsbnBarcodeProvider` 只支持 `BOOK`，`MylarSeriesProvider` 只支持 `SERIES`。所以 target 是 provider 能力和 library 配置的细分维度。

误区四：以为 `MetadataPatchTarget.SERIES` 总是来自 series 文件。

不一定。`SeriesMetadataLifecycle` 中有 `SeriesMetadataFromBookProvider`，它可以从 series 下的多本 book 中提取 series metadata，再聚合成一个 series patch。因此 `SERIES` 表示应用目标是 series，不表示数据来源一定是 series 级文件。

误区五：以为允许 `BOOK` 就一定允许 `READLIST`。

这两个开关是独立的。`BookMetadataLifecycle` 会分别判断 `BOOK` 和 `READLIST`。一个 library 可以配置为导入 book metadata，但不导入 read list；也可以根据 provider 实现只支持其中一类。

误区六：以为允许 `SERIES` 就一定允许 `COLLECTION`。

同理，`SERIES` 和 `COLLECTION` 是独立目标。`SeriesMetadataLifecycle` 会分别处理 series metadata 和 collection 关系。`SeriesMetadataPatch.collections` 即使存在，也只有在 provider 对 `MetadataPatchTarget.COLLECTION` 返回 `true` 时才会用于维护 collection 关系。

误区七：忽略 `Library` 配置。

`MetadataPatchTarget` 本身不决定是否导入。真正的判断是 `provider.shouldLibraryHandlePatch(library, target)`。例如 `ComicInfoProvider` 会把不同 target 映射到 `library.importComicInfoBook`、`library.importComicInfoSeries`、`library.importComicInfoReadList`、`library.importComicInfoCollection`。因此是否处理某类补丁取决于 provider 实现和当前 library 的配置。
