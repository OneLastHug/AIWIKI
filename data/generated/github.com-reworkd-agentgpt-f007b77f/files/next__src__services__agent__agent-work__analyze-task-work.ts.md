# 文件：next/src/services/agent/agent-work/analyze-task-work.ts

## 一句话定位

`AnalyzeTaskWork` 是 Agent 执行流水线中“分析当前任务”的工作单元：它把一个待执行 `Task` 标记为执行中，调用后端分析接口生成 `Analysis`，再根据分析结果决定是否进入真正的任务执行阶段 `ExecuteTaskWork`。

## 它暴露/定义了什么

该文件默认导出 `AnalyzeTaskWork` 类，并实现 `AgentWork` 接口约定的四个方法：`run`、`conclude`、`next`、`onError`。

类内部维护一个核心状态 `analysis: Analysis | undefined`。这个状态是 `run` 阶段调用 `parent.api.analyzeTask(...)` 的产物，也是后续 `conclude` 生成提示消息、`next` 决定是否创建执行工作单元的依据。构造函数接收两个依赖：`parent: AutonomousAgent` 和当前 `task: Task`。这里的 `parent` 不是简单容器，而是访问模型状态、API 层、消息服务的统一入口。

## 谁调用它

直接调用方在 `next/src/services/agent/autonomous-agent.ts`。`AutonomousAgent.addTasksIfWorklogEmpty` 会在 `workLog` 为空时，从 `model.getCurrentTask()` 取出当前任务，并 `push(new AnalyzeTaskWork(this, currentTask))`。随后 `AutonomousAgent.run` 从 `workLog` 取出 `AgentWork`，通过 `runWork` 执行它，再调用它的 `conclude` 和 `next`。

因此，`AnalyzeTaskWork` 不是被 UI 直接调用，而是被 `AutonomousAgent` 的工作队列调度。它处在 `StartGoalWork` 生成任务之后、`ExecuteTaskWork` 执行任务之前。

## 它调用谁

它主要调用三个方向的能力。

第一是状态模型：`parent.model.updateTaskStatus(this.task, "executing")`，用于把当前任务状态更新为执行中，并返回更新后的 `Task`。

第二是 API 层：`parent.api.analyzeTask(this.task.value)`。在 `next/src/services/agent/agent-api.ts` 中，`analyzeTask` 会请求 `/api/agent/analyze`，传入 `task` 和当前启用工具名 `tool_names`，返回 `Analysis`。`Analysis` 的结构定义在 `next/src/services/agent/analysis.ts`，包含 `reasoning`、`action` 和 `arg`，其中 `action` 可能是 `reason`、`search`、`wikipedia`、`image`、`code`。

第三是消息服务：`parent.messageService.sendAnalysisMessage(...)`、`skipTaskMessage(...)`、`sendErrorMessage(...)`，以及 `parent.api.saveMessages(...)`。这些调用负责把分析阶段的系统提示或错误提示写入前端消息流，并在有 agentId 时保存。

## 核心流程

`run` 是实际分析阶段。它先把 `task` 状态改为 `"executing"`，然后把 `task.value` 交给 `AgentApi.analyzeTask`，等待后端返回分析结果。这里没有本地分析逻辑，策略判断主要由后端 `/api/agent/analyze` 完成；根据当前片段推断，前端只负责传入任务文本和可用工具列表，依据是 `agent-api.ts` 中 `tool_names: useAgentStore.getState().tools.map(...)`。

`conclude` 是分析后的收尾阶段。如果 `analysis` 存在，就调用 `sendAnalysisMessage`，把分析出的动作转换成用户可见的系统提示，例如搜索网页、查 Wikipedia、生成图片、写代码或普通生成响应。如果 `analysis` 不存在，则发送跳过当前任务的消息。无论哪种情况，都会调用 `parent.api.saveMessages([message])` 尝试持久化消息。

`next` 是流水线连接点。如果没有 `analysis`，返回 `undefined`，表示不继续执行任务；如果有 `analysis`，返回新的 `ExecuteTaskWork(parent, task, analysis)`，把任务和分析结果交给执行阶段。

`onError` 是错误处理入口。它把异常交给 `messageService.sendErrorMessage` 展示，并返回 `true`，表示该工作单元愿意让 `AutonomousAgent.runWork` 的重试机制继续处理。真正是否停止还会受 `isRetryableError` 影响。

## 关键函数的高层作用

`run` 的高层职责是“取得执行计划”。它不关心分析结果如何生成，也不解释 `Analysis`，只负责把任务状态推进到执行中，并从 API 获得结构化分析。

`conclude` 的高层职责是“把分析阶段对用户可见化”。它不改变任务执行结果，只发送一条系统消息，让用户知道接下来 agent 准备采取什么类型的动作。

`next` 的高层职责是“把分析结果接入执行阶段”。这是该文件最关键的控制流出口：`Analysis` 存在才会进入 `ExecuteTaskWork`，否则当前任务不会被执行。

`onError` 的高层职责是“把异常转成消息并允许重试”。它不做分类判断，错误分类与停止逻辑主要在 `AutonomousAgent.runWork` 和 `types/errors` 相关逻辑中。

## 修改风险

最高风险是改变 `run` 中状态更新和 API 调用顺序。如果先分析再标记状态，UI 和任务模型可能在长请求期间仍显示旧状态；如果不保存 `this.task = updateTaskStatus(...)` 的返回值，后续 `ExecuteTaskWork` 可能拿到旧任务对象。

第二个风险是改变 `next` 的判定条件。当前设计中 `analysis` 是进入执行阶段的唯一门槛。如果放宽为总是创建 `ExecuteTaskWork`，执行阶段可能收到 `undefined` 分析结果；如果错误地返回 `undefined`，任务会只显示分析或跳过消息，而不会真正执行。

第三个风险是消息与持久化不一致。`conclude` 先通过 `messageService` 发送消息，再调用 `api.saveMessages` 保存同一个消息。如果改成只保存不发送，前端实时反馈会丢失；如果只发送不保存，刷新或历史记录可能缺少分析提示。

第四个风险是错误重试语义。`onError` 固定返回 `true`，配合 `withRetries` 和 `isRetryableError` 工作。若改为 `false`，可重试错误也可能不再重试；若吞掉错误但仍返回成功，调度器可能进入不完整的后续状态。

整体上，这个文件代码量小，但位于 agent 工作队列的关键衔接点。修改时应同时检查 `autonomous-agent.ts`、`agent-api.ts`、`execute-task-work.ts`、`message-service.ts`，确保任务状态、分析结果、用户消息和下一步工作单元四者仍然一致。
