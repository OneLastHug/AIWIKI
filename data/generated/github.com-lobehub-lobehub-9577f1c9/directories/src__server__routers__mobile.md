# 目录：src/server/routers/mobile

## 它负责什么

`src/server/routers/mobile` 是 LobeHub 后端专门给移动端 App 暴露的 tRPC router 入口目录。它的核心职责不是重新实现一套完整后端能力，而是从现有 `src/server/routers/lambda/*` 路由中挑选移动端实际需要的子 router，组合成一个更小的 `mobileRouter`，再通过 `/trpc/mobile` endpoint 对外提供给移动客户端调用。

这个目录目前只有两个文件：

- `src/server/routers/mobile/index.ts`
- `src/server/routers/mobile/topic.ts`

其中真正被 `/trpc/mobile` 挂载的是 `index.ts` 导出的 `mobileRouter`。它聚合了 agent、AI chat、model/provider、session、message、topic、file、upload、knowledge base、home、market、user、subscription 等移动端会用到的能力。

需要特别注意：`src/server/routers/mobile/topic.ts` 虽然定义了一个移动端专用的 `topicRouter`，但当前 `index.ts` 实际导入的是 `../lambda/topic`，不是本目录下的 `./topic`。因此，根据当前片段推断，`mobile/topic.ts` 目前更像是历史遗留、备用实现或尚未接入的移动端精简 topic router，不能把它当成当前线上 `/trpc/mobile.topic.*` 的真实实现入口。

## 关键组成

`index.ts` 是本目录的主入口。文件顶部注释已经说明它是 “Lobe Chat tRPC-backend for Mobile App” 的 root router，并且只包含移动客户端实际使用的 routers。它从 `@/libs/trpc/lambda` 引入 `router` 和 `publicProcedure`，然后把多个子 router 组合成一个对象：

- `agent: agentRouter`
- `aiAgent: aiAgentRouter`
- `aiChat: aiChatRouter`
- `aiModel: aiModelRouter`
- `aiProvider: aiProviderRouter`
- `brief: briefRouter`
- `chunk: chunkRouter`
- `config: configRouter`
- `document: documentRouter`
- `file: fileRouter`
- `home: homeRouter`
- `knowledgeBase: knowledgeBaseRouter`
- `market: marketRouter`
- `message: messageRouter`
- `session: sessionRouter`
- `sessionGroup: sessionGroupRouter`
- `subscription: mobileSubscriptionRouter`
- `task: taskRouter`
- `topic: topicRouter`
- `upload: uploadRouter`
- `user: userRouter`
- `healthcheck: publicProcedure.query(() => "i'm live!")`

这些子 router 大多来自 `src/server/routers/lambda/*`。也就是说，移动端 router 与主站 lambda router 共享大量后端能力，只是在聚合层做了范围裁剪。例外之一是 `subscription`，它来自 `@/business/server/mobile-routers/mobileSubscription`，说明移动端订阅能力有独立的业务适配。

`topic.ts` 定义了一个单独的 `topicRouter`。它使用 `authedProcedure.use(serverDatabase)` 创建 `topicProcedure`，在 tRPC context 中注入 `TopicModel`：

```ts
ctx: { topicModel: new TopicModel(ctx.serverDB, ctx.userId) }
```

这个 router 提供的 topic 操作包括：

- `batchCreateTopics`
- `batchDelete`
- `batchDeleteBySessionId`
- `cloneTopic`
- `countTopics`
- `createTopic`
- `getAllTopics`
- `getTopics`
- `hasTopics`
- `rankTopics`
- `removeAllTopics`
- `removeTopic`
- `searchTopics`
- `updateTopic`

它整体是围绕 `TopicModel` 的轻量 CRUD/查询封装。大多数 procedure 都要求登录态，只有 `getTopics` 使用了 `publicProcedure`，并通过 `ctx.userId` 自行判断是否有用户；如果没有用户，直接返回空数组。该文件中还有一个 TODO：`getTopics` 应该改成 `authedProcedure`，说明这里的鉴权模型和其他 topic 操作并不完全一致。

不过再次强调：当前 `mobileRouter` 没有导入这个 `topic.ts`，而是导入 `../lambda/topic`。所以实际移动端 `topic` 能力应以 `src/server/routers/lambda/topic.ts` 为准，本文件只能作为理解移动端曾经/可能的 topic 精简实现的参考。

## 上下游关系

上游入口是 Next.js App Router 下的 tRPC route handler：

`src/app/(backend)/trpc/mobile/[trpc]/route.ts`

这个 route handler 使用 `fetchRequestHandler` 接收 GET/POST 请求，关键配置包括：

- `endpoint: '/trpc/mobile'`
- `createContext: () => createLambdaContext(req)`
- `router: mobileRouter`
- `responseMeta: createResponseMeta`
- `req: prepareRequestForTRPC(req)`

因此，移动端客户端请求 `/trpc/mobile/...` 时，会先进入这个 Next.js route handler，然后由 tRPC 根据路径分发到 `mobileRouter` 中的具体子 router 和 procedure。

`mobileRouter` 的下游主要是各个 lambda 子 router。例如：

- `mobileRouter.message.*` 实际进入 `src/server/routers/lambda/message.ts`
- `mobileRouter.session.*` 实际进入 `src/server/routers/lambda/session.ts`
- `mobileRouter.topic.*` 当前实际进入 `src/server/routers/lambda/topic.ts`
- `mobileRouter.user.*` 实际进入 `src/server/routers/lambda/user.ts`

再往下，这些 lambda router 通常会通过 `authedProcedure`、`serverDatabase` 等中间件拿到登录用户、数据库连接和运行上下文，然后调用数据库 model、repository 或业务 service。

与完整 `lambdaRouter` 相比，`mobileRouter` 是一个子集。`src/server/routers/lambda/index.ts` 暴露了更多能力，例如 `apiKey`、`plugin`、`image`、`video`、`notification`、`share`、`usage`、`oauthDeviceFlow`、`accountDeletion`、`topUp` 等。移动端 router 没有把这些全部暴露出来，这有两个含义：

1. 移动端 API 面更窄，只开放 App 当前需要的后端能力。
2. 如果移动端要调用一个新领域能力，不能只实现 lambda router，还要检查是否需要加到 `mobileRouter` 聚合入口里。

## 运行/调用流程

移动端一次 tRPC 调用的大致链路如下：

1. 移动端客户端发起请求到 `/trpc/mobile`，路径中包含具体 procedure，例如根据 tRPC 客户端生成的调用路径访问 `topic.xxx`、`message.xxx`、`session.xxx`。
2. `src/app/(backend)/trpc/mobile/[trpc]/route.ts` 中的 handler 接收请求。
3. handler 调用 `prepareRequestForTRPC(req)` 克隆/适配请求。注释说明这是为了避免 Next.js 16 中请求 body stream 被内部机制消费后出现 “Response body object should not be disturbed or locked” 一类问题。
4. `fetchRequestHandler` 创建 tRPC 请求处理环境。
5. `createLambdaContext(req)` 根据当前 `NextRequest` 生成 tRPC context，后续 procedure 可通过 `ctx` 访问用户、数据库、请求相关信息。
6. tRPC 根据请求路径进入 `mobileRouter`。
7. `mobileRouter` 再把请求分发给对应子 router，例如 `topic`、`message`、`session`。
8. 子 router 内部的 procedure 校验 input。大多数文件会使用 `zod` schema 来约束输入结构。
9. 如果 procedure 使用 `authedProcedure`，则会要求用户已认证；如果叠加 `serverDatabase` 中间件，则会把 server DB 注入到 context。
10. procedure 调用对应 model/repository/service 执行业务逻辑，并把结果返回给 tRPC handler。
11. handler 通过 `createResponseMeta` 等机制生成响应元信息，最终返回给移动端。

以当前未挂载的 `mobile/topic.ts` 为例，它的内部流程是：

1. `topicProcedure` 基于 `authedProcedure` 创建。
2. `serverDatabase` 中间件给 `ctx` 注入 `serverDB`。
3. 自定义 middleware 再创建 `new TopicModel(ctx.serverDB, ctx.userId)`，放到 `ctx.topicModel`。
4. 各个 procedure 只负责 input 校验和调用 `ctx.topicModel`。
5. 例如 `createTopic` 校验 `title`、`sessionId`、`groupId`、`messages` 等字段后，调用 `ctx.topicModel.create(input)`，最后返回新 topic 的 `id`。
6. `updateTopic` 校验 `{ id, value }` 后调用 `ctx.topicModel.update(input.id, input.value)`。

这个模式符合仓库中 tRPC router 的常见写法：router 层做输入校验和上下文组装，真正的数据读写交给 model/repository。

## 小白阅读顺序

建议按这个顺序读：

1. 先看 `src/app/(backend)/trpc/mobile/[trpc]/route.ts`  
   这里能明白 `/trpc/mobile` 是怎么被 Next.js 接住，并交给 tRPC 的。

2. 再看 `src/server/routers/mobile/index.ts`  
   这是移动端 tRPC API 的总目录。先不要钻进每个子 router，只需要记住它是“移动端可访问的 router 白名单/聚合表”。

3. 对比 `src/server/routers/lambda/index.ts`  
   这样可以看出移动端 router 和完整 lambda router 的区别。完整 lambda router 暴露的业务域更多，mobile router 只挑了其中一部分。

4. 选择一个子 router 深入，例如 `src/server/routers/lambda/topic.ts` 或 `src/server/routers/lambda/session.ts`  
   因为 `mobileRouter` 当前多数能力都直接复用 lambda router，所以真正的业务逻辑要去 lambda 子 router 里看。

5. 最后再看 `src/server/routers/mobile/topic.ts`  
   阅读它时要带着一个问题：它为什么存在但没有被 `index.ts` 挂载？这个文件可以帮助理解一个“移动端精简 topic router”会怎么写，但不要默认它就是当前移动端 topic API 的实际来源。

如果只想快速建立地图，可以优先记住三层结构：

- HTTP 入口：`src/app/(backend)/trpc/mobile/[trpc]/route.ts`
- 移动端 router 聚合：`src/server/routers/mobile/index.ts`
- 具体业务实现：`src/server/routers/lambda/*` 和部分 `@/business/server/mobile-routers/*`

## 常见误区

第一个误区是以为 `src/server/routers/mobile/topic.ts` 一定被移动端使用。当前不是这样。`mobile/index.ts` 中的 `topic` 导入来自 `../lambda/topic`，不是 `./topic`。所以排查移动端 topic 行为时，应优先看 `src/server/routers/lambda/topic.ts`。

第二个误区是把 `mobileRouter` 当成一套独立后端。它更准确的定位是移动端 API 聚合层。大部分业务仍在 lambda router、model、repository、business router 中实现。

第三个误区是新增 lambda router 后以为移动端自动可用。不会自动可用。移动端只能访问 `mobileRouter` 中显式挂载的 key。如果新增业务要给移动端调用，需要确认是否把对应 router 加到 `src/server/routers/mobile/index.ts`。

第四个误区是忽略 `/trpc/mobile` 和普通 `/trpc` 的差异。它们可能共享 `createLambdaContext`、`fetchRequestHandler` 等机制，但挂载的 root router 不同，因此可调用的 procedure 范围也不同。

第五个误区是只看 router，不看 procedure 类型。`publicProcedure`、`authedProcedure`、`serverDatabase` 的组合决定了鉴权、数据库上下文和用户态行为。例如 `mobile/topic.ts` 中大多数 topic 操作走 `topicProcedure`，但 `getTopics` 是 `publicProcedure` 加手动 `ctx.userId` 判断，这种差异会影响未登录请求的返回方式。

第六个误区是把 `healthcheck` 理解成业务接口。它只是一个公开 query，返回 `"i'm live!"`，主要用于确认移动端 tRPC handler 是否存活，不代表用户态、数据库或具体业务链路都正常。
