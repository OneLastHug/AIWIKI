# 文件：next/src/services/agent/agent-work/execute-task-work.ts

## 一句话定位

`execute-task-work.ts` 是 Agent 工作链中“执行已分析任务”的节点：它把 `AnalyzeTaskWork` 产出的 `Analysis` 和当前 `Task` 发送到后端执行接口，通过流式文本持续更新前端消息与任务结果，并在完成后把任务标记为 `completed`。

## 它暴露/定义了什么

该文件默认导出 `ExecuteTaskWork` 类，并实现 `AgentWork` 接口。类内部主要状态只有两个：`result` 保存最终执行文本结果，`task` 保存执行过程中被不断更新的任务对象。构造函数接收三类上下文：`parent: AutonomousAgent`、当前 `task: Task`、前一步得到的 `analysis: Analysis`。

它实现了 `AgentWork` 约定的几个方法：`run`、`conclude`、`next`、`onError`。其中只有 `run` 承担核心业务；`conclude` 是空实现，`next` 返回 `undefined`，表示执行任务之后不会直接追加下一个工作节点；`onError` 负责把异常转成错误消息并允许重试。

## 谁调用它

直接创建它的是 `next/src/services/agent/agent-work/analyze-task-work.ts`。`AnalyzeTaskWork.next()` 在 `analysis` 存在时返回 `new ExecuteTaskWork(this.parent, this.task, this.analysis)`。

再往上看，`AutonomousAgent` 是工作链调度者。`next/src/services/agent/autonomous-agent.ts` 的 `addTasksIfWorklogEmpty()` 会从 `AgentRunModel.getCurrentTask()` 取当前任务，放入 `AnalyzeTaskWork`。`AutonomousAgent.run()` 通过 `runWork(work)` 执行每个 `AgentWork`，执行完调用 `conclude()`，再读取 `work.next()`，所以 `ExecuteTaskWork` 是由 `AnalyzeTaskWork` 的后继关系间接进入 `workLog` 的。

## 它调用谁

它最关键的外部调用是 `streamText`，来源于 `next/src/services/stream-utils.ts`。`streamText` 会向后端发起 `POST` 请求并读取 `text/event-stream` 风格的响应流。

它还调用 `parent` 上的多个服务：`parent.messageService.sendMessage()` 创建执行消息，`parent.messageService.updateMessage()` 在流式输出时刷新消息，`parent.messageService.sendErrorMessage()` 处理异常；`parent.model.updateTaskResult()` 保存任务执行结果，`parent.model.updateTaskStatus()` 改任务状态，`parent.model.getGoal()` 和 `parent.model.getLifecycle()` 提供目标与生命周期；`parent.api.saveMessages()` 持久化消息，`parent.api.runId` 和 `parent.api.props.session?.accessToken` 提供请求上下文。

此外，它调用 `toApiModelSettings()` 把前端模型设置和会话信息转换为后端 API 所需结构，调用 `uuid` 的 `v1()` 为执行消息生成新 id。

## 核心流程

`run()` 开始时先基于当前 `task` 构造一条 `executionMessage`。这条消息复用任务字段，但生成新 `id`，状态设为 `completed`，初始 `info` 为 `Loading...`。随后立即通过 `messageService.sendMessage()` 发到前端消息流中，让用户先看到任务进入执行结果输出阶段。

接着它调用 `streamText("/api/agent/execute", body, accessToken, onStart, onText, shouldClose)`。请求体包含 `run_id`、当前目标 `goal`、任务文本 `task`、分析结果 `analysis`、以及转换后的 `model_settings`。文件中有 TODO 注释说明“这部分应移动到 api layer”，意味着当前实现把 API 请求组装逻辑放在 work 节点内，边界并不完全理想。

流开始时，`onStart` 把 `executionMessage.info` 清空，覆盖掉 `Loading...`。每收到一段文本，`onText` 会把文本追加到 `executionMessage.info`，同步调用 `updateTaskResult()` 更新任务结果，再调用 `updateMessage()` 刷新消息内容。`shouldClose` 会检查 `parent.model.getLifecycle() === "stopped"`，如果 Agent 被停止，底层 `streamText` 会取消 reader，提前断开流。

流结束后，`run()` 把最终消息内容写入 `this.result`，调用 `parent.api.saveMessages([executionMessage])` 持久化消息，然后通过 `updateTaskStatus(this.task, "completed")` 把任务状态正式标记为完成。

## 关键函数的高层作用

`run` 是核心函数，负责从“已分析任务”进入“执行任务并接收流式结果”的完整生命周期：创建消息、发起执行请求、流式追加结果、同步任务结果、保存消息、完成任务状态。

`onError` 是错误入口，它不区分错误类型，只把错误交给 `messageService.sendErrorMessage(e)` 展示，并返回 `true`。结合 `AutonomousAgent.runWork()` 可知，真正是否重试还受 `isRetryableError(e)` 影响；该方法只表达“本 work 允许重试”。

`conclude` 是空实现。根据当前片段推断，执行阶段的收尾已经全部放在 `run()` 内完成，因此不需要像 `AnalyzeTaskWork.conclude()` 那样额外保存分析消息或跳过消息。

`next` 返回 `undefined`，表示执行完成后不直接创建 `CreateTaskWork` 或其他后继。根据当前片段推断，后续是否继续处理任务由 `AutonomousAgent.run()` 的 `addTasksIfWorklogEmpty()` 重新检查任务队列决定，而不是由 `ExecuteTaskWork` 自己决定。

## 修改风险

第一类风险是消息状态与任务状态不一致。`executionMessage.status` 一开始就被设为 `completed`，但任务本身直到流结束才 `updateTaskStatus(..., "completed")`。如果修改这里的状态语义，需要同步检查 UI 对 `Message.status` 和 `Task.status` 的理解，否则可能出现“消息显示完成但任务仍在执行”或相反的问题。

第二类风险是流式更新频率。`onText` 每收到片段都会调用 `updateTaskResult()` 和 `updateMessage()`，这会直接影响 Zustand store 或类似前端状态层的刷新频率。若后端流片段很碎，修改为更频繁或更重的逻辑可能造成 UI 卡顿；若改成批量更新，又会降低实时反馈。

第三类风险是停止逻辑。`shouldClose` 只检查生命周期是否为 `stopped`，没有处理 `pausing`。这与 `AutonomousAgent.run()` 的暂停机制有关，随意改动可能导致暂停、停止、恢复时流连接处理不一致。

第四类风险是 API 边界。文件直接知道 `"/api/agent/execute"`、`accessToken`、`model_settings` 组装方式，而其他 API 多由 `AgentApi` 封装。若要重构，应把执行接口迁移到 `AgentApi` 或专门的流式 API 层，并保持 `run_id`、鉴权、停止回调、错误传播行为不变。

第五类风险是任务对象引用更新。代码每次更新结果后都把返回的新 `Task` 重新赋给 `this.task`。如果改成只传旧对象，后续 `updateTaskStatus()` 可能基于过期任务覆盖掉最新 `result`。这一点是维护任务结果连续性的关键。
