# 文件：website/docs/index.mdx

## 一句话定位

`website/docs/index.mdx` 是 Hermes Agent 文档站的 docs 首页内容文件：它把产品定位、安装入口、快速导航、核心能力和面向 LLM 的机器可读入口集中到 Docusaurus 文档根路由。

## 它暴露/定义了什么

这个文件主要定义一个 MDX 文档页，而不是业务代码模块。顶部 frontmatter 暴露给 Docusaurus 的元数据包括：`slug: /` 将页面绑定到文档根路径，`sidebar_position: 0` 表示它在侧边栏中的优先位置，`title` 和 `description` 用于页面标题、SEO 和文档索引，`hide_table_of_contents: true` 关闭右侧目录，`displayed_sidebar: docs` 指定展示 `docs` 侧边栏。

正文暴露的是文档首页的信息架构：`# Hermes Agent` 作为首屏标题；安装命令区分 Linux/macOS/WSL2、Windows PowerShell、Android Termux；`Quick Links` 表格把用户导向安装、快速开始、配置、消息网关、工具、记忆、技能、MCP、语音、安全、架构、FAQ 等页面；`Key Features` 以项目卖点方式总结学习闭环、运行环境、消息平台、模型供应商、定时任务、子代理、技能、Web 控制、MCP 和研究用途；最后说明 `/llms.txt` 与 `/llms-full.txt` 这两个面向 LLM/编码代理的入口。

## 谁调用它

直接消费它的是 Docusaurus 的 docs 插件。根据 `website/docusaurus.config.ts`，站点使用 classic preset，`docs.routeBasePath: '/'`，同时站点 `baseUrl` 是 `/docs/`，所以该文件的 `slug: /` 会成为文档站 `/docs/` 下的首页。`website/package.json` 中的 `npm run start` 和 `npm run build` 会先执行 `scripts/prebuild.mjs`，再启动或构建 Docusaurus；构建阶段 Docusaurus 扫描 `website/docs`，解析这个 MDX 文件并生成页面。

侧边栏由 `website/sidebars.ts` 定义，`displayed_sidebar: docs` 指向其中的 `docs` sidebar。根据当前片段推断，这个首页不依赖 `sidebars.ts` 中显式列出自己的 doc id，而是通过 `slug` 和 Docusaurus 文档发现机制成为根页；依据是 `sidebars.ts` 顶层首先列出的是 `user-stories`，而不是 `index`。

## 它调用谁

MDX 层面它只显式 `import Link from '@docusaurus/Link'`，用于渲染 “Get Started” 内部导航按钮。其余导航多数是 Markdown 链接或普通 HTML `<a>` 标签。文件还依赖 Docusaurus/MDX 语法能力：frontmatter、Markdown 标题、表格、代码块、admonition `:::tip`、内联 HTML 和 React 组件混写。

内容上，它指向许多站内文档路径，例如 `getting-started/installation`、`getting-started/quickstart`、`user-guide/configuration`、`user-guide/features/tools`、`developer-guide/architecture`、`reference/faq` 等。它还提到仓库、Nous Research、OpenRouter、agentskills.io 等外部目的地；在本文档中这些真实 URL 不展开，统一视作外部链接占位 `[URL已移除]`。

## 核心流程

页面加载流程可以概括为：Docusaurus 读取 `website/docs/index.mdx`，先解析 frontmatter 确定路由、标题、描述、侧边栏和目录行为；再编译 MDX，将 Markdown、HTML、admonition 和 `@docusaurus/Link` 组件转换成 React 页面；构建时结合 `website/docusaurus.config.ts` 的 `baseUrl`、`routeBasePath`、主题和搜索插件配置，产出文档首页。

用户阅读流程则是典型入口页：先看到项目一句话定位和两个行动按钮；然后看到最短安装命令；再通过 tip 被引导到 `hermes setup --portal`；接着用一段文字解释 Hermes 与普通 IDE copilot 或聊天机器人不同；之后通过 Quick Links 进入具体任务页面；最后用 Key Features 建立产品能力地图，并给 LLM/编码代理提供机器可读文档入口。

## 关键函数的高层作用

这个文件没有定义传统意义上的函数或类。真正关键的“可执行单元”是 MDX 结构和 `Link` 组件。

`Link` 的作用是生成 Docusaurus 感知的站内导航链接，用在 “Get Started” 按钮上。相比普通 `<a>`，它更适合站内路由跳转，能配合 Docusaurus 的客户端导航和 base path 处理。

frontmatter 是本页最重要的配置单元：`slug` 决定首页身份，`description` 影响搜索和 SEO，`displayed_sidebar` 决定页面打开时展示哪套导航，`hide_table_of_contents` 让首页保持落地页式布局而不是普通长文目录页。

Markdown 表格和 bullet list 是信息组织单元：`Quick Links` 是用户任务分流器，`Key Features` 是产品能力摘要。它们不是函数，但修改时会直接影响首页的信息架构和新用户理解路径。

## 修改风险

最大风险是路由和导航破坏。改动 `slug: /`、`displayed_sidebar: docs`、`hide_table_of_contents` 或 `docs.routeBasePath` 的配合关系，可能导致文档首页位置变化、侧边栏异常或旧链接失效。尤其这是 docs 根页，任何路径错误都会影响用户进入文档的第一屏。

第二类风险是链接失效。`Quick Links` 覆盖大量站内页面，如果目标文档重命名、移动或删除，这里会产生断链。当前 Docusaurus 配置中 `onBrokenLinks: 'warn'`，断链可能只警告而不阻断构建，因此修改后需要主动检查构建输出。

第三类风险是内容与实际能力漂移。首页列出的平台数量、工具数量、供应商、安装方式、Windows beta 状态、`llms.txt` 大小等都属于易过期产品信息。修改功能文档或实现后，如果不同步更新首页，用户会形成错误预期。

第四类风险是 MDX/HTML 混写带来的构建问题。按钮区域使用内联 style、`Link` 组件和 `<a>` 标签混排；如果 JSX 语法、属性名或引号写错，会让 MDX 编译失败。admonition、代码块和表格也要保持 Docusaurus 支持的语法。

第五类风险是外部链接和品牌表述。首页含有多个外部服务、社区、模型供应商和安装脚本入口，改动时要避免泄露错误 URL、使用过期品牌名，或把外部链接替换成不受控目的地。对于安装命令尤其要谨慎，因为它直接影响用户机器上的执行路径。
