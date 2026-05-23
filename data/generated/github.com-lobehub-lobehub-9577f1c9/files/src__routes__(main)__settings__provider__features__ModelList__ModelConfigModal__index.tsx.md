# 文件：src/routes/(main)/settings/provider/features/ModelList/ModelConfigModal/index.tsx

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
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
