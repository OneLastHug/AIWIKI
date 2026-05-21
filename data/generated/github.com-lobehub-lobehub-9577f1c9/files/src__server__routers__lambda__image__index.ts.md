# 文件：src/server/routers/lambda/image/index.ts

## 它负责什么

`src/server/routers/lambda/image/index.ts` 定义的是前台 Lambda tRPC 路由里的图片生成入口：`imageRouter.createImage`。

它本身不直接调用模型生成图片，而是负责“创建一次图片生成任务”的前半段工作：

1. 校验前端传来的图片生成参数。
2. 解析业务模型映射，检查 LobeHub 内置图片模型是否仍可用。
3. 把参考图 URL 转成稳定的文件存储 key，避免把会过期的完整 URL 写入数据库。
4. 在必要时做生成前扣费或业务拦截。
5. 在数据库事务里创建 `generationBatch`、多条 `generation`、以及对应的 `asyncTask`。
6. 通过 `createAsyncCaller` 触发后台异步图片生成路由。
7. 立即把已创建的批次和 generation 信息返回给前端。

换句话说，这个文件是“图片生成请求的调度层”。它把一次用户点击生成图片的动作，拆成数据库记录、异步任务、后台模型调用这几部分，但真正耗时的模型生成发生在 `src/server/routers/async/image.ts`。

## 关键组成

### `imageProcedure`

```ts
const imageProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
  const { ctx } = opts;

  return opts.next({
    ctx: {
      asyncTaskModel: new AsyncTaskModel(ctx.serverDB, ctx.userId),
      fileService: new FileService(ctx.serverDB, ctx.userId),
    },
  });
});
```

这是该路由的基础 procedure。

它叠加了两层能力：

- `authedProcedure`：要求用户已登录，后续逻辑可使用 `ctx.userId`。
- `serverDatabase`：把服务端数据库连接注入 `ctx.serverDB`。

然后它继续往 `ctx` 中注入两个领域对象：

- `asyncTaskModel`：用于更新异步任务状态，尤其是启动后台任务失败时把任务标记为错误。
- `fileService`：用于把文件完整 URL 转换为存储 key，或在开发环境把 key 再转成可访问的 S3 URL。

这符合仓库里 tRPC router 的常见模式：在 middleware 阶段注入 model/service，procedure 内直接使用 `ctx.xxx`。

### `createImageInputSchema`

```ts
const createImageInputSchema = z.object({
  generationTopicId: z.string(),
  imageNum: z.number(),
  model: z.string(),
  params: z
    .object({
      cfg: z.number().optional(),
      height: z.number().optional(),
      imageUrls: z.array(z.string()).optional(),
      prompt: z.string(),
      seed: z.number().nullable().optional(),
      steps: z.number().optional(),
      width: z.number().optional(),
    })
    .passthrough(),
  provider: z.string(),
});
```

这是 `createImage` mutation 的输入校验。

核心字段含义：

- `generationTopicId`：图片生成所属的话题 ID。
- `provider`：模型服务提供方，例如 LobeHub 内置、OpenAI、ComfyUI 等。
- `model`：用户选择的模型 ID。
- `imageNum`：要生成多少张图。
- `params`：具体生成参数，包括 `prompt`、尺寸、步数、CFG、随机种子、参考图等。

注意 `params` 使用了 `.passthrough()`，说明这里只定义了一些已知字段，但允许额外字段继续传入。这对多 provider 场景很重要，因为不同图片模型可能有自己的扩展参数。

`CreateImageServicePayload` 直接从这个 schema 推导：

```ts
export type CreateImageServicePayload = z.infer<typeof createImageInputSchema>;
```

前端服务 `src/services/image.ts` 会复用这个类型，保证前后端调用形状一致。

### `imageRouter.createImage`

这是文件的核心 mutation。

它主要分为几段逻辑。

第一段是模型解析与废弃模型检查：

```ts
const { resolvedModelId } = await resolveBusinessModelMapping(provider, model);
```

这里会把业务层 model ID 映射为真正可调用的模型 ID。随后如果 `provider === BRANDING_PROVIDER`，还会通过 `loadModels()` 和 `isProviderModelAvailable()` 检查该 LobeHub 内置图片模型是否还存在于 model bank 中。

如果模型已废弃，会抛出：

```ts
new TRPCError({
  code: 'BAD_REQUEST',
  message: ChatErrorType.LobeHubModelDeprecated,
})
```

前端 store 里有 `handleLobeHubModelDeprecatedError(error)` 对这类错误做专门处理。

第二段是参考图 URL 归一化。

文件区分两种参考图字段：

- `params.imageUrls`：多张参考图。
- `params.imageUrl`：单张参考图。虽然 schema 中没有显式声明，但因为 `params.passthrough()`，这个字段仍可能存在。

对于这些字段，它会调用：

```ts
fileService.getKeyFromFullUrl(url)
```

把完整 URL 转换成文件 key，然后写入 `configForDatabase`。

这样数据库中的 `generationBatches.config` 存的是稳定 key，而不是可能带签名、会过期的 URL。

第三段是开发环境特殊处理。

在 `process.env.NODE_ENV === 'development'` 时，它会把数据库用的 key 再转回 S3 URL，放到 `generationParams` 里：

```ts
const s3Url = await fileService.getFullFileUrl(configForDatabase.imageUrl as string);
```

这里要区分两个变量：

- `configForDatabase`：用于写数据库，必须是 key，不能是完整 URL。
- `generationParams`：用于传给后台异步任务，开发环境下可能需要完整 S3 URL，方便后台任务访问图片资源。

第四段是防御性校验：

```ts
validateNoUrlsInConfig(configForDatabase, 'configForDatabase');
```

这个函数来自同目录 `utils.ts`，会递归检查对象里是否含有 `[URL已移除] 或 `[URL已移除] 开头的字符串。如果发现完整 URL，就直接抛错，阻止数据库写入。

这说明该文件对“数据库只存 key，不存完整 URL”这个约束非常重视。

第五段是生成前扣费或业务检查：

```ts
const chargeResult = await chargeBeforeGenerate({
  clientIp: ctx.clientIp,
  configForDatabase,
  generationParams,
  generationTopicId,
  imageNum,
  model,
  provider,
  userId,
});
if (chargeResult) {
  return chargeResult;
}
```

`chargeBeforeGenerate` 属于业务层能力。根据当前片段推断，它可能会检查套餐、余额、风控或扣费状态。如果它返回了结果，`createImage` 会提前返回，不再创建数据库任务。

第六段是数据库事务。

事务里依次创建：

1. `generationBatches` 记录。
2. 多条 `generations` 记录。
3. 每条 generation 对应一条 `asyncTasks` 记录。
4. 把 `asyncTaskId` 回写到对应 generation 上。

重点代码结构是：

```ts
const { batch: createdBatch, generationsWithTasks } = await serverDB.transaction(async (tx) => {
  const [batch] = await tx.insert(generationBatches).values(newBatch).returning();

  const createdGenerations = await tx.insert(generations).values(newGenerations).returning();

  const generationsWithTasks = await Promise.all(
    createdGenerations.map(async (generation) => {
      const [createdAsyncTask] = await tx.insert(asyncTasks).values(...).returning();

      await tx
        .update(generations)
        .set({ asyncTaskId })
        .where(and(eq(generations.id, generation.id), eq(generations.userId, userId)));

      return { asyncTaskId, generation };
    }),
  );

  return { batch, generationsWithTasks };
});
```

这里使用事务的原因很清楚：批次、单图记录、异步任务三类数据必须一致创建。如果中途失败，不应该留下半套 generation 或 task 数据。

关于 seed，有一处容易误读：

```ts
const seeds =
  'seed' in params
    ? generateUniqueSeeds(imageNum)
    : Array.from({ length: imageNum }, () => null);
```

只要 `params` 中存在 `seed` 字段，就会为每张图生成唯一 seed；如果没有 seed 字段，则每张图 seed 为 `null`。也就是说这里不是直接复用用户传入的某个固定 seed，而是根据“是否存在 seed 字段”决定是否生成一组唯一 seed。

第七段是触发后台任务。

事务完成后，它创建 async caller：

```ts
const asyncCaller = await createAsyncCaller({
  userId: ctx.userId,
});
```

然后对每个 generation 启动后台异步图片生成：

```ts
asyncCaller.image.createImage({
  generationBatchId: createdBatch.id,
  generationId: generation.id,
  generationTopicId,
  model,
  params: generationParams,
  provider,
  taskId: asyncTaskId,
});
```

代码注释明确说明这是 fire-and-forget：不会 `await` 每个后台任务，也不使用 `after()`，避免 Lambda 被不必要地拖住。

如果启动后台任务整体失败，则会把所有相关 `asyncTask` 更新为 `AsyncTaskStatus.Error`，并写入 `AsyncTaskError`。

最后返回：

```ts
return {
  data: {
    batch: createdBatch,
    generations: createdGenerations,
  },
  success: true,
};
```

这让前端可以马上拿到批次和 generation 占位信息，随后通过刷新或订阅任务状态看到生成进度和结果。

## 上下游关系

### 上游：前端图片生成入口

从调用链看，典型入口是：

```txt
src/routes/(main)/(create)/image/features/PromptInput/index.tsx
  -> useImageStore((s) => s.createImage)
  -> src/store/image/slices/createImage/action.ts
  -> imageService.createImage(...)
  -> src/services/image.ts
  -> lambdaClient.image.createImage.mutate(payload)
  -> src/server/routers/lambda/image/index.ts
```

`src/store/image/slices/createImage/action.ts` 会从 store 里取出：

- `imageNum`
- `parameters`
- `provider`
- `model`
- 当前 `generationTopicId`

如果没有当前话题，它会先创建 generation topic，再调用 `imageService.createImage()`。

`src/services/image.ts` 很薄，只是把 payload 传给：

```ts
lambdaClient.image.createImage.mutate(payload)
```

并复用本文件导出的 `CreateImageServicePayload` 类型。

### 路由挂载：`lambdaRouter.image`

本文件导出的 `imageRouter` 会在 `src/server/routers/lambda/index.ts` 中挂载：

```ts
import { imageRouter } from './image';

export const lambdaRouter = router({
  image: imageRouter,
});
```

所以客户端调用路径是：

```ts
lambdaClient.image.createImage.mutate(...)
```

### 下游：数据库表

本文件直接写入这些表：

- `generationBatches`
- `generations`
- `asyncTasks`

其中：

- `generationBatches` 表示一次生成批次，比如一次 prompt 生成 4 张图。
- `generations` 表示批次中的单张图记录。
- `asyncTasks` 表示后台异步任务状态。

它还使用了这些类型：

- `NewGeneration`
- `NewGenerationBatch`

用于构造插入数据库的数据。

### 下游：后台异步路由

真正执行图片生成的是：

```txt
src/server/routers/async/image.ts
```

本文件通过：

```ts
createAsyncCaller({ userId })
```

拿到 async router caller，然后调用：

```ts
asyncCaller.image.createImage(...)
```

`src/server/routers/async/image.ts` 中的 `createImage` 会继续做这些事：

- 校验 `generationBatch` 是否存在。
- 把 task 状态更新为 `Processing`。
- 初始化 provider 对应的 model runtime。
- 调用 `modelRuntime.createImage(...)`。
- 下载/转换生成图片。
- 更新 generation 和 async task 状态。

因此，`lambda/image/index.ts` 是“创建任务和调度任务”，`async/image.ts` 是“执行任务和落结果”。

### 下游：文件服务

`FileService` 在这里主要用于参考图处理：

- `getKeyFromFullUrl(url)`：完整 URL -> 文件 key。
- `getFullFileUrl(key)`：文件 key -> 可访问 URL，开发环境下传给后台任务。

同目录 `utils.ts` 的 `validateNoUrlsInConfig` 是它的兜底保护，防止转换遗漏。

### 下游：业务扣费和模型银行

本文件依赖几类业务能力：

- `chargeBeforeGenerate`：生成前扣费或检查。
- `resolveBusinessModelMapping`：业务模型 ID 到实际模型 ID 的映射。
- `loadModels` / `isProviderModelAvailable`：检查内置模型是否还可用。
- `ChatErrorType.LobeHubModelDeprecated`：模型废弃错误类型，前端会识别处理。

## 运行/调用流程

一次用户点击“生成图片”的完整流程可以这样读：

1. 用户在图片创建页面输入 prompt、选择模型和参数。
2. `PromptInput` 触发 `useImageStore().createImage()`。
3. store action 检查 `parameters.prompt`，必要时先创建 `generationTopic`。
4. store action 调用 `imageService.createImage(payload)`。
5. `imageService` 通过 `lambdaClient.image.createImage.mutate(payload)` 调用本文件的 tRPC mutation。
6. `createImage` 用 zod 校验输入。
7. 路由解析 `provider`、`model`，确认内置模型没有废弃。
8. 路由把 `params.imageUrls` / `params.imageUrl` 中的完整 URL 转成文件 key，形成 `configForDatabase`。
9. 开发环境下，路由额外把 key 转成 S3 URL，形成给后台任务用的 `generationParams`。
10. `validateNoUrlsInConfig` 确保 `configForDatabase` 中没有完整 URL。
11. `chargeBeforeGenerate` 执行生成前业务检查；如果返回结果，提前结束。
12. 数据库事务创建一个 `generationBatch`。
13. 数据库事务按 `imageNum` 创建多条 `generation`。
14. 数据库事务为每条 `generation` 创建一个 `asyncTask`，并把 `asyncTaskId` 写回 `generation`。
15. 事务提交后，调用 `createAsyncCaller`。
16. 遍历每条 generation，调用 `asyncCaller.image.createImage(...)` 启动后台任务。
17. 当前接口不等待图片真正生成完成，直接返回 `{ batch, generations }`。
18. 前端刷新 generation batch 或监听状态变化，展示任务进度和最终图片。

这里最重要的设计点是：前台 Lambda 请求只负责“排队”，不负责“等图生成完”。这样接口响应更快，也避免长耗时模型调用卡住普通请求。

## 小白阅读顺序

建议按下面顺序读，不要一上来就陷入所有 import。

1. 先看文件底部导出：

```ts
export const imageRouter = router({
  createImage: ...
});

export type ImageRouter = typeof imageRouter;
```

先确认这个文件只暴露一个路由：`createImage`。

2. 再看输入 schema：

```ts
const createImageInputSchema = z.object(...)
```

理解前端调用这个接口时必须传什么。尤其注意 `params.passthrough()`，它说明 `params` 是一个开放结构。

3. 再看 `imageProcedure`：

```ts
const imageProcedure = authedProcedure.use(serverDatabase)...
```

理解 procedure 里为什么能拿到 `ctx.userId`、`ctx.serverDB`、`ctx.asyncTaskModel`、`ctx.fileService`。

4. 然后按注释看 `createImage` 主流程：

- 模型检查。
- URL 转 key。
- 开发环境 URL 处理。
- 扣费。
- 数据库事务。
- 触发 async task。
- 返回结果。

这个文件的注释比较密集，基本就是流程边界。

5. 接着读同目录 `utils.ts`：

```ts
validateNoUrlsInConfig(...)
```

理解为什么本文件对 URL 写库这么谨慎。

6. 再读调用方 `src/services/image.ts`。

它能帮你理解前端是怎么调用 `lambdaClient.image.createImage.mutate(payload)` 的。

7. 最后读 `src/store/image/slices/createImage/action.ts`。

这里能看到 payload 的来源：store 中的图片参数、模型、provider、topic。

8. 如果要理解图片真正怎么生成，再读 `src/server/routers/async/image.ts` 的 `createImage`。

不要把这两个 `createImage` 混在一起：一个是 Lambda 路由里的“创建任务”，一个是 async 路由里的“执行任务”。

## 常见误区

### 误区一：以为这个文件直接生成图片

这个文件不直接调用模型生成图片。它没有直接调用 `modelRuntime.createImage`。

真正的模型调用在 `src/server/routers/async/image.ts` 中。本文件只是创建数据库记录并触发后台异步任务。

### 误区二：以为接口返回时图片已经生成好了

`createImage` 返回的是批次和 generation 记录，不代表图片已经完成。

返回时，`asyncTask` 通常刚刚创建或刚开始后台处理。前端还需要刷新 generation batch 或读取任务状态来看到最终结果。

### 误区三：混淆 `configForDatabase` 和 `generationParams`

这两个变量用途不同：

- `configForDatabase`：写入数据库，必须尽量稳定，尤其参考图要存 key。
- `generationParams`：传给后台生成任务，开发环境下可能包含完整 S3 URL，方便异步任务访问。

如果把完整 URL 写进 `configForDatabase`，`validateNoUrlsInConfig` 会抛错。

### 误区四：忽略 `params.passthrough()`

虽然 schema 中只列了 `cfg`、`height`、`imageUrls`、`prompt`、`seed`、`steps`、`width`，但 `.passthrough()` 允许其他字段存在。

所以代码里访问 `params.imageUrl` 并不矛盾。它不是 schema 显式字段，但可以通过 passthrough 传入。

### 误区五：误解 seed 逻辑

这段代码：

```ts
const seeds =
  'seed' in params
    ? generateUniqueSeeds(imageNum)
    : Array.from({ length: imageNum }, () => null);
```

不是把用户传入的 `params.seed` 原样复制到每张图上。

根据当前片段推断，它的语义更像是：只要用户启用了 seed 相关控制，就为本次生成的每张图分配唯一 seed；如果没有 seed 字段，就让 seed 为空，由下游或模型自行决定随机性。

### 误区六：以为 `forEach` 里的 async 调用会被等待

这里故意没有 `await`：

```ts
generationsWithTasks.forEach(({ generation, asyncTaskId }) => {
  asyncCaller.image.createImage(...)
});
```

注释说明这是 fire-and-forget。当前 Lambda 请求不会等待每个后台任务完成。

这也意味着：只要后台任务启动调用没有在同步阶段整体抛错，接口就会继续返回成功。后续单个任务的成功失败由 async router 和 async task 状态维护。

### 误区七：忽略启动后台任务失败时的补偿逻辑

如果创建 async caller 或启动任务阶段发生整体异常，代码会尝试：

```ts
asyncTaskModel.update(asyncTaskId, {
  status: AsyncTaskStatus.Error,
  error: new AsyncTaskError(...)
})
```

也就是说，数据库事务创建任务成功后，如果调度后台失败，任务不会一直停在 `Pending`，而是尽量标记为 `Error`。

### 误区八：把 `imageRouter` 和 `async/imageRouter` 看成同一个东西

项目里有两个图片路由：

- `src/server/routers/lambda/image/index.ts`：前端通过 `lambdaClient.image.createImage` 调用，负责创建任务。
- `src/server/routers/async/image.ts`：后台通过 `createAsyncCaller` 调用，负责实际生成图片。

它们方法名都叫 `createImage`，但职责不同。阅读时要始终看清路径。
