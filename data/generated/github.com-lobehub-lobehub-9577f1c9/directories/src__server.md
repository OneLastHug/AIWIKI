# 目录：src/server

## 它负责什么

`src/server` 是这个仓库里最核心的服务端组织区，主要承载三类东西：第一是对外暴露的服务端入口，包括 TRPC 路由、Hono API 应用、Next.js backend route 的落点；第二是业务服务层 `services`，负责把数据库、对象存储、模型运行时、分析埋点、业务开关等能力串起来；第三是通用但偏服务端的基础模块，例如模型运行时封装、加密密钥管理、S3、Agent 相关能力、工作流编排、全局配置生成等。

根据当前片段推断，这个目录的设计目标不是“单纯放工具函数”，而是把服务端执行链条拆成稳定层次：入口层负责路由和鉴权，service 层负责业务编排，module 层负责可复用基础能力，`globalConfig` 和 `runtimeConfig` 负责把环境变量、产品开关和默认配置统一输出给上层。

## 直接子目录地图

- `src/server/routers`：TRPC 路由聚合区，按调用场景拆成 `lambda`、`async`、`mobile`、`tools` 四组。
- `src/server/services`：业务服务层，目录数量最多，覆盖用户、消息、任务、知识库、搜索、市场、Webhook、风险控制、Agent、工作流等领域。
- `src/server/modules`：基础模块层，偏底层能力封装，例如 `ModelRuntime`、`S3`、`KeyVaultsEncrypt`、`AgentRuntime`、`GitHub`、`PluginStore`、`Mecha`、`AssistantStore`。
- `src/server/workflows`：偏离线或编排式任务的工作流实现。
- `src/server/workflows-hono`：以 Hono 组织的工作流 HTTP 入口。
- `src/server/agent-hono`：面向 `/api/agent/*` 的 Hono 应用，聚合 agent 执行、回调、Webhook、Gateway 相关接口。
- `src/server/globalConfig`：服务端全局配置生成与默认配置解析。
- `src/server/runtimeConfig`：运行时配置定义与 provider 相关类型。
- `src/server/featureFlags`：功能开关汇总。
- `src/server/utils`：服务端辅助函数，例如 URL、临时文件、输出序列化、截断工具结果等。
- `src/server/ld.ts`、`src/server/manifest.ts`、`src/server/metadata.ts`、`src/server/sitemap.ts`、`src/server/translation.ts`：偏站点元信息、清单、国际化或页面辅助生成逻辑。
- `src/server/agent-hono/handlers`、`src/server/agent-hono/middlewares`：`/api/agent` 的具体处理器和鉴权中间件。
- `src/server/workflows-hono/agent-signal`、`src/server/workflows-hono/task` 等：工作流级别的子应用。

## 关键入口

这个目录的关键入口不在这里直接对外监听，而是被 Next.js backend routes 挂载：

- `src/app/(backend)/trpc/lambda/[trpc]/route.ts` 挂 `src/server/routers/lambda`。
- `src/app/(backend)/trpc/async/[trpc]/route.ts` 挂 `src/server/routers/async`。
- `src/app/(backend)/trpc/mobile/[trpc]/route.ts`、`src/app/(backend)/trpc/tools/[trpc]/route.ts` 分别挂对应 router。
- `src/app/(backend)/api/agent/[[...route]]/route.ts` 挂 `src/server/agent-hono/index.ts`。
- `src/app/(backend)/api/workflows/[[...route]]/route.ts` 挂 `src/server/workflows-hono/index.ts`。

从目录内看，最重要的“总入口文件”有：

- `src/server/routers/lambda/index.ts`：Lambda TRPC 根 router，把大量业务子 router 聚合起来。
- `src/server/routers/async/index.ts`：异步任务类 router 聚合入口。
- `src/server/agent-hono/index.ts`：`/api/agent/*` 的 Hono 应用入口。
- `src/server/workflows-hono/index.ts`：`/api/workflows/*` 的 Hono 应用入口。
- `src/server/globalConfig/index.ts`：服务端配置生成总入口。
- `src/server/modules/ModelRuntime/index.ts`：模型运行时适配与 keyVault payload 组装的核心位置。
- `src/server/services/user/index.ts`：用户服务的典型实现样例，能看出 service 层如何接数据库、分析和文件存储。

## 主流程位置

主流程可以按“请求进来以后怎么走”来理解：

1. HTTP 请求先进入 `src/app/(backend)/.../route.ts`。
2. TRPC 请求进入 `src/server/routers/{lambda|async|mobile|tools}`，Hono 请求进入 `src/server/agent-hono` 或 `src/server/workflows-hono`。
3. 路由层把具体业务拆给 `src/server/services/*`，例如用户、消息、任务、知识库、搜索、Agent、Webhook。
4. service 层再调用 `src/server/modules/*` 里的基础能力，例如：
   - `ModelRuntime` 负责模型提供方、密钥、payload 组装和运行时参数；
   - `S3` 负责文件/头像/对象存储读写；
   - `KeyVaultsEncrypt` 负责密钥解密或访问控制；
   - `AgentRuntime`、`AgentTracing`、`PluginStore` 这类模块负责更底层的执行或状态封装。
5. 需要跨请求共享的环境配置，则先由 `src/server/globalConfig`、`src/server/runtimeConfig`、`src/server/featureFlags` 整理，再被上层服务消费。

如果看最能代表整条链路的两个位置：
- `src/server/routers/lambda/index.ts` 体现“应用层总路由如何把业务域拼起来”；
- `src/server/services/user/index.ts` 体现“服务层如何把数据库、分析和存储能力组合成一个业务动作”。

## 推荐阅读顺序

1. 先看 `src/server/routers/lambda/index.ts`、`src/server/routers/async/index.ts`，建立服务端 API 的整体分区感。
2. 再看 `src/server/agent-hono/index.ts`、`src/server/workflows-hono/index.ts`，理解非 TRPC 的 Hono 入口怎么组织。
3. 然后看 `src/server/globalConfig/index.ts`，掌握服务端配置是如何从环境变量和业务开关汇总出来的。
4. 接着看 `src/server/services/user/index.ts` 这类典型 service，理解业务层的编排方式。
5. 最后再进入 `src/server/modules/ModelRuntime/index.ts`、`src/server/modules/S3`、`src/server/modules/KeyVaultsEncrypt` 这类底层模块，补齐执行细节。

## 常见误区

- 把 `src/server/modules` 当成普通工具目录。这里通常是底层能力封装，不只是零散 helper；很多地方会直接影响鉴权、模型调用、文件访问和执行上下文。
- 把 `src/server/services` 和 `src/server/routers` 混为一谈。前者是业务实现，后者是入口分发。改功能时通常先定位 router，再下钻 service。
- 只看 `src/server/routers/lambda/index.ts` 就以为看懂了全部 API。实际上 `async`、`mobile`、`tools`、`agent-hono`、`workflows-hono` 都是独立入口，职责不同。
- 忽略 `globalConfig` 和 `runtimeConfig`。很多行为不是写死在 service 里，而是由这些配置汇总文件决定，尤其是模型 provider、默认 Agent、文件配置、SSO、功能开关。
- 看到 `workflows` 就误以为它只是后台任务。根据当前片段推断，这里同时承担了可被 Hono 暴露的流程型接口，和更偏内部编排的 workflow 逻辑。
