# 文件：src/server/routers/lambda/sessionGroup.ts

## 文件职责
这个文件位于 `src/server/routers/lambda`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { z } from 'zod';
import { SessionGroupModel } from '@/database/models/sessionGroup';
import { insertSessionGroupSchema } from '@/database/schemas';
import { authedProcedure, router } from '@/libs/trpc/lambda';
import { serverDatabase } from '@/libs/trpc/lambda/middleware';
import { type SessionGroupItem } from '@/types/session';
export const sessionGroupRouter = router({
export type SessionGroupRouter = typeof sessionGroupRouter;
```

## 主要对外内容
```text
const sessionProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
export const sessionGroupRouter = router({
export type SessionGroupRouter = typeof sessionGroupRouter;
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { z } from 'zod';

import { SessionGroupModel } from '@/database/models/sessionGroup';
import { insertSessionGroupSchema } from '@/database/schemas';
import { authedProcedure, router } from '@/libs/trpc/lambda';
import { serverDatabase } from '@/libs/trpc/lambda/middleware';
import { type SessionGroupItem } from '@/types/session';

const sessionProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
  const { ctx } = opts;

  return opts.next({
    ctx: {
      sessionGroupModel: new SessionGroupModel(ctx.serverDB, ctx.userId),
    },
  });
});

export const sessionGroupRouter = router({
  createSessionGroup: sessionProcedure
    .input(
      z.object({
        name: z.string(),
        sort: z.number().optional(),
      }),
    )
    .mutation(async ({ input, ctx }) => {
      const data = await ctx.sessionGroupModel.create({
        name: input.name,
        sort: input.sort,
      });

      return data?.id;
    }),

  getSessionGroup: sessionProcedure.query(async ({ ctx }): Promise<SessionGroupItem[]> => {
    return ctx.sessionGroupModel.query() as any;
  }),

  removeAllSessionGroups: sessionProcedure.mutation(async ({ ctx }) => {
    return ctx.sessionGroupModel.deleteAll();
  }),

  removeSessionGroup: sessionProcedure
    .input(z.object({ id: z.string(), removeChildren: z.boolean().optional() }))
    .mutation(async ({ input, ctx }) => {
      return ctx.sessionGroupModel.delete(input.id);
    }),

  updateSessionGroup: sessionProcedure
    .input(
      z.object({
        id: z.string(),
        value: insertSessionGroupSchema.partial(),
      }),
    )
    .mutation(async ({ input, ctx }) => {
      return ctx.sessionGroupModel.update(input.id, input.value);
    }),
  updateSessionGroupOrder: sessionProcedure
    .input(
      z.object({
        sortMap: z.array(
          z.object({
            id: z.string(),
            sort: z.number(),
          }),
        ),
      }),
    )
    .mutation(async ({ input, ctx }) => {
      console.info('sortMap:', input.sortMap);

      return ctx.sessionGroupModel.updateOrder(input.sortMap);
    }),
});

export type SessionGroupRouter = typeof sessionGroupRouter;

```
