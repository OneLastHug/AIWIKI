# 目录：src/app

## 它负责什么

`src/app` 是这个仓库的 Next.js App Router 层，主要承担三类职责：后端 HTTP 入口、需要服务端渲染的认证页面、以及承载前端 SPA 的 HTML 模板服务。它不是主要业务 UI 的聚集地；常规聊天、设置、工作区等 SPA 页面更多在 `src/routes`、`src/features`、`src/spa/router` 中组织。`src/app` 更像是“外壳与网关”：把浏览器请求、API 请求、认证回调、tRPC 调用、文件代理、市场接口等接入到后面的 `src/server`、`src/services`、`src/database`、`src/libs`。

从当前结构看，`src/app` 同时服务 Next.js 与内嵌 SPA。根布局 `src/app/layout.tsx` 提供全局 HTML/body 包裹，并挂载 `Analytics` 与 Vercel `SpeedInsights`。真正的 SPA 页面入口在 `src/app/spa/[variants]/[[...path]]/route.ts`，它根据语言、移动端标识等 `variants` 生成 HTML，把服务端配置、feature flags、analytics 配置和客户端环境变量序列化注入 `window.__SERVER_CONFIG__`。这解释了为什么很多用户可见页面并不直接出现在 `src/app` 下：Next.js 负责吐出 SPA 容器，后续路由由 `react-router-dom` 接管。

## 直接子目录地图

`src/app/(backend)` 是后端路由组。括号目录不会进入 URL 路径，本质上是把 API route handlers 组织在一起。这里包含 `api`、`trpc`、`webapi`、`market`、`oidc`、`middleware`、`f` 等子目录，是大部分服务端请求的入口。

`src/app/[variants]` 是带动态段的页面区域，当前主要承载 `(auth)` 认证相关页面。`variants` 用来区分 locale、mobile 等运行变体。其下的 `(auth)` 包含 `signin`、`signup`、`reset-password`、`verify-email`、`verify-im`、`auth-error`、`oauth`、`market-auth-callback` 等认证流程页面，以及 `_layout` 和工具函数。

`src/app/spa` 是 SPA HTML 服务入口。它通过 `src/app/spa/[variants]/[[...path]]/route.ts` 捕获 SPA 路径，返回注入配置后的 HTML。开发模式下会从 Vite dev server 读取模板并重写资源地址；生产模式下使用构建生成的 HTML 模板声明与源码模板。

此外，`src/app/layout.tsx` 是整个 App Router 的根布局，不属于某个子目录，但会包裹 `src/app` 下的页面和 route 输出。

## 关键入口

`src/app/layout.tsx` 是根布局入口，定义 `<html>`、`<body>` 基础结构，并在 `Suspense` 中挂载 `Analytics` 和 Vercel 性能采集。它的职责很薄，不承载业务页面结构。

`src/app/spa/[variants]/[[...path]]/route.ts` 是 SPA 的关键入口。它导出 `generateStaticParams()` 生成静态 variants，并导出 `GET()` 返回 HTML。`GET()` 会解析 `RouteVariants.deserializeVariants(variants)`，获得 `locale` 和 `isMobile`，然后读取 `getServerGlobalConfig()`、`getServerFeatureFlagsValue()`，构造 `SPAServerConfig`，替换模板里的 `window.__SERVER_CONFIG__` 占位符，并注入 SEO meta。根据当前片段推断，这是 Web/Mobile SPA 首屏配置下发的中心位置，依据是它同时处理模板、服务端配置、feature flags、analytics 和 SEO。

`src/app/[variants]/(auth)/layout.tsx` 是认证页布局入口。它读取动态 `variants`，用 `AuthGlobalProvider`、`ClientOnly`、`NuqsAdapter`、`BusinessAuthProvider` 和 `AuthContainer` 包裹认证子页面。认证页是少数仍留在 `src/app` 下的用户界面，因为它们需要 SSR/认证上下文和独立页面流程。

`src/app/(backend)/trpc/*/[trpc]/route.ts` 是 tRPC HTTP 桥接入口，例如 `src/app/(backend)/trpc/lambda/[trpc]/route.ts` 使用 `fetchRequestHandler`，绑定 `lambdaRouter`、`createLambdaContext()` 和 `createResponseMeta()`。同类目录还有 `async`、`mobile`、`tools`，对应不同服务端 router 分组。

`src/app/(backend)/webapi/*/route.ts` 是传统 REST/流式接口入口。例如 `src/app/(backend)/webapi/chat/[provider]/route.ts` 通过 `checkAuth` 获取用户和数据库上下文，再用 `initModelRuntimeFromDB()` 初始化模型运行时，最后调用 `modelRuntime.chat()` 返回聊天流。

`src/app/(backend)/api/auth/[...all]/route.ts` 是认证 API 入口，基于 `better-auth/next-js` 的 `toNextJsHandler(auth)` 转成 Next.js handler，并在 POST 前额外校验 JSON body，把 malformed JSON 明确返回 400。

`src/app/(backend)/oidc/[...oidc]/route.ts` 是 OIDC Provider 兼容入口。它把 Next.js `NextRequest` 转成 Node 风格 request/response，交给 `provider.callback()` 处理，最后再转换回 `NextResponse`。

`src/app/(backend)/f/[id]/route.ts` 是文件访问代理入口。它按文件 id 查库，生成预签名访问 URL，并可用 Redis 缓存短期跳转地址，最后返回 302 redirect。

## 主流程位置

SPA 首屏主流程在 `src/app/spa/[variants]/[[...path]]/route.ts`：请求进入 `GET()`，解析 variants，加载模板，构造 `SPAServerConfig`，序列化注入 HTML，然后返回给浏览器。浏览器拿到 HTML 后，后续页面导航主要进入 `src/spa/entry.*.tsx`、`src/spa/router/*` 和 `src/routes/*`，不再由 `src/app` 逐页渲染。

认证页面主流程在 `src/app/[variants]/(auth)`：`layout.tsx` 先搭建认证上下文，再进入 `signin/page.tsx`、`reset-password/page.tsx`、`verify-email/page.tsx` 等页面。认证 API 则通过 `src/app/(backend)/api/auth/[...all]/route.ts` 对接 `@/auth`。

业务 API 主流程分两条：类型安全的客户端服务通常走 `src/app/(backend)/trpc/*/[trpc]/route.ts`，再进入 `src/server/routers/*`；模型、语音、图片、trace、revalidate 等 HTTP 能力则走 `src/app/(backend)/webapi/*`，再进入 `src/server/modules`、`src/server/services`、`src/database` 或运行时包。

市场与外部集成流程集中在 `src/app/(backend)/market` 和 `src/app/(backend)/oidc`。`market` 目录通过 `MarketService.createFromRequest(req)` 获取 market 客户端，再处理 agent、user、social、oidc 相关接口；`oidc` 目录负责授权服务、回调、consent、handoff、clear-session 等身份协议流程。

## 推荐阅读顺序

1. 先读 `src/app/layout.tsx`，理解 App Router 根布局只做全局壳层，不是主要业务页面入口。
2. 再读 `src/app/spa/[variants]/[[...path]]/route.ts`，这是理解“Next.js 承载 SPA”的关键。重点看 `generateStaticParams()`、`GET()`、`getTemplate()`、`buildAnalyticsConfig()`、`buildClientEnv()`、`buildSeoMeta()`。
3. 接着看 `src/app/[variants]/(auth)/layout.tsx` 和几个认证 `page.tsx`，理解为什么认证页留在 `src/app`，以及它和 `BusinessAuthProvider`、`AuthGlobalProvider` 的关系。
4. 然后看 `src/app/(backend)/trpc/lambda/[trpc]/route.ts`，再顺着 `lambdaRouter` 去 `src/server/routers/lambda`，建立 tRPC 请求从 HTTP 到 server router 的链路。
5. 再看 `src/app/(backend)/webapi/chat/[provider]/route.ts`，它代表模型运行时类接口的典型路径：鉴权、中间件、初始化 runtime、调用服务、错误响应。
6. 最后按需求浏览 `api/auth`、`oidc`、`market`、`f`，分别对应认证、身份协议、市场服务和文件代理。

## 常见误区

不要把 `src/app` 当成全部前端页面目录。这个项目的常规 SPA 页面主要在 `src/routes`，页面业务组件在 `src/features`，路由配置在 `src/spa/router`；`src/app/spa` 只是返回 SPA HTML 的服务端入口。

不要误以为 `(backend)` 会出现在 URL 中。它是 Next.js route group，用于组织文件，不参与路径匹配。真实路径由其下的 `api`、`trpc`、`webapi`、`market`、`oidc`、`f` 等目录决定。

不要把 `api`、`webapi`、`trpc` 混为一类。`trpc` 是类型安全 RPC 网关，后面接 `src/server/routers`；`webapi` 更像面向模型、语音、图片等能力的 HTTP/streaming 接口；`api` 放认证、webhook、workflow、v1、dev 等更杂的 App Router API。

不要在 `src/app` 下新增厚重业务 UI。按照仓库约定，SPA route segment 应保持薄，业务 UI 应放到 `src/features`，路由树放 `src/routes`，App Router 只处理必须 SSR 或必须由 Next route handler 接管的入口。

不要忽略 `variants`。`src/app/spa/[variants]` 和 `src/app/[variants]/(auth)` 都依赖它表达 locale、mobile 等变体；如果新增入口时绕开这套机制，可能导致移动端、桌面端或多语言首屏配置不一致。

不要直接在 route handler 中堆积数据库和业务逻辑。现有模式通常是 route handler 做边界处理、鉴权、参数解析和响应封装，核心逻辑下沉到 `src/server/services`、`src/server/modules`、`src/database` 或对应 runtime 包。
