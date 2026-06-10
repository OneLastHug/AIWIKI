# 运行时流程

## 进程启动

进程入口是 `src/entrypoints/cli.tsx`。文件第一行 shebang 指向 Bun，随后首先导入 `../utils/performanceShim.js`，注释说明这是为了在 React/OTel 捕获 native performance 前替换实现，避免长会话内存问题。接着导入 `feature` 和 `isEnvTruthy`，为 `MACRO.*` 提供直接运行源码时的 fallback，并处理 `CLAUDE_CODE_FORCE_INTERACTIVE`、`COREPACK_ENABLE_AUTO_PIN`、远程容器 `NODE_OPTIONS` 等环境修正。

`main()` 读取 `process.argv.slice(2)` 后先走快速路径。`--version`、`-v`、`-V` 直接打印 `MACRO.VERSION`，不会加载完整 CLI。之后才动态导入 `startupProfiler`。接下来按优先级判断 `--dump-system-prompt`、`--claude-in-chrome-mcp`、`--chrome-native-host`、`--computer-use-mcp`、`--acp`、`weixin`、`--daemon-worker`、remote-control/rc/remote/sync/bridge、`daemon`、`autonomy` 等模式。这些路径都尽量动态 import 目标模块，命中后执行并 return。根据当前文件推断，这种设计的目的包括降低普通启动成本、避免不必要模块副作用、让独立 MCP/ACP/daemon 模式不加载整套 TUI。

如果没有命中特殊路径，`cli.tsx` 才会进入默认完整 CLI 路径，导入 `src/main.tsx`。虽然本文档没有逐行列出默认路径末尾代码，但从文件结构和 `main.tsx` 导入关系可以确定，完整 CLI 的 Commander 定义和主 action 都在 `src/main.tsx`。

## 初始化与配置加载

`src/main.tsx` 顶部先执行若干启动期副作用：`profileCheckpoint('main_tsx_entry')`、`startMdmRawRead()`、`startKeychainPrefetch()`。注释说明这些操作用于并行化 MDM 读取和 macOS keychain 预取，降低启动等待。随后导入 Commander、chalk、context、init、history、REPL launcher、GrowthBook、MCP、policy limits、remote managed settings、tools、settings、permissions、plugins、skills 等大量模块。

一次性初始化集中在 `src/entrypoints/init.ts` 的 `init()`。它先 `enableConfigs()`，设置主题配置回调，然后 `applySafeConfigEnvironmentVariables()`，读取额外 CA 证书，设置 graceful shutdown，异步初始化 1P event logging 与 GrowthBook，启动 provider balance polling，预取 OAuth account info，初始化 JetBrains 检测和 git repository 检测，准备 remote managed settings 与 policy limits 的 loading promise。之后它记录 first start time，配置 mTLS 与代理，初始化 Sentry、用户信息、Langfuse，预连接 Anthropic API，处理远程容器 upstream proxy，设置 Windows shell，注册 LSP manager cleanup、session team cleanup、scratchpad 目录。证据来自 `init.ts` 的顺序调用。

配置来源分散在 `src/utils/config.js`、`src/utils/settings/`、`src/services/remoteManagedSettings/`、`src/services/policyLimits/`、认证工具和环境变量中。根据当前文件推断，完整启动的顺序是：先启用本地配置系统和安全环境变量，再做 trust/策略/远程配置相关检查，之后再构建 UI 或执行非交互式查询。具体 trust dialog 和主 action 细节需要继续读 `main.tsx` 中 `.action()` 的实现。

## CLI 命令分发

`src/main.tsx` 使用 `new CommanderCommand()` 创建 program，并注册多个进程级子命令。通过 `rg` 可见命令包括 `mcp` 及其 `serve/remove/list/get/add-json/add-from-claude-desktop/reset-project-choices`，`server`、`ssh <host> [dir]`、`open <cc-url>`，`auth login/status/logout`，`plugin validate/list/marketplace/add/remove/update/install/uninstall/enable/disable/setup-token`，`agents`，`auto-mode defaults/config/critique`，`autonomy status/runs/flows/flow/cancel/resume`，`doctor`，`update`，以及一些隐藏或 feature-gated 命令。进程级命令通常在 action 中完成后退出；默认 action 则进入 REPL 或 headless pipe 模式。

会话内 slash commands 由 `src/commands.ts` 聚合。`loadAllCommands()` 并行加载 skills、plugin commands、workflow commands 和内置 `COMMANDS()`；`getCommands(cwd)` 再按 availability、`isCommandEnabled()` 和 dynamic skills 过滤。`getSkillToolCommands()` 和 `getSlashCommandToolSkills()` 进一步筛选可被模型或 SkillTool 使用的 prompt commands。这个流程说明：用户在 REPL 里输入 `/login`、`/config`、`/compact`、`/memory` 等命令，与插件/skills/workflows 提供的命令共享一套聚合机制。

## REPL 挂载与输入处理

交互式 UI 的轻量桥是 `src/replLauncher.tsx`。`launchRepl()` 动态导入 `App`、`SentryErrorBoundary`、`REPL`，再把 `<App><REPL /></App>` 交给 `renderAndRun()`。`App` 提供状态、统计和错误边界；`REPL` 是真正的交互界面。

`src/screens/REPL.tsx` 引入大量 hook 和组件，包括 `PromptInput`、`PermissionRequest`、`ElicitationDialog`、`MessageSelector`、`useCanUseTool`、`useQueueProcessor`、`useRemoteSession`、`useSSHSession`、`useReplBridge`、`useLogMessages` 等。用户提交输入时，代码调用 `src/utils/handlePromptSubmit.ts` 的 `handlePromptSubmit()`。该函数先处理队列路径，再处理空输入、退出命令、粘贴引用展开、图片引用过滤、slash command 分发、本地 JSX immediate command、排队逻辑和最终查询调用。它通过 `onQuery()` 回调把新消息、abort controller、allowed tools、model 和 effort 交还给 REPL 的查询逻辑。

根据当前文件推断，REPL 的输入路径可概括为：`PromptInput` 采集文本、图片和模式信息；`handlePromptSubmit()` 解析输入和命令；如果是本地 immediate command，则执行命令并可能更新 UI；如果需要模型响应，则创建 user message、设置 loading/abort 状态，并调用查询路径；查询产生的 stream messages 再回写 messages 列表并触发 Ink 重渲染。

## 上下文构造

上下文由 `src/context.ts` 和 prompt 构造相关工具负责。`getSystemContext()` 会在非远程且 git instructions 启用时读取 git 状态，包含当前分支、主分支、git user、short status、最近 5 条 commit，并带有截断逻辑。它也可以在 `BREAK_CACHE_COMMAND` feature 下加入 cache breaker。`getUserContext()` 会按 `CLAUDE_CODE_DISABLE_CLAUDE_MDS`、bare mode、additional directories 等条件读取 `CLAUDE.md`/memory files，并加入当前日期。它还会把 CLAUDE.md 内容缓存到 bootstrap state，供 auto-mode classifier 使用。

系统 prompt 本体来自 `src/constants/prompts.js` 等文件，REPL 中也能看到 `getSystemPrompt()`、`buildEffectiveSystemPrompt()` 的导入。根据当前文件推断，请求前会把系统 prompt、system context、user context、消息历史、工具 schema 和 MCP/skill 信息合并成模型可消费的结构；具体拼接细节分散在 `src/utils/api.js`、`src/utils/messages.js`、`src/utils/systemPrompt.js` 和 `src/services/api/claude.ts`。

## QueryEngine 与 query loop

非交互式便利入口是 `QueryEngine.ts` 末尾的 `ask()`，它创建 `new QueryEngine({...})`，然后 `yield* engine.submitMessage(prompt)`。交互式 REPL 也依赖同一套 QueryEngine/Query 逻辑，只是状态和回调来自 UI。

`QueryEngine.submitMessage()` 的职责包括清理 turn-scoped tracking、设置 cwd、包装 `canUseTool` 以记录 permission denials、处理 session persistence、构建 `ProcessUserInputContext`、调用 `processUserInput()`、拉取 system prompt parts、加载 memory prompt、构造 toolUseContext，并最终调用 `query()`。它还负责 transcript 记录、SDK message 映射、成本/usage 累积、file history snapshot、structured output enforcement、flush session storage 等周边事务。这个类是理解“一个用户 prompt 如何变成一轮 agent turn”的最佳入口。

`src/query.ts` 是更底层的 async generator。它会 yield `stream_request_start`、assistant message、system/error/tombstone/message updates 等事件。它处理 prompt too long、max output tokens recovery、auto compact、tool result pairing、token budget continuation、Langfuse trace、cache warning、stop hooks、工具摘要等逻辑。`queryLoop()` 中当 assistant message 包含 tool_use blocks 时，会调用 `runTools()` 执行工具，并把返回的 tool_result messages 加回消息历史，继续下一轮模型请求，直到终止条件满足或达到 `maxTurns`。

## API 请求与 provider 分流

`src/services/api/claude.ts` 是模型 API 边界。它导入 Anthropic SDK 的 beta messages 类型，处理 tool schema、prompt cache、betas、usage、cost、quota、Langfuse observation、VCR、错误转换等。`queryModel()` 内部根据 `getAPIProvider()` 分流：OpenAI、Gemini、Grok 兼容层有独立函数；Bedrock、Vertex、Foundry 等在 client 层和请求参数层处理。`src/utils/model/providers.ts` 明确 provider 选择优先级：settings 中 `modelType` 优先，其次环境变量，最后默认 `firstParty`。

`src/services/api/client.ts` 创建 Anthropic client，并配置默认 headers，如 `x-app`、`User-Agent`、`X-Claude-Code-Session-Id`、远程容器/session header、自定义 header、认证 header、代理 fetchOptions、timeout 等。它会先刷新 OAuth token；如果不是 Claude AI subscriber，会配置 API key headers；然后按 Bedrock、Foundry、Vertex 等环境变量返回不同 SDK client。根据当前文件推断，API 层目标是让上游 `query()` 看到统一的 assistant message 流，而把 provider 差异封装在 `client.ts` 和 `claude.ts` 内。

## 工具执行与结果回流

工具列表由 `src/tools.ts` 装配。`getTools()` 先处理 simple mode、REPL mode、coordinator mode，再从 `getAllBaseTools()` 取内置工具并过滤特殊工具、权限 deny rules 和 `isEnabled()`。`assembleToolPool()` 将内置工具和 MCP tools 合并，按名称排序并去重。MCP tools 来自 `src/services/mcp/client.ts`，该文件处理 stdio/SSE/HTTP/WebSocket transport、OAuth、resources、prompts、tool call、输出截断和二进制内容持久化。

当模型返回 tool_use，`src/services/tools/toolOrchestration.ts` 的 `runTools()` 会把 blocks 分批。`partitionToolCalls()` 通过 `findToolByName()` 找工具，解析 input schema，并调用工具的 `isConcurrencySafe()`。并发安全的连续工具会进入 `runToolsConcurrently()`，受 `CLAUDE_CODE_MAX_TOOL_USE_CONCURRENCY` 控制，默认 10；非并发安全工具进入 `runToolsSerially()`。每个工具调用由 `runToolUse()` 执行，产出 message update 和可选 context modifier。query loop 收到 tool_result 后把它作为 user message 继续送入模型请求，形成 agentic loop。

## 状态、持久化与退出

运行时状态分布在 AppState 和 bootstrap state。`src/state/AppStateStore.ts` 定义 UI 可响应状态，如 messages 附近的任务、MCP、plugins、permissions、todos、notifications、remote bridge 状态等。`src/bootstrap/state.ts` 管 session id、project root、cwd、成本、token、last API request、cached CLAUDE.md、telemetry providers、session flags 等。会话持久化相关函数在 `src/utils/sessionStorage.js` 被多处调用，`QueryEngine` 会 `recordTranscript()`、`flushSessionStorage()`，REPL 会保存当前 session cost。退出时，`init.ts` 注册的 graceful shutdown、Langfuse shutdown、LSP shutdown、team cleanup 等清理钩子会执行。具体持久化文件路径和格式需要继续阅读 `src/utils/sessionStorage.ts`、`src/utils/config.js`、`src/utils/settings/`。
