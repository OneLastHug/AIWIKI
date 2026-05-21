# 文件：src/server/routers/lambda/aiModel.ts

## 文件职责
这个文件位于 `src/server/routers/lambda`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { type AiProviderModelListItem } from 'model-bank';
import {
import { z } from 'zod';
import { AiModelModel } from '@/database/models/aiModel';
import { UserModel } from '@/database/models/user';
import { AiInfraRepos } from '@/database/repositories/aiInfra';
import { authedProcedure, router } from '@/libs/trpc/lambda';
import { serverDatabase } from '@/libs/trpc/lambda/middleware';
import { getServerGlobalConfig } from '@/server/globalConfig';
import { KeyVaultsGateKeeper } from '@/server/modules/KeyVaultsEncrypt';
import { type ProviderConfig } from '@/types/user/settings';
export const aiModelRouter = router({
export type AiModelRouter = typeof aiModelRouter;
```

## 主要对外内容
```text
const aiModelProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
export const aiModelRouter = router({
export type AiModelRouter = typeof aiModelRouter;
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { type AiProviderModelListItem } from 'model-bank';
import {
  AiModelTypeSchema,
  CreateAiModelSchema,
  ToggleAiModelEnableSchema,
  UpdateAiModelSchema,
} from 'model-bank';
import { z } from 'zod';

import { AiModelModel } from '@/database/models/aiModel';
import { UserModel } from '@/database/models/user';
import { AiInfraRepos } from '@/database/repositories/aiInfra';
import { authedProcedure, router } from '@/libs/trpc/lambda';
import { serverDatabase } from '@/libs/trpc/lambda/middleware';
import { getServerGlobalConfig } from '@/server/globalConfig';
import { KeyVaultsGateKeeper } from '@/server/modules/KeyVaultsEncrypt';
import { type ProviderConfig } from '@/types/user/settings';

const aiModelProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
  const { ctx } = opts;

  const gateKeeper = await KeyVaultsGateKeeper.initWithEnvKey();
  const { aiProvider } = await getServerGlobalConfig();

  return opts.next({
    ctx: {
      aiInfraRepos: new AiInfraRepos(
        ctx.serverDB,
        ctx.userId,
        aiProvider as Record<string, ProviderConfig>,
      ),
      aiModelModel: new AiModelModel(ctx.serverDB, ctx.userId),
      gateKeeper,
      userModel: new UserModel(ctx.serverDB, ctx.userId),
    },
  });
});

export const aiModelRouter = router({
  batchToggleAiModels: aiModelProcedure
    .input(
      z.object({
        enabled: z.boolean(),
        id: z.string(),
        models: z.array(z.string()),
      }),
    )
    .mutation(async ({ input, ctx }) => {
      return ctx.aiModelModel.batchToggleAiModels(input.id, input.models, input.enabled);
    }),
  batchUpdateAiModels: aiModelProcedure
    .input(
      z.object({
        id: z.string(),
        // TODO: Complete validation schema
        models: z.array(z.any()),
      }),
    )
    .mutation(async ({ input, ctx }) => {
      return ctx.aiModelModel.batchUpdateAiModels(input.id, input.models);
    }),

  clearModelsByProvider: aiModelProcedure
    .input(z.object({ providerId: z.string() }))
    .mutation(async ({ input, ctx }) => {
      return ctx.aiModelModel.clearModelsByProvider(input.providerId);
    }),
  clearRemoteModels: aiModelProcedure
    .input(z.object({ providerId: z.string() }))
    .mutation(async ({ input, ctx }) => {
      return ctx.aiModelModel.clearRemoteModels(input.providerId);
    }),

  createAiModel: aiModelProcedure.input(CreateAiModelSchema).mutation(async ({ input, ctx }) => {
    const data = await ctx.aiModelModel.create(input);

    return data?.id;
  }),

  getAiModelById: aiModelProcedure
    .input(z.object({ id: z.string() }))

    .query(async ({ input, ctx }) => {
      return ctx.aiModelModel.findById(input.id);
    }),

  getAiProviderModelList: aiModelProcedure
    .input(
      z.object({
        enabled: z.boolean().optional(),
        id: z.string(),
        limit: z.number().int().min(1).max(200).optional(),
        offset: z.number().int().min(0).optional(),
        type: z.string().optional(),
      }),
    )
    .query(async ({ ctx, input }): Promise<AiProviderModelListItem[]> => {
      return ctx.aiInfraRepos.getAiProviderModelList(input.id, {
        enabled: input.enabled,
        limit: input.limit,
        offset: input.offset,
        type: input.type,
      });
    }),

  removeAiModel: aiModelProcedure
    .input(z.object({ id: z.string(), providerId: z.string() }))
    .mutation(async ({ input, ctx }) => {
      return ctx.aiModelModel.delete(input.id, input.providerId);
    }),

  toggleModelEnabled: aiModelProcedure
    .input(ToggleAiModelEnableSchema)
    .mutation(async ({ input, ctx }) => {
      return ctx.aiModelModel.toggleModelEnabled(input);
    }),

  updateAiModel: aiModelProcedure
    .input(
      z.object({
        id: z.string(),
        providerId: z.string(),
        value: UpdateAiModelSchema,
      }),
    )
    .mutation(async ({ input, ctx }) => {
      return ctx.aiModelModel.update(input.id, input.providerId, input.value);
    }),

  updateAiModelOrder: aiModelProcedure
    .input(
      z.object({
        providerId: z.string(),
        sortMap: z.array(
          z.object({
            id: z.string(),
            sort: z.number(),
            type: AiModelTypeSchema.optional(),
          }),
        ),
      }),
    )
    .mutation(async ({ input, ctx }) => {
      return ctx.aiModelModel.updateModelsOrder(input.providerId, input.sortMap);
    }),
});

export type AiModelRouter = typeof aiModelRouter;

```
