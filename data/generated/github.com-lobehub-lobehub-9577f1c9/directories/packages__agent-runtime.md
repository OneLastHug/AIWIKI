# 目录：packages/agent-runtime

## 它负责什么

`packages/agent-runtime` 是一个独立的 agent 执行层包，职责不是“定义某个具体产品功能”，而是把 agent 的决策、工具调用、人类介入、状态推进和多 agent 编排统一收束到一套运行时里。根据当前片段推断，它更像一个通用引擎层：上层给它 `Agent`、`AgentState`、运行上下文和工具注册，它负责把“该做什么”变成“按步骤怎么执行”。

从代码结构看，这个包至少覆盖了四类能力：

1. 单 agent 运行时：`core/runtime.ts` 里的 `AgentRuntime` 负责执行 `step` 循环，处理 `call_llm`、`call_tool`、`finish` 以及 human intervention 相关指令。
2. agent 决策模型：`agents/GeneralChatAgent.ts` 体现的是“脑”的角色，负责根据上下文决定下一步是调用 LLM、执行工具还是等待人工确认。
3. 安全与干预控制：`audit/` 与 `core/InterventionChecker.ts` 一类模块，负责工具黑名单、人工审批策略、自动/手动/allow-list 等控制逻辑。
4. 多 agent 编排：`groupOrchestration/` 把 supervisor 和 executor 的轮转流程单独抽出来，说明这个包不只服务单对话，还支持群体协作式的 orchestration。

## 直接子目录地图

这个目录下的直接子目录很清楚，属于“运行时 + 策略 + 编排 + 类型 + 工具”的标准分层。

- `examples/`：演示用例。当前能看到 `tools-calling.ts`，用于展示如何把 runtime 接到 OpenAI 流式调用和本地工具上。
- `src/`：真正的源码主体，所有核心逻辑都在这里。
  - `src/agents/`：agent 的决策层实现，负责把状态和上下文翻译成 runtime 指令。
  - `src/audit/`：审计与安全策略，主要围绕工具调用是否需要拦截、审批或放行。
  - `src/core/`：基础运行时，包含 step 驱动、状态推进、异常处理、人工介入等通用机制。
  - `src/groupOrchestration/`：多 agent 协作运行时和 supervisor 状态机。
  - `src/types/`：各类运行时、事件、状态、工具、指令的类型定义。
  - `src/utils/`：辅助算法和选择器，例如 token 统计、消息选择、上下文计算等。

另外，每个关键目录下面都能看到 `__tests__`，说明测试是和实现并排放置的，而不是单独集中到顶层 `test/` 目录。

## 关键入口

最先看这几个点就够了：

- `packages/agent-runtime/package.json`：包级入口声明在 `main: "./src/index.ts"`，这说明这个包是直接围绕源码入口组织的。
- `packages/agent-runtime/src/index.ts`：总导出入口，把 `agents`、`audit`、`core`、`groupOrchestration`、`types`、`utils` 一次性导出。
- `packages/agent-runtime/src/core/index.ts`：核心运行时的聚合出口，串起 `InterventionChecker`、`runtime`、`UsageCounter`。
- `packages/agent-runtime/src/agents/index.ts`：agent 侧入口，目前导出 `GeneralChatAgent`、`GraphAgent`。
- `packages/agent-runtime/src/groupOrchestration/index.ts`：群组编排入口，导出 `GroupOrchestrationRuntime` 和 `GroupOrchestrationSupervisor`。
- `packages/agent-runtime/examples/tools-calling.ts`：最接近“怎么用”的样例，适合先看整体调用方式，再回头读实现。

## 主流程位置

这个包的主流程不是单一路径，而是两条主干：

1. 单 agent 主流程  
   关键在 `src/core/runtime.ts` 和 `src/agents/GeneralChatAgent.ts`。前者负责“执行循环”，后者负责“决策逻辑”。  
   典型链路是：`AgentRuntime.step()` 先推进 `state`，再从 `agent.runner(...)` 拿到指令，随后分发给对应 executor，最后返回事件和新状态。`GeneralChatAgent` 则在 `user_input`、`llm_result`、`tool_result` 等阶段间切换，决定下一步是 `call_llm`、`call_tool` 还是 `finish`。

2. 多 agent 编排主流程  
   关键在 `src/groupOrchestration/GroupOrchestrationRuntime.ts` 和 `src/groupOrchestration/GroupOrchestrationSupervisor.ts`。  
   这条线更像“监督者 + 执行者”的状态机：runtime 维护 step 和 abort，supervisor 根据上一轮结果决定下一条指令，再由 executor 执行并回传结果，直到 `finish` 或达到最大轮数。

安全控制和人工介入不是旁支，而是主流程的一部分。`src/audit/` 与 `src/core/InterventionChecker.ts` 决定工具能不能直接跑，这会直接影响 runtime 是否停下来等待审批。

## 推荐阅读顺序

建议按“先入口，再主干，再策略，再类型”的顺序看：

1. `packages/agent-runtime/package.json` 和 `packages/agent-runtime/src/index.ts`
2. `packages/agent-runtime/src/core/runtime.ts`
3. `packages/agent-runtime/src/agents/GeneralChatAgent.ts`
4. `packages/agent-runtime/src/audit/`
5. `packages/agent-runtime/src/groupOrchestration/`
6. `packages/agent-runtime/src/types/` 与 `packages/agent-runtime/src/utils/`
7. `packages/agent-runtime/examples/tools-calling.ts`

这样看能先建立“这个包到底提供什么 API”，再理解“它怎么跑”，最后补上策略和数据结构。

## 常见误区

- 容易把它当成“某个聊天 agent 的实现包”，实际上它更像 agent 运行时基础设施，支持单 agent 和多 agent 两种模式。
- 容易只盯着 `core/runtime.ts`，忽略 `agents/` 里的决策层；但运行时本身不决定业务行为，真正的策略在 agent 实现里。
- 容易忽略 `audit/`，以为工具调用只要能执行就行。实际上安全黑名单、动态审批、allow-list 这些逻辑直接影响主流程。
- 容易把 `groupOrchestration/` 视为附加功能。按目录结构看，它是这个包的一级能力，不是可有可无的示例代码。
- 容易误判构建形态。`package.json` 的 `main` 直接指向 `src/index.ts`，说明这里更偏源码入口组织，阅读时要把“导出入口”和“执行入口”分开看。
- 容易把测试当成独立模块。这里的测试是贴着实现放的，想理解某个行为时，`__tests__` 往往比说明文档更直接。
