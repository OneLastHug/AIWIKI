# 文件：src/server/routers/lambda/plugin.ts

## 文件职责
这个文件位于 `src/server/routers/lambda`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { type LobeTool } from '@lobechat/types';
import { z } from 'zod';
import { PluginModel } from '@/database/models/plugin';
import { getServerDB } from '@/database/server';
import { authedProcedure, publicProcedure, router } from '@/libs/trpc/lambda';
import { serverDatabase } from '@/libs/trpc/lambda/middleware';
export const pluginRouter = router({
export type PluginRouter = typeof pluginRouter;
```

## 主要对外内容
```text
const pluginProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
export const pluginRouter = router({
export type PluginRouter = typeof pluginRouter;
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { type LobeTool } from '@lobechat/types';
import { z } from 'zod';

import { PluginModel } from '@/database/models/plugin';
import { getServerDB } from '@/database/server';
import { authedProcedure, publicProcedure, router } from '@/libs/trpc/lambda';
import { serverDatabase } from '@/libs/trpc/lambda/middleware';

const pluginProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
  const { ctx } = opts;

  return opts.next({
    ctx: { pluginModel: new PluginModel(ctx.serverDB, ctx.userId) },
  });
});

export const pluginRouter = router({
  createOrInstallPlugin: pluginProcedure
    .input(
      z.object({
        customParams: z.any(),
        identifier: z.string(),
        manifest: z.any(),
        settings: z.any(),
        type: z.enum(['plugin', 'customPlugin']),
      }),
    )
    .mutation(async ({ input, ctx }) => {
      const result = await ctx.pluginModel.findById(input.identifier);

      // if not exist, we should create the plugin
      if (!result) {
        const data = await ctx.pluginModel.create({
          customParams: input.customParams,
          identifier: input.identifier,
          manifest: input.manifest,
          settings: input.settings,
          type: input.type,
        });

        return data.identifier;
      }

      // or we can just update the plugin manifest
      await ctx.pluginModel.update(input.identifier, { manifest: input.manifest });
    }),

  createPlugin: pluginProcedure
    .input(
      z.object({
        customParams: z.any(),
        identifier: z.string(),
        manifest: z.any(),
        type: z.enum(['plugin', 'customPlugin']),
      }),
    )
    .mutation(async ({ input, ctx }) => {
      const data = await ctx.pluginModel.create({
        customParams: input.customParams,
        identifier: input.identifier,
        manifest: input.manifest,
        type: input.type,
      });

      return data.identifier;
    }),

  // TODO: In the future, this method also needs to use authedProcedure
  getPlugins: publicProcedure.query(async ({ ctx }): Promise<LobeTool[]> => {
    if (!ctx.userId) return [];

    const serverDB = await getServerDB();
    const pluginModel = new PluginModel(serverDB, ctx.userId);

    return pluginModel.query();
  }),

  removeAllPlugins: pluginProcedure.mutation(async ({ ctx }) => {
    return ctx.pluginModel.deleteAll();
  }),

  removePlugin: pluginProcedure
    .input(z.object({ id: z.string() }))
    .mutation(async ({ input, ctx }) => {
      return ctx.pluginModel.delete(input.id);
    }),

  updatePlugin: pluginProcedure
    .input(
      z.object({
        customParams: z.any().optional(),
        id: z.string(),
        manifest: z.any().optional(),
        settings: z.any().optional(),
      }),
    )
    .mutation(async ({ input, ctx }) => {
      return ctx.pluginModel.update(input.id, {
        customParams: input.customParams,
        manifest: input.manifest,
        settings: input.settings,
      });
    }),
});

export type PluginRouter = typeof pluginRouter;

```
