# 文件：src/routes/(main)/group/_layout/Sidebar/GroupConfig/Header/index.tsx

## 文件职责
这个文件位于 `src/routes/(main)/group/_layout/Sidebar/GroupConfig/Header`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { Flexbox, Text } from '@lobehub/ui';
import { memo } from 'react';
import { useTranslation } from 'react-i18next';
import { useAgentGroupStore } from '@/store/agentGroup';
import { agentGroupSelectors } from '@/store/agentGroup/selectors';
import Avatar from './Avatar';
export default HeaderInfo;
```

## 主要对外内容
```text
const HeaderInfo = memo(() => {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
'use client';

import { Flexbox, Text } from '@lobehub/ui';
import { memo } from 'react';
import { useTranslation } from 'react-i18next';

import { useAgentGroupStore } from '@/store/agentGroup';
import { agentGroupSelectors } from '@/store/agentGroup/selectors';

import Avatar from './Avatar';

const HeaderInfo = memo(() => {
  const { t } = useTranslation('chat');
  const groupMeta = useAgentGroupStore(agentGroupSelectors.currentGroupMeta);

  const displayTitle = groupMeta.title || t('untitledGroup');

  return (
    <Flexbox
      horizontal
      align={'center'}
      flex={1}
      gap={8}
      style={{
        overflow: 'hidden',
      }}
    >
      <Avatar />
      <Text ellipsis weight={500}>
        {displayTitle}
      </Text>
    </Flexbox>
  );
});

export default HeaderInfo;

```
