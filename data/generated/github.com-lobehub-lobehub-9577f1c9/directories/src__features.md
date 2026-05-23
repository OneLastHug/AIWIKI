# 目录：src/features

## 它负责什么

`src/features` 是 LobeHub 前端业务能力的主要承载层，位于 `src/routes` 与底层 `src/store`、`src/services`、`src/components` 之间。它不是单纯的基础组件库，而是按业务域组织的“功能模块层”：会话、输入框、导航、任务、页面编辑、资源管理、插件、用户、设置、Electron 桥接、移动端辅助 UI 等都在这里沉淀。

从当前片段看，项目采用“routes thin、features thick”的分层方式：`src/routes` 下的页面段通常只负责路由壳、布局组合和少量参数衔接，实际页面主体、业务组件、局部 hooks、feature 内部 store、弹窗和面板大多放在 `src/features`。例如 `src/routes/(main)/task/[taskId]/index.tsx` 直接导出或使用 `src/features/AgentTasks`，`src/routes/(main)/page/_layout/index.tsx` 交给 `src/features/Pages/PageLayout`，主布局 `src/routes/(main)/_layout/index.tsx` 则组合 `NavPanel`、`RouteMetaBridge`、Electron 相关桥接和全局面板。

## 直接子目录地图

这个目录规模较大，直接子目录可以按角色理解，而不是逐个叶子阅读。

会话与输入相关包括 `Conversation`、`ChatInput`、`ChatMiniMap`、`SuggestQuestions`、`TopicCanvas`、`TopicPopupGuard`。其中 `Conversation` 更像聊天主流程的聚合入口，导出 `ConversationProvider`、`ChatList`、`MessageItem`、`ChatInput`、局部 store selectors 和类型；`ChatInput` 则拆分了 `Desktop`、`Mobile`、`InputEditor`、`ActionBar`、`SendArea`、`RuntimeConfig` 等输入区能力。

Agent 与任务相关包括 `AgentHome`、`AgentInfo`、`AgentSetting`、`AgentBuilder`、`AgentProfileCard`、`AgentTasks`、`AgentTaskList`、`AgentTaskManager`、`AgentDocumentsExplorer`、`AgentSkillDetail`、`AgentSkillEdit`。其中 `AgentTasks` 内部还分出 `AgentTaskDetail`、`AgentTaskList`、`CreateTaskModal`、`features`、`shared`，是任务列表、任务详情和任务路由元信息的重要聚合点。

页面与编辑相关包括 `Pages`、`PageExplorer`、`PageEditor`、`EditorCanvas`、`EditorModal`、`EditingPopover`、`DocumentModal`。`Pages` 负责页面路由布局和页面模块入口，`PageEditor` 负责编辑器主体、画布、Header、History、RightPanel 以及编辑器局部状态。

导航与布局相关包括 `NavPanel`、`NavHeader`、`RightPanel`、`WideScreenContainer`、`MobileTabBar`、`MobileSwitchLoading`、`RouteMeta`。`NavPanel` 不只是 UI，它提供 `NavPanelPortal`、`useActiveNavKey` 等机制，让不同 route 向主导航侧栏注入当前内容。

资源、文件与知识库相关包括 `ResourceManager`、`LibraryModal`、`FileViewer`、`FileTree`、`FileSidePanel`、`LocalFile`、`ExplorerTree`、`DataImporter`。这些模块连接资源页、文件预览、库创建/分配、层级树和本地文件能力。

插件、模型、工具与集成相关包括 `MCP`、`MCPPluginDetail`、`PluginDetailModal`、`PluginDevModal`、`PluginSettings`、`PluginsUI`、`PluginAvatar`、`PluginTag`、`ModelSelect`、`ModelSwitchPanel`、`ModelParamsControl`、`ServiceModel`、`ToolTag`、`SkillStore`、`SkillsList`。它们承接模型切换、插件详情、MCP 配置、技能市场与工具标签等功能。

用户、设置和系统辅助包括 `User`、`Setting`、`ProfileEditor`、`AuthCard`、`AvatarWithUpload`、`HotkeyHelperPanel`、`CommandMenu`、`ShareModal`、`SharePopover`、`ChangelogModal`、`AlertBanner`、`Billboard`、`Recommendations`、`DailyBrief`、`Onboarding` 等，覆盖账户面板、设置页、分享、更新提示、引导页和推荐内容。

桌面端与运行环境相关集中在 `Electron`、`DesktopFileMenuBridge`、`DesktopNavigationBridge`、`ProtocolUrlHandler`、`PWAInstall`、`OpenInAppButton`。`Electron` 下又有 `titlebar`、`system`、`navigation`、`ScreenCapture`、`HeterogeneousAgent`、`updater` 等子域，用于 Electron 外壳和 Web SPA 之间的衔接。

## 关键入口

多数 feature 通过目录下的 `index.ts` 或 `index.tsx` 暴露稳定入口，例如 `src/features/Conversation/index.ts`、`src/features/ChatInput/index.ts`、`src/features/PageEditor/index.ts`、`src/features/Pages/index.ts`、`src/features/AgentTasks/index.tsx`、`src/features/NavPanel/index.tsx`。

`Conversation/index.ts` 是典型聚合入口：它导出 provider、hooks、store selectors、类型，以及 `ChatInput`、`ChatList`、`MessageItem`、`TodoProgress` 等组件。读这个文件可以快速理解会话模块对外暴露了哪些能力。

`ChatInput/index.ts` 负责输入框能力的出口，包含 `ChatInputProvider`、`DesktopChatInput`、`MobileChatInput`、`ActionKeys`、编辑器 hook 和发送按钮处理类型。它常被首页输入区、图像/视频生成输入区等复用。

`NavPanel/index.tsx` 是主导航面板入口。它内部维护当前侧栏快照，默认回退到 home 侧栏，并通过 `NavPanelPortal` 允许其它页面把自己的侧栏内容挂到全局导航容器里。

`AgentTasks/index.tsx`、`Pages/index.ts`、`PageEditor/index.ts` 则分别是任务页、页面布局/页面域、页面编辑器域的对外门面。根据当前片段推断，这些入口的作用是隐藏 feature 内部结构，让 route 层只依赖少量稳定导出；依据是 `src/routes` 中存在多处 `export { default } from '@/features/...'` 或从 feature 根入口导入页面组件的用法。

## 主流程位置

主应用布局流程从 `src/routes/(main)/_layout/index.tsx` 进入，它组合 `NavPanel`、`RouteMetaBridge`、Electron 桥接、热键帮助、全局 banner 和标题栏等跨页面设施。这个文件是理解 `src/features` 如何被装配到应用壳的第一入口。

聊天/会话主流程主要分布在 `src/features/Conversation` 与 `src/features/ChatInput`，并由 `src/routes/(main)/home`、`src/routes/(main)/agent`、`src/routes/(mobile)/chat` 等 route 片段接入。`ConversationProvider`、`ChatList`、`MessageItem` 和输入区 provider 构成了阅读会话体验的主线。

任务主流程在 `src/features/AgentTasks`，路由侧对应 `src/routes/(main)/tasks/index.tsx`、`src/routes/(main)/task/[taskId]/index.tsx`，同时路由配置 `src/spa/router/desktopRouter.config.tsx`、`src/spa/router/desktopRouter.config.desktop.tsx` 引入 `taskRouteMeta`、`tasksRouteMeta`。这说明任务不仅有页面组件，也参与桌面路由元信息注册。

页面/文档主流程在 `src/features/Pages`、`src/features/PageExplorer`、`src/features/PageEditor`。路由侧对应 `src/routes/(main)/page/_layout/index.tsx`、`src/routes/(main)/page/index.tsx`、`src/routes/(main)/page/[id]/index.tsx`，路由配置还引入 `pageRouteMeta`。

资源管理主流程在 `src/features/ResourceManager`、`LibraryModal`、`FileViewer` 等模块，并由 `src/routes/(main)/resource`、`src/routes/(main)/resource/library` 接入。导航侧栏和资源层级树也通过 `NavPanel` 与 `ResourceManager/components/LibraryHierarchy` 协同。

桌面端流程主要在 `src/features/Electron` 及两个 bridge：`DesktopFileMenuBridge`、`DesktopNavigationBridge`。它们在主布局、popup 布局和 desktop onboarding 中被引用，是 Electron 外壳能力进入 React SPA 的位置。

## 推荐阅读顺序

1. 先读 `src/routes/(main)/_layout/index.tsx`，理解主应用壳如何组合 `src/features` 中的全局设施。
2. 再读 `src/features/NavPanel/index.tsx` 和 `src/features/RouteMeta`，掌握导航注入、当前导航态和路由元信息的组织方式。
3. 阅读 `src/features/Conversation/index.ts`、`src/features/ChatInput/index.ts`，建立聊天主流程的总体图。
4. 根据业务关注点选择分支：任务看 `src/features/AgentTasks`，页面编辑看 `src/features/Pages`、`src/features/PageEditor`，资源看 `src/features/ResourceManager`、`src/features/LibraryModal`、`src/features/FileViewer`。
5. 最后看横切能力：`src/features/User`、`src/features/Setting`、`src/features/Electron`、`src/features/PluginDevModal`、`src/features/MCP`、`src/features/SkillStore`。这些模块往往被多个页面复用，适合在理解主流程后补读。

## 常见误区

不要把 `src/features` 当成纯 UI 组件目录。基础、无业务语义的组件更可能在 `src/components` 或外部 UI 包中；`src/features` 里的组件通常携带业务上下文、hooks、局部 store、弹窗开启逻辑或路由协作逻辑。

不要在 `src/routes` 中继续堆业务实现。当前结构明确倾向于 route 只做页面段和组合，复杂 UI 与业务逻辑应进入 `src/features/<Domain>`，再由 feature 入口导出。

不要只改一个桌面路由配置。与 `AgentTasks`、`Pages` 相关的 route meta 同时出现在 `src/spa/router/desktopRouter.config.tsx` 和 `src/spa/router/desktopRouter.config.desktop.tsx`，这两个配置需要保持同步，否则不同构建入口可能出现路由缺失。

不要按字母顺序逐个目录读。`src/features` 是大目录，直接从 `AgentBuilder` 一路读到 `ZenModeToast` 效率很低。更有效的方式是先从 route 引用和 feature 根 `index` 建地图，再进入目标业务域。

不要忽略 feature 内部的 `store`、`hooks`、`shared`、`components` 子目录。它们通常表示该 feature 已经形成相对完整的局部边界；但也不要把这些局部 store 与全局 `src/store` 混淆，前者多服务于单一功能域，后者承载跨页面应用状态。
