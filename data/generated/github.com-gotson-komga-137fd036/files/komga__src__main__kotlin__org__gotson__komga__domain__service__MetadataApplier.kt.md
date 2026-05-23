# 文件：komga/src/main/kotlin/org/gotson/komga/domain/service/MetadataApplier.kt

## 它负责什么

`MetadataApplier` 是 Komga 领域层里的一个 Spring `@Service`，专门负责把“外部解析/导入得到的元数据补丁”应用到“当前已保存的元数据”上。

它处理两类元数据：

- 书籍元数据：`BookMetadataPatch` 应用到 `BookMetadata`
- 系列元数据：`SeriesMetadataPatch` 应用到 `SeriesMetadata`

它的核心职责不是解析文件、不是访问数据库、也不是发布事件，而是做一个很小但很关键的判断：

> patch 里有新值，并且对应字段没有被锁定时，才用 patch 的值覆盖原 metadata；否则保留原值。

也就是说，`MetadataApplier` 是“字段锁定规则”的集中执行点。用户或系统如果把某个字段设为 locked，例如 `titleLock = true`，后续从 ComicInfo、OPF、外部 provider 等来源刷新 metadata 时，这个字段就不会被自动覆盖。

## 关键组成

这个文件只有一个类：`MetadataApplier`。

### `@Service class MetadataApplier`

`MetadataApplier` 被标记为 Spring `@Service`，说明它由 Spring 容器托管，可以被其他 service 构造注入。实际调用方包括：

- `komga/src/main/kotlin/org/gotson/komga/domain/service/BookMetadataLifecycle.kt`
- `komga/src/main/kotlin/org/gotson/komga/domain/service/SeriesMetadataLifecycle.kt`

它没有保存状态，也没有依赖注入字段，是一个纯粹的领域规则服务。

### `private fun <T> getIfNotLocked(...)`

这是整个类的核心工具函数：

```kotlin
private fun <T> getIfNotLocked(
  original: T,
  patched: T?,
  lock: Boolean,
): T =
  if (patched != null && !lock)
    patched
  else
    original
```

参数含义：

- `original`：当前数据库或领域对象里已有的字段值
- `patched`：provider 提供的新字段值，可能为 `null`
- `lock`：当前字段是否被锁定

返回规则：

- 如果 `patched != null` 且 `lock == false`，返回 `patched`
- 否则返回 `original`

这个函数是泛型 `<T>`，所以可以复用于 `String`、`Float`、`LocalDate?`、`List<Author>`、`Set<String>`、枚举类型等字段。

需要注意：这里的 `patched != null` 是“是否有补丁值”的判断。对于字符串字段，如果 patch 给的是空字符串 `""`，它不是 `null`，所以在未锁定时会覆盖原值。后续规范化由对应 metadata 类型的构造逻辑负责，例如 `BookMetadata` 会 trim `title`、`summary`、`number`，并规范化 `tags`。

### `fun apply(patch: BookMetadataPatch, metadata: BookMetadata): BookMetadata`

这个方法处理书籍元数据。

它使用 `with(metadata)` 进入当前 metadata 的上下文，然后调用 `copy(...)` 创建一个新的 `BookMetadata`：

```kotlin
copy(
  title = getIfNotLocked(title, patch.title, titleLock),
  summary = getIfNotLocked(summary, patch.summary, summaryLock),
  number = getIfNotLocked(number, patch.number, numberLock),
  numberSort = getIfNotLocked(numberSort, patch.numberSort, numberSortLock),
  releaseDate = getIfNotLocked(releaseDate, patch.releaseDate, releaseDateLock),
  authors = getIfNotLocked(authors, patch.authors, authorsLock),
  isbn = getIfNotLocked(isbn, patch.isbn, isbnLock),
  links = getIfNotLocked(links, patch.links, linksLock),
  tags = getIfNotLocked(tags, patch.tags, tagsLock),
)
```

它会应用的 `BookMetadataPatch` 字段包括：

- `title`
- `summary`
- `number`
- `numberSort`
- `releaseDate`
- `authors`
- `isbn`
- `links`
- `tags`

它不会处理 `BookMetadataPatch.readLists`。这是因为 read list 不属于 `BookMetadata` 本体字段，调用方 `BookMetadataLifecycle` 会单独处理 read list：

- metadata 字段更新走 `metadataApplier.apply(...)`
- read list 更新走 `ReadListLifecycle.addBookToReadList(...)`

它也不会修改任何 lock 字段，例如 `titleLock`、`summaryLock`、`authorsLock`。锁本身是 metadata 的保护配置，不由这个 patch 应用器改变。

### `fun apply(patch: SeriesMetadataPatch, metadata: SeriesMetadata): SeriesMetadata`

这个方法处理系列元数据。

它同样通过 `metadata.copy(...)` 创建新的 `SeriesMetadata`：

```kotlin
copy(
  status = getIfNotLocked(status, patch.status, statusLock),
  title = getIfNotLocked(title, patch.title, titleLock),
  titleSort = getIfNotLocked(titleSort, patch.titleSort, titleSortLock),
  summary = getIfNotLocked(summary, patch.summary, summaryLock),
  readingDirection = getIfNotLocked(readingDirection, patch.readingDirection, readingDirectionLock),
  ageRating = getIfNotLocked(ageRating, patch.ageRating, ageRatingLock),
  publisher = getIfNotLocked(publisher, patch.publisher, publisherLock),
  language = getIfNotLocked(language, patch.language, languageLock),
  genres = getIfNotLocked(genres, patch.genres, genresLock),
  totalBookCount = getIfNotLocked(totalBookCount, patch.totalBookCount, totalBookCountLock),
)
```

它会应用的 `SeriesMetadataPatch` 字段包括：

- `status`
- `title`
- `titleSort`
- `summary`
- `readingDirection`
- `ageRating`
- `publisher`
- `language`
- `genres`
- `totalBookCount`

它不会处理 `SeriesMetadataPatch.collections`。集合归属不是 `SeriesMetadata` 本体字段，调用方 `SeriesMetadataLifecycle` 会通过 `SeriesCollectionLifecycle.addSeriesToCollection(...)` 单独处理。

它也不会处理 `SeriesMetadata` 里存在但 `SeriesMetadataPatch` 没有覆盖的字段，例如：

- `tags`
- `sharingLabels`
- `links`
- `alternateTitles`

根据当前片段推断，这些字段要么来自其他更新入口，要么暂时不属于当前 metadata provider patch 的应用范围。依据是 `SeriesMetadataPatch` 类型本身没有这些字段，而 `MetadataApplier.apply(SeriesMetadataPatch, SeriesMetadata)` 只能应用 patch 中存在的字段。

## 上下游关系

### 上游：metadata provider 生成 patch

`MetadataApplier` 的直接输入是 patch 对象，而 patch 通常由 metadata provider 生成。

书籍侧的上游在 `BookMetadataLifecycle` 中：

- 注入 `List<BookMetadataProvider>`
- 调用 `provider.getBookMetadataFromBook(BookWithMedia(book, media))`
- 得到 `BookMetadataPatch`
- 再交给 `metadataApplier.apply(...)`

系列侧的上游在 `SeriesMetadataLifecycle` 中：

- 注入 `List<SeriesMetadataFromBookProvider>`
- 注入 `List<SeriesMetadataProvider>`
- 从书籍文件或系列级 provider 中获取 `SeriesMetadataPatch`
- 对来自多本书的 series patch 先做聚合
- 再交给 `metadataApplier.apply(...)`

也就是说，`MetadataApplier` 不关心 patch 来自哪里。它只关心 patch 中有哪些字段，以及这些字段是否允许覆盖。

### 下游：repository 持久化新 metadata

`MetadataApplier` 返回的是新的 metadata 对象，不直接保存数据库。

书籍侧下游：

- `BookMetadataLifecycle.handlePatchForBookMetadata(...)`
- 读取当前 `BookMetadata`
- 调用 `metadataApplier.apply(bPatch, it)`
- 调用 `bookMetadataRepository.update(patched)`

系列侧下游：

- `SeriesMetadataLifecycle.handlePatchForSeriesMetadata(...)`
- 读取当前 `SeriesMetadata`
- 调用 `metadataApplier.apply(sPatch, it)`
- 调用 `seriesMetadataRepository.update(patched)`

因此它的位置可以理解为：

```text
Provider 解析外部来源
  -> 生成 MetadataPatch
  -> MetadataLifecycle 读取当前 Metadata
  -> MetadataApplier 按锁字段合并
  -> Repository 保存合并结果
  -> Lifecycle 发布 DomainEvent
```

### 与 model 的关系

`MetadataApplier` 依赖这些 domain model：

- `org.gotson.komga.domain.model.BookMetadata`
- `org.gotson.komga.domain.model.BookMetadataPatch`
- `org.gotson.komga.domain.model.SeriesMetadata`
- `org.gotson.komga.domain.model.SeriesMetadataPatch`

`BookMetadata` 和 `SeriesMetadata` 都不是 Kotlin `data class`，但它们手写了 `copy(...)` 方法。`MetadataApplier` 正是通过这些 `copy(...)` 方法保持不可变式更新风格：不直接改原对象，而是构造一个带有新字段的新对象。

这也很重要，因为 `BookMetadata` 和 `SeriesMetadata` 构造时会做一些标准化：

- `BookMetadata.title`、`summary`、`number` 会 `trim()`
- `BookMetadata.tags` 会 lower-case 并过滤空值
- `SeriesMetadata.title`、`titleSort`、`summary`、`publisher` 会 `trim()`
- `SeriesMetadata.language` 会通过 `BCP47TagValidator.normalize(...)` 标准化
- `SeriesMetadata.tags`、`genres`、`sharingLabels` 会 lower-case 并过滤空值

所以 `MetadataApplier` 只负责选择值，字段清洗由 metadata model 自己负责。

## 运行/调用流程

### 书籍 metadata 刷新流程

典型流程在 `BookMetadataLifecycle.refreshMetadata(...)` 中：

1. 外部调用要求刷新某本 `Book` 的 metadata，并传入能力集合 `capabilities`。
2. `BookMetadataLifecycle` 读取 book 的 media 和 library。
3. 遍历所有 `BookMetadataProvider`。
4. 判断 provider 是否支持请求的 capabilities。
5. 判断当前 library 是否允许该 provider 导入 book metadata 或 read list metadata。
6. 调用 provider 生成 `BookMetadataPatch`。
7. 如果 library 允许处理 book metadata，进入 `handlePatchForBookMetadata(...)`。
8. 从 `bookMetadataRepository.findById(book.id)` 读取当前 `BookMetadata`。
9. 调用 `metadataApplier.apply(bPatch, it)` 合并 patch 和当前 metadata。
10. 调用 `bookMetadataRepository.update(patched)` 保存。
11. 如果有变化，发布 `DomainEvent.BookUpdated(book)`。

其中第 9 步就是当前文件的核心工作。

举例：

```text
当前 BookMetadata:
title = "Old Title"
titleLock = true
summary = "Old Summary"
summaryLock = false

BookMetadataPatch:
title = "New Title"
summary = "New Summary"

应用结果:
title 保持 "Old Title"，因为 titleLock = true
summary 变为 "New Summary"，因为 summaryLock = false
```

### 系列 metadata 刷新流程

典型流程在 `SeriesMetadataLifecycle.refreshMetadata(...)` 中：

1. 外部调用要求刷新某个 `Series` 的 metadata。
2. `SeriesMetadataLifecycle` 读取 series 所属 library。
3. 先遍历 `SeriesMetadataFromBookProvider`，这些 provider 从 series 下的每本 book 中提取系列信息。
4. 对每本书调用 `provider.getSeriesMetadataFromBook(...)`，得到多个 `SeriesMetadataPatch`。
5. 如果 library 允许处理 series metadata，则先聚合多个 patch：
   - `title`、`titleSort`、`status`、`language`、`readingDirection`、`publisher` 取最常见值
   - `genres` 合并成集合
   - `ageRating` 取最大值
   - `totalBookCount` 取最大值
   - `summary` 被设置为 `null`
6. 聚合后调用 `handlePatchForSeriesMetadata(...)`。
7. 从 `seriesMetadataRepository.findById(series.id)` 读取当前 `SeriesMetadata`。
8. 调用 `metadataApplier.apply(sPatch, it)` 合并 patch。
9. 调用 `seriesMetadataRepository.update(patched)` 保存。
10. 再遍历 `SeriesMetadataProvider`，处理系列级 provider 返回的单个 patch。
11. 如果有变化，发布 `DomainEvent.SeriesUpdated(series)`。

这里有一个细节：从多本书聚合出来的 series patch 中，`summary = null`。按照 `getIfNotLocked(...)` 的规则，`null` 不会覆盖原值。因此从书籍聚合系列 metadata 时不会更新系列简介。根据当前片段推断，这是有意设计：简介可能不适合从多本书中自动选一个覆盖系列简介，依据是聚合逻辑显式把 `summary` 设为 `null`。

### 字段锁的执行方式

每个可更新字段都有对应 lock 字段。例如：

书籍侧：

- `title` 对应 `titleLock`
- `summary` 对应 `summaryLock`
- `number` 对应 `numberLock`
- `numberSort` 对应 `numberSortLock`
- `releaseDate` 对应 `releaseDateLock`
- `authors` 对应 `authorsLock`
- `tags` 对应 `tagsLock`
- `isbn` 对应 `isbnLock`
- `links` 对应 `linksLock`

系列侧：

- `status` 对应 `statusLock`
- `title` 对应 `titleLock`
- `titleSort` 对应 `titleSortLock`
- `summary` 对应 `summaryLock`
- `readingDirection` 对应 `readingDirectionLock`
- `publisher` 对应 `publisherLock`
- `ageRating` 对应 `ageRatingLock`
- `language` 对应 `languageLock`
- `genres` 对应 `genresLock`
- `totalBookCount` 对应 `totalBookCountLock`

判断公式始终一样：

```text
patch 字段不是 null，并且字段未锁定 -> 使用 patch 值
否则 -> 保留原 metadata 值
```

## 小白阅读顺序

建议按下面顺序读：

1. 先读 `komga/src/main/kotlin/org/gotson/komga/domain/service/MetadataApplier.kt`

   这个文件最短，先理解 `getIfNotLocked(...)`。只要理解了这个函数，就理解了 80% 的逻辑。

2. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/model/BookMetadataPatch.kt`

   看 patch 是什么。重点看字段都是 nullable，例如 `title: String? = null`、`numberSort: Float? = null`。这里的 `null` 表示“provider 没有提供这个字段”，不是“把字段清空”。

3. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/model/BookMetadata.kt`

   看真实保存的书籍 metadata 有哪些字段，以及每个字段对应哪些 lock。重点关注手写 `copy(...)` 方法和构造时的 trim、tag 标准化。

4. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/model/SeriesMetadataPatch.kt`

   看系列 patch 支持哪些字段。注意 `collections` 在 patch 里存在，但不由 `MetadataApplier` 应用到 `SeriesMetadata`。

5. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/model/SeriesMetadata.kt`

   看系列 metadata 的字段比 patch 更多，例如 `tags`、`sharingLabels`、`links`、`alternateTitles`，这些不是当前 applier 的覆盖范围。

6. 最后读调用方：

   - `komga/src/main/kotlin/org/gotson/komga/domain/service/BookMetadataLifecycle.kt`
   - `komga/src/main/kotlin/org/gotson/komga/domain/service/SeriesMetadataLifecycle.kt`

   这两个文件能帮助理解 `MetadataApplier` 不是独立运行的，而是在刷新 metadata 的流程里被调用。

## 常见误区

### 误区一：以为 patch 中的 `null` 会清空原字段

不会。

`getIfNotLocked(...)` 的第一条件是 `patched != null`。如果 patch 字段是 `null`，一定返回 `original`。

所以：

```text
original.summary = "旧简介"
patch.summary = null
summaryLock = false
结果仍然是 "旧简介"
```

`null` 的语义更接近“没有提供更新”，不是“设置为空”。

### 误区二：以为 lock 会阻止所有更新

lock 只阻止对应字段被 `MetadataApplier` 覆盖。

例如 `titleLock = true` 只影响 `title`，不影响 `summary`、`authors`、`tags`。每个字段独立判断。

### 误区三：以为 `MetadataApplier` 会保存数据库

不会。

它只返回新的 `BookMetadata` 或 `SeriesMetadata`。真正保存发生在调用方：

- `bookMetadataRepository.update(patched)`
- `seriesMetadataRepository.update(patched)`

这也是为什么这个类没有 repository 依赖。

### 误区四：以为 `MetadataApplier` 会发布事件

不会。

事件发布也在 lifecycle 中完成：

- `DomainEvent.BookUpdated(book)`
- `DomainEvent.SeriesUpdated(series)`

`MetadataApplier` 不知道业务事件，也不关心刷新来源。

### 误区五：以为所有 patch 字段都会被应用到 metadata

不会。

`BookMetadataPatch.readLists` 不由 `MetadataApplier` 处理，而是在 `BookMetadataLifecycle` 中通过 `ReadListLifecycle` 处理。

`SeriesMetadataPatch.collections` 不由 `MetadataApplier` 处理，而是在 `SeriesMetadataLifecycle` 中通过 `SeriesCollectionLifecycle` 处理。

这是因为 read list 和 collection 是关系型业务动作，不是 metadata 对象上的普通字段覆盖。

### 误区六：以为它会修改 lock 字段

不会。

`MetadataApplier` 调用 `copy(...)` 时只传入内容字段，没有传入 lock 字段。lock 字段会沿用原 metadata 的值。

例如 `BookMetadata.copy(...)` 的 `titleLock` 默认值是 `this.titleLock`，所以如果不显式传入，它保持不变。

### 误区七：以为它会判断 patch capability

不会。

书籍侧 capability 判断发生在 `BookMetadataLifecycle.refreshMetadata(...)`：

```text
capabilities.intersect(provider.capabilities).isEmpty()
```

`MetadataApplier` 接收到 patch 后，不再判断 provider 是否有能力提供这些字段。它只按 patch 值和字段锁合并。

### 误区八：以为它会对多个 series patch 做聚合

不会。

多个 `SeriesMetadataPatch` 的聚合发生在 `SeriesMetadataLifecycle.handlePatchForSeriesMetadata(patches: List<SeriesMetadataPatch>, series: Series)`。聚合完成后，才把单个 `SeriesMetadataPatch` 交给 `MetadataApplier`。

`MetadataApplier` 始终只处理一个 patch 和一个 metadata 的合并。
