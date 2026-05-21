# 文件：src/server/routers/lambda/usage.ts

## 文件职责
这个文件位于 `src/server/routers/lambda`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { z } from 'zod';
import { authedProcedure, router } from '@/libs/trpc/lambda';
import { serverDatabase } from '@/libs/trpc/lambda/middleware';
import { UsageRecordService } from '@/server/services/usage';
export const usageRouter = router({
```

## 主要对外内容
```text
const usageProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
export const usageRouter = router({
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { z } from 'zod';

import { authedProcedure, router } from '@/libs/trpc/lambda';
import { serverDatabase } from '@/libs/trpc/lambda/middleware';
import { UsageRecordService } from '@/server/services/usage';

const usageProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
  const { ctx } = opts;
  return opts.next({
    ctx: {
      usageRecordService: new UsageRecordService(ctx.serverDB, ctx.userId),
    },
  });
});

export const usageRouter = router({
  findAndGroupByDateRange: usageProcedure
    .input(
      z.object({
        endAt: z.string(),
        startAt: z.string(),
      }),
    )
    .query(async ({ ctx, input }) => {
      return await ctx.usageRecordService.findAndGroupByDateRange(input.startAt, input.endAt);
    }),

  findAndGroupByDay: usageProcedure
    .input(
      z.object({
        mo: z.string().optional(),
      }),
    )
    .query(async ({ ctx, input }) => {
      return await ctx.usageRecordService.findAndGroupByDay(input.mo);
    }),

  findByMonth: usageProcedure
    .input(
      z.object({
        mo: z.string().optional(),
      }),
    )
    .query(async ({ ctx, input }) => {
      return await ctx.usageRecordService.findByMonth(input.mo);
    }),
});

```
