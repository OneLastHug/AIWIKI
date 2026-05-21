# 文件：komga/src/main/kotlin/org/gotson/komga/domain/service/FileSystemScanner.kt

## 它负责什么

`FileSystemScanner.kt` 是 Komga 领域层里负责“把真实文件系统映射成领域对象”的扫描器。它不直接写数据库，也不解析漫画内容页，而是读取目录、文件和伴随文件 sidecar，把它们整理成 `ScanResult`，交给上层生命周期服务继续处理。

它主要做三件事：

1. 扫描一个 library 根目录，识别其中的 `Series`、`Book` 和 `Sidecar`。
2. 扫描单个文件，把文件路径转换成一个 `Book` 领域对象。
3. 扫描某本书旁边的 book sidecar 文件，用于导入、升级、转换等局部操作。

在架构位置上，它属于 `org.gotson.komga.domain.service`，由 Spring `@Service` 管理。它的输入是 `Path` 和扫描配置，输出是领域模型，不关心数据库持久化细节。

## 关键组成

这个文件的核心类是：

```kotlin
@Service
class FileSystemScanner(
  private val sidecarBookConsumers: List<SidecarBookConsumer>,
  private val sidecarSeriesConsumers: List<SidecarSeriesConsumer>,
)
```

两个构造参数来自 `komga/src/main/kotlin/org/gotson/komga/infrastructure/sidecar`：

- `SidecarBookConsumer`：定义 book sidecar 的类型、预过滤正则，以及如何判断某个 sidecar 是否属于某本书。
- `SidecarSeriesConsumer`：定义 series sidecar 的类型，以及哪些文件名可以被当作 series sidecar。

也就是说，`FileSystemScanner` 本身不硬编码所有 sidecar 规则，而是把“如何识别 sidecar”的细节交给 consumer 扩展点。

文件内还有一个私有数据类：

```kotlin
private data class TempSidecar(
  val name: String,
  val url: URL,
  val lastModifiedTime: LocalDateTime,
  val type: Sidecar.Type? = null,
)
```

它只用于扫描过程中的临时缓存。原因是 book sidecar 不能在 `visitFile` 阶段立即精确匹配，因为匹配需要知道同一目录下有哪些 `Book`。所以扫描器先把候选 sidecar 存成 `TempSidecar`，等目录遍历结束后再和该目录里的 books 做匹配。

主要公开方法有三个。

`scanRootFolder(...)` 是最重要的方法。它扫描整个 library 根目录，返回：

```kotlin
ScanResult(
  val series: Map<Series, List<Book>>,
  val sidecars: List<Sidecar>,
)
```

它支持这些配置：

- `forceDirectoryModifiedTime`：是否让 series 的修改时间至少不早于其中最新 book 的修改时间。
- `oneshotsDir`：命中特定目录名时，把每本书当作独立 one-shot series。
- `scanCbx`：是否扫描 `cbz`、`zip`、`cbr`、`rar`。
- `scanPdf`：是否扫描 `pdf`。
- `scanEpub`：是否扫描 `epub`。
- `directoryExclusions`：目录排除关键字集合。

`scanFile(path: Path)` 用于单个文件。文件不存在则返回 `null`，存在则通过 `pathToBook` 转成 `Book`。

`scanBookSidecars(path: Path)` 用于扫描某本书同级目录里的 book sidecar。它会取书文件的 `nameWithoutExtension`，再在父目录里找符合 `sidecarBookPrefilter` 的候选文件，并通过 `SidecarBookConsumer.isSidecarBookMatch` 判断是否匹配。

文件底部还有两个扩展函数：

```kotlin
fun BasicFileAttributes.getUpdatedTime(): LocalDateTime =
  maxOf(creationTime(), lastModifiedTime()).toLocalDateTime()

fun FileTime.toLocalDateTime(): LocalDateTime =
  LocalDateTime.ofInstant(this.toInstant(), ZoneId.systemDefault())
```

这里的“更新时间”不是简单使用 `lastModifiedTime`，而是取 `creationTime` 和 `lastModifiedTime` 的较大值。这个时间会被写入 `Book.fileLastModified`、`Series.fileLastModified`、`Sidecar.lastModifiedTime`，上层用它判断磁盘内容是否变化。

## 上下游关系

上游调用者主要在同目录的 service 中。

`komga/src/main/kotlin/org/gotson/komga/domain/service/LibraryContentLifecycle.kt` 是 `scanRootFolder` 的核心调用方。它从 `Library` 读取配置：

- `library.root`
- `library.scanForceModifiedTime`
- `library.oneshotsDirectory`
- `library.scanCbx`
- `library.scanPdf`
- `library.scanEpub`
- `library.scanDirectoryExclusions`

然后调用：

```kotlin
fileSystemScanner.scanRootFolder(...)
```

拿到 `ScanResult` 后，`LibraryContentLifecycle` 会继续做数据库层面的事情，例如：

- 给扫描到的 `Series`、`Book` 补上 `libraryId`。
- 对磁盘上已经不存在的 series 和 books 做 soft delete。
- 新增或更新 series。
- 新增、更新、恢复 books。
- 对 sidecars 和 `SidecarRepository` 中已有记录做对比、保存或清理。

所以 `FileSystemScanner` 只负责“发现磁盘现状”，`LibraryContentLifecycle` 才负责“让数据库状态跟磁盘现状同步”。

其他调用方包括：

- `komga/src/main/kotlin/org/gotson/komga/domain/service/TransientBookLifecycle.kt`：调用 `scanRootFolder` 扫描临时目录。
- `komga/src/main/kotlin/org/gotson/komga/domain/service/BookImporter.kt`：调用 `scanBookSidecars` 和 `scanFile`，用于导入或升级书籍时处理单本书及其 sidecar。
- `komga/src/main/kotlin/org/gotson/komga/domain/service/BookPageEditor.kt`：编辑页面后调用 `scanFile` 重新获得文件大小、修改时间等信息。
- `komga/src/main/kotlin/org/gotson/komga/domain/service/BookConverter.kt`：转换格式后调用 `scanFile` 识别输出文件。
- `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskHandler.kt`：任务层触发 library 扫描，实际会进入 `LibraryContentLifecycle.scanRootFolder`。

下游领域模型主要是：

- `Book`：位于 `komga/src/main/kotlin/org/gotson/komga/domain/model/Book.kt`，包含 `name`、`url`、`fileLastModified`、`fileSize`、`oneshot` 等信息。
- `Series`：位于 `komga/src/main/kotlin/org/gotson/komga/domain/model/Series.kt`，包含 `name`、`url`、`fileLastModified`、`oneshot` 等信息。
- `Sidecar`：位于 `komga/src/main/kotlin/org/gotson/komga/domain/model/Sidecar.kt`，包含 `url`、`parentUrl`、`lastModifiedTime`、`type`、`source`。
- `ScanResult`：位于 `komga/src/main/kotlin/org/gotson/komga/domain/model/ScanResult.kt`，包装扫描出来的 series/books 映射和 sidecars 列表。

## 运行/调用流程

`scanRootFolder` 的流程可以按“准备、遍历、目录收尾、返回结果”理解。

第一步，准备扫描扩展名。

```kotlin
val scanForExtensions =
  buildList {
    if (scanCbx) addAll(listOf("cbz", "zip", "cbr", "rar"))
    if (scanPdf) add("pdf")
    if (scanEpub) add("epub")
  }
```

这说明 Komga 的 library 扫描并不天然扫描所有文件，而是受 library 配置控制。比如关闭 `scanPdf` 后，`.pdf` 文件不会被当作 `Book`。

第二步，校验根目录。

```kotlin
if (!(Files.isDirectory(root) && Files.isReadable(root)))
  throw DirectoryNotFoundException("Folder is not accessible: $root", "ERR_1016")
```

如果根路径不是可读目录，会抛出 `DirectoryNotFoundException`。上层 `LibraryContentLifecycle` 捕获后会把 library 标记为不可用，并继续抛出异常。

第三步，初始化扫描过程中的临时结构。

```kotlin
val pathToSeries = mutableMapOf<Path, Series>()
val pathToSeriesSidecars = mutableMapOf<Path, MutableList<Sidecar>>()
val pathToBooks = mutableMapOf<Path, MutableList<Book>>()
val pathToBookSidecars = mutableMapOf<Path, MutableList<TempSidecar>>()
```

这些 map 的 key 基本都是目录 `Path`：

- `pathToSeries`：某个目录对应的临时 `Series`。
- `pathToBooks`：某个目录下发现的 books。
- `pathToSeriesSidecars`：某个目录下发现的 series sidecars。
- `pathToBookSidecars`：某个目录下发现的 book sidecar 候选。

第四步，用 `Files.walkFileTree` 遍历目录树。

它使用：

```kotlin
Files.walkFileTree(
  root,
  setOf(FileVisitOption.FOLLOW_LINKS),
  Integer.MAX_VALUE,
  object : FileVisitor<Path> { ... }
)
```

这里启用了 `FOLLOW_LINKS`，所以符号链接目录也可能被跟随遍历。最大深度是 `Integer.MAX_VALUE`，也就是理论上会递归扫描整个树。

`preVisitDirectory` 在进入目录前执行。它做两件事：

1. 跳过隐藏目录和排除目录。
2. 给每个未跳过的目录创建一个临时 `Series`。

跳过条件是：

```kotlin
dir.name.startsWith(".") ||
directoryExclusions.any { exclude ->
  dir.pathString.contains(exclude, true)
}
```

这里要注意，`directoryExclusions` 用的是 `contains(exclude, true)`，不是精确目录名匹配，也不是 glob。只要路径字符串中包含该排除片段，就会跳过整棵子树。

创建 `Series` 时，名称来自目录名：

```kotlin
Series(
  name = dir.name.ifBlank { dir.pathString },
  url = dir.toUri().toURL(),
  fileLastModified = attrs.getUpdatedTime(),
)
```

如果目录名为空，则退回使用完整路径字符串。根路径在某些平台或特殊路径下可能出现这种保护逻辑。

`visitFile` 在访问文件时执行。它会忽略符号链接和目录，只处理普通文件或其他非目录文件：

```kotlin
if (!attrs.isSymbolicLink && !attrs.isDirectory) { ... }
```

在文件访问阶段，它做三类识别。

第一类是 book 文件。

如果扩展名在 `scanForExtensions` 中，且文件名不是隐藏文件，就调用 `pathToBook(file, attrs)`：

```kotlin
Book(
  name = path.nameWithoutExtension,
  url = path.toUri().toURL(),
  fileLastModified = attrs.getUpdatedTime(),
  fileSize = attrs.size(),
)
```

然后把这本书放到 `pathToBooks[file.parent]` 中。也就是说，Komga 在这个扫描器里的默认建模是：一个目录就是一个 series，目录里的每个支持格式文件就是该 series 的 book。

第二类是 series sidecar。

扫描器会遍历 `sidecarSeriesConsumers`，检查当前文件名是否等于某个 consumer 声明的文件名：

```kotlin
consumer.getSidecarSeriesFilenames().any { file.name.equals(it, ignoreCase = true) }
```

匹配后会创建：

```kotlin
Sidecar(
  file.toUri().toURL(),
  file.parent.toUri().toURL(),
  attrs.getUpdatedTime(),
  it.getSidecarSeriesType(),
  Sidecar.Source.SERIES
)
```

这里 `parentUrl` 是当前目录 URL，`source` 是 `SERIES`。

第三类是 book sidecar 候选。

book sidecar 先通过预过滤：

```kotlin
if (sidecarBookPrefilter.any { it.matches(file.name) }) { ... }
```

预过滤只说明“这个文件可能是 book sidecar”，还不能说明它属于哪本书。扫描器会先把它放进 `pathToBookSidecars[file.parent]`，等目录结束后再匹配。

第五步，`postVisitDirectory` 在离开目录时执行。这是整段逻辑最关键的地方。

它先取出当前目录下发现的 books 和临时 series：

```kotlin
val books = pathToBooks[dir]
val tempSeries = pathToSeries[dir]
```

如果目录里没有 books，则不会把该目录加入最终结果。换句话说，虽然 `preVisitDirectory` 会为每个目录创建临时 `Series`，但只有包含 book 文件的目录才会成为最终的 series。

如果命中 `oneshotsDir`：

```kotlin
if (!oneshotsDir.isNullOrBlank() && dir.pathString.contains(oneshotsDir, true)) { ... }
```

则不会把整个目录作为一个普通 series，而是对目录里的每一本 book 创建一个独立 `Series`：

```kotlin
Series(
  name = book.name,
  url = book.url,
  fileLastModified = book.fileLastModified,
  oneshot = true,
)
```

并且 book 也会复制为 `oneshot = true`。这适合“一本文件就是一个独立作品”的目录结构。

如果不是 one-shot 目录，则按普通 series 处理。

当 `forceDirectoryModifiedTime` 为 `true` 时，series 的 `fileLastModified` 会取目录更新时间和该目录下最新 book 更新时间的较大值：

```kotlin
tempSeries.copy(
  fileLastModified = maxOf(tempSeries.fileLastModified, books.maxOf { it.fileLastModified })
)
```

这对某些文件系统很重要。根据当前片段推断，原因是有些网络文件系统或缓存场景中，目录修改时间不一定可靠，上层又依赖 series 修改时间判断是否需要深度扫描。

普通 series 加入 `scannedSeries` 后，series sidecar 才会加入最终 `scannedSidecars`：

```kotlin
pathToSeriesSidecars[dir]?.let { scannedSidecars.addAll(it) }
```

代码注释也强调：只有 series 有 books 时，series sidecar 才会被加入。空目录里的 sidecar 不会产生最终记录。

最后处理 book sidecar。

对当前目录下每本 book，扫描器会拿之前缓存的 `TempSidecar` 候选逐个尝试：

```kotlin
sidecarBookConsumers.firstOrNull {
  it.isSidecarBookMatch(book.name, sidecar.name)
}
```

匹配成功后创建真正的 `Sidecar`：

```kotlin
Sidecar(
  sidecar.url,
  book.url,
  sidecar.lastModifiedTime,
  type,
  Sidecar.Source.BOOK
)
```

这里要特别注意：book sidecar 的 `parentUrl` 是 `book.url`，不是目录 URL。series sidecar 的 `parentUrl` 才是目录 URL。

匹配后的候选会从 `pathToBookSidecars[dir]` 里移除，避免被后续 book 重复使用。

第六步，扫描结束后返回：

```kotlin
return ScanResult(scannedSeries, scannedSidecars)
```

扫描器还会记录耗时和数量：

- series 数量
- books 总数
- sidecars 数量

但日志只是观测用途，不影响业务结果。

## 小白阅读顺序

建议按下面顺序读，不要一上来陷进 `walkFileTree` 的所有回调细节。

1. 先看文件头部 imports，确认它依赖哪些领域模型：`Book`、`Series`、`Sidecar`、`ScanResult`、`DirectoryNotFoundException`。
2. 再看构造函数，理解它通过 `SidecarBookConsumer` 和 `SidecarSeriesConsumer` 扩展 sidecar 识别规则。
3. 看 `pathToBook`，这是最简单的转换逻辑：一个 `Path` 加文件属性变成一个 `Book`。
4. 看 `scanFile`，理解单文件扫描只是 `exists` 检查加 `pathToBook`。
5. 看 `scanBookSidecars`，理解 book sidecar 是通过“书文件基础名 + 同目录候选文件 + consumer 匹配”识别的。
6. 最后读 `scanRootFolder`，重点抓住四个 map：`pathToSeries`、`pathToBooks`、`pathToSeriesSidecars`、`pathToBookSidecars`。
7. 读 `walkFileTree` 时按回调顺序理解：`preVisitDirectory` 创建候选 series，`visitFile` 收集 books/sidecars，`postVisitDirectory` 把候选整理进最终结果。
8. 再回到 `LibraryContentLifecycle.scanRootFolder`，看扫描结果如何被用于新增、更新、删除 series/books/sidecars。

如果只想快速理解业务含义，可以记住一句话：`FileSystemScanner` 把“目录树”变成“Series -> Books”的结构，同时把 metadata/artwork 这类 sidecar 文件挂到对应的 series 或 book 上。

## 常见误区

第一个误区是以为每个目录都会成为 series。实际不是。`preVisitDirectory` 确实会为每个目录创建临时 `Series`，但 `postVisitDirectory` 只有在该目录下存在 book 文件时，才会加入 `scannedSeries`。空目录不会成为最终 series。

第二个误区是以为扫描器会解析漫画压缩包内容。这个文件不会读取 `cbz`、`zip`、`cbr`、`rar`、`pdf`、`epub` 的内部页面，它只根据文件扩展名、文件大小、修改时间创建 `Book`。媒体分析应在其他服务中完成。

第三个误区是以为 `directoryExclusions` 是精确匹配。这里用的是路径字符串的大小写不敏感包含判断：`dir.pathString.contains(exclude, true)`。因此排除词过短可能误伤更多目录。

第四个误区是忽略隐藏目录和隐藏文件。目录名以 `.` 开头会被整棵跳过；book 文件名以 `.` 开头不会被扫描成书。

第五个误区是混淆 series sidecar 和 book sidecar 的 `parentUrl`。series sidecar 的 `parentUrl` 指向目录；book sidecar 的 `parentUrl` 指向书文件 URL。这会影响后续 repository 如何判断 sidecar 归属。

第六个误区是以为 book sidecar 在 `visitFile` 阶段就完成匹配。实际它先进入 `TempSidecar` 候选列表，到 `postVisitDirectory` 时才根据当前目录里的 books 做精确匹配。

第七个误区是以为 `forceDirectoryModifiedTime` 会修改真实文件系统时间。它不会写磁盘，只是在构造 `Series` 领域对象时，把 `fileLastModified` 调整为目录时间和最新 book 时间中的较大值。

第八个误区是以为 one-shot 目录仍然是“一个目录一个 series”。当目录路径包含 `oneshotsDir` 时，目录里的每本书都会变成一个独立 series，series 的 `url` 也会使用 book 的 URL，并标记 `oneshot = true`。

第九个误区是以为 `FileSystemScanner` 会保存扫描结果。它不访问 repository。保存、更新、删除、恢复这些动作在 `LibraryContentLifecycle`、`BookImporter` 等上层服务里完成。

第十个误区是忽略 `getUpdatedTime()` 的时间策略。Komga 在这里用 `creationTime` 和 `lastModifiedTime` 的较大值作为更新时间，而不是单纯使用文件最后修改时间。上层判断变更时依赖这个值，因此它是扫描结果稳定性的重要组成部分。
