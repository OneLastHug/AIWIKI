# 文件：komga/src/main/kotlin/org/gotson/komga/domain/service/BookImporter.kt

## 它负责什么

`BookImporter` 是 Komga 领域层里的“书籍导入服务”。它负责把一个外部文件导入到指定 `Series` 中，并在导入过程中完成文件操作、数据库记录创建、升级旧书、迁移旧书关联数据、处理 sidecar 文件、发布事件和触发后续任务。

它不是 API Controller，也不是后台任务调度器本身。它更像导入流程的业务核心：上游告诉它“把哪个文件导入哪个系列、用复制/移动/硬链接哪种模式、是否替换某本旧书”，它负责把这个动作真正落到文件系统和领域数据上。

从代码看，它主要覆盖两类场景：

1. 普通导入：把 `sourceFile` 导入到目标 `series`，生成新的 `Book`，加入系列并排序。
2. 升级导入：传入 `upgradeBookId`，导入新文件后替换旧 `Book`，并把旧书的媒体信息、元数据、用户上传封面、阅读进度、阅读列表引用迁移到新书上。

## 关键组成

`BookImporter` 是一个 Spring `@Service`，构造函数注入了大量领域服务、仓库和事件组件。核心公开方法只有一个：

```kotlin
fun importBook(
  sourceFile: Path,
  series: Series,
  copyMode: CopyMode,
  destinationName: String? = null,
  upgradeBookId: String? = null,
): Book
```

参数含义如下：

- `sourceFile`：待导入的原始文件路径。
- `series`：目标系列。
- `copyMode`：导入文件的方式，支持 `CopyMode.MOVE`、`CopyMode.COPY`、`CopyMode.HARDLINK`。
- `destinationName`：可选目标文件名，不含扩展名；如果传入，会用这个名字替换原文件名。
- `upgradeBookId`：可选旧书 ID；传入时表示这次导入是在升级/替换某本已有书。

主要依赖可以按职责分组理解：

- 文件扫描与文件操作：
  - `FileSystemScanner`：扫描书籍文件和 sidecar 文件。
  - `java.nio.file.Files`、Kotlin `Path` 扩展：执行复制、移动、硬链接、删除、属性读取等文件操作。

- 领域生命周期：
  - `SeriesLifecycle`：把新书加入系列，并在导入后重新排序。
  - `BookLifecycle`：升级场景中删除旧书。
  - `TaskEmitter`：导入 sidecar 后触发刷新本地封面或元数据任务。

- 数据仓库：
  - `BookRepository`：查找被升级的旧书。
  - `MediaRepository`：迁移媒体分析记录，并标记为 `Media.Status.OUTDATED`。
  - `BookMetadataRepository`：迁移旧书元数据。
  - `ThumbnailBookRepository`：迁移用户上传的书籍缩略图。
  - `ReadProgressRepository`：迁移阅读进度。
  - `ReadListRepository`：把阅读列表中的旧书 ID 替换为新书 ID。
  - `LibraryRepository`：检查源文件是否已经位于某个 Komga library 内。
  - `SidecarRepository`：保存导入后的 sidecar 记录。
  - `HistoricalEventRepository`：记录导入、删除旧文件等历史事件。
  - `SeriesRepository`：one-shot 系列升级时更新系列自身的文件信息。

- 事件：
  - `ApplicationEventPublisher`：发布 `DomainEvent.BookImported`，无论成功失败都会发布。
  - `HistoricalEvent.BookImported`、`HistoricalEvent.BookFileDeleted`：写入历史事件。

文件中的 import 基本都服务于上述职责。它没有 Kotlin 意义上的 export；对外暴露的是 Spring Bean `BookImporter` 以及它的 `importBook` 方法。

## 上下游关系

上游调用链大致是：

`BookController.importBooks`  
→ `TaskEmitter.importBook`  
→ 后台任务 `Task.ImportBook`  
→ `TaskHandler`  
→ `BookImporter.importBook`

在 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/BookController.kt` 中，`POST api/v1/books/import` 接收 `BookImportBatchDto`，逐本调用 `taskEmitter.importBook(...)` 创建导入任务。该接口要求管理员权限，返回 `202 ACCEPTED`，说明导入是异步执行的。

在 `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskEmitter.kt` 中，`importBook(...)` 只是封装并提交 `Task.ImportBook`。

在 `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskHandler.kt` 中，处理 `Task.ImportBook` 时会先通过 `seriesRepository.findByIdOrNull(task.seriesId)` 找到目标系列，然后调用：

```kotlin
bookImporter.importBook(
  Paths.get(task.sourceFile),
  series,
  task.copyMode,
  task.destinationName,
  task.upgradeBookId,
)
```

导入成功后，`TaskHandler` 还会调用 `taskEmitter.analyzeBook(importedBook, priority = task.priority + 1)`，也就是说 `BookImporter` 只负责导入和基础关联迁移，不负责完整分析书籍内容；分析动作是后续任务。

下游关系主要包括：

- 写入新书：通过 `fileSystemScanner.scanFile(destFile)` 生成 `Book`，再通过 `seriesLifecycle.addBooks(series, listOf(importedBook))` 加入系列。
- 迁移旧数据：升级导入时把旧书上的 media、metadata、user uploaded thumbnails、read progress、read list 引用迁移到新书。
- 删除旧书：升级导入末尾调用 `bookLifecycle.deleteOne(bookToUpgrade)`。
- 触发 sidecar 刷新：如果 sidecar 类型是 `ARTWORK`，调用 `taskEmitter.refreshBookLocalArtwork(importedBook)`；如果是 `METADATA`，调用 `taskEmitter.refreshBookMetadata(importedBook)`。
- 发布领域事件：成功或失败都会发布 `DomainEvent.BookImported`，成功时还写入 `HistoricalEvent.BookImported`。

## 运行/调用流程

`importBook` 的执行流程可以按阶段理解。

第一阶段是前置校验。

它先检查 `sourceFile.notExists()`，不存在则抛出带错误码 `ERR_1018` 的 `FileNotFoundException`。然后检查 one-shot 系列：如果目标 `series.oneshot == true`，但没有传 `upgradeBookId`，就抛出异常。原因是 one-shot 系列本身对应单个文件，导入到 one-shot 时更像“替换/升级”，不能像普通系列那样额外添加一本。

接着它遍历所有 library，判断 `sourceFile.startsWith(library.path)`。如果源文件已经位于现有 library 内，会抛出 `PathContainedInPath`，错误码 `ERR_1019`。这可以避免把库内文件又导入到库中，造成路径管理和扫描逻辑混乱。

如果传了 `upgradeBookId`，它会查找旧书，并确认旧书属于当前 `series`。如果旧书不属于该系列，抛出带 `ERR_1020` 的异常。

第二阶段是计算目标路径。

目标目录 `destDir` 的选择逻辑是：

- 如果 `series.oneshot`，使用 `series.path.parent`。
- 否则使用 `series.path`。

目标文件 `destFile` 的名称逻辑是：

- 如果传了 `destinationName`，生成 `${destinationName}.${sourceFile.extension}`，并取安全的文件名部分。
- 否则沿用 `sourceFile.name`。

同时它会调用 `fileSystemScanner.scanBookSidecars(sourceFile)` 扫描源文件旁边的 sidecar，并为每个 sidecar 计算导入后的目标路径。如果传了 `destinationName`，sidecar 文件名中与源书文件名主干相同的部分也会被替换为 `destinationName`。

第三阶段是处理目标冲突和旧文件。

如果是升级导入，并且新目标路径刚好等于旧书路径，代码会先删除旧文件，并插入 `HistoricalEvent.BookFileDeleted`。这个分支用 `deletedUpgradedFile` 记录旧文件已经删过，避免后面重复删除。

如果不是上述情况，但 `destFile.exists()`，就抛出 `FileAlreadyExistsException`，错误码 `ERR_1021`。也就是说普通导入不会覆盖已有目标文件。

如果升级旧书存在路径，代码还会扫描旧书的 sidecar 并删除这些旧 sidecar 文件。这一步发生在复制/移动新文件之前。

第四阶段是真正导入文件。

根据 `copyMode` 分三种：

- `CopyMode.MOVE`：调用 `sourceFile.moveTo(destFile)`，sidecar 也移动到目标路径。
- `CopyMode.COPY`：调用 `sourceFile.copyTo(destFile)`，sidecar 也复制到目标路径。
- `CopyMode.HARDLINK`：优先用 `Files.createLink(destFile, sourceFile)` 创建硬链接；sidecar 也尝试硬链接。如果硬链接失败，会记录 warning，然后退回到复制模式。

注意 `HARDLINK` 模式对 sidecar 会先 `deleteIfExists()` 再 `Files.createLink(...)`，而普通目标书文件前面已经做过存在性检查。

第五阶段是扫描新书并加入系列。

文件落到目标位置后，代码调用：

```kotlin
fileSystemScanner.scanFile(destFile)
```

如果扫描成功，会得到一个新的 `Book`，并通过 `copy(libraryId = series.libraryId, oneshot = series.oneshot)` 补上目标库 ID 和 one-shot 标记。如果扫描失败，会抛出 `ERR_1022`。

然后调用：

```kotlin
seriesLifecycle.addBooks(series, listOf(importedBook))
```

这一步把新书纳入系列生命周期管理。

第六阶段是升级旧书的数据迁移。

只有 `bookToUpgrade != null` 时才进入这一段。

它会做以下迁移：

- 从旧书复制 `Media` 到新书，并把状态改为 `Media.Status.OUTDATED`，表示后续需要重新分析。
- 从旧书复制 metadata 到新书。
- 把旧书上 `ThumbnailBook.Type.USER_UPLOADED` 的缩略图改挂到新书。
- 把旧书所有阅读进度复制成新书阅读进度。
- 遍历包含旧书的 read list，把列表中的旧书 ID 替换为新书 ID，并用 `toIndexedMap()` 保持索引结构。
- 如果旧书文件之前还没删，则删除旧书文件并写历史事件。
- 调用 `bookLifecycle.deleteOne(bookToUpgrade)` 删除旧书领域对象。
- 如果是 one-shot 系列，更新 `series.url` 和 `series.fileLastModified`，避免下一次扫描时把系列标记为 not found。

第七阶段是收尾。

它会调用 `seriesLifecycle.sortBooks(series)` 重新排序系列内书籍。

然后遍历导入过来的 sidecar：

- `Sidecar.Type.ARTWORK`：触发刷新本地封面任务。
- `Sidecar.Type.METADATA`：触发刷新书籍元数据任务。

随后构造新的 `Sidecar` 对象，把 `url`、`parentUrl`、`lastModifiedTime` 更新为目标文件信息，并调用 `sidecarRepository.save(importedBook.libraryId, destSidecar)` 保存。

最后插入 `HistoricalEvent.BookImported`，并发布成功的 `DomainEvent.BookImported(importedBook, sourceFile.toUri().toURL(), success = true)`，返回 `importedBook`。

整个方法包在 `try/catch` 中。如果中途发生异常，会发布失败事件：

```kotlin
DomainEvent.BookImported(null, sourceFile.toUri().toURL(), success = false, msg)
```

其中 `msg` 优先取 `CodedException.code`，否则取异常 message。发布失败事件后异常会继续向上抛出。

## 小白阅读顺序

建议先从方法签名看起：

`BookImporter.importBook(...)`

先搞清楚五个参数分别代表“源文件、目标系列、导入方式、目标文件名、是否升级旧书”。理解这些参数后，后面的分支会清楚很多。

第二步看前置校验：

- 文件是否存在。
- one-shot 系列是否必须走升级。
- 源文件是否已经在某个 library 内。
- `upgradeBookId` 对应的旧书是否属于目标系列。

这些校验说明了这个服务的边界：它只允许把“库外文件”导入到“明确的目标系列”，并且升级时不能跨系列替换。

第三步看路径计算：

重点关注 `destDir`、`destFile`、`sidecars` 三个变量。它们决定了导入后的文件和 sidecar 会放在哪里。这里也是理解 `destinationName` 的关键。

第四步看 `when (copyMode)`：

这里是文件系统层面的核心。`MOVE`、`COPY` 很直观，`HARDLINK` 多了失败后回退复制的逻辑。

第五步看 `fileSystemScanner.scanFile(destFile)` 和 `seriesLifecycle.addBooks(...)`：

这两句是从“文件已经复制到磁盘”转向“领域模型里有一本新书”的分界线。

第六步看 `if (bookToUpgrade != null)`：

这是整份文件最复杂的部分。可以把它当成“旧书数据迁移清单”来读：media、metadata、thumbnail、read progress、read list、旧文件、旧 book、one-shot series 状态。

最后看 sidecar 和事件发布：

sidecar 会触发后续刷新任务；`HistoricalEvent` 是持久历史记录；`DomainEvent.BookImported` 是应用内事件通知。成功和失败都会发事件，这是理解外部状态反馈的重点。

## 常见误区

第一个误区：以为 `BookImporter` 会完成书籍内容分析。

实际上它只是在导入后通过 `fileSystemScanner.scanFile(destFile)` 得到基础 `Book`，并把书加入系列。真正的分析任务在上游 `TaskHandler` 里导入成功后继续触发：`taskEmitter.analyzeBook(importedBook, priority = task.priority + 1)`。所以导入和分析是两个阶段。

第二个误区：以为 `COPY`、`MOVE`、`HARDLINK` 只作用于主书籍文件。

代码里 sidecar 文件也会跟随主文件一起复制、移动或硬链接。导入完成后，sidecar 还会被保存到 `SidecarRepository`，并可能触发刷新封面或元数据任务。

第三个误区：以为升级旧书只是覆盖文件。

升级流程远比覆盖文件复杂。它会创建一本新的 `Book`，再迁移旧书的 media、metadata、用户上传封面、阅读进度、阅读列表引用，然后删除旧书。尤其是 media 会被迁移到新书并标记为 `OUTDATED`，表示后续需要重新分析。

第四个误区：以为目标文件存在时会自动覆盖。

普通导入时，如果 `destFile.exists()`，会直接抛出 `FileAlreadyExistsException`，错误码 `ERR_1021`。只有升级场景中“新目标路径正好等于旧书路径”时，才会先删除旧文件，为导入让路。

第五个误区：忽略 one-shot 系列的特殊处理。

`series.oneshot` 会影响多个地方：没有 `upgradeBookId` 时禁止导入；目标目录用 `series.path.parent`；新书会带上 `oneshot` 标记；升级完成后还要更新 `Series` 的 `url` 和 `fileLastModified`。这说明 one-shot 系列在 Komga 中更接近“单文件系列”，不能简单当成普通目录系列处理。

第六个误区：以为失败时没有外部反馈。

`importBook` 用 `try/catch` 包住整个流程。失败时仍然会发布 `DomainEvent.BookImported(..., success = false, msg)`，然后再把异常抛出。也就是说调用方可以感知异常，事件监听方也可以收到失败事件。
