# 文件：src/server/routers/mobile/index.ts

## 它负责什么

`src/server/routers/mobile/index.ts` 是 LobeHub 移动端后端 tRPC API 的根路由聚合文件。

它本身不实现具体业务逻辑，而是把一组已经存在的业务 router 挂到 `mobileRouter` 下面，形成移动客户端访问 `/trpc/mobile` 时可用的 API 树。文件顶部注释也说明了它的定位：这是 Mobile App 使用的 Lobe Chat tRPC backend root router，并且“只包含移动客户端实际使用的 routers”。

可以把它理解为移动端 API 的“目录表”：

```ts
export const mobileRouter = router({
  agent: agentRouter,
  aiAgent: aiAgentRouter,
  aiChat: aiChatRouter,
  // ...
  user: userRouter,
});
```

移动端请求不会直接访问 `agentRouter`、`messageRouter`、`sessionRouter` 等文件，而是通过这个聚合后的 `mobileRouter` 暴露出去。例如移动端调用 `message.xxx`、`session.xxx`、`user.xxx` 这类 tRPC procedure，最终都依赖这里的挂载关系。

## 关键组成

这个文件的核心只有三类内容：导入、健康检查、导出根 router。

第一类是从 `../lambda/*` 导入大量已有业务 router：

```ts
import { agentRouter } from '../lambda/agent';
import { aiAgentRouter } from '../lambda/aiAgent';
import { aiChatRouter } from '../lambda/aiChat';
import { aiModelRouter } from '../lambda/aiModel';
import { aiProviderRouter } from '../lambda/aiProvider';
import { briefRouter } from '../lambda/brief';
import { chunkRouter } from '../lambda/chunk';
import { configRouter } from '../lambda/config';
import { documentRouter } from '../lambda/document';
import { fileRouter } from '../lambda/file';
import { homeRouter } from '../lambda/home';
import { knowledgeBaseRouter } from '../lambda/knowledgeBase';
import { marketRouter } from '../lambda/market';
import { messageRouter } from '../lambda/message';
import { sessionRouter } from '../lambda/session';
import { sessionGroupRouter } from '../lambda/sessionGroup';
import { taskRouter } from '../lambda/task';
import { topicRouter } from '../lambda/topic';
import { uploadRouter } from '../lambda/upload';
import { userRouter } from '../lambda/user';
```

这些 router 大多来自 `src/server/routers/lambda/`。从命名看，`lambda` 目录更像是通用的后端 tRPC router 集合，而 `mobile/index.ts` 则从里面挑选移动端需要的部分。根据当前片段推断，移动端并没有维护一套完全独立的业务 API，而是复用 lambda router，再额外组合移动端特有 router。

第二类是移动端特有的订阅 router：

```ts
import { mobileSubscriptionRouter } from '@/business/server/mobile-routers/mobileSubscription';
```

它来自 `src/business/server/mobile-routers/mobileSubscription.ts`。当前查看到的实现是：

```ts
export const mobileSubscriptionRouter = router({});
```

也就是说，这个 router 目前是空的，但已经预留了 `subscription` 这个移动端 API 命名空间。后续如果移动端需要订阅、会员、支付或 entitlement 相关接口，很可能会在这个 router 下扩展。

第三类是 tRPC 基础设施导入：

```ts
import { publicProcedure, router } from '@/libs/trpc/lambda';
```

`router` 是项目封装后的 `trpc.router`，用于创建 tRPC router。`publicProcedure` 是未强制登录的 procedure 基类，但它仍然会经过项目统一的 `openTelemetry` 中间件。也就是说，`publicProcedure` 不是“完全裸奔”的函数，而是项目标准 tRPC procedure 的公开版本。

文件里唯一直接定义的 procedure 是：

```ts
healthcheck: publicProcedure.query(() => "i'm live!"),
```

它用于移动端 tRPC 服务健康检查，调用成功时返回字符串 `"i'm live!"`。这个接口不需要登录，适合客户端或探活逻辑确认 `/trpc/mobile` 是否可用。

最终导出的对象是：

```ts
export const mobileRouter = router({
  agent: agentRouter,
  aiAgent: aiAgentRouter,
  aiChat: aiChatRouter,
  brief: briefRouter,
  aiModel: aiModelRouter,
  aiProvider: aiProviderRouter,
  chunk: chunkRouter,
  config: configRouter,
  document: documentRouter,
  file: fileRouter,
  healthcheck: publicProcedure.query(() => "i'm live!"),
  home: homeRouter,
  knowledgeBase: knowledgeBaseRouter,
  market: marketRouter,
  message: messageRouter,
  session: sessionRouter,
  sessionGroup: sessionGroupRouter,
  subscription: mobileSubscriptionRouter,
  task: taskRouter,
  topic: topicRouter,
  upload: uploadRouter,
  user: userRouter,
});
```

这里的 key 就是移动端 tRPC 客户端看到的一级命名空间。例如：

- `mobileRouter.agent` 对应 agent 相关接口
- `mobileRouter.aiChat` 对应 AI chat 相关接口
- `mobileRouter.message` 对应消息相关接口
- `mobileRouter.session` 对应会话相关接口
- `mobileRouter.topic` 对应话题相关接口
- `mobileRouter.subscription` 对应移动端订阅相关接口
- `mobileRouter.healthcheck` 是当前文件本地定义的健康检查接口

## 上下游关系

上游入口是 Next.js 后端 API route：

`src/app/(backend)/trpc/mobile/[trpc]/route.ts`

该文件中直接导入了这里的 `mobileRouter`：

```ts
import { mobileRouter } from '@/server/routers/mobile';
```

然后把它交给 `fetchRequestHandler`：

```ts
return fetchRequestHandler({
  createContext: () => createLambdaContext(req),
  endpoint: '/trpc/mobile',
  req: preparedReq,
  responseMeta: createResponseMeta,
  router: mobileRouter,
});
```

这说明 `mobileRouter` 对外暴露的 HTTP 入口是：

```txt
/trpc/mobile
```

并且支持：

```ts
export { handler as GET, handler as POST };
```

因此移动端可以通过 GET 或 POST 调用 tRPC procedure，具体请求分发由 `@trpc/server/adapters/fetch` 处理。

`route.ts` 还做了几件重要事情：

- 使用 `prepareRequestForTRPC(req)` 预处理请求，注释说明这是为了避免 Next.js 16 中 body stream 已被内部消费导致的错误。
- 使用 `createLambdaContext(req)` 创建 tRPC 上下文。
- 使用 `createResponseMeta` 生成响应元信息。
- 在 `onError` 中打印 mobile tRPC 错误路径、类型和错误对象。

下游是各个被挂载的业务 router，例如：

```txt
src/server/routers/lambda/agent
src/server/routers/lambda/aiChat
src/server/routers/lambda/message
src/server/routers/lambda/session
src/server/routers/lambda/topic
...
```

这些业务 router 内部才会真正定义 query、mutation、输入校验、认证中间件、数据库访问和业务服务调用。

以同目录的 `src/server/routers/mobile/topic.ts` 为参照，它展示了一个具体 router 通常长什么样：使用 `zod` 定义输入，用 `authedProcedure` 或 `publicProcedure` 定义 procedure，通过 `TopicModel` 操作数据库。例如 `createTopic`、`batchDelete`、`searchTopics`、`updateTopic` 等。但需要注意，`mobile/index.ts` 当前实际导入的是 `../lambda/topic`，不是同目录的 `./topic`。因此同目录 `mobile/topic.ts` 可能是历史遗留、备用实现或尚未接入的移动端专用 topic router；仅根据当前片段不能断定它仍在运行链路中。

tRPC 基础设施来自：

```txt
src/libs/trpc/lambda/index.ts
src/libs/trpc/lambda/init.ts
```

其中：

```ts
export const router = trpc.router;
export const publicProcedure = baseProcedure;
export const authedProcedure = baseProcedure.use(oidcAuth).use(userAuth);
```

`trpc` 初始化时使用了：

```ts
initTRPC.context<LambdaContext>().create({
  transformer: superjson,
  errorFormatter(...)
});
```

所以 `mobileRouter` 的所有 procedure 都共享 `LambdaContext` 上下文、`superjson` 序列化能力，以及统一错误格式化逻辑。

## 运行/调用流程

一次移动端 tRPC 调用的大致流程如下：

1. 移动客户端向 `/trpc/mobile` 发起 tRPC 请求。

2. 请求进入 Next.js route：

```txt
src/app/(backend)/trpc/mobile/[trpc]/route.ts
```

该 route 同时处理 GET 和 POST。

3. `route.ts` 调用 `prepareRequestForTRPC(req)` 生成适配 tRPC 的请求对象。

4. `fetchRequestHandler` 开始处理请求，并绑定：

```ts
router: mobileRouter
endpoint: '/trpc/mobile'
createContext: () => createLambdaContext(req)
```

5. `createLambdaContext(req)` 从请求中构造后端上下文。根据已查看到的测试片段，这个 context 可能包含：

```ts
userId
userAgent
marketAccessToken
oidcAuth
resHeaders
```

以及认证、API Key、OIDC、trace context 等相关信息。具体字段以 `src/libs/trpc/lambda/context` 实现为准。

6. tRPC 根据客户端请求路径，在 `mobileRouter` 上查找对应命名空间和 procedure。

例如请求：

```txt
message.someProcedure
```

会进入：

```ts
mobileRouter.message -> messageRouter.someProcedure
```

请求：

```txt
healthcheck
```

会直接进入当前文件定义的：

```ts
publicProcedure.query(() => "i'm live!")
```

7. 如果目标 procedure 是 `publicProcedure`，它不强制登录，但仍会经过基础中间件，例如 `openTelemetry`。

8. 如果目标 procedure 在下游 router 里使用了 `authedProcedure`，则会经过 `oidcAuth` 和 `userAuth`，要求用户身份有效。

9. 业务 router 内部执行具体逻辑，比如读写数据库、调用服务层、返回数据。

10. tRPC 使用 `superjson` 序列化响应，并通过 `createResponseMeta` 附加响应元信息。

从这个流程可以看出，`mobile/index.ts` 不关心单个接口怎么查数据库，也不关心认证细节。它只决定“移动端 API 可以访问哪些 router，以及这些 router 的一级路径叫什么”。

## 小白阅读顺序

建议按从入口到细节的顺序阅读，不要一开始就钻进每个业务 router。

第一步，先读本文件：

```txt
src/server/routers/mobile/index.ts
```

重点看 `mobileRouter = router({ ... })` 里有哪些 key。它告诉你移动端 API 的能力范围。

第二步，读移动端 tRPC HTTP 入口：

```txt
src/app/(backend)/trpc/mobile/[trpc]/route.ts
```

重点理解 `fetchRequestHandler` 如何把 HTTP 请求交给 `mobileRouter`。看到这里，你就能知道为什么移动端访问的是 `/trpc/mobile`。

第三步，读 tRPC 基础封装：

```txt
src/libs/trpc/lambda/index.ts
src/libs/trpc/lambda/init.ts
```

重点理解三个概念：

- `router`：创建 tRPC router
- `publicProcedure`：公开 procedure，不强制登录
- `authedProcedure`：需要用户认证的 procedure

第四步，挑一个下游业务 router 深入，比如：

```txt
src/server/routers/lambda/session
src/server/routers/lambda/message
src/server/routers/lambda/topic
src/server/routers/lambda/user
```

这些文件会告诉你每个命名空间下具体有哪些 query/mutation，以及输入输出如何定义。

第五步，再看模型或服务层。比如 topic 相关逻辑通常会继续下钻到：

```txt
src/database/models/topic
```

或者对应的 service 文件。这样你能把“API 路由 -> procedure -> model/service -> 数据库”的链路串起来。

第六步，最后再看移动端客户端调用方。当前通过 `rg` 查到的直接服务端调用方主要是 `route.ts`。实际客户端调用通常可能藏在 service、store 或 tRPC client 封装里，需要按具体 procedure 名继续搜索。例如想看 `session` 的移动端调用，可以搜索 `session.`、`trpc.session` 或项目内封装后的 API client 名称。

## 常见误区

误区一：以为这个文件实现了移动端业务逻辑。

实际上它只是 root router 聚合层。真正的业务逻辑在被导入的 `../lambda/*` router，以及这些 router 调用的 model、service、database 层中。

误区二：以为 `mobileRouter` 和 Web 端 router 完全独立。

从当前文件看，移动端大量复用了 `src/server/routers/lambda/` 下的 router。也就是说，移动端 API 是“挑选并组合已有后端能力”，不是从零实现一套移动端专属 API。

误区三：看到 `publicProcedure` 就认为没有任何中间件。

`publicProcedure` 不强制登录，但它来自：

```ts
const baseProcedure = trpc.procedure.use(openTelemetry);
```

所以它仍会经过项目统一的 `openTelemetry` 中间件。只是它不会像 `authedProcedure` 那样继续使用 `oidcAuth` 和 `userAuth`。

误区四：以为 `healthcheck` 可以代表所有业务接口可用。

`healthcheck` 只说明 `/trpc/mobile` 入口和 tRPC handler 基本可达。它不验证数据库、用户认证、下游模型、AI provider 或文件服务是否正常。因此它适合做轻量探活，不适合当作完整业务健康检查。

误区五：误用同目录的 `mobile/topic.ts`。

同目录存在：

```txt
src/server/routers/mobile/topic.ts
```

但当前 `mobile/index.ts` 挂载的是：

```ts
import { topicRouter } from '../lambda/topic';
```

不是：

```ts
import { topicRouter } from './topic';
```

所以移动端当前实际暴露的 `topic` 命名空间，应以 `src/server/routers/lambda/topic` 为准。`mobile/topic.ts` 是否仍有用途，需要继续查看 git 历史或更多引用；根据当前片段，只能判断它没有被 `mobile/index.ts` 使用。

误区六：在这里新增复杂业务 procedure。

这个文件的职责是组合 router。若要新增移动端业务能力，更合理的方式通常是：

- 如果是通用能力，先在 `src/server/routers/lambda/*` 中新增或扩展业务 router，再在 `mobileRouter` 中挂载。
- 如果是移动端专属能力，可以放到类似 `src/business/server/mobile-routers/*` 的位置，再在这里挂载一个命名空间。
- 不建议把复杂 query/mutation 直接写在 `mobile/index.ts`，否则 root router 会变成业务实现文件，职责会混乱。

误区七：改了 router key 却忽略客户端路径变化。

`tRPC` 的一级 key 会成为客户端调用路径的一部分。比如：

```ts
message: messageRouter
```

意味着客户端会按 `message.xxx` 调用。如果把 key 改成 `messages`，所有原本调用 `message.xxx` 的客户端都会失效。因此这里的命名空间是 API contract 的一部分，不能随意改名。
