# 目录：src/spa/router

## 它负责什么

`src/spa/router` 是 LobeHub SPA 端的“路由注册中心”。它不负责页面业务逻辑，也不直接实现页面 UI，而是把不同运行入口需要的 `react-router-dom` 路由树组织出来，并导出给 `src/spa/entry.*.tsx` 使用。

这个目录的核心职责可以概括为三件事：

1. 定义 Web/Desktop/Mobile/Popup 四类 SPA 入口各自能访问哪些路径。
2. 把 URL path 映射到 `src/routes/**` 下的页面段组件或布局组件。
3. 为部分路由附加 `handle.meta`，供导航标题、图标、新标签页标题等上层 UI 读取。

它和 `src/routes` 的分工很明确：`src/spa/router` 只注册路由树，`src/routes` 提供页面段入口，真正复杂的业务组件应继续下沉到 `src/features`。

## 关键组成

这个目录当前包含以下文件：

- `desktopRouter.config.tsx`
- `desktopRouter.config.desktop.tsx`
- `desktopRouter.sync.test.tsx`
- `mobileRouter.config.tsx`
- `mobileRouter.test.tsx`
- `popupRouter.config.tsx`
- `routeMeta.ts`

`desktopRouter.config.tsx` 导出 `desktopRoutes: RouteObject[]`，是 Web 和 Electron desktop 入口实际引用的桌面路由配置。它大量使用 `dynamicElement` 和 `dynamicLayout`，例如：

- `dynamicElement(() => import('@/routes/(main)/agent'), 'Desktop > Chat')`
- `dynamicLayout(() => import('@/routes/(main)/agent/_layout'), 'Desktop > Chat > Layout')`

这说明桌面主路由以动态导入为主，具备代码分割能力。路由对象中常见字段包括：

- `path`：路径片段，例如 `agent`、`:aid`、`settings`、`page`。
- `index: true`：当前层级的默认子路由。
- `children`：嵌套路由。
- `element`：页面或布局元素。
- `errorElement`：错误边界，例如 `<ErrorBoundary />`。
- `handle: { meta: ... }`：路由元信息。

`desktopRouter.config.desktop.tsx` 也是桌面路由树，但它使用同步静态 import 方式注册页面和布局。根据 `spa-routes` 约定，这个文件必须和 `desktopRouter.config.tsx` 保持路径结构、嵌套结构、`index` 路由、`handle.meta` 基本一致。差异只允许少数明确记录的场景，例如测试中记录的 `'/desktop-onboarding'` 与 `'/onboarding'` 映射。

`mobileRouter.config.tsx` 导出 `mobileRoutes: RouteObject[]`，用于移动端 SPA。它同样使用 `dynamicElement`、`dynamicLayout`、`ErrorBoundary`、`redirectElement`，但路由面向移动端页面组，例如：

- `/agent/:aid`
- `/community`
- `/settings`
- `/me`
- `/onboarding`
- `/share/t/:id`

移动端也会复用一部分桌面主业务页面，例如任务相关页面引用了 `@/routes/(main)/(task-workspace)/_layout`、`@/routes/(main)/tasks`、`@/routes/(main)/task/[taskId]`。这说明“移动入口”不等于所有页面都在 `src/routes/(mobile)` 下，某些跨端业务会共享 main route 片段。

`popupRouter.config.tsx` 导出 `popupRoutes: RouteObject[]`，是一个非常小的专用路由树，入口路径是 `/popup`。它同步 import：

- `@/routes/(popup)/_layout`
- `@/routes/(popup)/agent/[aid]`
- `@/routes/(popup)/agent/[aid]/[tid]`
- `@/routes/(popup)/group/[gid]/[tid]`

从注释看，它是 desktop-only 的单会话弹窗入口，没有侧边栏和 portal，主要服务独立会话窗口。

`routeMeta.ts` 定义路由元信息的类型和工具函数：

- `StaticRouteMeta`：静态元信息，包含 `icon?: LucideIcon`、`titleKey?: string`。
- `DynamicRouteMeta`：动态元信息，包含 `avatar`、`backgroundColor`、`title`。
- `NewTabActionResult` / `NewTabAction`：创建新标签页时返回 URL 和可缓存元信息。
- `RouteMeta`：继承静态信息，并可提供 `createNewTab`、`useDynamicMeta`。
- `RouteHandle`：约定 React Router 的 `handle` 中可以放 `meta`。
- `ResolvedRouteMeta`：上层 UI 最终解析后的标题、图标、头像等信息。
- `routeMeta(meta)`：一个轻量包装函数，主要提供类型约束。
- `getRouteMetaFromHandle(handle)`：从未知类型的 `handle` 中安全提取 `meta`。

测试文件也很关键。`desktopRouter.sync.test.tsx` 不是普通单测，而是保护路由配置一致性的结构测试。它会读取 `desktopRouter.config.tsx` 和 `desktopRouter.config.desktop.tsx` 源码，比较：

- 两边 `path` 是否一致。
- 两边 `index: true` 数量是否一致。
- 两边 `handle.meta` 声明是否一致。
- 任务列表和任务详情是否都挂在共享 workspace layout 下。

`mobileRouter.test.tsx` 主要保护移动端任务路由的注册结构，确保 task list、task detail、agent task detail 都挂在共享 task workspace layout 下面。

## 上下游关系

上游调用方是 `src/spa/entry.*.tsx`：

- `src/spa/entry.web.tsx` import `desktopRoutes`。
- `src/spa/entry.desktop.tsx` import `desktopRoutes`。
- `src/spa/entry.mobile.tsx` import `mobileRoutes`。
- `src/spa/entry.popup.tsx` import `popupRoutes`。

这些入口会调用 `createAppRouter(routes)`，然后把生成的 router 传给 `<RouterProvider router={router} />`。根据当前片段推断，`createAppRouter` 来自 `@/utils/router`，应该是项目对 React Router 创建逻辑的封装；依据是所有 SPA entry 都通过它把 `RouteObject[]` 转成 RouterProvider 可用的 router。

下游主要是 `src/routes/**`。路由配置里的动态导入路径大量指向：

- `@/routes/(main)/agent`
- `@/routes/(main)/group`
- `@/routes/(main)/community`
- `@/routes/(main)/settings`
- `@/routes/(main)/memory`
- `@/routes/(main)/image`
- `@/routes/(main)/page`
- `@/routes/(mobile)/chat`
- `@/routes/(mobile)/(home)`
- `@/routes/(popup)`

这些 `routes` 文件应该保持“薄入口”角色，只做页面段和布局组合。更深层的业务状态、列表、表单、侧边栏、详情页组件等，应由 `src/features/**` 承担。

路由元信息的下游读取方包括 `src/features/RouteMeta/RouteMetaBridge.tsx`。当前片段显示它会调用 `getRouteMetaFromHandle(match.handle)`，说明 React Router 当前匹配链中的 `handle.meta` 会被桥接到某个上层 UI 状态或导航标题系统里。

此外，路由配置还从多个业务模块导入现成 meta：

- `@/features/AgentTasks/routeMeta`
- `@/features/Pages/routeMeta`
- `@/routes/(main)/agent/features/routeMeta`
- `@/routes/(main)/agent/features/topicPageRouteMeta`
- `@/routes/(main)/group/features/routeMeta`
- `@/routes/(main)/settings/features/routeMeta`
- `@/features/RouteMeta/mobileRouteMeta`

这表明 `src/spa/router` 不自己计算所有标题和图标，而是把业务域提供的 route meta 绑定到对应路由节点。

## 运行/调用流程

Web 入口的流程大致是：

1. 浏览器加载 `src/spa/entry.web.tsx`。
2. 入口 import `desktopRoutes`。
3. 入口根据是否处于 debug proxy，决定 `basename` 是否为 `/_dangerous_local_dev_proxy`。
4. 调用 `createAppRouter(desktopRoutes, { basename })`。
5. 渲染 `<RouterProvider router={router} />`。
6. React Router 根据当前 URL 匹配 `desktopRoutes`。
7. 命中的 route 通过 `dynamicElement` 或 `dynamicLayout` 加载 `src/routes/**` 页面段。
8. 页面段再组合 `src/features/**` 的业务组件。

Electron desktop 入口类似，但 `entry.desktop.tsx` 没有 debug proxy basename 逻辑，直接使用 `desktopRoutes`。

Mobile 入口的流程是：

1. `src/spa/entry.mobile.tsx` import `mobileRoutes`。
2. 调用 `createAppRouter(mobileRoutes)`。
3. 用 `<RouterProvider>` 挂载。
4. 当前移动端 URL 匹配 `mobileRoutes`。
5. 加载 `src/routes/(mobile)/**` 或部分共享的 `src/routes/(main)/**` 页面段。

Popup 入口的流程更简单：

1. `src/spa/entry.popup.tsx` import `popupRoutes`。
2. 创建 router。
3. 路径必须落在 `/popup` 下。
4. 根据 `agent/:aid/:tid`、`agent/:aid`、`group/:gid/:tid` 进入对应弹窗会话页。
5. 未匹配路径会通过 `redirectElement('/popup')` 回到 popup 根路径。

路由元信息的运行链路是：

1. 配置文件在某些 route 上声明 `handle: { meta: routeMeta(...) }`。
2. React Router 匹配 URL 后，匹配结果中包含 route `handle`。
3. `RouteMetaBridge` 这类上层组件读取 `match.handle`。
4. `getRouteMetaFromHandle` 从 `handle` 中提取 `meta`。
5. UI 根据 `titleKey`、`icon`、动态标题或头像等渲染导航信息。

## 小白阅读顺序

建议先从入口读，而不是直接扎进 800 行桌面路由：

1. 先读 `src/spa/entry.web.tsx`、`entry.mobile.tsx`、`entry.desktop.tsx`、`entry.popup.tsx`，理解“不同入口 import 不同 routes，然后交给 RouterProvider”。
2. 再读 `src/spa/router/routeMeta.ts`，理解路由除了页面组件，还能携带 `handle.meta`。
3. 然后读 `popupRouter.config.tsx`。它最短，能快速看懂 `RouteObject[]`、`children`、`path`、`element`、`errorElement` 的基本形状。
4. 再读 `mobileRouter.config.tsx`。它中等复杂，能看到移动端主布局、嵌套路由、动态导入、共享任务 workspace。
5. 最后读 `desktopRouter.config.tsx`。桌面路由最长，建议按一级 path 分块看，例如 `agent`、`group`、`community`、`resource`、`settings`、`memory`、`image`、`eval`、`page`、home fallback。
6. 读完异步桌面配置后，再对照 `desktopRouter.config.desktop.tsx`。重点不是逐行背，而是确认它和异步配置表达的是同一棵路由树。
7. 最后看 `desktopRouter.sync.test.tsx` 和 `mobileRouter.test.tsx`，理解哪些结构是项目明确要求不能漂移的。

## 常见误区

第一，容易把 `src/spa/router` 当成页面实现目录。它不是。这里应该只维护路由树和路由元信息绑定，复杂 UI 不应放进来。

第二，容易只改 `desktopRouter.config.tsx`，忘记 `desktopRouter.config.desktop.tsx`。这是高风险错误。桌面路由有异步配置和同步配置两份，测试明确要求 path、index 数量、`handle.meta` 保持一致。新增、删除、移动桌面 route 时，两边通常要一起改。

第三，容易以为 `src/routes` 是业务组件目录。按照当前仓库约定，`src/routes` 是 roots，只放 `_layout/index.tsx`、`index.tsx`、动态段入口等页面段文件；业务逻辑和复杂 UI 应放在 `src/features`。

第四，容易误解 `handle.meta` 只是装饰字段。实际上它会被 `RouteMetaBridge` 读取，影响导航标题、图标、动态标签页信息等。如果新增页面但漏了 meta，页面可能能打开，但上层导航体验会缺失。

第五，容易以为 mobile 路由只能引用 `src/routes/(mobile)`。当前 `mobileRouter.config.tsx` 已经复用了部分 `src/routes/(main)`，尤其是 task workspace 相关页面。是否复用取决于业务页面是否跨端共享，而不是目录名本身。

第六，容易忽略 `index: true` 的作用。嵌套路由中父级 path 命中后，如果没有继续的子路径，会进入 `index` 子路由。桌面同步测试还会比较两份配置里的 `index: true` 数量，说明默认子路由结构也是一致性要求的一部分。

第七，容易把 `popupRouter.config.tsx` 当作桌面主路由的一部分。它是独立 popup SPA 入口，路径根是 `/popup`，页面形态也和主应用不同，主要用于单会话窗口。
