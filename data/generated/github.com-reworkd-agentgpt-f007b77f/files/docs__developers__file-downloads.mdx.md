# 文件：docs/developers/file-downloads.mdx

## 一句话定位

`docs/developers/file-downloads.mdx` 是 Reworkd 文档中面向开发者的“文件下载处理策略”页面，用来告诉编写 scraping job 的开发者：不同下载形态应该把 URL 交给异步下载管线，还是在浏览器 worker 中直接捕获下载事件。

## 它暴露/定义了什么

这个文件本身不定义运行时代码、API 路由或库函数，而是定义一页 Mintlify/MDX 文档，frontmatter 中的 `title: Handling File Downloads` 决定页面标题。正文按下载来源把场景分成四类：

第一类是 `Regular Download Links`，即页面 HTML 中已经有直接文件链接，例如 `<a href="...">`。文档建议直接读取 `href`，再用 `sdk.save_data({"download_url": href})` 保存，让后端异步下载。

第二类是 `Indirect Download Links`，即点击按钮后才跳转到文件或下载页面。文档建议用 `sdk.capture_url(element)` 捕获点击后产生的 URL，再保存为 `download_url`。

第三类是 `JavaScript/Dynamic Downloads`，即浏览器内 JavaScript 触发下载，没有稳定的可见 URL。文档建议用 `sdk.capture_download(element)` 在浏览器上下文中捕获实际下载，并把返回的 metadata 写入 `attachment.download_url` 和 `attachment.title`。

第四类是 `Downloads Requiring Cookies/Session`，即文件必须在当前登录态、cookie 或浏览器 session 中获取。文档把它归入动态下载处理，要求通过 `capture_download` 在 browser context 内完成，而不是交给 AWS Lambda。

## 谁调用它

严格说，这个文件不会被业务代码“调用”。它被文档系统消费：`docs/docs.json` 的导航配置把 `developers/file-downloads` 放在 `Developers` 分组下，因此 Mintlify 构建文档站时会读取并渲染该 MDX 页面。

从内容关系看，`docs/features/file-downloads.mdx` 是面向功能使用者的文件下载总览，其中提到“更多技术细节见 Handling file downloading”，根据当前片段推断它指向的就是本文件，因为本文件标题为 `Handling File Downloads`，且位于开发者文档分组。`docs/schemas.mdx` 也说明 URL 字段可用于下载文件，并提示查看下载文件页面；这与本页描述的 `download_url` 保存方式形成上下游关系。

## 它调用谁

作为文档文件，它没有真实 import 或函数调用。但它的示例代码依赖 Harambe/Reworkd SDK 的几个核心接口：

`这几个接口分别是 `sdk.page.query_selector`、`ElementHandle.get_attribute`、`sdk.save_data`、`sdk.capture_url`、`sdk.capture_download`。其中 `sdk.page` 来自 Playwright 风格的页面对象；`query_selector` 用于定位下载按钮或链接；`get_attribute("href")` 用于读取直接下载地址；`save_data` 负责把抓取结果提交给 schema 校验和后续数据管线；`capture_url` 负责监听点击后产生的导航或网络 URL；`capture_download` 负责监听浏览器下载事件并生成可保存的文件 metadata。

文档还提到运行时基础设施：普通 URL 下载会由 Reworkd 异步访问和下载，使用 `curl-cffi` 模拟浏览器行为；功能页补充说明该路径通过 AWS Lambda 和 dedicated download queue 处理。动态下载则由 browser worker 直接完成，文件最终进入 Reworkd 的存储和导出体系。

## 核心流程

普通下载的核心流程是：开发者在页面上找到下载链接元素，读取 `href`，把它保存到 schema 中开启了文件下载能力的 URL 字段。后续下载不在当前 scraping 代码里同步完成，而是由 Reworkd 异步下载队列处理。这个流程适合 PDF、CSV、图片等有稳定 canonical URL 的文件。

间接下载的流程是：开发者先定位触发元素，再让 `sdk.capture_url` 点击并捕获跳转出来的资源 URL。捕获到 URL 后仍然走普通下载路径，即通过 `sdk.save_data` 写入字段，由异步下载基础设施处理。它解决的是“URL 不在 DOM 属性里，但点击后可获得”的情况。

动态下载的流程是：开发者定位触发下载的按钮，调用 `sdk.capture_download`。该方法会在当前浏览器会话中触发点击、等待下载、处理下载结果，并返回包含 `url`、`filename` 等信息的 `DownloadMeta`。开发者再把 metadata 作为附件字段保存。这个流程绕过 Lambda 的重新访问，因为重新访问可能缺少前端状态、cookie、一次性 token 或 JavaScript 生成的 blob 数据。

需要 session 的下载与动态下载共用路径：只要离开当前 browser context 就无法可靠获取文件，就应使用 `capture_download`，避免把只有当前会话可访问的 URL 交给异步下载器。

## 关键函数的高层作用

`sdk.save_data` 是数据管线入口。根据 `docs/developers/sdk.mdx`，它会保存 scraped data，并校验数据是否符合当前 schema。放到本页语境中，它的作用是把 `download_url` 或附件 metadata 写入结果，使后续文件下载、存储和导出流程有数据来源。

`sdk.capture_url` 是“点击后拿 URL”的工具。它通过点击元素并监听网络或页面打开行为来返回资源 URL，适合处理 redirect、按钮跳转、文档下载页等无法直接从 HTML 读取链接的场景。它仍然产出 URL，不直接代表文件已被浏览器下载完成。

`sdk.capture_download` 是“当前浏览器内完成下载捕获”的工具。它处理点击、下载、下载后 metadata 构造，适合无 canonical URL、JavaScript 触发、cookie/session 依赖等情况。相比 `capture_url`，它更重，但能覆盖普通异步下载器无法复现的浏览器状态。

`sdk.page.query_selector` 和 `get_attribute` 是辅助动作，分别用于选择页面元素和读取属性，本页只是把它们作为定位下载入口的样板代码，不承载下载策略本身。

## 修改风险

最大的风险是把三条下载路径的边界写错。若把 session 依赖或 JavaScript 动态下载误导为保存 `download_url`，异步 Lambda 重新请求时可能拿不到文件，导致导出缺失或下载失败。反过来，如果把所有下载都建议使用 `capture_download`，会增加 browser worker 负担，削弱异步下载队列的优势。

第二个风险是字段结构不一致。本页动态下载示例使用 `attachment.download_url` 和 `title`，普通下载示例使用顶层 `download_url`；而功能页强调 schema 中 URL 字段需开启 `Download file from URL`，导出结果会进入 `files` 数组。修改示例时必须与 schema、SDK 文档和导出格式保持一致，否则开发者会保存到无法触发下载的字段。

第三个风险是命名漂移。`docs/developers/sdk.mdx` 中 `capture_download` 的返回值描述包含 `url` 和 `filename`，而本页示例读取 `download_metadata["title"]`。根据当前片段无法确认真实 SDK 是否同时返回 `title` 与 `filename`；如果要修改这里，应优先核对 Harambe SDK 的实际 `DownloadMeta` 类型，否则文档可能提供不可运行示例。

第四个风险是导航和交叉引用断裂。本页由 `docs/docs.json` 暴露在 Developers 分组中，并被功能下载页概念性引用。重命名文件、标题或路径时，需要同步更新 `docs/docs.json` 以及相关“Downloading files / Handling file downloading”的引用文案，避免用户从功能说明无法跳到开发者实现策略。
