# 目录：docs

## 它负责什么

`docs` 是 OpenClaw 的公开文档源目录，面向最终用户、插件作者、运维者和贡献者，承载安装、快速开始、CLI、Gateway、channel、provider、plugin、automation、安全、诊断与概念说明等内容。根据 `docs/AGENTS.md`，这里的文档由 Mintlify 承载，`docs/docs.json` 负责站点元信息、导航、重定向、主题、图标和外部导航入口；仓库内英文文档与 `.i18n` glossary 是翻译源头，本仓库不维护本地化页面正文。

从角色上看，`docs` 不是代码运行时的一部分，而是产品行为、配置契约、CLI 使用方式、插件生态和排障路径的说明层。它与源码强相关：例如 Gateway 配置、channel 接入、provider 配置、plugin SDK、automation 任务等文档都需要与 `src/`、`extensions/`、`packages/` 等实现保持一致。对学习者而言，这个目录更像“产品地图 + 操作手册 + 架构解释”的组合。

## 直接子目录地图

`docs/start` 放快速开始和入门路径，通常是新用户第一站。`docs/install` 覆盖安装、迁移和部署环境。`docs/cli` 是命令行参考入口，包含 `openclaw` 各子命令说明，如 agent、gateway、doctor、plugins、models、message、sessions 等。

`docs/gateway` 负责 Gateway 进程、配置、认证、发现、诊断、后台运行和安全相关说明，是理解本地服务进程的核心区域。`docs/channels` 按消息渠道组织文档，覆盖 Discord、Slack、Telegram、WhatsApp、Matrix、iMessage、Signal、Google Chat、Microsoft Teams、Zalo 等接入与路由主题。`docs/providers` 说明模型提供方和运行时接入。`docs/plugins` 面向插件使用与开发，包含插件构建、发布、能力扩展和 reference 内容。

`docs/concepts` 是架构和机制解释区，主题包括 agent loop、context、memory、streaming、session、queue、models、multi-agent、provider failover 等。`docs/automation` 讲自动化能力，如 hooks、cron、webhook、tasks、standing orders、poll 等。`docs/tools` 放内置或插件化工具文档，如搜索、fetch、TTS 等能力。`docs/security`、`docs/diagnostics`、`docs/debug` 分别覆盖安全、诊断标志和问题定位材料。

`docs/platforms`、`docs/nodes`、`docs/web`、`docs/help` 偏部署平台、节点、Web 体验和帮助材料。`docs/assets`、`docs/images` 存放文档图片和静态资源。`docs/snippets` 放可复用片段或发布流程片段。`docs/.i18n` 保存翻译 glossary、导航翻译和翻译流程说明。`docs/.generated` 根据名称和 README 推断是生成产物说明区。`docs/refactor`、`docs/plan`、`docs/announcements` 更偏阶段性设计、计划或公告内容。

## 关键入口

最重要的结构入口是 `docs/docs.json`。它定义 Mintlify 站点名称、描述、主题、logo、字体、颜色、navbar、redirects 等。学习文档站如何组织时，应先看它，因为页面能否出现在站点导航、旧路径如何跳转、哪些路径是历史兼容入口，都由这里集中体现。

内容入口是 `docs/index.md`，它是文档首页。新用户路径入口是 `docs/start/quickstart.md` 和 `docs/install/index.md`。命令参考入口是 `docs/cli/index.md`。运行时与配置入口是 `docs/gateway/index.md`、`docs/gateway/configuration.md`、`docs/gateway/configuration-reference.md`。消息渠道入口是 `docs/channels/index.md`。模型提供方入口是 `docs/providers/index.md`。插件入口是 `docs/plugins` 下的概览与 reference 页面。概念学习入口是 `docs/concepts/architecture.md` 以及同目录下 context、messages、streaming、session、queue 等主题页。

还有两个维护入口值得注意：`docs/AGENTS.md` 规定本目录的写作和 Mintlify 链接规则；`docs/.i18n/README.md` 与 `docs/.i18n/translation-workflow.md` 说明翻译 glossary 与发布仓库协作方式。根级样式和脚本入口包括 `docs/style.css`、`docs/nav-tabs-underline.js`，用于文档站展示行为或样式补充。

## 主流程位置

文档发布主流程根据当前片段可概括为：在本仓库维护 `docs/**/*.md` 英文源文档和 `docs/docs.json` 导航配置，然后通过同步发布流程把内容镜像到独立的发布仓库，再由文档平台构建和分发。这个判断来自根规则中“source docs: `docs/**`；publish repo: `openclaw/docs`；Flow: source -> `docs-sync-publish.yml` -> mirror build -> R2 -> Worker router”的描述，以及 `docs/AGENTS.md` 对 Mintlify、i18n 和 publish repo 的约束。这里不展开真实外部地址，统一记作 `[URL已移除]`。

用户学习主流程大致是：先进入 `docs/index.md` 和 `docs/start/quickstart.md` 了解产品目标，再到 `docs/install` 完成部署，然后读 `docs/cli` 掌握命令行操作；需要实际接入消息平台时进入 `docs/channels`，需要配置模型时进入 `docs/providers`，需要后台进程和配置细节时进入 `docs/gateway`。当开始扩展能力或开发插件，再阅读 `docs/plugins`、`docs/tools`、`docs/clawhub`。遇到机制问题时回到 `docs/concepts`；遇到异常时走 `docs/diagnostics`、`docs/debug`、`docs/gateway/doctor.md`、`docs/channels/troubleshooting.md` 等排障页。

作者维护主流程是：先遵守 `docs/AGENTS.md` 的 Mintlify 链接规则，内部文档链接使用 root-relative 且不带 `.md` 或 `.mdx` 后缀；新增或移动页面时同步检查 `docs/docs.json` 导航和 redirects；新增术语、短标题或导航标签时补充 `docs/.i18n/glossary.*.json`。如果是行为、API、配置或 CLI 变化，对应文档应随代码改动一起更新。

## 推荐阅读顺序

第一步读 `docs/AGENTS.md`，理解本目录的写作边界、链接格式、i18n 政策和公开/内部文档区分。第二步读 `docs/docs.json`，建立站点结构、导航和重定向的全局认识。第三步读 `docs/index.md`、`docs/start/quickstart.md`、`docs/install/index.md`，获得产品入口和安装路径。

第四步按使用者角色分流：普通用户读 `docs/cli/index.md`、`docs/gateway/index.md`、`docs/channels/index.md`、`docs/providers/index.md`；运维者重点读 `docs/gateway/configuration.md`、`docs/gateway/configuration-reference.md`、`docs/gateway/doctor.md`、`docs/diagnostics/flags.md`；插件作者读 `docs/plugins`、`docs/plugins/reference`、`docs/tools`、`docs/clawhub/publishing.md`；想理解架构的人读 `docs/concepts/architecture.md`，再补 `docs/concepts/agent-loop.md`、`docs/concepts/context.md`、`docs/concepts/messages.md`、`docs/concepts/streaming.md`、`docs/concepts/session.md`。

第五步再看专题目录：自动化看 `docs/automation/index.md`，平台部署看 `docs/platforms/index.md`，节点相关看 `docs/nodes/index.md`，安全看 `docs/security`，帮助材料看 `docs/help/index.md`。

## 常见误区

不要把 `docs` 当作单纯 Markdown 堆。它受 `docs/docs.json`、Mintlify 链接规则、发布同步流程和 i18n glossary 共同约束，页面路径、标题、导航名和重定向都会影响公开文档体验。

不要在本仓库新增本地化正文目录。根据 `docs/AGENTS.md`，外语文档正文不在这里维护；这里的英文文档和 glossary 是源头，翻译输出位于独立发布仓库。

不要把内部路径、个人设备名、主机名或私有信息写进公开文档。`docs/AGENTS.md` 明确要求公开内容保持通用，内部长期运维文档另有位置，仓库内 `docs/internal` 即使存在也不能加入公开导航。

不要把 `extensions/` 这类内部实现术语暴露为用户说法。根规则要求产品、文档和 UI 使用 “plugin/plugins” 表述。阅读 `docs/plugins` 时也应把它理解为用户可见插件生态，而不是源码目录名。

不要只改正文不看导航。新增页面、改名、移动路径、废弃路径时，需要考虑 `docs/docs.json` 中的导航和 redirects。否则页面可能存在于仓库，却无法按预期在文档站访问或从旧路径跳转。

不要把概念文档当成命令参考。`docs/concepts` 解释机制和架构，`docs/cli` 才是命令入口，`docs/gateway` 才是运行时配置入口，`docs/channels` 和 `docs/providers` 才是接入具体服务的入口。各目录职责清晰，交叉阅读时应以路径角色判断信息的权威位置。
