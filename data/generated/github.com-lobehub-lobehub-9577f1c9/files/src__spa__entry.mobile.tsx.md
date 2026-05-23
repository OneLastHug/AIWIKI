# 文件：src/spa/entry.mobile.tsx

## 一句话定位

`src/spa/entry.mobile.tsx` 是移动端 Web SPA 的浏览器启动入口：它完成全局初始化，基于 `mobileRoutes` 创建 React Router 实例，并把整个移动端应用挂载到页面的 `#root` 节点。

## 它暴露/定义了什么

这个文件没有导出 API，也没有定义可复用组件。它定义了一个局部常量 `router`：

```ts
const router = createAppRouter(mobileRoutes);
```

随后直接执行 React 19 的 `createRoot(...).render(...)`。因此它更像“启动脚本”而不是业务模块，职责是把移动端路由配置和 React 渲染入口连接起来。

文件顶部的 `import '../initialize'` 是副作用导入，会在应用渲染前执行全局初始化逻辑。根据 `src/initialize.ts`，这些初始化包括启用 `immer` patch 与 Map/Set 支持、注册 `dayjs` 插件、监听 Vite chunk 加载失败、开发环境启用 `react-scan`。

## 谁调用它

根据当前片段推断，它不是被业务代码手动 import 的模块，而是由构建/运行时作为移动端 SPA 的入口文件加载。依据是它位于 `src/spa/`，同目录存在 `entry.web.tsx`、`entry.desktop.tsx`、`entry.popup.tsx` 这类平台入口；同时项目约定 `src/spa/entry.mobile.tsx` 对应移动端 SPA entry。

页面 HTML 或 Vite/Next 侧的 SPA 模板会加载对应 entry，entry 再接管浏览器里的 `#root` 容器。这个文件假设 DOM 中一定存在 `id="root"` 的节点，因此使用了非空断言 `document.getElementById('root')!`。

## 它调用谁

它直接依赖四类对象。

第一，`../initialize`：应用级副作用初始化，必须先于 React 渲染执行。

第二，`react-dom/client` 的 `createRoot`：创建 React 根节点。

第三，`react-router-dom` 的 `RouterProvider`：把 data router 注入 React 组件树，让后续页面通过 React Router 工作。

第四，`@/utils/router` 的 `createAppRouter` 与 `src/spa/router/mobileRouter.config.tsx` 的 `mobileRoutes`：前者负责把路由数组包装成真正的 browser router，后者声明移动端页面树。

间接调用链更重要：`createAppRouter` 会使用 `createBrowserRouter`，并额外包上一层 `RouterRoot`。`RouterRoot` 内部挂载 `SPAGlobalProvider`、`BusinessGlobalProvider`、`NavigatorRegistrar` 和 `Outlet`。所以虽然 `entry.mobile.tsx` 看起来只有几行，但它触发了全局 Provider、业务 Provider、全局导航引用注册和移动端路由渲染。

## 核心流程

启动顺序可以概括为五步。

第一步，执行 `src/initialize.ts` 的副作用初始化，准备全局运行环境和 chunk 加载错误兜底。

第二步，导入 `mobileRoutes`。这是一棵 `RouteObject[]` 路由树，覆盖移动端聊天、社区、设置、任务、个人中心、首页、onboarding、分享页，以及业务侧注入的 `BusinessMobileRoutesWithMainLayout`、`BusinessMobileRoutesWithoutMainLayout`。

第三步，调用 `createAppRouter(mobileRoutes)`。该函数会把移动端路由作为根路由的 children，并统一加上 `RouterRoot` 和根级 `ErrorBoundary`。

第四步，通过 `createRoot(document.getElementById('root')!)` 获取 React 挂载点。这里没有容错逻辑，说明 `#root` 是否存在由外层 HTML 模板保证。

第五步，渲染 `<RouterProvider router={router} />`。从这一刻开始，React Router 根据当前 URL 匹配 `mobileRoutes`，再通过 `dynamicElement`、`dynamicLayout` 懒加载具体 route 页面或 layout。

## 关键函数的高层作用

`createAppRouter` 是这个入口最关键的依赖。它不只是简单调用 `createBrowserRouter`，还为所有 SPA 路由统一套上 `SPAGlobalProvider` 和 `BusinessGlobalProvider`，并通过 `NavigatorRegistrar` 把 React Router 的 `navigate` 同步到全局 store，供应用内命令式导航使用。

`mobileRoutes` 是移动端页面结构的来源。它负责声明 URL path、嵌套路由、layout、错误页、重定向和 route meta。入口文件不关心任何页面细节，只把这棵配置树交给 router。

`RouterProvider` 是 React Router 的渲染桥梁。没有它，`mobileRoutes` 创建出来的 router 不会进入 React 组件树，所有 route component、`Outlet`、`useNavigate` 等能力也无法工作。

`createRoot` 是 React DOM 的启动点。它决定应用挂在哪个 DOM 容器下，但不参与路由或业务初始化。

## 修改风险

这个文件虽然短，但属于高风险入口文件。修改它会影响整个移动端 Web SPA 的启动，而不是单个页面。

最主要风险是删除或移动 `import '../initialize'`。这会让 `immer`、`dayjs`、chunk error 监听、开发扫描等全局行为失效或延后，问题可能表现为状态更新异常、日期能力缺失、懒加载失败时无提示。

第二个风险是替换或绕过 `createAppRouter`。如果直接使用 `createBrowserRouter(mobileRoutes)`，会丢失 `SPAGlobalProvider`、`BusinessGlobalProvider`、`NavigatorRegistrar` 和根级 `ErrorBoundary`，导致主题、业务上下文、全局导航和错误处理出现隐性故障。

第三个风险是改错路由配置来源。移动入口必须使用 `mobileRoutes`，不能误接 `desktopRoutes` 或 popup routes，否则移动端 URL、layout、页面动态导入和 route meta 都会错位。

第四个风险是随意添加 `basename`。对比 `src/spa/entry.web.tsx`，桌面/网页入口会处理 debug proxy basename，而当前移动入口没有传入 basename。根据当前片段推断，这是有意保持移动端根路径行为；若新增 basename，需要同步确认移动端 SPA 模板、部署路径、分享页和 onboarding 入口是否都匹配。

第五个风险是改变 `#root` 挂载假设。这里使用非空断言，说明入口不处理缺失容器。若 HTML 模板变更导致 `#root` 不存在，应用会在启动阶段直接抛错，错误边界也无法接管。
