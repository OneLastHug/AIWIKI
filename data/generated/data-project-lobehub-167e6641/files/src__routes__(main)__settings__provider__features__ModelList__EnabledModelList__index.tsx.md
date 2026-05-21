# 文件：src/routes/(main)/settings/provider/features/ModelList/EnabledModelList/index.tsx

## 文件职责
这个文件位于 `src/routes/(main)/settings/provider/features/ModelList/EnabledModelList`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { ActionIcon, Center, Flexbox, Text, TooltipGroup } from '@lobehub/ui';
import isEqual from 'fast-deep-equal';
import { ArrowDownUpIcon, ToggleLeft } from 'lucide-react';
import { use, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAiInfraStore } from '@/store/aiInfra';
import { aiModelSelectors } from '@/store/aiInfra/selectors';
import ModelItem from '../ModelItem';
import { ProviderSettingsContext } from '../ProviderSettingsContext';
import SortModelModal from '../SortModelModal';
export default EnabledModelList;
```

## 主要对外内容
```text
interface EnabledModelListProps {
const EnabledModelList = ({ activeTab }: EnabledModelListProps) => {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { ActionIcon, Center, Flexbox, Text, TooltipGroup } from '@lobehub/ui';
import isEqual from 'fast-deep-equal';
import { ArrowDownUpIcon, ToggleLeft } from 'lucide-react';
import { use, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useAiInfraStore } from '@/store/aiInfra';
import { aiModelSelectors } from '@/store/aiInfra/selectors';

import ModelItem from '../ModelItem';
import { ProviderSettingsContext } from '../ProviderSettingsContext';
import SortModelModal from '../SortModelModal';

interface EnabledModelListProps {
  activeTab: string;
}

const EnabledModelList = ({ activeTab }: EnabledModelListProps) => {
  const { t } = useTranslation('modelProvider');
  const { modelEditable } = use(ProviderSettingsContext);

  const enabledModels = useAiInfraStore(aiModelSelectors.enabledAiProviderModelList, isEqual);
  const batchToggleAiModels = useAiInfraStore((s) => s.batchToggleAiModels);
  const [open, setOpen] = useState(false);
  const [batchLoading, setBatchLoading] = useState(false);

  const isEmpty = enabledModels.length === 0;

  // Filter models based on active tab
  const filteredModels = useMemo(() => {
    if (activeTab === 'all') return enabledModels;
    return enabledModels.filter((model) => model.type === activeTab);
  }, [enabledModels, activeTab]);

  // Models that can be toggled (exclude embedding models when not editable)
  const togglableModels = useMemo(
    () =>
      modelEditable ? filteredModels : filteredModels.filter((model) => model.type !== 'embedding'),
    [filteredModels, modelEditable],
  );

  const isCurrentTabEmpty = filteredModels.length === 0;
  return (
    <>
      <Flexbox horizontal justify={'space-between'}>
        <Text style={{ fontSize: 12, marginTop: 8 }} type={'secondary'}>
          {t('providerModels.list.enabled')}
        </Text>
        {!isEmpty && (
          <TooltipGroup>
            <Flexbox horizontal>
              {togglableModels.length > 0 && (
                <ActionIcon
                  icon={ToggleLeft}
                  loading={batchLoading}
                  size={'small'}
                  title={t('providerModels.list.enabledActions.disableAll')}
                  onClick={async () => {
                    setBatchLoading(true);
                    await batchToggleAiModels(
                      togglableModels.map((i) => i.id),
                      false,
                    );
                    setBatchLoading(false);
                  }}
                />
              )}

              <ActionIcon
                icon={ArrowDownUpIcon}
                size={'small'}
                title={t('providerModels.list.enabledActions.sort')}
                onClick={() => {
                  setOpen(true);
                }}
              />
            </Flexbox>
          </TooltipGroup>
        )}
        {open && (
          <SortModelModal
            defaultItems={enabledModels}
            open={open}
            onCancel={() => {
              setOpen(false);
            }}
          />
        )}
      </Flexbox>

      {isEmpty ? (
        <Center padding={12}>
          <Text style={{ fontSize: 12 }} type={'secondary'}>
            {t('providerModels.list.enabledEmpty')}
          </Text>
        </Center>
      ) : isCurrentTabEmpty ? (
        <Center padding={12}>
          <Text style={{ fontSize: 12 }} type={'secondary'}>
            {t('providerModels.list.noModelsInCategory')}
          </Text>
        </Center>
      ) : (
        <TooltipGroup>
          <Flexbox gap={2}>
            {filteredModels.map(({ displayName, id, ...res }) => {
              const label = displayName || id;
              return (
                <ModelItem displayName={label as string} id={id as string} key={id} {...res} />
              );
            })}
          </Flexbox>
        </TooltipGroup>
      )}
    </>
  );
};
export default EnabledModelList;

```
