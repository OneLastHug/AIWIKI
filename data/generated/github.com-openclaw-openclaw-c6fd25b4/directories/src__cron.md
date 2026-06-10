# 目录：src/cron

## 它负责什么

`src/cron` 是 OpenClaw 内部的定时任务调度与执行子系统。它不是单纯的“cron 表达式解析目录”，而是把任务定义、任务持久化、下一次触发时间计算、运行状态维护、隔离 agent 执行、消息交付、失败通知、运行日志和诊断信息串起来的一组核心代码。

从类型上看，任务的中心模型在 `src/cron/types.ts`：`CronSchedule` 支持 `at`、`every`、`cron` 三类调度；`CronPayload` 主要分为 `systemEvent` 和 `agentTurn`；`CronDelivery` 描述是否公告、发 webhook 或不交付；`CronJobState` 保存 `nextRunAtMs`、`runningAtMs`、`lastRunStatus`、错误、诊断、连续失败次数等运行态。也就是说，这个目录同时管理“什么时候跑”“跑什么”“用哪个会话/agent 跑”“跑完怎么通知”“失败怎么记录”。

它与外围系统的关系也比较强：agent 工具侧通过 `src/agents/tools/cron-tool.ts` 调用 Gateway 方法如 `cron.add`、`cron.list`、`cron.run`；Gateway 侧测试和服务会构造 `CronService`；插件侧通过 `CronServiceContract` 使用计划任务能力；配置侧有 `cron.enabled`、`cron.store`、`cron.retry`、`cron.webhookToken`、`cron.sessionRetention`、`cron.runLog` 等字段。根据当前片段推断，`src/cron` 是“调度内核”，而不是面向用户的命令入口；用户入口主要在 agent tool、Gateway、插件 hook 和命令层。

## 直接子目录地图

`src/cron/service` 是调度服务的内部实现目录。它承接 `CronService` 的状态机和操作拆分，包括任务增删改查、启动停止、timer 重新布防、任务锁、状态保存、分页列表、初始交付策略、任务账本和超时策略等。读这个目录时应把它理解为“scheduler runtime”，负责决定哪些 job due、何时触发、如何更新 store/state，而不是具体运行 agent 的地方。

`src/cron/isolated-agent` 是 agentTurn 任务的隔离执行与交付目录。它处理 cron run 的 session key、会话落盘、技能快照、模型选择、模型预检、运行配置、auth profile、runtime plugin、外部内容、执行器、delivery dispatch、subagent follow-up 等。这里是 cron 与 agent runtime 深度耦合的位置，尤其是 `run.ts`、`run-executor.ts`、`delivery-dispatch.ts`、`session.ts`、`session-key.ts`、`run-session-state.ts`。

根目录下的一批文件是公共模型与横切辅助：`schedule.ts` 负责计算下一次/上一次运行时间；`store.ts` 负责 cron job 配置和状态文件的读取保存；`normalize.ts` 和 `parse.ts` 负责输入规整；`delivery.ts`、`delivery-plan.ts`、`delivery-context.ts`、`delivery-preview.ts` 负责交付计划、目标和预览；`run-log.ts`、`run-diagnostics.ts` 负责运行记录与诊断；`session-target.ts`、`schedule-identity.ts`、`normalize-job-identity.ts` 处理身份、会话和 schedule identity；`active-jobs.ts`、`heartbeat-policy.ts`、`session-reaper.ts`、`retry-hint.ts`、`stagger.ts` 则覆盖并发、心跳、清理、重试提示和错峰调度等策略。

## 关键入口

最重要的类入口是 `src/cron/service.ts` 的 `CronService`。它实现 `CronServiceContract`，公开 `start`、`stop`、`status`、`list`、`listPage`、`add`、`update`、`remove`、`run`、`enqueueRun`、`readJob`、`wake` 等方法。这个类本身很薄，主要把调用转发给 `src/cron/service/ops.ts`，状态由 `src/cron/service/state.ts` 创建和持有。

agent 执行入口是 `src/cron/isolated-agent.ts`，它重新导出 `runCronIsolatedAgentTurn`，实际实现在 `src/cron/isolated-agent/run.ts`。当任务 payload 是 `agentTurn`，服务层会把任务交给这个执行入口，后者再处理 session、模型、上下文、工具、执行结果、诊断和最终 delivery。

调度时间入口是 `src/cron/schedule.ts` 的 `computeNextRunAtMs` 和 `computePreviousRunAtMs`。它使用 `croner` 处理 cron 表达式，并兼容 `at`、`every` 等 schedule 形态。`src/cron/service/jobs.ts` 还在此基础上叠加了错峰、错误 backoff、stuck run 修复、one-shot 任务禁用等服务级策略。

持久化入口是 `src/cron/store.ts` 的 `resolveCronStorePath`、`loadCronStore`、`saveCronStore` 以及同步读取变体。根据当前片段，cron 默认会解析到配置目录下的 `cron/jobs.json`，并把运行态拆到相邻 state 文件，以区分用户配置和运行状态。

## 主流程位置

添加或更新任务的大致路径是：外部调用方发起 `cron.add` 或 `cron.update`，agent 工具侧会先使用 `src/cron/normalize.ts` 和 delivery 上下文逻辑规整 payload、schedule、sessionTarget、delivery 等字段；Gateway/服务侧进入 `CronService.add` 或 `CronService.update`；随后 `src/cron/service/ops.ts` 调用 `src/cron/service/jobs.ts` 做任务规范化、id 处理、下一次运行时间计算和 store 保存。

自动触发的主流程集中在 `src/cron/service/ops.ts`、`src/cron/service/timer.ts`、`src/cron/service/jobs.ts`。服务启动后加载 store，计算 due jobs 和 next timer；timer 到期或被 wake 后，服务判断任务是否 enabled、是否 due、是否被锁或正在运行，然后进入 run/enqueue 路径。`service/locked.ts` 和 `active-jobs.ts` 这类文件用于避免重复运行和并发冲突。

真正执行任务时，`systemEvent` 类型更偏向把事件放进主 agent/心跳通路；`agentTurn` 类型会进入 `runCronIsolatedAgentTurn`。在 `src/cron/isolated-agent/run.ts` 中，流程大致是解析 agent/config/session，做模型和 auth/profile 预检，创建或恢复 cron session，构造执行器，运行 embedded agent，收集 token usage、模型/provider、诊断、错误分类，再根据 `delivery-plan` 和 channel output policy 决定是否公告、webhook 或保持静默。

交付与失败通知分两层：`src/cron/isolated-agent/delivery-dispatch.ts` 更贴近一次 agent run 的结果投递；`src/cron/delivery.ts` 提供严格公告发送和失败通知发送，底层走 channels durable message。`src/cron/delivery-plan.ts` 则负责把 job 配置、失败目的地和默认目标解析成可执行的 delivery plan。

## 推荐阅读顺序

第一步读 `src/cron/types.ts`，先建立 `CronJob`、`CronSchedule`、`CronPayload`、`CronDelivery`、`CronJobState` 的数据模型。这个文件决定后面所有流程的词汇表。

第二步读 `src/cron/service.ts` 和 `src/cron/service/state.ts`，理解 `CronService` 的公开边界、依赖注入和内部状态结构。然后跳到 `src/cron/service/ops.ts`，把服务启动、列表、添加、更新、删除、运行、wake 的入口串起来。

第三步读 `src/cron/service/jobs.ts`、`src/cron/schedule.ts`、`src/cron/store.ts`。这一组解释“任务如何变成下一次运行时间”“状态如何被修复或 backoff”“配置和运行态如何落盘”。

第四步读 `src/cron/isolated-agent/run.ts`，只看主函数和它调用的相邻模块名，不要一开始钻进每个 runtime 文件。随后按需要补读 `run-executor.ts`、`run-session-state.ts`、`session-key.ts`、`model-selection.ts`、`delivery-dispatch.ts`。

第五步再看外围入口：`src/agents/tools/cron-tool.ts` 说明模型/用户如何发起 cron 操作；`src/plugins/host-hook-scheduled-turns.ts` 说明插件如何借用 cron；Gateway 相关测试如 `src/gateway/server-cron.test.ts` 可作为行为样例。

## 常见误区

不要把 `src/cron/service.ts` 当成完整实现。它只是薄 facade，真正复杂度在 `src/cron/service/ops.ts`、`src/cron/service/jobs.ts`、`src/cron/service/timer.ts` 和 `src/cron/service/store.ts` 周围。

不要把 `cron` schedule 与任务系统等同。`CronSchedule` 还有 `at` 和 `every`，而 `cron` 表达式只是其中一种；另外 `staggerMs`、error backoff、one-shot 禁用、stuck run 修复都会影响实际下一次运行。

不要认为 `isolated-agent` 只表示“独立会话”。从代码看，它还承载模型选择、auth profile、runtime plugin、技能快照、外部内容、delivery trace、subagent follow-up 等执行上下文。它是 cron agentTurn 的运行管线，不只是 session key 工具箱。

不要把 delivery 理解成简单发消息。`delivery.mode`、`failureDestination`、`bestEffort`、显式 channel/to/account/thread、last target fallback、message tool 输出策略都会影响最终是否投递、投到哪里、失败是否另行通知。

不要直接改 store 里的运行态字段来表达配置意图。根据 `src/cron/store.ts` 的拆分逻辑，配置 job 和 runtime state 有分离趋势；`state`、`updatedAtMs`、`lastRunStatus`、`nextRunAtMs` 等字段属于调度运行结果，应通过服务流程维护。
