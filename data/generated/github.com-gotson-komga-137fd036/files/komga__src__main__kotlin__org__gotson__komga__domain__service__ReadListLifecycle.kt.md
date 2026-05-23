# 文件：komga/src/main/kotlin/org/gotson/komga/domain/service/ReadListLifecycle.kt

## 它负责什么

这个文件定义了 `ReadListLifecycle`，它是 Komga 里“读书清单（ReadList）”的领域生命周期服务。它不负责展示层，也不直接暴露 HTTP 接口，而是把读书清单的增删改、封面缩略图、ComicRack 清单匹配、以及“从书籍元数据反向维护读书清单”这些操作集中在一起。

从职责上看，它更像读书清单的业务中枢：

- 维护 `ReadList` 的创建、更新、删除
- 处理读书清单里书籍的增量加入
- 维护读书清单缩略图 `ThumbnailReadList`
- 根据书籍缩略图生成读书清单的拼图封面
- 解析 ComicRack 的 `.cbl` 文件并做匹配校验
- 在关键变更后发布 `DomainEvent`

## 关键组成

这个类是一个 `@Service`，构造函数注入了多种依赖，说明它既是业务编排层，也是持久化和事件发布的协调者。

核心依赖可以分成几组：

- 持久化层
  - `ReadListRepository`
  - `ThumbnailReadListRepository`
- 其他领域服务
  - `BookLifecycle`：用于读取书籍缩略图
  - `ReadListMatcher`：用于把导入的 ComicRack 读书清单请求映射成匹配结果
- 基础设施组件
  - `MosaicGenerator`：用于把多本书的缩略图拼成一张读书清单封面
  - `ReadListProvider`：用于解析 ComicRack `.cbl` 文件
- 事务和事件
  - `TransactionTemplate`
  - `ApplicationEventPublisher`

主要方法可以按功能理解：

- CRUD：
  - `addReadList`
  - `updateReadList`
  - `deleteReadList`
- 自动维护成员书籍：
  - `addBookToReadList`
  - `deleteEmptyReadLists`
- 缩略图管理：
  - `addThumbnail`
  - `markSelectedThumbnail`
  - `deleteThumbnail`
  - `getThumbnailBytes(...)`
- ComicRack 支持：
  - `matchComicRackList`

## 上下游关系

上游调用方很明确，主要来自两个地方：

- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/ReadListController.kt`
  - 创建读书清单
  - 更新读书清单
  - 删除读书清单
  - 匹配 ComicRack 清单
  - 获取或维护读书清单缩略图
- `komga/src/main/kotlin/org/gotson/komga/domain/service/BookMetadataLifecycle.kt`
  - 在刷新书籍元数据时，如果 provider 给出了 read list 信息，就调用 `addBookToReadList(...)`

下游依赖则是这些组件：

- `ReadListRepository`、`ThumbnailReadListRepository`
  - 负责真实的数据读写
- `BookLifecycle`
  - `getThumbnailBytes(readList)` 在没有选中封面时，会取书籍缩略图来拼图
- `MosaicGenerator`
  - 负责把最多 4 张图片生成封面
- `ReadListProvider` + `ReadListMatcher`
  - 负责导入 ComicRack 文件并进行匹配
- `DomainEvent`
  - 负责把状态变化广播出去，让别的模块继续响应

根据当前片段推断，这个类是“读书清单领域”的核心编排点：Controller 负责接收请求，`ReadListLifecycle` 负责把业务规则、仓储操作和事件通知串起来。

## 运行/调用流程

典型流程可以按几条主线理解：

1. 创建、更新、删除读书清单
   - Controller 收到请求后构造 `ReadList`
   - 调用 `addReadList` / `updateReadList` / `deleteReadList`
   - 方法内部先做存在性和重名检查
   - 成功后写库，再发出对应的 `DomainEvent.ReadListAdded`、`ReadListUpdated`、`ReadListDeleted`

2. 给读书清单自动加书
   - `BookMetadataLifecycle.refreshMetadata(...)` 处理书籍元数据时，可能拿到 `patch.readLists`
   - 对每个读书清单请求调用 `addBookToReadList(readList.name, book, readList.number)`
   - 如果同名读书清单已存在，就在现有清单里插入或追加书籍
   - 如果不存在，就自动创建一个新的读书清单

3. 缩略图处理
   - `addThumbnail`：插入用户上传的缩略图，若标记为选中则一并更新选中状态
   - `markSelectedThumbnail`：把某张缩略图设为选中
   - `deleteThumbnail`：删除缩略图后执行 housekeeping，确保同一个读书清单不会出现多个选中项，或者在没有选中项时自动补一个
   - `getThumbnailBytes(readList)`：优先返回已选缩略图；如果没有，就取读书清单里前 4 本书的封面生成 mosaic

4. ComicRack 导入匹配
   - `matchComicRackList(file.bytes)` 先交给 `ReadListProvider.importFromCbl(...)`
   - 解析出 `ReadListRequest`
   - 再交给 `ReadListMatcher.matchReadListRequest(...)`
   - 最终返回 `ReadListRequestMatch`
   - 这条链路只做“解析 + 匹配 + 验证”，不直接落库

事务边界也比较重要：

- `addReadList`、`updateReadList`、`addBookToReadList`、`deleteEmptyReadLists` 都有事务语义
- `deleteReadList` 和 `deleteEmptyReadLists` 用 `TransactionTemplate.executeWithoutResult` 先删缩略图、再删读书清单
- 事件发布大多发生在事务操作之后，这样外部监听者拿到的是更接近最终状态的事件

## 小白阅读顺序

建议按下面顺序读，理解会比较顺：

1. 先看类头部和构造函数，认清它依赖了哪些组件。
2. 读 `addReadList`、`updateReadList`、`deleteReadList`，先建立“基础 CRUD + 事件”的直觉。
3. 再读 `addBookToReadList`，理解它如何自动创建读书清单、如何处理位置冲突。
4. 接着看 `getThumbnailBytes(readList)`、`addThumbnail`、`markSelectedThumbnail`、`deleteThumbnail`，理解封面管理。
5. 最后读 `matchComicRackList`，顺着链路去看 `ReadListProvider` 和 `ReadListMatcher`。

如果要补上下游链路，再去看：

- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/ReadListController.kt`
- `komga/src/main/kotlin/org/gotson/komga/domain/service/BookMetadataLifecycle.kt`
- `komga/src/main/kotlin/org/gotson/komga/domain/service/ReadListMatcher.kt`
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/metadata/comicrack/ReadListProvider.kt`

## 常见误区

- 这个类不是纯仓储封装。它除了读写数据库，还负责事件发布、缩略图生成、清单解析和业务规则判断。
- `addBookToReadList` 不只是“往后追加”。它会先检查是否已有同名清单，也会处理 `numberInList` 的位置冲突；冲突时会把新书放到末尾。
- `deleteReadList` 不是直接删主表记录。它会先删关联缩略图，再删读书清单，而且是通过事务模板完成。
- `markSelectedThumbnail` 虽然是在“选中缩略图”，但发布的事件类型还是 `ThumbnailReadListAdded`，这点很容易看错。
- `getThumbnailBytes(readList)` 并不总是拼图。只要有已选缩略图，就直接返回那张图。
- 根据当前片段推断，`getThumbnailBytes(readList)` 默认读书清单里至少有一些书可供拼图；如果读书清单为空，后面的补齐逻辑可能会出问题，所以它依赖上层避免这种状态。
- `matchComicRackList` 只是“解析并匹配”，不是导入落库；真正的持久化动作不在这个方法里。
