# 目录：src/routes/(main)

## 它负责什么

`src/routes/(main)` 是 LobeHub 桌面主应用的 SPA 路由页面段目录。它不属于 Next.js App Router 的页面系统，而是被 `src/spa/router/desktopRouter.config.tsx` 和 `src/spa/router/desktopRouter.config.desktop.tsx` 通过 `react-router-dom` 注册为客户端路由树。

这个目录承载的是“主工作台”里的页面入口：聊天、主页、设置、发现市场、资源库、记忆、页面文档、任务工作区、图片/视频生成、评测、开发工具等。它的顶层 `_layout` 是整个主应用外壳，负责挂载导航栏、桌面桥接能力、热键作用域、拖拽上下文、全局弹窗、认证相关组件和 `<Outlet />`。具体业务页面则通过子目录的 `_layout/index.tsx`、`index.tsx`、`[id]/index.tsx` 等文件进入。

按照仓库约定，`src/routes/` 理想上只应该做“路由根”：薄页面、薄布局、参数读取、跳转、组合 feature。真实代码里可以看到它处在渐进迁移状态：`page` 已经明显转向 `src/features/Pages`、`src/features/PageExplorer`；但 `agent`、`home`、`settings`、`community`、`resource`、`memory`、`eval` 等目录内部仍有不少 `features/`、`components/` 和较重 UI 逻辑。阅读时要把它理解为“路由入口 + 部分历史业务实现混合区”。

## 关键组成

顶层布局是 `src/routes/(main)/_layout/index.tsx`。它声明 `'use client'`，使用 `HotkeysProvider` 提供全局热键作用域，挂载 `RouteMetaBridge` 同步路由元信息，按 `isDesktop` 条件启用 `DesktopNavigationBridge`、`DesktopFileMenuBridge`、截屏 overlay、`TitleBar`、`AuthRequiredModal` 等 Electron 桌面能力。它还包裹 `DndContextWrapper`，渲染左侧 `NavPanel`，再通过 `DesktopLayoutContainer` 和 `MarketAuthProvider` 包住主内容。一个值得注意的设计是：它直接渲染了 `DesktopHomeLayout` 与 `DesktopHome`，同时再渲染 `<Outlet />`，这说明 Home 不是普通地只在 index route 出现，而是作为持久化背景/缓存布局的一部分存在。

`home` 是主应用默认页。`home/_layout/index.tsx` 使用 React 19 的 `Activity`，在非首页时把 Home 布局隐藏而不是卸载，并通过 `hasActivated` 避免首次未访问首页时就渲染。`home/index.tsx` 组合 `HomePageTracker`、`NavHeader`、`WideScreenContainer` 和 `HomeContent`。

`agent` 是聊天主域。`agent/_layout/index.tsx` 初始化 agent 配置，渲染聊天侧边栏、主内容 `<Outlet />`、热键、协议 URL 处理、`AgentIdSync` 和 `PortalAutoCollapse`。`agent/index.tsx` 是聊天页，挂载 `ChatHydration`、`Conversation` 和 `TelemetryNotification`。它下面还有 `agent/[topicId]`、`agent/page`、`agent/profile`、`agent/channel`、`agent/task/[taskId]` 等子页面。

`settings` 是设置中心。`settings/_layout/index.tsx` 提供 `SettingsContextProvider`，显示设置侧边栏，并把子页面放入 `<Outlet />`。`settings/index.tsx` 从 `useParams` 读取 `tab`，转成 `SettingsTabs`，交给 `SettingsContent` 渲染。`settings/provider/index.tsx` 还导出 `ProviderLayout` 和 `ProviderDetailPage`，用于 `/settings/provider/:providerId` 这种更深的嵌套路由。

`page` 是一个比较符合新规范的样板。`page/_layout/index.tsx` 直接 re-export `@/features/Pages/PageLayout`；`page/index.tsx` 只渲染 `PageExplorerPlaceholder`；`page/[id]/index.tsx` 读取 URL 参数，用 `getIdFromIdentifier(params.id, 'docs')` 得出 `pageId`，同步到 `usePageStore.selectedPageId`，卸载时清空，再渲染 `PageExplorer`。这类文件体现了“路由只负责参数和挂载 feature”的目标形态。

其他顶层目录可以按业务域理解：`community` 是发现/市场页；`resource` 是资源库；`memory` 是记忆管理；`group` 是群组智能体聊天；`(create)/image` 和 `(create)/video` 是生成式创作页面；`tasks`、`task/[taskId]` 和 `(task-workspace)/_layout` 是跨 agent 的任务工作区；`eval` 是评测相关页面；`devtools` 是开发工具页；`components`、`hooks` 是当前路由组内部复用的小工具。

## 上下游关系

上游入口主要是 `src/spa/router/desktopRouter.config.tsx`。这个文件声明 `desktopRoutes: RouteObject[]`，用 `dynamicLayout` 和 `dynamicElement` 动态导入 `@/routes/(main)/...`。例如 `/agent/:aid` 使用 `agent/_layout`，其 index route 使用 `agent/index.tsx`；`/page` 使用 `page/_layout`，index route 加载 `page/index.tsx`，`:id` 加载 `page/[id]/index.tsx`；`/tasks` 和 `/task/:taskId` 共享 `(task-workspace)/_layout`。

还有一个同步版本 `src/spa/router/desktopRouter.config.desktop.tsx`，它用静态 import 注册同一套路由树，供桌面端或同步加载场景使用。两份配置必须保持路径、嵌套、index route、动态段一致，否则可能出现某个构建路径空白屏。仓库里还有 `desktopRouter.sync.test.tsx` 专门检查关键路由是否同步。

下游主要是三类：

第一类是 `src/features/*`。例如 `page` 路由调用 `@/features/Pages/PageLayout`、`@/features/PageExplorer`；顶层 layout 调用 `NavPanel`、`RouteMetaBridge`、`DesktopFileMenuBridge`、`HotkeyHelperPanel` 等 feature。

第二类是 store 和 hooks。比如 `page/[id]` 读写 `usePageStore`；`agent/_layout` 调用 `useInitAgentConfig`；顶层 `_layout` 读取 `useServerConfigStore(featureFlagsSelectors)` 判断是否显示云端推广 banner；`DesktopLayoutContainer` 读取 `useGlobalStore` 判断左侧面板展开状态。

第三类是运行环境能力。`isDesktop`、`TITLE_BAR_HEIGHT`、Electron 桥接组件、截屏 overlay、`ProtocolUrlHandler` 等都说明 `(main)` 同时服务 Web SPA 和 Electron 桌面壳，部分组件只在桌面环境生效。

## 运行/调用流程

应用启动后，SPA entry 会加载 React Router 配置。访问 `/` 时，路由命中 `desktopRoutes` 中 path 为 `/` 的主节点，先加载 `src/routes/(main)/_layout/index.tsx`。这个 layout 建立全局外壳：热键、路由元信息桥、桌面桥、TitleBar、左侧导航、认证上下文、拖拽上下文、Home 持久布局，以及用于子路由渲染的 `<Outlet />`。

如果当前路径是 `/`，路由配置里 index route 只有 meta，没有额外 element；真正显示的首页来自主 layout 中常驻的 `DesktopHomeLayout + DesktopHome`。`home/_layout` 会根据 `pathname === '/'` 设置 `Activity mode="visible"`，所以首页内容可见。

如果访问 `/agent/:aid`，主 layout 仍然存在，`<Outlet />` 进入 `agent/_layout`。`agent/_layout` 初始化 agent 配置、显示 agent 侧边栏，再通过内部 `<Outlet />` 加载聊天页、profile、channel、topic page 或 task detail。访问 `/agent/:aid/:topicId/page/:docId` 时，会进一步进入 topic page 文档页面。

如果访问 `/settings/provider/openai`，主 layout 的 `<Outlet />` 进入 `settings/_layout`，它提供设置上下文和设置侧边栏；再进入 provider 专用布局 `ProviderLayout`，显示 provider 菜单和内部 `<Outlet />`；最后 `ProviderDetailPage` 从 params 里拿到 `providerId` 并渲染详情组件。

如果访问 `/page/docs-xxx` 一类路径，`page/[id]/index.tsx` 负责把路由参数解析成业务 `pageId`，写入 `usePageStore.selectedPageId`，渲染 `PageExplorer`，并在卸载时清理选择状态。这个流程最接近当前路线设计推荐的薄路由模式。

## 小白阅读顺序

1. 先读 `src/spa/router/desktopRouter.config.tsx` 的开头和 `/` 主节点，理解 `dynamicLayout(() => import('@/routes/(main)/_layout'))` 如何把这个目录接入 React Router。

2. 再读 `src/routes/(main)/_layout/index.tsx`，重点看它渲染了哪些全局壳组件、哪里是 `NavPanel`、哪里是 `DesktopHomeLayout`、哪里是 `<Outlet />`。这能建立“主应用外壳 + 子页面插槽”的整体模型。

3. 读 `src/routes/(main)/home/_layout/index.tsx` 和 `home/index.tsx`，理解为什么首页是持久化渲染，而不是普通 index element。

4. 读 `src/routes/(main)/agent/_layout/index.tsx` 和 `agent/index.tsx`，这是最核心的聊天工作区。看懂 `Sidebar + Outlet + Conversation`，就能理解大部分聊天路由的页面结构。

5. 读 `src/routes/(main)/settings/_layout/index.tsx`、`settings/index.tsx`、`settings/provider/index.tsx`，学习普通设置页和嵌套详情页怎么通过 `useParams`、`Outlet`、`navigate` 串起来。

6. 最后读 `src/routes/(main)/page`，把它当作新规范样板：路由文件薄，核心 UI 和业务逻辑下沉到 `src/features`、`src/store` 和工具函数。

## 常见误区

不要把 `src/routes/(main)` 当成 Next.js 的文件路由。这里的括号目录、`_layout`、`[id]` 命名虽然看起来像 App Router，但实际由 `react-router-dom` 的 `RouteObject` 手动注册，是否生效取决于 `src/spa/router/*.config.tsx`。

不要以为新增一个目录就会自动生成页面。比如新建 `src/routes/(main)/foo/index.tsx` 后，如果没有在桌面路由配置里加入 path 和 element，用户访问 `/foo` 不会命中它。桌面路由还要同时维护异步版 `desktopRouter.config.tsx` 和同步版 `desktopRouter.config.desktop.tsx`。

不要误解首页的渲染方式。`/` 的 index route 在配置里主要提供 route meta，首页内容实际被顶层 `_layout` 常驻挂载，再由 `home/_layout` 用 `Activity` 控制显示/隐藏。这是为了保留首页状态，不是普通的 `Outlet` 子页面模式。

不要认为所有 `features/` 都已经迁移到 `src/features`。当前 `(main)` 下仍有大量历史 `features/` 和 `components/`，例如 `agent/features`、`settings/features`、`community/features`、`memory/features`。根据当前片段推断，项目正在分阶段迁移，`page` 目录是更接近目标规范的示例。

不要在路由文件里随意堆复杂业务逻辑。现有历史代码可以阅读，但新增或大改时应优先把业务 UI、hooks、store 交互沉到 `src/features/<Domain>`，路由层只保留 layout、page entry、参数读取、跳转和 feature 组合。

不要忽略 `isDesktop` 条件。`(main)` 同时覆盖 Web 和 Electron 桌面体验，顶层 layout 中很多桥接、标题栏、截屏、协议处理只在桌面端启用。调试某个组件不出现时，需要先判断运行环境和 feature flag。
