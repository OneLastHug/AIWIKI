# 文件：docs/features/file-downloads.mdx

## 一句话定位

`docs/features/file-downloads.mdx` 是 Reworkd 文档站里面向普通产品用户的“文件自动下载”功能说明页，解释如何通过 URL 类型字段开启下载、下载结果如何出现在导出数据中，以及普通下载与动态下载在平台内部的大致处理差异。

## 它暴露/定义了什么

这个文件暴露的是一篇 Mintlify MDX 文档页，frontmatter 只定义了 `title: File Downloads`。正文定义了几个用户可见概念：自动下载配置方式、导出结果里的 `files` 数组、文件元数据字段含义、Regular downloads、Dynamic downloads，以及 S3 存储保留期。

它没有定义运行时代码、React 组件或 SDK API，只是通过 Markdown/MDX 组织产品说明。页面中使用了一个 `<Warning>` 组件提示“文件下载是异步发生的”，该组件应由文档站框架或全局 MDX 组件环境提供，不在本文件内实现。

## 谁调用它

直接调用方是文档站导航配置 `docs/docs.json`。该文件把 `features/file-downloads` 放在 Documentation tab 的 Features 分组下，因此 Mintlify 构建文档站时会把 `docs/features/file-downloads.mdx` 注册为一个功能页面。

内容层面，`docs/schemas.mdx` 在 URL 字段说明中提到 URL 字段也支持下载文件，并引导读者查看“Downloading files”页面；根据当前片段推断，这里的目标就是本页，因为本页正是面向用户解释 URL 字段下载配置的功能页。开发者相关入口则是 `docs/developers/file-downloads.mdx` 和 `docs/developers/sdk.mdx`，它们不是调用本页，而是从代码策略角度补充同一功能。

## 它调用谁

本页没有代码调用关系，但文档语义依赖几个外部或相邻能力：一是 schema 系统里的 **URL** 字段及其字段设置 `Download file from URL`；二是 job 运行后保存 URL 到该字段的采集流程；三是导出系统，它会把下载产物追加到导出结果的 `files` 数组；四是文件下载与存储基础设施，包括 AWS Lambda、专用下载队列、浏览器 worker、S3 bucket、pre-signed URL。

MDX 层面只显式调用 `<Warning>` 组件。示例 JSON 中的 `s3_url`、`source_url`、`file_url` 是字段展示，不代表本页实际发起网络请求。

## 核心流程

用户路径是：先在 schema 中创建一个 **URL** 类型字段，然后在字段设置里开启 `Download file from URL`，再创建一个 job，让采集结果把文件下载地址写入这个字段。job 运行后，平台会根据这个 URL 异步下载对应文件。因为下载不是同步阻塞采集流程，所以导出中可能需要等待一段时间才会看到文件链接。

结果路径是：下载完成后，导出数据中会包含 `files` 数组。数组元素描述文件与原始数据字段的关系，例如 `field` 表示文件来自输出数据中的哪个字段，`s3_url` 表示用于取回文件的预签名地址，`source_url` 表示原始文件来源地址，`file_type`、`file_checksum`、`file_metadata` 则提供类型、校验和和附加元信息。

下载路径分两类。Regular downloads 适用于文件本身有可直接访问 URL 的场景，例如直接 PDF 链接；平台保存 canonical URL 后，通过 AWS Lambda 和专用下载队列异步拉取。Dynamic downloads 适用于没有 canonical URL、下载依赖 JavaScript 或当前会话状态的场景；文件会在 browser worker 中直接下载，`source_url` 会退化为当前页面地址，并通过 `file_metadata.dynamic_download` 标识。

## 关键函数的高层作用

本文件本身没有函数。与它关系最近的关键 SDK 能力在 `docs/developers/sdk.mdx` 和 `docs/developers/file-downloads.mdx` 中：`sdk.save_data` 负责把采集到的数据写入 schema 字段，是触发 URL 字段后续下载处理的入口；`sdk.capture_url` 用于点击元素后捕获跳转或请求产生的真实下载 URL，适合间接下载；`sdk.capture_download` 用于在浏览器会话内捕获下载事件、下载文件并返回元数据，适合动态下载或需要 cookies/session 的文件；`sdk.capture_pdf`、`sdk.capture_html` 是把页面内容转成可下载产物后再保存的辅助能力。

根据当前片段推断，产品页把这些底层 API 抽象成“保存 URL 到开启下载的 URL 字段”这一用户动作，而开发者页负责解释不同网站下载形态下应该用哪个 SDK 方法。

## 修改风险

最大风险是把产品功能页和开发者实现页的边界写混。本页面向配置和结果理解，不应塞入过多 SDK 代码细节；如果需要解释 `capture_download` 或 `capture_url`，更适合改 `docs/developers/file-downloads.mdx` 或 `docs/developers/sdk.mdx`。

第二个风险是字段契约变更。`files` 数组示例里的 `s3_url`、`source_url`、`field`、`file_metadata.dynamic_download` 等字段一旦与真实 API 导出结构不一致，会直接误导用户集成。尤其是 `source_url` 的语义比较特殊：动态下载没有 canonical source 时可能指向当前页面或 S3 相关地址，修改时要和后端导出结构保持一致。

第三个风险是异步与保留期承诺。页面明确说下载异步发生，并声明 S3 bucket 内文件只保证保留 90 天。这里属于产品承诺和用户预期，不能随意改成同步、永久保存或更长保留期，除非基础设施和业务政策已经同步调整。

第四个风险是导航和交叉引用。若重命名文件或标题，需要同步检查 `docs/docs.json`、`docs/schemas.mdx` 以及开发者下载页中的相关描述，否则文档站导航或“Downloading files”指引会断裂或语义不一致。
