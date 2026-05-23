# 目录与架构

从目录分层看，这个仓库的结构非常清晰，但需要按“职责层”来读，而不是按纯文件树来读。`src/app` 是 Next.js 的后端入口层，`src/spa` 是浏览器 SPA 启动层，`src/routes` 是页面段层，`src/features` 是业务 UI 与领域逻辑层，`src/store` 是状态层，`src/services` 是客户端服务封装层，`src/server` 是服务端实现层，`packages/*` 是共享能力层，`apps/*` 是独立产品壳层。这样的层次来自 `tsconfig.json` 的路径映射、根目录 `package.json` 的 workspace 设置，以及各目录实际文件名的分布。

`src/app` 主要解决“把不同入口挂到 Next.js 上”的问题。`src/app/layout.tsx` 提供根 HTML 外壳；`src/app/[variants]/(auth)` 负责登录、重置密码、验证码等 SSR 认证页；`src/app/spa/[variants]/[[...path]]/route.ts` 负责把静态 SPA 模板、服务端配置、功能开关、SEO 元信息和客户端环境变量拼装成可返回的 HTML；`src/app/(backend)/api`、`src/app/(backend)/trpc`、`src/app/(backend)/webapi`、`src/app/(backend)/market`、`src/app/(backend)/oidc`、`src/app/(backend)/workflows` 则承载 HTTP 接口。这里的边界很重要：`src/app` 本身不放大量页面业务，而是把请求分派给其他层。

`src/spa` 负责浏览器里的路由根。`src/spa/entry.web.tsx`、`src/spa/entry.desktop.tsx`、`src/spa/entry.mobile.tsx`、`src/spa/entry.popup.tsx` 分别对应不同平台入口；`src/spa/router/desktopRouter.config.tsx` 与 `src/spa/router/desktopRouter.config.desktop.tsx` 必须同步，这一点由 `src/spa/router/desktopRouter.sync.test.tsx` 保护；`src/spa/router/mobileRouter.config.tsx` 与 `src/spa/router/popupRouter.config.tsx` 负责移动端和弹窗场景。`src/utils/router.tsx` 在这里起到枢纽作用，它把路由树、懒加载、错误边界、全局导航引用和预取逻辑合成一个可运行的浏览器路由实例。

`src/routes` 是“薄路由树”。它的职责是只保留页面段文件，真正的 UI 和业务流程要下沉到 `src/features`。比如 `src/routes/(main)/agent`、`src/routes/(main)/group`、`src/routes/(main)/page`、`src/routes/(main)/settings`、`src/routes/(mobile)/chat`、`src/routes/onboarding` 这些目录，大多只是布局壳、页面壳和少量转发逻辑。这个分工从仓库的 `AGENTS.md` 以及多处路由配置里可以直接看出来：路由文件本身越薄，越方便平台之间复用。

`src/features` 是真正的业务拼装区。这里包含 `AgentBuilder`、`AgentSetting`、`Conversation`、`ChatInput`、`Pages`、`PageEditor`、`ResourceManager`、`SkillStore`、`PluginsUI`、`Onboarding`、`User`、`NavPanel`、`RightPanel` 等大量领域组件。它们通常组合 `src/store`、`src/services` 和 UI 组件，完成实际交互。`src/components` 则更偏通用基础组件，比如加载态、错误态、图标、提示、上传、编辑器、弹窗宿主等。

`src/server` 的边界更像后端内核。`src/server/routers/lambda` 是主 tRPC router；`src/server/routers/async`、`src/server/routers/mobile` 和 `src/server/routers/tools` 是不同用途的子 router；`src/server/services` 是真正承载业务规则的地方，比如 Agent runtime、消息、文件、生成、知识库、网关、市场、追踪、用户记忆、MCP、视频等；`src/server/modules` 是可复用的服务端模块，不一定直接访问数据库，但会为 runtime、Tracing、S3、ModelRuntime、AssistantStore 等服务提供能力。`src/server/globalConfig` 和 `src/server/featureFlags` 则负责把环境与开关翻译成客户端能理解的配置。

`packages/database` 是全仓最关键的基础设施之一。`packages/database/src/schemas` 定义表结构和关系，`packages/database/src/models` 封装单表或聚合操作，`packages/database/src/repositories` 则提供更高层的数据访问接口。`packages/database/src/index.ts` 统一导出各 schema/model/repository，`packages/database/migrations` 保存迁移脚本，`drizzle.config.ts` 连接 schema 与迁移生成。这里建议把“schema -> model -> repository -> service -> route”作为默认依赖方向，而不是反过来。

`packages/agent-runtime`、`packages/model-runtime`、`packages/model-bank`、`packages/builtin-tools`、`packages/tool-runtime` 这些包是能力底座。`packages/model-bank` 管模型与供应商定义，`packages/model-runtime` 把不同供应商适配成统一运行时，`packages/agent-runtime` 实现 Agent 的核心状态机和运行循环，`packages/builtin-tools` 则注册内建工具清单和能力白名单，`packages/tool-runtime` 提供更底层的工具执行框架。`src/server/services/agentRuntime/AgentRuntimeService.ts` 说明后端真正执行 Agent 的时候，会把这些底层包组装起来。

`src/business` 和 `packages/business/*` 体现了“开源核心 + 商业覆写”的边界。`src/business/client/BusinessGlobalProvider.tsx`、`src/business/client/BusinessDesktopRoutes.tsx`、`src/business/server/lambda-routers/*` 等文件说明业务能力会以相同接口被替换或扩展。结合 `AGENTS.md` 里提到的“cloud repo root 覆盖 submodule”的说明，可以推断这些目录是为了在不破坏开源主干的情况下加入云端特性。
