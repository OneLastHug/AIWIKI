# 源码阅读指南

## 阅读原则

这个仓库不适合按目录顺序通读。它有反编译/逆向还原背景，大量 feature flags、条件 require、兼容层、远程模式、插件与实验能力混在一起；如果从 `src/main.tsx` 或 `src/screens/REPL.tsx` 第一行开始硬读，很容易被边缘功能拖走。更好的策略是先沿一条可运行主线读：进程启动、完整 CLI 初始化、REPL 输入、QueryEngine、query loop、API 请求、工具执行、结果回流。主线清楚后，再按目标选择分支模块。

本文的优先级基于当前仓库真实文件推断：能解释核心运行链路的文件为 P0；能解释扩展能力和重要横切机制的为 P1；功能独立、依赖主线但不是理解主线必需的为 P2。

## P0：第一轮必须读

第一步读 `package.json`。它告诉你项目名、Bun engine、bin、workspace、scripts、核心依赖和 devDependencies。重点看 `scripts.build`、`scripts.dev`、`scripts.typecheck`、`workspaces`、`bin`、`dependencies` 中的 SDK/MCP/React/WS 信号。

第二步读 `scripts/defines.ts`、`build.ts`、`vite.config.ts`。这三者解释 `MACRO.*`、默认 feature flags、Bun build、Vite build、code splitting、Node/Bun 双入口和 raw asset 处理。读完它们，你会知道为什么源码里大量出现 `feature('X')`，也知道某些代码存在但运行时未必启用。

第三步读 `src/entrypoints/cli.tsx`。只关注 `main()` 的 if/return 分支，先不要深入每个被动态导入的模块。你要掌握哪些参数会走特殊模式，哪些情况下才进入完整 CLI。

第四步读 `src/entrypoints/init.ts` 和 `src/main.tsx` 的结构。`init.ts` 负责配置、环境、代理、证书、遥测、Langfuse、policy、remote settings、cleanup。`main.tsx` 很大，第一轮只看 Commander 命令注册、主 action、`getCommands()`、`getTools()`、`launchRepl()` 附近的调用，不要追所有子命令实现。

第五步读 `src/replLauncher.tsx`、`src/state/AppStateStore.ts`、`src/state/AppState.tsx`、`src/screens/REPL.tsx` 的关键路径。`replLauncher` 很短，先建立 App/REPL 挂载印象；AppStateStore 了解状态结构；REPL 只搜索 `handlePromptSubmit`、`onQuery`、`useCanUseTool`、`PermissionRequest`、`ask` 或 `QueryEngine` 相关调用，避免被 UI 细节分散。

第六步读 `src/QueryEngine.ts`、`src/query.ts`、`src/services/api/claude.ts`。这是最核心的 agent loop。建议先读 `QueryEngine` 顶部类型和 `submitMessage()`，再读文件末尾 `ask()`；然后读 `query.ts` 的 `QueryParams`、`query()`、`queryLoop()` 和调用 `runTools()` 的位置；最后读 `claude.ts` 的 streaming/non-streaming、provider 分流和错误处理。

第七步读 `src/Tool.ts`、`src/tools.ts`、`src/services/tools/toolOrchestration.ts`。这组文件解释工具如何定义、如何装配、如何过滤权限、如何与 MCP 合并、如何串行或并发执行。读完后再选几个具体工具目录，例如 `packages/builtin-tools/src/tools/FileReadTool`、`FileEditTool`、`BashTool`、`AgentTool`。

## P1：第二轮下钻

如果你关心配置与上下文，读 `src/context.ts`、`src/utils/claudemd.ts`、`src/constants/prompts.ts`、`src/utils/systemPrompt.ts`、`src/utils/settings/`、`src/utils/config.js`。重点理解 git status、`CLAUDE.md`、当前日期、settings、环境变量如何进入模型请求。

如果你关心命令与技能，读 `src/commands.ts`、`src/commands/`、`src/skills/bundled/index.ts`、`src/skills/loadSkillsDir.ts`、`src/plugins/bundled/index.ts`、`src/utils/plugins/`。重点看 command 的 `type`、`immediate`、`loadedFrom`、`disableModelInvocation`、`whenToUse` 等字段如何决定它是用户命令还是模型可调用 skill。

如果你关心 API 兼容，读 `src/utils/model/providers.ts`、`src/services/api/client.ts`、`src/services/api/openai/`、`src/services/api/gemini/`、`src/services/api/grok/`、`packages/@ant/model-provider/`。重点看 provider 选择优先级、认证 header、消息格式转换、流式事件适配和 usage 统计。

如果你关心 MCP，读 `src/services/mcp/client.ts`、`src/services/mcp/config.ts`、`src/services/mcp/types.ts`、`packages/mcp-client/src/`，再看 `ListMcpResourcesTool`、`ReadMcpResourceTool`、`MCPTool`、`McpAuthTool`。MCP 代码量不小，建议先理解 transport 和 tool conversion，再追 OAuth 与 elicitation。

如果你关心状态与持久化，读 `src/bootstrap/state.ts`、`src/utils/sessionStorage.ts`、`src/history.js`、`src/cost-tracker.ts`、`src/utils/fileHistory.ts`。这里能解释 session id、transcript、成本、history、文件快照和恢复逻辑。

## P2：理解主线后再读

`src/bridge/`、`packages/remote-control-server/` 适合在理解 REPL 和 QueryEngine 后阅读。它们处理 remote-control、桥接环境、Web UI、权限回调和远程事件流，概念上依赖主会话模型。

`src/services/acp/`、`packages/acp-link/` 适合在理解 QueryEngine 后阅读。ACP agent 会创建或复用 QueryEngine，并把 `submitMessage()` 的 SDK messages 转成 ACP session update。它不是主 CLI 的第一入口，但能帮助理解该项目如何被 IDE 或外部 agent client 驱动。

`src/daemon/`、`src/tasks/`、`src/coordinator/`、`src/assistant/`、`src/remote/` 适合在理解工具、任务状态和后台会话后阅读。这些模块围绕后台 worker、多 agent、assistant/Kairos、远程任务编排展开。

`src/voice/`、`packages/@ant/computer-use-*`、`packages/audio-capture-napi`、`packages/image-processor-napi`、`packages/color-diff-napi`、`packages/modifiers-napi`、`packages/url-handler-napi` 可以后读。它们是重要能力，但对理解一次普通文本 prompt 的模型请求不是必需。

`docs/`、`spec/`、`teach-me/` 可以作为辅助资料，不建议替代源码。文档能提供背景和设计意图，但本学习路线以真实入口、构建配置和源码结构为准。

## 可暂时跳过的内容

第一轮可以跳过 `vendor/`、构建产物 `dist/`（如果存在）、图片和 logo 资源、具体测试 fixture、大部分 feature 文档、远程控制 Web UI 的视觉细节、很具体的插件市场 UI、少数 ant-only 或实验命令。也可以暂时跳过 `README.md` 中的外部链接和宣传性描述，只保留环境要求、运行命令、feature flags 和项目定位信息。

## 继续下钻顺序

完成 P0 后，建议选择一个目标主题继续：想改工具就从 `src/tools.ts` 到 `packages/builtin-tools/src/tools/<ToolName>`；想改模型兼容就从 `providers.ts` 到 `client.ts` 到 `claude.ts` 到具体 provider 目录；想改 REPL 体验就从 `REPL.tsx` 到 `components/PromptInput/`、`components/permissions/`、`state/`；想改 slash command 就从 `commands.ts` 到对应 `src/commands/<name>/`；想改远程控制就从 `cli.tsx` 的 bridge 快速路径到 `src/bridge/bridgeMain.ts`，再到 `packages/remote-control-server/`。每次下钻都先找入口和类型，再读实现细节，最后看测试。
