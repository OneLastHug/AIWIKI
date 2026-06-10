# 目录：packages

## 它负责什么

`packages` 是这个仓库的 npm workspace 主体，承载 Pi 的分层实现：底层是终端 UI 与统一 LLM API，中间是通用 agent loop，最上层是面向用户的 coding agent CLI。根 `package.json` 的 `workspaces` 指向 `packages/*`，并额外包含 `packages/coding-agent/examples/extensions/...` 下的示例扩展包；根构建脚本按 `tui -> ai -> agent -> coding-agent` 的顺序构建，说明这几个包之间存在自下而上的依赖关系。

整体可以理解为四层：

`@earendil-works/pi-tui` 提供终端渲染、输入、组件和编辑器能力；`@earendil-works/pi-ai` 提供跨 provider 的模型、流式响应、工具调用、OAuth、图片 API 等统一接口；`@earendil-works/pi-agent-core` 基于 `pi-ai` 封装 stateful agent、消息转换、工具执行和事件流；`@earendil-works/pi-coding-agent` 把前三者组合成实际的 `pi` 命令行产品，负责 CLI 参数、交互模式、print/JSON/RPC/SDK 模式、会话、配置、工具、扩展、技能、主题和包管理。

## 直接子目录地图

`packages/ai` 是 LLM provider 抽象层，包名为 `@earendil-works/pi-ai`。它的 `src/providers` 放各家模型服务适配，如 OpenAI、Anthropic、Google、Mistral、Bedrock、Cloudflare、GitHub Copilot 等；`src/api-registry.ts`、`src/models.ts`、`src/models.generated.ts`、`src/stream.ts`、`src/types.ts` 是理解文本模型主流程的关键；`src/images.ts`、`src/images-api-registry.ts`、`src/image-models*.ts` 负责图片模型；`scripts/generate-models.ts` 和 `scripts/generate-image-models.ts` 生成模型元数据。

`packages/agent` 是通用 agent core，包名为 `@earendil-works/pi-agent-core`。它不直接关心 coding agent 的终端产品形态，而是提供 `Agent`、agent loop、消息类型、状态管理、工具执行事件等。主要代码集中在 `src/agent.ts`、`src/agent-loop.ts`、`src/types.ts`，另有 `src/harness` 支撑更高层的 agent harness、compaction、session、env 和 prompt/skills 相关能力。

`packages/coding-agent` 是产品层，包名为 `@earendil-works/pi-coding-agent`，产物命令是 `pi`。它的目录最大，`src/cli` 处理命令行参数、初始消息、模型列表、配置选择、项目 trust 和会话选择；`src/core` 处理 agent session、工具、配置、会话管理、模型解析、prompt templates、skills、extensions、slash commands、telemetry 等核心业务；`src/modes` 放交互、print、RPC 等运行模式；`src/bun` 面向 Bun binary；`docs` 是用户文档；`examples` 是扩展示例；`npm-shrinkwrap.json` 用于发布时锁定该 CLI 的依赖树。

`packages/tui` 是终端 UI 库，包名为 `@earendil-works/pi-tui`。它的 `src/tui.ts`、`src/terminal.ts` 管理终端渲染和同步输出；`src/components` 放 Text、Input、Editor、Markdown、SelectList、SettingsList、Image、Box 等组件；`src/editor-component.ts`、`src/keybindings.ts`、`src/keys.ts`、`src/stdin-buffer.ts`、`src/terminal-image.ts` 负责编辑器、键盘输入和终端图片等交互基础设施；`native` 存放平台相关原生能力。

## 关键入口

包级入口首先看各自的 `src/index.ts`。`packages/ai/src/index.ts` 是统一 LLM API 的公共导出入口；`packages/agent/src/index.ts` 导出 agent core 能力；`packages/coding-agent/src/index.ts` 是 SDK/库入口，`packages/coding-agent/src/cli.ts` 和 `src/main.ts` 是命令行启动入口；`packages/tui/src/index.ts` 是终端 UI 组件和基础设施的导出入口。

可执行入口有两个：`packages/ai/package.json` 中的 `bin.pi-ai` 指向构建后的 `dist/cli.js`，对应源码 `packages/ai/src/cli.ts`；`packages/coding-agent/package.json` 中的 `bin.pi` 指向 `dist/cli.js`，对应源码 `packages/coding-agent/src/cli.ts`。实际用户使用的主 CLI 是后者。

构建入口由根 `package.json` 串联：先构建 `packages/tui`，再构建 `packages/ai`，再构建 `packages/agent`，最后构建 `packages/coding-agent`。这也反映依赖方向：`coding-agent` 依赖 `agent`、`ai`、`tui`；`agent` 依赖 `ai`；`tui` 更偏独立基础库。

## 主流程位置

LLM 请求主流程在 `packages/ai/src`。模型和 provider 注册从 `api-registry.ts`、`models.ts`、`providers/register-builtins.ts` 开始；具体调用路径落到 `src/providers/*.ts`；流式事件、工具调用片段、部分 JSON、上下文溢出、token 与 provider 兼容处理分别散落在 `stream.ts`、`types.ts`、`utils/*` 和 provider 文件中。

Agent 执行主流程在 `packages/agent/src/agent.ts` 与 `packages/agent/src/agent-loop.ts`。README 中描述的流程是 `AgentMessage[] -> transformContext() -> convertToLlm() -> Message[] -> LLM`，随后根据模型输出产生 assistant message、tool call、tool result，并通过事件流向上层 UI 或 SDK 发出 `agent_start`、`turn_start`、`message_update`、`tool_execution_*` 等事件。

Coding agent 产品主流程在 `packages/coding-agent/src/cli.ts`、`src/main.ts`、`src/modes/index.ts`、`src/modes/interactive`、`src/modes/rpc`、`src/modes/print-mode.ts` 和 `src/core/agent-session.ts`。用户输入先由 CLI 层解析，随后选择运行模式；交互模式接入 `pi-tui`，print/JSON 模式偏一次性输出，RPC 模式用于进程集成；核心 session 再组合配置、模型解析、工具管理、项目信任、会话持久化、compaction、extensions 和 skills，最终驱动 `pi-agent-core` 的 agent loop。

终端 UI 主流程在 `packages/tui/src/tui.ts`、`src/terminal.ts`、`src/components/editor.ts`、`src/editor-component.ts`。它负责 raw input、按键解析、组件树、焦点、overlay、差量渲染、同步输出和编辑器行为。`coding-agent` 的 interactive mode 根据当前片段推断会大量复用这些组件来呈现消息列表、输入框、选择器、状态栏和工具执行状态，依据是 `coding-agent` 依赖 `@earendil-works/pi-tui`，且 `tui` 暴露了完整组件库。

## 推荐阅读顺序

1. 先读根 `package.json` 和四个 `packages/*/package.json`，建立 workspace、构建顺序、包名、bin 和依赖方向。
2. 再读 `packages/coding-agent/README.md`，了解最终产品形态、运行模式、会话、配置、扩展和技能。
3. 接着读 `packages/coding-agent/src/cli.ts`、`src/main.ts`、`src/modes/index.ts`、`src/core/agent-session.ts`，把用户命令如何进入 agent session 串起来。
4. 然后读 `packages/agent/src/agent.ts`、`src/agent-loop.ts`、`src/types.ts`，理解 agent loop、消息转换、事件流和工具执行。
5. 再读 `packages/ai/src/index.ts`、`src/api-registry.ts`、`src/stream.ts`、`src/providers/register-builtins.ts` 以及一两个典型 provider，例如 `src/providers/anthropic.ts` 或 `src/providers/openai-responses.ts`。
6. 最后读 `packages/tui/src/tui.ts`、`src/terminal.ts`、`src/components/editor.ts`，理解交互界面如何渲染和接收输入。

## 常见误区

不要把 `packages/coding-agent` 当成全部核心逻辑。它是产品编排层，真正的 LLM 兼容细节在 `packages/ai`，通用 agent loop 在 `packages/agent`，终端 UI 基础能力在 `packages/tui`。

不要直接修改 `packages/ai/src/models.generated.ts` 来增删模型。仓库规则要求改 `packages/ai/scripts/generate-models.ts` 后再生成，图片模型同理应关注 `generate-image-models.ts` 与 `image-models.generated.ts` 的关系。

不要以为 `agent` 包只服务 CLI。`@earendil-works/pi-agent-core` 的 README 展示的是可嵌入的 stateful agent API，它面向更通用的应用集成；`coding-agent` 只是它的一个大型消费者。

不要忽略 `packages/coding-agent/docs` 和 `examples`。对 overview 来说它们不是主代码路径，但它们解释了扩展、RPC、SDK、settings、sessions、skills、themes 等高层概念，读产品流程时能帮助定位 `src/core/extensions`、`src/core/skills.ts`、`src/core/settings-manager.ts` 等模块的用途。

不要把 `test` 目录当成次要信息源。这个仓库测试文件很多，命名直接暴露了行为边界，例如 compaction、session branching、dynamic tools、RPC、trust、theme、export-html、provider 兼容等；当某个模块职责不清时，相关测试通常比逐文件扫源码更快说明主流程和边界条件。
