# 目录：docs/developers

## 它负责什么

`docs/developers` 是 Reworkd 文档体系里面向开发者集成和脚本编写的说明目录。它不承载产品概念的完整介绍，也不是 API Reference 的自动生成入口，而是把“开发者真正开始接入时会用到的几件事”集中放在一起：如何创建和使用 API Key、如何理解 Reworkd 生成代码所依赖的 scraping SDK、以及在爬取任务中如何处理不同类型的文件下载。

从 `docs/docs.json` 的导航结构看，这个目录位于 `Documentation` tab 下的 `Developers` 分组，页面顺序是 `developers/api-keys`、`developers/sdk`、`developers/file-downloads`。因此它的角色更接近“开发实践指南”，服务于已经理解 `introduction`、`key-concepts`、`schemas` 等基础概念，并准备调用 API 或编写 scraping 逻辑的读者。

这个目录中的内容以 `.mdx` 文档为主，没有业务源码、没有组件实现，也没有测试文件。它说明的是外部开发者该如何使用 Reworkd 平台和生成代码，而不是 Reworkd 内部后端、前端或任务调度系统的实现细节。

## 直接子目录地图

`docs/developers` 当前没有直接子目录，只有三个一级文档文件：

`docs/developers/api-keys.mdx`：说明组织级 API Key 的创建位置、创建步骤，以及请求时如何通过 `Authorization: Bearer <YOUR-API-KEY>` 进行认证。它是开发者接入 Reworkd API 前的准备页。

`docs/developers/sdk.mdx`：介绍 Reworkd 代码生成中使用的自定义 scraping SDK，即 `Harambe`。该页按 SDK 方法组织，覆盖 `save_data`、`enqueue`、`paginate`、`capture_url`、`capture_download`、`capture_html`、`capture_pdf`、`log` 等常用能力，是目录中最核心、信息量最大的开发文档。

`docs/developers/file-downloads.mdx`：面向 scraping 脚本中的文件下载场景，解释常规下载链接、间接下载链接、JavaScript 动态下载、需要 cookie/session 的下载分别应该采用什么策略。它和 `sdk.mdx` 中的 `capture_url`、`capture_download` 有明显关联。

## 关键入口

最直接的入口是 `docs/docs.json`。该文件配置 Mintlify 文档站的导航结构，其中 `navigation.tabs[0].groups` 下存在 `Developers` 分组，并把本目录的三个页面注册进去。换句话说，`docs/developers` 是否出现在文档站侧边栏、顺序如何，主要由 `docs/docs.json` 决定。

从阅读入口看，`docs/developers/api-keys.mdx` 是认证入口。它告诉用户先创建组织 API Key，再把 key 放入 HTTP 请求头。虽然页面中提到了外部认证页面和组织菜单截图，但学习源码时只需要理解它表达的接入前置条件：API 请求依赖 organization-level API key。

`docs/developers/sdk.mdx` 是开发者脚本入口。该页开头说明 Reworkd 的代码生成会生成基于 `Harambe` 的 scraping 代码，然后逐个说明 SDK 方法。若要理解 Reworkd 期望开发者如何保存结构化数据、排队新 URL、处理分页和下载，这个文件是第一关键入口。

`docs/developers/file-downloads.mdx` 是下载场景入口。它不讲通用 SDK 全貌，而是按问题类型组织：页面上直接能拿到 `href` 时保存 URL；点击后才出现目标时用 `capture_url`；浏览器会话内触发下载时用 `capture_download`。它更像 `sdk.mdx` 下载相关 API 的场景化补充。

## 主流程位置

这个目录描述的主流程可以概括为三段。

第一段是认证准备流程：用户进入组织 API key 页面，创建新的 API key，设置合理过期时间，然后在请求中附加 `Authorization` header。对应文档是 `docs/developers/api-keys.mdx`。这里并不定义 API 本身的接口形状，API Reference 在 `docs/docs.json` 中作为单独 tab 配置，来源是 OpenAPI 配置；开发者目录只负责说明“调用 API 前如何获得凭证”。

第二段是 scraping 代码编写流程：生成代码运行时使用 `Harambe` SDK，脚本通过 `save_data` 保存并校验符合 schema 的数据，通过 `enqueue` 把后续 URL 加入队列，通过 `paginate` 处理翻页，通过 `log` 输出调试信息。对应主文档是 `docs/developers/sdk.mdx`。根据当前片段推断，Reworkd 的爬取模型不是单页脚本一次性抓完，而是围绕 schema、URL 队列、stage/run 等概念组织；依据是 `sdk.mdx` 明确提到 schema validation、enqueue、pagination，而邻近的 `docs/key-concepts.mdx` 标题结构包含 `Groups`、`Jobs`、`Stages`、`Run`。

第三段是文件捕获和下载流程：当目标数据包含文件时，脚本需要根据链接类型选择保存 URL、捕获跳转 URL 或直接在浏览器上下文捕获下载。`docs/developers/file-downloads.mdx` 给出场景策略，`docs/developers/sdk.mdx` 提供底层方法说明，例如 `capture_url`、`capture_download`、`capture_html`、`capture_pdf`。另外，邻近的 `docs/features/file-downloads.mdx` 从产品功能角度说明下载设置、文件获取、文件存储等内容；开发者目录中的下载页更偏代码策略，features 目录中的下载页更偏平台能力说明。

## 推荐阅读顺序

建议先读 `docs/introduction.mdx`，建立 Reworkd 是“Extract web data at scale”的整体印象。接着读 `docs/key-concepts.mdx`，理解 `Groups`、`Jobs`、`Stages`、`Run` 这些运行模型词汇，否则 `enqueue`、stage、run 等开发者文档里的概念会显得孤立。

然后读 `docs/schemas.mdx`，因为 `sdk.save_data` 的核心行为是保存数据并校验当前 schema。如果不了解 schema 的字段类型和好 schema 的判断标准，很难正确理解为什么保存数据时会抛出 `SchemaValidationError`。

进入 `docs/developers` 后，先读 `docs/developers/api-keys.mdx`，解决 API 调用认证问题。再读 `docs/developers/sdk.mdx`，重点关注 `save_data`、`enqueue`、`paginate` 三个基础方法，然后再看 `capture_url`、`capture_download`、`capture_html`、`capture_pdf` 等专项能力。最后读 `docs/developers/file-downloads.mdx`，把 SDK 方法映射到具体下载场景。

如果学习目标是“开发一个可运行的 scraping 任务”，推荐顺序是：`key-concepts`、`schemas`、`developers/sdk`、`developers/file-downloads`。如果学习目标是“调用 Reworkd API”，则先看 `developers/api-keys`，再转到 API Reference。

## 常见误区

第一个误区是把 `docs/developers` 当成完整 API 文档。它只讲 API Key 和开发者用法概览，具体接口定义不在这个目录中，而是在文档导航的 `API Reference` tab 下通过 OpenAPI 配置提供。

第二个误区是把 `sdk.mdx` 理解为 Reworkd 源码中的 SDK 实现。这个文件只是文档说明，真正的 `Harambe` SDK 实现不在当前目录。这里能学到的是 Reworkd 期望开发者如何调用 SDK，而不是 SDK 内部如何实现分页、去重、下载捕获或 schema 校验。

第三个误区是手写分页循环。`sdk.mdx` 明确强调分页应使用 `sdk.paginate`，并让调用者提供返回下一页 URL 或元素的函数。按照文档意图，手动写复杂的 for loop 或 if 分支不是推荐路径。

第四个误区是混淆“保存下载 URL”和“直接下载文件”。在常规下载链接场景中，文档建议保存 URL，由平台异步访问和下载；但对于 JavaScript 动态下载或必须保持浏览器 session 的下载，应使用 `capture_download` 在当前浏览器上下文中捕获。

第五个误区是忽略 schema 对 `save_data` 的约束。`save_data` 不是简单写入任意字典，它会验证保存的数据是否符合当前 schema；字段缺失、类型不匹配或结构错误都可能导致 `SchemaValidationError`。
