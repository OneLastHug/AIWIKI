# 文件：src/routes/(main)/settings/provider/features/ModelList/ModelTitle/index.tsx

## 文件职责
这个文件位于 `src/routes/(main)/settings/provider/features/ModelList/ModelTitle`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { ActionIcon, Button, DropdownMenu, Flexbox, Skeleton, Text } from '@lobehub/ui';
import { App, Space } from 'antd';
import { cssVar } from 'antd-style';
import { CircleX, EllipsisVertical, LucideRefreshCcwDot, PlusIcon } from 'lucide-react';
import { memo, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useIsMobile } from '@/hooks/useIsMobile';
import { useAiInfraStore } from '@/store/aiInfra';
import { aiModelSelectors } from '@/store/aiInfra/selectors';
import CreateNewModelModal from '../CreateNewModelModal';
import Search from './Search';
export default ModelTitle;
```

## 主要对外内容
```text
interface ModelFetcherProps {
const ModelTitle = memo<ModelFetcherProps>(
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { ActionIcon, Button, DropdownMenu, Flexbox, Skeleton, Text } from '@lobehub/ui';
import { App, Space } from 'antd';
import { cssVar } from 'antd-style';
import { CircleX, EllipsisVertical, LucideRefreshCcwDot, PlusIcon } from 'lucide-react';
import { memo, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useIsMobile } from '@/hooks/useIsMobile';
import { useAiInfraStore } from '@/store/aiInfra';
import { aiModelSelectors } from '@/store/aiInfra/selectors';

import CreateNewModelModal from '../CreateNewModelModal';
import Search from './Search';

interface ModelFetcherProps {
  provider: string;
  showAddNewModel?: boolean;
  showModelFetcher?: boolean;
}

const ModelTitle = memo<ModelFetcherProps>(
  ({ provider, showAddNewModel = true, showModelFetcher = true }) => {
    const { t } = useTranslation('modelProvider');
    const { modal, message } = App.useApp();
    const [
      searchKeyword,
      totalModels,
      isEmpty,
      hasRemoteModels,
      fetchRemoteModelList,
      clearObtainedModels,
      clearModelsByProvider,
      useFetchAiProviderModels,
    ] = useAiInfraStore((s) => [
      s.modelSearchKeyword,
      aiModelSelectors.totalAiProviderModelList(s),
      aiModelSelectors.isEmptyAiProviderModelList(s),
      aiModelSelectors.hasRemoteModels(s),
      s.fetchRemoteModelList,
      s.clearRemoteModels,
      s.clearModelsByProvider,
      s.useFetchAiProviderModels,
    ]);

    const { isLoading } = useFetchAiProviderModels(provider);

    const [fetchRemoteModelsLoading, setFetchRemoteModelsLoading] = useState(false);
    const [clearRemoteModelsLoading, setClearRemoteModelsLoading] = useState(false);
    const [showModal, setShowModal] = useState(false);

    const mobile = useIsMobile();

    useEffect(() => {
      useAiInfraStore.setState({ modelSearchKeyword: '' });
    }, [provider]);

    return (
      <Flexbox
        gap={12}
        paddingBlock={8}
        style={{
          background: cssVar.colorBgContainer,
          marginTop: mobile ? 0 : -12,
          paddingTop: mobile ? 0 : 20,
          position: 'sticky',
          top: mobile ? -2 : -32,
          zIndex: 15,
        }}
      >
        <Flexbox horizontal align={'center'} gap={0} justify={'space-between'}>
          <Flexbox horizontal align={'center'} gap={8}>
            <Text strong style={{ fontSize: 16 }}>
              {t('providerModels.list.title')}
            </Text>

            {isLoading ? (
              <Skeleton.Button active style={{ height: 22 }} />
            ) : (
              <Text style={{ fontSize: 12 }} type={'secondary'}>
                <div style={{ display: 'flex', lineHeight: '24px' }}>
                  {t('providerModels.list.total', { count: totalModels })}
                  {hasRemoteModels && (
                    <ActionIcon
                      icon={CircleX}
                      loading={clearRemoteModelsLoading}
                      size={'small'}
                      title={t('providerModels.list.fetcher.clear')}
                      onClick={async () => {
                        setClearRemoteModelsLoading(true);
                        await clearObtainedModels(provider);
                        setClearRemoteModelsLoading(false);
                      }}
                    />
                  )}
                </div>
              </Text>
            )}
          </Flexbox>
          {isLoading ? (
            <Skeleton.Button active size={'small'} style={{ width: 120 }} />
          ) : isEmpty ? null : (
            <Flexbox horizontal gap={8}>
              {!mobile && (
                <Search
                  value={searchKeyword}
                  onChange={(value) => {
                    useAiInfraStore.setState({ modelSearchKeyword: value });
                  }}
                />
              )}
              <Space.Compact>
                {showModelFetcher && (
                  <Button
                    icon={LucideRefreshCcwDot}
                    loading={fetchRemoteModelsLoading}
                    size={'small'}
                    onClick={async () => {
                      setFetchRemoteModelsLoading(true);
                      try {
                        await fetchRemoteModelList(provider);
                      } catch (e) {
                        console.error(e);
                      }
                      setFetchRemoteModelsLoading(false);
                    }}
                  >
                    {fetchRemoteModelsLoading
                      ? t('providerModels.list.fetcher.fetching')
                      : t('providerModels.list.fetcher.fetch')}
                  </Button>
                )}
                {showAddNewModel && (
                  <>
                    <Button
                      icon={PlusIcon}
                      size={'small'}
                      onClick={() => {
                        setShowModal(true);
                      }}
                    />
                    <CreateNewModelModal open={showModal} setOpen={setShowModal} />
                  </>
                )}
                <DropdownMenu
                  items={[
                    {
                      key: 'reset',
                      label: t('providerModels.list.resetAll.title'),
                      onClick: async () => {
                        modal.confirm({
                          content: t('providerModels.list.resetAll.conform'),
                          onOk: async () => {
                            await clearModelsByProvider(provider);
                            message.success(t('providerModels.list.resetAll.success'));
                          },
                          title: t('providerModels.list.resetAll.title'),
                        });
                      },
                    },
                  ]}
                >
                  <Button icon={EllipsisVertical} size={'small'} />
                </DropdownMenu>
              </Space.Compact>
            </Flexbox>
          )}
        </Flexbox>

        {mobile && (
          <Search
            value={searchKeyword}
            variant={'filled'}
            onChange={(value) => {
              useAiInfraStore.setState({ modelSearchKeyword: value });
            }}
          />
        )}
      </Flexbox>
    );
  },
);
export default ModelTitle;

```
