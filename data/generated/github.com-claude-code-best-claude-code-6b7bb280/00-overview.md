# 项目整体介绍

## 项目定位

本仓库的 `package.json` 将项目命名为 `claude-code-best`，描述为一个“Reverse-engineered Anthropic Claude Code CLI”的终端 AI 编程助手；`README.md` 也明确说明它是对官方 Claude Code CLI 的反编译/逆向还原项目。基于这些文件可以确定：它不是一个普通聊天机器人前端，而是一个以终端为主界面的工程化 CLI，目标是在本地项目目录中读取上下文、接收用户输入、调用模型、执行工具、维护会话状态，并通过插件、MCP、远程控制、ACP、Computer Use、Voice Mode 等扩展能力覆盖更多工作流。仓库中出现的外部项目地址、文档站和徽章链接在本文档中不展开，统一视为 `[URL已移除]`。

## 它解决什么问题

从源码结构看，项目主要解决的是“把大模型变成可在开发者终端中持续工作的 coding agent”。这个问题拆成几个层次：第一，CLI 要能快速启动并处理 `--version`、MCP server、ACP、daemon、remote-control、模板任务等特殊入口，证据在 `src/entrypoints/cli.tsx` 的动态 import 快速路径。第二，完整模式需要加载配置、认证、策略限制、插件、技能、MCP 连接、工具权限和终端 UI，证据在 `src/main.tsx`、`src/entrypoints/init.ts`、`src/replLauncher.tsx`。第三，用户输入进入会话后，系统要构造 system prompt、user context、消息历史、工具列表和模型参数，再通过流式 API 获取 assistant 消息，证据在 `src/context.ts`、`src/QueryEngine.ts`、`src/query.ts`、`src/services/api/claude.ts`。第四，模型发起 tool_use 后，CLI 要按权限与并发规则执行本地工具或 MCP 工具，并把 tool_result 回写到下一轮请求，证据在 `src/tools.ts`、`src/Tool.ts`、`src/services/tools/toolOrchestration.ts` 和 `packages/builtin-tools/src/tools/`。

## 核心能力

核心能力可以概括为五组。第一组是交互式 REPL：`src/screens/REPL.tsx` 使用 React 与自定义 `@anthropic/ink` 终端渲染层，处理提示输入、消息列表、权限弹窗、通知、搜索、远程会话、SSH 会话和背景任务导航。第二组是模型请求主循环：`QueryEngine` 保存一段 conversation 的可变消息、读文件缓存、用量统计、权限拒绝记录等；`query.ts` 是流式查询和工具回合循环；`claude.ts` 负责将消息、工具 schema、betas、provider 信息组织成 API 请求。第三组是工具系统：`src/tools.ts` 从 `@claude-code-best/builtin-tools` 引入 `BashTool`、`FileReadTool`、`FileEditTool`、`FileWriteTool`、`GlobTool`、`GrepTool`、`WebFetchTool`、`WebSearchTool`、`AgentTool`、`SkillTool`、`TodoWriteTool` 等工具，并按 feature flag、环境变量、权限 deny rules、MCP 工具合并规则过滤。第四组是扩展系统：`src/commands.ts` 聚合内置 slash commands、技能目录、插件命令、workflow commands；`src/skills/bundled/index.ts` 注册内置 skills；`src/plugins/bundled/index.ts` 注册内置插件；`src/services/mcp/client.ts` 将 MCP server 的 prompts/resources/tools 转成 CLI 可用能力。第五组是远程与多模式运行：`src/bridge/`、`src/daemon/`、`src/services/acp/`、`src/ssh/`、`packages/acp-link/`、`packages/remote-control-server/` 分别支撑 remote-control、后台 daemon、ACP agent、SSH remote、自托管远程控制服务等模式。

## 主要模块

`src/entrypoints/` 是进入程序的最外层。`cli.tsx` 先做性能 shim、`MACRO` fallback、环境修正和快速路径判断；默认情况下才动态导入 `src/main.tsx`。`init.ts` 是一次性初始化，负责配置系统、环境变量、证书、代理、遥测、Langfuse、Sentry、OAuth 信息预取、policy/remote settings loading promise、清理钩子等。

`src/main.tsx` 是 CLI 面向用户的命令层。它使用 `@commander-js/extra-typings` 注册 `mcp`、`auth`、`plugin`、`agents`、`doctor`、`update`、`server`、`ssh`、`open`、`auto-mode`、`autonomy` 等子命令，并在主 action 中准备 REPL 或非交互式执行需要的上下文。由于该文件很大，初学者不应逐行通读，而应先搜索 `new CommanderCommand`、`.command(`、`.action(`、`launchRepl` 等关键点。

`src/query.ts`、`src/QueryEngine.ts`、`src/services/api/claude.ts` 是主循环模块。`QueryEngine.submitMessage()` 接收 prompt，处理用户输入、构造上下文、调用 `query()`，并把生成的 SDK message、transcript、成本和文件缓存状态串起来。`query()` 内部继续处理 token budget、auto compact、skill/search prefetch、工具执行、stop hooks、tool use summary 等逻辑。`claude.ts` 则与 Anthropic SDK 和兼容 provider 交界，代码中能看到 `queryModelWithStreaming`、`queryModelWithoutStreaming`、OpenAI/Gemini/Grok 分支和 Bedrock/Vertex/Foundry 相关客户端路径。

`packages/` 是 monorepo 的 workspace 层。`packages/builtin-tools` 存放主要工具实现，并通过 `exports` 暴露 `./tools/*`；`packages/@ant/ink` 是终端 UI 框架；`packages/@ant/model-provider` 抽象模型 provider；`packages/mcp-client` 提供 MCP 客户端工具函数；`packages/acp-link` 是 ACP WebSocket 代理服务；`packages/remote-control-server` 是自托管远程控制服务和 Web UI；若干 `*-napi` 包提供音频、图像、颜色、URL handler、键盘修饰键等本地能力。

## 初学者切入点

最适合初学者的入口不是最大文件，而是“从命令到一次模型请求”的路径。建议先读 `package.json`，确认运行命令、workspace、bin 和依赖；再读 `scripts/defines.ts`，理解默认 feature flags；然后读 `src/entrypoints/cli.tsx` 的 `main()`，只看它如何分流特殊模式和默认导入 `main.tsx`；接着读 `src/main.tsx` 中 Commander 命令注册和默认 action 附近的代码；之后跳到 `src/replLauncher.tsx` 和 `src/screens/REPL.tsx`，理解 UI 如何挂载；最后读 `src/QueryEngine.ts` 的 `submitMessage()`、`src/query.ts` 的 `query()`、`src/services/tools/toolOrchestration.ts` 的 `runTools()`。如果目标是理解工具，优先读 `src/Tool.ts` 和 `src/tools.ts`，再进入 `packages/builtin-tools/src/tools/FileReadTool`、`FileEditTool`、`BashTool`、`AgentTool` 等具体目录。

## 需要注意的背景

仓库带有明显的逆向/反编译痕迹，例如部分 React 组件包含 React Compiler 产物式结构，功能也大量由 `feature('FLAG')` 控制。`AGENTS.md` 明确要求 TypeScript strict 模式下 `bun run typecheck` 必须零错误，并说明 `feature()` 只能直接出现在 `if` 或三元条件位置，这是理解代码风格的重要约束。另一个特点是“主干和可选能力混在同一个仓库”：阅读时要分清 P0 主路径与可选分支。主路径是 CLI 启动、配置、REPL/headless、QueryEngine、API、工具执行、状态更新；可选分支包括 daemon、bridge、ACP、Voice、Computer Use、MCP skills、workflow scripts、remote-control server、微信插件等。
