# 子系统：src/cron/service

## 解决什么问题

`src/cron/service` 是 OpenClaw 定时任务服务的运行核心，承接 `src/cron/service.ts` 暴露的 `CronService` 类，把“任务配置”变成“可持久化、可调度、可执行、可观测”的运行时行为。它解决的不是 cron 表达式解析本身，而是围绕 cron job 生命周期的一整套服务问题：加载和修复持久化任务、计算下一次运行时间、启动后补跑遗漏任务、避免重复并发执行、执行主会话或隔离 agent 任务、记录任务状态、处理超时和失败重试、发出事件、维护定时器。

从代码形态看，`src/cron/service.ts` 是薄门面：`start`、`stop`、`list`、`add`、`update`、`remove`、`run`、`wake` 等方法几乎都转交给 `src/cron/service/ops.ts`。因此学习这个目录时，应把它理解为 `CronService` 的实现包，而不是独立 API 层。

## 相关目录和文件

`src/cron/service/state.ts` 定义 `CronServiceDeps`、`CronServiceState` 和事件类型。它是服务的依赖注入边界，包含日志、store 路径、当前时间、cron 配置、默认 agent、heartbeat、主会话投递、隔离 agent 执行、失败通知、事件回调等。

`src/cron/service/ops.ts` 是操作编排层，负责 start/stop/status/list/add/update/remove/manual run/wake 等对外动作。它不直接承载全部执行细节，而是调用 `jobs.ts`、`store.ts`、`timer.ts`。

`src/cron/service/jobs.ts` 是任务规则层，负责创建任务、应用 patch、校验任务规格、计算 `nextRunAtMs`、处理 `cron`/`every`/`at` 调度、stagger、错误 backoff、是否 due、下一次唤醒时间等。

`src/cron/service/store.ts` 是持久化加载层，调用上层 `src/cron/store.ts` 读写文件，并在加载时做运行时兼容修复、非法任务跳过、缺失字段默认值、`nextRunAtMs` 失效处理。

`src/cron/service/timer.ts` 是执行与定时器层，负责 arm timer、timer tick、补跑 missed jobs、执行 job core、超时 watchdog、任务账本、失败告警、状态回写和事件发射。

`src/cron/service/locked.ts` 提供串行化保护，避免服务内部操作交错修改同一个内存 store。`timeout-policy.ts` 定义 job 超时策略。`initial-delivery.ts` 处理创建任务时的初始 delivery 推断。`list-page-types.ts` 是分页列表的类型定义。`task-ledger.ts` 提供 cron 任务账本进度文案常量。邻近的 `src/cron/schedule.ts`、`src/cron/store.ts`、`src/cron/delivery-plan.ts`、`src/cron/session-reaper.ts`、`src/cron/types.ts` 是这个子系统的主要支撑文件。

## 核心对象

`CronService` 是外部入口，实现 `CronServiceContract`。它内部只持有一个 `CronServiceState`，所有行为通过 `ops` 完成。

`CronServiceState` 是运行时上下文，包含 `deps`、内存中的 `store`、当前 `timer`、串行操作 promise `op`、若干 warning 去重集合、保留的非法持久化配置行、store 加载时间和文件 mtime。这个对象贯穿整个目录，所有核心函数都以它作为第一参数。

`CronServiceDeps` 是服务与外部系统的契约。最关键的依赖包括 `enqueueSystemEvent`、`requestHeartbeat`、`runHeartbeatOnce`、`runIsolatedAgentJob`、`cleanupTimedOutAgentRun`、`sendCronFailureAlert` 和 `onEvent`。这说明 cron service 本身不拥有 channel、agent runner、heartbeat 或通知实现，只编排它们。

`CronJob` 是持久化和执行的核心数据结构，来自 `src/cron/types.ts`。service 关注它的 `schedule`、`payload`、`sessionTarget`、`delivery`、`failureAlert`、`enabled`、`state` 等字段。

## 运行流程

启动时，`CronService.start()` 调到 `ops.start`。流程先检查 `cronEnabled`，再通过 `locked` 串行进入加载阶段。`ensureLoaded` 从 `storePath` 读取任务，规范化旧字段，跳过非法持久化任务，必要时给缺失的 `sessionTarget` 做内存默认值。启动阶段还会检查上次进程中断时留下的 `runningAtMs`，把这些任务标记为失败，避免它们永久停在 running 状态。

随后服务调用 `runMissedJobs` 处理重启期间错过的任务。根据当前片段推断，agentTurn 类型的 missed jobs 会被延后，以避免 gateway 启动时立刻触发模型和工具初始化压力；依据是 `ops.start` 调用 `runMissedJobs` 时传入 `deferAgentTurnJobs: true`，且 `state.ts` 中有 `startupDeferredMissedAgentJobDelayMs` 配置。

常规运行时，`armTimer` 根据 `nextWakeAtMs` 设置下一次 `setTimeout`，最大单次延迟被限制在 `timer.ts` 中的 `MAX_TIMER_DELAY_MS`。timer tick 时会重新加载 store，收集 runnable jobs，受 `resolveCronMaxConcurrentRuns` 限制执行。执行前会标记 active job 和 task ledger，执行后通过 `applyJobResult` 写回 `lastStatus`、`lastError`、`lastDurationMs`、delivery 状态、下一次运行时间等，并持久化。

手动运行走 `ops.run` 或 `ops.enqueueRun`。它会先做 preflight：加载 store、找到 job、判断 due/force、检查是否 already-running、验证任务规格。真正执行仍复用 `executeJobCoreWithTimeout`，只是结果需要合并回重新加载后的 store，避免手动运行期间其他改动被覆盖。

## 上下游依赖

上游入口主要是 `src/cron/service.ts` 和实现 `CronServiceContract` 的调用方。服务对外提供任务管理、状态查询、分页列表、手动执行和 wake 能力。

调度计算依赖 `src/cron/schedule.ts` 的 `computeNextRunAtMs`、`computePreviousRunAtMs`，以及 `src/cron/stagger.ts` 的 top-of-hour stagger 逻辑。任务输入规范化依赖 `src/cron/normalize.ts`、`src/cron/service/normalize.ts`、`src/cron/normalize-job-identity.ts`。

持久化依赖 `src/cron/store.ts`，其中配置形态和运行态会被拆分/合并；`service/store.ts` 负责在服务加载时保护运行安全，同时尽量不删除未知但需要保留的配置行。

执行下游分两类：`systemEvent` 通常进入主会话，通过 `enqueueSystemEvent` 和 heartbeat 推进；`agentTurn` 通常通过 `runIsolatedAgentJob` 进入隔离 agent。delivery 和失败通知依赖 `src/cron/delivery-plan.ts`、`sendCronFailureAlert`，session 清理依赖 `src/cron/session-reaper.ts`，任务运行账本依赖 `src/tasks/detached-task-runtime.ts`。

## 修改时最容易踩的坑

第一，读操作不能意外推进任务。`ops.ensureLoadedForRead` 明确使用 `skipRecompute: true` 后再调用 maintenance 版本 recompute，避免 list/status 把 past-due job 的 `nextRunAtMs` 推走却没有执行。

第二，持久化 store 不是简单 JSON 读写。`store.ts` 会保留非法但不应被常规写入删除的 config jobs，还会对旧字段、缺失 `enabled`、缺失 `sessionTarget` 做运行时兼容处理。改这里要同时理解 `src/cron/store.ts` 的配置态/运行态拆分。

第三，`nextRunAtMs` 的计算有多层保护：cron stagger、error backoff、stuck run、one-shot `at` 禁用、`every` anchor、最小 refire gap。不要只改 `computeJobNextRunAtMs` 而忽略 `applyJobResult` 和 timer tick 的下界保护。

第四，隔离 agent 超时不是单一 timeout。`timer.ts` 区分 runner 启动前、执行前、执行中，并通过 phase watchdog 生成更有诊断价值的错误。修改 agent 执行流程时要维护 `onExecutionStarted`、`onExecutionPhase` 语义。

第五，服务并发依赖 `locked(state, ...)` 和 active job 标记。新增操作若绕过锁或忘记 `armTimer`/`persist`，很容易出现重复运行、状态丢失或 timer 不重置。

## 推荐阅读顺序

先读 `src/cron/service.ts`，确认外部 API 很薄。然后读 `src/cron/service/state.ts`，掌握依赖注入边界和服务状态。第三读 `src/cron/service/ops.ts` 的 `start`、`add`、`update`、`run`，理解生命周期编排。第四读 `src/cron/service/store.ts`，弄清持久化加载和兼容策略。第五读 `src/cron/service/jobs.ts`，重点看创建、patch、`nextRunAtMs`、due 判断和 backoff。最后读 `src/cron/service/timer.ts`，把定时器、missed jobs、执行、超时、结果回写和事件串起来。测试可按主题补读：`src/cron/service.restart-catchup.test.ts`、`src/cron/service.prevents-duplicate-timers.test.ts`、`src/cron/service/timer.test.ts`、`src/cron/service/store.test.ts`。
