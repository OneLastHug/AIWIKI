# 目录：website

## 它负责什么

`website` 是 Hermes Agent 的文档站点目录，整体采用 Docusaurus 3 构建。它不是主程序运行时代码，而是面向用户、贡献者和集成开发者的说明站：安装、CLI/TUI 使用、配置、功能指南、插件/工具/Provider 开发、参考手册、技能目录，以及少量站点级 React 页面。

从 `website/package.json` 可以看到主要命令是 `start`、`build`、`serve`、`typecheck`，并且 `prestart`、`prebuild` 都会先执行 `scripts/prebuild.mjs`。这说明文档站的构建流程并不只是把 `docs` 编译成网页，还会在构建前生成或刷新一部分派生文档内容。根据当前片段推断，技能目录和 LLM 友好文本很可能由 `website/scripts` 下的脚本从仓库其他目录提取生成，依据是存在 `generate-skill-docs.py`、`extract-skills.py`、`generate-llms-txt.py` 这类预构建脚本。

站点支持英文和简体中文国际化，配置在 `website/docusaurus.config.ts` 的 `i18n` 字段中；实际中文翻译资源入口在 `website/i18n/zh-Hans`。搜索、Mermaid 图、代码高亮、自定义 CSS、导航栏、页脚、侧边栏都在 Docusaurus 配置层集中控制。

## 直接子目录地图

`website/docs` 是文档正文的主目录。它按主题拆分为 `getting-started`、`user-guide`、`guides`、`developer-guide`、`integrations`、`reference` 等板块。`docs/index.mdx` 是文档首页，`docs/user-stories.mdx` 是用户故事页。这里是学习 Hermes Agent 使用方式和内部架构的第一资料源。

`website/docs/getting-started` 放入门路径，包括快速开始、安装、Termux、Nix、升级、学习路线等。适合先建立“怎么跑起来”的全局认识。

`website/docs/user-guide` 放使用手册，覆盖 `cli`、`tui`、配置、模型配置、会话、profile、Docker、安全、回滚等主题。其下还有 `features`、`messaging`、`secrets`、`skills` 等更细分目录，分别承载功能说明、消息平台、密钥管理和自动生成或归档的技能说明。

`website/docs/developer-guide` 面向贡献者和扩展开发者，包含架构、agent loop、工具运行时、Provider 运行时、插件开发、网关内部、压缩缓存、session 存储、prompt 组装等文档。它和仓库根目录中的 `run_agent.py`、`model_tools.py`、`gateway`、`plugins`、`tools` 等源码区域关系最密切。

`website/docs/guides` 是任务型教程集合，例如 cron 自动化、插件构建、不同模型服务接入、本地模型、MCP、语音模式、团队 Telegram 助手、GitHub PR review agent 等。它更像“按场景操作”的 cookbook。

`website/docs/reference` 是查询型资料，包括 CLI 命令、slash commands、环境变量、MCP 配置、模型目录、技能目录、工具与 toolsets 参考、FAQ 等。这里通常不适合从头读，而适合遇到具体参数或命令时查。

`website/docs/integrations` 是集成页，目前从浅层文件看包括 provider 概览和 Nous Portal 相关说明。

`website/src` 是站点自定义前端代码。当前浅层结构很轻，主要有 `src/pages/skills/index.tsx` 作为自定义技能页，`src/components/UserStoriesCollage` 作为用户故事展示组件，`src/data/userStories.json` 作为展示数据，`src/css/custom.css` 作为全站样式覆盖。

`website/static` 放静态资源。`static/img` 包含 logo、favicon、站点 banner、文档插图和 Kanban 教程截图；`static/api/model-catalog.json` 是可直接作为静态文件发布的模型目录数据。

`website/scripts` 放构建前辅助脚本。根据文件名可知，核心职责包括技能文档生成、技能信息提取、生成 `llms.txt` 类文本，以及由 `prebuild.mjs` 串联预构建步骤。

`website/i18n` 放 Docusaurus 国际化资源，目前有 `zh-Hans`。它不是另一套完整源码，而是翻译层，与 `docs` 和站点配置共同决定多语言输出。

## 关键入口

`website/package.json` 是开发入口，定义站点命令和依赖。常用路径是 `npm start` 启动开发站，`npm run build` 构建静态站，`npm run typecheck` 做 TypeScript 检查。`prestart` 和 `prebuild` 都会调用 `scripts/prebuild.mjs`，因此生成类文档问题要先看这里。

`website/docusaurus.config.ts` 是站点总配置入口。它定义标题、站点基础路径、Docusaurus preset、文档路由、语言、搜索插件、Mermaid、导航栏、页脚、主题、代码高亮语言和自定义 CSS。文档路由的关键设置是 `docs.routeBasePath: '/'`，表示文档内容在站点自身 base path 下作为根内容呈现。

`website/sidebars.ts` 是文档导航入口。它手写组织了 Getting Started、Using Hermes、Features、Skills、Developer Guide、Guides、Integrations、Reference 等导航结构。需要注意，技能目录部分非常长，包含大量 `user-guide/skills/bundled/...` 与 `user-guide/skills/optional/...` 条目，明显是目录索引性质，不应把它当成普通手写导航逐项阅读。

`website/docs/index.mdx` 是文档首页入口；`website/src/pages/skills/index.tsx` 是非 docs 体系下的自定义页面入口，对应导航中的 `Skills` 页面；`website/src/css/custom.css` 是视觉样式入口；`website/static/api/model-catalog.json` 是模型目录静态数据入口。

## 主流程位置

文档站的主流程可以按“内容源到构建产物”理解：开发者编辑 `website/docs`、`website/src`、`website/static`；执行 `npm start` 或 `npm run build` 时，`package.json` 先触发 `scripts/prebuild.mjs`；预构建脚本再根据需要调用 Python 脚本生成技能目录、提取技能元数据或生成面向 LLM 的文本；随后 Docusaurus 读取 `docusaurus.config.ts`、`sidebars.ts`、`docs`、`src/pages`、`static` 和 `i18n`，生成最终站点。

导航流程主要由 `sidebars.ts` 决定。`docs` preset 读取 `sidebarPath: './sidebars.ts'`，导航栏中的 `type: 'docSidebar'` 指向 `sidebarId: 'docs'`，因此侧边栏结构和文档路由的核心关系在 `sidebars.ts` 与 `docusaurus.config.ts` 之间。

内容维护流程大致分三类。第一类是手写说明，如 `getting-started`、`user-guide`、`developer-guide`、`guides`、`reference` 中大部分 Markdown。第二类是站点交互或展示页面，如 `src/pages/skills/index.tsx`、`src/components/UserStoriesCollage/index.tsx`。第三类是生成内容，尤其是技能目录相关文档和静态目录数据，入口集中在 `scripts`，产物位置则分散到 `docs/user-guide/skills`、`docs/reference` 或 `static/api`。

## 推荐阅读顺序

1. 先读 `website/package.json`，理解站点怎么启动、构建、检查，以及哪些脚本会在构建前自动运行。

2. 再读 `website/docusaurus.config.ts`，掌握站点级配置：文档根路由、语言、搜索、主题、导航栏、页脚和自定义 CSS。

3. 接着读 `website/sidebars.ts`，不要陷入技能长列表，只看顶层分类和主要文档板块，建立站点信息架构。

4. 然后读 `website/docs/index.mdx`、`website/docs/getting-started/quickstart.md`、`website/docs/getting-started/learning-path.md`，了解文档站希望新用户怎样进入 Hermes Agent。

5. 如果目标是使用 Hermes，继续读 `website/docs/user-guide/cli.md`、`website/docs/user-guide/tui.md`、`website/docs/user-guide/configuration.md`、`website/docs/user-guide/configuring-models.md` 和 `website/docs/user-guide/features/overview.md`。

6. 如果目标是改源码或扩展系统，转向 `website/docs/developer-guide/architecture.md`、`website/docs/developer-guide/agent-loop.md`、`website/docs/developer-guide/tools-runtime.md`、`website/docs/developer-guide/provider-runtime.md`、`website/docs/developer-guide/creating-skills.md`。

7. 最后把 `website/docs/reference` 当查询手册使用，把 `website/docs/guides` 当场景教程使用，把 `website/scripts` 当生成链路排查入口使用。

## 常见误区

不要把 `website` 当成 Hermes Agent 的运行时核心。Agent 循环、工具注册、CLI、TUI、gateway、插件加载等源码主要在仓库根目录、`agent`、`tools`、`plugins`、`gateway`、`ui-tui` 等位置；`website` 负责解释和发布这些能力。

不要逐项阅读 `sidebars.ts` 里的技能条目。技能列表数量很大，并且搜索配置还专门排除了自动生成的单技能页面，说明这些页面容易淹没更核心的文档。概览阶段只需要理解 `Skills` 是一个大分类，具体技能按需查。

不要只改 `docs` 而忽略 `sidebars.ts`。新增手写文档如果要出现在侧边栏，通常需要在 `sidebars.ts` 中挂到合适分类；自动生成类文档则要确认 `scripts/prebuild.mjs` 和相关 Python 脚本的生成规则。

不要把 `src/pages` 和 `docs` 混为一谈。`docs` 是 Docusaurus 文档内容，受 docs preset 和侧边栏控制；`src/pages/skills/index.tsx` 这类文件是自定义 React 页面，路由和布局逻辑不同。

不要在文档中随意写外部链接或站点地址。当前配置里确实包含站点、仓库、社区等外部地址，但在本学习文档语境下应只描述它们的角色，不直接展开真实地址。

不要认为中文目录是完整副本。`i18n/zh-Hans` 是 Docusaurus 国际化资源，具体哪些页面已翻译、哪些仍回退到英文，需要结合 Docusaurus 的 i18n 机制和实际翻译文件判断。
