# 目录：src/server/routers/lambda/video

## 它负责什么

`src/server/routers/lambda/video` 是 LobeHub 服务端 lambda TRPC 路由中的“视频生成任务创建入口”。它不直接完成视频生成，而是负责把一次用户发起的视频生成请求转成一组可追踪、可计费、可异步回调/轮询的后端任务。

核心职责集中在 `index.ts` 的 `videoRouter.createVideo` mutation：

- 校验前端传入的视频生成参数，例如 `provider`、`model`、`generationTopicId`、`params.prompt`、`imageUrl`、`endImageUrl`、`duration`、`resolution`、`seed` 等。
- 解析业务模型映射，把用户侧/品牌侧模型 ID 转成真实 provider 模型 ID。
- 检查 LobeHub 品牌模型是否仍在 model bank 中可用于 `video` 能力。
- 将图片 URL 归一化为文件 key，用于数据库持久化；开发环境下再转回 S3 可访问 URL，方便 provider API 调用。
- 在生成前做预扣费，防止并发滥用额度。
- 在数据库事务中创建 `generationBatches`、`generations`、`asyncTasks`，并把 generation 绑定到 async task。
- 调用模型运行时 `modelRuntime.createVideo` 提交视频生成任务。
- 根据 provider 返回结果选择 webhook 等待或后台轮询。
- 提交失败时记录 `AsyncTaskError`，并尝试执行失败后的扣费回滚/结算逻辑。

这个目录本质上是“视频生成请求进入后端后的编排层”，负责连接鉴权、数据库、文件服务、模型运行时、计费系统和异步任务系统。

## 关键组成

目录内只有三个文件：

- `index.ts`
- `error.ts`
- `error.test.ts`

`index.ts` 是主入口，导出：

```ts
export const videoRouter = router({ ... });
export type VideoRouter = typeof videoRouter;
```

其中最重要的是 `createVideo`：

```ts
createVideo: videoProcedure.input(createVideoInputSchema).mutation(...)
```

`videoProcedure` 基于 `authedProcedure`，并叠加了 `serverDatabase` middleware。它要求调用者已登录，并在上下文中注入：

- `ctx.serverDB`
- `ctx.userId`
- `asyncTaskModel: new AsyncTaskModel(ctx.serverDB, ctx.userId)`
- `fileService: new FileService(ctx.serverDB, ctx.userId)`

`createVideoInputSchema` 使用 `zod` 定义输入结构：

```ts
{
  generationTopicId: string;
  provider: string;
  model: string;
  params: {
    prompt: string;
    imageUrl?: string | null;
    endImageUrl?: string | null;
    aspectRatio?: string;
    duration?: number;
    resolution?: string;
    seed?: number | null;
    cameraFixed?: boolean;
    generateAudio?: boolean;
  }
}
```

`params` 使用 `.passthrough()`，说明它允许额外 provider 参数透传。也就是说，这个 router 只验证通用字段，不试图穷举所有 provider 的视频参数。

`error.ts` 提供一个小型错误工厂：

```ts
createVideoTaskSubmitError(error, providerContentPolicyMessage?)
```

它根据是否存在 provider 内容安全错误信息，生成两类 `AsyncTaskError`：

- `AsyncTaskErrorType.TaskTriggerError`：普通任务提交失败，例如 API timeout。
- `AsyncTaskErrorType.ProviderContentModeration`：provider 内容审核拒绝。

`error.test.ts` 覆盖了这两个分支，确保错误类型和错误文案符合预期。

## 上下游关系

上游挂载点是 `src/server/routers/lambda/index.ts`。该文件引入：

```ts
import { videoRouter } from './video';
```

并将其挂到 lambda router 的 `video` 字段下：

```ts
video: videoRouter
```

因此外部 TRPC 调用路径根据当前片段可理解为类似：

```ts
lambda.video.createVideo
```

根据搜索结果，`src/services/video.ts` 是可能的客户端 service 调用方，但当前任务没有进一步展开该文件；因此这里根据当前片段推断，前端不会直接访问数据库或模型运行时，而是通过 service 调用 TRPC 的 `video.createVideo`。

下游依赖比较多，说明这个 router 是编排层：

- 模型与 provider：
  - `resolveBusinessModelMapping`
  - `buildMappedBusinessModelFields`
  - `loadModels`
  - `isProviderModelAvailable`
  - `initModelRuntimeFromDB`
- 数据库：
  - `generationBatches`
  - `generations`
  - `asyncTasks`
  - `AsyncTaskModel`
  - `getServerDB`
- 文件：
  - `FileService.getKeyFromFullUrl`
  - `FileService.getFullFileUrl`
- 计费：
  - `chargeBeforeGenerate`
  - `chargeAfterGenerate`
  - `getVideoFreeQuota` 被 import，但在已读片段中没有看到直接使用；可能在文件后段或历史遗留中使用，根据当前片段不能确认。
- 异步任务：
  - `AsyncTaskStatus`
  - `AsyncTaskType.VideoGeneration`
  - `processBackgroundVideoPolling`
  - `next/server` 的 `after`
- 错误处理：
  - `getProviderContentPolicyErrorMessage`
  - `createVideoTaskSubmitError`
  - `TRPCError`
  - `ChatErrorType.LobeHubModelDeprecated`

它和 webhook 系统也有关系。`createVideo` 会生成一次性 `webhookToken`，并拼出：

```ts
/api/webhooks/video/${provider}?token=${webhookToken}
```

这个 callback URL 会传给 provider。provider 若支持 webhook，后续应由对应 webhook 路由更新任务结果。

## 运行/调用流程

一次 `createVideo` 调用大致分为 8 步。

第一步，TRPC 鉴权与上下文准备。调用必须经过 `authedProcedure`，并通过 `serverDatabase` middleware 拿到服务端数据库连接。随后 `videoProcedure` 给 ctx 增加 `asyncTaskModel` 和 `fileService`。

第二步，入参校验。`createVideoInputSchema` 要求有 `generationTopicId`、`provider`、`model` 和 `params.prompt`。视频参数中的图片、时长、分辨率、种子等字段是可选项。

第三步，模型映射和可用性检查。代码先调用：

```ts
resolveBusinessModelMapping(provider, model)
```

得到 `resolvedModelId`。如果 `provider === BRANDING_PROVIDER`，还会通过 `loadModels()` 和 `isProviderModelAvailable(..., 'video')` 检查该品牌模型是否仍然支持视频生成。不支持时抛出 `TRPCError`，message 为 `ChatErrorType.LobeHubModelDeprecated`。

第四步，图片地址处理。用户传入的 `params.imageUrl` 和 `params.endImageUrl` 可能是完整 URL。服务端会尝试用 `fileService.getKeyFromFullUrl` 转成文件 key，并写入 `configForDatabase`，这样数据库存储的是稳定 key，而不是临时完整 URL。开发环境下又会用 `fileService.getFullFileUrl` 把 key 转成 S3 URL，供 provider API 访问。

第五步，预扣费。调用：

```ts
chargeBeforeGenerate({
  generationTopicId,
  model,
  params,
  provider,
  userId,
})
```

如果返回 `errorBatch`，说明扣费或额度检查失败，router 会直接返回该错误 batch，不再创建任务。否则拿到 `prechargeResult`，后续会写入 async task metadata。

第六步，数据库事务创建记录。事务中依次创建：

1. `generationBatches`：保存本次生成批次，包含 `config`、`generationTopicId`、`model`、`prompt`、`provider`、`userId`。
2. `generations`：视频生成当前固定创建单条 generation，注释中写明 “video is always 1”。
3. `asyncTasks`：创建 `AsyncTaskType.VideoGeneration` 类型任务，状态为 `Pending`，metadata 中保存 `precharge` 和 `webhookToken`。
4. 更新 `generations.asyncTaskId`，把 generation 和 async task 关联起来。

这里使用事务的意义是保证 batch、generation、async task 和它们之间的绑定要么一起成功，要么一起失败，避免生成记录和异步任务脱节。

第七步，提交 provider 任务。代码初始化模型运行时：

```ts
initModelRuntimeFromDB(serverDB, userId, provider)
```

然后构造 callback URL，调用：

```ts
modelRuntime.createVideo(
  {
    callbackUrl,
    model: resolvedModelId,
    params: generationParams,
  },
  { metadata: { trigger: RequestTrigger.Video } },
)
```

返回结果里关键字段是 `inferenceId`，以及可选的 `useWebhook`。

第八步，选择异步完成方式。

如果 `response.useWebhook` 为真，说明 provider 会回调 webhook。此时只把 async task 更新为 `Processing`，并记录 `inferenceId`，等待 webhook 接管后续状态更新。

如果 provider 返回了 `response` 但不是 webhook 模式，则认为是轮询模式。代码同样把 async task 更新为 `Processing`，然后通过 Next.js 的 `after(async () => { ... })` 注册后台轮询任务，调用：

```ts
processBackgroundVideoPolling(db, {
  asyncTaskCreatedAt,
  asyncTaskId,
  generationBatchId,
  generationId,
  generationTopicId,
  inferenceId,
  model,
  prechargeResult,
  provider,
  userId,
})
```

如果提交 provider 任务失败，会进入 `catch`。它先尝试识别 provider 内容安全错误：

```ts
getProviderContentPolicyErrorMessage({
  error: e,
  provider,
  trigger: RequestTrigger.Video,
  userId,
})
```

然后更新 async task 为 `Error`，错误对象由 `createVideoTaskSubmitError` 创建。如果之前已经预扣费，还会调用 `chargeAfterGenerate`，传入 `isError: true`，尝试完成失败场景下的计费修正。

## 小白阅读顺序

建议按下面顺序读：

1. 先读 `src/server/routers/lambda/video/error.ts`  
   这个文件最小，能先理解视频任务提交失败时错误对象的形状。

2. 再读 `src/server/routers/lambda/video/error.test.ts`  
   测试会告诉你这个错误工厂期望产生哪两类错误：普通触发失败和 provider 内容审核失败。

3. 再读 `src/server/routers/lambda/video/index.ts` 的 import 区域  
   import 能快速暴露这个 router 的协作者：TRPC、DB、文件服务、模型运行时、计费、异步任务、webhook/轮询。

4. 读 `videoProcedure` 和 `createVideoInputSchema`  
   这里能理解“谁能调用”和“调用时要传什么”。

5. 分段读 `createVideo`  
   不要一口气读完整个 mutation。建议按“模型检查 -> 图片处理 -> 预扣费 -> DB 事务 -> provider 提交 -> webhook/轮询 -> 错误处理”的顺序画流程图。

6. 最后看上级挂载 `src/server/routers/lambda/index.ts`  
   只需要确认 `videoRouter` 是如何挂到总 router 上的，不必一开始就陷入整个 lambda router。

## 常见误区

第一个误区：以为这个目录负责“生成视频”。实际视频生成发生在外部 provider 或模型运行时中。这里负责的是创建任务、提交任务、记录状态、处理回调/轮询和计费。

第二个误区：把 `generationBatches`、`generations`、`asyncTasks` 看成重复记录。它们职责不同：`generationBatches` 表示一次生成批次，`generations` 表示具体生成结果项，`asyncTasks` 表示异步执行状态。视频当前只创建一个 generation，但仍沿用统一的 generation 数据模型。

第三个误区：忽略预扣费。`chargeBeforeGenerate` 在真正提交 provider 之前执行，是并发控制和额度控制的关键。如果只看 `modelRuntime.createVideo`，会漏掉商业计费链路。

第四个误区：认为所有 provider 都走 webhook。代码明确区分两类策略：`useWebhook` 为真时等待回调；否则用 `after()` 触发后台轮询。不同 provider 的异步完成机制可能不同。

第五个误区：以为数据库里直接保存图片完整 URL。实际代码会尽量把 `imageUrl` 和 `endImageUrl` 转成文件 key 写入 `configForDatabase`。开发环境下为了 provider 能访问，又临时把它们转成 S3 URL 放进 `generationParams`。

第六个误区：认为 `model` 一定就是最终 provider 模型 ID。这里先经过 `resolveBusinessModelMapping` 得到 `resolvedModelId`，提交给 runtime 的是解析后的模型；计费失败处理里也会用 `buildMappedBusinessModelFields` 同时记录 requested/resolved 模型关系。

第七个误区：把内容审核失败当成普通 API 错误。`createVideoTaskSubmitError` 会在有 provider 内容安全文案时返回 `AsyncTaskErrorType.ProviderContentModeration`，这会影响前端或任务系统如何展示失败原因。

第八个误区：看到 `params.passthrough()` 就以为没有校验。实际它校验了通用必需字段，额外字段只是为了兼容不同视频 provider 的差异化参数。
