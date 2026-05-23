# 文件：komga/src/main/kotlin/org/gotson/komga/domain/service/BookAnalyzer.kt
## 它负责什么
`BookAnalyzer` 是 Komga 里负责“把一本书解析成可用媒体信息”的核心服务。它不只是判断文件类型，还会把书拆成页面、资源、封面、位置索引和哈希信息，并把这些结果包装成 `Media`、`BookPage`、`ThumbnailBook` 等领域对象。

从依赖看，它直接编排了 `ContentDetector`、`PdfExtractor`、`EpubExtractor`、`DivinaExtractor`、`ImageConverter`、`ImageAnalyzer`、`Hasher` 和配置项 `KomgaSettingsProvider`，所以它更像是一个把“文件容器解析”和“领域媒体模型”连接起来的胶水层，而不是纯算法类。

## 关键组成
- `analyze(book, analyzeDimensions)`：入口方法。先检测媒体类型，再按 `MediaProfile` 分派到 `analyzeDivina`、`analyzePdf`、`analyzeEpub`。
- `divinaExtractors`：把注入进来的多个 `DivinaExtractor` 按 `mediaType` 建索引，方便后续按类型取对应 extractor。
- `analyzeDivina(...)`：读取 Divina 类资源，过滤出图片页，构造 `BookPage` 和附加文件 `MediaFile`，并汇总异常资源信息。
- `analyzeEpub(...)`：处理 EPUB 的目录、landmarks、page list、fixed layout、divina pages、positions，还会识别 `kepub` 和 EPUB 中缺失资源。
- `analyzePdf(...)`：提取 PDF 页面并生成最基础的页面列表。
- `generateThumbnail(book)` / `getPoster(book)`：从不同媒体类型中找封面或首图，并压缩成缩略图数据。
- `getPageContent(...)`、`getPageContentRaw(...)`、`getFileContent(...)`：按页或按文件名导出具体内容。
- `hashPages(book)`、`hashPage(...)`：给页面内容算哈希，默认只处理首尾若干页。
- `getPdfPagesDynamic(media)`：给 PDF 生成“动态页”视图，用于把 PDF 页面统一成图像页样式。
- 异常处理：统一把文件不可读、找不到、类型不支持等问题折算成 `Media.Status.ERROR` 或 `UNSUPPORTED`，并用错误码写入 `comment`。

## 上下游关系
上游主要是书籍生命周期和导入/转换流程。根据调用方搜索结果，`BookLifecycle`、`BookConverter`、`BookPageEditor`、`TransientBookLifecycle` 都会调用 `analyze(...)`；`BookLifecycle` 还会调用 `generateThumbnail(...)` 和 `hashPages(...)`。这说明 `BookAnalyzer` 是“书籍入库、重算媒体、生成缩略图、页面哈希”这条链路的基础依赖。

下游主要是 API 和内容提供者。`BookController`、`CommonBookController`、`TransientBooksController`、`OpdsGenerator`、`WebPubGenerator`、`ComicInfoProvider`、`IsbnBarcodeProvider` 都依赖它或其结果。根据当前片段推断，这些调用方会分别使用它提供的页面图像、封面、页面数量、EPUB 结构信息和媒体状态，去实现网页浏览、OPDS 输出、元数据生成和封面展示。

它还直接依赖基础设施层，所以从架构上看是“领域服务调用基础设施解析器”，而不是单纯只依赖领域模型的服务。

## 运行/调用流程
1. 调用方先传入 `Book`，通常还会带一个 `analyzeDimensions` 标志。
2. `analyze(...)` 用 `ContentDetector` 判断文件媒体类型，并尝试映射到内部 `MediaType`。
3. 如果文件后缀是 `.epub`，但检测结果不是 EPUB，还会额外用 `epubExtractor.isEpub(...)` 做一次校验，避免坏文件被当成普通 ZIP 或其他类型。
4. 根据 `MediaProfile` 分流：
   - `DIVINA` 走 `analyzeDivina(...)`
   - `PDF` 走 `analyzePdf(...)`
   - `EPUB` 走 `analyzeEpub(...)`
5. 每条分支都会尽量返回 `Media`，并把异常转成错误状态和错误码。
6. 缩略图链路是先 `getPoster(...)` 找封面，再用 `ImageConverter` 压缩，最后构造 `ThumbnailBook`。
7. 页面读取链路是按页号或文件名返回图像/字节流，供预览、导出、网页阅读器使用。
8. 页面哈希链路会跳过已有哈希的页，只对配置范围内的首尾页做内容哈希。

## 小白阅读顺序
1. 先看 `analyze(...)`，它是总入口，能快速明白类的职责边界。
2. 再看 `analyzeDivina(...)`、`analyzePdf(...)`、`analyzeEpub(...)`，理解三种媒体类型的分支差异。
3. 然后看 `generateThumbnail(...)` 和 `getPoster(...)`，把“封面从哪里来”这条线理清。
4. 接着看 `getPageContent(...)`、`getFileContent(...)`、`getPageContentRaw(...)`，理解外部怎么拿内容。
5. 最后看 `hashPages(...)` 和 `getPdfPagesDynamic(...)`，理解附加能力和一些特定场景的适配逻辑。

## 常见误区
- 误以为 `analyze(...)` 只做格式识别。实际上它还会解析页面、资源、目录、位置和封面。
- 误以为所有方法都能在任意 `Media.Status` 下调用。实际上很多方法都要求 `READY`，否则会抛 `MediaNotReadyException`。
- 误以为页码从 0 开始。这里的 `getPageContent(...)` 是 1-based，`number <= 0` 会直接报错。
- 误以为 `getPageContentRaw(...)` 是通用导出。它只支持 PDF，其他 profile 会抛 `MediaUnsupportedException`。
- 误以为 EPUB 一定走 EPUB 分支。这里还会检查 `.epub` 的真实结构，坏文件会被标记为错误，而不是硬解析。
- 误以为 `hashPages(...)` 会把整本书所有页面都算一遍。实际上它只处理配置里的首尾若干页，且跳过已有 `fileHash` 的页面。
- 误以为缩略图总能生成。`generateThumbnail(...)` 依赖 `getPoster(...)`，拿不到封面就会抛 `NoThumbnailFoundException`。
