# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/Exceptions.kt

## 它负责什么

`Exceptions.kt` 是 Komga 领域层的异常类型集中定义文件。它位于 `org.gotson.komga.domain.model` 包下，作用不是实现业务逻辑，而是为业务服务、基础设施解析器、REST API 控制器之间提供一组“可识别的失败语义”。

这个文件里的异常大致分两类：

一类是普通 `Exception`，只表达“发生了某种业务失败”，例如 `MediaNotReadyException`、`NoThumbnailFoundException`、`BookConversionException`、`EntryNotFoundException`、`ConfigurationException`。

另一类继承自 `CodedException`，除了 message 以外还携带一个 `code: String`。这些 code 常见形式是 `ERR_1016`、`ERR_1034` 等，用来让调用方或前端获得比自然语言 message 更稳定的错误标识。例如导入文件失败、路径冲突、RAR 加密不支持、ComicRack 阅读列表格式错误等场景。

因此，这个文件可以理解为领域层和接口层之间的“错误词汇表”：服务层抛出明确异常，接口层再把它们转换成 HTTP 状态码、错误 reason 或日志信息。

## 关键组成

`CodedException` 是本文件最核心的基类：

```kotlin
open class CodedException : Exception {
  val code: String
}
```

它提供两个构造方式：

- `constructor(cause: Throwable, code: String)`：用已有异常作为 cause 包装起来，同时附加 code。
- `constructor(message: String, code: String)`：直接用 message 创建异常，同时附加 code。

`fun Exception.withCode(code: String)` 是一个 Kotlin 扩展函数，用来把任意 `Exception` 包装成 `CodedException`。例如 `BookImporter` 中会把 `FileNotFoundException`、`IllegalArgumentException`、`FileAlreadyExistsException`、`IllegalStateException` 通过 `.withCode("ERR_1021")` 变成带稳定错误码的异常。这样做的好处是：不必为每一种 Java/Kotlin 标准异常都重新定义一个领域异常类，但仍然能向上游传递业务错误码。

带 code 的具体异常包括：

- `MediaUnsupportedException`：媒体格式或媒体能力不支持。调用方包括 EPUB/RAR 解析、页面提取、转换/修复等逻辑。
- `ImageConversionException`：图片转换失败或格式不支持，常由图像转换相关流程抛出或向 API 层传播。
- `DirectoryNotFoundException`：目录不存在、不可读或不是目录。`FileSystemScanner`、`LibraryLifecycle` 会使用它。
- `DuplicateNameException`：名称重复，例如 library、collection、read list、API key comment。
- `PathContainedInPath`：路径互相包含导致冲突，例如新 library 路径是已有 library 的父/子路径，或导入/扫描路径落在已有 library 内。
- `UserEmailAlreadyExistsException`：用户邮箱重复。
- `ComicRackListException`：ComicRack 阅读列表解析或校验失败，通常带 `ERR_1015`、`ERR_1029`、`ERR_1030`、`ERR_1031` 等 code。

普通异常包括：

- `MediaNotReadyException`：媒体分析结果尚未 ready，无法取页面、生成缩略图、转换等。
- `NoThumbnailFoundException`：没有找到可生成缩略图的封面或 poster。
- `BookConversionException`：书籍转换后的结果校验失败，比如转换文件不能分析、不是 zip、缺少页面或文件。
- `EntryNotFoundException`：压缩包内指定 entry 不存在，`ZipFileUtils` 会抛出。
- `ConfigurationException`：启动或配置检查失败，例如文件存储配置无效。

需要注意的是，`MediaNotReadyException` 和 `NoThumbnailFoundException` 没有 message，也不带 code。它们更像内部流程控制信号，由上层捕获后转换成固定文案或忽略某些失败。

## 上下游关系

上游主要是 domain service 和 infrastructure 组件，它们在检测到业务前置条件不满足、文件结构异常、媒体能力不支持时抛出这些异常。

典型上游包括：

- `komga/src/main/kotlin/org/gotson/komga/domain/service/BookAnalyzer.kt`：当媒体未分析完成时抛 `MediaNotReadyException`；找不到封面时抛 `NoThumbnailFoundException`；请求 EPUB 不支持的页面内容、PDF 以外的 raw page、非 PDF synthetic pages 时抛 `MediaUnsupportedException`。
- `komga/src/main/kotlin/org/gotson/komga/domain/service/BookConverter.kt`、`komga/src/main/kotlin/org/gotson/komga/domain/service/BookPageEditor.kt`：媒体类型不在可转换集合时抛 `MediaUnsupportedException`；媒体状态不是 `READY` 时抛 `MediaNotReadyException`；转换后文件不符合预期时抛 `BookConversionException`。
- `komga/src/main/kotlin/org/gotson/komga/domain/service/LibraryLifecycle.kt`：创建或更新 library 时校验目录、名称、路径包含关系，分别抛 `DirectoryNotFoundException`、`DuplicateNameException`、`PathContainedInPath`。
- `komga/src/main/kotlin/org/gotson/komga/domain/service/BookImporter.kt`：导入前后校验失败时使用 `.withCode(...)` 包装标准异常，或直接抛 `PathContainedInPath`。
- `komga/src/main/kotlin/org/gotson/komga/domain/service/KomgaUserLifecycle.kt`：邮箱重复抛 `UserEmailAlreadyExistsException`，API key comment 重复抛带 code 的 `DuplicateNameException`。
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/mediacontainer/divina/RarExtractor.kt`：加密 RAR、多卷 RAR 抛 `MediaUnsupportedException`，并带 `ERR_1002`、`ERR_1004`。
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/metadata/comicrack/ReadListProvider.kt`：ComicRack 阅读列表解析和字段校验失败抛 `ComicRackListException`。
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/configuration/ConfigurationChecker.kt`：配置不满足运行要求时抛 `ConfigurationException`。

下游主要是 interfaces 层的 API Controller。它们通常不会把领域异常原样暴露，而是捕获后转成 `ResponseStatusException`：

- `CommonBookController` 捕获 `ImageConversionException`、`MediaUnsupportedException`、`MediaNotReadyException`、`EntryNotFoundException`，分别转换为 `404 NOT_FOUND` 或 `400 BAD_REQUEST` 等。
- `LibraryController` 捕获 `DirectoryNotFoundException`、`DuplicateNameException`、`PathContainedInPath`，统一转换为 `400 BAD_REQUEST`。
- `ReadListController`、`SeriesCollectionController`、`UserController`、`TransientBooksController` 会针对 `DuplicateNameException`、`UserEmailAlreadyExistsException`、`CodedException` 做接口级错误转换。
- `BookImporter` 内部还会判断 `e is CodedException`，优先使用 `e.code` 作为失败消息或日志标识。

根据当前片段推断，项目没有把本文件里的所有领域异常统一交给一个全局 `@ControllerAdvice` 处理；`ErrorHandlingControllerAdvice` 更偏向 Bean Validation 相关异常。这里的领域异常多数由具体 Controller 就地捕获并映射 HTTP 语义。

## 运行/调用流程

以“获取书籍页面”为例，流程大致是：

1. API 层 `CommonBookController` 接收获取页面请求。
2. Controller 查找 book、检查内容限制，然后调用 `BookLifecycle` 或下游分析服务。
3. `BookAnalyzer` 检查 `book.media.status`。如果媒体还不是 `Media.Status.READY`，抛出 `MediaNotReadyException`。
4. 如果请求的媒体 profile 不支持对应操作，例如 EPUB profile 不支持某种 page content，抛出 `MediaUnsupportedException`。
5. 异常向上冒泡回 `CommonBookController`。
6. Controller 捕获异常并转换：
   - `MediaNotReadyException` 通常变成 `404 NOT_FOUND`，reason 类似 `"Book analysis failed"`。
   - `MediaUnsupportedException` 通常变成 `400 BAD_REQUEST`，reason 使用异常 message。
   - `ImageConversionException` 可能变成 `404 NOT_FOUND` 并返回转换失败信息。

以“创建 library”为例：

1. `LibraryController` 接收创建请求并构造 domain model。
2. 调用 `LibraryLifecycle`。
3. `LibraryLifecycle` 校验 library root 是否为目录；失败抛 `DirectoryNotFoundException`。
4. 校验名称是否重复；失败抛 `DuplicateNameException`。
5. 校验路径是否和已有 library 互为父子路径；失败抛 `PathContainedInPath`。
6. `LibraryController` 捕获这三种异常并转换为 `400 BAD_REQUEST`，把异常 message 作为 reason 返回。

以“导入书籍”为例：

1. `BookImporter` 检查源文件是否存在。
2. 如果不存在，抛 `FileNotFoundException(...).withCode("ERR_1018")`。
3. `.withCode` 会返回 `CodedException`，保留原异常作为 cause，并附加 `ERR_1018`。
4. 上层或同服务内部 catch 时可以判断 `e is CodedException`，优先取 `e.code`，从而得到稳定错误码，而不是依赖 message 文案。

## 小白阅读顺序

建议先从 `CodedException` 看起。理解它和普通 `Exception` 的区别：普通异常只有 message/cause；`CodedException` 多了一个 `code` 字段。

第二步看 `withCode`。这是 Kotlin 扩展函数，写法像给所有 `Exception` 临时增加了一个方法。看到 `someException.withCode("ERR_1021")` 时，要理解它不是修改原异常，而是创建一个新的 `CodedException` 包住原异常。

第三步按业务域给异常分组：

- 媒体读取/分析：`MediaNotReadyException`、`NoThumbnailFoundException`、`MediaUnsupportedException`、`ImageConversionException`、`EntryNotFoundException`
- 文件/路径/library：`DirectoryNotFoundException`、`PathContainedInPath`
- 唯一性校验：`DuplicateNameException`、`UserEmailAlreadyExistsException`
- 转换/导入/外部格式：`BookConversionException`、`ComicRackListException`
- 启动配置：`ConfigurationException`

第四步去调用方看“谁抛、谁接”。优先看 `BookAnalyzer.kt`、`BookConverter.kt`、`LibraryLifecycle.kt`、`BookImporter.kt` 这些上游，再看 `CommonBookController.kt`、`LibraryController.kt`、`ReadListController.kt`、`TransientBooksController.kt` 这些下游。

第五步观察 HTTP 映射。不要只看异常类名判断用户最终看到什么错误；最终 API 状态码和 reason 往往由 Controller 的 `catch` 块决定。

## 常见误区

不要以为所有异常都有错误码。只有继承 `CodedException` 的类，或通过 `.withCode(...)` 包装出来的异常，才有 `code` 字段。`MediaNotReadyException`、`NoThumbnailFoundException`、`BookConversionException` 等没有 code。

不要以为 `code` 一定非空。很多带 code 的异常构造函数默认 `code: String = ""`，只有部分调用方显式传入 `ERR_xxxx`。因此使用 `e.code` 时要考虑空字符串。

不要把 `CodedException(cause, code)` 理解成会自动复制 cause 的 message。它调用的是 `Exception(cause)` 构造；在 Java/Kotlin 异常体系里，message 可能来自 cause 的字符串形式，但业务上真正稳定的是 `code`，不是 message。

不要以为这些异常都由全局异常处理器统一转换。根据当前片段，领域异常大多由具体 Controller 捕获，并手动转换成 `ResponseStatusException`。所以新增异常时，如果没有在接口层捕获，可能会变成默认的 500 或非预期响应。

不要把 `MediaNotReadyException` 理解成文件不存在。它更准确的含义是“媒体分析状态不满足当前操作”，例如书籍还未分析完成、media profile 为空、页面列表不可用。文件不存在在接口层还可能由 `NoSuchFileException`、`FileNotFoundException` 等另行处理。

不要把 `BookConversionException` 和 `MediaUnsupportedException` 混用。前者表示转换流程已经进行到结果校验阶段，但产物不符合预期；后者表示一开始就不支持该媒体类型或操作能力。

不要以为异常类名 `PathContainedInPath` 是普通语法错误。它表达的是路径包含关系冲突：新路径不能是已有 library 的子路径，也不能把已有 library 包进去；导入或临时扫描路径也不能落在已有 library 内。
