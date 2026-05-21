# 文件：src/routes/(main)/settings/provider/(list)/ProviderGrid/index.tsx

## 文件职责
这个文件位于 `src/routes/(main)/settings/provider/(list)/ProviderGrid`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { Flexbox, Grid, Tag, Text } from '@lobehub/ui';
import isEqual from 'fast-deep-equal';
import { memo } from 'react';
import { useTranslation } from 'react-i18next';
import { aiProviderSelectors, useAiInfraStore } from '@/store/aiInfra';
import Card from './Card';
export default List;
```

## 主要对外内容
```text
const loadingArr = Array.from({ length: 12 })
type ListProps = {
const List = memo((props: ListProps) => {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
'use client';

import { Flexbox, Grid, Tag, Text } from '@lobehub/ui';
import isEqual from 'fast-deep-equal';
import { memo } from 'react';
import { useTranslation } from 'react-i18next';

import { aiProviderSelectors, useAiInfraStore } from '@/store/aiInfra';

import Card from './Card';

const loadingArr = Array.from({ length: 12 })
  .fill('-')
  .map((item, index) => `${index}x${item}`);

type ListProps = {
  onProviderSelect: (provider: string) => void;
};

const List = memo((props: ListProps) => {
  const { onProviderSelect } = props;
  const { t } = useTranslation('modelProvider');
  const enabledList = useAiInfraStore(aiProviderSelectors.enabledAiProviderList, isEqual);
  const disabledList = useAiInfraStore(aiProviderSelectors.disabledAiProviderList, isEqual);
  const disabledCustomList = useAiInfraStore(
    aiProviderSelectors.disabledCustomAiProviderList,
    isEqual,
  );
  const [initAiProviderList] = useAiInfraStore((s) => [s.initAiProviderList]);

  if (!initAiProviderList)
    return (
      <Flexbox gap={24} paddingBlock={'0 16px'}>
        <Flexbox horizontal align={'center'} gap={4}>
          <Text strong style={{ fontSize: 16 }}>
            {t('list.title.enabled')}
          </Text>
        </Flexbox>
        <Grid gap={16} rows={3}>
          {loadingArr.map((item) => (
            <Card
              loading
              enabled={false}
              id={item}
              key={item}
              source={'builtin'}
              onProviderSelect={onProviderSelect}
            />
          ))}
        </Grid>
      </Flexbox>
    );

  return (
    <>
      <Flexbox gap={24}>
        <Flexbox horizontal align={'center'} gap={8}>
          <Text strong style={{ fontSize: 18 }}>
            {t('list.title.enabled')}
          </Text>
          <Tag>{enabledList.length}</Tag>
        </Flexbox>
        <Grid gap={16} rows={3}>
          {enabledList.map((item) => (
            <Card {...item} key={item.id} onProviderSelect={onProviderSelect} />
          ))}
        </Grid>
      </Flexbox>
      {disabledCustomList.length > 0 && (
        <Flexbox gap={24}>
          <Flexbox horizontal align={'center'} gap={8}>
            <Text strong style={{ fontSize: 18 }}>
              {t('list.title.custom')}
            </Text>
            <Tag>{disabledCustomList.length}</Tag>
          </Flexbox>
          <Grid gap={16} rows={3}>
            {disabledCustomList.map((item) => (
              <Card {...item} key={item.id} onProviderSelect={onProviderSelect} />
            ))}
          </Grid>
        </Flexbox>
      )}
      <Flexbox gap={24}>
        <Flexbox horizontal align={'center'} gap={8}>
          <Text strong style={{ fontSize: 18 }}>
            {t('list.title.disabled')}
          </Text>
          <Tag>{disabledList.length}</Tag>
        </Flexbox>
        <Grid gap={16} rows={3}>
          {disabledList.map((item) => (
            <Card {...item} key={item.id} onProviderSelect={onProviderSelect} />
          ))}
        </Grid>
      </Flexbox>
    </>
  );
});

export default List;

```
