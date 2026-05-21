# 文件：vite.config.ts

## 它负责什么

`vite.config.ts` 是 LobeHub 前端 SPA 的 Vite 构建与开发服务器配置入口。它不负责 Next.js 后端，也不负责 Electron 主进程；它主要负责浏览器端 SPA 的开发预览、生产构建、资源拆包、环境变量注入、PWA 缓存、代理后端接口，以及本地开发时打印/打开 Debug Proxy 地址。

从 `package.json` 可以看到它的主要入口命令：

- `dev:spa`: `vite --port 9876`
- `dev:spa:mobile`: `MOBILE=true vite --port 3012`
- `build:spa:raw`: `rm -rf public/_spa && vite build`
- `build:spa:mobile`: `MOBILE=true vite build`

也就是说，普通桌面 Web SPA 和移动端 SPA 都走同一个 `vite.config.ts`，通过环境变量 `MOBILE=true` 切换构建入口和输出目录。

这个文件的核心职责可以概括为：

1. 根据 `NODE_ENV` 和 `MOBILE` 判断当前是开发/生产、Web/移动端。
2. 加载 `.env` 等环境变量，并把必要变量注入前端运行时代码。
3. 设置 SPA 构建入口：`index.html` 或 `index.mobile.html`。
4. 复用 `plugins/vite/sharedRendererConfig.ts` 中的公共渲染端配置。
5. 配置开发服务器端口、代理、预热文件。
6. 在本地开发时打印线上 Debug Proxy URL，必要时自动打开浏览器。
7. 配置 PWA/Workbox 缓存策略。
8. 在 Vercel 生产构建中追加部署 ID，降低动态 chunk 加载到旧版本资源的风险。

## 关键组成

### 1. 环境判断与环境变量加载

文件开头有几个关键变量：

```ts
const isMobile = process.env.MOBILE === 'true';
const mode = process.env.NODE_ENV === 'production' ? 'production' : 'development';

Object.assign(process.env, loadEnv(mode, process.cwd(), ''));

const isDev = process.env.NODE_ENV !== 'production';
const platform = isMobile ? 'mobile' : 'web';
```

这里做了三件事：

- `MOBILE=true` 时进入移动端构建/开发模式。
- `NODE_ENV=production` 时按生产模式读取环境变量，否则按开发模式。
- `loadEnv(mode, process.cwd(), '')` 会读取 Vite 的 `.env` 系列文件，并合并到 `process.env`。

注意第三个参数是空字符串 `''`，这表示不只加载 `VITE_` 前缀变量，而是把匹配到的环境变量都读出来。之后真正暴露给前端的变量由 `sharedRendererDefine` 控制。

### 2. 外部浏览器打开逻辑

`resolveCommandExecutable` 和 `openExternalBrowser` 是本文件内部的辅助函数。

`resolveCommandExecutable(cmd)` 用来在当前系统的 `PATH` 中找到可执行程序：

- Windows 下会考虑 `.COM`、`.EXE`、`.BAT`、`.CMD` 等扩展名。
- macOS/Linux 下直接按命令名查找。
- 找不到时返回 `undefined`。

`openExternalBrowser(url, logger)` 根据平台选择系统命令：

- Windows: `rundll32 url.dll,FileProtocolHandler <url>`
- macOS: `open <url>`
- Linux: `xdg-open <url>`

它的用途不是普通生产逻辑，而是给开发服务器插件使用：当本地 SPA 编译完成后，自动打开 Debug Proxy URL。

### 3. Vite 基础配置

主配置通过 `defineConfig` 导出：

```ts
export default defineConfig({
  base: isDev ? '/' : process.env.VITE_CDN_BASE || '/_spa/',
  ...
});
```

`base` 决定静态资源路径前缀：

- 开发环境：`/`
- 生产环境：优先使用 `VITE_CDN_BASE`
- 如果没有 CDN base，则默认 `/_spa/`

这和项目的构建链路有关。`build:spa:raw` 先构建 SPA，后续 `build:spa:copy` 会通过脚本把 SPA 构建结果复制/生成到 Next.js 可服务的位置。根据当前片段推断，生产环境默认把 SPA 静态资源挂在 `/_spa/` 下。

### 4. build 配置

```ts
build: {
  outDir: isMobile ? 'dist/mobile' : 'dist/desktop',
  reportCompressedSize: false,
  rolldownOptions: {
    input: path.resolve(__dirname, isMobile ? 'index.mobile.html' : 'index.html'),
    output: createSharedRolldownOutput({ strictExecutionOrder: true }),
  },
}
```

关键点：

- 移动端输出到 `dist/mobile`
- 非移动端输出到 `dist/desktop`
- 移动端入口是 `index.mobile.html`
- Web/桌面 SPA 入口是 `index.html`
- 使用 `rolldownOptions`，说明该项目使用 Vite/Rolldown 相关构建能力，而不是传统只写 `rollupOptions`
- `createSharedRolldownOutput` 来自 `plugins/vite/sharedRendererConfig.ts`，负责统一 chunk 拆分和文件命名

`reportCompressedSize: false` 是构建性能优化，避免构建阶段额外计算 gzip/brotli 体积。

### 5. define 配置

```ts
define: sharedRendererDefine({ isMobile, isElectron: false }),
```

`sharedRendererDefine` 会生成前端编译期常量，例如：

- `__CI__`
- `__DEV__`
- `__ELECTRON__`
- `__MOBILE__`
- `__TEST__`
- `process.env.NEXT_PUBLIC_*`
- `process.env`

这里 `isElectron: false` 表明该 Vite 配置面向 Web SPA，而不是 Electron 渲染器专用构建。Electron 相关构建在 `apps/desktop/electron.vite.config.ts` 等位置。

一个容易忽略的点：它只把 `NEXT_PUBLIC_` 开头的环境变量注入成 `process.env.Xxx`。虽然前面 `loadEnv` 读取了很多变量，但不是所有变量都会暴露到浏览器代码里。

### 6. resolve 与 optimizeDeps

```ts
resolve: {
  tsconfigPaths: true,
},
optimizeDeps: sharedOptimizeDeps,
```

`tsconfigPaths: true` 让 Vite 识别 `tsconfig.json` 里的路径别名，例如项目常见的 `@/xxx`。

`sharedOptimizeDeps` 来自共享配置，预构建常用依赖，例如：

- `react`
- `react-dom`
- `react-router-dom`
- `antd`
- `@lobehub/ui`
- `antd-style`
- `zustand`
- `swr`
- `i18next`
- `react-i18next`
- `dayjs`
- `motion/react`

这可以提升开发服务器启动和页面首次访问时的依赖解析速度，减少 Vite 反复扫描大型依赖的成本。

### 7. plugins 插件列表

插件数组大致分成四类。

第一类是生产/通用插件：

```ts
vercelSkewProtection(),
viteEnvRestartKeys(['APP_URL']),
...sharedRendererPlugins({ platform }),
```

`vercelSkewProtection()` 是本地 Vite 插件，用来在生产构建时给 JS/CSS/HTML/Worker 资源 URL 追加 `?dpl=<VERCEL_DEPLOYMENT_ID>`。它只在 `vite build` 且存在部署 ID 时启用。作用是配合 Vercel Skew Protection，避免用户页面还在旧 HTML 上，但动态 import 请求到了另一个部署版本的 chunk，导致 `Failed to fetch dynamically imported module`。

`viteEnvRestartKeys(['APP_URL'])` 是开发服务器插件。它监听 `.env`、`.env.local`、`.env.[mode]`、`.env.[mode].local`，但只在白名单 key 变化时重启服务。当前白名单只有 `APP_URL`。这避免了每次保存 `.env` 都让 Vite 重启。

`sharedRendererPlugins({ platform })` 来自共享配置，包含：

- `viteEmotionSpeedy()`
- `viteMarkdownImport()`
- `viteNodeModuleStub()`
- `vitePlatformResolve(platform)`
- 开发环境下移除 HTML manifest 的插件
- 开发环境下的 `codeInspectorPlugin`
- `@vitejs/plugin-react`

其中 `vitePlatformResolve(platform)` 会根据 `web` 或 `mobile` 做平台相关解析。根据当前片段推断，它应该负责选择类似 `.mobile.tsx`、平台差异文件或平台别名。

第二类是开发专用插件 `lobe-dev-proxy-print`。

它只在 `isDev` 时启用，负责：

- 构造 Debug Proxy URL
- 在 Vite 控制台打印：
  `[URL已移除]>`
- 在 bundled dev 模式下等待首次编译完成
- 编译完成后自动打开 Debug Proxy

这里的 Debug Proxy 很关键。项目的 `AGENTS.md` 也说明：开发时打开线上 `app.lobehub.com` 的代理页面，让线上环境加载本地 Vite SPA，从而既使用真实服务端配置，又保留本地 HMR。

第三类是 PWA 插件：

```ts
VitePWA({
  injectRegister: null,
  manifest: false,
  registerType: 'prompt',
  workbox: { ... },
})
```

这里没有让 VitePWA 注入 manifest，也没有自动注入 register。它主要配置 Workbox 缓存策略：

- 构建产物缓存：`js`、`css`、`html`、`woff2`
- Google Fonts stylesheet：`StaleWhileRevalidate`
- Google Fonts font 文件：`CacheFirst`
- 图片资源：`StaleWhileRevalidate`
- `/api` 和 `/trpc`：`NetworkFirst`，最多缓存 5 分钟

这说明它的 PWA 能力更偏资源缓存和离线/弱网体验，而不是完整由这个文件管理 manifest。

第四类是 `.filter(Boolean)`：

```ts
].filter(Boolean) as PluginOption[]
```

因为数组中有 `isDev && plugin` 这种写法，生产环境会产生 `false`。过滤后再断言为 `PluginOption[]`，避免类型不匹配。

### 8. server 配置

```ts
server: {
  cors: true,
  host: true,
  port: 9876,
  proxy: {
    '/api': `[URL已移除] || 3010}`,
    '/oidc': `[URL已移除] || 3010}`,
    '/trpc': `[URL已移除] || 3010}`,
    '/webapi': `[URL已移除] || 3010}`,
  },
  warmup: { clientFiles: [...] },
}
```

开发服务器默认监听 `9876`。`host: true` 允许局域网访问或容器环境访问。`cors: true` 允许跨域请求。

代理规则把这些路径转发给 Next.js 后端：

- `/api`
- `/oidc`
- `/trpc`
- `/webapi`

目标端口默认是 `3010`，也就是 `dev:next` 使用的端口：

```json
"dev:next": "next dev -p 3010"
```

如果设置了 `PORT`，代理会转到 `PORT` 指定的端口。

`warmup.clientFiles` 列出大量业务代码和 monorepo package 路径，让 Vite 预热常用模块。范围包括：

- `src/spa`
- `src/features`
- `src/routes`
- `src/store`
- `src/services`
- `src/locales`
- `packages/types`
- `packages/model-runtime`
- `packages/agent-runtime`
- `packages/builtin-tool-*`
- `packages/business/*`
- 等等

这对 LobeHub 这种大型前端仓库很重要：开发环境中首次访问页面时，如果没有预热，Vite 可能要临时转换大量模块，导致首屏慢或 HMR 初始阶段卡顿。

## 上下游关系

### 上游：谁会调用它

`vite.config.ts` 的直接上游主要是命令行脚本。

开发时：

```bash
bun run dev:spa
```

实际执行：

```bash
vite --port 9876
```

移动端开发时：

```bash
bun run dev:spa:mobile
```

实际执行：

```bash
MOBILE=true vite --port 3012
```

生产构建时：

```bash
bun run build:spa
```

间接执行：

```bash
vite build
```

移动端生产构建时：

```bash
bun run build:spa:mobile
```

实际执行：

```bash
MOBILE=true vite build
```

完整构建时：

```bash
bun run build
```

流程是：

1. `build:spa`
2. `build:spa:copy`
3. `build:next`

所以 `vite.config.ts` 是完整 Web 应用构建链路的 SPA 阶段配置，不是最终唯一构建入口。

### 下游：它依赖哪些配置和插件

本文件直接依赖这些本地模块：

- `./plugins/vite/envRestartKeys`
- `./plugins/vite/sharedRendererConfig`
- `./plugins/vite/vercelSkewProtection`

`sharedRendererConfig` 又聚合了多个 Vite 插件：

- `emotionSpeedy`
- `markdownImport`
- `nodeModuleStub`
- `platformResolve`
- `code-inspector-plugin`
- `@vitejs/plugin-react`

因此，阅读 `vite.config.ts` 时不要只看本文件。很多真正影响模块解析、React 编译、Markdown 导入、平台文件选择、chunk 拆分的逻辑，都被下沉到了 `plugins/vite/` 下。

### 与 Next.js 的关系

这个文件不是 `next.config.ts` 的替代品。LobeHub 是 Next.js + SPA 的组合：

- Next.js 负责后端 API、认证页面、服务端能力、生产启动等。
- Vite 负责 SPA 前端开发和 SPA 静态资源构建。
- 开发时 Vite 把 `/api`、`/trpc` 等请求代理给 Next.js。
- 生产时 SPA 构建结果会被后续脚本复制和模板化，再由 Next.js/部署平台服务。

根据当前片段推断，`scripts/copySpaBuild.mts` 和 `scripts/generateSpaTemplates.mts` 是 SPA 构建结果接入 Next.js 产物的关键后续步骤。

### 与移动端 SPA 的关系

同一份配置通过 `MOBILE=true` 切换移动端：

- `platform = 'mobile'`
- 构建入口：`index.mobile.html`
- 输出目录：`dist/mobile`
- `__MOBILE__` 编译期常量为 `true`
- `sharedRendererPlugins({ platform })` 会拿到 `mobile`

非移动端则是：

- `platform = 'web'`
- 构建入口：`index.html`
- 输出目录：`dist/desktop`
- `__MOBILE__` 为 `false`

这里的 `desktop` 输出目录名称容易误导。它不是 Electron desktop 主进程构建，而是非 mobile 的 SPA 构建目录。

## 运行/调用流程

### 开发模式流程

以 `bun run dev:spa` 为例：

1. 执行 `vite --port 9876`。
2. Vite 读取 `vite.config.ts`。
3. 根据 `NODE_ENV` 判断 `mode`，通常是 `development`。
4. 通过 `loadEnv` 读取 `.env` 系列文件并合并到 `process.env`。
5. `isMobile` 默认为 `false`，因此 `platform = 'web'`。
6. `define` 注入 `__DEV__`、`__MOBILE__`、`NEXT_PUBLIC_*` 等编译期常量。
7. 加载共享渲染插件，包括 React、平台解析、Markdown 导入、Node 模块 stub 等。
8. 启动 Vite dev server，默认端口是 `9876`。
9. `/api`、`/trpc`、`/oidc`、`/webapi` 请求被代理到 `localhost:3010` 或 `PORT` 指定端口。
10. `lobe-dev-proxy-print` 插件构造 Debug Proxy URL。
11. 如果是普通 dev 模式，重写 `server.printUrls`，让控制台打印 Debug Proxy。
12. 如果是 bundled dev 模式，则等待首次编译完成，显示 spinner，完成后自动打开 Debug Proxy。

Debug Proxy URL 的结构大致是：

```txt
[URL已移除]
```

它的作用是让线上页面加载本地 Vite SPA。这样可以在接近线上配置的环境中调试本地前端。

### 移动端开发流程

以 `bun run dev:spa:mobile` 为例：

1. 设置 `MOBILE=true`。
2. 执行 `vite --port 3012`。
3. `isMobile = true`。
4. `platform = 'mobile'`。
5. 共享插件中的平台解析逻辑按 mobile 平台工作。
6. `__MOBILE__` 被注入为 `true`。
7. 构建/加载入口切换到移动端相关逻辑。

开发命令里显式传了 `--port 3012`，它会覆盖配置里的默认 `server.port: 9876`。

### 生产 Web SPA 构建流程

以 `bun run build:spa` 为例：

1. `build:spa` 设置较大的 `NODE_OPTIONS`，然后运行 `build:spa:raw`。
2. `build:spa:raw` 删除 `public/_spa`，执行 `vite build`。
3. Vite 读取 `vite.config.ts`。
4. `base` 使用 `VITE_CDN_BASE` 或默认 `/_spa/`。
5. 构建入口为 `index.html`。
6. 输出目录为 `dist/desktop`。
7. 使用 `createSharedRolldownOutput({ strictExecutionOrder: true })` 配置 chunk 拆分。
8. `VitePWA` 生成/处理 Workbox 相关缓存逻辑。
9. 如果存在 `VERCEL_DEPLOYMENT_ID`，`vercelSkewProtection` 会改写构建产物里的资源 URL，追加 `dpl` 参数。
10. 构建完成后，后续 `build:spa:copy` 会复制构建结果并生成 SPA 模板。

### 生产移动端 SPA 构建流程

以 `bun run build:spa:mobile` 为例：

1. 设置 `MOBILE=true`。
2. 执行 `vite build`。
3. 构建入口变为 `index.mobile.html`。
4. 输出目录变为 `dist/mobile`。
5. `__MOBILE__` 为 `true`。
6. 其余 chunk、PWA、Vercel skew protection、共享插件逻辑基本一致。

## 小白阅读顺序

1. 先看顶部几个变量：`isMobile`、`mode`、`isDev`、`platform`。  
   这能帮你理解整个配置为什么会分 Web/移动端、开发/生产。

2. 再看 `export default defineConfig({...})` 的一级字段。  
   建议按这个顺序读：`base` → `build` → `define` → `resolve` → `optimizeDeps` → `plugins` → `server`。

3. 重点理解 `build`。  
   这里决定了入口 HTML 和输出目录：`index.html`/`index.mobile.html`、`dist/desktop`/`dist/mobile`。

4. 接着看 `server.proxy`。  
   它解释了为什么本地 Vite SPA 可以访问 `/api` 和 `/trpc`：这些请求会转发到 Next.js dev server。

5. 再看 `plugins` 数组。  
   先记住三个本地核心插件的职责：
   - `vercelSkewProtection`: 生产资源 URL 追加部署 ID。
   - `viteEnvRestartKeys`: `.env` 指定 key 变化才重启。
   - `sharedRendererPlugins`: React、平台解析、Markdown、Node stub 等公共前端插件。

6. 然后读 `plugins/vite/sharedRendererConfig.ts`。  
   这里比 `vite.config.ts` 更接近“为什么 chunk 会这样拆、为什么这些依赖会预构建”。

7. 最后再看 `lobe-dev-proxy-print`。  
   这段代码比较长，但它本质只做一件事：开发时打印或打开 Debug Proxy URL。不要一开始就陷进去。

## 常见误区

1. **误以为 `vite.config.ts` 负责整个 LobeHub 应用构建。**  
   实际上它只负责 SPA 前端部分。完整生产构建还包括 `build:spa:copy` 和 `build:next`。Next.js 仍然有自己的 `next.config.ts` 和构建流程。

2. **误以为 `dist/desktop` 就是 Electron 桌面端。**  
   这里的 `desktop` 更准确地说是“非 mobile 的 SPA 输出”。Electron 相关构建在 `apps/desktop` 下有独立配置。

3. **误以为所有 `.env` 变量都会暴露到浏览器。**  
   `loadEnv(..., '')` 确实读取了很多变量，但 `sharedRendererDefine` 主要只把 `NEXT_PUBLIC_` 开头的变量显式注入为 `process.env.Xxx`。不要在前端代码里随意依赖非公开环境变量。

4. **误以为开发时访问的是纯本地后端。**  
   `dev:spa` 的推荐路径是打开 Debug Proxy URL。这个 URL 在 `app.lobehub.com` 下加载本地 Vite SPA，因此它更像“线上壳 + 本地前端”。同时，本地 Vite server 也配置了 `/api`、`/trpc` 代理到 `localhost:3010`，两种路径要区分清楚。

5. **误以为 `VitePWA` 会自动管理完整 manifest。**  
   当前配置里 `manifest: false`、`injectRegister: null`，说明 manifest 和注册逻辑不是完全由这里自动注入。这里主要关注 Workbox 缓存策略。

6. **误以为 `.env` 文件变化都会触发 Vite 重启。**  
   `viteEnvRestartKeys(['APP_URL'])` 特意限制了重启条件。只有白名单 key 的值变化才会重启服务，普通 `.env` 修改会被 watch ignore 或忽略。

7. **误以为 `base` 在开发和生产一样。**  
   开发时固定是 `/`；生产时才是 `VITE_CDN_BASE` 或 `/_spa/`。如果本地开发没问题但生产资源 404，要优先检查 `base`、CDN 路径和后续 copy/template 脚本。

8. **误以为 Debug Proxy 打不开就是 Vite 启动失败。**  
   Debug Proxy 自动打开依赖系统命令：Windows 的 `rundll32`、macOS 的 `open`、Linux 的 `xdg-open`。如果这些命令不存在或不可用，插件会 warn，但 Vite server 本身可能仍然正常运行。

9. **误以为 chunk 拆分逻辑在 `vite.config.ts` 里。**  
   真正的拆分规则在 `plugins/vite/sharedRendererConfig.ts`：例如 i18n、`model-bank`、`lucide-react`、`@emotion`、`motion` 等会被分到特定 chunk。`vite.config.ts` 只是调用 `createSharedRolldownOutput`。

10. **误以为 `server.port: 9876` 永远生效。**  
   命令行参数优先级更高。比如 `dev:spa:mobile` 使用 `vite --port 3012`，会覆盖配置中的默认端口。
