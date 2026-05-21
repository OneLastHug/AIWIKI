# 文件：src/routes/(main)/settings/provider/features/ModelList/ModelConfigModal/index.tsx

## 文件职责
这个文件位于 `src/routes/(main)/settings/provider/features/ModelList/ModelConfigModal`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { Button, Modal } from '@lobehub/ui';
import { type FormInstance } from 'antd';
import isEqual from 'fast-deep-equal';
import { memo, use, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { aiModelSelectors, useAiInfraStore } from '@/store/aiInfra';
import ModelConfigForm from '../CreateNewModelModal/Form';
import { ProviderSettingsContext } from '../ProviderSettingsContext';
export default ModelConfigModal;
```

## 主要对外内容
```text
interface ModelConfigModalProps {
const ModelConfigModal = memo<ModelConfigModalProps>(({ id, open, setOpen }) => {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { Button, Modal } from '@lobehub/ui';
import { type FormInstance } from 'antd';
import isEqual from 'fast-deep-equal';
import { memo, use, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { aiModelSelectors, useAiInfraStore } from '@/store/aiInfra';

import ModelConfigForm from '../CreateNewModelModal/Form';
import { ProviderSettingsContext } from '../ProviderSettingsContext';

interface ModelConfigModalProps {
  id: string;
  open: boolean;
  setOpen: (open: boolean) => void;
}

const ModelConfigModal = memo<ModelConfigModalProps>(({ id, open, setOpen }) => {
  const { t } = useTranslation(['common', 'setting']);
  const [formInstance, setFormInstance] = useState<FormInstance>();
  const [loading, setLoading] = useState(false);
  const [editingProvider, updateAiModelsConfig] = useAiInfraStore((s) => [
    s.activeAiProvider!,
    s.updateAiModelsConfig,
  ]);
  const model = useAiInfraStore(aiModelSelectors.getAiModelById(id), isEqual);

  const closeModal = () => {
    setOpen(false);
  };
  const { showDeployName } = use(ProviderSettingsContext);

  return (
    <Modal
      destroyOnHidden
      maskClosable
      open={open}
      title={t('llm.customModelCards.modelConfig.modalTitle', { ns: 'setting' })}
      zIndex={1251} // Select is 1150
      footer={[
        <Button key="cancel" onClick={closeModal}>
          {t('cancel')}
        </Button>,
        <Button
          key="ok"
          loading={loading}
          style={{ marginInlineStart: '16px' }}
          type="primary"
          onClick={async () => {
            if (!editingProvider || !id || !formInstance) return;
            const data = formInstance.getFieldsValue();

            setLoading(true);
            await updateAiModelsConfig(id, editingProvider, data);
            setLoading(false);

            closeModal();
          }}
        >
          {t('ok')}
        </Button>,
      ]}
      styles={{
        body: {
          display: 'flex',
          flexDirection: 'column',
          maxHeight: 'calc(100vh - 150px)',
        },
      }}
      onCancel={closeModal}
    >
      <ModelConfigForm
        idEditable={false}
        initialValues={model}
        showDeployName={showDeployName}
        type={model?.type}
        onFormInstanceReady={setFormInstance}
      />
    </Modal>
  );
});
export default ModelConfigModal;

```
