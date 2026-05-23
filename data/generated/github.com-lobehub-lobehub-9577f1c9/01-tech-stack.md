# 技术栈说明

从根目录 `package.json`、`tsconfig.json`、`next.config.ts`、`vite.config.ts`、`apps/desktop/package.json` 和 `apps/cli/package.json` 可以确认，这个仓库的主语言是 TypeScript，运行时以 Node.js/Bun 为主，前端框架是 Next.js 16 + React 19，但界面主体并不是传统 App Router 页面，而是通过 Vite 构建的 SPA 再嵌入到 Next.js 壳中。`package.json` 里可直接看到 `next`、`react`、`react-dom`、`react-router-dom`、`vite`、`vitest`、`zustand`、`swr`、`drizzle-orm`、`better-auth`、`hono`、`@trpc/client`、`@trpc/server`、`@lobehub/ui` 和 `antd` 等关键依赖。

包管理和脚本信号也很明确。根目录 `package.json` 使用 `pnpm` workspace 声明 `packages/*`、`packages/business/*`、`e2e` 和 `apps/desktop/src/main`，但脚本大量通过 `bun run`、`bunx`、`tsx`、`next`、`vite`、`drizzle-kit`、`vitest` 和 `electron-vite` 组合运行，说明仓库对开发者工具链采用的是“pnpm 管依赖、bun 跑脚本、部分任务借助 tsx/tsx-like 入口”的混合方式。`scripts/devStartupSequence.mts` 进一步证明开发启动不是单一命令，而是会同时启动 Next.js 与 Vite，并在本地端口就绪后做预热。

前端技术栈的关键点是“路由和渲染分离”。`src/spa/entry.web.tsx`、`src/spa/entry.mobile.tsx`、`src/spa/entry.desktop.tsx`、`src/spa/entry.popup.tsx` 都会把 React Router 挂载到根节点；`src/spa/router/desktopRouter.config.tsx`、`src/spa/router/mobileRouter.config.tsx`、`src/spa/router/popupRouter.config.tsx` 负责路由树；`src/utils/router.tsx` 负责把 `RouteObject` 组装成浏览器路由，并且注入 `SPAGlobalProvider` 和 `BusinessGlobalProvider`。这意味着读源码时要先把“页面段”与“业务 feature”分开看，不能把 `src/routes` 误当成传统 Next 页面目录。

UI 层依赖 `@lobehub/ui`、`antd` 和 `antd-style`，并配合 `lucide-react` 图标、`react-hotkeys-hook` 快捷键、`react-scan`、`motion/react`、`@dnd-kit/*`、`@floating-ui/react`、`@formkit/auto-animate` 等组件库。样式系统上，仓库偏向 CSS-in-JS，且从 `src/layout/SPAGlobalProvider/index.tsx`、`src/utils/router.tsx` 与多个组件目录可以看出全局主题、弹窗宿主和上下文菜单宿主都是在根层统一挂载。

服务端技术栈的关键点有三层。第一层是 Next.js App Router 里的 `src/app/(backend)`，它承载 `api`、`trpc`、`webapi`、`market`、`oidc`、`workflows` 和 `spa` 等后端路由；第二层是 `src/server`，这里放 tRPC router、业务 service、runtime config、feature flags、workflow 处理器和 Agent 运行时协调逻辑；第三层是 `packages/database`，它使用 Drizzle ORM 和 PostgreSQL 数据模型来提供 schema、model 和 repository。`src/app/(backend)/trpc/lambda/[trpc]/route.ts`、`src/libs/trpc/lambda/context.ts`、`packages/database/src/schemas/index.ts`、`packages/database/migrations/*` 是读这部分最直接的入口。

如果只看运行环境，至少要记住三件事。其一，`vite.config.ts` 里有 `MOBILE=true`、`VITE_CDN_BASE`、`APP_URL` 等环境输入，说明 SPA 构建会按平台切换。其二，`next.config.ts` 里根据 `VERCEL_ENV` 调整 tracing exclude，说明部署目标包含 Vercel serverless。其三，`src/server/globalConfig/index.ts` 和 `src/envs/*` 表明大量能力由环境变量控制，包括登录、模型供应商、文件上传、Klavis、Langfuse、队列和 Agent Gateway。这里的判断都来自真实文件，而不是经验猜测。
