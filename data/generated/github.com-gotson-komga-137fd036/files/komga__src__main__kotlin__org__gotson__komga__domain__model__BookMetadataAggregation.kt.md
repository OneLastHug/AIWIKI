# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/BookMetadataAggregation.kt

## 它负责什么

`BookMetadataAggregation.kt` 定义了领域模型 `BookMetadataAggregation`，用于表示“某个系列下所有书籍元数据的聚合结果”。

在 Komga 的领域里，单本书有自己的 `BookMetadata`，包含标题、简介、编号、发布日期、作者、标签等信息；而一个 `Series` 页面或查询场景往往需要展示“这一整套书的汇总信息”，例如：

- 这一系列涉及哪些作者；
- 这一系列有哪些标签；
- 这一系列的发布日期代表值；
- 这一系列可展示的汇总简介；
- 汇总简介来自哪一本书的编号；
- 这些聚合元数据属于哪个 `seriesId`；
- 这条聚合记录何时创建、何时更新。

`BookMetadataAggregation` 就是这个“系列级书籍元数据汇总”的承载对象。它本身不做计算，只负责保存聚合后的结果。实际聚合逻辑在调用方，例如 `org.gotson.komga.domain.service.MetadataAggregator` 中完成；持久化由 `BookMetadataAggregationRepository` 及其 jOOQ 实现处理。

## 关键组成

这个文件位于包：

```kotlin
package org.gotson.komga.domain.model
```

它导入了两个 Java 时间类型：

```kotlin
import java.time.LocalDate
import java.time.LocalDateTime
```

其中：

- `LocalDate` 用于 `releaseDate`，只关心日期，不关心具体时间；
- `LocalDateTime` 用于审计字段 `createdDate`、`lastModifiedDate`，表示创建和修改时间。

核心定义是一个 Kotlin `data class`：

```kotlin
data class BookMetadataAggregation(
  val authors: List<Author> = emptyList(),
  val tags: Set<String> = emptySet(),
  val releaseDate: LocalDate? = null,
  val summary: String = "",
  val summaryNumber: String = "",
  val seriesId: String = "",
  override val createdDate: LocalDateTime = LocalDateTime.now(),
  override val lastModifiedDate: LocalDateTime = createdDate,
) : Auditable
```

各字段含义如下。

`authors: List<Author>`

表示聚合后的作者列表。`Author` 定义在同目录的 `Author.kt` 中，它包含 `name` 和 `role`。构造时会对 `name` 做 `trim()`，对 `role` 做 `trim().lowercase()`，所以作者角色会被标准化成小写。

这里使用 `List<Author>`，说明作者顺序可能有意义。比如来自元数据聚合时，调用方可能希望保留某种稳定顺序。当前文件本身不去重、不排序，也不校验作者内容。

`tags: Set<String>`

表示聚合后的标签集合。使用 `Set` 说明标签天然是去重集合。默认值是空集合。

需要注意，`BookMetadata.kt` 中的 `BookMetadata` 会通过 `lowerNotBlank().toSet()` 对单本书的标签做小写化和空值过滤；但 `BookMetadataAggregation` 自身只是接收一个 `Set<String>`，没有在构造器里再次标准化。因此标签是否已清洗，依赖上游传入数据或持久化读取逻辑。

`releaseDate: LocalDate?`

表示聚合后的发布日期。它是可空字段，默认是 `null`。这说明某个系列的书籍聚合结果可能没有可用发布日期。

根据当前片段推断，`MetadataAggregator.aggregate(metadatas: Collection<BookMetadata>)` 会从多本书的 `BookMetadata.releaseDate` 中计算出一个代表性的 `releaseDate`，但本次只读取到调用点片段，没有看到完整算法，所以不能确定它选择的是最早日期、最晚日期，还是其他规则。

`summary: String`

表示聚合后的简介文本，默认空字符串。

这个字段与单本书 `BookMetadata.summary` 有关。根据 `rg` 结果，`MetadataAggregator` 会构造：

```kotlin
BookMetadataAggregation(
  authors = authors,
  tags = tags,
  releaseDate = releaseDate,
  summary = summary,
  summaryNumber = summaryNumber
)
```

所以 `summary` 是由服务层聚合逻辑计算后传入的，而不是 `BookMetadataAggregation` 自己生成的。

`summaryNumber: String`

表示 `summary` 对应的书籍编号或来源编号，默认空字符串。

这个字段很容易被忽略。它不是“聚合结果的数量”，而更像是“当前聚合简介来自哪一本书的 `number`”。例如某个系列简介可能取自第一卷、最新卷或某个符合规则的卷，此时 `summaryNumber` 可以告诉前端或接口消费者该简介对应哪本书。

具体选择规则需要看 `MetadataAggregator` 的完整实现。根据当前片段推断，它与 `BookMetadata.number` 或排序逻辑有关，因为 `BookMetadata` 中存在 `number`、`numberSort` 字段。

`seriesId: String`

表示这条聚合记录归属的系列 ID。默认是空字符串。

这个字段在领域关系中非常关键：`BookMetadataAggregation` 不是孤立存在的，它挂在某个 `Series` 下。`SeriesLifecycle.kt` 中存在调用片段：

```kotlin
BookMetadataAggregation(seriesId = series.id)
```

说明创建系列生命周期相关数据时，系统可能先为一个系列建立空的聚合元数据记录。

`createdDate: LocalDateTime`

来自 `Auditable` 接口，表示创建时间。默认值是 `LocalDateTime.now()`。

`lastModifiedDate: LocalDateTime`

同样来自 `Auditable`，表示最后修改时间。默认值是 `createdDate`，也就是新建对象时，创建时间和修改时间一致。

这个设计在同目录的 `BookMetadata.kt` 中也能看到，是 Komga 领域模型常见的审计字段模式。

## 上下游关系

上游主要有三类。

第一类是单本书元数据 `BookMetadata`。

`BookMetadataAggregation` 聚合的是多本书的 `BookMetadata`。`BookMetadata.kt` 中的 `BookMetadata` 包含：

- `title`
- `summary`
- `number`
- `numberSort`
- `releaseDate`
- `authors`
- `tags`
- `isbn`
- `links`
- 多个锁定字段，例如 `summaryLock`、`authorsLock`、`tagsLock`
- `bookId`
- `createdDate`
- `lastModifiedDate`

相比之下，`BookMetadataAggregation` 只保留系列级展示需要的部分字段：`authors`、`tags`、`releaseDate`、`summary`、`summaryNumber`、`seriesId` 和审计字段。

这说明它不是 `BookMetadata` 的完整复制，而是面向系列视图或搜索场景的精简汇总模型。

第二类是聚合服务 `MetadataAggregator`。

调用方片段显示：

```kotlin
fun aggregate(metadatas: Collection<BookMetadata>): BookMetadataAggregation
```

并且最终返回：

```kotlin
BookMetadataAggregation(
  authors = authors,
  tags = tags,
  releaseDate = releaseDate,
  summary = summary,
  summaryNumber = summaryNumber
)
```

也就是说，`MetadataAggregator` 负责把多条 `BookMetadata` 汇总成一条 `BookMetadataAggregation`。当前文件只定义结果结构，不负责聚合算法。

第三类是生命周期服务。

`SeriesLifecycle.kt` 和 `SeriesMetadataLifecycle.kt` 都引用了 `BookMetadataAggregationRepository`，说明当系列创建、更新、删除或元数据变化时，系统会维护对应的聚合记录。

`SeriesLifecycle.kt` 中还出现：

```kotlin
BookMetadataAggregation(seriesId = series.id)
```

这说明系列生命周期里会创建与系列 ID 绑定的聚合对象，即使初始还没有作者、标签、发布日期或简介，也可以先建立空聚合记录。

下游主要有三类。

第一类是持久化层。

`BookMetadataAggregationRepository.kt` 定义了仓储接口，包含：

- `findById(seriesId: String): BookMetadataAggregation`
- `findByIdOrNull(seriesId: String): BookMetadataAggregation?`
- `insert(metadata: BookMetadataAggregation)`
- `update(metadata: BookMetadataAggregation)`

`BookMetadataAggregationDao.kt` 是 jOOQ 实现，负责把领域对象写入数据库，并从数据库记录还原为 `BookMetadataAggregation`。从搜索结果能看到它处理了：

- `BookMetadataAggregationRecord.toDomain(...)`
- `BookMetadataAggregationAuthorRecord.toDomain()`
- `insertAuthors(metadata: BookMetadataAggregation)`
- `insertTags(metadata: BookMetadataAggregation)`

这说明聚合对象在数据库层可能拆分存储：主体表保存 `seriesId`、`releaseDate`、`summary` 等字段，作者和标签可能分别进入关联表。

第二类是查询与搜索层。

`SeriesDao.kt` 中出现：

```kotlin
RequiredJoin.BookMetadataAggregation -> leftJoin(bma).on(s.ID.eq(bma.SERIES_ID))
```

`SeriesSearchHelper.kt` 中也有针对 `BOOK_METADATA_AGGREGATION.RELEASE_DATE` 的搜索条件。这说明系列查询时可以联结聚合表，尤其是按系列的书籍聚合发布日期进行筛选或排序。

第三类是 API DTO 层。

`SeriesDto.kt` 中包含：

```kotlin
val booksMetadata: BookMetadataAggregationDto
```

并定义了 `BookMetadataAggregationDto`。`SeriesDtoDao.kt` 中也存在把 `BookMetadataAggregationRecord` 转成 `BookMetadataAggregationDto` 的逻辑。

因此，在接口层面，`BookMetadataAggregation` 的信息最终会作为 `SeriesDto.booksMetadata` 暴露给客户端。用户看到的系列作者、标签、发布日期、简介等信息，很可能就来自这条聚合数据。

## 运行/调用流程

一个典型流程可以这样理解：

1. 系统扫描或导入书籍，生成每本书自己的 `BookMetadata`。

   单本书的元数据包含作者、标签、简介、发布日期、编号等。`BookMetadata` 会在构造时对部分字段做清洗，例如标题、简介、编号会 `trim()`，标签会转小写并过滤空值。

2. 某个系列的多本书元数据发生变化。

   变化可能来自扫描、用户编辑、元数据刷新、书籍增删等。此时系统需要重新计算该系列的“书籍元数据汇总”。

3. `MetadataAggregator.aggregate(...)` 接收一组 `BookMetadata`。

   根据当前片段可知，它会计算：

   - `authors`
   - `tags`
   - `releaseDate`
   - `summary`
   - `summaryNumber`

   然后构造 `BookMetadataAggregation` 返回。

   需要注意：`BookMetadataAggregation` 构造器没有传入 `seriesId` 的片段出现在 `MetadataAggregator` 返回处，所以根据当前片段推断，`seriesId` 可能由后续生命周期服务补上，或者聚合结果在更新已有记录时合并 `seriesId`。完整细节需要查看 `SeriesMetadataLifecycle.kt` 或相关更新逻辑才能确定。

4. 生命周期服务通过 `BookMetadataAggregationRepository` 保存结果。

   `SeriesLifecycle.kt` 和 `SeriesMetadataLifecycle.kt` 都依赖 `BookMetadataAggregationRepository`。仓储接口提供插入和更新方法，jOOQ DAO 负责实际数据库操作。

5. 查询系列时联结聚合表。

   `SeriesDao.kt` 会在需要 `RequiredJoin.BookMetadataAggregation` 时对聚合表做 `leftJoin`。这让系列查询可以拿到聚合后的书籍元数据。

6. API 返回给客户端。

   `SeriesDto` 中的 `booksMetadata: BookMetadataAggregationDto` 会承载这些信息。前端或 API 消费者拿到系列详情时，不需要自己遍历所有书籍来算作者、标签和简介，而是直接使用后端已经维护好的聚合结果。

## 小白阅读顺序

建议按下面顺序阅读，不要一开始就跳到 DAO 或 SQL 层。

1. 先读 `BookMetadataAggregation.kt`

   目标是理解它只是一个数据容器。重点看字段名、默认值和 `: Auditable`。

2. 再读 `Auditable.kt`

   理解为什么它必须有 `createdDate` 和 `lastModifiedDate`。这个接口很小，只定义两个审计字段。

3. 再读 `Author.kt`

   理解 `authors: List<Author>` 中的 `Author` 是什么。尤其要注意 `Author` 不是 `data class`，而是手写了 `equals()` 和 `hashCode()`，并在构造时清洗 `name` 和 `role`。

4. 再读 `BookMetadata.kt`

   对比单本书元数据和系列聚合元数据。你会发现 `BookMetadata` 字段更多，包含锁定字段、ISBN、链接、编号排序等；而 `BookMetadataAggregation` 只保存系列层面常用的汇总字段。

5. 再读 `MetadataAggregator.kt`

   这是理解“聚合结果怎么来”的关键。`BookMetadataAggregation.kt` 不告诉你作者如何去重、标签如何合并、发布日期如何选择、简介取哪一本，这些规则应在 `MetadataAggregator` 里。

6. 再读 `BookMetadataAggregationRepository.kt` 和 `BookMetadataAggregationDao.kt`

   这一步看“聚合结果怎么存”。重点关注 `insert()`、`update()`、`toDomain()`，以及作者、标签是否使用单独表保存。

7. 最后读 `SeriesDto.kt`、`SeriesDtoDao.kt`、`SeriesDao.kt`

   这一步看“聚合结果怎么被查询和暴露”。尤其关注 `booksMetadata: BookMetadataAggregationDto`，它是领域聚合对象进入 API 输出的地方。

## 常见误区

误区一：以为 `BookMetadataAggregation` 会自己计算聚合结果。

它不会。这个类没有方法，只有字段。真正的计算在服务层，例如 `MetadataAggregator`。它只是保存计算后的结果。

误区二：把 `summaryNumber` 理解成“简介数量”。

从字段名和上下文看，`summaryNumber` 更像是“简介来源书籍的编号”，不是计数。它和 `BookMetadata.number` 的关系更近，而不是和集合大小有关。由于本次没有读取完整 `MetadataAggregator`，这里属于根据当前片段推断，依据是 `BookMetadata` 中存在 `number` 字段，且聚合返回同时设置了 `summary` 和 `summaryNumber`。

误区三：认为 `tags` 在这里一定会自动小写化。

`BookMetadataAggregation` 自己不会处理标签。它接收什么 `Set<String>` 就保存什么。单本书 `BookMetadata` 会对标签做 `lowerNotBlank().toSet()`，但聚合对象本身没有这层逻辑。

误区四：认为 `seriesId` 一定在构造时总是非空。

`seriesId` 默认是空字符串。`SeriesLifecycle.kt` 中有 `BookMetadataAggregation(seriesId = series.id)` 的用法，但 `MetadataAggregator` 返回片段中没有传 `seriesId`。所以阅读调用链时要注意：聚合计算和系列绑定可能是两个步骤，不要只看构造函数默认值就下结论。

误区五：把它和 `BookMetadata` 当成同一层概念。

`BookMetadata` 是单本书的元数据；`BookMetadataAggregation` 是系列下多本书元数据的汇总。前者归属 `bookId`，后者归属 `seriesId`。它们字段相似，但服务对象不同。

误区六：忽略 `Auditable` 的影响。

这个类实现了 `Auditable`，所以它不仅是展示数据，也是一条可持久化、可追踪更新时间的领域记录。DAO 更新时需要维护 `lastModifiedDate`，查询 DTO 时也可能涉及时间转换。`CHANGELOG.md` 中还出现过 `BookMetadataAggregationDto` 时间转换相关修复记录，说明这些审计字段在接口层并非无关紧要。
