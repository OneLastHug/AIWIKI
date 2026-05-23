# 文件：README.zh-CN.md

## 一句话定位

`README.zh-CN.md` 是仓库根目录的中文门面文档，面向 GitHub 访客、潜在用户、部署者和贡献者，用中文解释 LobeHub 是什么、核心能力有哪些、如何部署和本地开发，以及如何进入生态、插件、社区与赞助入口。它不是运行时代码，但对项目认知、转化、部署路径和外部展示有很强影响。

## 它暴露/定义了什么

这个文件主要定义了项目的中文公开叙事和入口结构：顶部品牌区、语言切换、徽章组、分享入口、目录、产品介绍、功能分区、部署说明、环境变量摘要、OpenAI API Key 获取说明、生态系统、插件体系、本地开发、贡献说明、赞助、更多工具、License 和底部链接引用组。

从内容形态看，它暴露的是 Markdown + HTML 混合文档：用 `<div align="center">`、`<details>`、`<picture>`、`<table>` 等 HTML 控制 GitHub README 的视觉排版；用引用式链接统一管理大量外部入口；用图片、badge、部署按钮和命令块把产品介绍与操作路径串起来。它与英文 `README.md` 成对存在，顶部互相链接，承担中文用户的默认阅读路径。

## 谁调用它

直接“调用”它的不是业务代码，而是几个外部和维护场景。

第一类是平台渲染方：GitHub 仓库首页会直接展示它的内容，用户通过 `README.md` 的“简体中文”入口进入；搜索引擎、开源索引、社交分享预览也会间接受它影响。第二类是用户和部署者：他们按其中的 Vercel、Zeabur、Sealos、阿里云计算巢、Docker、本地开发命令执行部署或开发。第三类是仓库维护脚本：`package.json` 中的 `workflow:readme` 指向 `scripts/readmeWorkflow/index.ts`，该脚本通过 `scripts/readmeWorkflow/utlis.ts` 中的 `readReadme`、`writeReadme`、`updateReadme` 读写 `README.md` 或 `README.zh-CN.md` 这类语言版本文件。根据当前片段推断，自动同步主要服务于 README 中可批量更新的索引块，例如 Provider、Agent、Plugin 相关内容，依据是脚本入口依次调用 `syncProviderIndex`、`syncAgentIndex`、`syncPluginIndex`。

## 它调用谁

作为文档文件，它没有代码层面的 import 或函数调用，但通过链接、图片和命令“引用”了大量外部系统。它引用了官网、文档、博客、更新日志、GitHub Issues、Docker Hub、Vercel、Zeabur、Sealos、阿里云计算巢、Discord、Product Hunt、Trendshift、OpenCollective、OpenAI 平台、多个 LobeHub 生态仓库和 badge 服务；这些真实地址在文档中以引用式链接或内联 HTML 图片出现，学习时可统一理解为 `[URL已移除]`。

它还调用了用户本地环境中的工具链：部署段落要求用户执行 `docker compose up -d`、一键脚本 `bash <(curl -fsSL [URL已移除]) -l zh_CN`；本地开发段落要求 `git clone`、`pnpm install`、`pnpm run dev`、`bun run dev:spa`。这些不是程序调用，而是文档引导用户触发外部流程。

## 核心流程

阅读路径从“品牌认知”开始：顶部 banner、项目名、中文 slogan 和 badge 先建立项目可信度，再通过语言、官网、文档、博客、反馈等入口分流不同读者。接着目录把长文档压缩成可跳转结构，降低 GitHub README 的滚动成本。

产品介绍部分先描述传统 Agent 工具的痛点，再提出 LobeHub 的定位：以 Agent 为工作单元，构建能持续协作、调度、记忆和进化的工作空间。功能区按“运营、创建、协作、进化”组织，分别解释 Agent 团队调度、Agent Builder、Agent Groups / Pages / Schedule / Project / Workspace、Personal Memory 等概念。

部署流程分成两条主线：一键平台部署和 Docker 自托管。平台部署强调准备 `OPENAI_API_KEY`、点击部署按钮、填写环境变量、部署完成后使用；Docker 部署则从创建目录、一键脚本、`docker compose up -d` 进入。随后环境变量表只列出高频关键项，完整配置交给外部文档。OpenAI API Key 段落再补足新用户最容易卡住的前置条件。

后半部分从使用者转向生态和贡献者：生态系统列出 `@lobehub/ui`、`@lobehub/icons`、`@lobehub/tts`、`@lobehub/lint`；插件体系说明 Function Calling 扩展、插件索引、模板、SDK、网关；本地开发给出最短启动命令；贡献、赞助、更多工具和 License 构成开源项目的收尾。

## 关键函数的高层作用

`README.zh-CN.md` 本身没有函数。与它最相关的维护函数在 `scripts/readmeWorkflow/utlis.ts`：`getReadmePath(lang)` 根据语言参数决定读写根目录的 `README.md` 或 `README.<lang>.md`，因此 `lang` 为 `zh-CN` 时会定位到 `README.zh-CN.md`；`readReadme(lang)` 读取目标 README 文本；`writeReadme(content, lang)` 写回目标 README；`updateReadme(split, md, content)` 用分隔符切开原 Markdown，并替换中间内容，适合自动刷新某个固定区块；`getTitle(lang)` 返回不同语言下的表格标题，例如中文返回“最近新增”“描述”。`fetchAgentIndex` 和 `fetchPluginIndex` 从远端索引拉取 Agent / Plugin 数据，辅助生成 README 中可同步的生态内容。

这些函数的作用是维护 README 的结构化片段，而不是渲染应用页面。修改 `README.zh-CN.md` 时需要注意它可能被这些脚本覆盖局部内容。

## 修改风险

最大的风险是破坏公开入口。顶部语言切换、目录锚点、badge、部署按钮、文档入口和 License 链接一旦写错，用户会在仓库首页直接遇到断链或错误路径。尤其是 Markdown 标题改名后，目录里的锚点也要同步，否则跳转失效。

第二个风险是中英文内容漂移。`README.zh-CN.md` 与 `README.md` 共同承担项目首页说明，产品定位、部署方式、环境变量、开发命令、License 口径如果不一致，会让不同语言用户得到不同结论。涉及产品能力、部署平台、命令、环境变量时，应同时检查英文版。

第三个风险是自动同步区块冲突。根据当前片段推断，`workflow:readme` 会读写 README 语言版本并替换部分内容；如果人工修改落在脚本维护的分隔区间内，后续运行脚本可能覆盖。修改前应确认相关同步脚本的 split 标记和目标区块。

第四个风险是外部链接与敏感信息。README 中存在大量真实外部服务地址、图片地址、部署地址和第三方代理说明，更新时要避免引入失效链接、误导性价格、安全承诺或不可验证的服务背书。环境变量表也不应加入真实密钥示例，只能保留形如 `sk-xxxxxx...xxxxxx` 的占位形式。

第五个风险是 GitHub 渲染兼容性。该文件混合 Markdown、HTML、表格、`details`、`picture`、badge 和图片，轻微的标签未闭合或表格格式破坏都可能影响后续大段内容展示。修改时应优先保持现有结构，不做无关排版重构。
