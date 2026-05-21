# 目录：src/routes/(main)/settings/provider/features

## 它负责什么

`src/routes/(main)/settings/provider/features` 是“模型服务商设置页”的业务 UI 目录，核心职责是让用户在 `/settings/provider/:id` 这一类页面里完成三件事：

1. 配置某个 AI Provider 的连接参数，比如 `apiKey`、`baseURL`、是否启用浏览器端请求、是否启用 Responses API。
2. 查看、搜索、启用、禁用、排序、编辑或新增该 Provider 下的模型列表。
3. 新增或更新自定义 Provider，并把用户填写的 SDK 类型、名称、描述、Logo、代理地址、密钥等信息写入 `aiInfra` store。

从 SPA 目录规范看，这个目录位于 `src/routes/.../features` 下，属于历史结构中的“route 内业务组件”。当前项目的新约定更倾向于把复杂业务 UI 放到 `src/features/<Domain>/`，route 目录只保留薄页面入口。因此阅读时要把它当成“尚未迁移出去的 Provider 设置业务模块”，而不是普通的 route segment 文件。

## 关键组成

这个目录可以分成三组：Provider 创建、Provider 配置、模型列表。

`CreateNewProvider/index.tsx` 负责新增自定义 Provider。它导出默认组件 `CreateNewProvider`，接收 `open` 和 `onClose`，内部用 `FormModal` 渲染表单。表单分为基础信息和配置两组：基础信息包括 `id`、`name`、`description`、`logo`；配置项包括 `settings.sdkType`、`keyVaults.baseURL`、`keyVaults.apiKey`。提交时会调用 `useAiInfraStore` 里的 `createNewAiProvider`，并通过 `normalizeProviderSettings` 补齐或清理 `supportResponsesApi`。创建成功后跳转到 `/settings/provider/${values.id}`，并提示 `createSuccess`。

`customProviderSdkOptions.ts` 是自定义 Provider 支持的 SDK 类型选项表，包括 `openai`、`azure`、`anthropic`、`google`、`cloudflare`、`qwen`、`volcengine`、`ollama`、`router`。它使用 `satisfies { label: string; value: AiProviderSDKType }[]` 保证选项值符合 `AiProviderSDKType`。

`providerSettings.ts` 是配置归一化工具。`isResponsesApiSupportedSdkType` 判断某个 SDK 类型是否支持 Responses API，目前支持 `openai` 和 `router`。`normalizeProviderSettings` 会把 `previousSettings` 和 `nextSettings` 合并；如果 SDK 类型支持 Responses API，就强制设置 `supportResponsesApi: true`；否则删除 `supportResponsesApi`，并在没有剩余配置时返回 `undefined`。这个工具同时被新增 Provider 和更新 Provider 信息相关逻辑复用。

`ProviderConfig/index.tsx` 是 Provider 参数配置主组件，默认导出 `ProviderConfig`，并导出 `ProviderConfigProps` 类型。它读取 `AiProviderDetailItem` 相关字段，组合出表单项：API Key、Endpoint、Responses API 开关、浏览器端请求开关、连接检查器、安全提示等。它依赖 `useAiInfraStore` 获取 provider detail、运行时配置、启用状态、更新状态，并调用 `updateAiProviderConfig` 保存变更。表单值变化会通过 `useDebounceFn` 延迟 500ms 写回 store，避免频繁请求。连接检查前会先保存当前表单值，检查期间用 `isCheckingConnection` 阻止重复更新。

`ProviderConfig/Checker.tsx` 是连接检查功能，`ProviderConfig/EnableSwitch.tsx` 是 Provider 启用开关，`ProviderConfig/OAuthDeviceFlowAuth/*` 处理 OAuth Device Flow 授权，`ProviderConfig/UpdateProviderInfo/*` 处理自定义 Provider 信息更新。根据当前片段推断，`ProviderConfig/index.tsx` 是这些子能力的聚合入口。

`ModelList/index.tsx` 是模型列表主入口。它接收 Provider `id` 和若干展示配置，比如 `showModelFetcher`、`showAddNewModel`、`showDeployName`、`modelEditable`、`sdkType`，并通过 `ProviderSettingsContext` 传给子组件。内部 `Content` 会调用 `useFetchAiProviderModels(id)` 拉取模型，基于 `aiModelSelectors.filteredAiProviderModelList` 计算模型类型数量，并渲染分类 Tabs。分类包括 `all`、`chat`、`image`、`video`、`embedding`、`stt`、`tts`；没有模型的分类不会显示，但 `all` 始终显示。

`ModelList/ProviderSettingsContext.ts` 是模型列表内部上下文，向 `ModelItem`、新增/编辑模型弹窗等组件传递 Provider 级别配置，比如是否允许编辑模型、是否显示部署名、是否显示模型抓取按钮。

`ModelList/ModelTitle/index.tsx` 渲染模型列表顶部工具栏。它显示模型总数、搜索框、远程模型抓取按钮、新增模型按钮和更多菜单。它会在 Provider 切换时清空 `modelSearchKeyword`。远程抓取调用 `fetchRemoteModelList(provider)`，清除远程模型调用 `clearRemoteModels`，重置 Provider 模型调用 `clearModelsByProvider`。

`ModelList/EnabledModelList/index.tsx` 渲染已启用模型。它从 `aiModelSelectors.enabledAiProviderModelList` 取数据，按当前 Tab 过滤。用户可以批量禁用当前分类里的可切换模型，也可以打开 `SortModelModal` 调整已启用模型顺序。这里有一个细节：当 `modelEditable` 为 false 时，`embedding` 类型模型不会被批量切换，避免用户误关某些不可编辑场景需要的 embedding 模型。

`ModelList/DisabledModels.tsx` 渲染未启用模型，并实现分页加载和排序。它先从 store 中读取 `disabledAiProviderModelList`，首屏只展示 `PAGE_SIZE = 30` 条；随着滚动触底逐步展开本地已有数据，展开完后才通过 `aiModelService.getAiProviderModelList` 远程加载更多未启用模型。排序状态保存在 `useGlobalStore` 的 `systemStatusSelectors.disabledModelsSortType` 中，支持默认顺序、名称升降序、发布日期升降序。

`ModelList/ModelItem.tsx` 是单个模型行。它负责显示模型图标、名称、模型 ID、New 标记、能力标签、上下文窗口、价格信息、发布时间、启用开关、编辑按钮、删除按钮。切换开关调用 `toggleModelEnabled({ enabled, id, source, type })`；删除非内置模型调用 `removeAiModel(id, activeAiProvider)`；编辑会打开 `ModelConfigModal`。模型 ID 标签点击后会复制到剪贴板。

`ModelList/SearchResult.tsx` 是搜索结果视图。当 `modelSearchKeyword` 存在时，`ModelList/index.tsx` 不再渲染启用/禁用分组，而是渲染搜索结果。搜索结果来自 `aiModelSelectors.filteredAiProviderModelList`，并提供“批量启用搜索结果”操作。

`ModelList/CreateNewModelModal/*` 和 `ModelList/ModelConfigModal/index.tsx` 分别负责新增模型和编辑模型。两者复用 `CreateNewModelModal/Form` 作为表单。新增时调用 `createNewAiModel({ ...data, providerId })`，编辑时调用 `updateAiModelsConfig(id, editingProvider, data)`。`ExtendParamsSelect.tsx` 还引入了模型推理参数相关控件，例如不同模型族的 reasoning effort slider。

`ModelList/EmptyModels.tsx`、`SkeletonList.tsx`、`SortModelModal/*`、`ModelTitle/Search.tsx` 是列表体验层组件，分别处理空状态、加载骨架、排序弹窗和搜索输入。

## 上下游关系

上游调用主要来自 `src/routes/(main)/settings/provider/detail/default/index.tsx` 和 `src/routes/(main)/settings/provider/detail/default/ClientMode.tsx`。默认 Provider 详情页会组合：

```tsx
<ProviderConfig {...card} />
<ModelList id={card.id} {...card.settings} />
```

这说明 `features` 目录不是独立页面，而是 Provider detail 页面下的功能区。`ProviderConfig` 负责上半部分的 Provider 配置，`ModelList` 负责下半部分的模型管理。

还有很多 Provider 专用 detail 页面，例如 `azure`、`bedrock`、`cloudflare`、`comfyui`、`github`、`vertexai` 等。根据当前片段推断，它们会围绕相同 store 和 selector 获取 Provider 配置状态，有的可能定制 `ProviderConfigProps` 或模型展示参数。

核心数据上游是 `@/store/aiInfra`。这个目录大量使用：

- `useAiInfraStore`
- `aiProviderSelectors`
- `aiModelSelectors`
- `createNewAiProvider`
- `updateAiProviderConfig`
- `toggleModelEnabled`
- `batchToggleAiModels`
- `createNewAiModel`
- `updateAiModelsConfig`
- `removeAiModel`
- `fetchRemoteModelList`
- `useFetchAiProviderModels`

这意味着 UI 本身不直接维护 Provider 和 Model 的主数据，而是通过 Zustand store 读写。

服务层下游包括 `@/services/aiModel` 的 `aiModelService.getAiProviderModelList`，用于禁用模型列表的远程分页加载；`@/libs/trpc/client` 的 `lambdaQuery.oauthDeviceFlow.getAuthStatus.useQuery`，用于 OAuth Provider 的认证状态查询。

类型和领域模型主要来自 `@/types/aiProvider` 和 `model-bank`。`AiProviderDetailItem`、`AiProviderSettings`、`AiProviderSDKType`、`AiProviderSourceEnum` 决定 Provider 配置结构；`AiProviderModelListItem`、`AiModelSourceEnum` 决定模型列表项结构。

UI 下游依赖 `@lobehub/ui`、`@lobehub/icons`、`antd`、`antd-style`、`lucide-react` 和若干项目级组件，比如 `FormInput`、`FormPassword`、`ModelInfoTags`、`NewModelBadge`、`SkeletonInput`、`SkeletonSwitch`。

## 运行/调用流程

进入 Provider 设置详情页后，父级 detail 页面拿到 Provider 信息，并把它传入 `ProviderConfig` 和 `ModelList`。

`ProviderConfig` 首先从 `settings` 中解构出配置行为，例如是否显示 API Key、是否允许浏览器端请求、是否显示连接检查器、是否支持 Responses API。然后它从 `useAiInfraStore` 读取当前 Provider 的详情、启用状态、加载状态、运行时配置和更新状态。加载完成后，`useLayoutEffect` 会把 store 中的数据写入表单。这里用 `lastInitializedIdRef` 记录上一次初始化的 Provider ID，避免用户正在编辑时因为 store 刷新而重置表单。

用户修改表单时，`onValuesChange` 调用防抖后的 `updateAiProviderConfig(id, values)`。如果用户点击连接检查，`Checker` 会在检查前先保存当前表单值，然后执行测试；检查期间 `ProviderConfig` 会阻止防抖更新造成重复请求。OAuth Provider 则先渲染 `OAuthDeviceFlowAuth`，只有认证通过后才展示普通配置表单。

`ModelList` 渲染时先建立 `ProviderSettingsContext`，让子组件知道当前模型是否可编辑、是否能新增、是否显示部署名等。`Content` 调用 `useFetchAiProviderModels(id)` 拉模型列表；加载中显示 `SkeletonList`；如果有搜索关键词，显示 `SearchResult`；如果列表为空，显示 `EmptyModels`；否则显示分类 Tabs、已启用模型、未启用模型。

已启用模型走 `EnabledModelList`，用户可以批量禁用当前分类下可切换模型，也可以打开排序弹窗。未启用模型走 `DisabledModels`，先展示 store 中的未启用模型，再通过 `IntersectionObserver` 触底加载更多远程未启用模型。每个模型最终都渲染成 `ModelItem`，由它处理启用开关、复制 ID、编辑配置、删除自定义模型等交互。

新增 Provider 的流程相对独立：打开 `CreateNewProvider` 弹窗，填写基础信息和 SDK 配置，提交时执行 `normalizeProviderSettings`，再调用 `createNewAiProvider`。成功后跳转到新 Provider 的设置页。

## 小白阅读顺序

1. 先读 `providerSettings.ts` 和 `customProviderSdkOptions.ts`。这两个文件最小，能先理解“自定义 Provider 支持哪些 SDK 类型”以及“为什么有些 SDK 自动支持 Responses API”。

2. 再读 `CreateNewProvider/index.tsx`。它是最完整、最直观的表单提交例子：表单字段、校验、store action、成功跳转都在一个文件里。

3. 然后读 `ProviderConfig/index.tsx`。重点看三段：从 store 取数据、`useLayoutEffect` 初始化表单、`onValuesChange` 防抖保存。不要一开始陷入 UI 样式细节。

4. 接着读 `ModelList/index.tsx`。理解它如何把模型列表拆成加载态、搜索态、空态、正常态，以及如何通过 `ProviderSettingsContext` 给子组件传公共配置。

5. 再读 `ModelTitle/index.tsx`、`EnabledModelList/index.tsx`、`DisabledModels.tsx`。这三者分别对应顶部工具栏、已启用模型、未启用模型，是模型管理的主流程。

6. 最后读 `ModelItem.tsx` 和两个模型弹窗。`ModelItem` 汇总了单模型的展示和操作，是理解“启用/禁用、编辑、删除、复制 ID、价格信息展示”的关键。

## 常见误区

不要把这个目录理解成普通的 `src/features` 目录。它虽然叫 `features`，但实际位于 `src/routes/(main)/settings/provider` 下面，是历史 route 内业务实现。按照当前 SPA 约定，新增大型业务 UI 时更推荐放到 `src/features/<Domain>/`，route 目录只做页面组合。

不要以为 `ProviderConfig` 的表单是点击保存才提交。它是 `onValuesChange` 触发、500ms 防抖自动保存。连接检查按钮还会在检查前主动保存一次当前表单值，所以阅读网络请求时要注意这两个入口。

不要忽略 `providerRuntimeConfig` 和 `data` 的合并。`ProviderConfig` 初始化表单时不是只用 Provider detail，还会把运行时配置里的 `config` 合并进去，尤其影响 `enableResponseApi` 这类嵌套配置。

不要把 `supportResponsesApi` 当成用户任意填写字段。`normalizeProviderSettings` 会根据 `sdkType` 自动增删这个字段：`openai` 和 `router` 支持时设置为 true，不支持时删除。

不要认为 `DisabledModels` 一次性加载全部未启用模型。它先分页展示 store 中已有列表，再触底远程加载更多，并且会去重，避免远程结果和本地基础列表重复。

不要把 `modelEditable` 理解成完全禁止模型开关。`ModelItem` 里有特殊逻辑：当 `modelEditable` 为 false 时，非 `embedding` 模型仍可切换，但 `embedding` 类型不可切换；`EnabledModelList` 的批量禁用也遵循类似限制。

不要忘记搜索态会改变整个列表结构。只要 `modelSearchKeyword` 存在，`ModelList` 会直接渲染 `SearchResult`，不再显示已启用/未启用分组和分类下的正常列表。

不要把内置模型和自定义模型的删除逻辑混为一谈。`ModelItem` 只有在 `source !== AiModelSourceEnum.Builtin` 时才显示删除按钮，内置模型通常只能启用或禁用，不能直接删除。

不要忽略移动端分支。`ModelList`、`ModelTitle`、`ModelItem` 都根据 `useIsMobile` 调整布局，例如移动端搜索框会放到标题栏下方，模型项也会使用更紧凑的行布局。
