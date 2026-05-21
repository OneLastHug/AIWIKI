# 目录：src/libs/next

## 它负责什么

`src/libs/next` 是 LobeHub 在 Next.js 与 Vite/SPA 双运行环境之间做兼容的适配层。它的核心目的不是实现业务逻辑，而是把项目里常见的 Next.js API 包一层，让上层组件尽量使用统一入口，减少“某段代码只能在 Next App Router 下运行、不能在 SPA 下运行”的割裂。

从目录内容看，它主要承担三类职责：

1. **组件 API 兼容**  
   用 `Image.tsx`、`Link.tsx`、`dynamic.tsx` 提供类似 `next/image`、`next/link`、`next/dynamic` 的接口，但在 SPA 场景下落到普通 React、`react-router-dom` 或原生 DOM 元素。

2. **导航 API 兼容**  
   `navigation.ts` 默认转发 `next/navigation`，而 `navigation.vite.ts` 提供 SPA 版本实现。这样业务侧可以通过 `@/libs/next/navigation` 使用 `useRouter`、`usePathname`、`useSearchParams` 等能力。

3. **Next 配置与 middleware/proxy 配置集中化**  
   `config/define-config.ts` 包装 `next.config.ts` 的配置生成；`proxy/define-config.ts` 包装 Next middleware/proxy 逻辑，统一处理 API 跳过、SPA rewrite、Next-only routes、locale、设备类型、登录保护等。

这个目录可以理解为项目的“Next 兼容边界”：上游业务代码不直接关心当前是在 Next SSR/App Router、Vite SPA、桌面端还是移动端构建里，而是尽量通过这里暴露的稳定接口来访问 Next 风格能力。

## 关键组成

`index.ts` 是目录的统一出口：

```ts
export * from './navigation';
export { default as dynamic } from './dynamic';
export { default as Image } from './Image';
export { default as Link } from './Link';
```

它把导航、动态加载、图片、链接这几个最常用的 Next API 聚合起来。实际调用中，也有不少文件直接从具体文件导入，例如 `@/libs/next/dynamic`、`@/libs/next/Image`。

`Image.tsx` 是 `next/image` 的轻量替代。它定义了 `StaticImageData` 和 `ImageProps`，支持 `src` 传字符串或静态图片对象。实现上最终渲染的是普通 `<img>`。如果传入 `fill`，它会补上 `position: absolute`、`width: 100%`、`height: 100%`、`objectFit: cover` 等样式，以模拟 Next Image 的 `fill` 语义。`priority`、`quality`、`unoptimized` 等属性被接收但不会真正驱动 Next 的图片优化流程。

`Link.tsx` 是 `next/link` 的兼容适配。它接收 `href`，内部判断是否为外链或 Next-only 路由。如果是 `[URL已移除] 开头，或者命中 `nextjsOnlyRoutes`，就渲染普通 `<a>`；否则渲染 `react-router-dom` 的 `Link`，并把 `href` 转成 `to`。这让 SPA 内部路由走前端跳转，同时认证页、OAuth、欢迎页等仍交给 Next App Router。

`dynamic.tsx` 是 `next/dynamic` 的近似实现。它用 `React.lazy` 加 `Suspense` 包装异步组件加载，支持常见调用形式：

```ts
dynamic(() => import('./Foo'), { loading: () => <Spinner /> })
```

它会处理 loader 返回 `default export` 或直接返回组件函数两种情况。如果动态 import 结果为空，会抛出明确错误。`ssr` 选项只保留在类型和调用兼容层面，从当前实现看并不会真正控制 SSR 行为。

`navigation.ts` 是 Next 运行时版本，直接从 `next/navigation` 转发：

```ts
notFound
redirect
useParams
usePathname
useRouter
useSearchParams
```

文件注释说明，在 Vite/SPA 模式下它会通过 `viteModuleRedirect` 插件替换成 `navigation.vite.ts`。根据当前片段推断，这个替换发生在 Vite 共享插件配置中，但本次读取未定位到具体插件定义。

`navigation.vite.ts` 是 SPA 版本。它基于 `react-router-dom` 实现：

- `useRouter()` 包装 `useNavigate()`，提供 `push`、`replace`、`back`、`forward`、`refresh`
- `usePathname()` 返回 `useLocation().pathname`
- `useParams`、`useSearchParams` 直接从 `react-router-dom` 转发
- `redirect(url)` 抛出自定义 `RedirectError`
- `notFound()` 抛出带 `digest = 'NEXT_NOT_FOUND'` 的 `NotFoundError`

这不是 Next 行为的完全复刻，而是为了让 SPA 端已有调用不需要大面积改写。

`nextjsOnlyRoutes.ts` 定义不能进入 SPA catch-all 的路径：

```ts
/signin
/signup
/auth-error
/reset-password
/verify-email
/oauth
/market-auth-callback
/discover
/welcome
/verify-im
```

它被 `Link.tsx` 和 `proxy/define-config.ts` 共同使用，保证客户端跳转与服务端 rewrite 对这些路径的判断一致。

`config/define-config.ts` 是 `next.config.ts` 的配置工厂。`next.config.ts` 只做了一层很薄的调用：

```ts
import { defineConfig } from './src/libs/next/config/define-config';

const nextConfig = defineConfig({
  ...(isVercel ? vercelConfig : {}),
});

export default nextConfig;
```

从已读片段看，`defineConfig` 负责合并生产环境、Docker standalone、CSP、assetPrefix、compiler、experimental.optimizePackageImports、缓存头、输出追踪 include/exclude 等 Next 配置。它把复杂配置从根目录 `next.config.ts` 下沉到 `src/libs/next/config`，让根配置保持简洁。

`proxy/createRouteMatcher.ts` 是一个小工具，把路由模式数组编译为正则 matcher。它支持 `(.*)` 通配符，并会先转义其他正则特殊字符，避免 `/api/v1.0/users` 里的 `.` 被误当成任意字符。测试文件 `createRouteMatcher.test.ts` 覆盖了精确匹配、通配符、多 pattern、特殊字符、根路径、空数组、大小写敏感等场景。

`proxy/define-config.ts` 是 middleware/proxy 的核心。`src/proxy.ts` 只负责调用它：

```ts
import { defineConfig } from '@/libs/next/proxy/define-config';

const { middleware } = defineConfig();

export const config = { matcher: [...] };
export default middleware;
```

`proxy/define-config.ts` 内部定义了 `defaultMiddleware` 和 `betterAuthMiddleware`。前者处理请求分类、locale、设备类型、route variants、SPA rewrite、Next-only route rewrite；后者在默认 rewrite 基础上叠加登录保护。

## 上下游关系

上游入口主要有三个：

1. **根 Next 配置**  
   `next.config.ts` 导入 `src/libs/next/config/define-config`，把 Next.js 构建、输出、缓存、安全头等配置交给这里生成。

2. **Next proxy/middleware**  
   `src/proxy.ts` 导入 `@/libs/next/proxy/define-config`，拿到 `middleware`，再配合 `config.matcher` 决定哪些路径进入 middleware。

3. **业务 UI 和路由组件**  
   大量组件从 `@/libs/next/dynamic`、`@/libs/next/Image` 导入适配器。例如：
   - `src/components/Analytics/index.tsx`
   - `src/components/client/ClientResponsiveLayout.tsx`
   - `src/features/Conversation/Error/index.tsx`
   - `src/features/DevPanel/index.tsx`
   - `src/routes/(main)/_layout/index.tsx`
   - `src/routes/(mobile)/_layout/index.tsx`

下游依赖主要是：

- `react-router-dom`：SPA 端 `Link`、`useNavigate`、`useLocation`、`useParams`、`useSearchParams`
- `next/navigation`：Next 运行时的真实导航 API
- `next/server`：middleware/proxy 中的 `NextRequest`、`NextResponse`
- `@/auth`：middleware 中通过 `auth.api.getSession()` 做登录态判断
- `@/envs/app`、`@/envs/auth`：控制本地 rewrite、OIDC、APP_URL 等环境行为
- `@/utils/server/routeVariants`：根据 locale 和设备类型生成 variants 路径
- `ua-parser-js`：从 UA 判断是否 mobile
- `debug`：middleware 日志命名空间
- `url-join`：拼接本地 rewrite URL

它还与 `src/spa` 有间接关系。middleware 会把非 Next-only 的页面请求 rewrite 到 `/spa/[variants]/...`，而 Vite SPA 构建产物负责承接这些页面。`navigation.vite.ts` 则让 SPA 内部继续使用近似 Next 的导航 API。

## 运行/调用流程

一次普通页面请求大致经过以下流程：

1. 请求命中 `src/proxy.ts` 的 `matcher`。
2. `src/proxy.ts` 调用 `src/libs/next/proxy/define-config.ts` 生成的 `middleware`。
3. middleware 先判断是否是 `/api`、`/trpc`、`/webapi`、`/oidc` 等后端接口；如果是，直接 `NextResponse.next()`。
4. 对页面请求，读取 locale 来源，优先级是 `?hl=` 查询参数、locale cookie、浏览器 `accept-language`。
5. 解析 user-agent，判断设备是否 mobile。
6. 用 `RouteVariants.serializeVariants({ isMobile, locale })` 生成 variants 路径。
7. 判断请求路径是否属于 `nextjsOnlyRoutes`。
8. 如果不是 Next-only route，则 rewrite 到 `/spa/${route}${pathname}`，进入 SPA catch-all。
9. 如果是 Next-only route，则 rewrite 到 `/${route}${pathname}`，交给 Next App Router 的认证、OAuth、welcome 等页面。
10. 如果启用了认证保护，`betterAuthMiddleware` 会用 `auth.api.getSession()` 查 session；受保护路径且未登录时跳转到 `/signin?callbackUrl=...`。

一次 SPA 内部链接点击则更轻：

1. 组件使用 `@/libs/next/Link`。
2. `Link.tsx` 判断 `href`。
3. 外链或 Next-only route 渲染 `<a href="...">`，走浏览器完整导航。
4. 普通 SPA 内链渲染 `react-router-dom` 的 `<Link to="...">`，走客户端路由跳转。

一次动态组件加载流程：

1. 调用方使用 `dynamic(() => import('./SomeComponent'), { loading })`。
2. `dynamic.tsx` 用 `React.lazy` 包装 loader。
3. 返回的组件在渲染时进入 `Suspense`。
4. 加载中显示 `options.loading?.()` 或 `null`。
5. import 完成后渲染真实组件。

一次图片渲染流程：

1. 调用方使用 `@/libs/next/Image`。
2. 如果 `src` 是字符串，直接作为 `<img src>`。
3. 如果 `src` 是静态图片对象，读取其中的 `src` 字段。
4. 如果传入 `fill`，补充绝对定位和铺满样式。
5. 最终输出普通 `<img>`。

## 小白阅读顺序

1. 先读 `src/libs/next/index.ts`  
   了解这个目录对外暴露了哪些能力。它是最短的地图。

2. 再读 `src/libs/next/Image.tsx`  
   这是最容易理解的适配器：Next Image API 进来，普通 `<img>` 出去。读完能建立“兼容层”的直觉。

3. 再读 `src/libs/next/Link.tsx` 和 `src/libs/next/nextjsOnlyRoutes.ts`  
   重点看为什么有些链接走 `react-router-dom`，有些必须走原生 `<a>`。这里能理解 SPA 路由和 Next 路由的分工。

4. 再读 `src/libs/next/dynamic.tsx`  
   对照 `next/dynamic` 的用法，看它如何用 `React.lazy` 和 `Suspense` 模拟动态导入。

5. 再读 `src/libs/next/navigation.ts` 与 `src/libs/next/navigation.vite.ts`  
   这两个文件要一起看。前者是真 Next，后者是 SPA 替身。小白可以重点比较 `useRouter`、`usePathname`、`redirect`、`notFound` 在两个环境下的差异。

6. 然后读 `src/proxy.ts`  
   它很薄，适合先理解 middleware 的接入方式，以及 `matcher` 是如何决定哪些路径会进入 proxy 的。

7. 最后读 `src/libs/next/proxy/define-config.ts`  
   这是本目录最复杂的文件。建议分段看：先看 API 跳过，再看 locale，再看 variants，再看 SPA rewrite 和 Next-only rewrite，最后看 BetterAuth 登录保护。

8. 有余力再读 `src/libs/next/config/define-config.ts`  
   这是构建配置，不影响日常业务组件写法，但对理解 Docker、Vercel、缓存头、CSP、standalone 输出很重要。

## 常见误区

1. **误以为 `Image.tsx` 等价于 `next/image`**  
   它只是 API 兼容层，最终渲染普通 `<img>`。`priority`、`quality`、`unoptimized` 等字段不会触发 Next 图片优化。需要图片优化能力时，不能只看调用参数，要看实际运行环境。

2. **误以为 `dynamic.tsx` 完整支持 `next/dynamic` 的 SSR 语义**  
   当前实现保留了 `ssr?: boolean` 选项，但没有真正根据它控制 SSR。它主要解决组件懒加载和调用兼容，不是 Next dynamic 的完整替代。

3. **误把所有路由都当 SPA 路由**  
   `nextjsOnlyRoutes` 中的 `/signin`、`/signup`、`/oauth`、`/welcome` 等必须交给 Next App Router。`Link.tsx` 和 middleware 都依赖这份列表。随意删除或漏加路径，可能导致认证页被 SPA catch-all 吃掉，出现空白页或错误页面。

4. **误以为 `navigation.vite.ts` 的 `redirect()` 会真的导航**  
   SPA 版本的 `redirect(url)` 是抛出 `RedirectError`。这更像兼容占位，需要由组件、loader 或错误边界配合处理。普通组件内跳转应优先使用 `useRouter().push()` 或 `replace()`。

5. **误以为 `navigation.ts` 和 `navigation.vite.ts` 会同时生效**  
   `navigation.ts` 默认转发 `next/navigation`。文件注释说明 Vite/SPA 模式下会被替换成 `navigation.vite.ts`。也就是说，同一个 import 在不同构建环境下可能解析到不同实现。排查导航问题时要先确认运行环境。

6. **误以为 proxy 只做登录保护**  
   登录保护只是 `betterAuthMiddleware` 的一部分。proxy 更基础的职责是路由分流：API 直接放行、SPA 页面 rewrite 到 `/spa/[variants]`、Next-only 页面 rewrite 到 `/${variants}`，同时处理 locale、设备类型和本地容器 rewrite。

7. **误改 `nextjsOnlyRoutes` 只考虑客户端链接**  
   这份列表同时被 `Link.tsx` 和 `proxy/define-config.ts` 使用。改动它会同时影响客户端点击行为和服务端 middleware rewrite 行为，需要一起验证。

8. **误把 `createRouteMatcher` 的 `(.*)` 当成严格路径段匹配**  
   测试里明确指出 `/share(.*)` 会匹配 `/shared`，因为 `(.*)` 可以匹配 `d`。如果想表达严格子路径，应使用更精确的 pattern，例如根据当前测试注释推断可考虑 `/share/(.*)`，但这又不会匹配裸 `/share`，需要按需求组合 pattern。
