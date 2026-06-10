# 目录：src/tasks

## 它负责什么

`src/tasks` 是这个仓库里“任务实体层”的核心目录，集中定义各种可被 AppState 持有、可被 UI 展示、可被停止或完成的任务类型。这里不是单纯的业务工具集合，而是把“任务是什么、怎样注册、怎样推进状态、怎样终止”这些生命周期规则按类型拆开实现。

从当前片段看，它覆盖了几类任务：本地 shell 命令、本地 agent、远程 agent、进程内 teammate、工作流任务、MCP 监控任务，以及 `DreamTask` 这类偏后台/可视化的特殊任务。它们共同的特征是：都要进入统一的任务注册体系，都会写入 `AppState.tasks`，并参与底部 pill、背景任务面板、终止通知、SDK 事件等流程。

## 直接子目录地图

- `src/tasks/DreamTask/`：`DreamTask` 的生命周期入口。根据文件内容，它主要用于 auto-dream / memory consolidation 这类“原本不可见的后台 subagent”在 UI 中可见化。
- `src/tasks/InProcessTeammateTask/`：进程内 teammate 任务。它管理同进程 swarm teammate 的状态、消息注入、排序和身份信息。
- `src/tasks/LocalAgentTask/`：本地 agent 任务。这里既有任务状态定义，也有进度统计、消息队列、盘上 transcript 相关逻辑。
- `src/tasks/LocalShellTask/`：本地 shell / bash 任务。包含任务状态、守护逻辑、停止逻辑和输出阻塞检测，属于最重的任务类型之一。
- `src/tasks/LocalWorkflowTask/`：工作流任务入口。根据当前片段推断，它是给 workflow 脚本单独挂一个后台任务壳，方便在面板里查看、杀掉、跳过或重试子步骤。
- `src/tasks/MonitorMcpTask/`：MCP 资源监控任务。根据文件头注释，它负责把长期订阅流暴露到 UI。
- `src/tasks/RemoteAgentTask/`：远程 agent 任务。负责远程会话、轮询、内容提取、完成钩子和远程任务元数据。
- `src/tasks/LocalAgentTask/__tests__/`：本目录里唯一显式的测试子目录，用来覆盖 local agent 的行为边界。

根目录下还有几个直接文件：

- `src/tasks/types.ts`
- `src/tasks/stopTask.ts`
- `src/tasks/pillLabel.ts`
- `src/tasks/LocalMainSessionTask.ts`

## 关键入口

这个目录真正的“对外入口”不是目录名本身，而是几个导出点：

- `src/tasks/types.ts`：定义 `TaskState` 和 `BackgroundTaskState` 联合类型，以及 `isBackgroundTask()`。它是上层组件判断“哪些任务算后台任务”的统一口径。
- `src/tasks/stopTask.ts`：统一停止逻辑。它先查任务、验状态、找具体 task 实现，再调用 `kill()`，最后按类型决定是否补发通知。
- `src/tasks/pillLabel.ts`：把一组后台任务压缩成底部 pill 文案，是 UI 层和转录层共用的命名规则。
- `src/tasks/LocalMainSessionTask.ts`：把主会话背景化后的查询变成一个独立任务，和普通 `local_agent` 共用大部分状态结构，但 `agentType` 固定为 `main-session`。

在各子目录内部，最关键的通常是“注册 + 完成 + kill”三件套，例如 `register...Task()`、`complete...Task()`、`kill...()`，这些函数才是状态流转的真实入口。

## 主流程位置

主流程不在这个目录里全部闭环，它更多是“被主流程调用的任务层”。从依赖关系看，核心链路大致是：

1. 上层命令或交互层创建任务，调用各任务目录里的 `register...Task()` 或 `spawn...Task()`。
2. 任务对象被 `registerTask()` 写入 `AppState.tasks`，同时创建输出文件、清理钩子和 abort controller。
3. 运行过程中，任务通过 `updateTaskState()` 更新进度、消息、状态、终止时间等字段。
4. 终止时，统一走 `kill()` 或类型专属的 `complete.../fail...`，并可能触发 `enqueuePendingNotification()`、`emitTaskTerminatedSdk()`、`evictTaskOutput()`。
5. UI 层则通过 `src/components/TaskListV2.tsx`、`src/screens/REPL.tsx`、`src/components/Spinner.tsx` 等消费这些状态。

从当前片段推断，`src/tasks` 与 `src/utils/task/framework.ts` 是强耦合搭档：前者定义“某类任务怎么长、怎么死”，后者负责“如何放进全局任务系统、如何回收”。

## 推荐阅读顺序

1. 先看 `src/tasks/types.ts`，建立任务联合类型和后台任务判定的总图。
2. 再看 `src/tasks/pillLabel.ts`，理解后台任务在 UI 上如何被压缩展示。
3. 然后看 `src/tasks/stopTask.ts`，把“统一停止路径”作为主入口抓住。
4. 接着看 `src/tasks/LocalMainSessionTask.ts` 和 `src/tasks/LocalShellTask/`，这两类最接近主交互路径，能帮助你理解任务生命周期和通知机制。
5. 再看 `src/tasks/LocalAgentTask/`、`RemoteAgentTask/`、`InProcessTeammateTask/`、`LocalWorkflowTask/`、`MonitorMcpTask/`、`DreamTask/`，按“普通 agent → 远程 agent → teammate → 工作流/监控/特殊任务”的顺序补全分支。
6. 最后回到消费端：`src/screens/REPL.tsx`、`src/components/TaskListV2.tsx`、`src/utils/task/framework.ts`，把目录里的类型和状态流转接回实际 UI。

## 常见误区

- 不要把 `src/tasks` 误解成“普通工具函数目录”。这里的核心是任务模型和生命周期，而不是零散 helper。
- 不要只盯着某个任务子目录里的 `Task` 导出。真正的统一口径在 `src/tasks/types.ts`、`src/tasks/stopTask.ts` 和 `src/utils/task/framework.ts`。
- 不要忽略 `LocalMainSessionTask.ts`。它看起来像 local agent 的变体，但实际上承担的是主会话背景化这条关键路径。
- 不要把 `pillLabel.ts` 当成纯展示文本文件。它定义的是“后台任务聚合语义”，和面板、转录、状态提示要保持一致。
- 不要假设所有任务都能直接 kill 成功。`stopTask.ts` 先按类型分发，再按状态判断，并对 `local_bash` 这类任务做了额外的通知抑制逻辑。
- 不要忽略文件输出和 sidecar 约定。多个任务类型都会接 `getTaskOutputPath()`、`initTaskOutputAsSymlink()`、`evictTaskOutput()` 这一套，任务状态和磁盘 transcript 是绑定的。
