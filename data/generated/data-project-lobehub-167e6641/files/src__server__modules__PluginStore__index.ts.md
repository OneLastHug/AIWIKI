# 文件：src/server/modules/PluginStore/index.ts

## 文件职责
这个文件位于 `src/server/modules/PluginStore`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import urlJoin from 'url-join';
import { DEFAULT_LANG, isLocaleNotSupport } from '@/const/locale';
import { appEnv } from '@/envs/app';
import { type Locales } from '@/locales/resources';
import { normalizeLocale } from '@/locales/resources';
export class PluginStore {
```

## 主要对外内容
```text
export class PluginStore {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import urlJoin from 'url-join';

import { DEFAULT_LANG, isLocaleNotSupport } from '@/const/locale';
import { appEnv } from '@/envs/app';
import { type Locales } from '@/locales/resources';
import { normalizeLocale } from '@/locales/resources';

export class PluginStore {
  private readonly baseUrl: string;

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl || appEnv.PLUGINS_INDEX_URL;
  }

  getPluginIndexUrl = (lang: Locales = DEFAULT_LANG) => {
    if (isLocaleNotSupport(lang)) return this.baseUrl;
    return urlJoin(this.baseUrl, `index.${normalizeLocale(lang)}.json`);
  };

  getPluginList = async (locale?: string): Promise<any[]> => {
    try {
      let res = await fetch(this.getPluginIndexUrl(locale as Locales), {
        next: {
          revalidate: 3600,
        },
      });
      if (!res.ok) {
        res = await fetch(this.getPluginIndexUrl(DEFAULT_LANG), {
          next: {
            revalidate: 3600,
          },
        });
      }
      if (!res.ok) return [];
      const json = await res.json();
      return json.plugins ?? [];
    } catch (e) {
      console.error('[getPluginListError] failed to fetch plugin list, error detail:');
      console.error(e);
      return [];
    }
  };
}

```
