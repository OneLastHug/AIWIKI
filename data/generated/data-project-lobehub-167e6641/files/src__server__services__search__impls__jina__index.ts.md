# 文件：src/server/services/search/impls/jina/index.ts

## 文件职责
这个文件位于 `src/server/services/search/impls/jina`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import {
import { TRPCError } from '@trpc/server';
import debug from 'debug';
import urlJoin from 'url-join';
import { type SearchServiceImpl } from '../type';
import { type JinaResponse, type JinaSearchParameters } from './type';
export class JinaImpl implements SearchServiceImpl {
```

## 主要对外内容
```text
const log = debug('lobe-search:Jina');
export class JinaImpl implements SearchServiceImpl {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import {
  type SearchParams,
  type UniformSearchResponse,
  type UniformSearchResult,
} from '@lobechat/types';
import { TRPCError } from '@trpc/server';
import debug from 'debug';
import urlJoin from 'url-join';

import { type SearchServiceImpl } from '../type';
import { type JinaResponse, type JinaSearchParameters } from './type';

const log = debug('lobe-search:Jina');

/**
 * Jina implementation of the search service
 * Primarily used for web crawling
 */
export class JinaImpl implements SearchServiceImpl {
  private get apiKey(): string | undefined {
    return process.env.JINA_READER_API_KEY || process.env.JINA_API_KEY;
  }

  private get baseUrl(): string {
    // Assuming the base URL is consistent with the crawl endpoint
    return 'https://s.jina.ai';
  }

  async query(query: string, params: SearchParams = {}): Promise<UniformSearchResponse> {
    log('Starting Jina query with query: "%s", params: %o', query, params);
    const endpoint = urlJoin(this.baseUrl, '/');

    const body: JinaSearchParameters = {
      q: query,
    };

    log('Constructed request body: %o', body);

    let response: Response;
    const startAt = Date.now();
    let costTime: number;
    try {
      log('Sending request to endpoint: %s', endpoint);
      response = await fetch(endpoint, {
        body: JSON.stringify(body),
        headers: {
          'Accept': 'application/json',
          'Authorization': this.apiKey ? `Bearer ${this.apiKey}` : '',
          'Content-Type': 'application/json',
          'X-Respond-With': 'no-content',
        },
        method: 'POST',
      });
      log('Received response with status: %d', response.status);
      costTime = Date.now() - startAt;
    } catch (error) {
      log.extend('error')('Jina fetch error: %o', error);
      throw new TRPCError({
        cause: error,
        code: 'SERVICE_UNAVAILABLE',
        message: 'Failed to connect to Jina.',
      });
    }

    if (!response.ok) {
      const errorBody = await response.text();
      log.extend('error')(
        `Jina request failed with status ${response.status}: %s`,
        errorBody.length > 200 ? `${errorBody.slice(0, 200)}...` : errorBody,
      );
      throw new TRPCError({
        cause: errorBody,
        code: 'SERVICE_UNAVAILABLE',
        message: `Jina request failed: ${response.statusText}`,
      });
    }

    try {
      const jinaResponse = (await response.json()) as JinaResponse;

      log('Parsed Jina response: %o', jinaResponse);

      const mappedResults = (jinaResponse.data || []).map(
        (result): UniformSearchResult => ({
          category: 'general', // Default category
          content: result.description || '', // Prioritize content, fallback to snippet
          engines: ['jina'], // Use 'jina' as the engine name
          parsedUrl: result.url ? new URL(result.url).hostname : '', // Basic URL parsing
          score: 1, // Default score to 1
          title: result.title || '',
          url: result.url,
        }),
      );

      log('Mapped %d results to SearchResult format', mappedResults.length);

      return {
        costTime,
        query,
        resultNumbers: mappedResults.length,
        results: mappedResults,
      };
    } catch (error) {
      log.extend('error')('Error parsing Jina response: %o', error);
      throw new TRPCError({
        cause: error,
        code: 'INTERNAL_SERVER_ERROR',
        message: 'Failed to parse Jina response.',
      });
    }
  }
}

```
