# 继续阅读指南

如果你想尽快建立全局感，建议按下面顺序推进：先看 `README.zh-CN.md`、`package.json`、`pnpm-workspace.yaml`、`tsconfig.json`，确认项目边界和脚本入口；再看 `src/app/layout.tsx`、`src/layout/SPAGlobalProvider/index.tsx`、`src/app/spa/[variants]/[[...path]]/route.ts`、`src/spa/entry.web.tsx`、`src/utils/router.tsx`，把“Next 壳 + SPA 主体”的启动方式吃透；然后读 `src/server/routers/lambda/index.ts`、`src/libs/trpc/lambda/context.ts`、`src/services/session/index.ts`、`src/store/session/store.ts`，把请求、服务、状态和页面串起来；最后再下钻 `src/server/services/agentRuntime/AgentRuntimeService.ts`、`src/server/modules/AgentRuntime/factory.ts`、`src/server/services/queue/*`、`packages/agent-runtime`、`packages/model-runtime`、`packages/builtin-tools`、`packages/database`。

最核心的入口文件其实并不多。前端主线从 `src/spa/entry.web.tsx` 开始，平台分支则看 `src/spa/entry.desktop.tsx`、`src/spa/entry.mobile.tsx` 和 `src/spa/entry.popup.tsx`；路由主逻辑在 `src/spa/router/desktopRouter.config.tsx` 和 `src/spa/router/mobileRouter.config.tsx`；服务端 API 主线在 `src/app/(backend)/trpc/lambda/[trpc]/route.ts`、`src/app/(backend)/trpc/async/[trpc]/route.ts`、`src/app/(backend)/api/agent/[[...route]]/route.ts` 和 `src/app/(backend)/api/agent/stream/route.ts`；数据库主线在 `packages/database/src/index.ts`、`packages/database/src/schemas/index.ts` 和 `packages/database/src/models`。这些文件是理解系统整体行为最划算的节点。

可后读模块也很明确。`src/features` 里的 `AgentBuilder`、`Conversation`、`PageEditor`、`ResourceManager`、`SkillStore`、`PluginsUI`、`Onboarding`、`Settings` 相关子模块，最好等你已经知道数据是如何流转之后再看，因为它们是业务拼装层，单独读很容易只看到组件树而看不到业务意图。`src/components` 里大多数通用控件也可以后读，尤其是加载、错误、弹窗、上传、编辑器和图标类组件，它们对流程理解不是第一优先级。

可以暂时跳过的模块包括体量很大的静态资源目录、文档站内容、`locales/*` 的大面积翻译文件、与某些具体供应商强绑定的适配目录，以及桌面端打包产物和图标资源。不是因为它们不重要，而是因为它们对“先搞懂仓库怎么工作”这件事帮助有限。等你完成主链阅读后，再回头看这些内容，会更容易把它们放进正确的位置。

如果要继续下钻，我建议按“外壳 -> 路由 -> 服务 -> 数据 -> 能力包”这个顺序。先补 `src/routes/(main)/_layout/index.tsx` 和 `src/routes/(main)/agent/index.tsx`，理解一个真实页面怎么挂到布局里；再看 `src/services/chat/index.ts`、`src/services/document/index.ts`、`src/services/generation.ts`、`src/services/user/index.ts` 这些客户端服务，理解前端如何调用后端；然后读 `src/server/services/agentRuntime/*`、`src/server/services/queue/*`、`src/server/services/gateway/*`，理解 Agent 的执行和调度；最后进入 `packages/agent-runtime/src/core/runtime.ts`、`packages/model-runtime/src/core/ModelRuntime.ts`、`packages/database/src/repositories/*`，把底层能力串完整。

如果你的目标是改功能而不是做全景阅读，最稳的策略是先定位“调用点”和“状态点”。调用点通常在 `src/services/*`、`src/server/routers/*`、`src/app/(backend)/*`；状态点通常在 `src/store/*`、`packages/database/src/models/*`、`packages/database/src/schemas/*`。把这两类点找出来，通常就能判断一项改动会影响前端、服务端还是数据库迁移。
