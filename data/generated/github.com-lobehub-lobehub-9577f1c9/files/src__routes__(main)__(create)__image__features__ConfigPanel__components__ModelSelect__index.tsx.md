# 文件：src/routes/(main)/(create)/image/features/ConfigPanel/components/ModelSelect/index.tsx

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
import { type SelectProps } from '@lobehub/ui';
import { ActionIcon, Flexbox, Icon, Select } from '@lobehub/ui';
import { createStaticStyles, cssVar } from 'antd-style';
import { LucideArrowRight, LucideBolt } from 'lucide-react';
import { memo, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import { ProviderItemRender } from '@/components/ModelSelect';
import { useAiInfraStore } from '@/store/aiInfra';
import { aiProviderSelectors } from '@/store/aiInfra/slices/aiProvider/selectors';
import { useImageStore } from '@/store/image';
import { imageGenerationConfigSelectors } from '@/store/image/selectors';
import { type EnabledProviderWithModels } from '@/types/index';

import ImageModelItem from './ImageModelItem';

const prefixCls = 'ant';

const styles = createStaticStyles(({ css, cssVar }) => ({
  popup: css`
    &.${prefixCls}-select-dropdown .${prefixCls}-select-item-option {
      margin-block: 1px;
      margin-inline: 4px;
      padding-block: 8px;
      padding-inline: 8px;
      border-radius: ${cssVar.borderRadiusSM};
    }
    &.${prefixCls}-select-dropdown .${prefixCls}-select-item-option-selected {
      background: ${cssVar.colorFillTertiary};
    }
    &.${prefixCls}-select-dropdown .${prefixCls}-select-item-option-grouped {
      padding-inline-start: 12px;
    }
  `,
}));

interface ModelOption {
  label: any;
  provider: string;
  value: string;
}

const ModelSelect = memo(() => {
  const { t } = useTranslation('components');
  const navigate = useNavigate();

  const [currentModel, currentProvider] = useImageStore((s) => [
    imageGenerationConfigSelectors.model(s),
    imageGenerationConfigSelectors.provider(s),
  ]);
  const setModelAndProviderOnSelect = useImageStore((s) => s.setModelAndProviderOnSelect);

  const enabledImageModelList = useAiInfraStore(aiProviderSelectors.enabledImageModelList);

  const options = useMemo<SelectProps['options']>(() => {
    const getImageModels = (provider: EnabledProviderWithModels) => {
      const modelOptions = provider.children.map((model) => ({
        label: <ImageModelItem {...model} providerId={provider.id} />,
        provider: provider.id,
        value: `${provider.id}/${model.id}`,
      }));

      // if there are no models, add a placeholder guide
      if (modelOptions.length === 0) {
        return [
          {
            disabled: true,
            label: (
              <Flexbox horizontal gap={8} style={{ color: cssVar.colorTextTertiary }}>
                {t('ModelSwitchPanel.emptyModel')}
                <Icon icon={LucideArrowRight} />
              </Flexbox>
            ),
            onClick: () => {
              navigate(`/settings/provider/${provider.id}`);
            },
            value: `${provider.id}/empty`,
          },
        ];
      }

      return modelOptions;
    };

    // if there are no providers at all
    if (enabledImageModelList.length === 0) {
      return [
        {
          disabled: true,
          label: (
            <Flexbox horizontal gap={8} style={{ color: cssVar.colorTextTertiary }}>
              {t('ModelSwitchPanel.emptyProvider')}
              <Icon icon={LucideArrowRight} />
            </Flexbox>
          ),
          onClick: () => {
            navigate('/settings/provider/all');
          },
          value: 'no-provider',
        },
      ];
    }

    if (enabledImageModelList.length === 1) {
      const provider = enabledImageModelList[0];
      return getImageModels(provider);
    }

    return enabledImageModelList.map((provider) => ({
      label: (
        <Flexbox horizontal justify="space-between">
          <ProviderItemRender
            logo={provider.logo}
            name={provider.name}
            provider={provider.id}
            source={provider.source}
          />
          <ActionIcon
            icon={LucideBolt}
            size={'small'}
            title={t('ModelSwitchPanel.goToSettings')}
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/settings/provider/${provider.id}`);
            }}
          />
        </Flexbox>
      ),
      options: getImageModels(provider),
    }));
  }, [enabledImageModelList, t, navigate]);

  const labelRender: SelectProps['labelRender'] = (props) => {
    const modelInfo = enabledImageModelList
      .flatMap((provider) =>
        provider.children.map((model) => ({ ...model, providerId: provider.id })),
      )
      .find((model) => props.value === `${model.providerId}/${model.id}`);

    if (!modelInfo) return props.label;

    return (
      <ImageModelItem
        {...modelInfo}
        providerId={modelInfo.providerId}
        showBadge={false}
        showPopover={false}
      />
    );
  };

  return (
    <Select
      shadow
      labelRender={labelRender}
      options={options}
      popupClassName={styles.popup}
      size={'large'}
      value={currentProvider && currentModel ? `${currentProvider}/${currentModel}` : undefined}
      style={{
        width: '100%',
      }}
      onChange={(value, option) => {
        // Skip onChange for disabled options (empty states)
        if (value === 'no-provider' || value.includes('/empty')) return;
        const model = value.split('/').slice(1).join('/');
        const provider = (option as unknown as ModelOption).provider;
        if (model !== currentModel || provider !== currentProvider) {
          setModelAndProviderOnSelect(model, provider);
        }
      }}
    />
  );
});

export default ModelSelect;

```
