# 文件：next/src/services/agent/agent-work/start-task-work.ts

## 一句话定位

`start-task-work.ts` 是 `AutonomousAgent` 工作流的启动节点：它把用户目标写入消息流，向后端请求首批任务，确保 agent 记录被创建，并在收尾阶段把首批任务转成前端可见、模型可执行的任务队列。

## 它暴露/定义了什么

该文件默认导出 `StartGoalWork` 类，实现 `AgentWork` 接口。虽然文件名是 `start-task-work.ts`，类名叫 `StartGoalWork`，从职责看它同时处理“启动目标”和“初始化任务”。

`StartGoalWork` 内部维护一个 `tasksValues: string[]`，用于暂存 `getInitialTasks()` 返回的首批任务文本。它实现了 `AgentWork` 约定的四个方法：`run()`、`conclude()`、`onError()`、`next()`。

其中 `run()` 是实际启动动作，`conclude()` 是启动动作完成后的落地动作，`onError()` 负责把异常转成错误消息，`next()` 返回 `undefined`，表示它本身不直接指定下一个 work。

## 谁调用它

直接调用方是 `next/src/services/agent/autonomous-agent.ts`。`AutonomousAgent` 构造函数中初始化 `workLog = [new StartGoalWork(this)]`，所以每个新 agent 运行时，第一项工作就是 `StartGoalWork`。

后续执行由 `AutonomousAgent.run()` 驱动：它取出 `workLog[0]`，通过 `runWork(work)` 调用 `work.run()`，再在合适时机调用 `work.conclude()`，最后调用 `work.next()` 尝试加入后续 work。由于 `StartGoalWork.next()` 返回 `undefined`，真正的下一步不是由它直接返回，而是由 `AutonomousAgent.addTasksIfWorklogEmpty()` 根据模型中的当前任务创建 `AnalyzeTaskWork`。

## 它调用谁

`StartGoalWork` 主要依赖传入的 `AutonomousAgent parent`，再通过 parent 访问三个核心协作者。

它调用 `parent.model.getGoal()` 读取用户目标；调用 `parent.messageService.sendGoalMessage()` 生成并渲染目标消息；调用 `parent.api.getInitialTasks()` 请求首批任务；调用 `parent.api.createAgent()` 创建或确认持久化 agent；调用 `parent.api.saveMessages()` 保存目标消息和任务消息；在 `conclude()` 中调用 `parent.createTaskMessages()`，该方法会逐个调用 `messageService.startTask()` 并通过 `model.addTask()` 把任务加入运行模型。

从 `AgentApi` 可见，`getInitialTasks()` 会向 `/api/agent/start` 发送包含目标和模型配置的请求，返回 `newTasks`；`createAgent()` 通过 `agentUtils.createAgent()` 创建 agent；`saveMessages()` 只有在 `agentId` 存在时才会保存。

## 核心流程

启动阶段分两段完成，分别对应 `run()` 和 `conclude()`。

`run()` 首先把目标消息发送到消息流：`sendGoalMessage(this.parent.model.getGoal())`。这一步会立即渲染目标消息，并返回可保存的 `Message` 对象。随后它调用 `parent.api.getInitialTasks()`，让后端根据目标生成首批任务文本，并暂存在 `tasksValues`。接着调用 `parent.api.createAgent()` 创建持久化 agent，最后调用 `parent.api.saveMessages([goalMessage])` 保存目标消息。

`conclude()` 在 `run()` 成功后执行。它把 `tasksValues` 交给 `parent.createTaskMessages()`。该方法会为每个任务创建 `task` 类型消息、渲染到消息流、加入 `AgentRunModel` 的任务队列，并在任务之间短暂延迟。返回的任务消息随后通过 `parent.api.saveMessages(messages)` 保存。

这意味着首批任务不是在 `run()` 中加入模型，而是在 `conclude()` 中加入。这个设计和 `AutonomousAgent.run()` 的暂停逻辑有关：如果 agent 在某个 work 运行后不再处于 running 状态，`AutonomousAgent` 会把 `work.conclude()` 缓存在 `lastConclusion`，等下次恢复时再播放收尾动作，避免 UI 与模型状态在暂停边界上出现半完成状态。

## 关键函数的高层作用

`run()` 是启动请求的主体。它负责展示目标、请求初始任务、创建 agent 记录、保存目标消息。这里的顺序很重要：目标消息先在本地展示；任务先从后端取回；然后创建 agent；最后保存目标消息。由于 `AgentApi.saveMessages()` 在没有 `agentId` 时会直接返回，所以 `createAgent()` 必须发生在保存之前。

`conclude()` 是任务落地阶段。它不再请求后端，只负责把已获得的任务文本转成系统内部的任务消息和任务队列。根据当前片段推断，`AutonomousAgent.addTasksIfWorklogEmpty()` 后续能拿到 `model.getCurrentTask()`，正是依赖这里调用 `model.addTask()`。

`onError()` 是统一错误展示入口。它调用 `messageService.sendErrorMessage(e)`，然后返回 `true`，表示允许 `AutonomousAgent.runWork()` 的重试逻辑继续处理。实际是否停止还会受 `isRetryableError(e)` 影响。

`next()` 返回 `undefined`。这说明启动 work 不直接知道下一个具体任务 work；它只负责准备任务队列，调度权交回 `AutonomousAgent`。

## 修改风险

第一类风险是执行顺序风险。若把 `createAgent()` 移到 `saveMessages()` 之后，目标消息可能不会被保存，因为 `AgentApi.saveMessages()` 在 `agentId` 缺失时直接忽略。若把 `createTaskMessages()` 提前到 `run()`，可能破坏暂停恢复时 `lastConclusion` 的语义，使任务已进入模型但收尾消息未按预期播放。

第二类风险是状态一致性风险。`tasksValues` 是 `run()` 和 `conclude()` 之间的桥梁，任何异步改动、重复调用或清空逻辑都会影响首批任务是否能进入 `AgentRunModel`。如果 `getInitialTasks()` 返回空数组，流程仍会保存目标消息，但后续没有可分析任务，agent 可能直接停止，这是合理但需要调用方能接受的状态。

第三类风险是持久化与 UI 不一致。`sendGoalMessage()`、`startTask()` 会先渲染消息，再由 `saveMessages()` 保存。如果保存失败或 `agentId` 不存在，用户界面可能已经看到消息，但后端没有完整记录。修改这里时需要同时理解 `MessageService` 的即时渲染行为和 `AgentApi` 的保存条件。

第四类风险是命名误导。文件名是 `start-task-work.ts`，类名是 `StartGoalWork`，职责又包含 goal 与 initial tasks。重命名或拆分时要同步检查 `autonomous-agent.ts` 的 import，并避免只按文件名理解为“开始单个任务”；它实际上是整个 agent run 的入口 work。
