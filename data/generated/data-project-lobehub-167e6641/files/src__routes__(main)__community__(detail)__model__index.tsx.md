# 文件：src/routes/(main)/community/(detail)/model/index.tsx

## 文件职责
这个文件位于 `src/routes/(main)/community/(detail)/model`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { Flexbox } from '@lobehub/ui';
import { memo } from 'react';
import { useParams } from 'react-router-dom';
import { useDiscoverStore } from '@/store/discover';
import NotFound from '../components/NotFound';
import { DetailProvider } from './features/DetailProvider';
import Details from './features/Details';
import Header from './features/Header';
import Loading from './loading';
export const MobileModelPage = memo<{ mobile?: boolean }>(() => {
export default ModelDetailPage;
```

## 主要对外内容
```text
interface ModelDetailPageProps {
const ModelDetailPage = memo<ModelDetailPageProps>(({ mobile }) => {
export const MobileModelPage = memo<{ mobile?: boolean }>(() => {
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
import { useParams } from 'react-router-dom';

import { useDiscoverStore } from '@/store/discover';

import NotFound from '../components/NotFound';
import { DetailProvider } from './features/DetailProvider';
import Details from './features/Details';
import Header from './features/Header';
import Loading from './loading';

interface ModelDetailPageProps {
  mobile?: boolean;
}

const ModelDetailPage = memo<ModelDetailPageProps>(({ mobile }) => {
  const params = useParams<{ slug: string }>();
  const identifier = decodeURIComponent(params.slug ?? '');

  const useModelDetail = useDiscoverStore((s) => s.useModelDetail);
  const { data, isLoading } = useModelDetail({ identifier });

  if (isLoading) return <Loading />;
  if (!data) return <NotFound />;

  return (
    <DetailProvider config={data}>
      <Flexbox gap={16}>
        <Header mobile={mobile} />
        <Details mobile={mobile} />
      </Flexbox>
    </DetailProvider>
  );
});

export const MobileModelPage = memo<{ mobile?: boolean }>(() => {
  return <ModelDetailPage mobile={true} />;
});

export default ModelDetailPage;

```
