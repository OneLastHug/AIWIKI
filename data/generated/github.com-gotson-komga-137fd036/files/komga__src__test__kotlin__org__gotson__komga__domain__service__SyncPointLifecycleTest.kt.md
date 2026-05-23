# 文件：komga/src/test/kotlin/org/gotson/komga/domain/service/SyncPointLifecycleTest.kt

## 它负责什么

`SyncPointLifecycleTest.kt` 是 `SyncPointLifecycle` 的 Spring Boot 集成测试，重点验证 Komga 的 “sync point” 同步快照机制是否正确工作。

这里的 `SyncPoint` 可以理解为某个用户在某个时间点可同步内容的快照。它主要服务 Kobo 同步接口：设备每次同步时，Komga 会创建或复用一个目标同步点，然后把它和上一次成功同步点进行比较，得到新增、变更、删除的书籍，以及新增、变更、删除的阅读列表。

这个测试文件验证了几类核心行为：

1. 创建同步点时，只把当前用户真正有权限、可同步、可读取的 EPUB 书籍纳入快照。
2. 两个同步点之间新增的书籍能被识别出来。
3. 两个同步点之间删除或软删除的书籍能被识别出来。
4. 两个同步点之间文件信息、元数据、封面等变化能被识别为书籍变更。
5. Kobo 的特殊 `On Deck` 阅读列表能随着阅读进度变化而新增、变更、删除。
6. `takeBooksAdded`、`takeBooksChanged`、`takeBooksRemoved`、`takeReadListsAdded` 等方法具有“取出并标记为已同步”的副作用。

它不是普通单元测试，而是依赖真实 Spring 容器、真实仓储实现和数据库测试上下文的集成测试。

## 关键组成

测试类声明：

```kotlin
@SpringBootTest
class SyncPointLifecycleTest(...)
```

`@SpringBootTest` 表示测试会启动 Spring Boot 应用上下文，通过构造函数注入真实组件。这个文件没有 mock，测试对象直接连接领域服务和持久化层。

主要注入对象包括：

`SyncPointLifecycle`：被测对象，位于 `komga/src/main/kotlin/org/gotson/komga/domain/service/SyncPointLifecycle.kt`。它负责创建同步点，以及分页取出未同步的差异项并标记为已同步。

`SyncPointRepository`：同步点仓储接口，位于 `komga/src/main/kotlin/org/gotson/komga/domain/persistence/SyncPointRepository.kt`。测试中直接用它查询同步点中的书籍、阅读列表和差异结果。

`LibraryRepository`、`KomgaUserRepository`、`BookRepository`、`SeriesRepository`、`MediaRepository`、`BookMetadataRepository`、`SeriesMetadataRepository`：用于构造测试数据和修改测试状态。

`BookLifecycle`、`SeriesLifecycle`：用于按业务流程创建 series、添加 book、删除 book、标记阅读完成，而不是直接裸写所有表。

测试数据初始化集中在类字段和生命周期钩子里：

```kotlin
private val library1 = makeLibrary()
private val library2 = makeLibrary()
private val library3 = makeLibrary()
```

`user1` 是关键测试用户：

```kotlin
KomgaUser(
  "user1@example.org",
  "",
  sharedLibrariesIds = setOf(library1.id, library2.id),
  restrictions =
    ContentRestrictions(
      ageRestriction = AgeRestriction(18, AllowExclude.EXCLUDE),
      labelsExclude = setOf("exclude"),
    ),
)
```

这个用户只能访问 `library1`、`library2`，同时排除年龄评级超过限制的内容，以及带有 `exclude` 分享标签的内容。后续测试创建同步点时，会验证这些限制是否通过 `SearchContext(user)` 被正确应用。

测试生命周期方法：

`setup library`：在 `@BeforeAll` 中插入 3 个 library 和用户。

`clear repository`：在 `@AfterEach` 中通过 `seriesLifecycle.deleteMany(seriesRepository.findAll())` 清理每个测试创建的 series 及其关联 book。

`teardown`：在 `@AfterAll` 中清空 library、sync point、user。

核心生产逻辑在 `SyncPointLifecycle.createSyncPoint`：

```kotlin
fun createSyncPoint(
  user: KomgaUser,
  apiKeyId: String?,
  libraryIds: List<String>?,
): SyncPoint
```

它会构建 `BookSearch`，条件包括：

`LibraryId`：如果传入 `libraryIds`，只同步这些 library。

`MediaStatus == READY`：只同步媒体已就绪的书。

`MediaProfile == EPUB`：只同步 EPUB profile。

`Deleted == false`：排除已删除内容。

同时，`SearchContext(user)` 会把用户权限和内容限制带入查询。

创建主同步点后，还会调用：

```kotlin
syncPointRepository.addOnDeck(syncPoint.id, context, libraryIds)
```

这会把用户当前的 `On Deck` 内容写入同步点的阅读列表快照。

测试中使用的 `ON_DECK_ID` 来自：

```kotlin
SyncPoint.ReadList.Companion.ON_DECK_ID
```

其值定义在 `komga/src/main/kotlin/org/gotson/komga/domain/model/SyncPoint.kt`：

```kotlin
const val ON_DECK_ID = "KOMGA-ONDECK"
```

## 上下游关系

上游调用方主要是 Kobo 同步接口。

生产代码中，`KoboController.syncLibrary` 位于 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/kobo/KoboController.kt`，它会读取 Kobo 同步 token，找到上一次成功同步点和当前正在同步的同步点。

如果没有正在同步的目标同步点，会调用：

```kotlin
syncPointLifecycle.createSyncPoint(principal.user, principal.apiKey?.id, null)
```

如果存在上一次成功同步点，接口会依次取差异：

```kotlin
takeBooksAdded
takeBooksChanged
takeBooksRemoved
takeBooksReadProgressChanged
takeReadListsAdded
takeReadListsChanged
takeReadListsRemoved
```

如果没有上一次同步点，就走全量同步：

```kotlin
takeBooks
takeReadLists
```

这些 `take*` 方法的共同特点是：从仓储中查询 `onlyNotSynced = true` 的数据，并在返回后把这些数据标记为已同步。例如 `takeBooksAdded` 会调用 `findBooksAdded`，然后调用 `markBooksSynced`。

下游实现主要是 `SyncPointDao`，位于 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/SyncPointDao.kt`。它是 `SyncPointRepository` 的 jOOQ 实现，负责真正向数据库表写入同步点快照，并比较两个同步点之间的差异。

关键表含义根据当前片段可推断如下：

`SYNC_POINT`：同步点主表，保存 id、user id、api key id、创建时间。

`SYNC_POINT_BOOK`：某个同步点内的书籍快照，保存 book id、文件修改时间、文件大小、文件 hash、元数据修改时间、阅读进度修改时间、封面 id、是否已同步等。

`SYNC_POINT_BOOK_REMOVED_SYNCED`：已同步过的“删除书籍”记录。删除项来自旧同步点，不存在于新同步点，所以需要单独记录它们是否已经被推送给设备。

`SYNC_POINT_READLIST`：某个同步点内的阅读列表快照。

`SYNC_POINT_READLIST_BOOK`：同步点阅读列表和书籍的关联。

`SYNC_POINT_READLIST_REMOVED_SYNCED`：已同步过的“删除阅读列表”记录。

还有一个 REST 管理入口 `SyncPointController`，位于 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/SyncPointController.kt`。它提供：

```kotlin
DELETE api/v1/syncpoints/me
```

用于删除当前用户的同步点。如果传入 `key_id`，只删除指定 API key 关联的同步点。接口说明里也写明：删除同步点会让 Kobo 下一次从头同步。

## 运行/调用流程

第一个测试：`given user when creating syncpoint then all in-scope books are included`

这个测试验证创建同步点时的过滤规则。

它构造了多本书：

`bookValid`：合法书，属于 `library1`，文件 hash、大小、修改时间齐全。

`bookExcludedByAge`：所在 series 的 `ageRating` 被改成 20，会被用户的 `AgeRestriction(18, EXCLUDE)` 排除。

`bookExcludedByLabel`：所在 series 的 `sharingLabels` 被设置为 `exclude`，会被用户的 `labelsExclude` 排除。

`bookDeleted`：设置了 `deletedDate`，应被排除。

`bookNotReady`：媒体状态改成 `Media.Status.ERROR`，应被排除。

`bookNotEpub`：媒体类型改成 ZIP，非 EPUB，应被排除。

`bookOtherLibrary`：属于 `library2`，用户虽然有权限，但本次调用传入 `listOf(library1.id)`，所以应被排除。

`bookUnauthorizedLibrary`：属于 `library3`，用户没有共享权限，也应被排除。

然后调用：

```kotlin
val syncPoint = syncPointLifecycle.createSyncPoint(user1, null, listOf(library1.id))
```

最后通过：

```kotlin
syncPointRepository.findBooksById(syncPoint.id, false, Pageable.unpaged())
```

验证同步点里只剩 `bookValid` 一本，并且同步点记录里的 `fileHash`、`fileSize`、`fileLastModified` 与原书一致。

第二个测试：`given syncpoint when adding new books then syncpoint diff contains new books`

流程是：

1. 创建 `book1`。
2. 创建 `syncPoint1`。
3. 再往同一个 series 添加 `book2`、`book3`。
4. 创建 `syncPoint2`。
5. 查询 `findBooksAdded(syncPoint1.id, syncPoint2.id, false, ...)`。

断言新增差异包含 `book2`、`book3`。

随后又连续调用两次：

```kotlin
val page1 = syncPointLifecycle.takeBooksAdded(...)
val page2 = syncPointLifecycle.takeBooksAdded(...)
```

每次 `Pageable.ofSize(1)`，所以第一次取一个新增项并标记已同步，第二次再取另一个。测试断言两页不会返回同一本书，证明 `takeBooksAdded` 有“取出后标记”的副作用。

第三个测试：`given syncpoint when deleting books then syncpoint diff contains removed books`

流程是：

1. 创建 `book1`、`book2`、`book3`。
2. 创建 `syncPoint1`。
3. 对 `book2` 执行软删除：`bookLifecycle.softDeleteMany(...)`。
4. 对 `book3` 执行硬删除：`bookLifecycle.deleteOne(...)`。
5. 创建 `syncPoint2`。
6. 查询 `findBooksRemoved(syncPoint1.id, syncPoint2.id, false, ...)`。

断言删除差异包含 `book2`、`book3`。

这里的重要点是：删除差异不是从新同步点里找，而是从旧同步点里找“旧同步点存在、新同步点不存在”的 book。`SyncPointDao.findBooksRemoved` 也是这样实现的。

随后同样用两次 `takeBooksRemoved(... Pageable.ofSize(1))` 验证删除项会被逐个取出并标记。

第四个测试：`given syncpoint when changing books then syncpoint diff contains changed books`

流程是：

1. 创建 `book1`、`book2`、`book3`。
2. 创建 `syncPoint1`。
3. 修改 `book1.fileLastModified`。
4. 修改 `book2.fileHash`。
5. 修改 `book3` 的 metadata title。
6. 创建 `syncPoint2`。
7. 查询 `findBooksChanged(syncPoint1.id, syncPoint2.id, false, ...)`。

断言变更差异包含 `book1`、`book2`、`book3`。

生产实现中，`findBooksChanged` 比较的是两个同步点内同一本书的快照字段，包括：

`BOOK_FILE_LAST_MODIFIED`

`BOOK_FILE_SIZE`

`BOOK_FILE_HASH`

`BOOK_METADATA_LAST_MODIFIED_DATE`

`BOOK_THUMBNAIL_ID`

注意它不把阅读进度变化放进 `findBooksChanged`。阅读进度变化有单独的 `findBooksReadProgressChanged`。

测试后半段连续调用三次 `takeBooksChanged(... PageRequest.ofSize(1))`，每次取一个变更项，并断言三次返回的 book id 互不重复。

第五个测试：`given syncpoint when books are read then syncpoint diff contains on deck read list`

这个测试验证 Kobo `On Deck` 阅读列表的生命周期。

它创建同一 series 下的三本书，编号分别是 1、2、3，然后全部设为 READY + EPUB。

第一阶段：

创建 `syncPoint1`。此时没有书被读完，`On Deck` 为空，所以：

```kotlin
syncPointRepository.findReadListsById(syncPoint1.id, false, ...)
```

应返回空。

第二阶段：

调用：

```kotlin
bookLifecycle.markReadProgressCompleted(book1.id, user1)
```

把第一本书标记读完，再创建 `syncPoint2`。

此时 `On Deck` 应出现，并包含下一本书 `book2`。测试断言：

`findReadListsAdded(syncPoint1.id, syncPoint2.id, ...)` 包含 `ON_DECK_ID`。

`findReadListsChanged` 为空。

`findReadListsRemoved` 为空。

`findBookIdsByReadListIds(syncPoint2.id, listOf(ON_DECK_ID))` 返回 `book2.id`。

第三阶段：

把 `book2` 标记读完，创建 `syncPoint3`。

此时 `On Deck` 仍然存在，但内容从 `book2` 变成 `book3`。测试断言：

`findReadListsAdded` 为空。

`findReadListsChanged` 包含 `ON_DECK_ID`。

`findReadListsRemoved` 为空。

`findBookIdsByReadListIds` 返回 `book3.id`。

第四阶段：

把 `book3` 也标记读完，创建 `syncPoint4`。

整个 series 已读完，不再有下一本可推荐的 `On Deck` 内容。测试断言：

`findReadListsById(syncPoint4.id, ...)` 为空。

`findReadListsRemoved(syncPoint3.id, syncPoint4.id, ...)` 包含 `ON_DECK_ID`。

然后调用两次 `takeReadListsRemoved`，验证删除的阅读列表只会被取出一次，第二次为空。

## 小白阅读顺序

建议先读 `komga/src/main/kotlin/org/gotson/komga/domain/model/SyncPoint.kt`。

这个文件最短，先理解 `SyncPoint`、`SyncPoint.Book`、`SyncPoint.ReadList` 的字段。尤其要注意：同步点中的 book 不是完整 `Book` 实体，而是一份用于比较的快照，包含文件、元数据、阅读进度和封面相关时间戳或标识。

第二步读 `komga/src/main/kotlin/org/gotson/komga/domain/persistence/SyncPointRepository.kt`。

这里能看到同步点仓储的完整能力：创建、添加 `On Deck`、查全量书籍、查新增、查删除、查变更、查阅读进度变更、查阅读列表，以及标记已同步。

第三步读 `komga/src/main/kotlin/org/gotson/komga/domain/service/SyncPointLifecycle.kt`。

重点看两类方法：

`createSyncPoint`：负责定义“哪些书应该进入同步点”。

`take*`：负责定义“取哪些未同步差异，并标记为已同步”。

读到这里再回到测试文件，会更容易理解为什么测试连续调用 `takeBooksAdded`、`takeBooksChanged`、`takeReadListsRemoved`。

第四步读 `komga/src/test/kotlin/org/gotson/komga/domain/service/SyncPointLifecycleTest.kt`。

按测试方法从上到下读即可：

1. 先看创建同步点时的过滤条件。
2. 再看新增差异。
3. 再看删除差异。
4. 再看变更差异。
5. 最后看 `On Deck` 阅读列表。

第五步如果想理解 SQL 层，再读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/SyncPointDao.kt`。

这里的关键是比较两个同步点：

`findBooksAdded`：新同步点有，旧同步点没有。

`findBooksRemoved`：旧同步点有，新同步点没有。

`findBooksChanged`：两个同步点都有同一本书，但文件、元数据或封面字段不同。

`findBooksReadProgressChanged`：书本身没变，但阅读进度时间戳变了。

`findReadListsAdded`、`findReadListsChanged`、`findReadListsRemoved`：同理，只是对象从 book 换成 read list。

第六步再看生产入口 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/kobo/KoboController.kt` 的 `syncLibrary` 方法。

这个方法能解释为什么同步点要设计成“快照 + 差异 + 已同步标记”：Kobo 设备每次请求同步接口时，服务端可能只返回一部分结果。如果结果太多，下一次请求要继续返回剩余的未同步项，所以每个 `take*` 方法必须能记住哪些已经发给设备。

## 常见误区

第一个误区：把 `SyncPoint` 当成实时查询结果。

`SyncPoint` 是快照。创建之后，它记录的是当时满足条件的书籍和阅读列表。后续书籍变化不会自动改变旧同步点，而是通过创建新同步点后比较差异体现。

第二个误区：认为 `takeBooksAdded` 只是查询。

`takeBooksAdded`、`takeBooksChanged`、`takeBooksRemoved`、`takeReadListsAdded` 等都不是纯查询。它们会查询 `onlyNotSynced = true` 的数据，并在返回后调用标记方法，把本次返回内容标记为已同步。测试中连续调用 page1、page2，就是在验证这个副作用。

第三个误区：忽略 `Pageable.ofSize(1)` 的意义。

测试里使用 size 1 不是为了测试普通分页排序，而是为了模拟 Kobo 分批同步。第一次取一个并标记，第二次应取另一个未标记项，不能重复返回同一项。

第四个误区：以为删除项来自新同步点。

删除书籍的差异来自旧同步点：旧同步点里有，新同步点里没有。因为书可能已经被硬删除，新同步点里不可能再保存它的当前记录。所以删除项的已同步状态也需要类似 `SYNC_POINT_BOOK_REMOVED_SYNCED` 这样的额外记录表来追踪。

第五个误区：把书籍内容变更和阅读进度变更混在一起。

`findBooksChanged` 关注文件、元数据、封面等内容变化。阅读进度变化由 `findBooksReadProgressChanged` 单独处理。Kobo 同步接口中也会把它们映射成不同 DTO，例如 `ChangedProductMetadataDto` 和 `ChangedReadingStateDto`。

第六个误区：认为用户有 library 权限就一定会同步。

创建同步点时同时受多层条件影响：用户共享 library、内容限制、调用方传入的 `libraryIds`、媒体状态、媒体 profile、删除状态。测试里的 `bookOtherLibrary` 就说明：即使用户有 `library2` 权限，如果本次 `createSyncPoint` 只传 `library1.id`，`library2` 的书也不会进入同步点。

第七个误区：忽略 series metadata 对权限的影响。

年龄限制和分享标签不是在 book 上直接设置，而是通过 series metadata 修改：

```kotlin
seriesMetadataRepository.update(it.copy(ageRating = 20))
seriesMetadataRepository.update(it.copy(sharingLabels = setOf("exclude")))
```

同步点创建时的搜索条件会结合用户的 `ContentRestrictions`，把这些内容排除。

第八个误区：把 `On Deck` 当成普通用户创建的阅读列表。

测试里的 `On Deck` 是 Komga 为 Kobo 同步生成的特殊 read list/tag，id 固定为 `KOMGA-ONDECK`。它会根据用户阅读进度动态生成：读完第一本后推荐第二本，读完第二本后推荐第三本，整套读完后移除。

第九个误区：只看测试文件，不看 `SyncPointDao`。

这个测试的大部分断言最终依赖 DAO 的差异 SQL。比如 hash 变化、metadata 修改、read list lastModified 变化是否被识别，都不是测试文件自己判断的，而是 `SyncPointRepository` 实现决定的。理解差异规则时，必须把 `SyncPointLifecycleTest.kt`、`SyncPointLifecycle.kt`、`SyncPointDao.kt` 连起来看。
