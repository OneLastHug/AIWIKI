# 文件：next.config.ts

## 它负责什么

`next.config.ts` 是仓库根目录下的 Next.js 配置入口文件。它本身不直接堆大量 Next.js 配置，而是把配置构造工作委托给 `src/libs/next/config/define-config.ts` 里的 `defineConfig`。

这个文件的核心职责很明确：在 Vercel 环境下，为 Next.js 的 serverless 输出做文件追踪裁剪，避免把不需要的原生二进制、SPA 构建产物、桌面端构建产物、数据库迁移文件等打进每个 serverless function。

简化理解：

```ts
import { defineConfig } from './src/libs/next/config/define-config';

const isVercel = !!process.env.VERCEL_ENV;

const nextConfig = defineConfig({
  ...(isVercel ? vercelConfig : {}),
});

export default nextConfig;
```

也就是说，`next.config.ts` 是“环境判断 + 传入局部覆盖配置”的薄入口，真正的通用 Next.js 配置在 `defineConfig` 中。

## 关键组成

第一部分是 `defineConfig` 的导入：

```ts
import { defineConfig } from './src/libs/next/config/define-config';
```

这里没有直接导入 Next.js 的 `NextConfig` 类型，也没有直接写 `headers`、`redirects`、`experimental` 等配置。项目通过自定义封装 `defineConfig` 统一管理 Next.js 配置，避免多个入口重复维护。

第二部分是 Vercel 环境判断：

```ts
const isVercel = !!process.env.VERCEL_ENV;
```

只要存在 `VERCEL_ENV`，就认为当前构建/运行处于 Vercel 相关环境。`VERCEL_ENV` 通常可能是 `production`、`preview`、`development` 等值，但这里不区分具体值，只判断是否存在。

第三部分是 `vercelConfig`：

```ts
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
```

这里配置的是 Next.js 的 `outputFileTracingExcludes`。Next.js 在构建 serverless/standalone 输出时，会分析每个服务端入口实际需要哪些文件。这个配置告诉 Next.js：对所有 route，也就是 `'*'`，排除这些文件。

这些排除项可以分为三类：

1. 原生二进制包的 musl 版本  
   例如 `@napi-rs/canvas-*-musl*`、`sharp-libvips-*musl*`。注释说明 Vercel 使用 Amazon Linux，也就是 glibc 环境，而不是 Alpine Linux 的 musl 环境。因此 musl 相关二进制在 Vercel serverless function 里不需要。

2. SPA / desktop / mobile 构建产物  
   例如 `public/_spa/**`、`dist/desktop/**`、`dist/mobile/**`、`apps/desktop/**`。这些文件可能属于前端 SPA 或 Electron 桌面端构建链路，不应该被每个服务端函数携带。

3. 数据库迁移文件  
   `packages/database/migrations/**` 被排除，说明迁移 SQL/元数据不应进入 Vercel serverless function 的文件追踪包。

注释里提到这能节省约 `45MB`，其中 `canvas-musl` 约 `29MB`，`sharp-musl` 约 `16MB`。所以这不是风格配置，而是部署体积优化配置。

第四部分是最终导出：

```ts
const nextConfig = defineConfig({
  ...(isVercel ? vercelConfig : {}),
});

export default nextConfig;
```

如果是 Vercel 环境，就把 `vercelConfig` 传给 `defineConfig`；否则传一个空配置对象。最终导出的 `nextConfig` 会被 Next.js CLI 自动读取。

## 上下游关系

上游是 Next.js 的配置加载机制。执行 `next build`、`next dev`、`next start`、`next experimental-analyze` 等命令时，Next.js 会读取根目录的 `next.config.ts`。

从 `package.json` 看，相关脚本包括：

```json
"build:next:raw": "next build",
"build:next": "cross-env NODE_OPTIONS=--max-old-space-size=7168 bun run build:next:raw",
"build:docker": "... DOCKER=true next build ...",
"dev:next": "next dev -p 3010",
"dev:bun": "bun --bun next dev -p 3010"
```

这些命令都会走到 `next.config.ts`，再进入 `defineConfig`。

直接下游是 `src/libs/next/config/define-config.ts`。`next.config.ts` 只传入少量按环境变化的配置，`defineConfig` 会合并出完整的 `NextConfig`，包括：

- `output: 'standalone'`：在 Docker 或 `NEXT_BUILD_STANDALONE=1` 时启用；
- `assetPrefix`：来自 `NEXT_PUBLIC_ASSET_PREFIX`；
- `compiler.emotion: true`；
- `compress`：生产环境开启压缩；
- `experimental.optimizePackageImports`；
- `experimental.serverMinification: false`；
- `headers()`：统一设置安全头、缓存头、`.well-known` 文件响应头；
- `redirects()`：维护 sitemap、community、legacy 路由等重定向；
- `serverExternalPackages`：把 `pdfkit`、`@napi-rs/canvas`、`discord.js`、`oidc-provider` 等服务端包外置；
- `transpilePackages`；
- `turbopack.rules`；
- `typescript.ignoreBuildErrors: true`。

因此，`next.config.ts` 和 `defineConfig` 的关系可以理解为：

```text
next build / next dev
        ↓
next.config.ts
        ↓
判断 VERCEL_ENV，决定是否注入 vercelConfig
        ↓
src/libs/next/config/define-config.ts
        ↓
返回完整 NextConfig
        ↓
Next.js 使用该配置构建或运行应用
```

和部署环境的关系也很重要：

- Vercel：`VERCEL_ENV` 存在，启用 `outputFileTracingExcludes`；
- Docker：`DOCKER=true` 时，`defineConfig` 内部启用 `standaloneConfig`，并额外 include Docker 需要的文件；
- 普通本地开发：通常没有 `VERCEL_ENV`，因此不会启用 `vercelConfig`；
- 手动 standalone 构建：`NEXT_BUILD_STANDALONE=1` 时，`defineConfig` 会启用 standalone 输出。

## 运行/调用流程

以 `bun run build` 为例，流程大致是：

```text
bun run build
  → bun run build:spa
  → bun run build:spa:copy
  → bun run build:next
  → bun run build:next:raw
  → next build
  → Next.js 读取 next.config.ts
  → 执行 defineConfig(...)
  → 生成最终 NextConfig
  → 进行 Next.js 构建
```

如果是在 Vercel 上构建，环境中存在 `VERCEL_ENV`，于是：

```ts
defineConfig({
  outputFileTracingExcludes: {
    '*': [
      ...
    ],
  },
});
```

`defineConfig` 内部再把这个字段放进最终配置：

```ts
...(config.outputFileTracingExcludes && {
  outputFileTracingExcludes: config.outputFileTracingExcludes,
}),
```

最终效果是：Next.js 做 output file tracing 时，会排除 `next.config.ts` 指定的 Vercel 专属文件集合。

如果是在 Docker 构建，脚本里明确设置：

```bash
DOCKER=true next build
```

这时 `next.config.ts` 自己未必注入 `vercelConfig`，但 `defineConfig` 内部会识别：

```ts
const buildWithDocker = process.env.DOCKER === 'true';
const isStandaloneMode = buildWithDocker || process.env.NEXT_BUILD_STANDALONE === '1';
```

然后启用 `output: 'standalone'` 和 Docker 需要的 `outputFileTracingIncludes`。这和 Vercel 的 excludes 是两个方向：Vercel 是“排除不该进 serverless 的东西”，Docker standalone 是“确保运行镜像里包含需要的东西”。

如果是在本地 `dev:next`：

```bash
next dev -p 3010
```

通常没有 `VERCEL_ENV`，`next.config.ts` 只调用：

```ts
defineConfig({});
```

此时生效的是 `defineConfig` 里的通用开发/构建配置，例如 Turbopack 规则、headers、redirects、serverExternalPackages 等。

## 小白阅读顺序

建议先读 `next.config.ts`，只抓住三个点：

1. 它导入 `defineConfig`；
2. 它判断 `process.env.VERCEL_ENV`；
3. 它只在 Vercel 环境下注入 `outputFileTracingExcludes`。

然后读 `src/libs/next/config/define-config.ts`。这个文件才是完整 Next.js 配置中心。阅读时可以按以下顺序：

1. 先看顶部环境变量判断：
   - `NODE_ENV`
   - `DOCKER`
   - `ENABLED_CSP`
   - `TEST`
   - `E2E`
   - `NEXT_BUILD_STANDALONE`

2. 再看 `standaloneConfig`：
   - 理解 Docker standalone 构建为什么需要 `output: 'standalone'`；
   - 理解 `outputFileTracingIncludes` 和 `next.config.ts` 中 `outputFileTracingExcludes` 的区别。

3. 再看最终 `nextConfig` 对象：
   - `assetPrefix`
   - `compiler`
   - `compress`
   - `experimental`
   - `headers`
   - `redirects`
   - `serverExternalPackages`
   - `turbopack`
   - `typescript`

4. 最后回到 `package.json` 的 scripts：
   - `build`
   - `build:next`
   - `build:docker`
   - `dev:next`
   - `dev:spa`

这样能把“配置文件写了什么”和“什么时候被执行”连接起来。

## 常见误区

第一个误区：以为 `next.config.ts` 包含了全部 Next.js 配置。  
实际上它只是入口，完整配置在 `src/libs/next/config/define-config.ts`。如果只看根目录文件，会漏掉 headers、redirects、Turbopack、standalone、server external packages 等大量行为。

第二个误区：以为 `vercelConfig` 对所有环境都生效。  
不是。它只在 `process.env.VERCEL_ENV` 存在时注入。普通本地开发、普通 Docker 构建、没有 Vercel 环境变量的 CI 构建，都不会自动应用这组 excludes。

第三个误区：混淆 `outputFileTracingExcludes` 和 `outputFileTracingIncludes`。  
`next.config.ts` 里的是 `outputFileTracingExcludes`，用于 Vercel serverless 优化，目标是减少函数包体积。`defineConfig` 的 `standaloneConfig` 里有 `outputFileTracingIncludes`，尤其在 `DOCKER=true` 时补充 Docker standalone 运行需要的文件。一个是排除，一个是包含，服务的部署场景不同。

第四个误区：看到 `public/_spa/**` 被排除，就以为 SPA 构建产物不会发布。  
这里排除的是 Next.js serverless function 的 file tracing 输出，不等于删除 `public/_spa`，也不等于 SPA 不构建。`package.json` 里 `build` 会先执行 `build:spa` 和 `build:spa:copy`，再执行 `build:next`。排除项只是避免这些静态/桌面产物被塞进每个服务端函数。

第五个误区：以为 musl 包一定不能安装。  
配置只是说在 Vercel serverless 输出中排除 musl 相关二进制，因为 Vercel 使用的运行环境不需要它们。项目依赖层面仍可能存在这些包，尤其 pnpm workspace 和跨平台原生依赖会出现多个平台变体。

第六个误区：以为 `VERCEL_ENV=preview` 和 `VERCEL_ENV=production` 在这里有不同逻辑。  
在 `next.config.ts` 中没有区分具体值，只用 `!!process.env.VERCEL_ENV` 判断是否在 Vercel 环境。其他文件可能会区分 preview/production，但这个文件不区分。

第七个误区：修改 `next.config.ts` 就能解决所有 Next.js 行为问题。  
本仓库把大部分通用配置集中在 `defineConfig`，所以如果要改 headers、redirects、Turbopack、standalone、server external packages，通常应该先看 `src/libs/next/config/define-config.ts`，而不是直接在根配置里追加一堆逻辑。
