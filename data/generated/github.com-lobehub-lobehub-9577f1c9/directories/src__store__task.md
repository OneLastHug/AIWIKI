# 目录：src/store/task

## 它负责什么

`src/store/task` 是任务域的前端 Zustand store，负责把任务列表、任务详情、任务运行生命周期、任务配置更新等能力组织成一个统一的 `useTaskStore`。它不直接渲染 UI，也不是后端任务执行逻辑本身，而是位于“React UI / features”和 `taskService` 之间的状态与动作层。

从当前片段看，这个目录主要管理两类状态：一类是列表态，例如 `tasks`、`taskGroups`、`tasksTotal`、`viewMode`、`listAgentId`、初始化标记；另一类是详情态，例如 `activeTaskId`、`taskDetailMap`、`taskSaveStatus`、创建/删除 loading 状态、任务相关 topic drawer 状态。目录中的 action slice 会调用 `@/services/task` 暴露的 `taskService`，再把服务返回结果写回 store，或通过 SWR `mutate` 触发刷新。

整体角色可以理解为：任务页面的数据中枢。UI 组件从这里读 selector，调用这里的 action；这里再决定是本地更新、乐观更新、刷新缓存，还是调用服务端接口。

## 直接子目录地图

`src/store/task/selectors` 是选择器目录，负责把原始 store state 转换成 UI 更容易消费的派生数据。它分成 `listSelectors.ts`、`detailSelectors.ts`、`activitySelectors.ts` 三组：列表选择器处理任务列表、看板分组、空状态和显示状态；详情选择器处理当前任务、可运行/可暂停/可取消判断、配置字段、保存状态等；活动选择器处理详情里的 activities，并按 brief、topic、comment 分类。

`src/store/task/slices` 是 action 与 state 分片目录，下面有四个直接分片：`list`、`detail`、`lifecycle`、`config`。其中 `list` 关注列表和分组加载；`detail` 关注任务详情、创建、删除、更新、评论、依赖、子任务排序、文档 pin 等；`lifecycle` 关注任务运行过程，例如运行任务、取消 topic、删除 topic、更新任务状态、运行就绪子任务；`config` 关注任务配置类更新，例如模型配置、checkpoint、review、自动化模式、周期和 schedule。

## 关键入口

最外层入口是 `src/store/task/index.ts`，它只导出 `TaskStore`、`useTaskStore` 和 `getTaskStoreState`，供外部模块按 store 入口引用。

核心组装入口是 `src/store/task/store.ts`。这里定义 `TaskStore` interface，把 `TaskConfigSliceAction`、`TaskDetailSliceAction`、`TaskLifecycleSliceAction`、`TaskListSliceAction`、`ResetableStore` 和 `TaskStoreState` 合并成完整 store 类型。`createStore` 会展开 `initialState`，再通过 `flattenActions` 合并四个 slice 和 `TaskStoreResetAction`。最后使用 `createWithEqualityFn` 创建 `useTaskStore`，并通过 `createDevtools('task')` 和 `expose('task', useTaskStore)` 接入调试与暴露机制。

状态入口是 `src/store/task/initialState.ts`。它只聚合 `detail` 与 `list` 两个 slice 的 initial state。根据当前片段推断，`config` 和 `lifecycle` 主要提供动作，不单独贡献持久 state；依据是 `initialState.ts` 只导入了 `slices/detail/initialState` 和 `slices/list/initialState`。

selector 入口是 `src/store/task/selectors/index.ts`，统一导出 `taskActivitySelectors`、`taskDetailSelectors`、`taskListSelectors`。

## 主流程位置

列表加载主流程在 `src/store/task/slices/list/action.ts`。这里定义 `fetchTaskList`、`refreshTaskList`、`useFetchTaskList`、`refreshTaskGroupList`、`useFetchTaskGroupList`，并维护 `listAgentId` 与 `viewMode`。列表数据来自 `taskService.list`，分组数据来自 `taskService.groupList`；看板相关默认分组也在这个 slice 附近定义。

详情读取与编辑主流程在 `src/store/task/slices/detail/action.ts`。`fetchTaskDetail` 负责按 task id 拉取详情并写入 `taskDetailMap`；`useFetchTaskDetail` 负责 SWR 式订阅和轮询；`createTask`、`deleteTask`、`updateTask` 是任务 CRUD 的关键动作。这个文件还处理评论、依赖、子任务排序、文档 pin/unpin 等详情页交互。它的 reducer 在 `src/store/task/slices/detail/reducer.ts`，用于 `updateTaskDetail` 和 `deleteTaskDetail` 这类 map 更新，尤其支撑乐观更新和回滚。

运行生命周期主流程在 `src/store/task/slices/lifecycle/action.ts`。如果要理解“点击运行任务后发生什么”，应从 `runTask`、`runReadySubtasks`、`updateTaskStatus`、`cancelTopic`、`deleteTopic` 看起。这一层偏行为编排，通常会调用服务端后刷新任务列表或详情。

任务配置主流程在 `src/store/task/slices/config/action.ts`。这里处理 `updateTaskModelConfig`、`updateCheckpoint`、`updateReview`、`runReview`、`setAutomationMode`、`updatePeriodicInterval`、`updateSchedule`、`markBriefRead`、`resolveBrief` 等偏配置和任务活动处理的动作。默认心跳间隔、默认 cron pattern、默认 timezone 的解析也在这里。

## 推荐阅读顺序

建议先读 `src/store/task/store.ts`，确认这个 store 如何被创建、四个 slice 如何组合，以及 `useTaskStore` 是唯一对外 hook。接着读 `src/store/task/initialState.ts`，建立“列表态 + 详情态”的状态模型。

第二步读 `src/store/task/slices/list/initialState.ts` 和 `src/store/task/slices/detail/initialState.ts`，先理解 state 形状，再进入 action。这样看 `taskDetailMap`、`activeTaskId`、`tasks`、`taskGroups` 时不会迷路。

第三步读 `src/store/task/slices/list/action.ts` 和 `src/store/task/slices/detail/action.ts`。这是最核心的业务入口：一个对应任务列表页，一个对应任务详情页。读完后再看 `src/store/task/slices/detail/reducer.ts`，补上详情 map 更新、乐观更新和删除恢复的细节。

第四步读 `src/store/task/slices/lifecycle/action.ts` 和 `src/store/task/slices/config/action.ts`。前者理解任务运行状态流转，后者理解模型、自动化、schedule、review、brief 等配置型能力。

最后读 `src/store/task/selectors/*.ts`。selector 最适合在已理解 state 后阅读，因为它们展示了 UI 实际需要哪些派生视角，例如 active task 字段、看板分组、活动排序、未解决 brief 数量等。

## 常见误区

不要把 `src/store/task` 理解成任务后端执行器。它只是前端 store，真正的网络请求通过 `taskService` 发出，服务端逻辑应继续追到 `src/services/task` 以及对应 router/service 层。

不要绕过 selector 在 UI 中重复拼装派生数据。当前目录已经把列表、详情、活动三类派生逻辑集中到 `selectors`，例如 active task 的字段、可操作状态、activity 分类都不应该在多个组件里重复写。

不要只改某个 action 而忽略刷新链路。比如 `createTask`、`deleteTask`、`updateTask` 往往不只是调用服务，还会刷新列表、刷新详情、更新 `activeTaskId` 或处理失败回滚。这里的主流程重点在“服务调用 + store 更新 + SWR 刷新”三者的配合。

不要把 `config` slice 当作纯表单状态。根据当前片段，它没有独立 initial state，更多是任务配置写入动作集合，修改后通常需要刷新详情或同步当前任务数据。

不要误以为所有任务详情都只有当前 active 一个。`taskDetailMap` 是按 id 缓存多个详情，`activeTaskId` 只是当前视图指针；子任务、父任务、重挂父任务等场景会同时影响多个缓存项。

不要忽略测试文件的价值。`src/store/task/slices/*/*.test.ts` 和 `src/store/task/selectors/*.test.ts` 不属于主流程入口，但能快速确认行为边界，特别是 `updateTask` 失败回滚、删除恢复、selector 派生规则这类容易误判的逻辑。
