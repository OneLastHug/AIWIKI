# 文件：komga/src/main/kotlin/org/gotson/komga/domain/service/BookConverter.kt

## 它负责什么

`BookConverter.kt` 定义了领域服务 `BookConverter`，它主要负责两类“书籍文件维护”工作：

1. **把可转换的压缩漫画文件转换成 CBZ**
   - 当前只把 `MediaType.RAR_4`、`MediaType.RAR_5` 视为可转换类型。
   - 转换结果是 `.cbz` 文件，本质上是 ZIP 格式容器。
   - 转换完成后会删除旧文件、更新 `Book` 和 `Media` 数据、记录历史事件，并发布 `DomainEvent.BookUpdated`。

2. **修复书籍文件扩展名**
   - 当数据库中识别出的 `mediaType` 与文件扩展名不匹配时，将文件重命名为正确扩展名。
   - 支持的媒体类型映射包括 `RAR_4`、`RAR_5`、`ZIP`、`PDF`、`EPUB`。
   - 例如媒体类型识别为 ZIP，但文件扩展名不是 `zip` 或对应扩展名时，会尝试重命名。

可以把它理解为 Komga 中“根据实际媒体格式修正磁盘文件”的领域服务。它不负责扫描整个书库，也不负责用户接口，而是被后台任务系统调用，执行具体的单本书转换或修复动作。

## 关键组成

文件顶部的常量：

```kotlin
const val CBZ_EXTENSION = "cbz"
```

表示转换后的目标扩展名固定为 `cbz`。

`BookConverter` 是一个 Spring `@Service`，构造函数注入了多个依赖：

- `BookAnalyzer`：分析书籍文件，读取文件内容，生成 `Media` 信息。
- `FileSystemScanner`：扫描磁盘上的单个文件，得到 `Book` 基础信息。
- `BookRepository`：读写 `Book` 记录。
- `MediaRepository`：读写 `Media` 记录。
- `LibraryRepository`：读取书库配置，例如是否开启转换或扩展名修复。
- `TransactionTemplate`：在事务中更新 `Book` 和 `Media`。
- `ApplicationEventPublisher`：发布领域事件。
- `HistoricalEventRepository`：记录历史事件，例如文件删除、转换完成。

内部有三个重要字段：

```kotlin
private val convertibleTypes = listOf(MediaType.RAR_4.type, MediaType.RAR_5.type)
```

表示只有 RAR4 和 RAR5 可以被转换成 CBZ。

```kotlin
private val mediaTypeToExtension =
  listOf(MediaType.RAR_4, MediaType.RAR_5, MediaType.ZIP, MediaType.PDF, MediaType.EPUB)
    .associate { it.type to it.fileExtension }
```

表示媒体类型到正确文件扩展名的映射，用于扩展名修复。

```kotlin
private val failedConversions = mutableListOf<String>()
private val skippedRepairs = mutableListOf<String>()
```

这两个列表用于当前服务实例内的去重：
- `failedConversions`：某本书转换失败后，后续不再重复转换。
- `skippedRepairs`：某本书扩展名修复被跳过后，后续不再重复处理。

注意它们是内存状态，不是数据库持久状态。应用重启后这些记录会消失。

主要公开方法有四个：

```kotlin
fun getConvertibleBooks(library: Library): Collection<Book>
fun convertToCbz(book: Book)
fun getMismatchedExtensionBooks(library: Library): Collection<Book>
fun repairExtension(book: Book)
```

其中 `getConvertibleBooks` 和 `getMismatchedExtensionBooks` 用于批量找候选书籍；`convertToCbz` 和 `repairExtension` 用于处理单本书。

## 上下游关系

上游主要是后台任务系统。

在 `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskHandler.kt` 中，`TaskHandler` 注入了 `BookConverter`，并在任务分发时调用它：

- `Task.FindBooksToConvert`：
  - 先根据 `libraryId` 找到 `Library`。
  - 调用 `bookConverter.getConvertibleBooks(library)` 找出候选书籍。
  - 再通过 `taskEmitter.convertBookToCbz(...)` 发出单本转换任务。

- `Task.ConvertBook`：
  - 根据 `bookId` 找到 `Book`。
  - 调用 `bookConverter.convertToCbz(book)` 执行实际转换。

- `Task.RepairExtension`：
  - 根据 `bookId` 找到 `Book`。
  - 调用 `bookConverter.repairExtension(book)` 执行扩展名修复。

在 `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskEmitter.kt` 中：

- `findBooksToConvert(library)` 会提交 `Task.FindBooksToConvert`。
- `convertBookToCbz(books)` 会把多个 `Book` 转成多个 `Task.ConvertBook`。
- `repairExtensions(library)` 会在 `library.repairExtensions` 开启时调用 `bookConverter.getMismatchedExtensionBooks(library)`，再为每本书提交 `Task.RepairExtension`。

在 `komga/src/main/kotlin/org/gotson/komga/domain/service/LibraryLifecycle.kt` 中，当书库配置发生变化时：

- 如果 `repairExtensions` 从关闭变为开启，会触发 `taskEmitter.repairExtensions(toUpdate, LOWEST_PRIORITY)`。
- 如果 `convertToCbz` 从关闭变为开启，会触发 `taskEmitter.findBooksToConvert(toUpdate, LOWEST_PRIORITY)`。

另外，在扫描书库任务中，`TaskHandler` 也会在扫描后触发：

```kotlin
taskEmitter.repairExtensions(library, LOW_PRIORITY)
taskEmitter.findBooksToConvert(library, LOWEST_PRIORITY)
```

所以下游是：

- 磁盘文件系统：创建 `.cbz`、删除旧文件、重命名文件。
- `BookRepository`：更新书籍路径、文件信息等。
- `MediaRepository`：更新媒体分析结果。
- `HistoricalEventRepository`：插入历史事件。
- Spring 事件系统：发布 `DomainEvent.BookUpdated`。
- 后续监听 `BookUpdated` 的组件可能继续刷新索引、界面或其他派生数据；根据当前片段推断，依据是该服务发布了领域事件，但这里没有继续展开事件监听方。

## 运行/调用流程

### 1. 查找可转换书籍

`getConvertibleBooks(library)` 的逻辑很短：

```kotlin
if (library.convertToCbz) {
  bookRepository.findAllByLibraryIdAndMediaTypes(library.id, convertibleTypes)
} else {
  emptyList()
}
```

也就是说，只有书库开启了 `convertToCbz`，才会查询该书库下媒体类型为 RAR4 或 RAR5 的书籍。

这里并不执行转换，只是返回候选 `Book` 集合。真正的转换由后续 `Task.ConvertBook` 调用 `convertToCbz(book)` 完成。

### 2. 转换单本书为 CBZ

`convertToCbz(book)` 的流程比较严谨，可以分为几个阶段。

第一阶段是前置校验：

1. 重新读取书库配置。
   - 如果 `library.convertToCbz` 已经关闭，就直接跳过。
   - 这是为了防止任务排队期间用户修改了配置。

2. 检查这本书是否已经转换失败过。
   - 如果 `failedConversions` 包含当前 `book.id`，直接跳过。

3. 重新扫描磁盘文件。
   - 使用 `fileSystemScanner.scanFile(book.path)`。
   - 如果文件不存在，抛出 `FileNotFoundException`。
   - 如果磁盘上的 `fileLastModified` 与数据库里的 `book.fileLastModified` 不一致，说明文件已经变化，跳过转换。

4. 读取当前 `Media`。
   - 如果 `media.mediaType` 不是 RAR4 或 RAR5，抛出 `MediaUnsupportedException`。
   - 如果 `media.status != Media.Status.READY`，抛出 `MediaNotReadyException`。

第二阶段是创建 CBZ 文件：

1. 生成目标文件名：
   - 原文件名去掉扩展名。
   - 加上 `.cbz`。
   - 目标路径与原文件在同一目录。

2. 如果目标文件已经存在，抛出 `FileAlreadyExistsException`，避免覆盖用户文件。

3. 使用 `ZipArchiveOutputStream` 创建 ZIP。
   - 压缩方法设置为 `DEFLATED`。
   - 压缩等级设置为 `Deflater.NO_COMPRESSION`，也就是不真正压缩，只封装为 ZIP/CBZ。
   - 写入内容来自：
     - `media.pages.map { it.fileName }`
     - `media.files.map { it.fileName }`
   - 两者通过 `union` 合并，避免重复条目。
   - 每个条目的内容通过 `bookAnalyzer.getFileContent(BookWithMedia(book, media), entry)` 读取。

这说明转换不是简单地复制压缩包，而是从原媒体中逐个读取页面和附加文件，再重新写入新的 ZIP/CBZ 容器。

第三阶段是验证新文件：

1. 用 `fileSystemScanner.scanFile(destinationPath)` 扫描新 CBZ。
2. 将扫描出的 `Book` 补回原来的：
   - `id`
   - `seriesId`
   - `libraryId`

3. 调用 `bookAnalyzer.analyze(convertedBook, analyzeDimensions)` 分析新文件。

4. 检查转换结果：
   - 新媒体状态必须是 `READY`。
   - 新媒体类型必须是 `MediaType.ZIP.type`。
   - 新文件必须包含原文件所有页面。
   - 新文件必须包含原文件所有附加文件。

页面和附加文件的比较使用了 `FilenameUtils.getName(...)`，也就是只比较文件名部分，而不是完整路径。页面还会同时比较 `mediaType`。

如果这些检查失败，会：

```kotlin
destinationPath.deleteIfExists()
failedConversions += book.id
throw e
```

也就是删除失败产物、记录失败书籍、继续抛出异常。

第四阶段是替换旧文件和更新数据库：

1. 删除旧文件：
   - 如果删除成功，记录 `HistoricalEvent.BookFileDeleted`。
   - 事件原因是 `"File was deleted after conversion to CBZ"`。

2. 恢复页面 hash：
   - `convertedMedia.copy(pages = convertedMedia.pages.restoreHashFrom(media.pages))`
   - 这表示新分析出的页面对象会从旧页面中继承 hash 信息。
   - 这样可以避免转换后丢失已有页面 hash。

3. 在事务中更新：
   - `bookRepository.update(convertedBook)`
   - `mediaRepository.update(mediaWithHashes)`

4. 记录转换历史：
   - `HistoricalEvent.BookConverted(convertedBook, book)`

5. 发布领域事件：
   - `DomainEvent.BookUpdated(convertedBook)`

### 3. 查找扩展名不匹配书籍

`getMismatchedExtensionBooks(library)` 会遍历 `mediaTypeToExtension`：

```kotlin
mediaTypeToExtension.flatMap { (mediaType, extension) ->
  bookRepository.findAllByLibraryIdAndMismatchedExtension(library.id, mediaType, extension)
}
```

也就是对每种支持的媒体类型，查找该书库中“实际媒体类型是这个类型，但文件扩展名不是预期扩展名”的书籍。

它只查候选，不修复文件。

### 4. 修复扩展名

`repairExtension(book)` 的流程如下：

1. 重新读取书库配置。
   - 如果 `repairExtensions` 已关闭，跳过。
   - 同样是防止任务排队期间配置变化。

2. 检查是否已经跳过过。
   - 如果 `skippedRepairs` 包含当前 `book.id`，直接跳过。

3. 检查文件是否存在。
   - 不存在则抛出 `FileNotFoundException`。

4. 读取 `Media`。
   - 如果媒体类型不在 `mediaTypeToExtension.keys` 里，抛出 `MediaUnsupportedException`。

5. 特殊处理 EPUB：
   - 如果文件扩展名是 `epub`，但媒体类型识别为 ZIP，则跳过。
   - 原因是 EPUB 本身就是 ZIP 容器格式，不能因为识别为 ZIP 就把 `.epub` 改成 `.zip`。
   - 这里会把书籍 ID 加入 `skippedRepairs`。

6. 如果当前扩展名已经正确：
   - 记录日志。
   - 加入 `skippedRepairs`。

这里有一个阅读时需要注意的点：代码在判断“已经正确”后，并没有 `return`。因此从控制流上看，即使 `correctExtension == actualExtension`，后面仍然会继续生成目标路径并尝试处理。根据当前片段推断，这可能依赖调用方只传入“不匹配”的书籍，或者这里存在一个潜在的遗漏返回点。依据是 `getMismatchedExtensionBooks` 的确只会找不匹配项，但 `repairExtension(book)` 本身作为公开方法并没有强制保证入参一定不匹配。

7. 生成目标路径。
   - 文件名保持 `nameWithoutExtension` 不变。
   - 扩展名改为 `correctExtension`。

8. 如果目标文件已经存在，抛出 `FileAlreadyExistsException`。

9. 使用 `book.path.moveTo(destinationPath)` 重命名文件。

10. 重新扫描新路径。
    - 保留原来的 `id`、`seriesId`、`libraryId`。

11. 更新 `BookRepository`。
    - 这里只更新 `Book`，没有重新分析并更新 `Media`。
    - 因为修复扩展名不改变文件内容，只改变路径和文件名信息。

## 小白阅读顺序

建议按下面顺序读：

1. 先看类声明和构造函数：
   - 理解 `BookConverter` 是一个 `@Service`。
   - 记住它依赖仓库、扫描器、分析器、事务和事件发布器。

2. 再看这三个字段：
   - `convertibleTypes`
   - `mediaTypeToExtension`
   - `failedConversions` / `skippedRepairs`

   这能帮助你先理解“它支持哪些类型”和“它如何避免重复处理”。

3. 读 `getConvertibleBooks(library)`：
   - 这是最简单的入口。
   - 明白转换功能受 `library.convertToCbz` 控制。

4. 重点读 `convertToCbz(book)`：
   - 建议分成“校验、写新文件、验证新文件、更新数据库和事件”四段看。
   - 不要一口气把整个方法当成一段逻辑读。

5. 再读 `getMismatchedExtensionBooks(library)`：
   - 理解它只是查候选。

6. 最后读 `repairExtension(book)`：
   - 注意 EPUB 特例。
   - 注意它是重命名，不是重新编码或重新分析媒体内容。

7. 辅助阅读调用方：
   - `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskHandler.kt`
   - `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskEmitter.kt`
   - `komga/src/main/kotlin/org/gotson/komga/domain/service/LibraryLifecycle.kt`

   这三个文件能解释 `BookConverter` 为什么通常由后台任务触发，而不是由 REST Controller 直接调用。

## 常见误区

1. **误以为 CBZ 转换支持所有格式**

   实际上 `convertibleTypes` 只包含 `MediaType.RAR_4.type` 和 `MediaType.RAR_5.type`。ZIP、PDF、EPUB 不会被 `convertToCbz` 当作可转换来源。

2. **误以为转换是简单改扩展名**

   `convertToCbz` 不是把 `.rar` 改成 `.cbz`。它会读取原归档内的页面和文件，再写入新的 ZIP/CBZ 文件，并重新扫描、重新分析、校验内容完整性。

3. **误以为 CBZ 一定会压缩图片**

   代码设置了 `Deflater.NO_COMPRESSION`。也就是说新 CBZ 主要是重新封装，不追求压缩体积。漫画图片通常本来就是 JPEG/PNG/WebP 等已压缩格式，继续压缩收益也有限。

4. **误以为转换后旧文件一定还在**

   转换验证成功后，代码会删除旧文件：

   ```kotlin
   book.path.deleteIfExists()
   ```

   删除成功时还会记录 `HistoricalEvent.BookFileDeleted`。

5. **误以为转换失败会留下半成品**

   如果新文件分析失败、类型不是 ZIP、页面缺失或附加文件缺失，会删除目标 CBZ，并把书籍 ID 加入 `failedConversions`。

6. **误以为 `failedConversions` 是永久记录**

   它只是 `BookConverter` 实例里的 `mutableListOf<String>()`。应用重启后就不会保留。它的作用更像是避免同一次运行中反复处理同一本失败书。

7. **误以为扩展名修复会修改媒体内容**

   `repairExtension` 只调用 `moveTo(destinationPath)` 重命名文件，然后扫描新路径并更新 `Book`。它不重写文件内容，也不重新生成 `Media`。

8. **误以为 EPUB 被识别为 ZIP 就应该改成 `.zip`**

   代码专门处理了这种情况：

   ```kotlin
   if (book.path.extension.lowercase() == "epub" && media.mediaType == MediaType.ZIP.type)
   ```

   EPUB 本身是 ZIP 容器，所以 `.epub` 被识别为 ZIP 时不应该被修复成 `.zip`。

9. **误以为方法开始时的库配置检查多余**

   后台任务可能已经排队很久。用户可能在任务执行前关闭了 `convertToCbz` 或 `repairExtensions`。因此 `convertToCbz` 和 `repairExtension` 都会重新读取 `Library` 配置，避免执行过期任务。

10. **误以为 `BookConverter` 负责调度任务**

   它不负责调度。调度由 `TaskEmitter` 和 `TaskHandler` 完成。`BookConverter` 只提供查候选和执行单本处理的领域能力。
