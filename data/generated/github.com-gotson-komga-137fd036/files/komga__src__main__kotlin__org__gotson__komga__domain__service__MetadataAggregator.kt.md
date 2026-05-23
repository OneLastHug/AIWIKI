# 文件：komga/src/main/kotlin/org/gotson/komga/domain/service/MetadataAggregator.kt

## 它负责什么

`MetadataAggregator.kt` 定义了领域服务 `MetadataAggregator`，职责非常集中：把同一个 series 下多本书的 `BookMetadata` 汇总成一个 `BookMetadataAggregation`。

在 Komga 的领域模型里，每本书都有自己的元数据，例如作者、标签、发布日期、简介、卷号/册号等；而 series 页面或 series 级别的展示、搜索、更新通知等场景，往往需要一个“从书籍元数据汇总出来的系列级摘要”。`MetadataAggregator` 就是做这个汇总的地方。

它不负责读取数据库，也不负责保存结果；它只接收：

```kotlin
Collection<BookMetadata>
```

然后返回：

```kotlin
BookMetadataAggregation
```

因此它是一个纯业务聚合器，输入输出明确，副作用很少。类上标注了 `@Service`，说明它由 Spring 容器管理，并被其他领域服务注入使用。

## 关键组成

这个文件的 import 很少，能直接看出它的边界：

```kotlin
import org.gotson.komga.domain.model.BookMetadata
import org.gotson.komga.domain.model.BookMetadataAggregation
import org.springframework.stereotype.Service
```

含义分别是：

- `BookMetadata`：单本书的元数据模型，来自 `komga/src/main/kotlin/org/gotson/komga/domain/model/BookMetadata.kt`。
- `BookMetadataAggregation`：聚合后的系列级书籍元数据摘要，来自 `komga/src/main/kotlin/org/gotson/komga/domain/model/BookMetadataAggregation.kt`。
- `@Service`：Spring 注解，让 `MetadataAggregator` 成为可注入的服务组件。

核心类只有一个：

```kotlin
@Service
class MetadataAggregator {
  fun aggregate(metadatas: Collection<BookMetadata>): BookMetadataAggregation {
    ...
  }
}
```

`aggregate` 方法内部聚合了四类信息。

第一类是 `authors`：

```kotlin
val authors = metadatas.flatMap { it.authors }.distinctBy { "${it.role}__${it.name}" }
```

它会把所有书的作者列表展开成一个大列表，然后按 `role + name` 去重。

这里的去重规则很重要：同名但不同角色的作者会被视为不同作者。例如某人既是 `writer` 又是 `artist`，理论上会保留两条；同一个 `role` 和同一个 `name` 的重复项只保留第一次出现的那条。

第二类是 `tags`：

```kotlin
val tags = metadatas.flatMap { it.tags }.toSet()
```

它会合并所有书籍标签，并转成 `Set` 去重。根据 `BookMetadata` 的定义，`tags` 在模型构造时已经经过 `lowerNotBlank()` 处理，也就是空标签会被过滤，并且标签会被规范化为小写。`MetadataAggregator` 这里不再重复做清洗，只做集合合并。

第三类是 `summary` 和 `summaryNumber`：

```kotlin
val (summary, summaryNumber) =
  metadatas
    .sortedBy { it.numberSort }
    .find { it.summary.isNotBlank() }
    ?.let {
      it.summary to it.number
    } ?: ("" to "")
```

这里的规则是：先按 `numberSort` 排序，然后找第一本有非空 `summary` 的书。找到后，把这本书的 `summary` 作为聚合摘要，同时把这本书的 `number` 记录到 `summaryNumber`。

这意味着聚合摘要不是拼接所有简介，也不是取最长简介，而是取排序最靠前且简介不为空的那本书的简介。

如果没有任何一本书有简介，则返回：

```kotlin
summary = ""
summaryNumber = ""
```

第四类是 `releaseDate`：

```kotlin
val releaseDate = metadatas.mapNotNull { it.releaseDate }.minOrNull()
```

它会取所有非空发布日期中的最早日期。也就是说，聚合后的 `releaseDate` 更像是这个 series 中已知最早一本书的发布日期，而不是最新发布日期。

最后构造结果：

```kotlin
return BookMetadataAggregation(
  authors = authors,
  tags = tags,
  releaseDate = releaseDate,
  summary = summary,
  summaryNumber = summaryNumber
)
```

注意这里没有设置 `seriesId`。`seriesId` 是由调用方在外部补上的。

## 上下游关系

上游输入主要来自书籍元数据仓库。调用方位于：

`komga/src/main/kotlin/org/gotson/komga/domain/service/SeriesMetadataLifecycle.kt`

其中 `aggregateMetadata(series: Series)` 会执行：

```kotlin
val metadatas = bookMetadataRepository.findAllByIds(bookRepository.findAllIdsBySeriesId(series.id))
val aggregation = metadataAggregator.aggregate(metadatas).copy(seriesId = series.id)
```

这里可以看出完整上游链路：

1. `bookRepository.findAllIdsBySeriesId(series.id)` 找出某个 series 下所有 book id。
2. `bookMetadataRepository.findAllByIds(...)` 根据 book id 批量读取 `BookMetadata`。
3. `metadataAggregator.aggregate(metadatas)` 对这些书籍元数据做聚合。
4. `.copy(seriesId = series.id)` 给聚合结果补上所属 series id。

下游主要是聚合结果仓库：

```kotlin
bookMetadataAggregationRepository.update(aggregation)
```

也就是 `BookMetadataAggregation` 最终会被保存或更新到 `BookMetadataAggregationRepository` 对应的持久化实现中。

然后调用方还会发布事件：

```kotlin
eventPublisher.publishEvent(DomainEvent.SeriesUpdated(series))
```

说明聚合后的元数据变化会被系统视为 series 更新，可能进一步触发缓存刷新、索引更新、WebSocket 通知或其他监听逻辑。根据当前片段推断，具体事件消费者不在本次阅读范围内，但 `DomainEvent.SeriesUpdated(series)` 表明这是一个领域事件入口。

相关模型关系如下：

- `BookMetadata`：单本书的元数据，包含 `title`、`summary`、`number`、`numberSort`、`releaseDate`、`authors`、`tags`、`isbn`、`links` 和各种 lock 字段。
- `BookMetadataAggregation`：系列级聚合结果，包含 `authors`、`tags`、`releaseDate`、`summary`、`summaryNumber`、`seriesId` 和审计字段。
- `SeriesMetadataLifecycle`：负责 series 元数据生命周期，其中 `aggregateMetadata` 使用 `MetadataAggregator`。
- `BookMetadataRepository`、`BookRepository`：提供上游书籍元数据和书籍 id。
- `BookMetadataAggregationRepository`：保存下游聚合结果。

## 运行/调用流程

典型调用流程从 `SeriesMetadataLifecycle.aggregateMetadata(series)` 开始。

第一步，调用方收到一个 `Series`：

```kotlin
fun aggregateMetadata(series: Series)
```

这个方法表示“为某个 series 重新聚合它下面所有书的元数据”。

第二步，查出这个 series 下的所有书籍 id：

```kotlin
bookRepository.findAllIdsBySeriesId(series.id)
```

第三步，根据这些 id 查出对应的 `BookMetadata`：

```kotlin
bookMetadataRepository.findAllByIds(...)
```

第四步，交给 `MetadataAggregator`：

```kotlin
metadataAggregator.aggregate(metadatas)
```

进入 `aggregate` 后，内部按以下顺序计算：

1. 展开所有书的 `authors`，按 `role + name` 去重。
2. 展开所有书的 `tags`，转为 `Set` 去重。
3. 按 `numberSort` 排序，找到第一条非空 `summary`，同时记录它的 `number`。
4. 收集所有非空 `releaseDate`，取最早日期。
5. 构造 `BookMetadataAggregation` 返回。

第五步，调用方补齐 `seriesId`：

```kotlin
.copy(seriesId = series.id)
```

这说明 `MetadataAggregator` 本身并不知道这些 metadata 属于哪个 series。它只负责“纯聚合”，不关心聚合对象的身份。

第六步，调用方保存聚合结果：

```kotlin
bookMetadataAggregationRepository.update(aggregation)
```

第七步，发布 series 更新事件：

```kotlin
eventPublisher.publishEvent(DomainEvent.SeriesUpdated(series))
```

可以把这条链路理解为：

`Series` -> 找书 -> 找书的元数据 -> 聚合 -> 保存聚合结果 -> 通知 series 已更新

## 小白阅读顺序

建议先读 `MetadataAggregator.kt` 本身，因为它非常短，能快速建立主线：

`komga/src/main/kotlin/org/gotson/komga/domain/service/MetadataAggregator.kt`

重点看 `aggregate` 方法里四个局部变量：

- `authors`
- `tags`
- `summary, summaryNumber`
- `releaseDate`

然后读输入模型：

`komga/src/main/kotlin/org/gotson/komga/domain/model/BookMetadata.kt`

这里要关注几个字段：

- `summary`：书籍简介，会被 trim。
- `number`：书籍编号或卷号文本，用于记录 `summaryNumber`。
- `numberSort`：排序用数字，决定哪本书的简介优先。
- `releaseDate`：发布日期，聚合时取最早值。
- `authors`：作者列表，聚合时按角色和姓名去重。
- `tags`：标签集合，在模型内会被小写化和去空。

接着读输出模型：

`komga/src/main/kotlin/org/gotson/komga/domain/model/BookMetadataAggregation.kt`

它的字段和 `MetadataAggregator` 的返回值一一对应。这里要注意 `seriesId` 虽然在模型里，但不是由 `MetadataAggregator` 设置，而是由调用方设置。

最后读调用方：

`komga/src/main/kotlin/org/gotson/komga/domain/service/SeriesMetadataLifecycle.kt`

重点看 `aggregateMetadata(series: Series)`。这个方法能帮助你理解 `MetadataAggregator` 在真实业务流程里什么时候被调用、输入从哪里来、结果保存到哪里。

阅读时可以按这个问题链来理解：

1. “一本书的元数据长什么样？”看 `BookMetadata`。
2. “多本书聚合后要存哪些字段？”看 `BookMetadataAggregation`。
3. “具体怎么聚合？”看 `MetadataAggregator.aggregate`。
4. “谁调用它，聚合结果去哪？”看 `SeriesMetadataLifecycle.aggregateMetadata`。

## 常见误区

第一个误区：以为 `MetadataAggregator` 会更新数据库。

它不会。它没有注入 repository，也没有调用 `update`、`insert` 之类的方法。数据库更新发生在 `SeriesMetadataLifecycle.aggregateMetadata` 中：

```kotlin
bookMetadataAggregationRepository.update(aggregation)
```

`MetadataAggregator` 只是计算结果。

第二个误区：以为聚合摘要会合并所有书籍简介。

实际不是。它只取一本书的简介。规则是先按 `numberSort` 升序排序，然后取第一本 `summary` 非空的书。这个设计更像是为 series 找一个代表性摘要，而不是生成完整目录式介绍。

第三个误区：以为 `releaseDate` 是最新出版日期。

实际代码使用的是：

```kotlin
minOrNull()
```

所以取的是最早的非空发布日期，不是最新日期。如果要理解成业务含义，它更接近“这个 series 最早可知的发布日期”。

第四个误区：以为作者只按名字去重。

代码使用：

```kotlin
distinctBy { "${it.role}__${it.name}" }
```

所以去重键包含 `role` 和 `name`。同一个名字如果角色不同，会保留多条。

第五个误区：以为 `MetadataAggregator` 会处理锁定字段。

`BookMetadata` 中有很多 lock 字段，例如 `summaryLock`、`authorsLock`、`tagsLock` 等。但 `MetadataAggregator` 完全不看这些字段。锁定字段更可能用于元数据 patch/apply 阶段，例如 `MetadataApplier` 之类的服务。根据当前片段推断，聚合阶段只基于当前已经存在的最终 `BookMetadata` 值，不再判断这些值是否来自锁定或自动导入。

第六个误区：以为 `MetadataAggregator` 会设置 `seriesId`。

它返回的 `BookMetadataAggregation` 默认 `seriesId` 是空字符串，因为构造时没有传入 `seriesId`。真正设置发生在调用方：

```kotlin
metadataAggregator.aggregate(metadatas).copy(seriesId = series.id)
```

这说明聚合器被设计成只关心集合内容，不关心集合归属。

第七个误区：忽略空集合行为。

如果传入空的 `metadatas`，代码不会抛异常。结果大致是：

- `authors = emptyList()`
- `tags = emptySet()`
- `releaseDate = null`
- `summary = ""`
- `summaryNumber = ""`

这来自 Kotlin 标准库行为：空集合 `flatMap` 为空，`toSet` 为空，`find` 找不到会走默认值，`minOrNull` 对空集合返回 `null`。
