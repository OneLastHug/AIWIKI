# 文件：src/routes/(main)/settings/provider/detail/github/index.tsx

## 文件职责
这个文件位于 `src/routes/(main)/settings/provider/detail/github`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { Markdown } from '@lobehub/ui';
import { createStaticStyles } from 'antd-style';
import { GithubProviderCard } from 'model-bank/modelProviders';
import { useTranslation } from 'react-i18next';
import { FormPassword } from '@/components/FormInput';
import { SkeletonInput } from '@/components/Skeleton';
import { aiProviderSelectors, useAiInfraStore } from '@/store/aiInfra';
import { type GlobalLLMProviderKey } from '@/types/user/settings';
import { KeyVaultsConfigKey, LLMProviderApiTokenKey } from '../../const';
import { type ProviderItem } from '../../type';
import ProviderDetail from '../default';
export default Page;
```

## 主要对外内容
```text
const styles = createStaticStyles(({ css, cssVar }) => ({
const providerKey: GlobalLLMProviderKey = 'github';
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

import { Markdown } from '@lobehub/ui';
import { createStaticStyles } from 'antd-style';
import { GithubProviderCard } from 'model-bank/modelProviders';
import { useTranslation } from 'react-i18next';

import { FormPassword } from '@/components/FormInput';
import { SkeletonInput } from '@/components/Skeleton';
import { aiProviderSelectors, useAiInfraStore } from '@/store/aiInfra';
import { type GlobalLLMProviderKey } from '@/types/user/settings';

import { KeyVaultsConfigKey, LLMProviderApiTokenKey } from '../../const';
import { type ProviderItem } from '../../type';
import ProviderDetail from '../default';

const styles = createStaticStyles(({ css, cssVar }) => ({
  markdown: css`
    p {
      color: ${cssVar.colorTextDescription} !important;
    }
  `,
  tip: css`
    font-size: 12px;
    color: ${cssVar.colorTextDescription};
  `,
}));

const providerKey: GlobalLLMProviderKey = 'github';

// Same as OpenAIProvider, but replace API Key with Github Personal Access Token
const useProviderCard = (): ProviderItem => {
  const { t } = useTranslation('modelProvider');
  const isLoading = useAiInfraStore(aiProviderSelectors.isAiProviderConfigLoading(providerKey));

  return {
    ...GithubProviderCard,
    apiKeyItems: [
      {
        children: isLoading ? (
          <SkeletonInput />
        ) : (
          <FormPassword
            autoComplete={'new-password'}
            placeholder={t(`github.personalAccessToken.placeholder`)}
          />
        ),
        desc: (
          <Markdown className={styles.markdown} fontSize={12} variant={'chat'}>
            {t('github.personalAccessToken.desc')}
          </Markdown>
        ),
        label: t('github.personalAccessToken.title'),
        name: [KeyVaultsConfigKey, LLMProviderApiTokenKey],
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
