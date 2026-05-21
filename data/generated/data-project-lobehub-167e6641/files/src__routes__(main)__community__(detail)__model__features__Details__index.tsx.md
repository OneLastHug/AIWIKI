# 文件：src/routes/(main)/community/(detail)/model/features/Details/index.tsx

## 文件职责
这个文件位于 `src/routes/(main)/community/(detail)/model/features/Details`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { Flexbox } from '@lobehub/ui';
import { useResponsive } from 'antd-style';
import { memo } from 'react';
import { useQueryState } from '@/hooks/useQueryParam';
import { ModelNavKey } from '@/types/discover';
import Sidebar from '../Sidebar';
import Nav from './Nav';
import Overview from './Overview';
import Parameter from './Parameter';
import Related from './Related';
export default Details;
```

## 主要对外内容
```text
const Details = memo<{ mobile?: boolean }>(({ mobile: isMobile }) => {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
'use client';

import { Flexbox } from '@lobehub/ui';
import { useResponsive } from 'antd-style';
import { memo } from 'react';

import { useQueryState } from '@/hooks/useQueryParam';
import { ModelNavKey } from '@/types/discover';

import Sidebar from '../Sidebar';
import Nav from './Nav';
import Overview from './Overview';
import Parameter from './Parameter';
import Related from './Related';

const Details = memo<{ mobile?: boolean }>(({ mobile: isMobile }) => {
  const { mobile = isMobile } = useResponsive();
  const [activeTab, setActiveTab] = useQueryState('activeTab', {
    clearOnDefault: true,
    defaultValue: ModelNavKey.Overview,
  });

  return (
    <Flexbox gap={24}>
      <Nav activeTab={activeTab as ModelNavKey} mobile={mobile} setActiveTab={setActiveTab} />
      <Flexbox
        gap={48}
        horizontal={!mobile}
        style={mobile ? { flexDirection: 'column-reverse' } : undefined}
      >
        <Flexbox
          width={'100%'}
          style={{
            overflow: 'hidden',
          }}
        >
          {activeTab === ModelNavKey.Overview && <Overview />}
          {activeTab === ModelNavKey.Parameter && <Parameter />}
          {activeTab === ModelNavKey.Related && <Related />}
        </Flexbox>
        <Sidebar mobile={mobile} />
      </Flexbox>
    </Flexbox>
  );
});

export default Details;

```
