# 文件：web/src/App.tsx

## 一句话定位

`web/src/App.tsx` 是 Hermes dashboard 前端 SPA 的顶层应用壳：负责组合全局布局、侧边栏导航、路由表、插件页入口、主题/语言控件、系统操作入口，以及嵌入式 Chat 终端的持久挂载策略。

## 它暴露/定义了什么

该文件默认导出 `App()` 组件，同时在文件内定义一组只服务于应用壳的辅助组件和构建函数。

核心定义包括：`BUILTIN_ROUTES_CORE`、`BUILTIN_NAV_REST`、`CHAT_NAV_ITEM` 这些内置路由和导航配置；`buildNavItems()`、`partitionSidebarNav()`、`buildRoutes()` 用于把内置页面和 dashboard 插件 manifest 合并成导航与路由；`SidebarNavLink`、`SidebarSystemActions`、`SystemActionButton`、`GatewayDot`、`SidebarTooltip` 等用于侧边栏渲染与交互。`RootRedirect` 和 `UnknownRouteFallback` 处理默认跳转和未知路径兜底，`ChatRouteSink` 则是嵌入式 Chat 模式下为 `/chat` 保留路由命中的占位组件。

## 谁调用它

`web/src/main.tsx` 是直接调用方。它通过 `createRoot(...).render(...)` 渲染 `<App />`，并在外层包裹 `BrowserRouter`、`I18nProvider`、`ThemeProvider`、`SystemActionsProvider`。因此 `App.tsx` 假设自己运行在 router、国际化、主题和系统动作上下文之内。`main.tsx` 还会先调用 `exposePluginSDK()`，使插件脚本在 `App` 加载插件页面和插槽前已经能访问 dashboard 插件 SDK。

## 它调用谁

页面层面，它调用 `SessionsPage`、`AnalyticsPage`、`ModelsPage`、`LogsPage`、`CronPage`、`SkillsPage`、`PluginsPage`、`ProfilesPage`、`ConfigPage`、`EnvPage`、`DocsPage`、`ChatPage` 等页面组件。框架层面，它依赖 `react-router-dom` 的 `Routes`、`Route`、`NavLink`、`Navigate`、`useLocation`、`useNavigate` 完成 SPA 路由与导航状态。插件层面，它调用 `usePlugins()` 获取 manifest 和加载状态，使用 `PluginPage` 渲染插件页，使用 `PluginSlot` 暴露 `backdrop`、`header-banner`、`header-left`、`header-right`、`pre-main`、`post-main`、`overlay` 等插槽。状态和配置层面，它调用 `api.getConfig()` 决定是否显示 Analytics 导航，调用 `useSidebarStatus()` 获取 gateway 状态，调用 `useSystemActions()` 执行 restart/update，调用 `isDashboardEmbeddedChatEnabled()` 判断是否启用嵌入式 Chat。

## 核心流程

`App()` 首先读取当前路径、插件 manifest、主题、国际化文本和侧边栏状态。它根据 `localStorage` 初始化桌面侧边栏折叠状态，并用 `useBelowBreakpoint(1024)` 区分移动端和桌面端。随后通过 `api.getConfig()` 读取 dashboard 配置，只在 `dashboard.show_token_analytics === true` 时把 `/analytics` 放入侧边栏。

路由构建分两层：内置路由先来自 `BUILTIN_ROUTES_CORE`，如果嵌入式 Chat 开启，再把 `/chat` 映射到 `ChatRouteSink`；然后 `buildRoutes()` 用插件 manifest 处理三类情况：插件覆盖内置页面、插件新增可见页面、插件新增隐藏但可直达页面。导航构建类似，`buildNavItems()` 按插件 manifest 的 `tab.position` 插入插件导航项，`partitionSidebarNav()` 再把内置项和插件项分区展示。

渲染阶段，最外层提供背景、全局插件插槽和移动端 header。主体区域左侧是响应式 sidebar：移动端以抽屉方式打开，桌面端可折叠成窄栏。右侧内容区包在 `PageHeaderProvider` 内，先渲染 `Routes`，再在嵌入式 Chat 开启且没有插件覆盖 `/chat` 时，额外挂载持久化的 `ChatPage`。这里的关键点是 `ChatPage` 不完全交给 `Routes` 生命周期控制，而是通过 `display:none`/`hidden` 风格在非 `/chat` 页面隐藏，从而保留 PTY 子进程、WebSocket 和 xterm 实例。

## 关键函数的高层作用

`buildNavItems()` 负责把插件 manifest 转成 sidebar 导航项，并支持 `end`、`after:<name>`、`before:<name>` 三种位置语义。它是插件 tab 顺序的主要入口。

`partitionSidebarNav()` 在合并后的导航列表中区分内置项和插件项，保证 sidebar 可以把插件导航放到独立分组，同时仍保留插件声明的位置影响。

`buildRoutes()` 是路由合成中心。它先处理插件对内置路径的 `tab.override`，再追加普通插件页面，最后补充隐藏插件页面的直达路由。它还避免插件重复占用 `/plugins` 或已存在的内置路径。

`App()` 是布局和状态编排中心。它不负责具体页面业务，而是负责决定哪些页面存在、哪些导航出现、侧边栏如何响应设备尺寸、系统操作入口如何挂载、Chat 是否持久运行。

`SidebarSystemActions()` 和 `SystemActionButton()` 把 restart/update 这类全局系统动作放进侧边栏。点击后通过 `runAction()` 触发动作，并导航回 `/sessions`，避免用户停留在可能受重启或更新影响的页面。

`SidebarTooltip()` 使用 `createPortal` 把折叠侧边栏的提示浮层挂到 `document.body`，位置根据触发元素和 sidebar 边界计算。`GatewayDot()` 是折叠模式下 gateway 状态的紧凑展示。

## 修改风险

最高风险是 `/chat` 的持久挂载逻辑。注释表明这是为了让嵌入式 TUI Chat 的 PTY、WebSocket、xterm 实例在切换页面时不被销毁。如果把 `ChatPage` 重新放回普通 `<Route>` 生命周期，可能导致切页即断开终端会话；如果忽略 `pluginsLoading`，插件覆盖 `/chat` 的场景可能先启动内置 Chat，再被插件替换，造成会话被中途杀掉。

第二个风险是插件路由和导航合成。`buildRoutes()` 与 `buildNavItems()` 同时承担扩展点契约，修改 `tab.override`、`tab.hidden`、`tab.position` 的语义会影响第三方 dashboard 插件。尤其是覆盖内置页面、隐藏但可访问页面这两种行为，很容易在 UI 上不明显但破坏插件兼容性。

第三个风险是响应式 sidebar。`mobileOpen`、`collapsed`、`isMobile`、`isDesktopCollapsed` 分别控制移动抽屉和桌面折叠，且还涉及 `body.style.overflow`、Escape 关闭、媒体查询切换清理。改动样式或状态时要同时验证移动端、桌面展开、桌面折叠三种形态。

第四个风险是配置驱动导航。`/analytics` 页面本身仍可通过 URL 访问，但导航默认隐藏；这是为了避免展示可能误导的 token/cost 信息。如果把它改成路由级禁用，可能改变现有深链行为。

最后，`App.tsx` 直接承载大量全局插件插槽。调整 DOM 层级、z-index、布局容器或删除插槽，都会影响插件在背景、页头、主内容前后和 overlay 区域的注入位置。根据当前片段推断，dashboard 插件系统依赖这些稳定插槽作为扩展边界，依据是 `App` 多处直接渲染 `PluginSlot`，且 `usePlugins()` 会异步加载插件 manifest 与脚本。
