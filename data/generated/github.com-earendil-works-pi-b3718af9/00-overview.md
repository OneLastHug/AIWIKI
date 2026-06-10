# 项目整体介绍

## 项目解决的问题

当前仓库是 `Pi Agent Harness Mono Repo`。根目录 `README.md` 直接说明它是 pi agent harness 项目的主仓库，包含一个 “self extensible coding agent”。从包说明可以看出，它解决的不是单一模型调用问题，而是把多 provider LLM、agent 循环、终端交互、会话树、工具调用、扩展、skills、prompt templates、主题、RPC/SDK 嵌入这些能力组合成一个可运行的 coding agent。用户最终看到的主要入口是 `pi` 命令；开发者看到的核心边界是四个包：`packages/coding-agent`、`packages/agent`、`packages/ai`、`packages/tui`。

仓库中 `packages/coding-agent/package.json` 的描述是 “Coding agent CLI with read, bash, edit, write tools and session management”，这说明产品层的核心能力是命令行 coding agent、内置文件/命令工具和 session 管理。`packages/agent/package.json` 描述为 “General-purpose agent with transport abstraction, state management, and attachment support”，说明它是更底层的 agent runtime。`packages/ai/package.json` 描述为 “Unified LLM API with automatic model discovery and provider configuration”，负责统一不同 LLM provider。`packages/tui/package.json` 描述为 “Terminal User Interface library with differential rendering”，说明交互式界面不是外部依赖，而是本仓库自研包。

## 核心能力

第一类能力是多模式运行。`packages/coding-agent/src/main.ts` 通过 `resolveAppMode()` 判断运行模式：`--mode rpc` 进入 RPC，`--mode json` 进入 JSON，`--print`、管道输入或非 TTY 输出进入 print，否则进入 interactive。`packages/coding-agent/src/modes/index.ts` 导出 `InteractiveMode`、`runPrintMode`、`runRpcMode`，说明这些模式共享同一核心会话，但外层 I/O 不同。`packages/coding-agent/README.md` 也说明 pi 运行在 interactive、print/JSON、RPC 和 SDK 四类形态中。

第二类能力是会话和分支。`packages/coding-agent/src/core/session-manager.ts` 定义 `SessionHeader`、`SessionEntry`、`SessionManager`，会话文件是 JSONL，第一行是 session header，后续 entry 带 `id` 与 `parentId`，形成树结构。`buildSessionContext()` 会沿当前 leaf 还原消息上下文，并处理 `compaction`、`branch_summary`、`custom_message`、模型切换和 thinking level 变化。这解释了为什么 README 中可以支持 `/tree`、`/fork`、`/clone` 和恢复历史 session。

第三类能力是 agent 循环和工具调用。`packages/agent/src/agent-loop.ts` 中 `runAgentLoop()` 先发出 `agent_start`、`turn_start`、用户消息事件，然后 `streamAssistantResponse()` 调用 LLM，若 assistant message 中包含 `toolCall`，则执行工具并生成 `toolResult`，再进入下一轮。`packages/coding-agent/src/core/tools/index.ts` 将内置工具整理为 `read`、`bash`、`edit`、`write`、`grep`、`find`、`ls`。`packages/coding-agent/src/core/sdk.ts` 默认启用 `read`、`bash`、`edit`、`write`，但 CLI 的 `--tools`、`--exclude-tools`、`--no-tools`、`--no-builtin-tools` 可调整。

第四类能力是 provider 统一和模型选择。`packages/ai/src/types.ts` 定义 `Model`、`Context`、`Message`、`AssistantMessage`、`ToolCall`、`ToolResultMessage`、`Transport` 等跨 provider 类型。`packages/ai/src/api-registry.ts` 提供 `registerApiProvider()` 和 `getApiProvider()`，`packages/ai/src/stream.ts` 的 `streamSimple()` 根据 `model.api` 找 provider 并执行。`packages/coding-agent/src/core/model-registry.ts` 再把内置模型、`models.json`、OAuth、API key 和扩展注册 provider 合并成 CLI 可用的模型注册表。

第五类能力是可扩展性。`packages/coding-agent/src/core/extensions/loader.ts` 用 `jiti` 加载 TypeScript/JavaScript 扩展模块，并向扩展暴露 `ExtensionAPI`。扩展可以注册工具、命令、快捷键、flags、message renderer、provider，也能处理 agent 生命周期事件。`packages/coding-agent/src/core/resource-loader.ts` 负责加载 extensions、skills、prompts、themes、AGENTS/CLAUDE 上下文文件和 system prompt。`packages/coding-agent/src/core/package-manager.ts` 还支持从本地、npm 或 git 来源解析包资源。

## 主要模块

`packages/coding-agent` 是产品壳和业务编排。`src/cli.ts` 设置进程标题、环境变量、HTTP dispatcher 后调用 `main()`；`src/main.ts` 解析 CLI 参数、处理 stdin 和 `@file`、创建 session manager、加载设置与资源、解析模型和 trust，再启动某个 mode；`src/core` 是真正的产品核心；`src/modes` 负责外部交互；`src/utils` 负责路径、shell、图片、clipboard、版本检查等平台工具。

`packages/agent` 是不依赖 TUI 的 agent runtime。`src/agent.ts` 包装 agent state、消息队列、事件订阅和 prompt/continue 生命周期；`src/agent-loop.ts` 是低层循环；`src/harness` 提供更通用的 `AgentHarness`、`ExecutionEnv`、session repo、compaction、skills、prompt template 能力。根据当前文件推断，`coding-agent` 仍主要直接使用 `Agent` 与自己的 `AgentSession`，而 `harness` 是对外或新架构的可复用层。

`packages/ai` 是 LLM provider 层。它把 provider 差异收敛到统一 stream 事件和消息类型，并包含 `models.generated.ts`、`image-models.generated.ts`、provider 实现、OAuth 工具、模型发现脚本。`packages/ai/src/providers/register-builtins.ts` 通过 lazy import 注册 OpenAI、Anthropic、Google、Mistral、Bedrock 等 API 适配器。

`packages/tui` 是终端 UI 层。README 说明它提供 differential rendering、CSI 2026 synchronized output、bracketed paste、组件接口、inline images、autocomplete。`packages/coding-agent/src/modes/interactive/interactive-mode.ts` 大量导入 `@earendil-works/pi-tui` 组件，说明 interactive mode 的界面状态、消息渲染、编辑器、selector、footer、overlay 都依赖这个包。

## 初学者切入点

如果目标是理解 “pi 命令启动后发生什么”，从 `packages/coding-agent/src/cli.ts` 进入，然后读 `packages/coding-agent/src/main.ts`，再读 `packages/coding-agent/src/core/sdk.ts`、`packages/coding-agent/src/core/agent-session-services.ts`、`packages/coding-agent/src/core/agent-session.ts`。如果目标是理解 “模型为什么会调用工具”，读 `packages/agent/src/agent-loop.ts` 和 `packages/coding-agent/src/core/tools/index.ts`。如果目标是理解 “怎么接 provider”，读 `packages/ai/src/stream.ts`、`packages/ai/src/api-registry.ts`、`packages/coding-agent/src/core/model-registry.ts`。如果目标是理解 “交互界面怎么工作”，读 `packages/coding-agent/src/modes/interactive/interactive-mode.ts` 和 `packages/tui/src`。如果目标是改扩展系统，先读 `packages/coding-agent/src/core/resource-loader.ts`、`packages/coding-agent/src/core/extensions/types.ts`、`packages/coding-agent/src/core/extensions/loader.ts`、`packages/coding-agent/docs/extensions.md`。

## 依据文件

本文依据 `README.md`、`packages/coding-agent/README.md`、各包 `package.json`、`packages/coding-agent/src/cli.ts`、`packages/coding-agent/src/main.ts`、`packages/coding-agent/src/core/sdk.ts`、`packages/coding-agent/src/core/agent-session.ts`、`packages/coding-agent/src/core/session-manager.ts`、`packages/agent/src/agent-loop.ts`、`packages/ai/src/stream.ts`、`packages/ai/src/api-registry.ts`、`packages/tui/README.md`。没有根据外部站点补充信息。
