# 文件：src/store/serverConfig/Provider.tsx

## 文件职责
这个文件位于 `src/store/serverConfig`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { type ReactNode } from 'react';
import { memo } from 'react';
import { type IFeatureFlags } from '@/config/featureFlags';
import { mapFeatureFlagsEnvToState } from '@/config/featureFlags';
import { type GlobalServerConfig } from '@/types/serverConfig';
import { createServerConfigStore, Provider } from './store';
export const ServerConfigStoreProvider = memo<GlobalStoreProviderProps>(
```

## 主要对外内容
```text
interface GlobalStoreProviderProps {
export const ServerConfigStoreProvider = memo<GlobalStoreProviderProps>(
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
'use client';

import { type ReactNode } from 'react';
import { memo } from 'react';

import { type IFeatureFlags } from '@/config/featureFlags';
import { mapFeatureFlagsEnvToState } from '@/config/featureFlags';
import { type GlobalServerConfig } from '@/types/serverConfig';

import { createServerConfigStore, Provider } from './store';

interface GlobalStoreProviderProps {
  children: ReactNode;
  featureFlags?: Partial<IFeatureFlags>;
  isMobile?: boolean;
  segmentVariants?: string;
  serverConfig?: GlobalServerConfig;
}

export const ServerConfigStoreProvider = memo<GlobalStoreProviderProps>(
  ({ children, featureFlags, serverConfig, isMobile, segmentVariants }) => (
    <Provider
      createStore={() =>
        createServerConfigStore({
          featureFlags: featureFlags ? mapFeatureFlagsEnvToState(featureFlags) : undefined,
          isMobile,
          segmentVariants,
          serverConfig,
        })
      }
    >
      {children}
    </Provider>
  ),
);

```
