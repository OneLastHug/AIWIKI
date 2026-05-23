# 目录：src/store/global

## 它负责什么

`src/store/global` 是 LobeHub 前端全局 Zustand store 的一个集中模块，负责保存和操作“跨页面、跨功能域”的 UI 状态与系统状态。它不是某个业务实体的 store，而更像应用外壳层的全局控制台：侧边栏展开、面板显隐、移动端门户显示、语言偏好、Zen Mode、分页尺寸、资源管理器列宽、任务看板显示偏好、最近使用模型选择、客户端数据库初始化状态、版本检查结果、全局导航引用等，都在这里有状态或选择器入口。

从当前片段看，这个目录的核心状态是 `GlobalState.status: SystemStatus`。`SystemStatus` 存放大量可持久化的用户界面偏好，初始值来自 `INITIAL_STATUS`，并通过 `AsyncLocalStorage('LOBE_SYSTEM_STATUS')` 落到本地存储。主更新入口是 `updateSystemStatus`：它会先检查 `isStatusInit`，再将传入的局部状态与现有 `status` 合并，避免无变化写入，最后更新 Zustand 状态并保存到 localStorage。也就是说，这里的许多 toggle 方法本质上都是 `updateSystemStatus` 的薄封装。

这个目录还承接少量全局动作，例如在桌面端或浏览器端打开 agent/topic 新窗口、切换语言并同步 Electron 主进程、检查最新版本和服务端版本。根据当前片段推断，它处在“应用壳层状态”和“全局环境能力”之间，不适合放具体业务数据，例如会话消息、知识库内容、任务实体本身等。

## 直接子目录地图

`src/store/global/actions` 存放全局 store 的 action slice。当前主要分成两类：`general.ts` 与 `workspacePane.ts`。`general.ts` 处理语言、系统状态初始化、版本检查、打开新窗口、侧边栏自定义重置、资源管理器列宽等偏通用动作；`workspacePane.ts` 处理工作区面板与布局显隐，例如左栏、右栏、agent builder、page agent panel、task agent panel、command menu、移动端 topic/portal、Zen Mode、工作侧栏 tab 等。`actions/__tests__` 是这些 action 的测试目录。

`src/store/global/selectors` 存放从 `GlobalState` 派生读取值的 selector。`general.ts` 主要提供语言相关选择器，例如 `language`、`currentLanguage`；`systemStatus.ts` 是最大的一组，负责对 `status` 中的布局、宽度、分页、侧边栏顺序、任务看板偏好、面板显隐等做默认值兜底和派生；`clientDB.ts` 读取客户端数据库迁移初始化状态，并转换成展示所需的迁移状态列表。`selectors/index.ts` 统一导出这些 selector。

除两个子目录外，根层还有几个关键文件：`store.ts` 负责创建 `useGlobalStore`；`initialState.ts` 定义枚举、状态类型、默认状态和本地存储实例；`index.ts` 作为模块导出入口；`helpers.ts` 提供非 React 场景下读取当前语言的 helper；测试文件则覆盖 store action 与 selector 行为。

## 关键入口

最关键入口是 `src/store/global/store.ts`。这里定义 `GlobalStore extends GlobalState, GlobalWorkspacePaneAction, GlobalGeneralAction`，然后用 Zustand 的 `createWithEqualityFn` 创建 `useGlobalStore`。创建流程是：展开 `initialState`，重新创建独立的 `navigationRef`，再通过 `flattenActions` 合并 `globalWorkspaceSlice` 和 `generalActionSlice`。这符合仓库的 Zustand 约定：class-based action 不能直接对象展开，而要用 `flattenActions` 保留方法绑定。

`src/store/global/index.ts` 只是导出 `./store`，所以外部常见使用形式是 `import { useGlobalStore } from '@/store/global'`。

`src/store/global/initialState.ts` 是理解全局状态边界的入口。这里定义 `SidebarTabKey`、`SettingsTabs`、`ChatSettingsTabs`、`GroupSettingsTabs`、`WorkingSidebarTab` 等枚举或类型，也定义 `SystemStatus`、`GlobalState`、`INITIAL_STATUS`、`initialState`。如果要判断某个偏好是否应该进入 global store，通常先看它是否属于这些跨页面 UI 偏好。

`src/store/global/selectors/index.ts` 是读取侧入口，统一导出 `clientDB`、`general`、`systemStatus`。组件中通常不直接手写 `s.status.xxx ?? default`，而是使用 `systemStatusSelectors.xxx`，因为这里包含默认值、兼容旧字段、Zen Mode 屏蔽逻辑和侧边栏排序迁移逻辑。

## 主流程位置

初始化主流程在 `generalActionSlice` 的 `useInitSystemStatus` 附近。根据当前片段可见，它与 `statusStorage`、`INITIAL_STATUS`、`isStatusInit` 配合，用于把本地保存的系统状态恢复到 `useGlobalStore`。`updateSystemStatus` 会在 `isStatusInit` 为 false 时直接返回，这意味着调用方必须理解：全局持久化状态未初始化前，状态写入不会生效。这是阅读和调试该目录时最重要的流程之一。

状态写入主流程是 `组件或 hook -> useGlobalStore action -> updateSystemStatus -> set({ status }) -> statusStorage.saveToLocalStorage`。例如 `toggleLeftPanel`、`toggleRightPanel`、`toggleZenMode`、`setWorkingSidebarTab`、`updateModelDetailPanelExpandedKeys` 都走这条路径。直接使用 `updateSystemStatus` 的地方也很多，比如 home 侧边栏自定义、hotkey、banner 已读状态、图像/视频模型选择等。

状态读取主流程是 `组件 -> useGlobalStore(selector) -> systemStatusSelectors/globalGeneralSelectors/clientDBSelectors`。例如 home 布局读取 `sidebarItems`、`sidebarExpandedKeys`、`hiddenSidebarSections`，快捷键读取面板显隐状态，TTS 或工具服务读取 `currentLanguage`。`systemStatusSelectors` 中还处理了 `zenMode` 对 `showLeftPanel`、`showRightPanel`、`showAgentBuilderPanel` 等展示值的影响，所以 UI 更应该读 selector，而不是直接读裸 `status` 字段。

跨路由导航流程与 `navigationRef` 有关。`initialState.ts` 定义 `createNavigationRef`，`src/utils/router.tsx` 会把 React Router 的 `navigate` 写入 `useGlobalStore`，`src/utils/stableNavigate.ts` 再读取它。`workspacePane.ts` 中的 `switchBackToChat` 就通过 `getStableNavigate()` 跳转回 chat。根据当前片段推断，这是一种避免组件订阅导航函数变化、同时允许非组件 action 触发路由跳转的全局引用机制。

## 推荐阅读顺序

建议先读 `src/store/global/store.ts`，掌握 `useGlobalStore` 如何由 `initialState`、`generalActionSlice`、`globalWorkspaceSlice` 组合出来。然后读 `src/store/global/initialState.ts`，重点看 `SystemStatus`、`GlobalState`、`INITIAL_STATUS`，明确这个 store 保存的状态范围。

接着读 `src/store/global/actions/general.ts`，关注 `useInitSystemStatus`、`updateSystemStatus`、`switchLocale`、版本检查和新窗口打开逻辑。之后读 `src/store/global/actions/workspacePane.ts`，它更像一组 UI 布局快捷操作，能帮助理解页面面板如何统一写入 `status`。

再读 `src/store/global/selectors/systemStatus.ts`，这是实际 UI 读取全局状态时最常经过的文件。特别注意默认值兜底、`sidebarItems` 的旧字段迁移、`reorderSidebarItems` 的侧边栏排序约束、以及 `zenMode` 对面板展示 selector 的影响。最后读 `selectors/general.ts`、`selectors/clientDB.ts` 和 `helpers.ts`，补齐语言和客户端数据库迁移展示这两个较独立的读取面。

## 常见误区

不要把 `src/store/global` 理解成所有全局业务数据的容器。它主要管理应用级 UI 状态、系统偏好和少量环境动作；具体领域数据应放到对应 store、service 或 feature 中。

不要绕过 `updateSystemStatus` 随手 `set({ status: ... })`。这里的状态需要合并、去重、打 debug action，并保存到 `statusStorage`。绕过统一入口会造成刷新后丢失或状态不一致。

不要在组件里重复实现 selector 的默认值逻辑。像 `leftPanelWidth`、`sidebarItems`、`taskListViewOptions`、`modelDetailPanelExpandedKeys`、`showRightPanel` 这类值都已经在 `systemStatusSelectors` 中处理过默认值或派生规则。直接读 `s.status.xxx` 容易漏掉兼容逻辑。

不要忽略 `isStatusInit`。`updateSystemStatus` 在初始化前不会写入，某些“设置没生效”的问题可能不是 action 错了，而是初始化时机不对。

不要把 `navigationRef` 当普通可订阅状态使用。它是为了稳定导航引用而存在，组件内导航应优先用路由 hook；非组件或 store action 场景才通过 `getStableNavigate()` 间接使用。

不要只改 action 不看 selector。这个目录里很多行为是一写一读配套的：action 写入 `status` 字段，selector 决定 UI 实际看到什么。尤其是 Zen Mode、侧边栏排序、面板宽度和默认值兜底，问题经常出现在读取层而不是写入层。
