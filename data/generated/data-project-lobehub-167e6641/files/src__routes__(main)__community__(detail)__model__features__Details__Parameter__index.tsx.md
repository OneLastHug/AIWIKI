# 文件：src/routes/(main)/community/(detail)/model/features/Details/Parameter/index.tsx

## 文件职责
这个文件位于 `src/routes/(main)/community/(detail)/model/features/Details/Parameter`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { Collapse, Flexbox, Icon, Tag } from '@lobehub/ui';
import { type LucideIcon } from 'lucide-react';
import {
import { memo } from 'react';
import { useTranslation } from 'react-i18next';
import Title from '@/routes/(main)/community/features/Title';
import { formatTokenNumber } from '@/utils/format';
import { useDetailContext } from '../../DetailProvider';
import ParameterItem from './ParameterItem';
export default ParameterList;
```

## 主要对外内容
```text
interface Parameter {
const ParameterList = memo(() => {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
'use client';

import { Collapse, Flexbox, Icon, Tag } from '@lobehub/ui';
import { type LucideIcon } from 'lucide-react';
import {
  ChartColumnBig,
  Delete,
  FileMinus,
  MessageSquareText,
  Pickaxe,
  Thermometer,
} from 'lucide-react';
import { memo } from 'react';
import { useTranslation } from 'react-i18next';

import Title from '@/routes/(main)/community/features/Title';
import { formatTokenNumber } from '@/utils/format';

import { useDetailContext } from '../../DetailProvider';
import ParameterItem from './ParameterItem';

interface Parameter {
  defaultValue: string | number;
  desc: string;
  icon: LucideIcon;
  key: string;
  label: string;
  range?: (string | number)[];
  type: string;
}

const ParameterList = memo(() => {
  const { t } = useTranslation('discover');
  const data = useDetailContext();

  const items: Parameter[] = [
    {
      defaultValue: 1,
      desc: t('models.parameterList.temperature.desc'),
      icon: Thermometer,
      key: 'temperature',
      label: t('models.parameterList.temperature.title'),
      range: [0, 2],
      type: 'float',
    },
    {
      defaultValue: 1,
      desc: t('models.parameterList.top_p.desc'),
      icon: ChartColumnBig,
      key: 'top_p',
      label: t('models.parameterList.top_p.title'),
      range: [0, 1],
      type: 'float',
    },
    {
      defaultValue: 0,
      desc: t('models.parameterList.presence_penalty.desc'),
      icon: Delete,
      key: 'presence_penalty',
      label: t('models.parameterList.presence_penalty.title'),
      range: [-2, 2],
      type: 'float',
    },
    {
      defaultValue: 0,
      desc: t('models.parameterList.frequency_penalty.desc'),
      icon: FileMinus,
      key: 'frequency_penalty',
      label: t('models.parameterList.frequency_penalty.title'),
      range: [-2, 2],
      type: 'float',
    },
    {
      defaultValue: '--',
      desc: t('models.parameterList.max_tokens.desc'),
      icon: MessageSquareText,
      key: 'max_tokens',
      label: t('models.parameterList.max_tokens.title'),
      range: Boolean(data?.maxOutput || data?.maxDimension)
        ? [0, formatTokenNumber(data?.maxOutput || data?.maxDimension || 0)]
        : undefined,
      type: 'int',
    },
    {
      defaultValue: '--',
      desc: t('models.parameterList.reasoning_effort.desc'),
      icon: Pickaxe,
      key: 'reasoning_effort',
      label: t('models.parameterList.reasoning_effort.title'),
      range: ['low', 'high'],
      type: 'string',
    },
  ];

  return (
    <Flexbox gap={16}>
      <Title>{t('models.parameterList.title')}</Title>
      <Collapse
        defaultActiveKey={items.map((item) => item.key)}
        expandIconPlacement={'end'}
        gap={16}
        variant={'outlined'}
        items={items.map((item) => ({
          children: <ParameterItem {...item} key={item.key} />,
          key: item.key,
          label: (
            <Flexbox horizontal align={'center'} gap={8}>
              <Icon icon={item.icon} size={16} />
              {item.label}
              <Tag>{item.key}</Tag>
            </Flexbox>
          ),
        }))}
      />
    </Flexbox>
  );
});

export default ParameterList;

```
