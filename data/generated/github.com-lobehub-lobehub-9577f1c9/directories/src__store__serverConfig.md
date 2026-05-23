# 目录：src/store/serverConfig

## 它负责什么

`src/store/serverConfig` 是前端侧“运行时服务器配置”的 Zustand store。它把服务端下发的全局配置、特性开关、公告信息，以及当前端侧运行环境标记统一收敛到一个可订阅的状态源里，供页面、功能组件、hooks 和部分非 React 流程读取。

这里的“server config”不是用户个人设置，也不是模型会话状态；它更接近应用级能力开关和部署级配置。例如：是否启用商业功能、是否启用邮件验证、是否启用视觉理解、是否启用 Klavis / LobeHub Skill、是否显示市场入口、是否处于移动端布局、是否有全局公告 `billboard` 等。业务代码通常不直接关心配置从哪里来，而是通过 `useServerConfigStore` 或 `serverConfigSelectors` 读取最终状态。

这个目录还有一个开发期能力：`featureFlagOverride`。它只在 `NODE_ENV === 'development'` 下生效，用于开发面板临时覆盖 feature flags，并把覆盖值持久化到本地存储。生产环境中这些 action 会直接返回，不改变状态。

## 直接子目录地图

该目录整体很小，只有一个直接子目录：

`src/store/serverConfig/slices/featureFlagOverride`：开发环境下的 feature flag 覆盖 slice。它负责保存原始 feature flags 快照、读取本地持久化覆盖项、合并覆盖值、清空覆盖值。配套文件包括 `action.ts`、`storage.ts`、`constants.ts` 和测试文件。它不是主配置拉取流程，而是叠加在主配置之上的开发辅助层。

顶层文件承担 store 主体职责：

`store.ts`：定义 `ServerConfigState`、`initialState`、store 创建函数、全局单例、Provider context，以及 `useServerConfigStore`、`getServerConfigStoreState` 等核心导出。

`action.ts`：定义主 action slice，核心是 `useInitServerConfig`。它通过 SWR 只请求一次全局配置，并在成功或失败后更新初始化状态。

`selectors.ts`：集中封装读取配置的 selector，例如 `enableBusinessFeatures`、`enableKlavis`、`enableVisualUnderstanding`、`isMobile` 等。

`Provider.tsx`：React Provider 封装，用于把初始 `featureFlags`、`serverConfig`、`isMobile`、`segmentVariants` 注入 store。

`index.ts`：对外聚合导出 selector、hook 和非 React 读取入口。

测试文件分布在顶层和 slice 内，用于覆盖 action、selector、store 创建及开发覆盖逻辑。

## 关键入口

最重要的入口是 `src/store/serverConfig/index.ts`。业务侧通常从这里导入 `useServerConfigStore`、`serverConfigSelectors`、`featureFlagsSelectors`、`getServerConfigStoreState`。这层导出让调用方不需要知道 store 内部拆成了哪些 action 和 slice。

React 组件树入口是 `src/store/serverConfig/Provider.tsx` 中的 `ServerConfigStoreProvider`。它接收服务端或上层运行时传入的初始配置，然后调用 `createServerConfigStore` 创建全局 store。这里会把环境变量风格的 feature flags 通过 `mapFeatureFlagsEnvToState` 映射成前端状态结构。

状态定义入口是 `src/store/serverConfig/store.ts`。它把 `initialState`、运行时注入状态、主配置 action、开发覆盖 action 合并成一个 `ServerConfigStore`。其中 `createServerConfigStore` 维护模块级单例，并在浏览器环境下暴露 `window.global_serverConfigStore`，同时调用 `expose('serverConfig', store)` 方便调试或全局检查。

配置拉取入口是 `src/store/serverConfig/action.ts` 的 `useInitServerConfig`。它使用 `useOnlyFetchOnceSWR`，通过 `globalService.getGlobalConfig()` 获取 `GlobalRuntimeConfig`，成功后写入 `billboard`、`featureFlags`、`serverConfig`，并把 `serverConfigInit` 置为 `true`；失败时也会把 `serverConfigInit` 置为 `true`，让依赖初始化完成的 UI 不会永久等待。

## 主流程位置

主流程可以按“注入初值、远程初始化、消费配置、开发覆盖”四段理解。

第一段在 `Provider.tsx` 和 `store.ts`。应用启动或某个测试包装组件挂载时，`ServerConfigStoreProvider` 调用 `createServerConfigStore`，把外部传入的 `serverConfig`、`featureFlags`、`isMobile`、`segmentVariants` 合并到默认状态。默认状态中 `featureFlags` 来自 `DEFAULT_FEATURE_FLAGS` 的映射结果，`serverConfig` 至少包含空的 `aiProvider` 和 `telemetry`，`serverConfigInit` 初始为 `false`。

第二段在 `action.ts`。页面或顶层初始化组件调用 `useInitServerConfig` 后，store 通过 `globalService.getGlobalConfig()` 获取真实运行时配置。成功后，服务端配置会覆盖默认值；失败后不会写入配置内容，但会标记初始化结束。根据当前片段推断，这个设计是为了让 UI 能区分“还没初始化”和“初始化完成但使用兜底配置”，依据是 `onError` 只设置 `serverConfigInit: true`，而不写入 `serverConfig`。

第三段在全仓调用处。大量页面和 features 通过 `useServerConfigStore(selector)` 读取配置，例如 home、onboarding、settings、chat input、skill store、mobile layout、dev panel 等。常见读取方式有两类：直接读 `s.featureFlags.xxx` 或 `s.isMobile`；或者通过 `serverConfigSelectors.xxx` 读取标准化布尔值。对于 React 组件外的流程，`src/store/chat/slices/aiChat/actions/streamingExecutor.ts` 使用 `getServerConfigStoreState()` 获取当前 store 状态，再套用 selector 判断能力开关。

第四段在 `slices/featureFlagOverride/action.ts`。开发环境下，`syncDevFlagOverrides` 会把当前 `featureFlags` 拷贝为 `_originalFeatureFlags`，再读取本地持久化覆盖项并合并到 `featureFlags`。`setFlagOverride` 改单个 flag，`resetFlagOverrides` 清空全部覆盖并恢复原始快照。这个流程服务于 `src/features/DevFeatureFlagPanel` 一类开发工具。

## 推荐阅读顺序

建议先读 `src/store/serverConfig/store.ts`，建立状态字段和 store 组合方式的整体模型，特别关注 `initialState`、`ServerConfigStore`、`createServerConfigStore`、`useServerConfigStore`。

第二步读 `src/store/serverConfig/Provider.tsx`，理解初始配置如何从 React Provider 注入进来，以及 `featureFlags` 为什么需要经过 `mapFeatureFlagsEnvToState`。

第三步读 `src/store/serverConfig/action.ts`，把握远程配置初始化的时机和结果字段，重点看 `useInitServerConfig` 的 `onSuccess` 与 `onError`。

第四步读 `src/store/serverConfig/selectors.ts`，了解业务侧推荐读取哪些配置，以及哪些字段有默认兜底值。

第五步再看 `src/store/serverConfig/slices/featureFlagOverride/action.ts` 和 `storage.ts`，把开发覆盖逻辑作为附加层理解，不要把它误认为生产配置来源。

最后可以按调用场景抽样阅读：配置门控 UI 看 `src/features/ChatInput/ActionBar/Tools/useControls.tsx`、视觉理解能力看 `src/hooks/useVisualMediaUploadAbility.ts`、非 React 消费看 `src/store/chat/slices/aiChat/actions/streamingExecutor.ts`、开发面板看 `src/features/DevFeatureFlagPanel`。

## 常见误区

不要把 `featureFlags` 和 `serverConfig` 混为一谈。`featureFlags` 更偏功能显隐和实验开关，`serverConfig` 更偏部署、认证、遥测、网关、上传、业务能力等全局运行配置。两者都存在同一个 store 里，但语义不同。

不要以为 `serverConfigInit` 为 `true` 就代表成功拿到了远程配置。`action.ts` 中失败分支也会设置 `serverConfigInit: true`，它表达的是“初始化流程已结束”，不是“远程配置有效”。

不要在普通业务组件里手写复杂读取逻辑。已有字段优先用 `serverConfigSelectors` 或 `featureFlagsSelectors`，因为 selector 中已经处理了不少布尔兜底，例如 `false` 默认值和 `telemetry.langfuse` 的空值保护。

不要把 `featureFlagOverride` 当作生产逻辑。它明确检查 `process.env.NODE_ENV === 'development'`，只用于开发面板临时验证功能开关。生产环境中相关 action 不会执行实际变更。

不要忽略 `createServerConfigStore` 的单例行为。这个 store 不是每次 Provider 渲染都新建一个独立实例；模块级 `store` 会确保全局只有一个。测试或特殊初始化场景如果需要干净实例，应关注 `initServerConfigStore` 与相关测试写法。

不要只搜索 `serverConfigSelectors` 来判断使用范围。仓库里很多调用会直接通过 `useServerConfigStore((s) => s.featureFlags.xxx)`、`useServerConfigStore((s) => s.isMobile)` 读取状态，所以分析影响面时需要同时搜索 `useServerConfigStore`、`featureFlagsSelectors` 和具体字段名。
