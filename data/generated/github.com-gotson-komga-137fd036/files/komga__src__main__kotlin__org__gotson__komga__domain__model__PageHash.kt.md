# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/PageHash.kt

## 它负责什么

`PageHash.kt` 定义了领域模型 `PageHash`，它是 Komga 页面哈希功能里的基础类，用来表达“某一页图片/页面内容的哈希值，以及该页面文件大小”。

源码非常短：

```kotlin
open class PageHash(
  val hash: String,
  size: Long? = null,
) {
  val size: Long? = if (size != null && size < 0) null else size
}
```

它主要负责两件事：

1. 保存页面哈希字符串 `hash`
2. 保存可选的页面文件大小 `size`，并把负数大小归一化为 `null`

这里的“页面哈希”不是书籍本身的哈希，而是书内页面文件的哈希。根据 `BookAnalyzer.hashPages` 的逻辑，系统会对一本书开头和结尾的一部分页面计算 `fileHash`，用于发现重复页面，例如广告页、扫描组页面、重复封面页等。

`PageHash` 本身不包含“这是已知重复页还是未知重复页”的业务判断，它只是一个基础数据结构。具体业务语义由它的子类承载：

- `PageHashKnown`：已被系统或用户标记过的重复页哈希
- `PageHashUnknown`：系统检测到多次出现、但尚未被标记处理策略的重复页哈希

## 关键组成

### `open class PageHash`

`PageHash` 被声明为 `open class`，说明它设计上就是为了被继承。Kotlin 中普通类默认是 `final`，不能继承；这里显式使用 `open`，为 `PageHashKnown` 和 `PageHashUnknown` 这类派生模型提供共同父类。

它不是 `data class`，这一点也值得注意。原因根据当前片段推断有两个：

1. 它作为父类存在，子类才是业务上真正需要传递和序列化的模型
2. `size` 参数经过了自定义归一化逻辑，不是简单字段赋值

### `val hash: String`

`hash` 是页面内容哈希，类型为 `String`。从调用方看，它对应 `BookPage` 或数据库 page 记录里的 `FILE_HASH` / `fileHash`。

相关使用位置包括：

- `PageHashRepository.findKnown(pageHash: String)`
- `PageHashRepository.findMatchesByHash(pageHash: String, pageable: Pageable)`
- `PageHashDao.findAllUnknown`
- `PageHashDao.findMatchesByHash`
- `PageHashController.getPageHashMatches`
- `PageHashLifecycle.getPage`

也就是说，`hash` 是页面去重功能的核心索引键。系统通过这个值查：

- 这个哈希是否已经是 known duplicate
- 哪些书、哪些页命中了这个哈希
- 是否需要展示缩略图
- 是否可以批量删除这些重复页

### 构造参数 `size: Long? = null`

构造参数 `size` 是 nullable，默认值是 `null`。这表示页面大小可能未知。

它没有直接写成 `val size: Long?` 参数，而是在类体中重新定义：

```kotlin
val size: Long? = if (size != null && size < 0) null else size
```

这样做的重点是清洗非法数据：如果传入的 `size` 是负数，就把它改成 `null`。

这条规则有对应测试：`komga/src/test/kotlin/org/gotson/komga/domain/model/PageHashTest.kt` 中覆盖了三种情况：

- 传入负数时，`pageHash.size` 为 `null`
- 传入 `null` 时，`pageHash.size` 为 `null`
- 传入正常正数时，`pageHash.size` 保留值

### 为什么负数会变成 `null`

文件大小从语义上不应该为负数。这里没有抛异常，而是将负数当作“未知大小”处理，说明该模型偏向容错。

根据当前片段推断，这种设计可能是为了兼容不同来源的页面大小数据：有些数据源或旧记录可能无法得到真实大小，或者用负值表示未知。领域层统一把它整理成 `null`，避免下游 DTO、数据库写入或 UI 显示继续传播非法大小。

## 上下游关系

### 上游：页面哈希从哪里来

页面哈希主要来自 `BookAnalyzer.hashPages`。

相关文件：`komga/src/main/kotlin/org/gotson/komga/domain/service/BookAnalyzer.kt`

`BookAnalyzer.hashPages` 的注释说明：

```kotlin
Will hash the first and last pages of the given book.
The number of pages hashed from start/end is configurable.
```

核心逻辑是：

```kotlin
if (bookPage.fileHash.isBlank() && (index < pageHashing || index >= (book.media.pageCount - pageHashing))) {
  val content = getPageContent(book, index + 1)
  val hash = hashPage(bookPage, content)
  bookPage.copy(fileHash = hash)
}
```

也就是说，系统不是对整本书所有页面都计算哈希，而是只对开头和结尾的若干页计算。数量由 `KomgaProperties.pageHashing` 控制，默认值在 `komga/src/main/kotlin/org/gotson/komga/infrastructure/configuration/KomgaProperties.kt` 中是 `3`。

这意味着默认情况下，每本支持的书会对前 3 页和后 3 页做页面哈希，用来检测常见的重复页。

### 同层模型：`PageHashKnown`

文件：`komga/src/main/kotlin/org/gotson/komga/domain/model/PageHashKnown.kt`

`PageHashKnown` 继承 `PageHash`：

```kotlin
class PageHashKnown(
  hash: String,
  size: Long? = null,
  val action: Action,
  val deleteCount: Int = 0,
  val matchCount: Int = 0,
  override val createdDate: LocalDateTime = LocalDateTime.now(),
  override val lastModifiedDate: LocalDateTime = createdDate,
) : PageHash(hash, size),
  Auditable
```

它表示“已知重复页哈希”，也就是已经被用户或系统纳入管理的哈希。它比 `PageHash` 多了这些字段：

- `action`：处理策略
- `deleteCount`：已经删除过多少次
- `matchCount`：当前匹配次数
- `createdDate`
- `lastModifiedDate`

`action` 有三个枚举值：

```kotlin
DELETE_AUTO
DELETE_MANUAL
IGNORE
```

含义可以这样理解：

- `DELETE_AUTO`：命中该哈希的页面可以自动删除
- `DELETE_MANUAL`：需要手动删除或确认
- `IGNORE`：忽略这个哈希，不把它作为需要处理的重复页

`PageHashKnown` 还提供了一个手写 `copy` 方法，用来更新部分字段。它不是 `data class`，所以没有自动生成 `copy`。例如 `PageHashLifecycle.createOrUpdate` 中，当已存在同 hash 记录时，只更新 action：

```kotlin
pageHashRepository.update(existing.copy(action = pageHash.action))
```

### 同层模型：`PageHashUnknown`

文件：`komga/src/main/kotlin/org/gotson/komga/domain/model/PageHashUnknown.kt`

```kotlin
class PageHashUnknown(
  hash: String,
  size: Long? = null,
  val matchCount: Int = 0,
) : PageHash(hash, size)
```

它也继承 `PageHash`，表示系统发现“多个页面拥有相同哈希”，但这个哈希还没有被用户标记为 known。

`PageHashUnknown` 比父类只多一个 `matchCount`，用于说明这个哈希出现了多少次。

在 `PageHashDao.findAllUnknown` 中，unknown 的定义很清楚：

- `p.FILE_HASH.ne("")`：页面 hash 非空
- 不存在于 known hash 表中
- 按 `FILE_HASH` 分组
- 出现次数大于 1

换句话说：unknown duplicate 是“重复出现、但还没有被用户处理策略覆盖的页面哈希”。

### 同层模型：`PageHashMatch`

文件：`komga/src/main/kotlin/org/gotson/komga/domain/model/PageHashMatch.kt`

`PageHashMatch` 不继承 `PageHash`，它表达的是某个 hash 的具体命中位置：

```kotlin
data class PageHashMatch(
  val bookId: String,
  val url: URL,
  val pageNumber: Int,
  val fileName: String,
  val fileSize: Long,
  val mediaType: String,
)
```

如果 `PageHash` 表示“这个页面内容是什么 hash”，那么 `PageHashMatch` 表示“这个 hash 出现在了哪本书的哪一页”。

它由 `PageHashRepository.findMatchesByHash` 返回，最终可用于：

- 展示重复页列表
- 获取某个重复页缩略图
- 删除某个匹配页
- 批量删除某个 hash 的所有匹配页

### 下游：持久化接口

文件：`komga/src/main/kotlin/org/gotson/komga/domain/persistence/PageHashRepository.kt`

`PageHashRepository` 是页面哈希功能的领域持久化接口。它直接使用 `PageHashKnown`、`PageHashUnknown`、`PageHashMatch`：

```kotlin
interface PageHashRepository {
  fun findKnown(pageHash: String): PageHashKnown?

  fun findAllKnown(
    actions: List<PageHashKnown.Action>?,
    pageable: Pageable,
  ): Page<PageHashKnown>

  fun findAllUnknown(pageable: Pageable): Page<PageHashUnknown>

  fun findMatchesByHash(
    pageHash: String,
    pageable: Pageable,
  ): Page<PageHashMatch>

  fun findMatchesByKnownHashAction(
    actions: List<PageHashKnown.Action>?,
    libraryId: String?,
  ): Map<String, Collection<BookPageNumbered>>

  fun getKnownThumbnail(pageHash: String): ByteArray?

  fun insert(
    pageHash: PageHashKnown,
    thumbnail: ByteArray?,
  )

  fun update(pageHash: PageHashKnown)
}
```

可以看到，仓储层没有直接返回父类 `PageHash`，而是返回更具体的子类。这说明 `PageHash` 的价值主要是抽取共同字段和共同校验逻辑，而不是作为多态接口被大量使用。

### 下游：数据库实现

文件：`komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/PageHashDao.kt`

`PageHashDao` 是 `PageHashRepository` 的 jOOQ 实现。它把数据库表中的记录转换为领域模型。

`findAllKnown` 从 known hash 表查询，并统计匹配页面数量：

```kotlin
.select(*ph.fields(), DSL.count(p.FILE_HASH).`as`("count"))
.from(ph)
.leftJoin(p)
.on(ph.HASH.eq(p.FILE_HASH))
```

然后转换为 `PageHashKnown`：

```kotlin
.map { it.into(ph).toDomain(it.get("count", Int::class.java)) }
```

`findAllUnknown` 从页面表里找重复但未进入 known 表的 hash：

```kotlin
.where(p.FILE_HASH.ne(""))
.and(
  DSL.notExists(
    dslRO
      .selectOne()
      .from(ph)
      .where(ph.HASH.eq(p.FILE_HASH)),
  ),
)
.groupBy(p.FILE_HASH)
.having(DSL.count(p.BOOK_ID).gt(1))
```

然后构造：

```kotlin
PageHashUnknown(it.value1(), it.value2(), it.value3())
```

这里第二个参数 `it.value2()` 是 `FILE_SIZE`，会经过 `PageHash` 父类的 `size` 归一化逻辑。如果数据库里出现负数 size，最终领域对象会把它变成 `null`。

`insert` 和 `update` 只接收 `PageHashKnown`，因为只有 known hash 才会被显式写入 known hash 表：

```kotlin
.set(ph.HASH, pageHash.hash)
.set(ph.SIZE, pageHash.size)
.set(ph.ACTION, pageHash.action.name)
```

### 下游：领域服务

文件：`komga/src/main/kotlin/org/gotson/komga/domain/service/PageHashLifecycle.kt`

`PageHashLifecycle` 负责页面哈希生命周期相关操作。

重要方法包括：

```kotlin
fun getBookIdsWithMissingPageHash(library: Library): Collection<String>
```

用于找出还缺少页面 hash 的书。如果 library 没启用 `hashPages`，直接跳过。

```kotlin
fun getPage(
  pageHash: String,
  resizeTo: Int? = null,
): TypedBytes?
```

用于根据 hash 找一个匹配页面，再通过 `BookLifecycle.getBookPage` 取出页面内容。这通常用于生成或展示缩略图。

```kotlin
fun getBookPagesToDeleteAutomatically(library: Library): Map<String, Collection<BookPageNumbered>>
```

找出 action 为 `DELETE_AUTO` 的 known hash 对应页面，用于自动删除重复页。

```kotlin
fun createOrUpdate(pageHash: PageHashKnown)
```

用于新增或更新 known hash：

- 如果这个 hash 还不存在，就插入并尝试保存缩略图
- 如果已经存在，就更新 action

这里传入的是 `PageHashKnown`，它继承自 `PageHash`，所以 `hash` 和 `size` 的基础规则仍来自 `PageHash.kt`。

### 下游：REST API

文件：`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/PageHashController.kt`

`PageHashController` 把页面哈希功能暴露给 REST API，主要接口包括：

- `GET /api/v1/page-hashes`：列出 known duplicates
- `GET /api/v1/page-hashes/unknown`：列出 unknown duplicates
- `GET /api/v1/page-hashes/{pageHash}`：列出某个 hash 的所有匹配页面
- `PUT /api/v1/page-hashes`：把某个重复页 hash 标记为 known
- `POST /api/v1/page-hashes/{pageHash}/delete-all`：删除某个 hash 的所有重复页面
- `POST /api/v1/page-hashes/{pageHash}/delete-match`：删除某一个匹配页面

DTO 文件也保留了 `PageHash` 的两个核心字段：

`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/PageHashKnownDto.kt`：

```kotlin
data class PageHashKnownDto(
  val hash: String,
  val size: Long?,
  val action: PageHashKnown.Action,
  val deleteCount: Int,
  val matchCount: Int,
  val created: LocalDateTime,
  val lastModified: LocalDateTime,
)
```

`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/PageHashUnknownDto.kt`：

```kotlin
data class PageHashUnknownDto(
  val hash: String,
  val size: Long?,
  val matchCount: Int,
)
```

这说明 `PageHash.hash` 和 `PageHash.size` 最终会出现在 API 响应中，是前端页面哈希管理界面可见的数据。

## 运行/调用流程

一个典型流程可以分为 5 步。

### 1. 扫描或分析书籍时计算页面 hash

入口在 `BookAnalyzer.hashPages`。

系统会读取一本书的页面列表，只对开头和结尾的部分页面计算 hash：

```kotlin
index < pageHashing || index >= (book.media.pageCount - pageHashing)
```

默认 `pageHashing` 是 `3`，所以通常是前 3 页和后 3 页。

计算出来的值写入页面对象的 `fileHash`：

```kotlin
bookPage.copy(fileHash = hash)
```

### 2. 系统找出重复 hash

当任务系统处理页面哈希相关任务时，会调用 `PageHashLifecycle.getBookIdsWithMissingPageHash` 找出需要补 hash 的书。

重复 hash 的查询主要由 `PageHashDao.findAllUnknown` 完成。它从页面表中找出：

- `FILE_HASH` 非空
- 不在 known hash 表中
- 同一个 hash 出现次数大于 1

这些记录被包装为 `PageHashUnknown`。构造 `PageHashUnknown` 时，会调用父类 `PageHash` 的构造逻辑，因此 `size` 会被统一清洗。

### 3. 用户查看 unknown duplicates

REST 层的 `PageHashController.getUnknownPageHashes` 调用：

```kotlin
pageHashRepository.findAllUnknown(page).map { it.toDto() }
```

返回 `PageHashUnknownDto`，包含：

- `hash`
- `size`
- `matchCount`

这时用户或前端可以知道哪些页面 hash 是重复出现的。

### 4. 用户把某个 hash 标记为 known

用户通过 `PUT` 接口提交 `PageHashCreationDto`，Controller 中构造 `PageHashKnown`：

```kotlin
PageHashKnown(
  hash = pageHash.hash,
  size = pageHash.size,
  action = pageHash.action,
)
```

这里 `PageHashKnown` 继承 `PageHash`，所以如果请求里的 `size` 是负数，会被父类转成 `null`。

然后调用：

```kotlin
pageHashLifecycle.createOrUpdate(...)
```

如果是新 hash，就插入数据库；如果已存在，就更新 action。

### 5. 系统按 known action 执行处理

如果某个 `PageHashKnown.action` 是 `DELETE_AUTO`，那么 `PageHashLifecycle.getBookPagesToDeleteAutomatically` 会查出这些页面：

```kotlin
pageHashRepository.findMatchesByKnownHashAction(
  listOf(PageHashKnown.Action.DELETE_AUTO),
  library.id,
)
```

随后任务系统可以把这些页面交给删除流程。

手动删除时，`PageHashController` 也可以通过 `findMatchesByHash` 找出匹配页面，再调用 `taskEmitter.removeDuplicatePages` 删除。

## 小白阅读顺序

建议按下面顺序阅读，不要一开始就陷入数据库查询细节。

1. 先读 `komga/src/main/kotlin/org/gotson/komga/domain/model/PageHash.kt`

   重点看懂两个字段：`hash` 和 `size`。尤其注意 `size < 0` 会变成 `null`。

2. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/model/PageHashKnown.kt`

   理解 known duplicate 是什么。重点看 `Action` 枚举：`DELETE_AUTO`、`DELETE_MANUAL`、`IGNORE`。

3. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/model/PageHashUnknown.kt`

   理解 unknown duplicate 只是“重复出现但尚未被标记”的 hash。

4. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/model/PageHashMatch.kt`

   理解一个 hash 可以命中多个具体页面，`PageHashMatch` 就是命中位置。

5. 然后读 `komga/src/main/kotlin/org/gotson/komga/domain/persistence/PageHashRepository.kt`

   这个接口能帮你建立功能地图：查询 known、查询 unknown、查询 matches、插入 known、更新 known、取缩略图。

6. 接着读 `komga/src/main/kotlin/org/gotson/komga/domain/service/PageHashLifecycle.kt`

   这里能看到页面哈希的业务生命周期：找缺失 hash 的书、根据 hash 取页面、创建或更新 known hash、找自动删除页面。

7. 最后再读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/PageHashDao.kt`

   这里是 SQL 查询实现，适合在理解领域概念后再看。重点关注 `findAllUnknown`、`findAllKnown`、`findMatchesByHash`。

如果想从 API 角度理解，再补读 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/PageHashController.kt` 和 DTO 文件。

## 常见误区

### 误区 1：以为 `PageHash` 表示整本书的 hash

不是。`PageHash` 表示页面级别的 hash。它对应的是页面文件的 `fileHash`，用于发现重复页面，而不是判断两本书是否完全相同。

### 误区 2：以为所有页面都会计算 hash

不是。根据 `BookAnalyzer.hashPages`，系统只对一本书开头和结尾的若干页计算 hash。数量由 `KomgaProperties.pageHashing` 控制，默认是 `3`。

这个策略符合重复页检测场景：常见重复内容通常出现在书籍开头或结尾，例如广告页、发布组页面、扫描说明页等。

### 误区 3：以为 `size` 不能为空

`size` 是 `Long?`，可以是 `null`。`PageHash` 明确允许页面大小未知。

而且如果传入负数，最终也会被转成 `null`：

```kotlin
val size: Long? = if (size != null && size < 0) null else size
```

所以调用方不应该假设 `size` 一定有值。

### 误区 4：以为负数 `size` 会抛异常

不会。`PageHash` 选择容错处理，把负数归一化为 `null`。这说明非法大小在这里被解释为“未知大小”，而不是致命错误。

### 误区 5：以为 `PageHash` 会直接被 API 返回

通常不会直接返回父类 `PageHash`。API 返回的是更具体的 DTO：

- `PageHashKnownDto`
- `PageHashUnknownDto`
- `PageHashMatchDto`

`PageHash` 的字段会通过子类间接进入 DTO，但 REST 层并不直接暴露 `PageHash` 这个父类。

### 误区 6：以为 unknown duplicate 已经有处理策略

`PageHashUnknown` 没有 `action` 字段。它只是系统发现的候选重复项。

只有 `PageHashKnown` 才有 `action`，也只有 known hash 才能表达：

- 自动删除
- 手动删除
- 忽略

### 误区 7：以为 `PageHashKnown.copy` 会保留审计时间

`PageHashKnown` 的 `copy` 方法只接收并传递这些字段：

```kotlin
hash
size
action
deleteCount
matchCount
```

它没有把原对象的 `createdDate`、`lastModifiedDate` 传进去，因此会使用构造函数默认值。实际更新时间在 `PageHashDao.update` 中会设置 `LAST_MODIFIED_DATE` 为当前时间。

根据当前片段推断，这个 `copy` 方法主要服务于领域更新，不是为了完整复制数据库记录。

### 误区 8：以为 `hash` 和 `size` 一起决定唯一性

从仓储和 DAO 代码看，查找 known、匹配页面、缩略图等操作都以 `hash` 为主键或查询条件：

```kotlin
findKnown(pageHash: String)
findMatchesByHash(pageHash: String, pageable: Pageable)
getKnownThumbnail(pageHash: String)
```

`size` 更像辅助信息，用于展示、排序或估算重复数据体积。是否唯一、是否匹配，核心依据是 `hash`。
