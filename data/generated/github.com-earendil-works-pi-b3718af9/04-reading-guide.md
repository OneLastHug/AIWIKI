# 源码阅读指南

## 第一轮：建立主线

第一轮不要从 provider 细节、TUI 组件细节或 generated model 文件开始。先读 `README.md` 和 `packages/coding-agent/README.md`，只抓住四点：pi 是 terminal coding harness；默认有 `read`、`bash`、`edit`、`write` 工具；session 是 JSONL 树；扩展、skills、prompt templates、themes 都是可加载资源。然后读根 `package.json`，确认 monorepo 工作区和四个核心包。再读 `packages/coding-agent/package.json`，确认 `pi` bin 指向 `dist/cli.js`，源码入口对应 `src/cli.ts`。

接下来沿入口走：`packages/coding-agent/src/cli.ts` 很短，读完即可进入 `packages/coding-agent/src/main.ts`。`main.ts` 很长，不要逐行陷入所有分支，先标出五个区块：参数解析、模式判断、session manager 创建、settings/resource/model/trust/runtime 创建、启动 interactive/print/rpc mode。读到这里，就能解释 “执行 `pi -p` 和直接执行 `pi` 为什么走不同模式”。

## 第二轮：理解核心运行时

第二轮读 `packages/coding-agent/src/core/sdk.ts`、`agent-session-services.ts`、`agent-session-runtime.ts`、`agent-session.ts`。这四个文件是产品层核心。`sdk.ts` 解释怎样把 `Agent`、`SessionManager`、`SettingsManager`、`ModelRegistry`、`ResourceLoader`、工具和扩展组合成一个 `AgentSession`。`agent-session-services.ts` 解释为什么服务必须绑定 cwd。`agent-session-runtime.ts` 解释 session switch/new/fork/clone 如何替换当前 runtime。`agent-session.ts` 解释事件如何持久化、扩展如何接入、工具如何刷新、系统 prompt 如何构建、compaction/retry/bash/model/thinking 如何统一到一个 session 对象。

读 `agent-session.ts` 时建议先找方法和字段，不要先读每个组件渲染细节。重点看 constructor、`_installAgentToolHooks()`、`_handleAgentEvent`、`bindExtensions()`、`prompt()`、`runBash()`、`compact()`、`reload()`、`cycleModel()`、`setActiveTools()`。这些方法会把 `AgentSession` 的角色讲清楚：它不是底层 LLM loop，而是 CLI 产品逻辑与底层 agent runtime 的适配层。

## 第三轮：理解底层 loop

第三轮读 `packages/agent/src/agent.ts` 和 `packages/agent/src/agent-loop.ts`。`agent.ts` 说明 state、队列、订阅、prompt/continue/abort/waitForIdle 的外壳；`agent-loop.ts` 是真正的循环。建议从 `runAgentLoop()` 开始，再跳到 `runLoop()`、`streamAssistantResponse()`、`executeToolCalls()`、`prepareToolCall()`、`executeToolCallsParallel()`/`Sequential()`。读完后用一句话复述：用户消息进入 context，模型流式返回 assistant message，assistant 若要求工具则执行工具并追加 toolResult，再让模型继续，直到没有工具或队列消息。

这时再回头看 `packages/agent/README.md` 的 event sequence 会更容易。它列出的 `agent_start`、`turn_start`、`message_start`、`message_update`、`message_end`、`tool_execution_start`、`tool_execution_end`、`turn_end`、`agent_end` 与源码完全对应。interactive、print、rpc 都是消费这些事件，只是显示方式不同。

## 第四轮：读数据与配置

第四轮读 `packages/coding-agent/src/core/session-manager.ts`、`settings-manager.ts`、`auth-storage.ts`、`model-registry.ts`、`resource-loader.ts`、`package-manager.ts`、`trust-manager.ts`、`project-trust.ts`。这些文件解释 “状态从哪里来”。`session-manager.ts` 重点看 `SessionHeader`、`SessionEntry`、`buildSessionContext()`、`getDefaultSessionDir()`、`SessionManager` 构造与 `setSessionFile()`。`settings-manager.ts` 重点看 global/project merge 和 projectTrusted。`auth-storage.ts` 重点看 auth source 和 file lock。`model-registry.ts` 重点看内置模型、自定义 `models.json`、provider request config、OAuth、扩展 provider 的合并。`resource-loader.ts` 和 `package-manager.ts` 重点看 extensions/skills/prompts/themes/AGENTS 文件如何合并。

这轮阅读后再看 `packages/coding-agent/docs/settings.md`、`docs/session-format.md`、`docs/extensions.md`、`docs/skills.md`、`docs/prompt-templates.md` 会更有效，因为文档里的用户概念已经能落到源码对象上。

## 第五轮：根据目标下钻

如果目标是改内置工具，读 `packages/coding-agent/src/core/tools/index.ts`，再读对应工具文件。`read.ts` 包含文本和图片读取、截断、渲染；`bash.ts` 包含 shell 执行、超时、输出累计、进程树终止；`edit.ts`、`write.ts` 是文件修改核心；`grep.ts`、`find.ts`、`ls.ts` 是只读探索工具。改工具时同时找 `packages/coding-agent/test/tools.test.ts`、`path-utils.test.ts`、`file-mutation-queue.test.ts` 和相关回归测试。

如果目标是改模型/provider，先读 `packages/ai/src/types.ts`、`api-registry.ts`、`stream.ts`、`providers/register-builtins.ts`，再读具体 provider 文件。不要一开始改 `models.generated.ts`；模型生成逻辑在 `packages/ai/scripts/generate-models.ts`。如果目标是改模型选择或认证，读 coding-agent 的 `model-registry.ts`、`model-resolver.ts`、`auth-storage.ts`。

如果目标是改交互界面，先读 `packages/tui/README.md`，再读 `packages/tui/src/tui.ts`、`components/editor.ts`、`keybindings.ts`、`terminal.ts`。然后回到 `packages/coding-agent/src/modes/interactive/interactive-mode.ts`，按组件 import 逐个找对应 `components/*`。不要把业务状态写进 TUI 组件；现有模式是 `AgentSession` 管业务，InteractiveMode 管呈现和输入。

如果目标是改 RPC 或 SDK，RPC 先读 `packages/coding-agent/src/modes/rpc/rpc-types.ts`，再读 `rpc-mode.ts` 和 `rpc-client.ts`。SDK 先读 `packages/coding-agent/src/index.ts` 导出的公开面，再读 `core/sdk.ts`。更通用 harness 则从 `packages/agent/src/harness/agent-harness.ts` 和 `harness/types.ts` 入手。

## 可后读模块

`scripts`、发布脚本、shrinkwrap、native terminal modifier、HTML export 模板、图片 resize worker、version check、telemetry、clipboard、Windows self-update、theme JSON、docs images、示例扩展可以后读。它们很重要，但不是理解核心架构的第一步。`packages/ai/src/providers/*` 中的每个 provider 文件也可以按需阅读；先理解 registry 与统一类型，再看某个 provider 的协议转换。

## 可暂时跳过的文件

`packages/ai/src/models.generated.ts`、`packages/ai/src/image-models.generated.ts` 是生成结果，初学者不需要逐行读。`packages/tui/native/**/prebuilds/*.node` 是二进制产物。`packages/coding-agent/src/modes/interactive/assets/*`、theme JSON、export-html vendor JS 不是架构入口。大量测试 fixture 和截图也可在需要复现具体行为时再看。

## 推荐调试路径

遇到行为问题时，从测试名找入口。比如 session 问题找 `packages/coding-agent/test/session-manager` 和 `agent-session-*.test.ts`；扩展问题找 `extensions-*.test.ts`、`resource-loader.test.ts`、`package-manager.test.ts`；工具问题找 `tools.test.ts` 和具体工具测试；模型问题找 `model-registry.test.ts`、`model-resolver.test.ts`、`packages/ai/test/*`；TUI 问题找 `packages/tui/test` 和 interactive mode 组件测试。测试通常比 README 更贴近边界条件。
