# 目录：src/routes

## 它负责什么

`src/routes` 是 LobeHub SPA 的“页面路由段”目录，负责承接 `react-router-dom` 的路由树，把 URL 映射到对应的页面入口和布局入口。它不是传统 Next.js App Router 的业务页面目录，而是 Vite/React Router SPA 的 roots 层：路由配置在 `src/spa/router/*Router.config.tsx`，真正被动态或静态加载的页面模块大多来自这里。

从当前片段看，仓库正在逐步执行 “roots vs features” 拆分：理想状态下，`src/routes` 只放 `_layout/index.tsx`、`index.tsx`、动态段如 `[id]/index.tsx` 这类薄入口；复杂 UI、hooks、业务状态、列表、表单、侧边栏等应放到 `src/features/<Domain>/`。不过现有目录仍有历史代码，例如 `src/routes/(main)/agent/features`、`src/routes/(main)/community/(detail)/*/features`、`src/routes/(main)/(create)/*/features`，说明迁移尚未完全完成。阅读时要把它理解为“路由入口 + 部分尚未迁出的业务实现”的混合层。

## 关键组成

`src/routes/(main)` 是桌面主应用路由组。它包含 `home`、`agent`、`group`、`community`、`settings`、`memory`、`resource`、`page`、`task`、`tasks`、`devtools`、`eval`、`(create)` 等主工作区页面。`src/routes/(main)/_layout/index.tsx` 是桌面主壳：挂载 `HotkeysProvider`、`RouteMetaBridge`、`NavPanel`、桌面端桥接能力、云端横幅、认证 Provider、`DesktopHomeLayout`，最后通过 `<Outlet />` 渲染当前子路由。

`src/routes/(mobile)` 是移动端路由组。`src/routes/(mobile)/_layout/index.tsx` 提供移动端主壳，挂载 `RouteMetaBridge`、`MarketAuthProvider`、移动底部 `NavBar`，并根据 pathname 决定是否显示导航。移动端也会复用部分 `(main)` 页面模块，例如社区列表、模型详情、设置 tab 等。

`src/routes/(desktop)` 放 Electron 桌面专属流程，目前可见的是 `desktop-onboarding`。这类路由只服务桌面端运行环境。

`src/routes/(popup)` 是弹窗窗口路由组，对应 `src/spa/router/popupRouter.config.tsx`。它通过同步 import 加载 `PopupLayout`、`PopupAgentQuickPage`、`PopupAgentTopicPage`、`PopupGroupTopicPage`，用于独立会话窗口，没有主侧栏和完整桌面壳。

`src/routes/onboarding` 是引导流程，入口 `index.tsx` 直接导出 `@/features/Onboarding/Common`。它还包含 `branch.ts`、`config.ts`、`interestCategoryMap.ts` 和测试文件，说明这里不仅有页面入口，也有部分引导流程配置。

`src/routes/share` 是分享页路由组，用于公开或半公开分享场景，例如 topic 分享路径。当前未展开细看，按目录命名和路由分组推断，它属于特殊入口流，不走主应用完整导航。

`src/routes/(main)/page` 是较新的“薄路由”示例：`_layout/index.tsx` 直接 `export { default } from '@/features/Pages/PageLayout'`，`index.tsx` 只渲染 `@/features/PageExplorer/PageExplorerPlaceholder`。这符合当前约定：routes 只组合，功能在 features。

`src/routes/(main)/agent` 是历史上较重的路由示例。`index.tsx` 直接组合 `ChatHydration`、`Conversation`、`TelemetryNotification`，并且同目录下有大量 `features/Conversation`、Sidebar、profile 等实现。根据当前片段推断，这是尚未完全迁往 `src/features` 的核心聊天页面。

## 上下游关系

上游入口是 `src/spa/entry.*.tsx` 和 `src/spa/router/*Router.config.tsx`。路由配置文件定义 `RouteObject[]`，再通过 `dynamicElement`、`dynamicLayout` 或同步 import 指向 `src/routes` 下的模块。例如 `desktopRouter.config.tsx` 中的 `agent/:aid` 会加载 `@/routes/(main)/agent/_layout`，其 index 子路由加载 `@/routes/(main)/agent`；`mobileRouter.config.tsx` 中的 `/agent/:aid` 则加载 `@/routes/(mobile)/chat/_layout` 和 `@/routes/(mobile)/chat`。

下游主要是 `src/features`、`src/store`、`src/services`、`src/components`、`src/layout` 等。符合新规范的路由文件会导入 feature 页面或布局，例如 `src/routes/(main)/page/_layout/index.tsx` 指向 `@/features/Pages/PageLayout`；主布局会引入 `NavPanel`、`RouteMetaBridge`、`MarketAuthProvider`、Electron 相关 feature。历史路由则可能直接消费 store、hooks、业务组件和局部 features。

还有一层元信息关系：路由配置会给部分路由挂 `handle.meta`，例如 `agentRouteMeta`、`groupRouteMeta`、`settingsRouteMeta`、`pageRouteMeta`、`taskRouteMeta`。`RouteMetaBridge` 读取这些元信息后影响页面标题、导航高亮或布局行为。

## 运行/调用流程

应用启动时，SPA entry 选择对应 router：桌面/web 使用 desktop 路由树，移动端使用 mobile 路由树，弹窗使用 popup 路由树。路由树先匹配 URL，再加载布局模块和页面模块。

以桌面聊天为例：访问 `/agent/:aid` 时，路由先进入 `(main)` 主布局，渲染全局导航、热键、认证、桌面桥接等外壳；再进入 `agent/:aid` 的 agent layout；最后 index 子路由加载 `src/routes/(main)/agent/index.tsx`，由它渲染聊天水合、对话主体和遥测提示。若访问 `/agent/:aid/:topicId/page/:docId`，则会进入 topic page 子树，加载 `src/routes/(main)/agent/[topicId]/page/[docId]`。

以移动端社区为例：`mobileRouter.config.tsx` 的 `/community` 使用 `src/routes/(mobile)/community/_layout`，列表页内部复用 `src/routes/(main)/community/(list)/*`，详情页则通过 `.then((m) => m.MobileModelPage)` 之类方式取同一模块中的移动端导出。也就是说，部分页面模块同时服务桌面和移动，只是在路由配置中选择不同导出和不同 layout。

以弹窗为例：`/popup/agent/:aid/:tid` 由 `popupRouter.config.tsx` 直接同步渲染 `PopupLayout` 和对应 popup 页面，不走 `(main)` 主布局，因此它更像一个轻量独立窗口。

## 小白阅读顺序

1. 先看 `src/spa/router/desktopRouter.config.tsx` 和 `src/spa/router/mobileRouter.config.tsx`，建立 URL 到文件的映射关系。不要一开始就在 `src/routes` 里迷路。

2. 再看 `src/routes/(main)/_layout/index.tsx` 和 `src/routes/(mobile)/_layout/index.tsx`，理解桌面端、移动端共同外壳分别挂了哪些全局能力。

3. 接着读一个“薄路由”样板：`src/routes/(main)/page/_layout/index.tsx`、`src/routes/(main)/page/index.tsx`，理解新规范下 routes 如何委托给 `src/features`。

4. 再读一个核心历史路由：`src/routes/(main)/agent/index.tsx` 和 `src/routes/(main)/agent/_layout/index.tsx`。这里能看到聊天主链路，但也要意识到它比理想 routes 层更重。

5. 最后按业务域补读：社区看 `community/(list)` 与 `community/(detail)`，设置看 `settings`，任务看 `task`/`tasks`，创建能力看 `(create)/image`、`(create)/video`。

## 常见误区

不要把 `src/routes` 理解成 Next.js 的 `src/app`。这里是 SPA 的 React Router 页面段，真正的路由注册在 `src/spa/router`，不是靠文件系统自动生成。

不要以为目录名带括号如 `(main)`、`(mobile)` 会自动影响 URL。它们是组织分组，实际 path 由 router config 决定。

不要在新增路由时只改一个桌面配置。桌面路由存在 `desktopRouter.config.tsx` 和 `desktopRouter.config.desktop.tsx` 两份树，新增、删除、改 path、改嵌套时必须保持同步，否则可能出现某个构建路径白屏。

不要把大量业务 UI 继续塞进 `src/routes`。当前有历史遗留的 `features` 子目录，但新代码应优先放到 `src/features/<Domain>`，routes 只做布局入口、页面入口和少量组合。

不要看到移动端复用 `(main)` 模块就误判为桌面专用。`mobileRouter.config.tsx` 会选择性复用 `(main)/community`、`(main)/settings` 等模块，甚至通过命名导出拿移动端页面。

不要忽略 layout 的层级。页面实际渲染通常经过多层 `<Outlet />`：主 layout、业务 layout、列表/详情 layout、最终 page。很多“为什么组件一直显示”或“为什么导航存在”的问题，答案都在上层 layout。
