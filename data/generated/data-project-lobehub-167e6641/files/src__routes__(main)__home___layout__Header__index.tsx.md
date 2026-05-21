# 文件：src/routes/(main)/home/_layout/Header/index.tsx

## 文件职责
这个文件位于 `src/routes/(main)/home/_layout/Header`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { memo } from 'react';
import SideBarHeaderLayout from '@/features/NavPanel/SideBarHeaderLayout';
import InboxButton from './components/InboxButton';
import Nav from './components/Nav';
import User from './components/User';
export default Header;
```

## 主要对外内容
```text
const Header = memo(() => {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
'use client';

import { memo } from 'react';

import SideBarHeaderLayout from '@/features/NavPanel/SideBarHeaderLayout';

import InboxButton from './components/InboxButton';
import Nav from './components/Nav';
import User from './components/User';

const Header = memo(() => {
  return (
    <>
      <SideBarHeaderLayout left={<User />} right={<InboxButton />} showBack={false} />
      <Nav />
    </>
  );
});

export default Header;

```
