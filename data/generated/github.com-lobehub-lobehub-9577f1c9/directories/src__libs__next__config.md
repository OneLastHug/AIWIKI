# 目录：src/libs/next/config

## 它负责什么

`src/libs/next/config` 是项目里集中封装 **Next.js 构建与运行配置** 的小目录。当前目录下只有一个文件：

- `src/libs/next/config/define-config.ts`

它导出 `defineConfig(config)`，供根目录的 `next.config.ts` 调用，用来生成最终的 `NextConfig`。换句话说，这个目录不是业务功能目录，而是 Next.js 配置工厂：把项目通用的构建优化、HTTP 头、缓存策略、重定向、独立部署模式、Turbopack 规则、外部依赖处理等配置收束在一个地方。

根 `next.config.ts` 的使用方式很薄：

```ts
import { defineConfig } from './src/libs/next/config/define-config';

const nextConfig = defineConfig({
  ...(isVercel ? vercelConfig : {}),
});

export default nextConfig;
```

所以真正的 Next.js 配置主体基本都在 `define-config.ts` 中。

## 关键组成

### `CustomNextConfig`

`define-config.ts` 先定义了一个局部接口 `CustomNextConfig`，它只开放一部分可扩展配置：

- `experimental`
- `headers`
- `redirects`
- `serverExternalPackages`
- `turbopack`
- `outputFileTracingIncludes`
- `outputFileTracingExcludes`

这说明调用方不能随意传完整 `NextConfig`，只能补充或覆盖这个封装允许的配置片段。这样的设计可以让项目公共配置保持稳定，同时允许部署环境追加差异配置。

### 环境变量判断

`defineConfig` 内部会读取多个环境变量决定最终行为：

- `NODE_ENV === 'production'`：生产环境开启 `compress`
- `DOCKER === 'true'`：判断是否 Docker 构建
- `ENABLED_CSP === '1'`：是否启用 CSP 相关安全头
- `NODE_ENV === 'test'`、`TEST === '1'`、`E2E === '1'`：判断测试环境
- `NEXT_BUILD_STANDALONE === '1'`：是否构建 standalone 输出
- `NEXT_PUBLIC_ASSET_PREFIX`：设置静态资源前缀 `assetPrefix`

这些判断说明该模块同时服务本地开发、测试、Vercel、Docker standalone 等多种运行形态。

### `standaloneConfig`

当满足以下任一条件时，会启用 standalone 模式：

- `DOCKER === 'true'`
- `NEXT_BUILD_STANDALONE === '1'`

启用后会设置：

```ts
output: 'standalone'
```

并通过 `outputFileTracingIncludes` 显式包含一些文件：

- `public/**/*`
- `.next/static/**/*`
- Docker 构建时额外包含 `public/_spa/**`、`dist/desktop/**`、`dist/mobile/**`
- 数据库迁移文件 `packages/database/migrations/**`
- `@napi-rs/canvas` 相关 native binding

这里的重点是：Next.js standalone 输出依赖 output tracing 自动追踪文件，但动态 `require()` 或 native binding 可能无法被准确识别，所以要手动 include。

### 通用编译与实验配置

生成的 `nextConfig` 中包含：

- `compiler.emotion = true`
- `compress = isProd`
- `reactStrictMode = true`
- `typescript.ignoreBuildErrors = true`

`experimental` 中配置了：

- `optimizePackageImports`
- `serverMinification: false`
- `webVitalsAttribution: ['CLS', 'LCP']`
- `...config.experimental`

`serverMinification: false` 的注释说明它与 `oidc-provider` 有关：`oidc-provider` 依赖 `constructor.name`，而 SWC minification 可能移除名称，所以这里禁用服务端压缩混淆。

### HTTP Headers

`headers()` 是这个文件里体量较大的部分，负责返回全站和静态资源的响应头配置。

全站默认加：

- `x-robots-tag: all`

当 `ENABLED_CSP === '1'` 时，额外加：

- `X-Frame-Options: DENY`
- `Content-Security-Policy: frame-ancestors 'none';`

静态资源缓存策略覆盖了多个路径：

- `/icons/...`
- `/images/...`
- `/videos/...`
- `/screenshots/...`
- `/og/...`
- `/favicon.ico`
- `/favicon-32x32.ico`
- `/apple-touch-icon.png`

这些资源大多设置：

```http
Cache-Control: public, max-age=31536000, immutable
```

部分资源还加了：

- `CDN-Cache-Control`
- `Vercel-CDN-Cache-Control`

另外还为 Passkey 相关 well-known 文件设置了 JSON 类型和较短缓存：

- `/.well-known/apple-app-site-association`
- `/.well-known/assetlinks.json`

最后会拼接调用方传入的 `config.headers`。

### Redirects

`redirects()` 内置了一组历史路径和 SEO 相关重定向：

- `/sitemap.xml`、`/sitemap-0.xml` 到 `/sitemap-index.xml`
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

最后同样拼接调用方传入的 `config.redirects`。

### `serverExternalPackages`

默认把一些包声明为服务端外部包，不交给 Next.js/Turbopack 打包：

- `pdfkit`
- `@napi-rs/canvas`
- `@lobehub/editor`
- `discord.js`
- `ffmpeg-static`
- `pdfjs-dist`
- `ajv`
- `oidc-provider`

注释特别提到：开发模式下，Turbopack 处理 native module 容易出 bundle error，尤其是 `@napi-rs/canvas`，而 `pdfjs-dist` 在 Node.js 环境中可能通过它做 `DOMMatrix` polyfill。

### `turbopack.rules`

`turbopack` 里配置了两类规则：

一类是非测试环境下注入 `codeInspectorPlugin`：

```ts
codeInspectorPlugin({
  bundler: 'turbopack',
  hotKeys: ['altKey', 'ctrlKey'],
})
```

它通常用于开发时通过快捷键定位源码。

另一类是让 `.md` 文件通过 `raw-loader` 当成 JS 模块导入：

```ts
'*.md': {
  as: '*.js',
  loaders: ['raw-loader'],
}
```

最后拼接 `config.turbopack`，允许调用方补充 Turbopack 配置。

## 上下游关系

上游调用方主要是根目录的 `next.config.ts`。

`next.config.ts` 根据是否处于 Vercel 环境构造 `vercelConfig`：

```ts
const isVercel = !!process.env.VERCEL_ENV;
```

在 Vercel 上，它传入 `outputFileTracingExcludes`，排除一些不需要进入 serverless function 的文件：

- musl 版本的 `@napi-rs/canvas`
- musl 版本的 `sharp-libvips`
- `public/_spa/**`
- `dist/desktop/**`
- `dist/mobile/**`
- `apps/desktop/**`
- `packages/database/migrations/**`

这与 `define-config.ts` 里的 standalone include 形成互补：

- Docker standalone 构建更关心“需要把哪些文件带进去”
- Vercel serverless 构建更关心“哪些文件不要被追踪进去，避免函数体积过大”

下游消费方是 Next.js 自身。`defineConfig` 返回的对象会被 Next.js 在构建和启动时读取，用于影响：

- 构建输出形态
- 静态资源路径
- HTTP headers
- redirects
- Turbopack 行为
- 服务端依赖打包策略
- TypeScript 构建错误处理
- React strict mode
- fetch logging

同级邻近目录还有 `src/libs/next/proxy/define-config.ts`、`src/libs/next/Link.tsx`、`src/libs/next/navigation.ts` 等。它们也属于 `src/libs/next` 的 Next.js 适配层，但职责不同：

- `config/define-config.ts`：生成 Next.js 根配置
- `proxy/define-config.ts`：根据文件名推断，更偏 middleware/proxy 配置
- `Link.tsx`、`navigation.ts`、`dynamic.tsx`：更偏运行时代码中的 Next.js API 适配
- `nextjsOnlyRoutes.ts`：维护必须走 Next.js 而不是 SPA catch-all 的路由列表

根据当前片段推断，`src/libs/next` 是项目中隔离 Next.js 框架差异的工具层，而 `src/libs/next/config` 是其中专门面向构建配置的子模块。

## 运行/调用流程

1. Next.js 启动或构建时读取根目录 `next.config.ts`。

2. `next.config.ts` 判断当前是否在 Vercel 环境：

```ts
const isVercel = !!process.env.VERCEL_ENV;
```

3. 如果是 Vercel，则准备一份 `vercelConfig`，主要用于 `outputFileTracingExcludes`，减少 serverless function 体积。

4. `next.config.ts` 调用：

```ts
defineConfig({
  ...(isVercel ? vercelConfig : {}),
});
```

5. `defineConfig` 内部读取环境变量，计算：

- 是否生产环境
- 是否 Docker 构建
- 是否测试环境
- 是否 standalone 模式
- 是否启用 CSP
- 是否设置 asset prefix

6. 如果是 Docker 或显式 standalone 构建，则合入 `standaloneConfig`。

7. 生成完整 `nextConfig`，包括 compiler、experimental、headers、redirects、serverExternalPackages、turbopack 等配置。

8. 返回 `nextConfig` 给 `next.config.ts`。

9. Next.js 根据该配置执行构建、开发服务器启动、请求头注入、重定向处理和依赖 tracing。

可以把它理解成一条配置装配链：

```text
环境变量 + next.config.ts 传入项
        ↓
src/libs/next/config/define-config.ts
        ↓
NextConfig
        ↓
Next.js build / dev / runtime
```

## 小白阅读顺序

1. 先看根目录 `next.config.ts`

先理解这个项目的 Next.js 配置入口非常薄，只负责判断 Vercel 环境，然后调用 `defineConfig`。

2. 再看 `CustomNextConfig`

理解这个封装允许调用方扩展哪些字段。它不是完整开放 `NextConfig`，而是有意限制配置入口。

3. 再看环境变量判断

重点关注：

- `DOCKER`
- `NEXT_BUILD_STANDALONE`
- `VERCEL_ENV`
- `ENABLED_CSP`
- `NEXT_PUBLIC_ASSET_PREFIX`

这些变量决定同一份代码在本地、Vercel、Docker、测试环境下的不同行为。

4. 再看 `standaloneConfig`

理解 Docker standalone 构建为什么需要手动包含 native binding、静态资源和迁移文件。

5. 再看 `headers()`

这部分虽然长，但结构很简单：全站安全头 + 静态资源长缓存 + well-known 文件特殊处理 + 外部传入 headers。

6. 再看 `redirects()`

把它当成历史 URL 兼容表和 SEO 路由迁移表即可。

7. 最后看 `serverExternalPackages` 和 `turbopack`

这两块更偏构建问题排查。遇到 native package、Turbopack bundle error、Markdown 导入、源码定位插件相关问题时，再重点读。

## 常见误区

1. 误以为这个目录是运行时业务逻辑

`src/libs/next/config` 不处理页面渲染，也不处理 API 请求业务逻辑。它只生成 Next.js 配置对象，主要在构建、启动和路由层面生效。

2. 误以为 `headers()` 只影响静态资源

它也会对 `/:path*` 添加全站 header，例如 `x-robots-tag`，在启用 CSP 时还会加防 iframe 嵌入相关头。

3. 误以为 CSP 默认开启

CSP 只有在：

```text
ENABLED_CSP=1
```

时才会加 `X-Frame-Options` 和 `Content-Security-Policy`。默认逻辑只加 `x-robots-tag`。

4. 误以为 standalone 只由 Next.js 自动处理

这里的 standalone 还显式配置了 `outputFileTracingIncludes`，尤其是 Docker 构建时会手动包含 native binding 和若干产物目录。原因是 Next.js tracing 对动态加载和 native 模块不一定完全可靠。

5. 误以为 Vercel 和 Docker 使用同一套 tracing 策略

两者策略不同：

- Docker standalone：倾向于 include 必要文件，保证运行时不缺依赖
- Vercel serverless：倾向于 exclude 不必要文件，降低函数体积

6. 误以为 `config.outputFileTracingIncludes` 会和默认 includes 自动深度合并

当前代码里先通过 `standaloneConfig` 设置 `outputFileTracingIncludes`，随后如果调用方传入 `config.outputFileTracingIncludes`，会在顶层再次赋值：

```ts
...(config.outputFileTracingIncludes && {
  outputFileTracingIncludes: config.outputFileTracingIncludes,
})
```

这意味着调用方传入该字段时可能覆盖前面 standalone 的 includes，而不是深度合并。阅读或修改时要特别注意这一点。

7. 误以为 `typescript.ignoreBuildErrors: true` 表示项目不重视类型

这里表示 Next.js 构建阶段忽略 TypeScript 错误，但仓库规范仍要求通过单独命令做类型检查，例如 `bun run type-check`。构建配置和质量门禁不是同一个概念。

8. 误以为所有 redirects 都是永久跳转

大部分是 `permanent: true`，但 `/repos` 到 `/files` 是：

```ts
permanent: false
```

注释说明未来可能还会恢复 `/repos` URL，所以这里保留临时跳转语义。

9. 误以为 `codeInspectorPlugin` 测试环境也会启用

`isTest` 为真时，`turbopack.rules` 中不会注入 `codeInspectorPlugin`。这能避免测试环境受到开发辅助插件影响。

10. 误以为 `serverExternalPackages` 可以随便删

这些包多与 native module、动态加载、服务端运行时或大型依赖有关。删除后可能不会立刻在普通页面报错，但在 PDF、Canvas、OIDC、Discord、FFmpeg 等场景中引发构建或运行时问题。
