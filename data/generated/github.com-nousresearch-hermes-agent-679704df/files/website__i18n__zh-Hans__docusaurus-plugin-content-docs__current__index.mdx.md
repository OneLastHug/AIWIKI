# 文件：website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/index.mdx

## 一句话定位

这是 Hermes Agent 文档站点的简体中文首页，也是 `zh-Hans` 语言环境下 docs 插件的根路由页面；它承担“产品入口 + 安装入口 + 文档导航索引”的职责，而不是某个功能模块的实现说明。

## 它暴露/定义了什么

该文件通过 MDX frontmatter 定义了一个 Docusaurus 文档页：`slug: /` 表示它挂到中文 docs 的根路径，`sidebar_position: 0` 使其在文档侧边栏中位于靠前位置，`title`、`description` 用于页面标题、SEO 与搜索索引，`hide_table_of_contents: true` 隐藏右侧目录，`displayed_sidebar: docs` 指定使用 `docs` 侧边栏。

正文层面，它定义了中文首页内容：Hermes Agent 的定位说明、快速开始按钮、安装命令、产品解释、关键文档入口表、核心功能列表，以及面向 LLM 的机器可读入口说明。它还在 MDX 中导入 `@docusaurus/Link`，用于渲染内部导航按钮。

## 谁调用它

根据当前片段推断，直接消费它的是 Docusaurus 的 `@docusaurus/plugin-content-docs`，依据是 `website/docusaurus.config.ts` 中 classic preset 的 `docs.routeBasePath: '/'`、`sidebarPath: './sidebars.ts'`，以及站点 `i18n.locales` 包含 `zh-Hans`。构建中文站点时，Docusaurus 会从 `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/` 读取本地化文档内容，并把该 `index.mdx` 作为中文文档根页。

导航层面，`website/docusaurus.config.ts` 的 navbar 使用 `docSidebar` 指向 `sidebarId: 'docs'`；而本文件 frontmatter 又声明 `displayed_sidebar: docs`。因此用户点击 Docs 导航、切换到简体中文语言环境、访问 docs 根路径时，最终会进入这个页面。`website/sidebars.ts` 没有显式列出 `index`，但 `sidebar_position: 0` 和根 slug 仍让该页成为文档首页入口。

## 它调用谁

这个文件没有运行时业务调用，也没有定义 JavaScript 函数。它主要依赖三类对象。

第一类是 Docusaurus/MDX 运行时：frontmatter 被 docs 插件解析，Markdown 标题、表格、代码块、HTML/JSX 片段由 MDX 编译器处理。

第二类是 `@docusaurus/Link`：文件顶部 `import Link from '@docusaurus/Link';`，正文中用 `<Link to="/getting-started/installation">` 生成站内路由链接，避免普通 `<a>` 在内部跳转时丢失 SPA 导航能力。

第三类是文档站已有路由和静态产物：正文链接指向安装、快速入门、配置、工具、记忆、技能、MCP、语音、安全、架构、FAQ 等页面；末尾提到 `/llms.txt` 和 `/llms-full.txt`，这些文件根据 `website/scripts/prebuild.mjs` 与 `website/scripts/generate-llms-txt.py` 的上下文，是构建前生成到 `website/static/` 的机器可读文档索引。

## 核心流程

页面渲染流程可以概括为：Docusaurus 构建时读取 `website/docusaurus.config.ts`，识别默认语言 `en` 与本地化语言 `zh-Hans`；当构建中文版本时，docs 插件扫描 `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/` 下的本地化文档；本文件因 `slug: /` 被注册为中文文档根页；MDX 编译器处理 frontmatter、Markdown、`Link` 组件和内联 JSX；最终页面挂在站点的 docs 根路径下，并使用 `docs` 侧边栏与全站导航。

用户访问时，首先看到 `# Hermes Agent` 的产品定位，然后是两个主要行动入口：内部“快速开始”按钮和外部代码仓库按钮。随后页面给出 Linux/macOS/WSL2、Windows PowerShell、Android Termux 的安装方式，再通过“快速链接”表把用户分流到安装、快速入门、学习路径、配置、消息网关、工具、记忆、技能、安全和开发者架构等主题。最后的 LLM 区域告诉自动化智能体可以读取机器友好的文档索引。

## 关键函数的高层作用

本文件没有关键函数、类或复杂算法。需要重点理解的是几个“结构性元素”的作用。

`frontmatter` 是页面注册元数据，决定路由、标题、描述、侧边栏和目录行为，是这个文件和 Docusaurus 文档系统之间的主要契约。

`Link` 组件负责站内跳转，适合 `/getting-started/installation` 这类内部 docs 路径；与普通 `<a>` 相比，它更符合 Docusaurus 的客户端路由模型。

内联 `<div>` 和样式对象用于首页顶部的两个按钮布局，属于轻量展示层代码。它不是共享组件，修改时要注意中英文首页是否保持一致。

Markdown 表格是“文档入口索引”的核心内容组织方式，维护成本低，但链接目标变更时容易产生断链或翻译不同步。

## 修改风险

最大风险是路由和本地化契约被破坏。修改 `slug: /` 会改变中文文档首页位置；修改 `displayed_sidebar: docs` 可能导致侧边栏不显示或显示错误；删除 `title`、`description` 会影响搜索、SEO 和页面元信息。

第二类风险是链接失效。该页包含大量内部文档路径，如果英文文档重组、`sidebars.ts` 调整或页面迁移，中文首页需要同步更新。外部链接也要谨慎处理；在源码中它们是真实链接，但面向安全或脱敏输出时不应直接暴露。

第三类风险是中英文内容漂移。对比 `website/docs/index.mdx` 可见，英文首页包含一个 “Fastest path to a working agent” tip，而当前中文页没有对应段落；另外英文中某些数量描述如工具数量与中文不完全一致。后续修改产品卖点、安装路径、核心功能时，应同时检查英文源页与中文本地化页，避免用户在不同语言下获得不同指引。

第四类风险是 MDX/JSX 语法错误。按钮区域使用 JSX style 对象，属性名、引号、闭合标签不正确都会导致文档构建失败。修改这部分时应运行网站构建或至少进行 MDX 语法检查。

第五类风险是安装命令的准确性。首页安装命令通常是新用户的第一操作入口，任何路径、shell、平台说明错误都会直接影响转化和支持成本。若安装脚本路径、Windows 支持状态、Termux 说明发生变化，应优先同步这里。
