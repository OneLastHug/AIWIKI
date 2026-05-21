# 文件：src/routes/(main)/settings/provider/detail/default/index.tsx

## 文件职责
这个文件位于 `src/routes/(main)/settings/provider/detail/default`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { Flexbox } from '@lobehub/ui';
import { memo } from 'react';
import { useAiInfraStore } from '@/store/aiInfra';
import { useServerConfigStore } from '@/store/serverConfig';
import ModelList from '../../features/ModelList';
import { type ProviderConfigProps } from '../../features/ProviderConfig';
import ProviderConfig from '../../features/ProviderConfig';
export default ProviderDetail;
```

## 主要对外内容
```text
interface ProviderDetailProps extends ProviderConfigProps {
const ProviderDetail = memo<ProviderDetailProps>(({ showConfig = true, ...card }) => {
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

import { useAiInfraStore } from '@/store/aiInfra';
import { useServerConfigStore } from '@/store/serverConfig';

import ModelList from '../../features/ModelList';
import { type ProviderConfigProps } from '../../features/ProviderConfig';
import ProviderConfig from '../../features/ProviderConfig';

interface ProviderDetailProps extends ProviderConfigProps {
  showConfig?: boolean;
}
const ProviderDetail = memo<ProviderDetailProps>(({ showConfig = true, ...card }) => {
  const useFetchAiProviderItem = useAiInfraStore((s) => s.useFetchAiProviderItem);
  const useFetchAiProviderList = useAiInfraStore((s) => s.useFetchAiProviderList);
  const isMobile = useServerConfigStore((s) => s.isMobile);

  useFetchAiProviderList({ enabled: isMobile });
  useFetchAiProviderItem(card.id);

  return (
    <Flexbox gap={24} paddingBlock={8}>
      {showConfig && <ProviderConfig {...card} />}
      <ModelList id={card.id} {...card.settings} />
    </Flexbox>
  );
});

export default ProviderDetail;

```
