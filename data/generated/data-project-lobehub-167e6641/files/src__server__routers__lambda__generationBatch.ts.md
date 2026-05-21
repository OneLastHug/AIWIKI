# 文件：src/server/routers/lambda/generationBatch.ts

## 文件职责
这个文件位于 `src/server/routers/lambda`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { z } from 'zod';
import { GenerationBatchModel } from '@/database/models/generationBatch';
import { authedProcedure, router } from '@/libs/trpc/lambda';
import { serverDatabase } from '@/libs/trpc/lambda/middleware';
import { FileService } from '@/server/services/file';
import { getVideoAvgLatency } from '@/server/services/generation/latency';
export const generationBatchRouter = router({
export type GenerationBatchRouter = typeof generationBatchRouter;
```

## 主要对外内容
```text
const generationBatchProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
export const generationBatchRouter = router({
export type GenerationBatchRouter = typeof generationBatchRouter;
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { z } from 'zod';

import { GenerationBatchModel } from '@/database/models/generationBatch';
import { authedProcedure, router } from '@/libs/trpc/lambda';
import { serverDatabase } from '@/libs/trpc/lambda/middleware';
import { FileService } from '@/server/services/file';
import { getVideoAvgLatency } from '@/server/services/generation/latency';

const generationBatchProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
  const { ctx } = opts;

  return opts.next({
    ctx: {
      fileService: new FileService(ctx.serverDB, ctx.userId),
      generationBatchModel: new GenerationBatchModel(ctx.serverDB, ctx.userId),
    },
  });
});

export const generationBatchRouter = router({
  deleteGenerationBatch: generationBatchProcedure
    .input(z.object({ batchId: z.string() }))
    .mutation(async ({ ctx, input }) => {
      // 1. Delete database records and get thumbnail URLs to clean
      const result = await ctx.generationBatchModel.delete(input.batchId);

      // If batch not found, return early
      if (!result) {
        return;
      }

      const { deletedBatch, filesToDelete } = result;

      // 2. Clean up asset files from S3 (videos, covers, thumbnails)
      // Note: Even if file deletion fails, we consider the batch deletion successful
      // since the database record has been removed and users won't see the batch anymore
      if (filesToDelete.length > 0) {
        try {
          await ctx.fileService.deleteFiles(filesToDelete);
        } catch (error) {
          // Log the error but don't throw - file cleanup failure shouldn't affect
          // the user experience since the database operation succeeded
          console.error('Failed to delete files from S3:', error);
        }
      }

      return deletedBatch;
    }),

  getGenerationBatches: generationBatchProcedure
    .input(z.object({ topicId: z.string(), type: z.enum(['image', 'video']).optional() }))
    .query(async ({ ctx, input }) => {
      const batches = await ctx.generationBatchModel.queryGenerationBatchesByTopicIdWithGenerations(
        input.topicId,
      );

      if (input.type !== 'video') return batches;

      const uniqueModels = [...new Set(batches.map((b) => b.model))];
      const latencyMap = new Map<string, number | null>();

      await Promise.all(
        uniqueModels.map(async (model) => {
          const latency = await getVideoAvgLatency(model).catch(() => null);
          latencyMap.set(model, latency);
        }),
      );

      return batches.map((b) => ({ ...b, avgLatencyMs: latencyMap.get(b.model) ?? null }));
    }),
});

export type GenerationBatchRouter = typeof generationBatchRouter;

```
