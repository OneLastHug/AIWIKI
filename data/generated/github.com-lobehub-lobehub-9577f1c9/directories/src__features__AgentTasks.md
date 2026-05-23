# 目录：src/features/AgentTasks

## 它负责什么

`src/features/AgentTasks` 是任务工作区的前端功能目录，负责把“Agent 任务”从列表、看板、创建、详情到执行反馈串成一套 SPA 页面体验。它不直接定义后端任务模型，也不直接实现 TRPC router；它主要消费 `src/store/task` 和 `src/services/task.ts` 暴露的数据与动作，并把这些能力组织成可交互的 React UI。

从当前片段看，这个目录覆盖三类核心场景：第一是 `/tasks` 这类全局任务列表页，支持列表视图、看板视图、分组、隐藏已完成任务、快速创建；第二是任务详情页，展示任务标题、指令、负责人、模型配置、状态、优先级、计划执行、子任务、产物和活动流；第三是任务相关的共享 UI，比如任务卡片、状态标签、负责人头像、面包屑、详情路径构造等。

它位于 `src/features` 下，符合仓库“route thin、feature heavy”的约定：路由文件只负责取参数和挂载页面，主要业务 UI 放在这里。

## 直接子目录地图

`AgentTaskList` 是任务列表页区域。它包含 `AgentTasksPage.tsx` 入口，以及 `TaskList.tsx`、`KanbanBoard.tsx`、`KanbanColumn.tsx`、`CreateTaskInlineEntry.tsx`、`TasksGroupConfig.tsx` 等列表和看板相关组件。这里关心的是任务集合如何加载、过滤、分组、排序、展示和切换视图。

`AgentTaskDetail` 是任务详情页区域。入口是 `TaskDetailPage.tsx`，内部拆成标题、执行按钮、属性面板、指令、子任务、产物、活动流、评论、关联会话抽屉等模块。其下还有 `TopicChatDrawer`，用于从任务活动或话题进入聊天上下文；`scheduler` 则承载计划任务表单、cron 配置和辅助函数。

`CreateTaskModal` 是创建任务弹窗。`index.tsx` 使用 `@lobehub/ui/base-ui` 的 `createModal` 包装弹窗，`CreateTaskContent.tsx` 负责创建表单、编辑器输入、负责人选择、优先级等交互。

`features` 是跨列表和详情复用的小组件集合，例如 `AgentTaskItem.tsx`、`AgentTaskCardList.tsx`、`AssigneeAgentSelector.tsx`、`AssigneeAvatar.tsx`、`TaskStatusTag.tsx`、`TaskPriorityTag.tsx`、`TaskTriggerTag.tsx`。这里的“features”不是新的业务域，而是 AgentTasks 内部复用件。

`shared` 放共享工具和样式，例如 `Breadcrumb.tsx`、`taskDetailPath.ts`、`useAgentDisplayMeta.ts`、`isInboxAgent.ts`、`style.ts`。这些文件主要解决导航路径、展示元信息和局部样式复用。

## 关键入口

最上层导出在 `src/features/AgentTasks/index.tsx`，目前只导出 `TaskDetailPage` 和 `AgentTasksPage`，供路由层使用。

列表页入口是 `src/features/AgentTasks/AgentTaskList/AgentTasksPage.tsx`。它调用 `useTaskStore(taskListSelectors.viewMode)` 判断当前视图，调用 `useFetchTaskList({ allAgents: true })` 拉取任务列表，并根据状态渲染 `EmptyState`、`KanbanBoard` 或 `TaskList`。创建任务入口也在这里：点击加号或 inline entry 后会打开 `createTaskModal`，创建成功后通过 `taskDetailPath` 跳转到详情页。

详情页入口是 `src/features/AgentTasks/AgentTaskDetail/TaskDetailPage.tsx`。它接收 `taskId`，进入页面后调用 `setActiveTaskId(taskId)` 设置当前任务，再通过 `useFetchTaskDetail(taskId)` 拉取详情。页面主体由 `TaskDetailTitleInput`、`TaskDetailAssignee`、`TaskModelConfig`、`TaskDetailRunPauseAction`、`TaskProperties`、`TaskInstruction`、`TaskSubtasks`、`TaskArtifacts`、`TaskActivities` 组成。

布局入口是 `src/features/AgentTasks/TaskWorkspaceLayout.tsx`。它通过 `Outlet` 承载任务页面内容，并在非移动端右侧挂载 `AgentTaskManager`，因此它是任务工作区和右侧任务管理面板之间的连接点。

路由元信息在 `src/features/AgentTasks/routeMeta.ts`，其中 `tasksRouteMeta` 对应任务列表，`taskRouteMeta` 会根据 `params.taskId` 从 `useTaskStore` 取详情名称，用于动态标题。

## 主流程位置

任务列表主流程从路由进入。`src/routes/(main)/tasks/index.tsx` 直接导出 `AgentTasksPage`；桌面路由配置在 `src/spa/router/desktopRouter.config.tsx` 和 `src/spa/router/desktopRouter.config.desktop.tsx` 中引用 `tasksRouteMeta` 和相关页面。进入 `AgentTasksPage` 后，数据流主要是 `useTaskStore` → `useFetchTaskList` → `taskService.list` → `lambdaClient.task.list.query`。列表视图由 `TaskList.tsx` 负责分组、排序和折叠展示；看板视图由 `KanbanBoard.tsx` 负责列分组、拖拽和乐观移动。

任务详情主流程从 `src/routes/(main)/task/[taskId]/index.tsx` 或 `src/routes/(main)/agent/task/[taskId]/index.tsx` 进入。这两个路由都会读取 `useParams` 中的 `taskId`，然后渲染 `TaskDetailPage`。区别是 agent 内嵌详情会传入 `showTaskAgentPanelToggle={false}`，避免重复显示右侧面板开关。详情数据流是 `TaskDetailPage` → `useFetchTaskDetail` → `taskService.getDetail` → `lambdaClient.task.detail.query`。详情页内的标题、指令、属性、负责人、子任务、活动等组件再通过 `taskDetailSelectors` 读取当前 active task。

创建任务主流程分为弹窗创建和 inline 创建。弹窗由 `CreateTaskModal/index.tsx` 暴露 `createTaskModal`，内容在 `CreateTaskContent.tsx`；列表中的 `CreateTaskInlineEntry.tsx` 则提供更轻量的行内创建入口。创建动作最终落到 `useTaskStore((s) => s.createTask)`，再通过 `taskService.create` 调用 `lambdaClient.task.create.mutate`。

执行、暂停、评论、子任务和产物等动作分散在详情页组件中，但服务层集中在 `src/services/task.ts`。例如 `run`、`runReadySubtasks`、`updateStatus`、`addComment`、`reorderSubtasks`、`pinDocument` 等都在这里定义。根据当前片段推断，`AgentTasks` 本身主要负责调用和刷新，不承担任务执行的业务编排。

## 推荐阅读顺序

建议先读 `src/features/AgentTasks/index.tsx`，确认对外暴露的页面入口。然后读 `src/features/AgentTasks/TaskWorkspaceLayout.tsx`，理解任务页面和右侧 `AgentTaskManager` 的布局关系。

第二步读列表链路：`src/features/AgentTasks/AgentTaskList/AgentTasksPage.tsx`、`src/features/AgentTasks/AgentTaskList/TaskList.tsx`、`src/features/AgentTasks/AgentTaskList/KanbanBoard.tsx`。这样可以先建立“任务集合如何出现”的地图。

第三步读详情链路：`src/features/AgentTasks/AgentTaskDetail/TaskDetailPage.tsx`，再按页面结构看 `TaskProperties.tsx`、`TaskInstruction.tsx`、`TaskSubtasks.tsx`、`TaskArtifacts.tsx`、`TaskActivities.tsx`。这些文件对应用户在详情页看到的主要区块。

第四步读共享与服务边界：`src/features/AgentTasks/shared/taskDetailPath.ts`、`src/features/AgentTasks/shared/Breadcrumb.tsx`、`src/services/task.ts`、`src/store/task/store.ts`、`src/store/task/slices/list/action.ts`、`src/store/task/slices/detail/action.ts`。这样能把 UI、store、service 的职责分开。

最后再看 `CreateTaskModal` 和 `features` 下的小组件，因为它们多数是主流程中的局部 UI，不适合作为第一入口。

## 常见误区

不要把 `src/features/AgentTasks/features` 理解成仓库级 feature 目录。它只是 `AgentTasks` 内部的复用组件层，真正的业务域仍是 `AgentTasks`。

不要从 `src/routes` 开始逐文件追 UI。这里的路由文件很薄，主要只是导入 `TaskDetailPage` 或 `AgentTasksPage`；实际页面结构在 `src/features/AgentTasks`。

不要以为 `AgentTasks` 直接处理后端执行逻辑。任务查询、创建、更新、运行、评论、子任务、产物等 API 入口集中在 `src/services/task.ts`，状态聚合在 `src/store/task`。`AgentTasks` 更像前端任务工作台。

不要只看列表页而忽略 `TaskWorkspaceLayout.tsx`。在桌面端，任务页面经常和右侧 `AgentTaskManager` 同屏出现，这会影响导航、面板开关和页面宽度判断。

不要忽略双路由详情入口。`/task/:taskId` 和 `/agent/:aid/task/:taskId` 都会进入 `TaskDetailPage`，但传参略有不同；如果改详情页顶部按钮或右侧面板开关，需要同时考虑这两种上下文。

不要把 `scheduler` 当成独立任务系统。根据当前片段，它只是详情页中计划执行配置的 UI 和 cron 辅助逻辑，真正保存仍通过任务详情配置和 `taskService.update` 等服务动作完成。
