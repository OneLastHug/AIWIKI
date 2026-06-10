# 文件：src/commands/agent.ts

## 一句话定位

`src/commands/agent.ts` 是 `agent` 命令能力的兼容转出口，本文件本身只有 `export * from "../agents/agent-command.js";`，真实调度逻辑集中在 `src/agents/agent-command.ts`。因此学习这个文件时，重点不是它的代码体积，而是它在命令层保留了旧的 `src/commands/agent.js` 导入路径，把 CLI、gateway、TUI 和 plugin SDK 调用面统一导向 agent 运行核心。

## 它暴露/定义了什么

从当前代码看，它通过转出口暴露 `src/agents/agent-command.ts` 的公开成员，核心是 `agentCommand`、`agentCommandFromIngress`，以及测试用的 `testing` / `__testing`。

`agentCommand` 是本地可信入口，默认把 `senderIsOwner` 视为 `true`，并默认允许本次运行覆盖 provider/model。`agentCommandFromIngress` 是网络、插件、嵌入式入口，要求调用方显式传入 `allowModelOverride`，并且只有 `senderIsOwner === true` 才会被当成 owner。这个分叉是安全边界，不只是参数包装。

## 谁调用它

直接引用 `src/commands/agent.ts` 的主要调用者包括 `src/commands/agent-via-gateway.ts` 和 `src/gateway/boot.ts`。前者是 CLI 的 gateway 优先入口，在 gateway 不可用或需要 fallback 时会落到本地 `agentCommand`；后者在 gateway 启动时读取 `BOOT.md` 并发起一次 agent boot check。

另一个调用面绕过此转出口，直接引用 `src/agents/agent-command.ts` 或经 `src/plugin-sdk/agent-runtime.ts` 暴露，例如 `src/tui/embedded-backend.ts`、`src/gateway/server-methods/agent.ts`、`src/gateway/openai-http.ts`、`src/gateway/openresponses-http.ts`、`src/gateway/server-node-events.ts`、`extensions/discord/src/voice/ingress.ts`。根据当前片段推断，`src/commands/agent.ts` 的存在主要服务命令层历史路径和本地 CLI/gateway fallback，而不是唯一入口。

## 它调用谁

本文件自身不调用任何模块，只做 re-export。真实实现会调用多组核心组件：配置和运行时解析来自 `resolveAgentRuntimeConfig`、`getRuntimeConfig`；会话解析来自 `resolveSession`、`routing/session-key`、session store runtime；模型选择来自 `model-selection`、`model-visibility-policy`、`model-fallback`；agent 执行落到 `runAgentAttempt`；ACP 会话走 `acpManager.runTurn`；技能快照走 `skills`、`skills/filter`、`skills/refresh-state`；输出投递由 `deliverAgentCommandResult` 处理；事件通过 `infra/agent-events` 发出。

## 核心流程

入口先校验 message、目标会话参数、agent id、session key 形态、thinking/verbose/timeout 等显式输入，然后加载运行配置，归一化 agent、workspace、session、spawn metadata，并确保 workspace bootstrap 文件存在。

随后分两条路径：如果当前 session 是 ACP-ready 且不是 raw model run，会进入 ACP turn 流程，校验 ACP dispatch/agent policy，调用 `acpManager.runTurn`，把文本 delta 转成 agent event，最后持久化 ACP transcript 并投递结果。

普通路径会准备技能快照、持久化 thinking/verbose 覆盖、解析默认模型和会话模型覆盖，校验 agent 模型 allowlist，确保所选 harness plugin 可用，再处理 auth profile 与模型 runtime 的兼容性。之后通过 `runWithModelFallback` 包住 `runAgentAttempt`，支持自动 fallback、live session model switch 重试、trajectory 记录和生命周期事件。执行完成后更新 session store 的 token/model/usage 状态，补写 CLI transcript，必要时触发 compaction，最后做 pending final delivery 持久化、实际投递和清理。

## 关键函数的高层作用

`agentCommand`：本地可信入口，包一层 `withLocalGatewayRequestScope`，给 CLI/local 调用默认 owner 权限和模型覆盖权限。

`agentCommandFromIngress`：外部 ingress 入口，强制调用方显式声明 `allowModelOverride`，避免网络入口意外继承本地权限。

`agentCommandInternal`：真正的编排器，串起配置、会话、ACP、技能、模型选择、fallback、attempt 执行、transcript、delivery 和生命周期事件。

`prepareAgentCommandExecution`：前置解析和校验函数，把输入参数归一化为后续执行需要的上下文包，包括 `cfg`、`sessionKey`、`sessionEntry`、`workspaceDir`、`agentDir`、`acpResolution`、`runId` 等。

辅助函数如 `persistSessionEntry`、`clearPendingFinalDeliveryFields`、`normalizeExplicitOverrideInput` 只服务局部状态持久化或输入清洗，不是架构主线。

## 修改风险

最大风险是把 `src/commands/agent.ts` 当作无害空壳删除或改路径。大量命令层代码和测试仍可能依赖 `../commands/agent.js` 这个稳定导入面，直接迁移会造成运行时 ESM import 断裂。

第二类风险是误改 `agentCommand` 与 `agentCommandFromIngress` 的权限默认值。本地 CLI 默认 owner、ingress 默认非 owner 是安全边界；放宽 ingress 的 owner 或模型覆盖策略，会影响网络入口、gateway HTTP、TUI 和插件通道。

第三类风险在会话和模型状态。这里会写 session store、transcript、skills snapshot、pending delivery、model override、auth profile override。小改动可能改变历史会话继续运行的模型、投递幂等性或 compaction 行为。

第四类风险是 ACP 与普通 CLI runtime 的双路径差异。ACP 路径使用 `acpManager.runTurn` 和 ACP transcript；普通路径使用 `runAgentAttempt`、fallback、CLI transcript。修改共享前置逻辑时要同时验证两条路径，以及 `sessionEffects: "internal"` 这种不应污染用户可见状态的内部运行。

第五类风险是导入时成本。实现文件大量使用 `createLazyImportLoader`，说明 cold start 和命令路由性能被刻意控制；把 lazy import 改成静态 import 可能影响 CLI 启动、gateway 热路径或测试隔离。
