# 子系统：src/agents/pi-embedded-runner/run

## 解决什么问题

`src/agents/pi-embedded-runner/run` 是 OpenClaw 内嵌 Pi agent 单次“尝试执行”的核心子系统。它不负责整个 agent run 的外层重试循环，而是把一次模型调用前后的所有运行时条件准备好：会话历史、系统提示词、工具集合、图片、context engine、auth profile、prompt cache、compaction、stream 包装、tool result、最终回复 payload、诊断事件和清理动作。

从调用关系看，外层入口在 `src/agents/pi-embedded-runner/run.ts`，它负责选择 provider/model、failover、重试、compaction 后续处理、lane queue 等更高层策略；真正进入一次执行时通过 `runEmbeddedAttemptWithBackend` 调到 `src/agents/harness/selection.ts`，再由内置 Pi harness `src/agents/harness/builtin-pi.ts` 指向 `run/attempt.ts`。因此本目录可以理解为“attempt runtime”：把一个已决策好的 run attempt 变成实际 LLM 会话和可交付结果。

## 相关目录和文件

本目录的主入口是 `src/agents/pi-embedded-runner/run/attempt.ts`，它组合绝大部分 helper，执行 `runEmbeddedAttempt`。`src/agents/pi-embedded-runner/run/backend.ts` 是后端适配层，目前把 attempt 委托给 agent harness 选择器，使 Pi 内置执行与插件 harness 共用同一分发路径。

类型边界集中在 `src/agents/pi-embedded-runner/run/params.ts` 和 `src/agents/pi-embedded-runner/run/types.ts`。前者定义外层 runner 传入的 `RunEmbeddedPiAgentParams`，包含 session、channel、trigger、workspace、prompt、工具策略、stream callback、timeout、auth 等输入；后者定义 `EmbeddedRunAttemptParams` 和 `EmbeddedRunAttemptResult`，是 attempt 层与外层重试/failover/交付逻辑之间的契约。

若按职责分组，`setup.ts` 处理 hook 影响下的模型选择和 context window guard；`auth-controller.ts` 管理 auth profile、runtime auth refresh 和 provider request override；`attempt-tool-construction-plan.ts` 决定哪些工具需要构造和按 allowlist 过滤；`attempt-system-prompt.ts`、`attempt.prompt-helpers.ts`、`runtime-context-prompt.ts` 负责系统提示词、运行时上下文和 prompt 注入；`preemptive-compaction.ts`、`compaction-timeout.ts`、`compaction-retry-aggregate-timeout.ts` 处理上下文压力与 compaction 超时；`payloads.ts` 把 assistant/tool 结果转成对上层可交付的 reply payload；`failover-policy.ts`、`assistant-failover.ts`、`retry-limit.ts` 辅助外层做失败分类和重试决策。

## 核心对象

`RunEmbeddedPiAgentParams` 是外部请求形态，既包含用户输入，也包含通道和运行策略。它的字段很多，说明这个子系统处在多条链路交汇点：聊天通道、CLI、cron、heartbeat、memory、subagent 和 model probe 都会复用同一套 run attempt 入口。

`EmbeddedRunAttemptParams` 是经过外层准备后的执行参数。它要求明确的 `provider`、`modelId`、`model`、`authStorage`、`modelRegistry`、`thinkLevel`，还可携带 `contextEngine`、`runtimePlan`、`agentHarnessTaskRuntimeScope`、`onToolOutcome` 等运行时对象。也就是说，外层负责“选什么”，attempt 层负责“怎么跑”。

`EmbeddedRunAttemptResult` 是 attempt 的完整结果快照。它不仅有 `aborted`、`timedOut`、`promptError`、`promptErrorSource`，还包括 `assistantTexts`、`toolMetas`、`lastAssistant`、消息工具投递证据、media URL、usage、prompt cache、context budget、compaction 计数、client tool calls、yield 状态和 replay metadata。外层 runner 依赖这些字段判断是否发回复、是否 failover、是否重试、是否压缩上下文，以及如何记录 trajectory。

## 运行流程

根据当前片段推断，一次 run 的上游流程是：`src/agents/pi-embedded-runner/run.ts` 解析 session/workspace、模型、auth profile、context engine、runtime plan 和 failover 状态，然后调用 `runEmbeddedAttemptWithBackend`。`backend.ts` 进入 `runAgentHarnessAttempt`，如果选择内置 Pi harness，则执行 `run/attempt.ts` 的 `runEmbeddedAttempt`。

在 attempt 内部，流程大致是先建立 session 和 resource loader，修复或读取历史，组装系统提示词、bootstrap/runtime context 和当前 prompt；随后根据 `disableTools`、`toolsAllow`、通道能力、plugin tool、MCP/LSP、code mode、tool search 等条件构造工具列表。模型调用前还会做 context window 与 preemptive compaction 检查，必要时返回可恢复的 preflight signal，而不是盲目把超大 prompt 送进模型。

真正发起模型流式调用时，attempt 会叠加多层 stream wrapper：例如 idle timeout、tool call 参数修复、tool name normalization、stop reason recovery、diagnostic model event、provider text transform、prompt cache 观察等。订阅层把 assistant 输出、工具调用、tool result、message tool 投递、media payload、session spawn/yield 等事件写回 session，并同步更新 active run snapshot 和 trajectory metadata。

模型结束后，`payloads.ts` 根据 assistant 文本、tool meta、最后一次工具错误、silent reply token、heartbeat response、message tool 是否已投递等条件生成上层 reply payload。attempt 同时返回 replay metadata、usage、context budget、tool media 和错误分类，交由外层继续处理 retry、failover、compaction side effects 或最终交付。

## 上下游依赖

上游主要是 `src/agents/pi-embedded-runner/run.ts`、`src/agents/harness/selection.ts`、`src/agents/harness/builtin-pi.ts`，以及 CLI 侧的 `src/agents/cli-runner/*`。CLI runner 复用了本目录的一些 prompt/image helper，说明这些 helper 已经被抽成跨运行时的纯逻辑，而不是只服务 embedded Pi。

下游依赖分布很广。模型与 session 来自 `@earendil-works/pi-ai`、`@earendil-works/pi-agent-core`、`@earendil-works/pi-coding-agent`。OpenClaw 内部依赖包括 `src/context-engine/*`、`src/plugins/*`、`src/config/sessions/*`、`src/trajectory/*`、`src/agents/pi-tools.ts`、`src/agents/pi-bundle-mcp-tools.ts`、`src/agents/code-mode.ts`、`src/agents/tool-search.ts`、`src/agents/session-transcript-repair.ts`、`src/agents/runtime-plan/*`、`src/agents/harness/*` 等。它还依赖通道上下文和消息投递策略，例如 message tool、heartbeat tool、Slack/Telegram 风格的 thread/target 信息，但通道实现本身不应该被硬编码进 attempt。

## 修改时最容易踩的坑

第一，不能把外层 retry/failover 职责塞进 `attempt.ts`。attempt 可以产出精确的错误来源和结果证据，但“是否换模型、是否换 profile、是否继续重试”主要由 `src/agents/pi-embedded-runner/run.ts` 和 `failover-policy.ts` 决定。

第二，工具构造要尊重 allowlist、runtime policy、channel tool、plugin tool、bundle MCP/LSP 和 code mode 的组合。随手在 `attempt.ts` 里添加工具，很容易绕开 `attempt-tool-construction-plan.ts` 和 `pi-tools.policy.ts` 的策略边界。

第三，context engine 与 compaction 是强契约。`preemptive-compaction.ts` 的估算、`promptErrorSource` 的分类、`timedOutDuringCompaction` 的标记会影响外层是否安全重放。把 compaction 错误当普通 prompt 错误重试，可能导致同一工具 turn 被重复执行。

第四，session 写入和 transcript 修复不能随意绕开锁。目录中有 `attempt.session-lock.ts`、`attempt.subscription-cleanup.ts`、`session-transcript-repair` 相关调用，说明运行中可能存在订阅事件、外部 hook、tool result 和 session manager 并发写入。

第五，payload 不是简单取最后一条 assistant 文本。`payloads.ts` 会处理 silent reply、message tool 已投递、mutating tool error warning、heartbeat response、source suppression delivery、reasoning/visible text 分离等规则。改回复行为时应先读这个文件和对应测试。

## 推荐阅读顺序

1. 先读 `src/agents/pi-embedded-runner/run.ts`，理解外层 run loop、模型选择、failover、compaction 和 attempt 调度。
2. 再读 `src/agents/harness/selection.ts`、`src/agents/harness/builtin-pi.ts`、`src/agents/pi-embedded-runner/run/backend.ts`，确认 attempt 如何接入 harness。
3. 读 `src/agents/pi-embedded-runner/run/params.ts` 和 `src/agents/pi-embedded-runner/run/types.ts`，先掌握输入输出契约。
4. 读 `src/agents/pi-embedded-runner/run/setup.ts`、`auth-controller.ts`、`attempt-tool-construction-plan.ts`，理解模型、认证和工具准备。
5. 读 `src/agents/pi-embedded-runner/run/attempt.ts`，只按“准备 prompt、准备工具、调用模型、订阅事件、返回结果”的主线阅读。
6. 最后读 `payloads.ts`、`preemptive-compaction.ts`、`failover-policy.ts`、`incomplete-turn.ts` 和相邻测试，理解边界行为与回归保护。
