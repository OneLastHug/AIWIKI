# 文件：komga/src/main/kotlin/org/gotson/komga/domain/service/PageHashLifecycle.kt

## 它负责什么

`PageHashLifecycle` 是 Komga 里“页哈希”这条链路的服务层入口，主要管三件事：查缺失页哈希、按哈希取回具体页面、维护已知哈希记录。

它本身不直接做文件扫描或图像计算，而是把“页面哈希”相关的查询、回填、自动删除候选整理成可被任务系统和 REST API 调用的服务方法。根据当前片段推断，它是页哈希功能的协调层，真正的数据读写落在 `PageHashRepository`、`MediaRepository`、`BookRepository` 和 `BookLifecycle` 上。

## 关键组成

这个类是一个 Spring `@Service`，构造注入了 5 个依赖：

- `PageHashRepository`：读写页哈希索引数据，包含已知哈希、未知哈希、匹配页、缩略图等。
- `MediaRepository`：按库查找需要补页哈希的书。
- `BookLifecycle`：根据书和页码取出页面内容。
- `BookRepository`：把哈希匹配结果映射回具体 `Book`。
- `KomgaProperties`：提供 `pageHashing` 相关配置，决定扫描时的筛选粒度。

类里还有一个本地常量 `hashableMediaTypes = listOf(MediaType.ZIP.type)`，说明这里默认只把 ZIP 类媒体纳入“页哈希缺失”扫描范围。

核心方法有 4 个：

- `getBookIdsWithMissingPageHash(library)`
- `getPage(pageHash, resizeTo)`
- `getBookPagesToDeleteAutomatically(library)`
- `createOrUpdate(pageHash)`

## 上下游关系

上游调用者主要有两类：

- `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskHandler.kt`
  - `Task.FindBooksWithMissingPageHash` 会调用 `getBookIdsWithMissingPageHash`
  - `Task.FindDuplicatePagesToDelete` 会调用 `getBookPagesToDeleteAutomatically`
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/PageHashController.kt`
  - `GET /api/v1/page-hashes/unknown/{pageHash}/thumbnail` 会调用 `getPage`
  - `PUT /api/v1/page-hashes` 会调用 `createOrUpdate`

下游依赖主要是仓储和书页读取逻辑：

- `PageHashRepository.findMatchesByHash(...)`：把页哈希映射到书、页码、文件信息。
- `PageHashRepository.findMatchesByKnownHashAction(...)`：按已知哈希动作筛出可自动删除的页。
- `PageHashRepository.findKnown(...) / insert(...) / update(...)`：维护已知哈希记录。
- `MediaRepository.findAllBookIdsByLibraryIdAndMediaTypeAndWithMissingPageHash(...)`：找缺页哈希的书。
- `BookLifecycle.getBookPage(...)`：按书对象和页码返回页面字节数据。
- `BookRepository.findByIdOrNull(...)`：把匹配结果转回具体书对象。

DAO 层的实现落在 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/PageHashDao.kt` 和 `MediaDao.kt`。根据当前片段推断，`PageHashLifecycle` 只负责业务编排，不直接碰 SQL。

## 运行/调用流程

1. 扫描缺失页哈希  
   `TaskHandler` 在扫描库或专门任务中，会先确认 `library.hashPages` 是否开启。开启后，`PageHashLifecycle.getBookIdsWithMissingPageHash(library)` 通过 `MediaRepository` 找出同库里还没补页哈希的书，并受 `komgaProperties.pageHashing` 约束。

2. 读取未知页的缩略图  
   `PageHashController` 在请求 `unknown/{pageHash}/thumbnail` 时调用 `getPage(pageHash, resize)`。  
   这里先用 `PageHashRepository.findMatchesByHash(pageHash, Pageable.ofSize(1))` 找到第一条匹配，再用 `BookRepository.findByIdOrNull(match.bookId)` 找书，最后交给 `BookLifecycle.getBookPage(book, match.pageNumber, resizeTo)` 取出页面。

3. 维护已知哈希  
   `createOrUpdate(pageHash)` 先查 `PageHashRepository.findKnown(pageHash.hash)`。  
   - 如果不存在，就调用 `insert(pageHash, getPage(pageHash.hash, 500)?.bytes)`，顺带尝试生成 500 宽度的缩略图。
   - 如果已存在，就 `update(existing.copy(action = pageHash.action))`，只更新动作等元数据。

4. 自动删除候选整理  
   `getBookPagesToDeleteAutomatically(library)` 会调用 `PageHashRepository.findMatchesByKnownHashAction(listOf(PageHashKnown.Action.DELETE_AUTO), library.id)`，返回一个按 `bookId` 聚合的 `Map<String, Collection<BookPageNumbered>>`，供任务系统后续批量移除重复页。

## 小白阅读顺序

1. 先看 `PageHashLifecycle.kt`，把 4 个公开方法的输入输出记住。
2. 再看 `komga/src/main/kotlin/org/gotson/komga/domain/model/PageHashKnown.kt`，理解 `DELETE_AUTO`、`DELETE_MANUAL`、`IGNORE` 这几个动作。
3. 接着看 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/PageHashController.kt`，把 API 怎么进到这个服务串起来。
4. 再看 `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskHandler.kt`，理解后台任务如何触发缺失页哈希扫描和自动删除整理。
5. 最后看 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/PageHashDao.kt` 和 `MediaDao.kt`，确认数据是怎么查、怎么写的。

## 常见误区

- 容易把它当成“计算页哈希”的地方，但这里其实不负责哈希算法，更多是查询和生命周期管理。
- `getPage` 不是直接按哈希算图，而是“先找到匹配页，再回书里取页图”，所以书记录缺失时会返回 `null`。
- `createOrUpdate` 不一定能拿到缩略图；如果 `getPage(..., 500)` 找不到页面，仍然会插入哈希记录，只是 thumbnail 为空。
- `getBookIdsWithMissingPageHash` 只有在 `library.hashPages` 开启时才会工作，否则直接返回空集合。
- 这个类里默认只处理 `MediaType.ZIP.type`，所以它不是对所有媒体格式都做页哈希扫描。根据当前片段推断，其他格式要么不支持，要么在别处有单独流程。
