# 文件：src/server/routers/lambda/home.ts

## 文件职责
这个文件位于 `src/server/routers/lambda`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { after } from 'next/server';
import { z } from 'zod';
import { AgentModel } from '@/database/models/agent';
import { AgentMigrationRepo } from '@/database/repositories/agentMigration';
import { HomeRepository } from '@/database/repositories/home';
import { authedProcedure, router } from '@/libs/trpc/lambda';
import { serverDatabase } from '@/libs/trpc/lambda/middleware';
import { type HomeBriefData, HomeService } from '@/server/services/home';
export const homeRouter = router({
export type HomeRouter = typeof homeRouter;
```

## 主要对外内容
```text
const homeProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
export const homeRouter = router({
export type HomeRouter = typeof homeRouter;
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { after } from 'next/server';
import { z } from 'zod';

import { AgentModel } from '@/database/models/agent';
import { AgentMigrationRepo } from '@/database/repositories/agentMigration';
import { HomeRepository } from '@/database/repositories/home';
import { authedProcedure, router } from '@/libs/trpc/lambda';
import { serverDatabase } from '@/libs/trpc/lambda/middleware';
import { type HomeBriefData, HomeService } from '@/server/services/home';

const homeProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
  const { ctx } = opts;

  return opts.next({
    ctx: {
      agentMigrationRepo: new AgentMigrationRepo(ctx.serverDB, ctx.userId),
      agentModel: new AgentModel(ctx.serverDB, ctx.userId),
      homeRepository: new HomeRepository(ctx.serverDB, ctx.userId),
      homeService: new HomeService(ctx.userId),
    },
  });
});

export const homeRouter = router({
  getDailyBrief: homeProcedure.query(
    ({ ctx }): Promise<HomeBriefData> => ctx.homeService.getDailyBrief(),
  ),

  getSidebarAgentList: homeProcedure.query(async ({ ctx }) => {
    const result = await ctx.homeRepository.getSidebarAgentList();

    // Runtime migration: backfill sessionGroupId for legacy agents
    const runMigration = async () => {
      try {
        await ctx.agentMigrationRepo.migrateSessionGroupId();
      } catch (error) {
        console.error('[AgentMigration] Failed to migrate sessionGroupId:', error);
      }
    };

    // Use Next.js after() for non-blocking execution
    after(runMigration);

    return result;
  }),

  searchAgents: homeProcedure
    .input(z.object({ keyword: z.string() }))
    .query(async ({ input, ctx }) => {
      return ctx.homeRepository.searchAgents(input.keyword);
    }),

  updateAgentSessionGroupId: homeProcedure
    .input(
      z.object({
        agentId: z.string(),
        sessionGroupId: z.string().nullable(),
      }),
    )
    .mutation(async ({ input, ctx }) => {
      return ctx.agentModel.updateSessionGroupId(input.agentId, input.sessionGroupId);
    }),
});

export type HomeRouter = typeof homeRouter;

```
