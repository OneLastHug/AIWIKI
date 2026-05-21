# 文件：src/server/routers/lambda/changelog.ts

## 文件职责
这个文件位于 `src/server/routers/lambda`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { TRPCError } from '@trpc/server';
import { z } from 'zod';
import { publicProcedure, router } from '@/libs/trpc/lambda';
import { ChangelogService } from '@/server/services/changelog';
export const changelogRouter = router({
export type ChangelogRouter = typeof changelogRouter;
```

## 主要对外内容
```text
const changelogProcedure = publicProcedure.use(async ({ next }) => {
export const changelogRouter = router({
export type ChangelogRouter = typeof changelogRouter;
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { TRPCError } from '@trpc/server';
import { z } from 'zod';

import { publicProcedure, router } from '@/libs/trpc/lambda';
import { ChangelogService } from '@/server/services/changelog';

const changelogProcedure = publicProcedure.use(async ({ next }) => {
  return next({
    ctx: {
      changelogService: new ChangelogService(),
    },
  });
});

export const changelogRouter = router({
  getIndex: changelogProcedure.query(async ({ ctx }) => {
    try {
      return await ctx.changelogService.getChangelogIndex();
    } catch (e) {
      throw new TRPCError({
        code: 'INTERNAL_SERVER_ERROR',
        message: 'Failed to fetch changelog index',
      });
    }
  }),

  getPostById: changelogProcedure
    .input(
      z.object({
        id: z.string(),
        locale: z.string().optional(),
      }),
    )
    .query(async ({ input, ctx }) => {
      try {
        return await ctx.changelogService.getPostById(input.id, { locale: input.locale as any });
      } catch (e) {
        throw new TRPCError({
          code: 'INTERNAL_SERVER_ERROR',
          message: 'Failed to fetch changelog post',
        });
      }
    }),
});

export type ChangelogRouter = typeof changelogRouter;

```
