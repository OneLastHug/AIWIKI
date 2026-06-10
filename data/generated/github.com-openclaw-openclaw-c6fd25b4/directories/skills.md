# 目录：skills

## 它负责什么

`skills` 是 OpenClaw 仓库内的一组内置 AgentSkill 资源目录，用来把“可触发的专用工作流”以轻量 Markdown 包的形式提供给代理。它不是核心运行时代码目录，也不是插件 SDK 本体；它更像一组可被运行时发现、展示、检查、打包或安装的技能素材。每个技能通常是一个独立子目录，核心入口是 `SKILL.md`，通过 YAML frontmatter 声明 `name`、`description`，有些还带 `metadata.openclaw`，用于描述图标、依赖、安装项、配置要求等。

从 `skills/skill-creator/SKILL.md` 可以看出本目录的设计原则：技能元数据常驻可见，正文在触发后加载，`references/`、`scripts/`、`assets/` 等辅助资源只在需要时读取。也就是说，`skills` 目录主要承载“给模型看的操作说明”和“少量确定性辅助脚本”，而不是把业务逻辑全部写进主程序。

## 直接子目录地图

这个目录下的直接子目录大致可以按用途分组理解。

一类是账号、应用和个人信息工具技能，例如 `1password`、`apple-notes`、`apple-reminders`、`bear-notes`、`notion`、`obsidian`、`things-mac`、`trello`。它们面向外部应用或本地个人工作流，通常说明如何读取、整理或操作相应工具。

一类是通信和消息渠道相关技能，例如 `discord`、`github`、`gh-issues`、`slack`、`imsg`、`wacli`、`voice-call`。它们不是渠道核心实现本身，而是面向代理的操作流程提示，帮助代理按既定规则使用已有命令或服务。

一类是开发、调试和代理编排技能，例如 `coding-agent`、`taskflow`、`node-connect`、`node-inspect-debugger`、`python-debugpy`、`tmux`、`session-logs`、`healthcheck`、`clawhub`。这些目录通常和后台任务、调试会话、终端会话或 OpenClaw 自身生态协作有关，是理解高级代理工作流的重点。

一类是媒体、内容和文件处理技能，例如 `diagram-maker`、`meme-maker`、`nano-pdf`、`openai-whisper`、`openai-whisper-api`、`sherpa-onnx-tts`、`video-frames`、`gifgrep`、`summarize`、`songsee`。其中部分目录带有 `scripts/`、`references/` 或 `bin/`，说明它们不只是提示词，还依赖本地脚本或二进制工具完成可重复操作。

还有一类是设备、服务和生活工具，例如 `openhue`、`sonoscli`、`spotify-player`、`weather`、`goplaces`、`gog`、`ordercli`、`oracle`、`peekaboo`、`camsnap`、`blucli`、`eightctl`、`xurl`。这些技能通常把某个 CLI、服务或硬件控制入口包装成代理可理解的流程。

## 关键入口

最重要的入口是每个子目录里的 `SKILL.md`。它承担三层职责：第一，frontmatter 里的 `name` 和 `description` 决定技能身份与触发语义；第二，正文说明该技能何时使用、怎么使用、有哪些限制；第三，正文会指向必要的脚本、参考材料或验证方式。

`skills/skill-creator/SKILL.md` 是理解技能格式的首选入口。它明确给出推荐结构：`SKILL.md` 为主，`scripts/` 放确定性辅助脚本，`references/` 放较长资料，`assets/` 放模板或媒体资源，`agents/` 可放 UI 元数据。它还提供 `skills/skill-creator/scripts/quick_validate.py`、`skills/skill-creator/scripts/package_skill.py` 等工具，用于校验或打包技能。

`skills/pyproject.toml` 是 Python 辅助脚本测试与 lint 的本地配置入口。根据当前片段推断，技能目录里的 Python 测试主要覆盖脚本类技能，例如 `skills/skill-creator/scripts/test_quick_validate.py`、`skills/model-usage/scripts/test_model_usage.py`。

代表性技能可以先看 `skills/coding-agent/SKILL.md` 和 `skills/taskflow/SKILL.md`。前者展示如何把复杂编码任务委派给后台 worker，并强调通知路线、后台执行和进程监控；后者展示 OpenClaw 内部长期任务编排概念，如 `api.runtime.tasks.flow`、`createManaged(...)`、`runTask(...)`、`setWaiting(...)`、`resume(...)`、`finish(...)`。

## 主流程位置

`skills` 本身主要存放资源，真正的发现、筛选、提示词拼装和命令暴露逻辑在邻近的运行时代码与文档中。根据当前片段推断，技能快照和 prompt 构建的核心位置在 `src/agents/skills.ts` 一带，依据是 `docs/pi.md` 明确提到 `skills.ts` 负责 skill snapshot 和 prompt building，并说明 `buildAgentSystemPrompt()` 会组装包含 Skills 在内的系统提示词。

技能和命令授权之间的连接点在 `src/plugin-sdk/command-auth.ts`。该文件导出或转发 `listSkillCommandsForAgents`、`listSkillCommandsForWorkspace`、`resolveSkillCommandInvocation`，并从 `src/agents/skills.js` 引出 `SkillCommandSpec` 类型。这说明技能不只进入系统提示词，也可能形成可列举、可解析的命令调用面。

CLI 使用侧可以参考 `docs/cli/skills.md`、`docs/tools/skills` 和 `docs/tools/skills-config` 对应文档。当前片段显示 `openclaw skills` 支持 `search`、`install`、`update`、`list`、`info`、`check` 等动作，并约定 Git 或本地目录安装时源根目录需要有 `SKILL.md`。配置侧还和 `openclaw.json` 中的 agent skill 可见性有关。

插件侧的连接点在 `docs/plugins/manifest.md`：插件 manifest 可声明 `skills` 字段，表示相对于插件根目录加载的技能目录。也就是说，仓库根部 `skills` 是一组内置或示例性的技能包，而 OpenClaw 的技能机制还允许插件或迁移流程提供额外技能。

## 推荐阅读顺序

第一步先读 `skills/skill-creator/SKILL.md`，掌握一个技能目录的标准形状、frontmatter 规则、`references/` 与 `scripts/` 的分工。

第二步读两三个不同类型的技能：`skills/coding-agent/SKILL.md` 理解后台代理协作，`skills/taskflow/SKILL.md` 理解持久任务编排，`skills/meme-maker/SKILL.md` 或 `skills/model-usage/SKILL.md` 理解带脚本技能如何组织。

第三步看带辅助资源的目录结构，例如 `skills/1password/references`、`skills/diagram-maker/references`、`skills/meme-maker/scripts`、`skills/video-frames/scripts`。重点不是记每个文件，而是理解：长说明放 `references/`，可执行流程放 `scripts/`，主 `SKILL.md` 保持精简。

第四步再回到运行时入口，结合 `src/agents/skills.ts`、`src/plugin-sdk/command-auth.ts`、`docs/cli/skills.md` 理解技能如何从目录资源进入 agent prompt、CLI 检查和命令调用面。

## 常见误区

不要把 `skills` 当成核心插件实现目录。真正的 plugin runtime、channel、provider、gateway 协议在 `src/`、`extensions/`、`packages/` 等目录；`skills` 更多是代理工作流说明和辅助工具集合。

不要认为所有子目录都会无条件进入每个代理上下文。技能通常受安装位置、配置、agent 可见性、依赖检查和触发条件影响；`metadata.openclaw.requires`、`skills.entries.*` 配置和 CLI `check` 都可能影响可用状态。

不要把 `references/` 里的长文复制进 `SKILL.md`。当前目录的设计明显偏向“主入口短、细节懒加载”，这样可以减少 prompt 常驻负担。

不要把 `scripts/` 当成随意脚本堆放区。已有配置显示 Python 脚本有测试入口，部分技能还用 Node 或 shell 脚本完成确定性处理；修改这类技能时应同时考虑脚本验证，而不是只改 Markdown。

不要把外部服务地址、真实凭据或本地绝对路径写进技能文档。技能常会被安装、打包或迁移，路径和秘密都应通过配置、环境、凭据系统或运行时上下文处理。
