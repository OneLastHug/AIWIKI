# 文件：src/store/serverConfig/store.ts

## 文件职责
这个文件位于 `src/store/serverConfig`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { type StoreApiWithSelector } from '@lobechat/types';
import { type StoreApi } from 'zustand';
import { shallow } from 'zustand/shallow';
import { createWithEqualityFn } from 'zustand/traditional';
import { type StateCreator } from 'zustand/vanilla';
import { createContext } from 'zustand-utils';
import { type IFeatureFlagsState } from '@/config/featureFlags';
import { DEFAULT_FEATURE_FLAGS, mapFeatureFlagsEnvToState } from '@/config/featureFlags';
import { createDevtools } from '@/store/middleware/createDevtools';
import { expose } from '@/store/middleware/expose';
import { type GlobalBillboard, type GlobalServerConfig } from '@/types/serverConfig';
import { merge } from '@/utils/merge';
import { flattenActions } from '../utils/flattenActions';
import { type ServerConfigAction } from './action';
import { createServerConfigSlice } from './action';
import {
export interface ServerConfigStore
export const initServerConfigStore = (initState: Partial<ServerConfigStore>) =>
export const createServerConfigStore = (initState?: Partial<ServerConfigStore>) => {
export const getServerConfigStoreState = () => store?.getState();
export const { useStore: useServerConfigStore, Provider } =
```

## 主要对外内容
```text
interface ServerConfigState {
const initialState: ServerConfigState = {
export interface ServerConfigStore
type ServerConfigStoreAction = ServerConfigAction & FeatureFlagOverrideAction;
type CreateStore = (
const createStore: CreateStore =
const devtools = createDevtools('serverConfig');
export const initServerConfigStore = (initState: Partial<ServerConfigStore>) =>
export const createServerConfigStore = (initState?: Partial<ServerConfigStore>) => {
export const getServerConfigStoreState = () => store?.getState();
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { type StoreApiWithSelector } from '@lobechat/types';
import { type StoreApi } from 'zustand';
import { shallow } from 'zustand/shallow';
import { createWithEqualityFn } from 'zustand/traditional';
import { type StateCreator } from 'zustand/vanilla';
import { createContext } from 'zustand-utils';

import { type IFeatureFlagsState } from '@/config/featureFlags';
import { DEFAULT_FEATURE_FLAGS, mapFeatureFlagsEnvToState } from '@/config/featureFlags';
import { createDevtools } from '@/store/middleware/createDevtools';
import { expose } from '@/store/middleware/expose';
import { type GlobalBillboard, type GlobalServerConfig } from '@/types/serverConfig';
import { merge } from '@/utils/merge';

import { flattenActions } from '../utils/flattenActions';
import { type ServerConfigAction } from './action';
import { createServerConfigSlice } from './action';
import {
  createFeatureFlagOverrideSlice,
  type FeatureFlagOverrideAction,
} from './slices/featureFlagOverride/action';

interface ServerConfigState {
  /** dev-only: pending overrides keyed by mapped flag name; empty in prod */
  _featureFlagOverrides: Partial<IFeatureFlagsState>;
  /** dev-only: snapshot of server-provided featureFlags before any override; null until hydrated */
  _originalFeatureFlags: IFeatureFlagsState | null;
  billboard?: GlobalBillboard | null;
  featureFlags: IFeatureFlagsState;
  isMobile?: boolean;
  segmentVariants?: string;
  serverConfig: GlobalServerConfig;
  serverConfigInit: boolean;
}

const initialState: ServerConfigState = {
  _featureFlagOverrides: {},
  _originalFeatureFlags: null,
  billboard: null,
  featureFlags: mapFeatureFlagsEnvToState(DEFAULT_FEATURE_FLAGS),
  segmentVariants: '',
  serverConfig: { aiProvider: {}, telemetry: {} },
  serverConfigInit: false,
};

//  ===============  Aggregate createStoreFn ============ //

export interface ServerConfigStore
  extends ServerConfigState, ServerConfigAction, FeatureFlagOverrideAction {}

type ServerConfigStoreAction = ServerConfigAction & FeatureFlagOverrideAction;

type CreateStore = (
  initState: Partial<ServerConfigStore>,
) => StateCreator<ServerConfigStore, [['zustand/devtools', never]]>;

const createStore: CreateStore =
  (runtimeState: any) =>
  (...params) => ({
    ...merge(initialState, runtimeState),
    ...flattenActions<ServerConfigStoreAction>([
      createServerConfigSlice(...params),
      createFeatureFlagOverrideSlice(...params),
    ]),
  });

//  ===============  Implement useStore ============ //

let store: StoreApi<ServerConfigStore> | undefined;

declare global {
  interface Window {
    global_serverConfigStore: StoreApi<ServerConfigStore>;
  }
}

const devtools = createDevtools('serverConfig');

export const initServerConfigStore = (initState: Partial<ServerConfigStore>) =>
  createWithEqualityFn<ServerConfigStore>()(devtools(createStore(initState || {})), shallow);

export const createServerConfigStore = (initState?: Partial<ServerConfigStore>) => {
  // make sure there is only one store
  if (!store) {
    store = createWithEqualityFn<ServerConfigStore>()(
      devtools(createStore(initState || {})),
      shallow,
    );

    if (typeof window !== 'undefined') {
      window.global_serverConfigStore = store;
    }

    expose('serverConfig', store);
  }

  return store;
};

export const getServerConfigStoreState = () => store?.getState();

export const { useStore: useServerConfigStore, Provider } =
  createContext<StoreApiWithSelector<ServerConfigStore>>();

```
