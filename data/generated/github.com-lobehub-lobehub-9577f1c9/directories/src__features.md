# 目录：src/features

## 它负责什么

`src/features` 是 LobeHub 前端 SPA 的“业务功能层”。它位于 `src/routes` 和更底层的 `src/store`、`src/services`、`src/server` 之间，主要承载可复用的业务 UI、页面级功能块、局部状态、领域 hooks、弹窗、面板、编辑器、聊天输入、会话渲染、资源管理、插件/MCP、Electron 桥接等能力。

从仓库约定看，`src/routes` 应保持很薄，只做路由段组合；真正复杂的页面结构和业务交互会下沉到 `src/features/<Domain>`。例如 `src/routes/(main)/page/_layout/index.tsx` 直接导出 `@/features/Pages/PageLayout`，`src/routes/(main)/task/[taskId]/index.tsx` 使用 `@/features/AgentTasks`，主布局也大量引入 `NavPanel`、`RouteMeta`、`HotkeyHelperPanel`、`Electron/*` 等 feature。

因此，小白可以把 `src/features` 理解为：它不是“通用基础组件库”，也不是“数据服务层”，而是“面向具体产品功能的前端业务组件集合”。

## 关键组成

`src/features` 的直接子目录很多，按功能大致可以分成几类：

1. 聊天与会话核心：`Conversation`、`ChatInput`、`ChatMiniMap`、`FloatingChatPanel`、`TopicCanvas`、`SuggestQuestions`。其中 `Conversation/index.ts` 统一导出 `ConversationProvider`、局部 store、selectors、hooks、`ChatList`、`MessageItem`、`TodoProgress` 等；`ChatInput/index.ts` 导出桌面/移动输入框、输入编辑器 hook、发送按钮类型、action bar 配置等。它们是聊天页最核心的 UI 组合层。

2. Agent 相关：`AgentSetting`、`AgentProfileCard`、`AgentInfo`、`AgentHome`、`AgentTasks`、`AgentTaskManager`、`AgentDocumentsExplorer`、`AgentSkillDetail`、`AgentSkillEdit`。例如 `AgentSetting` 下面拆分出 `AgentMeta`、`AgentPrompt`、`AgentPlugin`、`AgentOpening`、`AgentTTS`、`AgentDocuments` 等，并带有自己的 `store` 和 `hooks`，说明它是一个完整的 agent 设置功能域。

3. 页面与文档编辑：`Pages`、`PageEditor`、`PageExplorer`、`EditorCanvas`、`EditorModal`、`DocumentModal`。`Pages/index.ts` 导出 `PageLayout`；`PageEditor/index.ts` 导出 `PageEditor` 和 `PageEditorProvider`。`PageEditor` 内部继续拆成 `Header`、`EditorCanvas`、`Copilot`、`History`、`RightPanel`、`store`，代表一个复杂编辑器功能域。

4. 导航与全局壳层：`NavPanel`、`NavHeader`、`MobileTabBar`、`RouteMeta`、`HotkeyHelperPanel`、`CommandMenu`、`RightPanel`、`WideScreenContainer`。这些 feature 经常被布局路由引用，用于构成应用框架。

5. 资源、文件和知识库：`ResourceManager`、`LibraryModal`、`FileViewer`、`FileTree`、`FileSidePanel`、`LocalFile`、`ExplorerTree`。它们负责资源列表、文件预览、知识库选择、文件树等界面能力。

6. 插件、MCP 与工具生态：`MCP`、`MCPPluginDetail`、`PluginDetailModal`、`PluginDevModal`、`PluginSettings`、`PluginAvatar`、`PluginTag`、`PluginsUI`、`ToolTag`。这些目录通常连接插件市场、插件配置、MCP 安装/详情/评分/部署等 UI。

7. Electron/桌面专属能力：`Electron`、`DesktopFileMenuBridge`、`DesktopNavigationBridge`、`ProtocolUrlHandler`、`OpenInAppButton`。`Electron` 目录下有 `AuthRequiredModal`、`ScreenCapture`、`connection`、`navigation`、`system`、`titlebar`、`updater`，用于连接桌面壳能力和 SPA。

8. 用户、认证与设置：`User`、`AuthCard`、`ProfileEditor`、`Setting`、`AvatarWithUpload`、`PlanIcon`、`Follow` 等。

9. 开发与调试：`DevPanel`、`DevFeatureFlagPanel`、`AgentMockDevtools`。这些更偏内部辅助，用于查看 feature flags、metadata、缓存、mock agent 时间线等。

`CommandMenu` 是一个文档较完整的代表。它基于 `cmdk` 做全局命令面板，包含 `index.tsx`、`useCommandMenu.ts`、`types.ts`、`components`、`MainMenu`、`SearchResults`、`ThemeMenu` 等。README 中说明它支持上下文感知、页面栈、多模式、Zustand 全局状态和 portal 渲染。

## 上下游关系

上游主要是 `src/routes` 和 `src/spa/router`。路由层会把具体页面或布局委托给 feature，例如 home、resource、page、task、onboarding、main layout 都通过 `@/features/...` 引用具体业务组件。`src/spa/router/desktopRouter.config.tsx` 和 `desktopRouter.config.desktop.tsx` 还会引用 `AgentTasks/routeMeta`、`Pages/routeMeta` 这类 feature 元数据。

下游主要有四类：

第一类是状态层。很多复杂 feature 内部带局部 store，例如 `Conversation/store`、`ChatInput/store`、`AgentSetting/store`、`PageEditor/store`。这些通常用 Zustand 管理局部 UI 状态、选择状态、编辑状态，再通过 selectors 暴露给组件。

第二类是全局 store。比如 `CommandMenu/index.tsx` 使用 `useGlobalStore` 读取和关闭全局命令菜单状态；路由布局引用的 `NavPanel`、`RouteMeta` 等也可能和全局状态协作。

第三类是服务/API 层。根据 `CommandMenu` README，它的搜索流通过 `lambdaClient.search.query.query` 请求 tRPC Lambda，并用 SWR 做数据获取。其他 feature 也常见通过 `src/services` 或 `src/server/routers` 间接访问后端。

第四类是 UI 基础设施。feature 内部会使用 `@lobehub/ui`、antd、`lucide-react`、`react-i18next`、`react-router-dom`、`cmdk` 等库组合产品界面。也就是说，feature 不负责定义基础按钮/弹窗范式，但负责把基础组件拼成具体业务体验。

## 运行/调用流程

典型调用流程是：

用户访问某个 SPA 路径，`src/spa/router/*` 匹配到 `src/routes` 下的路由段；路由段文件保持轻量，导入 `@/features/<Domain>`；feature 组件加载自身的 provider、hooks、store、selectors 和子组件；需要数据时通过 SWR、client service 或 tRPC 请求后端；用户操作触发局部 store 或全局 store 更新，界面随之重渲染。

以聊天相关功能为例，根据当前片段推断：页面会组合 `Conversation` 和 `ChatInput`。`Conversation/index.ts` 暴露 `ConversationProvider`、`useConversationStore`、`ChatList`、`MessageItem` 等；`ChatInput/index.ts` 暴露 `ChatInputProvider`、`DesktopChatInput`、`MobileChatInput`、`useChatInputEditor` 等。这样外部页面不需要知道消息项、输入框、action bar、错误态、markdown 渲染等内部细节，只消费 feature 的入口导出。

以 `CommandMenu` 为例：用户按下快捷键后，全局 store 标记 `showCommandMenu`；`CommandMenu` 通过 portal 渲染到 `document.body`；内部 `useCommandMenu` 检测当前 `pathname`，决定展示主菜单、上下文命令、搜索结果、主题菜单或 AI 菜单；搜索文本经过 debounce 后用 SWR 调用后端搜索接口；按 `Escape`、`Backspace`、`Tab` 等键会改变页面栈或模式。

## 小白阅读顺序

建议先读项目分层，而不是直接扎进所有目录。

1. 先看 `src/routes` 中几个薄路由如何引用 feature，例如 `src/routes/(main)/_layout/index.tsx`、`src/routes/(main)/page/_layout/index.tsx`、`src/routes/(main)/task/[taskId]/index.tsx`。目标是理解 feature 如何被页面挂载。

2. 再看 `src/features/Conversation/index.ts` 和 `src/features/ChatInput/index.ts`。这两个入口能展示该目录常见模式：`index.ts` 聚合导出 provider、store、hooks、types 和组件。

3. 接着读 `src/features/CommandMenu/README.md`。它是少数带完整说明的 feature，适合理解“一个完整业务功能如何拆分组件、hook、utils、types、状态和数据流”。

4. 然后选一个页面型 feature，例如 `src/features/PageEditor` 或 `src/features/AgentSetting`。看它如何按 header、body、modal、store、hooks、子功能拆目录。

5. 最后再按兴趣阅读专项能力：桌面端看 `Electron`，资源管理看 `ResourceManager`/`LibraryModal`/`FileViewer`，插件生态看 `MCP`/`PluginDetailModal`/`PluginsUI`。

## 常见误区

第一，误以为 `src/features` 是通用组件库。这里的组件大多绑定具体业务语义，例如 agent 设置、会话渲染、资源管理、页面编辑；真正更通用的基础组件通常不应随意塞进这里。

第二，把业务逻辑写回 `src/routes`。当前架构强调 `routes` 是薄页面段，业务 UI 和交互应放在 `src/features`，否则路由树会膨胀，也会破坏复用边界。

第三，只改一个桌面路由配置。虽然本任务目标是 `src/features`，但 feature 的页面入口经常被 `src/spa/router/desktopRouter.config.tsx` 和 `desktopRouter.config.desktop.tsx` 引用；涉及新增页面或 route meta 时，两个配置要保持同步。

第四，忽略 feature 内部的局部 store。像 `Conversation`、`ChatInput`、`AgentSetting`、`PageEditor` 这类目录不只是 UI 文件夹，还包含 `store`、selectors、provider、hooks。阅读时如果只看 `index.tsx`，容易漏掉真实状态流。

第五，把入口导出当成全部实现。很多 feature 的 `index.ts` 只是门面，核心实现藏在子目录中，例如 `ChatInput/InputEditor`、`RuntimeConfig`、`SendArea`，`Conversation/Messages`、`Error`、`InterventionBar`，`PageEditor/Copilot`、`History` 等。应先通过入口建立地图，再进入具体子模块。

第六，忽视平台差异。`ChatInput` 同时导出 `Desktop` 和 `Mobile`，`Electron` 目录只服务桌面能力，`ProtocolUrlHandler`、`DesktopFileMenuBridge` 等也和运行环境有关。修改或学习时要先确认当前功能在哪个平台生效。
