# 目录：packages/file-loaders

## 它负责什么

`packages/file-loaders` 是 LobeHub monorepo 中负责“把本地文件解析成统一文本文档结构”的 workspace 包，包名是 `@lobechat/file-loaders`。它不直接处理上传、下载、数据库写入或前端展示，而是提供底层解析能力：输入一个文件路径，按扩展名选择合适的 loader，输出统一的 `FileDocument`，其中包含聚合后的 `content`、分段后的 `pages`、文件级 metadata、字符数和行数统计。

这个包覆盖两类文件：一类是普通文本或可读文本扩展名，统一走 `TextLoader`；另一类是结构化文档格式，如 `pdf`、`doc`、`docx`、`xlsx/xls`、`pptx`，分别交给专门的 loader。它的设计重点不是“文件管理”，而是“文件内容抽取与标准化”。上层服务拿到标准化结果后，再决定是否创建 document、截断内容、存储页面信息或返回给本地文件工具。

## 直接子目录地图

`packages/file-loaders/src` 是核心源码目录，承担包的公开导出、主流程和所有 loader 实现。`src/loadFile.ts` 是总入口流程；`src/index.ts` 是包级导出入口；`src/types.ts` 定义统一数据结构和 loader 接口；`src/blackList.ts` 提供系统文件忽略列表。

`packages/file-loaders/src/loaders` 是解析器目录，按文件格式分组。`loaders/text` 处理纯文本及文本类扩展名；`loaders/pdf` 使用 `pdfjs-dist` 抽取 PDF 页面文本；`loaders/doc`、`loaders/docx` 分别处理旧版 Word 和现代 Word；`loaders/excel` 将工作表转成 Markdown 表格；`loaders/pptx` 从 PPTX 压缩包里的 slide XML 抽取幻灯片文本。`loaders/index.ts` 是 loader 注册和懒加载分发点。

`packages/file-loaders/src/utils` 放解析辅助工具，例如文本/二进制判断、UTF-16 编码探测、从压缩包中提取 XML 并解析的工具。`packages/file-loaders/src/types` 当前主要放第三方库类型补充，例如 `word-extractor.d.ts`。`packages/file-loaders/test` 和各 loader 子目录下的 `*.test.ts`、`fixtures`、`__snapshots__` 共同构成测试与样例文件区域。

## 关键入口

最重要的公开入口是 `packages/file-loaders/src/index.ts`。它导出 `blackList`、`loadFile`、`types`、`isBinaryContent`、`isTextReadableFile` 等能力。上层通常不会直接 import 某个具体 loader，而是通过 `@lobechat/file-loaders` 调用统一 API。

核心函数是 `loadFile`，位置在 `packages/file-loaders/src/loadFile.ts`。它先读取文件 stat，组合文件名、扩展名、创建时间、修改时间等基础信息；再通过内部 `getFileType` 按扩展名决定 parser 类型；随后调用 `getFileLoader` 获取具体 loader class；最后执行 `loadPages`、`aggregateContent`，如果 loader 支持，还会执行 `attachDocumentMetadata`。这些结果会被组装为统一的 `FileDocument`。

loader 侧的关键契约在 `packages/file-loaders/src/types.ts`，尤其是 `FileLoaderInterface`。所有 loader 都要实现 `loadPages(filePath)` 和 `aggregateContent(pages)`，可选实现 `attachDocumentMetadata(filePath)`。这使得 PDF、Excel、PPTX、Word、文本文件虽然解析方式不同，但输出都能被上层当作同一种 document 处理。

## 主流程位置

主流程从 `loadFile(filePath, fileMetadata?)` 开始。第一步是文件类型识别：无扩展名默认按 `txt` 尝试；文本可读扩展名也归入 `txt`；`pdf`、`doc`、`docx`、`xls/xlsx`、`pptx` 分别映射到对应 parser；其他非文本类型会抛出 `UnsupportedFileTypeError`。

第二步是 loader 选择，位置在 `packages/file-loaders/src/loaders/index.ts`。这里有一个重要设计：`TextLoader` 是静态引入的，因为它依赖轻；PDF、Word、Excel、PPTX 等重型解析器使用 dynamic import 懒加载，避免主 bundle 一启动就加载 `pdfjs-dist`、`mammoth`、`xlsx` 等大依赖。PDF loader 在 Node 环境下还会尝试用 `@napi-rs/canvas` 补齐 `DOMMatrix`、`DOMPoint`、`DOMRect`、`Path2D` 等能力。

第三步是内容抽取。文本 loader 读取文件并自动处理 UTF-8 BOM、UTF-16LE/BE BOM 和无 BOM UTF-16 探测；PDF loader 按页抽取文本并用 PDF prompt 模板聚合；Excel loader 按 sheet 生成 Markdown 表格；PPTX loader 从 `ppt/slides/slide*.xml` 提取段落文本；Word 相关 loader 则依赖对应第三方库读取文档内容。最后 `loadFile` 会统计 `pages` 的总字符数和总行数，并把 loader 错误、聚合错误、metadata 错误合并进 `metadata.error`。

上层主调用点主要有两个。服务端文档解析在 `src/server/services/document/index.ts` 中调用 `loadFile`，把上传文件解析成 `LobeDocument` 并写入文档模型。本地文件读取能力在 `packages/local-file-shell/src/file/read.ts` 中调用 `loadFile`，用于读取本地文件内容，并在调用前做大小限制、扩展名判断和二进制 sniff。

## 推荐阅读顺序

建议先读 `packages/file-loaders/src/types.ts`，理解 `FileDocument`、`DocumentPage`、`FileMetadata`、`FileLoaderInterface` 这四个核心结构。这个包所有实现都围绕这些类型组织，先看类型能减少后面阅读 loader 时的分散感。

第二步读 `packages/file-loaders/src/loadFile.ts`。这里能看到完整编排：文件 stat、metadata override、类型识别、loader 获取、分页解析、内容聚合、metadata 附加、错误合并、最终 document 构造。读完这个文件，基本就知道包的边界在哪里。

第三步读 `packages/file-loaders/src/loaders/index.ts`。重点看懒加载策略和 `txt` 的特殊处理。这里解释了为什么轻量文本 loader 不拆动态 chunk，而重型格式要延迟加载。

第四步按格式挑 loader 看，不必逐个展开。想理解最简单契约可读 `loaders/text/index.ts`；想理解页面级结构可读 `loaders/pdf/index.ts`；想理解结构化表格输出可读 `loaders/excel/index.ts`；想理解 Office XML 解包解析可读 `loaders/pptx/index.ts`。最后再看 `src/utils` 中的编码、二进制、压缩包/XML 辅助函数。

## 常见误区

不要把 `packages/file-loaders` 理解成上传系统。它不负责文件从哪里来，也不负责文件保存到哪里；它只接收本地路径并产出可消费的文本结构。上传、下载、临时文件清理、数据库创建分别在上层服务中完成。

不要认为 `fileType` 和 parser 类型完全等价。`loadFile` 返回的 `fileType` 更多来自原始扩展名或传入 metadata，而内部 parser 类型会把大量文本扩展名归并为 `txt`，也会把 `xls` 和 `xlsx` 归并为 `excel`。

不要绕过 `loadFile` 直接调用具体 loader，除非是在测试或非常明确的内部扩展场景。`loadFile` 不只是分发器，它还统一处理 stat、metadata override、错误合并、总字符/行数统计和最终 `FileDocument` 结构。

不要忽视懒加载边界。`packages/file-loaders/src/loaders/index.ts` 明确避免重型解析依赖进入主路径；新增格式时应优先延续这个模式。根据当前片段推断，这一点对桌面端或本地文件读取场景尤其重要，因为注释中提到动态 chunk 和 Electron 初始化副作用相关的回归。

不要把“可读文本文件”和“支持的特殊文档格式”混为一谈。普通 `.md`、`.json`、`.ts` 等更可能通过文本判断进入 `TextLoader`；PDF、Office、Excel、PPTX 则需要对应解析器。上层如 `packages/local-file-shell/src/file/read.ts` 还会在调用 `loadFile` 前做二进制与大小保护，这些保护不属于 loader 本身的完整职责。
