# 文件：src/spa/router/popupRouter.config.tsx

## 文件职责
这个文件位于 `src/spa/router`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import type { RouteObject } from 'react-router-dom';
import PopupLayout from '@/routes/(popup)/_layout';
import PopupAgentQuickPage from '@/routes/(popup)/agent/[aid]';
import PopupAgentTopicPage from '@/routes/(popup)/agent/[aid]/[tid]';
import PopupGroupTopicPage from '@/routes/(popup)/group/[gid]/[tid]';
import { ErrorBoundary, redirectElement } from '@/utils/router';
export const popupRoutes: RouteObject[] = [
```

## 主要对外内容
```text
export const popupRoutes: RouteObject[] = [
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
'use client';

import type { RouteObject } from 'react-router-dom';

import PopupLayout from '@/routes/(popup)/_layout';
import PopupAgentQuickPage from '@/routes/(popup)/agent/[aid]';
import PopupAgentTopicPage from '@/routes/(popup)/agent/[aid]/[tid]';
import PopupGroupTopicPage from '@/routes/(popup)/group/[gid]/[tid]';
import { ErrorBoundary, redirectElement } from '@/utils/router';

// Popup router configuration — dedicated SPA entry for single-topic windows.
// Desktop-only; no sidebar, no portal, hosts a single conversation per window.
export const popupRoutes: RouteObject[] = [
  {
    children: [
      {
        element: <PopupAgentTopicPage />,
        path: 'agent/:aid/:tid',
      },
      {
        element: <PopupAgentQuickPage />,
        path: 'agent/:aid',
      },
      {
        element: <PopupGroupTopicPage />,
        path: 'group/:gid/:tid',
      },
      {
        element: redirectElement('/popup'),
        path: '*',
      },
    ],
    element: <PopupLayout />,
    errorElement: <ErrorBoundary resetPath="/popup" />,
    path: '/popup',
  },
];

```
