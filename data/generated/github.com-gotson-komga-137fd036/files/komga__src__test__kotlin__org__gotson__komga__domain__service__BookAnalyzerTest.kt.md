# 文件：komga/src/test/kotlin/org/gotson/komga/domain/service/BookAnalyzerTest.kt

## 它负责什么

`BookAnalyzerTest.kt` 是 `BookAnalyzer` 的集成式单元测试文件，用来验证 Komga 在“分析一本书文件”时能否正确识别媒体类型、生成 `Media` 结构、处理异常降级，以及执行页面哈希逻辑。

它测试的不是 HTTP API，也不是数据库持久化，而是领域服务 `org.gotson.komga.domain.service.BookAnalyzer` 的核心行为。`BookAnalyzer` 负责把一个 `Book` 的实际文件路径转换成可被系统使用的 `Media` 信息，例如：

- 文件媒体类型：`application/zip`、`application/epub+zip`、`application/x-rar-compressed; version=4` 等。
- 媒体状态：`READY`、`ERROR`、`UNSUPPORTED`。
- 页面列表：`Media.pages`。
- EPUB 扩展信息：目录、landmarks、page list、positions 等。
- 页面哈希：`BookPage.fileHash`。

这个测试文件使用 Spring Boot 测试上下文运行，因此它会拿到真实的 `BookAnalyzer` Bean，同时通过 `@SpykBean` 对 `BookAnalyzer` 和 `EpubExtractor` 做局部 mock/spy。这样既能复用真实组件，又能模拟某些提取步骤抛异常，验证 `BookAnalyzer` 的容错逻辑。

## 关键组成

文件顶部的包名是：

`org.gotson.komga.domain.service`

这说明它与被测类 `BookAnalyzer` 位于同一个 Kotlin package，测试可以直接访问该包内公开的服务行为。

主要 import 可以分成几组理解：

- 测试框架：`org.junit.jupiter.api.Test`、`Nested`、`ParameterizedTest`、`ValueSource`、`MethodSource`。
- 断言库：`org.assertj.core.api.Assertions.assertThat`。
- MockK/Spring MockK：`SpykBean`、`clearAllMocks`、`every`、`verify`。
- 领域模型：`Book`、`BookPage`、`BookWithMedia`、`Media`、`MediaExtensionEpub`、`makeBook`。
- 配置与基础设施：`KomgaProperties`、`EpubExtractor`。
- 测试资源读取：`ClassPathResource`。
- Kotlin Path 工具：`extension`、`inputStream`、`listDirectoryEntries`、`name`、`toPath`。

测试类声明为：

`@SpringBootTest class BookAnalyzerTest(@Autowired private val komgaProperties: KomgaProperties)`

这表示测试会启动 Spring Boot 测试上下文，并注入 `KomgaProperties`。其中 `komgaProperties.pageHashing` 被用于验证“页面哈希只处理开头和结尾若干页”的规则，而不是在测试里硬编码数字。

两个关键 spy Bean 是：

- `bookAnalyzer: BookAnalyzer`：被测对象本身。测试中会 spy 它的部分方法，例如 `getPageContent`、`hashPage`。
- `epubExtractor: EpubExtractor`：EPUB 提取器。测试中会让某些 EPUB 子步骤抛异常，以验证 `BookAnalyzer.analyzeEpub` 是否把错误记录到 `Media.comment`，同时保持整体 `READY`。

`@AfterEach fun afterEach()` 调用 `clearAllMocks()`，确保每个测试之间的 mock 行为不会互相污染。

文件内部按语义分成三个 `@Nested` 测试组。

`ArchiveFormats` 测试常见归档格式：

- RAR4 普通包和 solid 包应被识别为 `application/x-rar-compressed; version=4`，状态为 `READY`，并能得到 3 页。
- RAR4 加密包应为 `UNSUPPORTED`。
- RAR5 普通、solid、加密包都应为 `UNSUPPORTED`。
- 7z 普通和加密包都应为 `UNSUPPORTED`。
- 多种 ZIP 压缩方式，例如 bzip2、copy、deflate64、lzma、ppmd，应识别为 `application/zip`，状态为 `READY`。
- 加密 ZIP 应为 `ERROR`。
- EPUB 测试归档应识别为 `application/epub+zip` 且 `READY`。

这里的测试资源来自 classpath，例如 `archives/rar4.rar`、`archives/zip.zip`、`archives/epub3.epub`。

`Epub` 测试 EPUB 相关容错：

- `zip-as-epub.epub` 是扩展名为 `.epub` 但内容不是合法 EPUB 的文件。测试期望它被识别成 `application/zip`，状态为 `ERROR`，页面数为 0。
- 正常 EPUB `epub/The Incomplete Theft - Ralph Burke.epub` 应为 `application/epub+zip`、`READY`，且 `comment` 为空。
- 当 `epubExtractor.getToc` 抛异常时，整体仍为 `READY`，但 `comment` 包含 `ERR_1035`，`MediaExtensionEpub.toc` 为空。
- 当 `getLandmarks` 抛异常时，`comment` 包含 `ERR_1036`，`landmarks` 为空。
- 当 `getPageList` 抛异常时，`comment` 包含 `ERR_1037`，`pageList` 为空。
- 当 `getDivinaPages` 抛异常时，`comment` 包含 `ERR_1038`，`pages` 为空。
- 当 `computePositions` 抛异常时，`comment` 包含 `ERR_1039`，`positions` 为空。

这些测试对应 `BookAnalyzer.analyzeEpub` 里的设计：EPUB 的某些附加结构提取失败不应该让整本书分析失败，而是记录错误码并返回一个尽可能可用的 `Media`。

`PageHashing` 测试页面哈希逻辑：

- 单页书籍：所有页面都应被哈希。
- 多于 `pageHashing * 2` 页的书籍：只哈希开头 `pageHashing` 页和结尾 `pageHashing` 页，中间页面的 `fileHash` 保持空字符串。
- 已经有 `fileHash` 的页面：不再调用 `getPageContent` 和 `hashPage`。
- 内容相同但元数据可能不同的图片：通过 `provideDirectoriesForPageHashing` 遍历 `hashpage` 测试资源目录，验证两张“实际页面内容相同”的文件得到相同哈希。

最后一个测试尤其重要，因为 `BookAnalyzer.hashPage` 对 JPEG 有特殊处理：它会读取并重新写出 JPEG，以去掉 EXIF 等元数据，再计算哈希。这样可以避免“同一张图因为元数据不同而哈希不同”。

## 上下游关系

上游主要是领域生命周期服务。`BookAnalyzerTest.kt` 直接测试 `BookAnalyzer`，而生产代码中常见调用方包括：

- `komga/src/main/kotlin/org/gotson/komga/domain/service/BookLifecycle.kt`
- `komga/src/main/kotlin/org/gotson/komga/domain/service/BookConverter.kt`
- `komga/src/main/kotlin/org/gotson/komga/domain/service/BookPageEditor.kt`
- `komga/src/main/kotlin/org/gotson/komga/domain/service/TransientBookLifecycle.kt`

其中 `BookLifecycle.analyzeAndPersist(book)` 会调用：

`bookAnalyzer.analyze(book, libraryRepository.findById(book.libraryId).analyzeDimensions)`

随后把返回的 `Media` 写入 `mediaRepository`，并根据 `media.status` 决定是否触发缩略图生成、元数据刷新等后续动作。

`BookLifecycle.hashPagesAndPersist(book)` 会调用：

`bookAnalyzer.hashPages(BookWithMedia(book, mediaRepository.findById(book.id)))`

然后将带页面哈希的 `Media` 更新回仓库。

下游则是 `BookAnalyzer` 依赖的具体媒体解析组件：

- `ContentDetector`：识别文件媒体类型。
- `DivinaExtractor` 列表：处理 ZIP、RAR 等漫画归档类媒体。
- `PdfExtractor`：处理 PDF。
- `EpubExtractor`：处理 EPUB，包括资源、目录、landmarks、page list、positions、封面等。
- `ImageAnalyzer`、`ImageConverter`：图片分析和转换。
- `Hasher`：计算文件或页面内容哈希。
- `KomgaSettingsProvider`、`KomgaProperties`：提供缩略图、页面哈希数量等配置。

测试文件与这些下游组件的关系是“选择性真实 + 局部模拟”。例如归档格式测试更偏向真实分析，而 EPUB 错误码测试通过 mock `EpubExtractor` 的某一步骤来制造异常。

## 运行/调用流程

以归档分析测试为例，流程是：

1. 用 `ClassPathResource("archives/zip.zip")` 找到测试资源。
2. 构造领域对象：`Book("book", file.url, LocalDateTime.now())`。
3. 调用 `bookAnalyzer.analyze(book, false)`。
4. `BookAnalyzer` 通过 `ContentDetector.detectMediaType(book.path)` 识别媒体类型。
5. 根据 `MediaType.profile` 分派到 `analyzeDivina`、`analyzePdf` 或 `analyzeEpub`。
6. 返回 `Media`。
7. 测试断言 `media.mediaType`、`media.status`、`media.pages` 等字段。

以 EPUB 可恢复错误测试为例，流程是：

1. 使用正常 EPUB 测试资源。
2. 用 `every { epubExtractor.getToc(any()) } throws Exception("mock exception")` 模拟目录提取失败。
3. 调用 `bookAnalyzer.analyze(book, false)`。
4. `BookAnalyzer.analyzeEpub` 捕获异常，把 `ERR_1035` 加入错误列表。
5. `Media.status` 仍返回 `READY`。
6. `Media.comment` 包含 `ERR_1035`。
7. `Media.extension as MediaExtensionEpub` 中的 `toc` 为空列表。

以页面哈希测试为例，流程是：

1. 构造 `Book`、`BookPage` 列表和 `Media`。
2. 组合成 `BookWithMedia(book, media)`。
3. 对 `bookAnalyzer.getPageContent` 和 `bookAnalyzer.hashPage` 做 spy mock，避免真的读取页面文件。
4. 调用 `bookAnalyzer.hashPages(...)`。
5. `BookAnalyzer.hashPages` 遍历页面：
   - 如果 `fileHash` 已有值，跳过。
   - 如果页面位于开头或结尾配置范围内，读取页面内容并计算哈希。
   - 如果页面在中间区域，保持原样。
6. 测试断言哪些页面被写入 `"hashed"`，哪些仍为空字符串。

## 小白阅读顺序

建议先读 `BookAnalyzerTest.kt` 的三个嵌套类名，而不是直接陷入每个断言：

1. 先看 `ArchiveFormats`，理解 Komga 对漫画压缩包的基本期望：哪些格式能读，哪些格式只是识别但不支持，哪些格式会报错。
2. 再看 `Epub`，重点理解“EPUB 子结构失败”和“整本书分析失败”是两回事。TOC、landmarks、page list、positions 失败时，系统尽量返回 `READY` 并记录错误码。
3. 最后看 `PageHashing`，理解页面哈希不是给所有页面都算，而是默认只算首尾若干页，用于后续匹配或识别。
4. 读完测试后再看 `BookAnalyzer.kt` 的 `analyze` 方法。它是总入口，先识别媒体类型，再按 `MediaProfile` 分派。
5. 接着看 `analyzeDivina`、`analyzeEpub`、`hashPages`、`hashPage`。这些方法正好对应本测试文件的三大分组。
6. 如果想理解生产链路，再看 `BookLifecycle.kt` 的 `analyzeAndPersist` 和 `hashPagesAndPersist`，它们说明分析结果如何进入数据库和后续任务。

## 常见误区

第一个误区是把 `UNSUPPORTED` 和 `ERROR` 混为一谈。测试里 RAR5、7z 返回 `UNSUPPORTED`，表示系统识别到了格式，但当前不支持读取；加密 ZIP 返回 `ERROR`，表示按 ZIP 流程处理时发生了实际错误。两者语义不同。

第二个误区是认为扩展名决定媒体类型。`zip-as-epub.epub` 的测试说明，即使文件名是 `.epub`，如果内容不是合法 EPUB，系统也可能识别为 `application/zip` 并返回错误。`BookAnalyzer` 会结合内容检测和 `epubExtractor.isEpub` 判断。

第三个误区是认为 EPUB 任意子步骤失败都会让 `Media.status` 变成 `ERROR`。测试明确验证了 TOC、landmarks、page list、Divina pages、positions 的提取失败是可恢复的：状态仍是 `READY`，错误通过 `Media.comment` 的 `ERR_1035` 到 `ERR_1039` 表达。

第四个误区是以为页面哈希会覆盖所有页面。`hashPages` 的策略是只处理开头和结尾配置数量的页面，配置来自 `KomgaProperties.pageHashing`。如果页面已经有 `fileHash`，它也不会重复计算。

第五个误区是忽略 JPEG 元数据对哈希的影响。`hashPage` 对 JPEG 会做读写归一化，目的是去掉 EXIF 等元数据，让视觉内容相同的 JPEG 更可能得到相同哈希。`given 2 exact pages when hashing then hashes are the same` 就是在保护这个行为。

第六个误区是把这个文件当成纯 mock 测试。它使用了 `@SpringBootTest` 和 `@SpykBean`，说明它依赖 Spring 上下文和真实 Bean，只在需要制造特定异常或隔离哈希范围时局部 mock。它更接近领域服务级别的集成测试，而不是完全手写依赖的轻量单元测试。
