# 文件：komga/src/main/kotlin/org/gotson/komga/domain/service/SyncPointLifecycle.kt

## 它负责什么

`SyncPointLifecycle.kt` 定义了领域服务 `SyncPointLifecycle`，负责 Komga 的“同步点生命周期”操作。这里的同步点可以理解为一次同步快照：系统在某个时间点把当前用户可同步的书籍、阅读列表等内容记录下来，之后客户端可以拿“上一次成功同步的同步点”和“本次同步点”做差异比较，得到新增、变更、删除的数据。

这个文件本身不直接写 SQL，也不直接组装 API 返回 DTO。它处在领域服务层，主要职责有两类：

1. 创建同步点：根据用户、API Key、可选 library 过滤条件，生成一个 `SyncPoint`。
2. 分页领取待同步项目：从 `SyncPointRepository` 查询还没同步过的书籍或阅读列表，并在返回后立刻把这些条目标记为已同步，避免下一页或下一次请求重复返回。

它是一个 Spring 组件：

```kotlin
@Component
class SyncPointLifecycle(
  private val syncPointRepository: SyncPointRepository,
)
```

说明它由 Spring 容器托管，外部调用方通过依赖注入使用它。当前主要调用方是 Kobo API 的同步接口，位于 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/kobo/KoboController.kt`。

## 关键组成

### `createSyncPoint`

```kotlin
fun createSyncPoint(
  user: KomgaUser,
  apiKeyId: String?,
  libraryIds: List<String>?,
): SyncPoint
```

这是创建同步点的入口。它做了几件关键事情：

首先用当前用户创建 `SearchContext`：

```kotlin
val context = SearchContext(user)
```

`SearchContext` 表示这次查询发生在某个用户上下文中。后续仓储层可以据此套用权限、用户可见性等规则。根据当前片段推断，它不只是普通参数，而是领域查询的权限边界，因为 `SyncPointRepository.create` 和 `addOnDeck` 都接收它。

然后构造一个 `BookSearch`，其中的搜索条件是 `SearchCondition.AllOfBook`，即所有条件都要满足：

```kotlin
SearchCondition.AllOfBook(
  buildList {
    libraryIds?.let {
      add(
        SearchCondition.AnyOfBook(
          it.map { libraryId -> SearchCondition.LibraryId(SearchOperator.Is(libraryId)) },
        ),
      )
    }
    add(SearchCondition.MediaStatus(SearchOperator.Is(Media.Status.READY)))
    add(SearchCondition.MediaProfile(SearchOperator.Is(MediaProfile.EPUB)))
    add(SearchCondition.Deleted(SearchOperator.IsFalse))
  },
)
```

这些条件表达了同步点只收录适合 Kobo 同步的书籍：

- 如果传入 `libraryIds`，则只同步这些 library 下的书。
- `Media.Status.READY`：媒体必须已经分析完成、可用。
- `MediaProfile.EPUB`：只同步 EPUB 类型。
- `Deleted(false)`：排除已删除书籍。

随后调用：

```kotlin
syncPointRepository.create(apiKeyId, BookSearch(...), context)
```

仓储层负责真正创建 `SyncPoint`，并把符合搜索条件的书籍快照保存起来。

创建完成后又调用：

```kotlin
syncPointRepository.addOnDeck(syncPoint.id, context, libraryIds)
```

这一步会把 `On Deck` 阅读列表相关信息加入同步点。测试 `SyncPointLifecycleTest` 里可以看到，当用户阅读进度变化时，`ON_DECK_ID` 对应的 read list 会被视为新增、变更或删除。因此同步点不仅包含书籍，也包含特殊的阅读列表快照。

最后返回创建出的 `SyncPoint`。

### `takeBooks`

```kotlin
fun takeBooks(
  toSyncPointId: String,
  pageable: Pageable,
): Page<SyncPoint.Book>
```

它读取某个同步点中尚未同步的书籍：

```kotlin
syncPointRepository.findBooksById(toSyncPointId, true, pageable)
```

这里第二个参数 `true` 对应 `onlyNotSynced`，表示只查未同步项。

然后通过 `also` 做副作用：

```kotlin
.also { page ->
  syncPointRepository.markBooksSynced(
    toSyncPointId,
    false,
    page.content.map { it.bookId },
  )
}
```

也就是说，只要本页被取出，就会被标记为已同步。这个方法适合“没有上一同步点”的首次同步场景：直接取当前同步点里所有待同步书籍。

### `takeBooksAdded`

```kotlin
fun takeBooksAdded(
  fromSyncPointId: String,
  toSyncPointId: String,
  pageable: Pageable,
): Page<SyncPoint.Book>
```

查询两个同步点之间“新增”的书：

```kotlin
syncPointRepository.findBooksAdded(fromSyncPointId, toSyncPointId, true, pageable)
```

取出后标记为已同步：

```kotlin
syncPointRepository.markBooksSynced(toSyncPointId, false, page.content.map { it.bookId })
```

这里标记的是 `toSyncPointId` 上的条目，因为新增书存在于本次同步点中。

### `takeBooksChanged`

```kotlin
fun takeBooksChanged(
  fromSyncPointId: String,
  toSyncPointId: String,
  pageable: Pageable,
): Page<SyncPoint.Book>
```

查询两个同步点之间“内容发生变化”的书。变化依据不在当前文件中实现，而是在 `SyncPointRepository` 的实现层中判断。结合测试片段可知，文件修改时间、文件 hash、元数据变更等都可能被识别为 changed。

它同样只查询未同步项，并在返回后调用：

```kotlin
markBooksSynced(toSyncPointId, false, bookIds)
```

### `takeBooksRemoved`

```kotlin
fun takeBooksRemoved(
  fromSyncPointId: String,
  toSyncPointId: String,
  pageable: Pageable,
): Page<SyncPoint.Book>
```

查询两个同步点之间“被移除”的书：

```kotlin
syncPointRepository.findBooksRemoved(fromSyncPointId, toSyncPointId, true, pageable)
```

注意它标记同步时第二个参数是 `true`：

```kotlin
syncPointRepository.markBooksSynced(toSyncPointId, true, page.content.map { it.bookId })
```

`markBooksSynced` 的签名是：

```kotlin
fun markBooksSynced(
  syncPointId: String,
  forRemovedBooks: Boolean,
  bookIds: Collection<String>,
)
```

所以 `forRemovedBooks = true` 明确表示这是删除类条目的同步标记。原因是 removed books 在数据形态上可能不是普通“存在于当前同步点的书”，而是从旧同步点对比出来的删除结果。仓储层需要区分普通书籍条目和删除条目。

### `takeBooksReadProgressChanged`

```kotlin
fun takeBooksReadProgressChanged(
  fromSyncPointId: String,
  toSyncPointId: String,
  pageable: Pageable,
): Page<SyncPoint.Book>
```

查询“书本身没有变化，但阅读进度变化”的书。Kobo 同步需要把阅读状态同步给客户端，所以它独立于 added、changed、removed 存在。

它查询：

```kotlin
syncPointRepository.findBooksReadProgressChanged(fromSyncPointId, toSyncPointId, true, pageable)
```

并把这些书标记为已同步。这里 `forRemovedBooks` 是 `false`，因为阅读进度变化不是删除。

### `takeReadLists`

```kotlin
fun takeReadLists(
  toSyncPointId: String,
  pageable: Pageable,
): Page<SyncPoint.ReadList>
```

首次同步或直接读取某同步点下未同步阅读列表时使用。流程和 `takeBooks` 类似：

1. `findReadListsById(toSyncPointId, true, pageable)`
2. `markReadListsSynced(toSyncPointId, false, readListIds)`

### `takeReadListsAdded`

查询新增阅读列表：

```kotlin
syncPointRepository.findReadListsAdded(fromSyncPointId, toSyncPointId, true, pageable)
```

返回后：

```kotlin
markReadListsSynced(toSyncPointId, false, readListIds)
```

测试中 `On Deck` 列表首次出现时会被识别为 added。

### `takeReadListsChanged`

查询变更阅读列表：

```kotlin
syncPointRepository.findReadListsChanged(fromSyncPointId, toSyncPointId, true, pageable)
```

测试中，当用户继续读完一本书，`On Deck` 仍然存在但包含的下一本书变化时，会被识别为 changed。

### `takeReadListsRemoved`

查询删除阅读列表：

```kotlin
syncPointRepository.findReadListsRemoved(fromSyncPointId, toSyncPointId, true, pageable)
```

标记时传入 `forRemovedReadLists = true`：

```kotlin
syncPointRepository.markReadListsSynced(toSyncPointId, true, page.content.map { it.readListId })
```

测试中，当整个 series 都读完，`On Deck` 不再存在时，会被识别为 removed。

## 上下游关系

### 上游调用方

主要上游是 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/kobo/KoboController.kt`。

Kobo 同步接口会先从请求头里解析同步 token：

```kotlin
val syncTokenReceived = komgaSyncTokenGenerator.fromRequestHeaders(getCurrentRequest()) ?: KomgaSyncToken()
```

然后查找 ongoing sync point，如果没有就创建新的同步点：

```kotlin
val toSyncPoint =
  getSyncPointVerified(syncTokenReceived.ongoingSyncPointId, principal.user.id)
    ?: syncPointLifecycle.createSyncPoint(principal.user, principal.apiKey?.id, null)
```

这里传入的 `libraryIds` 是 `null`，旁边注释写着“for now we sync all libraries”，表示当前 Kobo 同步暂时同步所有 library。

接着 controller 会找上一次成功同步点：

```kotlin
val fromSyncPoint = getSyncPointVerified(syncTokenReceived.lastSuccessfulSyncPointId, principal.user.id)
```

如果存在 `fromSyncPoint`，就按固定顺序做增量同步：

1. `takeBooksAdded`
2. `takeBooksChanged`
3. `takeBooksRemoved`
4. `takeBooksReadProgressChanged`
5. `takeReadListsAdded`
6. `takeReadListsChanged`
7. `takeReadListsRemoved`

每一步都会受 `komgaProperties.kobo.syncItemLimit` 控制。上一类数据没取完时，后面的类别会被延后到下一次请求。这也是为什么 `SyncPointLifecycle` 的 take 方法要“取出并标记”：一个同步点可能通过多次 HTTP 请求逐页消费。

如果不存在 `fromSyncPoint`，根据当前片段推断，controller 会走首次同步逻辑，使用 `takeBooks`、`takeReadLists` 这类只依赖 `toSyncPointId` 的方法。

### 下游依赖

`SyncPointLifecycle` 的直接下游是 `SyncPointRepository`，定义在 `komga/src/main/kotlin/org/gotson/komga/domain/persistence/SyncPointRepository.kt`。

这个接口提供了完整的同步点持久化能力：

- `create`：创建同步点。
- `addOnDeck`：向同步点加入 On Deck 阅读列表。
- `findBooksById`：按同步点查询书。
- `findBooksAdded`、`findBooksRemoved`、`findBooksChanged`、`findBooksReadProgressChanged`：比较两个同步点的书籍差异。
- `findReadListsById`、`findReadListsAdded`、`findReadListsChanged`、`findReadListsRemoved`：查询阅读列表快照和差异。
- `markBooksSynced`、`markReadListsSynced`：把已经发给客户端的项目标记为同步完成。
- `deleteByUserId`、`deleteByUserIdAndApiKeyIds`、`deleteOne`、`deleteAll`：清理同步点。

实际实现位于 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/SyncPointDao.kt`。当前文件不关心 SQL 细节，只依赖接口。

### 领域模型

`SyncPoint` 模型定义在 `komga/src/main/kotlin/org/gotson/komga/domain/model/SyncPoint.kt`。

顶层字段包括：

- `id`
- `userId`
- `apiKeyId`
- `createdDate`

内部还有两个嵌套数据类：

- `SyncPoint.Book`
- `SyncPoint.ReadList`

`SyncPoint.Book` 包含 `bookId`、创建时间、修改时间、文件修改时间、文件大小、文件 hash、元数据修改时间、封面缩略图 id、`synced` 等字段。它们是判断书籍新增、变更、是否已同步的基础数据。

`SyncPoint.ReadList` 表示同步点内的阅读列表快照，包含 `readListId`、名称、创建时间等信息。测试中 `ON_DECK_ID` 就是一个特殊 read list。

### import 关系

当前文件 import 的核心类型可以分成几组：

- 搜索相关：`BookSearch`、`SearchCondition`、`SearchContext`、`SearchOperator`
- 用户与媒体相关：`KomgaUser`、`Media`、`MediaProfile`
- 同步点模型：`SyncPoint`
- 仓储接口：`SyncPointRepository`
- Spring / 分页：`Page`、`Pageable`、`Component`

这些 import 说明 `SyncPointLifecycle` 的定位是“用领域搜索条件创建快照，然后用分页方式消费快照差异”。

## 运行/调用流程

### 创建同步点流程

1. Kobo 客户端发起同步请求。
2. `KoboController` 从请求头解析 sync token。
3. 如果 token 里没有可继续使用的 ongoing sync point，调用 `createSyncPoint`。
4. `createSyncPoint` 用当前 `KomgaUser` 创建 `SearchContext`。
5. 构造 `BookSearch`：
   - 限定 library，可选。
   - 限定媒体状态为 `READY`。
   - 限定媒体 profile 为 `EPUB`。
   - 排除 deleted book。
6. 调用 `syncPointRepository.create` 创建书籍快照。
7. 调用 `syncPointRepository.addOnDeck` 补充 `On Deck` 阅读列表快照。
8. 返回新的 `SyncPoint` 给 controller。
9. controller 把这个同步点作为本次同步目标 `toSyncPoint`。

### 增量同步流程

当存在上一次成功同步点 `fromSyncPoint` 时，controller 会拿它和本次 `toSyncPoint` 比较。

整体流程是：

1. 先取新增书籍：`takeBooksAdded(from, to, pageable)`。
2. 如果新增书籍这一页已经取完，并且还有剩余额度，取变更书籍：`takeBooksChanged(from, to, pageable)`。
3. 如果变更书籍取完，取删除书籍：`takeBooksRemoved(from, to, pageable)`。
4. 如果删除书籍取完，取阅读进度变化：`takeBooksReadProgressChanged(from, to, pageable)`。
5. 再依次取阅读列表新增、变更、删除。
6. 每个 `take...` 方法都会只查 `onlyNotSynced = true` 的条目。
7. 每页返回后，立刻调用 `markBooksSynced` 或 `markReadListsSynced`。
8. 如果某个分类还有下一页，controller 会设置 `shouldContinueSync`，客户端下次请求继续同一个 ongoing sync point。

这个流程的关键点是：`SyncPointLifecycle` 不负责决定“先同步哪类数据”，顺序控制在 `KoboController`；它只保证每类数据的“领取一页 + 标记已领取”是统一的。

### 首次同步流程

当没有 `fromSyncPoint` 时，不存在“两个同步点之间的差异”。此时应该直接把当前同步点内的内容发给客户端。

当前文件为这种场景提供了：

- `takeBooks(toSyncPointId, pageable)`
- `takeReadLists(toSyncPointId, pageable)`

它们只需要一个 `toSyncPointId`，不做 added/changed/removed 对比。

### 分页和已同步标记

所有 `take...` 方法都有同一个模式：

```kotlin
syncPointRepository
  .findSomething(..., true, pageable)
  .also { page ->
    syncPointRepository.markSomethingSynced(..., page.content.map { it.id })
  }
```

这里的 `also` 很重要。它表示返回值仍然是查询出来的 `Page`，但在返回之前执行一个副作用：标记本页内容已同步。

所以调用方拿到的数据是“刚刚被标记过的那一页”。这能支持断点式同步：客户端每次拿一页，服务端记住这一页已经发出过，下次继续拿剩下的。

## 小白阅读顺序

1. 先读 `komga/src/main/kotlin/org/gotson/komga/domain/model/SyncPoint.kt`  
   理解 `SyncPoint` 是什么，以及 `SyncPoint.Book`、`SyncPoint.ReadList` 保存哪些快照字段。重点看 `synced` 字段，它解释了为什么 take 方法会标记已同步。

2. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/persistence/SyncPointRepository.kt`  
   这个接口列出了同步点能做的所有动作。先不用看实现，只要理解 `findBooksAdded`、`findBooksChanged`、`findBooksRemoved`、`markBooksSynced` 这些方法名即可。

3. 然后读当前文件 `komga/src/main/kotlin/org/gotson/komga/domain/service/SyncPointLifecycle.kt`  
   重点看两个模式：
   - `createSyncPoint` 如何构造搜索条件并创建快照。
   - `take...` 方法如何查询未同步数据并标记已同步。

4. 接着读 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/kobo/KoboController.kt` 的同步接口片段  
   看 controller 如何根据 sync token 找 `fromSyncPoint` 和 `toSyncPoint`，再按 added、changed、removed 的顺序调用 `SyncPointLifecycle`。

5. 最后读 `komga/src/test/kotlin/org/gotson/komga/domain/service/SyncPointLifecycleTest.kt`  
   这个测试能帮你建立业务直觉：READY + EPUB 的书才进入同步点；新增书分多页领取后不会重复；删除书、变更书、On Deck 阅读列表变化都会被识别出来。

## 常见误区

### 误区一：以为 `SyncPointLifecycle` 负责比较差异

它不直接比较两个同步点的字段。真正的差异查询在 `SyncPointRepository` 的实现中，例如 `SyncPointDao`。当前文件只是选择调用哪种查询方法，并处理“已同步标记”。

### 误区二：以为 `takeBooksAdded` 只是查询，不会修改状态

所有 `take...` 方法都有副作用。它们在返回 `Page` 之前会调用 `markBooksSynced` 或 `markReadListsSynced`。所以这些方法不是纯查询方法，调用一次就会改变同步点内条目的 `synced` 状态。

### 误区三：忽略 `onlyNotSynced = true`

每个查询都传入 `true`，意味着只取尚未同步的项目。这是分页同步能够继续推进的基础。如果直接调用 repository 且传入 `false`，会得到包含已同步项在内的结果，行为就不一样。

### 误区四：不理解 removed 为什么单独传 `true`

`takeBooksRemoved` 调用 `markBooksSynced(toSyncPointId, true, ...)`，`takeReadListsRemoved` 调用 `markReadListsSynced(toSyncPointId, true, ...)`。这个 `true` 不是“是否同步成功”，而是“这批 id 属于 removed 类型”。普通 added/changed/read progress changed 都传 `false`。

### 误区五：以为 `libraryIds = null` 表示不同步任何库

在 `createSyncPoint` 里，只有 `libraryIds?.let { ... }` 非空时才添加 library 条件。因此 `libraryIds = null` 表示不按 library 过滤，也就是同步所有当前用户上下文可见且符合条件的书。`KoboController` 当前就是这样调用的，并有注释说明暂时同步所有 libraries。

### 误区六：以为所有媒体都会进入 Kobo 同步点

不会。当前同步点创建时明确要求：

- `Media.Status.READY`
- `MediaProfile.EPUB`
- `Deleted` 为 false

所以未分析完成、分析失败、非 EPUB、已删除的书不会作为普通可同步书籍进入新同步点。测试里也覆盖了 not ready 和 not epub 被排除的情况。

### 误区七：把 `On Deck` 当成普通 read list 来源

`createSyncPoint` 在创建书籍快照后专门调用 `addOnDeck`。这说明 `On Deck` 是同步点创建过程额外加入的特殊阅读列表数据，不只是普通 read list 查询结果。测试中它会根据阅读进度变化表现为 added、changed 或 removed。
