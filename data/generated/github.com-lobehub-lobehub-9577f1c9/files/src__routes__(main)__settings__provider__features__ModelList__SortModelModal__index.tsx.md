# 文件：src/routes/(main)/settings/provider/features/ModelList/SortModelModal/index.tsx

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
import { Button, Flexbox, Modal, SortableList } from '@lobehub/ui';
import { App } from 'antd';
import { createStaticStyles } from 'antd-style';
import { type AiProviderModelListItem } from 'model-bank';
import { memo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useAiInfraStore } from '@/store/aiInfra';

import ListItem from './ListItem';

const styles = createStaticStyles(({ css, cssVar }) => ({
  container: css`
    height: 36px;
    padding-inline: 8px;
    border-radius: ${cssVar.borderRadius};
    transition: background 0.2s ease-in-out;

    &:hover {
      background: ${cssVar.colorFillTertiary};
    }
  `,
}));

interface SortModelModalProps {
  defaultItems: AiProviderModelListItem[];
  onCancel: () => void;
  open: boolean;
}
const SortModelModal = memo<SortModelModalProps>(({ open, onCancel, defaultItems }) => {
  const { t } = useTranslation('modelProvider');
  const [providerId, updateAiModelsSort] = useAiInfraStore((s) => [
    s.activeAiProvider,
    s.updateAiModelsSort,
  ]);
  const [loading, setLoading] = useState(false);
  const { message } = App.useApp();

  const [items, setItems] = useState(defaultItems);
  return (
    <Modal
      allowFullscreen
      footer={null}
      open={open}
      title={t('sortModal.title')}
      width={400}
      onCancel={onCancel}
    >
      <Flexbox gap={16}>
        <SortableList
          items={items}
          renderItem={(item: AiProviderModelListItem) => (
            <SortableList.Item
              horizontal
              align={'center'}
              className={styles.container}
              gap={4}
              id={item.id}
              justify={'space-between'}
            >
              <ListItem {...item} />
            </SortableList.Item>
          )}
          onChange={async (items: AiProviderModelListItem[]) => {
            setItems(items);
          }}
        />
        <Button
          block
          loading={loading}
          style={{ bottom: 0, position: 'sticky' }}
          type={'primary'}
          onClick={async () => {
            if (!providerId) return;

            const sortMap = items.map((item, index) => ({
              id: item.id,
              sort: index,
              type: item.type,
            }));

            setLoading(true);
            await updateAiModelsSort(providerId, sortMap);
            setLoading(false);
            message.success(t('sortModal.success'));
            onCancel();
          }}
        >
          {t('sortModal.update')}
        </Button>
      </Flexbox>
    </Modal>
  );
});

export default SortModelModal;

```
