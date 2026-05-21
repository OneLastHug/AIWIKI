# 目录：src

## 它负责什么

`src` 是 LobeHub 主应用的核心源码目录。它同时承载 Next.js 服务端入口、React Router SPA 前端入口、页面路由、业务功能组件、客户端状态、客户端服务层、服务端路由与服务端业务逻辑。简单说，`apps/` 和 `packages/` 提供外壳与共享包，而 `src` 是 LobeHub Web/SPA 主应用真正“跑起来”的地方。

从当前代码可以看出，LobeHub 不是纯 Next.js 页面应用，也不是纯 Vite SPA，而是二者结合：

- `src/app` 负责 Next.js App Router、后端 API、认证页、SPA HTML 模板输出。
- `src/spa` 负责 Vite/React SPA 的浏览器入口和 `react-router-dom` 路由表。
- `src/routes` 负责 SPA 的页面段文件，通常只做页面组合。
- `src/features`、`src/components`、`src/layout` 负责实际 UI 和交互。
- `src/store`、`src/services` 负责前端状态与前端请求封装。
- `src/server` 负责 tRPC/Hono/API 背后的服务端业务实现。

这个目录的核心设计思想是分层：页面入口要薄，业务 UI 放到 `features`，可复用 UI 放到 `components`，前端调用后端走 `services`，后端入口走 `server/routers`，真正业务逻辑再沉到 `server/services`、`server/modules`。

## 关键组成

`src/app` 是 Next.js App Router 区域。根文件 `src/app/layout.tsx` 输出全局 `<html>` 和 `<body>`，并挂载 `Analytics`、Vercel `SpeedInsights`。`src/app/(backend)` 下是真正的后端 HTTP 入口，例如 `api/auth/[...all]/route.ts`、`trpc/lambda/[trpc]/route.ts`、`webapi/chat/[provider]/route.ts`、`api/workflows/**/route.ts`。`src/app/[variants]/(auth)` 放登录、注册、重置密码、OAuth consent、设备码等需要 SSR/认证上下文的页面。`src/app/spa/[variants]/[[...path]]/route.ts` 是 SPA HTML 模板服务：开发环境会从 `[URL已移除] 读取 Vite HTML，并改写资源地址；生产环境导入构建好的 `desktopHtmlTemplate` 或 `mobileHtmlTemplate`，再注入 `window.__SERVER_CONFIG__`、SEO metadata、feature flags、analytics config。

`src/spa` 是 SPA 启动层。`entry.web.tsx`、`entry.desktop.tsx`、`entry.mobile.tsx`、`entry.popup.tsx` 都先导入 `../initialize`，再用 `createRoot` 挂载 `RouterProvider`。不同入口使用不同路由表：桌面 Web 用 `desktopRoutes`，移动端用 `mobileRoutes`，弹窗窗口用 `popupRoutes`。其中 `entry.web.tsx` 额外处理 `/_dangerous_local_dev_proxy` 的 `basename`，用于本地 Vite SPA 嵌进线上调试代理。

`src/initialize.ts` 是全局初始化文件。它启用 `immer` 的 `enablePatches()` 和 `enableMapSet()`，给 `dayjs` 扩展 `relativeTime`、`utc`、`isToday`、`isYesterday`，并监听 `vite:preloadError` 和 `unhandledrejection` 来捕获异步 chunk 加载失败。开发环境还启用 `react-scan`。

`src/spa/router` 保存 React Router 配置。`desktopRouter.config.tsx` 是桌面主路由表，包含 `/agent/:aid` 聊天、`/group/:gid` 群组、`/community` 发现页、`/resource` 资源库、`/settings` 设置、`/memory` 记忆、`/image`、`/video`、`/eval`、`/tasks`、`/task/:taskId`、`/page`、`/share/t/:id`、`/onboarding` 和开发环境 `/devtools`。`desktopRouter.config.desktop.tsx` 需要与它保持同步。`mobileRouter.config.tsx` 是移动端路由表，会复用部分 `src/routes/(main)` 页面，也会挂载移动专用布局。`popupRouter.config.tsx` 是桌面弹窗专用路由，只承载单个 agent/group 话题窗口。

`src/utils/router.tsx` 是 SPA 路由工具。它提供 `createAppRouter()`，把业务路由包在 `RouterRoot` 下；`RouterRoot` 再挂 `SPAGlobalProvider`、`BusinessGlobalProvider`、`NavigatorRegistrar` 和 `Outlet`。它还提供 `dynamicElement()`、`dynamicLayout()` 做懒加载页面/布局，`ErrorBoundary` 统一处理路由错误和 chunk 加载错误，`redirectElement()` 用于声明式重定向，`prefetchRoute()` 用于预加载常用路由布局 chunk。

`src/routes` 是 SPA 页面段。这里的文件应当尽量薄。例如 `src/routes/(main)/page/index.tsx` 只组合 `PageTitle` 和 `PageExplorerPlaceholder`；`src/routes/onboarding/index.tsx` 直接导出 `@/features/Onboarding/Common`；`src/routes/(main)/agent/index.tsx` 组合 `ChatHydration`、`PageTitle`、`Conversation` 和通知组件。`src/routes/(main)/_layout/index.tsx` 是桌面主布局，挂载热键作用域、桌面桥接、标题栏、导航栏 `NavPanel`、首页背景布局、`MarketAuthProvider`、`Outlet`、命令面板、反馈弹窗等。

`src/features` 是业务功能 UI。这里不是简单组件库，而是按业务域组织的大块功能，例如 `AgentBuilder`、`AgentHome`、`AgentSetting`、`ChatInput`、`Conversation`、`CommandMenu`、`DailyBrief`、`EditorCanvas`、`PageEditor`、`PageExplorer`、`RecommendTaskTemplates`、`ResourceManager`、`ShareModal`、`TopicCanvas` 等。路由页经常只是把这些 feature 组合起来。

`src/components` 是通用 UI 组件库，粒度比 `features` 小，面向复用。例如 `BootErrorBoundary`、`Error`、`Loading`、`DragUploadZone`、`FormInput`、`ModelSelect`、`StreamingMarkdown`、`FileIcon`、`InvalidAPIKey`、`Notification`、`StatisticCard`、`HtmlPreview`、`MCPStdioCommandInput` 等。这里也有 `components/mdx`、`components/client`、`components/server` 这样的运行环境细分组件。

`src/layout` 放全局 Provider 和跨页面布局能力。最关键的是 `src/layout/SPAGlobalProvider/index.tsx`：它读取 `window.__SERVER_CONFIG__`，包裹 `Locale`、主题、`ServerConfigStoreProvider`、React Query/SWR 相关 provider、`AuthProvider`、store 初始化、favicon、拖拽上传、motion、tooltip、`StyleProvider`、analytics、Modal/Toast/ContextMenu host、导入设置和开发面板。小白可以把它理解为 SPA 启动后所有页面共同拥有的“运行环境外壳”。

`src/store` 是 Zustand 状态层。它按业务拆 store，例如 `agent`、`agentGroup`、`chat`、`global`、`serverConfig`、`user`、`task`、`file`、`image`、`video`、`page`、`library`、`document`、`notebook`、`tool`、`electron` 等。典型结构是 `initialState.ts` 定义初始状态，`store.ts` 用 `createWithEqualityFn` 创建 store，`selectors.ts` 提供选择器，`slices/` 或 `action.ts` 放动作。`src/store/agent/store.ts` 展示了这种模式：它合并 `initialState`，通过 `flattenActions()` 聚合 `createAgentSlice`、`createBotSlice`、`createBuiltinAgentSlice`、`createKnowledgeSlice`、`createPluginSlice` 和 reset action，再用 `createDevtools('agent')` 和 `expose('agent', useAgentStore)` 暴露调试能力。

`src/services` 是浏览器侧服务层。它把 UI/store 对后端的调用封装为类或对象方法，通常通过 `lambdaClient`、`asyncClient`、fetch 或 Electron bridge 调用。比如 `src/services/agent.ts` 的 `AgentService` 封装了创建 agent、查询 agent 配置、更新配置、管理知识库/文件、查询 builtin agent 等方法，并通过 `lambdaClient.agent.*` 调用 tRPC。`src/services/_auth.ts` 负责根据 provider 和本地 key vault 生成模型供应商认证 payload。`src/services/electron/*` 则处理桌面端特有能力，如 auto update、local file、gateway connection、heterogeneous agent 等。

`src/libs` 是基础库适配层，封装第三方库或平台差异。这里有 `trpc` 客户端/服务端初始化、`better-auth`、`redis`、`qstash`、`swr`、`mcp`、`pdfjs`、`oidc-provider`、`analytics`、`document-loaders`、`next` 兼容封装、`router` 封装等。比如 `src/libs/trpc/client/lambda.ts` 创建 `lambdaClient` 和 `lambdaQuery`，配置错误处理、401 登录态处理、请求 credentials、批量请求与非批量请求拆分；`src/libs/trpc/lambda/context.ts` 则在服务端从 API key、OIDC header、Better Auth session、cookie、traceparent 等信息构造 tRPC context。

`src/server` 是服务端业务层。`src/server/routers/lambda/index.ts` 聚合了大量 tRPC router，例如 `agent`、`aiChat`、`aiModel`、`aiProvider`、`file`、`knowledgeBase`、`message`、`session`、`task`、`userMemory`、`video`，也合入 `business/server/lambda-routers` 的订阅、充值、推荐等商业路由。`src/server/services` 放具体业务服务，例如 agent、chat、document、file、generation、knowledgeBase、memory、messenger、task、toolExecution 等。`src/server/modules` 放更底层的能力模块，例如 `AgentRuntime`、`ModelRuntime`、`AgentTracing`、`S3`、`KeyVaultsEncrypt`。`src/server/globalConfig/index.ts` 根据 env、feature flags、模型供应商配置、文件配置、认证配置生成前端可见的全局服务端配置。

`src/business` 是商业功能扩展层，分 `client` 和 `server`。客户端侧包含商业路由、订阅/账单/额度设置页、推荐任务模板、错误处理等；服务端侧包含 Better Auth 扩展、充值/订阅/消费相关 lambda router、图片/视频生成扣费通知、商业模型运行时等。主路由表中通过 `BusinessDesktopRoutesWithMainLayout`、`BusinessDesktopRoutesWithoutMainLayout`、`BusinessMobileRoutesWithMainLayout` 等把商业路由插入普通路由。

`src/config`、`src/envs` 和 `src/const` 是配置与常量层。`src/envs/app.ts` 使用 `@t3-oss/env-core` 和 `zod` 解析 `APP_URL`、`INTERNAL_APP_URL`、`AGENTS_INDEX_URL`、`PLUGINS_INDEX_URL`、`MARKET_TRUSTED_CLIENT_SECRET`、`AGENT_GATEWAY_URL`、`AGENT_RUNTIME_MODE` 等环境变量。`src/config/routes/index.ts` 定义共享导航路由 `NAVIGATION_ROUTES`，供 Electron 导航和 CommandMenu 使用。`src/config/featureFlags` 负责 feature flag schema 和解析。

`src/locales` 是国际化资源。`src/locales/default` 下按 namespace 保存默认文案，例如 `agent.ts`、`chat.ts`、`common.ts`、`setting.ts`、`metadata.ts`、`video.ts`。`src/locales/resources.ts` 定义支持的 locale 列表、`normalizeLocale()` 和语言选项。代码里使用 `react-i18next`，服务端 metadata 也会通过 `src/server/translation.ts` 读取翻译。

`src/hooks` 和 `src/helpers` 是可复用逻辑。`hooks` 包含 React hooks，例如 `useFetchSessions`、`useFetchTopics`、`useInitAgentConfig`、`useNavigateToAgent`、`usePWAInstall`、`usePlatform`、`useStableNavigate`、模型能力判断 hooks 等。`helpers` 放纯辅助逻辑，例如 search config、skill filters、tool availability、全局 agent context 管理等。

`src/types` 是应用级 TypeScript 类型补充，例如 `spaServerConfig.ts`、`serverConfig` 相关类型、i18next 类型声明、resource 类型、worker 类型等。`src/styles` 放全局样式覆盖，比如 `antdOverride.ts`。根部文件 `src/auth.ts` 用 `@/libs/better-auth/define-config` 定义认证配置；`src/proxy.ts` 定义 Next middleware/proxy matcher，覆盖 `/api`、`/trpc`、`/webapi`、`/agent`、`/settings`、`/share`、认证相关路径等；`src/instrumentation.ts` 和 `src/instrumentation.node.ts` 用于运行时观测/埋点初始化。

## 上下游关系

上游入口主要有三类。

第一类是浏览器访问页面。请求先进入 Next.js。对于主应用 SPA，`src/app/spa/[variants]/[[...path]]/route.ts` 返回 HTML 模板，并把 `getServerGlobalConfig()`、feature flags、analytics config 注入到 `window.__SERVER_CONFIG__`。浏览器加载 Vite/构建产物后进入 `src/spa/entry.*.tsx`，再进入 React Router。

第二类是浏览器或桌面端调用 API。前端组件或 store 通常调用 `src/services/*`，服务层再通过 `src/libs/trpc/client/lambda.ts` 的 `lambdaClient` 请求 `/trpc/lambda`。Next 后端入口 `src/app/(backend)/trpc/lambda/[trpc]/route.ts` 使用 `fetchRequestHandler`，创建 `createLambdaContext()`，再分发到 `src/server/routers/lambda/index.ts` 聚合的各业务 router。router 内部再调用 `src/server/services/*` 和 `src/server/modules/*`，必要时访问数据库模型、Redis、S3、QStash、模型运行时等。

第三类是认证、webhook、工作流和传统 webapi。认证相关路径在 `src/app/(backend)/api/auth`、`src/app/[variants]/(auth)`、`src/auth.ts`、`src/libs/better-auth`、`src/libs/oidc-provider` 之间协作。Webhook 和工作流入口位于 `src/app/(backend)/api/webhooks/**`、`src/app/(backend)/api/workflows/**`，背后调用 `src/server/workflows`、`src/server/workflows-hono` 或相应 service。传统模型接口如 `webapi/chat/[provider]`、`webapi/tts/*`、`webapi/models/[provider]` 则绕过部分 tRPC 流程，直接作为 Next route handler 暴露。

下游依赖主要来自 `packages/` 和外部服务。`src` 大量引用 `@lobechat/types`、`@lobechat/const`、`@lobechat/database`、`@lobechat/utils`、`@lobehub/ui`、`model-bank`、`react-router-dom`、`zustand`、`@trpc/*`、`better-auth`、`dayjs` 等。数据库模型虽然通过 `@/database/...` 路径引用，但实际在本仓库别处或路径别名下提供；小白阅读时不要误以为所有数据库 schema 都在 `src` 里。

前端层内部的常见依赖方向是：`routes` 引用 `features` 和 `components`；`features` 引用 `store`、`services`、`hooks`、`components`；`store` 的 action 调用 `services`；`services` 调用 `libs/trpc/client`；`server/routers` 调用 `server/services`；`server/services` 调用数据库模型、`server/modules`、`envs` 和外部 SDK。这个方向一般不要反过来，例如不应该让通用 `components` 依赖某个具体 route。

## 运行/调用流程

主 SPA 的启动流程可以按下面理解：

1. 用户访问 `/`、`/agent/...`、`/settings/...` 等路径，请求被 `src/proxy.ts` 的 matcher 覆盖，Next 根据变体路由返回 SPA HTML。
2. `src/app/spa/[variants]/[[...path]]/route.ts` 判断 locale 和 mobile variant，读取 Vite dev server 或生产 HTML 模板，注入 `window.__SERVER_CONFIG__` 和 SEO meta。
3. 浏览器加载 `src/spa/entry.web.tsx`、`entry.desktop.tsx` 或 `entry.mobile.tsx`。
4. 入口文件先执行 `src/initialize.ts`，完成 dayjs、immer、chunk 错误监听等全局初始化。
5. 入口调用 `createAppRouter(routes)`。`createAppRouter()` 在所有业务路由外包一层 `RouterRoot`。
6. `RouterRoot` 挂载 `SPAGlobalProvider`，建立语言、主题、认证、服务端配置 store、全局弹窗、Toast、拖拽上传、analytics、业务全局 Provider 等环境。
7. React Router 根据 `desktopRoutes` 或 `mobileRoutes` 懒加载对应 `src/routes/**` 页面段。
8. 页面段再组合 `src/features/**` 和 `src/components/**`，通过 hooks/store/services 获取数据并响应用户操作。

一次典型的“前端改 agent 配置”的调用链大致是：

1. 某个设置页 feature 触发 store action 或直接调用 `agentService.updateAgentConfig()`。
2. `src/services/agent.ts` 通过 `lambdaClient.agent.updateAgentConfig.mutate()` 发起 tRPC 请求。
3. `src/libs/trpc/client/lambda.ts` 给请求加 credentials，必要时动态生成认证 header，并处理 401/abort/错误通知。
4. 请求到达 `src/app/(backend)/trpc/lambda/[trpc]/route.ts`。
5. route handler 调用 `createLambdaContext()`，从 API key、OIDC、自身 Better Auth session 等解析 `userId`。
6. `lambdaRouter` 分发到 `src/server/routers/lambda/agent.ts` 中的 procedure。
7. router 调用 `src/server/services/agent/index.ts` 的 `AgentService.updateAgentConfig()`。
8. 服务端 `AgentService` 调用 `AgentModel.updateConfig()` 写数据库，然后重新查询配置，并按 `DEFAULT_AGENT_CONFIG`、服务端默认配置、用户默认配置、数据库 agent 配置的顺序合并后返回。
9. 前端收到结果后更新 store 或重新渲染页面。

移动端和桌面端的差异主要在路由表、布局和平台能力。移动端入口用 `mobileRoutes`，布局在 `src/routes/(mobile)`；桌面端除了主 Web 路由，还会通过 `isDesktop` 挂载 Electron 桥接能力，例如桌面导航、文件菜单、屏幕捕获、标题栏、桌面认证提醒。弹窗入口 `entry.popup.tsx` 只使用 `popupRoutes`，目标是打开一个轻量单会话窗口。

## 小白阅读顺序

建议先从入口读，不要一开始就扎进几百个业务文件。

1. 先读 `src/app/spa/[variants]/[[...path]]/route.ts`，理解 Next 如何把 SPA HTML 和 `window.__SERVER_CONFIG__` 发给浏览器。
2. 再读 `src/spa/entry.web.tsx`、`src/spa/entry.mobile.tsx`、`src/spa/entry.popup.tsx`，确认 SPA 是如何挂载的。
3. 读 `src/initialize.ts`，了解全局初始化、chunk 错误处理和开发辅助工具。
4. 读 `src/utils/router.tsx`，重点看 `createAppRouter()`、`dynamicElement()`、`dynamicLayout()`、`ErrorBoundary`。
5. 读 `src/spa/router/desktopRouter.config.tsx` 和 `src/spa/router/mobileRouter.config.tsx`，只需要先看有哪些一级路径，不要逐行背所有路由。
6. 读 `src/layout/SPAGlobalProvider/index.tsx`，理解语言、主题、认证、server config、弹窗、Toast、analytics 等全局能力在哪里挂载。
7. 选一个简单页面读 route 到 feature 的链路，例如 `src/routes/(main)/page/index.tsx` 到 `src/features/PageExplorer`，或者 `src/routes/onboarding/index.tsx` 到 `src/features/Onboarding/Common`。
8. 再读一个核心业务链路，例如 `src/routes/(main)/agent/index.tsx`、`src/features/Conversation`、`src/store/chat`、`src/services/aiChat.ts` 或 `src/services/agent.ts`。
9. 想理解前后端通信时，读 `src/libs/trpc/client/lambda.ts`、`src/app/(backend)/trpc/lambda/[trpc]/route.ts`、`src/server/routers/lambda/index.ts`。
10. 想理解服务端业务时，选一个 router 和 service 成对阅读，例如 agent：`src/server/routers/lambda/agent.ts` 与 `src/server/services/agent/index.ts`。
11. 最后再读配置与环境：`src/envs/app.ts`、`src/server/globalConfig/index.ts`、`src/store/serverConfig/Provider.tsx`、`src/store/serverConfig/store.ts`。

如果目标是改 UI，优先读 `routes`、`features`、`components`、`layout`。如果目标是改数据请求，优先读 `services`、`store`、`libs/trpc`。如果目标是改后端能力，优先读 `app/(backend)`、`server/routers`、`server/services`、`server/modules`。

## 常见误区

不要把 `src/app` 当成所有页面的所在地。当前主交互页面大多是 SPA，页面段在 `src/routes`，真正 UI 又常常在 `src/features`。`src/app` 更多负责 Next 后端入口、认证 SSR 页面、SPA HTML 模板和全局 metadata。

不要在 `src/routes` 里堆业务逻辑。仓库约定 route 文件应该薄，主要导入 `@/features/*` 并组合布局/页面。复杂 UI、hooks、状态联动应放到 `src/features/<Domain>` 或更合适的共享层。

不要只改 `desktopRouter.config.tsx` 而忘记 `desktopRouter.config.desktop.tsx`。仓库明确要求桌面路由两份配置路径和嵌套保持同步，否则某些构建路径可能出现空白屏，`desktopRouter.sync.test.tsx` 就是守这个约束的。

不要把 `components` 和 `features` 混为一谈。`components` 是跨业务复用的小组件，`features` 是面向具体业务场景的大组件或模块。比如通用 `Loading`、`ModelSelect` 更适合 `components`，而 `Conversation`、`PageEditor`、`CommandMenu` 属于 `features`。

不要让前端直接散落调用 tRPC。当前代码倾向通过 `src/services` 封装后端调用，再由 store/action 或 feature 使用。这样可以集中处理 URL、header、认证、错误通知和平台差异。

不要忽略 `SPAGlobalProvider`。很多“为什么页面里能用主题/语言/认证/store/Modal/Toast”的答案都在这里。如果绕过这个 Provider 单独渲染某个页面，可能会缺上下文。

不要误以为所有配置都来自客户端。`src/app/spa/[variants]/[[...path]]/route.ts` 会把服务端配置注入 HTML；`src/server/globalConfig/index.ts` 会根据 env 和服务端能力生成 `GlobalServerConfig`；前端再通过 `ServerConfigStoreProvider` 注入 store。

不要混淆客户端 `services` 和服务端 `server/services`。`src/services/agent.ts` 是浏览器侧代理，负责调用 `lambdaClient.agent.*`；`src/server/services/agent/index.ts` 才是真正访问数据库模型、合并默认配置、处理 Redis welcome 数据的服务端实现。

不要在运行环境不明确时直接使用浏览器或 Node API。这个目录同时包含浏览器 SPA、Next server、Electron desktop、移动端和 popup。代码中已经有 `.desktop.ts`、`.vite.ts`、`isDesktop`、`typeof window !== 'undefined'`、`import.meta.env.PROD` 等分支，新增逻辑要先确认运行在哪一侧。

不要看到 `dynamicElement()` 就以为只是语法糖。它统一了懒加载、Suspense loading、模块 default 解析和 chunk 失败提示；路由表大量依赖它来减少首屏体积。

不要随便改 env schema。`src/envs/*.ts` 使用 `zod` 和 `createEnv` 校验环境变量，改动会影响启动、构建和服务端配置输出。新增环境变量时需要考虑 client/server 前缀、默认值、生产环境是否必填，以及是否要暴露给 `SPAServerConfig`。
