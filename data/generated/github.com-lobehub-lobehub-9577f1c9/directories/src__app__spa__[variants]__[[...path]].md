# 目录：src/app/spa/[variants]/[[...path]]

## 它负责什么

`src/app/spa/[variants]/[[...path]]` 是 Next.js App Router 里的一个 SPA HTML 网关目录。它不渲染 React 页面组件，而是通过 `route.ts` 暴露一个 `GET` Route Handler，把已经由 Vite 构建好的 SPA `index.html` 模板返回给浏览器。

可以把它理解成：所有普通前端页面最终都会被 middleware 改写到这里，由这里决定返回 desktop 版还是 mobile 版 HTML，并在 HTML 里注入运行 SPA 所需的服务端配置、功能开关、分析配置、客户端环境变量和 SEO meta。

它的路由结构是：

```text
/spa/[variants]/[[...path]]
```

其中：

- `[variants]`：编码后的路由变体，包含 `locale` 和 `isMobile`，例如 `zh-CN__1`、`en-US__0`。
- `[[...path]]`：可选 catch-all 路径，用来承接原始 SPA 路径，例如 `/chat`、`/settings`、`/files` 等。这个目录自身不关心具体 path，只负责统一返回 SPA HTML，让前端的 `react-router-dom` 接管后续路由。

## 关键组成

这个目录目前有 3 个文件：

```text
src/app/spa/[variants]/[[...path]]
├── route.ts
├── mobileHtmlTemplate.source.ts
└── spaHtmlTemplates.d.ts
```

`route.ts` 是核心文件，导出两个重要入口：

```ts
export function generateStaticParams()
export async function GET(...)
```

`generateStaticParams()` 用于生成静态 variants 参数。它会为固定语言 `en-US`、`zh-CN` 生成 desktop/mobile 两套组合；如果当前是 desktop 环境，则只生成 desktop 组合。这里依赖 `RouteVariants.serializeVariants({ isMobile, locale })` 把对象序列化成 URL 段。

`GET()` 是真正处理请求的 Route Handler。它从 `params.variants` 里解析出 `locale` 和 `isMobile`，然后读取服务端全局配置、功能开关、分析配置和客户端环境变量，组装成 `SPAServerConfig`，再把配置注入到 HTML 模板中的：

```ts
window.__SERVER_CONFIG__ = undefined; /* SERVER_CONFIG */
```

最终返回 `text/html; charset=utf-8`，并设置：

```http
Cache-Control: no-cache
```

`mobileHtmlTemplate.source.ts` 是移动端 HTML 模板的预提交来源，文件头说明它由 `scripts/mobileSpaWorkflow` 自动生成，不应手写修改。它导出：

```ts
export const mobileHtmlTemplate = "..."
```

模板里包含：

- `<!--SEO_META-->` 占位符，等待 `route.ts` 注入 SEO 标签。
- 初始化主题的脚本，根据 `localStorage.theme` 和系统暗色模式设置 `data-theme`。
- 初始化语言方向的脚本，根据 `?hl=`、`LOBE_LOCALE` cookie、`navigator.language` 设置 `document.documentElement.lang` 和 `dir`。
- `window.__SERVER_CONFIG__` 占位脚本。
- 指向 `[URL已移除] 的移动端 JS/CSS 资源。
- `<!--ANALYTICS_SCRIPTS-->` 占位符，目前在 `route.ts` 中被替换为空字符串。

`spaHtmlTemplates.d.ts` 是类型声明文件，声明运行时会存在：

```ts
export declare const desktopHtmlTemplate: string;
export declare const mobileHtmlTemplate: string;
```

真正的 `spaHtmlTemplates.ts` 并不在仓库里长期维护，而是由 `scripts/generateSpaTemplates.mts` 在 Vite build 后生成。该脚本会读取 `dist/desktop/index.html` 作为 desktop 模板；如果本地有 mobile 构建产物，则内联 mobile 模板，否则从 `mobileHtmlTemplate.source.ts` 导入移动端模板。根据当前片段推断，`.d.ts` 的作用是让源码阶段能通过 TypeScript 类型检查，而实际实现由构建脚本补齐。

## 上下游关系

上游主要是 Next.js middleware 里的 rewrite 逻辑。`src/libs/next/proxy/define-config.ts` 会判断当前请求是否属于 API 或 Next.js 专用路由。如果不是，它会把普通 SPA 路由改写成：

```ts
/spa/${route}${url.pathname === '/' ? '' : url.pathname}
```

其中 `route` 来自：

```ts
RouteVariants.serializeVariants({
  isMobile: device.type === 'mobile',
  locale,
})
```

也就是说，用户访问 `/chat` 时，实际可能被内部改写为：

```text
/spa/zh-CN__0/chat
```

或：

```text
/spa/zh-CN__1/chat
```

这就会命中当前目录的 `GET()`。

`RouteVariants` 的底层实现在 `packages/desktop-bridge/src/routeVariants.ts`。它把变体序列化为：

```text
{locale}__{isMobileNumber}
```

例如：

```text
en-US__0
zh-CN__1
```

反序列化时，如果 locale 不合法，会回退到默认语言 `en-US`；`isMobile` 只有字符串 `'1'` 才会被视为 `true`。

下游主要是浏览器端 SPA。`route.ts` 注入的 `window.__SERVER_CONFIG__` 会被 `src/layout/SPAGlobalProvider/index.tsx` 读取：

```ts
const serverConfig: SPAServerConfig | undefined = window.__SERVER_CONFIG__;
```

然后传给 `ServerConfigStoreProvider`，让前端 store 获得：

- `serverConfig.config`
- `serverConfig.featureFlags`
- `serverConfig.isMobile`

分析配置则会被 `src/components/Analytics/LobeAnalyticsProviderWrapper.tsx` 读取，用来初始化 GA、PostHog、X Ads 等分析能力。

SEO 数据的上游来自 `translation('metadata', locale)` 和品牌常量。`buildSeoMeta()` 根据当前语言生成 title、description、Open Graph、Twitter card 等标签，并替换 HTML 里的 `<!--SEO_META-->`。

客户端环境变量的上游来自：

- `appEnv.MARKET_BASE_URL`
- `pythonEnv.NEXT_PUBLIC_PYODIDE_INDEX_URL`
- `pythonEnv.NEXT_PUBLIC_PYODIDE_PIP_INDEX_URL`
- `fileEnv.NEXT_PUBLIC_S3_FILE_PATH`

这些值被放进 `clientEnv`，再进入 `window.__SERVER_CONFIG__`，供 SPA 运行时读取。

## 运行/调用流程

一次普通页面访问的大致流程如下：

1. 用户访问一个前端路由，例如 `/chat`。
2. middleware 解析请求：
   - 从 `?hl=`、`LOBE_LOCALE` cookie、浏览器语言中决定 `locale`。
   - 从 `User-Agent` 判断是否 mobile。
   - 用 `RouteVariants.serializeVariants()` 生成 variants。
3. middleware 判断该路径不是 API，也不是 Next.js 专用路由，于是 rewrite 到 `/spa/[variants]/[[...path]]`。
4. 当前目录的 `route.ts` 收到 `GET` 请求。
5. `GET()` 从 `params.variants` 解析出 `locale` 和 `isMobile`。
6. `GET()` 拉取服务端全局配置：
   - `getServerGlobalConfig()`
   - `getServerFeatureFlagsValue()`
   - `buildAnalyticsConfig()`
   - `buildClientEnv()`
7. `GET()` 调用 `getTemplate(isMobile)` 获取 HTML 模板。
8. 如果是 development 环境，`getTemplate()` 会请求 `[URL已移除] Vite dev server。
9. development 环境下还会调用 `rewriteViteAssetUrls()`，用 `linkedom` 把 HTML 里的相对资源改成 `[URL已移除] patch `Worker`，解决 dev proxy 场景下跨源 worker 加载问题。
10. production 环境下，`getTemplate()` 动态导入 `./spaHtmlTemplates`，根据 `isMobile` 返回 `mobileHtmlTemplate` 或 `desktopHtmlTemplate`。
11. `GET()` 用 `serializeForHtml(spaConfig)` 安全序列化配置，替换 `window.__SERVER_CONFIG__` 占位脚本。
12. `GET()` 根据 `locale` 生成 SEO meta，替换 `<!--SEO_META-->`。
13. `GET()` 把 `<!--ANALYTICS_SCRIPTS-->` 替换为空。
14. 浏览器收到 HTML，加载对应的 Vite SPA JS/CSS。
15. SPA 启动后由 `SPAGlobalProvider` 读取 `window.__SERVER_CONFIG__`，初始化语言、主题、store、鉴权、分析、弹窗、上传、全局 UI 等客户端运行环境。
16. 之后具体页面路由由前端的 `react-router-dom` 接管。

这里有一个容易忽略的点：`[[...path]]` 捕获了路径，但 `GET()` 没有读取 `path`。这是有意的，因为服务端只需要返回同一份 SPA HTML，具体 `/chat`、`/settings`、`/files` 应该由前端路由系统解析。

## 小白阅读顺序

建议按这个顺序读：

1. 先读 `src/app/spa/[variants]/[[...path]]/route.ts` 的 `GET()`  
   先理解“请求进来后如何拿 variants、如何组装配置、如何替换 HTML、如何返回 Response”。

2. 再读 `getTemplate()`  
   重点看 development 和 production 的区别。development 走 Vite dev server，production 走构建生成的 `spaHtmlTemplates`。

3. 再读 `buildAnalyticsConfig()` 和 `buildClientEnv()`  
   这两块只是把环境变量整理成前端可消费的结构，不涉及复杂业务。

4. 再读 `buildSeoMeta()`  
   关注它如何通过 `translation('metadata', locale)` 生成多语言 SEO。

5. 再看 `mobileHtmlTemplate.source.ts`  
   不需要逐字读完整 HTML 字符串，重点看几个占位符和初始化脚本：`<!--SEO_META-->`、`window.__SERVER_CONFIG__`、`<!--ANALYTICS_SCRIPTS-->`、主题初始化、语言初始化。

6. 再看 `src/libs/next/proxy/define-config.ts`  
   这是理解“为什么请求会来到 `/spa/[variants]/[[...path]]`”的关键。尤其看 SPA routes rewrite 那段。

7. 最后看 `src/layout/SPAGlobalProvider/index.tsx`  
   这是理解“服务端注入的配置在前端被谁消费”的入口。

## 常见误区

第一，误以为这个目录是具体页面实现。实际上它不是 `/chat` 或 `/settings` 的页面代码，而是所有 SPA 路由共享的 HTML 入口。真正的页面组件在 `src/routes/` 和 `src/features/`，路由配置在 `src/spa/router/`。

第二，误以为 `[[...path]]` 会在服务端分发不同页面。当前 `GET()` 只使用 `variants`，没有使用 `path`。这是因为它返回的是同一类 SPA shell，具体页面由浏览器端 React Router 处理。

第三，误以为 `mobileHtmlTemplate.source.ts` 应该手动编辑。文件头明确写着它由 `scripts/mobileSpaWorkflow` 自动生成，不应手改。生产用的 `spaHtmlTemplates.ts` 也由 `scripts/generateSpaTemplates.mts` 构建生成。

第四，误以为 `spaHtmlTemplates.d.ts` 就是实际模板实现。它只是类型声明。源码中看不到 `spaHtmlTemplates.ts` 是正常的，因为它是 build 后生成的文件。

第五，误以为 `window.__SERVER_CONFIG__` 是普通前端环境变量。它其实是服务端在返回 HTML 前注入的运行时配置，包含全局配置、feature flags、analytics config、client env 和 `isMobile`。前端通过 `SPAGlobalProvider`、`ServerConfigStoreProvider`、`LobeAnalyticsProviderWrapper` 等消费它。

第六，误以为 SEO meta 是静态写死在模板里的。模板只有 `<!--SEO_META-->` 占位符，真正的 title、description、OG、Twitter meta 是 `route.ts` 根据 `locale` 和品牌信息动态生成的。

第七，误以为开发环境和生产环境加载 HTML 的方式一样。开发环境直接 fetch `[URL已移除] 的 Vite HTML，并重写资源 URL；生产环境使用构建生成的 `desktopHtmlTemplate` / `mobileHtmlTemplate`。

第八，误以为 analytics 脚本是通过 `<!--ANALYTICS_SCRIPTS-->` 注入的。当前代码里这个占位符被替换为空，实际分析配置主要通过 `window.__SERVER_CONFIG__.analyticsConfig` 进入前端，再由 React 侧的分析 Provider 初始化。
