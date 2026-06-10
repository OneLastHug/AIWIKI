# 文件：website/README.md

## 一句话定位

`website/README.md` 是 `website` 子项目的入口说明文件，用最小篇幅告诉贡献者这个目录是一个 Docusaurus 文档站点、如何安装依赖、启动本地开发、构建静态产物、部署到托管分支，以及文档图表 lint 的约束。

## 它暴露/定义了什么

这个文件不暴露代码 API，也不定义运行时对象；它暴露的是面向人的操作契约。核心内容包括：

1. `Website` 项目身份：说明该目录由 Docusaurus 构建，是一个静态站点工程。
2. 安装命令：`yarn`，用于安装 `website/package.json` 中定义的 Node 依赖。
3. 本地开发命令：`yarn start`，用于启动 Docusaurus dev server，并依赖热更新反馈文档和页面变化。
4. 构建命令：`yarn build`，用于生成 `build` 静态目录。
5. 部署命令：`USE_SSH=true yarn deploy` 与 `GIT_USER=<Your GitHub username> yarn deploy`，对应 Docusaurus 的部署脚本。
6. 图表 lint 规则：CI 会运行 `ascii-guard` 检查 docs 中的 ASCII box diagrams，推荐使用 Mermaid 代码块或普通列表、表格替代手写 ASCII 框图。

从仓库上下文看，README 中的命令与 `website/package.json` 的 `scripts` 对应：`start` 实际执行 `docusaurus start`，但会先触发 `prestart`；`build` 实际执行 `docusaurus build`，但会先触发 `prebuild`；`deploy` 对应 `docusaurus deploy`。因此 README 是简化版操作入口，具体行为由 npm/yarn 生命周期脚本和 Docusaurus 配置补全。

## 谁调用它

严格来说，没有源码“调用” `website/README.md`。它是文档文件，被以下角色读取或间接依赖：

1. 新贡献者或维护者：进入 `website` 目录后，通过该文件了解站点开发命令。
2. 代码托管平台的 README 渲染器：在浏览 `website` 目录时展示这份说明。
3. 维护 CI/部署流程的人：用它快速确认本地命令与 CI 中的命令是否一致。
4. 根据当前片段推断，文档作者和审查者也会依赖其中的 “Diagram Linting” 约定，避免提交触发 `ascii-guard` 失败。依据是 `.github/workflows/docs-site-checks.yml` 中确实安装 `ascii-guard` 并运行 `npm run lint:diagrams`，而 `website/package.json` 中该脚本为 `ascii-guard lint --exclude-code-blocks docs`。

CI 不读取 README 来决定流程。真正的 CI 入口在 `.github/workflows/docs-site-checks.yml`、`.github/workflows/deploy-site.yml`；README 只是把其中最常用的本地操作以更轻量的形式写给人看。

## 它调用谁

`website/README.md` 本身是 Markdown，不会执行任何调用。但它描述的命令会进入以下调用链：

1. `yarn`：读取 `website/package.json` 与 lockfile，安装 Docusaurus、React、Mermaid theme、本地搜索插件、TypeScript 等依赖。
2. `yarn start`：触发 `prestart`，即 `node scripts/prebuild.mjs`，然后运行 `docusaurus start`。
3. `yarn build`：触发 `prebuild`，同样先运行 `node scripts/prebuild.mjs`，再运行 `docusaurus build`。
4. `scripts/prebuild.mjs`：调用 `website/scripts/extract-skills.py` 生成 `static/api/skills.json`，调用 `website/scripts/generate-llms-txt.py` 生成 `llms.txt` 与 `llms-full.txt`，并尝试准备 `static/api/skills-index.json`。
5. `docusaurus.config.ts`：被 Docusaurus 读取，决定站点标题、`baseUrl`、docs 路由、国际化、Mermaid、搜索、导航栏、页脚、代码高亮等。
6. `sidebars.ts`：被 Docusaurus docs 插件读取，决定左侧文档目录结构。
7. `yarn deploy`：映射到 `docusaurus deploy`，通常面向 GitHub Pages 风格的静态部署流程。

README 中的部署说明提到了外部托管和仓库分支，但最终文档中应理解为“Docusaurus 的标准部署入口”，不要把它当作项目唯一部署流程。当前仓库还存在 GitHub Actions 部署路径：`deploy-site.yml` 会安装依赖、生成技能索引、构建 Docusaurus，再把 `website/build` 内容复制到发布目录。

## 核心流程

本地开发流程是：进入 `website` 目录，执行 `yarn` 安装依赖；执行 `yarn start` 时，npm/yarn 生命周期先运行 `prestart`，也就是 `scripts/prebuild.mjs`。该脚本负责准备技能数据和 LLM 友好的文档索引，避免开发者忘记手工生成辅助文件。随后 Docusaurus dev server 启动，读取 `docusaurus.config.ts`、`sidebars.ts`、`docs/`、`src/`、`i18n/` 等内容，并提供热更新。

构建流程是：执行 `yarn build`，先跑同一个 `prebuild`，再由 Docusaurus 生成 `build` 目录。这个目录是纯静态产物，可以交给任意静态站点托管服务。CI 中的 `docs-site-checks.yml` 还会在构建前显式执行 `extract-skills.py` 和 `generate-skill-docs.py`，再运行 `npm run lint:diagrams`，最后构建站点。这说明 README 的命令是开发者视角的最短路径，而 CI 流程更严格，包含技能文档生成和图表 lint。

部署流程有两层。README 描述的是 Docusaurus 自带的 `yarn deploy`，可以通过 SSH 或用户名环境变量推送到发布分支。仓库实际自动部署还由 `.github/workflows/deploy-site.yml` 负责：在 release、main 分支相关路径变更或手动触发时，构建技能索引、提取技能元数据、生成技能页面、安装网站依赖、构建 Docusaurus，并发布静态产物。

图表检查流程是：文档作者不要在 docs 中维护 ASCII box diagrams；应改用 Mermaid 或列表、表格。原因是 CI 运行 `ascii-guard`，而 README 明确把这个规则放在 “Diagram Linting” 中，属于贡献前必须知道的质量门槛。

## 关键函数的高层作用

`website/README.md` 没有函数、类或模块级导出，因此不存在“关键函数”。如果把 README 中的命令视为操作入口，则可以对应到几个关键脚本或配置：

1. `scripts/prebuild.mjs`：网站构建前置准备脚本。它的高层职责是保证 Skills Hub 所需的 JSON、LLM 文档索引等静态文件存在；在本地缺少 Python 或依赖时，它会写入空的 `skills.json` 作为降级，保证 Docusaurus 构建不被硬阻断。
2. `extract-skills.py`：根据当前片段推断，用于从仓库技能目录提取技能元数据，产出供前端 Skills 页面懒加载的数据。依据是 `prebuild.mjs` 注释和 `package.json` 生命周期脚本。
3. `generate-llms-txt.py`：生成面向 Agent 或 IDE 的短文档索引和完整文档拼接文件，部署 workflow 还会把这些文件额外复制到站点根发布路径。
4. `docusaurus.config.ts`：不是函数入口，但它是 Docusaurus 的核心配置对象，控制路由、主题、搜索、国际化、导航和插件。
5. `sidebars.ts`：定义 docs 侧边栏结构，影响文档可发现性和导航层级。
6. `npm run lint:diagrams`：封装 `ascii-guard`，是 README 中 Diagram Linting 规则的实际执行入口。

## 修改风险

修改这个 README 的主要风险不是运行时崩溃，而是误导贡献者或让本地说明与真实工程行为脱节。

第一类风险是命令漂移。如果 `website/package.json` 改为 npm 工作流、pnpm 工作流，或脚本名发生变化，而 README 仍写 `yarn start`、`yarn build`，新贡献者会按错路径操作。反过来，如果 README 修改了推荐命令，却没有同步 `package.json`、CI workflow 和部署文档，也会制造不一致。

第二类风险是低估 `prebuild`。README 目前把 `yarn start` 和 `yarn build` 描述成标准 Docusaurus 操作，但实际会先运行 `scripts/prebuild.mjs`。如果未来补充说明，需要准确表达：本地构建会准备技能数据和 LLM 索引；Python 或依赖缺失时可能降级为空数据。写得过重会吓退普通文档贡献者，写得过轻则会让调试 Skills Hub 的人忽略前置生成步骤。

第三类风险是部署说明过时。README 中的 `yarn deploy` 是 Docusaurus 标准方式，但仓库实际发布还有 GitHub Actions 流程，并可能触发其他托管服务。若修改部署段落，应避免写入真实外部地址，并明确区分“本地手动部署命令”和“仓库 CI 自动部署流程”。

第四类风险是图表 lint 规则被删弱。`Diagram Linting` 虽然只有一小段，却对应 CI 的硬检查。删除或模糊这段会增加文档 PR 失败概率，尤其是架构文档容易手写 ASCII 框图。若要调整规则，必须同步检查 `website/package.json` 的 `lint:diagrams` 和 `.github/workflows/docs-site-checks.yml`。

第五类风险是链接策略。README 原文包含 Docusaurus 官网链接；在面向 AIWIKI 的学习文档中不应输出真实网址。若维护原 README，可以保留普通 Markdown 链接；若生成派生说明，则应按当前任务要求写成 `[URL已移除]`，避免泄露真实外链。
