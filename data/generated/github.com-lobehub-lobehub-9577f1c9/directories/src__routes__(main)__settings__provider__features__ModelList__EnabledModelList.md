# 目录：src/routes/(main)/settings/provider/features/ModelList/EnabledModelList

## 它负责什么

`EnabledModelList` 是 provider 设置页中“已启用模型”区域的 UI 组件。它只关心当前 provider 下已经启用的模型，并根据父组件传入的 `activeTab` 做模型类型过滤，例如 `all`、`chat`、`embedding`、`image`、`stt`、`tts`、`video` 等。

它承担三类职责：

1. 展示已启用模型列表：从 `useAiInfraStore` 读取 `aiModelSelectors.enabledAiProviderModelList`，再渲染为一组 `ModelItem`。
2. 提供批量禁用入口：点击 `ToggleLeft` 图标后，对当前 tab 下可切换的模型执行 `batchToggleAiModels(ids, false)`。
3. 提供排序入口：点击 `ArrowDownUpIcon` 后打开 `SortModelModal`，允许用户拖拽调整已启用模型的顺序。

这个目录本身只有一个文件：

`src/routes/(main)/settings/provider/features/ModelList/EnabledModelList/index.tsx`

它不是一个独立页面，而是 `ModelList` 功能模块里的一个子组件。

## 关键组成

核心 import 可以分成几组理解：

`@lobehub/ui`：
提供 UI 基础组件，包括 `ActionIcon`、`Center`、`Flexbox`、`Text`、`TooltipGroup`。这个组件没有自己定义 CSS，布局主要依赖 `Flexbox` 和内联小字号样式。

`fast-deep-equal`：
作为 zustand selector 的比较函数传给 `useAiInfraStore`，用于减少无意义重渲染。这里读取的是数组型模型列表，如果不用深比较，store 变化时更容易触发组件刷新。

`lucide-react`：
使用 `ToggleLeft` 作为“全部禁用”按钮图标，使用 `ArrowDownUpIcon` 作为“排序”按钮图标。

`react`：
使用 `use` 读取 `ProviderSettingsContext`，使用 `useMemo` 缓存过滤后的模型列表，使用 `useState` 管理排序弹窗开关和批量操作 loading 状态。

`react-i18next`：
通过 `useTranslation('modelProvider')` 读取 provider 模型管理相关文案，例如已启用标题、空状态、按钮 tooltip。

`@/store/aiInfra` 和 `@/store/aiInfra/selectors`：
这是数据和操作的核心来源。组件通过 `aiModelSelectors.enabledAiProviderModelList` 获取已启用模型，通过 `batchToggleAiModels` 执行批量禁用。

同级依赖：

`../ModelItem`：
真正负责渲染单个模型行，包括模型图标、模型 ID、能力标签、开关、编辑按钮、删除按钮等。`EnabledModelList` 只把模型数据拆开后传给它。

`../ProviderSettingsContext`：
提供 provider 模型设置上下文。这里主要读取 `modelEditable`，用于判断当前 provider 的模型是否完全可编辑。

`../SortModelModal`：
排序弹窗。`EnabledModelList` 负责打开它，并把完整的 `enabledModels` 作为 `defaultItems` 传入。

组件 props 很简单：

```ts
interface EnabledModelListProps {
  activeTab: string;
}
```

`activeTab` 来自父组件 `ModelList` 中的 `Tabs`，不是本组件自己维护。

## 上下游关系

上游调用方是：

`src/routes/(main)/settings/provider/features/ModelList/index.tsx`

`ModelList` 先通过 `useFetchAiProviderModels(id)` 拉取当前 provider 的模型列表，然后计算每个模型类型的数量，生成 tab。正常状态下它按顺序渲染：

```tsx
<EnabledModelList activeTab={currentActiveTab} />
<DisabledModels activeTab={currentActiveTab} providerId={id} />
```

因此，`EnabledModelList` 展示的是“启用区”，`DisabledModels` 展示的是“未启用区”，两者共享同一个 `activeTab`。

再往上，`ModelList` 被 provider 详情页使用，例如：

`src/routes/(main)/settings/provider/detail/default/index.tsx`

默认 provider 详情页会把 provider card 的 `settings` 传给 `ModelList`：

```tsx
<ModelList id={card.id} {...card.settings} />
```

这意味着 `modelEditable`、`showAddNewModel`、`showDeployName`、`showModelFetcher` 等能力开关通常来自 provider 配置。

数据下游链路是：

`EnabledModelList`
→ `useAiInfraStore`
→ `AiModelActionImpl.batchToggleAiModels`
→ `aiModelService.batchToggleAiModels`
→ `lambdaClient.aiModel.batchToggleAiModels.mutate`
→ `src/server/routers/lambda/aiModel.ts`
→ `ctx.aiModelModel.batchToggleAiModels(...)`

排序链路是：

`EnabledModelList`
→ `SortModelModal`
→ `updateAiModelsSort(providerId, sortMap)`
→ `aiModelService.updateAiModelOrder`
→ `lambdaClient.aiModel.updateAiModelOrder.mutate`
→ `ctx.aiModelModel.updateModelsOrder(...)`

单个模型开关不在 `EnabledModelList` 里完成，而是在 `ModelItem` 里通过 `toggleModelEnabled({ enabled, id, source, type })` 完成。

## 运行/调用流程

页面进入某个 provider 设置详情后，父级 `ModelList` 使用当前 provider id 调用 `useFetchAiProviderModels(id)`。这个 hook 内部通过 `aiModelService.getAiProviderModelList(id)` 请求后端模型列表，并在成功后写入 `aiProviderModelList`。

`EnabledModelList` 渲染时，从 store 中选择：

```ts
const enabledModels = useAiInfraStore(aiModelSelectors.enabledAiProviderModelList, isEqual);
```

selector 的逻辑很直接：

```ts
s.aiProviderModelList.filter((item) => item.enabled)
```

然后组件根据 `activeTab` 得到 `filteredModels`：

- 如果 `activeTab === 'all'`，直接返回所有已启用模型。
- 否则只保留 `model.type === activeTab` 的模型。

接着它计算 `togglableModels`。这里有一个重要规则：

```ts
modelEditable
  ? filteredModels
  : filteredModels.filter((model) => model.type !== 'embedding')
```

也就是说，当 `modelEditable` 为 false 时，`embedding` 类型模型不会出现在批量禁用目标里。这个规则和 `ModelItem` 里的单项开关逻辑一致：`canToggle = modelEditable || type !== 'embedding'`。根据当前片段推断，这可能是为了保护某些 provider 下不可编辑的 embedding 模型，避免用户误关导致检索、向量化等能力异常。

渲染分支有三个：

1. `enabledModels.length === 0`  
   展示 `providerModels.list.enabledEmpty`，表示没有已启用模型。

2. `enabledModels` 不为空，但当前 tab 过滤后为空  
   展示 `providerModels.list.noModelsInCategory`，表示当前分类下没有已启用模型。

3. 当前 tab 有模型  
   遍历 `filteredModels`，每个模型渲染一个 `ModelItem`。

顶部操作区只有在 `enabledModels` 不为空时出现：

- 如果 `togglableModels.length > 0`，显示“全部禁用”按钮。
- 始终显示“排序”按钮。
- 点击排序按钮后设置 `open = true`，渲染 `SortModelModal`。

批量禁用流程：

```ts
setBatchLoading(true);
await batchToggleAiModels(
  togglableModels.map((i) => i.id),
  false,
);
setBatchLoading(false);
```

store action 会读取当前 `activeAiProvider`。如果没有 active provider，直接返回；否则调用 service，并在成功后执行 `refreshAiModelList()`，通过 SWR mutate 重新拉取当前 provider 的模型列表。

## 小白阅读顺序

1. 先读 `EnabledModelList/index.tsx`  
   重点看四个变量：`enabledModels`、`filteredModels`、`togglableModels`、`isCurrentTabEmpty`。理解这四个变量，就理解了这个组件大部分展示逻辑。

2. 再读父组件 `ModelList/index.tsx`  
   看 `activeTab` 是怎么来的，以及为什么有 `EnabledModelList` 和 `DisabledModels` 两块。这里还能看到模型列表的加载入口 `useFetchAiProviderModels(id)`。

3. 再读 `ModelItem.tsx`  
   因为 `EnabledModelList` 不负责单个模型的具体 UI 和单项开关。模型名称、ID 标签、能力标签、价格信息、编辑、删除、启用开关都在 `ModelItem` 中。

4. 然后读 `SortModelModal/index.tsx`  
   理解排序弹窗如何把拖拽后的数组转换成 `{ id, sort, type }`，并调用 `updateAiModelsSort`。

5. 最后读 store 和 service  
   推荐顺序是：
   `src/store/aiInfra/slices/aiModel/selectors.ts`
   → `src/store/aiInfra/slices/aiModel/action.ts`
   → `src/services/aiModel/index.ts`
   → `src/server/routers/lambda/aiModel.ts`

这样可以从 UI 一路追到后端 mutation。

## 常见误区

1. 误以为 `EnabledModelList` 会主动请求模型列表。  
   它不会。模型列表的请求发生在父组件 `ModelList` 的 `useFetchAiProviderModels(id)` 中。`EnabledModelList` 只消费 store 中已经存在的数据。

2. 误以为 `activeTab` 会影响后端请求。  
   当前组件里的 tab 过滤是前端过滤：`enabledModels.filter((model) => model.type === activeTab)`。它不会因为切换 tab 而重新请求后端。

3. 误以为“全部禁用”一定会禁用当前 tab 下所有模型。  
   实际上它禁用的是 `togglableModels`。当 `modelEditable` 为 false 时，`embedding` 类型会被排除。

4. 误以为排序只排序当前 tab。  
   `SortModelModal` 接收的是完整的 `enabledModels`，不是 `filteredModels`。所以排序入口虽然显示在当前 tab 页面上，但弹窗默认拿到的是全部已启用模型。根据当前片段推断，这是为了维护 provider 内启用模型的整体顺序，而不是分类内局部顺序。

5. 误以为空状态只有一种。  
   这里区分两种空：`enabledModels` 为空表示完全没有已启用模型；`filteredModels` 为空表示有已启用模型，但当前分类没有。

6. 误以为单项开关逻辑在本组件中。  
   本组件只做批量禁用。单个模型的启用/禁用开关在 `ModelItem` 中，并且还会维护单项 loading 状态 `aiModelLoadingIds`。

7. 误以为 `isEmpty` 应该基于 `filteredModels`。  
   代码中特意用 `enabledModels.length === 0` 判断总的已启用列表是否为空，再用 `filteredModels.length === 0` 判断当前 tab 是否为空。这两个判断服务于不同文案和不同 UI 状态。
