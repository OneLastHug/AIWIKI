# 文件：src/server/routers/mobile/topic.ts

## 文件职责
这个文件位于 `src/server/routers/mobile`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { z } from 'zod';
import { TopicModel } from '@/database/models/topic';
import { getServerDB } from '@/database/server';
import { authedProcedure, publicProcedure, router } from '@/libs/trpc/lambda';
import { serverDatabase } from '@/libs/trpc/lambda/middleware';
import { type BatchTaskResult } from '@/types/service';
export const topicRouter = router({
export type TopicRouter = typeof topicRouter;
```

## 主要对外内容
```text
const topicProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
export const topicRouter = router({
export type TopicRouter = typeof topicRouter;
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { z } from 'zod';

import { TopicModel } from '@/database/models/topic';
import { getServerDB } from '@/database/server';
import { authedProcedure, publicProcedure, router } from '@/libs/trpc/lambda';
import { serverDatabase } from '@/libs/trpc/lambda/middleware';
import { type BatchTaskResult } from '@/types/service';

const topicProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
  const { ctx } = opts;

  return opts.next({
    ctx: { topicModel: new TopicModel(ctx.serverDB, ctx.userId) },
  });
});

export const topicRouter = router({
  batchCreateTopics: topicProcedure
    .input(
      z.array(
        z.object({
          favorite: z.boolean().optional(),
          id: z.string().optional(),
          messages: z.array(z.string()).optional(),
          sessionId: z.string().optional(),
          title: z.string(),
        }),
      ),
    )
    .mutation(async ({ input, ctx }): Promise<BatchTaskResult> => {
      const data = await ctx.topicModel.batchCreate(
        input.map((item) => ({
          ...item,
        })) as any,
      );

      return { added: data.length, ids: [], skips: [], success: true };
    }),

  batchDelete: topicProcedure
    .input(z.object({ ids: z.array(z.string()) }))
    .mutation(async ({ input, ctx }) => {
      return ctx.topicModel.batchDelete(input.ids);
    }),

  batchDeleteBySessionId: topicProcedure
    .input(z.object({ id: z.string().nullable().optional() }))
    .mutation(async ({ input, ctx }) => {
      return ctx.topicModel.batchDeleteBySessionId(input.id);
    }),

  cloneTopic: topicProcedure
    .input(z.object({ id: z.string(), newTitle: z.string().optional() }))
    .mutation(async ({ input, ctx }) => {
      const data = await ctx.topicModel.duplicate(input.id, input.newTitle);

      return data.topic.id;
    }),

  countTopics: topicProcedure
    .input(
      z
        .object({
          endDate: z.string().optional(),
          range: z.tuple([z.string(), z.string()]).optional(),
          startDate: z.string().optional(),
        })
        .optional(),
    )
    .query(async ({ ctx, input }) => {
      return ctx.topicModel.count(input);
    }),

  createTopic: topicProcedure
    .input(
      z.object({
        favorite: z.boolean().optional(),
        groupId: z.string().nullable().optional(),
        messages: z.array(z.string()).optional(),
        sessionId: z.string().nullable().optional(),
        title: z.string(),
      }),
    )
    .mutation(async ({ input, ctx }) => {
      const data = await ctx.topicModel.create(input);

      return data.id;
    }),

  getAllTopics: topicProcedure.query(async ({ ctx }) => {
    return ctx.topicModel.queryAll();
  }),

  // TODO: this procedure should be used with authedProcedure
  getTopics: publicProcedure
    .input(
      z.object({
        containerId: z.string().nullable().optional(),
        current: z.number().optional(),
        pageSize: z.number().optional(),
      }),
    )
    .query(async ({ input, ctx }) => {
      if (!ctx.userId) return [];

      const serverDB = await getServerDB();
      const topicModel = new TopicModel(serverDB, ctx.userId);

      return topicModel.query(input);
    }),

  hasTopics: topicProcedure.query(async ({ ctx }) => {
    return (await ctx.topicModel.count()) === 0;
  }),

  rankTopics: topicProcedure.input(z.number().optional()).query(async ({ ctx, input }) => {
    return ctx.topicModel.rank(input);
  }),

  removeAllTopics: topicProcedure.mutation(async ({ ctx }) => {
    return ctx.topicModel.deleteAll();
  }),

  removeTopic: topicProcedure
    .input(z.object({ id: z.string() }))
    .mutation(async ({ input, ctx }) => {
      return ctx.topicModel.delete(input.id);
    }),

  searchTopics: topicProcedure
    .input(
      z.object({
        groupId: z.string().nullable().optional(),
        keywords: z.string(),
        sessionId: z.string().nullable().optional(),
      }),
    )
    .query(async ({ input, ctx }) => {
      return ctx.topicModel.queryByKeyword(input.keywords, input.sessionId);
    }),

  updateTopic: topicProcedure
    .input(
      z.object({
        id: z.string(),
        value: z.object({
          favorite: z.boolean().optional(),
          historySummary: z.string().optional(),
          messages: z.array(z.string()).optional(),
          metadata: z
            .object({
              model: z.string().optional(),
              provider: z.string().optional(),
            })
            .optional(),
          sessionId: z.string().optional(),
          title: z.string().optional(),
        }),
      }),
    )
    .mutation(async ({ input, ctx }) => {
      return ctx.topicModel.update(input.id, input.value);
    }),
});

export type TopicRouter = typeof topicRouter;

```
