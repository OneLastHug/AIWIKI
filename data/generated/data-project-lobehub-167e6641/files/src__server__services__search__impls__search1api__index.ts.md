# 文件：src/server/services/search/impls/search1api/index.ts

## 文件职责
这个文件位于 `src/server/services/search/impls/search1api`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import {
import { TRPCError } from '@trpc/server';
import debug from 'debug';
import urlJoin from 'url-join';
import { type SearchServiceImpl } from '../type';
import { type Search1ApiRawResponse, type TimeRange } from './type';
export class Search1APIImpl implements SearchServiceImpl {
```

## 主要对外内容
```text
const timeRangeMapping: Record<string, TimeRange | undefined> = {
interface Search1APIQueryParams {
const log = debug('lobe-search:search1api');
export class Search1APIImpl implements SearchServiceImpl {
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
import { type Search1ApiRawResponse, type TimeRange } from './type';

const timeRangeMapping: Record<string, TimeRange | undefined> = {
  day: 'day',
  month: 'month',
  week: 'month', // Search1API doesn't support 'week', map to closest
  year: 'year',
};

interface Search1APIQueryParams {
  crawl_results?: 0 | 1;
  exclude_sites?: string[];
  image?: boolean;
  include_sites?: string[];
  language?: string;
  max_results: number;
  query: string;
  search_service?: string;
  time_range?: string;
}

const log = debug('lobe-search:search1api');

/**
 * Search1API implementation of the search service
 * Primarily used for web crawling
 */
export class Search1APIImpl implements SearchServiceImpl {
  private get apiKey(): string | undefined {
    return process.env.SEARCH1API_SEARCH_API_KEY || process.env.SEARCH1API_API_KEY;
  }

  private get baseUrl(): string {
    // Assuming the base URL is consistent with the crawl endpoint
    return 'https://api.search1api.com';
  }

  async query(query: string, params: SearchParams = {}): Promise<UniformSearchResponse> {
    log('Starting Search1API query with query: "%s", params: %o', query, params);
    const endpoint = urlJoin(this.baseUrl, '/search');

    const { searchEngines } = params;

    const defaultQueryParams: Search1APIQueryParams = {
      crawl_results: 0, // Default is no crawling
      image: false,
      max_results: 15, // Default max results
      query,
    };

    let body: Search1APIQueryParams[] = [
      {
        ...defaultQueryParams,
        time_range:
          params?.searchTimeRange && params.searchTimeRange !== 'anytime'
            ? timeRangeMapping[params.searchTimeRange]
            : undefined,
      },
    ];

    if (searchEngines && searchEngines.length > 0) {
      body = searchEngines.map((searchEngine) => ({
        ...defaultQueryParams,

        max_results: parseInt((20 / searchEngines.length).toFixed(0)),
        search_service: searchEngine,
        time_range:
          params?.searchTimeRange && params.searchTimeRange !== 'anytime'
            ? timeRangeMapping[params.searchTimeRange]
            : undefined,
      }));
    }

    // Note: Other SearchParams like searchCategories, searchEngines (beyond the first one)
    // and Search1API specific params like include_sites, exclude_sites, language
    // are not currently mapped.

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
      log.extend('error')('Search1API fetch error: %o', error);
      throw new TRPCError({
        cause: error,
        code: 'SERVICE_UNAVAILABLE',
        message: 'Failed to connect to Search1API.',
      });
    }

    if (!response.ok) {
      const errorBody = await response.text();
      log.extend('error')(
        `Search1API request failed with status ${response.status}: %s`,
        errorBody.length > 200 ? `${errorBody.slice(0, 200)}...` : errorBody,
      );
      throw new TRPCError({
        cause: errorBody,
        code: 'SERVICE_UNAVAILABLE',
        message: `Search1API request failed: ${response.statusText}`,
      });
    }

    try {
      const rawResponse = (await response.json()) as Search1ApiRawResponse;

      log('Parsed Search1API response: %o', rawResponse);

      const mappedResults = (rawResponse.results || []).flatMap((item) => {
        if (!item.success || !item.data) return [];
        const { results = [], searchParameters } = item.data;
        return results.map(
          (result): UniformSearchResult => ({
            category: 'general',
            content: result.content || result.snippet || '',
            engines: [searchParameters?.search_service || ''],
            parsedUrl: result.link ? new URL(result.link).hostname : '',
            score: 1,
            title: result.title || '',
            url: result.link,
          }),
        );
      });

      log('Mapped %d results to SearchResult format', mappedResults.length);

      return {
        costTime,
        query,
        resultNumbers: mappedResults.length,
        results: mappedResults,
      };
    } catch (error) {
      log.extend('error')('Error parsing Search1API response: %o', error);
      throw new TRPCError({
        cause: error,
        code: 'INTERNAL_SERVER_ERROR',
        message: 'Failed to parse Search1API response.',
      });
    }
  }
}

```
