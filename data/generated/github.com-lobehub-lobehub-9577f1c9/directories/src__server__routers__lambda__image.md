# 目录：src/server/routers/lambda/image

## 它负责什么

`src/server/routers/lambda/image` 是“发起 AI 图片生成”的 Lambda tRPC 路由目录。它不直接执行真正的图片生成推理，而是负责把一次前端请求转换成一组可追踪的数据库记录和后台异步任务。

核心职责可以概括为：

1. 接收前端传来的图片生成参数，例如 `provider`、`model`、`prompt`、`width`、`height`、`imageNum`、参考图 URL 等。
2. 校验并规范化模型信息，尤其是 LobeHub 自有品牌模型是否仍可用于 `image` 类型任务。
3. 把参考图的完整 URL 转换成存储 key，避免把会过期的 presigned URL 写进数据库。
4. 在数据库事务中创建：
   - `generationBatches`
   - `generations`
   - `asyncTasks`
5. 调用计费/额度前置逻辑 `chargeBeforeGenerate`。
6. 触发 `src/server/routers/async/image` 中的后台图片生成任务。
7. 返回批次和生成项，让前端可以立刻展示任务列表和后续轮询状态。

这个目录可以理解为图片生成链路的“入口协调层”：它负责建账、建任务、做防御性校验，然后把实际耗时的生成工作交给 async router。

## 关键组成

这个目录当前只有四个文件：

```text
src/server/routers/lambda/image
├── index.ts
├── index.test.ts
├── utils.ts
└── utils.test.ts
```

### `index.ts`

`index.ts` 是目录入口，导出两个核心内容：

```ts
export const imageRouter = router({
  createImage: ...
});

export type ImageRouter = typeof imageRouter;
```

同时它还导出前端服务会复用的输入类型：

```ts
export type CreateImageServicePayload = z.infer<typeof createImageInputSchema>;
```

主要 import 可以按层次理解：

```ts
import { authedProcedure, router } from '@/libs/trpc/lambda';
import { serverDatabase } from '@/libs/trpc/lambda/middleware';
```

这说明该目录提供的是 Lambda tRPC 路由，并且要求用户已登录，同时通过 `serverDatabase` 中间件拿到服务端数据库上下文。

```ts
import { AsyncTaskModel } from '@/database/models/asyncTask';
import { asyncTasks, generationBatches, generations } from '@/database/schemas';
```

这说明它直接写入异步任务表和图片生成相关表。

```ts
import { createAsyncCaller } from '@/server/routers/async/caller';
```

这说明 Lambda 路由只负责发起任务，真正的生成执行交给 async router。

```ts
import { FileService } from '@/server/services/file';
```

`FileService` 用来把完整文件 URL 转换为存储 key，或在开发环境下把 key 再转成后台任务能访问的真实 S3 URL。

```ts
import { chargeBeforeGenerate } from '@/business/server/image-generation/chargeBeforeGenerate';
```

这是业务层计费/额度前置检查。根据当前片段可见，如果 `chargeBeforeGenerate` 返回结果，`createImage` 会直接返回该结果，不再继续创建数据库记录和异步任务。

### `imageProcedure`

`index.ts` 先定义了一个专用 procedure：

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

它在通用的 `authedProcedure` 基础上追加了两个上下文对象：

- `ctx.asyncTaskModel`：用于更新异步任务状态，尤其是启动后台任务失败时批量标记为失败。
- `ctx.fileService`：用于处理参考图片 URL 和文件 key。

这符合仓库内 tRPC router 的常见模式：通过 procedure middleware 注入 model/service，而不是在每个 procedure 内重复创建。

### `createImageInputSchema`

`createImageInputSchema` 是 `createImage` 的输入协议：

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

几个点值得注意：

- `generationTopicId` 用于把这批生成结果归到某个图片生成主题下。
- `imageNum` 决定本次要创建多少条 `generation` 和 `asyncTask`。
- `params.prompt` 是必填。
- `params` 使用 `.passthrough()`，表示 schema 只显式声明了常用字段，但允许 provider/model 特有参数继续透传。
- `imageUrls` 是多参考图字段。
- 代码还兼容 `params.imageUrl` 这个单图字段，但它没有显式写在 schema 里，是通过 `.passthrough()` 被允许的。

### `createImage`

`createImage` 是唯一的路由过程，也是这个目录的核心逻辑。

它的主要阶段如下：

1. 解析输入：

```ts
const { generationTopicId, provider, model, imageNum, params } = input;
```

2. 解析业务模型映射：

```ts
const { resolvedModelId } = await resolveBusinessModelMapping(provider, model);
```

如果是 `BRANDING_PROVIDER`，还会检查模型是否仍在 model bank 中可用于图片生成：

```ts
if (
  provider === BRANDING_PROVIDER &&
  !isProviderModelAvailable(await loadModels(), BRANDING_PROVIDER, resolvedModelId, 'image')
) {
  throw new TRPCError({
    cause: { data: { modelType: 'image', requestedModel: model } },
    code: 'BAD_REQUEST',
    message: ChatErrorType.LobeHubModelDeprecated,
  });
}
```

这一步避免用户选择了已下架或不支持图片生成的 LobeHub 模型时，错误延迟到下游 provider 才暴露。

3. 将数据库配置里的图片 URL 转成 key。

多图字段：

```ts
params.imageUrls -> configForDatabase.imageUrls
```

单图字段：

```ts
params.imageUrl -> configForDatabase.imageUrl
```

这里使用：

```ts
fileService.getKeyFromFullUrl(url)
```

目标是让数据库只保存稳定的对象存储 key，而不是完整 URL。

4. 开发环境特殊处理。

在 `NODE_ENV === 'development'` 时，后台 async task 可能无法访问本地代理 URL，所以代码会把用于实际生成的 `generationParams` 转换成 S3 URL：

```ts
fileService.getFullFileUrl(key)
```

这里要区分两个对象：

- `configForDatabase`：写入数据库，必须是 key。
- `generationParams`：传给 async router，开发环境下可能是 S3 完整 URL。

5. 防御性检查：

```ts
validateNoUrlsInConfig(configForDatabase, 'configForDatabase');
```

这会递归检查数据库配置里是否残留 `[URL已移除] 或 `[URL已移除] 开头的完整 URL。如果发现，会直接抛错，阻止错误数据入库。

6. 计费/额度前置处理：

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

根据当前片段推断，`chargeBeforeGenerate` 可能会在额度不足、支付状态异常、风控命中等场景直接返回一个业务响应，从而中断后续生成流程。依据是调用方在收到 `chargeResult` 后立即 `return`。

7. 数据库事务中创建批次、生成项和异步任务。

事务内先创建 `generationBatches`：

```ts
const newBatch: NewGenerationBatch = {
  config: configForDatabase,
  generationTopicId,
  height: params.height,
  model,
  prompt: params.prompt,
  provider,
  userId,
  width: params.width,
};
```

然后按 `imageNum` 创建多条 `generations`：

```ts
const newGenerations: NewGeneration[] = Array.from({ length: imageNum }, ...)
```

再为每条 `generation` 创建一个 `asyncTasks` 记录，并把 `asyncTaskId` 回写到对应 generation：

```ts
await tx
  .update(generations)
  .set({ asyncTaskId })
  .where(and(eq(generations.id, generation.id), eq(generations.userId, userId)));
```

事务保证了批次、生成项、任务三者要么一起成功，要么一起失败，不会出现只建了一半的状态。

8. 触发后台 async router。

事务成功后，代码创建 async caller：

```ts
const asyncCaller = await createAsyncCaller({
  userId: ctx.userId,
});
```

然后对每个 generation 调用：

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

这里有一个重要细节：代码使用 `forEach` 触发，并没有 `await` 每个异步调用。注释也明确写了这是 fire-and-forget。也就是说 Lambda 请求不等待图片真正生成完成，只负责把后台任务启动出去。

9. 返回创建结果：

```ts
return {
  data: {
    batch: createdBatch,
    generations: createdGenerations,
  },
  success: true,
};
```

前端拿到的是“任务已创建”的结果，而不是“图片已生成”的结果。

### `utils.ts`

`utils.ts` 当前只有一个工具函数：

```ts
export function validateNoUrlsInConfig(obj: any, path: string = ''): void
```

它递归遍历输入对象：

- 如果遇到字符串，检查是否以 `[URL已移除] 或 `[URL已移除] 开头。
- 如果遇到数组，逐项递归。
- 如果遇到对象，逐字段递归。

一旦发现完整 URL，就抛出错误：

```ts
Invalid configuration: Found full URL instead of key ...
```

这个函数的定位是“最后一道防线”：即使前面 URL 到 key 的转换逻辑漏掉了某个字段，也能阻止完整 URL 被写入数据库。

需要注意它现在使用了 `any`，这在类型风格上并不理想，但作为一个递归检查任意 JSON-like 配置的工具函数，在当前片段里可以理解为为了接受任意结构。

### `index.test.ts` 和 `utils.test.ts`

这两个文件分别测试：

- `imageRouter` 的创建任务、异常分支、任务状态更新等行为。
- `validateNoUrlsInConfig` 对嵌套对象、数组、字符串 URL 的检查行为。

学习这个目录时，测试文件很重要，因为 `createImage` 涉及数据库事务、计费短路、文件 URL 转换、后台任务触发等多个分支，单看实现容易漏掉边界条件。

## 上下游关系

### 上游：前端服务层

直接调用方是：

```text
src/services/image.ts
```

它定义了：

```ts
export class AiImageService {
  async createImage(payload: CreateImageServicePayload) {
    const result = await lambdaClient.image.createImage.mutate(payload);
    return result;
  }
}

export const imageService = new AiImageService();
```

这里可以看到前端/客户端侧不会直接知道数据库或 async router，它只通过：

```ts
lambdaClient.image.createImage.mutate(payload)
```

调用 Lambda tRPC。

`CreateImageServicePayload` 直接从服务端 router 导入：

```ts
import { type CreateImageServicePayload } from '@/server/routers/lambda/image';
```

这保证了客户端服务层和服务端输入 schema 的类型一致。

### 上游：Lambda router 聚合入口

`imageRouter` 被注册到：

```text
src/server/routers/lambda/index.ts
```

搜索结果显示其中有：

```ts
import { imageRouter } from './image';

...
image: imageRouter,
```

因此最终 tRPC 路径是：

```text
lambdaClient.image.createImage.mutate(...)
```

也就是说目录名 `image` 会成为 Lambda router 命名空间的一部分。

### 下游：数据库

`createImage` 会写入三类表：

```ts
generationBatches
generations
asyncTasks
```

它们之间的关系是：

```text
generationBatch
  ├─ generation 1 ─ asyncTask 1
  ├─ generation 2 ─ asyncTask 2
  └─ generation N ─ asyncTask N
```

一次用户请求对应一个 batch；如果 `imageNum` 为 N，就会创建 N 个 generation，每个 generation 对应一个 async task。

### 下游：文件服务

`FileService` 负责在 URL 和对象存储 key 之间转换：

```ts
fileService.getKeyFromFullUrl(url)
fileService.getFullFileUrl(key)
```

在持久化配置时使用 key；在开发环境触发 async task 时，可能转为完整 S3 URL。

### 下游：业务计费/额度

`chargeBeforeGenerate` 位于：

```text
@/business/server/image-generation/chargeBeforeGenerate
```

它处在数据库创建之前。如果它返回结果，后续不会创建 generation batch，也不会触发 async task。

这说明图片生成前置收费/额度判断是强约束，而不是生成后补偿。

### 下游：async router

真正的图片生成由 async router 接手：

```ts
createAsyncCaller({ userId: ctx.userId })
asyncCaller.image.createImage(...)
```

根据当前片段推断，`src/server/routers/async/image.ts` 负责实际调用 provider、更新任务状态、保存生成结果。依据是 Lambda router 只创建任务并调用 `asyncCaller.image.createImage`，没有任何直接请求图片模型或写入生成图片结果的代码。

## 运行/调用流程

完整流程可以按下面顺序理解：

```text
前端 UI
  ↓
src/services/image.ts
  imageService.createImage(payload)
  ↓
lambdaClient.image.createImage.mutate(payload)
  ↓
src/server/routers/lambda/index.ts
  image: imageRouter
  ↓
src/server/routers/lambda/image/index.ts
  imageRouter.createImage
  ↓
校验输入 zod schema
  ↓
解析 provider/model 映射
  ↓
检查 LobeHub 品牌图片模型是否仍可用
  ↓
把 params.imageUrl / params.imageUrls 转成存储 key
  ↓
开发环境下，为 async task 准备可访问的 S3 URL
  ↓
validateNoUrlsInConfig(configForDatabase)
  ↓
chargeBeforeGenerate(...)
  ↓
数据库事务：
  创建 generationBatch
  创建 N 条 generation
  创建 N 条 asyncTask
  回写 generation.asyncTaskId
  ↓
createAsyncCaller({ userId })
  ↓
fire-and-forget 调用 asyncCaller.image.createImage(...)
  ↓
返回 { success: true, data: { batch, generations } }
```

这里最关键的分界线是：

```text
Lambda image router：创建任务，立即返回
Async image router：后台执行图片生成
```

所以用户在前端点击生成图片后，接口返回成功只代表任务创建成功，不代表图片已经生成完成。

## 小白阅读顺序

建议按下面顺序阅读：

1. 先读 `src/services/image.ts`

   从客户端视角理解入口：

   ```ts
   imageService.createImage(payload)
   ```

   重点看它如何调用：

   ```ts
   lambdaClient.image.createImage.mutate(payload)
   ```

2. 再读 `src/server/routers/lambda/index.ts`

   只需要确认 `imageRouter` 是如何挂到 `image` 命名空间下的。看到：

   ```ts
   image: imageRouter
   ```

   就能把客户端调用路径和服务端 router 对上。

3. 然后读 `src/server/routers/lambda/image/index.ts` 顶部 import

   先不要急着看 `createImage` 细节。先通过 import 判断它依赖哪些层：

   - `@/libs/trpc/lambda`：tRPC Lambda 层
   - `@/database/models/asyncTask`：异步任务模型
   - `@/database/schemas`：数据库表
   - `@/server/services/file`：文件服务
   - `@/server/routers/async/caller`：后台任务调用
   - `@/business/server/image-generation/chargeBeforeGenerate`：业务计费/额度

4. 再读 `createImageInputSchema`

   明确这个接口要求什么输入。特别注意 `params` 是 `.passthrough()`，所以 provider 特有参数可以透传。

5. 接着分段读 `createImage`

   不要从头到尾一次性硬读。按阶段拆：

   - 模型解析和可用性检查
   - URL/key 转换
   - `validateNoUrlsInConfig`
   - `chargeBeforeGenerate`
   - 数据库事务
   - async router 触发
   - 返回值

6. 再读 `utils.ts`

   理解为什么要递归禁止完整 URL 入库。

7. 最后读 `index.test.ts` 和 `utils.test.ts`

   测试能帮助你确认哪些分支是作者认为重要的，例如 URL 转换失败、async task 启动失败、配置中残留 URL 等。

## 常见误区

1. 误以为 `createImage` 会同步生成图片

   它不会。`createImage` 只创建 batch、generation、asyncTask，然后 fire-and-forget 调用 async router。返回时图片通常还没有生成完成。

2. 误以为返回 `success: true` 表示图片生成成功

   这里的 `success: true` 表示任务创建流程成功，不等于 provider 已经返回图片。真正生成结果需要看后续 generation/task 状态。

3. 误以为数据库里保存的是完整图片 URL

   代码明确把 `params.imageUrl` 和 `params.imageUrls` 转换成 key，并用 `validateNoUrlsInConfig` 防止完整 URL 入库。完整 URL 可能会过期，不适合作为长期配置保存。

4. 误以为 `configForDatabase` 和 `generationParams` 是同一个东西

   它们用途不同：

   ```text
   configForDatabase：写数据库，必须是稳定 key
   generationParams：传给后台生成任务，开发环境下可能需要完整 S3 URL
   ```

5. 误以为 `imageNum` 只是传给 provider 的数量参数

   在这个 router 里，`imageNum` 直接决定创建多少条 `generations` 和多少条 `asyncTasks`。也就是一张图一个 generation，一张图一个 async task。

6. 误以为 seed 会直接按用户传入值保存

   当前代码逻辑是：

   ```ts
   const seeds =
     'seed' in params
       ? generateUniqueSeeds(imageNum)
       : Array.from({ length: imageNum }, () => null);
   ```

   也就是说，只要 `params` 中存在 `seed` 字段，就会为多张图片生成唯一 seed；否则每条 generation 的 seed 是 `null`。这不是简单地把用户传入的 `params.seed` 原样写入每条 generation。

7. 误以为所有 provider/model 都会经过 model bank 可用性检查

   当前片段中，只有：

   ```ts
   provider === BRANDING_PROVIDER
   ```

   时才会调用 `isProviderModelAvailable(..., 'image')` 做 LobeHub 品牌模型下架检查。其他 provider 的可用性大概率由后续 runtime/provider 层处理。

8. 误以为 async task 启动失败会回滚数据库事务

   数据库事务已经在触发 async task 之前完成。如果后续启动 async task 的整体过程失败，代码会尝试把已创建的 async task 批量更新为 `Error`，而不是回滚之前创建的 batch/generation/task。

9. 误以为 `params` 只能包含 schema 里列出的字段

   `params` 使用 `.passthrough()`，所以允许额外字段存在。这对不同图片模型的私有参数很重要，但也意味着保存前需要 `validateNoUrlsInConfig` 这种递归防御，避免额外字段里藏着完整 URL。

10. 误以为这个目录是完整图片生成系统

   它只是 Lambda 入口。完整链路还包括：

   ```text
   src/services/image.ts
   src/server/routers/lambda/index.ts
   src/server/routers/lambda/image
   src/server/routers/async/image.ts
   src/server/services/generation
   src/server/services/file
   database schemas/models
   business chargeBeforeGenerate
   ```

   阅读时要把它放在“创建生成任务”的位置，而不是“执行生成模型”的位置。
