# 文件：src/routes/(main)/settings/provider/features/ModelList/EnabledModelList/index.tsx

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
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
