# 文件：src/utils/router.tsx

## 一句话定位

这是整个 SPA 的路由基础工具层，负责把 React Router 的路由树、懒加载、错误边界、全局导航引用和部分路由预取能力统一收口，供 `src/spa/*` 的入口与各路由配置复用。根据当前片段推断，它是桌面端、移动端和 popup 这些不同入口共享的“路由底座”。

## 它暴露/定义了什么

它主要定义了 5 类能力：

1. `dynamicElement()`：把动态 `import()` 包装成可直接放进路由配置里的页面元素。
2. `dynamicLayout()`：和上面类似，但语义上用于 layout。
3. `ErrorBoundary`：路由级错误边界，专门处理 chunk 加载失败等异常。
4. `createAppRouter()`：创建带根布局和根错误边界的 `createBrowserRouter()` 实例。
5. `redirectElement()`、`NavigatorRegistrar`、`prefetchRoute()`：分别用于声明式重定向、把 `navigate` 写入全局 store、预取常用路由 chunk。

## 谁调用它

直接调用点很集中：

- `src/spa/entry.web.tsx`、`src/spa/entry.mobile.tsx`、`src/spa/entry.desktop.tsx`、`src/spa/entry.popup.tsx` 用 `createAppRouter()` 创建路由实例。
- `src/spa/router/desktopRouter.config.tsx`、`src/spa/router/mobileRouter.config.tsx`、`src/spa/router/popupRouter.config.tsx` 用 `dynamicElement()`、`dynamicLayout()`、`ErrorBoundary`、`redirectElement()` 组装路由树。
- `src/routes/(main)/home/_layout/Header/components/Nav.tsx`、`Footer/index.tsx`、`Body/index.tsx` 等导航类组件调用 `prefetchRoute()`，提前加载用户下一步可能进入的页面。

## 它调用谁

它依赖的外部模块也很明确：

- `react-router-dom`：`createBrowserRouter`、`Navigate`、`Outlet`、`useNavigate`、`useRouteError`、`RouteObject`。
- `@lobehub/ui` 的 `ThemeProvider`：给错误页补齐主题上下文。
- `@/layout/SPAGlobalProvider`、`@/business/client/BusinessGlobalProvider`：作为路由根包裹全局业务环境。
- `@/store/global`、`@/store/global/initialState`：写入和重置 `navigationRef`。
- `@/utils/chunkError`：识别 chunk 失败并触发统一通知。
- `@/components/Loading/BrandTextLoading`、`@/components/Error`：分别作为懒加载和错误页展示。

## 核心流程

核心链路可以按“入口启动 -> 路由创建 -> 根组件挂载 -> 页面加载/导航/异常处理”理解：

1. 各入口在启动时调用 `createAppRouter(desktopRoutes, { basename })`。
2. 这个函数创建一个以 `RouterRoot` 为根节点的 browser router。
3. `RouterRoot` 先挂 `SPAGlobalProvider` 和 `BusinessGlobalProvider`，再挂 `NavigatorRegistrar`，最后用 `Outlet` 渲染具体页面。
4. 路由配置里通过 `dynamicElement()` / `dynamicLayout()` 把页面和布局拆成懒加载 chunk，首屏和跳转时由 `Suspense` + `Loading` 托底。
5. 一旦路由渲染出错，`ErrorBoundary` 兜底；如果是 chunk 失败，它还会触发 `notifyChunkError()`。
6. 导航相关代码通过 `prefetchRoute()` 预热 `/agent`、`/community`、`/group`、`/page`、`/resource`、`/settings` 这几类常用布局 chunk，减少首次跳转等待。

## 关键函数的高层作用

- `dynamicElement()`：把“页面组件的动态导入”变成可直接放进 `element` 的 React 元素，核心价值是减少路由配置样板代码。
- `dynamicLayout()`：和 `dynamicElement()` 结构相同，但表达“这是一个布局”，便于路由树阅读和维护。
- `NavigatorRegistrar`：在组件挂载时把 React Router 的 `navigate` 同步到全局 store，让非路由组件也能通过稳定引用做命令式跳转。
- `createAppRouter()`：统一所有 SPA 入口的 router 创建方式，确保根 provider、错误边界和 `basename` 行为一致。
- `prefetchRoute()`：按首个 path segment 做一次性预取，避免重复请求同一个路由 chunk。
- `ErrorBoundary`：把路由错误转换成用户可见的错误页，并对 chunk 类错误做额外通知。

## 修改风险

这个文件的改动风险比较高，因为它是全局路由基础设施，影响面不是单个页面，而是整个 SPA：

- 改 `dynamicElement()` / `dynamicLayout()` 可能影响所有懒加载页面的 Suspense 行为和错误表现。
- 改 `RouterRoot` 的 provider 顺序，可能破坏业务上下文或导航引用初始化。
- 改 `NavigatorRegistrar` 会直接影响 `useStableNavigate`、`stableNavigate` 这条全局跳转链。
- 改 `prefetchRoute()` 的映射或 key 规则，可能让导航预取失效或重复加载。
- 改 `createAppRouter()` 的根结构或 `basename`，可能导致桌面、移动端、debug proxy 入口路径异常。
- 如果路由路径本身变化，还要同步检查 `src/spa/router/desktopRouter.config.tsx` 和 `src/spa/router/desktopRouter.config.desktop.tsx`，否则容易出现某些构建路径下的空白页。
