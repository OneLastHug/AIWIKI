# 文件：src/routes/(main)/settings/service-model/index.tsx

## 文件职责
这个文件位于 `src/routes/(main)/settings/service-model`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { useTranslation } from 'react-i18next';
import { ModelAssignmentsForm } from '@/features/ServiceModel';
import SettingHeader from '@/routes/(main)/settings/features/SettingHeader';
import { featureFlagsSelectors, useServerConfigStore } from '@/store/serverConfig';
import Image from '../image/features/Image';
import OpenAI from '../tts/features/OpenAI';
import STT from '../tts/features/STT';
export default Page;
```

## 主要对外内容
```text
const Page = () => {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
'use client';

import { useTranslation } from 'react-i18next';

import { ModelAssignmentsForm } from '@/features/ServiceModel';
import SettingHeader from '@/routes/(main)/settings/features/SettingHeader';
import { featureFlagsSelectors, useServerConfigStore } from '@/store/serverConfig';

import Image from '../image/features/Image';
import OpenAI from '../tts/features/OpenAI';
import STT from '../tts/features/STT';

const Page = () => {
  const { t } = useTranslation('setting');
  const { enableSTT, showAiImage } = useServerConfigStore(featureFlagsSelectors);
  return (
    <>
      <SettingHeader title={t('tab.serviceModel')} />
      <ModelAssignmentsForm />
      {enableSTT && (
        <>
          <STT />
          <OpenAI />
        </>
      )}
      {showAiImage && <Image />}
    </>
  );
};

export default Page;

```
