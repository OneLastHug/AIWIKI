# 文件：src/routes/(main)/home/_layout/Body/Agent/Modals/ConfigGroupModal/index.tsx

## 文件职责
这个文件位于 `src/routes/(main)/home/_layout/Body/Agent/Modals/ConfigGroupModal`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { Button, Modal, type ModalProps, SortableList } from '@lobehub/ui';
import { Flexbox } from '@lobehub/ui';
import { createStaticStyles } from 'antd-style';
import isEqual from 'fast-deep-equal';
import { Plus } from 'lucide-react';
import { memo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useHomeStore } from '@/store/home';
import { homeAgentListSelectors } from '@/store/home/selectors';
import type { SessionGroupItemBase } from '@/types/session';
import GroupItem from './GroupItem';
export default ConfigGroupModal;
```

## 主要对外内容
```text
const styles = createStaticStyles(({ css, cssVar }) => ({
const ConfigGroupModal = memo<ModalProps>(({ open, onCancel }) => {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { Button, Modal, type ModalProps, SortableList } from '@lobehub/ui';
import { Flexbox } from '@lobehub/ui';
import { createStaticStyles } from 'antd-style';
import isEqual from 'fast-deep-equal';
import { Plus } from 'lucide-react';
import { memo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useHomeStore } from '@/store/home';
import { homeAgentListSelectors } from '@/store/home/selectors';
import type { SessionGroupItemBase } from '@/types/session';

import GroupItem from './GroupItem';

const styles = createStaticStyles(({ css, cssVar }) => ({
  container: css`
    height: 36px;
    padding-inline: 8px;
    border-radius: ${cssVar.borderRadius}px;
    transition: background 0.2s ease-in-out;

    &:hover {
      background: ${cssVar.colorFillTertiary};
    }
  `,
}));

const ConfigGroupModal = memo<ModalProps>(({ open, onCancel }) => {
  const { t } = useTranslation('chat');
  // Map SidebarGroup to SessionGroupItem-like structure for the sortable list
  const sessionGroupItems = useHomeStore(
    (s) =>
      homeAgentListSelectors.agentGroups(s).map((g) => ({
        id: g.id,
        name: g.name,
        sort: g.sort,
      })),
    isEqual,
  ) as SessionGroupItemBase[];
  const [addGroup, updateGroupSort] = useHomeStore((s) => [s.addGroup, s.updateGroupSort]);
  const [loading, setLoading] = useState(false);

  return (
    <Modal
      allowFullscreen
      footer={null}
      open={open}
      title={t('sessionGroup.config')}
      width={400}
      onCancel={onCancel}
    >
      <Flexbox>
        <SortableList
          items={sessionGroupItems}
          renderItem={(item: SessionGroupItemBase) => (
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
          onChange={(items: SessionGroupItemBase[]) => {
            updateGroupSort(items);
          }}
        />
        <Button
          block
          icon={Plus}
          loading={loading}
          onClick={async () => {
            setLoading(true);
            await addGroup(t('sessionGroup.newGroup'));
            setLoading(false);
          }}
        >
          {t('sessionGroup.createGroup')}
        </Button>
      </Flexbox>
    </Modal>
  );
});

export default ConfigGroupModal;

```
