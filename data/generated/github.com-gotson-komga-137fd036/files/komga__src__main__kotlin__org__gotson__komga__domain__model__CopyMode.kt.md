# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/CopyMode.kt

## 它负责什么

`CopyMode.kt` 定义了 Komga 领域模型中的一个枚举类型：`CopyMode`。它用来描述“导入书籍文件时，源文件应该如何被放到目标书库目录中”。

这个文件本身非常小，只包含一个 Kotlin `enum class`：

```kotlin
enum class CopyMode {
  MOVE,
  COPY,
  HARDLINK,
}
```

它不直接执行文件操作，也不包含业务流程；它的职责是提供一个稳定、类型安全的取值集合，让 API 层、任务层、领域服务层都用同一套语义来表达导入模式。

在 Komga 当前代码中，`CopyMode` 主要服务于“导入书籍”功能，最终由 `BookImporter.importBook(...)` 根据不同枚举值执行不同的文件系统动作。

## 关键组成

`CopyMode` 位于包：

```kotlin
org.gotson.komga.domain.model
```

它没有额外 import，说明它不依赖其他项目类或第三方库，是一个纯领域枚举。

它包含三个枚举值：

```kotlin
MOVE
COPY
HARDLINK
```

### `MOVE`

表示移动文件。

在 `komga/src/main/kotlin/org/gotson/komga/domain/service/BookImporter.kt` 中，`CopyMode.MOVE` 会触发：

```kotlin
sourceFile.moveTo(destFile)
```

同时，和书籍文件相关的 sidecar 文件也会被移动到目标位置。

sidecar 可以理解为伴随书籍文件存在的附属文件，比如本地元数据、封面或其他由扫描器识别出的旁挂文件。具体有哪些类型需要结合 `FileSystemScanner.scanBookSidecars(...)` 的实现继续阅读。

语义上，`MOVE` 会让原始导入来源消失，文件从原路径转移到 Komga 书库目录中。

### `COPY`

表示复制文件。

在 `BookImporter.kt` 中，`CopyMode.COPY` 会触发：

```kotlin
sourceFile.copyTo(destFile)
```

相关 sidecar 文件也会复制到目标位置。

语义上，`COPY` 会保留原始来源文件，同时在目标书库目录中创建一份副本。这通常是最容易理解、风险也较低的导入方式，因为它不会删除或移动用户原来的文件。

### `HARDLINK`

表示创建硬链接。

在 `BookImporter.kt` 中，`CopyMode.HARDLINK` 会尝试：

```kotlin
Files.createLink(destFile, sourceFile)
```

sidecar 文件也会尝试通过 `Files.createLink(...)` 创建硬链接。

如果文件系统不支持硬链接，或者创建硬链接时发生异常，代码会捕获异常并降级为复制：

```kotlin
sourceFile.copyTo(destFile)
```

所以 `HARDLINK` 的实际语义是：优先使用硬链接，失败时自动 fallback 到 `COPY`。

硬链接不是快捷方式，也不是符号链接。它让两个路径指向同一个底层文件内容。删除其中一个路径通常不会立刻删除实际数据，只要还有其他硬链接存在，文件内容仍然保留。这个特性适合节省磁盘空间，但对普通用户来说容易误解。

## 上下游关系

`CopyMode.kt` 是一个底层领域模型文件，上游通常来自 API 请求，下游进入任务系统和导入服务。

主要链路如下：

```text
REST API 请求
  -> BookImportBatchDto.copyMode
  -> BookController.importBooks(...)
  -> TaskEmitter.importBook(...)
  -> Task.ImportBook.copyMode
  -> TaskHandler 执行任务
  -> BookImporter.importBook(...)
  -> 根据 CopyMode 执行 MOVE / COPY / HARDLINK
```

### 上游：API DTO

`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/BookImportBatchDto.kt` 引用了 `CopyMode`：

```kotlin
data class BookImportBatchDto(
  val books: List<BookImportDto> = emptyList(),
  val copyMode: CopyMode,
)
```

这说明批量导入接口会接收一个统一的 `copyMode`，应用到该批次里的所有书籍。

同一个 DTO 里每本书单独携带：

```kotlin
sourceFile
seriesId
upgradeBookId
destinationName
```

而 `copyMode` 是批次级别的，不是每本书单独设置的。

### 上游：REST Controller

`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/BookController.kt` 中的导入接口：

```kotlin
@PostMapping("api/v1/books/import")
@PreAuthorize("hasRole('ADMIN')")
@ResponseStatus(HttpStatus.ACCEPTED)
fun importBooks(
  @RequestBody bookImportBatch: BookImportBatchDto,
)
```

这里会遍历 `bookImportBatch.books`，并把 `bookImportBatch.copyMode` 传给任务发射器：

```kotlin
taskEmitter.importBook(
  sourceFile = it.sourceFile,
  seriesId = it.seriesId,
  copyMode = bookImportBatch.copyMode,
  destinationName = it.destinationName,
  upgradeBookId = it.upgradeBookId,
  priority = HIGHEST_PRIORITY,
)
```

可以看到，导入接口只创建任务，不同步执行真正的文件移动或复制。接口返回状态是 `ACCEPTED`，说明这是异步处理模型。

### 中游：任务模型

`komga/src/main/kotlin/org/gotson/komga/application/tasks/Task.kt` 中定义了任务类型：

```kotlin
class ImportBook(
  val sourceFile: String,
  val seriesId: String,
  val copyMode: CopyMode,
  val destinationName: String?,
  val upgradeBookId: String?,
  priority: Int = DEFAULT_PRIORITY,
) : Task(priority, seriesId)
```

`copyMode` 被保存进 `Task.ImportBook`，和 `sourceFile`、`seriesId`、`destinationName`、`upgradeBookId` 一起成为异步任务执行时需要的上下文。

### 中游：任务发射器

`komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskEmitter.kt` 中的 `importBook(...)` 接收 `CopyMode` 并创建任务：

```kotlin
fun importBook(
  sourceFile: String,
  seriesId: String,
  copyMode: CopyMode,
  destinationName: String?,
  upgradeBookId: String?,
  priority: Int = DEFAULT_PRIORITY,
) {
  submitTask(Task.ImportBook(sourceFile, seriesId, copyMode, destinationName, upgradeBookId, priority))
}
```

这里仍然不解释 `CopyMode`，只是把它作为任务参数继续传递。

### 下游：任务处理器

`komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskHandler.kt` 中处理 `Task.ImportBook` 时，会调用领域服务：

```kotlin
val importedBook = bookImporter.importBook(
  Paths.get(task.sourceFile),
  series,
  task.copyMode,
  task.destinationName,
  task.upgradeBookId,
)
```

然后继续发起分析任务：

```kotlin
taskEmitter.analyzeBook(importedBook, priority = task.priority + 1)
```

因此 `CopyMode` 决定的是导入阶段的文件落盘方式；导入完成后，后续的媒体分析流程不再关心它。

### 下游：领域服务 `BookImporter`

真正解释 `CopyMode` 的地方是：

```kotlin
komga/src/main/kotlin/org/gotson/komga/domain/service/BookImporter.kt
```

核心分支是：

```kotlin
when (copyMode) {
  CopyMode.MOVE -> { ... }
  CopyMode.COPY -> { ... }
  CopyMode.HARDLINK -> { ... }
}
```

也就是说，如果未来新增枚举值，比如 `SYMLINK`，这里会成为必须修改的核心位置。由于 Kotlin 对 enum 的 `when` 可以做穷尽性检查，新增枚举通常会暴露出未处理分支，帮助开发者补齐逻辑。

## 运行/调用流程

一次导入请求大致会经历以下步骤。

1. 客户端调用导入接口

接口路径是：

```text
POST api/v1/books/import
```

请求体会被反序列化为 `BookImportBatchDto`。其中 `copyMode` 字段会映射到 `CopyMode` 枚举。

根据当前代码可以推断，请求中的枚举字符串应当与 Kotlin 枚举名一致，例如：

```json
{
  "copyMode": "COPY",
  "books": [
    {
      "sourceFile": "/some/path/book.cbz",
      "seriesId": "series-id"
    }
  ]
}
```

这里“根据当前代码可以推断”的依据是：DTO 字段类型直接是 `CopyMode`，没有看到自定义 JSON 映射或别名处理。

2. Controller 创建导入任务

`BookController.importBooks(...)` 要求管理员权限：

```kotlin
@PreAuthorize("hasRole('ADMIN')")
```

它不会直接操作文件，而是对每本书调用：

```kotlin
taskEmitter.importBook(...)
```

并把同一个批次级 `copyMode` 传进去。

3. 任务系统保存 `CopyMode`

`TaskEmitter.importBook(...)` 创建：

```kotlin
Task.ImportBook(sourceFile, seriesId, copyMode, destinationName, upgradeBookId, priority)
```

任务对象中的 `copyMode` 会跟随任务一起进入任务队列。

4. TaskHandler 执行任务

当任务执行到 `Task.ImportBook` 分支时，`TaskHandler` 先查找目标 `Series`：

```kotlin
seriesRepository.findByIdOrNull(task.seriesId)
```

找不到系列时只记录警告，不会调用导入服务。

找到系列后，调用：

```kotlin
bookImporter.importBook(Paths.get(task.sourceFile), series, task.copyMode, task.destinationName, task.upgradeBookId)
```

5. BookImporter 做导入前检查

`BookImporter.importBook(...)` 在处理 `CopyMode` 前，会先做一批通用校验和准备：

- `sourceFile.notExists()` 时抛出文件不存在错误。
- 如果目标 `series` 是 oneshot，但没有 `upgradeBookId`，抛出非法参数异常。
- 遍历所有 library，禁止导入一个已经位于现有 library 路径内的文件。
- 如果是升级已有书籍，检查被升级的 book 是否属于目标 series。
- 根据 `series.oneshot` 决定目标目录：
  - oneshot 系列使用 `series.path.parent`
  - 普通系列使用 `series.path`
- 计算目标文件名：
  - 如果有 `destinationName`，使用 `destinationName + 原扩展名`
  - 否则沿用源文件名
- 扫描源文件的 sidecar，并计算对应的目标 sidecar 路径。
- 如果升级目标文件正好等于已有书籍路径，会先删除旧文件。
- 如果目标文件已经存在且不是上述升级场景，会抛出 `FileAlreadyExistsException`。

这些逻辑和 `CopyMode` 无关，但会影响 `CopyMode` 分支是否有机会执行。

6. 根据 `CopyMode` 执行文件动作

`MOVE`：

```text
移动主文件
移动 sidecar 文件
```

`COPY`：

```text
复制主文件
复制 sidecar 文件
```

`HARDLINK`：

```text
尝试为主文件创建硬链接
尝试为 sidecar 文件创建硬链接
如果失败，记录 warning，并改为复制主文件和 sidecar 文件
```

7. 扫描导入后的目标文件

文件进入目标目录后，`BookImporter` 调用：

```kotlin
fileSystemScanner.scanFile(destFile)
```

扫描成功后，会把扫描得到的 book 补上：

```kotlin
libraryId = series.libraryId
oneshot = series.oneshot
```

然后调用：

```kotlin
seriesLifecycle.addBooks(series, listOf(importedBook))
```

这一步才是真正把导入后的文件挂到系列和书库模型中。

8. 如果是升级书籍，迁移旧书数据

如果 `upgradeBookId` 不为空，`BookImporter` 会把旧书上的一些数据迁移到新导入的书上，包括：

- media，并标记为 `OUTDATED`
- metadata
- 用户上传的缩略图
- 阅读进度
- read list 中的书籍引用

这一段逻辑和 `CopyMode` 的取值没有直接关系，但它说明 `CopyMode` 参与的是“文件层面的替换方式”，不是“业务数据迁移策略”。

9. 导入完成后发起分析

`TaskHandler` 拿到 `importedBook` 后，会调用：

```kotlin
taskEmitter.analyzeBook(importedBook, priority = task.priority + 1)
```

后续分析流程通常会重新解析媒体信息、页面、封面等内容。

## 小白阅读顺序

建议按下面顺序阅读，不要一开始就陷入 `BookImporter` 的所有细节。

1. 先读 `komga/src/main/kotlin/org/gotson/komga/domain/model/CopyMode.kt`

只需要理解它是一个枚举，有三个值：`MOVE`、`COPY`、`HARDLINK`。

重点是：这个文件定义“有哪些模式”，不定义“怎么执行”。

2. 再读 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/BookImportBatchDto.kt`

这里能看到 `CopyMode` 是如何进入系统的：

```kotlin
val copyMode: CopyMode
```

同时注意 `copyMode` 是批量导入请求的字段，而不是每一本书自己的字段。

3. 再读 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/BookController.kt` 中的 `importBooks(...)`

这一步理解 API 层只是接收请求和创建任务，并不直接操作文件。

重点看：

```kotlin
taskEmitter.importBook(...)
```

4. 再读 `komga/src/main/kotlin/org/gotson/komga/application/tasks/Task.kt` 中的 `Task.ImportBook`

这里可以看到 `CopyMode` 被作为任务参数保存下来。理解这一点后，就能明白为什么导入接口可以快速返回 `ACCEPTED`：真正导入是在后台任务里完成的。

5. 再读 `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskHandler.kt` 中的 `Task.ImportBook` 分支

这里是任务进入领域服务的地方。重点看：

```kotlin
bookImporter.importBook(..., task.copyMode, ...)
```

6. 最后读 `komga/src/main/kotlin/org/gotson/komga/domain/service/BookImporter.kt`

这是最重要但也最复杂的文件。建议只先关注 `importBook(...)` 里的这段：

```kotlin
when (copyMode) {
  CopyMode.MOVE -> ...
  CopyMode.COPY -> ...
  CopyMode.HARDLINK -> ...
}
```

等理解三种模式的文件操作差异后，再回头看前面的路径校验、sidecar 处理、升级书籍迁移逻辑。

## 常见误区

### 误区一：以为 `CopyMode.kt` 自己会执行复制或移动

不会。

`CopyMode.kt` 只定义枚举值。真正执行文件操作的是 `BookImporter.importBook(...)`。

`CopyMode` 更像是一个“参数字典”或“领域语言”：它告诉下游服务应该选择哪种策略，但策略实现不在这个文件里。

### 误区二：以为 `COPY` 和 `HARDLINK` 完全一样

不一样。

`COPY` 会创建一份独立副本，占用新的磁盘空间。

`HARDLINK` 优先创建硬链接，通常不复制文件内容，因此可能节省磁盘空间。但硬链接依赖文件系统能力，并且有跨设备、权限、文件系统类型等限制。

当前实现中，如果硬链接失败，会自动降级为复制。因此从用户结果看，目标位置最终仍然会出现文件；但从磁盘空间和底层文件关系看，成功的 hardlink 和 copy 是不同的。

### 误区三：以为 `HARDLINK` 失败会导致导入失败

根据当前 `BookImporter.kt` 片段，不是这样。

`CopyMode.HARDLINK` 的实现包在 `try/catch` 中。如果硬链接失败，会记录 warning：

```text
Filesystem does not support hardlinks, copying instead
```

然后改用 `copyTo(...)`。所以硬链接失败通常不会让导入整体失败，除非 fallback copy 本身也失败。

### 误区四：以为 `MOVE` 只移动主书籍文件

不是。

`MOVE` 不仅移动 `sourceFile`，也会移动通过 `fileSystemScanner.scanBookSidecars(sourceFile)` 找到的 sidecar 文件。

同理，`COPY` 和 `HARDLINK` 也会处理 sidecar。

### 误区五：以为 `copyMode` 是每本书单独设置

从 `BookImportBatchDto` 看，`copyMode` 在批量导入 DTO 的顶层：

```kotlin
val copyMode: CopyMode
```

而每个 `BookImportDto` 只包含：

```kotlin
sourceFile
seriesId
upgradeBookId
destinationName
```

所以当前 API 设计是：一个批次共用一个 `copyMode`。

### 误区六：以为导入接口同步完成导入

不是。

`BookController.importBooks(...)` 返回 `HttpStatus.ACCEPTED`，并通过 `TaskEmitter` 提交 `Task.ImportBook`。真正的文件操作在任务执行阶段由 `TaskHandler` 调用 `BookImporter` 完成。

因此 API 请求成功只表示任务被接受，不一定表示文件已经移动、复制或硬链接完成。

### 误区七：以为 `CopyMode` 会决定导入后的扫描和分析方式

`CopyMode` 只影响文件如何进入目标目录。文件进入后，`BookImporter` 都会调用 `fileSystemScanner.scanFile(destFile)`，然后加入 series，并由 `TaskHandler` 继续触发 `analyzeBook(...)`。

换句话说，无论是 `MOVE`、`COPY` 还是 `HARDLINK`，后续扫描和分析流程基本是同一条路径。

### 误区八：以为可以从已有 library 内导入文件

`BookImporter.importBook(...)` 会遍历所有 library，并检查：

```kotlin
sourceFile.startsWith(library.path)
```

如果源文件已经位于某个现有 library 路径下，会抛出 `PathContainedInPath`。这说明导入功能主要面向“书库外部文件导入到书库”，不是把已有书库内部文件再导入一遍。

### 误区九：以为新增枚举值只需要改 `CopyMode.kt`

如果新增一个模式，例如 `SYMLINK`，只改 `CopyMode.kt` 不够。

至少还需要检查：

- `komga/src/main/kotlin/org/gotson/komga/domain/service/BookImporter.kt` 的 `when (copyMode)`
- API 文档或前端传参是否支持新枚举值
- 测试文件中针对导入行为的覆盖
- 硬链接、移动、复制对应的 sidecar 行为是否需要新增模式同步支持

`CopyMode.kt` 是入口定义，但业务含义必须在调用方中实现。
