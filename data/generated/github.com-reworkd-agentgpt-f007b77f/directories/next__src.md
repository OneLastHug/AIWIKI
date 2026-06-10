# 目录：next/src

## 它负责什么

`next/src` 是这个仓库里 Next.js 应用的主要源码目录，承担前端页面、客户端 Agent 运行编排、用户会话、tRPC BFF、状态管理、UI 组件和类型定义等职责。它不是纯展示层：页面会直接组装 `AutonomousAgent`、`AgentApi`、`MessageService`、`DefaultAgentRunModel` 等对象，在浏览器侧驱动 Agent 的生命周期；同时 `server/api` 和 `pages/api` 又提供 Next.js API Route、NextAuth、tRPC 入口，用于用户登录、Agent 记录持久化和数据库访问。

整体上可以把它理解为三层：第一层是 `pages`、`layout`、`components`、`ui` 构成的页面与交互；第二层是 `hooks`、`stores`、`services/agent` 构成的客户端业务状态和 Agent 执行流程；第三层是 `server`、`pages/api`、`utils/api.ts` 构成的服务端入口和类型安全 RPC 通道。

## 直接子目录地图

`components` 是复用组件区，既有通用组件如 `Button.tsx`、`Input.tsx`、`NavBar.tsx`，也有按场景拆分的组件目录。`components/index` 对应首页的 Landing 和 Chat 主视图；`components/console` 放聊天窗口、消息渲染、Agent 控制、来源卡片等运行台组件；`components/drawer` 和 `components/sidebar` 负责左右侧栏；`components/landing` 是落地页展示模块；`components/dialog` 是帮助、登录、工具弹窗；`components/templates` 是模板页组件；`components/pdf` 负责报告导出相关 UI；`components/motions` 是动画包装组件。

`env` 管理环境变量校验，包含客户端、服务端和 schema。`hooks` 封装前端业务 Hook，例如认证、模型、工具、Agent tRPC 操作和设置读取。`layout` 放页面布局，核心是 `dashboard.tsx`、`default.tsx`、`grid.tsx`。`lib` 当前主要承载博客文章读取工具。`pages` 是 Next.js Pages Router 的路由根，包含页面路由和 API 路由。`server` 是服务端内部代码，包含 tRPC router、auth 配置和 Prisma 客户端。`services` 是业务服务层，其中 `services/agent` 最关键，定义 Agent 的运行模型、任务工作流、API 调用和消息服务。`stores` 是 Zustand 状态切片，管理 Agent、消息、任务、配置、输入和模型设置。`styles` 放全局 CSS。`types` 放跨层类型定义。`ui` 是更底层的基础 UI 控件。`utils` 是 API client、常量、i18n、语言、用户、空白字符判断等工具集合。

## 关键入口

应用全局入口是 `pages/_app.tsx`。它包裹 `SessionProvider`、Google/Vercel analytics、`next-i18next`，最后通过 `api.withTRPC(appWithTranslation(...))` 注入 tRPC 和国际化能力。读前端初始化时应先看这里，因为全局 provider 和样式 `styles/globals.css` 都从这里进入。

主页面入口是 `pages/index.tsx`。这是 AgentGPT 的核心交互页：它读取 `useAuth`、`useSettings`、多个 Zustand store，决定显示 `components/index/landing.tsx` 还是 `components/index/chat.tsx`，并在用户启动目标时创建 `DefaultAgentRunModel`、`MessageService`、`AgentApi`、`AutonomousAgent`。这个文件是理解“用户输入目标后系统如何开始运行”的第一入口。

服务端 RPC 入口是 `pages/api/trpc/[trpc].ts`、`server/api/root.ts`、`server/api/trpc.ts`。`root.ts` 当前把 `agentRouter` 挂到 `appRouter.agent`，`utils/api.ts` 在客户端创建 tRPC React client。Agent 数据的创建、保存、查询、删除集中在 `server/api/routers/agentRouter.ts`。

认证入口是 `pages/api/auth/[...nextauth].ts`，具体配置在 `server/auth/auth.ts` 和 `server/auth/local-auth.ts`。数据库入口是 `server/db.ts`，通过 PrismaClient 暴露 `prisma`。

## 主流程位置

核心主流程从 `pages/index.tsx` 的 `handlePlay`、`handleNewAgent` 开始。用户输入 goal 后，如果未登录，会把目标暂存到 localStorage 并打开 `SignInDialog`；如果已经登录，会构造 Agent 运行所需对象，然后调用 `newAgent.run()`。

`services/agent/autonomous-agent.ts` 是 Agent 客户端编排核心。它维护 `workLog`，初始放入 `StartGoalWork`，运行时按顺序执行 `AgentWork.run()`、`conclude()`、`next()`，并在任务队列为空时根据当前任务补入 `AnalyzeTaskWork`。暂停、恢复、停止、总结、聊天也都在这个类中统一控制。

具体工作单元在 `services/agent/agent-work`。根据当前片段推断，`start-task-work.ts` 负责根据目标生成初始任务，`analyze-task-work.ts` 分析当前任务，`execute-task-work.ts` 执行任务，`create-task-work.ts` 创建后续任务，`summarize-work.ts` 总结结果，`chat-work.ts` 处理用户与运行中 Agent 的对话。依据是这些类均实现或引用 `AgentWork`，并由 `AutonomousAgent` 按 `next()` 串接。

Agent 与后端交互集中在 `services/agent/agent-api.ts`。它会请求 `/api/agent/start`、`/api/agent/create`、`/api/agent/analyze` 等接口；但在当前 `next/src/pages/api` 片段中只看到 `auth` 和 `trpc` 路由，未看到这些 `agent` API Route。因此根据当前片段推断，这些接口可能由仓库其他目录、部署 rewrite、或独立后端服务提供，不应误以为都定义在 `next/src` 内。

持久化主流程是 `hooks/useAgent.ts` 调用 `api.agent.create`、`api.agent.save`，进入 `server/api/routers/agentRouter.ts`，再通过 `ctx.prisma` 或 `prisma` 写入 `agent`、`agentTask`。其中 `create` 会尝试用 OpenAI 根据 goal 生成 Agent 名称，失败则回退到原始 goal。

## 推荐阅读顺序

1. 先读 `pages/_app.tsx`、`utils/api.ts`，了解全局 provider、tRPC client 和国际化包装。
2. 再读 `pages/index.tsx`，抓住首页如何在 Landing、Chat、登录弹窗和 Agent 启动之间切换。
3. 接着读 `services/agent/autonomous-agent.ts`、`services/agent/agent-work/agent-work.ts`，理解 Agent 的执行循环和工作单元接口。
4. 然后按流程读 `services/agent/agent-work/start-task-work.ts`、`analyze-task-work.ts`、`execute-task-work.ts`、`create-task-work.ts`、`summarize-work.ts`，不要一开始陷入所有组件细节。
5. 读 `stores/agentStore.ts`、`stores/messageStore.ts`、`stores/taskStore.ts`、`stores/configStore.ts`，理解 UI 如何响应 Agent 生命周期、消息和任务变化。
6. 最后读 `server/api/root.ts`、`server/api/trpc.ts`、`server/api/routers/agentRouter.ts`、`server/auth/*`、`server/db.ts`，补齐服务端持久化和认证链路。

## 常见误区

不要把 `components` 当成全部业务逻辑所在地。这里的组件很多，但真正的 Agent 运行编排在 `services/agent`，页面只是把服务、状态和组件连接起来。

不要把 `server/api` 理解成所有 HTTP API。`server/api` 主要是 tRPC router；传统 Next API Route 在 `pages/api`。而 `AgentApi` 中请求的 `/api/agent/*` 在当前 `next/src` 片段里没有对应文件，需要结合仓库其他目录或部署配置继续确认。

不要误认为 `pages/index.tsx` 只是首页展示。它同时负责创建 Agent、处理登录前目标暂存、恢复暂停 Agent、重置状态和触发运行，是主业务入口。

不要混淆 `components` 和 `ui`。`ui` 更像底层控件库，`components` 是按业务场景组合后的组件；改样式或交互时应先判断改动属于基础控件还是业务组件。

不要忽略 `stores`。聊天窗口、任务侧栏、Agent 生命周期、布局开关等都依赖 Zustand 状态；只看 React props 会漏掉很多跨组件状态流。

不要把 `server/auth/auth.ts` 与 `server/auth/local-auth.ts` 简单视为重复文件。它们都涉及 NextAuth 配置，但适用场景可能不同；根据当前片段只能确认 `pages/api/auth/[...nextauth].ts` 引用了 `server/auth/auth.ts`。
