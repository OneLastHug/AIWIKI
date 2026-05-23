# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/PageHashKnown.kt

## 它负责什么

`PageHashKnown.kt` 定义了领域模型 `PageHashKnown`，表示系统已经“识别并登记过”的页面哈希。它属于 `org.gotson.komga.domain.model` 包，是 Komga 重复页面检测/处理功能中的核心对象之一。

在 Komga 中，页面哈希用于判断不同书籍或归档文件里的页面图片是否重复。和它相邻的模型有：

- `PageHash`：页面哈希的基础模型，只包含 `hash` 和 `size`。
- `PageHashUnknown`：系统发现有重复匹配，但还没有被管理员标记处理策略的哈希。
- `PageHashKnown`：管理员或系统已经知道这个哈希，并给它设置了处理动作。
- `PageHashMatch`：某个哈希命中的具体页面位置，例如 `bookId`、`pageNumber`、`fileName` 等。

所以，`PageHashKnown` 不是“某一页”的模型，而是“某一种重复页面指纹”的管理记录。它记录这个哈希应该如何处理，以及它被匹配、删除过多少次。

## 关键组成

`PageHashKnown` 的声明如下：

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

几个字段的含义：

- `hash: String`：页面文件哈希，继承自 `PageHash`，用于唯一识别相同页面内容。
- `size: Long?`：页面文件大小，传给 `PageHash`。基类会把负数大小归一化为 `null`。
- `action: Action`：这个已知哈希的处理策略，是本文件最重要的业务字段。
- `deleteCount: Int`：基于这个哈希删除重复页面的累计次数。
- `matchCount: Int`：当前或查询时统计到的匹配数量。根据 `PageHashDao.findAllKnown` 的查询片段可见，它来自页面表里 `FILE_HASH` 的聚合计数。
- `createdDate: LocalDateTime`：创建时间，实现 `Auditable`。
- `lastModifiedDate: LocalDateTime`：最后修改时间，实现 `Auditable`，默认等于 `createdDate`。

`Action` 是内部枚举：

```kotlin
enum class Action {
  DELETE_AUTO,
  DELETE_MANUAL,
  IGNORE,
}
```

三个动作可以这样理解：

- `DELETE_AUTO`：系统可以自动删除匹配这个哈希的重复页面。
- `DELETE_MANUAL`：该哈希被标记为需要人工删除或人工确认。
- `IGNORE`：忽略这个重复页面哈希，不作为需要删除的目标。

从调用方可以确认，`DELETE_AUTO` 会被 `PageHashLifecycle.getBookPagesToDeleteAutomatically` 用来查询自动删除目标：

```kotlin
pageHashRepository.findMatchesByKnownHashAction(listOf(PageHashKnown.Action.DELETE_AUTO), library.id)
```

文件中还定义了一个手写的 `copy` 方法：

```kotlin
fun copy(
  hash: String = this.hash,
  size: Long? = this.size,
  action: Action = this.action,
  deleteCount: Int = this.deleteCount,
  matchCount: Int = this.matchCount,
) = PageHashKnown(
  hash = hash,
  size = size,
  action = action,
  deleteCount = deleteCount,
  matchCount = matchCount,
)
```

这说明 `PageHashKnown` 不是 Kotlin `data class`，但作者仍希望它能像数据类一样方便地基于旧对象创建新对象。例如在 `BookPageEditor` 中，删除重复页面后会这样递增删除计数：

```kotlin
pageHashRepository.update(it.copy(deleteCount = it.deleteCount + 1))
```

在 `PageHashLifecycle.createOrUpdate` 中，更新已存在记录的动作时会这样做：

```kotlin
pageHashRepository.update(existing.copy(action = pageHash.action))
```

需要注意：这个 `copy` 方法没有暴露 `createdDate` 和 `lastModifiedDate` 参数。单看当前文件，它创建的新对象会使用构造函数里的默认时间。持久化层最终如何处理审计字段，需要结合 DAO 的 `update` 实现判断；根据当前片段推断，审计时间可能主要由数据库或 DAO 更新逻辑控制，而不是由这个 `copy` 方法完整保留。

## 上下游关系

上游主要来自重复页面检测、管理员 API 标记和页面哈希扫描流程。

`PageHashKnown` 的创建入口之一是 REST API：`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/PageHashController.kt`。

当管理员调用 `PUT api/v1/page-hashes` 标记某个重复页面哈希时，控制器会把请求 DTO 转成领域对象：

```kotlin
PageHashKnown(
  hash = pageHash.hash,
  size = pageHash.size,
  action = pageHash.action,
)
```

然后交给：

```kotlin
pageHashLifecycle.createOrUpdate(...)
```

`PageHashLifecycle` 位于 `komga/src/main/kotlin/org/gotson/komga/domain/service/PageHashLifecycle.kt`。它负责判断这个哈希是否已经存在：

- 不存在：调用 `pageHashRepository.insert(pageHash, getPage(pageHash.hash, 500)?.bytes)` 插入，并尝试保存一张缩略图。
- 已存在：调用 `pageHashRepository.update(existing.copy(action = pageHash.action))` 更新动作。

下游主要是持久化、API 输出和重复页删除流程。

持久化接口是 `komga/src/main/kotlin/org/gotson/komga/domain/persistence/PageHashRepository.kt`，它围绕 `PageHashKnown` 提供这些能力：

- `findKnown(pageHash: String): PageHashKnown?`
- `findAllKnown(actions: List<PageHashKnown.Action>?, pageable: Pageable): Page<PageHashKnown>`
- `findMatchesByKnownHashAction(actions: List<PageHashKnown.Action>?, libraryId: String?): Map<String, Collection<BookPageNumbered>>`
- `getKnownThumbnail(pageHash: String): ByteArray?`
- `insert(pageHash: PageHashKnown, thumbnail: ByteArray?)`
- `update(pageHash: PageHashKnown)`

API 输出 DTO 是 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/PageHashKnownDto.kt`。它把领域对象转成接口返回结构：

```kotlin
PageHashKnownDto(
  hash = hash,
  size = size,
  action = action,
  deleteCount = deleteCount,
  matchCount = matchCount,
  created = createdDate.toUTC(),
  lastModified = lastModifiedDate.toUTC(),
)
```

这说明 `PageHashKnown` 的字段基本都会暴露给管理员 API，尤其是 `action`、`deleteCount`、`matchCount` 和审计时间。

删除流程中，`BookPageEditor` 删除重复页面后，会找到对应的 `PageHashKnown` 并递增 `deleteCount`：

```kotlin
pagesToDelete
  .mapNotNull { pageHashRepository.findKnown(it.fileHash) }
  .forEach { pageHashRepository.update(it.copy(deleteCount = it.deleteCount + 1)) }
```

任务调度层也会使用它。`TaskHandler` 会触发查找重复页和删除重复页任务；其中自动删除候选来自 `PageHashLifecycle.getBookPagesToDeleteAutomatically`，而这个方法只查询 `Action.DELETE_AUTO` 的已知哈希。

## 运行/调用流程

一个典型流程可以分成两条线：发现重复页面、处理已知重复页面。

第一条线是发现重复页面：

1. `BookAnalyzer` 在分析书籍时会给部分页面计算 `fileHash`。从注释和代码片段可见，受 `KomgaProperties.pageHashing` 控制，通常会对书籍开头和结尾若干页做哈希。
2. `PageHashRepository.findAllUnknown` 会在页面表中聚合 `FILE_HASH`，筛选出现次数大于 1 且还没有进入已知哈希表的记录。
3. API `GET api/v1/page-hashes/unknown` 返回这些 `PageHashUnknown`，管理员可以看到“未知重复哈希”。

第二条线是把未知哈希变成已知哈希并处理：

1. 管理员通过 `PUT api/v1/page-hashes` 提交 `hash`、`size`、`action`。
2. `PageHashController.createOrUpdateKnownPageHash` 创建 `PageHashKnown`。
3. `PageHashLifecycle.createOrUpdate` 查询是否已有该哈希。
4. 如果没有，调用 `PageHashRepository.insert` 保存 `PageHashKnown`，并通过 `getPage(hash, 500)` 找一个匹配页面生成缩略图。
5. 如果已有，使用 `existing.copy(action = pageHash.action)` 更新处理动作。
6. 后续如果 `action` 是 `DELETE_AUTO`，`PageHashLifecycle.getBookPagesToDeleteAutomatically` 会把它纳入自动删除候选。
7. 删除实际发生在 `BookPageEditor` 等服务中。删除完成后，系统根据页面的 `fileHash` 找回 `PageHashKnown`，并更新 `deleteCount`。
8. 管理员再通过 `GET api/v1/page-hashes` 查看已知哈希列表时，`PageHashKnownDto` 会返回动作、删除次数、匹配数量和时间信息。

还有一条手动删除路径：`PageHashController` 提供了 `POST {pageHash}/delete-all` 和 `POST {pageHash}/delete-match`。这两个接口根据具体哈希找到匹配页面，构造 `BookPageNumbered`，再交给 `TaskEmitter.removeDuplicatePages`。这类接口不一定依赖 `PageHashKnown.action`，而是直接按指定哈希删除。

## 小白阅读顺序

建议按下面顺序读，不要一开始就钻 DAO SQL：

1. 先读 `komga/src/main/kotlin/org/gotson/komga/domain/model/PageHash.kt`  
   这是基类，只要理解 `hash` 和 `size`。特别注意 `size < 0` 会变成 `null`。

2. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/model/PageHashKnown.kt`  
   重点看 `action`、`deleteCount`、`matchCount`、`Action` 枚举和手写 `copy`。

3. 对比读 `komga/src/main/kotlin/org/gotson/komga/domain/model/PageHashUnknown.kt`  
   你会发现 unknown 只有 `matchCount`，没有 `action` 和审计字段。这能帮助理解 known/unknown 的区别：unknown 是“系统发现了重复但还没决策”，known 是“已经登记了处理策略”。

4. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/persistence/PageHashRepository.kt`  
   这里能看到 `PageHashKnown` 在领域层需要哪些持久化能力，例如查找、分页、插入、更新、取缩略图。

5. 接着读 `komga/src/main/kotlin/org/gotson/komga/domain/service/PageHashLifecycle.kt`  
   这是理解生命周期的关键：创建、更新、自动删除候选都在这里串起来。

6. 最后读 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/PageHashController.kt` 和 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/PageHashKnownDto.kt`  
   这里能看到它如何被管理员 API 使用，以及哪些字段会暴露给前端。

如果还想深入数据库行为，再去看 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/PageHashDao.kt`。它会告诉你 `matchCount` 是如何从页面表聚合出来的，以及 known/unknown 的 SQL 查询差异。

## 常见误区

第一个误区：把 `PageHashKnown` 理解成一本书的一页。  
它不是具体页面，而是某个页面内容哈希的管理记录。具体命中的页面位置由 `PageHashMatch` 或 `BookPageNumbered` 表达。

第二个误区：以为 `DELETE_AUTO` 会立刻删除页面。  
`PageHashKnown.Action.DELETE_AUTO` 只是策略标记。真正删除还需要任务调度和 `BookPageEditor` 等服务执行。`PageHashLifecycle.getBookPagesToDeleteAutomatically` 只是把这些哈希对应的页面找出来。

第三个误区：认为 `matchCount` 是手动维护的字段。  
从 `PageHashDao.findAllKnown` 的查询片段看，`matchCount` 是通过页面表里匹配该哈希的记录数聚合得到的，并传入 `toDomain(count)`。它更像查询视图字段，而不是用户直接设置的业务状态。

第四个误区：认为 `copy` 和 Kotlin `data class copy` 完全一样。  
`PageHashKnown` 不是 `data class`，这里的 `copy` 是手写方法。它只复制 `hash`、`size`、`action`、`deleteCount`、`matchCount`，没有复制 `createdDate`、`lastModifiedDate` 参数。阅读更新时间相关逻辑时，需要继续看持久化层如何处理审计字段，不能只凭这个方法下结论。

第五个误区：忽略 `PageHash` 对 `size` 的处理。  
`PageHashKnown` 把 `size` 传给父类 `PageHash`。如果传入负数，最终 `size` 会变成 `null`。所以不要在业务里假设构造参数的原始 `size` 一定被保留。

第六个误区：以为 known 和 unknown 是两张完全无关的业务。  
它们其实是同一套重复页识别流程的两个阶段：`PageHashUnknown` 表示“重复但未决策”，`PageHashKnown` 表示“重复且已有处理策略”。`findAllUnknown` 会排除已经存在于 known 表中的哈希，这说明二者在列表语义上是互斥的。
