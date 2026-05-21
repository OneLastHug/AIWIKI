# 目录：src/store/serverConfig

## 它负责什么

`src/store/serverConfig` 是前端全局“服务端运行时配置”的 Zustand store。它把后端返回的全局配置、功能开关、公告信息、移动端标记等运行时数据集中保存起来，供客户端页面、组件、鉴权入口、功能开关判断等场景读取。

这个目录的核心职责可以概括为三类：

1. 初始化服务端配置：通过 `globalService.getGlobalConfig()` 拉取 `GlobalRuntimeConfig`，写入 `serverConfig`、`featureFlags`、`billboard` 等状态。
2. 暴露配置选择器：通过 `serverConfigSelectors` 和 `featureFlagsSelectors` 给业务代码读取配置，避免组件直接了解完整 store 结构。
3. 支持开发环境功能开关覆写：在 `NODE_ENV === 'development'` 时，允许开发者临时覆盖 `featureFlags`，并持久化到 `localStorage`。

它不是普通业务 store，而是应用启动阶段依赖的基础配置层。很多“某个功能是否显示”“某种登录方式是否启用”“当前是否移动端”等判断，都应该从这里读取。

## 关键组成

### `index.ts`

`index.ts` 是目录出口，只导出两组内容：

```ts
export { featureFlagsSelectors, serverConfigSelectors } from './selectors';
export { getServerConfigStoreState, useServerConfigStore } from './store';
```

这说明外部主要通过两种方式使用本目录：

- 用 `useServerConfigStore` 订阅 Zustand 状态。
- 用 `serverConfigSelectors` / `featureFlagsSelectors` 读取配置派生值。

它没有导出 `Provider`，说明正常业务代码不应该随意创建或替换这个 store；Provider 的挂载通常在应用根部完成。

### `store.ts`

`store.ts` 是核心状态定义和 store 创建入口。

关键状态包括：

```ts
interface ServerConfigState {
  _featureFlagOverrides: Partial<IFeatureFlagsState>;
  _originalFeatureFlags: IFeatureFlagsState | null;
  billboard?: GlobalBillboard | null;
  featureFlags: IFeatureFlagsState;
  isMobile?: boolean;
  segmentVariants?: string;
  serverConfig: GlobalServerConfig;
  serverConfigInit: boolean;
}
```

其中：

- `serverConfig`：服务端运行时配置，类型是 `GlobalServerConfig`。
- `featureFlags`：功能开关状态，来自 `@/config/featureFlags`。
- `billboard`：全局公告或横幅信息。
- `isMobile`：当前运行环境是否移动端。
- `segmentVariants`：可能用于分流、实验或变体标识。
- `serverConfigInit`：服务端配置是否已经初始化完成。
- `_featureFlagOverrides`、`_originalFeatureFlags`：开发环境功能开关覆写专用状态。

初始值里 `featureFlags` 由 `mapFeatureFlagsEnvToState(DEFAULT_FEATURE_FLAGS)` 生成，说明即使服务端配置还没拉取回来，前端也有一套默认功能开关兜底。

`ServerConfigStore` 组合了三部分：

```ts
export interface ServerConfigStore
  extends ServerConfigState, ServerConfigAction, FeatureFlagOverrideAction {}
```

也就是：

- 状态字段：`ServerConfigState`
- 服务端配置初始化 action：`ServerConfigAction`
- 开发环境 feature flag 覆写 action：`FeatureFlagOverrideAction`

该 store 使用了 LobeHub 当前的 class-based action 组织方式：

```ts
...flattenActions<ServerConfigStoreAction>([
  createServerConfigSlice(...params),
  createFeatureFlagOverrideSlice(...params),
])
```

这里的 `flattenActions` 用来把 class 实例上的方法展开成 Zustand store 可直接调用的 action。

另外，`createServerConfigStore` 使用模块级变量 `store` 保证单例：

```ts
let store: StoreApi<ServerConfigStore> | undefined;
```

第一次创建后会：

- 赋值给 `window.global_serverConfigStore`
- 通过 `expose('serverConfig', store)` 暴露给调试工具或全局调试通道
- 接入 `createDevtools('serverConfig')`

### `Provider.tsx`

`Provider.tsx` 提供 React 入口组件 `ServerConfigStoreProvider`。

它接收：

```ts
interface GlobalStoreProviderProps {
  children: ReactNode;
  featureFlags?: Partial<IFeatureFlags>;
  isMobile?: boolean;
  segmentVariants?: string;
  serverConfig?: GlobalServerConfig;
}
```

然后调用 `createServerConfigStore` 注入初始状态：

```ts
createServerConfigStore({
  featureFlags: featureFlags ? mapFeatureFlagsEnvToState(featureFlags) : undefined,
  isMobile,
  segmentVariants,
  serverConfig,
})
```

这说明 server config store 的初始化数据可以来自页面外层，例如 SSR 注入、HTML 模板注入、运行环境判断或路由入口传入。后续再由 `useInitServerConfig` 拉取最新的全局配置。

注意：`Provider.tsx` 是 `'use client'` 文件，只能在客户端 React 环境中运行。

### `action.ts`

`action.ts` 定义主 action：`useInitServerConfig`。

它内部使用：

```ts
useOnlyFetchOnceSWR<GlobalRuntimeConfig>(
  FETCH_SERVER_CONFIG_KEY,
  () => globalService.getGlobalConfig(),
  ...
)
```

含义是：通过 SWR 拉取全局配置，并且同一个 key 只取一次，避免多组件重复请求。

成功时写入：

```ts
{
  billboard: data.billboard ?? null,
  featureFlags: data.serverFeatureFlags,
  serverConfig: data.serverConfig,
  serverConfigInit: true,
}
```

失败时只设置：

```ts
{ serverConfigInit: true }
```

这个失败处理很重要：即使后端配置请求失败，应用也不会一直卡在“配置未初始化”的状态。它会使用 `initialState` 或 Provider 传入的兜底配置继续运行。

`ServerConfigActionImpl` 是 class-based action：

```ts
export class ServerConfigActionImpl {
  readonly #set: Setter;

  useInitServerConfig = (): SWRResponse<GlobalRuntimeConfig> => { ... };
}
```

它只需要 `set`，不需要读取当前状态，所以构造函数里 `void get`。

### `selectors.ts`

`selectors.ts` 是读取层，集中提供 server config 的常用派生值。

例如：

```ts
disableEmailPassword: (s) => s.serverConfig.disableEmailPassword || false
enableEmailVerification: (s) => s.serverConfig.enableEmailVerification || false
enableKlavis: (s) => s.serverConfig.enableKlavis || false
enabledTelemetryChat: (s) => s.serverConfig.telemetry.langfuse || false
isMobile: (s) => s.isMobile || false
```

这些 selector 做了默认值兜底，避免业务组件到处写 `?.` 或 `|| false`。

其中有些 selector 返回布尔值，有些直接返回配置字段：

```ts
oAuthSSOProviders: (s) => s.serverConfig.oAuthSSOProviders
visualUnderstanding: (s) => s.serverConfig.visualUnderstanding
enableUploadFileToServer: (s) => s.serverConfig.enableUploadFileToServer
```

这表示对应字段可能本身不是简单布尔值，或者业务方需要区分 `undefined` 与具体配置值。

`featureFlagsSelectors` 则直接返回完整 `featureFlags`：

```ts
export const featureFlagsSelectors = (s: ServerConfigStore) => s.featureFlags;
```

### `slices/featureFlagOverride`

这是开发环境专用的功能开关覆写 slice。

包含三个文件：

- `action.ts`：覆写逻辑。
- `constants.ts`：localStorage key 和 schema version。
- `storage.ts`：读写 localStorage，并做校验和容错。

核心 action 有三个：

```ts
syncDevFlagOverrides()
setFlagOverride(key, value)
resetFlagOverrides()
```

它们都先判断：

```ts
process.env.NODE_ENV === 'development'
```

所以生产环境不会生效。

`syncDevFlagOverrides` 的逻辑是：

1. 读取当前 `featureFlags`，复制为 `_originalFeatureFlags`。
2. 从 `localStorage` 读取已持久化的覆写值。
3. 只保留当前已知 key 且值为 boolean 的覆写项。
4. 合并原始功能开关和覆写值。
5. 写回 Zustand store。

`setFlagOverride` 用于单个开关的覆盖：

- `value === undefined`：删除覆写项，恢复原始值。
- `value === true | false`：写入覆写项，并更新当前 `featureFlags`。

`resetFlagOverrides` 清空所有覆写，并恢复 `_originalFeatureFlags`。

`storage.ts` 还引入了 `DEV_FLAG_OVERRIDE_SCHEMA_VERSION`。如果持久化数据版本不匹配，会删除旧数据，避免旧结构污染新逻辑。

## 上下游关系

上游依赖主要有：

- `@/services/global`：提供 `globalService.getGlobalConfig()`，这是服务端运行时配置的真实来源。
- `@/types/serverConfig`：定义 `GlobalRuntimeConfig`、`GlobalServerConfig`、`GlobalBillboard` 等类型。
- `@/config/featureFlags`：提供 `DEFAULT_FEATURE_FLAGS`、`mapFeatureFlagsEnvToState`、`IFeatureFlagsState`。
- `@/libs/swr`：提供 `useOnlyFetchOnceSWR`，控制配置请求只初始化一次。
- `@/store/middleware/createDevtools`：接入 Zustand devtools。
- `@/store/middleware/expose`：把 store 暴露到调试通道。
- `../utils/flattenActions`：把 class action 实例展开到 store。

下游使用方式主要有两类。

第一类是 Provider 挂载链路。根据当前片段推断，应用根部会渲染 `ServerConfigStoreProvider`，把初始的 `serverConfig`、`featureFlags`、`isMobile` 等注入 Zustand context。依据是 `Provider.tsx` 专门封装了 `createServerConfigStore`，并且 `store.ts` 使用 `zustand-utils` 的 `createContext` 暴露 `Provider` / `useStore`。

第二类是业务组件读取链路。业务代码会从 `src/store/serverConfig` 导入：

```ts
useServerConfigStore
serverConfigSelectors
featureFlagsSelectors
```

然后通过 selector 判断功能是否启用，例如邮箱密码登录、Magic Link、OAuth SSO、文件上传、视觉理解、Telemetry、商业功能等。

因为本次只读取了目标目录和必要入口，未展开调用方文件；具体哪些页面消费这些 selector，需要进一步用 `rg "serverConfigSelectors"` 或 `rg "useServerConfigStore"` 查找。

## 运行/调用流程

典型流程如下：

1. 应用客户端入口渲染 `ServerConfigStoreProvider`。
2. Provider 接收外部注入的 `serverConfig`、`featureFlags`、`isMobile`、`segmentVariants`。
3. Provider 调用 `createServerConfigStore` 创建或复用单例 Zustand store。
4. `store.ts` 用 `initialState` 和运行时 `initState` 做 `merge`，得到初始状态。
5. `flattenActions` 合并 `createServerConfigSlice` 和 `createFeatureFlagOverrideSlice` 产生的 action。
6. 某个根组件或初始化组件调用 `useInitServerConfig()`。
7. `useInitServerConfig` 通过 `globalService.getGlobalConfig()` 请求后端全局配置。
8. 请求成功后写入 `billboard`、`featureFlags`、`serverConfig`，并把 `serverConfigInit` 设为 `true`。
9. 请求失败时也把 `serverConfigInit` 设为 `true`，让应用继续使用默认值或注入值运行。
10. 业务组件通过 `useServerConfigStore(serverConfigSelectors.xxx)` 读取配置。
11. 开发环境中，如果调用 `syncDevFlagOverrides`，会把 localStorage 中的功能开关覆写合并进 `featureFlags`。
12. 开发者通过 `setFlagOverride` 修改某个 flag 时，store 和 localStorage 同步更新。
13. 调用 `resetFlagOverrides` 时，清除 localStorage 并恢复原始服务端 feature flags。

这个流程里最重要的状态位是 `serverConfigInit`。它代表“初始化流程已经结束”，不等价于“服务端配置一定请求成功”。失败时它也会变成 `true`。

## 小白阅读顺序

建议按下面顺序阅读：

1. 先看 `index.ts`  
   了解这个目录对外只暴露 selector 和 store hook，不直接暴露内部实现。

2. 再看 `store.ts`  
   重点看 `ServerConfigState`、`initialState`、`ServerConfigStore`、`createServerConfigStore`。这一步能理解这里保存了哪些全局配置，以及为什么是单例 store。

3. 再看 `Provider.tsx`  
   理解服务端或入口层传入的初始配置如何进入 Zustand store。

4. 接着看 `action.ts`  
   重点看 `useInitServerConfig`，这是运行时从后端刷新配置的主流程。

5. 然后看 `selectors.ts`  
   了解业务代码应该通过哪些 selector 读取配置，而不是直接访问复杂对象。

6. 最后看 `slices/featureFlagOverride/action.ts`  
   这是开发工具性质的扩展逻辑。先理解主 store，再看它如何覆写 `featureFlags` 会更容易。

7. 有余力再看 `storage.ts` 和 `constants.ts`  
   理解开发环境覆写值如何持久化、如何做版本校验、如何丢弃非法 key。

## 常见误区

1. 把 `serverConfigInit` 理解成“配置请求成功”  
   实际上它只表示初始化流程结束。请求失败时也会设为 `true`，应用会继续使用兜底配置。

2. 直接在组件里读取 `s.serverConfig.xxx`  
   更推荐使用 `serverConfigSelectors`。selector 已经处理了默认值，能减少空值和布尔兜底问题。

3. 以为 `featureFlags` 只来自服务端  
   初始状态来自 `DEFAULT_FEATURE_FLAGS`，Provider 也可以注入 `featureFlags`，运行时请求成功后会用 `data.serverFeatureFlags` 覆盖。开发环境还可能被 `featureFlagOverride` 覆写。

4. 以为开发环境覆写会影响生产  
   `featureFlagOverride` 的所有入口都检查 `NODE_ENV === 'development'`，生产环境不会读取或写入这些覆写。

5. 忽略 `_originalFeatureFlags` 的作用  
   它不是业务配置，而是开发环境恢复默认值的快照。`setFlagOverride(key, undefined)` 和 `resetFlagOverrides()` 都依赖它恢复原始状态。

6. 以为 `createServerConfigStore` 每次都会创建新 store  
   它内部有模块级 `store` 单例。第一次创建后，后续调用会复用已有实例。这对全局配置 store 很重要，避免不同组件读到不同配置状态。

7. 把 `Provider.tsx` 当成服务端组件使用  
   文件顶部有 `'use client'`，并且依赖 Zustand context 和浏览器侧 store。它属于客户端 Provider。

8. 误用 `enableUploadFileToServer` 这类 selector 的返回值  
   有些 selector 用 `|| false` 强制返回布尔值，有些直接返回原始字段。阅读 `selectors.ts` 时要注意返回值是否可能为 `undefined` 或配置对象。

9. 忽略 localStorage 数据校验  
   `storage.ts` 不会盲信持久化数据。它会检查 schema version、known keys 和 boolean 类型，非法数据会被丢弃或忽略。

10. 在业务代码里调用 `setFlagOverride`  
   这个 action 是 dev panel 或开发调试场景使用的，不应该成为正式业务流程的一部分。
