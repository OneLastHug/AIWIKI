# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/BookMetadata.kt

## 它负责什么

`BookMetadata.kt` 定义的是 Komga 领域层里的 `BookMetadata` 模型，用来表示“某一本书的元数据”。它和 `Book.kt` 中的 `Book` 分工不同：

`Book` 描述书籍文件本身，例如 `name`、`url`、`fileLastModified`、`fileSize`、`seriesId`、`libraryId` 等偏文件和归属关系的信息；`BookMetadata` 描述用户看到和编辑的书籍内容信息，例如标题、简介、卷号、排序号、发布日期、作者、标签、ISBN、外部链接等。

这个文件的核心职责有三类：

1. 保存书籍元数据字段。
2. 在构造时做轻量规范化，例如去掉字符串首尾空白、处理 tags。
3. 保存每个字段的 lock 状态，用来控制自动导入元数据时哪些字段不能被覆盖。

它实现了 `Auditable`，因此每条书籍元数据也带有 `createdDate` 和 `lastModifiedDate`。这说明它不仅是临时对象，也会参与持久化、更新和审计时间记录。

## 关键组成

`BookMetadata` 是普通 Kotlin `class`，不是 `data class`。这点很重要，因为它自己实现了 `copy()` 和 `toString()`，并在主构造函数参数进入属性时做了规范化处理。

主要字段如下：

`title`：书籍标题。构造参数进入对象后会执行 `title.trim()`，所以对象内部保存的是去掉首尾空白后的标题。

`summary`：书籍简介。默认值是空字符串，同样会 `trim()`。

`number`：书籍编号或卷号，类型是 `String`。它和 `numberSort` 不同，`number` 更偏展示，例如可能来自文件名或元数据源中的原始卷号；`numberSort` 是 `Float`，更适合排序。

`numberSort`：用于排序的数字字段。没有默认值，创建 `BookMetadata` 时必须显式传入。

`releaseDate`：发布日期，类型是 `LocalDate?`，可以为空。

`authors`：作者列表，类型是 `List<Author>`。`Author.kt` 中的 `Author` 会把 `name` 做 `trim()`，把 `role` 做 `trim().lowercase()`，所以作者角色也会被标准化为小写。

`tags`：标签集合。构造参数默认是空集合，进入对象后会执行 `tags.lowerNotBlank().toSet()`。根据当前片段推断，`lowerNotBlank()` 的作用应当是把标签转成小写并过滤空白标签；依据是函数名 `lowerNotBlank` 以及它用于 tags 的规范化场景。

`isbn`：ISBN 字符串，默认空字符串。这个字段没有在 `BookMetadata` 内部 trim，从当前文件看只有 `title`、`summary`、`number` 和 `tags` 有显式规范化。

`links`：外部链接列表，类型是 `List<WebLink>`。`WebLink.kt` 中的 `WebLink` 是 `data class`，包含 `label: String` 和 `url: URI`。

`bookId`：关联的书籍 ID。它把元数据和 `Book` 关联起来，默认空字符串，但真实持久化场景下通常应当对应某个 `Book.id`。

`createdDate`、`lastModifiedDate`：来自 `Auditable` 接口。默认 `createdDate` 是 `LocalDateTime.now()`，`lastModifiedDate` 默认等于 `createdDate`。

此外，它为多个元数据字段配套定义了 lock 布尔值：

`titleLock`、`summaryLock`、`numberLock`、`numberSortLock`、`releaseDateLock`、`authorsLock`、`tagsLock`、`isbnLock`、`linksLock`

这些字段表示对应元数据是否被锁定。锁定后，自动元数据导入流程不能覆盖该字段。这个行为不是在 `BookMetadata` 自己内部完成的，而是在 `MetadataApplier.kt` 中完成。

`copy()` 方法是本文件的另一个重点。因为 `BookMetadata` 不是 `data class`，所以 Kotlin 不会自动生成 `copy()`。这里手写的 `copy()` 接收所有字段作为可选参数，并默认沿用当前对象的值，最后重新构造一个新的 `BookMetadata`。

这带来两个效果：

1. 调用方可以像使用 `data class.copy()` 一样局部更新字段。
2. 由于最终会重新调用 `BookMetadata(...)` 构造函数，所以 `title`、`summary`、`number`、`tags` 的规范化逻辑仍然会再次执行。

`toString()` 也被手写实现，用于日志输出。`BookMetadataLifecycle.kt` 中会打印 `Original metadata`、`Patch`、`Patched metadata`，因此这里的 `toString()` 对调试元数据刷新过程很有用。

## 上下游关系

上游来源主要有三类。

第一类是书籍生命周期创建默认元数据。`rg` 结果显示 `SeriesLifecycle.kt` 会直接创建 `BookMetadata(...)`。根据命名和引用关系推断，在书籍被加入系列或扫描导入时，系统会为每本书初始化一条元数据记录。

第二类是外部或文件内元数据提供器。`BookMetadataProvider.kt` 定义了书籍元数据提供器接口，返回 `BookMetadataPatch?`。具体提供器包括 `EpubMetadataProvider.kt`、`ComicInfoProvider.kt`、`IsbnBarcodeProvider.kt` 等。它们不会直接修改 `BookMetadata`，而是先产出 `BookMetadataPatch`。

第三类是 REST API 用户更新。`BookMetadataUpdateDto.kt` 中存在 `fun BookMetadata.patch(patch: BookMetadataUpdateDto)`，说明接口层接收用户提交的更新 DTO 后，会转成对 `BookMetadata` 的修改。当前没有展开该文件，但从引用关系可以确认它是用户编辑元数据的入口之一。

中游核心处理是 `MetadataApplier.kt`。它的 `apply(patch: BookMetadataPatch, metadata: BookMetadata): BookMetadata` 会读取 patch 中的字段，然后调用 `metadata.copy(...)` 生成新对象。它内部有一个 `getIfNotLocked(original, patched, lock)` 方法：

如果 patch 字段不为 null 且对应 lock 为 false，就使用 patch 值；否则保留原值。

所以 `BookMetadata` 里的 lock 字段真正发挥作用的位置是 `MetadataApplier`，不是模型本身。

下游主要是持久化、API 输出、聚合和事件。

`BookMetadataRepository.kt` 定义了领域层仓储接口，提供 `findById`、`findByIdOrNull`、`findAllByIds`、`insert`、`update`、`delete`、`count` 等方法。`BookMetadataDao.kt` 是 JOOQ 实现，负责和数据库表互转。`BookDtoDao.kt`、`KoboDtoDao.kt` 会把数据库里的书籍元数据映射成 REST 或 Kobo API 的 DTO。

`MetadataAggregator.kt` 会读取一组 `BookMetadata` 并聚合成 `BookMetadataAggregation`，供系列维度使用。例如一个 series 的作者、标签、发布日期摘要等可能来自该 series 下多本书的元数据。

`BookMetadataLifecycle.kt` 在更新元数据后会发布 `DomainEvent.BookUpdated(book)`，说明元数据变更会被视为书籍更新，可能触发后续缓存、索引、同步或前端刷新逻辑。

## 运行/调用流程

一个典型的自动刷新书籍元数据流程如下：

1. 任务系统触发刷新  
   `TaskEmitter.kt` 会提交 `Task.RefreshBookMetadata`，任务里带有 `bookId` 和需要刷新的 `BookMetadataPatchCapability` 集合。

2. 生命周期服务处理刷新  
   `BookMetadataLifecycle.refreshMetadata(book, capabilities)` 被调用。它先通过 `mediaRepository.findById(book.id)` 找到媒体信息，再通过 `libraryRepository.findById(book.libraryId)` 找到书籍所属 library。

3. 遍历元数据提供器  
   `BookMetadataLifecycle` 会遍历注入的 `bookMetadataProviders`。每个 provider 都声明自己支持哪些 `BookMetadataPatchCapability`，例如 `TITLE`、`SUMMARY`、`NUMBER`、`NUMBER_SORT`、`RELEASE_DATE`、`AUTHORS`、`TAGS`、`ISBN`、`LINKS` 等。

4. 判断是否应该处理  
   如果当前刷新请求的能力集合和 provider 支持能力没有交集，就跳过该 provider。  
   如果 library 配置不允许该 provider 处理 book metadata 或 read list metadata，也会跳过。

5. Provider 生成 patch  
   满足条件时，provider 调用 `getBookMetadataFromBook(BookWithMedia(book, media))`，返回 `BookMetadataPatch?`。这个 patch 只表示“候选更新”，不是最终结果。

6. 读取当前元数据  
   `handlePatchForBookMetadata(patch, book)` 会通过 `bookMetadataRepository.findById(book.id)` 读取当前持久化的 `BookMetadata`。

7. 应用 patch  
   `metadataApplier.apply(bPatch, it)` 根据 lock 状态决定每个字段是否可以被 patch 覆盖。未锁定且 patch 非空的字段会更新，锁定字段或 patch 为空的字段会保留原值。

8. 生成新的 `BookMetadata`  
   `MetadataApplier` 调用 `metadata.copy(...)`。这里会进入 `BookMetadata.copy()`，再重新构造 `BookMetadata`，因此 `title`、`summary`、`number`、`tags` 会再次执行模型层规范化。

9. 保存并发布事件  
   新对象通过 `bookMetadataRepository.update(patched)` 写回。只要本轮处理了 book metadata patch，`BookMetadataLifecycle` 最后会发布 `DomainEvent.BookUpdated(book)`。

用户手动编辑元数据的流程略有不同：接口层会接收 `BookMetadataUpdateDto`，再对已有 `BookMetadata` 执行 patch。根据引用关系看，这条链路经过 `BookController.kt` 和 `BookMetadataUpdateDto.kt`，最终仍然会得到更新后的 `BookMetadata` 并持久化。

## 小白阅读顺序

建议按下面顺序读，不要一开始就跳到 DAO 或任务系统：

1. 先读 `komga/src/main/kotlin/org/gotson/komga/domain/model/BookMetadata.kt`  
   重点看字段、lock 字段、`copy()` 和构造时的规范化逻辑。先搞清楚“这个对象长什么样”。

2. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/model/Book.kt`  
   对比 `Book` 和 `BookMetadata` 的边界：一个偏文件实体，一个偏展示和编辑用的元数据。

3. 读 `komga/src/main/kotlin/org/gotson/komga/domain/model/Author.kt`、`komga/src/main/kotlin/org/gotson/komga/domain/model/WebLink.kt`  
   理解 `authors` 和 `links` 这两个复合字段。尤其是 `Author` 也会做规范化，`role` 会小写。

4. 读 `komga/src/main/kotlin/org/gotson/komga/domain/model/BookMetadataPatch.kt`  
   理解自动导入或更新时不是直接构造完整 `BookMetadata`，而是先生成一个部分字段可空的 patch。

5. 读 `komga/src/main/kotlin/org/gotson/komga/domain/service/MetadataApplier.kt`  
   这是理解 lock 行为的关键文件。`BookMetadata` 只保存 lock 状态，真正判断“能不能覆盖”的逻辑在这里。

6. 读 `komga/src/main/kotlin/org/gotson/komga/domain/service/BookMetadataLifecycle.kt`  
   看自动刷新流程如何从 provider 拿 patch、应用 patch、保存 metadata、发布 `BookUpdated` 事件。

7. 最后再看 `komga/src/main/kotlin/org/gotson/komga/domain/persistence/BookMetadataRepository.kt` 和 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/BookMetadataDao.kt`  
   前者是领域层接口，后者是数据库实现。先理解领域模型再看持久化，会更容易。

## 常见误区

误区一：把 `BookMetadata` 当成 `data class`。  
它不是 `data class`。虽然它手写了 `copy()`，但没有自动生成的 `equals()`、`hashCode()`。如果代码里比较两个 `BookMetadata` 实例，要注意它不是天然按字段值比较。

误区二：以为 lock 字段会自动阻止任何修改。  
`titleLock`、`summaryLock` 等字段只是状态。自动元数据导入时，`MetadataApplier.getIfNotLocked()` 会尊重这些 lock；但如果有其他代码直接调用 `copy(title = "...")` 或构造新对象，模型本身不会阻止修改。也就是说，lock 是业务流程约束，不是不可变权限机制。

误区三：以为 `BookMetadataPatch` 和 `BookMetadata` 是同一种东西。  
`BookMetadataPatch` 是“部分更新请求”，字段大多可空；`BookMetadata` 是完整领域模型，保存当前最终状态。Provider 产出的是 patch，不是最终 metadata。

误区四：忽略构造时的规范化。  
`title`、`summary`、`number` 会 `trim()`，`tags` 会经过 `lowerNotBlank().toSet()`。所以输入值和对象内部值可能不同。尤其 tags 可能被小写化、去空、去重。根据当前片段推断，去重来自最后的 `toSet()`，小写和过滤空白来自 `lowerNotBlank()`。

误区五：把 `number` 和 `numberSort` 混在一起。  
`number` 是字符串，偏展示；`numberSort` 是 `Float`，偏排序。一个书籍编号可能显示为特殊格式，但排序仍然依赖数值字段。

误区六：以为 `bookId` 一定在构造时有值。  
`bookId` 默认是空字符串，但在真实业务中它应该关联到 `Book.id`。默认值只是让构造更灵活，不代表空 `bookId` 是正常持久化状态。

误区七：认为 `lastModifiedDate` 会在 `copy()` 时自动变成当前时间。  
`copy()` 的默认参数是 `lastModifiedDate = this.lastModifiedDate`，不会自动刷新为 `LocalDateTime.now()`。如果业务需要更新修改时间，必须由调用方或持久化层显式处理。当前片段只能确认模型本身不会自动更新时间。

误区八：只看这个文件会误解它的业务意义。  
`BookMetadata.kt` 只是模型定义。它的实际价值要结合 `BookMetadataPatch.kt`、`MetadataApplier.kt`、`BookMetadataLifecycle.kt`、`BookMetadataRepository.kt` 一起看：provider 产生 patch，applier 尊重 lock 生成新 metadata，repository 持久化，lifecycle 发布更新事件。
