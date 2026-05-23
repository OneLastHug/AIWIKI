# 项目整体介绍

LobeHub 是一个围绕 AI Agent 工作空间展开的仓库。根据 `README.zh-CN.md`、根目录 `package.json` 和 `src/routes`、`src/server`、`packages/*` 的目录结构来看，它的目标不是只做一个聊天界面，而是把 Agent 的创建、调度、协作、记忆、工具调用和结果汇总放到同一个系统里。仓库同时覆盖 Web、桌面端和命令行三种形态，说明它面对的不是单一页面应用，而是一套可复用的 Agent 产品内核。

从功能切面上看，核心能力大致分成几类。第一类是对话与 Agent 运行：`src/routes/(main)/agent`、`src/server/routers/lambda/agent*.ts`、`src/server/services/agentRuntime/*`、`packages/agent-runtime` 共同承担了 Agent 对话、步骤执行、工具调用、结果回传和运行状态管理。第二类是页面与内容组织：`src/routes/(main)/page`、`src/features/Pages`、`src/features/PageEditor`、`src/features/PageExplorer` 这些目录表明项目把“页面”视作可编辑、可协作的内容单元，而不是普通静态路由。第三类是资源与能力扩展：`src/features/ResourceManager`、`src/features/PluginsUI`、`src/features/SkillStore`、`packages/builtin-tools`、`packages/model-bank` 说明系统支持模型、插件、技能和工具的组合。第四类是平台能力：`apps/desktop`、`apps/cli`、`src/business` 和 `packages/business/*` 表明仓库包含桌面壳、命令行客户端，以及一部分商业能力的覆写层。

从架构位置上看，`src/app/(backend)` 负责后端 API 和 tRPC/Hono 入口，`src/app/spa` 负责把 SPA HTML 模板和服务器配置注入到页面中，`src/spa` 负责真正的 React Router 启动，`src/layout` 负责全局 Provider 和主题/国际化/上传/路由桥接，`src/store` 负责状态，`src/services` 负责面向界面的客户端 API 封装，`packages/database` 负责表结构、模型与仓储。这个分工说明该项目采用的是“Next.js 外壳 + SPA 主体 + 服务端 API + 共享包”的混合模式。

对初学者来说，最合适的切入点不是从海量工具包里硬啃，而是先从一条最短主线理解系统：先看 `src/app/layout.tsx` 和 `src/layout/SPAGlobalProvider/index.tsx`，知道全局 Provider 怎么挂；再看 `src/app/spa/[variants]/[[...path]]/route.ts`，知道 SPA HTML 和服务器配置怎么生成；然后看 `src/spa/entry.web.tsx` 和 `src/utils/router.tsx`，知道前端路由怎么启动；最后看 `src/server/routers/lambda/index.ts`、`src/services/session/index.ts`、`src/store/session/store.ts` 和 `packages/database/src/models`，就能把“页面 -> 服务 -> 路由 -> 数据库”的主链串起来。后续如果想深入 Agent 能力，再看 `src/server/services/agentRuntime/AgentRuntimeService.ts` 和 `packages/agent-runtime` 会更顺。

仓库还有一个容易误判的点：它不是单纯的 Next.js App Router 项目。`src/app` 里确实有服务端路由，但用户真正看到的大部分业务界面来自 `src/routes` 里的 SPA 页面段，路由树由 `src/spa/router/*.tsx` 装配，`src/app/spa` 只是把 SPA 模板和运行时配置送进浏览器。这个判断来自 `src/spa/entry.web.tsx`、`src/spa/router/desktopRouter.config.tsx`、`src/app/spa/[variants]/[[...path]]/route.ts` 以及 `vite.config.ts` 中对 `public/_spa/` 的打包配置。
