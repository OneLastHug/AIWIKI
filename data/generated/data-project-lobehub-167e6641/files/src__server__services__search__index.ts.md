# 文件：src/server/services/search/index.ts

## 文件职责
这个文件位于 `src/server/services/search`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import type { SearchParams, SearchQuery } from '@lobechat/types';
import type { Crawler, CrawlImplType, CrawlUniformResult } from '@lobechat/web-crawler';
import debug from 'debug';
import pMap from 'p-map';
import { toolsEnv } from '@/envs/tools';
import { type SearchImplType, type SearchServiceImpl } from './impls';
import { createSearchServiceImpl } from './impls';
export class SearchService {
export const searchService = new SearchService();
```

## 主要对外内容
```text
const DEFAULT_CRAWL_CONCURRENCY = 3;
const DEFAULT_CRAWLER_RETRY = 1;
const log = debug('lobe-oom:web-browsing:search-service');
const parseImplEnv = (envString: string = '') => {
const getMemorySnapshot = () => {
export class SearchService {
export const searchService = new SearchService();
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import type { SearchParams, SearchQuery } from '@lobechat/types';
import type { Crawler, CrawlImplType, CrawlUniformResult } from '@lobechat/web-crawler';
import debug from 'debug';
import pMap from 'p-map';

import { toolsEnv } from '@/envs/tools';

import { type SearchImplType, type SearchServiceImpl } from './impls';
import { createSearchServiceImpl } from './impls';

const DEFAULT_CRAWL_CONCURRENCY = 3;
const DEFAULT_CRAWLER_RETRY = 1;
const log = debug('lobe-oom:web-browsing:search-service');

const parseImplEnv = (envString: string = '') => {
  // Handle full-width commas and extra whitespace
  const envValue = envString.replaceAll('，', ',').trim();
  return envValue.split(',').filter(Boolean);
};

const getMemorySnapshot = () => {
  if (typeof process === 'undefined' || typeof process.memoryUsage !== 'function') {
    return 'non-node';
  }

  const { heapUsed, rss } = process.memoryUsage();

  return `rss=${(rss / 1024 / 1024).toFixed(1)}MB heap=${(heapUsed / 1024 / 1024).toFixed(1)}MB`;
};

/**
 * Search service class
 * Uses different implementations for different search operations
 */
export class SearchService {
  private searchImpList: SearchServiceImpl[];

  private get crawlerImpls() {
    return parseImplEnv(toolsEnv.CRAWLER_IMPLS);
  }

  private get crawlConcurrency() {
    return toolsEnv.CRAWL_CONCURRENCY ?? DEFAULT_CRAWL_CONCURRENCY;
  }

  private get crawlerRetry() {
    return toolsEnv.CRAWLER_RETRY ?? DEFAULT_CRAWLER_RETRY;
  }

  constructor() {
    const impls = this.searchImpls;
    this.searchImpList =
      impls.length > 0
        ? impls.map((impl) => createSearchServiceImpl(impl))
        : [createSearchServiceImpl()];
  }

  async crawlPages(input: { impls?: CrawlImplType[]; urls: string[] }) {
    try {
      if (log.enabled) {
        log(
          'crawlPages:start urls=%d impls=%s mem=%s',
          input.urls.length,
          (input.impls || this.crawlerImpls).join(',') || '-',
          getMemorySnapshot(),
        );
      }
    } catch {}

    const { Crawler } = await import('@lobechat/web-crawler');
    const crawler = new Crawler({ impls: this.crawlerImpls });

    const results = await pMap(
      input.urls,
      async (url) => {
        return await this.crawlWithRetry(crawler, url, input.impls);
      },
      { concurrency: this.crawlConcurrency },
    );

    return { results };
  }

  private async crawlWithRetry(
    crawler: Crawler,
    url: string,
    impls?: CrawlImplType[],
  ): Promise<CrawlUniformResult> {
    const maxAttempts = this.crawlerRetry + 1;
    let lastResult: CrawlUniformResult | undefined;
    let lastError: Error | undefined;

    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      try {
        const result = await crawler.crawl({ impls, url });
        try {
          if (log.enabled) {
            log('crawlWithRetry:result crawler=%s mem=%s', result.crawler, getMemorySnapshot());
          }
        } catch {}
        lastResult = result;

        if (!this.isFailedCrawlResult(result)) {
          return result;
        }
      } catch (error) {
        lastError = error as Error;
      }
    }

    if (lastResult) {
      return lastResult;
    }

    return {
      crawler: 'unknown',
      data: {
        content: `Fail to crawl the page. Error type: ${lastError?.name || 'UnknownError'}, error message: ${lastError?.message}`,
        errorMessage: lastError?.message,
        errorType: lastError?.name || 'UnknownError',
      },
      originalUrl: url,
    };
  }

  /**
   * A successful crawl result always includes `contentType` (e.g. 'text', 'json')
   * in `result.data`, while a failed result contains `errorType`/`errorMessage` instead.
   */
  private isFailedCrawlResult(result: CrawlUniformResult): boolean {
    return !('contentType' in result.data);
  }

  private get searchImpls() {
    return parseImplEnv(toolsEnv.SEARCH_PROVIDERS) as SearchImplType[];
  }

  /**
   * Query for search results using the specified impl
   */
  private async queryWithImpl(impl: SearchServiceImpl, query: string, params?: SearchParams) {
    try {
      return await impl.query(query, params);
    } catch (e) {
      console.error('[SearchService] query failed:', (e as Error).message);
      return {
        costTime: 0,
        errorDetail: (e as Error).message,
        query,
        resultNumbers: 0,
        results: [],
      };
    }
  }

  /**
   * Query for search results (uses the first provider)
   */
  async query(query: string, params?: SearchParams) {
    return this.queryWithImpl(this.searchImpList[0], query, params);
  }

  async webSearch({ query, searchCategories, searchEngines, searchTimeRange }: SearchQuery) {
    try {
      if (log.enabled) {
        log(
          'webSearch:start providers=%d q=%d c=%d e=%d mem=%s',
          this.searchImpList.length,
          query.length,
          searchCategories?.length || 0,
          searchEngines?.length || 0,
          getMemorySnapshot(),
        );
      }
    } catch {}

    for (const impl of this.searchImpList) {
      try {
        if (log.enabled) {
          log(
            'webSearch:impl impl=%s mem=%s',
            impl.constructor.name || 'UnknownSearchImpl',
            getMemorySnapshot(),
          );
        }
      } catch {}

      let data = await this.queryWithImpl(impl, query, {
        searchCategories,
        searchEngines,
        searchTimeRange,
      });

      // First retry: remove search engine restrictions if no results found
      if (data.results.length === 0 && searchEngines && searchEngines?.length > 0) {
        data = await this.queryWithImpl(impl, query, {
          searchCategories,
          searchEngines: undefined,
          searchTimeRange,
        });
      }

      // Second retry: remove all restrictions if still no results found
      if (data.results.length === 0) {
        data = await this.queryWithImpl(impl, query);
      }

      // If this provider returned results, use them
      if (data.results.length > 0) {
        return data;
      }
    }

    // All providers exhausted, return empty result
    return { costTime: 0, query, resultNumbers: 0, results: [] };
  }
}

// Add a default exported instance for convenience
export const searchService = new SearchService();

```
