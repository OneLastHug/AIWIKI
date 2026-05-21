# 文件：src/routes/(main)/settings/provider/detail/comfyui/index.tsx

## 文件职责
这个文件位于 `src/routes/(main)/settings/provider/detail/comfyui`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { Select } from '@lobehub/ui';
import { ComfyUIProviderCard } from 'model-bank/modelProviders';
import { useTranslation } from 'react-i18next';
import { FormInput, FormPassword } from '@/components/FormInput';
import KeyValueEditor from '@/components/KeyValueEditor';
import { SkeletonInput } from '@/components/Skeleton';
import { aiProviderSelectors, useAiInfraStore } from '@/store/aiInfra';
import { type GlobalLLMProviderKey } from '@/types/user/settings';
import { KeyVaultsConfigKey } from '../../const';
import { type ProviderItem } from '../../type';
import ProviderDetail from '../default';
export default Page;
```

## 主要对外内容
```text
const providerKey: GlobalLLMProviderKey = 'comfyui';
const useComfyUICard = (): ProviderItem => {
const Page = () => {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
'use client';

import { Select } from '@lobehub/ui';
import { ComfyUIProviderCard } from 'model-bank/modelProviders';
import { useTranslation } from 'react-i18next';

import { FormInput, FormPassword } from '@/components/FormInput';
import KeyValueEditor from '@/components/KeyValueEditor';
import { SkeletonInput } from '@/components/Skeleton';
import { aiProviderSelectors, useAiInfraStore } from '@/store/aiInfra';
import { type GlobalLLMProviderKey } from '@/types/user/settings';

import { KeyVaultsConfigKey } from '../../const';
import { type ProviderItem } from '../../type';
import ProviderDetail from '../default';

const providerKey: GlobalLLMProviderKey = 'comfyui';

const useComfyUICard = (): ProviderItem => {
  const { t } = useTranslation('modelProvider');

  const isLoading = useAiInfraStore(aiProviderSelectors.isAiProviderConfigLoading(providerKey));

  // Get current config and watch for auth type changes
  const config = useAiInfraStore((s) => s.aiProviderRuntimeConfig?.[providerKey]);
  const authType = config?.keyVaults?.authType || 'none';

  const authTypeOptions = [
    { label: t('comfyui.authType.options.none'), value: 'none' },
    { label: t('comfyui.authType.options.basic'), value: 'basic' },
    { label: t('comfyui.authType.options.bearer'), value: 'bearer' },
    { label: t('comfyui.authType.options.custom'), value: 'custom' },
  ];

  const apiKeyItems = [
    // Base URL - Always shown
    {
      children: isLoading ? (
        <SkeletonInput />
      ) : (
        <FormInput placeholder={t('comfyui.baseURL.placeholder')} />
      ),
      desc: t('comfyui.baseURL.desc'),
      label: t('comfyui.baseURL.title'),
      name: [KeyVaultsConfigKey, 'baseURL'],
    },

    // Authentication Type Selector - Always shown
    {
      children: isLoading ? (
        <SkeletonInput />
      ) : (
        <Select
          allowClear={false}
          options={authTypeOptions}
          placeholder={t('comfyui.authType.placeholder')}
        />
      ),
      desc: t('comfyui.authType.desc'),
      label: t('comfyui.authType.title'),
      name: [KeyVaultsConfigKey, 'authType'],
    },
  ];

  // Conditionally add fields based on auth type
  if (authType === 'basic') {
    apiKeyItems.push(
      {
        children: isLoading ? (
          <SkeletonInput />
        ) : (
          <FormInput autoComplete="username" placeholder={t('comfyui.username.placeholder')} />
        ),
        desc: t('comfyui.username.desc'),
        label: t('comfyui.username.title'),
        name: [KeyVaultsConfigKey, 'username'],
      },
      {
        children: isLoading ? (
          <SkeletonInput />
        ) : (
          <FormPassword
            autoComplete="new-password"
            placeholder={t('comfyui.password.placeholder')}
          />
        ),
        desc: t('comfyui.password.desc'),
        label: t('comfyui.password.title'),
        name: [KeyVaultsConfigKey, 'password'],
      },
    );
  }

  if (authType === 'bearer') {
    apiKeyItems.push({
      children: isLoading ? (
        <SkeletonInput />
      ) : (
        <FormPassword autoComplete="new-password" placeholder={t('comfyui.apiKey.placeholder')} />
      ),
      desc: t('comfyui.apiKey.desc'),
      label: t('comfyui.apiKey.title'),
      name: [KeyVaultsConfigKey, 'apiKey'],
    });
  }

  if (authType === 'custom') {
    apiKeyItems.push({
      children: isLoading ? (
        <SkeletonInput />
      ) : (
        <KeyValueEditor
          addButtonText={t('comfyui.customHeaders.addButton')}
          deleteTooltip={t('comfyui.customHeaders.deleteTooltip')}
          duplicateKeyErrorText={t('comfyui.customHeaders.duplicateKeyError')}
          keyPlaceholder={t('comfyui.customHeaders.keyPlaceholder')}
          valuePlaceholder={t('comfyui.customHeaders.valuePlaceholder')}
        />
      ),
      desc: t('comfyui.customHeaders.desc'),
      label: t('comfyui.customHeaders.title'),
      name: [KeyVaultsConfigKey, 'customHeaders'],
    });
  }

  return {
    ...ComfyUIProviderCard,
    apiKeyItems,
  };
};

const Page = () => {
  const card = useComfyUICard();

  return <ProviderDetail {...card} />;
};

export default Page;

```
