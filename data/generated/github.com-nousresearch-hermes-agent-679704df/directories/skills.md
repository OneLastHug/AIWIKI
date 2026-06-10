# 目录：skills

## 它负责什么

`skills` 是 Hermes Agent 随仓库发布的“内置技能库”源码目录，用来存放可被 Agent 按需加载的任务指导包。每个技能通常以一个包含 `SKILL.md` 的目录为单位，`SKILL.md` 提供 YAML frontmatter 元数据和正文指令，旁边可带 `references/`、`templates/`、`scripts/`、`assets/` 等支持文件。它的核心定位不是 Python 包，也不是运行时唯一技能目录，而是“官方内置技能的来源树”。

运行时真正被 Agent 读取的技能目录通常是 profile 下的 `~/.hermes/skills/`。`tools/skills_sync.py` 会把仓库内的 `skills/` 同步到用户技能目录，并通过 `.bundled_manifest` 记录来源 hash，避免覆盖用户修改。因此阅读 `skills` 时要把它理解为“内置技能模板库 / 种子库”，而不是用户现场编辑的主目录。

这个目录体现的是 Hermes 的 progressive disclosure 设计：模型先通过 `skills_list` 看到技能名和简短描述，需要使用时再通过 `skill_view` 或斜杠命令加载完整说明和支持文件。这样可以避免把所有技能全文塞进系统提示，降低上下文消耗。

## 直接子目录地图

`skills` 下一级基本按能力域分组：

`apple` 放 Apple 生态相关技能，例如 Notes、Reminders、Find My、iMessage、macOS 操作。

`autonomous-ai-agents` 放与其他编码 Agent 或多 Agent 工作流协作相关的技能，例如 `codex`、`claude-code`、`hermes-agent`、`opencode`、`kanban-codex-lane`。

`creative` 是较大的创意生产类集合，覆盖图表、ASCII、设计稿、漫画、信息图、ComfyUI、Manim、p5.js、像素艺术、网页设计风格等，很多子技能带 `references/`、`scripts/`、`templates/`。

`data-science`、`mlops` 面向数据科学、模型评测、推理、训练、Hugging Face、向量数据库、研究工具等机器学习工作流。

`devops`、`software-development` 放工程协作与开发方法技能，如 Kanban 编排、Webhook、调试 TUI 命令、技能编写、测试驱动开发、代码评审请求、计划写作、子 Agent 开发等。

`github` 聚焦 GitHub 工作流，包括认证、代码审查、issues、PR 流程、仓库管理和代码库检查。

`productivity`、`email`、`note-taking` 覆盖 Airtable、Google Workspace、Linear、Maps、Notion、OCR、PowerPoint、Teams、Himalaya、Obsidian 等办公与知识管理场景。

`research` 放研究辅助技能，例如 arXiv、论文写作、LLM wiki、市场/预测类研究等。

`media`、`gaming`、`smart-home`、`social-media`、`mcp`、`red-teaming`、`yuanbao` 等是较专门的领域集合。`dogfood`、`domain`、`gifs`、`inference-sh`、`index-cache` 更像特定用途或兼容性/内部使用技能集合，根据当前片段推断，它们不是统一业务域，而是历史演进中沉淀的独立入口。

## 关键入口

技能本体入口是每个技能目录下的 `SKILL.md`。工具层入口在 `tools/skills_tool.py`，其中 `skills_list()` 负责列出技能元数据，`skill_view()` 负责加载技能全文或支持文件，`check_skills_requirements()` 负责检查技能系统可用性。该文件也定义了技能 frontmatter 形态、平台过滤、环境变量检查、注入检测等基础规则，并注册 `skills_list`、`skill_view` 两个工具。

同步入口在 `tools/skills_sync.py`。它通过 `_discover_bundled_skills()` 扫描仓库 `skills/` 内所有 `SKILL.md`，再由 `sync_skills()` 同步到 `~/.hermes/skills/`，保留分类结构，并使用 manifest 判断新增、更新、用户修改和删除状态。

斜杠命令入口在 `agent/skill_commands.py`。`scan_skill_commands()` 扫描运行时技能目录和 `skills.external_dirs`，把技能名规范化成 `/skill-name` 命令；`build_skill_invocation_message()` 把某个技能加载成一段用户消息；`build_preloaded_skills_prompt()` 支持 CLI 启动时通过 `--skills` 预加载技能。

CLI 分发入口在 `cli.py`。`HermesCLI.process_command()` 先处理内置命令，再在 fallback 分支检查 quick commands、plugin commands、skill bundles，最后匹配技能斜杠命令并把构造出的技能消息放入 `_pending_input`，交给正常 Agent 对话流程处理。`/skills` 命令本身委托给 `hermes_cli/skills_hub.py`，`/reload-skills` 调用 `_reload_skills()` 刷新扫描结果。

## 主流程位置

典型主流程可以分为三段。

第一段是安装或启动阶段的同步：仓库 `skills/` 作为 bundled source，被 `tools/skills_sync.py` 复制到 `~/.hermes/skills/`。同步逻辑保留目录层级，例如 `skills/mlops/inference/vllm` 会对应到用户技能目录下相同相对结构。manifest 用于判断用户是否改过本地副本，避免无意覆盖。

第二段是发现与索引：`tools/skills_tool.py` 通过 `skills_list()` 提供轻量目录视图；`agent/skill_commands.py` 通过 `scan_skill_commands()` 扫描 `SKILL.md`，读取 frontmatter 的 `name`、`description`、`platforms` 等信息，过滤不兼容平台和禁用技能，再生成 `/xxx` 命令映射。

第三段是加载与使用：用户输入 `/gif-search` 这类命令时，`cli.py` 在 `process_command()` 中识别为技能命令，调用 `build_skill_invocation_message()`。后者内部通过 `skill_view()` 读取技能内容，追加技能目录、配置值、setup 提示和支持文件提示，形成一条注入对话的消息。模型随后按普通用户消息理解“用户调用了某技能”，并根据其中的指令执行任务。

## 推荐阅读顺序

先读 `tools/skills_tool.py` 顶部注释和 `skills_list()`、`skill_view()`，建立技能格式、加载层级和工具接口概念。

再读 `tools/skills_sync.py` 的文件头、`_discover_bundled_skills()`、`sync_skills()`，理解仓库 `skills/` 与用户 `~/.hermes/skills/` 的关系。

接着读 `agent/skill_commands.py` 的 `scan_skill_commands()`、`build_skill_invocation_message()`、`build_preloaded_skills_prompt()`，理解技能如何变成斜杠命令和对话消息。

然后看 `cli.py` 中 `process_command()` 关于 `skills`、`reload-skills`、skill bundles、skill slash commands 的分支，确认 CLI 调用链。

最后抽样阅读几个代表性技能即可：例如 `skills/software-development/hermes-agent-skill-authoring` 看技能编写规范，`skills/github/github-pr-workflow` 看工程流程型技能，`skills/creative/comfyui` 看带脚本和参考文件的复杂技能，`skills/mlops/inference/vllm` 看领域工具型技能。overview 阶段不需要逐个叶子目录展开。

## 常见误区

不要把 `skills/` 当作运行时唯一技能目录。代码注释明确说明运行时单一事实源是 `~/.hermes/skills/`，仓库目录主要用于内置技能种子和同步。

不要认为新增一个 `SKILL.md` 就自动进入系统提示。技能通常通过 `skills_list`、`skill_view`、`/skill-name` 或 `--skills` 按需加载，`reload_skills()` 也说明刷新斜杠命令不需要刷新系统提示缓存。

不要把技能当作 Python 插件。技能主要是 Markdown 指令包，脚本只是支持文件；插件系统在 `plugins/`，工具注册在 `tools/` 或插件上下文中，职责不同。

不要忽略 frontmatter。`name` 会影响技能命令名，`description` 会影响列表和菜单展示，`platforms` 会影响是否在当前系统可见，`metadata.hermes.config` 会触发配置值注入。

不要在 overview 阶段逐文件解释 `creative`、`mlops` 这类大目录。它们的价值主要在分类地图和代表性模式：有的技能只有 `SKILL.md`，有的技能附带 `references/`、`templates/`、`scripts/`，阅读时按任务需要下钻即可。
