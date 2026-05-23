# 目录：src/features/AgentTasks/features

## 它负责什么

`src/features/AgentTasks/features` 是 `AgentTasks` 任务功能域里的“列表展示组件层”。它不承担任务工作区的路由布局，也不直接表示任务详情页或创建弹窗，而是集中放置任务列表页会复用的 UI 单元、展示格式化逻辑和局部交互辅助。

需要先说明一个路径差异：按当前仓库片段读取，用户给出的 `src/features/AgentTasks/features` 在仓库根目录下未直接出现；实际可读到的同名实现位于 `project/lobehub/src/features/AgentTasks/features`。以下内容根据该实际目录及其邻近入口推断，依据包括 `project/lobehub/src/features/AgentTasks/index.tsx`、`project/lobehub/src/features/AgentTasks/TaskWorkspaceLayout.tsx`、`project/lobehub/src/features/AgentTasks/features/index.ts` 和该目录文件结构。

从职责边界看，这个目录更像 `AgentTaskList` 的组件工具箱：`AgentTaskCardList` 负责把任务集合组织成卡片列表，`AgentTaskItem` 负责单个任务条目的主要展示，若干 `Task*Tag`、`TaskStatusIcon`、`AssigneeAvatar`、`TaskLatestActivity` 等组件负责把任务的状态、优先级、触发方式、子任务进度、负责人、最近活动等字段转换成可读 UI。这里还包含 `formatTaskItemDate`、`taskCardListDisplay` 这类纯展示辅助逻辑，以及 `useTaskItemContextMenu`、`menuExtra` 这类列表项局部菜单能力。

## 直接子目录地图

这个目录的直接子目录很少，当前只看到一个：

- `src/features/AgentTasks/features/icons`：优先级图标集合，包含 `PriorityHighIcon`、`PriorityLowIcon`、`PriorityMediumIcon`、`PriorityNoneIcon`、`PriorityUrgentIcon`。这些图标通过 `features/index.ts` 对外导出，主要服务 `TaskPriorityTag` 或任务条目里的优先级展示。

目录根层则是主要组件和展示辅助文件，按角色可以分成几组：

- 列表主体：`AgentTaskCardList.tsx`、`AgentTaskItem.tsx`。
- 列表头和条目扩展：`TaskListHeader.tsx`、`TaskLatestActivity.tsx`、`menuExtra.tsx`、`useTaskItemContextMenu.tsx`。
- 字段展示组件：`TaskPriorityTag.tsx`、`TaskStatusTag.tsx`、`TaskStatusIcon.tsx`、`TaskSubtaskProgressTag.tsx`、`TaskTriggerTag.tsx`、`AssigneeAvatar.tsx`、`AssigneeAgentSelector.tsx`。
- 展示逻辑：`formatTaskItemDate.ts`、`taskCardListDisplay.ts`。
- 测试：`AgentTaskItem.test.tsx`、`TaskSubtaskProgressTag.test.tsx`、`formatTaskItemDate.test.ts`、`taskCardListDisplay.test.ts`。

## 关键入口

这个目录自己的聚合入口是 `src/features/AgentTasks/features/index.ts`。它导出了列表页外部最常用的一批组件和图标，例如 `AgentTaskCardList`、`AgentTaskItem`、`AssigneeAvatar`、各优先级图标、`TaskLatestActivity`、`TaskListHeader`、`TaskPriorityTag`、`TaskStatusIcon`、`TaskSubtaskProgressTag`、`TaskTriggerTag`。

需要注意，`index.ts` 并没有导出目录中的所有文件。比如从当前片段看，`TaskStatusTag`、`AssigneeAgentSelector`、`formatTaskItemDate`、`taskCardListDisplay`、`menuExtra`、`useTaskItemContextMenu` 未出现在该聚合导出里。根据当前片段推断，这些更可能是目录内部使用的细粒度实现或被具体文件按相对路径引用，而不是稳定的跨模块公开 API。

上一级功能域入口是 `src/features/AgentTasks/index.tsx`，它只导出 `TaskDetailPage` 和 `AgentTasksPage`，分别来自 `AgentTaskDetail` 与 `AgentTaskList`。这说明 `features` 目录不是整个 `AgentTasks` 模块的顶级页面入口，而是被 `AgentTaskList` 等页面层组合使用的内部功能组件集合。

## 主流程位置

`AgentTasks` 的页面主流程不从本目录启动，而是从上一级工作区和页面入口进入。

第一层是 `src/features/AgentTasks/TaskWorkspaceLayout.tsx`。它是任务工作区布局组件，内部使用 `Outlet` 承接 React Router 的子页面，同时在非移动端渲染 `AgentTaskManager`。它还会在挂载时调用 `resetNavPanel()`，说明进入任务工作区时会重置侧边导航面板状态。这个布局负责“任务页面放在哪里、右侧管理器是否出现”，不是负责具体任务列表条目如何画出来。

第二层是 `src/features/AgentTasks/index.tsx` 暴露的 `AgentTasksPage`。根据命名和导出关系，任务列表页面应在 `AgentTaskList` 下组合本目录组件。列表页需要展示任务集合时，会进入 `AgentTaskCardList`；每个任务行或卡片再进入 `AgentTaskItem`；条目内部再调用 `TaskPriorityTag`、`TaskStatusIcon`、`TaskSubtaskProgressTag`、`TaskTriggerTag`、`AssigneeAvatar`、`TaskLatestActivity` 等小组件完成字段渲染。日期展示和列表显示策略则由 `formatTaskItemDate`、`taskCardListDisplay` 这类辅助模块支撑。

第三层是局部交互。任务条目上的更多菜单、上下文菜单或额外操作，应主要落在 `useTaskItemContextMenu.tsx` 与 `menuExtra.tsx`。根据当前片段推断，这部分是“列表项行为”的入口，而不是全局任务状态管理入口；真正的数据读写通常会在上层页面、store、service 或 Agent Task 管理模块中完成。

## 推荐阅读顺序

建议先读 `src/features/AgentTasks/index.tsx`，确认 `AgentTasks` 对外只暴露列表页和详情页两个页面级入口。然后读 `src/features/AgentTasks/TaskWorkspaceLayout.tsx`，理解任务工作区如何通过 `Outlet` 接入路由页面，以及桌面端如何同时挂载 `AgentTaskManager`。

接着进入目标目录，从 `src/features/AgentTasks/features/index.ts` 开始，看哪些组件被明确作为本目录的公开出口。之后读 `AgentTaskCardList.tsx` 和 `AgentTaskItem.tsx`，它们是列表展示的主干。再顺着单个任务条目读 `TaskPriorityTag.tsx`、`TaskStatusIcon.tsx`、`TaskSubtaskProgressTag.tsx`、`TaskTriggerTag.tsx`、`AssigneeAvatar.tsx`、`TaskLatestActivity.tsx`，理解任务字段如何被拆成小组件。

最后阅读 `formatTaskItemDate.ts`、`taskCardListDisplay.ts` 和对应测试。这些文件通常比 UI 组件更能说明“什么情况展示什么文案、什么状态走什么分支”。如果要理解交互菜单，再补读 `useTaskItemContextMenu.tsx` 和 `menuExtra.tsx`。

## 常见误区

第一，不要把 `features` 目录理解成 `AgentTasks` 的总入口。总入口在 `src/features/AgentTasks/index.tsx`，工作区布局在 `TaskWorkspaceLayout.tsx`，而目标目录主要负责列表相关的展示组件和局部行为。

第二，不要把 `icons` 目录误认为通用图标库。它当前只服务任务优先级这一组语义，命名也都围绕 `Priority*Icon`，应被看作 Agent Task 领域内的专用视觉资产。

第三，不要认为所有文件都会从 `features/index.ts` 公开导出。当前片段显示该入口只导出一部分稳定组件；未导出的辅助逻辑更可能是内部实现细节，引用时应优先确认既有调用方式，而不是随意扩大公开面。

第四，不要在这里寻找完整的数据流。任务数据的获取、状态更新、服务调用大概率在 `AgentTaskList`、`AgentTaskDetail`、`AgentTaskManager`、store 或 service 层。本目录关注的是“拿到任务数据后如何在列表中呈现和操作”。

第五，路径上要注意仓库结构差异。当前读取到的实际代码位于 `project/lobehub/src/features/AgentTasks/features`，而不是仓库根下直接的 `src/features/AgentTasks/features`。如果后续在云端覆盖层或子模块之间查找引用，应先确认当前构建实际解析到哪一份源码。
