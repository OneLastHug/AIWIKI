# 子系统：src/agents/runtime-plan

## 解决什么问题

`src/agents/runtime-plan` 负责把一次 agent 运行前已经知道的上下文，整理成一个稳定的 `AgentRuntimePlan`。它不是执行器本身，也不是模型调用层，而是运行前的“计划对象”构建层：把认证、提示词贡献、工具 schema 处理、投递策略、结果分类、传输参数、转录策略、可观测信息等决策集中起来，供后续 embedded runner 的 attempt 阶段直接读取。

这个目录解决的核心问题是：避免运行热路径在请求过程中反复从 provider、plugin、channel、config 中重新发现同一批事实。根目录规则明确要求 hot path 携带 prepared facts，少做 request-time discovery；`runtime-plan` 正是把这些事实提前规范化的边界。这样 `src/agents/pi-embedded-runner/run/attempt.ts` 在拼 prompt、构造工具、分派请求、处理结果时，可以优先使用 `runtimePlan` 中的函数和字段，而不是散落地调用旧的 provider fallback 或插件元数据读取逻辑。

## 相关目录和文件

`src/agents/runtime-plan/types.ts` 是契约中心，定义 `AgentRuntimePlan` 以及拆分后的 `AgentRuntimeAuthPlan`、`AgentRuntimePromptPlan`、`AgentRuntimeToolPlan`、`AgentRuntimeDeliveryPlan`、`AgentRuntimeOutcomePlan`、`AgentRuntimeTransportPlan` 等类型。它还保留构建参数类型，例如 `BuildAgentRuntimePlanParams` 和 `BuildAgentRuntimeDeliveryPlanParams`，用于锁定构建函数的外部形状。

`src/agents/runtime-plan/build.ts` 是主要入口，导出 `buildAgentRuntimePlan`、`buildAgentRuntimeDeliveryPlan`、`buildAgentRuntimeOutcomePlan`。从当前片段可见，它会组装 auth、prompt、tools、delivery、outcome、transport、transcript、observability 等子计划，并把模型、thinking level、provider runtime handle、workspace、config、auth profile 等上下文合并到最终计划中。

`src/agents/runtime-plan/auth.ts` 独立构建认证相关计划，负责解析 `providerForAuth`、`authProfileProviderForAuth`、`harnessAuthProvider`、`forwardedAuthProfileId`、候选 auth profile id 等字段。测试显示它需要兼容如 `openai` 与 `openai-codex` 这类 provider / harness auth provider 分离的场景。

`src/agents/runtime-plan/tools.ts` 是运行计划与工具处理旧路径之间的适配层。它优先调用 `runtimePlan.tools.normalize` 和 `runtimePlan.tools.logDiagnostics`；没有计划时，保留 legacy provider schema normalization 与 diagnostics fallback。

测试文件集中在同目录，如 `build.test.ts`、`tools.test.ts`、`tools.diagnostics.test.ts`、`types.test.ts`、`types.compat.test.ts`。它们不只是单元测试，也说明这个目录的设计目标：叶子契约要独立于具体 runtime policy 模块，类型兼容性要稳定，旧 fallback 仍要在没有 `RuntimePlan` 时可用。

## 核心对象

`AgentRuntimePlan` 是核心聚合对象。根据当前片段，它至少包含以下能力面：

`auth`：保存模型调用认证需要的 provider、auth profile、harness provider 和转发 profile 信息。它把“模型属于哪个 provider”和“认证应该走哪个 provider/profile”的差异提前算清。

`prompt`：提供 `resolveSystemPromptContribution`，用于在 attempt 阶段根据模型上下文解析系统提示词补充。这样 prompt overlay 不必散落在 runner 内部。

`tools`：负责工具 schema normalization、诊断输出，以及 `preparedPlanning`。其中 `preparedPlanning.loadMetadataSnapshot` 是懒加载的插件元数据快照入口，说明工具规划需要知道插件 manifest 元数据，但不希望构建计划时无条件加载完整 runtime。

`delivery`：处理消息投递相关策略，例如 `isSilentPayload` 和 `resolveFollowupRoute`。测试片段显示它会识别 `{"action":"NO_REPLY"}` 这类静默 payload，并能解析 follow-up route。

`outcome`：提供 `classifyRunResult`，将运行结果归类为 empty、reasoning-only、planning-only 或其他内部结果类别。它服务于 runner 对“不完整回合”的处理。

`transport`：保存或解析模型传输参数，尤其是 `extraParams` 与 `resolveExtraParams`。它把模型、provider、thinking level、调用覆盖参数等合并为最终请求参数。

`transcript`：提供 `resolvePolicy`。`src/agents/pi-embedded-runner/run/attempt.transcript-policy.ts` 会优先使用 `runtimePlan.transcript.resolvePolicy`，没有计划时再回到 legacy provider transcript fallback。

`observability`：从测试片段看包含 `resolvedRef`、`harnessId`，用于日志、阶段追踪或结果标注，避免运行后再拼接模型引用信息。

## 运行流程

典型流程是：上层在准备一次 agent attempt 前调用 `buildAgentRuntimePlan(params)`。构建函数先把输入中的模型、provider runtime handle、thinking level、配置、workspace、auth profile 等上下文规范化；如果传入了项目配置，还会把配置投影成 runtime source snapshot，并准备一个懒加载的 plugin metadata snapshot。

随后 `buildAgentRuntimePlan` 调用 `buildAgentRuntimeAuthPlan` 生成认证计划，再内联或委托生成 prompt、tools、delivery、outcome、transport、transcript、observability 等子对象。最终得到的 `AgentRuntimePlan` 被传入 `src/agents/pi-embedded-runner/run/attempt.ts` 等执行路径。

在 attempt 阶段，调用方会构造 `runtimePlanModelContext`，然后按需读取计划：工具构造时通过 `runtimePlan.tools.normalize` 标准化 OpenClaw-owned 工具 schema；生成系统提示词时使用 `runtimePlan.prompt.resolveSystemPromptContribution`；发送请求前通过 `runtimePlan.transport.resolveExtraParams` 得到传输参数；处理 transcript 时通过 `runtimePlan.transcript.resolvePolicy`；完成后用 `runtimePlan.outcome.classifyRunResult` 辅助分类。根据当前片段推断，旧的 provider fallback 仍存在，但它是兼容路径，而不是新代码应优先依赖的主路径。

## 上下游依赖

上游输入主要来自 agent 运行准备层，包括模型选择、provider runtime handle、harness id、workspace、auth profile、项目配置和工具集合。相关邻近文件包括 `src/agents/agent-runtime-config.ts`、`src/agents/model-runtime-policy.ts`、`src/agents/provider-model-normalization.runtime.ts`、`src/agents/runtime-plugins.ts`、`src/agents/models-config.runtime.ts`、`src/agents/auth-profiles.runtime.ts`。

插件元数据方面，`runtime-plan` 通过 manifest metadata snapshot 和 runtime source snapshot 工作。当前片段出现了 `loadManifestMetadataSnapshot`、`projectConfigOntoRuntimeSourceSnapshot`、`PluginMetadataSnapshot` 等符号，说明它依赖的是较轻的元数据快照，而不是直接启动完整插件 runtime。这符合 `src/agents/AGENTS.md` 中“agent 测试和热路径避免冷加载完整 bundled plugin/channel/provider runtime”的要求。

下游主要是 `src/agents/pi-embedded-runner/run/attempt.ts`、`src/agents/pi-embedded-runner/run/attempt.transcript-policy.ts`、`src/agents/runtime-plan/tools.ts` 的调用者，以及所有构造模型请求、工具 schema、消息投递和结果分类的执行路径。`src/agents/pi-embedded-runner/run/types.ts` 中的 attempt 参数也持有可选 `AgentRuntimePlan`，说明系统仍支持没有 runtime plan 的旧调用形态。

## 修改时最容易踩的坑

第一，不要把具体 provider、plugin、channel 的策略硬编码进 `runtime-plan`。这个目录应承载已准备好的事实和通用计划函数，插件或 provider 特有行为应留在对应 owner 边界，通过 manifest、runtime handle 或 SDK seam 传入。

第二，不要为了方便在构建计划时加载完整插件 runtime。测试和 scoped 指南都强调 agent tests 往往 import-bound，应该优先使用轻量 typed artifact、metadata snapshot 或懒加载函数。`preparedPlanning.loadMetadataSnapshot` 这类设计就是为了避免过早加载。

第三，改 `types.ts` 时要重视结构兼容性。`types.compat.test.ts` 明确校验构建函数参数与导出类型的兼容关系，随意改字段名、可选性或函数签名，可能影响 embedded runner、provider fallback 和测试替身。

第四，保留旧 fallback 的边界要清楚。`tools.ts` 和 `attempt.transcript-policy.ts` 都有“有 `runtimePlan` 优先走计划、没有则走 legacy fallback”的模式。新增调用点时应沿用这个迁移形态，避免一半路径依赖计划、一半路径重新读取 provider 策略。

第五，认证字段不要简单等同。测试显示 `providerForAuth`、`authProfileProviderForAuth`、`harnessAuthProvider`、`forwardedAuthProfileId` 可能不同。修改 auth 逻辑时要覆盖 provider 与 harness provider 分离、profile id 转发、候选 profile 顺序等场景。

第六，传输参数和 prompt 解析要保持确定性。它们会影响模型请求字节、缓存、日志和回放；涉及 map、插件列表、工具列表时要避免非确定顺序。

## 推荐阅读顺序

先读 `src/agents/runtime-plan/types.ts`，建立 `AgentRuntimePlan` 的整体结构和各子计划边界。

再读 `src/agents/runtime-plan/build.ts`，看 `buildAgentRuntimePlan` 如何把输入参数组装成完整计划，重点关注 auth、tools、delivery、transport、transcript、observability 的生成位置。

接着读 `src/agents/runtime-plan/auth.ts` 和 `src/agents/runtime-plan/tools.ts`，理解两个最容易出兼容问题的局部：认证 provider 解析、工具 schema normalization 与 diagnostics fallback。

然后读 `src/agents/runtime-plan/build.test.ts`，它覆盖了完整计划对象的主要行为，包括 auth profile 转发、silent payload、extra params、prompt contribution、outcome classification、observability 和懒加载 metadata snapshot。

最后读下游调用点：`src/agents/pi-embedded-runner/run/types.ts`、`src/agents/pi-embedded-runner/run/attempt.transcript-policy.ts`，以及 `src/agents/pi-embedded-runner/run/attempt.ts` 中使用 `runtimePlan` 的片段。这样可以把“计划如何构建”和“执行器如何消费计划”连起来，而不会陷入逐行阅读整个 runner 的细节。
