# 文件：src/server/services/search/impls/index.ts

## 文件职责
这个文件位于 `src/server/services/search/impls`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { AnspireImpl } from './anspire';
import { BochaImpl } from './bocha';
import { BraveImpl } from './brave';
import { ExaImpl } from './exa';
import { FirecrawlImpl } from './firecrawl';
import { GoogleImpl } from './google';
import { JinaImpl } from './jina';
import { KagiImpl } from './kagi';
import { Search1APIImpl } from './search1api';
import { SearXNGImpl } from './searxng';
import { TavilyImpl } from './tavily';
import { type SearchServiceImpl } from './type';
export enum SearchImplType {
export const createSearchServiceImpl = (
export type { SearchServiceImpl } from './type';
```

## 主要对外内容
```text
export const createSearchServiceImpl = (
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { AnspireImpl } from './anspire';
import { BochaImpl } from './bocha';
import { BraveImpl } from './brave';
import { ExaImpl } from './exa';
import { FirecrawlImpl } from './firecrawl';
import { GoogleImpl } from './google';
import { JinaImpl } from './jina';
import { KagiImpl } from './kagi';
import { Search1APIImpl } from './search1api';
import { SearXNGImpl } from './searxng';
import { TavilyImpl } from './tavily';
import { type SearchServiceImpl } from './type';

/**
 * Available search service implementations
 */
export enum SearchImplType {
  Anspire = 'anspire',
  Bocha = 'bocha',
  Brave = 'brave',
  Exa = 'exa',
  Firecrawl = 'firecrawl',
  Google = 'google',
  Jina = 'jina',
  Kagi = 'kagi',
  Search1API = 'search1api',
  SearXNG = 'searxng',
  Tavily = 'tavily',
}

/**
 * Create a search service implementation instance
 */
export const createSearchServiceImpl = (
  type: SearchImplType = SearchImplType.SearXNG,
): SearchServiceImpl => {
  switch (type) {
    case SearchImplType.Anspire: {
      return new AnspireImpl();
    }

    case SearchImplType.Bocha: {
      return new BochaImpl();
    }

    case SearchImplType.Brave: {
      return new BraveImpl();
    }

    case SearchImplType.Exa: {
      return new ExaImpl();
    }

    case SearchImplType.Firecrawl: {
      return new FirecrawlImpl();
    }

    case SearchImplType.Google: {
      return new GoogleImpl();
    }

    case SearchImplType.Jina: {
      return new JinaImpl();
    }

    case SearchImplType.Kagi: {
      return new KagiImpl();
    }

    case SearchImplType.SearXNG: {
      return new SearXNGImpl();
    }

    case SearchImplType.Tavily: {
      return new TavilyImpl();
    }

    default: {
      return new Search1APIImpl();
    }
  }
};

export type { SearchServiceImpl } from './type';

```
