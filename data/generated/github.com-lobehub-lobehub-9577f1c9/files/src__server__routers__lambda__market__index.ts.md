# 文件：src/server/routers/lambda/market/index.ts

## 它负责什么

`src/server/routers/lambda/market/index.ts` 定义了后端 `lambda` TRPC 体系里的 `marketRouter`，也就是 LobeHub “市场/发现页”相关能力的服务端入口。

它本身不是复杂业务实现层，而是一个“路由编排层”：

1. 把 Market 相关子路由挂到 `market` 命名空间下，例如 `agent`、`agentGroup`、`creds`、`skill`、`oidc`、`social`、`socialProfile`、`user`。
2. 为助手市场、群组 Agent 市场、MCP 市场、模型市场、插件市场、Provider 市场提供查询接口。
3. 为安装、点击、调用、反馈等行为提供上报接口。
4. 通过统一的 `marketProcedure` 注入 `DiscoverService` 和 `MarketService`，让每个 TRPC procedure 可以访问远端 Market SDK 或 Discover 服务。
5. 使用 `zod` 校验输入，使用 `TRPCError` 把内部错误转换为 TRPC 标准错误。

从上级路由看，`marketRouter` 被挂载到 `src/server/routers/lambda/index.ts` 的：

```ts
market: marketRouter
```

因此客户端调用路径大致会是：

```ts
lambda.market.getAssistantList
lambda.market.getPluginDetail
lambda.market.reportMcpEvent
lambda.market.oidc.xxx
```

根据当前片段推断，`marketRouter` 是 LobeHub Web/Desktop 访问官方市场、发现资源、管理市场账号和上报市场行为的主要后端网关。

## 关键组成

### 1. 基础依赖

文件顶部的 import 可以分成几类：

```ts
import { isDesktop } from '@lobechat/const';
import { TRPCError } from '@trpc/server';
import { serialize } from 'cookie';
import debug from 'debug';
import { z } from 'zod';
```

这些是通用基础设施：

- `isDesktop`：判断当前运行环境是否为 Desktop，用于上报平台、注册客户端等。
- `TRPCError`：把内部异常转换成 TRPC 可识别的错误。
- `serialize`：生成 `Set-Cookie` 头，主要用于保存 marketplace token。
- `debug`：日志工具，命名空间是 `lambda-router:market`。
- `z`：输入参数 schema 校验。

然后是 TRPC 和服务层：

```ts
import { publicProcedure, router } from '@/libs/trpc/lambda';
import { marketUserInfo, serverDatabase } from '@/libs/trpc/lambda/middleware';
import { DiscoverService } from '@/server/services/discover';
import { MarketService } from '@/server/services/market';
```

这里能看出它基于 `lambda` TRPC 框架创建路由，并通过 middleware 获取数据库上下文、market 用户信息或 token。`DiscoverService` 是发现页/市场资源读取与上报的主要服务，`MarketService` 更偏向底层 Market SDK 初始化和反馈提交等市场服务能力。

还引入了一批排序和连接类型枚举：

```ts
AssistantSorts,
McpConnectionType,
McpSorts,
ModelSorts,
PluginSorts,
ProviderSorts
```

这些类型用于限制列表查询参数里的 `sort`、`connectionType` 等字段，避免客户端传入任意字符串。

### 2. 子路由聚合

文件引入同目录下多个子路由：

```ts
import { agentRouter } from './agent';
import { agentGroupRouter } from './agentGroup';
import { credsRouter } from './creds';
import { oidcRouter } from './oidc';
import { skillRouter } from './skill';
import { socialRouter } from './social';
import { socialProfileRouter } from './socialProfile';
import { userRouter } from './user';
```

这些子文件负责更细的市场功能分组：

- `agentRouter`：Agent 管理相关能力。
- `agentGroupRouter`：Agent Group 管理。
- `credsRouter`：市场凭据管理。
- `oidcRouter`：Marketplace OIDC 认证。
- `skillRouter`：Skill 管理。
- `socialRouter`：社交能力。
- `socialProfileRouter`：社交 Profile OAuth。
- `userRouter`：用户 Profile 相关能力。

在 `marketRouter` 中直接挂载：

```ts
agent: agentRouter,
agentGroup: agentGroupRouter,
creds: credsRouter,
skill: skillRouter,
oidc: oidcRouter,
social: socialRouter,
socialProfile: socialProfileRouter,
user: userRouter,
```

这说明 `index.ts` 是 market 模块的总入口，复杂的认证、用户、社交、资源管理逻辑会继续下沉到子路由中。

### 3. `marketSourceSchema`

```ts
const marketSourceSchema = z.enum(['legacy', 'new']);
```

这个 schema 限定市场数据源只能是：

- `legacy`
- `new`

它被用于 Assistant 相关接口，例如：

```ts
getAssistantCategories
getAssistantDetail
getAssistantIdentifiers
getAssistantList
```

这说明助手市场可能存在旧版和新版两套数据来源。调用方可以通过 `source` 控制读取哪个来源；如果不传，则由服务层决定默认行为。

### 4. `marketProcedure`

这是整个文件最关键的封装：

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

它在 `publicProcedure` 基础上追加了三层处理：

1. `serverDatabase`
   给 procedure 注入服务端数据库相关上下文。目标文件里没有直接使用数据库对象，但子服务或 middleware 可能依赖它。

2. `marketUserInfo`
   根据当前请求提取 marketplace access token 或可信客户端用户信息。目标文件使用了：
   - `ctx.marketAccessToken`
   - `ctx.marketUserInfo`

3. 自定义 middleware
   把 `DiscoverService` 和 `MarketService` 实例塞进 `ctx`：

   ```ts
   ctx.discoverService
   ctx.marketService
   ```

后续所有接口都通过这两个服务完成业务动作。

这里要注意，虽然它叫 `publicProcedure`，但并不意味着“完全没有身份上下文”。它允许公开访问，但可以在请求存在可信 token 或用户信息时自动带上身份能力。文件注释也说明了这一点：

```ts
// Public procedure with optional user info for trusted client token
```

### 5. Discover 查询类接口

大部分接口都是同一种模式：

```ts
.input(z.object(...).optional())
.query(async ({ input, ctx }) => {
  log('xxx input: %O', input);

  try {
    return await ctx.discoverService.xxx(input);
  } catch (error) {
    log('Error fetching xxx: %O', error);
    throw new TRPCError({
      code: 'INTERNAL_SERVER_ERROR',
      message: 'Failed to fetch xxx',
    });
  }
})
```

这些接口主要覆盖以下资源类型。

#### Assistant Market

包括：

- `getAssistantCategories`
- `getAssistantDetail`
- `getAssistantIdentifiers`
- `getAssistantList`
- `getAgentsByPlugin`

常见参数：

- `locale`：本地化语言。
- `q`：搜索关键词。
- `category`：分类。
- `page` / `pageSize`：分页。
- `sort`：排序，使用 `AssistantSorts`。
- `order`：`asc` 或 `desc`。
- `source`：`legacy` 或 `new`。
- `identifier`：详情页资源标识。
- `version`：指定版本。
- `pluginId`：按插件查 Agent。

这些接口最终转发到 `DiscoverService`：

```ts
ctx.discoverService.getAssistantList(input)
ctx.discoverService.getAssistantDetail(input)
ctx.discoverService.getAssistantCategories(input)
```

#### Group Agent Market

包括：

- `getGroupAgentCategories`
- `getGroupAgentDetail`
- `getGroupAgentIdentifiers`
- `getGroupAgentList`

它和 Assistant Market 很像，但目标资源是“群组 Agent”。列表排序支持：

```ts
createdAt
updatedAt
name
recommended
```

#### MCP Market

包括：

- `getMcpCategories`
- `getMcpDetail`
- `getMcpList`
- `getMcpManifest`

参数中比较重要的是：

- `connectionType: z.nativeEnum(McpConnectionType)`
- `sort: z.nativeEnum(McpSorts)`
- `install: z.boolean().optional()`

`getMcpManifest` 会读取 MCP 的 manifest。`install` 参数根据当前片段推断可能用于区分“只查看 manifest”还是“安装流程中获取 manifest”。

#### Models

包括：

- `getModelCategories`
- `getModelDetail`
- `getModelIdentifiers`
- `getModelList`

这些接口用于模型市场/模型发现页。排序枚举是 `ModelSorts`。

#### Plugin Market

包括：

- `getLegacyPluginList`
- `getPluginCategories`
- `getPluginDetail`
- `getPluginIdentifiers`
- `getPluginList`

`getPluginDetail` 支持：

```ts
withManifest: z.boolean().optional()
```

这意味着插件详情可以选择是否同时带出 manifest，避免普通详情页请求过重。

#### Providers

包括：

- `getProviderDetail`
- `getProviderIdentifiers`
- `getProviderList`

`getProviderDetail` 支持：

```ts
withReadme: z.boolean().optional()
```

这说明 Provider 详情可能带有 README 内容，但可以按需读取。

#### User Profile

顶层还有：

```ts
getUserInfo
```

它接收：

```ts
username
locale?
```

然后调用：

```ts
ctx.discoverService.getUserInfo(input)
```

用于读取市场用户公开资料。

### 6. 客户端注册和 token 相关接口

`registerClientInMarketplace`：

```ts
registerClientInMarketplace: marketProcedure.input(z.object({})).mutation(async ({ ctx }) => {
  return ctx.discoverService.registerClient({
    userAgent: ctx.userAgent,
  });
});
```

它通过 `DiscoverService.registerClient` 注册当前客户端，传入 `userAgent`。根据已读到的 `DiscoverService` 代码，该方法会根据 Web/Desktop 环境组织 `clientName`、`clientType`、`deviceId`、`platform`、`version`，再调用 Market SDK 注册客户端，返回：

```ts
clientId
clientSecret
```

`registerM2MToken`：

```ts
registerM2MToken: marketProcedure
  .input(
    z.object({
      clientId: z.string(),
      clientSecret: z.string(),
    }),
  )
  .query(...)
```

它用客户端凭据换取 M2M access token：

```ts
const { accessToken, expiresIn } = await ctx.discoverService.fetchM2MToken(input);
```

成功后设置两个 Cookie：

1. `mp_token`
   - 保存真实 access token。
   - `httpOnly: true`
   - 客户端 JS 不能直接读取。

2. `mp_token_status`
   - 保存状态标记 `active`。
   - `httpOnly: false`
   - 客户端可以读取，用于知道 token 是否存在。

过期时间会提前 60 秒：

```ts
const expirationTime = new Date(Date.now() + (expiresIn - 60) * 1000);
```

返回值也是提前后的有效期：

```ts
return {
  expiresIn: expiresIn - 60,
  success: true,
};
```

如果没有拿到 `accessToken`，它会清理这两个 Cookie 并返回：

```ts
{ success: false }
```

这里的设计重点是：真实 token 放在 HttpOnly Cookie 里，前端只通过状态 Cookie 判断登录/授权状态，减少 token 暴露风险。

### 7. 行为上报和分析接口

文件后半段有大量 `report*` mutation。它们有一个共同特点：多数上报失败不会影响主流程。

例如：

```ts
reportAgentEvent
reportAgentInstall
reportGroupAgentEvent
reportGroupAgentInstall
reportMcpEvent
reportMcpInstallResult
reportCall
```

这些接口常见模式是：

```ts
try {
  await ctx.discoverService.xxx(input);
  return { success: true };
} catch (error) {
  console.error(...);
  return { success: false };
}
```

注意这里没有统一抛出 `TRPCError`，因为上报失败通常不应该阻断用户安装、点击、调用工具等主要动作。代码中甚至明确写了注释：

```ts
// Don't throw error, as reporting failure should not affect main flow
```

#### `reportAgentEvent`

上报 Agent 行为：

```ts
event: z.enum(['add', 'chat', 'click'])
identifier: z.string()
source?: z.string()
```

调用：

```ts
ctx.discoverService.createAgentEvent(input)
```

#### `reportAgentInstall`

安装计数上报：

```ts
ctx.discoverService.increaseAgentInstallCount(input.identifier)
```

#### `reportGroupAgentEvent` / `reportGroupAgentInstall`

和 Agent 类似，但目标是 Group Agent。

#### `reportMcpEvent`

MCP 行为上报：

```ts
event: z.enum(['click', 'install', 'activate', 'uninstall'])
```

调用的是：

```ts
ctx.discoverService.createPluginEvent(input)
```

这里容易误解：虽然接口叫 `reportMcpEvent`，但服务方法叫 `createPluginEvent`。根据当前片段推断，历史上 MCP 可能复用了 plugin 事件模型，或者 Market SDK 中 MCP 仍归在 plugin 资源体系下。

#### `reportMcpInstallResult`

上报 MCP 安装结果，参数比较宽松：

```ts
errorCode?: z.any()
errorMessage?: z.any()
installParams?: z.any()
manifest?: z.any()
metadata?: z.any()
```

这说明安装结果上报需要兼容不同 MCP 安装失败原因和上下文信息，因此没有做非常严格的 schema 限制。

#### `reportCall`

上报 MCP/tool/prompt/resource 调用情况：

```ts
methodType: z.enum(['tool', 'prompt', 'resource'])
methodName
callDurationMs
success
version
identifier
requestSizeBytes?
responseSizeBytes?
traceId?
sessionId?
metadata?
```

它会补充平台和 userAgent：

```ts
platform: isDesktop ? process.platform : 'web',
userAgent: ctx.userAgent,
```

然后调用：

```ts
ctx.discoverService.reportCall(...)
```

这类数据通常用于市场侧统计 MCP 工具调用质量、失败率、耗时、版本分布等。

### 8. 反馈提交接口

`submitFeedback` 接收用户反馈：

```ts
title
message
email?
screenshotUrl?
clientInfo?
```

然后调用：

```ts
const result = await ctx.marketService.submitFeedback(input);
return { issueUrl: result?.issueUrl, success: true };
```

这里和大多数发现页查询不同，它使用的是 `MarketService`，不是 `DiscoverService`。这说明反馈提交更贴近 Market 服务本身，而不是 Discover 聚合层。

失败时会抛出：

```ts
new TRPCError({
  code: 'INTERNAL_SERVER_ERROR',
  message: 'Failed to submit feedback',
})
```

和行为上报不同，反馈提交失败需要让调用方知道，所以这里没有静默返回 `success: false`。

## 上下游关系

### 上游：TRPC 根路由

`marketRouter` 被 `src/server/routers/lambda/index.ts` 引入：

```ts
import { marketRouter } from './market';
```

并挂到：

```ts
export const lambdaRouter = router({
  ...
  market: marketRouter,
  ...
});
```

因此它是 `lambdaRouter.market` 这个命名空间下的完整市场路由树。

另外，搜索结果显示移动端路由也复用了它：

```ts
src/server/routers/mobile/index.ts
```

其中存在：

```ts
market: marketRouter
```

根据当前片段推断，Web/Desktop/Mobile 的部分市场接口共享同一套路由实现。

### 中游：`marketProcedure`

`marketRouter` 内绝大多数接口都基于 `marketProcedure`。

调用链是：

```ts
publicProcedure
  -> serverDatabase middleware
  -> marketUserInfo middleware
  -> 注入 DiscoverService / MarketService
  -> 具体 query/mutation
```

这层负责统一准备上下文，避免每个接口都手动创建服务实例。

### 下游：`DiscoverService`

大多数接口最终调用 `ctx.discoverService`。

已读到的 `src/server/services/discover/index.ts` 显示：

```ts
export class DiscoverService {
  assistantStore = new AssistantStore();
  pluginStore = new PluginStore();
  market: MarketSDK;

  constructor(options: DiscoverServiceOptions = {}) {
    const { accessToken, userInfo } = options;

    const marketService = new MarketService({ accessToken, userInfo });
    this.market = marketService.market;
  }
}
```

这说明 `DiscoverService` 内部会：

1. 初始化 `AssistantStore`。
2. 初始化 `PluginStore`。
3. 通过 `MarketService` 拿到 `MarketSDK`。
4. 根据 `accessToken` 或 `userInfo` 决定是否带认证访问 Market。

根据当前片段推断，`DiscoverService` 是市场资源的聚合服务：它可能同时读取本地内置助手/插件数据和远端 Market SDK 数据，再做过滤、排序、兼容、归一化等处理。

### 下游：`MarketService`

目标文件中 `MarketService` 主要用于两处：

1. 在 `marketProcedure` 中注入 `ctx.marketService`。
2. 在 `submitFeedback` 中调用：

```ts
ctx.marketService.submitFeedback(input)
```

而 `DiscoverService` 构造函数内部也会使用 `MarketService` 初始化 Market SDK：

```ts
const marketService = new MarketService({ accessToken, userInfo });
this.market = marketService.market;
```

因此可以把关系理解成：

```txt
marketRouter
  -> DiscoverService
      -> MarketService
          -> MarketSDK
  -> MarketService
      -> MarketSDK / marketplace API
```

### 同级子路由

`index.ts` 不处理所有 market 业务，而是把很多功能拆给同目录文件：

```txt
src/server/routers/lambda/market/
├── agent.ts
├── agentGroup.ts
├── creds.ts
├── index.ts
├── oidc.ts
├── skill.ts
├── social.ts
├── socialProfile.ts
└── user.ts
```

`index.ts` 负责总装配；更细的管理型接口放在这些子路由里。

## 运行/调用流程

以 `getAssistantList` 为例，完整调用流程可以这样理解：

1. 客户端通过 TRPC 调用：

   ```ts
   lambda.market.getAssistantList.query(...)
   ```

2. 请求进入 `lambdaRouter`，根据命名空间分发到：

   ```ts
   marketRouter.getAssistantList
   ```

3. TRPC 执行 `marketProcedure` middleware：

   ```txt
   publicProcedure
   -> serverDatabase
   -> marketUserInfo
   -> new DiscoverService(...)
   -> new MarketService(...)
   ```

4. `zod` 校验输入：

   ```ts
   z.object({
     category: z.string().optional(),
     connectionType: z.nativeEnum(McpConnectionType).optional(),
     includeAgentGroup: z.boolean().optional(),
     locale: z.string().optional(),
     order: z.enum(['asc', 'desc']).optional(),
     ownerId: z.string().optional(),
     page: z.number().optional(),
     pageSize: z.number().optional(),
     q: z.string().optional(),
     sort: z.nativeEnum(AssistantSorts).optional(),
     source: marketSourceSchema.optional(),
   }).optional()
   ```

5. 路由打印 debug 日志：

   ```ts
   log('getAssistantList input: %O', input);
   ```

6. 调用服务层：

   ```ts
   return await ctx.discoverService.getAssistantList(input);
   ```

7. 如果服务层成功，结果直接返回给客户端。

8. 如果服务层抛错，路由捕获并转换成：

   ```ts
   new TRPCError({
     code: 'INTERNAL_SERVER_ERROR',
     message: 'Failed to fetch assistant list',
   })
   ```

再看 `registerM2MToken` 的流程：

1. 客户端传入 `clientId` 和 `clientSecret`。
2. 路由调用：

   ```ts
   ctx.discoverService.fetchM2MToken(input)
   ```

3. 服务层使用客户端凭据向 Market 换取 access token。
4. 如果失败或没有 token：
   - 清理 `mp_token_status`
   - 清理 `mp_token`
   - 返回 `{ success: false }`

5. 如果成功：
   - 计算提前 60 秒过期的时间。
   - 设置 HttpOnly 的 `mp_token`。
   - 设置可读的 `mp_token_status=active`。
   - 返回：

   ```ts
   {
     expiresIn: expiresIn - 60,
     success: true,
   }
   ```

再看 `reportCall` 的流程：

1. 客户端在 MCP/tool/prompt/resource 调用完成后提交调用统计。
2. 路由校验调用耗时、方法名、成功状态、版本、错误信息等字段。
3. 路由补充：
   - Desktop 下用 `process.platform`
   - Web 下用 `'web'`
   - `userAgent` 使用 `ctx.userAgent`

4. 调用：

   ```ts
   ctx.discoverService.reportCall(...)
   ```

5. 上报成功返回 `{ success: true }`。
6. 上报失败只返回 `{ success: false }`，不抛出 TRPC 错误。

## 小白阅读顺序

1. 先看 `marketProcedure`

   这是理解整份文件的入口。重点看它如何从 `ctx.marketAccessToken`、`ctx.marketUserInfo` 创建：

   ```ts
   discoverService
   marketService
   ```

   只要明白每个接口都能通过 `ctx.discoverService` 和 `ctx.marketService` 干活，后面的代码就容易很多。

2. 再看 `marketRouter = router({...})` 的一级结构

   先不要陷入每个接口的细节，先观察它按注释分了哪些区块：

   ```txt
   Agent Management
   Agent Group Management
   Credential Management
   Skill Management
   Assistant Market
   Group Agent Market
   MCP Market
   Models
   Plugin Market
   Providers
   User Profile
   OIDC Authentication
   Analytics
   Social Features
   Feedback
   ```

   这能帮你建立“市场模块有哪些能力”的地图。

3. 然后看一类典型查询接口

   推荐从 `getAssistantList` 开始，因为它字段多、模式完整：

   ```ts
   input -> log -> try -> ctx.discoverService.getAssistantList -> catch -> TRPCError
   ```

   看懂它后，`getPluginList`、`getMcpList`、`getProviderList` 都是类似模式。

4. 接着看详情接口

   例如：

   ```ts
   getAssistantDetail
   getMcpDetail
   getPluginDetail
   getProviderDetail
   ```

   这些接口通常以 `identifier` 为核心参数，外加 `locale`、`version`、`withManifest`、`withReadme` 等选项。

5. 再看 `registerClientInMarketplace` 和 `registerM2MToken`

   这两个接口涉及 marketplace 认证和 Cookie，是理解 Market 访问权限的关键。

6. 最后看 `report*` 上报接口

   这些接口数量多，但模式很一致。重点理解它们为什么多数失败时只返回 `{ success: false }`，而不是抛错。

7. 如果继续深入，下一步应该读：

   ```txt
   src/server/services/discover/index.ts
   src/server/services/market/index.ts
   src/libs/trpc/lambda/middleware
   src/server/routers/lambda/market/oidc.ts
   src/server/routers/lambda/market/agent.ts
   ```

   其中 `DiscoverService` 是业务实现重点，`index.ts` 只是路由门面。

## 常见误区

1. 误以为 `index.ts` 实现了市场业务本身

   这个文件主要是 TRPC 路由层。真正的数据获取、远端请求、聚合逻辑在：

   ```ts
   DiscoverService
   MarketService
   MarketSDK
   AssistantStore
   PluginStore
   ```

   路由层的职责是校验输入、组装上下文、调用服务、处理错误。

2. 误以为 `publicProcedure` 表示没有认证信息

   这里的 procedure 是公开可调用的，但通过 `marketUserInfo` middleware 可以附带：

   ```ts
   ctx.marketAccessToken
   ctx.marketUserInfo
   ```

   所以它支持“公开访问 + 可选身份增强”的模式。

3. 误以为所有错误都会抛给前端

   查询类接口通常会抛 `TRPCError`，例如 `getAssistantList`、`getPluginDetail`。

   但统计上报类接口通常不会抛错，而是返回：

   ```ts
   { success: false }
   ```

   因为上报失败不应该阻塞主流程。

4. 误以为 `reportMcpEvent` 一定调用 MCP 专属服务

   实际代码调用的是：

   ```ts
   ctx.discoverService.createPluginEvent(input)
   ```

   根据当前片段推断，MCP 在事件统计层可能复用了 Plugin 的事件模型，不能只凭接口名判断底层模型。

5. 误以为 `mp_token_status` 就是 access token

   `registerM2MToken` 设置了两个 Cookie：

   ```txt
   mp_token          HttpOnly，保存真实 token
   mp_token_status   非 HttpOnly，只保存 active 状态
   ```

   前端可读的只是状态标记，不是真实 token。

6. 误以为 `registerM2MToken` 是 mutation

   它虽然会设置 Cookie，有明显副作用，但代码里定义为：

   ```ts
   .query(...)
   ```

   这在语义上容易让人困惑。阅读时要以实际行为为准：它会写响应头里的 `Set-Cookie`。

7. 误以为 `source` 是所有市场资源通用参数

   `source: legacy | new` 主要出现在 Assistant 相关接口中，例如：

   ```ts
   getAssistantCategories
   getAssistantDetail
   getAssistantIdentifiers
   getAssistantList
   ```

   MCP、Plugin、Provider、Model 的列表接口不一定支持这个字段。

8. 误以为 `locale` 总是必填

   多数接口的 `locale` 都是 optional。服务层会处理默认 locale 或 fallback。路由层只负责允许调用方传入本地化偏好。

9. 误以为所有输入 schema 都很严格

   查询类接口字段通常比较明确，但安装结果、调用 metadata、custom plugin 信息等上报接口中有不少：

   ```ts
   z.any()
   z.record(z.any())
   ```

   这是为了兼容复杂动态数据，不代表这些字段在业务上无意义。

10. 误以为 `marketRouter` 只服务桌面端

   文件确实使用了 `isDesktop` 判断平台，但 `marketRouter` 被挂在 `lambdaRouter` 下，也被移动端路由复用。它是跨 Web/Desktop/Mobile 的市场后端入口，只是在部分逻辑中根据运行环境分支处理。
