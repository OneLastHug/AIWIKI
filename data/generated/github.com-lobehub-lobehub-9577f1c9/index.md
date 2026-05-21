# LobeHub 仓库学习索引

这组文档面向第一次阅读 `lobehub/lobehub` 仓库的中文读者。建议不要从单个业务页面直接跳进去，而是先理解“Next.js 后端 + Vite SPA 前端 + workspace packages + Electron/CLI 辅助应用”的整体形状，再按数据流追一个功能。本文档只基于仓库中的 README、`package.json`、构建配置、入口文件和源码结构整理；涉及执行机制的判断会在对应页面标注依据或“根据当前文件推断”。

## 推荐阅读顺序

1. [00-overview.md](./00-overview.md) - 先了解项目解决的问题、核心能力、主要模块和初学者切入点。
2. [01-tech-stack.md](./01-tech-stack.md) - 再看技术栈、运行环境、构建脚本、包管理和读源码前的概念。
3. [02-architecture.md](./02-architecture.md) - 接着理解目录分层、模块边界、依赖方向和常见扩展点。
4. [03-runtime-flow.md](./03-runtime-flow.md) - 最后按启动、配置加载、请求、Agent 任务与数据库链路串起来。
5. [critical_paths.json](./critical_paths.json) - 用机器可读格式列出最值得优先阅读的目录和文件。

## 后续最值得看的目录/文件

- `README.md` / `README.zh-CN.md`：确认产品定位、功能范围、自托管和本地开发入口。
- `package.json`：确认 workspace、脚本、依赖版本和构建方式，尤其是 `dev`、`dev:spa`、`build`、`build:spa`、`build:next`、`db:*`。
- `vite.config.ts`：理解 SPA 构建、移动端开关、PWA、Debug Proxy 和 Vite 入口。
- `next.config.ts` 与 `src/libs/next/config/define-config.ts`：理解 Next 服务端配置、静态资源缓存、redirect、standalone/Docker 行为。
- `src/spa/entry.web.tsx`、`src/spa/entry.mobile.tsx`、`src/spa/router/*.tsx`：理解 React Router SPA 如何挂载。
- `src/app/spa/[variants]/[[...path]]/route.ts`：理解 Next 如何提供 SPA HTML 模板并注入 `window.__SERVER_CONFIG__`。
- `src/layout/SPAGlobalProvider/index.tsx`、`src/layout/GlobalProvider/StoreInitialization.tsx`：理解全局 Provider、主题、认证、SWR、store 初始化。
- `src/services/` 与 `src/libs/trpc/client/`：理解客户端服务层如何调用 tRPC。
- `src/app/(backend)/trpc/lambda/[trpc]/route.ts`、`src/server/routers/lambda/index.ts`：理解主要 API 入口和 router 聚合。
- `src/server/services/` 与 `packages/database/src/`：理解服务层、数据库模型、schema、repository 的边界。
- `src/server/services/aiAgent/index.ts`、`src/server/services/agentRuntime/AgentRuntimeService.ts`、`src/server/agent-hono/index.ts`：理解 Agent 执行、队列、步骤调度、工具调用和异步入口。
- `apps/desktop/src/main/`、`apps/desktop/src/preload/`、`src/services/electron/`：理解 Electron 主进程、preload 与 Web SPA 的桥接。
