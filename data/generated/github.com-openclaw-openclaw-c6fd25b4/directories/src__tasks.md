# 目录：src/tasks

## 它负责什么

`src/tasks` 是 OpenClaw 内部的“后台任务与任务流状态层”。它不直接实现某个具体 agent、channel 或 plugin 的业务能力，而是为这些运行时提供统一的任务记录、状态迁移、取消、恢复、投递通知、审计和持久化能力。

从当前片段看，这里的核心抽象有两类：`TaskRecord` 和 `TaskFlowRecord`。`TaskRecord` 表示一次具体后台运行，例如 subagent、ACP、CLI 或 cron 发起的异步任务；`TaskFlowRecord` 表示由一个或多个任务组成的更高层流程，可以记录当前步骤、阻塞任务、等待状态、取消请求和最终状态。两者通过 `parentFlowId` 关联，单个可投递任务还可能被自动包装成 one-task flow。

这个目录的职责边界比较清楚：它维护任务事实，不拥有具体执行器实现。具体运行时来自 `src/agents`、`src/acp`、`src/cron`、`src/plugins/runtime`、`src/plugin-sdk` 等；这些调用方通过这里的 API 创建、更新、查询和取消任务。状态写入由 registry 完成，消息投递由懒加载的 delivery runtime 转到外部 outbound 消息层，任务取消则在需要时调用 ACP session manager 或 subagent control 这类控制面能力。

## 直接子目录地图

`src/tasks` 当前是扁平目录，没有直接子目录。文件大致可以按职责分组理解：

`task-registry*` 是任务注册表主线，负责 `TaskRecord` 的生命周期、索引、查询、持久化、审计、维护和进程内状态。

`task-flow-registry*` 是任务流注册表主线，负责 `TaskFlowRecord` 的创建、状态同步、等待/恢复、取消请求、持久化、审计和维护。

`task-executor*` 处在 registry 与外部运行时之间，提供更语义化的任务运行操作，例如创建 queued/running run、记录进度、完成/失败、取消任务或 flow，并包含终态通知策略。

`detached-task-runtime*` 定义“脱离当前同步调用链的任务运行时”接口与注册机制。默认实现会回落到 `task-executor`，plugin 或测试可以注册替代 runtime。

`task-owner-access*`、`task-flow-owner-access*`、`task-status-access*` 是访问控制和面向查询场景的薄层，避免调用方绕过 owner/session 边界直接读写任意任务。

`task-status*`、`task-domain-views*`、`task-registry.summary*` 负责把内部记录整理成状态标题、详情、摘要和 domain view，供 CLI、gateway、status 面板或 plugin runtime 展示。

`task-retention*`、`task-registry.maintenance*`、`task-flow-registry.maintenance*`、`*.audit*` 处理保留期限、丢失任务、可检查状态、重启阻塞、清理和操作员审计。

`*.store*`、`*.paths*` 负责 registry 的存储抽象、SQLite 实现和状态目录路径解析。

测试文件集中在同一目录，覆盖 registry、flow registry、executor、retention、import boundary、owner access 等行为。

## 关键入口

最核心的内部入口是 `src/tasks/task-registry.ts`。它维护进程内 Map 与索引，导出 `createTaskRecord`、`markTaskRunningByRunId`、`recordTaskProgressByRunId`、`finalizeTaskRunByRunId`、`cancelTaskById`、`listTaskRecords`、`getTaskById` 等基础操作。它还负责恢复持久化状态、触发 observer、同步 flow、判断终态并尝试发送任务状态消息。

任务流入口是 `src/tasks/task-flow-registry.ts`。重点函数包括 `createManagedTaskFlow`、`createTaskFlowForTask`、`updateFlowRecordByIdExpectedRevision`、`setFlowWaiting`、`resumeFlow`、`finishFlow`、`failFlow`、`requestFlowCancel`、`syncFlowFromTask`。如果要理解“一个后台任务如何变成可跟踪流程”，这里是主入口。

调用方通常不直接碰 registry，而是使用 `src/tasks/detached-task-runtime.ts` 或 `src/tasks/task-executor.ts`。`detached-task-runtime.ts` 暴露 `createQueuedTaskRun`、`createRunningTaskRun`、`recordTaskRunProgressByRunId`、`finalizeTaskRunByRunId`、`cancelDetachedTaskRunById` 等门面；`task-executor.ts` 则实现这些门面的默认语义，并处理 one-task flow、flow 内任务、blocked flow 重试和取消。

对 plugin/runtime 侧，重要邻近入口在 `src/plugins/runtime/runtime-tasks.ts`、`src/plugins/runtime/runtime-taskflow.ts`、`src/plugin-sdk/agent-harness-task-runtime.ts`、`src/plugin-sdk/codex-native-task-runtime.ts`。它们把 `src/tasks` 的内部能力转换成 plugin SDK 或 harness 可用的接口。

对 CLI/gateway 侧，入口主要是 `src/commands/tasks.ts`、`src/commands/flows.ts`、`src/commands/tasks-json.ts`、`src/gateway/server-methods/tasks.ts`、`src/gateway/server-methods/agent.ts`。这些位置负责把任务查询、取消和 JSON 输出暴露给命令行或控制面。

## 主流程位置

创建任务的主流程通常是：外部运行时调用 `detached-task-runtime.ts` 的 `createQueuedTaskRun` 或 `createRunningTaskRun`，默认转入 `task-executor.ts`，再调用 `runtime-internal.ts` 重新导出的 registry API，最终由 `task-registry.ts` 创建 `TaskRecord`、建立 runId/owner/session/flow 索引并写入 store。

进度更新流程是：运行时用 runId 调用 `recordTaskRunProgressByRunId`，`task-registry.ts` 找到对应任务，追加事件、更新时间和摘要，再按通知策略判断是否需要状态变更投递。投递策略集中在 `task-executor-policy.ts`，实际发送通过 `task-registry-delivery-runtime.ts` 转到 outbound message。

终态流程是：调用 `finalizeTaskRunByRunId`、`completeTaskRunByRunId` 或 `failTaskRunByRunId` 后，registry 把任务标记为 `succeeded`、`failed`、`cancelled`、`lost` 等终态，计算 cleanup 时间，并同步关联 flow。若任务属于 one-task flow，flow 的状态会从 task 推导；若是 managed flow，则由 flow 控制逻辑显式推进。

取消流程分两层。取消单个 task 走 `cancelDetachedTaskRunById` 或 `cancelTaskById`，再根据 runtime 类型调用控制面能力。取消 flow 走 `cancelFlowById` 或 `cancelFlowByIdForOwner`，先在 flow 上记录取消请求，再处理当前阻塞或关联任务。根据当前片段推断，真正终止底层执行依赖 runtime 提供的控制接口，依据是 `task-registry-control.runtime.ts` 只导出 ACP 和 subagent 的控制能力。

维护流程由 gateway 启停和 status/doctor 命令触发。`task-registry.maintenance.ts` 负责识别 lost、retained、restart blocker、inspectable task 等状态，并提供 `startTaskRegistryMaintenance`、`runTaskRegistryMaintenance`、`sweepTaskRegistry`。flow 侧有对应的 `task-flow-registry.maintenance.ts`。

## 推荐阅读顺序

1. 先读 `src/tasks/task-registry.types.ts` 和 `src/tasks/task-flow-registry.types.ts`，建立状态枚举、记录字段、runtime 类型、notify policy 和 flow sync mode 的基本概念。

2. 再读 `src/tasks/detached-task-runtime-contract.ts`、`src/tasks/detached-task-runtime.ts`，理解外部运行时看到的任务生命周期 API，以及默认 runtime 如何落到 executor。

3. 然后读 `src/tasks/task-executor.ts`，把创建、进度、终态、取消、flow 内任务这些操作串起来。这里比 registry 更适合作为主流程入口。

4. 接着读 `src/tasks/task-registry.ts` 和 `src/tasks/task-flow-registry.ts`，重点看状态写入、索引维护、observer、store、flow 同步，不必一开始陷入所有测试和维护分支。

5. 最后按使用场景补读：展示看 `task-status.ts`、`task-domain-views.ts`；权限看 `task-owner-access.ts`、`task-flow-owner-access.ts`；运维看 `task-registry.maintenance.ts`、`task-registry.audit.ts`、`task-flow-registry.audit.ts`；持久化看 `task-registry.store.sqlite.ts`、`task-flow-registry.store.sqlite.ts`。

## 常见误区

不要把 `src/tasks` 理解成“任务执行引擎”。它记录和协调任务生命周期，但具体 agent、ACP、cron、plugin 的执行逻辑在其他目录。这里的 cancel/recover 也更多是通过 runtime/control seam 去请求底层执行器配合。

不要绕过 owner access 直接给用户侧功能暴露 `getTaskById` 或 `listTaskRecords`。面向 owner/session 的查询应优先看 `task-owner-access.ts`、`task-flow-owner-access.ts`、`task-status-access.ts`，否则容易破坏任务隔离。

不要混淆 task 和 flow。task 是一次运行记录，flow 是流程容器；有些 task 会自动创建 one-task flow，但这不代表所有 flow 都只有一个 task，也不代表更新 task 就一定能表达 managed flow 的全部状态。

不要忽略 delivery status 与 notify policy。任务终态不等于已经通知用户；`deliveryStatus`、`notifyPolicy` 和 `task-executor-policy.ts` 共同决定是否自动发送 state change 或 terminal message。

不要把 store 文件当作业务入口。`*.store.ts` 和 `*.store.sqlite.ts` 是持久化适配层，主行为仍在 registry/executor。学习时先看生命周期，再回头看 SQLite 如何保存 snapshot 和 record。
