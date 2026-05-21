# 文件：src/server/routers/lambda/apiKey.ts

## 文件职责
这个文件位于 `src/server/routers/lambda`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { z } from 'zod';
import { ApiKeyModel } from '@/database/models/apiKey';
import { authedProcedure, router } from '@/libs/trpc/lambda';
import { serverDatabase } from '@/libs/trpc/lambda/middleware';
export const apiKeyRouter = router({
```

## 主要对外内容
```text
const apiKeyProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
export const apiKeyRouter = router({
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { z } from 'zod';

import { ApiKeyModel } from '@/database/models/apiKey';
import { authedProcedure, router } from '@/libs/trpc/lambda';
import { serverDatabase } from '@/libs/trpc/lambda/middleware';

const apiKeyProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
  const { ctx } = opts;

  return opts.next({
    ctx: {
      apiKeyModel: new ApiKeyModel(ctx.serverDB, ctx.userId),
    },
  });
});

export const apiKeyRouter = router({
  createApiKey: apiKeyProcedure
    .input(
      z.object({
        expiresAt: z.date().optional().nullable(),
        name: z.string(),
      }),
    )
    .mutation(async ({ input, ctx }) => {
      return await ctx.apiKeyModel.create(input);
    }),

  deleteAllApiKeys: apiKeyProcedure.mutation(async ({ ctx }) => {
    return ctx.apiKeyModel.deleteAll();
  }),

  deleteApiKey: apiKeyProcedure
    .input(z.object({ id: z.string() }))
    .mutation(async ({ input, ctx }) => {
      return ctx.apiKeyModel.delete(input.id);
    }),

  getApiKey: apiKeyProcedure
    .input(z.object({ apiKey: z.string() }))
    .query(async ({ input, ctx }) => {
      return ctx.apiKeyModel.findByKey(input.apiKey);
    }),

  getApiKeyById: apiKeyProcedure
    .input(z.object({ id: z.string() }))
    .query(async ({ input, ctx }) => {
      return ctx.apiKeyModel.findById(input.id);
    }),

  getApiKeys: apiKeyProcedure.query(async ({ ctx }) => {
    return ctx.apiKeyModel.query();
  }),

  updateApiKey: apiKeyProcedure
    .input(
      z.object({
        id: z.string(),
        value: z.object({
          description: z.string().optional(),
          enabled: z.boolean().optional(),
          expiresAt: z.date().optional().nullable(),
          name: z.string().optional(),
        }),
      }),
    )
    .mutation(async ({ input, ctx }) => {
      return ctx.apiKeyModel.update(input.id, input.value);
    }),

  validateApiKey: apiKeyProcedure
    .input(z.object({ key: z.string() }))
    .query(async ({ input, ctx }) => {
      return ctx.apiKeyModel.validateKey(input.key);
    }),
});

```
