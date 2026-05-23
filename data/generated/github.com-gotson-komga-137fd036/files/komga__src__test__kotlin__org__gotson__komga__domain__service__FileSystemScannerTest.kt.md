# 文件：komga/src/test/kotlin/org/gotson/komga/domain/service/FileSystemScannerTest.kt

## 它负责什么

`FileSystemScannerTest.kt` 是 `FileSystemScanner` 的单元测试文件，重点验证“从文件系统目录扫描出漫画库内容”的基础规则是否正确。

它不直接测试数据库、导入流程或媒体分析，而是把一个临时文件系统组织成不同目录结构，然后调用：

`FileSystemScanner.scanRootFolder(...)`

最后断言返回的 `ScanResult.series` 是否符合预期。这里的 `series` 类型是：

`Map<Series, List<Book>>`

也就是说，扫描器会把文件系统中的目录识别成 `Series`，把目录里的漫画文件识别成 `Book`。测试文件主要覆盖这些行为：

- 根目录不存在时抛出 `DirectoryNotFoundException`
- 空目录扫描结果为空
- 根目录中只有文件时，会把根目录本身视为一个 `Series`
- 支持 `.cbz`、`.zip`、`.cbr`、`.rar`、`.pdf`、`.epub`
- 可以按库配置关闭 CBX、PDF、EPUB 扫描
- 不支持的文件扩展名会被忽略
- 子目录会各自成为独立 `Series`
- 符号链接目录会被跟随扫描
- 被排除目录、隐藏目录、隐藏文件不会进入结果
- 扩展名大小写不敏感，例如 `comic.Cbz`、`comic2.CBR`
- `_oneshots` 这类 one-shot 目录会被特殊处理：每个文件单独成为一个 `Series`

这个测试文件的核心价值是固定 `FileSystemScanner` 的文件系统语义，避免未来修改扫描逻辑时破坏库扫描的基础行为。

## 关键组成

文件位于测试包：

`org.gotson.komga.domain.service`

它测试的主类位于：

`komga/src/main/kotlin/org/gotson/komga/domain/service/FileSystemScanner.kt`

### `scanner`

测试类里定义了一个成员：

`private val scanner = FileSystemScanner(emptyList(), emptyList())`

`FileSystemScanner` 构造函数需要两个依赖：

- `List<SidecarBookConsumer>`
- `List<SidecarSeriesConsumer>`

这里传入 `emptyList()`，说明本测试不关心 sidecar 文件，例如外部元数据文件、封面文件等。它只聚焦目录和书籍文件扫描。

### `Jimfs`

大部分测试都使用：

`Jimfs.newFileSystem(Configuration.unix()).use { fs -> ... }`

`Jimfs` 是 Google Guava 提供的内存文件系统。它让测试可以在内存中创建 `/root`、`/link`、`.hidden`、`_oneshots` 等路径，而不需要真实修改本机磁盘。

这对文件系统扫描测试很重要，因为它可以稳定模拟：

- Unix 风格路径
- 根目录 `/`
- 普通目录
- 普通文件
- 符号链接
- 隐藏文件和隐藏目录

### `Files`

测试中通过 Java NIO 的 `Files` 创建目录、文件、符号链接：

- `Files.createDirectory(root)`
- `Files.createFile(root.resolve(it))`
- `Files.createSymbolicLink(link, root)`

这些操作都是为了给 `scanRootFolder` 准备输入目录结构。

### `FilenameUtils.removeExtension`

测试期望书籍名不包含扩展名，例如 `file1.cbz` 扫描成 `Book(name = "file1")`。

因此测试用：

`FilenameUtils.removeExtension(it)`

把源文件名转换成期望的书籍名。

实际生产代码里对应的是 Kotlin path API：

`path.nameWithoutExtension`

### `catchThrowable`

第一个测试使用 AssertJ 的：

`catchThrowable { scanner.scanRootFolder(root) }`

用于捕获异常并断言类型：

`DirectoryNotFoundException`

它验证的是不可访问根目录的错误路径。

### `libraryScanFileTypesArguments`

这是参数化测试的数据源：

`private fun libraryScanFileTypesArguments(): Stream<Arguments>`

它构造了一组源文件：

`cbz.cbz`、`cbr.cbr`、`zip.zip`、`rar.rar`、`pdf.pdf`、`epub.epub`

然后组合 `scanCbz`、`scanPdf`、`scanEpub` 三个布尔参数，验证不同库配置下应该扫描哪些文件。

注意这里参数名有一个容易看错的点：测试方法参数叫 `scanCbz`，但调用 `scanRootFolder` 时使用的命名参数是：

`scanCbx = scanCbz`

生产代码中参数名是 `scanCbx`，它代表 CBX 类漫画归档格式集合，包括 `cbz`、`zip`、`cbr`、`rar`。

### `makeSubDir`

文件末尾有一个测试辅助函数：

`makeSubDir(root: Path, name: String, files: List<String>): Path`

它会：

1. 用 `root.resolve(name)` 创建子目录
2. 在该子目录下创建传入的文件
3. 返回创建出来的目录路径

这个函数让测试可以快速写出结构：

`root/series1/volume1.cbz`

`root/series1/volume2.cbz`

`root/series2/book1.cbz`

`root/series2/book2.cbz`

不过实现里创建文件时使用的是：

`Files.createFile(root.resolve(root.fileSystem.getPath(name, it)))`

它等价于在 `root/name/it` 下创建文件。阅读时不要误以为文件创建在当前工作目录，它仍然是 `root` 下的子路径。

## 上下游关系

### 被测试对象：`FileSystemScanner`

本测试直接覆盖：

`komga/src/main/kotlin/org/gotson/komga/domain/service/FileSystemScanner.kt`

核心方法是：

`scanRootFolder(root: Path, forceDirectoryModifiedTime: Boolean = false, oneshotsDir: String? = null, scanCbx: Boolean = true, scanPdf: Boolean = true, scanEpub: Boolean = true, directoryExclusions: Set<String> = emptySet()): ScanResult`

生产代码的关键逻辑包括：

- 先根据 `scanCbx`、`scanPdf`、`scanEpub` 组合出要扫描的扩展名集合
- 检查 `root` 是否是可读目录
- 使用 `Files.walkFileTree` 遍历目录树
- 使用 `FileVisitOption.FOLLOW_LINKS` 跟随符号链接
- 在 `preVisitDirectory` 中把目录登记为候选 `Series`
- 如果目录名以 `.` 开头，跳过整个子树
- 如果目录路径包含 `directoryExclusions` 中的排除片段，跳过整个子树
- 在 `visitFile` 中把匹配扩展名的文件转换成 `Book`
- 如果文件名以 `.` 开头，忽略隐藏文件
- 在 `postVisitDirectory` 中把当前目录的 `Series` 与直接子文件形成最终扫描结果
- 如果目录路径包含 `oneshotsDir`，则每个文件单独变成一个 `oneshot = true` 的 `Series`

测试文件中的每个场景基本都能映射到这些分支。

### 返回模型：`ScanResult`

`ScanResult` 位于：

`komga/src/main/kotlin/org/gotson/komga/domain/model/ScanResult.kt`

结构很简单：

```kotlin
data class ScanResult(
  val series: Map<Series, List<Book>>,
  val sidecars: List<Sidecar>,
)
```

本测试只断言 `series`，没有断言 `sidecars`。原因是测试初始化 `FileSystemScanner(emptyList(), emptyList())`，没有注入 sidecar consumer，因此 sidecar 逻辑不会成为重点。

### 上游调用方：`LibraryContentLifecycle`

主要业务调用方是：

`komga/src/main/kotlin/org/gotson/komga/domain/service/LibraryContentLifecycle.kt`

其中 `scanRootFolder(library: Library, scanDeep: Boolean = false)` 会调用：

```kotlin
fileSystemScanner.scanRootFolder(
  Paths.get(library.root.toURI()),
  library.scanForceModifiedTime,
  library.oneshotsDirectory,
  library.scanCbx,
  library.scanPdf,
  library.scanEpub,
  library.scanDirectoryExclusions,
)
```

这说明测试里的参数不是孤立存在的，它们来自 `Library` 配置：

- `library.root`
- `library.scanForceModifiedTime`
- `library.oneshotsDirectory`
- `library.scanCbx`
- `library.scanPdf`
- `library.scanEpub`
- `library.scanDirectoryExclusions`

扫描结果之后会被 `LibraryContentLifecycle` 用来和数据库里的 `Series`、`Book` 做同步，包括新增、更新、软删除等。也就是说，`FileSystemScannerTest.kt` 验证的是整个库同步流程最底层的“磁盘内容识别”阶段。

### 其他调用方

根据当前片段可见，`scanRootFolder` 还被这些位置使用或测试：

- `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskHandler.kt`
- `komga/src/main/kotlin/org/gotson/komga/domain/service/TransientBookLifecycle.kt`
- `komga/src/test/kotlin/org/gotson/komga/domain/service/LibraryContentLifecycleTest.kt`
- `komga/src/test/kotlin/org/gotson/komga/interfaces/api/rest/SeriesControllerTest.kt`

根据当前片段推断，`TaskHandler` 负责从任务系统触发库扫描，`LibraryContentLifecycleTest` 则进一步测试扫描结果进入生命周期同步后的数据库行为。依据是 `LibraryContentLifecycle` 中已经明确把 `ScanResult` 转换成带 `libraryId` 的 `Series` 和 `Book`，然后进行删除、恢复、更新等处理。

## 运行/调用流程

从测试视角看，一次典型调用流程是：

1. 创建内存文件系统

   测试通过 `Jimfs.newFileSystem(Configuration.unix())` 创建一个临时 Unix 风格文件系统。

2. 准备根目录

   例如：

   `val root = fs.getPath("/root")`

   `Files.createDirectory(root)`

3. 准备文件结构

   可能是根目录下直接放文件：

   `file1.cbz`

   `file2.cbz`

   也可能是子目录：

   `series1/volume1.cbz`

   `series1/volume2.cbz`

   或特殊目录：

   `_oneshots/single.cbz`

4. 调用扫描器

   最常见调用是：

   `scanner.scanRootFolder(root).series`

   带配置的调用包括：

   `scanner.scanRootFolder(root, scanCbx = scanCbz, scanPdf = scanPdf, scanEpub = scanEpub)`

   `scanner.scanRootFolder(root, directoryExclusions = setOf("#recycle"))`

   `scanner.scanRootFolder(root, oneshotsDir = "_oneshots")`

5. 生产代码内部遍历目录树

   `FileSystemScanner` 使用 `Files.walkFileTree`，并开启 `FOLLOW_LINKS`，所以符号链接目录也会被当成可遍历目录。

6. 目录先成为候选 `Series`

   每进入一个目录，`preVisitDirectory` 会构造一个 `Series`：

   - `name = dir.name.ifBlank { dir.pathString }`
   - `url = dir.toUri().toURL()`
   - `fileLastModified = attrs.getUpdatedTime()`

   如果是文件系统根目录 `/`，`dir.name` 可能为空，于是会使用 `dir.pathString`。这对应测试中断言：

   `series.name == "/"`

7. 文件转换成 `Book`

   如果文件扩展名在允许列表里，且文件名不是隐藏文件，就会调用 `pathToBook` 转换成 `Book`：

   - `name = path.nameWithoutExtension`
   - `url = path.toUri().toURL()`
   - `fileLastModified = attrs.getUpdatedTime()`
   - `fileSize = attrs.size()`

8. 目录结束时形成结果

   在 `postVisitDirectory` 中，如果当前目录有书籍文件，就会把当前目录对应的 `Series` 和书籍列表写入 `scannedSeries`。

   这也是为什么“只有子目录有书”的场景下，根目录本身不会出现在结果里：根目录没有直接书籍文件，所以不会被加入最终扫描结果。

9. 返回 `ScanResult`

   测试只取：

   `scanRootFolder(...).series`

   然后断言 `Series.name` 和 `Book.name`。

### 具体测试场景说明

#### 根目录不可用

测试名：

`given unavailable root directory when scanning then throw exception`

它没有创建 `/root`，直接扫描，期望抛出：

`DirectoryNotFoundException`

这对应生产代码：

```kotlin
if (!(Files.isDirectory(root) && Files.isReadable(root)))
  throw DirectoryNotFoundException(...)
```

#### 空根目录

测试名：

`given empty root directory when scanning then return empty list`

只创建 `/root`，不放任何书籍文件，结果 `series` 为空。

这说明扫描器不是“目录即系列”，而是“有书籍文件的目录才进入最终结果”。

#### 根目录只有文件

测试名：

`given root directory with only files when scanning then return 1 series containing those files as books`

目录结构类似：

```text
/root/file1.cbz
/root/file2.cbz
```

扫描结果是一个 `Series`，里面有两个 `Book`：

- `file1`
- `file2`

这说明根目录也可以作为系列目录。

#### 根目录是文件系统根 `/`

测试名：

`given root directory as filesystem root when scanning then return 1 series containing those files as books`

目录结构类似：

```text
/file1.cbz
/file2.cbz
```

结果中的 `Series.name` 是 `/`。

这个测试覆盖了一个边界条件：根路径没有普通目录名，所以生产代码需要用 `dir.pathString` 兜底。

#### 不支持文件类型

测试名：

`given directory with unsupported files when scanning then return a series excluding those files as books`

文件包括：

- `file1.cbz`
- `file2.txt`
- `file3`

结果只包含：

- `file1`

这说明扫描不是“所有文件都是书”，而是严格按扩展名过滤。

#### 按库配置过滤文件类型

参数化测试：

`given directory when scanning excluding some files then return a series excluding those files as books`

它验证：

- `scanCbx = true` 时包含 `cbz`、`cbr`、`zip`、`rar`
- `scanPdf = true` 时包含 `pdf`
- `scanEpub = true` 时包含 `epub`
- 全部关闭时结果为空

这个测试与 `LibraryContentLifecycle` 传入的 `library.scanCbx`、`library.scanPdf`、`library.scanEpub` 直接对应。

#### 子目录变成系列

测试名：

`given directory with sub-directories containing files when scanning then return 1 series per folder containing direct files as books`

结构类似：

```text
/root/series1/volume1.cbz
/root/series1/volume2.cbz
/root/series2/book1.cbz
/root/series2/book2.cbz
```

结果有两个 `Series`：

- `series1`
- `series2`

每个系列包含自己目录下的直接文件。

#### 符号链接根目录

测试名：

`given symlink root directory when scanning then return series and books`

它创建：

```text
/root
/link -> /root
```

然后扫描 `/link`。

由于生产代码使用 `FileVisitOption.FOLLOW_LINKS`，所以符号链接根目录可以正常扫描出 `/root` 下的系列和书籍。

#### 根目录中包含符号链接子目录

测试名：

`given root directory with symlinks when scanning then return series and books`

它为每个真实目录创建一个链接目录：

```text
/root/series1
/root/series1_link -> /root/series1
/root/series2
/root/series2_link -> /root/series2
```

结果中有四个 `Series`：

- `series1`
- `series1_link`
- `series2`
- `series2_link`

这说明扫描器会把符号链接目录当作独立路径处理。即使链接指向同一批文件，扫描结果中仍然会出现链接路径对应的系列。

#### 排除目录

测试名：

`given directory structure with excluded directories when scanning then excluded directories are not returned`

结构中有：

```text
/root/dir1/comic.cbz
/root/dir1/subdir1/comic2.cbz
/root/#recycle/trash.cbz
/root/#recycle/subtrash/trash2.cbz
```

调用时传入：

`directoryExclusions = setOf("#recycle")`

结果只包含：

- `dir1`
- `subdir1`

不包含：

- `#recycle`
- `subtrash`

生产代码使用的是路径字符串包含判断：

`dir.pathString.contains(exclude, true)`

所以它不是只匹配目录名，也不是 glob/regex，而是大小写不敏感的路径片段包含匹配。

#### 隐藏目录

测试名：

`given directory structure with hidden directories when scanning then hidden directories are not returned`

隐藏目录 `.hidden` 及其子目录 `subhidden` 都不会进入结果。

生产代码判断：

`dir.name.startsWith(".")`

并返回：

`FileVisitResult.SKIP_SUBTREE`

所以隐藏目录下的所有内容都会被跳过。

#### 隐藏文件

测试名：

`given directory structure with hidden files when scanning then hidden files are not returned`

例如：

```text
/root/dir1/subdir1/comic2.cbz
/root/dir1/subdir1/.comic2.cbz
```

结果只包含：

- `comic2`

隐藏文件 `.comic2.cbz` 被忽略。

#### 扩展名大小写不敏感

测试名：

`given file with mixed-case extension when scanning then files are returned`

例如：

```text
comic.Cbz
comic2.CBR
```

结果是：

- `comic`
- `comic2`

生产代码里使用：

`file.extension.lowercase()`

因此扩展名大小写不影响识别。

#### one-shot 目录

测试名：

`given oneshot directory when scanning then return a series per file`

结构类似：

```text
/root/normal/comic.cbz
/root/normal/_oneshots/single4.cbz
/root/normal/_oneshots/single5.cbz
/root/_oneshots/single.cbz
/root/_oneshots/single2.cbz
/root/_oneshots/single3.cbz
```

调用：

`scanner.scanRootFolder(root, oneshotsDir = "_oneshots")`

结果有六个系列：

- `normal`
- `single`
- `single2`
- `single3`
- `single4`
- `single5`

其中：

- `_oneshots` 自己不会作为系列名出现
- 每个 one-shot 文件单独成为一个 `Series`
- one-shot 生成的 `Series.oneshot` 是 `true`
- one-shot 生成的 `Book.oneshot` 也是 `true`
- 普通目录 `normal` 仍然是普通系列，`oneshot = false`

生产代码对应逻辑在 `postVisitDirectory`：

```kotlin
if (!oneshotsDir.isNullOrBlank() && dir.pathString.contains(oneshotsDir, true)) {
  books.forEach { book ->
    val series = Series(
      name = book.name,
      url = book.url,
      fileLastModified = book.fileLastModified,
      oneshot = true,
    )
    scannedSeries[series] = listOf(book.copy(oneshot = true))
  }
}
```

注意它也是用路径包含判断，所以只要路径中包含 `_oneshots`，该目录里的书就会按 one-shot 处理。

## 小白阅读顺序

1. 先看测试类开头的 `scanner`

   重点理解这里没有 mock，也没有 Spring 上下文，直接实例化：

   `FileSystemScanner(emptyList(), emptyList())`

   这说明测试对象很纯粹，主要依赖文件系统输入。

2. 再看最简单的三个测试

   推荐顺序：

   - `given unavailable root directory when scanning then throw exception`
   - `given empty root directory when scanning then return empty list`
   - `given root directory with only files when scanning then return 1 series containing those files as books`

   这三个测试能建立基本概念：不可用目录报错、空目录无结果、有文件目录才成为系列。

3. 接着看文件类型过滤

   阅读：

   - `given directory with unsupported files when scanning then return a series excluding those files as books`
   - `given directory when scanning excluding some files then return a series excluding those files as books`
   - `libraryScanFileTypesArguments`

   这里要记住 `scanCbx` 控制的是一组归档格式，不只是 `.cbz`。

4. 再看目录结构测试

   阅读：

   - `given directory with sub-directories containing files when scanning then return 1 series per folder containing direct files as books`

   这一段能理解 Komga 的基本扫描模型：目录是系列，文件是书。

5. 然后看符号链接测试

   阅读：

   - `given symlink root directory when scanning then return series and books`
   - `given root directory with symlinks when scanning then return series and books`

   重点理解符号链接不是被忽略，而是会被跟随扫描。

6. 再看排除和隐藏规则

   阅读：

   - `given directory structure with excluded directories when scanning then excluded directories are not returned`
   - `given directory structure with hidden directories when scanning then hidden directories are not returned`
   - `given directory structure with hidden files when scanning then hidden files are not returned`

   这几段是实际使用中很常见的行为，例如跳过回收站、临时目录、隐藏文件。

7. 最后看 one-shot 规则

   阅读：

   - `given oneshot directory when scanning then return a series per file`

   这是测试文件里业务含义最特殊的一段。普通目录通常是“一个目录一个系列”，但 one-shot 目录是“一个文件一个系列”。

8. 对照生产代码阅读

   完成测试文件后，再打开：

   `komga/src/main/kotlin/org/gotson/komga/domain/service/FileSystemScanner.kt`

   按这个顺序看：

   - `scanRootFolder` 参数
   - `scanForExtensions`
   - 根目录可读性检查
   - `Files.walkFileTree`
   - `preVisitDirectory`
   - `visitFile`
   - `postVisitDirectory`
   - `pathToBook`

   这样能把测试断言和生产实现一一对应起来。

## 常见误区

### 误区一：以为扫描结果包含所有目录

不是。`FileSystemScanner` 虽然会在遍历时把目录登记成候选 `Series`，但最终只有包含书籍文件的目录才会进入 `ScanResult.series`。

所以空目录不会出现在结果中。

### 误区二：以为根目录不会成为系列

会。只要根目录下直接有支持的书籍文件，根目录本身就会成为一个 `Series`。

测试中 `/root/file1.cbz`、`/root/file2.cbz` 会生成一个系列；如果根目录就是 `/`，系列名会是 `/`。

### 误区三：以为 `.zip`、`.rar` 不属于漫画扫描

在这里它们属于 `scanCbx` 控制的格式集合。生产代码里：

`scanCbx = true`

会加入：

- `cbz`
- `zip`
- `cbr`
- `rar`

所以 `scanCbx` 不只是扫描 `.cbz`。

### 误区四：把 `scanCbz` 和 `scanCbx` 混成一个概念

测试方法参数叫 `scanCbz`，生产方法参数叫 `scanCbx`。

从行为看，生产参数 `scanCbx` 更准确，因为它控制的是 CBX 类压缩漫画格式集合。阅读测试时不要误以为它只控制 `.cbz`。

### 误区五：以为排除目录是精确匹配目录名

不是。生产代码使用：

`dir.pathString.contains(exclude, true)`

这意味着排除规则是“路径字符串包含”，并且大小写不敏感。

例如 `directoryExclusions = setOf("#recycle")` 会跳过路径中包含 `#recycle` 的目录子树。根据当前片段推断，如果某个更深层路径名称包含同样片段，也会被跳过，依据是它匹配的是完整 `pathString`。

### 误区六：以为隐藏目录和隐藏文件规则一样

它们结果上都是被忽略，但处理位置不同：

- 隐藏目录在 `preVisitDirectory` 阶段被 `SKIP_SUBTREE`
- 隐藏文件在 `visitFile` 阶段被过滤

区别是隐藏目录下的全部内容都不会继续访问，而隐藏文件只是单个文件不入结果。

### 误区七：以为符号链接会被去重

不会从这些测试看出有去重。生产代码使用 `FileVisitOption.FOLLOW_LINKS`，测试明确断言真实目录和链接目录都会各自成为系列：

- `series1`
- `series1_link`
- `series2`
- `series2_link`

因此如果库目录里有指向已有目录的符号链接，扫描结果可能出现重复内容但路径不同的系列。

### 误区八：以为 one-shot 目录本身会成为一个系列

不会。`_oneshots` 目录里的每个文件会单独成为一个系列，系列名取自书籍文件名。

例如：

`_oneshots/single.cbz`

生成的不是系列 `_oneshots`，而是系列 `single`，并且 `Series.oneshot = true`、`Book.oneshot = true`。

### 误区九：以为测试覆盖了 sidecar 行为

没有。虽然 `FileSystemScanner` 生产代码包含 sidecar 扫描逻辑，但本测试传入的是：

`FileSystemScanner(emptyList(), emptyList())`

因此 sidecar consumer 为空。本文件只验证目录和书籍扫描，不验证 `Sidecar` 匹配、收集或保存。

### 误区十：以为这个测试会验证数据库同步

不会。这个测试只验证 `FileSystemScanner.scanRootFolder` 返回的内存模型。

数据库层面的新增、更新、删除、恢复等行为属于 `LibraryContentLifecycle` 及其测试，例如：

`komga/src/test/kotlin/org/gotson/komga/domain/service/LibraryContentLifecycleTest.kt`

本文件处在更底层，只负责确认“磁盘文件结构被识别成什么扫描结果”。
