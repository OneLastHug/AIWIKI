# 架构分层与模块边界

## 顶层结构

仓库顶层可以按“应用入口、共享包、服务端、前端业务、数据库、部署与工具”理解。`src/` 是主应用代码；`packages/` 是 workspace 共享包；`apps/` 放桌面、CLI、device gateway 等附加应用；`docs/`、`locales/`、`public/`、`scripts/`、`tests/`、`e2e/` 分别对应文档、本地化、静态资源、工程脚本、测试工具和端到端测试。`pnpm-workspace.yaml` 把根项目、`packages/**`、`e2e`、`apps/desktop/src/main` 纳入 workspace，说明这些目录之间可以通过 `workspace:*` 依赖协同开发。

`src/app/` 属于 Next App Router。它不是主要 SPA 页面目录，而是承载服务端 API、认证页面、站点元信息、manifest、robots、sitemap 和 SPA HTML 模板。`src/app/(backend)/trpc/lambda/[trpc]/route.ts` 是主要 tRPC lambda 入口；`src/app/(backend)/api/agent/[[...route]]/route.ts` 把请求交给 `src/server/agent-hono`；`src/app/spa/[variants]/[[...path]]/route.ts` 返回 SPA HTML。`src/app/[variants]/(auth)` 则是 SSR/Next 页面形态的认证相关页面。

`src/spa/` 是 SPA 的浏览器入口与路由配置。`entry.web.tsx`、`entry.mobile.tsx`、`entry.desktop.tsx`、`entry.popup.tsx` 都调用 `createAppRouter` 并渲染 `RouterProvider`。`router/desktopRouter.config.tsx`、`desktopRouter.config.desktop.tsx`、`mobileRouter.config.tsx`、`popupRouter.config.tsx` 声明不同平台的 React Router route tree。桌面路由中大量使用 `dynamicElement` 和 `dynamicLayout`，说明页面按路由懒加载。`desktopRouter.sync.test.tsx` 也表明普通 desktop config 与 desktop build config 必须保持结构同步。

`src/routes/` 是页面段目录，按路由根分组。仓库约定中要求 `src/routes/` 保持薄层：只做 route segment、layout/page 组合，业务组件和复杂逻辑放到 `src/features/`。真实路由配置也印证了这一点：`desktopRouter.config.tsx` 中的 import 指向 `@/routes/(main)/agent`、`@/routes/(main)/settings`、`@/routes/(mobile)/chat` 等页面段，同时 route meta 和 UI 能力来自 `@/features/*`。

`src/features/` 是业务 UI 和领域组件的主要位置。目录包含 `AgentBuilder`、`AgentTasks`、`Conversation`、`PageEditor`、`Pages`、`SkillStore`、`ModelSelect`、`Messenger`、`ResourceManager`、`Setting` 等。`src/components/` 则更偏通用组件和基础 UI 拼装，如错误、Loading、菜单、复制标签、文件图标、Markdown、插件展示、统计等。边界可以粗略理解为：`components` 可复用粒度更小，`features` 贴近业务域，`routes` 负责页面挂载。

## 前端状态与数据边界

`src/store/` 使用 zustand 按业务域拆分：`agent`、`agentGroup`、`chat`、`session`、`topic`、`task`、`file`、`user`、`serverConfig`、`tool`、`image`、`page`、`document` 等。每个 store 下常见 `slices`、`selectors`、`reducers`、`utils`。`src/layout/GlobalProvider/StoreInitialization.tsx` 是跨 store 初始化入口，会触发系统状态、服务端配置、用户状态和内置 Agent 初始化。`src/store/serverConfig/action.ts` 展示了常见模式：store action 使用 SWR hook 调 service，成功后写入 store。

`src/services/` 是客户端服务层，通常面向 store 或 feature 暴露方法。这里有 `agent.ts`、`aiAgent.ts`、`aiChat.ts`、`file/index.ts`、`global.ts`、`knowledgeBase.ts`、`message/index.ts`、`task.ts`、`topic/index.ts`、`user/index.ts`、`generation.ts` 等。它们不应直接承载 UI 状态，而是封装 HTTP/tRPC、上传、导入导出、Electron bridge 等调用。`src/libs/trpc/client/lambda.ts` 是最核心的 tRPC client，负责 `/trpc/lambda`、鉴权 header、401 处理、batch 策略和 superjson。

## 后端边界

`src/server/routers/` 是 API router 层，分为 `lambda`、`async`、`mobile`、`tools`。`lambda/index.ts` 聚合绝大多数业务 API；`async` 和 workflow/queue 相关；`tools` 面向工具市场、MCP、搜索等；`mobile` 有移动端专用 router。router 层通常引入 `publicProcedure`、`authedProcedure` 或业务中间件，使用 zod schema 校验输入，然后调用 service。

`src/server/services/` 是业务服务层，负责把请求语义变成领域操作。这里的服务会组合 database model、server module、外部 SDK、队列、S3、Agent Runtime、邮件、gateway、market 等能力。例如 `AiAgentService` 读取 Agent 配置、构造执行上下文并调用 `AgentRuntimeService`；`AgentRuntimeService` 负责 operation state、stream event、hook、tool execution、queue 调度；`FileService`、`KnowledgeBaseService`、`MessageService` 等则围绕各自领域组织持久化和业务规则。

`src/server/modules/` 是更底层的服务端模块，文件结构显示有 `AgentRuntime`、`ModelRuntime`、`Mecha`、`S3`、`KeyVaultsEncrypt`、`PluginStore`、`AgentTracing` 等。根据当前引用关系推断，modules 更接近可复用基础设施，services 更接近产品业务用例。例如 `AgentRuntimeService` 会调用 `src/server/modules/AgentRuntime` 中的 `AgentRuntimeCoordinator` 和 stream event manager。

`packages/database/` 是数据库边界。`packages/database/src/schemas/` 定义表和关系，`models/` 按业务对象封装读写，`repositories/` 封装跨模型或复杂查询场景，`core/` 负责 Drizzle DB 实例。`src/database/*` 通过 tsconfig path 指向 `packages/database/src/*`，所以应用层可以用 `@/database/models/...` 引入数据库 model。这个别名让主应用看起来像在 `src/database` 下，但真实源文件在 package 中。

## 关键依赖方向

从常见调用链看，依赖方向大致是：`src/routes`/`src/features` 调 `src/store` 或 `src/services`；`src/store` 通过 service 和 SWR/tRPC 获取数据；`src/services` 调 `src/libs/trpc/client` 或 Electron bridge；Next route handler 调 `src/server/routers`；router 调 `src/server/services`；service 调 `src/server/modules`、`packages/*`、`packages/database/src/models`；database model 调 Drizzle schema 和 DB 实例。这个方向有助于避免初学者在 UI 层直接改数据库或在 database 包里引入 React UI。

另一个重要边界是 platform-specific。Web/mobile/desktop/popup 的 SPA 入口不同，Electron 主进程和 preload 在 `apps/desktop/src/`，而 Web UI 仍在根 `src/`。`src/services/electron/` 是 renderer 侧调用桌面能力的桥，`apps/desktop/src/main/controllers/` 是主进程实现。根据当前文件推断，桌面端通过 IPC/bridge 把本地文件、系统、MCP、远程服务器、异构 Agent 等能力暴露给 SPA。

## 扩展点

新增页面时优先看 `src/spa/router/*.tsx`、`src/routes/`、`src/features/` 的分工；新增 API 时看 `src/server/routers/lambda` 和 `src/server/services`；新增数据库字段或表时看 `packages/database/src/schemas`、`models`、`drizzle.config.ts` 和 migrations；新增内置工具时看 `packages/builtin-tool-*`、`packages/builtin-tools/src` 和 `src/store/tool`、`src/server/services/toolExecution`；新增模型/provider 时看 `packages/model-bank`、`packages/model-runtime`、`src/server/globalConfig/genServerAiProviderConfig.ts`。新增桌面能力时看 `apps/desktop/src/main/controllers`、`apps/desktop/src/preload`、`src/services/electron`。

## 依据

本页依据 `pnpm-workspace.yaml`、`tsconfig.json`、`src/app/*`、`src/spa/*`、`src/routes/*`、`src/features/*`、`src/store/*`、`src/services/*`、`src/server/routers/*`、`src/server/services/*`、`src/server/modules/*`、`packages/database/src/*`、`apps/desktop/src/*` 的目录结构和入口引用整理。模块边界部分包含少量“根据当前文件推断”，依据是文件命名、导入方向和服务调用链。
