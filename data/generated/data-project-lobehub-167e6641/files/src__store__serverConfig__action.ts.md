# 文件：src/store/serverConfig/action.ts

## 文件职责
这个文件位于 `src/store/serverConfig`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { type SWRResponse } from 'swr';
import { useOnlyFetchOnceSWR } from '@/libs/swr';
import { globalService } from '@/services/global';
import { type StoreSetter } from '@/store/types';
import { type GlobalRuntimeConfig } from '@/types/serverConfig';
import { type ServerConfigStore } from './store';
export const createServerConfigSlice = (
export class ServerConfigActionImpl {
export type ServerConfigAction = Pick<ServerConfigActionImpl, keyof ServerConfigActionImpl>;
```

## 主要对外内容
```text
const FETCH_SERVER_CONFIG_KEY = 'FETCH_SERVER_CONFIG';
type Setter = StoreSetter<ServerConfigStore>;
export const createServerConfigSlice = (
export class ServerConfigActionImpl {
export type ServerConfigAction = Pick<ServerConfigActionImpl, keyof ServerConfigActionImpl>;
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { type SWRResponse } from 'swr';

import { useOnlyFetchOnceSWR } from '@/libs/swr';
import { globalService } from '@/services/global';
import { type StoreSetter } from '@/store/types';
import { type GlobalRuntimeConfig } from '@/types/serverConfig';

import { type ServerConfigStore } from './store';

const FETCH_SERVER_CONFIG_KEY = 'FETCH_SERVER_CONFIG';

type Setter = StoreSetter<ServerConfigStore>;
export const createServerConfigSlice = (
  set: Setter,
  get: () => ServerConfigStore,
  _api?: unknown,
) => new ServerConfigActionImpl(set, get, _api);

export class ServerConfigActionImpl {
  readonly #set: Setter;

  constructor(set: Setter, get: () => ServerConfigStore, _api?: unknown) {
    void _api;
    this.#set = set;
    void get;
  }

  useInitServerConfig = (): SWRResponse<GlobalRuntimeConfig> => {
    return useOnlyFetchOnceSWR<GlobalRuntimeConfig>(
      FETCH_SERVER_CONFIG_KEY,
      () => globalService.getGlobalConfig(),
      {
        onError: () => {
          this.#set({ serverConfigInit: true }, false, 'initServerConfigFallback');
        },
        onSuccess: (data) => {
          this.#set(
            {
              billboard: data.billboard ?? null,
              featureFlags: data.serverFeatureFlags,
              serverConfig: data.serverConfig,
              serverConfigInit: true,
            },
            false,
            'initServerConfig',
          );
        },
      },
    );
  };
}

export type ServerConfigAction = Pick<ServerConfigActionImpl, keyof ServerConfigActionImpl>;

```
