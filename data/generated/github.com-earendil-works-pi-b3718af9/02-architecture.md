# 架构与模块边界

## 总体分层

这个仓库的架构可以按四层理解。最外层是 `packages/coding-agent`，它提供 `pi` CLI、配置、会话、工具、扩展、TUI/RPC/print 模式和对用户可见的行为。中间是 `packages/agent`，它提供不绑定具体 UI 的 agent state、agent loop、事件流、工具执行机制和更通用的 `AgentHarness`。再下一层是 `packages/ai`，它统一模型、provider、stream 事件、OAuth、API key 和模型元数据。并列的 UI 基础层是 `packages/tui`，它为 `coding-agent` 的 interactive mode 提供终端渲染和输入组件。

依赖方向从源码 import 可以直接看出：`packages/coding-agent/src/core/sdk.ts` 从 `@earendil-works/pi-agent-core` 导入 `Agent`，从 `@earendil-works/pi-ai` 导入 `streamSimple`、`Model`、`Message`，从自身 core 创建 `AgentSession`；`packages/coding-agent/src/modes/interactive/interactive-mode.ts` 同时导入 `@earendil-works/pi-tui`、`@earendil-works/pi-ai` 和 coding-agent core。`packages/agent/src/agent.ts` 依赖 `@earendil-works/pi-ai`，但不依赖 `coding-agent` 或 `tui`。`packages/ai` 是 provider 底座，不依赖 `agent` 或 `coding-agent`。这形成了较清晰的方向：`coding-agent -> agent + ai + tui`，`agent -> ai`，`tui` 基本独立，`ai` 最底层。

## 根目录职责

根目录不是应用源码层，而是 monorepo 控制层。`package.json` 定义 workspace、根脚本、Node 版本、devDependencies 和发布脚本。`tsconfig.json` 配置 workspace 路径别名，使 `@earendil-works/pi-ai` 等 import 在源码中指向 `packages/*/src`。`tsconfig.base.json` 设定 TypeScript/ESM 编译规则。`biome.json` 管理 lint/format。`test.sh` 控制无 API key 的测试环境。`scripts` 包含 release、local-release、shrinkwrap、dependency checks、stats、binary build 等维护脚本。读业务功能时，根目录主要用于理解“如何构建、检查、运行”。

## `packages/coding-agent` 产品层

`packages/coding-agent/src/cli.ts` 是发布 bin `pi` 对应的入口。它设置 `process.title`、`PI_CODING_AGENT`、屏蔽 warning、配置 HTTP dispatcher，然后调用 `main()`。`src/main.ts` 是启动编排中心：解析参数、处理 package/config 子命令、判断运行模式、读取 stdin、处理 `@file`、创建 `SessionManager`、加载 settings、project trust、extensions/resources、解析模型、组装 `CreateAgentSessionOptions`，最后进入某个 mode。

`src/core` 是业务核心。`sdk.ts` 提供 `createAgentSession()`，把 cwd、agentDir、AuthStorage、ModelRegistry、SettingsManager、SessionManager、ResourceLoader、工具配置和扩展 runner 组合成 `AgentSession`。`agent-session-services.ts` 创建 cwd-bound services，尤其在切换 session cwd 时保证 settings、resources、provider registrations 重新绑定。`agent-session-runtime.ts` 负责运行时持有当前 session 和 services，并支持 `switchSession()`、`newSession()`、`fork()`、`clone()`、`dispose()` 等会话替换操作。`agent-session.ts` 是产品层状态机，订阅底层 Agent 事件、持久化 session、发扩展事件、处理 compaction、retry、bash、model/thinking/tools 切换、slash commands 和系统 prompt。

`src/core/tools` 是内置工具边界。`index.ts` 汇总 `read`、`bash`、`edit`、`write`、`grep`、`find`、`ls`，并提供 `createCodingTools()`、`createReadOnlyTools()`、`createAllToolDefinitions()`。每个工具文件既定义 TypeBox 参数 schema，也定义执行逻辑和 TUI 渲染逻辑。`file-mutation-queue.ts` 用于协调文件写入类工具，避免并发编辑互相破坏。

`src/core/extensions` 是扩展边界。`types.ts` 定义扩展可以看到的 `ExtensionContext`、`ExtensionUIContext`、事件、注册工具/命令/provider 的接口。`loader.ts` 用 `jiti` 加载扩展模块，并为扩展提供虚拟模块或 aliases，使扩展能 import 本仓库包。`runner.ts` 负责把 `AgentSession` 生命周期、tool hooks、provider request hooks、project trust hooks 等发给扩展处理。`wrapper.ts` 把扩展注册的 `ToolDefinition` 包装成 agent tool。

`src/modes` 是 I/O 边界。`print-mode.ts` 负责单次 prompt 后输出最终文本或 JSON 事件；`rpc/rpc-mode.ts` 建立 JSONL stdin/stdout 协议，支持 prompt、abort、state、model、thinking、bash、session、export、fork 等命令；`interactive/interactive-mode.ts` 负责 TUI，处理 editor、selector、footer、消息组件、工具组件、扩展 UI、keybindings、clipboard、images、startup notices 等。

## `packages/agent` 运行时层

`packages/agent/src/agent.ts` 定义 `Agent` 类。它持有 `AgentState`，包括 systemPrompt、model、thinkingLevel、tools、messages、streaming 状态、pendingToolCalls 和 errorMessage。它还有 steering/follow-up 两个 pending queue，支持 `prompt()`、`continue()`、`abort()`、`waitForIdle()` 等能力。`Agent` 不知道 CLI、settings、session 文件或 TUI。

`packages/agent/src/agent-loop.ts` 是最核心的行为循环。它把 prompts 加入 context，调用 `streamAssistantResponse()`，把 `AgentMessage[]` 转换成 LLM `Message[]`，调用 `streamSimple()` 或自定义 streamFn，流式发出 assistant message 事件。若 assistant 返回 tool calls，则调用 `executeToolCalls()`，校验参数、执行工具、生成 `toolResult` 消息，然后进入下一轮。它还支持 steering messages、follow-up messages、`shouldStopAfterTurn()` 和 sequential/parallel 工具执行。

`packages/agent/src/harness` 是更通用的 harness 层。`agent-harness.ts` 结合 `ExecutionEnv`、session、resources、tools、stream options、hooks 和 compaction。`env/nodejs.ts` 提供 Node 环境下的文件系统与 shell 执行实现。根据当前文件推断，harness 面向嵌入式或新 SDK 风格的使用场景；`packages/coding-agent` 目前主要使用 `Agent` 加自己的 `AgentSession`，但也复用 `agent` 包中的 compaction、messages、skills 等概念。

## `packages/ai` Provider 层

`packages/ai/src/types.ts` 定义 provider 统一类型：`Api`、`KnownProvider`、`Model`、`Context`、`TextContent`、`ThinkingContent`、`ImageContent`、`ToolCall`、`Usage`、`AssistantMessage`、`ToolResultMessage`、`StreamOptions`、`Transport`。`api-registry.ts` 通过 `registerApiProvider()` 注册 `api -> stream/streamSimple` 实现。`stream.ts` 引入内置 provider 注册，然后 `stream()` 和 `streamSimple()` 通过 `model.api` 找 provider，并补环境变量 API key。

`src/providers/register-builtins.ts` 是内置 provider 的集中注册点。它为 Anthropic、OpenAI completions、OpenAI responses、OpenAI Codex responses、Azure OpenAI responses、Google、Google Vertex、Mistral、Bedrock 等 API 注册 lazy stream。具体 provider 文件负责协议转换、payload 构造、streaming event 解析、thinking/tool/image 兼容。`models.generated.ts` 与 `image-models.generated.ts` 是模型数据产物，生成脚本在 `packages/ai/scripts`。

## `packages/tui` UI 基础层

`packages/tui/src` 提供终端 UI 原语。README 中的核心接口是 `Component.render(width): string[]`，可选 `handleInput()` 和 `invalidate()`。`tui.ts` 管理 render loop、focus、overlay、terminal，`components` 提供 `Editor`、`Input`、`SelectList`、`Markdown`、`Loader`、`Image`、`Box`、`Container` 等。`terminal-image.ts`、native modifier 模块和 keybindings 支持跨平台输入和图片显示。`coding-agent` interactive mode 以此构建完整聊天界面。

## 存储边界

会话存储在 JSONL 文件中，由 `SessionManager` 管理。settings、auth、trust 都是 JSON 文件，并通过锁处理并发写。资源来自多个位置：全局 `agentDir`，项目 `.pi`，CLI 临时路径，package manager 安装路径，扩展声明的 resources，AGENTS/CLAUDE 上下文文件。`ResourceLoader` 是资源汇合点；`SettingsManager` 与 `ProjectTrustStore` 决定项目资源是否可信；`PackageManager` 决定 npm/git/local package 的资源路径。

## 扩展点

最重要的扩展点有五类。第一，扩展模块可通过 `registerTool()` 增加 LLM 可调用工具。第二，可通过 `registerCommand()` 增加 slash commands。第三，可通过 `registerProvider()` 增加模型 provider 配置。第四，可通过事件 hook 改写上下文、provider payload、tool call/result、session switching、compaction。第五，interactive/RPC 模式提供不同级别的 `ExtensionUIContext`，允许扩展请求 selector、confirm、input、editor、status、widget 等 UI。skills、prompt templates、themes 则是较轻量的资源扩展点。

## 依据文件

本文依据 `package.json`、`packages/coding-agent/src/cli.ts`、`packages/coding-agent/src/main.ts`、`packages/coding-agent/src/core/sdk.ts`、`packages/coding-agent/src/core/agent-session-services.ts`、`packages/coding-agent/src/core/agent-session-runtime.ts`、`packages/coding-agent/src/core/agent-session.ts`、`packages/coding-agent/src/core/resource-loader.ts`、`packages/coding-agent/src/core/extensions/*`、`packages/agent/src/agent.ts`、`packages/agent/src/agent-loop.ts`、`packages/ai/src/stream.ts`、`packages/ai/src/api-registry.ts`、`packages/tui/README.md`。
