# 文件：src/libs/trpc/client/lambda.ts

## 它负责什么

`src/libs/trpc/client/lambda.ts` 是前端访问主业务 tRPC Lambda Router 的客户端装配文件。它不定义具体业务接口，也不实现后端逻辑，而是把“前端如何调用 `/trpc/lambda`”这件事统一封装起来。

它主要负责四类事情：

1. 创建类型安全的 tRPC 客户端 `lambdaClient`，供服务层、store、组件直接调用 `query` / `mutate`。
2. 创建 React Query 风格的 hooks 入口 `lambdaQuery` 和 `lambdaQueryClient`，供组件使用 `useQuery`、`useMutation` 等。
3. 给每次请求统一加认证 header、cookie、序列化器、Electron 协议适配。
4. 统一处理 tRPC 错误，尤其是 `401` 未授权、Market 登录态失效、普通登录态失效和 abort 请求。

可以把它理解成：

```text
前端业务代码
  -> lambdaClient / lambdaQuery
  -> src/libs/trpc/client/lambda.ts
  -> /trpc/lambda
  -> src/server/routers/lambda/index.ts
  -> 具体业务 router
```

## 关键组成

### 1. 类型来源：`LambdaRouter`

文件中引入了：

```ts
import { type LambdaRouter } from '@/server/routers/lambda';
```

`LambdaRouter` 来自 `src/server/routers/lambda/index.ts`，它是后端主业务 router 的类型：

```ts
export const lambdaRouter = router({
  agent: agentRouter,
  config: configRouter,
  file: fileRouter,
  market: marketRouter,
  session: sessionRouter,
  topic: topicRouter,
  ...
});

export type LambdaRouter = typeof lambdaRouter;
```

因此，前端调用：

```ts
lambdaClient.config.getGlobalConfig.query()
lambdaClient.market.getAssistantList.query(...)
lambdaClient.file.createFile.mutate(...)
```

这些路径不是字符串魔法，而是由 `LambdaRouter` 类型推导出来的。后端 router 变了，前端类型也会跟着变。

### 2. `errorHandlingLink`

`errorHandlingLink` 是一个自定义 tRPC link，用来包住后续请求链路：

```ts
const errorHandlingLink: TRPCLink<LambdaRouter> = () => {
  return ({ op, next }) =>
    observable((observer) =>
      next(op).subscribe({
        ...
      }),
    );
};
```

它监听每个 tRPC operation 的结果，核心处理逻辑在 `error` 分支。

它会先识别 abort 类错误：

```ts
const isAbortError =
  err.message.includes('aborted') ||
  err.name === 'AbortError' ||
  err.cause?.name === 'AbortError' ||
  err.message.includes('signal is aborted without reason');
```

如果是用户取消、组件卸载、请求被中止这类错误，就不会弹通知或走登录态处理。这样避免把正常的取消请求当成系统错误。

然后它读取：

```ts
const showError = (op.context?.showNotification as boolean) ?? true;
const status = err.data?.httpStatus as number;
const isMarketApi = op.path.startsWith('market.');
```

这里有两个重要点：

- `showNotification` 可以由调用方通过 tRPC context 控制是否展示错误通知。
- `market.*` 路径会被单独识别，因为 Market 登录态和 LobeChat 主登录态不是一回事。

### 3. `401` 防抖处理

文件顶部有两个时间戳：

```ts
let last401Time = 0;
let lastMarket401Time = 0;
const MIN_401_INTERVAL = 5000;
```

它们用于防止短时间内多个接口同时返回 `401` 时重复弹通知、重复重定向、重复触发事件。

普通 `401` 和 Market `401` 分开防抖：

```text
普通业务 401       -> last401Time
market.* 401      -> lastMarket401Time
```

这是必要的，因为页面初始化时可能同时发出多个请求。如果不防抖，一个登录过期可能导致连续多次 logout、通知、redirect。

### 4. Market API 的 `401`

如果出错路径是 `market.*`，代码不会触发 LobeChat 主账号 logout，而是动态导入：

```ts
const { marketAuthEvents } =
  await import('@/layout/AuthProvider/MarketAuth/events');
```

然后发出事件：

```ts
marketAuthEvents.emit('market-unauthorized', {
  path: op.path,
  timestamp: now,
});
```

这表示 Market 登录态失效交给 `MarketAuthProvider` 处理。

这点很关键：`market.*` 的 `401` 不等于主应用用户登录过期。Market 可能有自己的 token、OIDC、资源认领或 marketplace 认证流程。

### 5. 普通业务的 `401`

如果不是 `market.*`，则按 LobeChat 主登录态处理：

```ts
if (!isDesktop) {
  const { getUserStoreState } = await import('@/store/user/store');
  const { isSignedIn, logout } = getUserStoreState();

  if (isSignedIn) {
    await logout();
  }

  const { loginRequired } =
    await import('@/components/Error/loginRequiredNotification');
  loginRequired.redirect();
}
```

注意这里跳过了桌面端：

```ts
if (!isDesktop) {
  ...
}
```

注释说明桌面端没有 Web 端那套 `/signin` 登录路由，所以不能直接执行 Web 登录重定向。

处理完 `401` 后还会设置：

```ts
err.meta = { ...err.meta, shouldRetry: false };
```

这用于告诉上层，例如 SWR，不要因为 `401` 进入无限重试循环。

### 6. `linkOptions.fetch`

`linkOptions` 是 HTTP link 共用配置，其中 `fetch` 被重写：

```ts
fetch: async (input: RequestInfo | URL, init?: RequestInit) => {
  const fetchOptions: RequestInit = {
    ...init,
    credentials: 'include',
  };

  if (isDesktop) {
    const res = await fetch(input as string, fetchOptions);

    if (res) return res;
  }

  return await fetch(input, fetchOptions);
}
```

核心目的是让请求携带 cookie：

```ts
credentials: 'include'
```

注释中特别提到 cookie 里可能有 `mp_token`，这与 Market 认证相关。

桌面端分支把 `input` 转成 `string` 再 fetch。根据当前片段推断，这是为了配合 Electron 自定义协议或桌面端 fetch 行为，具体协议转换由 `withElectronProtocolIfElectron` 负责。

### 7. `linkOptions.headers`

每次请求前动态生成 header：

```ts
const { createHeaderWithAuth } = await import('@/services/_auth');
```

这里用动态导入，注释说明是为了避免循环依赖。

特殊逻辑是图片页面：

```ts
if (location.pathname === '/image') {
  const { getImageStoreState } = await import('@/store/image');
  const { imageGenerationConfigSelectors } =
    await import('@/store/image/slices/generationConfig/selectors');

  provider = imageGenerationConfigSelectors.provider(getImageStoreState()) as ModelProvider;
}
```

如果当前路径是 `/image`，它会从图片生成配置 store 中读取当前模型 provider，然后传给：

```ts
createHeaderWithAuth(provider ? { provider } : undefined);
```

文件里的注释说明了意图：

```text
Only include provider in JWT for image operations
For other operations (like knowledge base embedding), let server use its own config
```

也就是说，只有图片相关操作需要把 provider 写入认证 header/JWT 语境。其他业务不应该被当前图片页面的 provider 污染。

### 8. `superjson`

配置中使用：

```ts
transformer: superjson
```

这让 tRPC 可以安全传输普通 JSON 不支持或不好表达的数据结构，比如 `Date`、复杂对象等。前后端必须使用一致的 transformer，否则序列化/反序列化可能不一致。

### 9. 请求地址

```ts
url: withElectronProtocolIfElectron('/trpc/lambda')
```

Web 端最终访问的是 `/trpc/lambda`。Electron 下会经过 `withElectronProtocolIfElectron` 做协议适配。

服务端入口位于：

```text
src/app/(backend)/trpc/lambda/[trpc]/route.ts
```

那里使用：

```ts
fetchRequestHandler({
  createContext: () => createLambdaContext(req),
  endpoint: '/trpc/lambda',
  router: lambdaRouter,
  ...
});
```

所以客户端这里的 URL 与服务端 handler 的 endpoint 是配套的。

### 10. 批处理与 `splitLink`

文件定义了几组不走 batch 的 procedure：

```ts
const initialLoadProcedures = new Set(['user.getUserState', 'config.getGlobalConfig']);
const slowProcedures = new Set(['market.getAssistantList']);
const SKIP_BATCH_PROCEDURES = new Set([...initialLoadProcedures, ...slowProcedures]);
```

然后用 `splitLink` 按路径分流：

```ts
const customSplitLink = splitLink({
  condition: (op) => SKIP_BATCH_PROCEDURES.has(op.path),
  false: httpBatchLink({ ...linkOptions, maxURLLength: 2083 }),
  true: httpLink(linkOptions),
});
```

含义是：

```text
如果 op.path 在 SKIP_BATCH_PROCEDURES 中
  -> 使用 httpLink，单独请求，不参与 batch

否则
  -> 使用 httpBatchLink，多个请求可合并发送
```

被跳过 batch 的接口包括：

- `user.getUserState`
- `config.getGlobalConfig`
- `market.getAssistantList`

前两个是首屏初始化关键接口，单独发可以减少等待 batch 聚合带来的延迟。`market.getAssistantList` 被标记为慢接口，避免它拖慢同一批次里的其他请求。

### 11. 最终导出

文件最后导出三个对象：

```ts
export const lambdaClient = createTRPCClient<LambdaRouter>({
  links,
});

export const lambdaQuery = createTRPCReact<LambdaRouter>();

export const lambdaQueryClient = lambdaQuery.createClient({ links });
```

它们用途不同：

| 导出 | 用途 |
| --- | --- |
| `lambdaClient` | 命令式调用，常见于 service、store action、工具执行器 |
| `lambdaQuery` | React hooks 工厂，例如 `lambdaQuery.xxx.useQuery()` |
| `lambdaQueryClient` | 给 `lambdaQuery.Provider` 使用的客户端实例 |

同目录 `index.ts` 会重新导出它：

```ts
export * from './lambda';
```

所以大多数调用方可以直接从：

```ts
@/libs/trpc/client
```

导入。

## 上下游关系

### 上游：前端调用方

这个文件被大量前端业务代码使用。典型调用方式有两类。

第一类是 service / action 中直接调用 `lambdaClient`：

```ts
lambdaClient.config.getGlobalConfig.query()
lambdaClient.topic.createTopic.mutate(...)
lambdaClient.file.createFile.mutate(...)
lambdaClient.market.creds.list.query()
```

搜索结果显示调用方分布在：

```text
src/services/*
src/store/*
src/features/*
src/routes/*
packages/builtin-tool-*/src/client/*
```

比如：

- `src/services/global.ts` 通过 `lambdaClient.config.getGlobalConfig.query()` 获取全局配置。
- `src/services/discover.ts` 通过 `lambdaClient.market.*` 获取 marketplace 数据。
- `src/services/aiAgent.ts` 通过 `lambdaClient.aiAgent.*` 执行 agent 任务。
- `packages/builtin-tool-knowledge-base/src/client/executor/index.ts` 通过 `lambdaClient.knowledgeBase.*` 和 `lambdaClient.file.*` 操作知识库。

第二类是在组件中使用 `lambdaQuery` hooks：

```ts
lambdaQuery.market.creds.list.useQuery(...)
lambdaQuery.oauthDeviceFlow.getAuthStatus.useQuery(...)
lambdaQuery.exporter.exportPdf.useMutation()
```

这类调用依赖 React Query 的缓存、加载态、错误态和重新请求能力。

### 上游：全局 Provider

`lambdaQueryClient` 会被挂到全局 Query Provider 中。搜索结果显示位置是：

```text
src/layout/GlobalProvider/Query.tsx
```

那里使用类似结构：

```tsx
<lambdaQuery.Provider client={lambdaQueryClient} queryClient={providerQueryClient}>
  ...
</lambdaQuery.Provider>
```

这意味着组件里调用 `lambdaQuery.xxx.useQuery()` 时，实际使用的是本文件创建的 links、headers、error handling、batch 策略。

### 下游：服务端 tRPC endpoint

客户端请求最终进入：

```text
src/app/(backend)/trpc/lambda/[trpc]/route.ts
```

这个 Next.js route handler 做几件事：

1. 用 `prepareRequestForTRPC(req)` 准备请求，避免 Next.js 16 下 body stream 被消费的问题。
2. 用 `createLambdaContext(req)` 创建 tRPC context。
3. 使用 `lambdaRouter` 作为后端 router。
4. 通过 `fetchRequestHandler` 处理 GET / POST。
5. 对非 `UNAUTHORIZED` 错误做服务端日志输出。

### 下游：`lambdaRouter`

`lambdaRouter` 位于：

```text
src/server/routers/lambda/index.ts
```

它聚合了大量业务 router，例如：

```text
agent
aiAgent
config
file
image
knowledgeBase
market
message
session
topic
upload
user
...
```

所以 `lambda.ts` 是前端通往这组主业务 API 的统一入口。

### 旁路关系：`async.ts` 和 `tools.ts`

同目录还有：

```text
src/libs/trpc/client/async.ts
src/libs/trpc/client/tools.ts
```

它们分别创建 `asyncClient` 和 `toolsClient`。

对比可以看出：

- `async.ts` 很轻，只配置 `httpBatchLink`、`superjson`、`/trpc/async`。
- `tools.ts` 也有 Market `401` 处理，但没有 React Query hooks，也没有图片 provider header 逻辑。
- `lambda.ts` 是最复杂的主客户端，承担主业务、登录态、Market、图片 provider、batch 分流等多种横切逻辑。

## 运行/调用流程

以组件调用：

```ts
lambdaQuery.config.getGlobalConfig.useQuery()
```

或服务调用：

```ts
lambdaClient.config.getGlobalConfig.query()
```

为例，流程大致如下：

```text
1. 前端业务代码发起 tRPC 调用
   -> lambdaClient.xxx.query/mutate
   -> 或 lambdaQuery.xxx.useQuery/useMutation

2. 请求进入 links 链
   -> 先经过 errorHandlingLink
   -> 再进入 customSplitLink

3. customSplitLink 判断 op.path
   -> user.getUserState / config.getGlobalConfig / market.getAssistantList 使用 httpLink
   -> 其他接口使用 httpBatchLink

4. linkOptions.headers 执行
   -> 动态导入 createHeaderWithAuth
   -> 如果当前路径是 /image，则读取图片 store 中的 provider
   -> 生成带认证信息的 headers

5. linkOptions.fetch 执行
   -> credentials: 'include'
   -> 携带 cookie
   -> Electron 环境下走桌面端兼容逻辑

6. 请求发送到 /trpc/lambda
   -> Web 端是普通路径
   -> Electron 端经 withElectronProtocolIfElectron 适配

7. Next.js route handler 接收请求
   -> src/app/(backend)/trpc/lambda/[trpc]/route.ts

8. fetchRequestHandler 创建 context
   -> createLambdaContext(req)

9. lambdaRouter 根据路径分发到具体 router
   -> 例如 config.getGlobalConfig
   -> 或 market.getAssistantList
   -> 或 file.createFile

10. 响应通过 superjson 返回前端

11. 如果请求失败
   -> errorHandlingLink 判断错误类型
   -> abort 错误静默
   -> market.* 401 触发 market-unauthorized
   -> 普通 401 执行 logout 和 loginRequired.redirect
   -> 其他错误 console.error 后继续抛给调用方
```

一个关键细节是：`errorHandlingLink` 不会吞掉错误。它最后仍然执行：

```ts
observer.error(err);
```

所以调用方、React Query、SWR 等上层仍然能感知失败，只是这个 link 在错误传播前做了统一副作用处理。

## 小白阅读顺序

建议按下面顺序读，不要一上来陷入 tRPC link 的类型细节。

1. 先看文件最后的三个导出：

```ts
lambdaClient
lambdaQuery
lambdaQueryClient
```

先明确这个文件对外提供什么。

2. 再看 `links` 的组成：

```ts
const links = [errorHandlingLink, customSplitLink];
```

这说明所有请求都会先过错误处理，再进入 HTTP 请求分流。

3. 看 `linkOptions.url`：

```ts
url: withElectronProtocolIfElectron('/trpc/lambda')
```

确认客户端请求发往哪个 endpoint。

4. 跳到服务端入口：

```text
src/app/(backend)/trpc/lambda/[trpc]/route.ts
```

确认 `/trpc/lambda` 最终交给 `lambdaRouter`。

5. 再看 router 聚合：

```text
src/server/routers/lambda/index.ts
```

理解为什么前端可以调用 `lambdaClient.file.*`、`lambdaClient.market.*`、`lambdaClient.topic.*`。

6. 回到 `linkOptions.headers`，理解认证 header 如何动态生成，以及为什么 `/image` 页面要额外带 provider。

7. 最后读 `errorHandlingLink`，重点看三类错误：

```text
abort 错误
market.* 401
普通 401
```

8. 有余力再看同目录：

```text
src/libs/trpc/client/async.ts
src/libs/trpc/client/tools.ts
src/libs/trpc/client/index.ts
```

通过对比能更清楚 `lambda.ts` 为什么更复杂。

## 常见误区

### 误区 1：以为 `lambda.ts` 实现了业务 API

它没有实现业务 API。真正的业务 API 在：

```text
src/server/routers/lambda/*
```

`lambda.ts` 只是前端 tRPC client 的配置层。

### 误区 2：以为所有 `401` 都应该 logout

不是。代码明确区分：

```text
market.* 401  -> MarketAuthProvider 处理
非 market 401 -> LobeChat 主登录态处理
```

Market 认证和主应用认证是两套语义，不能混在一起。

### 误区 3：以为 abort error 是异常故障

很多 abort 是正常行为，例如组件卸载、请求取消、快速切换页面。这里专门识别 abort，避免无意义的错误提示。

### 误区 4：以为所有请求都会 batch

不是。`splitLink` 会让部分接口跳过 batch：

```text
user.getUserState
config.getGlobalConfig
market.getAssistantList
```

首屏关键接口和慢接口不参与 batch，是为了避免互相拖累。

### 误区 5：以为 `lambdaClient` 和 `lambdaQuery` 可以随便替换

二者都基于 `LambdaRouter`，但使用场景不同：

```text
lambdaClient -> 命令式调用，适合 service、store action、工具执行器
lambdaQuery  -> React hooks，适合组件内数据请求和 mutation
```

组件里需要缓存、加载态、自动刷新时，通常用 `lambdaQuery`。非组件逻辑或一次性命令调用通常用 `lambdaClient`。

### 误区 6：忽略 `credentials: 'include'`

这个配置保证 cookie 会随请求发送。去掉它可能导致登录态、Market token、服务端 session 等失效。

### 误区 7：忽略 `/image` 的 provider 注入

`headers` 中只在 `location.pathname === '/image'` 时读取图片 store 的 provider。这不是通用 provider 逻辑，而是图片生成场景的特殊需求。其他业务应该让服务端使用自己的配置，避免被当前图片页面状态影响。

### 误区 8：以为动态 import 只是代码风格

这里的动态 import 有实际作用。文件注释多次提到是为了避免循环依赖，例如：

```ts
await import('@/services/_auth')
await import('@/store/user/store')
await import('@/layout/AuthProvider/MarketAuth/events')
```

如果改成顶部静态 import，可能引入初始化顺序或循环依赖问题。
