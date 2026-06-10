# 子系统：src/agents/harness

## 解决什么问题

`src/agents/harness` 是 OpenClaw 的“agent runtime harness”抽象层，负责把一次 agent 运行从核心会话逻辑中解耦出来。它解决的问题不是“如何调用某个模型”，而是：在不同 agent 后端之间统一选择、注册、运行、压缩、重置、生命周期 hook、上下文引擎和工具结果处理。

核心思想是：核心 agents 流程只认识 `AgentHarness` 这类稳定接口；具体运行时可以是内置 PI，也可以是插件注册的 Codex 类 harness，甚至带有自己的 context engine、tool middleware、lifecycle hooks。这样核心代码不用硬编码某个插件或后端实现。

## 相关目录和文件

目标目录内可以按职责分成几组：

`src/agents/harness/types.ts` 定义公共契约，包括 `AgentHarness`、`AgentHarnessSupportContext`、`AgentHarnessAttemptParams`、`AgentHarnessSideQuestionParams`、`AgentHarnessCompactParams` 等。它是这个目录的类型中心。

`src/agents/harness/registry.ts` 维护全局 harness 注册表，提供 `registerAgentHarness`、`getAgentHarness`、`listRegisteredAgentHarnesses`、`resetRegisteredAgentHarnessSessions`、`disposeRegisteredAgentHarnesses`。

`src/agents/harness/selection.ts` 负责选择实际使用哪个 harness。它会结合配置、模型 runtime alias、provider、sandbox、tool policy、subagent policy 和已注册 harness 来做决策。

`src/agents/harness/builtin-pi.ts` 是内置 PI harness 的适配入口；`src/agents/harness/runtime-plugin.ts` 处理插件 runtime 相关桥接。

`src/agents/harness/v2.ts`、`src/agents/harness/lifecycle-hook-helpers.ts`、`src/agents/harness/hook-helpers.ts`、`src/agents/harness/native-hook-relay.ts` 组成生命周期与 hook 执行层。根据当前片段推断，依据是 `selection.ts` 导入了 `adaptAgentHarnessToV2`、`runAgentHarnessV2LifecycleAttempt`，且 SDK 侧导出了多种 hook runner。

`src/agents/harness/context-engine-lifecycle.ts` 管理 harness 运行期间的 context engine 生命周期；`src/agents/harness/tool-result-middleware.ts`、`src/agents/harness/codex-app-server-extensions.ts` 处理工具结果和 Codex app server 扩展点。

邻近上游主要是 `src/plugin-sdk/agent-harness-runtime.ts`、`src/plugins/registry.ts`、`src/agents/pi-embedded-runner`、`src/agents/harness-runtimes.ts`、`src/plugins/gateway-startup-plugin-ids.ts`。

## 核心对象

`AgentHarness` 是中心对象。它包含 `id`、`label`、可选 `pluginId`、`contextEngineHostCapabilities`、`deliveryDefaults`，以及运行方法 `supports`、`runAttempt`、可选 `runSideQuestion`、`classify`、`compact`、`reset`、`dispose`。

`RegisteredAgentHarness` 在 harness 外再包一层 `ownerPluginId`，用来记录注册来源，避免核心把插件所有权信息混进运行逻辑。

`AgentHarnessSupport` 是选择阶段的能力声明，返回支持与否、优先级和原因。`selection.ts` 会把这些信息变成候选列表，再根据 policy 和 runtime 选择最终 harness。

`AgentHarnessPolicy` 来自 `src/agents/harness/policy.ts`，它描述配置层面对 embedded harness、plugin harness 或 fallback 的偏好。它不是直接运行器，而是选择器的输入。

## 运行流程

典型流程是：插件或内置代码先注册 harness。插件注册通常从 `src/plugins/registry.ts` 接收 `api.registerAgentHarness`，再调用 `src/agents/harness/registry.ts` 的全局注册函数；SDK 暴露面在 `src/plugin-sdk/agent-harness-runtime.ts`。

当一次 agent 请求进入时，上层根据配置和模型 runtime 进入 `selection.ts`。选择器读取 `OpenClawConfig`、provider、model、requested runtime，并检查已注册 harness 的 `supports` 结果。若配置强制 PI 或插件 harness，会走强制路径；若隐式偏好不可用，可能回退到 PI 占位或内置运行路径。

选中 harness 后，运行不会只是直接调用 `runAttempt`。`selection.ts` 会结合 tool policy、sender/group policy、sandbox runtime 状态，把工具可用性和拒绝提示整理到请求上下文中。随后通过 `v2.ts` 的生命周期适配执行 attempt。运行中可能触发 LLM input/output hook、tool call 后 hook、message write 前 hook、agent finalize/end hook，以及 compaction 前后 hook。

如果启用了 context engine，`context-engine-lifecycle.ts` 负责组装 runtime context、启动、维护和 finalize。工具结果还可能经过 `tool-result-middleware.ts`，让插件 harness 能调整或观察工具输出。

## 上下游依赖

上游输入来自配置系统、会话系统、插件系统和 agent 调度层。重要依赖包括 `src/config/types.openclaw.ts`、`src/config/sessions.ts`、`src/plugins/registry.ts`、`src/plugins/manifest.ts`、`src/agents/harness-runtimes.ts`。

下游执行依赖 `src/agents/pi-embedded-runner` 的 attempt、compact、session 类型；也依赖 `src/agents/tool-policy.ts`、`src/agents/pi-tools.policy.ts`、`src/agents/sender-tool-policy.ts`、`src/agents/sandbox/runtime-status.ts` 来形成工具策略。插件侧通过 `src/plugin-sdk/agent-harness-runtime.ts` 暴露注册、hook、context engine 和 middleware 能力。

网关启动相关逻辑会读取插件 manifest 中的 `activation.onAgentHarnesses`、`cliBackends` 等信息，见 `src/plugins/gateway-startup-plugin-ids.ts`，以决定哪些插件需要随启动加载。

## 修改时最容易踩的坑

第一，registry 是 `Symbol.for("openclaw.agentHarnessRegistryState")` 挂在 `globalThis` 上的全局状态。测试或运行时修改注册表后，必须考虑恢复、清理、`reset` 和 `dispose`，否则会污染后续用例。

第二，harness 选择是兼容敏感路径。`agents.defaults.embeddedHarness`、provider runtime alias、插件注册状态、PI fallback、CLI runtime 都可能影响结果。改 `selection.ts` 时不能只看一个 provider 或一个测试。

第三，agent hot path 不应为了分类、选择或静态信息加载完整插件/channel runtime。`src/agents/AGENTS.md` 明确把这类慢测试视为架构信号，应优先使用轻量 typed artifact 或依赖注入。

第四，context engine 有 host capability 要求。新增 harness 如果省略 `contextEngineHostCapabilities`，可能对声明了 host requirements 的 engine 不可用。

第五，hook 有同步/异步、before/after、native relay、history 记录等多个层次。改一个 hook helper 时，要同时确认 SDK 导出面和测试，如 `lifecycle-hook-helpers.test.ts`、`native-hook-relay.test.ts`、`tool-result-middleware.test.ts`。

## 推荐阅读顺序

1. 先读 `src/agents/harness/types.ts`，建立 `AgentHarness` 契约。
2. 再读 `src/agents/harness/registry.ts`，理解注册和生命周期清理。
3. 然后读 `src/agents/harness/policy.ts` 与 `src/agents/harness/selection.ts`，看运行时如何被选中。
4. 接着读 `src/agents/harness/v2.ts`、`src/agents/harness/lifecycle-hook-helpers.ts`、`src/agents/harness/hook-helpers.ts`，理解 attempt 外围生命周期。
5. 最后读 `src/plugin-sdk/agent-harness-runtime.ts`、`src/plugins/registry.ts`、`src/agents/pi-embedded-runner`，把插件注册、SDK 暴露和内置 PI 执行链串起来。
