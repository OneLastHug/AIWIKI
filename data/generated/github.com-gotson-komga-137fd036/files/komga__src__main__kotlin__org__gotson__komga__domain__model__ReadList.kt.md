# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/ReadList.kt

## 它负责什么

`ReadList.kt` 定义的是 Komga 领域层里的“阅读列表”模型：`org.gotson.komga.domain.model.ReadList`。

它本身不负责查询数据库、不处理 HTTP 请求，也不执行添加、删除、校验等业务流程；它只是用一个 Kotlin `data class` 描述一份 read list 应该携带哪些领域数据：

- 阅读列表名称：`name`
- 简介：`summary`
- 是否手动排序：`ordered`
- 列表中的书籍及其顺序：`bookIds`
- 唯一标识：`id`
- 创建时间和修改时间：`createdDate`、`lastModifiedDate`
- 当前 `bookIds` 是否只是过滤后的部分结果：`filtered`

可以把它理解成领域层的“数据载体”和“业务事实定义”。其他层围绕这个模型做创建、更新、持久化、API 返回、权限过滤和阅读进度计算。

## 关键组成

### 包与导入

文件位于：

`komga/src/main/kotlin/org/gotson/komga/domain/model/ReadList.kt`

包名是：

`org.gotson.komga.domain.model`

它导入了三个外部/标准类型：

- `com.github.f4b6a3.tsid.TsidCreator`
- `java.time.LocalDateTime`
- `java.util.SortedMap`

其中 `TsidCreator` 用来生成默认 `id`，`LocalDateTime` 用来记录审计时间，`SortedMap` 用来保存有序的书籍 ID 映射。

### `ReadList`

核心定义如下：

```kotlin
data class ReadList(
  val name: String,
  val summary: String = "",
  val ordered: Boolean = true,
  val bookIds: SortedMap<Int, String> = sortedMapOf(),
  val id: String = TsidCreator.getTsid256().toString(),
  override val createdDate: LocalDateTime = LocalDateTime.now(),
  override val lastModifiedDate: LocalDateTime = createdDate,
  val filtered: Boolean = false,
) : Auditable
```

字段含义如下。

`name: String`

阅读列表名称。创建和更新时，业务服务会检查名称是否重复。调用方示例在 `komga/src/main/kotlin/org/gotson/komga/domain/service/ReadListLifecycle.kt` 中，`addReadList` 会通过 `readListRepository.existsByName(readList.name)` 判断重名。

`summary: String = ""`

阅读列表简介，默认是空字符串。API 创建阅读列表时会从 `ReadListCreationDto.summary` 传入；如果没有特别说明，模型层不做额外处理。

`ordered: Boolean = true`

表示这个阅读列表是否是手动排序的。源码注释写的是：

```kotlin
/**
 * Indicates whether the read list is ordered manually
 */
```

默认值是 `true`，说明新建的阅读列表默认按手动顺序维护。这个字段只表达状态，不在模型里执行排序逻辑。

`bookIds: SortedMap<Int, String> = sortedMapOf()`

这是 `ReadList` 最关键的字段之一。

它不是简单的 `List<String>`，而是 `SortedMap<Int, String>`：

- key：`Int`，表示书籍在阅读列表中的位置、编号或排序键
- value：`String`，表示 `Book` 的 `id`

例如根据当前片段推断，一个列表可能像这样表达：

```kotlin
sortedMapOf(
  0 to "book-id-a",
  1 to "book-id-b",
  2 to "book-id-c",
)
```

使用 `SortedMap` 的意义是：即使添加顺序不同，也可以按 key 的自然顺序稳定遍历。`ReadListLifecycle.addBookToReadList` 中也会基于 `existing.bookIds.lastKey() + 1` 给新书分配下一个位置。

`id: String = TsidCreator.getTsid256().toString()`

阅读列表 ID，默认使用 `TsidCreator.getTsid256()` 生成。

TSID 通常用于生成带时间特征、适合排序的唯一 ID。这里模型层只负责生成默认值，不负责说明数据库主键策略。根据当前片段可以确认：如果调用方没有传入 `id`，创建 `ReadList` 时会自动生成一个字符串 ID；从数据库恢复时，DAO 会显式传入已有 `id`。

`createdDate: LocalDateTime = LocalDateTime.now()`

创建时间，来自 `Auditable` 接口。

`lastModifiedDate: LocalDateTime = createdDate`

最后修改时间，也来自 `Auditable` 接口。默认等于 `createdDate`，也就是说新建对象时，如果没有显式传入修改时间，创建时间和修改时间一致。

`filtered: Boolean = false`

源码注释是：

```kotlin
/**
 * Indicates that the bookIds have been filtered and is not exhaustive.
 */
```

含义是：当前 `bookIds` 可能不是完整列表，而是经过权限、库范围或其他条件过滤后的子集。

这个字段很容易被忽略。它不是说整个 `ReadList` 无效，而是提醒调用方：这个对象里的 `bookIds` 可能“不完整”。例如 API 层有按用户授权 library ids 查询 read list 的调用，`ReadListController` 中会使用类似 `readListRepository.findByIdOrNull(id, principal.user.getAuthorizedLibraryIds(null))` 的方式读取数据；根据当前片段推断，这类查询可能导致 `bookIds` 被过滤，`filtered` 用来标记这个状态。

### `Auditable`

`ReadList` 实现了同目录的 `Auditable` 接口：

`komga/src/main/kotlin/org/gotson/komga/domain/model/Auditable.kt`

接口很小：

```kotlin
interface Auditable {
  val createdDate: LocalDateTime
  val lastModifiedDate: LocalDateTime
}
```

所以 `ReadList` 必须提供 `createdDate` 和 `lastModifiedDate`。这让阅读列表和其他可审计领域对象保持一致，例如数据库映射、同步、API 输出时都可以统一处理创建/修改时间。

## 上下游关系

### 上游：API DTO 和业务入口

`ReadList` 的一个主要上游是 REST API。

在 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/ReadListController.kt` 中，创建阅读列表时，控制器会把 API 请求 DTO 转成领域模型：

```kotlin
ReadList(
  name = readList.name,
  summary = readList.summary,
  ordered = readList.ordered,
  bookIds = readList.bookIds.toIndexedMap(),
)
```

这里可以看出：

- API 输入不是直接暴露 `ReadList`
- 控制器负责把 `ReadListCreationDto` 转成领域模型
- `bookIds` 会通过 `toIndexedMap()` 转成带索引的 map
- `id`、`createdDate`、`lastModifiedDate` 没有从请求传入，而是使用 `ReadList` 的默认值

更新时，控制器会先查出现有 `ReadList`，再用 `copy` 生成更新后的对象：

```kotlin
existing.copy(
  name = readList.name ?: existing.name,
  summary = readList.summary ?: existing.summary,
  ordered = readList.ordered ?: existing.ordered,
  bookIds = readList.bookIds?.toIndexedMap() ?: existing.bookIds,
)
```

这体现了 Kotlin `data class` 的典型用法：模型不可变，更新时创建一个新对象，而不是原地修改字段。

### 中游：领域服务 `ReadListLifecycle`

核心业务流程在：

`komga/src/main/kotlin/org/gotson/komga/domain/service/ReadListLifecycle.kt`

它围绕 `ReadList` 做生命周期管理：

- `addReadList(readList: ReadList): ReadList`
- `updateReadList(toUpdate: ReadList)`
- `deleteReadList(readList: ReadList)`
- `addBookToReadList(readListName: String, book: Book, numberInList: Int?)`

`ReadList` 在这里不再只是“请求数据”，而是业务服务处理的领域对象。

创建时：

- 记录日志
- 检查名称重复
- 调用 `readListRepository.insert(readList)`
- 发布 `DomainEvent.ReadListAdded(readList)`
- 再从仓库查询一次并返回

更新时：

- 先确认目标存在
- 如果名称发生变化，检查新名称是否重复
- 调用 `readListRepository.update(toUpdate)`
- 发布 `DomainEvent.ReadListUpdated(toUpdate)`

删除时：

- 删除关联缩略图
- 删除 read list 本身
- 发布 `DomainEvent.ReadListDeleted(readList)`

自动添加书籍时：

- 如果同名 read list 已存在，就复制现有 `bookIds`，加入新的 book id，再调用 `updateReadList`
- 如果不存在，就创建新的 `ReadList`
- 新列表的 `bookIds` 会用 `mapOf((numberInList ?: 0) to book.id).toSortedMap()`

这说明 `ReadList` 的 `bookIds` 是业务服务维护阅读列表顺序的核心结构。

### 下游：Repository / DAO / 数据库映射

持久化层相关文件包括：

`komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/ReadListDao.kt`

在 DAO 中，数据库记录会被转回领域模型。当前片段显示 `ReadlistRecord.toDomain(bookIds: SortedMap<Int, String>)` 会构造 `ReadList`：

```kotlin
ReadList(
  name = name,
  summary = summary,
  ordered = ordered,
  bookIds = bookIds,
  id = id,
  createdDate = createdDate.toCurrentTimeZone(),
  ...
)
```

这里说明：

- 数据库中的 `readlist` 记录是 `ReadList` 的持久化来源
- DAO 会把数据库时间转换成当前时区
- 从数据库恢复对象时，不使用 `ReadList` 的默认 `id` 和默认时间，而是使用数据库已有值
- `bookIds` 是 DAO 额外组装出来的 `SortedMap<Int, String>`

根据当前片段推断，read list 本体信息和 read list 中的书籍关系可能不是完全存在同一张表里；DAO 需要额外拿到 `bookIds` 后再组装领域对象。依据是 `toDomain(bookIds: SortedMap<Int, String>)` 的参数由外部传入，而不是直接从单个 `ReadlistRecord` 字段读取。

### 其他下游：阅读、导航、进度、缩略图

`ReadList` 还被其他功能消费：

- `ReadListController` 用它查找 read list 内上一本文档和下一本文档
- `BookDtoDao` 有 `findSiblingReadList` 相关逻辑，用于 read list 内的前后导航
- `ReadProgressDtoRepository` / `ReadProgressDtoDao` 有 `findProgressByReadList`，用于按 read list 统计阅读进度
- `ThumbnailReadList` 用于阅读列表缩略图
- OPDS v1/v2 控制器也有获取 read list 的接口
- `ReferentialController` / `ReferentialDao` 会按 read list 查询作者、标签等引用信息
- `SyncPoint.ReadList` 用于同步点相关逻辑

所以 `ReadList` 虽然只是一个小模型，但它连接了书籍排序、API 展示、阅读进度、同步、缩略图和权限过滤等多个功能面。

## 运行/调用流程

### 创建阅读列表

典型流程是：

1. 客户端调用 REST API 创建 read list。
2. `ReadListController.createReadList` 接收 `ReadListCreationDto`。
3. 控制器构造领域对象 `ReadList(...)`。
4. `id` 默认由 `TsidCreator.getTsid256().toString()` 生成。
5. `createdDate` 默认使用 `LocalDateTime.now()`。
6. `lastModifiedDate` 默认等于 `createdDate`。
7. `bookIds` 从请求中的书籍 ID 列表转换成 `SortedMap<Int, String>`。
8. 控制器调用 `readListLifecycle.addReadList(...)`。
9. `ReadListLifecycle` 检查名称是否重复。
10. Repository / DAO 将 `ReadList` 写入数据库。
11. 服务发布 `DomainEvent.ReadListAdded(readList)`。
12. 服务重新查询并返回保存后的 `ReadList`。
13. 控制器把领域模型转成 DTO 返回给 API 客户端。

### 更新阅读列表

典型流程是：

1. 客户端调用 PATCH 接口。
2. `ReadListController.updateReadListById` 先通过 `readListRepository.findByIdOrNull(id)` 找到现有对象。
3. 控制器使用 `existing.copy(...)` 合并请求字段。
4. 未传入的字段保留原值。
5. 如果请求传入 `bookIds`，会重新转换成 indexed map。
6. 控制器调用 `readListLifecycle.updateReadList(updated)`。
7. 生命周期服务确认对象存在。
8. 如果名称变化，检查是否和其他 read list 重名。
9. Repository / DAO 更新数据库。
10. 发布 `DomainEvent.ReadListUpdated(toUpdate)`。

这里要注意，`ReadList.kt` 自己没有更新方法。更新依赖 `data class` 的 `copy` 和服务层的业务规则。

### 删除阅读列表

典型流程是：

1. 控制器按 ID 查询 `ReadList`。
2. 找不到则返回 `NOT_FOUND`。
3. 找到后调用 `readListLifecycle.deleteReadList(it)`。
4. 服务层在事务中删除关联的 read list thumbnail。
5. 服务层删除 read list。
6. 发布 `DomainEvent.ReadListDeleted(readList)`。

删除流程说明 `ReadList` 也参与缩略图等关联资源的生命周期管理，但真正删除逻辑不在模型类中。

### 向阅读列表添加书籍

`ReadListLifecycle.addBookToReadList` 是理解 `bookIds` 的好入口。

流程大致是：

1. 按名称查找 read list。
2. 如果列表存在，复制现有 `bookIds` 到可变 map。
3. 如果目标 book 已经存在于 `bookIds.values`，则不会重复添加。
4. 如果指定了 `numberInList`，优先使用该位置。
5. 如果没有指定，则使用 `existing.bookIds.lastKey() + 1` 作为新位置。
6. 把 `book.id` 放进 map。
7. 用 `existing.copy(bookIds = map)` 得到新 `ReadList`。
8. 调用 `updateReadList` 保存。
9. 如果列表不存在，则用给定名称创建新的 `ReadList`，并初始化 `bookIds`。

这里能看出 `SortedMap<Int, String>` 的设计意图：位置编号和书籍 ID 分离，列表顺序由 key 决定。

## 小白阅读顺序

建议按下面顺序阅读：

1. 先读 `komga/src/main/kotlin/org/gotson/komga/domain/model/Auditable.kt`

   这个文件只有一个接口，能帮助你理解为什么 `ReadList` 要实现 `createdDate` 和 `lastModifiedDate`。

2. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/model/ReadList.kt`

   重点看每个字段的默认值。这个文件没有函数，所以不要试图在这里找业务流程。

3. 接着读 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/ReadListController.kt`

   重点看 `createReadList`、`updateReadListById`、`deleteReadListById`。这里可以看到外部 API 请求如何进入领域模型。

4. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/service/ReadListLifecycle.kt`

   重点看 `addReadList`、`updateReadList`、`deleteReadList`、`addBookToReadList`。这里是真正的业务规则，例如重名检查、事件发布、添加书籍时如何计算位置。

5. 最后读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/ReadListDao.kt`

   重点看 `toDomain` 之类的映射函数，理解数据库记录如何变回 `ReadList`。

如果只想快速理解这个文件，可以先抓住一句话：

`ReadList` 是一个不可变领域模型，它用 `SortedMap<Int, String>` 表达“阅读列表中的书籍顺序”，用 `Auditable` 字段表达创建和修改时间，用 `filtered` 标记当前书籍列表是否完整。

## 常见误区

### 误区一：以为 `ReadList` 会自己维护列表顺序

不会。

`ReadList` 只是保存 `bookIds: SortedMap<Int, String>`。真正决定何时插入、插入到哪个位置、如何避免重复书籍的是 `ReadListLifecycle.addBookToReadList` 和上层 API / Repository 逻辑。

### 误区二：以为 `bookIds` 是普通书籍 ID 列表

不是。

它是 `SortedMap<Int, String>`，key 是排序位置，value 才是 book id。阅读时要关注 key 的含义，不能只看 values。

这也解释了为什么创建接口里会有 `toIndexedMap()`：请求里可能只是一个书籍 ID 列表，但领域模型需要带顺序索引的 map。

### 误区三：以为 `ordered = true` 会自动排序

`ordered` 只是一个标志，表示 read list 是否手动排序。它不会自动改变 `bookIds`。排序行为仍然依赖服务层、DAO 查询或调用方如何解释这个字段。

### 误区四：以为 `filtered = true` 表示 read list 被破坏了

不是。

`filtered` 表示 `bookIds` 不是完整集合，可能因为权限或过滤条件只返回了一部分书籍。这个字段提醒调用方不要把当前 `bookIds` 当成完整列表。

### 误区五：以为 `id` 总是调用数据库后才生成

从这个模型看，新建 `ReadList` 时如果没有传入 `id`，会直接在对象构造阶段通过 `TsidCreator.getTsid256().toString()` 生成。数据库恢复对象时，DAO 会传入已有 `id`，不会使用默认生成逻辑。

### 误区六：以为修改 `ReadList` 是直接改字段

`ReadList` 的字段都是 `val`，对象本身是不可变数据结构。更新时通常使用 `copy(...)` 创建新对象，例如控制器更新名称、简介、排序状态和 `bookIds` 时就是这样做的。

### 误区七：以为这个文件包含完整 read list 功能

这个文件只定义模型。完整功能分散在多个层次：

- API 入口：`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/ReadListController.kt`
- 生命周期业务：`komga/src/main/kotlin/org/gotson/komga/domain/service/ReadListLifecycle.kt`
- 持久化映射：`komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/ReadListDao.kt`
- 请求导入模型：`komga/src/main/kotlin/org/gotson/komga/domain/model/ReadListRequest.kt`
- 缩略图模型：`komga/src/main/kotlin/org/gotson/komga/domain/model/ThumbnailReadList.kt`

阅读 `ReadList.kt` 时，应把它当作中心数据结构，而不是完整业务模块。
