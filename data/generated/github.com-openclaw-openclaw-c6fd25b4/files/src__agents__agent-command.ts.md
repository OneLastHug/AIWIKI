# 文件：src/agents/agent-command.ts

## 一句话定位

`src/agents/agent-command.ts` 是 OpenClaw “执行一次 agent turn”的核心编排入口：它不直接实现模型运行、消息投递或会话存储的底层细节，而是把 CLI、本地嵌入、Gateway ingress、OpenAI 兼容接口等入口传来的 `AgentCommandOpts` 规范化为一次可执行的 agent 请求，并负责会话选择、模型选择、ACP/普通运行分流、fallback、生命周期事件、 transcript 落盘和最终投递。

## 它暴露/定义了什么

该文件主要导出三个公开面：

`agentCommand(opts, runtime, deps)` 是本地/CLI 可信入口。它会默认把 `senderIsOwner` 设为 `true`，并默认允许单次 provider/model override，所以适合本机 operator 或 CLI 流程。

`agentCommandFromIngress(opts, runtime, deps)` 是网络入口或外部 ingress 使用的入口。它强制调用方显式传入 `allowModelOverride`，并且只有 `senderIsOwner === true` 时才认为发送者是 owner，避免网络路径意外继承本地信任默认值。

`testing` / deprecated `__testing` 暴露 `resolveAgentRuntimeConfig` 和 `prepareAgentCommandExecution`，供测试验证准备阶段的配置、会话和上下文解析。

文件内部还定义了 `prepareAgentCommandExecution`、`agentCommandInternal`、若干 lazy runtime loader、会话持久化辅助、override 输入校验和 pending final delivery 清理函数。辅助函数主要服务于主流程，不是对外 API。

## 谁调用它

从当前仓库片段看，`src/commands/agent.ts` 直接 re-export 该文件，使 CLI/命令层可以通过 commands facade 使用它；`src/plugin-sdk/agent-runtime.ts` 也 re-export 它，让插件 SDK 层能拿到 agent runtime 能力。`src/tui/embedded-backend.ts` 直接调用 `agentCommandFromIngress`，说明 TUI 嵌入后端按 ingress 信任模型接入。Gateway 相关路径中，`src/gateway/openai-http.ts` 和 `src/gateway/openresponses-http.ts` 会把 OpenAI Chat/Responses 兼容请求转换成 agent command input 后调用 `agentCommandFromIngress`。测试中大量 `src/gateway/*`、`src/commands/*`、`src/agents/*` 用 mock 或 helper 验证它收到的参数和行为。

## 它调用谁

它调用的下游可以按职责分组理解。

配置与会话：`resolveAgentRuntimeConfig`、`resolveSession`、`getRuntimeConfig`、`session-store.runtime`、`transcript-resolve.runtime`、`routing/session-key` 负责读取配置、解析 agent/session key、定位 session store 和 transcript 文件。

模型与运行：`model-selection`、`model-visibility-policy`、`model-catalog`、`harness/selection`、`harness/runtime-plugin`、`runWithModelFallback`、`attempt-execution.runtime` 负责默认模型、模型 allowlist、harness 插件可用性、fallback 和真正的 agent attempt。

ACP 分支：`acp/control-plane/manager`、`acp/policy`、`acp/runtime/errors`、`acp/runtime/session-identifiers` 负责已绑定 ACP session 的 turn 执行、策略检查、错误包装和 cwd/session 元数据。

投递与事件：`delivery.runtime`、`infra/agent-events`、`outbound/session-context`、`auto-reply/reply/pending-final-delivery` 负责生命周期事件、回复 payload 归一、持久化 pending final delivery 和渠道投递。

技能与工作区：`workspace`、`skills`、`skills/filter`、`skills/refresh-state`、`skills/snapshot-hydration`、`infra/skills-remote` 负责 agent workspace bootstrap、skills snapshot 构建和缓存刷新。

## 核心流程

入口先经过 `agentCommand` 或 `agentCommandFromIngress` 设置信任边界，再进入 `agentCommandInternal`。`agentCommand` 还包了一层 `withLocalGatewayRequestScope`，给本地 gateway request scope 注入 deps 和 config 读取能力。

`prepareAgentCommandExecution` 是第一阶段。它校验 message 非空，确认至少有 `to`、`sessionId`、`sessionKey` 或 `agentId` 能定位会话；读取 runtime config；规范化 spawned metadata、agent id、legacy session key；解析 verbose/thinking/timeout；调用 `resolveSession` 得到 `sessionId`、`sessionKey`、session entry/store/path；确定 agent workspace、agent dir、manifest metadata、默认模型上下文；确保 workspace bootstrap；最后检查 ACP session 是否 ready/stale，并构造真正送入模型或 ACP 的 `body` 和 transcript body。

第二阶段先按 `deliver` 检查 send policy。若当前 session 是 ACP ready 且不是 raw model run，则走 ACP 分支：注册 run context，发出 lifecycle start，检查 ACP dispatch/agent policy，调用 `acpManager.runTurn`，累积 visible text delta，持久化 ACP transcript，再调用 `deliverAgentCommandResult` 输出或投递结果。

非 ACP 分支更长：先持久化本轮 thinking/verbose override；解析默认 provider/model、session stored override、显式 override、模型 allowlist 和 auto fallback probe；校验 harness 插件和 auth profile 是否兼容；解析 thinking level；确定 transcript file；注册 lifecycle 回调；构造 skills snapshot；然后用 `runWithModelFallback` 包裹 `runAgentAttempt`。每次 attempt 会传入 provider/model、session、workspace、prompt body、工具上下文、skills、verbose/thinking、timeout、auth profile 等完整运行上下文。若遇到 `LiveSessionModelSwitchError`，会在最多 5 次内切换模型重试，并继续受模型 allowlist 约束。

运行成功后，它更新 session store 中的 token/model 等字段，持久化 CLI/embedded transcript，必要时触发 compaction 生命周期。若需要渠道投递，会先把最终回复文本写入 `pendingFinalDelivery`，再调用 `deliverAgentCommandResult`；投递成功后清理 pending 字段。最后发出 lifecycle end，并在 `finally` 中 `clearAgentRunContext`。

## 关键函数的高层作用

`prepareAgentCommandExecution` 负责“运行前归一化”：把松散的 CLI/ingress 参数变成稳定的配置、会话、workspace、模型上下文、ACP 状态和 prompt body。修改它会影响所有入口。

`agentCommandInternal` 是主编排器：统一处理 ACP 与普通 agent attempt 两条路径，并串起模型选择、skills、fallback、transcript、session store、delivery 和 lifecycle。它是本文件最高风险区域。

`agentCommand` 是可信本地入口，核心价值是默认 owner 身份和允许模型 override；`agentCommandFromIngress` 是非本地入口，核心价值是强制显式授权，防止网络调用误用本地权限。

`normalizeExplicitOverrideInput` 只负责 provider/model override 的基础输入卫生：trim、非空、长度和控制字符检查。

`persistSessionEntry`、`clearPendingFinalDeliveryFields` 是会话存储辅助，主要维护 session entry 更新和 pending final delivery 的可靠投递状态。

## 修改风险

最高风险是信任边界。`agentCommand` 与 `agentCommandFromIngress` 对 `senderIsOwner`、`allowModelOverride` 的默认值不同，任何合并、复用或“简化”都可能让外部入口获得本地 operator 权限，或允许未授权模型切换。

第二类风险是会话兼容性。这里处理 legacy session key scoping、agent-prefixed key、subagent key、visible/internal session effects、transcript 文件和 session store 更新。改错会造成历史会话串线、agent id 不匹配、内部 run 污染用户可见会话，或 transcript 丢失。

第三类风险是模型选择与 fallback。默认模型、stored override、explicit override、allowlist、auto fallback provenance、auth profile 兼容性、live model switch 都在同一流程中交织。局部改动必须同时证明主模型、fallback 模型、显式 override、stored override 和 live switch 都仍受 allowlist 与 auth 约束。

第四类风险是投递可靠性。`pendingFinalDelivery` 在投递前落盘、成功后清理，是防进程重启丢最终回复的关键机制。改变 payload 合并、清理条件或 fresh session entry 读取，可能造成重复发送、漏发或错误清理。

第五类风险是性能与冷启动。文件大量使用 `createLazyImportLoader`，符合 `src/agents/AGENTS.md` 对 agent 热路径和测试性能的要求。把 runtime-heavy 模块改成静态 import，可能拖慢 help/cold import、测试和 gateway 热路径。

最后，ACP 分支和普通 attempt 分支都要维护 lifecycle event、transcript persistence 和 delivery 语义。新增行为时应分别验证 ACP ready session、普通 CLI/local run、ingress run、deliver run、internal session effects、model fallback run；只测一条路径很容易漏掉另一条路径的回归。
