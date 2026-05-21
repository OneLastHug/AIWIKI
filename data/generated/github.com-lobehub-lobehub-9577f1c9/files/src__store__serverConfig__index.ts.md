# 文件：src/store/serverConfig/index.ts

## 它负责什么

`src/store/serverConfig/index.ts` 是 `serverConfig` Zustand store 模块的对外入口文件，也就是常见的 barrel export。它本身不实现状态、不拉取接口、不写业务逻辑，只负责把同目录下最常被外部使用的能力统一导出：

```ts
export { featureFlagsSelectors, serverConfigSelectors } from './selectors';
export { getServerConfigStoreState, useServerConfigStore } from './store';
```

从使用者视角看，外部组件不需要知道 `selectors.ts`、`store.ts` 的具体位置，只要从 `@/store/serverConfig` 引入即可。例如：

```ts
import { serverConfigSelectors, useServerConfigStore } from '@/store/serverConfig';
```

这个模块代表的是“服务端运行时配置”的客户端状态入口。它把后端或运行环境下发的配置，比如功能开关、商业功能开关、SSO 登录方式、视觉理解能力、遥测配置、移动端标记、公告信息等，暴露给前端页面、功能组件和部分非 React 执行逻辑读取。

需要注意：`index.ts` 只是入口门面，真正的核心在：

- `src/store/serverConfig/store.ts`
- `src/store/serverConfig/selectors.ts`
- `src/store/serverConfig/action.ts`
- `src/store/serverConfig/Provider.tsx`

## 关键组成

### `featureFlagsSelectors`

`index.ts` 从 `./selectors` 导出：

```ts
export const featureFlagsSelectors = (s: ServerConfigStore) => s.featureFlags;
```

它是一个简单 selector，直接返回 `ServerConfigStore` 中的 `featureFlags` 对象。

`featureFlags` 来源主要有两类：

1. 初始默认值：`DEFAULT_FEATURE_FLAGS` 经过 `mapFeatureFlagsEnvToState` 转成 store 状态。
2. 运行时服务端配置：`globalService.getGlobalConfig()` 返回的 `data.serverFeatureFlags`。

外部常见用法是一次性取出多个 feature flag：

```ts
const { showMarket, hideGitHub } = useServerConfigStore(featureFlagsSelectors);
```

这些开关会影响导航、市场入口、文档入口、上传能力、知识库、语音识别、Agent 自迭代等功能是否显示或启用。

### `serverConfigSelectors`

`index.ts` 也导出 `serverConfigSelectors`。它是一组围绕 `serverConfig` 字段封装的 selector：

```ts
export const serverConfigSelectors = {
  disableEmailPassword: (s) => s.serverConfig.disableEmailPassword || false,
  enableBusinessFeatures: (s) => s.serverConfig.enableBusinessFeatures || false,
  enableEmailVerification: (s) => s.serverConfig.enableEmailVerification || false,
  enableKlavis: (s) => s.serverConfig.enableKlavis || false,
  enableLobehubSkill: (s) => s.serverConfig.enableLobehubSkill || false,
  enableMagicLink: (s) => s.serverConfig.enableMagicLink || false,
  enableMarketTrustedClient: (s) => s.serverConfig.enableMarketTrustedClient || false,
  enableUploadFileToServer: (s) => s.serverConfig.enableUploadFileToServer,
  enableVisualUnderstanding: (s) => s.serverConfig.enableVisualUnderstanding || false,
  enabledTelemetryChat: (s) => s.serverConfig.telemetry.langfuse || false,
  isMobile: (s) => s.isMobile || false,
  oAuthSSOProviders: (s) => s.serverConfig.oAuthSSOProviders,
  visualUnderstanding: (s) => s.serverConfig.visualUnderstanding,
};
```

它的作用不是创造新数据，而是把 `serverConfig` 里的字段包装成稳定、语义明确、带默认值的读取函数。

例如：

```ts
const enableBusinessFeatures = useServerConfigStore(
  serverConfigSelectors.enableBusinessFeatures,
);
```

比直接写：

```ts
const enableBusinessFeatures = useServerConfigStore(
  (s) => s.serverConfig.enableBusinessFeatures || false,
);
```

更统一，也能减少各处默认值判断不一致的问题。

### `useServerConfigStore`

`index.ts` 从 `./store` 导出：

```ts
export const { useStore: useServerConfigStore, Provider } =
  createContext<StoreApiWithSelector<ServerConfigStore>>();
```

`useServerConfigStore` 是 React 组件中读取 `serverConfig` store 的主要 hook。它来自 `zustand-utils` 的 `createContext`，不是直接裸用 Zustand 的全局 hook。

常见用法有三类：

第一类，直接读状态字段：

```ts
const serverConfigInit = useServerConfigStore((s) => s.serverConfigInit);
const mobile = useServerConfigStore((s) => s.isMobile);
const billboard = useServerConfigStore((s) => s.billboard);
```

第二类，使用 selector：

```ts
const enableKlavis = useServerConfigStore(serverConfigSelectors.enableKlavis);
const featureFlags = useServerConfigStore(featureFlagsSelectors);
```

第三类，读取 action 并执行初始化：

```ts
const useFetchServerConfig = useServerConfigStore((s) => s.useInitServerConfig);
useFetchServerConfig();
```

### `getServerConfigStoreState`

`index.ts` 还导出：

```ts
export const getServerConfigStoreState = () => store?.getState();
```

这个函数用于 React 组件之外读取当前 store 状态。它依赖 `store.ts` 里的模块级变量：

```ts
let store: StoreApi<ServerConfigStore> | undefined;
```

也就是说，只有 `createServerConfigStore()` 被调用、store 实例创建之后，`getServerConfigStoreState()` 才能返回真实 state；否则可能返回 `undefined`。

调用方中可以看到非组件逻辑会用它，例如：

```ts
import { getServerConfigStoreState, serverConfigSelectors } from '@/store/serverConfig';
```

在 `src/store/chat/slices/aiChat/actions/streamingExecutor.ts` 中，它被用来读取视觉理解相关配置，决定聊天流式执行时是否启用特定能力。

根据当前片段推断：这个 API 是为了让 store 配置不仅能服务 React UI，也能服务底层执行器、工具包客户端等非 React 调用场景。

## 上下游关系

### 上游：配置从哪里来

`serverConfig` store 的上游主要有三层。

第一层是默认初始状态，定义在 `store.ts`：

```ts
const initialState: ServerConfigState = {
  _featureFlagOverrides: {},
  _originalFeatureFlags: null,
  billboard: null,
  featureFlags: mapFeatureFlagsEnvToState(DEFAULT_FEATURE_FLAGS),
  segmentVariants: '',
  serverConfig: { aiProvider: {}, telemetry: {} },
  serverConfigInit: false,
};
```

这里保证了应用在服务端配置尚未拉取完成前，也有一个可用的默认状态。

第二层是 `Provider.tsx` 注入的初始运行时参数：

```ts
createServerConfigStore({
  featureFlags: featureFlags ? mapFeatureFlagsEnvToState(featureFlags) : undefined,
  isMobile,
  segmentVariants,
  serverConfig,
})
```

这说明 `ServerConfigStoreProvider` 可以从外部接收：

- `featureFlags`
- `serverConfig`
- `isMobile`
- `segmentVariants`

然后作为 store 初始化参数。

第三层是异步接口拉取，位于 `action.ts`：

```ts
globalService.getGlobalConfig()
```

成功后写入：

```ts
{
  billboard: data.billboard ?? null,
  featureFlags: data.serverFeatureFlags,
  serverConfig: data.serverConfig,
  serverConfigInit: true,
}
```

失败时至少会设置：

```ts
{ serverConfigInit: true }
```

这意味着即使配置接口失败，应用也会把“初始化阶段”标记为完成，避免依赖 `serverConfigInit` 的界面一直等待。

### 下游：谁在用它

`@/store/serverConfig` 被大量 UI 和业务模块使用，典型下游包括：

- 首页布局：`src/routes/(main)/home/_layout/Footer/index.tsx`
- 首页输入区：`src/routes/(main)/home/features/InputArea/index.tsx`
- 用户面板：`src/features/User/UserPanel/useMenu.tsx`
- 设置页：`src/routes/(main)/settings/**`
- 聊天输入工具栏：`src/features/ChatInput/ActionBar/**`
- Agent 设置：`src/features/AgentSetting/**`
- 移动端布局：`src/routes/(mobile)/**`
- 开发 Feature Flag 面板：`src/features/DevFeatureFlagPanel/**`
- 聊天执行器：`src/store/chat/slices/aiChat/actions/streamingExecutor.ts`
- 内置工具包客户端：`packages/builtin-tool-lobe-agent/src/client/executor/index.ts`

这些下游读取的内容大体可以分成几类：

1. UI 展示开关：是否展示市场、文档、云服务推广、API Key 管理入口。
2. 业务能力开关：是否启用商业能力、Klavis、LobeHub Skill、文件上传、视觉理解。
3. 认证能力配置：是否禁用邮箱密码、是否启用 Magic Link、有哪些 OAuth SSO provider。
4. 运行环境信息：是否移动端、segment variant、agent gateway URL。
5. 调试和开发能力：feature flag 原始值、覆盖值、override 数量。

### 与 `store.ts` 的关系

`index.ts` 不导出 `createServerConfigStore`、`initServerConfigStore` 和 `Provider`，只导出：

```ts
getServerConfigStoreState
useServerConfigStore
```

这说明对普通业务代码来说，推荐只消费 store，而不是创建 store。

创建 store 的职责被限制在内部文件或 Provider 里：

- `Provider.tsx` 使用 `createServerConfigStore`
- 测试文件使用 `createServerConfigStore` / `initServerConfigStore`
- 外部业务代码通常只使用 `useServerConfigStore`

这是一个边界设计：业务层读取状态，初始化和创建逻辑留在 store 模块内部。

## 运行/调用流程

一个典型运行流程如下。

1. 应用外层挂载 `ServerConfigStoreProvider`

`Provider.tsx` 中的 `ServerConfigStoreProvider` 会创建或复用 `serverConfig` store：

```tsx
<Provider
  createStore={() =>
    createServerConfigStore({
      featureFlags,
      isMobile,
      segmentVariants,
      serverConfig,
    })
  }
>
  {children}
</Provider>
```

`createServerConfigStore` 内部保证单例：

```ts
if (!store) {
  store = createWithEqualityFn<ServerConfigStore>()(...)
}
```

所以在浏览器运行期，`serverConfig` store 通常只有一个实例。

2. 创建 store 时合并初始状态和运行时状态

`store.ts` 里通过：

```ts
...merge(initialState, runtimeState)
```

把默认值和 Provider 传入值合并。这样既有兜底默认配置，也能接收服务端渲染或入口层注入的配置。

同时它会挂载两个 action slice：

```ts
flattenActions([
  createServerConfigSlice(...params),
  createFeatureFlagOverrideSlice(...params),
])
```

其中 `createServerConfigSlice` 提供 `useInitServerConfig`，`createFeatureFlagOverrideSlice` 提供开发环境下 feature flag 覆盖能力。

3. 全局初始化阶段触发配置拉取

在 `src/layout/GlobalProvider/StoreInitialization.tsx` 中：

```ts
const useFetchServerConfig = useServerConfigStore((s) => s.useInitServerConfig);
useFetchServerConfig();
```

这里调用的是一个 SWR hook：

```ts
useOnlyFetchOnceSWR(
  FETCH_SERVER_CONFIG_KEY,
  () => globalService.getGlobalConfig(),
  ...
)
```

它的 key 是固定的 `FETCH_SERVER_CONFIG`，语义是全局配置只拉取一次。

4. 接口成功后写入 store

成功回调里写入：

```ts
billboard: data.billboard ?? null,
featureFlags: data.serverFeatureFlags,
serverConfig: data.serverConfig,
serverConfigInit: true,
```

从此之后，所有使用 `useServerConfigStore` 的组件都会读到更新后的配置，并按 selector 结果重新渲染。

5. 业务组件读取 selector

例如设置页或输入区会这样读：

```ts
const enableBusinessFeatures = useServerConfigStore(
  serverConfigSelectors.enableBusinessFeatures,
);
```

如果服务端配置中 `enableBusinessFeatures` 为真，对应商业功能入口、限制逻辑或 UI 组件就会启用。

6. 非 React 逻辑读取当前状态

对于不在 React 组件树里的代码，不能调用 hook，于是使用：

```ts
const serverConfigState = getServerConfigStoreState();
```

然后配合：

```ts
serverConfigSelectors.enableVisualUnderstanding(serverConfigState)
```

读取配置。这里要注意 `getServerConfigStoreState()` 可能返回 `undefined`，调用方通常需要先判断。

## 小白阅读顺序

1. 先看 `src/store/serverConfig/index.ts`

这个文件只有两行导出。先理解它是入口文件，不是实现文件。看到从 `@/store/serverConfig` 引入的地方，实际拿到的是 `selectors.ts` 和 `store.ts` 里的东西。

2. 再看 `src/store/serverConfig/store.ts`

重点看四块：

- `ServerConfigState`：这个 store 存哪些状态。
- `initialState`：默认值是什么。
- `createServerConfigStore`：store 如何创建、为什么是单例。
- `getServerConfigStoreState` / `useServerConfigStore`：React 内外分别怎么读取。

特别留意这些字段：

```ts
featureFlags
serverConfig
serverConfigInit
isMobile
billboard
_originalFeatureFlags
_featureFlagOverrides
```

3. 再看 `src/store/serverConfig/action.ts`

重点看 `useInitServerConfig`。它解释了配置从后端怎么进入 store：

```ts
globalService.getGlobalConfig()
```

成功时写入配置，失败时只标记初始化完成。

4. 再看 `src/store/serverConfig/selectors.ts`

理解为什么业务组件一般不用直接读 `s.serverConfig.xxx`，而是使用 `serverConfigSelectors.xxx`。selector 统一了默认值，也让调用点更语义化。

5. 再看 `src/store/serverConfig/Provider.tsx`

这个文件解释 store 如何被注入 React 组件树。注意它会把外部传入的 `featureFlags` 转换成 store state：

```ts
mapFeatureFlagsEnvToState(featureFlags)
```

6. 最后看调用方

推荐选两个调用方看：

- `src/layout/GlobalProvider/StoreInitialization.tsx`：理解初始化流程。
- 任意业务组件，例如 `src/features/User/UserPanel/useMenu.tsx` 或 `src/features/ChatInput/ActionBar/Tools/useControls.tsx`：理解业务如何消费配置。

## 常见误区

### 误区一：以为 `index.ts` 里有业务逻辑

`src/store/serverConfig/index.ts` 只是导出入口。真正逻辑在 `store.ts`、`action.ts`、`selectors.ts`。读这个文件时不要停在两行 export 上，要顺着 export 找实现。

### 误区二：把 `featureFlags` 和 `serverConfig` 混为一谈

它们都属于“服务端/环境控制前端行为”的配置，但语义不同。

`featureFlags` 更像产品功能开关集合，例如是否展示市场、是否启用某些实验能力。

`serverConfig` 更像服务端运行配置集合，例如：

- `enableBusinessFeatures`
- `enableKlavis`
- `enableLobehubSkill`
- `disableEmailPassword`
- `oAuthSSOProviders`
- `telemetry`
- `visualUnderstanding`

两者都在同一个 store 中，但读取入口不同：

```ts
useServerConfigStore(featureFlagsSelectors)
useServerConfigStore(serverConfigSelectors.enableBusinessFeatures)
```

### 误区三：以为 `serverConfigInit` 代表配置一定拉取成功

不是。`action.ts` 中失败回调也会设置：

```ts
serverConfigInit: true
```

所以 `serverConfigInit` 更准确的含义是“初始化流程已经结束”，不是“服务端配置成功获取”。如果要判断某个能力是否可用，仍然应该读取具体配置字段或 selector。

### 误区四：在 React 组件外使用 `useServerConfigStore`

`useServerConfigStore` 是 hook，适合 React 组件或自定义 hook 内使用。

在非 React 逻辑中，例如执行器、工具包客户端，应使用：

```ts
getServerConfigStoreState()
```

但它可能返回 `undefined`，因为 store 可能尚未创建。调用方需要判空。

### 误区五：绕过 selector 直接读深层字段

直接写：

```ts
useServerConfigStore((s) => s.serverConfig.enableBusinessFeatures)
```

虽然能工作，但容易遗漏默认值处理。项目里已经提供了：

```ts
serverConfigSelectors.enableBusinessFeatures
```

优先使用 selector 能保持行为一致，也方便后续修改字段来源或默认策略。

### 误区六：以为 `createServerConfigStore` 每次都会创建新 store

`store.ts` 里有模块级变量：

```ts
let store: StoreApi<ServerConfigStore> | undefined;
```

`createServerConfigStore` 只有在 `store` 不存在时才创建。后续调用会复用同一个实例。这对全局配置类 store 很重要，避免多个 Provider 或重复初始化导致状态分裂。

测试场景如果需要隔离实例，会使用 `initServerConfigStore` 或测试前重新创建环境，而普通业务代码不应该手动创建新 store。

### 误区七：忽略开发环境 feature flag override

`ServerConfigState` 中有两个看起来“内部”的字段：

```ts
_featureFlagOverrides
_originalFeatureFlags
```

它们服务于开发 Feature Flag 面板，用来保存原始服务端开关和本地覆盖值。普通业务代码通常不需要碰它们，但看到 `src/features/DevFeatureFlagPanel/**` 使用这些字段时，不要误认为它们是线上业务配置的一部分。
