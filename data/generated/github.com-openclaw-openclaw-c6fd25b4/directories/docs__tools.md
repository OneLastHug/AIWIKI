# 目录：docs/tools

## 它负责什么

`docs/tools` 是 OpenClaw 文档中解释“agent 可以调用什么能力、这些能力如何配置、如何排错、如何扩展”的工具文档区。它不是运行时代码目录，而是面向用户和插件作者的说明层：把 `exec`、`apply_patch`、`web_search`、`browser`、`message`、`subagents`、媒体生成、技能、插件、审批策略等能力整理成可阅读的产品文档。

这个目录的核心职责可以分成三层。第一层是工具总览与选择，入口在 `docs/tools/index.md`，帮助读者区分 tools、skills、plugins，以及什么时候用内置工具、什么时候写 skill、什么时候通过 plugin 扩展。第二层是具体工具手册，例如 `docs/tools/exec.md`、`docs/tools/web.md`、`docs/tools/browser.md`、`docs/tools/media-overview.md`，说明工具能做什么、配置项在哪里、与其他工具的边界是什么。第三层是策略与故障处理，例如 `docs/tools/exec-approvals.md`、`docs/tools/exec-approvals-advanced.md`、`docs/tools/loop-detection.md`、`docs/tools/browser-linux-troubleshooting.md`，解释安全策略、审批流、循环检测、平台问题等运行时行为。

根据当前片段推断，`docs/tools` 在整个 docs 信息架构里承担“能力目录”的角色：它不直接定义 Gateway 配置 schema，也不实现工具注册逻辑，而是把散落在 core、plugins、providers、channels 里的能力，以用户可理解的方式聚合到 `/tools/...` 文档路径下。

## 直接子目录地图

`docs/tools` 当前没有直接子目录，所有页面都平铺在同一层。逻辑分组主要来自 `docs/docs.json` 的导航，而不是文件系统目录。

可以按内容角色把同层文件理解为几组：

运行与文件类：`docs/tools/exec.md`、`docs/tools/apply-patch.md`、`docs/tools/code-execution.md`、`docs/tools/elevated.md`、`docs/tools/exec-approvals.md`、`docs/tools/exec-approvals-advanced.md`。这一组说明命令执行、补丁应用、远端 Python 分析、提升权限和审批策略。

Web 与浏览器类：`docs/tools/web.md`、`docs/tools/web-fetch.md`、`docs/tools/browser.md`、`docs/tools/browser-control.md`、`docs/tools/browser-login.md`，以及 `docs/tools/brave-search.md`、`docs/tools/perplexity-search.md`、`docs/tools/exa-search.md`、`docs/tools/tavily.md` 等搜索 provider 页面。它们覆盖结构化搜索、页面抓取、浏览器自动化、登录态和平台排错。

多代理与会话类：`docs/tools/subagents.md`、`docs/tools/acp-agents.md`、`docs/tools/acp-agents-setup.md`、`docs/tools/agent-send.md`、`docs/tools/multi-agent-sandbox-tools.md`、`docs/tools/steer.md`。这一组解释代理之间如何派发、通信、转向和限制工具面。

媒体类：`docs/tools/media-overview.md`、`docs/tools/image-generation.md`、`docs/tools/video-generation.md`、`docs/tools/music-generation.md`、`docs/tools/tts.md`、`docs/tools/pdf.md`。它们描述图片、视频、音乐、语音、PDF 等媒体工具的入口和 provider 行为。

扩展与工作流类：`docs/tools/plugin.md`、`docs/tools/skills.md`、`docs/tools/creating-skills.md`、`docs/tools/skills-config.md`、`docs/tools/tool-search.md`、`docs/tools/llm-task.md`、`docs/tools/lobster.md`、`docs/tools/tokenjuice.md`。这一组说明如何增加能力、组织可复用工作流、搜索大工具目录、压缩工具输出。

辅助能力与行为说明：`docs/tools/thinking.md`、`docs/tools/slash-commands.md`、`docs/tools/reactions.md`、`docs/tools/diffs.md`、`docs/tools/trajectory.md`、`docs/tools/btw.md`、`docs/tools/loop-detection.md`。这些页面通常解释某个交互行为、调试能力或工具周边概念。

## 关键入口

最重要的入口是 `docs/tools/index.md`。它的定位是 “OpenClaw tools, skills, and plugins overview”，先讲 tools、skills、plugins 的边界，再列出代表性工具分类，并指向更深入页面。读这个页面可以先建立全局模型：工具是模型可见的结构化调用面，skills 是可复用指导和工作流，plugins 则能注册工具、provider、channel、hook、skill bundle 等更大的扩展面。

第二个入口是 `docs/tools/web.md`。它像 Web 能力的目录页，汇总 `web_search`、`web_fetch`、浏览器，以及 Brave、DuckDuckGo、Exa、Firecrawl、Gemini、Grok、Kimi、MiniMax、Ollama、Perplexity、SearXNG、Tavily 等 provider。搜索类页面数量很多，先读 `web.md` 能避免直接陷入单个 provider 的配置细节。

第三个入口是 `docs/tools/media-overview.md`。媒体工具页面也很多，先从 overview 看同步/异步任务、provider 选择和工具形态，再进入图片、视频、音乐、TTS 页面更合适。

第四个入口是 `docs/tools/plugin.md`、`docs/tools/skills.md` 和 `docs/tools/subagents.md`。它们分别对应“扩展能力”“复用流程”“协调多个 agent”。如果读者关心的是“如何让 OpenClaw 做更多事”，这三页比单个工具手册更关键。

## 主流程位置

工具文档的主流程从 `docs/tools/index.md` 开始：先选择能力类型，再根据任务进入对应工具族。需要本地执行时走 `docs/tools/exec.md`，涉及安全与审批再跳到 `docs/tools/exec-approvals.md` 和 `docs/tools/exec-approvals-advanced.md`；需要改文件时看 `docs/tools/apply-patch.md`；需要远端 provider 的代码分析时看 `docs/tools/code-execution.md`。

Web 主流程从 `docs/tools/web.md` 分叉：普通搜索看各 provider 页面，抓取 URL 看 `docs/tools/web-fetch.md`，复杂 JS、登录态或交互页面看 `docs/tools/browser.md` 和 `docs/tools/browser-control.md`，登录和平台问题再进入 `docs/tools/browser-login.md`、`docs/tools/browser-linux-troubleshooting.md`、`docs/tools/browser-wsl2-windows-remote-cdp-troubleshooting.md`。

扩展主流程从 `docs/tools/index.md` 的 “Choose tools, skills, or plugins” 分叉：已有工具但需要固定流程，读 `docs/tools/skills.md` 和 `docs/tools/creating-skills.md`；需要安装、启用或管理 plugin，读 `docs/tools/plugin.md`；需要写 plugin 工具时，再跳到 `docs/plugins/building-plugins` 和相关 plugin SDK 页面。这里的 `docs/tools/capability-cookbook.md`、`docs/tools/clawhub.md` 标题显示为 redirect，说明它们更像迁移或兼容入口，不是当前主说明页。

多代理主流程从 `docs/tools/subagents.md` 开始，进一步看 ACP 相关的 `docs/tools/acp-agents.md`、`docs/tools/acp-agents-setup.md`，以及消息发送的 `docs/tools/agent-send.md`。如果涉及子代理能否拿到工具、沙箱限制、session tools 暴露规则，则看 `docs/tools/multi-agent-sandbox-tools.md`。

## 推荐阅读顺序

1. 先读 `docs/tools/index.md`，建立 tools、skills、plugins 的总体边界，并了解各类代表工具。
2. 如果目标是日常使用 agent 能力，接着读 `docs/tools/exec.md`、`docs/tools/apply-patch.md`、`docs/tools/web.md`、`docs/tools/browser.md`。
3. 如果目标是配置安全策略，继续读 `docs/tools/exec-approvals.md`、`docs/tools/exec-approvals-advanced.md`、`docs/tools/elevated.md`、`docs/tools/loop-detection.md`。
4. 如果目标是 Web 能力选型，先读 `docs/tools/web.md` 和 `docs/tools/web-fetch.md`，再按 provider 选择 `docs/tools/brave-search.md`、`docs/tools/perplexity-search.md`、`docs/tools/exa-search.md` 等单页。
5. 如果目标是扩展 OpenClaw，读 `docs/tools/plugin.md`、`docs/tools/skills.md`、`docs/tools/creating-skills.md`、`docs/tools/tool-search.md`。
6. 如果目标是多 agent 协作，读 `docs/tools/subagents.md`、`docs/tools/acp-agents.md`、`docs/tools/agent-send.md`。
7. 最后再按需要读媒体和辅助页面，例如 `docs/tools/media-overview.md`、`docs/tools/image-generation.md`、`docs/tools/tts.md`、`docs/tools/diffs.md`、`docs/tools/trajectory.md`。

## 常见误区

第一个误区是把 `docs/tools` 当成工具实现目录。这里是文档，不是 runtime。真实工具注册、provider 路由、channel 行为、plugin SDK 合同通常在 `src/`、`extensions/`、`src/plugin-sdk/*`、`src/plugins/*` 等代码区；`docs/tools` 负责解释这些能力如何被用户理解和配置。

第二个误区是认为目录没有子目录就没有结构。实际结构由 `docs/docs.json` 导航和页面互链承担。文件系统是平铺的，但文档阅读上有明显分组：Tools 主组、Web browser 子组、搜索 provider 页面、媒体页面、多代理页面和扩展页面。

第三个误区是直接从单个 provider 页面开始读，例如先看 `docs/tools/grok-search.md` 或 `docs/tools/tavily.md`。这样容易错过 `docs/tools/web.md` 中对 provider 选择、托管搜索、fetch、browser 边界的统一说明。搜索类能力应先读总览，再读 provider。

第四个误区是混淆 tools、skills、plugins。工具是模型直接调用的结构化能力；skill 更像可复用的工作说明和流程知识；plugin 才是增加工具、provider、channel、hook 等能力的扩展包。`docs/tools/index.md` 专门解释这个边界，修改或学习扩展能力时应优先参考它。

第五个误区是只看 `exec`，忽略审批与 host 策略。`docs/tools/exec.md` 描述执行工具本身，但安全含义、审批行为、safe bins、elevated 模式需要结合 `docs/tools/exec-approvals.md`、`docs/tools/exec-approvals-advanced.md`、`docs/tools/elevated.md` 一起理解。
