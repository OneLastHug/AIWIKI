# 文件：src/routes/(main)/community/(list)/provider/index.tsx

## 文件职责
这个文件位于 `src/routes/(main)/community/(list)/provider`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { Flexbox } from '@lobehub/ui';
import { memo } from 'react';
import { useQuery } from '@/hooks/useQuery';
import { useDiscoverStore } from '@/store/discover';
import { type ProviderQueryParams } from '@/types/discover';
import { DiscoverTab } from '@/types/discover';
import Pagination from '../features/Pagination';
import List from './features/List';
import Loading from './loading';
export default ProviderPage;
```

## 主要对外内容
```text
const ProviderPage = memo(() => {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
'use client';

import { Flexbox } from '@lobehub/ui';
import { memo } from 'react';

import { useQuery } from '@/hooks/useQuery';
import { useDiscoverStore } from '@/store/discover';
import { type ProviderQueryParams } from '@/types/discover';
import { DiscoverTab } from '@/types/discover';

import Pagination from '../features/Pagination';
import List from './features/List';
import Loading from './loading';

const ProviderPage = memo(() => {
  const { q, page, sort, order } = useQuery() as ProviderQueryParams;
  const useProviderList = useDiscoverStore((s) => s.useProviderList);
  const { data, isLoading } = useProviderList({
    order,
    page,
    pageSize: 21,
    q,
    sort,
  });

  if (isLoading || !data) return <Loading />;

  const { items, currentPage, pageSize, totalCount } = data;

  return (
    <Flexbox gap={32} width={'100%'}>
      <List data={items} />
      <Pagination
        currentPage={currentPage}
        pageSize={pageSize}
        tab={DiscoverTab.Providers}
        total={totalCount}
      />
    </Flexbox>
  );
});

export default ProviderPage;

```
