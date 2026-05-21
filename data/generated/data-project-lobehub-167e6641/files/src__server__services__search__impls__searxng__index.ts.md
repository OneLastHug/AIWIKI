# 文件：src/server/services/search/impls/searxng/index.ts

## 文件职责
这个文件位于 `src/server/services/search/impls/searxng`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { type UniformSearchResponse } from '@lobechat/types';
import { SEARCH_SEARXNG_NOT_CONFIG } from '@lobechat/types';
import { TRPCError } from '@trpc/server';
import { toolsEnv } from '@/envs/tools';
import { SearXNGClient } from '@/server/services/search/impls/searxng/client';
import { type SearchServiceImpl } from '../type';
export class SearXNGImpl implements SearchServiceImpl {
```

## 主要对外内容
```text
export class SearXNGImpl implements SearchServiceImpl {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { type UniformSearchResponse } from '@lobechat/types';
import { SEARCH_SEARXNG_NOT_CONFIG } from '@lobechat/types';
import { TRPCError } from '@trpc/server';

import { toolsEnv } from '@/envs/tools';
import { SearXNGClient } from '@/server/services/search/impls/searxng/client';

import { type SearchServiceImpl } from '../type';

/**
 * SearXNG implementation of the search service
 */
export class SearXNGImpl implements SearchServiceImpl {
  async query(
    query: string,
    params?: {
      searchCategories?: string[];
      searchEngines?: string[];
      searchTimeRange?: string;
    },
  ): Promise<UniformSearchResponse> {
    if (!toolsEnv.SEARXNG_URL) {
      throw new TRPCError({ code: 'NOT_IMPLEMENTED', message: SEARCH_SEARXNG_NOT_CONFIG });
    }

    const client = new SearXNGClient(toolsEnv.SEARXNG_URL);

    try {
      let costTime = 0;
      const startAt = Date.now();
      const data = await client.search(query, {
        categories: params?.searchCategories,
        engines: params?.searchEngines,
        time_range: params?.searchTimeRange,
      });
      costTime = Date.now() - startAt;

      return {
        costTime,
        query,
        resultNumbers: data.number_of_results,
        results: data.results.map((item) => ({
          category: item.category,
          content: item.content!,
          engines: item.engines,
          parsedUrl: item.url ? new URL(item.url).hostname : '',
          publishedDate: item.publishedDate || undefined,
          score: item.score,
          thumbnail: item.thumbnail || undefined,
          title: item.title,
          url: item.url,
        })),
      };
    } catch (e) {
      console.error(e);

      throw new TRPCError({
        code: 'SERVICE_UNAVAILABLE',
        message: (e as Error).message,
      });
    }
  }
}

```
