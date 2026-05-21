# 文件：src/routes/(main)/community/(list)/provider/features/List/index.tsx

## 文件职责
这个文件位于 `src/routes/(main)/community/(list)/provider/features/List`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { Grid } from '@lobehub/ui';
import { memo } from 'react';
import { type DiscoverProviderItem } from '@/types/discover';
import ProviderEmpty from '../../../../features/ProviderEmpty';
import Item from './Item';
export interface ProvoderListProps {
export default ProvoderList;
```

## 主要对外内容
```text
export interface ProvoderListProps {
const ProvoderList = memo<ProvoderListProps>(({ data = [], rows = 3 }) => {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
'use client';

import { Grid } from '@lobehub/ui';
import { memo } from 'react';

import { type DiscoverProviderItem } from '@/types/discover';

import ProviderEmpty from '../../../../features/ProviderEmpty';
import Item from './Item';

export interface ProvoderListProps {
  data?: DiscoverProviderItem[];
  rows?: number;
}

const ProvoderList = memo<ProvoderListProps>(({ data = [], rows = 3 }) => {
  if (data.length === 0) return <ProviderEmpty />;

  return (
    <Grid rows={rows} width={'100%'}>
      {data.map((item, index) => (
        <Item key={index} {...item} />
      ))}
    </Grid>
  );
});

export default ProvoderList;

```
