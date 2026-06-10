# 文件：src/QueryEngine.ts

## 一句话定位

`src/QueryEngine.ts` 是非交互式会话的编排层：它把外部输入、系统提示词、AppState、权限判断、工具上下文、消息持久化和底层 `query()` 流式结果包装成 SDK 可消费的 `SDKMessage` 异步流。

## 它暴露/定义了什么

本文件主要定义三类接口：

`QueryEngineConfig`：创建一次会话引擎所需的完整配置，包括 `cwd`、`tools`、`commands`、`mcpClients`、`agents`、`canUseTool`、`getAppState`、`setAppState`、模型参数、预算参数、结构化输出 schema、回放选项、abort controller、孤儿权限处理等。

`QueryEngine` class：一个会话级对象。注释明确说明 “One QueryEngine per conversation”，每次 `submitMessage()` 是同一会话中的一个 turn，内部保留 `mutableMessages`、`readFileState`、累计 usage、权限拒绝记录、已加载 memory 路径、技能发现状态等。

`ask()`：一次性便捷包装器。它临时创建 `QueryEngine`，调用 `engine.submitMessage()`，最后把 `readFileState` 写回调用方缓存。旧的 print/headless 路径更可能直接使用它。

## 谁调用它

从仓库引用看，直接调用方主要有：

`src/cli/print.ts` 导入 `ask`，用于 `-p`/print/headless 这类非交互输出路径。

`src/services/acp/agent.ts` 直接创建 `new QueryEngine(engineConfig)`，并在 ACP session 中保存 `queryEngine`。随后通过 `queryEngine.submitMessage(promptInput)` 驱动请求，通过 `interrupt()`、`resetAbortController()`、`getAbortSignal()`、`setModel()` 支持 ACP 客户端的取消、重试和模型切换。

`src/services/acp/bridge.ts` 根据注释负责把 `QueryEngine.submitMessage()` 产出的 `SDKMessage` 转换成 ACP `SessionUpdate` 通知。

测试中 `src/services/acp/__tests__/agent.test.ts` mock 了 `QueryEngine`，说明 ACP agent 对它有明确边界依赖。

## 它调用谁

核心下游是 `src/query.ts` 的 `query()`。`QueryEngine` 负责准备 `messages`、`systemPrompt`、`userContext`、`systemContext`、`canUseTool`、`toolUseContext`、`fallbackModel`、`maxTurns`、`taskBudget` 等参数，然后消费 `query()` 返回的流式消息。

它还调用 `processUserInput()` 处理用户输入、slash command、附件、模型切换、允许工具规则等；调用 `fetchSystemPromptParts()` 组装系统提示词上下文；调用 `recordTranscript()`、`flushSessionStorage()` 持久化 transcript；调用 `fileHistoryMakeSnapshot()` 做文件历史快照；调用 `normalizeMessage()` 把内部 `Message` 映射为 SDK 消息；调用 `accumulateUsage()`、`updateUsage()` 统计 token usage。

此外，它会通过 feature-gated require 接入 `COORDINATOR_MODE`、`HISTORY_SNIP`，避免未启用功能的字符串和模块进入常规路径。

## 核心流程

`submitMessage()` 是主流程。它先从 config 解构运行环境，清空当前 turn 的技能发现和权限拒绝记录，设置 cwd，并判断 session 是否需要持久化。

然后它包装 `canUseTool`，在原权限逻辑之外记录被拒绝的工具调用，供最终 `result.permission_denials` 输出。

接着构造初始模型和 thinking 配置，调用 `fetchSystemPromptParts()` 获取默认 system prompt、用户上下文和系统上下文，再叠加自定义 prompt、memory mechanics prompt、append prompt，形成最终 `systemPrompt`。

随后构造 `ProcessUserInputContext`，先处理 orphaned permission，再调用 `processUserInput()`。该步骤会把原始 prompt 转成内部消息，也可能执行 slash command、改变模型、返回本地命令输出，或者决定 `shouldQuery=false`。

如果不需要请求模型，`QueryEngine` 会把本地命令输出、compact boundary 等转成 SDK 消息，写 transcript，并直接产出 `result success`。

如果需要请求模型，它先加载 slash-command skills 和插件缓存，产出 `system init` 消息，然后调用 `query()` 进入模型与工具循环。循环中它按消息类型更新 `mutableMessages`、写 transcript、累计 usage、转发 assistant/user/progress/attachment/compact/api_retry/tool_use_summary 等 SDK 事件，并处理最大轮数、预算、结构化输出重试上限等提前终止场景。

流结束后，它从最后一个 assistant 或 user 消息判断是否成功，失败则产出 `error_during_execution`，成功则提取文本结果、结构化输出、成本、usage、stop reason 等，产出最终 `result success`。

## 关键函数的高层作用

`QueryEngine.constructor()` 初始化会话级状态，不做重逻辑。重点是保存 config、初始消息、abort controller、文件读取缓存和 usage 计数。

`submitMessage()` 是文件的核心函数，承担一个 turn 的完整生命周期：输入预处理、系统上下文组装、权限包装、消息持久化、调用 `query()`、事件归一化、错误/预算/轮数控制、最终结果生成。

`interrupt()` 只负责 abort 当前 controller，用于外部取消正在运行的请求。

`resetAbortController()` 在取消后创建新的 controller，保证下一次 `submitMessage()` 不会复用已 aborted 的 signal。

`getAbortSignal()` 给 ACP bridge 等外部消费者监听当前请求取消状态。

`getMessages()`、`getReadFileState()`、`getSessionId()` 是状态读取接口。

`setModel()` 修改 config 中的 `userSpecifiedModel`，让后续 turn 使用新模型；实际模型解析仍在 `submitMessage()` 开始阶段完成。

`ask()` 是兼容型包装函数。它适合“一次 prompt，一次响应”的非交互路径，不负责长期 session 管理；长期会话应直接持有 `QueryEngine` 实例。

## 修改风险

最大风险是消息链和 transcript 持久化。`submitMessage()` 内部同时维护局部 `messages` 和实例级 `mutableMessages`，并在 assistant、user、progress、attachment、compact boundary 等分支中以不同策略写入 transcript。随意调整 push 或 record 顺序，可能导致 resume 断链、重复消息、compact 后历史无法裁剪，或 headless 结果为空。

第二个风险是 SDK 事件兼容性。这里输出的 `SDKMessage` 被 print、ACP、远控或外部客户端消费，字段如 `session_id`、`uuid`、`permission_denials`、`stop_reason`、`structured_output`、`fast_mode_state` 都有协议含义。改名、漏填或改变时机都可能破坏客户端。

第三个风险是权限与工具上下文。`wrappedCanUseTool` 不只是透传权限判断，还收集拒绝记录；`processUserInputContext` 中的 `readFileState`、`setAppState`、`updateFileHistoryState`、`handleElicitation` 会影响工具执行、副作用记录和 MCP 交互。修改时需要确认 SDK、ACP、print 三条路径都能工作。

第四个风险是 feature flag。文件中 `feature('COORDINATOR_MODE')`、`feature('HISTORY_SNIP')` 使用了 Bun 编译器敏感模式。仓库约束要求 `feature()` 只能直接出现在 `if` 或三元条件位置，不能随意抽变量或放进复杂表达式，否则可能破坏构建。

第五个风险是取消和长会话内存。`abortController`、snip/compact 裁剪、usage 累计、插件 cache-only 加载都服务于长时间 headless/ACP session。改动这些逻辑时，除了 `bun run typecheck`，还应重点跑 print 模式、ACP session、取消后再次发送、compact/resume、结构化输出和预算上限相关测试。
