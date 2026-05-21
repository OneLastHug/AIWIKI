# 文件：src/server/routers/lambda/generationTopic.ts

## 文件职责
这个文件位于 `src/server/routers/lambda`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { z } from 'zod';
import { GenerationTopicModel } from '@/database/models/generationTopic';
import { type GenerationTopicItem } from '@/database/schemas/generation';
import { authedProcedure, router } from '@/libs/trpc/lambda';
import { serverDatabase } from '@/libs/trpc/lambda/middleware';
import { FileService } from '@/server/services/file';
import { GenerationService } from '@/server/services/generation';
export const generationTopicRouter = router({
export type GenerationTopicRouter = typeof generationTopicRouter;
export type UpdateTopicInput = z.infer<typeof updateTopicSchema>;
export type UpdateTopicValue = UpdateTopicInput['value'];
export type UpdateTopicCoverInput = z.infer<typeof updateTopicCoverSchema>;
```

## 主要对外内容
```text
const generationTopicProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
const updateTopicSchema = z.object({
const updateTopicCoverSchema = z.object({
export const generationTopicRouter = router({
export type GenerationTopicRouter = typeof generationTopicRouter;
export type UpdateTopicInput = z.infer<typeof updateTopicSchema>;
export type UpdateTopicValue = UpdateTopicInput['value'];
export type UpdateTopicCoverInput = z.infer<typeof updateTopicCoverSchema>;
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { z } from 'zod';

import { GenerationTopicModel } from '@/database/models/generationTopic';
import { type GenerationTopicItem } from '@/database/schemas/generation';
import { authedProcedure, router } from '@/libs/trpc/lambda';
import { serverDatabase } from '@/libs/trpc/lambda/middleware';
import { FileService } from '@/server/services/file';
import { GenerationService } from '@/server/services/generation';

const generationTopicProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
  const { ctx } = opts;

  return opts.next({
    ctx: {
      fileService: new FileService(ctx.serverDB, ctx.userId),
      generationService: new GenerationService(ctx.serverDB, ctx.userId),
      generationTopicModel: new GenerationTopicModel(ctx.serverDB, ctx.userId),
    },
  });
});

// Define input schemas
const updateTopicSchema = z.object({
  id: z.string(),
  value: z.object({
    coverUrl: z.string().nullable().optional(),
    title: z.string().nullable().optional(),
  }),
});

const updateTopicCoverSchema = z.object({
  coverUrl: z.string(),
  id: z.string(),
});

export const generationTopicRouter = router({
  createTopic: generationTopicProcedure
    .input(z.object({ type: z.enum(['image', 'video']).optional() }).optional())
    .mutation(async ({ ctx, input }) => {
      const data = await ctx.generationTopicModel.create('', input?.type);
      return data.id;
    }),
  deleteTopic: generationTopicProcedure
    .input(z.object({ id: z.string() }))
    .mutation(async ({ ctx, input }) => {
      // 1. Delete database records and get file URLs to clean
      const result = await ctx.generationTopicModel.delete(input.id);

      // If topic not found, throw an error instead of returning undefined
      if (!result) {
        return;
      }

      const { deletedTopic, filesToDelete } = result;

      // 2. Clean up all files from S3 (cover image and thumbnails)
      // Note: Even if file deletion fails, we consider the topic deletion successful
      // since the database record has been removed and users won't see the topic anymore
      if (filesToDelete.length > 0) {
        try {
          await ctx.fileService.deleteFiles(filesToDelete);
        } catch (error) {
          // Log the error but don't throw - file cleanup failure shouldn't affect
          // the user experience since the database operation succeeded
          console.error('Failed to delete files from S3:', error);
        }
      }

      return deletedTopic;
    }),
  getAllGenerationTopics: generationTopicProcedure
    .input(z.object({ type: z.enum(['image', 'video']).optional() }).optional())
    .query(async ({ ctx, input }) => {
      return ctx.generationTopicModel.queryAll(input?.type);
    }),
  updateTopic: generationTopicProcedure
    .input(updateTopicSchema)
    .mutation(async ({ ctx, input }) => {
      return ctx.generationTopicModel.update(input.id, input.value as Partial<GenerationTopicItem>);
    }),
  updateTopicCover: generationTopicProcedure
    .input(updateTopicCoverSchema)
    .mutation(async ({ ctx, input }) => {
      // Process the cover image and get key
      const newCoverKey = await ctx.generationService.createCoverFromUrl(input.coverUrl);

      // Update the topic with the new cover key
      return ctx.generationTopicModel.update(input.id, { coverUrl: newCoverKey });
    }),
});

export type GenerationTopicRouter = typeof generationTopicRouter;

// Export input types for client/server service consistency
export type UpdateTopicInput = z.infer<typeof updateTopicSchema>;
export type UpdateTopicValue = UpdateTopicInput['value'];
export type UpdateTopicCoverInput = z.infer<typeof updateTopicCoverSchema>;

```
