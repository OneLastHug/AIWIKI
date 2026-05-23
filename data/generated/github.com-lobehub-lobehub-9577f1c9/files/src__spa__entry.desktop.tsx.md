# 文件：src/spa/entry.desktop.tsx

## 一句话定位

`src/spa/entry.desktop.tsx` 是 Electron 桌面端 SPA 的 React 启动入口：它把桌面端路由表 `desktopRoutes` 转成 `react-router-dom` 可运行的 router，并挂载到 HTML 中的 `#root` 节点。

## 它暴露/定义了什么

这个文件不导出组件、函数或类型，而是一个“入口副作用模块”。它在被打包器加载时直接执行初始化逻辑：

1. 引入 `../initialize`，触发全局初始化副作用。
2. 用 `createAppRouter(desktopRoutes)` 创建桌面端路由实例。
3. 用 `createRoot(...).render(...)` 将 `<RouterProvider />` 挂到 DOM。

因此它的职责不是提供业务 API，而是完成桌面端运行时的首屏启动。

## 谁调用它

直接调用方不是业务代码，而是桌面端 HTML/构建入口。当前上下文中 `apps/desktop/index.html` 通过 `<script type="module" src="../../src/spa/entry.desktop.tsx">` 加载它。也就是说，在 Electron 桌面窗口打开并加载该 HTML 后，浏览器环境会执行这个 TypeScript/React 入口。

根据当前片段推断，Vite 或 Electron 桌面构建链会把这个入口作为 renderer 侧的应用入口处理；依据是它位于 `src/spa/entry.*.tsx` 入口族中，并且 `entry.web.tsx`、`entry.desktop.tsx` 都采用同样的 React Router 挂载模式。

## 它调用谁

它直接依赖这些模块：

`../initialize`：应用级初始化入口，通常用于设置全局环境、polyfill、样式、监控或运行前配置。该文件只引入不取值，说明它依靠模块副作用。

`react-dom/client` 的 `createRoot`：创建 React 19 的根节点渲染器。

`react-router-dom` 的 `RouterProvider`：把 router 注入 React 组件树，驱动后续页面匹配、导航和懒加载。

`@/utils/router` 的 `createAppRouter`：把项目声明式路由配置包装成实际 router。根据当前片段推断，它还承载项目自定义的路由增强逻辑，例如错误边界、动态组件封装或 router 创建参数。

`./router/desktopRouter.config` 的 `desktopRoutes`：桌面端主路由树，包含 agent、group、discover、settings 等页面的路径、layout、懒加载组件和 route meta。

## 核心流程

启动流程很短，但处在应用生命周期最前面。

第一步，执行 `../initialize`。这一步发生在任何 React 渲染之前，因此适合放置必须先于 UI 运行的全局初始化。如果这里失败，后续 router 和页面通常不会正常启动。

第二步，读取 `desktopRoutes`，调用 `createAppRouter(desktopRoutes)`。`desktopRoutes` 是声明式 `RouteObject[]`，其中大量页面通过 `dynamicElement`、`dynamicLayout` 懒加载；入口文件本身不关心具体页面，只把整棵路由树交给统一 router 工厂。

第三步，查找 DOM 节点 `document.getElementById('root')!`，创建 React root，并渲染 `<RouterProvider router={router} />`。从这一刻开始，当前 URL 会交给 React Router 匹配，匹配到的 layout/page 再按需加载 `src/routes/` 下的页面段。

值得注意的是，`entry.desktop.tsx` 与 `entry.web.tsx` 非常接近，但桌面入口没有包 `BootErrorBoundary`，也没有设置 debug proxy 的 `basename`。这说明桌面端启动环境更固定，路径基准由 Electron 本地 HTML/窗口环境控制；Web 入口则需要兼容线上调试代理路径。

## 关键函数的高层作用

`createAppRouter` 是这个入口里最关键的项目函数。它把 `desktopRoutes` 这种项目内声明式路由配置转换为 React Router 实例，是路由系统和页面代码之间的连接点。入口文件通过它避免直接调用底层 router 创建 API，从而让项目可以在统一位置处理路由增强策略。

`createRoot(...).render(...)` 是 React 应用挂载点。这里的非空断言 `!` 表示代码假设 HTML 一定存在 `id="root"` 的节点；如果桌面 HTML 模板改动导致该节点缺失，会在启动阶段直接失败。

`RouterProvider` 是运行期路由容器。它本身不定义页面，只消费 `router`，并负责根据导航状态渲染当前匹配的 route element。

辅助层面，`desktopRoutes` 是真正决定桌面端可访问页面结构的配置；`../initialize` 是启动前置副作用。入口文件只负责把这些拼接起来。

## 修改风险

最大风险是把桌面端入口和 Web 入口的环境差异混在一起。比如直接照搬 `entry.web.tsx` 的 debug proxy `basename`，可能让 Electron 内部路由路径变形，导致刷新、深链、标签页恢复或窗口导航异常。

第二个风险是误改 `desktopRoutes` 的来源。当前入口使用 `src/spa/router/desktopRouter.config`，而项目还要求 `desktopRouter.config.tsx` 和 `desktopRouter.config.desktop.tsx` 保持同步。虽然本文件只引用前者，但桌面构建、测试或其他 Electron 功能也会读取桌面路由配置；只改入口引用可能掩盖同步问题，最终表现为空白屏或路由元信息不一致。

第三个风险是删除或延后 `../initialize`。由于这是全局前置初始化，具体影响不一定在本文件显现，可能在主题、国际化、客户端配置、监控、Electron bridge 或运行时 feature flag 中延迟爆出。

第四个风险是改动挂载节点假设。`document.getElementById('root')!` 和 `apps/desktop/index.html` 必须配套；如果 HTML 模板中的 root 节点名称变化，本文件也要同步调整。

最后，给入口增加业务逻辑要谨慎。这个文件应该保持薄入口定位，复杂的错误边界、provider 组合、环境分支或路由策略更适合放到统一 layout、router 工厂或初始化模块中，否则会让桌面端和 Web/mobile/popup 入口逐渐分叉，增加启动问题排查成本。
