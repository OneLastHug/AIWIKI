# 文件：src/routes/(mobile)/_layout/index.tsx

## 文件职责
这个文件位于 `src/routes/(mobile)/_layout`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { type FC } from 'react';
import { Suspense } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import Loading from '@/components/Loading/BrandTextLoading';
import { MarketAuthProvider } from '@/layout/AuthProvider/MarketAuth';
import dynamic from '@/libs/next/dynamic';
import { featureFlagsSelectors, useServerConfigStore } from '@/store/serverConfig';
import NavBar from './NavBar';
export default MobileMainLayout;
```

## 主要对外内容
```text
const CloudBanner = dynamic(() => import('@/features/AlertBanner/CloudBanner'));
const MOBILE_NAV_ROUTES = new Set([
const MobileMainLayout: FC = () => {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
'use client';

import { type FC } from 'react';
import { Suspense } from 'react';
import { Outlet, useLocation } from 'react-router-dom';

import Loading from '@/components/Loading/BrandTextLoading';
import { MarketAuthProvider } from '@/layout/AuthProvider/MarketAuth';
import dynamic from '@/libs/next/dynamic';
import { featureFlagsSelectors, useServerConfigStore } from '@/store/serverConfig';

import NavBar from './NavBar';

const CloudBanner = dynamic(() => import('@/features/AlertBanner/CloudBanner'));
const MOBILE_NAV_ROUTES = new Set([
  '/',
  '/community',
  '/community/agent',
  '/community/mcp',
  '/community/plugin',
  '/community/model',
  '/community/provider',
  '/me',
]);

const MobileMainLayout: FC = () => {
  const { showCloudPromotion } = useServerConfigStore(featureFlagsSelectors);
  const location = useLocation();
  const pathname = location.pathname;
  const showNav = MOBILE_NAV_ROUTES.has(pathname);
  return (
    <>
      <Suspense fallback={null}>{showCloudPromotion && <CloudBanner mobile />}</Suspense>
      <MarketAuthProvider isDesktop={false}>
        <Suspense fallback={<Loading debugId="MobileMainLayout > Outlet" />}>
          <Outlet />
          {showNav && <NavBar />}
        </Suspense>
      </MarketAuthProvider>
    </>
  );
};

export default MobileMainLayout;

```
