# 目录：src/app/spa

## 它负责什么

`src/app/spa` 是 Next.js App Router 里的一个“SPA HTML 服务端入口”。它不承载 React 页面组件，也不是前端路由配置本身，而是负责在用户访问 `/spa/...` 这类路径时，返回一份已经注入服务端配置、SEO 信息和静态资源入口的 HTML。

可以把它理解成 LobeHub SPA 的“HTML 壳层生成器”：

- 根据 URL 中的 `variants` 解析当前语言和是否移动端。
- 选择 desktop 或 mobile 的 SPA HTML 模板。
- 注入 `window.__SERVER_CONFIG__`，让浏览器端 SPA 启动后能拿到服务端配置、feature flags、分析统计配置等。
- 注入 SEO meta，例如 title、description、OpenGraph、Twitter card。
- 在开发环境下，从 Vite dev server `[URL已移除] 拉取 HTML，并重写资源 URL，支持本地 SPA 开发。
- 在生产环境下，读取构建生成的 `spaHtmlTemplates` 模板，返回完整 HTML。

所以它连接的是 Next.js 后端运行时和 Vite 构建出的 SPA 前端产物。

## 关键组成

这个目录当前实际文件很少，核心都在：

- `src/app/spa/[variants]/[[...path]]/route.ts`
- `src/app/spa/[variants]/[[...path]]/mobileHtmlTemplate.source.ts`
- `src/app/spa/[variants]/[[...path]]/spaHtmlTemplates.d.ts`

`route.ts` 是主入口。它导出两个关键函数：

`generateStaticParams()`  
用于生成静态参数。当前固定生成 `en-US`、`zh-CN` 两种 locale，并按运行形态生成 mobile/desktop 组合：

- 如果 `isDesktop` 为真，只生成 desktop 组合。
- 否则生成 mobile 和 desktop 两类组合。

这些组合通过 `RouteVariants.serializeVariants({ isMobile, locale })` 序列化到 `[variants]` 动态段里。

`GET()`  
这是真正响应请求的 handler。它从 `params.variants` 里反序列化出：

- `locale`
- `isMobile`

然后依次构造：

- `serverConfig`：来自 `getServerGlobalConfig()`。
- `featureFlags`：来自 `getServerFeatureFlagsValue()`。
- `analyticsConfig`：由 `buildAnalyticsConfig()` 从 `analyticsEnv` 和部分 `NEXT_PUBLIC_DESKTOP_*` 环境变量拼出。
- `clientEnv`：由 `buildClientEnv()` 从 app、file、python 相关 env 中提取客户端可用字段。

这些内容被组合成 `SPAServerConfig`：

```ts
{
  analyticsConfig,
  clientEnv,
  config: serverConfig,
  featureFlags,
  isMobile,
}
```

随后 `route.ts` 会拿到 HTML 模板，把模板里的占位代码：

```ts
window.__SERVER_CONFIG__ = undefined; /* SERVER_CONFIG */
```

替换成序列化后的真实配置：

```ts
window.__SERVER_CONFIG__ = ...
```

这里使用 `serializeForHtml()`，说明它不是普通 `JSON.stringify` 的裸输出，而是面向 HTML 注入场景做过处理，降低脚本注入或转义问题的风险。

`mobileHtmlTemplate.source.ts` 是一个预提交的 mobile HTML 模板兜底文件。文件头写明它由 `scripts/mobileSpaWorkflow` 自动生成，不应手改。它包含：

- 基础 HTML 结构。
- `<div id="root">` SPA 挂载点。
- `<!--SEO_META-->` 占位符。
- `<!--ANALYTICS_SCRIPTS-->` 占位符。
- `window.__SERVER_CONFIG__ = undefined; /* SERVER_CONFIG */` 占位符。
- mobile SPA 的远程静态资源 URL，例如 `[URL已移除]
- 主题、locale、RTL 方向的早期初始化脚本。
- Worker patch，用于处理跨源 worker 资源。

`spaHtmlTemplates.d.ts` 只声明：

```ts
export declare const desktopHtmlTemplate: string;
export declare const mobileHtmlTemplate: string;
```

真正的 `spaHtmlTemplates.ts` 根据当前片段推断是在构建流程中生成的，依据是 `scripts/generateSpaTemplates.mts` 会把 `dist/desktop/index.html` 和 mobile 构建产物写入：

```ts
src/app/spa/[variants]/[[...path]]/spaHtmlTemplates.ts
```

如果本地没有 mobile build，则生成文件会从 `mobileHtmlTemplate.source.ts` 导入 mobile 模板。

## 上下游关系

上游主要有三类。

第一类是构建产物。`scripts/generateSpaTemplates.mts` 从：

- `dist/desktop/index.html`
- `dist/mobile/index.mobile.html` 或 `dist/mobile/index.html`

读取 Vite 构建后的 HTML，然后生成 `spaHtmlTemplates.ts`。如果 mobile 构建产物不存在，则回退到 `mobileHtmlTemplate.source.ts`。

第二类是服务端配置来源。`route.ts` 依赖：

- `@/server/globalConfig` 的 `getServerGlobalConfig()`
- `@/config/featureFlags` 的 `getServerFeatureFlagsValue()`
- `@/envs/analytics`
- `@/envs/app`
- `@/envs/file`
- `@/envs/python`
- `@/server/translation`
- `@/utils/server/routeVariants`

这些模块提供运行时配置、功能开关、统计平台配置、客户端需要的环境变量、SEO 翻译文案、路由变体解析能力。

第三类是 Vite dev server。开发模式下，`getTemplate()` 不读取构建产物，而是直接 `fetch('[URL已移除]')`。随后 `rewriteViteAssetUrls()` 会把 HTML 中以 `/` 开头的 `script[src]`、`link[href]` 改成 `[URL已移除] inline module import 和 Worker 创建方式。这样在线上域名或 Next 代理环境里，也能加载本地 Vite SPA 资源。

下游主要是浏览器端 SPA。

`src/layout/SPAGlobalProvider/index.tsx` 会读取：

```ts
window.__SERVER_CONFIG__
```

并把其中的：

- `featureFlags`
- `isMobile`
- `config`

传入 `ServerConfigStoreProvider`，让 Zustand/React 侧拿到服务端配置。

`src/components/Analytics/LobeAnalyticsProviderWrapper.tsx` 也读取 `window.__SERVER_CONFIG__.analyticsConfig`，再配置 GA4、PostHog、X Ads 等分析 provider。

此外，`src/types/global.d.ts` 声明了全局 `window.__SERVER_CONFIG__` 类型，`src/types/spaServerConfig.ts` 定义了它的结构。

## 运行/调用流程

一次典型请求可以按这个顺序理解：

1. 用户访问 Next.js 路由，例如 `/spa/[variants]/some/client/path`。
2. App Router 命中 `src/app/spa/[variants]/[[...path]]/route.ts`。
3. `GET()` 从动态段 `[variants]` 解析 locale 和 mobile 状态。`[[...path]]` 是可选 catch-all，主要用于承接 SPA 内部路径，不在服务端逐个匹配页面。
4. 服务端读取全局配置、feature flags、analytics env、客户端 env。
5. 服务端调用 `getTemplate(isMobile)` 获取 HTML 模板。
6. 如果是开发环境，则从 `[URL已移除] 获取 Vite HTML，并重写资源地址。
7. 如果是生产环境，则动态导入 `./spaHtmlTemplates`，按 `isMobile` 选择 `mobileHtmlTemplate` 或 `desktopHtmlTemplate`。
8. 服务端把 `window.__SERVER_CONFIG__ = undefined; /* SERVER_CONFIG */` 替换成真实 `SPAServerConfig`。
9. 服务端调用 `buildSeoMeta(locale)`，通过 `translation('metadata', locale)` 获取标题和描述，再替换 `<!--SEO_META-->`。
10. 当前代码把 `<!--ANALYTICS_SCRIPTS-->` 替换为空字符串，说明分析脚本主要不是在这个 HTML 字符串里直接注入，而是交给客户端 provider 或其他机制处理。
11. 返回 `content-type: text/html; charset=utf-8`，并设置 `Cache-Control: no-cache`。
12. 浏览器加载 HTML 和 Vite/静态资源，React SPA 挂载到 `#root`。
13. SPA 启动后，`SPAGlobalProvider`、`LobeAnalyticsProviderWrapper` 等客户端模块读取 `window.__SERVER_CONFIG__`，完成全局配置、主题、locale、统计等初始化。

## 小白阅读顺序

建议先读 `src/app/spa/[variants]/[[...path]]/route.ts`，重点看 `GET()`。这是理解整个目录的主线：请求进来、配置构造、模板选择、HTML 替换、响应返回。

第二步看 `src/types/spaServerConfig.ts`。它能告诉你 `window.__SERVER_CONFIG__` 里到底有哪些字段。理解这个类型后，再回到 `route.ts` 看 `buildAnalyticsConfig()` 和 `buildClientEnv()` 会更清楚。

第三步看 `mobileHtmlTemplate.source.ts`。不要被长字符串吓到，它本质上就是 HTML 模板。重点找三个占位点：

- `<!--SEO_META-->`
- `window.__SERVER_CONFIG__ = undefined; /* SERVER_CONFIG */`
- `<!--ANALYTICS_SCRIPTS-->`

第四步看 `scripts/generateSpaTemplates.mts`。这个脚本解释了为什么源码里只有 `spaHtmlTemplates.d.ts`，而 `route.ts` 却能导入 `./spaHtmlTemplates`：实际 `.ts` 文件是构建后生成的。

第五步看消费者：

- `src/layout/SPAGlobalProvider/index.tsx`
- `src/components/Analytics/LobeAnalyticsProviderWrapper.tsx`

这两个文件能帮助你把“服务端注入配置”和“客户端使用配置”串起来。

最后再看 `src/spa/entry.web.tsx`、`src/spa/entry.mobile.tsx`、`src/spa/router/*`。这些才是 SPA 前端入口和客户端路由配置；它们和 `src/app/spa` 是上下游关系，不是同一个职责层。

## 常见误区

第一个误区：把 `src/app/spa` 当成 SPA 前端源码目录。  
实际 SPA 前端入口在 `src/spa`，页面路由在 `src/routes`，业务 UI 多在 `src/features`。`src/app/spa` 是 Next.js 侧返回 HTML 的服务端 route。

第二个误区：以为 `[[...path]]` 会在服务端解析每一个 SPA 页面。  
它只是 catch-all，把不同客户端路径都交给同一份 SPA HTML。真正的页面匹配发生在浏览器端 React Router 里。

第三个误区：手改 `mobileHtmlTemplate.source.ts` 或生成后的 `spaHtmlTemplates.ts`。  
`mobileHtmlTemplate.source.ts` 标记为自动生成；`spaHtmlTemplates.ts` 根据 `scripts/generateSpaTemplates.mts` 推断也是构建产物。正常应改构建流程、模板源或 SPA 构建输出，而不是直接改生成文件。

第四个误区：忽略 `window.__SERVER_CONFIG__` 的安全注入。  
这里使用 `serializeForHtml(spaConfig)`，不是随手拼字符串。类似配置注入涉及 HTML script 上下文，不能简单替换成普通序列化逻辑。

第五个误区：认为 analytics 脚本一定在 HTML 模板里注入。  
当前 `route.ts` 会把 `<!--ANALYTICS_SCRIPTS-->` 替换为空，而 analytics 配置被放进 `window.__SERVER_CONFIG__`，客户端 `LobeAnalyticsProviderWrapper` 再据此启用 GA4、PostHog、X Ads 等。

第六个误区：开发模式资源路径和生产模式一样。  
开发模式下 HTML 来自 Vite dev server，`rewriteViteAssetUrls()` 会主动把 `/assets/...`、`/@...` 等路径改到 `[URL已移除] patch Worker。生产模式则依赖构建生成的 HTML 模板和静态资源 URL。
