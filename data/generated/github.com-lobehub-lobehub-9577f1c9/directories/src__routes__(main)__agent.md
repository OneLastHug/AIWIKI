# 目录：src/routes/(main)/agent

## 它负责什么

`src/routes/(main)/agent` 是桌面主应用里单个 Agent 会话空间的路由根目录，对应路由树大致是 `/agent/:aid/...`。它承载的不只是聊天页，还包括 Agent 资料编辑、渠道接入、任务详情、主题会话、页面文档跳转等 Agent 相关工作区。

从当前片段看，这个目录还处在较早的组织形态：它既有路由入口文件，也包含不少 `features/` 和局部 UI 组件。按照仓库新的 `spa-routes` 约定，`src/routes/` 理想上应只保留薄路由入口，业务 UI 应逐步迁移到 `src/features/`；但此处仍有 `src/routes/(main)/agent/features`、`profile/features`、`_layout/Sidebar` 等 route-local 实现。因此学习时要把它理解为“Agent 路由根 + 历史遗留的局部功能实现集合”。

整体职责可以概括为：在选定 Agent 后初始化配置、同步 Agent ID、挂载左侧栏与主内容区；在聊天子布局中加载聊天头部、会话区、Portal 和工作侧栏；在若干子路径下切换到资料编辑、渠道配置、任务详情和页面文档相关视图。

## 直接子目录地图

`_layout` 是 `/agent/:aid` 的顶层布局。它负责调用 `useInitAgentConfig()`，渲染 `Sidebar`、主内容 `<Outlet />`，并挂载 `RegisterHotkeys`、`AgentIdSync`、`PortalAutoCollapse`，桌面环境下还会挂载 `ProtocolUrlHandler`。其下的 `Sidebar` 是 Agent 工作区左侧栏实现，包含 `Header`、`Task`、`Topic` 等分区。

`(chat)` 是聊天主区域的布局分组。`(chat)/_layout/index.tsx` 包裹聊天类子路由，负责根据全局状态显示 `ChatHeader`，并在右侧挂载 `Portal` 和 `AgentWorkingSidebar`。这个分组下面的默认页面最终落到 `src/routes/(main)/agent/index.tsx`。

`[topicId]` 是主题会话动态段。`[topicId]/index.tsx` 当前只是重新导出 Agent 默认聊天页，说明进入某个 topic 时仍复用主聊天会话组件。`[topicId]/page` 是 topic 内页面文档相关入口，路由配置中还包含 `page/:docId` 的文档详情路径。

`page` 是无效或缺少 topic 上下文时的页面跳转入口。`page/index.tsx` 会读取 `aid`，通过 `Navigate` 重定向回该 Agent 的聊天 URL；如果没有 `aid`，则回到 `/agent`。这更像兜底路由，不是正式页面编辑主入口。

`profile` 是 Agent 资料/配置编辑页。它使用 `ProfileProvider`、`ProfileHydration`、`ProfileEditor`，同时挂载 `AgentBuilder` 作为右侧构建器面板。这个目录下还有 `features/store`，说明 profile 自己维护一部分页面编辑状态。

`channel` 是 Agent 渠道接入页面。它读取 `aid`，通过 `useAgentStore` 拉取平台定义、bot provider 配置和运行状态，并在左侧平台列表与右侧平台详情之间切换。`detail` 放渠道表单详情，`platform` 放平台定义/注册相关代码，当前有 `line`、`wechat` 等平台目录。

`features` 是聊天和 Agent 路由共用的局部实现集合。核心在 `features/Conversation`，还包括 `Page`、`Portal`、`ChangelogModal`、`TelemetryNotification`、`routeMeta`、`topicPageRouteMeta` 等。根据当前片段推断，这里是该路由历史上沉淀业务 UI 的主要位置，依据是聊天页入口直接从 `./features/Conversation` 导入主会话组件。

`task` 是 Agent 任务详情路径容器。`task/[taskId]/index.tsx` 读取 `taskId` 后渲染 `@/features/AgentTasks` 中的 `TaskDetailPage`，并关闭任务 Agent 面板切换能力。

## 关键入口

顶层布局入口是 `src/routes/(main)/agent/_layout/index.tsx`。它是进入 `/agent/:aid` 后最先挂载的外壳，决定了 Agent 工作区的基础结构：左侧栏、主内容区、快捷键注册、协议 URL 处理、Agent ID 同步和 Portal 自动折叠。

默认聊天页入口是 `src/routes/(main)/agent/index.tsx`。它先挂载 `ChatHydration`，再渲染 `Conversation`，最后显示 `TelemetryNotification`。这说明聊天页的数据准备和遥测提示都在页面入口层处理，而真实聊天 UI 下沉到 `features/Conversation`。

聊天布局入口是 `src/routes/(main)/agent/(chat)/_layout/index.tsx`。它负责聊天区域的横向结构：中间会话内容、可选头部、Portal 和工作侧栏。想理解聊天主界面布局，应先看这里，再进入 `features/Conversation/index.tsx`。

路由注册入口在 `src/spa/router/desktopRouter.config.tsx`。这里把 `agent` 注册为桌面路由分支，并声明 `path: 'agent'`、子级 `path: ':aid'`、顶层 Agent layout、聊天 layout、默认聊天页、topic、page、profile、channel、task 等子路由。按照项目约定，桌面同步配置 `src/spa/router/desktopRouter.config.desktop.tsx` 也应保持相同路由树。

## 主流程位置

进入 Agent 的主流程从桌面路由开始：`src/spa/router/desktopRouter.config.tsx` 将 `/agent/:aid` 指向 `src/routes/(main)/agent/_layout`。顶层 layout 初始化 Agent 配置，然后渲染侧边栏与 `<Outlet />`。如果是默认聊天路径，内部会进入 `(chat)/_layout`，再由其 `<Outlet />` 渲染 `src/routes/(main)/agent/index.tsx`。

聊天页的数据与渲染链路大致是：`index.tsx` 挂载 `ChatHydration`，再进入 `features/Conversation/index.tsx`。`Conversation` 会从 `useAgentStore` 读取当前模型、provider、异构 Agent 状态和本地系统开关，使用 `useUploadFiles` 支持拖拽上传，并在桌面异构或本地系统启用时支持本地文件夹 mention。最后它通过 `DragUploadZone`、`TooltipGroup` 包裹 `ConversationArea`，真正消息流和输入区的细节继续分散在 `ConversationArea`、`MainChatInput`、`HeterogeneousChatInput`、`WorkingSidebar` 等子模块中。

资料编辑流程从 `/agent/:aid/profile` 进入 `profile/index.tsx`。它通过 `ProfileProvider` 提供上下文，`ProfileHydration` 做数据同步，`ProfileEditor` 承担编辑主体，`AgentBuilder` 提供构建器侧栏。

渠道配置流程从 `/agent/:aid/channel` 进入 `channel/index.tsx`。这里先按 `aid` 获取平台定义和 provider 配置，触发运行状态刷新，然后把合并后的平台列表交给 `PlatformList`，把当前平台配置交给 `PlatformDetail` 或 `ComingSoonDetail`。

任务详情流程从 `/agent/:aid/task/:taskId` 进入 `task/[taskId]/index.tsx`，随后转交给全局 feature `@/features/AgentTasks`，这个分支比较符合新的 routes/features 拆分方式。

## 推荐阅读顺序

第一步读 `src/spa/router/desktopRouter.config.tsx` 中 `agent` 分支，先建立 URL 到页面入口的映射，尤其关注 `agent/:aid`、`:topicId`、`profile`、`channel`、`task/:taskId` 的嵌套关系。

第二步读 `src/routes/(main)/agent/_layout/index.tsx` 和 `_layout/Sidebar/index.tsx`，理解 Agent 工作区的外壳、初始化副作用和左侧导航。

第三步读 `src/routes/(main)/agent/(chat)/_layout/index.tsx` 与 `src/routes/(main)/agent/index.tsx`，把聊天主页面的 layout、hydration、notification 和主会话组件关系串起来。

第四步读 `src/routes/(main)/agent/features/Conversation/index.tsx`，再按需要进入 `ConversationArea`、`Header`、`MainChatInput`、`HeterogeneousChatInput`、`WorkingSidebar`。这条线是理解 Agent 聊天体验的主线。

第五步按功能分支阅读 `profile/index.tsx`、`channel/index.tsx`、`task/[taskId]/index.tsx`。其中 profile 和 channel 的实现仍较多留在 route 目录内，task 则主要委托给 `src/features/AgentTasks`。

## 常见误区

不要把 `src/routes/(main)/agent/features` 误认为项目推荐的新结构。根据当前片段推断，它是历史遗留的 route-local feature 目录；新代码通常应优先放到 `src/features/<Domain>/`，路由文件只做组合和转发。

不要只看 `src/routes/(main)/agent/index.tsx` 就以为它包含完整聊天逻辑。它只是聊天页入口，真正的布局在 `(chat)/_layout`，核心会话行为在 `features/Conversation` 及其子目录。

不要忽略 `:aid` 这一层。`profile`、`channel`、`task/:taskId` 都是在 `/agent/:aid` 下面运行，很多逻辑依赖 `useParams()` 中的 `aid`。

不要把 `page/index.tsx` 当成页面文档功能主体。当前它主要是重定向兜底；topic 下的 `page` 和 `page/:docId` 才是路由配置中与具体页面文档相关的分支。

不要改动桌面 Agent 路由时只改一个 router config。项目约定要求 `src/spa/router/desktopRouter.config.tsx` 和 `src/spa/router/desktopRouter.config.desktop.tsx` 保持同构，否则可能出现某个构建入口空白或路由缺失。
