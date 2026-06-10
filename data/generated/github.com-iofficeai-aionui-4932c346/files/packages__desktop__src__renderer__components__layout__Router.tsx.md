# 文件：packages/desktop/src/renderer/components/layout/Router.tsx

## 一句话定位

`Router.tsx` 是桌面渲染端的顶层路由表文件：它用 `HashRouter` 建立前端页面导航边界，并把登录态校验、页面懒加载、默认跳转、历史兼容跳转和功能开关路由集中在一个入口里。

## 它暴露/定义了什么

该文件默认导出 `PanelRoute` 组件。它接收一个 `layout: React.ReactElement` 参数，外部把主布局传进来，`PanelRoute` 负责把这个布局包进 `HashRouter` 和 `Routes` 中。

文件内部还定义了两个关键包装函数/组件：

`withRouteFallback`：把懒加载页面组件包进 `Suspense`，加载期间显示 `AppLoader`。

`ProtectedLayout`：读取 `useAuth()` 的 `status`，在认证检查中显示加载页，未登录时重定向到 `/login`，已登录时渲染传入的 `layout`。

除此之外，它集中声明了多个 `React.lazy` 页面入口，例如 `Guid`、`Conversation`、各类 settings 页面、login 页面、cron 定时任务页面、team 页面等。

## 谁调用它

直接调用者是 `packages/desktop/src/renderer/main.tsx`。`main.tsx` 中的 `Main` 组件等待 `useAuth().ready` 和配置初始化完成后，渲染：

`<Router layout={<ConversationHistoryProvider><Layout sider={<Sider />} /></ConversationHistoryProvider>} />`

因此 `Router.tsx` 不是普通页面组件，而是整个 renderer 应用进入业务 UI 的路由根。`Layout`、`Sider`、`ConversationHistoryProvider` 等外层业务框架由 `main.tsx` 组装后交给它，具体页面内容则通过 `Layout` 内部的 `Outlet` 展开。根据当前片段推断，`ProtectedLayout` 渲染的 `layout` 中包含 `Outlet`，依据是 `Layout.tsx` 引入了 `Outlet` 且该文件被作为 `layout` 传入。

## 它调用谁

路由层面，它调用 `react-router-dom` 的 `HashRouter`、`Routes`、`Route`、`Navigate`。选择 `HashRouter` 说明应用使用 hash 路径承载虚拟路由，适合 Electron/静态资源场景，避免依赖服务端 fallback。

认证层面，它调用 `@renderer/hooks/context/AuthContext` 的 `useAuth`。认证状态来自 `AuthProvider`：桌面运行时会直接设为 `authenticated`，WebUI 模式会请求 `/api/auth/user` 判断登录态。

页面层面，它懒加载 `@renderer/pages/guid`、`@renderer/pages/conversation`、`@renderer/pages/login`、`@renderer/pages/settings/*`、`@renderer/pages/cron/*`、`@renderer/pages/team` 等页面模块。

配置层面，它读取 `TEAM_MODE_ENABLED` 控制 `/team/:id` 是否可用；关闭时访问团队路由会跳回 `/guid`。

## 核心流程

应用启动后，`main.tsx` 先完成认证 ready、配置初始化、agent 预取等前置工作，然后把主布局传入 `PanelRoute`。

`PanelRoute` 创建 `HashRouter`，并声明完整路由树。第一条显式路由是 `/login`：如果当前已经认证，则直接重定向到 `/guid`；否则懒加载登录页。

登录页以外的大多数业务路由都放在 `<Route element={<ProtectedLayout layout={layout} />}>` 下面。进入这些路由时，`ProtectedLayout` 先检查认证状态：`checking` 显示 `AppLoader`，非 `authenticated` 重定向 `/login`，认证通过后渲染主布局。主布局再通过 React Router 的嵌套路由机制承载子页面。

受保护路由的默认 index 会跳转 `/guid`。主要业务页包括 `/guid`、`/conversation/:id`、`/scheduled`、`/scheduled/:job_id`、多组 `/settings/...`，以及受 `TEAM_MODE_ENABLED` 控制的 `/team/:id`。

最后的 `path='*'` 是兜底路由：已登录用户进入未知路径会回 `/guid`，未登录用户回 `/login`。

## 关键函数的高层作用

`withRouteFallback` 的作用是统一页面懒加载体验，避免每个路由重复写 `Suspense fallback={<AppLoader />}`。它只处理加载态，不参与权限或布局。

`ProtectedLayout` 是业务路由的认证闸门。它不关心具体目标页面，只根据 `useAuth().status` 决定显示加载、跳登录，还是放行到主布局。这里用 `React.cloneElement(layout)` 渲染传入布局，保留外部传入的布局结构，同时让它处于受保护路由上下文中。

`PanelRoute` 是核心路由声明函数。它把登录路由、受保护路由、legacy redirect、功能开关路由和 404 兜底放在同一棵 `Routes` 树里。辅助性的 `React.lazy` 声明只是拆包优化，不需要理解为业务逻辑。

## 修改风险

最大风险是认证边界。把新业务页放在 `/login` 同级而不是 `ProtectedLayout` 子级，会绕过登录保护；反过来，把登录或公开页放进 `ProtectedLayout`，未登录用户会被重定向，可能形成不可达页面。

第二类风险是 hash 路由语义。仓库中很多地方调用 `useNavigate()` 跳转 `/guid`、`/conversation/:id`、`/settings/...`、`/scheduled/...`。修改路径字符串、参数名或默认重定向，会影响 `Sider`、`Titlebar`、deep link、通知点击、托盘事件、快捷键、定时任务详情跳转等多个入口。

第三类风险是布局嵌套。受保护页面依赖传入的 `Layout` 承载 `Outlet`；如果移除嵌套路由结构，页面可能只显示框架不显示内容，或布局级 hooks 如 deep link、通知点击、快捷键监听不再生效。

第四类风险是 legacy route。`/settings/skills-hub`、`/settings/tools`、`/settings/display`、`/settings/about` 这类跳转看起来是兼容旧路径或旧入口的桥接，删除它们可能破坏历史链接、设置侧栏入口、外部事件或旧版本缓存路径。

第五类风险是 `TEAM_MODE_ENABLED`。团队页并非单纯页面注册，它受编译/运行配置控制。新增团队相关入口时，需要同时考虑关闭团队模式时的跳转策略，否则可能出现侧栏可点但路由被重定向，或路由可达但数据能力未启用的状态。
