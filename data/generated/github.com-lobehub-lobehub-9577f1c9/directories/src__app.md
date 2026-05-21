# 目录：src/app

## 它负责什么

`src/app` 是 LobeHub 在 Next.js App Router 层的入口目录，但它并不承载主要业务页面。这个项目的主应用 UI 是 SPA，页面段落主要放在 `src/routes`，路由配置在 `src/spa/router`；`src/app` 更像一个“外壳与服务端入口层”，负责把 Next.js 能力接到 SPA、认证、API、SEO 和平台能力上。

从当前目录结构看，它主要承担四类职责：

1. **全局 Next.js 外壳**：`layout.tsx` 提供根 HTML/body、全局 Analytics、Vercel Speed Insights。
2. **SPA HTML 服务**：`spa/[variants]/[[...path]]/route.ts` 根据语言、移动端标记、服务端配置和特性开关，返回注入配置后的 SPA HTML。
3. **后端 Route Handler**：`(backend)` 下放置 `trpc`、`webapi`、`market`、`oidc`、`f` 等服务端 HTTP 入口。
4. **SSR 认证页面**：`[variants]/(auth)` 下放置登录、重置密码、邮箱验证、认证错误页等需要 Next.js SSR/路由能力的页面。

因此阅读 `src/app` 时，不要把它当成传统 Next.js 页面目录。它是 Next.js 与项目内 SPA、服务端路由、认证系统之间的连接层。

## 关键组成

`src/app/layout.tsx` 是根布局。它输出 `<html>`、`<body>`，挂载 `Analytics`，并在 Vercel 环境下挂载 `SpeedInsights`。这里没有业务页面布局，也没有全局状态初始化，说明主应用 UI 不从这里展开。

`src/app/[variants]/metadata.ts` 负责动态生成页面元信息。它通过 `RouteVariants.getLocale(props)` 解析当前变体中的 locale，再调用 `translation('metadata', locale)` 取国际化文案，结合 `BRANDING_NAME`、`BRANDING_LOGO_URL`、`OFFICIAL_URL`、`OG_URL` 生成 title、description、icons、Open Graph、Twitter card 等 SEO 信息。

`src/app/manifest.ts` 生成 PWA manifest。开发环境下返回轻量 manifest，避免编译重模块；生产环境动态 import `@lobechat/business-const`、`es-toolkit/compat` 和 `@/server/manifest`，再用品牌信息生成完整 manifest。

`src/app/robots.tsx` 和 `src/app/sitemap.tsx` 是搜索引擎入口。它们都设置了 `revalidate = 86400` 和 `dynamic = 'force-static'`。`robots.tsx` 使用 `Sitemap` 和 `getCanonicalUrl()` 输出 robots 规则；`sitemap.tsx` 使用 `Sitemap` 服务生成 pages、assistants、plugins、models、providers 等 sitemap，并支持分页 sitemap，例如 `plugins-1`、`assistants-2`。

`src/app/spa/[variants]/[[...path]]/route.ts` 是 SPA 外壳服务的核心。它的 `generateStaticParams()` 会为 `en-US`、`zh-CN` 以及移动/桌面组合生成 variants。`GET()` 会反序列化 variants，拿到 `locale` 和 `isMobile`，读取 `getServerGlobalConfig()`、`getServerFeatureFlagsValue()`、analytics env、client env，然后把这些内容序列化进 `window.__SERVER_CONFIG__`。生产环境使用构建好的 `desktopHtmlTemplate` / `mobileHtmlTemplate`，开发环境则从 `[URL已移除] 拉 Vite HTML，并重写 script/link/Worker URL。

`src/app/(backend)` 是后端 HTTP 入口集合。括号目录是 Next.js route group，不进入 URL 路径，所以 `src/app/(backend)/api/version/route.ts` 实际暴露为 `/api/version`，`src/app/(backend)/trpc/lambda/[trpc]/route.ts` 暴露为 `/trpc/lambda/...`。

`src/app/(backend)/trpc/*/[trpc]/route.ts` 把请求交给 `@trpc/server/adapters/fetch` 的 `fetchRequestHandler`，分别挂接 `lambdaRouter`、`mobileRouter`、`asyncRouter`、`toolsRouter`。它们共同使用 `prepareRequestForTRPC()` 处理 Next.js 16 请求体读取问题，并通过 `createResponseMeta` 生成响应元信息。

`src/app/(backend)/middleware` 提供后端路由复用中间件。`auth/index.ts` 的 `checkAuth(handler)` 支持开发 mock 用户、OIDC JWT、Better Auth session 三种认证路径，认证成功后把 `serverDB`、`userId`、`jwtPayload` 注入 handler，并处理 trace header。`validate/createValidator.ts` 用 zod 校验请求输入，GET/HEAD 从 query 取值，JSON 请求从 body 取值，失败时返回 422。

`src/app/(backend)/oidc` 负责 OIDC Provider 和桌面端登录交接。`[...oidc]/route.ts` 把 NextRequest/NextResponse 适配到 Node.js request/response 后交给 `oidc-provider` middleware。`consent/route.ts` 处理授权确认。`callback/desktop/route.ts` 把桌面端回调中的 `code` 和 `state` 写入 `OAuthHandoffModel`，再跳转到成功页。`handoff/route.ts` 供客户端轮询并消费这份凭据。

`src/app/(backend)/f/[id]/route.ts` 是文件代理。它按文件 id 查数据库，使用 `FileService.createPreSignedUrlForPreview()` 生成 S3 预签名地址，并用 Redis 缓存 4 分钟，最后 302 跳转到真实文件地址。

`src/app/[variants]/(auth)` 是认证页面组。`layout.tsx` 包裹 `AuthGlobalProvider`、`ClientOnly`、`NuqsAdapter`、`BusinessAuthProvider` 和 `AuthContainer`。`signin/page.tsx` 使用 `useSignIn()` 在邮箱步骤和密码步骤之间切换；`useSignIn.ts` 会调用 `/api/auth/resolve-username`、`/api/auth/check-user`、Better Auth 的 `signIn.email` / `signIn.magicLink`，并处理社交登录、callbackUrl、邮箱验证跳转等流程。

## 上下游关系

上游看，`src/app` 接收来自浏览器、桌面端、CLI、搜索引擎、Vite dev server 和市场服务客户端的请求。不同入口对应不同协议：普通页面请求进入 SPA HTML route，API 请求进入 `(backend)` route handler，认证交互进入 `[variants]/(auth)` 或 `oidc`，爬虫访问 `robots.txt` / sitemap / metadata。

下游看，`src/app` 很少自己实现核心业务，而是调用其他层：

- 配置来自 `@/server/globalConfig`、`@/config/featureFlags`、`@/envs/*`。
- 国际化来自 `@/server/translation` 和 locale 资源。
- tRPC 具体业务来自 `@/server/routers/lambda`、`mobile`、`async`、`tools`。
- 文件、市场、OIDC 等能力来自 `@/server/services/*`、`@/database/*`、`@/libs/*`。
- 认证客户端逻辑连接 `@/libs/better-auth/auth-client` 和 `@/business/client/*`。
- SPA 真正运行后，会进入 `src/spa/entry.*.tsx`、`src/spa/router`、`src/routes`、`src/features`、`src/store` 等目录。

可以把 `src/app` 理解成“协议入口层”：它关心 URL、HTTP method、headers、cookies、HTML 注入、Next.js metadata、Response 格式；业务状态和复杂 UI 通常在别处。

## 运行/调用流程

主应用访问流程大致是：浏览器请求某个 SPA 路径，Next.js 命中 `src/app/spa/[variants]/[[...path]]/route.ts`，从 variants 解析 locale 和移动端状态，加载服务端全局配置、feature flags、analytics 配置和 client env，把它们注入 HTML 里的 `window.__SERVER_CONFIG__`，再返回 `text/html`。浏览器加载 HTML 中的 Vite/静态资源后，React SPA 启动，后续页面切换主要由 `react-router-dom` 接管。

开发环境下，这个流程多了一步：`getTemplate()` 会请求 `[URL已移除] 的 Vite dev server，并用 `rewriteViteAssetUrls()` 把相对的 script/link/module import 改成 Vite origin，避免通过线上代理打开本地 SPA 时资源地址错位。

tRPC 请求流程是：前端 service 或 store action 请求 `/trpc/lambda`、`/trpc/mobile`、`/trpc/async` 或 `/trpc/tools`，对应 route handler 调用 `prepareRequestForTRPC(req)`，再由 `fetchRequestHandler` 创建上下文、分发到对应 router。router 内部再进入 server services、database model 或外部服务。

登录流程以 `/signin` 为例：Next.js 渲染 `[variants]/(auth)/layout.tsx` 和 `signin/page.tsx`，页面先展示邮箱/用户名步骤。`useSignIn()` 解析 query 中的 `email` 和 `callbackUrl`，检查用户是否存在；如果不存在跳转注册，如果有密码则进入密码步骤，如果没有密码且启用 magic link 则发送登录邮件。密码登录成功后跳回 `callbackUrl`，403 时跳转 `/verify-email`。

OIDC/桌面登录流程中，OIDC provider 的协议请求进入 `/oidc/...`，用户授权走 `/oidc/consent`，桌面回调进入 `/oidc/callback/desktop` 写入 handoff 记录，桌面客户端再通过 `/oidc/handoff?id=...&client=desktop` 轮询并消费凭据。

## 小白阅读顺序

1. 先看 `src/app/layout.tsx`，理解根布局很薄，只负责 HTML 外壳和统计组件。
2. 再看 `src/app/spa/[variants]/[[...path]]/route.ts`，这是理解“Next.js 托管 SPA”的关键文件，重点看 `generateStaticParams()`、`getTemplate()`、`GET()`。
3. 接着看 `src/app/[variants]/metadata.ts`、`manifest.ts`、`robots.tsx`、`sitemap.tsx`，理解 SEO/PWA/爬虫入口如何接入服务端配置和品牌信息。
4. 然后看 `src/app/(backend)/trpc/lambda/[trpc]/route.ts`，再横向比较 `mobile`、`async`、`tools`，掌握 tRPC route handler 的统一模式。
5. 再读 `src/app/(backend)/middleware/auth/index.ts` 和 `middleware/validate/createValidator.ts`，理解后端入口如何复用认证、DB、trace、zod 校验。
6. 最后按需求读具体业务入口：认证看 `[variants]/(auth)/signin`，文件访问看 `(backend)/f/[id]/route.ts`，OIDC 看 `(backend)/oidc`，市场接口看 `(backend)/market`。

## 常见误区

`src/app` 不是主业务页面目录。主聊天、设置、工作区等 SPA 页面通常不在这里，而在 `src/routes` 和 `src/features`。如果只在 `src/app` 找页面，很容易误判项目结构。

`(backend)` 不会出现在 URL 中。Next.js 的括号目录是 route group，例如文件路径 `src/app/(backend)/webapi/revalidate/route.ts` 对应 URL 是 `/webapi/revalidate`，不是 `/(backend)/webapi/revalidate`。

`[variants]` 不是普通业务 id。它承载类似 locale、mobile/desktop 这类路由变体信息，代码通过 `RouteVariants.serializeVariants()` 和 `deserializeVariants()` 解析，不应当当成用户数据或页面资源 id。

SPA HTML route 返回的是“带配置的 HTML 壳”，不是 React 页面组件。`GET()` 里主要做模板选择、服务端配置注入和 SEO meta 替换，真正的交互 UI 在 HTML 加载的 SPA bundle 里。

开发环境的 `[URL已移除] 是 Vite SPA dev server，不是 Next.js 主服务。`rewriteViteAssetUrls()` 的存在说明本地调试依赖 Vite 资源重写和 Debug Proxy；看到线上域名或本地端口混用时不要马上认为是错误。

认证页面虽然在 `src/app`，但大量逻辑仍依赖 Better Auth、business provider、server config store 和后端 `/api/auth/*`。阅读登录问题时，只看 `signin/page.tsx` 不够，必须继续看 `useSignIn.ts` 和相关 API route。

`checkAuth` 里有开发 mock 路径，但它只在 `NODE_ENV === 'development'` 且特定 header/env 开启时生效。不要把 mock 用户逻辑理解成生产认证路径。生产主要走 OIDC JWT 或 Better Auth session。
