# 文件：komga/src/main/kotlin/org/gotson/komga/domain/service/SeriesMetadataLifecycle.kt

## 它负责什么

`SeriesMetadataLifecycle` 是 Komga 领域层里负责“系列元数据生命周期”的 Spring 服务，类上标注了 `@Service`。它主要做两件事：

1. 刷新某个 `Series` 的元数据：从书籍文件、系列级 provider 中提取 `SeriesMetadataPatch`，再把 patch 应用到当前系列元数据并落库。
2. 聚合某个 `Series` 下所有书籍的元数据：把每本书的作者、标签、发布日期、简介等聚合成 `BookMetadataAggregation`，供系列层面展示或查询使用。

它不是扫描器，也不是任务调度器。调度入口在 `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskHandler.kt`，其中 `Task.RefreshSeriesMetadata` 会调用 `seriesMetadataLifecycle.refreshMetadata(series)`，随后再派发 `AggregateSeriesMetadata` 任务；`Task.AggregateSeriesMetadata` 会调用 `seriesMetadataLifecycle.aggregateMetadata(series)`。

简单说，这个文件是“系列元数据刷新与聚合的执行器”。

## 关键组成

### 类与依赖

`SeriesMetadataLifecycle` 构造函数注入了多类依赖：

- `seriesMetadataFromBookProviders: List<SeriesMetadataFromBookProvider>`  
  从单本书中提取系列级元数据的 provider。例如 ComicInfo、EPUB 这类文件内嵌信息可以提供系列标题、状态、出版社、集合等字段。

- `seriesMetadataProviders: List<SeriesMetadataProvider>`  
  直接从 `Series` 对象或系列级上下文提取元数据的 provider。和上一类不同，它不逐本书读取。

- `metadataApplier: MetadataApplier`  
  负责把 `SeriesMetadataPatch` 应用到已有 `SeriesMetadata` 上。它会尊重字段锁定，例如 `titleLock`、`summaryLock`、`genresLock` 等；如果字段被锁，patch 不会覆盖原值。

- `metadataAggregator: MetadataAggregator`  
  负责把多个 `BookMetadata` 聚合成 `BookMetadataAggregation`。例如聚合作者、标签、最早发布日期，以及取第一本有简介的书作为系列摘要来源。

- 多个 repository  
  包括 `MediaRepository`、`BookMetadataRepository`、`SeriesMetadataRepository`、`BookMetadataAggregationRepository`、`LibraryRepository`、`BookRepository`。这些分别负责读取书籍媒体、书籍元数据、系列元数据、聚合结果、library 配置和 series 下的 book 列表。

- `collectionLifecycle: SeriesCollectionLifecycle`  
  当 provider 提供了 collections 信息时，用它把当前 series 加入对应 collection，必要时会创建新 collection。

- `eventPublisher: ApplicationEventPublisher`  
  用于发布 `DomainEvent.SeriesUpdated(series)`，通知系统其它部分：这个 series 的元数据或聚合信息已经变化。

### `refreshMetadata(series: Series)`

这是刷新系列元数据的主方法。逻辑分两大段：

第一段处理 `SeriesMetadataFromBookProvider`：

```kotlin
seriesMetadataFromBookProviders.forEach { provider -> ... }
```

它会先读取当前 series 所属的 library：

```kotlin
val library = libraryRepository.findById(series.libraryId)
```

然后根据 provider 和 library 配置判断是否允许处理：

```kotlin
provider.shouldLibraryHandlePatch(library, MetadataPatchTarget.SERIES)
provider.shouldLibraryHandlePatch(library, MetadataPatchTarget.COLLECTION)
```

也就是说，是否导入系列元数据、是否导入 collection 元数据，不是这个类硬编码决定的，而是由 provider 结合 library 配置判断。

如果允许处理，它会读取该 series 下所有 book：

```kotlin
bookRepository.findAllBySeriesId(series.id)
```

对每本书再读取对应 media：

```kotlin
mediaRepository.findById(book.id)
```

然后组合成 `BookWithMedia`，交给 provider：

```kotlin
provider.getSeriesMetadataFromBook(
  BookWithMedia(book, mediaRepository.findById(book.id)),
  library.importComicInfoSeriesAppendVolume,
)
```

这里的 `library.importComicInfoSeriesAppendVolume` 表明某些 provider 在生成 series 标题时可能支持把 volume 追加到标题中。接口 `SeriesMetadataFromBookProvider` 也暴露了 `supportsAppendVolume`，说明这是 provider 能力之一。

第二段处理 `SeriesMetadataProvider`：

```kotlin
seriesMetadataProviders.forEach { provider -> ... }
```

这类 provider 不逐本 book 读取，而是直接：

```kotlin
provider.getSeriesMetadata(series)
```

拿到一个 `SeriesMetadataPatch?` 后，调用同一个 `handlePatchForSeriesMetadata(patch, series)` 应用并保存。

### `handlePatchForSeriesMetadata(patches: List<SeriesMetadataPatch>, series: Series)`

这个私有方法用于处理“从多本书得到多个 series patch”的场景。它不会简单用第一本书的结果，而是先把多个 patch 聚合成一个 patch：

- `title`、`titleSort`、`status`、`language`、`readingDirection`、`publisher` 使用 `mostFrequent`，即取最常出现的值。
- `genres` 会收集所有非空 genre，拍平成集合去重。
- `ageRating` 取最大值。
- `totalBookCount` 取最大值。
- `summary` 固定为 `null`。
- `collections` 固定为空集合，因为 collection 在前面的刷新逻辑中单独处理，不参与写入 `SeriesMetadata`。

这个设计说明：从书籍反推系列元数据时，Komga 尽量用“多数值”来避免单本书的异常数据污染整个系列；对年龄分级、总册数这类字段则选择最大值。

### `handlePatchForSeriesMetadata(patch: SeriesMetadataPatch?, series: Series)`

这个重载方法是真正落库的位置。

流程是：

1. patch 为 `null` 时直接跳过。
2. 用 `seriesMetadataRepository.findById(series.id)` 读取当前系列元数据。
3. 调用 `metadataApplier.apply(sPatch, it)` 生成新元数据。
4. 用 `seriesMetadataRepository.update(patched)` 更新数据库。

关键点是，字段覆盖规则不在这个文件里，而在 `MetadataApplier`。`MetadataApplier.apply(patch: SeriesMetadataPatch, metadata: SeriesMetadata)` 会对每个字段调用类似逻辑：

```kotlin
if (patched != null && !lock) patched else original
```

因此，即使 provider 给出了新标题、新 genre、新 publisher，只要对应字段 lock 为 true，就不会覆盖用户手动维护的数据。

### `aggregateMetadata(series: Series)`

这个方法负责书籍元数据聚合，不直接修改 `SeriesMetadata`，而是更新 `BookMetadataAggregation`。

流程是：

1. 查出 series 下所有 book id：

```kotlin
bookRepository.findAllIdsBySeriesId(series.id)
```

2. 查出这些 book 的 `BookMetadata`：

```kotlin
bookMetadataRepository.findAllByIds(...)
```

3. 调用 `metadataAggregator.aggregate(metadatas)` 聚合。
4. 把聚合结果绑定到当前 series：

```kotlin
.copy(seriesId = series.id)
```

5. 更新聚合表：

```kotlin
bookMetadataAggregationRepository.update(aggregation)
```

6. 发布 `DomainEvent.SeriesUpdated(series)`。

根据 `MetadataAggregator.kt`，聚合规则包括：

- `authors`：合并所有书籍作者，按 `role + name` 去重。
- `tags`：合并为集合。
- `summary`：按 `numberSort` 排序，取第一本有非空 summary 的书。
- `summaryNumber`：记录该 summary 来自哪一册。
- `releaseDate`：取最早发布日期。

## 上下游关系

### 上游：谁调用它

主要调用方在任务系统：

- `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskHandler.kt`
- `komga/src/main/kotlin/org/gotson/komga/application/tasks/Task.kt`

任务流大致是：

1. `Task.RefreshBookMetadata` 刷新单本书元数据。
2. 刷新完单本书后，`TaskHandler` 调用 `taskEmitter.refreshSeriesMetadata(book.seriesId, ...)`。
3. `Task.RefreshSeriesMetadata` 被执行时，调用 `SeriesMetadataLifecycle.refreshMetadata(series)`。
4. 刷新 series 元数据后，继续派发 `AggregateSeriesMetadata`。
5. `Task.AggregateSeriesMetadata` 被执行时，调用 `SeriesMetadataLifecycle.aggregateMetadata(series)`。

这说明 series 元数据刷新通常是 book 元数据刷新之后的后续任务。

### 下游：它调用谁

`SeriesMetadataLifecycle` 的下游可以分成几类：

- 元数据 provider  
  `SeriesMetadataFromBookProvider`、`SeriesMetadataProvider` 负责产生 `SeriesMetadataPatch`。这个类只编排 provider，不关心具体解析 ComicInfo、EPUB 或其它格式的细节。

- 元数据应用器  
  `MetadataApplier` 负责处理 patch 与 lock 规则。

- 元数据聚合器  
  `MetadataAggregator` 负责从 `BookMetadata` 生成 `BookMetadataAggregation`。

- 持久化仓库  
  `SeriesMetadataRepository` 更新 series metadata；`BookMetadataAggregationRepository` 更新聚合结果；`BookRepository`、`MediaRepository`、`BookMetadataRepository`、`LibraryRepository` 提供读取能力。

- collection 生命周期  
  `SeriesCollectionLifecycle.addSeriesToCollection(collectionName, series)` 会根据 provider 给出的 collection 名称，把 series 加入 collection。如果 collection 不存在，会创建。

- 事件系统  
  `ApplicationEventPublisher` 发布 `DomainEvent.SeriesUpdated(series)`。其它监听器可以据此刷新索引、通知 UI、更新缓存或执行后续动作。具体监听者不在当前片段中展开；根据当前片段推断，它是 Komga 内部领域事件机制的一部分，依据是 `DomainEvent.kt` 定义了 `SeriesUpdated`，且多个 lifecycle 都通过 `eventPublisher.publishEvent(...)` 发布领域事件。

### 与配置的关系

是否导入 metadata 由 provider 的：

```kotlin
shouldLibraryHandlePatch(library, target)
```

决定。这里的 `target` 可以是：

- `MetadataPatchTarget.SERIES`
- `MetadataPatchTarget.COLLECTION`

因此同一个 provider 可能被允许导入 series metadata，但不允许导入 collection；也可能反过来只处理 collection。`refreshMetadata` 中的判断正是围绕这两个 target 展开的。

## 运行/调用流程

### 刷新 series metadata

完整流程可以按下面理解：

1. 外部任务系统拿到 `seriesId`，加载 `Series`。
2. `TaskHandler` 调用 `seriesMetadataLifecycle.refreshMetadata(series)`。
3. `SeriesMetadataLifecycle` 根据 `series.libraryId` 加载 `Library`。
4. 遍历所有 `SeriesMetadataFromBookProvider`。
5. 对每个 provider，先判断当前 library 是否允许它处理 `SERIES` 或 `COLLECTION`。
6. 如果不允许，记录日志并跳过。
7. 如果允许，读取当前 series 下所有 book。
8. 对每本 book 读取 media，封装成 `BookWithMedia`。
9. 调用 provider 从每本书中提取 `SeriesMetadataPatch?`。
10. 如果 provider 允许处理 `SERIES`，把多个 patch 聚合成一个 patch。
11. 用 `MetadataApplier` 将 patch 应用到当前 `SeriesMetadata`。
12. 通过 `SeriesMetadataRepository.update(...)` 保存。
13. 如果 provider 允许处理 `COLLECTION`，读取所有 patch 中的 `collections`，去重后逐个调用 `SeriesCollectionLifecycle.addSeriesToCollection(...)`。
14. 遍历所有 `SeriesMetadataProvider`。
15. 对每个 provider，判断当前 library 是否允许处理 `SERIES`。
16. 如果允许，直接基于 `Series` 获取一个 patch。
17. 应用 patch 并保存。
18. 只要有 provider 尝试处理过 series patch，就把 `changed` 置为 true。
19. 最后如果 `changed == true`，发布 `DomainEvent.SeriesUpdated(series)`。

这里有一个细节：`changed` 的含义更接近“执行过 series metadata patch 流程”，不一定代表数据库字段实际发生变化。因为 `handlePatchForSeriesMetadata` 内部没有比较 `patched` 和原 metadata 是否相等，只要 provider 配置允许处理 series，外层就会设置 `changed = true`。

### 聚合 book metadata

聚合流程独立于刷新流程：

1. 外部任务系统执行 `Task.AggregateSeriesMetadata`。
2. `TaskHandler` 调用 `seriesMetadataLifecycle.aggregateMetadata(series)`。
3. 查出该 series 下所有 book id。
4. 查出所有 book metadata。
5. 使用 `MetadataAggregator.aggregate(...)` 聚合。
6. 设置 `seriesId`。
7. 更新 `BookMetadataAggregationRepository`。
8. 发布 `DomainEvent.SeriesUpdated(series)`。

注意：`aggregateMetadata` 不调用 provider，也不读取文件 media。它只基于已经落库的 book metadata 做汇总。

### 异常处理

在 provider 提取 metadata 时，每本书或每个 series 的 provider 调用都包了一层 `try/catch`：

```kotlin
try {
  ...
} catch (e: Exception) {
  logger.error(e) { ... }
  null
}
```

这意味着某个 provider 解析失败不会中断整个 series 的刷新。失败的 book 会返回 `null`，后续通过 `mapNotNull` 排除；失败的 series provider 也会返回 `null`，不落库。

## 小白阅读顺序

1. 先看 `SeriesMetadataLifecycle.refreshMetadata(series)`  
   这是主流程，先不用纠结每个 provider 的具体实现，只要理解它在“遍历 provider、拿 patch、应用 patch”。

2. 再看 `SeriesMetadataPatch`  
   路径是 `komga/src/main/kotlin/org/gotson/komga/domain/model/SeriesMetadataPatch.kt`。它定义了 provider 能修改哪些 series 字段：`title`、`titleSort`、`status`、`summary`、`readingDirection`、`publisher`、`ageRating`、`language`、`genres`、`totalBookCount`、`collections`。

3. 再看两个 provider 接口  
   路径是 `komga/src/main/kotlin/org/gotson/komga/infrastructure/metadata/SeriesMetadataFromBookProvider.kt` 和 `komga/src/main/kotlin/org/gotson/komga/infrastructure/metadata/SeriesMetadataProvider.kt`。重点区分：
   - `SeriesMetadataFromBookProvider`：从 book + media 中推导 series metadata。
   - `SeriesMetadataProvider`：直接从 series 中获取 series metadata。

4. 然后看 `MetadataApplier`  
   路径是 `komga/src/main/kotlin/org/gotson/komga/domain/service/MetadataApplier.kt`。这里能理解为什么用户锁定字段后，导入元数据不会覆盖它。

5. 接着看 `aggregateMetadata(series)` 和 `MetadataAggregator`  
   路径是 `komga/src/main/kotlin/org/gotson/komga/domain/service/MetadataAggregator.kt`。这部分和 provider 无关，是从 book metadata 汇总 series 展示信息。

6. 最后看 `TaskHandler`  
   路径是 `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskHandler.kt`。理解这个类如何被后台任务触发，以及为什么刷新 book metadata 后会继续刷新 series metadata。

## 常见误区

1. 误以为这个类负责解析 ComicInfo 或 EPUB  
   实际解析逻辑在具体 provider 中。`SeriesMetadataLifecycle` 只是编排 provider，统一处理 patch、落库、事件发布和 collection 副作用。

2. 误以为 `refreshMetadata` 一定会改变数据库  
   不一定。provider 可能返回 `null`，也可能返回的字段都被 lock，或者 patch 内容和原值相同。但只要配置允许处理 series patch，外层仍可能发布 `SeriesUpdated` 事件。

3. 误以为 `collections` 会写入 `SeriesMetadata`  
   不会。`SeriesMetadataPatch` 中虽然有 `collections` 字段，但在从多本书聚合 patch 时，写入 series metadata 的聚合 patch 把 `collections` 设为 `emptySet()`。collection 的处理走的是 `SeriesCollectionLifecycle.addSeriesToCollection(...)`，它会修改 collection 关系，而不是写进 `SeriesMetadata`。

4. 误以为 `aggregateMetadata` 和 `refreshMetadata` 是同一件事  
   不是。`refreshMetadata` 是 provider 驱动的元数据导入，目标是 `SeriesMetadataRepository`；`aggregateMetadata` 是基于已存在的 `BookMetadata` 做汇总，目标是 `BookMetadataAggregationRepository`。

5. 误以为字段覆盖无条件发生  
   实际覆盖由 `MetadataApplier` 控制。只要原 metadata 对应字段有 lock，patch 就不会覆盖原值。例如 `titleLock == true` 时，provider 给出的 `title` 会被忽略。

6. 误以为从书籍提取 series metadata 时会使用第一本书的数据  
   不是简单取第一本。多个 `SeriesMetadataPatch` 会先聚合：多数值字段取最常见值，`genres` 合并去重，`ageRating` 和 `totalBookCount` 取最大值。

7. 误以为 provider 失败会导致整个任务失败  
   当前代码对 provider 调用做了异常捕获。单本书解析失败或某个 provider 失败会记录 error 日志并跳过，不会直接中断整个 series 刷新流程。

8. 误以为 `DomainEvent.SeriesUpdated` 只在 series 基础信息变化时发布  
   这里刷新 series metadata 和更新 book metadata aggregation 后都会发布 `SeriesUpdated`。因此这个事件更像“series 相关展示数据可能需要刷新”的通知，而不只是 series 表本身变化。
