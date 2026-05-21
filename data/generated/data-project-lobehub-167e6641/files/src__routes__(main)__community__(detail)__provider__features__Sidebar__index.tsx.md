# 文件：src/routes/(main)/community/(detail)/provider/features/Sidebar/index.tsx

## 文件职责
这个文件位于 `src/routes/(main)/community/(detail)/provider/features/Sidebar`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { Flexbox, ScrollShadow } from '@lobehub/ui';
import { memo } from 'react';
import { useQuery } from '@/hooks/useQuery';
import { ProviderNavKey } from '@/types/discover';
import ActionButton from './ActionButton';
import Related from './Related';
import RelatedModels from './RelatedModels';
export default Sidebar;
```

## 主要对外内容
```text
const Sidebar = memo<{ mobile?: boolean }>(({ mobile }) => {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { Flexbox, ScrollShadow } from '@lobehub/ui';
import { memo } from 'react';

import { useQuery } from '@/hooks/useQuery';
import { ProviderNavKey } from '@/types/discover';

import ActionButton from './ActionButton';
import Related from './Related';
import RelatedModels from './RelatedModels';

const Sidebar = memo<{ mobile?: boolean }>(({ mobile }) => {
  const { activeTab = ProviderNavKey.Overview } = useQuery() as { activeTab: ProviderNavKey };

  if (mobile) {
    return (
      <Flexbox gap={32}>
        <ActionButton />
      </Flexbox>
    );
  }

  return (
    <ScrollShadow
      hideScrollBar
      flex={'none'}
      gap={32}
      size={4}
      width={360}
      style={{
        maxHeight: 'calc(100vh - 76px)',
        paddingBottom: 24,
        position: 'sticky',
        top: 16,
      }}
    >
      <ActionButton />
      {activeTab !== ProviderNavKey.Related && <Related />}
      {activeTab !== ProviderNavKey.Overview && <RelatedModels />}
    </ScrollShadow>
  );
});

export default Sidebar;

```
