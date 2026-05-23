# 目录：src/features/AgentTasks/AgentTaskDetail

## 它负责什么

`src/features/AgentTasks/AgentTaskDetail` 是 Agent Tasks 功能里的“任务详情页”实现目录。它不负责路由注册，也不直接定义后端接口；它的主要职责是把某个 `taskId` 对应的任务详情数据组织成一个可编辑、可运行、可查看活动记录的页面。

从当前代码片段看，这个目录围绕 `TaskDetailPage` 展开：页面进入时会通过 `useTaskStore` 设置 `activeTaskId`，调用 `useFetchTaskDetail(taskId)` 拉取详情，然后根据任务是否存在、是否初次加载，分别渲染 404、加载态或完整详情页。完整详情页包含任务标题、负责人、模型配置、运行/暂停按钮、状态/优先级/触发配置、任务说明、子任务树、产物列表、活动流，以及用于查看某次 topic 会话的右侧抽屉。

它更像一个“详情页 UI 编排层”：业务状态主要来自 `src/store/task` 的 selectors 和 actions，接口能力主要经由 `src/services/task` 或 store action 间接触发；本目录负责把这些能力挂到具体控件上，并维持详情页内的交互体验。

## 直接子目录地图

当前目录只有两个直接子目录。

`TopicChatDrawer/` 负责任务活动 topic 的会话抽屉。它把任务运行中的某个 topic 映射为 `ConversationContext`，接入 `ChatList`、`ConversationProvider`、`MessageItem` 等会话组件，同时提供复制 topic id、复制 operation id、分享入口和反馈输入。它既可从 `TaskDetailPage` 内部打开，也可在其他入口如 `src/features/DailyBrief/index.tsx` 中挂载，因此内部有“抽屉在详情页外打开时补水任务详情”的逻辑。

`scheduler/` 负责定时/周期触发配置的表单与展示辅助逻辑。`SchedulerForm.tsx` 处理 cron 模式下的 hourly、daily、weekly、timezone、maxExecutions 等输入；`CronConfig.ts` 定义 cron 配置的解析、构造和选项；`helpers.ts` 提供触发摘要、时区名称、下一次触发时间、heartbeat 下一次执行时间等格式化与计算函数。这个子目录是 `TaskScheduleConfig.tsx` 的底层配置工具区，同时也被邻近的 `TaskTriggerTag` 复用展示辅助能力。

除这两个子目录外，根层是一组详情页组件文件，并配有少量测试，如 `TaskParentBar.test.tsx`、`TaskSubtasks.test.tsx` 和 `TopicChatDrawer/index.test.tsx`。

## 关键入口

最核心入口是 `src/features/AgentTasks/AgentTaskDetail/index.tsx`，它只导出 `TaskDetailPage`。再往上一层，`src/features/AgentTasks/index.tsx` 会继续导出该页面，使 route 侧可以通过 `@/features/AgentTasks` 引入。

页面实现入口是 `src/features/AgentTasks/AgentTaskDetail/TaskDetailPage.tsx`。它接收 `taskId` 和可选的 `showTaskAgentPanelToggle`，负责设置当前 active task、拉取详情、处理初始 loading 与 not found，并装配详情页主体。

路由入口不在本目录内，而在 `src/routes/(main)/task/[taskId]/index.tsx` 和 `src/routes/(main)/agent/task/[taskId]/index.tsx`。前者渲染普通任务详情，后者渲染 agent 视角任务详情并传入 `showTaskAgentPanelToggle={false}`。根据当前片段推断，桌面端路由注册还会经过 `src/spa/router/desktopRouter.config.desktop.tsx`；搜索结果只显示了该文件中的 `agent/task/[taskId]` 引用，普通 `/task/[taskId]` 是否在其他 router config 中注册，需要继续查看完整路由配置才能确认。

## 主流程位置

详情页主流程集中在 `TaskDetailPage.tsx`。进入页面后，`useEffect` 调用 `setActiveTaskId(taskId)`，卸载时清空 active task。随后 `useFetchTaskDetail(taskId)` 触发数据加载，`hasTaskDetail` 从 `taskDetailMap` 判断本地是否已有详情。页面避免在已有缓存详情时因为短暂 revalidation 错误直接切到 404，这一点由 `isInitialLoading` 和 `isNotFound` 的判断共同完成。

主体信息编辑流分散在几个小组件里：`TaskDetailTitleInput.tsx` 编辑任务标题，`TaskInstruction.tsx` 编辑任务说明，`TaskModelConfig.tsx` 编辑模型配置，`TaskDetailAssignee.tsx` 管理负责人，`TaskProperties.tsx` 组合状态、优先级和触发配置。它们大多通过 `taskDetailSelectors.activeTask*` 读取当前任务，再调用 `updateTask`、`updateTaskModelConfig`、`updateTaskStatus`、`setAutomationMode`、`updateSchedule` 等 store action 写回。

执行控制流主要在 `TaskDetailRunPauseAction.tsx` 和 `TaskSubtasks.tsx`。前者根据 `canRunActiveTask`、`canPauseActiveTask`、任务状态、自动化模式、周期配置等决定运行或暂停按钮行为；后者展示子任务树，并提供“创建子任务”“右键菜单操作”“运行可运行子任务”等能力。`TaskSubtasks.tsx` 在运行全部子任务前会调用 `taskService.previewSubtaskLayers(taskId)` 获取执行层预览，再通过 `RunSubtasksPreview.tsx` 展示确认内容，最后调用 `runReadySubtasks`。

活动与产物流分别在 `TaskActivities.tsx` 和 `TaskArtifacts.tsx`。`TaskActivities.tsx` 从 `taskActivitySelectors.activeTaskActivities` 读取活动记录，并可触发 `internal_refreshTaskDetail`；活动中的 topic 可通过 `TopicCard.tsx` 打开 `TopicChatDrawer`。`TaskArtifacts.tsx` 读取 `activeTaskWorkspace`，展示任务产物，并提供如 `unpinDocument` 这类文档关联操作。页面底部固定挂载 `DocumentPreviewModal`，说明产物预览弹窗并不只由单个列表项内部维护。

## 推荐阅读顺序

建议先读 `src/features/AgentTasks/AgentTaskDetail/index.tsx` 和 `TaskDetailPage.tsx`，确认外部入口、页面生命周期、整体布局和主要子组件顺序。

第二步读 `TaskProperties.tsx`、`TaskDetailRunPauseAction.tsx`、`TaskInstruction.tsx`、`TaskDetailTitleInput.tsx`、`TaskModelConfig.tsx`、`TaskDetailAssignee.tsx`，这些文件能帮助理解“任务详情基础字段如何读写”。

第三步读 `TaskSubtasks.tsx` 和 `RunSubtasksPreview.tsx`，这是详情页里逻辑最重的一块，涉及树形结构、跳转、右键菜单、批量运行前预览和子任务创建。

第四步读 `TaskActivities.tsx`、`TopicCard.tsx`、`TopicChatDrawer/index.tsx`、`TopicChatDrawer/FeedbackInput.tsx`，理解任务执行记录如何转入会话查看，以及用户反馈如何回流到任务。

第五步读 `TaskScheduleConfig.tsx` 和 `scheduler/`，把自动化模式、heartbeat、cron schedule、timezone、maxExecutions 的配置关系串起来。最后再看测试文件，尤其是 `TaskSubtasks.test.tsx`、`TaskParentBar.test.tsx`、`TopicChatDrawer/index.test.tsx`，它们能补充边界行为。

## 常见误区

不要把这个目录理解成 Agent Tasks 的完整领域实现。它只是详情页 feature 层，列表页、共享组件、store、service、后端路由都在其他目录。比如上下文菜单、状态标签、负责人选择器等来自 `src/features/AgentTasks/features` 或 `shared`，不是详情页私有能力。

不要在 route 文件里寻找详情页业务逻辑。当前路由文件只读取 URL 参数并渲染 `TaskDetailPage`；真正的详情页装配在本目录，状态读写在 `src/store/task`。

不要认为 `TopicChatDrawer` 只服务当前详情页。它也被 `DailyBrief` 使用，所以它内部需要在缺少详情上下文时自行 `useFetchTaskDetail`。这解释了为什么抽屉组件里既有会话上下文，又有任务详情补水逻辑。

不要把 `scheduler/` 当作后端调度器。它处理的是前端 cron 表单、展示摘要和下一次触发时间推算；真实调度执行规则仍应到 task store、service 和服务端相关实现中继续追踪。

不要逐个叶子组件孤立阅读。这个目录的关键不是每个小组件的 UI 细节，而是 `TaskDetailPage` 如何把 active task、store selectors、运行控制、子任务、活动 topic 和产物预览组织成一个连续的详情页工作流。
