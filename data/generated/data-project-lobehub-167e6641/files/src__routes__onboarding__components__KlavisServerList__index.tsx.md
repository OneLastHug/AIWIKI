# 文件：src/routes/onboarding/components/KlavisServerList/index.tsx

## 文件职责
这个文件位于 `src/routes/onboarding/components/KlavisServerList`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { Grid, ScrollShadow } from '@lobehub/ui';
import isEqual from 'fast-deep-equal';
import { memo } from 'react';
import { KLAVIS_SERVER_TYPES } from '@/const/index';
import { useToolStore } from '@/store/tool';
import { klavisStoreSelectors } from '@/store/tool/slices/klavisStore';
import KlavisServerItem from './components/KlavisServerItem';
export default KlavisServerList;
```

## 主要对外内容
```text
const KlavisServerList = memo(() => {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
'use client';

import { Grid, ScrollShadow } from '@lobehub/ui';
import isEqual from 'fast-deep-equal';
import { memo } from 'react';

import { KLAVIS_SERVER_TYPES } from '@/const/index';
import { useToolStore } from '@/store/tool';
import { klavisStoreSelectors } from '@/store/tool/slices/klavisStore';

import KlavisServerItem from './components/KlavisServerItem';

const KlavisServerList = memo(() => {
  const allKlavisServers = useToolStore(klavisStoreSelectors.getServers, isEqual);
  const useFetchUserKlavisServers = useToolStore((s) => s.useFetchUserKlavisServers);

  useFetchUserKlavisServers(true);

  const getServerByIdentifier = (identifier: string) => {
    return allKlavisServers.find((server) => server.identifier === identifier);
  };

  return (
    <ScrollShadow height={'33vh'} offset={8} size={12}>
      <Grid gap={8} maxItemWidth={120} rows={2}>
        {KLAVIS_SERVER_TYPES.map((type) => (
          <KlavisServerItem
            icon={type.icon}
            identifier={type.identifier}
            key={type.identifier}
            label={type.label}
            server={getServerByIdentifier(type.identifier)}
            serverName={type.serverName}
          />
        ))}
      </Grid>
    </ScrollShadow>
  );
});

KlavisServerList.displayName = 'KlavisServerList';

export default KlavisServerList;

```
