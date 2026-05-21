# 目录：src/spa

## 它负责什么

`src/spa` 是 LobeHub 前端 SPA 的“启动与路由装配层”。它不直接实现聊天、设置、发现、页面编辑等业务功能，而是负责在不同运行形态下选择对应的 React Router 路由树，并把它挂载到页面根节点 `#root`。

从目录结构看，它主要服务四类入口：

- `entry.web.tsx`：Web SPA 入口，使用桌面路由树 `desktopRoutes`。
- `entry.desktop.tsx`：Electron/Desktop SPA 入口，也使用 `desktopRoutes`。
- `entry.mobile.tsx`：移动端 SPA 入口，使用 `mobileRoutes`。
- `entry.popup.tsx`：桌面弹窗入口，使用 `popupRoutes`。

这些入口都先导入 `../initialize`，再通过 `createRoot(...).render(...)` 渲染 `<RouterProvider router={router} />`。因此，`src/spa` 的职责可以概括为：初始化运行环境，创建路由实例，挂载对应平台的 SPA。

## 关键组成

`src/spa/entry.web.tsx` 是 Web 端入口。它导入 `desktopRoutes`，调用 `createAppRouter(desktopRoutes, { basename })` 创建路由。这里有一个特殊点：它会识别 `/_dangerous_local_dev_proxy`，当 `window.__DEBUG_PROXY__` 存在或当前路径以该代理路径开头时，把 `basename` 设置为 debug proxy 路径。这样本地 `dev:spa` 可以被线上代理页面加载，仍然让 React Router 正确解析路径。Web 入口还包了一层 `BootErrorBoundary`，用于启动阶段兜底。

`src/spa/entry.desktop.tsx` 与 `entry.mobile.tsx` 更直接：分别创建 `desktopRoutes` 和 `mobileRoutes` 的 router，然后渲染 `RouterProvider`。`entry.popup.tsx` 则使用 `popupRoutes`，面向桌面独立会话弹窗。

`src/spa/router/desktopRouter.config.tsx` 是桌面主路由配置，导出 `desktopRoutes: RouteObject[]`。它使用 `dynamicElement`、`dynamicLayout` 做动态导入和代码分割，路由目标主要指向 `src/routes/(main)`、`src/routes/share`、`src/routes/onboarding` 等页面段。它还引入了大量 `routeMeta`，例如 `agentRouteMeta`、`settingsRouteMeta`、`pageRouteMeta`、`tasksRouteMeta`，供导航、标题、新标签页等上层能力使用。

`src/spa/router/desktopRouter.config.desktop.tsx` 是桌面同步版路由配置。根据 `spa-routes` 约定，它必须和 `desktopRouter.config.tsx` 保持相同的路径、嵌套、index route 和 `handle.meta`。区别在于：前者偏动态导入，后者偏同步静态导入，服务 Electron/桌面构建下更可控的打包与运行。

`src/spa/router/mobileRouter.config.tsx` 导出 `mobileRoutes`。它注册移动端聊天、发现、设置、任务、首页、分享、onboarding 等路径。值得注意的是，移动端并不完全只引用 `src/routes/(mobile)`，它也会复用部分 `src/routes/(main)` 的页面实现，并通过 `.then((m) => m.MobileXxxPage)` 选取移动端导出的组件。

`src/spa/router/popupRouter.config.tsx` 导出 `popupRoutes`。它是一个很小的专用路由树，挂在 `/popup` 下，包含：

- `agent/:aid/:tid`
- `agent/:aid`
- `group/:gid/:tid`
- 兜底重定向到 `/popup`

它直接静态导入 `PopupLayout`、`PopupAgentQuickPage`、`PopupAgentTopicPage`、`PopupGroupTopicPage`，说明弹窗入口追求简单、确定、体积小的路由结构。

`src/spa/router/routeMeta.ts` 定义路由元信息类型，包括 `StaticRouteMeta`、`DynamicRouteMeta`、`RouteMeta`、`RouteHandle`、`ResolvedRouteMeta` 等。它还导出 `routeMeta(meta)` 和 `getRouteMetaFromHandle(handle)`。这些类型把 React Router 的 `handle.meta` 约束成项目可理解的数据结构，例如图标、标题 key、动态标题、头像、新标签创建行为等。

## 上下游关系

上游是 HTML/构建入口与初始化逻辑。`src/spa/entry.*.tsx` 被不同运行目标加载，入口统一导入 `../initialize`，说明应用级初始化发生在路由创建之前。

中游是 `@/utils/router`。当前片段显示 `src/spa` 依赖其中的：

- `createAppRouter`
- `dynamicElement`
- `dynamicLayout`
- `redirectElement`
- `ErrorBoundary`

根据当前片段推断，`createAppRouter` 是项目对 React Router 创建逻辑的统一封装；`dynamicElement` 和 `dynamicLayout` 用于把 `src/routes` 下的页面段包装成可 Suspense 加载的 route element；`redirectElement` 用于声明式重定向；`ErrorBoundary` 用于 route 级错误兜底。依据是这些工具被所有主路由配置集中使用，且 `rg` 结果显示它们统一定义在 `src/utils/router.tsx`。

下游是 `src/routes` 与 `src/features`。`src/spa/router/*.config.tsx` 只把 URL path 映射到 `src/routes/...` 的页面段；真正的页面布局、业务组件、store 使用和数据请求应继续下沉到 `src/features`、`src/store`、`src/services` 等位置。按照仓库约定，`src/routes` 是 roots，应该保持薄；`src/features` 才是业务 UI 和逻辑的主要承载处。

另外还有业务扩展入口：桌面与移动路由都导入了 `BusinessDesktopRoutesWithMainLayout`、`BusinessDesktopRoutesWithoutMainLayout` 或 `BusinessMobileRoutes...`。这说明商业版/企业版路由可以在主路由树中插入，但仍由 `src/spa` 统一装配。

## 运行/调用流程

Web 端大致流程是：

1. 浏览器加载 Web SPA bundle。
2. `entry.web.tsx` 执行 `import '../initialize'`。
3. 判断是否处于 debug proxy 路径。
4. 调用 `createAppRouter(desktopRoutes, { basename })`。
5. `createRoot(document.getElementById('root')!).render(...)`。
6. `RouterProvider` 根据当前 URL 匹配 `desktopRoutes`。
7. 命中的 route 通过 `dynamicElement` 或 `dynamicLayout` 加载 `src/routes/...` 模块。
8. `src/routes` 页面段继续组合 `src/features` 中的真实业务 UI。

Desktop 端类似，但 `entry.desktop.tsx` 不设置 debug proxy 的 `basename`，也没有额外包 `BootErrorBoundary`。它仍然使用 `desktopRoutes`，因此桌面主应用与 Web 桌面态共享大部分路由树。

Mobile 端从 `entry.mobile.tsx` 进入，创建 `mobileRoutes`。移动路由树有自己的顶层布局，例如 `@/routes/(mobile)/_layout`，也会在发现页、设置页等场景复用 main 路由下的组件导出。

Popup 端从 `entry.popup.tsx` 进入，只加载 `/popup` 下的轻量路由。它的目标不是完整主应用，而是“单会话窗口”：无侧边栏、无主 portal，只承载某个 agent/group topic。

测试侧的流程也很关键：`desktopRouter.sync.test.tsx` 会读取 `desktopRouter.config.tsx` 和 `desktopRouter.config.desktop.tsx` 的源码，比较 path、index route 数量和 `handle.meta` 声明。它允许少量已知差异，例如 `/desktop-onboarding` 对应 `/onboarding`。这类测试不是普通组件测试，而是在防止两份桌面路由树漂移。`mobileRouter.test.tsx` 则检查移动端任务路由是否挂在共享 workspace layout 下。

## 小白阅读顺序

建议先读 `src/spa/entry.web.tsx`。它最短，但包含 SPA 启动的完整骨架：初始化、创建 router、挂载 `RouterProvider`、处理 debug proxy。

第二步读 `src/spa/router/desktopRouter.config.tsx`。不要一开始逐行背完整路由树，而是先看它的形状：顶层 `desktopRoutes: RouteObject[]`，下面按 `agent`、`group`、`community`、`settings`、`tasks`、`page`、`share`、`onboarding` 等业务域组织。重点理解 `path`、`children`、`element`、`index`、`handle.meta`、`errorElement` 这几个字段。

第三步读 `src/spa/router/mobileRouter.config.tsx`，对比它和桌面路由的差异：移动端有自己的 layout 和部分页面，但也复用 main 路由中的 detail/list 页面导出。

第四步读 `src/spa/router/popupRouter.config.tsx`。它很小，适合理解一个独立 SPA 入口如何拥有自己的路由树。

第五步读 `src/spa/router/routeMeta.ts`。这能解释为什么路由里会挂 `handle: { meta: ... }`，以及导航标题、图标、动态 tab 信息大概从哪里来。

最后再看 `src/spa/router/desktopRouter.sync.test.tsx`。这份测试能帮助理解项目为什么维护两份桌面路由配置，以及改路由时必须同步更新的原因。

## 常见误区

第一个误区是把 `src/spa` 当成业务页面目录。实际上它是入口和路由装配层。新增聊天页、设置页、发现页 UI 时，不应该直接把复杂组件塞到 `src/spa`，而应放到 `src/routes` 页面段或更推荐的 `src/features` 业务域中。

第二个误区是只改 `desktopRouter.config.tsx`，忘记 `desktopRouter.config.desktop.tsx`。仓库明确要求两份桌面路由树保持同步；否则 Web 构建可能正常，Electron/Desktop 构建却出现空白页、路由缺失或导航元信息不一致。`desktopRouter.sync.test.tsx` 就是专门防这个问题的。

第三个误区是认为 `src/routes` 可以承载大量业务逻辑。按照当前约定，`src/routes` 是 roots，只应放 `_layout/index.tsx`、`index.tsx`、动态段页面等薄入口；复杂布局、列表、表单、动作、hooks 应放到 `src/features/<Domain>/`。

第四个误区是忽略 `handle.meta`。很多路由不只是“URL 到组件”的映射，还携带标题、图标、动态元信息、新标签行为等数据。改路径、移动页面或新增 route 时，如果漏掉 meta，可能页面能打开，但导航、tab 标题或新建标签能力异常。

第五个误区是混淆 Web、Desktop、Mobile、Popup 四种入口。`entry.web.tsx` 有 debug proxy basename 和 `BootErrorBoundary`；`entry.desktop.tsx` 共享桌面路由但运行在 Electron/Desktop 语境；`entry.mobile.tsx` 使用移动路由树；`entry.popup.tsx` 是轻量独立窗口。定位问题时应先确认当前 bundle 是从哪个 `entry.*.tsx` 进入的。
