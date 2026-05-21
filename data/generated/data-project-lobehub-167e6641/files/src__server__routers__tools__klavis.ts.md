# 文件：src/server/routers/tools/klavis.ts

## 文件职责
这个文件位于 `src/server/routers/tools`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { z } from 'zod';
import { getKlavisClient } from '@/libs/klavis';
import { authedProcedure, publicProcedure, router } from '@/libs/trpc/lambda';
import { MCPService } from '@/server/services/mcp';
export const klavisRouter = router({
```

## 主要对外内容
```text
const klavisProcedure = authedProcedure.use(async (opts) => {
export const klavisRouter = router({
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { z } from 'zod';

import { getKlavisClient } from '@/libs/klavis';
import { authedProcedure, publicProcedure, router } from '@/libs/trpc/lambda';
import { MCPService } from '@/server/services/mcp';

/**
 * Klavis procedure with client initialized in context
 */
const klavisProcedure = authedProcedure.use(async (opts) => {
  const klavisClient = getKlavisClient();

  return opts.next({
    ctx: { ...opts.ctx, klavisClient },
  });
});

/**
 * Klavis router for tools
 * Contains callTool and listTools which call external Klavis API
 */
export const klavisRouter = router({
  /**
   * Call a tool on a Klavis Strata server
   */
  callTool: klavisProcedure
    .input(
      z.object({
        serverUrl: z.string(),
        toolArgs: z.record(z.unknown()).optional(),
        toolName: z.string(),
      }),
    )
    .mutation(async ({ ctx, input }) => {
      const response = await ctx.klavisClient.mcpServer.callTools({
        serverUrl: input.serverUrl,
        toolArgs: input.toolArgs,
        toolName: input.toolName,
      });

      // Handle error case
      if (!response.success || !response.result) {
        return {
          content: response.error || 'Unknown error',
          state: {
            content: [{ text: response.error || 'Unknown error', type: 'text' }],
            isError: true,
          },
          success: false,
        };
      }

      // Process the response using the common MCP tool call result processor
      const processedResult = await MCPService.processToolCallResult({
        content: (response.result.content || []) as any[],
        isError: response.result.isError,
      });

      return processedResult;
    }),

  /**
   * Get tools by server name (public endpoint, no auth required)
   */
  getTools: publicProcedure
    .input(
      z.object({
        serverName: z.string(),
      }),
    )
    .query(async ({ input }) => {
      const klavisClient = getKlavisClient();
      const response = await klavisClient.mcpServer.getTools(input.serverName as any);

      return {
        tools: response.tools,
      };
    }),

  /**
   * List tools available on a Klavis Strata server
   */
  listTools: klavisProcedure
    .input(
      z.object({
        serverUrl: z.string(),
      }),
    )
    .query(async ({ ctx, input }) => {
      const response = await ctx.klavisClient.mcpServer.listTools({
        serverUrl: input.serverUrl,
      });

      return {
        tools: response.tools,
      };
    }),
});

```
