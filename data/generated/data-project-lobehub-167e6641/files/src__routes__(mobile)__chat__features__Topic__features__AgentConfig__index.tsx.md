# 文件：src/routes/(mobile)/chat/features/Topic/features/AgentConfig/index.tsx

## 文件职责
这个文件位于 `src/routes/(mobile)/chat/features/Topic/features/AgentConfig`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { ActionIcon } from '@lobehub/ui';
import { Edit } from 'lucide-react';
import { type MouseEvent } from 'react';
import { memo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import useMergeState from 'use-merge-value';
import { useAgentStore } from '@/store/agent';
import { agentSelectors } from '@/store/agent/selectors';
import { useGlobalStore } from '@/store/global';
import { systemStatusSelectors } from '@/store/global/selectors';
import { useSessionStore } from '@/store/session';
import { sessionSelectors } from '@/store/session/selectors';
import ConfigLayout from '../ConfigLayout';
import Header from './Header';
import SystemRole from './SystemRole';
export default AgentConfig;
```

## 主要对外内容
```text
const AgentConfig = memo(() => {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
'use client';

import { ActionIcon } from '@lobehub/ui';
import { Edit } from 'lucide-react';
import { type MouseEvent } from 'react';
import { memo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import useMergeState from 'use-merge-value';

import { useAgentStore } from '@/store/agent';
import { agentSelectors } from '@/store/agent/selectors';
import { useGlobalStore } from '@/store/global';
import { systemStatusSelectors } from '@/store/global/selectors';
import { useSessionStore } from '@/store/session';
import { sessionSelectors } from '@/store/session/selectors';

import ConfigLayout from '../ConfigLayout';
import Header from './Header';
import SystemRole from './SystemRole';

const AgentConfig = memo(() => {
  const [editing, setEditing] = useState(false);

  const [init, sessionId] = useSessionStore((s) => [
    sessionSelectors.isSomeSessionActive(s),
    s.activeId,
  ]);

  const [isAgentConfigLoading] = useAgentStore((s) => [agentSelectors.isAgentConfigLoading(s)]);

  const [showSystemRole, toggleSystemRole] = useGlobalStore((s) => [
    systemStatusSelectors.showSystemRole(s),
    s.toggleSystemRole,
  ]);

  const [open, setOpen] = useMergeState(false, {
    defaultValue: showSystemRole,
    onChange: toggleSystemRole,
    value: showSystemRole,
  });

  const { t } = useTranslation('common');

  const isLoading = !init || isAgentConfigLoading;

  const handleOpenWithEdit = (e: MouseEvent) => {
    if (isLoading) return;

    e.stopPropagation();
    setEditing(true);
    setOpen(true);
  };

  return (
    <ConfigLayout
      expandedHeight={200}
      headerStyle={{ cursor: 'pointer' }}
      sessionId={sessionId}
      title={<Header />}
      actions={
        <ActionIcon icon={Edit} size={'small'} title={t('edit')} onClick={handleOpenWithEdit} />
      }
    >
      <SystemRole
        editing={editing}
        isLoading={isLoading}
        open={open}
        setEditing={setEditing}
        setOpen={setOpen}
      />
    </ConfigLayout>
  );
});

AgentConfig.displayName = 'AgentConfig';

export default AgentConfig;

```
