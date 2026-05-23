# 目录：src/store

## 它负责什么

`src/store` 是前端 SPA 的全局状态层，主要基于 `zustand` 组织。它位于 UI 与服务层之间：页面和业务组件通常从 `src/routes`、`src/features`、`src/hooks` 中调用 `useXxxStore` 读取状态或触发 action；store 内部 action 再调用 `src/services`、TRPC client 或其他客户端服务完成数据读写。按项目约定，典型数据流可以理解为：React UI → Store Actions → Client Service → TRPC Lambda → Server Services → DB Model → PostgreSQL。

这个目录不是单一“大 store”，而是按业务域拆成多个 store：聊天、用户、全局 UI 状态、文件、工具、知识库、任务、文档、图片、视频等。每个业务域一般独立维护 `initialState`、`store`、`selectors`、`slices`，并通过 `index.ts` 对外导出 hook 和少量直接访问函数，例如 `useChatStore`、`getChatStoreState`。

从当前片段看，`src/store` 同时承载两类状态：一类是纯前端交互状态，例如面板开关、分页大小、当前 tab、编辑状态；另一类是带业务读写流程的客户端状态，例如会话列表、消息、文件、工具安装状态、用户设置、知识库内容。后者通常会在 action 中调用 service，并配合乐观更新、刷新、错误处理等流程。

## 直接子目录地图

`src/store/chat` 是聊天域核心 store，覆盖会话上下文、消息、话题、AI 对话、插件、内置工具、线程、操作状态等聊天主流程。它是被 `src/features`、`src/hooks`、`src/services/chat` 高频引用的中心 store。

`src/store/user` 管用户状态、认证、个人资料、设置、系统 agent 配置等。设置页、用户头像、鉴权判断、模型和语言偏好都会依赖它。

`src/store/global` 管全局 UI 和系统状态，例如侧边栏、弹窗、面板显隐、系统状态字段、语言等。很多页面用它保存跨页面 UI 偏好。

`src/store/serverConfig` 保存服务端下发配置、feature flags、移动端判断、业务特性开关等。它和普通 store 略有不同，当前片段显示它带有 `Provider` 和初始化状态工厂，用于把服务端配置注入前端树。

`src/store/session` 管会话列表与当前会话相关状态；`src/store/agent` 管 agent 配置和 bot provider；`src/store/agentGroup` 管群组会话或 chat group 相关状态；`src/store/groupProfile` 管群组资料面板状态。

`src/store/file`、`src/store/tree`、`src/store/document`、`src/store/page` 与资源、文件树、文档编辑和页面列表相关。`tree` 会订阅 `file` store 的状态变化并做 reconcile，说明这里存在跨 store 同步。

`src/store/tool` 管插件、MCP、内置工具、技能服务等工具生态状态。聊天上下文组装、工具预加载、设置页技能列表都会读取它。

`src/store/library`、`src/store/notebook`、`src/store/brief`、`src/store/userMemory` 分别对应知识库、笔记本、简报、用户记忆等内容型业务。

`src/store/image`、`src/store/video` 管 AI 图片和视频生成配置、生成话题、媒体生成流程。它们会读取 `user` 与 `global` 中的登录、设置和系统状态。

`src/store/task` 管 agent task 或任务详情、配置、列表等；`src/store/electron` 管桌面端 Electron 相关状态；`src/store/aiInfra` 管 AI provider、模型和基础设施配置；`src/store/discover`、`src/store/eval`、`src/store/followUpAction`、`src/store/mention` 等则是较独立的功能域 store。

`src/store/middleware`、`src/store/utils` 是共享基础设施。当前片段中多处 store 使用 `src/store/utils/flattenActions`，`src/store/utils/optimisticEngine.test.ts` 也表明这里放了通用 action 组合和乐观更新工具。

## 关键入口

每个业务域的首要入口通常是 `src/store/<domain>/index.ts`。它负责导出外部使用的 hook、selector 或 helper。比如 `src/store/chat/index.ts` 导出 `useChatStore` 与 `getChatStoreState`，`src/store/user/index.ts` 导出用户 store，`src/store/serverConfig/index.ts` 导出 `useServerConfigStore`。

`src/store/<domain>/store.ts` 是具体 Zustand store 创建入口。常见模式是定义 `createStore`，合并 `initialState` 与多个 slice action，然后用 `createWithEqualityFn` 创建 `useXxxStore`。很多 store 还会包 `createDevtools`，部分使用 `subscribeWithSelector`，并通过 `expose('name', useXxxStore)` 暴露调试入口。

`src/store/<domain>/initialState.ts` 定义状态初始值与部分枚举型 UI 状态。`src/store/<domain>/selectors.ts` 或 `src/store/<domain>/selectors/` 放派生读取逻辑，供组件用 `useXxxStore(selector)` 订阅较小状态片段，减少组件直接理解内部结构。

`src/store/<domain>/slices` 是复杂 store 的核心分层位置。大 store 不会把所有 action 写在 `store.ts`，而是拆成多个 slice，例如 chat 下的 message、topic、plugin、aiChat、builtinTool、thread 等。根据当前片段，slice action 正在逐步使用 class-based action，并通过 `flattenActions` 合并回 store。

## 主流程位置

聊天主流程优先看 `src/store/chat/store.ts` 和 `src/store/chat/slices`。它聚合聊天相关 action，外部组件通过 `useChatStore` 触发发送消息、刷新话题、替换消息、处理工具调用等。`src/services/chat` 也会读取 `getChatStoreState`、`topicSelectors`、`getToolStoreState` 来完成上下文工程和工具预加载。

用户与配置初始化流程集中在 `src/store/user/store.ts`、`src/store/serverConfig/store.ts`、`src/store/global/store.ts`。页面加载时，组件和 hooks 会同时读取登录状态、服务端 feature flags、系统 UI 状态，决定是否显示业务功能、插件能力、移动端布局和设置项。

内容资源流程分散在 `src/store/file`、`src/store/tree`、`src/store/document`、`src/store/page`。文件列表和文档编辑 action 会调用对应 service，`document` 中的 action 还会调用 `usePageStore.getState().upsertDocument`，说明文档保存后会同步页面级状态。

工具与插件流程集中在 `src/store/tool/store.ts`、`src/store/tool/slices`、`src/store/tool/selectors`。设置页技能列表、聊天上下文、MCP service 都会读取这里的工具 manifest、安装状态、授权状态和内置工具注册信息。

媒体生成流程集中在 `src/store/image` 与 `src/store/video`。它们会读取 `useUserStore` 判断登录和默认生成设置，也会通过 `useGlobalStore` 更新系统状态，例如最后选择的 provider、model 或面板状态。

## 推荐阅读顺序

1. 先读 `src/store/utils/flattenActions` 和任意一个中等复杂 store，例如 `src/store/home/store.ts` 或 `src/store/session/store.ts`，理解本仓库如何组合 `initialState`、slice action、devtools、`subscribeWithSelector`。
2. 再读 `src/store/global`、`src/store/user`、`src/store/serverConfig`，这三个是许多页面的公共依赖，理解它们后再看业务 store 会轻松很多。
3. 接着读 `src/store/chat/store.ts` 和 `src/store/chat/slices` 的目录结构，只看 slice 名称和 action 入口，不必逐文件展开。聊天是全站最复杂的状态域，适合用来理解跨 store 调用和服务层协作。
4. 然后按业务兴趣选择 `src/store/tool`、`src/store/file`、`src/store/document`、`src/store/image`、`src/store/video`、`src/store/task`。这些目录更贴近具体功能页。
5. 最后看 `selectors.ts`、`reducers`、测试文件。它们能补充状态结构的边界条件，但不适合作为第一入口。

## 常见误区

不要把 `src/store` 理解成后端数据模型。这里是客户端状态和前端业务流程层，真正的数据库 schema、model、repository 在 `packages/database`，服务端业务在 `src/server`，客户端请求封装在 `src/services`。

不要在组件里绕过 action 直接改复杂状态。当前约定强调 public action、`internal_*` action、`internal_dispatch*` 分层：UI 调 public action；内部 action 负责 service 调用、乐观更新和错误处理；dispatch 方法或 reducer 负责真正更新 map/list 状态。

不要把所有派生逻辑写进组件。大量目录提供 `selectors.ts` 或 `selectors/`，组件应优先订阅 selector 返回的最小状态片段，而不是拿整个 store 后自行拼装。

不要以为每个 store 都完全同构。多数 store 是 `createWithEqualityFn` + `devtools` + `flattenActions`，但 `serverConfig` 有 Provider 初始化模式，`tree` 会订阅 `file` store，`groupProfile` 直接在 `index.ts` 创建 store，一些简单域可能没有独立 `slices`。

不要随意新增跨 store 依赖。当前已有 `home` 调 `chat/global/groupProfile`、`document` 调 `page`、`tree` 订阅 `file`、`image/video` 调 `user/global` 等模式。新增依赖时应确认方向是否合理，否则容易形成隐式循环和难以测试的状态同步。

不要把 `slices` 当成路由分组。它是 store 内部业务能力拆分，不对应页面目录。页面入口仍在 `src/routes`，业务 UI 在 `src/features`，store 只负责状态、action 和派生读取。
