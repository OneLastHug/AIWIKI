# 文件：vite.config.ts

## 一句话定位

`vite.config.ts` 是 LobeHub Web/Mobile SPA 的 Vite 总入口配置，负责把 `index.html` 或 `index.mobile.html` 编译成可被 Next.js 后续承载的前端静态产物，同时配置本地 SPA 开发服务器、共享渲染插件、PWA 缓存、依赖预构建和生产部署兼容逻辑。

## 它暴露/定义了什么

这个文件默认导出 `defineConfig(...)` 生成的 Vite 配置对象。它没有导出业务 API，而是定义构建系统行为：`base`、`build.outDir`、`rolldownOptions.input/output`、`define`、`resolve.tsconfigPaths`、`optimizeDeps`、`plugins`、`server.proxy`、`server.warmup` 等。

文件内还定义了两个本地辅助函数：`resolveCommandExecutable` 用于在当前系统 `PATH` 中查找命令；`openExternalBrowser` 用于开发模式下自动打开 Debug Proxy。它们服务于本文件里的开发插件，不参与应用运行时。

## 谁调用它

直接调用者是 Vite CLI。`package.json` 中的 `dev:spa` 执行 `vite --port 9876`，`dev:spa:mobile` 执行 `MOBILE=true vite --port 3012`，`build:spa:raw` 执行 `vite build`，`build:spa:mobile` 执行 `MOBILE=true vite build`，都会加载这个配置。

间接调用链上，`build`、`build:docker`、`build:raw` 会先跑 SPA 构建，再通过 `scripts/copySpaBuild.mts` 和 `scripts/generateSpaTemplates.mts` 把 SPA 产物复制并生成给 Next.js 使用的模板。根据当前片段推断，Next.js 后端并不直接 import 该文件，而是消费它构建出的 `dist/desktop`、`dist/mobile` 或被复制到 `public/_spa` 的静态资源。

## 它调用谁

它调用 Vite 核心能力：`defineConfig`、`loadEnv`、开发服务器插件钩子、构建输出配置和依赖预构建。它还组合了多个本仓库 Vite 插件：`plugins/vite/sharedRendererConfig.ts` 中的 `sharedRendererPlugins`、`sharedRendererDefine`、`sharedOptimizeDeps`、`createSharedRolldownOutput`；`plugins/vite/envRestartKeys.ts` 中的 `viteEnvRestartKeys`；`plugins/vite/vercelSkewProtection.ts` 中的 `vercelSkewProtection`。

外部插件主要是 `vite-plugin-pwa` 的 `VitePWA`，以及共享配置中继续引入的 `@vitejs/plugin-react`、`code-inspector-plugin`、Emotion 加速、Markdown import、Node module stub、平台解析插件等。

## 核心流程

配置加载时先根据 `MOBILE=true` 判断当前目标是 mobile 还是 web，再根据 `NODE_ENV` 决定 `mode`，并用 `loadEnv(mode, process.cwd(), '')` 把 `.env` 系列变量注入 `process.env`。随后计算 `isDev`、`platform`，这些值会影响入口 HTML、输出目录、全局编译常量和插件行为。

构建阶段，`build.rolldownOptions.input` 在桌面 Web 场景指向 `index.html`，在移动端指向 `index.mobile.html`。两个 HTML 分别加载 `src/spa/entry.web.tsx` 和 `src/spa/entry.mobile.tsx`。输出目录也随平台切换：桌面 Web 输出到 `dist/desktop`，移动端输出到 `dist/mobile`。`createSharedRolldownOutput({ strictExecutionOrder: true })` 负责共享分包策略，尤其是 i18n、vendor、图标、Emotion、motion 等 chunk 的命名和拆分。

开发阶段，`server.proxy` 把 `/api`、`/trpc`、`/webapi`、`/oidc` 转发到本地 Next.js 后端端口，默认是 `3010`。`server.warmup.clientFiles` 预热大量 `src/` 和 `packages/` 下的前端依赖，目标是降低首次访问和热更新等待时间。开发插件 `lobe-dev-proxy-print` 会打印 Debug Proxy 地址，并在 bundled dev 场景下等待首次编译完成后打开浏览器。

生产阶段，`base` 使用 `VITE_CDN_BASE` 或默认 `/_spa/`，PWA 插件生成 Workbox 缓存规则，`vercelSkewProtection` 在有部署 ID 时给静态资源、动态 import、CSS URL、HTML script/link 等追加部署参数，降低多版本部署时 chunk 加载错位风险。

## 关键函数的高层作用

`defineConfig` 包裹的是全局配置装配点，核心职责是按平台和环境组装一份可运行的 SPA 构建配置。

`sharedRendererPlugins({ platform })` 是渲染端插件集合入口。它把 React、Markdown import、Node 模块 stub、平台文件解析、开发态 manifest 移除、代码定位插件等统一注入，保证 Web、Mobile、Desktop renderer 的行为尽量一致。

`sharedRendererDefine({ isMobile, isElectron: false })` 负责把运行时全局常量编译进浏览器代码，例如 `__DEV__`、`__MOBILE__`、`__ELECTRON__`、`NEXT_PUBLIC_*` 环境变量，并提供 `process.env` 空对象兜底，避免浏览器运行时报错。

`createSharedRolldownOutput` 定义共享 chunk 输出策略，控制 i18n、vendor、model provider 配置等资源如何拆分和落盘。它影响缓存命中、首屏加载和长期维护中的 chunk 兼容性。

`lobe-dev-proxy-print` 是本文件中最特殊的内联插件。它不是业务插件，而是开发体验插件：读取 Vite 本地地址，拼接线上 Debug Proxy 入口，替换默认 URL 打印逻辑，并在 bundled dev 时等待编译完成后再打开代理页面。

`VitePWA` 配置 Service Worker 相关缓存策略：字体样式用 `StaleWhileRevalidate`，字体文件用 `CacheFirst`，图片静态资源缓存 30 天，`/api` 和 `/trpc` 走短期 `NetworkFirst`。这会直接影响离线体验、缓存刷新和接口数据新鲜度。

## 修改风险

最高风险是入口、输出目录和 `base`。如果误改 `index.html`、`index.mobile.html`、`outDir` 或 `VITE_CDN_BASE` 逻辑，可能导致 SPA 构建产物无法被后续复制脚本和 Next.js 模板正确引用，表现为白屏、资源 404 或移动端加载到 Web 入口。

其次是 `define` 和环境变量加载。`sharedRendererDefine` 决定浏览器代码看到的编译常量，错误的 `__MOBILE__`、`__ELECTRON__`、`NEXT_PUBLIC_*` 注入会让同一套源码走错平台分支。`loadEnv` 的 prefix 为空，意味着所有 env 都可能进入 `process.env`，修改时要特别注意不要把敏感变量进一步暴露到客户端 define 中。

分包策略也很敏感。`createSharedRolldownOutput` 和共享手动分包会影响动态 import、预加载和缓存路径；不理解依赖图时调整 chunk 规则，容易引入循环加载、chunk 数量激增或生产环境动态模块加载失败。

开发服务器配置的风险主要在代理和 Debug Proxy。`server.proxy` 必须和本地 Next.js 后端路径保持一致，否则 SPA 开发态会出现登录、TRPC、API 请求失败。内联插件中包含外部代理地址，文档中用 `[URL已移除]` 表示；如果改动自动打开逻辑，需要兼顾 macOS、Windows、Linux 的命令查找和失败降级。

PWA 缓存规则改动会影响线上用户的资源更新节奏。尤其是 API 缓存、图片缓存、字体缓存和 `maximumFileSizeToCacheInBytes`，配置过宽可能缓存陈旧数据，配置过窄则会降低离线能力和二次加载性能。
