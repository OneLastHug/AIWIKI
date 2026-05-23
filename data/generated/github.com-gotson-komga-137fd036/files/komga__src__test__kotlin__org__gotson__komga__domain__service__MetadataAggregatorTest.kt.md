# 文件：komga/src/test/kotlin/org/gotson/komga/domain/service/MetadataAggregatorTest.kt

## 它负责什么

`MetadataAggregatorTest.kt` 是 `MetadataAggregator` 的单元测试文件，用来验证“把多本书的 `BookMetadata` 汇总成一个 `BookMetadataAggregation`”时，核心聚合规则是否正确。

它不测试数据库、不测试 Spring 容器，也不测试完整业务流程，而是直接实例化：

```kotlin
private val aggregator = MetadataAggregator()
```

然后构造若干 `BookMetadata` 输入，调用：

```kotlin
aggregator.aggregate(metadatas)
```

最后用 AssertJ 断言聚合结果。

从测试覆盖面看，这个文件主要确认 4 类业务规则：

1. 多本书的 `authors` 会被合并，并按“角色 + 姓名”去重。
2. 多本书的 `tags` 会被合并，并去重。
3. 系列级 `releaseDate` 取所有书中最早的发布日期。
4. 系列级 `summary` 取按 `numberSort` 排序后第一本“有摘要”的书，并记录这本书的 `number` 到 `summaryNumber`。

这里的“系列级”是根据上下游代码推断的：`MetadataAggregator.aggregate()` 返回的是 `BookMetadataAggregation`，而调用方 `SeriesMetadataLifecycle.aggregateMetadata(series)` 会把聚合结果 `.copy(seriesId = series.id)` 后写入 `bookMetadataAggregationRepository`，因此它服务于某个 `Series` 下所有书籍 metadata 的聚合视图。

## 关键组成

这个测试文件位于包：

```kotlin
org.gotson.komga.domain.service
```

它导入的关键依赖有：

```kotlin
import org.assertj.core.api.Assertions.assertThat
import org.gotson.komga.domain.model.Author
import org.gotson.komga.domain.model.BookMetadata
import org.junit.jupiter.api.Test
import java.time.LocalDate
```

各 import 的作用如下：

- `assertThat`：AssertJ 断言入口，用来写可读性较高的测试断言，例如 `hasSize(4)`、`isEqualTo("summary 1")`。
- `Author`：书籍作者模型，包含 `name` 和 `role`。生产代码中 `Author.role` 会被 `trim().lowercase()` 规范化。
- `BookMetadata`：单本书的 metadata 输入模型，包含 `title`、`summary`、`number`、`numberSort`、`releaseDate`、`authors`、`tags` 等字段。
- `Test`：JUnit 5 的测试注解。
- `LocalDate`：构造发布日期，用来验证最早日期选择逻辑。

文件中只有一个测试类：

```kotlin
class MetadataAggregatorTest
```

类里只有一个被测对象：

```kotlin
private val aggregator = MetadataAggregator()
```

这说明测试不依赖 Spring 的 `@Service` 注入，属于纯单元测试。

第一个测试：

```kotlin
given metadatas when aggregating then aggregation is relevant
```

构造两本书：

- 第一本：`summary = "summary 1"`、`number = "1"`、`numberSort = 1F`、作者两个、日期 `2020-01-01`、标签 `tag1`
- 第二本：`summary = "summary 2"`、`number = "2"`、`numberSort = 2F`、作者两个、日期 `2021-01-01`、标签 `tag2`

断言结果：

```kotlin
aggregation.authors hasSize 4
aggregation.tags hasSize 2
aggregation.releaseDate?.year == 2020
aggregation.summary == "summary 1"
aggregation.summaryNumber == "1"
```

这里有一个容易忽略的点：第二本书里有 `Author("author2", "role3")`，第一本书里有 `Author("author2", "role2")`。虽然名字相同，但角色不同，所以不是重复作者。生产代码去重依据是：

```kotlin
distinctBy { "${it.role}__${it.name}" }
```

因此两个 `author2` 会被保留。

第二个测试：

```kotlin
given metadatas with summary only on second book when aggregating then aggregation has second book's summary
```

第一本没有摘要，第二本有摘要。断言聚合摘要来自第二本：

```kotlin
aggregation.summary == "summary 2"
aggregation.summaryNumber == "2"
```

这验证了 `MetadataAggregator` 不会盲目取第一本书，而是会在按 `numberSort` 排序后查找第一本 `summary.isNotBlank()` 的书。

第三个测试：

```kotlin
given metadatas with second book with earlier release date when aggregating then aggregation has release date from second book
```

第一本日期是 `2020-01-01`，第二本日期是 `2019-01-01`。虽然第二本 `numberSort` 更大，但聚合结果的 `releaseDate` 应该是 `2019`。

这对应生产逻辑：

```kotlin
val releaseDate = metadatas.mapNotNull { it.releaseDate }.minOrNull()
```

也就是说发布日期不是按卷号选，而是单纯取最早的非空日期。

第四个测试：

```kotlin
given metadatas with duplicate authors or tags when aggregating then aggregation has no duplicates
```

两本书有完全相同的两个作者，并且标签有重叠。断言：

```kotlin
aggregation.authors hasSize 2
aggregation.tags hasSize 2
```

它验证了作者和标签的去重行为。标签在 `BookMetadata` 构造时还会经过 `lowerNotBlank().toSet()`，因此空白标签会被过滤，大小写也可能被规范化为小写；不过这个测试只覆盖了简单重复场景，没有覆盖大小写和空白输入。

## 上下游关系

上游输入是多个 `BookMetadata` 对象。`BookMetadata` 是单本书 metadata 的领域模型，核心字段包括：

```kotlin
title
summary
number
numberSort
releaseDate
authors
tags
isbn
links
locks...
bookId
```

其中这个测试主要关心：

- `summary`
- `number`
- `numberSort`
- `releaseDate`
- `authors`
- `tags`

被测服务是：

```kotlin
komga/src/main/kotlin/org/gotson/komga/domain/service/MetadataAggregator.kt
```

它是一个 Spring `@Service`：

```kotlin
@Service
class MetadataAggregator
```

核心方法是：

```kotlin
fun aggregate(metadatas: Collection<BookMetadata>): BookMetadataAggregation
```

下游输出是：

```kotlin
BookMetadataAggregation
```

该模型位于：

```kotlin
komga/src/main/kotlin/org/gotson/komga/domain/model/BookMetadataAggregation.kt
```

字段包括：

```kotlin
authors
tags
releaseDate
summary
summaryNumber
seriesId
createdDate
lastModifiedDate
```

从调用方看，`MetadataAggregator` 由：

```kotlin
komga/src/main/kotlin/org/gotson/komga/domain/service/SeriesMetadataLifecycle.kt
```

使用。关键流程是：

```kotlin
val metadatas = bookMetadataRepository.findAllByIds(bookRepository.findAllIdsBySeriesId(series.id))
val aggregation = metadataAggregator.aggregate(metadatas).copy(seriesId = series.id)

bookMetadataAggregationRepository.update(aggregation)
eventPublisher.publishEvent(DomainEvent.SeriesUpdated(series))
```

也就是说，真实业务中它的上游是某个 `Series` 下所有 `Book` 的 metadata；下游是 `bookMetadataAggregationRepository`，用于保存这批书的聚合结果，并发布 `SeriesUpdated` 事件。

根据当前片段推断，这个聚合结果大概率用于系列详情页、搜索索引、筛选条件或其他展示层逻辑，让系列可以拥有从书籍汇总出来的作者、标签、最早发布日期和简介。

## 运行/调用流程

从测试视角看，流程是：

1. 创建 `MetadataAggregator`。
2. 手动构造一个 `List<BookMetadata>`。
3. 调用 `aggregate(metadatas)`。
4. 检查返回的 `BookMetadataAggregation`。

从生产代码视角看，`aggregate()` 内部流程是：

1. 聚合作者：

   ```kotlin
   val authors = metadatas.flatMap { it.authors }.distinctBy { "${it.role}__${it.name}" }
   ```

   它先把所有书的 `authors` 拉平成一个列表，再按 `role + name` 去重。注意这里不是只按姓名去重。

2. 聚合标签：

   ```kotlin
   val tags = metadatas.flatMap { it.tags }.toSet()
   ```

   所有书的标签合并成一个 `Set`，天然去重。

3. 选择摘要：

   ```kotlin
   val (summary, summaryNumber) =
     metadatas
       .sortedBy { it.numberSort }
       .find { it.summary.isNotBlank() }
       ?.let {
         it.summary to it.number
       } ?: ("" to "")
   ```

   这段逻辑很关键：先按 `numberSort` 排序，再找第一条非空摘要。如果找到了，摘要来自那本书，同时 `summaryNumber` 记录那本书的 `number`。如果所有书都没有摘要，则结果是空字符串和空字符串。

4. 选择发布日期：

   ```kotlin
   val releaseDate = metadatas.mapNotNull { it.releaseDate }.minOrNull()
   ```

   忽略空日期，取最早日期。

5. 返回聚合对象：

   ```kotlin
   BookMetadataAggregation(
     authors = authors,
     tags = tags,
     releaseDate = releaseDate,
     summary = summary,
     summaryNumber = summaryNumber
   )
   ```

测试文件的 4 个测试分别对上面第 1、2、3、4 步建立了行为保护。

## 小白阅读顺序

建议按下面顺序阅读：

1. 先看 `MetadataAggregatorTest.kt` 的类开头，理解它直接 new 了 `MetadataAggregator`，没有 mock、没有 Spring 上下文。
2. 看第一个测试，它是综合样例，覆盖作者、标签、发布日期、摘要和摘要来源卷号。
3. 打开 `komga/src/main/kotlin/org/gotson/komga/domain/service/MetadataAggregator.kt`，对照第一个测试理解 `flatMap`、`distinctBy`、`toSet`、`sortedBy`、`find`、`minOrNull` 分别在做什么。
4. 回到第二个测试，重点理解“摘要不是必须来自第一本书，而是来自按 `numberSort` 排序后的第一本有摘要的书”。
5. 看第三个测试，确认 `releaseDate` 的规则和摘要规则不同：日期取全局最早，不受 `numberSort` 控制。
6. 看第四个测试，理解作者和标签去重的差异：作者按 `role + name` 去重，标签靠 `Set` 去重。
7. 最后看 `SeriesMetadataLifecycle.aggregateMetadata(series)`，理解这个聚合服务在真实业务中什么时候被调用：系列 metadata 生命周期里从书籍 metadata 汇总出系列相关的聚合信息。

如果是 Kotlin 新手，建议特别留意这些语法：

- 反引号函数名：测试方法名可以写成自然语言，例如 ``fun `given metadatas when aggregating then aggregation is relevant`()``。
- 命名参数：`BookMetadata(title = "ignored", number = "1", numberSort = 1F)`。
- 空安全调用：`aggregation.releaseDate?.year`。
- Elvis 操作符：`?: ("" to "")`。
- Pair 解构：`val (summary, summaryNumber) = ...`。

## 常见误区

第一个误区：以为作者只按名字去重。实际生产代码是按 `"${it.role}__${it.name}"` 去重，所以同名但不同角色会保留。测试一中 `author2` 出现了两次，但角色分别是 `role2` 和 `role3`，因此最终作者数量是 4，不是 3。

第二个误区：以为摘要总是来自第一本输入书。实际逻辑先按 `numberSort` 排序，再找第一本非空摘要。输入列表顺序不是核心依据，`numberSort` 才是摘要选择的排序依据。

第三个误区：以为发布日期也跟 `numberSort` 有关。发布日期完全独立处理，取所有非空 `releaseDate` 中最早的一个。第三个测试里第二本书日期更早，所以聚合结果来自第二本。

第四个误区：忽略 `BookMetadata` 构造器里的规范化。`title`、`summary`、`number` 会 `trim()`；`tags` 会经过 `lowerNotBlank().toSet()`；`Author.role` 会转成小写。当前测试没有覆盖这些规范化细节，但真实输入会受到它们影响。

第五个误区：把这个测试理解成集成测试。它不是集成测试。它没有启动 Spring，也没有访问 repository，只验证 `MetadataAggregator.aggregate()` 的纯内存逻辑。真正把结果写入仓库的是 `SeriesMetadataLifecycle.aggregateMetadata(series)`。

第六个误区：以为 `BookMetadataAggregation.seriesId` 由 `MetadataAggregator` 设置。实际上 `MetadataAggregator.aggregate()` 只产生通用聚合结果；调用方 `SeriesMetadataLifecycle` 会在之后执行 `.copy(seriesId = series.id)`。因此这个测试不会断言 `seriesId`。

第七个误区：认为 `summaryNumber` 是书籍排序号 `numberSort`。它实际保存的是那本摘要来源书的 `number` 字符串，例如 `"1"`、`"2"`，不是 `1F`、`2F`。
