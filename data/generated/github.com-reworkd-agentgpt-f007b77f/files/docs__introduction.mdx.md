# 文件：docs/introduction.mdx

## 一句话定位

`docs/introduction.mdx` 是 Mintlify 文档站的首页/入门页，负责用最短路径介绍 Reworkd 的产品定位，并把读者导向初次抓取、核心概念、数据导出和博客等关键入口。

## 它暴露/定义了什么

这个文件暴露的是一个 MDX 文档页面，而不是 TypeScript/Python 运行时代码。它主要定义三类内容：

第一类是 frontmatter 元数据：`title: Introduction` 和 `description: Reworkd - Extract web data at scale`。这些字段会被 Mintlify 文档构建系统读取，用于页面标题、SEO 描述、导航展示或搜索索引。

第二类是页面首屏视觉：`<Frame>` 包裹 `/images/banner.png`，用作产品介绍页的主视觉。该图片路径对应 `docs/images/banner.png`，属于文档站静态资源。

第三类是内容和导航卡片：正文说明 Reworkd 使用 LLM 理解并交互网页，帮助用户大规模抓取网页数据；`<Info>` 提示 AgentGPT 相关信息转到 GitHub；`<CardGroup>` 和多个 `<Card>` 提供后续阅读入口，包括首次构建 scraper、关键术语、导出数据和博客。

## 谁调用它

直接调用关系来自 `docs/docs.json`。在 `navigation.tabs` 的 `Documentation` 标签下，`Get Started` 分组的 `pages` 数组把 `"introduction"` 放在第一位。根据 Mintlify 的约定，这意味着文档站构建/运行时会把 `docs/introduction.mdx` 解析成 `introduction` 页面，并作为入门分组的首个页面展示。

根据当前片段推断，它还可能是访问文档根入口时默认推荐的首页，因为它位于 Get Started 第一项，并且页面标题、内容都承担“Introduction”职责。但仓库中没有看到 Mintlify 托管侧的路由实现，因此默认首页映射只能基于 `docs/docs.json` 的导航顺序和 Mintlify 常见约定推断。

## 它调用谁

这个 MDX 文件“调用”的对象主要是 Mintlify 提供的内置 MDX 组件和静态资源，而不是本仓库里的函数。

它使用 `<Frame>` 渲染带框视觉区域，内部引用 `/images/banner.png`。它使用 `<Info>` 渲染提示块，承载 AgentGPT 的说明。它使用 `<CardGroup cols={2}>` 建立两列卡片布局，并通过 `<Card>` 定义四个跳转入口。`Card` 的 `icon` 字段依赖 Mintlify 支持的图标名，例如 `lightbulb`、`brain`、`globe`、`rss`。`href` 字段既包含站内路径，如 `/key-concepts`、`/features/exports/overview`，也包含外部地址；文档中不展开真实网址。

此外，它依赖 `docs/docs.json` 中的全局主题、logo、favicon、导航、API Reference 和社交链接配置。页面本身不 import 这些配置，但 Mintlify 构建文档站时会把两者组合成最终站点。

## 核心流程

构建流程可以概括为：Mintlify 读取 `docs/docs.json`，发现 `Documentation` 标签页下的 `Get Started` 分组包含 `introduction`；随后解析 `docs/introduction.mdx` 的 frontmatter，生成页面标题和描述；再把 MDX 内容交给 Mintlify 的 MDX 渲染器，将 `<Frame>`、`<Info>`、`<CardGroup>`、`<Card>` 转成文档站 UI；最后把 `/images/banner.png` 等静态资源挂载到文档站资源路径中。

用户访问流程则是：进入文档站后，在 Documentation/Get Started 下看到 Introduction；打开页面后先看到 banner 和产品一句话价值说明；如果用户寻找 AgentGPT 信息，会被 `Info` 块引导到 GitHub；如果用户继续学习 Reworkd，则通过四张卡片进入教程、概念、导出能力或博客。

## 关键函数的高层作用

本文件没有定义 JavaScript/TypeScript 函数，也没有导出类或 API。这里的“关键函数”可理解为关键 MDX 组件的页面职责：

`Frame` 的高层作用是承载首屏图片，让产品介绍有视觉锚点。它只包裹一个 `img`，没有复杂逻辑。

`Info` 的高层作用是放置重要提示，避免读者把 Reworkd 文档和 AgentGPT 文档混淆。它承担的是分流职责。

`CardGroup` 的高层作用是组织下一步路径，`cols={2}` 指定卡片区以两列布局展示。它决定入门页下半部分的信息架构。

`Card` 的高层作用是定义单个推荐入口，包括标题、图标、跳转地址和一句说明。四个卡片分别对应教程起步、术语学习、导出功能和更新资讯。

`img` 是普通 HTML 元素，用于引用 `/images/banner.png`。它没有 `alt` 文本，若提升可访问性，这是一个可改进点。

## 修改风险

最大风险是导航和页面路径不一致。`docs/docs.json` 中引用的是 `"introduction"`，因此重命名 `docs/introduction.mdx`、移动文件或改变 slug 相关约定，都会导致导航失效或页面 404。

第二个风险是 Mintlify 组件兼容性。`Frame`、`Info`、`CardGroup`、`Card` 属于文档平台组件；如果替换为非支持组件、写错属性名、传入不支持的 `icon`，页面可能构建失败或样式退化。

第三个风险是链接稳定性。卡片中有站内路径 `/key-concepts`、`/features/exports/overview`，这些路径依赖对应 MDX 文件存在；如果调整 `docs/key-concepts.mdx` 或 `docs/features/exports/overview.mdx` 的位置，需要同步更新本页。外部链接虽然不影响构建，但会影响用户分流和品牌可信度。

第四个风险是产品定位漂移。该页明确把 Reworkd 描述为用 LLM 大规模解析、理解和交互网页以抓取数据的产品。如果实际产品能力、商业定位或 AgentGPT 与 Reworkd 的关系发生变化，首页文案需要优先更新，否则会误导新用户。

第五个风险是资源引用。`/images/banner.png` 来自 `docs/images/banner.png`。删除、压缩出错或改名会让首页主视觉缺失。由于这是 introduction 页首屏内容，视觉资源损坏会比普通内页图片更明显。

第六个风险是合规与可访问性。当前 `img` 没有 `alt` 属性；若文档站对可访问性有要求，建议补充简短替代文本。同时，外部链接集中出现于首页，修改时应避免泄露错误环境地址、过期营销链接或不再维护的仓库入口。
