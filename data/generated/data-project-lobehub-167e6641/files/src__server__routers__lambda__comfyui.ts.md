# 文件：src/server/routers/lambda/comfyui.ts

## 文件职责
这个文件位于 `src/server/routers/lambda`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { type ComfyUIKeyVault } from '@lobechat/types';
import { z } from 'zod';
import { authedProcedure, router } from '@/libs/trpc/lambda';
import { ComfyUIClientService } from '@/server/services/comfyui/core/comfyUIClientService';
import { ImageService } from '@/server/services/comfyui/core/imageService';
import { ModelResolverService } from '@/server/services/comfyui/core/modelResolverService';
import { WorkflowBuilderService } from '@/server/services/comfyui/core/workflowBuilderService';
import { type WorkflowContext } from '@/server/services/comfyui/types';
export const comfyuiRouter = router({
export type ComfyUIRouter = typeof comfyuiRouter;
```

## 主要对外内容
```text
const ComfyUIParamsSchema = z
export const comfyuiRouter = router({
export type ComfyUIRouter = typeof comfyuiRouter;
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { type ComfyUIKeyVault } from '@lobechat/types';
import { z } from 'zod';

import { authedProcedure, router } from '@/libs/trpc/lambda';
// Import Framework layer services
import { ComfyUIClientService } from '@/server/services/comfyui/core/comfyUIClientService';
import { ImageService } from '@/server/services/comfyui/core/imageService';
import { ModelResolverService } from '@/server/services/comfyui/core/modelResolverService';
import { WorkflowBuilderService } from '@/server/services/comfyui/core/workflowBuilderService';
import { type WorkflowContext } from '@/server/services/comfyui/types';

// ComfyUI params validation - only validate required fields
// Other RuntimeImageGenParams fields are passed through automatically
const ComfyUIParamsSchema = z
  .object({
    prompt: z.string(), // Only validate required fields
  })
  .passthrough();

/**
 * ComfyUI tRPC Router
 * Exposes Framework layer services to Runtime layer
 */
export const comfyuiRouter = router({
  /**
   * Create image with complete business logic
   */
  createImage: authedProcedure
    .input(
      z.object({
        model: z.string(),
        options: z.custom<ComfyUIKeyVault>().optional(),
        params: ComfyUIParamsSchema,
      }),
    )
    .mutation(async ({ input }) => {
      const { model, params, options = {} } = input;

      // Initialize Framework layer services
      const clientService = new ComfyUIClientService(options);
      const modelResolverService = new ModelResolverService(clientService);

      // Create workflow context
      const context: WorkflowContext = {
        clientService,
        modelResolverService,
      };

      const workflowBuilderService = new WorkflowBuilderService(context);

      // Initialize image service with all dependencies
      const imageService = new ImageService(
        clientService,
        modelResolverService,
        workflowBuilderService,
      );

      // Execute image creation
      return imageService.createImage({
        model,
        params,
      });
    }),

  /**
   * Get authentication headers for image downloads
   */
  getAuthHeaders: authedProcedure
    .input(
      z.object({
        options: z.custom<ComfyUIKeyVault>().optional(),
      }),
    )
    .query(async ({ input }) => {
      const clientService = new ComfyUIClientService(input.options || {});
      return clientService.getAuthHeaders();
    }),

  /**
   * Get available models
   */
  getModels: authedProcedure
    .input(
      z.object({
        options: z.custom<ComfyUIKeyVault>().optional(),
      }),
    )
    .query(async ({ input }) => {
      const clientService = new ComfyUIClientService(input.options || {});
      const modelResolverService = new ModelResolverService(clientService);

      return modelResolverService.getAvailableModelFiles();
    }),
});

export type ComfyUIRouter = typeof comfyuiRouter;

```
