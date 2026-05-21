# 目录：src

## 它负责什么

`src` 是 LobeHub 主应用的核心源码目录，承担“把产品跑起来”的大部分职责：既包含 Next.js App Router 相关入口，也包含 Vite/React Router 驱动的 SPA 前端；既有页面路由、业务组件、全局布局，也有客户端服务层、Zustand 状态层、服务端配置与工具函数。

从当前片段看，这个仓库不是传统“Next.js 页面都在 `src/app`”的单一路由结构，而是采用混合架构：`src/app` 负责 Next.js 后端、认证、SPA HTML 模板等入口；真正的主产品界面主要通过 `src/spa` 创建 React Router，并加载 `src/routes` 下的页面段，再组合 `src/features` 中的业务 UI 和逻辑。

可以把 `src` 理解为应用层总装车间：`packages/` 提供共享能力，`apps/` 提供桌面端、CLI 等外壳，而 `src` 把 Web、Desktop、Mobile、Popup、后端 API、状态管理、服务调用、样式、i18n 组织成一个完整产品。

## 关键组成

`src/app` 是 Next.js App Router 区域。根据目录结构，它包含 `(backend)`、`[variants]`、`spa` 等分支，通常用于后端 API、认证页面、SSR 相关页面和 SPA 宿主页。它更偏“Next.js 外壳与后端入口”，不是主业务页面的唯一来源。

`src/spa` 是 SPA 运行入口。典型文件包括 `entry.web.tsx`、`entry.mobile.tsx`、`entry.desktop.tsx`、`entry.popup.tsx`，分别对应不同运行形态。`entry.web.tsx` 中先导入 `../initialize`，再用 `createRoot` 渲染 `RouterProvider`，路由由 `createAppRouter(desktopRoutes)` 创建。它还处理了 Debug Proxy 的 `basename`，说明本地开发可以通过代理路径加载本地 SPA。

`src/spa/router` 是 React Router 配置区。`desktopRouter.config.tsx`、`desktopRouter.config.desktop.tsx`、`mobileRouter.config.tsx`、`popupRouter.config.tsx` 分别定义不同平台的路由树。桌面路由中大量使用 `dynamicElement`、`dynamicLayout` 懒加载 `src/routes` 下的页面段，并通过 `handle.meta` 挂载 `routeMeta`，例如 agent、group、settings、page、tasks 等页面元信息。

`src/routes` 是 SPA 页面段目录。它按运行形态和页面分组，例如 `(main)`、`(mobile)`、`(desktop)`、`(popup)`、`onboarding`。根据仓库规范，`routes` 应保持“薄”：主要提供 `_layout/index.tsx`、`index.tsx`、动态路由页面等，负责组合布局和引入 feature，不应该沉淀大量业务逻辑。当前片段中 `(main)/_layout/index.tsx` 是桌面主布局，组合了 `NavPanel`、`DesktopHomeLayout`、`Outlet`、热键、桌面桥接、CloudBanner、命令面板等全局能力。

`src/features` 是业务功能组件区，数量很多，例如 `AgentBuilder`、`Conversation`、`ChatInput`、`Pages`、`PageEditor`、`NavPanel`、`Setting`、`MCP`、`PluginDetailModal`、`RouteMeta` 等。它承接页面中的实际业务 UI、交互和局部逻辑。新读者应把它看作“产品功能模块库”。

`src/store` 是 Zustand 状态层。它按业务域拆分，如 `chat`、`agent`、`agentGroup`、`user`、`serverConfig`、`tool`、`file`、`task`、`page`、`electron` 等。以 `src/store/chat/store.ts` 为例，store 由 `initialState` 加多个 slices/actions 聚合而成，使用 `createWithEqualityFn`、`subscribeWithSelector`、`createDevtools`，并通过 `flattenActions` 把函数式 slice 和 class action 实例的方法合并成普通对象。`getChatStoreState` 提供非 React 场景读取状态的能力。

`src/services` 是客户端服务层，负责把 UI/store 的操作转为 API、SSE、导入导出、文件、插件、agent runtime、Electron IPC 等调用。比如 `services/config.ts` 的 `ConfigService.exportAll` 调用 `exportService.exportData()`，再根据返回的 `url` 或 `data` 下载/导出 JSON；`services/chat/index.ts` 中的 `ChatService` 则是聊天流式请求的重要入口，会读取 agent、chat、tool、user 等 store 状态，组装模型、工具、记忆、搜索配置和请求头。

`src/server` 是应用服务端能力区，包含 `globalConfig`、`runtimeConfig`、`featureFlags`、`manifest`、`metadata`、`sitemap`、`translation`、`workflows-hono`、`agent-hono` 等。它更接近 Next.js 后端和运行时配置的服务逻辑。

其他常见基础层包括：`src/components` 放跨业务复用组件；`src/hooks` 放 React hooks；`src/layout` 放全局 Provider/Layout；`src/config`、`src/const`、`src/envs` 放配置、常量和环境变量解析；`src/libs` 封装第三方或基础库适配；`src/utils`、`src/helpers` 放通用工具；`src/locales` 放 i18n 文案；`src/styles` 放全局样式入口；`src/types` 放应用级类型。

## 上下游关系

上游看，`src` 依赖大量仓库内共享包和外部库。代码中可见 `@lobechat/const`、`@lobechat/types`、`@lobechat/model-runtime`、`@lobechat/fetch-sse`、`@lobehub/ui`、`@lobechat/utils` 等包；UI 层依赖 React、React Router、lucide-react、antd-style；状态层依赖 Zustand；服务层会调用内部 API endpoint、SSE、导入导出和运行时能力。

下游看，`src` 被不同运行入口消费：Web SPA、Mobile SPA、Desktop Electron、Popup、小程序式窗口、Next.js 后端路由等。`apps/desktop` 这类外壳会通过桥接能力和 `src/features/Electron`、`src/services/electron`、`src/store/electron` 互动。浏览器端主应用则从 `src/spa/entry.*.tsx` 进入。

内部调用链通常是：`src/spa/router` 定义路由，路由加载 `src/routes`，页面段组合 `src/features`，feature 读取/更新 `src/store`，store action 调用 `src/services`，services 再访问 API、SSE、Electron bridge 或其他运行时。服务端相关请求会落到 `src/app/(backend)` 或 `src/server` 组织的能力上。根据当前片段推断，`src/business` 还提供商业版或定制能力的路由/逻辑注入，例如 `BusinessDesktopRoutesWithMainLayout`、`BusinessDesktopRoutesWithoutMainLayout` 被桌面路由配置引用。

## 运行/调用流程

Web 主入口以 `src/spa/entry.web.tsx` 为例：先执行 `src/initialize.ts` 做全局初始化；随后创建 `desktopRoutes` 对应的 router；最后把 `RouterProvider` 渲染到 DOM 的 `#root`。如果处于 `_dangerous_local_dev_proxy` 调试代理路径，会设置对应 `basename`，保证本地 Vite SPA 能挂在代理路径下运行。

路由匹配后，`desktopRouter.config.tsx` 会按路径懒加载页面。例如 `/agent/:aid` 下会加载 agent 相关 layout 和页面，`/group/:gid` 加载 group 页面，discover/settings/page/tasks 等也在路由树中声明。`dynamicElement` 和 `dynamicLayout` 让页面代码分块加载，`ErrorBoundary` 提供错误兜底。

进入主桌面布局时，`src/routes/(main)/_layout/index.tsx` 会先挂载全局能力：热键作用域、RouteMetaBridge、桌面导航/文件菜单桥接、屏幕捕获相关组件、CloudBanner、TitleBar、拖拽上下文、导航栏和主内容容器。真正的子页面通过 React Router 的 `Outlet` 渲染。

业务交互发生后，feature 通常读写 store。例如聊天功能会通过 `useChatStore` 或 `getChatStoreState` 操作 `chat` store；`chat` store 聚合 message、topic、thread、plugin、tool、tts、translate、agent 等 slice/action。需要请求模型时，action 或 runtime 会调用 `chatService.createAssistantMessage`，该服务再读取 agent/user/tool/aiInfra 等 store，组装 payload、工具、记忆、搜索配置和认证头，最后走流式请求。

## 小白阅读顺序

1. 先看 `src/spa/entry.web.tsx`：理解 SPA 是如何启动的，以及 React Router 在哪里接入。
2. 再看 `src/spa/router/desktopRouter.config.tsx`：不用逐行读完，先看一级路径和 `dynamicElement` 指向哪些 `src/routes` 页面。
3. 接着看 `src/routes/(main)/_layout/index.tsx`：理解主界面框架，包括导航、全局弹窗、热键、桌面桥接和 `Outlet`。
4. 然后挑一个具体页面，例如 `src/routes/(main)/agent/index.tsx` 或 `src/routes/(main)/home/index.tsx`，顺着 import 进入 `src/features`。
5. 读对应 feature 后，再看它用到的 store，例如聊天读 `src/store/chat/store.ts`、agent 读 `src/store/agent`、用户设置读 `src/store/user`。
6. 最后看 service，例如 `src/services/chat/index.ts`、`src/services/config.ts`，理解前端状态如何转成真实 API、SSE 或导入导出行为。
7. 如果关心后端配置，再读 `src/server/globalConfig/index.ts`、`src/server/runtimeConfig` 和 `src/app/(backend)`。

## 常见误区

第一个误区是把 `src/app` 当成所有页面的入口。这个项目的主产品界面大量走 `src/spa`、`src/spa/router` 和 `src/routes`，`src/app` 更偏 Next.js 宿主、后端和 SSR/认证相关入口。

第二个误区是在 `src/routes` 里写复杂业务。仓库规范要求 routes 保持薄，业务 UI 和逻辑应放入 `src/features/<Domain>`，route 文件只负责页面段组合和导出。

第三个误区是改桌面路由时只改一个配置。仓库说明明确要求 `src/spa/router/desktopRouter.config.tsx` 和 `src/spa/router/desktopRouter.config.desktop.tsx` 保持同步，否则不同构建路径可能出现空白页。

第四个误区是直接在组件里散落请求逻辑。这个项目倾向于 `features -> store -> services` 的分层，数据请求和副作用应优先放到 service/store 体系里，而不是随手塞进页面组件。

第五个误区是忽略运行形态差异。`web`、`mobile`、`desktop`、`popup` 都有独立入口或路由配置；Electron 相关能力还会通过 `features/Electron`、`services/electron`、`store/electron` 连接桌面桥接。

第六个误区是看到 `components` 和 `features` 都有 UI 就混用。一般来说，`components` 更偏通用基础组件，`features` 更偏具体业务域；例如一个通用 Loading 可以在 `components`，而聊天输入、页面编辑器、插件详情这类应归入 `features`。
