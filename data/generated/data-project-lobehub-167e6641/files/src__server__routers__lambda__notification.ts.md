# 文件：src/server/routers/lambda/notification.ts

## 文件职责
这个文件位于 `src/server/routers/lambda`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { z } from 'zod';
import { NotificationModel } from '@/database/models/notification';
import { authedProcedure, router } from '@/libs/trpc/lambda';
import { serverDatabase } from '@/libs/trpc/lambda/middleware';
export const notificationRouter = router({
export type NotificationRouter = typeof notificationRouter;
```

## 主要对外内容
```text
const notificationProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
export const notificationRouter = router({
export type NotificationRouter = typeof notificationRouter;
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { z } from 'zod';

import { NotificationModel } from '@/database/models/notification';
import { authedProcedure, router } from '@/libs/trpc/lambda';
import { serverDatabase } from '@/libs/trpc/lambda/middleware';

const notificationProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
  const { ctx } = opts;

  return opts.next({
    ctx: { notificationModel: new NotificationModel(ctx.serverDB, ctx.userId) },
  });
});

export const notificationRouter = router({
  archive: notificationProcedure
    .input(z.object({ id: z.string() }))
    .mutation(async ({ ctx, input }) => {
      return ctx.notificationModel.archive(input.id);
    }),

  archiveAll: notificationProcedure.mutation(async ({ ctx }) => {
    return ctx.notificationModel.archiveAll();
  }),

  list: notificationProcedure
    .input(
      z.object({
        category: z.string().optional(),
        cursor: z.string().optional(),
        limit: z.number().min(1).max(50).default(20),
        unreadOnly: z.boolean().optional(),
      }),
    )
    .query(async ({ ctx, input }) => {
      return ctx.notificationModel.list(input);
    }),

  markAllAsRead: notificationProcedure.mutation(async ({ ctx }) => {
    return ctx.notificationModel.markAllAsRead();
  }),

  markAsRead: notificationProcedure
    .input(z.object({ ids: z.array(z.string()).min(1) }))
    .mutation(async ({ ctx, input }) => {
      return ctx.notificationModel.markAsRead(input.ids);
    }),

  unreadCount: notificationProcedure.query(async ({ ctx }) => {
    return ctx.notificationModel.getUnreadCount();
  }),
});

export type NotificationRouter = typeof notificationRouter;

```
