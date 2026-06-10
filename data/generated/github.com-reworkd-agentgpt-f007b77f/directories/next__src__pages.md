# 目录：next/src/pages

## 它负责什么

`next/src/pages` 是这个 Next.js 前端应用的 Pages Router 路由层，负责把 URL 映射到页面组件或 API endpoint。它不是单纯的“页面 UI 文件夹”：这里同时包含浏览器页面入口、全局 App 包装器、认证回调 API、tRPC API 入口，以及少量静态生成页面。

从当前片段看，应用的核心体验是 AgentGPT 风格的 agent 控制台。根页面 `next/src/pages/index.tsx` 是主要入口，负责根据用户输入创建并运行 agent；全局入口 `next/src/pages/_app.tsx` 负责挂载 `SessionProvider`、tRPC client、i18n、统计组件和全局样式。后端交互则通过 `next/src/pages/api/trpc/[trpc].ts` 接入 `server/api` 下的 tRPC router，通过 `next/src/pages/api/auth/[...nextauth].ts` 接入 NextAuth。

因此，这个目录更像是“应用路由编排层”：真正的 UI 组件在 `next/src/components`，布局在 `next/src/layout`，agent 运行逻辑在 `next/src/services/agent`，服务端 API router 和认证配置在 `next/src/server`。`pages` 负责把这些模块组合成可访问的页面和接口。

## 直接子目录地图

`next/src/pages/agent`：agent 详情或历史记录相关页面。目前可见入口是 `next/src/pages/agent/index.tsx`，它使用 `api.agent.findById.useQuery`、`api.agent.deleteById.useMutation` 等 tRPC hook，说明它主要读取或操作已保存的 agent 数据。根据当前片段推断，这里不是 agent 实时运行主入口，而是与持久化 agent 记录相关的页面。

`next/src/pages/api`：Next.js API Routes 目录，承载服务端 endpoint。它下面的 `auth` 接入 NextAuth，`trpc` 接入 tRPC。这里的文件会运行在服务端上下文，不是 React 页面组件。

`next/src/pages/blog`：博客文章动态路由目录。`next/src/pages/blog/[slug].tsx` 暴露 `getStaticPaths` 和 `getStaticProps`，说明文章页面采用静态生成；顶层 `next/src/pages/blog.tsx` 则像是博客列表页，也有 `getStaticProps`。

## 关键入口

`next/src/pages/_app.tsx` 是全局入口。它导入 `globals.css`，用 `SessionProvider` 注入 NextAuth session，用 `appWithTranslation` 接入 `next-i18next`，再用 `api.withTRPC` 包装整个应用。也就是说，页面组件里能直接使用 `useTranslation`、`useAuth`、`api.xxx.useQuery` 这类能力，是从这里开始接上的。

`next/src/pages/index.tsx` 是根路由 `/`，也是应用主流程的核心页面。它组合 `DashboardLayout`、`Landing`、`Chat`、`HelpDialog`、`SignInDialog`，并通过 zustand 风格的 store 管理 messages、tasks、agent lifecycle、输入内容等状态。用户输入 goal 后，页面会创建 `DefaultAgentRunModel`、`MessageService`、`AgentApi`、`AutonomousAgent`，然后调用 `newAgent.run()` 启动 agent。

`next/src/pages/api/trpc/[trpc].ts` 是 tRPC 服务端入口。它使用 `createNextApiHandler`，挂载 `appRouter` 和 `createTRPCContext`。实际 router 定义不在这里，而在 `next/src/server/api/root.ts` 及其 routers 中；上下文创建逻辑在 `next/src/server/api/trpc.ts`。

`next/src/pages/api/auth/[...nextauth].ts` 是认证入口。它把请求交给 `NextAuth(req, res, authOptions(req, res))`，认证策略、adapter、session 等具体配置在 `next/src/server/auth` 侧。

## 主流程位置

用户主流程从 `next/src/pages/index.tsx` 开始。页面加载后先通过 `getStaticProps` 准备翻译资源，运行时由 `_app.tsx` 提供 session、tRPC 和 i18n 环境。进入根页面后，如果还没有 agent，则显示 `Landing`；如果已经创建 agent，则切到 `Chat`。

启动 agent 的关键流程集中在 `handlePlay` 和 `handleNewAgent`。如果用户未登录，页面会把 agent name 和 goal 暂存到 `localStorage`，再打开登录弹窗；登录后通过 effect 读回数据。若用户已登录，页面会把当前 settings、session、goal、agentUtils 传给 `AgentApi`，再构造 `AutonomousAgent` 并放入 `useAgentStore`，最后调用 `run()`。消息追加由 `MessageService(addMessage)` 连接到 message store，任务和生命周期由 stores 管理。

服务端主流程则从 `next/src/pages/api/trpc/[trpc].ts` 进入，进入后转到 `next/src/server/api/trpc.ts` 创建 context，再进入 `next/src/server/api/root.ts` 暴露的 router。当前搜索结果显示 `agentRouter` 提供 `create`、查询、删除等 agent 相关 procedure，页面中的 `api.agent.*` hook 最终会落到这些 procedure 上。

认证流程从 `next/src/pages/api/auth/[...nextauth].ts` 进入，实际行为由 `next/src/server/auth/auth.ts`、`next/src/server/auth/index.ts`、`next/src/server/auth/local-auth.ts` 等邻近模块决定。`signin.tsx` 作为页面入口，使用 `getServerSideProps`，说明登录页需要服务端上下文判断或准备认证状态。

## 推荐阅读顺序

1. 先读 `next/src/pages/_app.tsx`，理解全局 wrapper：session、i18n、tRPC、analytics 和全局样式是如何接入的。
2. 再读 `next/src/pages/index.tsx`，这是用户启动 agent 的主页面，也是理解产品核心交互的最佳入口。
3. 顺着 `index.tsx` 的 imports 看 `next/src/services/agent`、`next/src/stores`、`next/src/hooks/useAgent`、`next/src/hooks/useAuth`，理解 agent 运行、消息、任务、认证和设置如何协作。
4. 然后读 `next/src/pages/api/trpc/[trpc].ts`、`next/src/server/api/trpc.ts`、`next/src/server/api/root.ts`，把前端 `api.agent.*` hook 和后端 procedure 对上。
5. 接着看 `next/src/pages/api/auth/[...nextauth].ts` 和 `next/src/server/auth`，理解登录态从哪里来。
6. 最后再看辅助页面：`settings.tsx` 负责模型、语言、API key 等设置；`templates.tsx` 负责模板搜索和展示；`agent/index.tsx` 负责已保存 agent 的读取或管理；`blog.tsx`、`blog/[slug].tsx` 负责内容型静态页面。

## 常见误区

不要把 `next/src/pages` 当成全部业务代码所在地。这里主要是路由入口和编排层，大量真实逻辑分散在 `components`、`layout`、`services`、`stores`、`server`、`utils` 中。只读 `pages` 能知道流程从哪里进入，但无法完整理解 agent 如何执行。

不要把 `next/src/pages/api` 理解成普通前端目录。`pages/api` 下的文件是服务端 API Routes，其中 `api/trpc/[trpc].ts` 是 tRPC 聚合入口，`api/auth/[...nextauth].ts` 是认证入口；它们不会渲染页面。

不要把 `next/src/pages/index.tsx` 当成纯 landing page。虽然它会渲染 `Landing`，但它同时持有启动 agent 的关键控制逻辑，包括登录拦截、localStorage 暂存、agent 实例化、重启、键盘触发和 Chat/Landing 切换。

不要误以为所有页面都是 SSR。当前片段显示多处页面使用 `getStaticProps` 加载翻译或内容，例如 `index.tsx`、`templates.tsx`、`settings.tsx`、博客页面；而 `signin.tsx` 使用 `getServerSideProps`。不同页面的数据准备策略并不相同。

不要忽略 `_app.tsx`。如果页面中 tRPC hook、NextAuth session 或翻译看起来“凭空可用”，根因通常在 `_app.tsx` 的 `api.withTRPC(appWithTranslation(...))` 和 `SessionProvider`。
