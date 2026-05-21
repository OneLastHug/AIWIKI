# 文件：src/routes/(main)/settings/stats/features/usage/UsageCards/ActiveModels/index.tsx

## 文件职责
这个文件位于 `src/routes/(main)/settings/stats/features/usage/UsageCards/ActiveModels`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { ModelIcon, ProviderIcon } from '@lobehub/icons';
import { ActionIcon, Flexbox, Modal } from '@lobehub/ui';
import { cssVar } from 'antd-style';
import { MaximizeIcon } from 'lucide-react';
import { memo, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import StatisticCard from '@/components/StatisticCard';
import TitleWithPercentage from '@/components/StatisticCard/TitleWithPercentage';
import { type UsageLog } from '@/types/usage/usageRecord';
import { formatNumber } from '@/utils/format';
import { type UsageChartProps } from '../../../../types';
import { GroupBy } from '../../../../types';
import ModelTable from './ModelTable';
export default ActiveModels;
```

## 主要对外内容
```text
const computeList = (data: UsageLog[], groupBy: GroupBy): string[] => {
const ActiveModels = memo<UsageChartProps>(({ data, isLoading, groupBy }) => {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { ModelIcon, ProviderIcon } from '@lobehub/icons';
import { ActionIcon, Flexbox, Modal } from '@lobehub/ui';
import { cssVar } from 'antd-style';
import { MaximizeIcon } from 'lucide-react';
import { memo, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import StatisticCard from '@/components/StatisticCard';
import TitleWithPercentage from '@/components/StatisticCard/TitleWithPercentage';
import { type UsageLog } from '@/types/usage/usageRecord';
import { formatNumber } from '@/utils/format';

import { type UsageChartProps } from '../../../../types';
import { GroupBy } from '../../../../types';
import ModelTable from './ModelTable';

const computeList = (data: UsageLog[], groupBy: GroupBy): string[] => {
  if (!data || data?.length === 0) return [];

  return Array.from(
    data.reduce((acc, log) => {
      if (log.records) {
        for (const item of log.records) {
          if (groupBy === GroupBy.Model && item.model?.length !== 0) {
            acc.add(item.model);
          }
          if (groupBy === GroupBy.Provider && item.provider?.length !== 0) {
            acc.add(item.provider);
          }
        }
      }
      return acc;
    }, new Set<string>()),
  );
};

const ActiveModels = memo<UsageChartProps>(({ data, isLoading, groupBy }) => {
  const { t } = useTranslation('auth');

  const [open, setOpen] = useState(false);

  const iconList = useMemo(
    () => computeList(data || [], groupBy || GroupBy.Model),
    [data, groupBy],
  );

  return (
    <>
      <StatisticCard
        key={groupBy}
        loading={isLoading}
        extra={
          <ActionIcon
            icon={MaximizeIcon}
            size={'small'}
            title={
              groupBy === GroupBy.Model
                ? t('usage.activeModels.modelTable')
                : t('usage.activeModels.providerTable')
            }
            onClick={() => setOpen(true)}
          />
        }
        statistic={{
          description: (
            <Flexbox horizontal wrap={'wrap'}>
              {iconList.map((item, i) => {
                if (!item) return null;
                return groupBy === GroupBy.Model ? (
                  <ModelIcon
                    key={item}
                    model={item}
                    size={18}
                    style={{
                      border: `2px solid ${cssVar.colorBgContainer}`,
                      boxSizing: 'content-box',
                      marginRight: -8,
                      zIndex: i + 1,
                    }}
                  />
                ) : (
                  <ProviderIcon
                    key={item}
                    provider={item}
                    size={18}
                    style={{
                      border: `2px solid ${cssVar.colorBgContainer}`,
                      boxSizing: 'content-box',
                      marginRight: -8,
                      zIndex: i + 1,
                    }}
                  />
                );
              })}
            </Flexbox>
          ),
          precision: 0,
          value: formatNumber(iconList?.length ?? 0),
        }}
        title={
          <TitleWithPercentage
            title={
              groupBy === GroupBy.Model
                ? t('usage.activeModels.models')
                : t('usage.activeModels.providers')
            }
          />
        }
      />
      <Modal
        footer={null}
        open={open}
        title={
          groupBy === GroupBy.Model
            ? t('usage.activeModels.modelTable')
            : t('usage.activeModels.providerTable')
        }
        onCancel={() => setOpen(false)}
      >
        <ModelTable data={data} groupBy={groupBy} isLoading={isLoading} />
      </Modal>
    </>
  );
});

export default ActiveModels;

```
