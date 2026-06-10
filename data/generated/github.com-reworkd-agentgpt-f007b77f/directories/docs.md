# 目录：docs

## 它负责什么

`docs` 是这个仓库里的产品文档站内容目录，主要用于介绍 Reworkd 的概念、功能、导出方式和开发者接入方式。它不是主应用运行时代码，也不包含业务后端、前端页面或数据库模型；这些更可能分布在 `next`、`platform`、`cli`、`db` 等目录中。`docs` 的核心角色是“面向用户和开发者的文档源”，采用 `MDX` 内容文件配合 `docs/docs.json` 进行导航、主题、图标、Logo、API Reference 入口等配置。

从内容看，这套文档描述的是 Reworkd 的网页数据抽取产品：用户创建 group、定义 schema、配置 jobs 和 runs，通过 LLM 与 scraping SDK 进行网页抓取，并通过 API 或批量导出拿到数据。文档里还保留了 AgentGPT 的提示，说明这个仓库历史上或品牌上与 AgentGPT 有关联，但 `docs` 当前重点已经转向 Reworkd 产品文档。

## 直接子目录地图

`docs/developers` 面向开发者接入。它包含 API key 创建、SDK 使用、文件下载代码策略等内容。这里的文档更接近“怎么写代码、怎么认证、怎么处理特殊下载场景”。

`docs/features` 面向产品功能说明。它覆盖 deduplication、scheduling、templates、file-downloads 等功能页，解释用户在平台内会遇到的功能概念、配置方式和行为规则。

`docs/features/exports` 是 `features` 下的一个专题子目录，专门讲数据导出。它把导出拆成 overview、API exports、bulk exports 三个层次：先说明导出总览，再区分通过 API 增量拉取和通过 UI 批量导出。

`docs/images` 存放文档站使用的图片资源，例如 banner、logo、organization menu 截图等。它服务于 MDX 页面里的 `<img>`、Logo 配置和说明截图，不承担业务逻辑。

## 关键入口

`docs/docs.json` 是最关键的文档站配置入口。它定义了 Mintlify 风格的站点元信息，包括主题、站点名、颜色、favicon、Logo、顶部导航、侧边栏分组、外部锚点、API Reference 的 OpenAPI 来源、页脚社交链接等。阅读 `docs` 时应先看这个文件，因为它给出了真实的文档组织结构，而不仅是文件系统结构。

`docs/introduction.mdx` 是用户进入文档后的概览入口。它介绍 Reworkd 的定位：使用 LLM 解析、理解和操作网页，以规模化抽取网页数据。页面还通过卡片把读者引向 “Build your first scraper”、`key-concepts`、exports 和 blog 等入口。注意最终文档站里这些卡片会作为导航元素出现，不只是普通文本。

`docs/key-concepts.mdx` 是概念入口，解释 group、schema、job、stage、run 等核心模型。它承担理解整套产品流程的基础作用：先有 group 和统一 schema，再把不同 source URL 表示为 jobs，job 按 stage 推进并产生 run 和 outputs。

`docs/schemas.mdx` 是数据结构入口，讲 schema 字段类型、字段设计原则和缺失字段处理。它和抓取质量、数据一致性、去重键选择都有关系。

`docs/README.md`、`docs/README.zh-HANS.md`、`docs/README.hu-Cs4K1Sr4C.md` 看起来是文档根部的 README 变体或遗留入口；其中当前片段里 `docs/README.md` 没有实际内容。根据当前片段推断，真正驱动文档站导航的是 `docs/docs.json`，不是这些 README 文件。

## 主流程位置

用户理解主流程时，应从 `docs/introduction.mdx` 进入，再到 `docs/key-concepts.mdx` 建立产品模型。主流程大致是：创建 group，定义 schema，把 source URLs 放入 jobs，jobs 按 category、listing、detail 等 stages 抓取页面，运行时生成 runs 和 outputs，最后通过 exports 或 API 把数据取出。

抓取代码与 SDK 使用的主流程在 `docs/developers/sdk.mdx`。该页围绕 Harambe SDK 展开，重点方法包括 `save_data`、`enqueue`、`paginate` 等。`save_data` 对应保存并校验结构化数据，`enqueue` 对应发现后续 URL 并进入下一阶段，`paginate` 对应列表页翻页处理。根据当前片段推断，这些方法是文档中最接近“抓取执行流程”的描述，实际实现不在 `docs` 目录中。

导出主流程在 `docs/features/exports/overview.mdx`、`docs/features/exports/api-exports.mdx`、`docs/features/exports/bulk-exports.mdx`。API exports 更适合持续增量同步，文档提到通过 `created_after` 参数只取上次同步之后的新数据；bulk exports 更适合一次性获得某个 group 或 job 的完整快照。

文件下载流程分成用户功能说明和开发者实现说明两层。`docs/features/file-downloads.mdx` 讲如何在 schema 中配置 URL 字段并启用下载，以及导出结果里的 `files` 信息；`docs/developers/file-downloads.mdx` 讲实际 scraper 代码如何处理直链下载、间接下载、JavaScript 动态下载、需要 cookie/session 的下载。

## 推荐阅读顺序

1. 先读 `docs/docs.json`，把文档站导航和分组结构看清楚。这里能看到 Get Started、Features、Developers、API Reference 的整体布局。
2. 再读 `docs/introduction.mdx`，了解 Reworkd 文档的产品定位和面向对象。
3. 接着读 `docs/key-concepts.mdx`，掌握 group、schema、job、stage、run 的关系。没有这些概念，后面的 scheduling、deduplication、exports 很容易混在一起。
4. 然后读 `docs/schemas.mdx`，理解输出数据为什么依赖 schema，以及字段设计如何影响抽取质量。
5. 功能层按 `docs/features/deduplication.mdx`、`docs/features/scheduling.mdx`、`docs/features/templates.mdx`、`docs/features/file-downloads.mdx` 阅读，建立平台能力地图。
6. 导出专题读 `docs/features/exports/overview.mdx`，再读 `api-exports.mdx` 和 `bulk-exports.mdx`。
7. 如果目标是写集成代码，再进入 `docs/developers/api-keys.mdx`、`docs/developers/sdk.mdx`、`docs/developers/file-downloads.mdx`。

## 常见误区

不要把 `docs` 当成产品实现目录。这里的 `.mdx` 文件描述概念、流程和用法，不是前端应用、API 服务或爬虫 SDK 的实现源码。要找真实应用逻辑，应转向 `next`、`platform`、`cli` 等目录。

不要只按文件名阅读而忽略 `docs/docs.json`。文档站展示顺序、分组和 API Reference 入口由 `docs/docs.json` 控制，文件系统顺序不等于读者看到的导航顺序。

不要误以为所有链接都在仓库内实现。`docs/docs.json` 和若干 MDX 卡片里引用了外部站点、外部应用页面、外部 OpenAPI 地址和外部代码仓库；这些在当前学习文档中统一视为外部入口 `[URL已移除]`，不能从本仓库直接推出其实现细节。

不要把 `features/file-downloads.mdx` 和 `developers/file-downloads.mdx` 混为一谈。前者讲产品层“如何配置和获取下载文件”，后者讲开发者层“scraper 代码如何捕获下载地址或下载事件”。

不要认为 `features/exports` 是普通叶子功能。它是一个二级专题，连接 API Reference、批量导出和数据消费流程，是用户把抓取结果带出系统的关键路径。
