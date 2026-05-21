# 文件：src/routes/(main)/settings/provider/ProviderMenu/SortProviderModal/index.tsx

## 文件职责
这个文件位于 `src/routes/(main)/settings/provider/ProviderMenu/SortProviderModal`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { Button, Flexbox, Modal, SortableList } from '@lobehub/ui';
import { App } from 'antd';
import { createStaticStyles } from 'antd-style';
import { memo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAiInfraStore } from '@/store/aiInfra';
import { type AiProviderListItem } from '@/types/aiProvider';
import GroupItem from './GroupItem';
export default ConfigGroupModal;
```

## 主要对外内容
```text
const styles = createStaticStyles(({ css, cssVar }) => ({
interface ConfigGroupModalProps {
const ConfigGroupModal = memo<ConfigGroupModalProps>(({ open, onCancel, defaultItems }) => {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { Button, Flexbox, Modal, SortableList } from '@lobehub/ui';
import { App } from 'antd';
import { createStaticStyles } from 'antd-style';
import { memo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useAiInfraStore } from '@/store/aiInfra';
import { type AiProviderListItem } from '@/types/aiProvider';

import GroupItem from './GroupItem';

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

interface ConfigGroupModalProps {
  defaultItems: AiProviderListItem[];
  onCancel: () => void;
  open: boolean;
}
const ConfigGroupModal = memo<ConfigGroupModalProps>(({ open, onCancel, defaultItems }) => {
  const { t } = useTranslation('modelProvider');
  const updateAiProviderSort = useAiInfraStore((s) => s.updateAiProviderSort);
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
          renderItem={(item: AiProviderListItem) => (
            <SortableList.Item
              horizontal
              align={'center'}
              className={styles.container}
              gap={4}
              id={item.id}
              justify={'space-between'}
            >
              <GroupItem {...item} />
            </SortableList.Item>
          )}
          onChange={async (items: AiProviderListItem[]) => {
            setItems(items);
          }}
        />
        <Button
          block
          loading={loading}
          style={{ bottom: 0, position: 'sticky' }}
          type={'primary'}
          onClick={async () => {
            const sortMap = items.map((item, index) => ({
              id: item.id,
              sort: index,
            }));
            setLoading(true);
            await updateAiProviderSort(sortMap);
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

export default ConfigGroupModal;

```
