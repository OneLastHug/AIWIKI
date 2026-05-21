# 文件：src/routes/(main)/agent/profile/features/store/index.ts

## 文件职责
这个文件位于 `src/routes/(main)/agent/profile/features/store`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { type StoreApiWithSelector } from '@lobechat/types';
import { subscribeWithSelector } from 'zustand/middleware';
import { shallow } from 'zustand/shallow';
import { createWithEqualityFn } from 'zustand/traditional';
import { createContext } from 'zustand-utils';
import { type Store } from './action';
import { store } from './action';
import { type State } from './initialState';
export type { PublicState, State } from './initialState';
export const createStore = (initState?: Partial<State>) =>
export const {
export { selectors } from './selectors';
```

## 主要对外内容
```text
export const createStore = (initState?: Partial<State>) =>
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
'use client';

import { type StoreApiWithSelector } from '@lobechat/types';
import { subscribeWithSelector } from 'zustand/middleware';
import { shallow } from 'zustand/shallow';
import { createWithEqualityFn } from 'zustand/traditional';
import { createContext } from 'zustand-utils';

import { type Store } from './action';
import { store } from './action';
import { type State } from './initialState';

export type { PublicState, State } from './initialState';

export const createStore = (initState?: Partial<State>) =>
  createWithEqualityFn(subscribeWithSelector(store(initState)), shallow);

export const {
  useStore: useProfileStore,
  useStoreApi,
  Provider,
} = createContext<StoreApiWithSelector<Store>>();

export { selectors } from './selectors';

```
