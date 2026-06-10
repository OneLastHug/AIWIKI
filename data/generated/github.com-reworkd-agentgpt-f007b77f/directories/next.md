# 目录：next

## 它负责什么

`next` 是 AgentGPT 项目的 Next.js 前端应用目录，也是用户实际操作“创建、运行、查看、保存 Agent”的主要界面层。它不是单纯静态站点，而是一个包含页面路由、会话认证、tRPC API、Prisma 数据访问、Agent 运行状态管理、国际化、静态资源和测试配置的完整 Web 应用。

从 `package.json` 看，这里使用 Next.js 13、React 18、NextAuth、tRPC、Prisma、Zustand、Tailwind CSS、OpenAI SDK、next-i18next 等技术。`scripts` 中的 `dev`、`build`、`start`、`test` 都围绕这个目录运行，`postinstall` 会执行 `prisma generate`，说明数据库类型生成也是此应用启动链路的一部分。

需要注意的是，`next` 内部的 Agent 执行逻辑分成两段：前端本地编排在 `src/services/agent`，数据库持久化和用户会话相关接口在 `src/server` 与 `src/pages/api`；但 `AgentApi` 调用的 `/api/agent/start`、`/api/agent/create`、`/api/agent/analyze` 在当前 `next` 目录片段中没有对应 `pages/api/agent/*` 文件。根据当前片段推断，这些端点可能由项目其他服务、部署平台重写规则，或历史代码中的外部 API 提供。

## 直接子目录地图

`src` 是主源码目录，包含页面、组件、服务、状态、类型、工具函数和服务端 API。读这个目录就能理解应用主体。

`src/pages` 是 Next.js Pages Router 路由入口。首页、登录页、设置页、模板页、博客页、Agent 查看页，以及 `api` 路由都在这里。

`src/components` 是 UI 组件集合，既有通用组件如 `Button`、`Input`、`Tooltip`，也有业务分区如 `console`、`dialog`、`drawer`、`index`、`landing`、`templates`、`pdf`。

`src/services` 是业务服务层。最关键的是 `src/services/agent`，其中 `AutonomousAgent`、`AgentApi`、`AgentRunModel` 和 `agent-work` 子目录共同组成 Agent 运行编排。

`src/server` 是服务端能力，包含 tRPC 路由、认证封装和 Prisma 数据库连接。核心路径是 `src/server/api/root.ts`、`src/server/api/routers/agentRouter.ts`、`src/server/auth`、`src/server/db.ts`。

`src/stores` 是 Zustand 状态层，保存 Agent 生命周期、消息、任务、配置和模型设置等前端状态。

`src/hooks` 封装页面使用的业务 Hook，例如 `useAgent`、`useAuth`、`useSettings`、`useTools`、`useModels`。

`src/layout` 放页面布局，`dashboard.tsx` 是主操作界面的外层布局。

`src/styles` 是全局样式入口，`src/types` 是消息、任务、错误、模型设置、NextAuth 扩展等类型定义，`src/utils` 是 tRPC 客户端、接口转换、语言配置和通用工具。

`prisma` 保存数据库 schema 与数据库切换脚本，关键文件是 `prisma/schema.prisma`。

`public` 保存浏览器可直接访问的资源，包括图标、logo、字体、本地化文件、工具资源和站点 manifest。

`posts` 保存 MDX 博客内容，配合 `src/lib/posts.ts` 和 `src/pages/blog*` 使用。

`__tests__` 和 `__mocks__` 是 Jest 测试与浏览器能力 mock。根部的 `next.config.mjs`、`tailwind.config.cjs`、`next-i18next.config.js`、`jest.config.cjs`、`Dockerfile`、`entrypoint.sh`、`wait-for-db.sh` 是构建、样式、国际化、测试和容器启动配置。

## 关键入口

应用全局入口是 `src/pages/_app.tsx`。它挂载 `SessionProvider`、Google Analytics、Vercel Analytics、next-i18next，并用 `api.withTRPC(...)` 包住整个应用，所以认证、国际化和 tRPC 客户端都从这里进入。

用户主操作入口是 `src/pages/index.tsx`。这里渲染 `DashboardLayout`，根据是否已有 Agent 切换 `Landing` 与 `Chat`，并在用户点击运行时创建 `DefaultAgentRunModel`、`MessageService`、`AgentApi`、`AutonomousAgent`，随后调用 `newAgent.run()`。

历史 Agent 查看入口是 `src/pages/agent/index.tsx`。它通过路由参数读取 `id`，调用 `api.agent.findById.useQuery` 获取 Agent 与任务消息，并提供删除、分享、返回等操作。

服务端 API 入口是 `src/pages/api/trpc/[trpc].ts`，它把 Next API Route 接到 `appRouter`。`appRouter` 定义在 `src/server/api/root.ts`，当前只挂载了 `agentRouter`。

认证 API 入口是 `src/pages/api/auth/[...nextauth].ts`，具体认证配置位于 `src/server/auth`。

## 主流程位置

创建并运行 Agent 的主流程从 `src/pages/index.tsx` 的 `handlePlay`、`handleNewAgent` 开始。未登录用户会把目标暂存到 `localStorage` 并打开登录弹窗；已登录用户会创建模型、消息服务、API 包装器和 `AutonomousAgent` 实例，然后将其写入 `useAgentStore` 并执行 `run()`。

运行编排核心在 `src/services/agent/autonomous-agent.ts`。`AutonomousAgent` 内部维护 `workLog`，初始放入 `StartGoalWork`；每轮取出一个 `AgentWork` 执行 `run()`，再执行 `conclude()`，然后通过 `next()` 推入后续工作。没有工作项时，会检查当前任务并追加 `AnalyzeTaskWork`。暂停、停止、总结、用户聊天也都在这个类里统一处理。

具体工作单元位于 `src/services/agent/agent-work`。从文件名可以看出主要阶段包括 `start-task-work.ts`、`analyze-task-work.ts`、`execute-task-work.ts`、`create-task-work.ts`、`summarize-work.ts`、`chat-work.ts`。这些文件是理解 Agent 如何拆任务、分析任务、执行任务、追加任务和总结结果的关键位置。

前端调用后端模型接口的位置是 `src/services/agent/agent-api.ts`。它负责创建 Agent 记录、保存消息，并向 `/api/agent/start`、`/api/agent/create`、`/api/agent/analyze` 发送请求。根据当前片段推断，这些端点不在 `next/src/pages/api` 下，读源码时不要误以为所有 Agent 智能能力都在 tRPC 里。

Agent 持久化主流程在 `src/server/api/routers/agentRouter.ts`。它提供 `create`、`save`、`getAll`、`findById`、`deleteById`。其中 `create` 会尝试用 OpenAI 根据目标生成 Agent 名称，`save` 会把消息保存成 `agentTask`，`findById` 会连同 tasks 按创建时间取出。

## 推荐阅读顺序

第一步读 `next/package.json`，确认这是一个 Next.js、tRPC、Prisma、NextAuth、Zustand 组合的应用。

第二步读 `src/pages/_app.tsx`，理解全局 Provider、国际化和 tRPC 客户端如何挂载。

第三步读 `src/pages/index.tsx`，这是用户从输入目标到启动 Agent 的最短主线。

第四步读 `src/services/agent/autonomous-agent.ts` 和 `src/services/agent/agent-work`，理解 Agent 的本地编排模型。

第五步读 `src/services/agent/agent-api.ts`，看前端编排如何调用后端能力与保存数据。

第六步读 `src/server/api/root.ts`、`src/server/api/routers/agentRouter.ts`、`src/pages/api/trpc/[trpc].ts`，理解 tRPC 持久化接口。

第七步再回到 `src/components/index`、`src/components/console`、`src/components/drawer` 和 `src/stores`，把 UI 展示与状态变化串起来。

## 常见误区

不要把 `src/pages/agent/index.tsx` 理解成运行 Agent 的入口。它主要是查看已保存 Agent 的详情页，真正启动 Agent 的入口是 `src/pages/index.tsx`。

不要把 `agentRouter` 当成全部智能执行后端。`agentRouter` 主要负责创建、保存、查询、删除 Agent 记录；任务拆解、分析、执行相关请求由 `AgentApi` 发往 `/api/agent/*`，而这些端点在当前 `next` 目录中没有实现文件。

不要忽略 Zustand stores。Agent 生命周期、消息、任务、设置并不完全来自服务端，很多运行时状态保存在 `src/stores`，所以只读 API 路由会看不完整。

不要把 `components/landing` 和 `components/index/landing.tsx` 混为一类。前者更偏营销/介绍页组件，后者参与首页 Agent 输入与启动体验。

不要认为 `public/locales` 只是静态资源。它和 `next-i18next.config.js`、`src/pages/_app.tsx`、各页面的 `serverSideTranslations` 共同构成国际化流程。

不要跳过 `prisma/schema.prisma`。即使当前目标是前端目录，Agent、用户、任务等核心数据结构仍由 Prisma schema 决定，理解持久化字段时必须回到这里核对。
