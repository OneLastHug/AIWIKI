# 文件：src/server/services/search/impls/tavily/index.ts

## 文件职责
这个文件位于 `src/server/services/search/impls/tavily`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import {
import { TRPCError } from '@trpc/server';
import debug from 'debug';
import urlJoin from 'url-join';
import { type SearchServiceImpl } from '../type';
import { type TavilyResponse, type TavilySearchParameters } from './type';
export class TavilyImpl implements SearchServiceImpl {
```

## 主要对外内容
```text
const log = debug('lobe-search:Tavily');
export class TavilyImpl implements SearchServiceImpl {
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
import { type TavilyResponse, type TavilySearchParameters } from './type';

const log = debug('lobe-search:Tavily');

/**
 * Tavily implementation of the search service
 * Primarily used for web crawling
 */
export class TavilyImpl implements SearchServiceImpl {
  private get apiKey(): string | undefined {
    return process.env.TAVILY_API_KEY;
  }

  private get baseUrl(): string {
    // Assuming the base URL is consistent with the crawl endpoint
    return 'https://api.tavily.com';
  }

  async query(query: string, params: SearchParams = {}): Promise<UniformSearchResponse> {
    log('Starting Tavily query with query: "%s", params: %o', query, params);
    const endpoint = urlJoin(this.baseUrl, '/search');

    const defaultQueryParams: TavilySearchParameters = {
      include_answer: false,
      include_image_descriptions: true,
      include_images: false,
      include_raw_content: false,
      max_results: 15,
      query,
      search_depth: process.env.TAVILY_SEARCH_DEPTH || 'basic', // basic or advanced
    };

    const body: TavilySearchParameters = {
      ...defaultQueryParams,
      time_range:
        params?.searchTimeRange && params.searchTimeRange !== 'anytime'
          ? params.searchTimeRange
          : undefined,
      // Tavily only supports news and general types
      topic: params?.searchCategories?.find((cat) => ['news', 'general'].includes(cat)),
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
          'Authorization': this.apiKey ? `Bearer ${this.apiKey}` : '',
          'Content-Type': 'application/json',
        },
        method: 'POST',
      });
      log('Received response with status: %d', response.status);
      costTime = Date.now() - startAt;
    } catch (error) {
      log.extend('error')('Tavily fetch error: %o', error);
      throw new TRPCError({
        cause: error,
        code: 'SERVICE_UNAVAILABLE',
        message: 'Failed to connect to Tavily.',
      });
    }

    if (!response.ok) {
      const errorBody = await response.text();
      log.extend('error')(
        `Tavily request failed with status ${response.status}: %s`,
        errorBody.length > 200 ? `${errorBody.slice(0, 200)}...` : errorBody,
      );
      throw new TRPCError({
        cause: errorBody,
        code: 'SERVICE_UNAVAILABLE',
        message: `Tavily request failed: ${response.statusText}`,
      });
    }

    try {
      const tavilyResponse = (await response.json()) as TavilyResponse;

      log('Parsed Tavily response: %o', tavilyResponse);

      const mappedResults = (tavilyResponse.results || []).map(
        (result): UniformSearchResult => ({
          category: body.topic || 'general', // Default category
          content: result.content || '', // Prioritize content, fallback to snippet
          engines: ['tavily'], // Use 'tavily' as the engine name
          parsedUrl: result.url ? new URL(result.url).hostname : '', // Basic URL parsing
          score: result.score || 0, // Default score to 0 if undefined
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
      log.extend('error')('Error parsing Tavily response: %o', error);
      throw new TRPCError({
        cause: error,
        code: 'INTERNAL_SERVER_ERROR',
        message: 'Failed to parse Tavily response.',
      });
    }
  }
}

```
