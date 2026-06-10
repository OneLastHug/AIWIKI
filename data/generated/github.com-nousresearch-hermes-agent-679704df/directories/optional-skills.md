# 目录：optional-skills

## 它负责什么

`optional-skills` 是 Hermes Agent 随仓库发布的“官方可选技能库”。它和根目录下的 `skills/` 不同：`skills/` 是默认可加载的内置技能，而 `optional-skills/` 中的技能默认不会进入系统提示词，也不会在初始安装时自动复制到用户的 `~/.hermes/skills/`。它们通过 Skills Hub 暴露给用户，以 `official/...` 标识安装，例如提示信息中出现的 `hermes skills install official/security/1password`。

从 `tools/skills_hub.py` 的 `OptionalSkillSource` 注释和实现可以看出，这里的技能被视为官方维护、`trust_level` 为 `builtin`，但激活需要用户显式搜索、检查或安装。目录本身主要承担“技能包仓库”的角色：每个技能目录通常以 `SKILL.md` 作为描述入口，可附带 `scripts/`、`references/`、`templates/` 等资源。运行时不会直接把整个目录塞进 Agent 上下文，而是先由 Skills Hub 扫描元数据，再在安装时按需读取目标技能目录内的文件。

## 直接子目录地图

`optional-skills` 的一级目录按领域分类，而不是按 Python 包或运行模块分类。当前片段看到的分类包括：

- `autonomous-ai-agents`：与外部 Agent、CLI Agent、自动化协作相关的技能，如 `antigravity-cli`、`blackbox`、`grok`、`honcho`、`openhands`。
- `blockchain`：链上开发和交易相关技能，如 `evm`、`hyperliquid`、`solana`。
- `communication`：沟通方法类技能，目前有 `one-three-one-rule`。
- `creative`：创意生产、图形、视频、MCP 创作工具相关技能，如 `blender-mcp`、`concept-diagrams`、`hyperframes`、`meme-generation`。
- `devops`：运维和开发环境辅助，如 `cli`、`docker-management`、`pinggy-tunnel`、`watchers`。
- `dogfood`：内部自测或体验评估类技能，如 `adversarial-ux-test`。
- `email`：邮件平台集成，如 `agentmail`。
- `finance`：金融建模和文档产出类技能，包含 `3-statement-model`、`dcf-model`、`lbo-model`、`pptx-author`、`stocks` 等。
- `health`：健康和生物信号相关技能，如 `fitness-nutrition`、`neuroskill-bci`。
- `mcp`：MCP 开发和迁移辅助，如 `fastmcp`、`mcporter`。
- `migration`：迁移工具链，目前看到 `openclaw-migration`。
- `mlops`：最大的一组，覆盖训练、推理、向量库、多模态、分布式和模型工具，如 `accelerate`、`faiss`、`inference`、`modal`、`peft`、`pytorch-fsdp`、`stable-diffusion`、`tensorrt-llm`、`training`、`whisper` 等。
- `productivity`：生产力工具和个人工作流，如 `canvas`、`memento-flashcards`、`shopify`、`telephony`。
- `research`：研究、情报、搜索和实验型工作流，如 `bioinformatics`、`drug-discovery`、`osint-investigation`、`searxng-search`。
- `security`：安全、取证和渗透测试类技能，如 `1password`、`oss-forensics`、`sherlock`、`web-pentest`。
- `software-development`：软件工程辅助技能，如 `code-wiki`、`rest-graphql-debug`。
- `web-development`：Web 自动化或页面 Agent 技能，如 `page-agent`。

根据当前片段推断，一级目录只是分类容器，真正的技能单元是二级目录；少数领域未来可能继续扩展更深层级，但 `OptionalSkillSource` 是通过递归查找 `SKILL.md` 来识别技能，因此不强依赖固定层级。

## 关键入口

最关键的代码入口是 `tools/skills_hub.py` 中的 `OptionalSkillSource`。它实现了官方可选技能源的三个核心动作：`search()` 用名称、描述和标签做简单匹配；`fetch()` 根据 `official/category/skill` 或技能名定位目录并打包文件；`inspect()` 返回单个技能的元数据。内部的 `_scan_all()` 会递归查找 `optional-skills/**/SKILL.md`，读取 frontmatter 中的 `name`、`description`、`metadata.hermes.tags`，并生成 `SkillMeta`。

同一文件中的 `create_source_router()` 把 `OptionalSkillSource()` 放在 source 列表首位，说明官方可选技能在 Skills Hub 搜索和安装路由中优先级最高。它后面才是中心索引、外部技能源、GitHub 源、ClawHub、Claude Marketplace、LobeHub 等来源。

`hermes_constants.get_optional_skills_dir()` 是路径解析入口；`OptionalSkillSource.__init__()` 用它把默认路径定位到仓库内的 `optional-skills`。`tools/skills_sync.py` 负责同步或修复用户已安装的官方技能副本，从搜索结果看它会定位官方目录，并处理 active copy 与官方版本的关系。`scripts/build_skills_index.py` 会把 `OptionalSkillSource` 纳入索引构建。`hermes_cli/setup.py`、`hermes_cli/skills_hub.py`、`hermes_cli/main.py` 则是 CLI 安装、展示和维护流程的上层入口。

## 主流程位置

主流程可以按“发现、展示、安装、激活”理解。

第一步是发现：Skills Hub 创建 source router 时加载 `OptionalSkillSource`，它递归扫描 `optional-skills` 下的 `SKILL.md`。这一步只读取元数据，不等于启用技能。

第二步是展示：用户执行技能搜索、查看或安装相关命令时，上层 CLI 调用 source 的 `search()` 或 `inspect()`，展示 `official/...` 标识、描述、标签和信任级别。由于这些技能是官方可选技能，标识格式通常是 `official/<category>/<skill>`。

第三步是安装：当用户安装某个 `official/...` 技能时，`fetch()` 会先去掉 `official/` 前缀，把剩余部分映射到 `optional-skills` 下的相对路径。代码中有路径穿越防护，会校验解析后的路径仍在 `_optional_dir` 内。如果精确路径不存在，还会按最后一段技能名在所有 `SKILL.md` 父目录中搜索。找到后，`fetch()` 递归读取该技能目录内的普通文件，过滤隐藏文件、`__pycache__` 和 `.pyc`，生成 `SkillBundle`。

第四步是激活：安装后的技能副本进入用户技能目录，后续才可能被 Hermes 的技能加载机制注入对话上下文。`optional-skills` 原目录本身仍然只是官方源，不是运行时直接激活目录。

## 推荐阅读顺序

建议先看 `optional-skills` 的一级分类，建立“领域分类容器 + 二级技能包”的地图。然后任选一个简单技能目录阅读它的 `SKILL.md`，重点观察 frontmatter、`## When to Use`、`## Prerequisites`、`## How to Run`、`## Procedure` 等标准结构，而不要一开始深入所有脚本。

第二步阅读 `tools/skills_hub.py` 的 `OptionalSkillSource`，理解 `search()`、`fetch()`、`inspect()`、`_scan_all()` 如何把磁盘目录转换为 Skills Hub 可消费的元数据和安装包。接着看 `create_source_router()`，确认它在多来源技能系统中的优先级。

第三步再看 `tools/skills_sync.py`、`scripts/build_skills_index.py` 和 `hermes_cli/skills_hub.py`。前者帮助理解官方技能与用户已安装副本的同步关系，后者帮助理解 CLI 如何把 source adapter 暴露成命令。最后再根据具体任务深入某个技能的 `scripts/`、`references/` 或 `templates/`。

## 常见误区

第一个误区是把 `optional-skills` 当成默认启用技能。它不是默认系统提示词的一部分，也不是 setup 时自动复制的技能集合；必须通过 Skills Hub 显式安装。

第二个误区是认为一级目录就是功能入口。一级目录只是分类，真正的技能入口通常是每个技能目录下的 `SKILL.md`。Skills Hub 也是通过递归查找 `SKILL.md` 来识别技能，而不是导入 Python 包。

第三个误区是把这里的脚本当成 Hermes 核心工具。技能目录里的 `scripts/` 是技能随附资源，只有该技能被安装并被 Agent 使用时才有意义；核心工具注册仍在 `tools/`、`toolsets.py`、插件系统等位置。

第四个误区是手动复制单个脚本来“安装技能”。正确路径是使用 `official/...` 标识走 Skills Hub 安装流程，因为安装流程会读取完整技能目录、保留 `SKILL.md`、脚本、模板和参考资料，并记录来源与信任级别。

第五个误区是把 `official/` 前缀等同于任意可信路径。代码中虽然支持 `official/category/skill`，但 `fetch()` 明确做了路径穿越防护；`official/../../...` 这类输入不会被当作合法技能路径处理。
