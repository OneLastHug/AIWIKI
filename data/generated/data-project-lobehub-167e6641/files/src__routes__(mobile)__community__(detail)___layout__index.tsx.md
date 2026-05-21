# 文件：src/routes/(mobile)/community/(detail)/_layout/index.tsx

## 文件职责
这个文件位于 `src/routes/(mobile)/community/(detail)/_layout`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { Outlet } from 'react-router-dom';
import MobileContentLayout from '@/components/server/MobileNavLayout';
import Footer from '@/features/Setting/Footer';
import { SCROLL_PARENT_ID } from '@/routes/(main)/community/features/const';
import Header from './Header';
export default Layout;
```

## 主要对外内容
```text
const Layout = () => {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { Outlet } from 'react-router-dom';

import MobileContentLayout from '@/components/server/MobileNavLayout';
import Footer from '@/features/Setting/Footer';
import { SCROLL_PARENT_ID } from '@/routes/(main)/community/features/const';

import Header from './Header';

const Layout = () => {
  return (
    <MobileContentLayout gap={16} header={<Header />} id={SCROLL_PARENT_ID} padding={16}>
      <Outlet />
      <div />
      <Footer />
    </MobileContentLayout>
  );
};

export default Layout;

```
