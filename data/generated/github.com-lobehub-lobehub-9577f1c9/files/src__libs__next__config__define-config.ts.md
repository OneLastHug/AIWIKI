# 文件：src/libs/next/config/define-config.ts

## 它负责什么

`src/libs/next/config/define-config.ts` 是项目的 **Next.js 配置工厂函数**。它导出 `defineConfig(config)`，由仓库根目录的 `next.config.ts` 调用，用来生成最终的 `NextConfig`。

它的核心职责不是写业务逻辑，而是把 LobeHub 在不同运行环境下需要的 Next.js 构建、部署、缓存、安全、重定向、Turbopack、原生依赖追踪等配置集中管理起来。

可以把它理解为：

> 项目级 Next.js 配置的“封装层”：外部只传少量可扩展配置，它内部负责补齐 LobeHub 默认约定。

这个文件主要处理这些事情：

1. 根据环境变量判断是否启用 `standalone` 构建。
2. 配置 Docker / Vercel / 普通构建下的文件追踪规则。
3. 配置公共资源缓存头。
4. 配置可选的 CSP 安全头。
5. 配置旧路径到新路径的 redirects。
6. 配置需要外置的服务端依赖包。
7. 配置 Turbopack 规则，包括 Markdown raw loader 和开发期代码定位插件。
8. 开启 React strict mode、Emotion 编译支持、压缩、包导入优化等 Next.js 行为。

## 关键组成

### `CustomNextConfig`

文件内部定义了一个本地接口：

```ts
interface CustomNextConfig {
  experimental?: NextConfig['experimental'];
  headers?: Header[];
  outputFileTracingExcludes?: NextConfig['outputFileTracingExcludes'];
  outputFileTracingIncludes?: NextConfig['outputFileTracingIncludes'];
  redirects?: Redirect[];
  serverExternalPackages?: NextConfig['serverExternalPackages'];
  turbopack?: NextConfig['turbopack'];
}
```

它不是完整的 `NextConfig`，而是允许调用方传入一小部分“可合并”的配置。

这说明作者不希望调用方随意覆盖全部 Next.js 配置，而是只开放几个稳定扩展点：

- `experimental`
- `headers`
- `redirects`
- `outputFileTracingExcludes`
- `outputFileTracingIncludes`
- `serverExternalPackages`
- `turbopack`

也就是说，`defineConfig` 本身掌握项目默认配置，调用方只能补充或覆盖指定区域。

### 环境判断变量

函数开头根据环境变量计算几个关键布尔值：

```ts
const isProd = process.env.NODE_ENV === 'production';
const buildWithDocker = process.env.DOCKER === 'true';
const shouldUseCSP = process.env.ENABLED_CSP === '1';
const isTest =
  process.env.NODE_ENV === 'test' || process.env.TEST === '1' || process.env.E2E === '1';
const isStandaloneMode = buildWithDocker || process.env.NEXT_BUILD_STANDALONE === '1';
```

它们分别控制：

- `isProd`：生产环境才开启 `compress`。
- `buildWithDocker`：Docker 构建时追加更多 standalone 文件追踪。
- `shouldUseCSP`：是否给所有路径加 `X-Frame-Options` 和 `Content-Security-Policy`。
- `isTest`：测试或 E2E 环境下跳过 `codeInspectorPlugin`。
- `isStandaloneMode`：是否启用 Next.js `output: 'standalone'`。

这里的设计重点是：同一个配置函数要兼容本地开发、测试、Docker 部署、Vercel 部署等不同场景。

### `standaloneConfig`

`standaloneConfig` 是在 Docker 或显式设置 `NEXT_BUILD_STANDALONE=1` 时才合入的配置：

```ts
const standaloneConfig: NextConfig = {
  output: 'standalone',
  outputFileTracingIncludes: {
    '*': [
      'public/**/*',
      '.next/static/**/*',
      ...
    ],
  },
};
```

其中 `output: 'standalone'` 是 Next.js 的独立部署输出模式，常用于 Docker 镜像。

它默认包含：

- `public/**/*`
- `.next/static/**/*`

如果是 Docker 构建，还额外包含：

- `public/_spa/**`
- `dist/desktop/**`
- `dist/mobile/**`
- `packages/database/migrations/**`
- `node_modules/@napi-rs/canvas/**/*`
- `node_modules/@napi-rs/canvas-*/**/*`
- `node_modules/.pnpm/@napi-rs+canvas*/**/*`
- `node_modules/.pnpm/@napi-rs+canvas-*/**/*`

注释里解释了原因：`@napi-rs/canvas` 可能通过动态 `require()` 被加载，Next.js 的 output tracing 不一定能自动发现，所以 Docker standalone 构建时要显式包含这些原生绑定文件。

这里要注意一个细节：这些 native bindings 只在 Docker standalone 场景下包含。注释明确说，在 Vercel serverless 上包含 native bindings 容易导致函数体积超限。

### `assetPrefix`

```ts
const assetPrefix = process.env.NEXT_PUBLIC_ASSET_PREFIX;
```

最终会进入：

```ts
assetPrefix,
```

这表示静态资源前缀由 `NEXT_PUBLIC_ASSET_PREFIX` 控制。常见用途是 CDN 前缀或部署在非根路径下的资源地址调整。

### `compiler`

```ts
compiler: {
  emotion: true,
},
```

项目使用 Emotion / antd-style 相关能力，这里开启 Next.js 编译器对 Emotion 的支持。

### `compress`

```ts
compress: isProd,
```

只有 `NODE_ENV === 'production'` 时开启压缩。

### `experimental`

```ts
experimental: {
  optimizePackageImports: [
    'emoji-mart',
    '@emoji-mart/react',
    '@emoji-mart/data',
    '@icons-pack/react-simple-icons',
    '@lobehub/ui',
    '@lobehub/icons',
  ],
  serverMinification: false,
  webVitalsAttribution: ['CLS', 'LCP'],
  ...config.experimental,
},
```

这里有三类配置：

第一类是 `optimizePackageImports`，用于优化一些大包或组件库的导入：

- `emoji-mart`
- `@emoji-mart/react`
- `@emoji-mart/data`
- `@icons-pack/react-simple-icons`
- `@lobehub/ui`
- `@lobehub/icons`

第二类是：

```ts
serverMinification: false
```

注释说明：`oidc-provider` 依赖 `constructor.name`，而 SWC minification 可能会移除或改变 name，因此禁用服务端压缩。

第三类是：

```ts
webVitalsAttribution: ['CLS', 'LCP']
```

用于 Web Vitals 指标归因。

最后通过：

```ts
...config.experimental
```

允许调用方覆盖或补充 experimental 配置。由于它放在最后，调用方传入的 `experimental` 优先级更高。

### `headers()`

`headers` 是这个文件里最长的逻辑之一，用于生成 Next.js 自定义响应头。

基础安全头：

```ts
const securityHeaders = [
  {
    key: 'x-robots-tag',
    value: 'all',
  },
];
```

默认给所有路径：

```ts
source: '/:path*'
```

加上 `x-robots-tag: all`。

如果 `ENABLED_CSP === '1'`，会额外加：

```ts
X-Frame-Options: DENY
Content-Security-Policy: frame-ancestors 'none';
```

这表示禁止页面被其他页面通过 frame 嵌入，主要用于防点击劫持。

然后它给多个静态资源路径配置长期缓存：

- `/icons/(.*).(png|jpe?g|gif|svg|ico|webp)`
- `/images/(.*).(png|jpe?g|gif|svg|ico|webp)`
- `/videos/(.*).(mp4|webm|ogg|avi|mov|wmv|flv|mkv)`
- `/screenshots/(.*).(png|jpe?g|gif|svg|ico|webp)`
- `/og/(.*).(png|jpe?g|gif|svg|ico|webp)`
- `/favicon.ico`
- `/favicon-32x32.ico`
- `/apple-touch-icon.png`

大部分静态资源使用：

```txt
Cache-Control: public, max-age=31536000, immutable
```

部分资源还附加：

```txt
CDN-Cache-Control
Vercel-CDN-Cache-Control
```

这说明项目希望浏览器、CDN、Vercel CDN 都能长期缓存这些带 hash 或稳定路径的静态资源。

另外还配置了 Passkey 相关 well-known 文件：

- `/.well-known/apple-app-site-association`
- `/.well-known/assetlinks.json`

它们设置：

```txt
Content-Type: application/json
Cache-Control: public, max-age=3600
```

这类文件通常用于 iOS / Android 与站点之间的关联验证，例如 passkey、Universal Links、App Links 等场景。

最后：

```ts
...(config.headers ?? []),
```

调用方可以追加自己的 headers。

### `logging`

```ts
logging: {
  fetches: {
    fullUrl: true,
    hmrRefreshes: true,
  },
},
```

这里打开 Next.js fetch 日志的完整 URL 和 HMR 刷新相关日志。它更偏开发调试和运行观测。

### `outputFileTracingExcludes` / `outputFileTracingIncludes`

```ts
...(config.outputFileTracingExcludes && {
  outputFileTracingExcludes: config.outputFileTracingExcludes,
}),
...(config.outputFileTracingIncludes && {
  outputFileTracingIncludes: config.outputFileTracingIncludes,
}),
```

这里允许调用方覆盖或补充 Next.js 文件追踪规则。

直接调用方 `next.config.ts` 在 Vercel 环境下传入了 `outputFileTracingExcludes`，用于排除 musl 版本 native 包和一些构建产物：

- `node_modules/.pnpm/@napi-rs+canvas-*-musl*`
- `node_modules/.pnpm/@img+sharp-libvips-*musl*`
- `public/_spa/**`
- `dist/desktop/**`
- `dist/mobile/**`
- `apps/desktop/**`
- `packages/database/migrations/**`

根据当前片段推断，这样做是为了降低 Vercel serverless function 的体积。依据是 `next.config.ts` 中的注释明确写到 Vercel 使用 Amazon Linux glibc，而不是 Alpine Linux musl，并说明可节省约 45MB。

### `redirects`

`redirects` 返回固定重定向列表，并允许调用方追加：

```ts
redirects: async () => [
  ...
  ...(config.redirects ?? []),
],
```

内置重定向包括：

- `/sitemap.xml` 到 `/sitemap-index.xml`
- `/sitemap-0.xml` 到 `/sitemap-index.xml`
- `/sitemap/plugins.xml` 到 `/sitemap/plugins-1.xml`
- `/sitemap/assistants.xml` 到 `/sitemap/assistants-1.xml`
- `/manifest.json` 到 `/manifest.webmanifest`
- `/community/assistants` 到 `/community/agent`
- `/community/plugins` 到 `/community/plugin`
- `/community/models` 到 `/community/model`
- `/community/providers` 到 `/community/provider`
- `/discover` 到 `/community`
- `/discover/:path*` 到 `/community/:path*`
- `/repos` 到 `/files`
- `/chat` 到 `/`
- `/login` 到 `/signin`

这些重定向反映了项目历史路径迁移：

- `discover` 迁移到 `community`
- 旧的复数资源路径迁移到单数资源路径
- 旧 Clerk 登录路径 `/login` 迁移到 Better Auth 的 `/signin`
- `/chat` 回到首页
- `/repos` 临时跳到 `/files`

其中 `/repos -> /files` 是 `permanent: false`，注释说未来可能还要恢复 `/repos` URL，因此这里不是永久跳转。

### `serverExternalPackages`

```ts
serverExternalPackages: config.serverExternalPackages ?? [
  'pdfkit',
  '@napi-rs/canvas',
  '@lobehub/editor',
  'discord.js',
  'ffmpeg-static',
  'pdfjs-dist',
  'ajv',
  'oidc-provider',
],
```

这些包在服务端构建时被标记为 external，不让 Next.js 打包进服务端 bundle。

注释特别说明：

```ts
// when external packages in dev mode with turbopack, this config will lead to bundle error
// @napi-rs/canvas is a native module that can't be bundled by Turbopack
// pdfjs-dist uses @napi-rs/canvas for DOMMatrix polyfill in Node.js environment
```

这里的关键点是 native module 和某些大型库不适合被 Turbopack/Next.js 直接打包。

默认 external 包包括 PDF、Canvas、编辑器、Discord、FFmpeg、JSON schema、OIDC 相关依赖。

如果调用方传了 `serverExternalPackages`，会完全替代默认列表，而不是合并。这是一个容易误解的地方。

### `transpilePackages`

```ts
transpilePackages: ['mermaid', 'better-auth-harmony'],
```

这些包需要经过 Next.js 转译。常见原因是包发布格式、浏览器兼容、ESM/CJS 处理或项目构建环境需要。

### `turbopack`

```ts
turbopack: {
  rules: {
    ...(isTest
      ? void 0
      : codeInspectorPlugin({
          bundler: 'turbopack',
          hotKeys: ['altKey', 'ctrlKey'],
        })),
    '*.md': {
      as: '*.js',
      loaders: ['raw-loader'],
    },
  },
  ...config.turbopack,
},
```

这里有两个默认规则。

第一，非测试环境启用 `codeInspectorPlugin`：

```ts
codeInspectorPlugin({
  bundler: 'turbopack',
  hotKeys: ['altKey', 'ctrlKey'],
})
```

这个插件通常用于开发时从页面元素跳转或定位到源码。它绑定了 `altKey + ctrlKey`。测试环境禁用它，避免影响测试稳定性。

第二，`.md` 文件通过 `raw-loader` 作为 JS 导入：

```ts
'*.md': {
  as: '*.js',
  loaders: ['raw-loader'],
}
```

这意味着项目中可以把 Markdown 文件当作原始字符串导入。

最后：

```ts
...config.turbopack
```

调用方可以覆盖 Turbopack 配置。注意这里的展开在 `rules` 同级，如果调用方传了 `turbopack.rules`，根据对象合并方式，可能覆盖整个默认 `rules`，而不是深度合并其中每一条规则。

### `typescript`

```ts
typescript: {
  ignoreBuildErrors: true,
},
```

这表示 Next.js 构建阶段忽略 TypeScript 类型错误。

这不等于项目不做类型检查。根据仓库说明，类型检查应通过：

```bash
bun run type-check
```

也就是说，类型检查被从 Next.js build 流程中拆出来，可能是为了加快构建、避免部署流程被 Next 内置 type-check 阻断，或者由 CI 单独负责。

## 上下游关系

### 上游：`next.config.ts`

仓库根目录的 `next.config.ts` 是这个文件的直接调用方：

```ts
import { defineConfig } from './src/libs/next/config/define-config';

const isVercel = !!process.env.VERCEL_ENV;

const vercelConfig = {
  outputFileTracingExcludes: {
    '*': [
      'node_modules/.pnpm/@napi-rs+canvas-*-musl*',
      'node_modules/.pnpm/@img+sharp-libvips-*musl*',
      'public/_spa/**',
      'dist/desktop/**',
      'dist/mobile/**',
      'apps/desktop/**',
      'packages/database/migrations/**',
    ],
  },
};

const nextConfig = defineConfig({
  ...(isVercel ? vercelConfig : {}),
});

export default nextConfig;
```

也就是说：

- `next.config.ts` 判断是否是 Vercel 环境。
- 如果是 Vercel，就传入 `outputFileTracingExcludes`。
- `defineConfig` 在内部合成完整 Next.js 配置。
- 最终导出给 Next.js 使用。

### 下游：Next.js 构建和运行时

`defineConfig` 返回的是 `NextConfig`，最终被 Next.js 消费。

它影响的下游包括：

- `next build`
- `next dev`
- Vercel serverless 构建
- Docker standalone 构建
- 静态资源响应头
- 页面路由 redirects
- 服务端 bundle 依赖处理
- Turbopack 开发构建规则
- TypeScript 构建行为
- React strict mode 行为

### 相关邻近文件

`src/libs/next/config/` 目录下当前只看到这个文件：

```txt
src/libs/next/config/define-config.ts
```

`src/libs/next/` 目录中还有一些 Next.js 兼容封装：

- `Image.tsx`
- `Link.tsx`
- `dynamic.tsx`
- `index.ts`
- `navigation.ts`
- `navigation.vite.ts`
- `nextjsOnlyRoutes.ts`
- `proxy/define-config.ts`

这些文件和当前目标文件同属 `src/libs/next` 这一层，但职责不同。当前文件管的是 `next.config.ts`，而其他文件更多是运行时代码或路由/代理相关封装。

## 运行/调用流程

整体流程可以按构建启动时理解：

1. Next.js 读取根目录 `next.config.ts`。
2. `next.config.ts` 导入 `src/libs/next/config/define-config.ts` 的 `defineConfig`。
3. `next.config.ts` 判断 `process.env.VERCEL_ENV`。
4. 如果是 Vercel 环境，准备 `vercelConfig.outputFileTracingExcludes`。
5. 调用：

   ```ts
   defineConfig({
     ...(isVercel ? vercelConfig : {}),
   })
   ```

6. `defineConfig` 内部读取多个环境变量：

   - `NODE_ENV`
   - `DOCKER`
   - `ENABLED_CSP`
   - `TEST`
   - `E2E`
   - `NEXT_BUILD_STANDALONE`
   - `NEXT_PUBLIC_ASSET_PREFIX`

7. 如果是 Docker 或 standalone 模式，合入：

   ```ts
   output: 'standalone'
   ```

   以及对应的 `outputFileTracingIncludes`。

8. 生成基础 `nextConfig`，包含：

   - `assetPrefix`
   - `compiler.emotion`
   - `compress`
   - `experimental`
   - `headers`
   - `logging`
   - `reactStrictMode`
   - `redirects`
   - `serverExternalPackages`
   - `transpilePackages`
   - `turbopack`
   - `typescript.ignoreBuildErrors`

9. 如果调用方传入了 `headers`、`redirects`、`experimental`、`turbopack` 等扩展配置，则按文件中写好的位置合并进去。

10. 返回最终 `nextConfig` 给 `next.config.ts`。

11. Next.js 根据这个配置执行开发、构建或部署。

可以用一句话概括调用链：

```txt
next.config.ts -> defineConfig(customConfig) -> NextConfig -> Next.js build/dev/runtime
```

## 小白阅读顺序

建议按下面顺序读，不要一开始就陷入 headers 的长列表。

### 1. 先看文件顶部 import

```ts
import { codeInspectorPlugin } from 'code-inspector-plugin';
import { type NextConfig } from 'next';
import { type Header, type Redirect } from 'next/dist/lib/load-custom-routes';
```

这里说明这个文件主要依赖三类东西：

- `NextConfig`：Next.js 配置类型。
- `Header` / `Redirect`：Next.js 自定义 headers 和 redirects 的类型。
- `codeInspectorPlugin`：开发期源码定位插件。

### 2. 再看 `CustomNextConfig`

理解调用方能传什么。

重点是：它不是完整 Next.js config，只开放有限字段。

### 3. 看 `defineConfig` 开头的环境变量

这一段决定了后续配置分支：

```ts
const isProd = ...
const buildWithDocker = ...
const shouldUseCSP = ...
const isTest = ...
const isStandaloneMode = ...
```

读懂这些变量后，后面大部分条件都能理解。

### 4. 看 `standaloneConfig`

这里解释了 Docker standalone 构建为什么要包含额外文件，尤其是 native bindings 和 SPA/desktop/mobile 构建产物。

### 5. 跳过 headers 长列表，先看 `nextConfig` 的整体结构

建议先扫这些顶层字段：

```ts
assetPrefix
compiler
compress
experimental
headers
logging
reactStrictMode
redirects
serverExternalPackages
transpilePackages
turbopack
typescript
```

先知道有哪些配置区域，再回头细读每块。

### 6. 回头读 `headers`

`headers` 里虽然长，但结构很规则：

- 第一段是全局安全头。
- 中间是静态资源长期缓存。
- 最后是 passkey well-known 文件。
- 末尾追加 `config.headers`。

### 7. 再读 `redirects`

`redirects` 是历史 URL 兼容表。读的时候重点看 source 和 destination，不必纠结每条业务含义。

### 8. 最后看 `next.config.ts`

直接调用方能帮助你理解这个文件为什么设计成“配置工厂”：

```ts
const nextConfig = defineConfig({
  ...(isVercel ? vercelConfig : {}),
});
```

这说明根配置文件很薄，复杂逻辑都被收进 `define-config.ts`。

## 常见误区

### 误区 1：以为 `defineConfig` 是 Next.js 官方函数

不是。这里的 `defineConfig` 是项目自定义函数，只是名字上借鉴了很多构建工具常见的 `defineConfig` 风格。

它最终返回的是 `NextConfig`，但函数本身由 LobeHub 自己实现。

### 误区 2：以为 `CustomNextConfig` 等于完整 `NextConfig`

不是。`CustomNextConfig` 只开放了少数字段。调用方不能通过它传入任意 Next.js 配置。

这样做可以减少根配置被随意改乱的风险，让项目默认配置集中在一个地方。

### 误区 3：以为 Docker 和 Vercel 的文件追踪策略一样

不一样。

Docker standalone 构建时，文件里倾向于显式包含更多运行所需文件，尤其是 native bindings。

Vercel serverless 环境下，`next.config.ts` 反而传入 `outputFileTracingExcludes` 排除一些 musl 包和大体积构建产物，避免函数体积过大。

### 误区 4：以为 `serverExternalPackages` 会和默认值合并

不会。

代码是：

```ts
serverExternalPackages: config.serverExternalPackages ?? [
  ...
]
```

这意味着如果调用方传了 `serverExternalPackages`，就直接使用调用方的数组，默认列表不会自动保留。

如果未来要新增调用方自定义 external 包，需要注意不要意外丢掉默认 external 包。

### 误区 5：以为 `config.turbopack` 是深度合并

不一定。

当前写法是：

```ts
turbopack: {
  rules: {
    ...
  },
  ...config.turbopack,
},
```

因为 `...config.turbopack` 在后面，如果调用方传入 `turbopack.rules`，可能覆盖前面默认的 `rules` 对象。

所以扩展 Turbopack 配置时要特别小心，不要误删：

- `codeInspectorPlugin`
- `*.md` raw-loader 规则

### 误区 6：以为测试环境也会启用 `codeInspectorPlugin`

不会。

测试环境判断包括：

```ts
NODE_ENV === 'test'
TEST === '1'
E2E === '1'
```

只要满足其中之一，就不会加入 `codeInspectorPlugin`。

这通常是为了减少测试环境里的额外构建行为和不稳定因素。

### 误区 7：以为开启 `typescript.ignoreBuildErrors` 就不用管类型错误

不是。

这个配置只是让 Next.js build 不因为 TS 类型错误中断。仓库规范仍然要求运行：

```bash
bun run type-check
```

所以类型检查仍然存在，只是不由 Next.js build 阶段直接承担。

### 误区 8：以为 CSP 默认开启

不是。

CSP 只有在：

```txt
ENABLED_CSP=1
```

时才会添加：

```txt
X-Frame-Options: DENY
Content-Security-Policy: frame-ancestors 'none';
```

默认情况下只有：

```txt
x-robots-tag: all
```

### 误区 9：以为所有 redirects 都是永久跳转

不是。

大多数是：

```ts
permanent: true
```

但 `/repos -> /files` 是：

```ts
permanent: false
```

注释说明未来可能还会恢复 `/repos` URL，所以这里保留为临时跳转。

### 误区 10：以为静态资源缓存头只对浏览器有效

不完全是。

部分路径不仅设置了：

```txt
Cache-Control
```

还设置了：

```txt
CDN-Cache-Control
Vercel-CDN-Cache-Control
```

这说明缓存策略同时考虑了浏览器、通用 CDN 和 Vercel CDN。
