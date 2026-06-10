# 目录：packages/desktop/src/renderer/pages/cron/ScheduledTasksPage

## 它负责什么

`packages/desktop/src/renderer/pages/cron/ScheduledTasksPage` 是桌面端渲染进程里“计划任务 / Scheduled Tasks”页面的页面级实现目录。它不负责真正的定时调度执行，也不直接访问文件系统或 Node 能力；它主要负责把 cron 任务列表、任务详情、创建/编辑表单、状态标签和 agent 展示信息组织成用户可操作的 React UI，并通过 `ipcBridge.cron`、`systemSettings` 等 IPC 封装与主进程侧能力交互。

从职责上看，这个目录可以理解为 cron 功能的“页面壳层 + 表单层”。列表页展示所有任务，详情页展示单个任务的历史、指令、执行模式、agent、模型、workspace 等信息，弹窗组件统一承担新建和编辑任务的表单逻辑。真正的数据订阅和列表状态维护主要来自邻近目录的 `packages/desktop/src/renderer/pages/cron/useCronJobs.ts`，时间格式化和 schedule 构造来自 `packages/desktop/src/renderer/pages/cron/cronUtils.ts`，执行、创建、更新、删除等持久化操作则通过 `@/common/adapter/ipcBridge` 暴露的 cron IPC 接口完成。

这个目录里的代码也承担了一部分“任务和对话系统的衔接”：任务可以选择 `new_conversation` 或 `existing` 执行模式；详情页的“立即运行”如果返回 `conversation_id`，会等待对话可读取后写入 SWR 缓存，再导航到 `/conversation/:id`；历史区域则使用 `useCronJobConversations(job_id)` 读取该任务关联的对话记录。

## 直接子目录地图

该目录当前没有直接子目录，只有页面组件和少量辅助文件。直接文件可以按角色分成四类：

`index.tsx` 是计划任务列表页入口，负责展示所有任务卡片、空状态、加载态、创建任务按钮、保持唤醒开关，并把任务卡片点击导航到详情页。

`TaskDetailPage.tsx` 是单个任务详情页入口，负责根据路由参数 `job_id` 获取任务、订阅任务更新和执行事件、展示历史对话和配置摘要，并提供编辑、删除、暂停/恢复、立即运行等操作。

`CreateTaskDialog.tsx` 是创建/编辑任务共用弹窗。它包含表单、频率选择、cron 表达式生成、agent 选择、模型和 workspace 等高级配置，并在提交时调用 `ipcBridge.cron.addJob.invoke` 或 `ipcBridge.cron.updateJob.invoke`。

`CronStatusTag.tsx` 和 `jobAgentMeta.ts` 是轻量展示辅助：前者把任务状态映射成 Arco `Tag`，后者根据任务的 `metadata.agent_type`、`metadata.agent_config` 和检测到的 agent 列表解析展示名称与 logo。

## 关键入口

最核心的入口是 `packages/desktop/src/renderer/pages/cron/ScheduledTasksPage/index.tsx`。它导出的默认组件 `ScheduledTasksPage` 是计划任务总览页。组件初始化时通过 `useAllCronJobs()` 获取 `jobs`、`loading`、`pauseJob`、`resumeJob`；通过 `useConversationAgents()` 获取 agent 元数据；通过 `configService.get('system.keepAwake')` 初始化保持唤醒状态，并通过 `systemSettings.setKeepAwake.invoke` 把用户切换同步到系统设置。

任务卡片的主信息由 `ICronJob` 驱动：名称来自 `job.name`，状态来自 `CronStatusTag`，计划描述来自 `formatSchedule(job, t)`，下次运行时间来自 `formatNextRun(job.state.next_run_at_ms)`，agent 展示来自 `getJobAgentMeta(job, cliAgents)`。卡片点击进入 `/scheduled/${job.id}`，开关点击则调用 `pauseJob(job.id)` 或 `resumeJob(job.id)`。

另一个页面入口是 `packages/desktop/src/renderer/pages/cron/ScheduledTasksPage/TaskDetailPage.tsx`。它通过 `useParams<{ job_id: string }>()` 读取路由参数，用 `ipcBridge.cron.getJob.invoke({ job_id })` 拉取任务详情，并用 `repairCronJobTimeZone` 修正旧数据或时区相关信息。页面还订阅 `ipcBridge.cron.onJobUpdated` 和 `ipcBridge.cron.onJobExecuted`，确保任务被编辑或执行后详情自动刷新。

创建和编辑的统一入口是 `CreateTaskDialog`。列表页以无 `editJob` 的方式打开它，表示新建；详情页传入 `editJob={job}`，表示编辑已有任务。这个设计使任务名称、描述、prompt、频率、agent、模型、workspace 等字段的 UI 和提交逻辑集中在一个组件里。

## 主流程位置

列表加载流程在 `index.tsx` 和邻近的 `useCronJobs.ts` 之间完成。`ScheduledTasksPage` 调用 `useAllCronJobs()`，后者内部调用 `ipcBridge.cron.listJobs.invoke()` 拉取全部任务，再通过 `repairCronJobTimeZones` 处理时区字段，最后订阅 `onJobCreated`、`onJobUpdated`、`onJobRemoved` 三类事件来维持列表实时更新。列表页只消费这个 hook 的结果，不自己维护完整任务数组。

新建任务流程集中在 `CreateTaskDialog.tsx`。用户填写表单后，`handleSubmit` 先执行 `form.validate()`，再根据 `frequency`、`time`、`weekday`、`customCronExpr` 计算 `scheduleInfo`，并通过 `createCronSchedule(scheduleExpr, scheduleDesc)` 构造 `ICronJob['schedule']` 形态的数据。随后 `resolveAgentConfig(values.agent)` 将用户选择的 CLI agent 或 preset assistant 转换成后端可识别的 `agent_type` 和 `agent_config`。新建模式下调用 `ipcBridge.cron.addJob.invoke(params)`；编辑模式下调用 `ipcBridge.cron.updateJob.invoke({ job_id, updates })`。

频率到 cron 表达式的转换也在 `CreateTaskDialog.tsx` 内部完成：`manual` 对应空表达式，`hourly` 对应 `0 * * * *`，`daily`、`weekdays`、`weekly` 则根据时间和星期拼出标准表达式，`custom` 直接使用用户输入。展示侧的反向格式化不在本目录，而在 `packages/desktop/src/renderer/pages/cron/cronUtils.ts` 的 `formatSchedule` 和 `formatCronExpr`。

详情页运行流程在 `TaskDetailPage.tsx` 的 `handleRunNow`。它调用 `ipcBridge.cron.runNow.invoke({ job_id: job.id })`，成功后如果拿到 `conversation_id`，会在最多约 15 秒内轮询 `ipcBridge.conversation.get.invoke`，等待对话对象和必要的 workspace 信息可用；随后用 `mutate` 更新 `conversation/${conversation_id}` 的 SWR 缓存，并导航到 `/conversation/${conversation_id}`。这里体现了 cron 任务与会话页面之间的跳转闭环。

删除与启停流程也在详情页和列表页各自实现。列表页通过 `useAllCronJobs` 返回的 `pauseJob`、`resumeJob` 修改 `enabled`；详情页直接调用 `ipcBridge.cron.updateJob.invoke` 修改 `enabled`，删除则调用 `ipcBridge.cron.removeJob.invoke` 后回到 `/scheduled`。

## 推荐阅读顺序

建议先读 `packages/desktop/src/renderer/pages/cron/ScheduledTasksPage/index.tsx`，建立“计划任务总览页如何展示任务、如何进入详情、如何打开新建弹窗”的整体印象。这里的代码最能说明这个目录的用户入口和页面骨架。

第二步读 `packages/desktop/src/renderer/pages/cron/useCronJobs.ts`，虽然它在邻近目录而不在目标目录内，但它是列表数据来源和事件订阅中心。理解 `useAllCronJobs` 之后，再回看列表页会更清楚为什么页面本身不处理 `onJobCreated`、`onJobUpdated`、`onJobRemoved` 的细节。

第三步读 `packages/desktop/src/renderer/pages/cron/ScheduledTasksPage/CreateTaskDialog.tsx`。这个文件较长，但它是业务信息密度最高的地方：频率选择、cron 表达式、agent 类型、preset assistant、ACP/aionrs 模型、workspace、创建和编辑提交都在这里。阅读时可以先抓 `handleSubmit`、`scheduleInfo`、`resolveAgentConfig` 三个核心点，不必一开始陷入每个表单控件。

第四步读 `packages/desktop/src/renderer/pages/cron/ScheduledTasksPage/TaskDetailPage.tsx`，重点看 `fetchJob`、自动刷新订阅、`handleRunNow`、`handleDelete` 和页面下方的历史/配置展示。它解释了单个任务的生命周期操作如何串到对话页面。

最后读 `CronStatusTag.tsx`、`jobAgentMeta.ts` 和 `packages/desktop/src/renderer/pages/cron/cronUtils.ts`。这些文件是展示辅助，适合在理解主流程后补齐状态、agent 名称/logo、schedule 文案格式化等细节。

## 常见误区

第一个误区是把这个目录当成 cron 调度器本身。实际上这里是 renderer 页面层，只负责 UI、表单、导航和 IPC 调用；任务的保存、执行、事件派发都在 IPC 背后的主进程或服务层。看到 `runNow`、`addJob`、`updateJob` 等名字时，要注意它们是 `ipcBridge.cron.*.invoke` 调用，不是本目录直接执行定时任务。

第二个误区是认为“手动任务”没有 schedule。根据当前片段推断，手动任务仍然使用 `schedule.kind === 'cron'`，只是 `expr` 为空；列表页和详情页都用 `job.schedule.kind === 'cron' && !job.schedule.expr` 判断 `isManualOnly`，并在这种情况下隐藏启停开关或显示手动说明。

第三个误区是混淆 `agent_type` 和 `agent_config.backend`。`jobAgentMeta.ts` 的注释已经说明：ACP 任务的 `agent_type` 可能只是 `"acp"`，真实供应商或后端标识在 `agent_config.backend`；而 aionrs 场景中 `agent_config.backend` 可能是 provider id，不应被当成 agent 类型兜底使用。因此展示 agent 名称/logo 时要走 `getJobAgentMeta`，不要直接拼字段。

第四个误区是忽略时区修复。列表 hook 会调用 `repairCronJobTimeZones`，详情页会调用 `repairCronJobTimeZone`，而新建 schedule 会用 `createCronSchedule` 写入当前 IANA 时区。阅读或改动 schedule 相关逻辑时，需要同时关注 `packages/desktop/src/renderer/pages/cron/repairCronJobTimeZone.ts` 和 `cronUtils.ts`，否则容易造成展示时间与实际调度时间不一致。

第五个误区是把创建弹窗只当作“新增表单”。`CreateTaskDialog.tsx` 同时支持编辑模式，是否传入 `editJob` 决定它调用 `addJob` 还是 `updateJob`。编辑模式还会解析已有 cron 表达式、回填 agent、模型、workspace 和高级配置。修改表单字段时，要确认新建和编辑两条路径都能正确初始化、提交和展示。
