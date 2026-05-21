# 文件：src/routes/(main)/settings/provider/index.tsx

## 文件职责
这个文件位于 `src/routes/(main)/settings/provider`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { Flexbox } from '@lobehub/ui';
import { memo } from 'react';
import { Outlet, useNavigate, useParams } from 'react-router-dom';
import { isCustomBranding } from '@/const/version';
import DesktopLayoutContainer from './_layout/Desktop/Container';
import Footer from './(list)/Footer';
import ProviderDetailPageComponent from './detail';
import ProviderMenu from './ProviderMenu';
export const ProviderLayout = memo(() => {
export const ProviderDetailPage = memo(() => {
export default ProviderPage;
```

## 主要对外内容
```text
export const ProviderLayout = memo(() => {
export const ProviderDetailPage = memo(() => {
type ProviderPageType = {
const ProviderPage = (props: ProviderPageType) => {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
'use client';

import { Flexbox } from '@lobehub/ui';
import { memo } from 'react';
import { Outlet, useNavigate, useParams } from 'react-router-dom';

import { isCustomBranding } from '@/const/version';

import DesktopLayoutContainer from './_layout/Desktop/Container';
import Footer from './(list)/Footer';
import ProviderDetailPageComponent from './detail';
import ProviderMenu from './ProviderMenu';

// Layout component that wraps provider pages with navigation
export const ProviderLayout = memo(() => {
  const navigate = useNavigate();

  const handleProviderSelect = (providerKey: string) => {
    navigate(`/settings/provider/${providerKey}`);
  };

  return (
    <Flexbox
      horizontal
      width={'100%'}
      style={{
        maxHeight: '100%',
      }}
    >
      <ProviderMenu mobile={false} onProviderSelect={handleProviderSelect} />
      <DesktopLayoutContainer>
        <Outlet />
        {!isCustomBranding && <Footer />}
      </DesktopLayoutContainer>
    </Flexbox>
  );
});

ProviderLayout.displayName = 'ProviderLayout';

// Detail page component that receives providerId from route params
export const ProviderDetailPage = memo(() => {
  const params = useParams<{ providerId: string }>();
  const navigate = useNavigate();

  const handleProviderSelect = (providerKey: string) => {
    navigate(`/settings/provider/${providerKey}`);
  };

  return (
    <ProviderDetailPageComponent
      id={params.providerId ?? ''}
      onProviderSelect={handleProviderSelect}
    />
  );
});

ProviderDetailPage.displayName = 'ProviderDetailPage';

// Default export for backward compatibility (used by SettingsContent)
type ProviderPageType = {
  mobile?: boolean;
};

const ProviderPage = (props: ProviderPageType) => {
  const { mobile } = props;

  // For mobile or when used via SettingsContent, use the old Page component
  // This is a fallback for non-router usage
  const OldPage = require('./(list)').default;
  return <OldPage mobile={mobile} />;
};

export default ProviderPage;

```
