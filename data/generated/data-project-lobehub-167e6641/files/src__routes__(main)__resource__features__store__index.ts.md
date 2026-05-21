# 文件：src/routes/(main)/resource/features/store/index.ts

## 文件职责
这个文件位于 `src/routes/(main)/resource/features/store`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import type { SWRResponse } from 'swr';
import { subscribeWithSelector } from 'zustand/middleware';
import { shallow } from 'zustand/shallow';
import { createWithEqualityFn } from 'zustand/traditional';
import { useFileStore } from '@/store/file';
import type { FolderCrumb, Store } from './action';
import { store } from './action';
export type { State } from './initialState';
export const createStore = () =>
export const useResourceManagerStore = createStore();
export { selectors } from './selectors';
export const useResourceManagerFetchFolderBreadcrumb = (
```

## 主要对外内容
```text
export const createStore = () =>
export const useResourceManagerStore = createStore();
export const useResourceManagerFetchFolderBreadcrumb = (
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
'use client';

import type { SWRResponse } from 'swr';
import { subscribeWithSelector } from 'zustand/middleware';
import { shallow } from 'zustand/shallow';
import { createWithEqualityFn } from 'zustand/traditional';

import { useFileStore } from '@/store/file';

import type { FolderCrumb, Store } from './action';
import { store } from './action';

export type { State } from './initialState';

export const createStore = () =>
  createWithEqualityFn<Store>()(subscribeWithSelector(store()), shallow);

export const useResourceManagerStore = createStore();

export { selectors } from './selectors';

export const useResourceManagerFetchFolderBreadcrumb = (
  slug?: string | null,
): SWRResponse<FolderCrumb[]> => {
  return useFileStore((s) => s.useFetchFolderBreadcrumb)(slug);
};

```
