# 文件：docs/developers/sdk.mdx

## 一句话定位

`docs/developers/sdk.mdx` 是 Reworkd 开发者文档中的 “Scraping SDK” 页面，用来向写爬取脚本或审查自动生成代码的开发者说明 Harambe SDK 的核心能力、方法边界和推荐用法。它不是运行时代码，而是 SDK 使用契约的文档入口。

## 它暴露/定义了什么

该文件通过 MDX frontmatter 定义页面标题 `Scraping SDK`，正文定义一组面向 Python 异步爬虫代码的 SDK 方法说明：`save_data`、`enqueue`、`paginate`、`capture_url`、`capture_download`、`capture_html`、`capture_pdf`、`log`。每个方法主要暴露签名、参数、返回值、异常和少量示例，帮助读者理解 Reworkd 代码生成器生成的 `sdk.*` 调用应如何工作。

从内容看，Harambe SDK 被描述为 Reworkd 自定义的网页抓取 SDK，职责覆盖结构化数据保存与 schema 校验、URL 入队与去重、分页、PDF、HTML 捕获、动态下载等典型爬虫问题。文档中的外部仓库链接应视为 Harambe 项目地址，本文不展开真实 URL。

## 谁调用它

直接调用这个文件的是文档站构建/导航系统。`docs/docs.json` 在 `Documentation` tab 的 `Developers` 分组中列出 `developers/sdk`，因此该 MDX 页面会作为开发者文档导航中的一页被渲染。

间接使用者是两类人：一类是 Reworkd 用户或集成开发者，他们需要理解自动生成的 scraping code 中 `sdk` 对象有哪些能力；另一类是维护文档或 SDK 行为的人，他们需要确保文档签名和 Harambe 实际实现保持一致。根据当前片段推断，代码生成器会产出使用 Harambe SDK 的 Python 代码，依据是页面开头明确写到 “As part of code generation, Reworkd generates code in its own custom SDK called Harambe”。

## 它调用谁

作为文档文件，它在运行时不调用任何函数，也不导入代码模块。它依赖的是 MDX/Mintlify 文档系统对 frontmatter、Markdown 标题、代码块和列表的解析。

在内容层面，它描述的 SDK 方法会调用或依赖若干外部能力：`save_data` 依赖 schema 校验与数据持久化；`enqueue` 依赖 URL 规范化、任务队列和去重；`paginate` 依赖 Playwright 页面元素或链接导航；`capture_url` 依赖浏览器点击与网络请求拦截；`capture_download`、`capture_pdf` 依赖下载处理逻辑；`capture_html` 依赖页面 DOM、`BeautifulSoup` 清洗转换以及 HTML 到 markdown/text 的转换；`log` 依赖 Python `print` 和浏览器 `console.log`。

## 核心流程

这个页面的阅读流程是先建立 SDK 定位：Reworkd 的代码生成会生成基于 Harambe 的爬虫代码，SDK 负责处理抓取过程中的通用问题。随后文档按功能逐个展开 API：先讲最终产出 `save_data`，再讲任务扩展 `enqueue`，接着讲分页 `paginate`，最后集中讲动态资源捕获，包括 URL、下载、HTML、PDF 和日志。

从爬虫执行角度看，一个典型脚本会先通过 `sdk.page` 或 Playwright API 读取当前页面元素；如果拿到结构化记录，就用 `sdk.save_data` 保存并校验；如果发现详情页或下一阶段 URL，就用 `sdk.enqueue` 入队；如果列表页有多页，则在抓取函数末尾使用 `sdk.paginate` 交给 SDK 统一翻页；遇到文件或动态跳转时，用 `capture_url` 或 `capture_download` 获得可保存的下载信息；需要保存当前页面正文或快照时，则调用 `capture_html` 或 `capture_pdf`，再把元数据写回 schema 字段。

## 关键函数的高层作用

`save_data` 是数据出口，负责把爬取结果写入系统并按当前 schema 做类型校验。它是最容易暴露业务错误的 API，因为字段缺失、类型不匹配或错误的 `source_url` 都会影响最终导出和文件关联。

`enqueue` 是任务扩展入口，负责把后续要抓取的 URL 放入队列，并可携带 `context` 与 `options`。它的关键价值是让列表页和详情页拆成不同阶段，同时保留只有当前页才知道的上下文。

`paginate` 是分页抽象，要求用户提供一个返回下一页链接或元素的异步函数。文档强调分页应优先使用该方法，而不是手写循环，说明 SDK 可能在其中统一处理重复页面、终止条件、等待和重新执行抓取函数。

`capture_url` 用于处理点击后才产生的目标 URL，核心机制是点击元素并通过网络请求拦截捕获特定 `resource_type` 的 URL，适合重定向、文档跳转等场景。

`capture_download` 用于真正的浏览器会话内下载，适合 JavaScript 触发或需要 cookie/session 的动态文件。它返回 `DownloadMeta`，通常再交给 `save_data` 写入下载字段。

`capture_html` 和 `capture_pdf` 是内容快照能力：前者抓取并清洗指定 DOM 区域，输出 HTML、文本、URL 和文件名；后者把当前页面导出为 PDF 并返回下载元数据。`log` 只是调试辅助，同时写 Python 输出和浏览器控制台。

## 修改风险

最大风险是文档与 Harambe SDK 实现漂移。这里写的是方法签名、参数类型、异常和返回值，一旦 SDK 改名、改参数默认值、返回结构字段变化，用户会按错误契约写爬虫代码，代码生成器产物也可能看起来“符合文档但运行失败”。

第二个风险是示例中的 URL、文件下载字段和 schema 字段表达不一致。相邻文档 `docs/developers/file-downloads.mdx` 和 `docs/features/file-downloads.mdx` 也解释了 `capture_url`、`capture_download` 和自动下载流程；如果只改本页，可能造成开发者文档和功能文档对动态下载、异步下载、S3 文件元数据的描述不一致。

第三个风险是过度展开底层实现。该页定位是 SDK 使用说明，不是 Harambe 内部源码文档；修改时应保持高层 API 契约清晰，避免把 Playwright、BeautifulSoup、下载队列等实现细节写成不可变承诺。

第四个风险是 MDX 渲染问题。frontmatter、代码块语言标记、列表缩进和反引号方法名都会影响文档站展示；新增真实外链时也要遵守文档站和安全规范，在本学习文档中真实 URL 已省略为 `[URL已移除]`。
