# 技术栈与运行环境

## 总体技术栈

根 `package.json` 明确项目名为 `@lobehub/lobehub`，版本为 `2.2.0`，workspace 包括 `packages/*`、`packages/business/*`、`.`、`e2e`、`apps/desktop/src/main`。结合依赖和源码入口，可以把技术栈分成五层：前端应用层、Next 服务端层、Agent/模型/工具运行层、数据库层、桌面与外部入口层。

前端应用层使用 React 19、TypeScript、React Router、Vite、`@lobehub/ui`、antd、`antd-style`、lucide-react、`@ant-design/icons`、react-i18next、zustand、SWR、React Query/tRPC client 等。证据包括 `package.json` 依赖、`src/spa/entry.web.tsx` 使用 `createRoot` 和 `RouterProvider`、`src/utils/router.tsx` 使用 `createBrowserRouter`、`src/layout/SPAGlobalProvider/index.tsx` 使用 `StyleProvider`、`ServerConfigStoreProvider`、`QueryProvider`、`AuthProvider`。页面路由本身不靠 Next 页面路由驱动，而是由 Vite 构建 SPA，React Router 在浏览器内接管。

Next 服务端层使用 Next.js 16 风格 App Router。`next.config.ts` 调用 `src/libs/next/config/define-config.ts` 生成配置，包含 `reactStrictMode`、静态资源缓存 header、redirect、server external packages、Turbopack 规则、standalone/Docker 输出等。`src/app/(backend)/` 下有 `/api`、`/trpc`、`/webapi`、`/oidc`、middleware 和 webhooks；`src/app/[variants]/(auth)` 保留认证页面；`src/app/spa/[variants]/[[...path]]/route.ts` 返回 SPA HTML 并注入配置。

Agent/模型/工具运行层主要在 `packages/` 和 `src/server/`。`packages/agent-runtime`、`packages/model-runtime`、`packages/model-bank`、`packages/context-engine`、`packages/builtin-tool-*`、`packages/builtin-tools` 组成底层能力；`src/server/services/aiAgent` 和 `src/server/services/agentRuntime` 把这些能力接入产品数据模型和请求流程。`src/server/services/queue` 支持本地 setTimeout 队列和 QStash 队列；`src/server/agent-hono/index.ts` 使用 Hono 组织 `/api/agent/*` 后台执行入口。

数据库层使用 PostgreSQL、Drizzle ORM、Drizzle Kit。`drizzle.config.ts` 指定 `dialect: 'postgresql'`、schema 为 `packages/database/src/schemas`、迁移输出为 `packages/database/migrations`。`packages/database/src/core/web-server.ts` 根据 `DATABASE_DRIVER` 选择 `drizzle-orm/node-postgres` 或 `drizzle-orm/neon-serverless`，并要求 `DATABASE_URL` 和 `KEY_VAULTS_SECRET`。测试环境下返回 mock DB，避免初始化真实数据库。

桌面与外部入口层包括 Electron、CLI 和 device gateway。`apps/desktop/package.json` 使用 `electron`、`electron-vite`、`electron-builder`，主进程位于 `apps/desktop/src/main/`，preload 位于 `apps/desktop/src/preload/`，覆盖窗口、菜单、托盘、本地文件、MCP、异构 Agent、远程服务器同步等控制器。`apps/cli/src/index.ts` 和 `apps/cli/src/program.ts` 是 CLI 入口。`apps/device-gateway/` 使用 wrangler 配置和 `DeviceGatewayDO.ts`，根据当前文件可判断它面向 Cloudflare Durable Object/Worker 形态。

## 包管理与构建信号

仓库使用 `pnpm` 管理 workspace，`pnpm-workspace.yaml` 包含 `packages/**`、`.`、`e2e`、`apps/desktop/src/main`。根脚本大量使用 `bun run`、`pnpm run`、`tsx`、`vite`、`next`，说明实际开发中 `bun` 常作为脚本启动器，`pnpm` 负责包解析和 workspace。`package.json` 中 `build` 是组合脚本：`build:spa`、`build:spa:copy`、`build:next`。`build:spa:raw` 会清理 `public/_spa` 并运行 `vite build`；`build:spa:copy` 调用 `scripts/copySpaBuild.mts` 和 `scripts/generateSpaTemplates.mts`；`build:next:raw` 调用 `next build`。这说明生产构建先产出 Vite SPA 静态资源和模板，再交给 Next 构建服务端。

开发态脚本也能反映架构：`dev:spa` 是 `vite --port 9876`，`dev:next` 是 `next dev -p 3010`，`dev` 调 `scripts/devStartupSequence.mts`。`vite.config.ts` 中开发模式会打印 Debug Proxy URL，把线上 `[URL已移除] 指向本地 Vite 服务器。这个设计说明前端开发可以在本地热更新，同时借用线上环境的后端配置。`dev:spa:mobile` 设置 `MOBILE=true` 并使用 3012 端口；`vite.config.ts` 读取 `MOBILE` 决定 `index.mobile.html` 与 `dist/mobile`。

测试与质量工具包括 Vitest、Playwright/e2e、ESLint、Stylelint、Remark、Knip、dpdm、tsgo。根脚本中 `type-check` 使用 `tsgo --noEmit`，`test-app` 使用 `vitest run`，`e2e` 进入 `e2e` 目录运行测试。仓库说明中强调不要随意运行完整 `bun run test`，因为耗时较长；读源码时更重要的是知道测试文件大量与源码同目录或 `__tests__` 中并存，例如 `src/server/routers/lambda/__tests__`、`packages/database/src/models/__tests__`。

## 读源码前需要知道的概念

第一，SPA 与 Next 的关系不是二选一。`src/spa/entry.web.tsx` 负责浏览器根挂载，`src/spa/router/desktopRouter.config.tsx` 负责前端路由声明；但实际 HTML 在生产或服务端场景由 `src/app/spa/[variants]/[[...path]]/route.ts` 返回。该 route 在开发时从 `[URL已移除] 拉取 Vite HTML 并重写资源 URL，在生产时导入生成的 `spaHtmlTemplates`，然后替换 `window.__SERVER_CONFIG__` 占位符和 SEO meta。也就是说：Next 提供 shell 和后端，Vite 提供前端资产，React Router 提供页面切换。

第二，数据请求通常经过客户端 service 层。以全局配置为例，`src/store/serverConfig/action.ts` 使用 `useOnlyFetchOnceSWR` 调 `globalService.getGlobalConfig()`；`src/services/global.ts` 中该方法调用 `lambdaClient.config.getGlobalConfig.query()`；`lambdaClient` 定义在 `src/libs/trpc/client/lambda.ts`，目标 URL 是 `/trpc/lambda`，并附带鉴权 header、错误处理、batch/split link 和 superjson。这个模式在许多 `src/services/*.ts` 中重复出现。

第三，tRPC router 与 service/database 分层明显。`src/app/(backend)/trpc/lambda/[trpc]/route.ts` 使用 `fetchRequestHandler`，`createLambdaContext` 从 request 中提取 API key、OIDC、cookies、trace、userAgent、clientIp 等上下文，`src/server/routers/lambda/index.ts` 聚合业务 router。具体 router 通常负责 zod 输入、鉴权 procedure、调用服务层和返回结果；服务层再实例化 database model 或其他模块。

第四，Agent 执行是异步、多步骤、可被队列驱动的。`AgentRuntimeService.createOperation` 会记录 operation、保存初始 state、注册 hook，并把第一步调度到 `/api/agent/run`。本地模式下 `LocalQueueServiceImpl` 用 `setTimeout` 触发 callback；队列模式下 `QStashQueueServiceImpl` 发布 HTTP 请求。`executeStep` 加锁、加载 state、创建 runtime、执行 `runtime.step()`、保存 step result、发布事件、记录 trace、决定是否继续调度下一步。

第五，环境变量被拆到多个 `src/envs/*.ts` 文件和 `src/config/*` 中。`src/server/globalConfig/index.ts` 是理解服务端配置如何暴露给客户端的关键文件，它会聚合 AI provider、认证、上传、视觉理解、市场、记忆、telemetry 和系统 Agent 配置。数据库初始化还依赖 `src/config/db` 提供的 `serverDBEnv`，具体文件可在继续阅读时打开。

## 依据

本页依据 `package.json`、`pnpm-workspace.yaml`、`tsconfig.json`、`vite.config.ts`、`next.config.ts`、`src/libs/next/config/define-config.ts`、`drizzle.config.ts`、`src/spa/entry.*.tsx`、`src/app/spa/[variants]/[[...path]]/route.ts`、`src/libs/trpc/client/lambda.ts`、`src/store/serverConfig/action.ts`、`src/services/global.ts`、`packages/database/src/core/web-server.ts`、`apps/desktop/package.json`、`apps/device-gateway/*` 整理。
