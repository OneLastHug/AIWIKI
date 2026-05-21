# 文件：src/routes/(main)/settings/provider/detail/azureai/index.tsx

## 文件职责
这个文件位于 `src/routes/(main)/settings/provider/detail/azureai`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { ModelProvider } from 'model-bank';
import { AzureAIProviderCard } from 'model-bank/modelProviders';
import { useTranslation } from 'react-i18next';
import { FormInput, FormPassword } from '@/components/FormInput';
import { SkeletonInput } from '@/components/Skeleton';
import { aiProviderSelectors, useAiInfraStore } from '@/store/aiInfra';
import { KeyVaultsConfigKey, LLMProviderApiTokenKey, LLMProviderBaseUrlKey } from '../../const';
import { type ProviderItem } from '../../type';
import ProviderDetail from '../default';
export default Page;
```

## 主要对外内容
```text
const providerKey = ModelProvider.AzureAI;
const useProviderCard = (): ProviderItem => {
const Page = () => {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
'use client';

import { ModelProvider } from 'model-bank';
import { AzureAIProviderCard } from 'model-bank/modelProviders';
import { useTranslation } from 'react-i18next';

import { FormInput, FormPassword } from '@/components/FormInput';
import { SkeletonInput } from '@/components/Skeleton';
import { aiProviderSelectors, useAiInfraStore } from '@/store/aiInfra';

import { KeyVaultsConfigKey, LLMProviderApiTokenKey, LLMProviderBaseUrlKey } from '../../const';
import { type ProviderItem } from '../../type';
import ProviderDetail from '../default';

const providerKey = ModelProvider.AzureAI;

const useProviderCard = (): ProviderItem => {
  const { t } = useTranslation('modelProvider');

  const isLoading = useAiInfraStore(aiProviderSelectors.isAiProviderConfigLoading(providerKey));

  return {
    ...AzureAIProviderCard,
    apiKeyItems: [
      {
        children: isLoading ? (
          <SkeletonInput />
        ) : (
          <FormPassword
            autoComplete={'new-password'}
            placeholder={t('azureai.token.placeholder')}
          />
        ),
        desc: t('azureai.token.desc'),
        label: t('azureai.token.title'),
        name: [KeyVaultsConfigKey, LLMProviderApiTokenKey],
      },
      {
        children: isLoading ? (
          <SkeletonInput />
        ) : (
          <FormInput allowClear placeholder={t('azureai.endpoint.placeholder')} />
        ),
        desc: t('azureai.endpoint.desc'),
        label: t('azureai.endpoint.title'),
        name: [KeyVaultsConfigKey, LLMProviderBaseUrlKey],
      },
    ],
  };
};

const Page = () => {
  const card = useProviderCard();

  return <ProviderDetail {...card} />;
};

export default Page;

```
