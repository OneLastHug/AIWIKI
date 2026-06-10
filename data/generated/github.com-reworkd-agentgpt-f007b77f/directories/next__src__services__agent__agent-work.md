# 子系统：next/src/services/agent/agent-work

## 解决什么问题

`next/src/services/agent/agent-work` 是 AgentGPT 前端服务层里“Agent 工作单元”的实现目录。它把一个自治 Agent 的运行拆成若干可调度、可重试、可串联的小步骤，例如启动目标、分析任务、执行任务、生成后续任务、对话追问、总结结果。

这个目录本身不负责保存全局状态，也不直接实现大模型 API 的全部细节；它更像是 `AutonomousAgent` 的动作层。每个 `Work` 对象都拿到同一个 `parent: AutonomousAgent`，通过 `parent.model` 读写任务状态，通过 `parent.api` 调用后端或持久化消息，通过 `parent.messageService` 把运行过程呈现到 UI 消息流中。

## 相关目录和文件

核心文件集中在 `next/src/services/agent/agent-work`：

`agent-work.ts` 定义统一接口 `AgentWork`，要求每个工作单元实现 `run`、`conclude`、`next`、`onError`。

`start-task-work.ts` 实现 `StartGoalWork`，负责 Agent 启动时发送目标消息、拉取初始任务、创建 agent 运行记录，并把初始任务写入消息流。

`analyze-task-work.ts` 实现 `AnalyzeTaskWork`，负责把任务标记为 `executing`，调用分析接口，并在分析成功后衔接到执行阶段。

`execute-task-work.ts` 实现 `ExecuteTaskWork`，负责流式执行单个任务，把模型输出持续写回消息和任务结果。

`create-task-work.ts` 实现 `CreateTaskWork`，负责根据当前任务、剩余任务、已完成任务和当前结果生成更多任务。根据当前片段推断，它是补充任务生成阶段的工作单元；依据是它调用 `parent.api.getAdditionalTasks` 并通过 `parent.createTaskMessages` 保存新增任务消息。但在已检索到的 `autonomous-agent.ts` 调用片段中，没有看到它被直接构造。

`chat-work.ts` 实现 `ChatWork`，用于在已有目标和已完成结果上下文上回答用户追问。

`summarize-work.ts` 实现 `SummarizeWork`，用于把已完成任务结果汇总成总结。

相邻上下文主要是 `next/src/services/agent/autonomous-agent.ts`。它导入 `AgentWork`、`StartGoalWork`、`AnalyzeTaskWork`、`ChatWork`、`SummarizeWork`，并维护类似 `workLog` 的执行队列或历史：启动时放入 `new StartGoalWork(this)`，处理当前任务时放入 `new AnalyzeTaskWork(this, currentTask)`，总结和聊天则分别创建 `SummarizeWork`、`ChatWork`。

## 核心对象

`AgentWork` 是该目录的抽象协议。`run()` 执行主要副作用，例如调用 API、流式请求、更新模型状态；`conclude()` 做收尾，例如发送分析消息、创建任务消息、保存消息；`next()` 返回下一个工作单元，用来表达阶段衔接；`onError(e)` 统一处理错误，并返回是否继续重试。

`StartGoalWork` 是运行入口对象。它先通过 `messageService.sendGoalMessage` 创建目标消息，再调用 `api.getInitialTasks()` 获取初始任务，随后 `api.createAgent()` 建立运行记录，最后保存目标消息。收尾阶段会调用 `parent.createTaskMessages` 把初始任务转成消息。

`AnalyzeTaskWork` 是任务执行前的规划阶段。它通过 `model.updateTaskStatus(task, "executing")` 修改任务状态，再用 `api.analyzeTask(task.value)` 获取 `Analysis`。如果有分析结果，收尾时发送 analysis 消息；如果没有结果，则发送 skip task 消息。它的 `next()` 会在有 `analysis` 时返回 `new ExecuteTaskWork(...)`。

`ExecuteTaskWork` 是真正产生任务结果的阶段。它创建一条 `Message`，初始 `info` 为 `Loading...`，然后调用 `streamText` 请求 `/api/agent/execute`。流开始时清空 `info`，每收到一段文本就追加到 `executionMessage.info`，同步调用 `model.updateTaskResult` 和 `messageService.updateMessage`。结束后保存消息，并把任务状态更新为 `completed`。

`ChatWork` 和 `SummarizeWork` 都是基于已完成任务结果的流式生成工作。它们会从 `model.getCompletedTasks()` 中筛选非空 `result`，传给 `/api/agent/chat` 或 `/api/agent/summarize`，再把流式文本更新到消息里。

`CreateTaskWork` 是生成追加任务的对象。它将当前任务、剩余任务、已完成任务和当前任务结果传给 `api.getAdditionalTasks`，再把返回的任务值转成消息保存。它的错误策略是忽略错误并停止继续创建更多任务。

## 运行流程

标准任务链路可以理解为：

1. `AutonomousAgent` 创建 `StartGoalWork`。
2. `StartGoalWork.run()` 发送目标、获取初始任务、创建 agent 运行记录。
3. `StartGoalWork.conclude()` 把初始任务写成任务消息。
4. `AutonomousAgent` 选择当前任务，创建 `AnalyzeTaskWork`。
5. `AnalyzeTaskWork.run()` 将任务置为 `executing`，并请求任务分析。
6. `AnalyzeTaskWork.conclude()` 发送分析消息或跳过消息。
7. `AnalyzeTaskWork.next()` 在分析成功时返回 `ExecuteTaskWork`。
8. `ExecuteTaskWork.run()` 调用流式执行接口，边接收边更新 UI 消息和任务结果。
9. 执行完成后保存最终消息，并把任务状态置为 `completed`。

聊天和总结不是主任务链的一部分，更像用户触发的旁路工作流。`ChatWork` 根据目标、用户输入、已完成结果生成回答；`SummarizeWork` 根据目标和所有已完成结果生成总结。二者都没有后继 `next()`。

## 上下游依赖

上游主要是 `next/src/services/agent/autonomous-agent.ts`。它决定什么时候创建哪个 `AgentWork`，并向工作单元提供 `model`、`api`、`messageService`、`modelSettings`、`session` 等上下文。

状态依赖来自 `parent.model`。该目录使用 `getGoal`、`getRemainingTasks`、`getCompletedTasks`、`updateTaskStatus`、`updateTaskResult`、`getLifecycle` 等能力。尤其是 `streamText` 的停止条件依赖 `getLifecycle() === "stopped"`，所以生命周期状态会直接影响流式请求是否中止。

API 依赖来自 `parent.api`。主要方法包括 `getInitialTasks`、`createAgent`、`saveMessages`、`analyzeTask`、`getAdditionalTasks`，以及属性 `runId`、`props.session?.accessToken`。其中 `ExecuteTaskWork`、`ChatWork`、`SummarizeWork` 目前直接调用 `streamText` 和后端路径 `/api/agent/execute`、`/api/agent/chat`、`/api/agent/summarize`。源码里也标了 TODO，提示这部分应移动到 api layer。

类型依赖包括 `next/src/types/task` 的 `Task`、`next/src/types/message` 的 `Message`、`next/src/services/agent/analysis` 的 `Analysis`。模型设置会经 `next/src/utils/interfaces` 的 `toApiModelSettings` 转成接口需要的结构。消息 ID 使用 `uuid` 的 `v1()` 生成。

## 修改时最容易踩的坑

第一，`run` 和 `conclude` 的职责不要混淆。多数主要副作用发生在 `run`，而消息收尾、任务消息创建、阶段结束后的保存常放在 `conclude`。如果把保存逻辑提前或遗漏，UI 可能能看到临时消息，但刷新后丢失。

第二，`next()` 是阶段衔接点，不是所有工作单元都会返回后继。`AnalyzeTaskWork` 会根据 `analysis` 返回 `ExecuteTaskWork`，但 `ExecuteTaskWork`、`ChatWork`、`SummarizeWork`、`CreateTaskWork` 都返回 `undefined`。新增阶段时要确认调度方是否真的会消费 `next()`。

第三，流式输出期间同一条 `executionMessage` 会被持续修改。`ExecuteTaskWork` 还会同步更新 `task.result`。如果改成不可变对象或延迟批量更新，需要同时处理 `messageService.updateMessage` 和 `model.updateTaskResult`，否则 UI 展示和内部任务状态会不一致。

第四，错误策略并不完全相同。`StartGoalWork`、`AnalyzeTaskWork`、`ExecuteTaskWork`、`ChatWork`、`SummarizeWork` 都会发送错误消息并返回 `true`，表示调度层可以继续重试；`CreateTaskWork` 返回 `false`，含义是忽略错误且不继续创建更多任务。统一改动 `onError` 时要避免破坏这个语义差异。

第五，`CreateTaskWork` 在当前可见调用关系中没有直接入口。修改它之前应先确认实际调度逻辑是否在别处、是否曾被移除、或者是否是遗留设计。根据当前片段推断，它的存在说明系统曾设计过“执行后扩展任务列表”的阶段，但当前 `autonomous-agent.ts` 片段没有显示该阶段被接入。

## 推荐阅读顺序

先读 `next/src/services/agent/agent-work/agent-work.ts`，理解统一工作单元接口。

再读 `next/src/services/agent/autonomous-agent.ts`，看这些工作单元如何被创建、放入 `workLog`、执行和重试。

然后按主链路阅读 `next/src/services/agent/agent-work/start-task-work.ts`、`next/src/services/agent/agent-work/analyze-task-work.ts`、`next/src/services/agent/agent-work/execute-task-work.ts`。

接着阅读旁路能力 `next/src/services/agent/agent-work/chat-work.ts`、`next/src/services/agent/agent-work/summarize-work.ts`。

最后再看 `next/src/services/agent/agent-work/create-task-work.ts`，并结合调度层确认它在当前版本中是否仍被使用。
