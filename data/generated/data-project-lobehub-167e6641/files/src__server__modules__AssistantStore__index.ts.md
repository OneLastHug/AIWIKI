# 文件：src/server/modules/AssistantStore/index.ts

## 文件职责
这个文件位于 `src/server/modules/AssistantStore`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { EdgeConfig } from '@lobechat/edge-config';
import urlJoin from 'url-join';
import { DEFAULT_LANG, isLocaleNotSupport } from '@/const/locale';
import { appEnv } from '@/envs/app';
import { type Locales } from '@/locales/resources';
import { normalizeLocale } from '@/locales/resources';
import { CacheRevalidate, CacheTag } from '@/types/discover';
export class AssistantStore {
```

## 主要对外内容
```text
export class AssistantStore {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { EdgeConfig } from '@lobechat/edge-config';
import urlJoin from 'url-join';

import { DEFAULT_LANG, isLocaleNotSupport } from '@/const/locale';
import { appEnv } from '@/envs/app';
import { type Locales } from '@/locales/resources';
import { normalizeLocale } from '@/locales/resources';
import { CacheRevalidate, CacheTag } from '@/types/discover';

export class AssistantStore {
  private readonly baseUrl: string;

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl || appEnv.AGENTS_INDEX_URL;
  }

  private getAgentIndexUrl = (lang: Locales = DEFAULT_LANG) => {
    if (isLocaleNotSupport(lang)) return this.baseUrl;

    return urlJoin(this.baseUrl, `index.${normalizeLocale(lang)}.json`);
  };

  getAgentUrl = (identifier: string, lang: Locales = DEFAULT_LANG) => {
    if (isLocaleNotSupport(lang)) return urlJoin(this.baseUrl, `${identifier}.json`);

    return urlJoin(this.baseUrl, `${identifier}.${normalizeLocale(lang)}.json`);
  };

  getAgentIndex = async (locale: Locales = DEFAULT_LANG): Promise<any[]> => {
    let res: Response;
    try {
      res = await fetch(this.getAgentIndexUrl(locale as any), {
        cache: 'force-cache',
        next: { revalidate: CacheRevalidate.List, tags: [CacheTag.Discover, CacheTag.Assistants] },
      });

      if (res.status === 404) {
        res = await fetch(this.getAgentIndexUrl(DEFAULT_LANG), {
          cache: 'force-cache',
          next: {
            revalidate: CacheRevalidate.List,
            tags: [CacheTag.Discover, CacheTag.Assistants],
          },
        });
      }

      if (!res.ok) {
        console.warn('fetch agent index error:', await res.text());
        return [];
      }

      const data: any = await res.clone().json();

      if (EdgeConfig.isEnabled()) {
        // Get the assistant whitelist from Edge Config
        const edgeConfig = new EdgeConfig();

        const { whitelist, blacklist } = await edgeConfig.getAgentRestrictions();

        // use whitelist mode first
        if (whitelist && whitelist?.length > 0) {
          data.agents = data.agents.filter((item: any) => whitelist.includes(item.identifier));
        }

        // if no whitelist, use blacklist mode
        else if (blacklist && blacklist?.length > 0) {
          data.agents = data.agents.filter((item: any) => !blacklist.includes(item.identifier));
        }
      }

      return data.agents;
    } catch (e) {
      // it means failed to fetch
      if ((e as Error).message.includes('fetch failed')) {
        return [];
      }

      console.error(`[AgentIndexFetchError] failed to fetch agent index, error detail:`);
      console.error(e);
      if (res!) {
        console.error(`status code: ${res?.status}`, await res.text());
      }

      throw e;
    }
  };

  getAgent = async (identifier: string, lang: Locales = DEFAULT_LANG): Promise<any> => {
    let res = await fetch(this.getAgentUrl(identifier, lang), {
      cache: 'force-cache',
      next: {
        revalidate: CacheRevalidate.Details,
        tags: [CacheTag.Discover, CacheTag.Assistants],
      },
    });
    if (!res.ok) {
      res = await fetch(this.getAgentUrl(identifier, DEFAULT_LANG), {
        cache: 'force-cache',
        next: {
          revalidate: CacheRevalidate.Details,
          tags: [CacheTag.Discover, CacheTag.Assistants],
        },
      });
    }
    if (!res.ok) return;
    const data = await res.json();
    return data;
  };
}

```
