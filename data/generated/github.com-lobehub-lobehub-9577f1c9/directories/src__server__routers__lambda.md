# 目录：src/server/routers/lambda

## 它负责什么

`src/server/routers/lambda` 是 LobeHub 后端 tRPC “lambda” 路由的主体目录。它把聊天、Agent、文件、知识库、模型配置、市场、生成任务、用户设置等同步 RPC 能力按业务域拆成多个 router，再由统一入口 `src/server/routers/lambda/index.ts` 聚合为 `lambdaRouter`。

从调用链看，它位于“客户端服务层”和“服务端业务/数据库层”之间：前端或内部服务通过 typed tRPC client 调用 `lambdaRouter` 下的 procedure；每个 procedure 负责输入校验、鉴权上下文、数据库连接注入和业务模型/服务调用。典型路径是：React UI 或 Store action → `src/services` / `src/libs/trpc/client/lambda.ts` → `src/app/(backend)/trpc/lambda/[trpc]/route.ts` → `lambdaRouter` → `src/server/services`、`src/database/models` 或业务覆盖 router。

这里的 “lambda” 不是单个云函数文件，而是一组面向在线应用主交互的 tRPC API。它区别于 `src/server/routers/async`、`mobile`、`tools` 等其他 router 分组：`lambda` 更像 Web/桌面端主要业务 API 的聚合层。

## 直接子目录地图

`src/server/routers/lambda/__tests__` 放置该目录内主要 router 的 Vitest 测试，覆盖 agent、aiAgent、message、file、topic、user、generation、video 等业务接口。其下还有 `integration`，用于更接近集成场景的测试。

`src/server/routers/lambda/_helpers` 是 lambda router 私有辅助逻辑目录，目前可见核心是上下文解析相关文件，例如 `resolveContext.ts`。根据当前片段推断，它服务于多个 router 对消息上下文、知识上下文或运行时上下文的共同解析需求，依据是该目录命名为私有 helper，且配有 `resolveContext.test.ts`。

`src/server/routers/lambda/_schema` 存放本目录复用的输入/数据 schema，例如 `context.ts`、`documentHistory.ts`。它用于避免把跨 procedure 的 zod/schema 定义散落在业务 router 内。

`src/server/routers/lambda/config` 是配置类 router 子目录，入口为 `config/index.ts`。它提供公共配置读取能力，如默认 Agent 配置、全局运行配置、服务端 feature flags，以及 cloud/business 侧注入的配置端点。

`src/server/routers/lambda/image` 是图片生成/图片能力 router 子目录，入口为 `image/index.ts`，旁边有 `utils.ts` 和对应测试。它把图片相关的 procedure 与工具函数从根目录拆出，避免根部文件继续膨胀。

`src/server/routers/lambda/market` 是市场/发现页相关 API 的子树，入口为 `market/index.ts`，并继续拆分 `agent.ts`、`agentGroup.ts`、`creds.ts`、`oidc.ts`、`skill.ts`、`social.ts`、`socialProfile.ts`、`user.ts`。这说明 market 域本身已经足够复杂，既有公开发现接口，也有需要登录或市场身份的管理接口。

`src/server/routers/lambda/video` 是视频生成相关 router 子目录，入口为 `video/index.ts`，另有 `error.ts` 和测试。它承载视频任务、额度、错误归一化等相关能力。

除这些子目录外，根部还有大量按业务域命名的 router 文件，例如 `agent.ts`、`aiAgent.ts`、`message.ts`、`session.ts`、`topic.ts`、`file.ts`、`knowledgeBase.ts`、`generation.ts`、`user.ts` 等。这些不是“叶子小工具”，而是主要业务域 API 的分组入口。

## 关键入口

最核心入口是 `src/server/routers/lambda/index.ts`。它导入各业务 router，并通过 `router({ ... })` 组装出 `lambdaRouter`，最后导出 `LambdaRouter` 类型。客户端类型安全调用依赖这个类型，服务端 tRPC handler 也挂载这个对象。

HTTP 暴露入口在 `src/app/(backend)/trpc/lambda/[trpc]/route.ts`。该文件使用 `fetchRequestHandler`，设置 `endpoint: '/trpc/lambda'`，通过 `createLambdaContext(req)` 创建上下文，并把 `lambdaRouter` 交给 tRPC 处理 GET/POST 请求。这里还会调用 `prepareRequestForTRPC(req)` 适配 Next.js 16 的 request body 行为，并使用 `createResponseMeta` 统一响应元信息。

tRPC 基础设施入口在 `src/libs/trpc/lambda/index.ts`。这里定义 `router`、`publicProcedure`、`authedProcedure`、`heteroAuthedProcedure` 和 `createCallerFactory`。多数业务 router 都从这里取 `authedProcedure` 和 `router`，形成一致的鉴权、OpenTelemetry 与 procedure 构造方式。

数据库上下文注入入口在 `src/libs/trpc/lambda/middleware/serverDatabase.ts`。`serverDatabase` middleware 调用 `getServerDB()` 后把 `serverDB` 注入 `ctx`。业务 router 通常继续在本文件内定义如 `agentProcedure`、`sessionProcedure` 这样的领域 procedure，把 `AgentModel`、`SessionModel`、服务类等挂到 `ctx` 上。

## 主流程位置

请求主流程从 `src/app/(backend)/trpc/lambda/[trpc]/route.ts` 开始。请求进入 Next.js route handler 后，被转换为 tRPC 可处理的 request，随后创建 lambda context，再按 URL 中的 tRPC path 分派到 `lambdaRouter` 的对应命名空间。例如 `agent.createAgent` 会进入 `src/server/routers/lambda/agent.ts` 的 `agentRouter`，`market.getAssistantCategories` 会进入 `src/server/routers/lambda/market/index.ts` 的 `marketRouter`。

router 内部的主流程通常是：先用 `zod` 定义 `.input(...)`，再通过 `query` 或 `mutation` 执行业务；如果需要登录，用 `authedProcedure`；如果需要数据库，用 `.use(serverDatabase)`；如果同一个 router 有多处需要模型，就在领域 procedure middleware 中一次性构造并注入 `ctx`。例如 `agent.ts` 创建 `agentProcedure`，在上下文中放入 `agentModel`、`agentService`、`sessionModel`、`fileModel` 等，然后各 procedure 直接调用 `ctx.agentModel` 或 `ctx.agentService`。

公共接口也存在，但占比更小。`config/index.ts` 使用 `publicProcedure` 提供全局配置；`session.ts` 中 `getGroupedSessions` 是 public procedure，但内部会检查 `ctx.userId`，没有用户时返回空列表；`share.ts`、`message.ts`、`plugin.ts`、`market` 下部分接口也有公开读取场景。常见模式不是“文件是否在 lambda 就必然需要登录”，而是按 procedure 选择 `publicProcedure` 或 `authedProcedure`。

还有一条内部调用流程：`createCallerFactory(lambdaRouter)` 可在服务端直接构造 caller，不经过 HTTP。例如 `src/libs/trpc/mock.ts` 和某些 webapi route 会这样复用 lambda router 能力。这意味着本目录既服务外部 tRPC 请求，也可能被服务端内部逻辑当作类型安全的应用 API 层调用。

## 推荐阅读顺序

1. 先读 `src/server/routers/lambda/index.ts`，建立完整命名空间地图。重点看聚合出的键名，例如 `agent`、`message`、`market`、`config`、`generation`，这些就是客户端调用时的第一层路径。

2. 再读 `src/app/(backend)/trpc/lambda/[trpc]/route.ts`，理解 `lambdaRouter` 如何被 Next.js 暴露为 `/trpc/lambda` tRPC endpoint，以及错误处理、context 创建、response meta 的位置。

3. 接着读 `src/libs/trpc/lambda/index.ts` 和 `src/libs/trpc/lambda/middleware/serverDatabase.ts`，掌握 `publicProcedure`、`authedProcedure`、`heteroAuthedProcedure`、`serverDatabase` 的职责。读懂这里后，大多数 router 文件的结构会变得很直观。

4. 选择一个典型业务 router 阅读，比如 `src/server/routers/lambda/agent.ts`。它展示了“领域 procedure middleware 注入多个 model/service，再在 query/mutation 中调用”的主流写法。

5. 再读一个兼容/遗留 router，例如 `src/server/routers/lambda/session.ts`。文件注释表明 session router 有 deprecated 部分，推荐迁移到 agent router。它有助于理解新旧业务模型并存的状态。

6. 最后读大子域入口，如 `src/server/routers/lambda/market/index.ts`、`src/server/routers/lambda/image/index.ts`、`src/server/routers/lambda/video/index.ts`。这些目录展示了当单一业务域变复杂后，如何从根部单文件拆成子 router 组合。

## 常见误区

不要把 `src/server/routers/lambda/index.ts` 理解成“业务实现文件”。它主要是聚合层，业务实现分散在同目录各领域 router，以及更下游的 `src/server/services`、`src/database/models`、`src/business/server/lambda-routers` 中。

不要以为所有 lambda procedure 都是公开接口。多数写法是 `authedProcedure.use(serverDatabase)`，会经过 OIDC/userAuth，并注入数据库。只有配置、分享、市场发现、部分列表读取等场景会使用 `publicProcedure`，而 public procedure 内部也可能根据 `ctx.userId` 分支处理。

不要在阅读时只看 router 文件名判断数据来源。很多 procedure 实际调用的是 model 或 service，例如 Agent 相关逻辑会落到 `AgentModel`、`AgentService`，market 相关逻辑会落到 `DiscoverService`、`MarketService`。router 层的职责更偏 API 编排、输入校验和上下文装配。

不要忽略 business 覆盖入口。`lambda/index.ts` 直接引入了 `@/business/server/lambda-routers/accountDeletion`、`referral`、`spend`、`subscription`、`taskTemplate`、`topUp` 等 cloud/business router。根据当前片段推断，这些是云版本或商业功能对开源核心的扩展，依据是导入路径位于 `@/business`，且 AGENTS 说明存在 cloud override 机制。

不要把 `session.ts` 当作新功能首选入口。它的注释明确标出部分 session-based agent 创建接口已 deprecated，新 Agent CRUD 应优先看 `agent.ts`。阅读会话列表或兼容移动端时仍需要它，但新增 Agent 相关能力应先确认是否属于 `agentRouter`。

不要把 `_helpers`、`_schema` 当作公共 SDK。它们位于 lambda 目录内部，命名也带下划线，主要服务本目录 router 复用。跨层复用时应先看是否已有 `src/server/services`、`src/types`、`src/database` 等更合适的位置。
