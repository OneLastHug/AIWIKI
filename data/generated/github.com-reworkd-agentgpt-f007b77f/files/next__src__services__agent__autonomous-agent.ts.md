# 文件：next/src/services/agent/autonomous-agent.ts

## 一句话定位

`next/src/services/agent/autonomous-agent.ts` 是前端 Agent 运行时的总调度器：它把用户目标、任务队列、消息展示、后端 API 调用、暂停/停止生命周期和单次工作单元 `AgentWork` 串成一个可持续运行的自治执行循环。

## 它暴露/定义了什么

该文件默认导出 `AutonomousAgent` 类。它不是具体的 LLM 任务执行器，而是一个“编排对象”，内部持有 `AgentRunModel`、`MessageService`、`ModelSettings`、`AgentApi`、可选的 `Session`，以及私有的 `workLog: AgentWork[]` 队列。

构造时会把 `StartGoalWork` 放入 `workLog`，表示一次 agent run 的第一步永远是发送目标、请求初始任务、创建/保存 agent 记录。对外主要暴露 `run()`、`pauseAgent()`、`stopAgent()`、`summarize()`、`chat(message)`、`createTaskMessages(tasks)` 等方法。真正的任务细节由 `agent-work` 目录下的 work 类实现。

## 谁调用它

主要调用方在 `next/src/pages/index.tsx`。页面在用户提交目标后创建 `DefaultAgentRunModel`、`MessageService`、`AgentApi`，再实例化 `new AutonomousAgent(...)`，写入 `useAgentStore`，随后调用 `newAgent.run()` 启动执行。如果已有 agent 且生命周期为 `paused`，页面会再次调用 `agent.run()` 恢复。

交互组件也直接调用它：`next/src/components/index/chat.tsx` 触发 `agent.chat(...)`、`agent.pauseAgent()`、`agent.stopAgent()`；`next/src/components/console/SummarizeButton.tsx` 调用 `agent.summarize()`。`next/src/stores/agentStore.ts` 只保存 `AutonomousAgent | null` 引用，不负责执行逻辑。

## 它调用谁

它调用 `AgentRunModel` 读取目标、当前任务、剩余任务、生命周期，并更新生命周期或新增任务。默认实现 `DefaultAgentRunModel` 会进一步读写 `useAgentStore` 和 `useTaskStore`。

它调用 `AgentApi` 获取初始任务、分析任务、保存消息、创建 agent 记录。`AgentApi` 再通过 `/api/agent/start`、`/api/agent/analyze` 等后端接口工作，并维护 `runId`。它调用 `MessageService` 生成目标消息、任务消息、错误消息以及 UI 展示消息。

它还依赖各类 `AgentWork`：`StartGoalWork`、`AnalyzeTaskWork`、`ChatWork`、`SummarizeWork`。根据邻近文件可见，`AnalyzeTaskWork.next()` 会生成 `ExecuteTaskWork`；`ExecuteTaskWork`、`ChatWork`、`SummarizeWork` 通过 `streamText` 流式请求执行、聊天和总结接口。`CreateTaskWork` 存在于目录中，但当前目标文件没有直接引用；根据当前片段推断，当前循环主要依赖已有任务队列推进，而不是在 `AutonomousAgent` 中显式插入追加任务生成步骤。

## 核心流程

`run()` 是主循环。它先把生命周期设为 `running`。如果之前暂停时留下了 `lastConclusion`，会先补跑上一次 work 的 `conclude()`，避免暂停发生在 `run()` 完成后、`conclude()` 尚未执行时导致消息或状态丢失。

随后它调用 `addTasksIfWorklogEmpty()`：当 `workLog` 为空且模型中还有 `started` 状态任务时，放入一个 `AnalyzeTaskWork`。循环每次取队首 work，先检查生命周期；如果处于 `pausing`，转为 `paused` 并退出；如果不是 `running`，直接返回。然后通过 `runWork(work, shouldStop)` 执行带重试的 work，执行完移出队列。

work 执行后，如果生命周期已不再是 `running`，不会立刻 `conclude()`，而是把 `work.conclude()` 存到 `lastConclusion`，等待下一次 `run()` 恢复时补跑；否则立即 conclude。接着读取 `work.next()`，有后继 work 就追加到 `workLog`。如果队列又空了，再从模型当前任务中补一个 `AnalyzeTaskWork`。当没有 work 且没有任务时，`stopAgent()` 把生命周期设为 `stopped`。

## 关键函数的高层作用

`runWork()` 封装错误处理和重试。它使用 `withRetries` 包裹 `work.run()`，先让 work 自己的 `onError` 处理错误，再用 `isRetryableError` 判断是否可重试；不可重试时停止 agent。重试前会把 `isAgentThinking` 设为 true 并等待 2 秒，结束后设回 false。这里有一个细节：`const shouldRetry = work.onError?.(e) || true` 会让 falsy 返回值被 `true` 覆盖，因此从代码效果看，work 想通过返回 `false` 阻止重试可能不会生效；这会影响类似 `CreateTaskWork.onError = false` 的设计意图，虽然当前文件没有直接调它。

`addTasksIfWorklogEmpty()` 是任务队列桥接器：`workLog` 只记录“下一步动作”，真实待办任务保存在 `AgentRunModel`/store 中。队列空时，它取 `getCurrentTask()` 并创建 `AnalyzeTaskWork`，让模型任务进入分析、执行链路。

`summarize()` 是一次性总结流程：临时把生命周期设为 `running`，运行 `SummarizeWork`，conclude 后停止。它不进入主 `workLog` 循环。

`chat(message)` 是插队聊天流程：如果 agent 正在跑，先请求暂停；如果原本已停止，则临时标记为 `pausing` 并在聊天结束后恢复 `stopped`。随后运行 `ChatWork` 并 conclude。它会读取已完成任务结果作为上下文，具体在 `ChatWork` 中完成。

`createTaskMessages(tasks)` 把字符串任务批量转成 UI 消息，并同步调用 `model.addTask(value)` 写入任务 store。每个任务之间有 150ms 延迟，更多是为了前端展示节奏，而不是业务必要性。

## 修改风险

最高风险是生命周期语义。`running`、`pausing`、`paused`、`stopped` 不只是 UI 状态，也决定流式请求是否中断、work 是否 conclude、恢复后是否补偿执行。改动 `run()` 中暂停和 `lastConclusion` 的顺序，容易造成任务消息未保存、任务状态卡在 `executing`、恢复后重复 conclude 或漏执行。

第二个风险是 `workLog` 与 store 任务队列的双层状态。`workLog` 是执行动作队列，`useTaskStore` 中的任务才是业务待办。若新增 work 时没有正确实现 `next()` 或没有在合适时机更新任务状态，主循环可能提前 `stopped`，也可能不断重复分析同一个任务。

第三个风险是错误重试。`runWork()` 同时依赖 `work.onError`、`isRetryableError`、`withRetries` 和全局 thinking 状态。当前 `work.onError?.(e) || true` 会弱化 work 对“不要重试”的控制，修改这里可能改变所有任务、聊天、总结的失败行为；修复时应同步检查各 `AgentWork.onError` 的语义。

第四个风险是 API 与消息保存耦合。`StartGoalWork`、`AnalyzeTaskWork`、`ExecuteTaskWork` 等会通过 `MessageService` 先渲染消息，再通过 `AgentApi.saveMessages` 持久化。调整 `AutonomousAgent` 的执行时机，可能导致 UI 看得到但后端没保存，或保存顺序与展示顺序不一致。

最后，`chat()` 和 `summarize()` 共享同一个 `model`、`api.runId`、`messageService`。在主循环运行中触发聊天或总结时，暂停、流式中断、恢复之间存在竞态；任何改动都应重点测试“运行中暂停后聊天”“停止后聊天”“暂停后恢复”“执行中停止”这些交互路径。
