# 目录：src/server/routers/lambda/market

## 它负责什么

`src/server/routers/lambda/market` 是 LobeHub 服务端 `lambda` tRPC 路由里的“市场/发现/发布/社交”聚合入口。它把前端对 Marketplace 的访问统一包装成 `lambdaClient.market.*` 调用，再在服务端侧转发到 `DiscoverService`、`MarketService` 以及底层 Market SDK。

这个目录处理的业务面比较宽，核心可以分成两类：

1. **发现型市场接口**：查询 assistants、MCP/plugins、models、providers、skills、group agents 等公开市场资源，例如 `getAssistantList`、`getMcpDetail`、`getPluginList`、`getProviderDetail`。
2. **账户/创作/社交型接口**：发布 agent、发布 agent group、管理凭据、OIDC 登录、用户资料、收藏/点赞/关注、资源认领等，例如 `market.agent.publishOrCreate`、`market.creds.createKV`、`market.social.follow`。

它不是数据库 model，也不是 Marketplace 的真正业务实现层；它更像一个 **tRPC BFF 层**：做输入校验、鉴权上下文注入、服务实例创建、错误转换，然后调用 `src/server/services/discover` 或 `src/server/services/market`。

## 关键组成

直接文件如下：

- `index.ts`：总入口，导出 `marketRouter`。它组合所有子 router，并直接定义大量“市场发现”接口。
- `agent.ts`：agent 发布、版本、归属检查、fork、我的 agents、onboarding 数据等。
- `agentGroup.ts`：agent group 的发布、归属检查、fork、列表、详情等。
- `skill.ts`：market skill 的分类、详情、列表查询。
- `creds.ts`：市场凭据管理，包括 KV、OAuth、文件凭据、凭据注入、OAuth connections、文件上传。
- `oidc.ts`：Marketplace OIDC 流程，包括授权码换 token、refresh token、handoff、userinfo。
- `social.ts`：关注、收藏、点赞，以及用户收藏/点赞列表查询。
- `socialProfile.ts`：社交资料相关资源认领，例如扫描可认领资源、认领资源、提交 repo。
- `user.ts`：用户公开资料查询和当前用户资料更新。

`index.ts` 里最重要的本地抽象是 `marketProcedure`：

```ts
const marketProcedure = publicProcedure
  .use(serverDatabase)
  .use(marketUserInfo)
  .use(async ({ ctx, next }) => {
    return next({
      ctx: {
        discoverService: new DiscoverService({
          accessToken: ctx.marketAccessToken,
          userInfo: ctx.marketUserInfo,
        }),
        marketService: new MarketService({
          accessToken: ctx.marketAccessToken,
          userInfo: ctx.marketUserInfo,
        }),
      },
    });
  });
```

这段说明了该目录的基本模式：

- 从 `@/libs/trpc/lambda` 引入 `publicProcedure` 和 `router`，说明它是 lambda tRPC router。
- 通过 `serverDatabase` 初始化服务端上下文。
- 通过 `marketUserInfo` 读取 Marketplace 用户信息和 access token。
- 在 `ctx` 上挂载 `discoverService` 和 `marketService`，后续 procedure 只调用服务方法。
- 通过 `zod` 对输入参数做 schema 校验。
- 通过 `TRPCError` 把底层异常转换成 tRPC 错误。

`marketRouter` 的 export 结构大致是：

```ts
export const marketRouter = router({
  agent: agentRouter,
  agentGroup: agentGroupRouter,
  creds: credsRouter,
  skill: skillRouter,
  oidc: oidcRouter,
  social: socialRouter,
  socialProfile: socialProfileRouter,
  user: userRouter,

  getAssistantList: ...,
  getMcpList: ...,
  getPluginList: ...,
  getModelList: ...,
  getProviderList: ...,
  registerClientInMarketplace: ...,
  registerM2MToken: ...,
  reportCall: ...,
  submitFeedback: ...,
});
```

其中 `agent`、`agentGroup`、`creds` 等是子命名空间，调用时会变成 `lambdaClient.market.agent.*`、`lambdaClient.market.creds.*`；而 `getAssistantList`、`getMcpList` 这类直接挂在 `market` 下。

几个子 router 的职责可以这样记：

| 文件 | 导出 | 主要职责 |
| --- | --- | --- |
| `index.ts` | `marketRouter` | 聚合入口，公开市场资源查询，安装/调用上报，注册 Marketplace client/token，反馈提交 |
| `agent.ts` | `agentRouter` / `AgentRouter` | 单个 agent 的发布、创建版本、fork、归属判断、上下架 |
| `agentGroup.ts` | `agentGroupRouter` / `AgentGroupRouter` | agent group 的发布、fork、详情、列表、上下架 |
| `skill.ts` | `skillRouter` | skill 市场列表、分类、详情 |
| `creds.ts` | `credsRouter` | 凭据 CRUD、凭据注入、OAuth 连接、凭据文件上传 |
| `oidc.ts` | `oidcRouter` / `OidcRouter` | Market OAuth/OIDC token 交换、刷新和用户信息 |
| `social.ts` | `socialRouter` / `SocialRouter` | 关注、收藏、点赞及相关列表 |
| `socialProfile.ts` | `socialProfileRouter` / `SocialProfileRouter` | 资源认领、repo 提交 |
| `user.ts` | `userRouter` / `UserRouter` | 用户公开资料读取、当前用户资料更新 |

## 上下游关系

上游调用方主要是前端 service 和少量路由组件。根据当前片段可确认的调用包括：

- `src/services/discover.ts`：调用 `lambdaClient.market.getAssistantList`、`getMcpDetail`、`getPluginList`、`getProviderList`、`registerM2MToken`、各种 report 接口等，是发现页/市场页的主要客户端服务。
- `src/services/marketApi.ts`：调用 `lambdaClient.market.agent.*`、`agentGroup.*`、`skill.*`，负责发布、fork、获取自己创建的市场资源等偏创作者侧 API。
- `src/services/social.ts`：调用 `lambdaClient.market.social.*`，封装关注、收藏、点赞。
- `src/services/tool.ts`、`src/services/mcp.ts`：会调用 market 插件/MCP 相关接口。
- 设置页凭据 UI：例如 `src/routes/(main)/settings/creds/features/*` 调用 `market.creds.list`、`createKV`、`createOAuth`、`uploadFile`、`update`、`delete`。
- agent/group 发布按钮：例如 `src/routes/(main)/agent/profile/.../useMarketPublish.ts`、`src/routes/(main)/group/profile/.../useMarketGroupPublish.ts` 调用 `checkOwnership`、`publishOrCreate`。
- 社区用户页：例如 `src/routes/(main)/community/(detail)/user/features/SubmitRepoModal.tsx` 调用 `market.socialProfile.submitRepo`。

下游依赖主要有三层：

- `src/server/services/discover/index.ts`：负责公开发现类接口，例如 assistants、plugins/MCP、models、providers、group agents、安装/事件上报。
- `src/server/services/market/index.ts`：负责 Market SDK 封装，包括 OIDC、feedback、connect、skills、creds、plugins、agents、agentGroups、user 等。
- Market SDK / 外部 Marketplace 服务：代码中多处使用 `MARKET_BASE_URL` 或默认 `[URL已移除] Marketplace 服务侧。

这个 router 被挂载到两个服务端入口：

- `src/server/routers/lambda/index.ts`：`market: marketRouter`
- `src/server/routers/mobile/index.ts`：`market: marketRouter`

因此它不仅服务 Web/桌面 SPA 的 lambda tRPC，也复用给 mobile router。阅读时要注意：这里的接口变更可能影响多端。

## 运行/调用流程

一个典型的公开查询流程，例如前端获取 MCP 列表：

1. 前端业务代码调用 `src/services/discover.ts`。
2. service 调用 `lambdaClient.market.getMcpList.query(...)`。
3. tRPC 请求进入 `src/server/routers/lambda/index.ts` 下的 `marketRouter`。
4. `getMcpList` 的 `zod` schema 校验参数，例如 `category`、`connectionType`、`locale`、`page`、`pageSize`、`sort`。
5. `marketProcedure` 依次执行 `serverDatabase`、`marketUserInfo`，并创建 `DiscoverService` / `MarketService`。
6. handler 调用 `ctx.discoverService.getMcpList(input)`。
7. `DiscoverService` 调用 Market SDK，例如 `this.market.plugins.getPluginList(...)`。
8. 成功时直接返回给前端；失败时记录 `debug` 日志并抛出 `TRPCError`。

一个需要登录的凭据流程，例如创建 KV 凭据：

1. 设置页表单调用 `lambdaClient.market.creds.createKV.mutate(...)`。
2. 请求进入 `credsRouter.createKV`。
3. `credsProcedure` 执行 `serverDatabase`、`marketUserInfo`、`requireMarketAuth`。
4. 如果没有 Marketplace 登录态或 token，`requireMarketAuth` 会阻断请求。
5. procedure 创建 `MarketService`，并调用 `ctx.marketService.market.creds.createKV(input)`。
6. 日志中会隐藏敏感字段，例如 `values: '[HIDDEN]'`。
7. 返回创建结果，失败则转成 `INTERNAL_SERVER_ERROR`。

一个发布 agent 的流程，根据当前片段推断如下：前端 profile 发布按钮调用 `market.agent.checkOwnership` 判断当前用户是否拥有目标 `identifier`，再调用 `market.agent.publishOrCreate`。`agent.ts` 内部会校验 agent 的基础字段、版本字段、配置字段，并通过 Market SDK 创建或更新 Marketplace 侧 agent。这个推断依据是 `agent.ts` 暴露了 `checkOwnership`、`publishOrCreate`、`createAgent`、`createAgentVersion`、`publishAgent` 等方法，同时调用方 `useMarketPublish.ts` 正在按这个命名空间调用。

OIDC 流程则集中在 `oidc.ts`：

- `exchangeAuthorizationCode`：接收 `clientId`、`code`、`codeVerifier`、`redirectUri`，调用 `marketService.exchangeAuthorizationCode`。
- `refreshToken`：接收 `refreshToken`，刷新 access token。
- `getUserInfo`：可用显式 token，也可在已有 `marketUserInfo` 时走 trusted client。
- `getOAuthHandoff`：根据 handoff id 获取 OAuth 交接信息。

`index.ts` 中还存在 `registerClientInMarketplace` 和 `registerM2MToken`。根据当前片段可见，`registerClientInMarketplace` 会调用 `ctx.discoverService.registerClient({ userAgent: ctx.userAgent })`；`registerM2MToken` 会用 `clientId`、`clientSecret` 换取 M2M token，并通过 cookie 记录 token 状态。由于长文件输出被截断，cookie 细节只能根据当前片段推断，依据是它导入了 `serialize`，并在 `registerM2MToken` 内处理 `mp_token_status` 的 `Set-Cookie`。

## 小白阅读顺序

1. 先看 `src/server/routers/lambda/market/index.ts` 顶部 import 和 `marketProcedure`。这里能理解所有接口共享的上下文：`serverDatabase`、`marketUserInfo`、`DiscoverService`、`MarketService`。
2. 继续看 `index.ts` 里的 `marketRouter` 结构，不必一开始逐行读每个 handler。先把接口按 assistant、MCP、model、plugin、provider、group agent、report、feedback 分组。
3. 看 `src/server/routers/lambda/index.ts`，确认 `marketRouter` 被挂载为 `market`，这样前端调用路径为什么是 `lambdaClient.market.xxx` 就清楚了。
4. 看 `src/services/discover.ts`，从客户端角度理解公开市场查询如何调用这些接口。
5. 看 `src/services/marketApi.ts`，理解 agent / agent group / skill 这些创作者侧能力。
6. 再读 `creds.ts`，因为它的鉴权要求更强，还涉及敏感数据隐藏、文件上传、OAuth connections、凭据注入。
7. 最后读 `agent.ts`、`agentGroup.ts`、`social.ts`、`socialProfile.ts`、`user.ts`。这些文件业务字段较多，适合在已经理解总路由模式后再看。

建议小白不要从 `agent.ts` 开始，因为它 schema 多、发布语义多、还有 fork/ownership/version 概念；从 `index.ts` 的公开查询接口入手更容易建立整体模型。

## 常见误区

1. **误以为这里直接操作数据库。**  
   这个目录主要是 tRPC router 和 BFF 层。虽然 procedure 使用了 `serverDatabase` middleware，但大多数核心业务是委托给 `DiscoverService`、`MarketService` 和 Market SDK，不是在 router 内直接写 DB 查询。

2. **误把 `marketProcedure` 当成强鉴权接口。**  
   `marketProcedure` 是 `publicProcedure` 加 `marketUserInfo`，它可以携带 Marketplace 用户信息，但不等于所有接口都强制登录。真正需要登录的子模块通常会使用类似 `requireMarketAuth` 的 middleware，例如 `creds.ts` 的 `credsProcedure`。

3. **混淆 `DiscoverService` 和 `MarketService`。**  
   `DiscoverService` 更偏公开发现、列表、详情、事件上报；`MarketService` 更偏 Market SDK 能力封装，包括 OIDC、凭据、connect、skills、feedback、发布相关底层能力。实际边界不是绝对的，但阅读时可以先按这个方向理解。

4. **忽略子 router 命名空间。**  
   `market.getPluginList` 和 `market.agent.getAgentDetail` 是不同层级。前者直接定义在 `index.ts`，后者来自 `agentRouter`。查调用方时要按完整路径搜索，例如 `lambdaClient.market.agent.`、`lambdaClient.market.creds.`。

5. **以为 `skill` 和 `plugin/MCP` 是同一套路由。**  
   `skill.ts` 是 `market.skill.*` 子命名空间；而 plugin/MCP 的大量公开查询在 `index.ts` 中直接定义，如 `getPluginList`、`getMcpDetail`、`getMcpManifest`。两者都和 Marketplace 有关，但入口不同。

6. **忽视 mobile 复用。**  
   `marketRouter` 同时挂在 lambda 和 mobile router 下。修改这里的输入 schema、返回结构或错误语义时，不只影响 Web 页面，也可能影响移动端调用。

7. **把 report 接口当成前端统计逻辑。**  
   `reportCall`、`reportMcpEvent`、`reportAgentInstall`、`reportGroupAgentEvent` 等在 router 中只是接收并转交给服务层。真正的安装数、调用数、事件记录逻辑在 Marketplace/Discover 服务侧。

8. **忽略敏感信息处理。**  
   `creds.ts` 和 `oidc.ts` 里会刻意在日志中隐藏 `fileHashId`、`values`、`code`、`refreshToken` 等字段。阅读或扩展同类接口时，要延续这个习惯，避免把凭据、token、授权码写进日志。
