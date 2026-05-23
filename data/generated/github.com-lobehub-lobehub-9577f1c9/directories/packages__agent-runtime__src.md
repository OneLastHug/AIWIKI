# 目录：packages/agent-runtime/src

## 它负责什么

`packages/agent-runtime/src` 是 LobeHub 中“Agent 运行时”包的源码核心。它不直接等同于某个具体聊天页面，也不直接负责模型 Provider 的底层适配，而是提供一套可复用的 Agent 执行框架：Agent 负责根据上下文产出下一步 `AgentInstruction`，Runtime 负责执行这些指令、更新 `AgentState`、产生 `AgentEvent`，并把下一轮所需的 `AgentRuntimeContext` 交回调用方。

从当前片段看，这个包把 Agent 执行拆成几个层次：`agents` 放“脑”，例如 `GeneralChatAgent` 和 `GraphAgent`；`core` 放“引擎”，核心是 `AgentRuntime`；`types` 定义事件、状态、指令、hook、graph 等协议；`audit` 提供工具调用前的人类干预和安全审计；`groupOrchestration` 面向多 Agent 或群组协作；`utils` 放消息选择、上下文压缩、token 计数等辅助逻辑。

因此，阅读这个目录时应把它理解为“Agent loop 的协议和执行层”，而不是“业务 UI”或“单一模型调用工具”。

## 直接子目录地图

`packages/agent-runtime/src/agents` 是具体 Agent 策略层。这里的关键文件是 `GeneralChatAgent.ts` 和 `GraphAgent.ts`。`GeneralChatAgent` 实现通用聊天 Agent 的决策循环：从用户输入进入 `call_llm`，根据 LLM 结果判断是否有 tool calls，再决定 `call_tools_batch`、`call_tool`、`request_human_approve` 或 `finish`。`GraphAgent` 则基于声明式 `ReasoningGraph` 包装通用 Agent，把多节点推理流程组织成图结构执行。

`packages/agent-runtime/src/core` 是运行时执行层。`runtime.ts` 中的 `AgentRuntime` 是最核心入口，它接收一个实现了 `Agent` 接口的实例，并在 `step()` 中完成“获取指令、规范化指令、执行指令、累计事件、更新状态、返回下一上下文”的流程。`InterventionChecker.ts`、`UsageCounter.ts` 分别支撑人类干预检查和用量统计。

`packages/agent-runtime/src/types` 是协议定义层。它包含 `runtime.ts`、`state.ts`、`event.ts`、`generalAgent.ts`、`graph.ts`、`hooks.ts`、`instruction.ts`、`usage.ts` 等文件。这里定义了 Agent、Runtime、事件、状态、图节点、hook 事件、usage/cost 等跨模块共享类型，是理解整个包边界的基础。

`packages/agent-runtime/src/audit` 是安全审计与默认策略区域。`defaultSecurityBlacklist.ts`、`createSecurityBlacklistAudit.ts`、`globalAudit.ts` 共同服务于工具调用前的安全判断，尤其和 `GeneralChatAgent` 中的人类干预逻辑相关。

`packages/agent-runtime/src/groupOrchestration` 是群组编排层。它包含 `GroupOrchestrationRuntime.ts`、`GroupOrchestrationSupervisor.ts` 和 `types.ts`，关注 supervisor 如何决定下一步：让某个 agent 发言、并行调用多个 agents、委派任务、执行异步任务或结束编排。它和单 Agent 的 `AgentRuntime` 相似，但协议是 `SupervisorInstruction` 与 `GroupOrchestrationEvent`。

`packages/agent-runtime/src/utils` 是运行辅助层。当前能看到 `messageSelectors.ts`、`stepContextComputer.ts`、`tokenCounter.ts` 及对应测试。它们服务于消息筛选、步骤上下文计算、token 预算与压缩判断，不是主入口，但常被 Agent 策略和 Runtime 使用。

## 关键入口

包级导出入口是 `packages/agent-runtime/src/index.ts`。它统一导出 `agents`、`audit`、`core`、`groupOrchestration`、`types`、`utils`，说明这个目录被设计为一个独立 runtime package，对外暴露的是多层能力，而不是单个默认对象。

单 Agent 执行的关键入口是 `packages/agent-runtime/src/core/runtime.ts` 中的 `AgentRuntime`。构造函数接收 `agent` 和 `RuntimeConfig`，并组合内置 executor、config executor、agent executor。优先级从代码看是：内置 executor 作为基础，`config.executors` 可覆盖，`agent.executors` 具有最高优先级。它内置支持的主要指令包括 `call_llm`、`call_tool`、`finish`、`request_human_approve`、`request_human_prompt`、`request_human_select`，并对 `call_tools_batch` 做了特殊处理。

通用聊天 Agent 的关键入口是 `packages/agent-runtime/src/agents/GeneralChatAgent.ts` 的 `GeneralChatAgent.runner()`。它不是直接执行模型或工具，而是根据 `AgentRuntimeContext.phase` 和当前 `AgentState` 产出下一条或一组 `AgentInstruction`。例如 `user_input` 阶段通常返回 `call_llm`；`llm_result` 阶段会检查工具调用和人工干预；工具执行结果阶段再回到 `call_llm`；没有后续动作时返回 `finish`。

图式推理入口是 `packages/agent-runtime/src/agents/GraphAgent.ts` 的 `GraphAgent`。根据当前片段推断，它通过拦截内部 `GeneralChatAgent` 的 `finish` 指令来推进图节点：普通节点完成并不一定结束整个 Agent，而是可能进入下一个 graph node；只有终止节点完成时才返回真正的 `finish`。依据是文件注释和 `GraphAgent` 中围绕 `finish`、`currentNode`、`:extract` 的处理痕迹。

群组编排入口是 `packages/agent-runtime/src/groupOrchestration/GroupOrchestrationRuntime.ts` 和 `GroupOrchestrationSupervisor.ts`。前者偏执行，后者偏决策，类型协议集中在 `groupOrchestration/types.ts`。

## 主流程位置

单 Agent 主流程主要在 `AgentRuntime.step()`。它先克隆并更新 `AgentState`，增加 `stepCount` 和 `lastModified`，检查 `maxSteps` 与 `forceFinish`；然后建立或接收 `AgentRuntimeContext`。如果当前 phase 是 `human_approved_tool`，Runtime 会直接构造 `call_tool` 指令执行已批准工具；否则调用 `this.agent.runner(runtimeContext, newState)` 让 Agent 产出下一步。

随后 Runtime 会把单条指令规范化为数组，并兼容旧格式的 `call_tools_batch` payload，把 OpenAI 风格的 `ToolsCalling` 转换为内部 `ChatToolPayload` 结构。之后按顺序执行每条 instruction：普通指令交给 `this.executors[instruction.type]`，批量工具调用优先使用自定义 `call_tools_batch` executor，否则回落到内置批处理。执行结果中的 `events` 会累计，`newState` 会滚动更新，`nextContext` 会保存给下一轮。如果状态进入 `waiting_for_human` 或 `interrupted`，Runtime 会停止继续推进，并清空 `nextContext` 让外层循环停下来。

`GeneralChatAgent` 的主流程则集中在其 `runner()` 和工具干预判断相关私有方法。它会结合 `state.toolManifestMap`、用户的 `userInterventionConfig`、默认安全黑名单、全局审计 resolver、工具级 `humanIntervention` 配置和动态干预策略，决定工具是直接执行、批量执行、请求人工批准，还是在 headless 场景中跳过高风险工具。

群组主流程位于 `groupOrchestration`。从 `types.ts` 可见，supervisor 指令包括 `call_supervisor`、`call_agent`、`parallel_call_agents`、`exec_async_task`、`exec_client_async_task`、`batch_exec_async_tasks`、`delegate`、`finish`。这说明群组运行时不是简单循环同一个 Agent，而是由 supervisor 在每轮决定协作拓扑和动作类型。

## 推荐阅读顺序

1. 先读 `packages/agent-runtime/src/index.ts` 和各子目录的 `index.ts`，建立导出边界。
2. 再读 `packages/agent-runtime/src/types/runtime.ts`、`packages/agent-runtime/src/types/state.ts`、`packages/agent-runtime/src/types/event.ts`、`packages/agent-runtime/src/types/instruction.ts`，先理解协议名词。
3. 接着读 `packages/agent-runtime/src/core/runtime.ts`，重点看 `AgentRuntime.step()`、executor 组合逻辑、`call_llm`、`call_tool`、`finish` 和人工干预 executor。
4. 然后读 `packages/agent-runtime/src/agents/GeneralChatAgent.ts`，把 Runtime 的“执行指令”与 Agent 的“产生指令”对上。
5. 如果关心复杂任务流，再读 `packages/agent-runtime/src/agents/GraphAgent.ts` 和 `packages/agent-runtime/src/types/graph.ts`。
6. 如果关心多 Agent 协作，再读 `packages/agent-runtime/src/groupOrchestration/types.ts`、`GroupOrchestrationSupervisor.ts`、`GroupOrchestrationRuntime.ts`。
7. 最后补读 `audit` 和 `utils`，它们解释为什么某些工具调用会被拦截、为什么上下文会压缩、消息如何被选择。

## 常见误区

第一，容易把 `AgentRuntime` 当成“Agent 本身”。实际上 Runtime 更像执行引擎，它不知道业务上该怎么思考，真正决定下一步的是实现 `Agent.runner()` 的对象，例如 `GeneralChatAgent` 或 `GraphAgent`。

第二，容易以为 `call_llm` 会自动修改消息历史。根据测试注释和 runtime 片段，新的架构中 `call_llm` executor 不一定直接把消息写入 state；状态如何变化要看 executor 返回的 `newState` 和上下文设计，不能用旧式聊天循环经验直接套。

第三，`finish` 不是普通执行步骤。`AgentRuntime.step()` 中如果发现 `finish` 指令，会回退本轮增加的 `stepCount`，说明它被视为结束信号，而不是一次真实工作步骤。

第四，工具调用不是简单“有 tool call 就执行”。`GeneralChatAgent` 会经过全局审计、黑名单、用户审批模式、工具 manifest 的 `humanIntervention`、动态 resolver 等多层判断；在 `headless`、`auto-run`、`manual` 等模式下行为也不同。

第五，`call_tool` 和 `call_tools_batch` 不只是数量区别。批量工具调用在 Runtime 中有专门规范化和执行分支，还可能由外部自定义 executor 接管，尤其服务端可能需要数据库或业务上下文。

第六，`GraphAgent` 不是替代 Runtime 的另一套执行器。根据当前片段推断，它仍实现 `Agent` 接口，主要通过包装 `GeneralChatAgent` 和操纵 graph context 来改变决策流，最终仍可交给 `AgentRuntime` 执行。

第七，`groupOrchestration` 与单 Agent loop 不应混在一起理解。它的核心概念是 supervisor instruction 和群组事件，适合看多角色、多任务、异步任务编排；而 `core/runtime.ts` 主要服务单个 Agent 的 step-by-step 执行。
