# 文件：next/src/services/agent/agent-run-model.tsx

## 一句话定位

`next/src/services/agent/agent-run-model.tsx` 是前端 Agent 单次运行的数据模型适配层：它把“本次运行的目标、运行 ID、生命周期、任务队列读写”封装成 `AgentRunModel` 接口，供 `AutonomousAgent` 用统一方式驱动任务执行，而不直接关心 Zustand store 的具体结构。

## 它暴露/定义了什么

文件主要定义三类内容。

第一是 `AgentRunModel` interface，描述 Agent 运行时需要的最小数据能力：读取 run id、读取目标、读写生命周期、获取待处理任务/当前任务/已完成任务、追加任务、更新任务状态与结果。

第二是 `AgentLifecycle` 类型，限定生命周期只能是 `"offline"`、`"running"`、`"pausing"`、`"paused"`、`"stopped"`。这个类型也被 `next/src/stores/agentStore.ts` 和控制组件复用，属于前端 Agent 状态机的公共枚举。

第三是 `DefaultAgentRunModel` class，这是当前唯一的默认实现。它在构造时生成一个 `uuid v4` 作为本次运行 ID，并保存用户输入的 goal；运行中的可变状态并不放在类实例字段里，而是读写 `useAgentStore` 和 `useTaskStore`。

## 谁调用它

直接创建者在 `next/src/pages/index.tsx`。用户开始一个新 Agent 时，`handleNewAgent` 会执行 `new DefaultAgentRunModel(goal.trim())`，随后把它传给 `new AutonomousAgent(...)`。

核心使用者是 `next/src/services/agent/autonomous-agent.ts`。`AutonomousAgent` 只依赖 `AgentRunModel` 接口，不依赖 `DefaultAgentRunModel` 的具体实现。它通过 `model.setLifecycle()` 控制运行状态，通过 `model.getCurrentTask()` 找到下一项任务，通过 `model.addTask()` 追加新任务。

间接使用者包括多个 `agent-work`：`analyze-task-work.ts` 把任务从 `started` 改成 `executing`，`execute-task-work.ts` 写入执行结果并标记 `completed`，`create-task-work.ts` 读取 remaining/completed 任务作为生成后续任务的上下文，`chat-work.ts`、`summarize-work.ts` 也会读取已完成任务。

## 它调用谁

它直接调用两个 Zustand store。

`useAgentStore` 负责 Agent 级别状态，包括 `lifecycle`、`setLifecycle`，以及其他文件使用的 `agent`、`isAgentThinking`、`tools` 等。当前文件只读写生命周期。

`useTaskStore` 负责任务数组。当前文件通过 `tasks.filter(...)` 读取待执行和已完成任务，通过 `addTask` 插入新任务，通过 `updateTask` 更新已有任务。

它还调用 `uuid` 包的 `v4()`，分别用于生成 run id 和新增任务 id。

## 核心流程

一次新运行开始时，页面层根据用户 goal 创建 `DefaultAgentRunModel`。构造函数只做两件事：生成不可变的 `id`，保存不可变的 `goal`。随后 `AutonomousAgent.run()` 调用 `model.setLifecycle("running")`，正式进入执行循环。

执行循环中，`AutonomousAgent.addTasksIfWorklogEmpty()` 会在工作队列为空时调用 `model.getCurrentTask()`。而 `getCurrentTask()` 实际取的是 `getRemainingTasks()[0]`，即 `useTaskStore` 中第一个 `status === "started"` 的任务。找到任务后，Agent 创建 `AnalyzeTaskWork`。

任务被分析时，`AnalyzeTaskWork.run()` 调用 `updateTaskStatus(task, "executing")`。任务执行时，`ExecuteTaskWork.run()` 在流式返回文本过程中反复调用 `updateTaskResult(...)`，把中间结果写回 store；流结束后再调用 `updateTaskStatus(task, "completed")`。后续 `CreateTaskWork` 会用 `getRemainingTasks()` 和 `getCompletedTasks()` 作为上下文请求更多任务，再通过 `AutonomousAgent.createTaskMessages()` 间接调用 `model.addTask()` 追加新任务。

生命周期也贯穿整个流程。`pauseAgent()` 设置 `"pausing"`，主循环检测到后转为 `"paused"` 并返回；`stopAgent()` 设置 `"stopped"`；恢复运行时仍通过同一个 model 读取当前 store 中剩余任务。

## 关键函数的高层作用

`getId()` 和 `getGoal()` 提供本次运行的稳定标识与目标。`id` 主要用于区分一次 run，`goal` 会在执行任务请求中作为全局目标传给后端或执行接口。

`getLifecycle()` / `setLifecycle()` 是 `AutonomousAgent` 的状态机入口。它们没有本地缓存，始终读写 `useAgentStore.getState()`，因此 UI、控制按钮和运行循环看到的是同一份生命周期状态。

`getRemainingTasks()` 定义“还需要处理”的含义：只认 `status === "started"`。这意味着处于 `"executing"` 的任务不会再次被 `getCurrentTask()` 选中，已完成任务也不会进入待处理队列。

`getCurrentTask()` 是一个简单队列策略：取 remaining tasks 的第一个。这里没有优先级、排序字段或并发调度，任务执行顺序取决于 `useTaskStore.tasks` 数组顺序。

`getCompletedTasks()` 用于为总结、聊天、生成新任务提供历史上下文。它只认 `status === "completed"`，不会包含 `"final"` 或空状态任务。

`addTask(taskValue)` 把字符串包装成标准 `Task` 对象：`type: "task"`、`status: "started"`、`result: ""`，并生成新的 uuid。它是后续任务进入执行队列的唯一模型入口。

`updateTaskStatus()` 和 `updateTaskResult()` 都是浅拷贝任务后交给 `updateTask()`。`updateTask()` 再调用 `useTaskStore.updateTask(updatedTask)`，最后返回更新后的对象，方便 work 类继续持有最新 task 引用。

## 修改风险

最大风险是任务状态语义。`getRemainingTasks()` 写死只筛选 `"started"`，如果新增状态、改名状态，或希望 `"executing"` 任务可恢复，必须同步调整 `AutonomousAgent` 与各个 `agent-work` 的状态流转，否则可能出现任务永远不被调度、暂停后无法恢复、或任务重复执行。

第二个风险是 store 更新匹配逻辑。`useTaskStore.updateTask` 通过 `task.id === updatedTask.id && task.taskId == updatedTask.taskId` 匹配任务；而 `addTask()` 创建的任务只有 `id`，`taskId` 是可选字段。修改 `Task` 标识字段、引入后端任务 ID 或改变 `taskId` 赋值方式时，要验证旧任务是否还能被正确更新。

第三个风险是生命周期一致性。`AgentLifecycle` 被 store、页面、控制组件和 `AutonomousAgent` 共同依赖。新增或删除生命周期值时，不能只改这个文件；例如 `index.tsx` 里启动按钮逻辑依赖 `"paused"`、`"stopped"`，聊天页控制逻辑也会根据 lifecycle 决定暂停、继续或停止。

第四个风险是把可变状态搬进 class 字段。当前实现刻意让任务和生命周期落在 Zustand 中，这样 UI 与 Agent 执行循环共享状态。如果改成本地缓存，需要处理同步、React 渲染刷新、暂停按钮即时生效等问题。

第五个风险是文件扩展名为 `.tsx` 但内容没有 JSX。改名为 `.ts` 理论上更贴合内容，但会影响所有 import 路径、构建缓存和工具配置；除非项目有统一清理需求，否则不应在功能修改中顺手改名。
