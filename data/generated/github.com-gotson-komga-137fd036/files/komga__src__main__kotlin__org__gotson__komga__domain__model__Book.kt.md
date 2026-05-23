# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/Book.kt

## 它负责什么

`Book.kt` 定义了 Komga 领域层里的核心实体 `Book`，表示一个被书库管理的“书籍文件”。这里的“书”不是元数据意义上的标题、作者、简介，而是一个实际文件在系统中的领域对象：它有文件名、文件 URL、修改时间、大小、哈希、所属书库、所属系列、删除状态、是否 one-shot 等信息。

这个文件的职责非常集中：

- 保存一本书对应的文件级信息，例如 `url`、`fileLastModified`、`fileSize`、`fileHash`。
- 保存领域关系信息，例如 `seriesId`、`libraryId`。
- 提供统一的主键 `id`，默认用 `TsidCreator.getTsid256().toString()` 生成。
- 实现 `Auditable`，让 `Book` 具备 `createdDate` 和 `lastModifiedDate`。
- 从 `url` 懒加载转换出本地 `Path`，供文件系统操作使用。

它本身不做扫描、入库、解析、生成缩略图、计算哈希等业务动作，只是这些流程共享的领域数据载体。

## 关键组成

### 包与 import

文件位于包：

`org.gotson.komga.domain.model`

引入的依赖包括：

- `com.github.f4b6a3.tsid.TsidCreator`：用于生成默认 `id`。
- `java.net.URL`：书籍文件位置用 `URL` 表示。
- `java.nio.file.Path`：运行时需要访问本地文件路径。
- `java.time.LocalDateTime`：记录文件时间、删除时间、审计时间。
- `kotlin.io.path.toPath`：把 `URI` 转成 Kotlin/JDK `Path`。

这里没有传统意义上的 export。Kotlin 中顶层 `data class Book` 默认对同模块可见，其他包通过 import `org.gotson.komga.domain.model.Book` 使用。

### `data class Book`

核心定义是：

```kotlin
data class Book(
  val name: String,
  val url: URL,
  val fileLastModified: LocalDateTime,
  val fileSize: Long = 0,
  val fileHash: String = "",
  val fileHashKoreader: String = "",
  val number: Int = 0,
  val id: String = TsidCreator.getTsid256().toString(),
  val seriesId: String = "",
  val libraryId: String = "",
  val deletedDate: LocalDateTime? = null,
  val oneshot: Boolean = false,
  override val createdDate: LocalDateTime = LocalDateTime.now(),
  override val lastModifiedDate: LocalDateTime = createdDate,
) : Auditable
```

字段可以按用途分成几组。

文件身份字段：

- `name`：书籍名称，通常来自文件名去掉扩展名。`FileSystemScanner.pathToBook()` 中使用 `path.nameWithoutExtension` 赋值。
- `url`：文件 URL，通常是本地文件的 `file:` URL。数据库层会把它保存成字符串，再读回来转成 `URL`。
- `path`：不是构造参数，而是由 `url` 懒加载得到的本地 `Path`。

文件状态字段：

- `fileLastModified`：文件更新时间。扫描时来自文件系统属性，具体取 `creationTime()` 和 `lastModifiedTime()` 中较大的一个。
- `fileSize`：文件大小。扫描时来自 `BasicFileAttributes.size()`。
- `fileHash`：普通文件哈希，初始为空，后续由 `BookLifecycle.hashAndPersist()` 计算并保存。
- `fileHashKoreader`：KOReader 兼容哈希，初始为空，后续由 `BookLifecycle.hashKoreaderAndPersist()` 计算并保存。

排序和归属字段：

- `number`：书籍在系列里的排序编号之一。注意它是 `Int`，而更细的元数据排序值在 `BookMetadata.numberSort` 中，是 `Float`。
- `seriesId`：所属系列 ID。
- `libraryId`：所属书库 ID。
- `oneshot`：是否为 one-shot 书籍。扫描 one-shot 目录时，一个文件可能被当作一个独立系列处理。

生命周期字段：

- `id`：领域对象主键，默认生成 TSID 字符串。
- `deletedDate`：软删除时间。为空表示未删除。
- `createdDate`：创建时间，来自 `Auditable`。
- `lastModifiedDate`：最后修改时间，来自 `Auditable`，默认等于 `createdDate`。

### `Auditable`

`Book` 实现同目录的 `Auditable`：

```kotlin
interface Auditable {
  val createdDate: LocalDateTime
  val lastModifiedDate: LocalDateTime
}
```

这说明 `Book` 的创建和修改时间是领域对象通用约定。数据库读取时，`BookDao.toDomain()` 会把数据库中的 `createdDate`、`lastModifiedDate` 转成当前时区后放回 `Book`。

### `path` 懒加载属性

`Book` 内部还有一个属性：

```kotlin
@delegate:Transient
val path: Path by lazy { this.url.toURI().toPath() }
```

这表示：

- `path` 不参与主构造函数。
- 它通过 `url.toURI().toPath()` 延迟计算。
- `by lazy` 让它只在第一次访问时转换。
- `@delegate:Transient` 标记 lazy 委托字段为 transient，避免序列化 lazy 委托本身。

这个设计说明领域对象内部保存的是更通用的 `URL`，而文件系统操作需要时再得到 `Path`。例如 `BookLifecycle.hashAndPersist()` 会调用 `hasher.computeHash(book.path)`，`BookImporter` 会用 `bookToUpgrade.path` 删除或替换旧文件。

## 上下游关系

### 上游：谁创建 `Book`

主要上游是文件扫描与导入流程。

`komga/src/main/kotlin/org/gotson/komga/domain/service/FileSystemScanner.kt` 中的 `pathToBook()` 会把文件系统路径转成 `Book`：

```kotlin
Book(
  name = path.nameWithoutExtension,
  url = path.toUri().toURL(),
  fileLastModified = attrs.getUpdatedTime(),
  fileSize = attrs.size(),
)
```

这时创建出来的 `Book` 只有文件基础信息，`id` 自动生成，`seriesId`、`libraryId` 仍是默认空字符串。后续在扫描根目录或导入书籍时再补齐归属关系。

`BookImporter.importBook()` 也会通过 `fileSystemScanner.scanFile(destFile)` 得到新导入的 `Book`，然后执行：

```kotlin
.copy(libraryId = series.libraryId, oneshot = series.oneshot)
```

之后交给 `seriesLifecycle.addBooks(series, listOf(importedBook))` 持久化和建立系列关系。

### 中游：谁持久化 `Book`

领域层通过接口 `komga/src/main/kotlin/org/gotson/komga/domain/persistence/BookRepository.kt` 操作 `Book`。这个接口定义了查询、插入、更新、删除、统计等方法，例如：

- `findByIdOrNull(bookId: String): Book?`
- `findAllBySeriesId(seriesId: String): Collection<Book>`
- `findNotDeletedByLibraryIdAndUrlOrNull(libraryId: String, url: URL): Book?`
- `insert(book: Book)`
- `update(book: Book)`
- `delete(bookId: String)`

基础设施层实现是 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/BookDao.kt`。它负责把 `Book` 映射到数据库表 `BOOK`：

- 插入时保存 `ID`、`NAME`、`URL`、`NUMBER`、`FILE_LAST_MODIFIED`、`FILE_SIZE`、`FILE_HASH`、`FILE_HASH_KOREADER`、`LIBRARY_ID`、`SERIES_ID`、`DELETED_DATE`、`ONESHOT`。
- 更新时会刷新 `LAST_MODIFIED_DATE`。
- 读取时通过 `BookRecord.toDomain()` 重新构造 `Book`。

这说明 `Book.kt` 是领域模型，数据库细节不在它里面，而在 `BookDao` 中完成映射。

### 下游：谁消费 `Book`

下游非常多，主要可以分成几类。

文件分析与媒体信息：

- `BookLifecycle.analyzeAndPersist(book)` 调用 `bookAnalyzer.analyze(book, ...)` 解析媒体信息。
- `BookWithMedia` 把 `Book` 和 `Media` 组合起来，供缩略图、元数据、页面哈希等逻辑使用。
- `BookAnalyzer`、元数据 provider 会读取 `Book.url` 或 `Book.path` 来打开实际文件。

哈希与文件操作：

- `BookLifecycle.hashAndPersist(book)` 使用 `book.path` 计算普通哈希，写回 `fileHash`。
- `BookLifecycle.hashKoreaderAndPersist(book)` 使用 `book.path` 计算 KOReader 哈希，写回 `fileHashKoreader`。
- `BookImporter` 使用 `bookToUpgrade.path` 处理升级旧书时的文件删除、替换和 sidecar 文件迁移。

任务系统：

- `TaskEmitter.analyzeBook(book, priority)` 会把 `book.id` 和 `book.seriesId` 包装成任务。
- `TaskHandler` 中的导入、分析、哈希任务会围绕 `Book` 的 ID 查询并继续处理。

接口层：

- REST、OPDS、Kobo 等控制器通常不会直接依赖 `Book.kt` 的所有细节，但会通过 repository 查询 `Book`，再结合 metadata、media、read progress 转成 API DTO。
- 搜索条件 `SearchCondition.Book` 会通过 `BookDao.findAll()` 查询 `Book` 分页结果。

相关模型：

- `BookMetadata`：保存标题、简介、作者、ISBN、标签等书籍元数据。它和 `Book` 通过 `bookId` 关联，但不混在 `Book` 里。
- `Media`：保存媒体解析结果，例如页数、格式、状态等。`BookWithMedia` 把两者组合。
- `TransientBook`：用于临时分析导入前的书，内部包含 `book: Book`、`media: Media` 和临时元数据。
- `Series`：`Book.seriesId` 指向所属系列，扫描目录时通常先得到 series，再挂载 books。

## 运行/调用流程

一个典型的扫描入库流程可以这样理解：

1. `FileSystemScanner.scanRootFolder()` 遍历书库根目录。
2. 遇到扩展名符合条件的文件，例如 `cbz`、`zip`、`cbr`、`rar`、`pdf`、`epub`。
3. 调用 `pathToBook(file, attrs)` 创建 `Book`。
4. 此时 `Book.name` 来自文件名，`Book.url` 来自文件路径，`Book.fileLastModified` 和 `Book.fileSize` 来自文件属性。
5. 扫描器按目录把 `Book` 归入对应 `Series`。
6. 后续生命周期服务把 `libraryId`、`seriesId` 等关系补齐并通过 `BookRepository.insert()` 保存。
7. `BookDao.insert()` 把领域对象字段写入数据库。
8. 后续任务再根据 `Book.id` 查询出对象，执行分析、哈希、缩略图生成、元数据刷新等动作。

一个典型的导入流程是：

1. `BookImporter.importBook(sourceFile, series, copyMode, ...)` 收到外部文件。
2. 根据 `copyMode` 把文件复制、移动或硬链接到目标系列目录。
3. 调用 `fileSystemScanner.scanFile(destFile)`，重新从目标文件创建 `Book`。
4. 用 `copy(libraryId = series.libraryId, oneshot = series.oneshot)` 补齐书库和 one-shot 状态。
5. 调用 `seriesLifecycle.addBooks(series, listOf(importedBook))` 把书加入系列。
6. 如果是升级旧书，会把旧书的 `Media`、`BookMetadata`、用户缩略图、阅读进度、阅读列表引用迁移到新书 ID。
7. 发布 `DomainEvent.BookImported`，后续任务可能继续分析书籍。

一个典型的哈希流程是：

1. 任务系统或生命周期服务拿到 `Book`。
2. `BookLifecycle.hashAndPersist(book)` 检查所属书库是否启用 `hashFiles`。
3. 如果 `book.fileHash` 为空，调用 `hasher.computeHash(book.path)`。
4. `book.path` 第一次被访问时由 `url.toURI().toPath()` 懒加载得到。
5. 计算出的哈希通过 `bookRepository.update(book.copy(fileHash = hash))` 保存。

## 小白阅读顺序

建议按下面顺序读：

1. 先读 `komga/src/main/kotlin/org/gotson/komga/domain/model/Book.kt`  
   重点看 `Book` 有哪些字段，以及 `path` 是怎么由 `url` 转出来的。

2. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/model/Auditable.kt`  
   理解为什么 `Book` 有 `createdDate` 和 `lastModifiedDate`。

3. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/service/FileSystemScanner.kt`  
   看 `pathToBook()`，这是最直观的 `Book` 创建入口。这里能明白 `name`、`url`、`fileLastModified`、`fileSize` 的来源。

4. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/persistence/BookRepository.kt`  
   理解领域层对 `Book` 的持久化需求有哪些。

5. 再读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/BookDao.kt`  
   看 `insert()`、`updateBook()`、`toDomain()`，理解 `Book` 和数据库表字段如何互相转换。

6. 最后读 `komga/src/main/kotlin/org/gotson/komga/domain/service/BookLifecycle.kt` 和 `komga/src/main/kotlin/org/gotson/komga/domain/service/BookImporter.kt`  
   这两个文件展示 `Book` 在真实业务里的使用：导入、分析、哈希、缩略图、升级旧书等。

## 常见误区

### 误区一：以为 `Book` 保存了完整书籍元数据

`Book` 只保存文件级和归属级信息，不保存作者、简介、ISBN、标签等内容。那些在 `BookMetadata` 中，通过 `bookId` 和 `Book` 关联。

也就是说：

- `Book.name` 更接近文件名。
- `BookMetadata.title` 才是元数据标题。
- `Book.number` 是一个整数字段。
- `BookMetadata.number`、`BookMetadata.numberSort` 才处理更丰富的编号和排序信息。

### 误区二：以为 `url` 和 `path` 是重复字段

`url` 是构造参数和持久化字段，数据库也保存它。`path` 是运行时派生属性，不参与构造，也不直接持久化。

这种设计让领域对象用 `URL` 表达资源位置，同时在需要访问本地文件系统时再转换为 `Path`。不过根据当前片段推断，Komga 的书籍文件主要是本地文件，因为大量调用使用 `book.path`、`toURI().toPath()` 和文件系统 API。

### 误区三：以为 `id` 必须外部传入

`Book.id` 有默认值：

```kotlin
TsidCreator.getTsid256().toString()
```

所以扫描新文件时不需要手动指定 ID。数据库读取已有记录时，`BookDao.toDomain()` 会把数据库中的 `id` 填回来，避免重新生成。

### 误区四：以为 `deletedDate` 表示文件已经从磁盘删除

`deletedDate` 是领域和数据库中的删除标记，表示该书被系统认为已删除或不可用。它不等同于文件系统状态。实际文件是否存在，还要看 `url/path` 对应的文件。

例如 `BookDao.findNotDeletedByLibraryIdAndUrlOrNull()` 会显式过滤 `DELETED_DATE.isNull`，说明系统用这个字段区分“未删除的书”。

### 误区五：忽略 `oneshot`

`oneshot` 不是普通标签，而会影响扫描和导入逻辑。`FileSystemScanner.scanRootFolder()` 中，如果目录匹配 one-shot 配置，会为每本书创建一个独立的 `Series`，并把书复制成 `book.copy(oneshot = true)`。`BookImporter` 中如果目标 series 是 one-shot，也会有专门的路径和升级处理。

### 误区六：以为 `lastModifiedDate` 等于文件修改时间

不是。这里有两个不同概念：

- `fileLastModified`：文件系统层面的文件更新时间。
- `lastModifiedDate`：系统数据库/领域对象层面的记录更新时间，来自 `Auditable`。

`BookDao.updateBook()` 更新数据库记录时会设置 `LAST_MODIFIED_DATE` 为当前 UTC 时间，而不会直接等同于 `fileLastModified`。

### 误区七：以为 `Book` 里应该包含业务方法

这个项目把业务行为放在 service/lifecycle/repository 中，`Book` 更像一个不可变数据模型。需要修改字段时通常使用 Kotlin data class 的 `copy()`，例如：

```kotlin
book.copy(fileHash = hash)
```

这种风格让 `Book` 本身保持简单，也便于在扫描、导入、分析、持久化之间传递。
