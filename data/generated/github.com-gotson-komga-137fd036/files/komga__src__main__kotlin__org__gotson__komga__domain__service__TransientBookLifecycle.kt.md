# 文件：komga/src/main/kotlin/org/gotson/komga/domain/service/TransientBookLifecycle.kt

## 它负责什么

`TransientBookLifecycle` 是一个 Spring `@Service`，专门管理“临时书籍” `TransientBook` 的生命周期。这里的“临时”不是正式入库后的书，而是用户刚扫描进来、还需要分析和补充元数据的一批文件。

它做的事情可以概括成三步：

1. 扫描指定文件夹，找出可作为书籍处理的文件，并先持久化成 `TransientBook`。
2. 对某一本临时书执行分析，补齐媒体信息、编号和可能关联到的系列。
3. 提供某一页的原始内容，供 API 层读取和返回。

从职责上看，它更像一个编排层，把 `FileSystemScanner`、`BookAnalyzer`、仓储和元数据提供器串起来，而不是自己做底层解析。

## 关键组成

这个文件的核心依赖很清楚：

- `TransientBookRepository`：保存和读取临时书记录。
- `BookAnalyzer`：分析书籍文件，生成 `Media`，并读取指定页内容。
- `FileSystemScanner`：从文件系统里扫描目录，找出待处理的书。
- `LibraryRepository`：用于做路径冲突检查，避免扫描到已经属于正式库的目录。
- `SeriesRepository`：根据书名线索反查可能的系列。
- `SeriesMetadataFromBookProvider`：从书本内容里提取系列名线索。
- `BookMetadataProvider`：从书本内容里提取书号等元数据，这里只保留支持 `BookMetadataPatchCapability.NUMBER_SORT` 的实现。
- `pdfImageType`：通过 `@Qualifier("pdfImageType")` 注入，处理 PDF 页面的媒体类型判断。

文件里最重要的三个方法是：

- `scanAndPersist(filePath: String)`
- `analyzeAndPersist(transientBook: TransientBook)`
- `getBookPage(transientBook: TransientBook, number: Int)`

另外还有一个辅助方法：

- `getMetadata(transientBook: TransientBook)`

## 上下游关系

上游调用方只有一个，来自 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/TransientBooksController.kt`。

控制器暴露了三个接口，对应这个 service 的三项能力：

- `POST /api/v1/transient-books` -> 扫描目录并保存临时书
- `POST /api/v1/transient-books/{id}/analyze` -> 分析某本临时书
- `GET /api/v1/transient-books/{id}/pages/{pageNumber}` -> 读取某一页内容

下游依赖主要是基础设施和领域服务：

- 文件扫描走 `FileSystemScanner.scanRootFolder`
- 媒体分析走 `BookAnalyzer.analyze`
- 页内容读取走 `BookAnalyzer.getPageContent`
- 元数据匹配走 `SeriesMetadataFromBookProvider`、`BookMetadataProvider`、`SeriesRepository`
- 持久化走 `TransientBookRepository`
- 路径校验走 `LibraryRepository`

根据当前片段推断，`TransientBookLifecycle` 的设计目标是把“扫描 -> 分析 -> 取页”这条链路集中到一个服务里，让 REST 层只负责参数接收和错误映射。

## 运行/调用流程

### 1. 扫描并保存
`scanAndPersist(filePath)` 先把传入路径转成 `Paths.get(filePath)`，然后遍历所有 library：

- 如果要扫描的目录落在已有 library 的路径之下，就直接抛出 `PathContainedInPath`
- 这样可以避免把正式库目录当成临时导入目录重复扫描

随后调用 `fileSystemScanner.scanRootFolder(folderToScan)`，取出扫描结果里的 `series.values.flatten()`，为每个条目包装成 `TransientBook(it, Media())`，最后批量保存。

### 2. 分析并补全元数据
`analyzeAndPersist(transientBook)` 会先调用 `bookAnalyzer.analyze(transientBook.book, true)` 得到 `Media`。

然后调用 `getMetadata(transientBook.copy(media = media))` 去补充：

- `number`：书号，来自 `BookMetadataProvider`
- `seriesId`：系列 ID，来自 `SeriesRepository` 匹配结果

最后把新的 `media` 和 `metadata` 写回 `TransientBookRepository`。

### 3. 读取页面内容
`getBookPage(transientBook, number)` 调 `bookAnalyzer.getPageContent(...)` 取页面字节，再根据媒体类型决定返回值：

- 如果是 `MediaProfile.PDF`，强制使用 `pdfImageType.mediaType`
- 否则使用 `transientBook.media.pages[number - 1].mediaType`

这里抛出的异常会被 controller 转成更适合 API 的 HTTP 错误码。

### 4. 元数据匹配逻辑
`getMetadata(...)` 的流程比较有代表性：

- 先把 `TransientBook` 转成 `BookWithMedia`
- 通过 `bookMetadataProviders` 找 `numberSort`
- 再从所有 `SeriesMetadataFromBookProvider` 收集系列名候选
- 先做精确匹配 `SearchOperator.Is`
- 如果没有结果，再做模糊匹配 `SearchOperator.Contains`
- 最终返回 `series?.id to number`

这意味着它不是简单地存文件扫描结果，而是在尝试把临时书和现有系列结构对齐。

## 小白阅读顺序

1. 先看 `TransientBookLifecycle.kt` 里的三个公开方法，建立整体印象。
2. 再看 `TransientBooksController.kt`，把 HTTP 接口和 service 方法对应起来。
3. 接着看 `TransientBook.kt`，理解 `TransientBook` 只是 `Book + Media + Metadata` 的组合体。
4. 然后回头看 `scanAndPersist`，搞清楚扫描结果是怎么被包装进 `TransientBook` 的。
5. 再看 `analyzeAndPersist` 和 `getMetadata`，理解分析、补元数据、系列反查这条链路。
6. 最后看 `getBookPage`，确认页面内容是如何根据 PDF/非 PDF 分流的。

## 常见误区

- 不要把 `TransientBook` 当成正式书籍实体。它更像导入过程中的中间态。
- 不要忽略 `scanAndPersist` 里的路径校验。它是在防止扫描目录落入已有 library，避免重复和冲突。
- 不要把 `analyzeAndPersist` 误解成纯解析文件。它还会把分析结果写回仓库，并补充系列和书号信息。
- 不要以为所有页面类型都直接返回 `media.pages[number - 1]` 的 MIME type。PDF 有单独的 `pdfImageType` 处理。
- 不要把 `getMetadata` 看成固定规则匹配。它先精确查，再模糊查，而且线索来自多个 metadata provider，属于“尽量对齐现有系列”的策略。
