# 文件：src/server/routers/lambda/search.ts

## 文件职责
这个文件位于 `src/server/routers/lambda`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { z } from 'zod';
import { SearchRepo } from '@/database/repositories/search';
import { authedProcedure, router } from '@/libs/trpc/lambda';
import { serverDatabase } from '@/libs/trpc/lambda/middleware';
import { DiscoverService } from '@/server/services/discover';
export const searchRouter = router({
```

## 主要对外内容
```text
function calculateMarketplaceRelevance(query: string, title: string): number {
const searchProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
export const searchRouter = router({
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { z } from 'zod';

import { SearchRepo } from '@/database/repositories/search';
import { authedProcedure, router } from '@/libs/trpc/lambda';
import { serverDatabase } from '@/libs/trpc/lambda/middleware';
import { DiscoverService } from '@/server/services/discover';

/**
 * Calculate relevance score for marketplace items
 * 1 = exact match, 2 = prefix match, 3 = contains match
 */
function calculateMarketplaceRelevance(query: string, title: string): number {
  const lowerQuery = query.toLowerCase().trim();
  const lowerTitle = title.toLowerCase();

  if (lowerTitle === lowerQuery) return 1;
  if (lowerTitle.startsWith(lowerQuery)) return 2;
  if (lowerTitle.includes(lowerQuery)) return 3;
  return 4;
}

const searchProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
  const { ctx } = opts;

  return opts.next({
    ctx: {
      discoverService: new DiscoverService({ accessToken: ctx.marketAccessToken }),
      searchRepo: new SearchRepo(ctx.serverDB, ctx.userId),
    },
  });
});

/**
 * The unified search router for all entities in the database.
 *
 * Can specify the type of entity to search for.
 */
export const searchRouter = router({
  query: searchProcedure
    .input(
      z.object({
        agentId: z.string().optional(),
        limitPerType: z.number().optional(),
        locale: z.string().optional(),
        offset: z.number().optional(),
        query: z.string(),
        type: z
          .enum([
            'agent',
            'chatGroup',
            'topic',
            'file',
            'folder',
            'message',
            'page',
            'memory',
            'mcp',
            'plugin',
            'communityAgent',
            'knowledgeBase',
          ])
          .optional(),
      }),
    )
    .query(async ({ input, ctx }) => {
      const { query, type, limitPerType = 5, locale } = input;

      // Early return for empty query
      if (!query || query.trim() === '') return [];

      // Build search promises based on type filter
      const searchPromises: Promise<any>[] = [];

      // Database searches (agent, topic, file, folder, message, page, memory)
      if (
        !type ||
        [
          'agent',
          'chatGroup',
          'topic',
          'file',
          'folder',
          'message',
          'page',
          'memory',
          'knowledgeBase',
        ].includes(type)
      ) {
        searchPromises.push(ctx.searchRepo.search(input));
      }

      // Marketplace searches (mcp, plugin)
      if (!type || type === 'mcp') {
        searchPromises.push(
          ctx.discoverService
            .getMcpList({
              locale,
              pageSize: limitPerType,
              q: query,
            })
            .then((response) =>
              response.items.slice(0, limitPerType).map((item: any) => ({
                author:
                  typeof item.author === 'string' ? item.author : item.author?.name || 'Unknown',
                avatar: item.avatar || item.icon || null,
                category: item.category || null,
                connectionType: item.connectionType || null,
                createdAt: new Date(item.createdAt || Date.now()),
                description: item.description || null,
                id: item.identifier,
                identifier: item.identifier,
                installCount: item.installCount || null,
                isFeatured: item.isFeatured || null,
                isValidated: item.isValidated || null,
                relevance: calculateMarketplaceRelevance(
                  query,
                  (item.name || item.title || item.identifier) as string,
                ),
                tags: item.tags || null,
                title: (item.name || item.title || item.identifier) as string,
                type: 'mcp' as const,
                updatedAt: new Date(item.updatedAt || Date.now()),
              })),
            )
            .catch(() => []),
        );
      }

      if (!type || type === 'plugin') {
        searchPromises.push(
          ctx.discoverService
            .getPluginList({
              locale,
              pageSize: limitPerType,
              q: query,
            })
            .then((response) =>
              response.items.slice(0, limitPerType).map((item: any) => ({
                author:
                  typeof item.author === 'string' ? item.author : item.author?.name || 'Unknown',
                avatar: item.avatar || null,
                category: item.category || null,
                createdAt: new Date(item.createdAt || Date.now()),
                description: item.description || null,
                id: item.identifier,
                identifier: item.identifier,
                relevance: calculateMarketplaceRelevance(
                  query,
                  (item.title || item.identifier) as string,
                ),
                tags: item.tags || null,
                title: (item.title || item.identifier) as string,
                type: 'plugin' as const,
                updatedAt: new Date(item.updatedAt || Date.now()),
              })),
            )
            .catch(() => []),
        );
      }

      if (!type || type === 'communityAgent') {
        searchPromises.push(
          ctx.discoverService
            .getAssistantList({
              includeAgentGroup: true,
              locale,
              pageSize: limitPerType,
              q: query,
            })
            .then((response) =>
              response.items.slice(0, limitPerType).map((item: any) => ({
                author:
                  typeof item.author === 'string' ? item.author : item.author?.name || 'Unknown',
                avatar: item.avatar || null,
                createdAt: new Date(item.createdAt || Date.now()),
                description: item.description || null,
                homepage: item.homepage || null,
                id: item.identifier,
                identifier: item.identifier,
                relevance: calculateMarketplaceRelevance(
                  query,
                  (item.title || item.identifier) as string,
                ),
                tags: item.tags || null,
                title: (item.title || item.identifier) as string,
                type: 'communityAgent' as const,
                updatedAt: new Date(item.updatedAt || Date.now()),
              })),
            )
            .catch(() => []),
        );
      }

      // Execute searches in parallel and merge results
      const results = await Promise.all(searchPromises);
      const mergedResults = results.flat();

      // Sort by relevance and limit total results
      return mergedResults.sort((a, b) => {
        if (a.relevance !== b.relevance) return a.relevance - b.relevance;
        return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime();
      });
    }),
});

```
