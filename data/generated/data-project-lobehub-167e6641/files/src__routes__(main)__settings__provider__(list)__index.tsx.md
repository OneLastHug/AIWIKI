# 文件：src/routes/(main)/settings/provider/(list)/index.tsx

## 文件职责
这个文件位于 `src/routes/(main)/settings/provider/(list)`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { isCustomBranding } from '@/const/version';
import DesktopLayout from '../_layout/Desktop';
import MobileLayout from '../_layout/Mobile';
import ProviderDetailPage from '../detail';
import Footer from './Footer';
export default Page;
```

## 主要对外内容
```text
const Page = (props: { mobile?: boolean }) => {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
'use client';

import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import { isCustomBranding } from '@/const/version';

import DesktopLayout from '../_layout/Desktop';
import MobileLayout from '../_layout/Mobile';
import ProviderDetailPage from '../detail';
import Footer from './Footer';

const Page = (props: { mobile?: boolean }) => {
  const [SearchParams, setSearchParams] = useSearchParams();
  const [provider, setProviderState] = useState(SearchParams.get('provider') || 'all');
  const setProvider = (provider: string) => {
    setSearchParams({ active: 'provider', provider });
    setProviderState(provider);
  };

  const { mobile } = props;
  const ProviderLayout = mobile ? MobileLayout : DesktopLayout;

  const ProviderListPage = useMemo(() => {
    return <ProviderDetailPage id={provider} onProviderSelect={setProvider} />;
  }, [provider]);

  return (
    <ProviderLayout onProviderSelect={setProvider}>
      {ProviderListPage}
      {!isCustomBranding && <Footer />}
    </ProviderLayout>
  );
};

export default Page;

```
