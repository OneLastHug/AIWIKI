# 子系统：src/agents/pi-embedded-runner

## 解决什么问题

`src/agents/pi-embedded-runner` 是 OpenClaw 内置 Pi/Codex 风格 agent 的执行内核。它解决的不是“调用一次模型”这么简单的问题，而是把一次用户请求转成可恢复、可重试、可压缩、可观测的 agent 运行过程：选择模型和 provider、装配 system prompt 与历史上下文、构造工具、执行模型流、处理工具调用、记录 transcript、累积 usage、在上下文溢出或超时时压缩会话，并在鉴权、限流、空回复、server_error、context overflow 等失败场景下决定是否重试、切换 profile 或 fallback 到其他模型。

从调用关系看，上游主要通过 `src/agents/pi-embedded.ts`、`src/agents/pi-embedded.runtime.ts` 暴露 `runEmbeddedPiAgent`，实际 CLI/命令执行路径在 `src/agents/command/attempt-execution.ts` 调用它。因此这个目录是 agent request 生命周期的核心执行层，介于命令入口、provider runtime、context-engine、plugin hooks、工具系统和会话存储之间。

## 相关目录和文件

`src/agents/pi-embedded-runner/run.ts` 是最高层编排入口，导出 `runEmbeddedPiAgent`。它负责准备运行环境、解析 runtime plan、处理 lane、auth profile、模型 fallback、compaction、retry、失败信号和最终 `EmbeddedPiRunResult`。

`src/agents/pi-embedded-runner/run/attempt.ts` 是单次模型尝试的主体，导出 `runEmbeddedAttempt`。它更靠近一次 LLM boundary：准备消息、工具、bootstrap context、session steering、tool-call normalization、hook 调用和 transcript 策略。

`src/agents/pi-embedded-runner/run/backend.ts` 提供 `runEmbeddedAttemptWithBackend`，用于把 attempt 与具体后端执行、恢复逻辑连接起来。`run/setup.ts` 处理模型解析前后的 setup，例如 hook model selection、附件和有效 runtime model。`run/payloads.ts` 负责构造发送给模型/后端的 payload。

`src/agents/pi-embedded-runner/model.ts`、`model.static-catalog.ts`、`model.provider-normalization.ts` 等文件处理 provider/model 解析、静态 catalog、inline provider 和 forward compatibility。`extra-params.ts`、各种 `*-stream-wrappers.ts` 处理不同 provider 的请求参数与流式响应差异。

`src/agents/pi-embedded-runner/compact.ts`、`compact.runtime.ts`、`compaction-runtime-context.ts`、`context-engine-maintenance.ts` 组成上下文压缩与维护路径。`compact.ts` 导出 `compactEmbeddedPiSessionDirect`，在上下文溢出、主动压缩或 runner 恢复时使用。

`src/agents/pi-embedded-runner/types.ts` 是结果和 trace 类型中心，包含 `EmbeddedPiRunResult`、`EmbeddedPiRunMeta`、`TraceAttempt`、`ExecutionTrace`、`ContextManagementTrace`、`EmbeddedRunFailureSignal` 等。

## 核心对象

`runEmbeddedPiAgent` 是整个子系统的门面函数。它接收 `RunEmbeddedPiAgentParams`，输出 `EmbeddedPiRunResult`，并把多次 attempt、compaction、fallback 和最终可见回复合并成一次 agent run 的结果。

`runEmbeddedAttempt` 表示一次真实 attempt。它不负责所有跨 attempt 的策略，而是负责把当前 session、messages、tools、模型参数和执行上下文交给后端，并规范化返回结果。

`EmbeddedPiRunResult` 是上游最关心的返回对象。它承载最终文本、reply payload、usage、meta、trace、liveness/failure 信号等信息。`EmbeddedPiAgentMeta` 与 `EmbeddedPiRunMeta` 进一步记录模型、provider、token、工具摘要、上下文管理和失败恢复信息。

`compactEmbeddedPiSessionDirect` 是压缩入口。它会与 context-engine、session transcript、post-compaction hooks 配合，生成后继 transcript，并让后续 attempt 在压缩后的上下文上继续，而不是从头执行。

`resolveModelAsync`、`resolveModelWithRegistry`、`resolveEffectiveRuntimeModel` 是模型选择链上的关键函数。它们把默认 provider、显式模型、provider runtime、auth profile、hook 选择和 fallback 策略统一到最终可执行模型。

## 运行流程

典型流程从 `src/agents/command/attempt-execution.ts` 发起，调用 `runEmbeddedPiAgent`。runner 先解析 agent scope、workspace、session key、runtime plugin、auth profile、provider 配置和 context-engine 能力，然后进入受 lane 控制的执行区，避免同一 session 或全局运行互相踩踏。

随后 `run.ts` 选择有效模型，构建 payload 和 attempt 参数，调用 `runEmbeddedAttemptWithBackend`，后者再进入 `runEmbeddedAttempt`。attempt 会组装 system prompt、历史消息、附件、工具 schema、tool policy、runtime context prompt 和 provider 额外参数，并把模型输出流规范化为 assistant 文本、工具调用、usage 与 trace。

如果 attempt 成功，runner 会合并工具媒体 payload、usage、delivery evidence 和 transcript 状态，返回最终结果。如果出现空回复、reasoning-only、incomplete turn、idle timeout、rate limit、billing/auth 错误、context overflow 或 provider server error，`run.ts` 会通过 failover policy、auth controller、retry limit、compaction guard 等模块决定下一步：重试同模型、切换 auth profile、切换 fallback model、触发 context compaction，或返回/抛出失败。

上下文压缩是该流程的重要旁路。发生 token overflow、超时触发压缩或预防性压缩时，runner 会构造 compaction runtime context，调用 `compactEmbeddedPiSessionDirect` 或 context-engine 自有压缩路径，执行 post-compaction hooks，再用 continuation instruction 开启后继 attempt。

## 上下游依赖

上游依赖主要是 `src/agents/command/*` 的命令执行与交付路径、`src/agents/pi-embedded.ts` 的公开 barrel、以及测试中的 e2e harness。命令层把用户请求、session、目标 channel、工具 allowlist、模型偏好等传给 runner；runner 返回结果后，delivery 层再决定如何把回复送回用户。

下游依赖非常广。模型和鉴权依赖 `src/agents/model-auth.ts`、`src/agents/openai-codex-routing.ts`、`src/plugins/provider-runtime.ts`、`src/agents/runtime-plan/*`。上下文依赖 `src/context-engine/*` 和本目录的 `compact*` 模块。工具依赖 `src/agents/pi-tools.ts`、MCP runtime、工具 schema 与 tool result truncation。插件 hook 依赖 `src/plugins/hook-runner-global.ts`、`src/plugins/hook-agent-context.ts`。队列依赖 `src/process/command-queue.ts`。诊断、日志和事件依赖 `src/infra/*`、`logger.ts`、`delivery-evidence.ts`、`failure-signal.ts`。

根据当前片段推断，provider 差异被刻意收敛在 `extra-params.ts` 和各类 stream wrapper 中，依据是目录中存在 `google-stream-wrappers.ts`、`openai-stream-wrappers.ts`、`minimax-stream-wrappers.ts`、`moonshot-*`、`zai-stream-wrappers.ts`，且 `extra-params.*.test.ts` 覆盖多个 provider。

## 修改时最容易踩的坑

第一，不要把跨 attempt 策略塞进 `run/attempt.ts`。attempt 更像单次模型边界，retry、fallback、auth profile rotation、compaction loop guard 这类全局策略应留在 `run.ts` 或 `run/*policy*` 模块。

第二，不要在热路径随意加载完整 plugin/channel/provider runtime。`src/agents/AGENTS.md` 明确把 agent 测试慢视为架构信号；如果只需要静态能力、target 解析或 routing facts，应优先使用轻量 helper。

第三，改模型参数时要同时考虑 provider contract。`extra-params.ts`、stream wrapper、cache-control、reasoning effort、tool payload compat 都可能受影响，不能只让一个 provider 测试通过。

第四，改 compaction 时要保留 `sessionKey`、`sessionFile`、token budget、prompt cache、routing fields 和 successor transcript 语义。`run/AGENTS.md` 特别强调 full-runner 测试昂贵，但不能因此丢掉 context-engine 覆盖。

第五，失败恢复路径容易互相影响。空回复 retry、idle timeout breaker、auth profile cooldown、rate limit rotation、server_error fallback、post-compaction loop guard 都会改变下一次 attempt 的输入，修改时要看相邻测试而不是只看本文件。

## 推荐阅读顺序

1. 先读 `src/agents/pi-embedded.ts` 和 `src/agents/pi-embedded.runtime.ts`，了解对外导出面。
2. 再读 `src/agents/command/attempt-execution.ts`，看上游如何构造 runner 参数。
3. 阅读 `src/agents/pi-embedded-runner/types.ts`，先建立结果、trace、meta 的数据模型。
4. 阅读 `src/agents/pi-embedded-runner/run.ts`，把握顶层 orchestration。
5. 阅读 `src/agents/pi-embedded-runner/run/attempt.ts`、`run/backend.ts`、`run/payloads.ts`，理解一次模型调用如何形成。
6. 阅读 `model.ts`、`extra-params.ts` 和相关 stream wrapper，理解 provider/model 差异层。
7. 最后阅读 `compact.ts`、`compaction-runtime-context.ts`、`context-engine-maintenance.ts` 以及 `run.overflow-compaction*.test.ts`，理解上下文压缩和恢复语义。
