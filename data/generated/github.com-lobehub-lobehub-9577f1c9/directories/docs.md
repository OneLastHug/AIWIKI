# 目录：docs

## 它负责什么

`docs` 是 LobeHub 仓库内的产品与开发文档内容源，主要承载用户使用指南、自部署指南、开发者指南、更新日志、术语表和 Wiki 首页等 Markdown/MDX 文档。它不是应用运行时代码目录，也不是 Next.js App Router 的页面目录；从当前片段看，它更多像“文档内容仓库”：由脚本进行 i18n、SEO、CDN 图片处理、MDX lint 和 changelog 工作流处理，再被官网文档系统或发布流程消费。

根 `package.json` 中与它直接相关的脚本包括 `docs:i18n`、`docs:seo`、`docs:cdn`、`lint:mdx`、`workflow:docs`、`workflow:docs-cdn`、`workflow:mdx`、`workflow:changelog`、`workflow:changelog:gen`。其中 `lint:mdx` 明确扫描 `docs/**/*.mdx`，`db:visualize` 使用 `docs/development/database-schema.dbml` 生成数据库结构可视化文档。由此可以判断，`docs` 既是文案源，也是若干自动化文档工作流的输入。

## 直接子目录地图

`docs/changelog` 是产品更新日志目录。文件以日期加主题命名，例如 `2026-05-19-chief-agent-operator.mdx` 与对应的 `2026-05-19-chief-agent-operator.zh-CN.mdx`。目录内还有 `index.json` 和 `schema.json`，用于更新日志索引与结构约束。这里适合从产品版本演进角度理解功能发布节奏，但不要把它当作代码实现入口。

`docs/development` 是开发者文档目录。根下有 `start.mdx`、`start.zh-CN.mdx` 和 `database-schema.dbml`，子目录包含 `basic`、`internationalization`、`others`、`state-management`、`tests`。它面向参与开发的人，覆盖起步、基础规范、国际化、状态管理、测试和其他工程约定。数据库结构可视化的源文件也放在这里。

`docs/self-hosting` 是自部署文档目录。根下有 `start.mdx`、`auth.mdx`、`environment-variables.mdx` 及中文版本，子目录包括 `advanced`、`auth`、`environment-variables`、`examples`、`faq`、`migration`、`platform`。它围绕部署者视角组织，从快速开始到认证、环境变量、平台差异、迁移、示例和常见问题。

`docs/usage` 是终端用户使用文档目录。根下有 `start.mdx`、`help.mdx`、`providers.mdx`、`migrate-from-local-database.mdx` 及中文版本，子目录包括 `agent`、`channels`、`community`、`getting-started`、`messenger`、`providers`、`user-interface`。它解释产品怎么用、模型服务商如何配置、界面与 Agent 能力如何理解。

`docs/wiki` 当前片段中主要看到 `HOME.md` 和 `HOME.zh-CN.md`，更像 Wiki 入口页或外部 Wiki 内容的同步入口，而不是完整文档树。

此外，`docs` 根部还有 `glossary.md`、`glossary.zh-CN.md`，用于术语表；`.cdn.cache.json` 则与文档资源 CDN 处理流程相关，不应按普通说明文档阅读。

## 关键入口

阅读入口首先是各分区的 `start` 文件：`docs/usage/start.mdx`、`docs/usage/start.zh-CN.mdx`、`docs/self-hosting/start.mdx`、`docs/self-hosting/start.zh-CN.mdx`、`docs/development/start.mdx`、`docs/development/start.zh-CN.mdx`。这些文件通常承担对应文档分区的总览或入门导航角色。

更新日志入口是 `docs/changelog/index.json`。它和 `docs/changelog/schema.json` 一起说明 changelog 不只是零散 MDX，而是有索引和结构校验的集合。具体发布文章再落到 `docs/changelog/YYYY-MM-DD-topic.mdx` 与 `*.zh-CN.mdx`。

术语入口是 `docs/glossary.md` 和 `docs/glossary.zh-CN.md`。如果阅读业务概念时遇到专有词，应优先回到这里核对命名，而不是只根据 UI 文案猜测含义。

开发数据库视角的入口是 `docs/development/database-schema.dbml`。根脚本 `db:visualize` 直接引用它，说明该文件用于数据库结构文档化或可视化。

## 主流程位置

文档编写主流程大致是：在 `docs` 下按主题选择分区，编写或更新 `.mdx` / `.md` 内容，维护英文与 `zh-CN` 双语版本，再通过根脚本做格式、链接、资源与元信息处理。根据当前片段推断，依据是 `package.json` 中的 `docs:i18n`、`docs:seo`、`docs:cdn` 和 `lint:mdx`。

MDX 质量检查主流程在 `lint:mdx`：它会先跑 `workflow:mdx`，再用 `remark` 处理 `docs/**/*.mdx`，最后用 `eslint` 修复 MDX。也就是说，文档不是单纯 Markdown 文本，MDX 语法、组件用法和 lint 规则都会影响提交质量。

多语言主流程在 `docs:i18n` 和成对文件命名上。目录中大量文件采用 `xxx.mdx` 与 `xxx.zh-CN.mdx` 的模式，说明新增文档通常需要考虑英文源和中文版本的配套关系。根目录的 `glossary.md` / `glossary.zh-CN.md`、`docs/wiki/HOME.md` / `docs/wiki/HOME.zh-CN.md` 也是同一模式。

更新日志主流程在 `scripts/changelogWorkflow` 相关脚本与 `docs/changelog`。`workflow:changelog`、`workflow:changelog:gen` 指向 `scripts/changelogWorkflow/index.ts` 和 `scripts/changelogWorkflow/generateChangelog.ts`，而内容落点在 `docs/changelog`。因此，新增版本说明时应关注 changelog 的文件命名、索引 JSON 和 schema，而不是只新建一篇 MDX。

资源处理主流程与 `docs:cdn`、`workflow:docs-cdn`、`docs/.cdn.cache.json` 有关。根据当前片段推断，文档中的图片或远程资源可能会被自动 CDN 化并缓存处理结果，手工改 `.cdn.cache.json` 风险较高。

## 推荐阅读顺序

1. 先读 `docs/usage/start.zh-CN.mdx` 或 `docs/usage/start.mdx`，建立普通用户如何进入产品、如何理解功能模块的视角。
2. 再读 `docs/self-hosting/start.zh-CN.mdx`，理解部署者关心的运行环境、配置和数据迁移问题。
3. 然后读 `docs/development/start.zh-CN.mdx`，把注意力切到贡献者视角，了解开发准备、工程规范和测试入口。
4. 遇到概念不清时读 `docs/glossary.zh-CN.md`，避免把产品术语、技术术语和营销描述混在一起。
5. 想看功能演进时读 `docs/changelog/index.json`，再按日期挑选近几篇 `docs/changelog/*.zh-CN.mdx`。
6. 最后按需进入细分目录，例如状态管理看 `docs/development/state-management`，环境变量看 `docs/self-hosting/environment-variables`，模型服务商配置看 `docs/usage/providers`。

## 常见误区

不要把 `docs` 当成应用页面路由。LobeHub 的 SPA 页面主要在 `src/routes`，路由配置在 `src/spa/router`；`docs` 是文档内容源，不负责实现产品界面。

不要只改一个语言版本。当前目录大量采用英文文件与 `zh-CN` 文件成对维护，新增或调整文档时应检查对应语言是否也需要同步，否则文档站可能出现中英文内容不一致。

不要绕过 MDX 工作流。`.mdx` 文件会经过 `workflow:mdx`、`remark` 和 `eslint`，能在普通 Markdown 预览里显示不代表能通过仓库检查。

不要把 `docs/changelog` 当作随手记录。它有 `index.json` 和 `schema.json`，并且有独立 changelog workflow。新增更新日志需要考虑索引、日期、主题命名和双语版本。

不要把文档日期等同于当前代码状态。`docs/changelog` 记录的是发布叙事和功能演进，某篇更新日志提到的能力，实际实现可能已经在 `src`、`packages` 或配置中继续演化。

不要手工解释所有叶子目录。`docs` 是大目录，正确学习方式是先按 `usage`、`self-hosting`、`development`、`changelog`、`wiki` 建地图，再在具体问题出现时进入对应子树。
