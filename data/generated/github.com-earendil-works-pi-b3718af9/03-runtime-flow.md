# 运行时流程

## 启动入口

发布后的 `pi` 命令来自 `packages/coding-agent/package.json` 的 `bin: { "pi": "dist/cli.js" }`。源码入口是 `packages/coding-agent/src/cli.ts`。这个文件很短，但含义重要：它设置 `process.title = APP_NAME`，设置 `process.env.PI_CODING_AGENT = "true"`，屏蔽 `process.emitWarning`，调用 `configureHttpDispatcher()`，最后执行 `main(process.argv.slice(2))`。因此所有真实启动逻辑都在 `packages/coding-agent/src/main.ts`。

本地源码运行脚本 `pi-test.sh` 用 `tsx` 直接跑 `packages/coding-agent/src/cli.ts`，所以开发态和发布态使用同一套入口。`packages/coding-agent/src/bun/cli.ts` 与 `src/bun/register-bedrock.ts` 处理 Bun binary 相关路径和 provider 差异；根据当前文件推断，Node npm 安装和 Bun 编译二进制会在资源定位、Bedrock provider 加载、asset 拷贝上有不同处理，但业务主线仍回到 `main()`。

## 参数解析与模式判断

`main()` 先处理 offline：若参数包含 `--offline` 或 `PI_OFFLINE` 为真，则设置 `PI_OFFLINE=1` 和 `PI_SKIP_VERSION_CHECK=1`。接着处理 Windows self-update quarantine，处理 package/config 子命令，再调用 `parseArgs()`。`packages/coding-agent/src/cli/args.ts` 支持 provider/model/api-key/system-prompt/append-system-prompt/thinking/session/fork/session-dir/models/tools/extensions/skills/themes/list-models/project trust/offline 等参数；未知 `--flag` 会进入 `unknownFlags`，后续可能作为扩展 flag 解析。

`resolveAppMode()` 的规则很直接：显式 `--mode rpc` 返回 `rpc`；显式 `--mode json` 返回 `json`；`--print`、stdin 不是 TTY 或 stdout 不是 TTY 返回 `print`；否则返回 `interactive`。这条规则解释了为什么管道输入时不会启动全屏 TUI。若不是 interactive 且不是纯 metadata 命令，`main()` 会 `takeOverStdout()`，保证 JSON/print 输出不被日志和 TUI 干扰。

## 会话选择

`main()` 创建启动期 `SettingsManager` 后，根据 CLI、环境变量和 settings 决定 `sessionDir`。`createSessionManager()` 处理不同 session 入口：`--no-session`、`--help`、`--list-models` 使用内存 session；`--fork` 会解析路径、本地 session ID 或全局 session ID 并创建 fork；`--session` 可打开路径或本地 session，若命中其他项目 session，interactive 模式会询问是否 fork 到当前目录；`--resume` 打开选择器；`--continue` 继续最近 session；`--session-id` 可打开或创建固定 ID；默认则 `SessionManager.create(cwd, sessionDir)`。

`SessionManager` 的文件模型是 append-only JSONL。构造时如果有 session file，会 `loadEntriesFromFile()`、迁移旧版本、建立索引和 leaf；如果没有文件，会写入 session header。`buildSessionContext()` 沿 leaf 的 `parentId` 走到 root，收集 path，并把 message、custom message、branch summary、compaction summary 转成 agent 上下文。根据当前文件推断，`/tree` 和 `/fork` 不需要复制所有历史即可工作，因为同一文件里的 parent tree 已经表达分支。

## 配置、trust 与资源加载

启动时有两个阶段的 settings/resource 概念。第一阶段用当前 cwd 的 `startupSettingsManager` 只为 session lookup 和 sessionDir 服务。因为 `--session` 或 `--resume` 可能切到另一个 cwd，`main.ts` 注释明确说明最终 runtime cwd 要在创建 cwd-bound services 前确定。第二阶段通过 `createAgentSessionRuntime()` 和 `createAgentSessionServices()` 为有效 cwd 创建 `AuthStorage`、`SettingsManager`、`ModelRegistry`、`ResourceLoader`。

`SettingsManager.create(cwd, agentDir)` 会读全局 `agentDir/settings.json` 和项目 `cwd/.pi/settings.json`。项目 settings 只有在 project trusted 时才加载。`ResourceLoader.reload()` 会先在需要时触发 project trust：`loadProjectTrustExtensions()` 在不信任项目设置的状态下先加载用户/全局和 CLI 扩展，让扩展有机会处理 `project_trust`；随后根据 trust 结果加载最终 extensions、skills、prompts、themes、AGENTS/CLAUDE 上下文、system prompt 和 append prompt。非交互模式没有 UI 时，`resolveProjectTrusted()` 会按 `defaultProjectTrust` 或 `--approve`/`--no-approve` 决定。

`PackageManager.resolve()` 是资源来源展开器。它处理 settings 中的 package sources、本地路径、npm/git 安装路径、`.ignore`/`.gitignore` 类规则、resource precedence，并返回 extensions/skills/prompts/themes。`ResourceLoader` 再把这些路径分别交给 `loadExtensions()`、`loadSkills()`、`loadPromptTemplates()`、theme loader，并为每个资源附上 `SourceInfo`。这个流程使项目可以通过 `.pi`、全局配置、临时 CLI 参数和 package 共同扩展 pi。

## 模型与认证加载

`createAgentSessionServices()` 创建 `AuthStorage` 和 `ModelRegistry`。`AuthStorage` 的认证来源包括 `auth.json`、runtime `--api-key`、环境变量、fallback resolver 和 OAuth provider。`ModelRegistry.refresh()` 会 `resetApiProviders()`、`resetOAuthProviders()`，加载内置模型和 `models.json` 自定义模型/覆盖项，再应用扩展注册 provider。`getAvailable()` 返回已配置认证的模型；`findInitialModel()` 根据 scoped models、已有 session、settings default provider/model 和 provider defaults 找初始模型。

`createAgentSession()` 还会处理已有 session 的模型恢复。如果 session 中已有模型记录且 `modelRegistry` 能找到并认证，则恢复；否则记录 fallback message，并用设置默认或 provider 默认模型。thinking level 也类似：新 session 记录 model change 和 thinking change；已有 session 若没有 thinking entry，则用 settings default 或 `DEFAULT_THINKING_LEVEL`。随后调用 `clampThinkingLevel(model, thinkingLevel)` 保证 thinking level 不超过模型能力。

## AgentSession 创建

`createAgentSession()` 创建底层 `Agent`。它传入初始 state、`convertToLlmWithBlockImages()`、`streamFn`、`onPayload`、`onResponse`、`transformContext`、sessionId、steering/follow-up mode、transport、thinking budgets、retry delay 等。`streamFn` 的关键逻辑是：从 `ModelRegistry.getApiKeyAndHeaders(model)` 取认证和 headers，从 settings 取 retry/timeout/transport 参数，调用 `streamSimple(model, context, options)`。`onPayload` 和 `onResponse` 会把 provider 请求前后事件交给扩展。

然后 `createAgentSession()` 创建 `AgentSession`，传入 `Agent`、`SessionManager`、`SettingsManager`、cwd、ResourceLoader、customTools、ModelRegistry、active tool names、allow/deny tool names 和 extension runner ref。`AgentSession` 构造函数订阅底层 Agent 事件，安装 tool hooks，并调用 `_buildRuntime()` 构建系统 prompt、工具 registry、extension runner 和 active tools。根据当前文件推断，`AgentSession` 是 CLI 产品层和底层 `Agent` 之间的适配器：它既知道 session 文件和扩展，也知道如何把这些变成底层 Agent 的 state。

## Prompt 到 LLM 的调用链

用户输入进入某个 mode 后，最终会调用 `session.prompt(text, options)`。`AgentSession.prompt()` 会处理 prompt template 展开、skills 显式调用、输入事件 hook、preflight、pending next-turn messages、图片附件、slash command 或普通 prompt。普通 prompt 进入底层 `Agent.prompt()`，再进入 `packages/agent/src/agent-loop.ts` 的 `runAgentLoop()`。

`runAgentLoop()` 先把用户消息加入 context，发出 `agent_start`、`turn_start`、`message_start/end`。随后 `streamAssistantResponse()` 运行 `transformContext()`，再 `convertToLlm()`，构造 `{ systemPrompt, messages, tools }` 的 LLM context，调用 `streamSimple()`。`packages/ai/src/stream.ts` 根据 `model.api` 从 `api-registry` 找 provider；`packages/ai/src/providers/register-builtins.ts` 已经注册了 Anthropic、OpenAI、Google、Mistral、Bedrock 等 API 的 lazy stream。provider 产生 `start`、`text_delta`、`thinking_delta`、`toolcall_delta`、`done`、`error` 等事件，agent loop 转成 `message_update` 和最终 `message_end`。

如果 assistant message 的 content 包含 `toolCall`，`executeToolCalls()` 找到对应 `AgentTool`，运行参数 prepare/validate，再调用 `beforeToolCall` hook。未被阻止时执行工具，结束后调用 `afterToolCall` hook，并发出 `tool_execution_end` 与 `toolResult` message。toolResult 被加入 context 后，loop 进入下一 turn，再让模型基于 tool result 继续回答。若工具全部返回 `terminate: true`，或 `shouldStopAfterTurn()` 返回真，loop 会提前结束并发出 `agent_end`。

## 事件、持久化与扩展

`AgentSession` 订阅底层 Agent 事件后先向扩展发对应事件，再向 mode listener 发事件，然后在 `message_end` 时持久化。普通 user/assistant/toolResult message 通过 `SessionManager.appendMessage()` 写入 JSONL；custom message 使用专门 entry；assistant message 会被记录用于自动 compaction 和 retry 判断。`AgentSession` 还在 tool hook 中调用扩展的 `tool_call`、`tool_result`，在 provider hook 中调用 `before_provider_request` 和 `after_provider_response`。

模式层只关心事件如何显示或输出。`print-mode.ts` 在 JSON 模式下把 session header 和每个 `AgentSessionEvent` 序列化为 JSON 行；文本模式只输出最后 assistant 文本。`rpc-mode.ts` 把 stdin JSON command 映射到 `session.prompt()`、`session.abort()`、`session.setModel()`、`session.runBash()`、`runtimeHost.switchSession()` 等操作，并把事件和 response 写到 stdout。`interactive-mode.ts` 把事件转成 TUI 组件更新，维护 streaming assistant component、tool execution component、pending queues、footer、selector 和扩展 UI。

## Compaction 与重试

长会话处理在 `packages/coding-agent/src/core/compaction` 和 `AgentSession` 中。`AgentSession` 会根据 settings 判断自动 compaction 是否启用，也会在 context overflow 或阈值附近触发。`compact()` 会计算上下文 token、找 cut point、生成 summary，并把 compaction entry 写入 session。之后 `buildSessionContext()` 会把 compaction summary 放在上下文前部，同时保留 recent messages。重试逻辑由 settings 中 retry 配置控制，`AgentSession` 在 assistant error 后判断是否 retryable，发出 `auto_retry_start/end`，并调用底层 `Agent.continue()`。

## 依据文件

本文依据 `packages/coding-agent/src/cli.ts`、`packages/coding-agent/src/main.ts`、`packages/coding-agent/src/cli/args.ts`、`packages/coding-agent/src/core/agent-session-services.ts`、`packages/coding-agent/src/core/sdk.ts`、`packages/coding-agent/src/core/agent-session.ts`、`packages/coding-agent/src/core/resource-loader.ts`、`packages/coding-agent/src/core/session-manager.ts`、`packages/agent/src/agent-loop.ts`、`packages/ai/src/stream.ts`、`packages/ai/src/providers/register-builtins.ts`、`packages/coding-agent/src/modes/print-mode.ts`、`packages/coding-agent/src/modes/rpc/rpc-mode.ts`、`packages/coding-agent/src/modes/interactive/interactive-mode.ts`。
