# 文件：src/routes/(main)/community/(detail)/model/features/Details/Overview/ProviderList/index.tsx

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
'use client';

import { ProviderIcon } from '@lobehub/icons';
import { ActionIcon, Block, Flexbox, Icon, Tooltip, TooltipGroup } from '@lobehub/ui';
import { cssVar } from 'antd-style';
import { BadgeCheck, BookIcon, ChevronRightIcon, KeyIcon } from 'lucide-react';
import { memo } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import urlJoin from 'url-join';

import InlineTable from '@/components/InlineTable';
import { ModelInfoTags } from '@/components/ModelSelect';
import { BASE_PROVIDER_DOC_URL } from '@/const/url';
import { formatPriceByCurrency, formatTokenNumber } from '@/utils/format';
import { getTextInputUnitRate, getTextOutputUnitRate } from '@/utils/pricing';

import { useDetailContext } from '../../../DetailProvider';

const ProviderList = memo(() => {
  const { providers = [] } = useDetailContext();
  const { t } = useTranslation('discover');

  return (
    <TooltipGroup>
      <Block variant={'outlined'}>
        <InlineTable
          dataSource={providers}
          rowKey="id"
          scroll={{ x: 1000 }}
          columns={[
            {
              dataIndex: 'id',
              key: 'provider',
              render: (_, record) => {
                return (
                  <Link style={{ color: 'inherit' }} to={urlJoin('/community/provider', record.id)}>
                    <Flexbox horizontal align="center" gap={8}>
                      <ProviderIcon provider={record.id} size={24} type={'avatar'} />
                      <div style={{ fontWeight: 500 }}>{record.name}</div>
                    </Flexbox>
                  </Link>
                );
              },
              sorter: (a, b) => a.name.localeCompare(b.name),
              title: t('tab.provider'),
              width: 200,
            },
            {
              dataIndex: 'model.abilities',
              key: 'abilities',
              render: (_, record) => {
                if (!record?.model?.abilities) return '--';
                return <ModelInfoTags {...record?.model?.abilities} />;
              },
              title: t('models.abilities'),
              width: 120,
            },
            {
              dataIndex: 'model.contextLength',
              key: 'contextLength',
              render: (_, record) =>
                record.model?.contextWindowTokens
                  ? formatTokenNumber(record.model.contextWindowTokens)
                  : '--',
              sorter: (a, b) =>
                (a.model?.contextWindowTokens || 0) - (b.model?.contextWindowTokens || 0),
              title: t('models.contentLength'),
              width: 120,
            },
            {
              dataIndex: 'model.maxOutput',
              key: 'maxOutput',
              render: (_, record) =>
                record.model?.maxOutput
                  ? formatTokenNumber(record.model.maxOutput)
                  : record.model?.maxDimension
                    ? formatTokenNumber(record.model.maxDimension)
                    : '--',
              showSorterTooltip: false,
              sorter: (a, b) => {
                const aValue = a.model?.maxOutput || a.model?.maxDimension || 0;
                const bValue = b.model?.maxOutput || b.model?.maxDimension || 0;
                return aValue - bValue;
              },
              title: (
                <Tooltip title={t('models.providerInfo.maxOutputTooltip')}>
                  <span>{t('models.providerInfo.maxOutput')}</span>
                </Tooltip>
              ),
              width: 120,
            },
            {
              dataIndex: 'model.inputPrice',
              key: 'inputPrice',
              render: (_, record) => {
                const inputRate = getTextInputUnitRate(record.model?.pricing);
                return inputRate
                  ? '$' + formatPriceByCurrency(inputRate, record.model.pricing?.currency)
                  : '--';
              },
              showSorterTooltip: false,
              sorter: (a, b) => {
                const aRate = getTextInputUnitRate(a.model?.pricing) || 0;
                const bRate = getTextInputUnitRate(b.model?.pricing) || 0;
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
              dataIndex: 'model.outputPrice',
              key: 'outputPrice',
              render: (_, record) => {
                const outputRate = getTextOutputUnitRate(record.model?.pricing);
                return outputRate
                  ? '$' + formatPriceByCurrency(outputRate, record.model.pricing?.currency)
                  : '--';
              },
              showSorterTooltip: false,
              sorter: (a, b) => {
                const aRate = getTextOutputUnitRate(a.model?.pricing) || 0;
                const bRate = getTextOutputUnitRate(b.model?.pricing) || 0;
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
                const isLobeHub = record.id === 'lobehub';
                return (
                  <Flexbox horizontal align="center" gap={4} justify={'flex-end'}>
                    {isLobeHub && (
                      <Tooltip title={t('models.providerInfo.officialTooltip')}>
                        <ActionIcon
                          color={cssVar.colorSuccess}
                          icon={BadgeCheck}
                          size={'small'}
                          variant={'filled'}
                        />
                      </Tooltip>
                    )}
                    {!isLobeHub && (
                      <Tooltip title={t('models.providerInfo.apiTooltip')}>
                        <ActionIcon
                          icon={<Icon icon={KeyIcon} />}
                          size={'small'}
                          variant={'filled'}
                        />
                      </Tooltip>
                    )}
                    <Tooltip title={t('models.guide')}>
                      <a
                        href={urlJoin(BASE_PROVIDER_DOC_URL, record.id)}
                        rel="noreferrer"
                        target={'_blank'}
                      >
                        <ActionIcon icon={BookIcon} size={'small'} variant={'filled'} />
                      </a>
                    </Tooltip>
                    <Link
                      style={{ color: 'inherit' }}
                      to={urlJoin('/community/provider', record.id)}
                    >
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
              width: 120,
            },
          ]}
        />
      </Block>
    </TooltipGroup>
  );
});

export default ProviderList;

```
