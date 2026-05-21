# 文件：src/server/routers/lambda/index.ts

## 它负责什么

`src/server/routers/lambda/index.ts` 是 LobeHub 后端 tRPC “lambda” 路由树的总入口。它本身不实现具体业务逻辑，而是把大量领域子路由汇总成一个根路由 `lambdaRouter`，供前端、CLI、Next.js API Route、服务端内部 caller 统一调用。

可以把它理解为后端 RPC API 的目录表：每个 key 都会成为客户端可调用路径的一段。例如：

- `message: messageRouter` 对应客户端路径形态 `message.xxx`
- `config: configRouter` 对应 `config.xxx`
- `market: marketRouter` 对应 `market.xxx`
- `user: userRouter` 对应 `user.xxx`
- `healthcheck` 是直接定义在根路由上的公开 query

这个文件最后导出：

```ts
export const lambdaRouter = router({ ... });

export type LambdaRouter = typeof lambdaRouter;
```

`lambdaRouter` 是运行时使用的路由实例，`LambdaRouter` 是类型层面的 API 合约，会被客户端 `createTRPCClient<LambdaRouter>`、React Query tRPC client、CLI client 等消费。

## 关键组成

第一类 import 来自业务扩展目录：

```ts
import { accountDeletionRouter } from '@/business/server/lambda-routers/accountDeletion';
import { referralRouter } from '@/business/server/lambda-routers/referral';
import { spendRouter } from '@/business/server/lambda-routers/spend';
import { subscriptionRouter } from '@/business/server/lambda-routers/subscription';
import { taskTemplateRouter } from '@/business/server/lambda-routers/taskTemplate';
import { topUpRouter } from '@/business/server/lambda-routers/topUp';
```

这些路由来自 `@/business/server/lambda-routers/*`，看命名主要覆盖账号删除、推荐、消费、订阅、充值、任务模板等偏商业化或云服务相关能力。根据当前片段推断，它们与开源核心路由分层放置，方便把产品业务能力和通用后端能力拆开维护。

第二类 import 是 tRPC 基础设施：

```ts
import { publicProcedure, router } from '@/libs/trpc/lambda';
```

`router` 用来创建 tRPC router；`publicProcedure` 用来声明无需登录态保护的公开过程。当前文件里只有 `healthcheck` 直接使用 `publicProcedure`。

第三类 import 来自同目录下的大量领域子路由，例如：

```ts
import { agentRouter } from './agent';
import { aiChatRouter } from './aiChat';
import { configRouter } from './config';
import { fileRouter } from './file';
import { messageRouter } from './message';
import { sessionRouter } from './session';
import { userRouter } from './user';
```

这些子路由文件才是具体业务 API 的主要承载位置。`index.ts` 只负责挂载它们，不关心每个路由内部有哪些 procedure、用什么 schema、调用什么 service。

核心对象是：

```ts
export const lambdaRouter = router({
  agent: agentRouter,
  ...
  healthcheck: publicProcedure.query(() => "i'm live!"),
  ...
});
```

其中 `healthcheck` 是一个根级别的健康检查接口，调用路径通常是 `healthcheck`，返回固定字符串 `"i'm live!"`。因为它使用 `publicProcedure`，它不依赖用户登录上下文，适合用于简单探活。

最后的：

```ts
export type LambdaRouter = typeof lambdaRouter;
```

是 tRPC 类型推导的关键。客户端不需要手写接口定义，只要引用这个类型，就能获得完整的 procedure 路径、输入参数、输出结果的类型提示。

## 上下游关系

上游是 `@/libs/trpc/lambda` 提供的 tRPC 创建能力，以及各个领域子路由文件。当前文件从它们那里拿到已定义好的 router，再组合成总路由。

直接上游包括：

- `@/libs/trpc/lambda`：提供 `router`、`publicProcedure`
- `src/server/routers/lambda/agent.ts`、`message.ts`、`session.ts`、`user.ts` 等：提供具体领域路由
- `src/server/routers/lambda/config/index.ts`、`image/index.ts`、`market/index.ts`、`video/index.ts` 等目录型子路由：提供更复杂领域的聚合子路由
- `@/business/server/lambda-routers/*`：提供商业/云服务相关子路由

下游主要有四类。

第一类是 Next.js 后端 tRPC endpoint：

```ts
src/app/(backend)/trpc/lambda/[trpc]/route.ts
```

这个文件把 `lambdaRouter` 交给 `fetchRequestHandler`：

```ts
router: lambdaRouter
```

也就是说，浏览器或桌面端请求 `/trpc/lambda` 时，最终会进入这个根路由，再由 tRPC 根据 path 分发到具体子路由。

第二类是前端 tRPC client：

```ts
src/libs/trpc/client/lambda.ts
```

它引用：

```ts
import { type LambdaRouter } from '@/server/routers/lambda';
```

然后创建：

```ts
createTRPCClient<LambdaRouter>({ ... })
createTRPCReact<LambdaRouter>()
```

这让前端调用 `lambdaClient`、`lambdaQuery`、`lambdaQueryClient` 时具备端到端类型安全。比如前端写错 `config.getGlobalConfig` 这类 path，理论上会在类型层面暴露问题。

第三类是 CLI client：

```ts
apps/cli/src/api/client.ts
```

它同样引用 `LambdaRouter`，说明 CLI 也复用同一套后端 RPC 类型合约，而不是另起一套 REST 或手写 API 类型。

第四类是服务端内部 caller：

```ts
src/libs/trpc/mock.ts
src/app/(backend)/webapi/create-image/comfyui/route.ts
```

这些地方通过 `createCallerFactory(lambdaRouter)` 直接在服务端调用 router，绕过 HTTP client。这常用于测试、mock、或某些 webapi route 内部复用已有 tRPC procedure。

## 运行/调用流程

以浏览器调用一个 lambda tRPC 接口为例，流程大致是：

1. 前端代码通过 `src/libs/trpc/client/lambda.ts` 创建的 `lambdaClient` 或 `lambdaQuery` 发起调用。
2. 请求目标地址是 `/trpc/lambda`，并且会通过 `httpLink` 或 `httpBatchLink` 发送到后端。
3. Next.js 路由 `src/app/(backend)/trpc/lambda/[trpc]/route.ts` 接收 `GET` 或 `POST` 请求。
4. 该路由调用 `prepareRequestForTRPC(req)` 处理请求对象，避免 Next.js 16 中 body stream 被提前消费的问题。
5. `fetchRequestHandler` 使用 `createLambdaContext(req)` 创建 tRPC context。
6. `fetchRequestHandler` 接收 `router: lambdaRouter`，根据请求 path 找到对应 procedure。
7. 如果 path 是 `message.someProcedure`，就进入 `lambdaRouter` 上的 `message: messageRouter`；如果 path 是 `config.getGlobalConfig`，就进入 `configRouter`。
8. 子路由内部 procedure 执行业务逻辑，通常会继续调用 service、model、database、外部 provider 或其他 server 模块。
9. 结果经过 tRPC 序列化后返回给客户端；客户端侧 `superjson` 负责处理更复杂的数据类型序列化。

以 `healthcheck` 为例，流程更短：

1. 客户端请求 `/trpc/lambda/healthcheck` 这一类 path。
2. `fetchRequestHandler` 找到根路由上的 `healthcheck`。
3. `publicProcedure.query(() => "i'm live!")` 执行。
4. 返回字符串 `"i'm live!"`。

这个文件本身不会创建 HTTP 服务，也不会直接监听端口；真正承接 HTTP 请求的是 `src/app/(backend)/trpc/lambda/[trpc]/route.ts`。

## 小白阅读顺序

建议不要一上来逐个打开所有子路由。这个文件 import 很多，直接全读容易迷失。更合适的顺序是：

1. 先读 `src/server/routers/lambda/index.ts`，只关注它如何把 key 映射到 router。重点看 `router({ ... })` 对象。
2. 再读 `src/app/(backend)/trpc/lambda/[trpc]/route.ts`，理解 `lambdaRouter` 如何接到 HTTP endpoint 上。
3. 再读 `src/libs/trpc/client/lambda.ts`，理解前端怎样通过 `LambdaRouter` 获得类型安全，以及请求如何发到 `/trpc/lambda`。
4. 然后挑一个简单子路由读，例如 `src/server/routers/lambda/config/index.ts` 或 `src/server/routers/lambda/user.ts`。重点看子路由内部怎么声明 procedure。
5. 如果想理解认证、数据库上下文，再读 `src/libs/trpc/lambda/context.ts` 和 `src/libs/trpc/lambda/middleware/*`。
6. 如果想理解某个业务域，比如会话、消息、文件、知识库，再沿着对应 key 打开子路由：`session`、`message`、`file`、`knowledgeBase`。
7. 最后再看测试目录 `src/server/routers/lambda/__tests__/*`，通过测试用例反推 procedure 的输入输出和边界行为。

一个具体例子：如果你想理解“消息 API”，阅读路线可以是：

```text
src/server/routers/lambda/index.ts
  -> message: messageRouter
src/server/routers/lambda/message.ts
  -> message router 内部 procedure
相关 service/model/test
```

如果你想理解“前端怎么调用后端”，阅读路线可以是：

```text
src/libs/trpc/client/lambda.ts
  -> LambdaRouter 类型
src/server/routers/lambda/index.ts
  -> 真实路由树
src/app/(backend)/trpc/lambda/[trpc]/route.ts
  -> HTTP 入口
```

## 常见误区

第一个误区是把这个文件当成业务实现文件。它不是。这里几乎没有业务逻辑，只有路由聚合。真正的输入校验、权限控制、数据库读写、外部 API 调用，大多在具体子路由、service、model 或 middleware 中。

第二个误区是认为添加一个新 router 文件就能自动生效。不能。新增 `src/server/routers/lambda/foo.ts` 后，还必须在这个 `index.ts` 中 import 并挂到 `router({ foo: fooRouter })`，否则客户端无法通过 `foo.xxx` 调到它。

第三个误区是随意改 `router({ ... })` 里的 key。这里的 key 是 RPC path 的一部分，改名会直接影响前端、CLI、测试和服务端 caller。例如把 `user` 改成 `users`，所有 `user.xxx` 调用都会失效，`LambdaRouter` 类型也会随之变化。

第四个误区是忽略 `LambdaRouter` 的影响范围。它不仅服务浏览器前端，也被 `apps/cli/src/api/client.ts` 等外部入口使用。这个类型就是跨端 API 合约，变更时要考虑 CLI、桌面端、web 端和测试环境。

第五个误区是误解 `lambda` 的含义。根据当前代码片段，它主要表示这套 tRPC 后端路由命名空间和 endpoint：`/trpc/lambda`。不要仅凭名字就推断它一定运行在 AWS Lambda 上；实际运行入口是 Next.js route handler。

第六个误区是以为所有子路由都需要登录。当前文件里只有 `healthcheck` 明确使用了 `publicProcedure`。其他子路由内部可能使用 public、protected、admin、market auth、OIDC 等不同 procedure 或 middleware，必须进入对应子路由和 `@/libs/trpc/lambda` 的 middleware 体系才能判断。

第七个误区是把 `@/business/server/lambda-routers/*` 和 `src/server/routers/lambda/*` 混为一层。根据当前片段推断，`@/business` 下的路由更偏产品商业能力或部署相关扩展，而 `src/server/routers/lambda` 下是主仓库的核心领域路由。阅读时应先分清来源，再判断它们的维护边界。
