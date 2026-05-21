# 文件：src/routes/(main)/community/(list)/model/_layout/index.tsx

## 文件职责
这个文件位于 `src/routes/(main)/community/(list)/model/_layout`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { Flexbox } from '@lobehub/ui';
import { Outlet } from 'react-router-dom';
import CategoryContainer from '../../../components/CategoryContainer';
import Category from '../features/Category';
import { styles } from './style';
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
import { Flexbox } from '@lobehub/ui';
import { Outlet } from 'react-router-dom';

import CategoryContainer from '../../../components/CategoryContainer';
import Category from '../features/Category';
import { styles } from './style';

const Layout = () => {
  return (
    <Flexbox horizontal className={styles.mainContainer} gap={24} width={'100%'}>
      <CategoryContainer>
        <Category />
      </CategoryContainer>
      <Flexbox flex={1} gap={16}>
        <Outlet />
      </Flexbox>
    </Flexbox>
  );
};

export default Layout;

```
