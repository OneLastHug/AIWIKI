# 文件：src/routes/(popup)/_layout/index.tsx

## 文件职责
这个文件位于 `src/routes/(popup)/_layout`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { HotkeyScopeEnum } from '@lobechat/const/hotkeys';
import { Flexbox } from '@lobehub/ui';
import { createStaticStyles } from 'antd-style';
import { type FC } from 'react';
import { HotkeysProvider } from 'react-hotkeys-hook';
import { Outlet } from 'react-router-dom';
import { isDesktop } from '@/const/version';
import ProtocolUrlHandler from '@/features/ProtocolUrlHandler';
import { MarketAuthProvider } from '@/layout/AuthProvider/MarketAuth';
import { useChatStore } from '@/store/chat';
import { topicSelectors } from '@/store/chat/selectors';
import PopupTitleBar from './TitleBar';
export default PopupLayout;
```

## 主要对外内容
```text
const styles = createStaticStyles(({ css, cssVar }) => ({
const PopupLayout: FC = () => {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
'use client';

import { HotkeyScopeEnum } from '@lobechat/const/hotkeys';
import { Flexbox } from '@lobehub/ui';
import { createStaticStyles } from 'antd-style';
import { type FC } from 'react';
import { HotkeysProvider } from 'react-hotkeys-hook';
import { Outlet } from 'react-router-dom';

import { isDesktop } from '@/const/version';
import ProtocolUrlHandler from '@/features/ProtocolUrlHandler';
import { MarketAuthProvider } from '@/layout/AuthProvider/MarketAuth';
import { useChatStore } from '@/store/chat';
import { topicSelectors } from '@/store/chat/selectors';

import PopupTitleBar from './TitleBar';

const styles = createStaticStyles(({ css, cssVar }) => ({
  container: css`
    background: ${cssVar.colorBgContainer};
  `,
}));

const PopupLayout: FC = () => {
  const topicTitle = useChatStore((s) => topicSelectors.currentActiveTopic(s)?.title);

  return (
    <HotkeysProvider initiallyActiveScopes={[HotkeyScopeEnum.Global]}>
      <MarketAuthProvider isDesktop={isDesktop}>
        <Flexbox
          className={styles.container}
          height={'100%'}
          style={{ overflow: 'hidden' }}
          width={'100%'}
        >
          <PopupTitleBar title={topicTitle} />
          <Flexbox flex={1} style={{ minHeight: 0, overflow: 'hidden', position: 'relative' }}>
            <Outlet />
          </Flexbox>
          <ProtocolUrlHandler />
        </Flexbox>
      </MarketAuthProvider>
    </HotkeysProvider>
  );
};

export default PopupLayout;

```
