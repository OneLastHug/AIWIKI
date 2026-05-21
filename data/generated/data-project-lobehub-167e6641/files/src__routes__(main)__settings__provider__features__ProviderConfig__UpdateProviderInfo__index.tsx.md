# 文件：src/routes/(main)/settings/provider/features/ProviderConfig/UpdateProviderInfo/index.tsx

## 文件职责
这个文件位于 `src/routes/(main)/settings/provider/features/ProviderConfig/UpdateProviderInfo`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { Button, Tooltip } from '@lobehub/ui';
import isEqual from 'fast-deep-equal';
import { SettingsIcon } from 'lucide-react';
import { memo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { aiProviderSelectors, useAiInfraStore } from '@/store/aiInfra';
import SettingModal from './SettingModal';
export default UpdateProviderInfo;
```

## 主要对外内容
```text
const UpdateProviderInfo = memo(() => {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
'use client';

import { Button, Tooltip } from '@lobehub/ui';
import isEqual from 'fast-deep-equal';
import { SettingsIcon } from 'lucide-react';
import { memo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { aiProviderSelectors, useAiInfraStore } from '@/store/aiInfra';

import SettingModal from './SettingModal';

const UpdateProviderInfo = memo(() => {
  const { t } = useTranslation('modelProvider');

  const [open, setOpen] = useState(false);
  const providerConfig = useAiInfraStore(aiProviderSelectors.activeProviderConfig, isEqual);

  return (
    <>
      <Tooltip title={t('updateAiProvider.tooltip')}>
        <Button
          icon={SettingsIcon}
          size={'small'}
          type={'text'}
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            setOpen(true);
          }}
        />
      </Tooltip>
      {open && providerConfig && (
        <SettingModal
          id={providerConfig.id}
          initialValues={providerConfig}
          open={open}
          onClose={() => {
            setOpen(false);
          }}
        />
      )}
    </>
  );
});

export default UpdateProviderInfo;

```
