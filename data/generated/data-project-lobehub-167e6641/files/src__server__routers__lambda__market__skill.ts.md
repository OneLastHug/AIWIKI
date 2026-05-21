# 文件：src/server/routers/lambda/market/skill.ts

## 文件职责
这个文件位于 `src/server/routers/lambda/market`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { TRPCError } from '@trpc/server';
import debug from 'debug';
import { z } from 'zod';
import { publicProcedure, router } from '@/libs/trpc/lambda';
import { marketUserInfo, serverDatabase } from '@/libs/trpc/lambda/middleware';
import { MarketService } from '@/server/services/market';
import { SkillSorts } from '@/types/discover';
export const skillRouter = router({
```

## 主要对外内容
```text
const log = debug('lambda-router:market:skill');
const marketProcedure = publicProcedure
export const skillRouter = router({
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { TRPCError } from '@trpc/server';
import debug from 'debug';
import { z } from 'zod';

import { publicProcedure, router } from '@/libs/trpc/lambda';
import { marketUserInfo, serverDatabase } from '@/libs/trpc/lambda/middleware';
import { MarketService } from '@/server/services/market';
import { SkillSorts } from '@/types/discover';

const log = debug('lambda-router:market:skill');

// Public procedure with optional user info for trusted client token
const marketProcedure = publicProcedure
  .use(serverDatabase)
  .use(marketUserInfo)
  .use(async ({ ctx, next }) => {
    return next({
      ctx: {
        marketService: new MarketService({
          accessToken: ctx.marketAccessToken,
          userInfo: ctx.marketUserInfo,
        }),
      },
    });
  });

export const skillRouter = router({
  getSkillCategories: marketProcedure
    .input(
      z
        .object({
          locale: z.string().optional(),
          q: z.string().optional(),
        })
        .optional(),
    )
    .query(async ({ input, ctx }) => {
      log('getSkillCategories input: %O', input);

      try {
        return await ctx.marketService.getSkillCategories();
      } catch (error) {
        log('Error fetching skill categories: %O', error);
        throw new TRPCError({
          code: 'INTERNAL_SERVER_ERROR',
          message: 'Failed to fetch skill categories',
        });
      }
    }),

  getSkillDetail: marketProcedure
    .input(
      z.object({
        identifier: z.string(),
        locale: z.string().optional(),
        version: z.string().optional(),
      }),
    )
    .query(async ({ input, ctx }) => {
      log('getSkillDetail input: %O', input);

      try {
        return await ctx.marketService.getSkillDetail(input.identifier, {
          locale: input.locale,
          version: input.version,
        });
      } catch (error) {
        log('Error fetching skill detail: %O', error);
        throw new TRPCError({
          code: 'INTERNAL_SERVER_ERROR',
          message: 'Failed to fetch skill detail',
        });
      }
    }),

  getSkillList: marketProcedure
    .input(
      z
        .object({
          category: z.string().optional(),
          locale: z.string().optional(),
          order: z.enum(['asc', 'desc']).optional(),
          page: z.number().optional(),
          pageSize: z.number().optional(),
          q: z.string().optional(),
          sort: z.nativeEnum(SkillSorts).optional(),
        })
        .optional(),
    )
    .query(async ({ input, ctx }) => {
      log('getSkillList input: %O', input);

      try {
        return await ctx.marketService.searchSkill(input ?? {});
      } catch (error) {
        log('Error fetching skill list: %O', error);
        throw new TRPCError({
          code: 'INTERNAL_SERVER_ERROR',
          message: 'Failed to fetch skill list',
        });
      }
    }),
});

```
