# 文件：src/server/routers/lambda/video/index.ts

## 它负责什么

`src/server/routers/lambda/video/index.ts` 定义了 lambda 侧的 `videoRouter`，是前端发起“创建视频生成任务”的主要后端入口。它不直接等待视频生成完成，而是完成一次视频任务的“提交阶段”：校验输入、解析业务模型、检查模型可用性、处理图片 URL、预扣费、创建数据库记录、调用模型运行时提交任务，然后根据供应商能力决定后续由 webhook 回调还是后台轮询接管。

这个文件暴露两个 TRPC procedure：

- `createVideo`：创建一次视频生成任务，返回 `generationBatch` 和 `generation` 初始记录。
- `getVideoFreeQuota`：查询指定模型的视频免费额度。

从职责边界看，它更像“视频生成任务编排器”，不是视频文件处理器。真正的视频下载、转存、封面提取、文件资产写入等完成态处理，位于后续 webhook 或 polling 服务中。

## 关键组成

### `videoProcedure`

```ts
const videoProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
  ...
});
```

这是 `createVideo` 使用的基础 procedure。它叠加了两层能力：

- `authedProcedure`：要求用户已登录，后续可从 `ctx.userId` 取当前用户。
- `serverDatabase` middleware：注入 `ctx.serverDB`，让 procedure 可以访问服务端数据库。

随后它额外向 `ctx` 注入两个服务实例：

- `asyncTaskModel: new AsyncTaskModel(ctx.serverDB, ctx.userId)`
- `fileService: new FileService(ctx.serverDB, ctx.userId)`

`asyncTaskModel` 用于更新异步任务状态、写入 `inferenceId`、错误信息等；`fileService` 用于把前端传来的文件完整 URL 与数据库/对象存储中的 key 互相转换。

### `createVideoInputSchema`

```ts
const createVideoInputSchema = z.object({
  generationTopicId: z.string(),
  model: z.string(),
  params: z.object({...}).passthrough(),
  provider: z.string(),
});
```

这是 `createVideo` 的入参 schema。核心字段含义：

- `generationTopicId`：视频生成所属的话题 ID。
- `provider`：模型供应商，例如 LobeHub branding provider、OpenAI compatible provider 等。
- `model`：调用方请求的模型 ID。
- `params`：视频生成参数，至少包含 `prompt`，还可能包含：
  - `imageUrl`：首帧图。
  - `endImageUrl`：尾帧图。
  - `aspectRatio`
  - `duration`
  - `generateAudio`
  - `resolution`
  - `seed`
  - `cameraFixed`

这里的 `params` 使用 `.passthrough()`，说明 schema 只声明了当前 router 关心的通用字段，但允许模型供应商携带额外参数。小白容易误以为未列出的字段会被丢弃，实际上不会。

`CreateVideoServicePayload` 是这个 schema 推导出的类型，被客户端服务层 `src/services/video.ts` 复用：

```ts
export type CreateVideoServicePayload = z.infer<typeof createVideoInputSchema>;
```

这使前端调用 `lambdaClient.video.createVideo.mutate(payload)` 时可以获得类型约束。

### `createVideo`

`createVideo` 是文件核心。它的主要步骤如下：

1. 从 `ctx` 和 `input` 中取出 `userId`、`serverDB`、`asyncTaskModel`、`fileService`、`generationTopicId`、`provider`、`model`、`params`。
2. 调用 `resolveBusinessModelMapping(provider, model)` 得到 `resolvedModelId`。
3. 如果 `provider === BRANDING_PROVIDER`，检查 `resolvedModelId` 是否仍存在于 model bank 的 video 模型列表中；不可用则抛出 `TRPCError`，错误类型为 `ChatErrorType.LobeHubModelDeprecated`。
4. 将 `params.imageUrl` / `params.endImageUrl` 从完整 URL 尽量转换为对象存储 key，用于数据库保存。
5. 在开发环境中，把本地代理 URL 转为真实 S3 URL，用于模型供应商 API 访问。
6. 调用 `chargeBeforeGenerate` 做预扣费，防止并发滥用预算。
7. 生成一次性 `webhookToken`，用于 webhook 回调校验。
8. 在数据库事务中创建：
   - `generationBatches`
   - `generations`
   - `asyncTasks`
   - 并把 `generations.asyncTaskId` 关联到刚创建的异步任务。
9. 初始化模型运行时 `initModelRuntimeFromDB(serverDB, userId, provider)`。
10. 拼接 callback URL：`${callbackBaseUrl}/api/webhooks/video/${provider}?token=${webhookToken}`。
11. 调用 `modelRuntime.createVideo(...)` 提交视频生成任务。
12. 根据返回结果决定异步策略：
   - `response.useWebhook === true`：等待供应商 webhook 回调。
   - 否则：注册 `after(...)` 后台轮询任务，调用 `processBackgroundVideoPolling(...)`。
13. 如果提交模型任务失败：
   - 把 `asyncTask` 标记为 `Error`。
   - 通过 `createVideoTaskSubmitError(...)` 写入错误。
   - 如有预扣费结果，则调用 `chargeAfterGenerate({ isError: true, ... })` 做失败后的费用处理。
14. 最终返回已创建的 batch 和 generation。

一个重要细节：即使模型任务提交失败，代码也不会向客户端重新抛出错误，而是返回已经创建的 batch/generation，并把异步任务状态写成 `Error`。这说明前端展示很可能依赖 generation 列表和 async task 状态来显示失败，而不是只靠 mutation 的异常。

### `getVideoFreeQuota`

```ts
getVideoFreeQuota: authedProcedure
  .input(z.object({ model: z.string() }))
  .query(async ({ ctx, input }) => {
    return getVideoFreeQuota(ctx.userId, input.model);
  }),
```

这是一个较薄的查询接口，只要求登录，不使用 `serverDatabase` 中间件。它把当前用户 ID 和模型 ID 传给业务函数 `getVideoFreeQuota`，用于查询免费额度。

### `createVideoTaskSubmitError`

同目录 `error.ts` 提供：

```ts
createVideoTaskSubmitError(error, providerContentPolicyMessage?)
```

它把模型任务提交阶段的异常统一包装成 `AsyncTaskError`：

- 如果存在供应商内容审核错误信息，则类型为 `AsyncTaskErrorType.ProviderContentModeration`。
- 否则类型为 `AsyncTaskErrorType.TaskTriggerError`。
- 错误消息默认为 `Failed to submit video task: ...`。

也就是说，这个 router 把“提交任务失败”和“后台轮询失败”区分开了。提交阶段失败由 lambda router 写入 `TaskTriggerError`；后续 async polling 失败在 `src/server/routers/async/video.ts` 中更偏向写入 `ServerError` 或内容审核错误。

## 上下游关系

### 上游调用方

直接客户端服务层是 `src/services/video.ts`：

```ts
lambdaClient.video.createVideo.mutate(payload)
```

`AiVideoService.createVideo(payload)` 使用了从本文件导出的 `CreateVideoServicePayload` 类型，因此前后端共享同一个输入结构。

更上层是 Zustand action：`src/store/video/slices/createVideo/action.ts`。其中：

- `createVideo()` 从 video store 读取当前参数、provider、model、active generation topic。
- 如果没有 topic，会先创建 topic 并切换过去。
- 然后调用 `videoService.createVideo({ generationTopicId, model, params, provider })`。
- 成功后刷新 generation batches，并清空 prompt。
- `recreateVideo(generationBatchId)` 会读取旧 batch 的 `model/provider/config`，删除旧 batch 后重新调用同一个 `videoService.createVideo(...)`。

因此用户在视频创建页面点击生成，最终会走到本文件的 `createVideo` mutation。

### Router 注册关系

`src/server/routers/lambda/index.ts` 中注册了：

```ts
import { videoRouter } from './video';

export const lambdaRouter = router({
  ...
  video: videoRouter,
  ...
});
```

因此外部调用路径是：

```ts
lambdaClient.video.createVideo.mutate(...)
lambdaClient.video.getVideoFreeQuota.query(...)
```

`VideoRouter = typeof videoRouter` 则用于类型系统，让 TRPC client 能推导接口形状。

### 下游数据库表

本文件直接写入这些表：

- `generationBatches`
- `generations`
- `asyncTasks`

三者关系大致是：

- 一个 `generationBatch` 表示一次生成请求批次，保存 prompt、provider、model、config、topic 等。
- 一个 `generation` 表示批次下的具体生成结果。视频场景中注释明确写了 “video is always 1”，所以一次 batch 只建一个 generation。
- 一个 `asyncTask` 表示异步执行状态，保存 `Pending`、`Processing`、`Error`、`Success` 等状态，以及 `inferenceId`、metadata、error 等。

创建顺序是：

1. 插入 `generationBatches`。
2. 插入 `generations`，关联 `generationBatchId`。
3. 插入 `asyncTasks`，metadata 中保存 `precharge` 和 `webhookToken`。
4. 更新 `generations.asyncTaskId` 关联异步任务。

这些操作被包在 `serverDB.transaction(...)` 内，保证基础记录要么一起成功，要么一起失败。

### 下游模型运行时

本文件通过：

```ts
const modelRuntime = await initModelRuntimeFromDB(serverDB, userId, provider);
```

初始化供应商运行时，然后调用：

```ts
modelRuntime.createVideo(
  {
    callbackUrl,
    model: resolvedModelId,
    params: generationParams,
  },
  { metadata: { trigger: RequestTrigger.Video } },
);
```

这里传给模型供应商的模型是 `resolvedModelId`，不是一定等于用户请求的 `model`。这对应 LobeHub 的 business model mapping：用户看到的模型 ID 可能会映射到某个实际供应商模型 ID。

### 异步后续处理

提交成功后根据响应决定后续路径：

- webhook 型供应商：只把任务状态更新为 `Processing`，等待 `/api/webhooks/video/${provider}?token=...` 回调。
- polling 型供应商：同样更新为 `Processing`，然后通过 Next.js `after(...)` 注册后台轮询，调用 `processBackgroundVideoPolling(...)`。

根据当前片段推断，`processBackgroundVideoPolling` 的职责与 `src/server/routers/async/video.ts` 类似：轮询供应商任务状态，拿到最终视频 URL 后下载/处理视频，创建 asset/file，更新 generation 和 async task 状态，并完成后置扣费或失败退款。依据是本文件传入了 `generationBatchId`、`generationId`、`generationTopicId`、`inferenceId`、`prechargeResult` 等后续完成视频任务所需的完整上下文。

## 运行/调用流程

一次正常的视频生成调用可以按下面理解：

1. 用户在视频生成页面输入 prompt 和参数。
2. 前端 store 的 `createVideo()` 读取当前 `parameters/provider/model/topic`。
3. 如果没有 `generationTopicId`，前端先创建一个 generation topic。
4. 前端调用 `videoService.createVideo(...)`。
5. `videoService` 通过 `lambdaClient.video.createVideo.mutate(payload)` 进入本文件。
6. `createVideoInputSchema` 校验入参。
7. router 解析模型映射，得到 `resolvedModelId`。
8. 如果是 LobeHub branding provider，检查该 video model 是否仍在 model bank 中。
9. router 把图片 URL 尽量转换为内部 key 保存到 `generationBatches.config`。
10. 开发环境下，如果图片 URL 是本地代理地址，则转成供应商可访问的 S3 URL。
11. 调用 `chargeBeforeGenerate(...)` 预扣费。
12. 生成 `webhookToken`。
13. 数据库事务创建 batch、generation、asyncTask，并建立 generation 到 asyncTask 的关联。
14. 初始化 provider 对应的 `modelRuntime`。
15. 调用 `modelRuntime.createVideo(...)` 把任务提交给真实模型供应商。
16. 如果 provider 使用 webhook，任务进入 `Processing`，等待 webhook。
17. 如果 provider 使用 polling，任务进入 `Processing`，由 `after(...)` 触发后台轮询。
18. mutation 立即返回 `{ success: true, data: { batch, generations } }`。
19. 前端刷新 generation batches，页面出现一条正在生成的视频记录。
20. 后台完成后，其他服务更新 async task 和 generation 资产，前端再通过列表刷新或订阅机制看到最终结果。

异常流程也很关键：

- 如果预扣费失败，`chargeBeforeGenerate` 返回 `errorBatch`，router 直接返回这个 batch，不继续创建新的数据库记录和供应商任务。
- 如果供应商任务提交失败，router 会把已创建的 async task 标记为 `Error`，必要时调用 `chargeAfterGenerate({ isError: true })`，然后仍返回 batch/generation。
- 如果提交成功但后续生成失败，错误处理不在这个文件主流程中，而在 webhook/polling 后续处理里完成。

## 小白阅读顺序

1. 先看文件底部的导出：

   ```ts
   export const videoRouter = router({...});
   export type VideoRouter = typeof videoRouter;
   ```

   明白这个文件是一个 TRPC router，不是普通工具函数。

2. 再看 `createVideoInputSchema`。

   这里定义了前端必须传什么：`generationTopicId`、`provider`、`model`、`params.prompt` 等。理解入参后，再读主流程会容易很多。

3. 接着看 `videoProcedure`。

   它解释了为什么 `createVideo` 的 `ctx` 里有 `serverDB`、`asyncTaskModel`、`fileService`。这些不是函数内部凭空来的，而是 middleware 注入的。

4. 然后从 `createVideo` 开头顺序读到 `chargeBeforeGenerate`。

   这一段主要做“准备工作”：模型映射、模型可用性校验、图片 URL 归一化、开发环境 URL 转换、预扣费。

5. 再重点看 `serverDB.transaction(...)`。

   这一段是数据结构核心。建议画出 `generationBatch -> generation -> asyncTask` 的关系。视频一次生成只创建一个 `generation`。

6. 继续看 `modelRuntime.createVideo(...)`。

   这里才是真正把任务提交给供应商。注意传入的是 `resolvedModelId` 和 `generationParams`，不是纯前端原始参数。

7. 最后看 `useWebhook` 分支和 `catch` 分支。

   这两段解释了为什么接口返回时视频还没生成好，以及失败为什么可能体现为 async task 的错误状态，而不是 mutation 直接 throw。

8. 补充阅读调用方：

   - `src/services/video.ts`
   - `src/store/video/slices/createVideo/action.ts`
   - `src/server/routers/lambda/index.ts`
   - 同目录 `error.ts`

   读完这几个文件，就能连起“页面点击生成 -> store action -> service -> lambda router -> 模型供应商 -> webhook/polling”的链路。

## 常见误区

1. 误以为 `createVideo` 会返回最终视频文件。

   实际上它只提交异步任务并返回初始 batch/generation。最终视频资产由 webhook 或后台轮询后续写入。

2. 误以为 `params.imageUrl` 原样存数据库。

   代码会尽量用 `fileService.getKeyFromFullUrl(...)` 把完整 URL 转成对象存储 key，保存到 `generationBatches.config`。这样数据库更稳定，不依赖临时代理 URL。

3. 误以为开发环境和生产环境传给供应商的图片 URL 一样。

   开发环境中，本地代理 URL 可能无法被供应商访问，所以代码会再通过 `fileService.getFullFileUrl(...)` 转成 S3 URL，供模型 API 使用。

4. 误以为 `model` 一定就是供应商实际调用的模型。

   本文件先调用 `resolveBusinessModelMapping(provider, model)`，真正传给 `modelRuntime.createVideo` 的是 `resolvedModelId`。计费 metadata 中也会记录 requested/resolved model 的映射关系。

5. 误以为所有供应商都用 webhook。

   代码根据 `response.useWebhook` 判断：
   - 有 `useWebhook`：等待供应商回调。
   - 没有 `useWebhook` 但有 `response`：使用后台轮询。

6. 误以为创建数据库记录和调用供应商 API 是一个事务。

   数据库记录创建在 transaction 中，但调用 `modelRuntime.createVideo(...)` 在事务之后。这样可以避免长事务包住外部网络请求。副作用是：数据库记录可能已经创建，但供应商任务提交失败；因此 catch 分支必须把 async task 更新为 `Error`。

7. 误以为 catch 后会把错误抛给前端。

   本文件提交失败时会记录错误状态并处理预扣费，但最后仍返回 batch/generation。这是为了让前端能在生成列表中展示失败任务，而不是完全没有记录。

8. 误以为 `getVideoFreeQuota` 和 `createVideo` 使用同一套上下文。

   `getVideoFreeQuota` 只用 `authedProcedure`，没有使用 `serverDatabase` 和 `videoProcedure`，因为它只需要 `ctx.userId` 和 `input.model`，不需要本文件注入的 `asyncTaskModel`、`fileService`。

9. 误以为 `console.error` 是普通日志风格。

   文件大部分调试信息使用 `debug('lobe-video:lambda')`，但错误路径仍有 `console.error`。这在代码审查中通常需要关注是否符合项目日志规范，不过当前片段确实如此实现。

10. 误以为 `params` 的字段是封闭集合。

   `.passthrough()` 允许额外字段继续传递给下游模型运行时。这对于不同视频模型拥有不同参数很重要。
