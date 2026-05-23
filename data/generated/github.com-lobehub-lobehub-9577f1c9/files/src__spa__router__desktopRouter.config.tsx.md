# 文件：src/spa/router/desktopRouter.config.tsx

## 一句话定位
这是桌面端 SPA 的主路由注册表，负责把 `src/routes/` 下的页面段、布局段和少量全局入口拼成 `react-router-dom` 可消费的 `RouteObject[]`，再交给 `src/spa/entry.web.tsx` 和 `src/spa/entry.desktop.tsx` 创建桌面路由实例。根据当前片段推断，它还是桌面路由体系里“动态按需加载”的那一份配置，和 `desktopRouter.config.desktop.tsx` 保持同构。

## 它暴露/定义了什么
它主要导出 `desktopRoutes: RouteObject[]`。这个数组里定义了桌面端的完整路由树，包括 `agent`、`group`、`community`、`page`、`settings`、`devtools`、`resource`、`eval`、`memory`、`task`、`share` 以及 `onboarding` 等入口。每个节点会带上 `element`、`path`、`index`、`children`、`errorElement` 和 `handle.meta` 等信息，供路由渲染、导航元信息和错误边界使用。

## 谁调用它
直接调用方是 `src/spa/entry.web.tsx` 和 `src/spa/entry.desktop.tsx`，它们都会导入 `desktopRoutes` 并交给 `createAppRouter(...)` 创建运行时路由。间接上，`src/spa/router/desktopRouter.sync.test.tsx` 会校验它与 `desktopRouter.config.desktop.tsx` 的一致性，所以它也是测试约束的对象。

## 它调用谁
它依赖路由工具 `dynamicElement`、`dynamicLayout`、`redirectElement` 和 `ErrorBoundary`，这些来自 `@/utils/router`。它还调用大量具体路由模块，例如 `@/routes/(main)/agent`、`@/routes/(main)/group/_layout`、`@/routes/(main)/community/(list)/model`、`@/routes/(main)/page/_layout` 等。与此同时，它引用了一批路由元信息，如 `agentRouteMeta`、`pageRouteMeta`、`settingsRouteMeta`、`taskRouteMeta`，以及 `BusinessDesktopRoutesWithMainLayout`、`BusinessDesktopRoutesWithoutMainLayout` 这类业务桌面路由集合。

## 核心流程
这份文件的工作方式是“先搭骨架，再挂页面”。最外层先声明一个 `desktopRoutes` 数组，内部按业务域分块组织路由树：`agent` 相关路由有自己的布局和 topic 子路由，`group`、`community`、`page`、`settings` 等也是同样模式。页面和布局大多通过 `dynamicElement`、`dynamicLayout` 懒加载，以减少初始包体积；根路径或非法路径则用 `redirectElement('/')` 做跳转。每个重要页面还会挂 `handle.meta`，把图标和标题键交给上层导航系统。文件末尾再把一些业务桌面路由按条件追加进 `desktopRoutes`，并补上 `/onboarding` 等独立入口。

## 关键函数的高层作用
`dynamicElement` 负责把某个 `src/routes/...` 页面变成可懒加载的路由元素，适合页面级组件。`dynamicLayout` 做同样的事，但面向布局壳层，通常包着 `<Outlet />`。`redirectElement` 提供纯跳转路由，常用于默认页或非法入口回退。`ErrorBoundary` 则兜底路由加载和渲染错误，避免整个桌面壳层直接白屏。`handle.meta` 不是渲染逻辑，而是把路由标题、图标和导航信息附着在节点上，供别处消费。

## 修改风险
这类文件最怕“树结构漂移”。因为 `desktopRouter.config.tsx` 和 `desktopRouter.config.desktop.tsx` 必须保持同构，任何新增、删除、改名、改层级、改 `index/path` 的变动都要同步两份，否则容易出现某个构建入口找不到路由、导航不一致，甚至白屏。另一个风险是懒加载路径写错或布局层级挂错，问题往往只在运行时暴露。`handle.meta` 缺失会影响侧边栏和顶栏文案，`redirectElement` 放错位置会改变默认落点。若调整到 `BusinessDesktopRoutes*` 这类追加路由，还要注意顺序和条件分支，避免把全局入口覆盖掉或漏注册。
