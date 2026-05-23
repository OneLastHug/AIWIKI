# 文件：src/spa/entry.web.tsx

## 一句话定位

`src/spa/entry.web.tsx` 是 Web 端 SPA 的浏览器启动入口：它在页面里的 `#root` 节点上挂载 React 应用，创建桌面版 `react-router-dom` 路由实例，并用 `BootErrorBoundary` 兜住启动阶段错误。

## 它暴露/定义了什么

这个文件没有对外 `export` 任何 API，它的价值在于模块加载时产生副作用：初始化全局运行环境并完成应用渲染。

它定义了三个关键局部对象：

`debugProxyBase`：固定为 `/_dangerous_local_dev_proxy`，用于识别本地调试代理路径。

`basename`：根据 `window.__DEBUG_PROXY__` 或当前 `window.location.pathname` 是否以调试代理前缀开头来决定。命中时传给路由器，让 React Router 在代理路径下正确解析子路由；否则为 `undefined`。

`router`：由 `createAppRouter(desktopRoutes, { basename })` 创建，是 Web SPA 实际交给 `RouterProvider` 使用的路由对象。

## 谁调用它

它通常不是被业务代码直接 `import` 调用，而是作为 Web SPA 的构建入口被前端构建链加载。根据当前片段推断，Next.js 内的 SPA HTML 模板或 Vite 开发入口会把这个文件编译成浏览器脚本，浏览器加载脚本后执行该模块，从而触发 `createRoot(...).render(...)`。

判断依据是：同目录还存在 `entry.desktop.tsx`、`entry.mobile.tsx`、`entry.popup.tsx`，并且它们都采用类似的 `createRoot` + `RouterProvider` 模式，说明 `src/spa/entry.*.tsx` 是按运行场景拆分的 SPA 入口族。

## 它调用谁

首先它导入 `../initialize`，该模块负责全局初始化：启用 `immer` 的 patches 与 Map/Set 支持，注册 `dayjs` 插件，监听 Vite preload error 和未处理的 chunk load rejection，并在开发环境启用 `react-scan`。

然后它调用 React DOM 的 `createRoot`，把 React 应用挂到 `document.getElementById('root')!`。

路由方面，它调用 `@/utils/router` 中的 `createAppRouter`，传入 `src/spa/router/desktopRouter.config.tsx` 导出的 `desktopRoutes`。`desktopRoutes` 是桌面 Web 的声明式路由树，内部通过 `dynamicElement`、`dynamicLayout` 延迟加载 `src/routes/(main)` 等页面段，也会合入 `@/business/client/BusinessDesktopRoutes` 这类业务扩展路由。

渲染方面，它使用 `react-router-dom` 的 `RouterProvider` 接管路由渲染，并用 `@/components/BootErrorBoundary` 包裹整个 Router。

## 核心流程

模块加载后第一步执行 `../initialize` 的副作用，保证全局能力先于 React 应用启动完成注册。这里的顺序重要，因为 chunk load 监听、dayjs 插件、immer 设置都属于全局运行前置条件。

第二步计算 `basename`。正常线上或普通本地路径下，`basename` 为 `undefined`，路由按站点根路径工作；当处于 `/_dangerous_local_dev_proxy` 或 `window.__DEBUG_PROXY__` 环境时，`basename` 被设置为该代理前缀，避免 React Router 把代理前缀误当作业务路由的一部分。

第三步用 `desktopRoutes` 创建 app router。这个入口明确选择 `desktopRouter.config`，所以 Web 端默认承载的是桌面版 SPA 路由树，而不是 mobile、desktop Electron 或 popup 的入口路由。

第四步查找页面中的 `#root` DOM 节点，并渲染：

`BootErrorBoundary` 是最外层启动保护；`RouterProvider` 是实际应用壳，负责根据当前 URL 匹配 route object、加载 layout/page、处理路由嵌套与错误边界。

## 关键函数的高层作用

`createRoot` 是 React 19 客户端挂载入口，把静态 HTML 容器变成 React 管理的应用根。

`createAppRouter` 是项目封装的路由创建函数。根据当前片段推断，它大概率包装了 `react-router-dom` 的 router 创建能力，并统一接入项目级路由约定，例如动态导入、错误边界或 basename 配置。依据是 `desktopRoutes` 使用的是 `RouteObject[]`，并且入口只把路由树和 `basename` 交给它。

`RouterProvider` 负责运行 React Router 的路由实例，是后续所有 `src/routes/` 页面段能够显示的根调度器。

`BootErrorBoundary` 保护 SPA 首次启动。它在首次成功 mount 前捕获异常时，会尝试一次带缓存破坏参数的硬刷新，用来恢复资源缓存错配、旧 chunk 等启动期问题；成功 mount 后则清理刷新标记并重置尝试次数。

## 修改风险

不要轻易改变 `../initialize` 的导入顺序。它是纯副作用导入，移到渲染之后会让 chunk load 兜底、dayjs 插件或 immer 配置滞后，问题可能只在特定运行路径中出现。

`basename` 逻辑风险很高。`/_dangerous_local_dev_proxy` 是本地调试代理的路由基准，改错会导致调试代理下刷新、深链、跳转全部错位，表现为空白页或路由不匹配。

`desktopRoutes` 的来源也要谨慎。Web 入口当前使用 `desktopRouter.config.tsx`，而项目还有 `desktopRouter.config.desktop.tsx`，两者需要保持路由结构同步；随意切换或只改其中一个，会让不同构建目标出现行为漂移。

`document.getElementById('root')!` 假设 HTML 模板一定存在 `id="root"`。如果模板或服务端注入点改名，这里会在启动阶段直接崩溃，只能依赖 `BootErrorBoundary` 之外的浏览器错误信息定位。

不要把 `window` 相关逻辑抽到可能被服务端执行的模块。当前文件作为浏览器入口使用 `window` 是合理的，但若复用到 SSR、测试或共享工具层，会引入运行时环境错误。

最后，外层 `BootErrorBoundary` 不只是展示 fallback，它还承担启动期缓存恢复策略。删除或缩小它的包裹范围，会降低线上发布后旧资源与新路由代码不一致时的自恢复能力。
