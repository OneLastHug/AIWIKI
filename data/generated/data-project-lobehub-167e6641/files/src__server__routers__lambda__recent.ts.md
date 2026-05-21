# 文件：src/server/routers/lambda/recent.ts

## 文件职责
这个文件位于 `src/server/routers/lambda`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import type { TaskStatus } from '@lobechat/types';
import { z } from 'zod';
import { SESSION_CHAT_TOPIC_URL } from '@/const/url';
import { RecentModel } from '@/database/models/recent';
import { authedProcedure, router } from '@/libs/trpc/lambda';
import { serverDatabase } from '@/libs/trpc/lambda/middleware';
import type { ChatTopicMetadata } from '@/types/topic';
export interface RecentItem {
export const recentRouter = router({
export type RecentRouter = typeof recentRouter;
```

## 主要对外内容
```text
export interface RecentItem {
const recentProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
export const recentRouter = router({
export type RecentRouter = typeof recentRouter;
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import type { TaskStatus } from '@lobechat/types';
import { z } from 'zod';

import { SESSION_CHAT_TOPIC_URL } from '@/const/url';
import { RecentModel } from '@/database/models/recent';
import { authedProcedure, router } from '@/libs/trpc/lambda';
import { serverDatabase } from '@/libs/trpc/lambda/middleware';
import type { ChatTopicMetadata } from '@/types/topic';

export interface RecentItem {
  agentId?: string | null;
  icon: string;
  id: string;
  metadata?: ChatTopicMetadata;
  routePath: string;
  /** Task lifecycle status when `type === 'task'`; null for topic/document. */
  status: TaskStatus | null;
  title: string;
  type: 'topic' | 'document' | 'task';
  updatedAt: Date;
}

const recentProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
  const { ctx } = opts;
  return opts.next({
    ctx: {
      recentModel: new RecentModel(ctx.serverDB, ctx.userId),
    },
  });
});

export const recentRouter = router({
  getAll: recentProcedure
    .input(z.object({ limit: z.number().optional() }).optional())
    .query(async ({ ctx, input }): Promise<RecentItem[]> => {
      const limit = input?.limit ?? 10;

      const items = await ctx.recentModel.queryRecent(limit);

      return items.map((item) => {
        let routePath: string;

        switch (item.type) {
          case 'topic': {
            if (item.routeGroupId) {
              routePath = `/group/${item.routeGroupId}?topic=${item.id}`;
            } else if (item.routeId) {
              routePath = SESSION_CHAT_TOPIC_URL(item.routeId, item.id);
            } else {
              routePath = '/';
            }
            break;
          }
          case 'document': {
            routePath = `/page/${item.id}`;
            break;
          }
          case 'task': {
            routePath = item.routeId
              ? `/agent/${item.routeId}/task/${item.id}`
              : `/task/${item.id}`;
            break;
          }
        }

        return {
          agentId: item.routeId,
          icon: item.type,
          id: item.id,
          metadata: item.metadata as ChatTopicMetadata | undefined,
          routePath,
          status: item.status,
          title: item.title,
          type: item.type,
          updatedAt: item.updatedAt,
        };
      });
    }),
});

export type RecentRouter = typeof recentRouter;

```
