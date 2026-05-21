# 文件：src/routes/(main)/settings/provider/features/ModelList/EnabledModelList/index.tsx

## 它负责什么

`EnabledModelList/index.tsx` 负责在“设置 → 模型供应商 → 模型列表”页面中渲染“已启用模型”区域。

它的职责不是拉取模型数据，也不是决定当前供应商是谁，而是从 `useAiInfraStore` 里取出当前供应商已经启用的模型列表，然后根据父组件传入的 `activeTab` 按模型类型过滤展示，例如 `all`、`chat`、`image`、`video`、`embedding`、`stt`、`tts`。

这个组件还提供两个针对已启用模型的批量操作入口：

- 一键禁用当前分类下可操作的已启用模型。
- 打开 `SortModelModal` 对已启用模型排序。

它最终把每个模型交给同目录的 `ModelItem` 渲染，因此单个模型的开关、编辑、删除、标签、价格等细节不在本文件里实现。

## 关键组成

### `EnabledModelListProps`

```ts
interface EnabledModelListProps {
  activeTab: string;
}
```

`activeTab` 来自父组件 `ModelList/index.tsx` 中的 Tabs。它表示当前用户正在查看哪个模型分类。

本文件对它的使用很直接：

- `activeTab === 'all'` 时展示全部已启用模型。
- 其他值时只展示 `model.type === activeTab` 的模型。

这里没有使用更严格的联合类型，而是用 `string`。根据当前片段推断，这是因为父组件的 Tabs key 也是字符串形式，组件之间保持了较宽松的传参类型。

### `useTranslation('modelProvider')`

```ts
const { t } = useTranslation('modelProvider');
```

本组件所有 UI 文案都来自 `modelProvider` 命名空间，例如：

- `providerModels.list.enabled`
- `providerModels.list.enabledActions.disableAll`
- `providerModels.list.enabledActions.sort`
- `providerModels.list.enabledEmpty`
- `providerModels.list.noModelsInCategory`

这说明它是设置页模型供应商文案体系的一部分，不应该在组件里直接写中文或英文固定文案。

### `ProviderSettingsContext`

```ts
const { modelEditable } = use(ProviderSettingsContext);
```

这里使用 React 19 的 `use()` 读取 Context，而不是传统的 `useContext()`。

`modelEditable` 来自父组件 `ModelList` 的外层包裹：

```tsx
<ProviderSettingsContext
  value={{ modelEditable, sdkType, showAddNewModel, showDeployName, showModelFetcher }}
>
```

它表示当前供应商的模型列表是否允许编辑。这个值会影响批量禁用逻辑：当 `modelEditable` 为 `false` 时，`embedding` 类型模型不会被纳入批量禁用范围。

### `enabledModels`

```ts
const enabledModels = useAiInfraStore(aiModelSelectors.enabledAiProviderModelList, isEqual);
```

这是本组件最核心的数据来源。

`aiModelSelectors.enabledAiProviderModelList` 的逻辑在 `src/store/aiInfra/slices/aiModel/selectors.ts` 中：

```ts
s.aiProviderModelList.filter((item) => item.enabled)
```

也就是说，本组件拿到的不是所有模型，而是当前供应商模型列表里 `enabled` 为真值的模型。

第二个参数 `isEqual` 来自 `fast-deep-equal`，用于 Zustand selector 的相等性比较，避免数组内容没变时触发不必要重渲染。

### `batchToggleAiModels`

```ts
const batchToggleAiModels = useAiInfraStore((s) => s.batchToggleAiModels);
```

这个 action 来自 `src/store/aiInfra/slices/aiModel/action.ts`。它的核心行为是：

1. 从 store 里读取 `activeAiProvider`。
2. 如果没有当前供应商，直接返回。
3. 调用 `aiModelService.batchToggleAiModels(activeAiProvider, ids, enabled)`。
4. 调用 `refreshAiModelList()` 刷新模型列表。
5. `refreshAiModelList()` 内部通过 SWR `mutate` 刷新当前供应商模型数据，并触发运行时状态刷新。

所以本组件点击“禁用全部”时，并不是本地直接改数组，而是走服务层更新，再刷新 store。

### `open`

```ts
const [open, setOpen] = useState(false);
```

控制 `SortModelModal` 是否显示。

当用户点击排序按钮时：

```ts
setOpen(true);
```

当排序弹窗取消时：

```ts
setOpen(false);
```

弹窗只在 `open` 为真时渲染：

```tsx
{open && (
  <SortModelModal
    defaultItems={enabledModels}
    open={open}
    onCancel={() => {
      setOpen(false);
    }}
  />
)}
```

注意：排序弹窗拿到的是完整的 `enabledModels`，不是 `filteredModels`。也就是说，即使当前 Tab 是 `chat`，排序入口打开后默认数据仍然是所有已启用模型。根据当前片段推断，排序是针对整个供应商的已启用模型顺序，而不是只排序当前分类。

### `batchLoading`

```ts
const [batchLoading, setBatchLoading] = useState(false);
```

用于禁用全部按钮的 loading 状态。

点击批量禁用时：

```ts
setBatchLoading(true);
await batchToggleAiModels(
  togglableModels.map((i) => i.id),
  false,
);
setBatchLoading(false);
```

这里没有 `try/finally`。如果 `batchToggleAiModels` 抛错，`setBatchLoading(false)` 可能不会执行。阅读时要注意这是当前实现的行为，而不是通用最佳实践。

### `filteredModels`

```ts
const filteredModels = useMemo(() => {
  if (activeTab === 'all') return enabledModels;
  return enabledModels.filter((model) => model.type === activeTab);
}, [enabledModels, activeTab]);
```

这是按当前 Tab 过滤后的已启用模型列表。

它只在两个依赖变化时重算：

- `enabledModels`
- `activeTab`

这个列表用于真正渲染 `ModelItem`。

### `togglableModels`

```ts
const togglableModels = useMemo(
  () =>
    modelEditable ? filteredModels : filteredModels.filter((model) => model.type !== 'embedding'),
  [filteredModels, modelEditable],
);
```

这是“批量禁用”按钮真正操作的模型集合。

规则是：

- 如果 `modelEditable === true`，当前 Tab 下所有已启用模型都可以被批量禁用。
- 如果 `modelEditable === false`，排除 `embedding` 模型。

这个规则和 `ModelItem.tsx` 里的单项开关逻辑保持一致：

```ts
const canToggle = modelEditable || type !== 'embedding';
```

也就是说，当模型不可编辑时，`embedding` 类型模型连单项开关也不会显示，批量操作也会避开它。

### 空状态判断

本组件有两个不同层次的空状态：

```ts
const isEmpty = enabledModels.length === 0;
const isCurrentTabEmpty = filteredModels.length === 0;
```

区别很重要：

- `isEmpty`：当前供应商没有任何已启用模型。
- `isCurrentTabEmpty`：当前供应商有已启用模型，但当前分类下没有。

对应 UI：

```tsx
{isEmpty ? (
  enabledEmpty
) : isCurrentTabEmpty ? (
  noModelsInCategory
) : (
  ModelItem 列表
)}
```

所以用户在 `image` Tab 看到“当前分类没有模型”，并不代表整个供应商没有启用模型。

## 上下游关系

### 上游：`ModelList/index.tsx`

`EnabledModelList` 的直接父组件是：

```txt
src/routes/(main)/settings/provider/features/ModelList/index.tsx
```

父组件负责更大的模型列表页面结构：

1. 调用 `useFetchAiProviderModels(id)` 拉取当前供应商模型列表。
2. 根据 `modelSearchKeyword` 判断是否展示搜索结果。
3. 根据 `aiProviderModelList` 统计各模型类型数量。
4. 渲染 Tabs。
5. 把当前 Tab 传给 `EnabledModelList` 和 `DisabledModels`。

核心调用关系是：

```tsx
<EnabledModelList activeTab={currentActiveTab} />
<DisabledModels activeTab={currentActiveTab} providerId={id} />
```

因此 `EnabledModelList` 只处理“已启用”半区；“未启用”半区由 `DisabledModels` 处理。

### 更上游：供应商详情页

`ModelList` 又被供应商详情页面使用，例如：

```txt
src/routes/(main)/settings/provider/detail/default/index.tsx
src/routes/(main)/settings/provider/detail/default/ClientMode.tsx
```

这些页面会把供应商 `id` 传入 `ModelList`。`ModelList` 再用这个 `id` 拉取对应供应商的模型数据。

所以完整页面层级大致是：

```txt
provider detail page
  -> ModelList
    -> ProviderSettingsContext
    -> ModelTitle
    -> EnabledModelList
      -> ModelItem
      -> SortModelModal
    -> DisabledModels
```

### 数据来源：`useAiInfraStore`

本组件的数据来自：

```txt
src/store/aiInfra
```

关键 selector：

```ts
aiModelSelectors.enabledAiProviderModelList
```

它从 `aiProviderModelList` 里筛出 `enabled` 模型。

`aiProviderModelList` 的初始化和刷新由 store action 管理。父组件 `ModelList` 调用：

```ts
useFetchAiProviderModels(id)
```

这个 action 使用 SWR 请求服务层：

```ts
aiModelService.getAiProviderModelList(id)
```

成功后写入：

```ts
{
  aiProviderModelList: data,
  isAiModelListInit: true,
}
```

因此 `EnabledModelList` 本身不关心接口请求，只订阅 store 中已经准备好的结果。

### 下游：`ModelItem`

每个模型通过：

```tsx
<ModelItem displayName={label as string} id={id as string} key={id} {...res} />
```

交给同目录的 `ModelItem.tsx` 渲染。

`ModelItem` 负责更细的交互，例如：

- 展示模型图标。
- 展示模型 ID、名称、能力标签。
- 展示价格、发布时间等信息。
- 单独开关模型启用状态。
- 打开模型配置弹窗。
- 删除非内置模型。

所以 `EnabledModelList` 是列表容器，`ModelItem` 是模型行组件。

### 下游：`SortModelModal`

排序按钮会打开：

```txt
src/routes/(main)/settings/provider/features/ModelList/SortModelModal/index.tsx
```

本组件传入：

```tsx
defaultItems={enabledModels}
```

`SortModelModal` 根据当前片段可知会接收 `AiProviderModelListItem[]`，并在排序变更时调用 store 的排序更新 action，例如 `updateAiModelsSort`，最终走服务层更新顺序并刷新列表。

这里要注意，排序弹窗使用的是所有已启用模型，而不是当前 Tab 的过滤结果。

### 服务层关系

本组件通过 store 间接调用服务层，不直接 import 服务。

批量禁用路径是：

```txt
EnabledModelList
  -> useAiInfraStore(s => s.batchToggleAiModels)
  -> aiModelService.batchToggleAiModels(activeAiProvider, ids, false)
  -> refreshAiModelList()
  -> SWR mutate
  -> aiProviderModelList 更新
  -> EnabledModelList 重渲染
```

根据当前片段推断，`aiModelService` 是模型供应商配置的客户端服务封装，负责把 UI 操作落到后端或本地持久层。

## 运行/调用流程

1. 用户进入某个供应商设置详情页。

2. 详情页渲染 `ModelList`，并传入供应商 `id` 以及一些设置能力，例如 `modelEditable`、`showAddNewModel`、`showModelFetcher` 等。

3. `ModelList` 通过 `useFetchAiProviderModels(id)` 拉取该供应商的模型列表。

4. 拉取成功后，store 中的 `aiProviderModelList` 被更新。

5. `EnabledModelList` 通过 `aiModelSelectors.enabledAiProviderModelList` 从 store 里拿到已启用模型。

6. 父组件 `ModelList` 根据全部模型类型生成 Tabs，并把当前 Tab 作为 `activeTab` 传给 `EnabledModelList`。

7. `EnabledModelList` 根据 `activeTab` 计算 `filteredModels`：

   - `all`：直接使用全部已启用模型。
   - 其他分类：只保留对应 `type` 的模型。

8. `EnabledModelList` 根据 `modelEditable` 计算 `togglableModels`：

   - 可编辑时，当前分类下所有模型都可批量禁用。
   - 不可编辑时，排除 `embedding` 模型。

9. 渲染顶部标题和操作按钮：

   - 如果没有任何已启用模型，不显示操作按钮。
   - 如果存在可批量操作模型，显示“禁用全部”按钮。
   - 只要有已启用模型，就显示排序按钮。

10. 渲染列表主体：

    - 没有任何已启用模型：显示 `enabledEmpty`。
    - 有已启用模型但当前分类为空：显示 `noModelsInCategory`。
    - 当前分类有模型：逐个渲染 `ModelItem`。

11. 用户点击“禁用全部”：

    - 设置 `batchLoading = true`。
    - 收集 `togglableModels.map((i) => i.id)`。
    - 调用 `batchToggleAiModels(ids, false)`。
    - store action 调用服务层更新。
    - 刷新模型列表。
    - 设置 `batchLoading = false`。
    - UI 根据新的 store 数据重渲染。

12. 用户点击排序：

    - 设置 `open = true`。
    - 渲染 `SortModelModal`。
    - 弹窗拿到完整 `enabledModels` 作为默认排序项。
    - 取消时调用 `onCancel`，设置 `open = false`。

## 小白阅读顺序

1. 先看 `EnabledModelListProps`，明确这个组件只接收一个 `activeTab`。

2. 再看这几行数据读取：

   ```ts
   const { modelEditable } = use(ProviderSettingsContext);
   const enabledModels = useAiInfraStore(aiModelSelectors.enabledAiProviderModelList, isEqual);
   const batchToggleAiModels = useAiInfraStore((s) => s.batchToggleAiModels);
   ```

   这三行分别说明：它依赖父级配置、从 store 读已启用模型、通过 store 修改模型启用状态。

3. 接着看两个 `useMemo`：

   ```ts
   filteredModels
   togglableModels
   ```

   这是理解本组件业务规则的核心。一个决定“展示哪些”，一个决定“批量操作哪些”。

4. 然后看 JSX 顶部的 `<Flexbox horizontal justify="space-between">`，理解标题、禁用按钮、排序按钮如何显示。

5. 再看底部三段条件渲染：

   ```tsx
   isEmpty ? ... : isCurrentTabEmpty ? ... : ...
   ```

   这里能看清两个空状态的区别。

6. 最后再去看邻近文件：

   - `ModelList/index.tsx`：理解 `activeTab` 从哪里来。
   - `ModelItem.tsx`：理解每个模型行具体怎么渲染和切换。
   - `SortModelModal/index.tsx`：理解排序弹窗如何消费 `enabledModels`。
   - `src/store/aiInfra/slices/aiModel/selectors.ts`：理解 `enabledModels` 如何筛出来。
   - `src/store/aiInfra/slices/aiModel/action.ts`：理解批量禁用如何落到服务层。

## 常见误区

1. 不要把 `enabledModels` 理解成“当前 Tab 的模型”。

   `enabledModels` 是所有已启用模型。当前 Tab 过滤后的结果是 `filteredModels`。

2. 不要把 `isEmpty` 和 `isCurrentTabEmpty` 混为一谈。

   `isEmpty` 表示没有任何已启用模型。  
   `isCurrentTabEmpty` 表示当前分类下没有已启用模型。

3. “禁用全部”不是禁用所有已启用模型，而是禁用当前 Tab 下的 `togglableModels`。

   如果当前 Tab 是 `chat`，它只会收集当前已启用的 chat 模型。  
   如果当前 Tab 是 `all`，才会覆盖所有符合可切换条件的已启用模型。

4. `modelEditable === false` 不代表所有模型都不能切换。

   当前逻辑是：不可编辑时排除 `embedding`，其他类型仍然可以进入 `togglableModels`。这一点和 `ModelItem` 里的单项开关规则一致。

5. 排序弹窗不是按当前 Tab 排序。

   `SortModelModal` 收到的是 `enabledModels`，也就是所有已启用模型。即使当前用户停留在某个分类 Tab，排序操作的数据源仍是完整已启用列表。

6. 本组件不负责加载数据。

   数据加载发生在父组件 `ModelList` 的 `useFetchAiProviderModels(id)` 中。本组件只订阅 store 里的结果。

7. 本组件不负责单个模型的详细交互。

   单个模型的开关、配置、删除、复制 ID、能力标签、价格展示等逻辑都在 `ModelItem.tsx` 中。

8. `batchLoading` 只覆盖批量禁用按钮。

   单个模型的 loading 状态来自 `aiModelSelectors.isModelLoading(id)`，在 `ModelItem` 中处理，不在本文件里处理。

9. `displayName || id` 只是列表展示名兜底。

   传给 `ModelItem` 的 `displayName` 被处理成 `label`，但模型真实标识仍然是 `id`。不要把展示名当作模型主键。

10. `isEqual` 的作用是减少重渲染，不是业务过滤。

   真正筛选已启用模型的是 `aiModelSelectors.enabledAiProviderModelList`；`isEqual` 只是 Zustand selector 的相等性判断。
