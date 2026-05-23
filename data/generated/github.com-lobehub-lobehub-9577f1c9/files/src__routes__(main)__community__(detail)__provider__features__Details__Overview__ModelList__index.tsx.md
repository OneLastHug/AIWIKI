# 文件：src/routes/(main)/community/(detail)/provider/features/Details/Overview/ModelList/index.tsx

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
'use client';

import { ModelIcon } from '@lobehub/icons';
import { ActionIcon, Block, Flexbox, Tooltip, TooltipGroup } from '@lobehub/ui';
import { cssVar } from 'antd-style';
import { ChevronRightIcon } from 'lucide-react';
import { memo } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import urlJoin from 'url-join';

import InlineTable from '@/components/InlineTable';
import { ModelInfoTags } from '@/components/ModelSelect';
import { formatPriceByCurrency, formatTokenNumber } from '@/utils/format';
import { getTextInputUnitRate, getTextOutputUnitRate } from '@/utils/pricing';

import { useDetailContext } from '../../../DetailProvider';

const ModelList = memo(() => {
  const { models = [] } = useDetailContext();
  const { t } = useTranslation('discover');

  return (
    <TooltipGroup>
      <Block variant={'outlined'}>
        <InlineTable
          dataSource={models}
          rowKey="id"
          scroll={{ x: 900 }}
          columns={[
            {
              dataIndex: 'id',
              key: 'model',
              render: (_, record) => {
                return (
                  <Link style={{ color: 'inherit' }} to={urlJoin('/community/model', record.id)}>
                    <Flexbox horizontal align="center" gap={8}>
                      <ModelIcon model={record.id} size={24} type={'avatar'} />
                      <Flexbox style={{ overflow: 'hidden' }}>
                        <div style={{ fontWeight: 500 }}>{record.displayName}</div>
                        <div style={{ color: cssVar.colorTextSecondary, fontSize: 12 }}>
                          {record.id}
                        </div>
                      </Flexbox>
                    </Flexbox>
                  </Link>
                );
              },
              sorter: (a, b) => a.displayName.localeCompare(b.displayName),
              title: t('providers.modelName'),
              width: 200,
            },
            {
              dataIndex: 'abilities',
              key: 'abilities',
              render: (_, record) => {
                if (!record?.abilities || !Object.values(record?.abilities).includes(true))
                  return '--';
                return <ModelInfoTags {...record?.abilities} />;
              },
              title: t('models.abilities'),
              width: 120,
            },
            {
              dataIndex: 'contextWindowTokens',
              key: 'contextLength',
              render: (_, record) =>
                record.contextWindowTokens ? formatTokenNumber(record.contextWindowTokens) : '--',
              sorter: (a, b) => (a.contextWindowTokens || 0) - (b.contextWindowTokens || 0),
              title: t('models.contentLength'),
              width: 120,
            },
            {
              dataIndex: 'maxOutput',
              key: 'maxOutput',
              render: (_, record) =>
                record.maxOutput ? formatTokenNumber(record.maxOutput) : '--',
              showSorterTooltip: false,
              sorter: (a, b) => (a.maxOutput || 0) - (b.maxOutput || 0),
              title: (
                <Tooltip title={t('models.providerInfo.maxOutputTooltip')}>
                  <span>{t('models.providerInfo.maxOutput')}</span>
                </Tooltip>
              ),
              width: 120,
            },
            {
              dataIndex: 'inputPrice',
              key: 'inputPrice',
              render: (_, record) => {
                const inputRate = getTextInputUnitRate(record.pricing);
                return inputRate
                  ? '$' + formatPriceByCurrency(inputRate, record.pricing?.currency)
                  : '--';
              },
              showSorterTooltip: false,
              sorter: (a, b) => {
                const aRate = getTextInputUnitRate(a.pricing) || 0;
                const bRate = getTextInputUnitRate(b.pricing) || 0;
                return aRate - bRate;
              },
              title: (
                <Tooltip title={t('models.providerInfo.inputTooltip')}>
                  <span>{t('models.providerInfo.input')}</span>
                </Tooltip>
              ),
              width: 100,
            },
            {
              dataIndex: 'outputPrice',
              key: 'outputPrice',
              render: (_, record) => {
                const outputRate = getTextOutputUnitRate(record.pricing);
                return outputRate
                  ? '$' + formatPriceByCurrency(outputRate, record.pricing?.currency)
                  : '--';
              },
              showSorterTooltip: false,
              sorter: (a, b) => {
                const aRate = getTextOutputUnitRate(a.pricing) || 0;
                const bRate = getTextOutputUnitRate(b.pricing) || 0;
                return aRate - bRate;
              },
              title: (
                <Tooltip title={t('models.providerInfo.outputTooltip')}>
                  <span>{t('models.providerInfo.output')}</span>
                </Tooltip>
              ),
              width: 100,
            },
            {
              align: 'right',
              dataIndex: 'action',
              key: 'action',
              render: (_, record) => {
                return (
                  <Flexbox horizontal align="center" gap={4} justify={'flex-end'}>
                    <Link style={{ color: 'inherit' }} to={urlJoin('/community/model', record.id)}>
                      <ActionIcon
                        color={cssVar.colorTextDescription}
                        icon={ChevronRightIcon}
                        size={'small'}
                        variant={'filled'}
                      />
                    </Link>
                  </Flexbox>
                );
              },
              title: '',
              width: 60,
            },
          ]}
        />
      </Block>
    </TooltipGroup>
  );
});

export default ModelList;

```
