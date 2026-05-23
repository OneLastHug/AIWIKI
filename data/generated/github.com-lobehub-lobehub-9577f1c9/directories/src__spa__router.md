# 子系统：src/spa/router

## 解决什么问题

`src/spa/router` 负责把整个 SPA 的页面入口、布局层级、路由参数、错误边界和路由元信息组织起来，统一交给 `react-router-dom` 使用。这里不是“页面实现”本身，而是“页面怎么被装配出来”的控制层。它解决的核心问题有三个：一是按桌面、移动端、弹窗三种运行形态拆分路由；二是把 `handle.meta` 这类路由元数据标准化，供导航、标题、图标、动态新标签页等能力消费；三是保证桌面异步路由配置和 Electron 同步路由配置一致，避免出现白屏或路径漂移。

## 相关目录和文件

最核心的是 `src/spa/router/desktopRouter.config.tsx`、`src/spa/router/desktopRouter.config.desktop.tsx`、`src/spa/router/mobileRouter.config.tsx`、`src/spa/router/popupRouter.config.tsx`。其中 desktop 有两份配置：一份偏 Web/异步加载，一份偏 Electron/同步加载。

`src/spa/router/routeMeta.ts` 定义了路由元数据的数据结构和读取工具，像 `RouteMeta`、`ResolvedRouteMeta`、`getRouteMetaFromHandle` 都在这里。`desktopRouter.sync.test.tsx` 和 `mobileRouter.test.tsx` 是这个目录的防回归约束，前者校验 desktop 双配置的路径和 `handle.meta` 是否一致，后者校验移动端任务路由是否沿用了共享工作区布局。

根据当前片段推断，上游还会依赖 `src/spa/entry.web.tsx`、`src/spa/entry.mobile.tsx`、`src/spa/entry.desktop.tsx`、`src/spa/entry.popup.tsx` 来选择不同的路由树；下游则是 `src/routes/**` 下的页面和布局组件，以及 `src/features/**` 中承载业务逻辑的特性模块。

## 核心对象

`desktopRoutes`、`mobileRoutes`、`popupRoutes` 是三个入口级路由树，都是 `RouteObject[]`。它们的节点普遍由三类信息组成：`element` 负责渲染页面或布局，`children` 负责嵌套路由，`handle.meta` 负责路由附加信息。`dynamicElement`、`dynamicLayout`、`redirectElement`、`ErrorBoundary` 则是路由装配时的关键辅助函数和兜底组件。

`routeMeta(meta)` 是一个轻量封装，用来显式标记“这里声明的是路由元数据”。`RouteMeta` 不只包含静态标题和图标，还支持 `createNewTab`、`useDynamicMeta`，说明这个系统不仅用于导航，还服务于动态内容页、二级入口页和“新建标签页”这类交互。

## 运行流程

启动后，SPA 入口会按平台选择对应路由配置。桌面端大多先进入 `desktopRoutes`，再按 `agent`、`group`、`community`、`settings`、`page`、`resource`、`memory` 等一级分支继续分发。移动端使用 `mobileRoutes`，但会复用大量 `src/routes/(main)` 的页面模块，只是在布局和导航结构上做了移动适配。弹窗场景则走 `popupRoutes`，它更像一个独立的单会话窗口，只保留最小必要的会话页面。

路由节点上的 `handle.meta` 会被后续导航栏、面包屑、标题栏或新标签页逻辑读取。`routeMeta.ts` 提供统一的提取函数，避免各处手写解析 `handle`。桌面双配置之间还有测试保证：异步版和同步版必须在路径、索引路由数量、`handle.meta` 声明上保持一致。

## 上下游依赖

上游依赖主要是应用运行环境和入口层：Next.js/SPA 启动器选择哪套 router 配置，Electron 是否需要同步导入，决定了这里的装配方式。它还依赖 `lucide-react` 图标、`react-router-dom` 的路由模型，以及 `@/utils/router` 中的动态加载和重定向工具。

下游依赖更广，几乎覆盖全部页面目录：`src/routes/(main)/**`、`src/routes/(mobile)/**`、`src/routes/(desktop)/**`、`src/routes/(popup)/**`。业务元信息则来自 `src/features/AgentTasks/routeMeta`、`src/features/Pages/routeMeta`、`src/features/RouteMeta/mobileRouteMeta`，以及各业务页自己导出的 `routeMeta`。`BusinessDesktopRoutesWithMainLayout`、`BusinessDesktopRoutesWithoutMainLayout`、`BusinessMobileRoutesWithMainLayout`、`BusinessMobileRoutesWithoutMainLayout` 说明这个子系统还承担“哪些业务路由挂在哪个主布局下”的编排责任。

## 修改时最容易踩的坑

最常见的问题是只改了 `desktopRouter.config.tsx`，忘了同步 `desktopRouter.config.desktop.tsx`。这两份配置必须保持路径、索引路由和 `handle.meta` 一致，否则 Electron 和 Web 会出现行为不一致。第二类坑是把页面逻辑塞进 router 文件里，破坏了“路由只做装配”的边界，后续维护会变得很难。第三类坑是新增路由后忘记补 `routeMeta` 或 handle 结构，导致导航标题、图标或动态标签页信息缺失。第四类坑是移动端和桌面端复用同一页面时，没有检查布局差异，容易在 `mobileRouter.config.tsx` 中留下不合适的桌面布局依赖。

## 推荐阅读顺序

先看 `src/spa/router/routeMeta.ts`，理解这套路由元信息的基本协议。再看 `src/spa/router/desktopRouter.config.tsx`，把桌面端主路由树和业务分支看一遍。然后对照 `src/spa/router/desktopRouter.config.desktop.tsx`，理解 Electron 同步配置为什么必须单独存在。接着看 `src/spa/router/mobileRouter.config.tsx` 和 `src/spa/router/popupRouter.config.tsx`，补全其他运行形态。最后读 `desktopRouter.sync.test.tsx`、`mobileRouter.test.tsx`，你会更清楚这个目录最在意什么边界和一致性。
