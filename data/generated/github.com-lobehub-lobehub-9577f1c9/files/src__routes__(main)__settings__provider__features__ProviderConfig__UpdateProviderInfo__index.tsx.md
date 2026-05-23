# 文件：src/routes/(main)/settings/provider/features/ProviderConfig/UpdateProviderInfo/index.tsx

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
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
