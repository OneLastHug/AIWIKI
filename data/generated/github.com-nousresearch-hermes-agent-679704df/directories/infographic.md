# 目录：infographic

## 它负责什么

`infographic` 不是 Hermes Agent 的运行时代码目录，也不是一个 Python 包、前端应用或测试模块。根据当前片段推断，它更像是仓库内用于存放“信息图生成结果”的产物目录：每个主题一个子目录，子目录中保存最终生成的图片，以及按技能规范本应可能出现的分析、结构化内容和 prompt 等中间文件。

当前仓库实际可见内容很少：`infographic` 下只有 `kanban-db-corruption-defense` 一个主题目录，里面只有 `infographic.png`。该图片是 `1024 x 1024` 的 PNG，RGB、非隔行格式。也就是说，从现有文件看，它是一个静态视觉资产目录，而不是包含生成逻辑的源码目录。

它和仓库中 `skills/creative/baoyu-infographic` 的关系更密切。`baoyu-infographic` 技能文档定义了输出结构为 `infographic/{topic-slug}/...`，并说明最终图片应保存为 `infographic.png`。因此，`infographic/kanban-db-corruption-defense/infographic.png` 可以理解为某次围绕 “kanban db corruption defense” 主题生成的信息图结果。这里没有发现 README、配置文件、构建脚本或代码入口。

## 直接子目录地图

`infographic` 当前只有一个直接子目录：

`infographic/kanban-db-corruption-defense`

这个目录是一个具体主题的输出目录。目录名采用 kebab-case，符合 `baoyu-infographic` 技能中对 `topic-slug` 的约定：从主题提取 2-4 个词组成 slug，发生冲突时追加时间戳。当前主题名暗示它可能用于解释 Kanban 数据库损坏防护、恢复策略或相关工程实践，但仅凭目录和图片文件无法确认图片具体内容。

该子目录当前只有：

`infographic/kanban-db-corruption-defense/infographic.png`

这是最终信息图文件。技能文档中还定义过更完整的输出形态：`source-{slug}.{ext}`、`analysis.md`、`structured-content.md`、`prompts/infographic.md`、`infographic.png`。但当前目录没有这些中间文件。因此应把这里视为“只保留最终图像”的产物快照，而不是一次完整生成过程的全部工作区。

## 关键入口

这个目录本身没有可执行入口。没有 `__init__.py`、`package.json`、`pyproject.toml`、`README.md`、`vite.config.*` 或脚本文件。因此学习时不要从 `infographic` 里寻找类、函数或命令入口。

与它相关的关键入口在技能目录：

`skills/creative/baoyu-infographic/SKILL.md`

这个文件描述了什么时候触发信息图生成、可选布局和风格、输出目录结构、分析流程、prompt 生成流程以及调用图像生成工具的步骤。它是理解 `infographic` 目录来源的主要入口。

相关参考资料在：

`skills/creative/baoyu-infographic/references/analysis-framework.md`、`skills/creative/baoyu-infographic/references/structured-content-template.md`、`skills/creative/baoyu-infographic/references/base-prompt.md`、`skills/creative/baoyu-infographic/references/layouts/<layout>.md`、`skills/creative/baoyu-infographic/references/styles/<style>.md`

这些文件不在 `infographic` 目录下，但决定了生成出来的信息图应该如何分析内容、组织结构、套用布局和风格。

仓库中还有网站文档镜像，例如 `website/docs/user-guide/skills/bundled/creative/creative-baoyu-infographic.md` 和中文文档 `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/creative/creative-baoyu-infographic.md`。这些更偏用户说明，不是产物目录的入口。

## 主流程位置

主流程不在 `infographic` 目录内，而在 `skills/creative/baoyu-infographic/SKILL.md` 的 `Workflow` 部分。根据当前片段，信息图生成流程大致是：

第一步，分析输入内容。技能会读取 `references/analysis-framework.md`，保存源内容，识别主题、数据类型、复杂度、语气、受众、语言和用户设计要求，并输出 `analysis.md`。

第二步，生成结构化内容。源材料被整理为 `structured-content.md`，包括标题、学习目标、分区、关键概念、原文内容、视觉元素、文本标签和数据点。这里强调不能添加新信息，统计数字和引用要保持原样，同时需要剥离密钥、token 等敏感信息。

第三步，推荐布局和风格。技能支持 21 种 layout 和 21 种 style，例如默认的 `bento-grid` 与 `craft-handmade`。如果用户输入包含“信息图 / infographic”之类关键词，会优先选择对应的快捷组合；如果是“高密度信息大图 / high-density-info”，会倾向 `dense-modules` 等组合。

第四步，确认选项。通过 `clarify` 逐个确认布局风格组合、画幅比例和语言。画幅支持 `landscape`、`portrait`、`square` 或自定义比例。

第五步，生成 prompt。技能会读取所选 `references/layouts/<layout>.md`、`references/styles/<style>.md` 和 `references/base-prompt.md`，再结合结构化内容，输出到 `prompts/infographic.md`。

第六步，调用 `image_generate` 生成图片，最终保存图片 URL 或路径到输出目录。按规范最终文件名是 `infographic.png`，也就是当前目录中能看到的文件。

第七步，输出摘要，报告主题、布局、风格、比例、语言、输出路径和创建的文件。

因此，`infographic` 是这条流程的落点；真正的流程定义、约束和决策逻辑都在 `skills/creative/baoyu-infographic`。

## 推荐阅读顺序

建议先看 `infographic` 的目录形状，确认它不是源码模块，而是主题化输出目录。当前只需要知道：`infographic/kanban-db-corruption-defense` 是一个主题，`infographic.png` 是最终图片。

然后阅读 `skills/creative/baoyu-infographic/SKILL.md`。重点看 `When to Use`、`Options`、`Output Structure` 和 `Workflow`。这些段落能解释为什么输出会落在 `infographic/{topic-slug}/`，以及为什么最终文件叫 `infographic.png`。

接着阅读 `skills/creative/baoyu-infographic/references/analysis-framework.md` 和 `skills/creative/baoyu-infographic/references/structured-content-template.md`。这两类文件解释生成前的内容分析和结构化方式，适合理解“信息图不是直接把文本丢给图片模型，而是先做教学目标和视觉结构拆解”。

再看 `skills/creative/baoyu-infographic/references/base-prompt.md`、`references/layouts/<layout>.md`、`references/styles/<style>.md`。这些决定最终图像的版式、视觉风格和 prompt 拼装。

最后再回到 `infographic/kanban-db-corruption-defense/infographic.png`，把它当作上述流程的一次输出样本来看。由于当前缺少 `analysis.md`、`structured-content.md` 和 `prompts/infographic.md`，无法从该目录本身完整复盘生成决策。

## 常见误区

第一个误区是把 `infographic` 当成一个功能模块。它没有代码入口，也没有注册逻辑；Hermes 的技能系统、图像生成工具和 prompt 组织逻辑都不在这里。

第二个误区是认为 `infographic/kanban-db-corruption-defense` 包含完整生成过程。按技能规范，一个完整输出目录可能包含源内容、分析文件、结构化内容、prompt 和最终图片；但当前只保留了 `infographic.png`。如果要追踪生成依据，需要去技能定义和参考模板中找流程，而不是在这个目录里找缺失文件。

第三个误区是把 `infographic.png` 视为文档站点资源入口。当前搜索到的引用主要指向 `baoyu-infographic` 技能和网站技能文档，未发现代码或文档直接引用 `infographic/kanban-db-corruption-defense/infographic.png`。根据当前片段推断，它更像仓库中的示例产物或临时成果，而不是被某个构建流程稳定消费的资产。

第四个误区是忽略敏感信息处理。`baoyu-infographic` 的流程明确要求在源内容进入输出文件前剥离 credentials、API keys、tokens、secrets。即使 `infographic` 只是产物目录，理解它的上游流程时也要把数据完整性和脱敏作为核心约束。

第五个误区是从图片目录反推全部语义。目录名能提示主题，图片格式能说明产物类型，但没有中间 markdown 和 prompt 时，不应断言使用了哪种 layout、style、语言或原始材料。除非能看到对应的 `analysis.md`、`structured-content.md` 或 `prompts/infographic.md`，否则只能说“根据当前片段推断”。
