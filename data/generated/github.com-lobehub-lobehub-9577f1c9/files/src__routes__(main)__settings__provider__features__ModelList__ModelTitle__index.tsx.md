# 文件：src/routes/(main)/settings/provider/features/ModelList/ModelTitle/index.tsx

## 它负责什么

`ModelTitle/index.tsx` 定义并默认导出 `ModelTitle` 组件。它是“设置页 > Provider 配置 > 模型列表”顶部的标题和操作栏，主要负责展示模型列表标题、模型总数、搜索框，以及几个围绕模型列表的操作按钮。

它本身不直接渲染模型条目，也不负责模型卡片的启用、排序、编辑等细节。它更像 `ModelList` 的头部控制区，承担这些职责：

- 显示模型列表标题：`providerModels.list.title`
- 显示当前 provider 下模型总数：`providerModels.list.total`
- 根据加载状态展示 `Skeleton`
- 提供模型搜索入口，并把关键词写入 `useAiInfraStore.modelSearchKeyword`
- 提供“从远程拉取模型列表”的按钮
- 提供“新增自定义模型”的按钮和弹窗入口
- 当列表里存在远程模型时，提供“清除已获取远程模型”的快捷按钮
- 提供更多菜单，目前菜单里只有“重置全部模型”
- 根据移动端和桌面端做不同布局

它的父级是：

`src/routes/(main)/settings/provider/features/ModelList/index.tsx`

父组件会先渲染 `ModelTitle`，再渲染下面的模型列表内容。也就是说，`ModelTitle` 是模型列表区域的固定头部，而真正的列表内容由 `Content`、`EnabledModelList`、`DisabledModels`、`SearchResult`、`EmptyModels` 等组件处理。

## 关键组成

这个文件的核心组件是：

```ts
const ModelTitle = memo<ModelFetcherProps>(
  ({ provider, showAddNewModel = true, showModelFetcher = true }) => {
    // ...
  },
);
```

它接收 3 个 props：

```ts
interface ModelFetcherProps {
  provider: string;
  showAddNewModel?: boolean;
  showModelFetcher?: boolean;
}
```

- `provider`：当前模型供应商 id，例如 OpenAI、Anthropic、Azure 之类的 provider 标识。这个值会传给模型拉取、清空、重置等 store action。
- `showAddNewModel`：是否显示新增模型按钮，默认 `true`。
- `showModelFetcher`：是否显示远程获取模型按钮，默认 `true`。

组件使用了 `memo`，说明它希望在 props 没变化时避免不必要重渲染。

### 1. UI 依赖

文件从 `@lobehub/ui` 引入了这些组件：

```ts
ActionIcon, Button, DropdownMenu, Flexbox, Skeleton, Text
```

它们分别用于：

- `Flexbox`：组织整体布局和横向/纵向排列
- `Text`：标题、总数文本
- `Skeleton.Button`：加载态占位
- `Button`：获取远程模型、新增模型、更多菜单按钮
- `ActionIcon`：总数旁边的清除远程模型图标按钮
- `DropdownMenu`：更多操作菜单

从 `antd` 引入：

```ts
App, Space
```

- `App.useApp()` 提供 `modal` 和 `message`
- `Space.Compact` 把多个小按钮压成一组紧凑按钮

从 `lucide-react` 引入图标：

```ts
CircleX, EllipsisVertical, LucideRefreshCcwDot, PlusIcon
```

它们对应：

- `CircleX`：清除远程模型
- `LucideRefreshCcwDot`：拉取远程模型
- `PlusIcon`：新增模型
- `EllipsisVertical`：更多菜单

### 2. 国际化

组件使用：

```ts
const { t } = useTranslation('modelProvider');
```

说明所有文案来自 `modelProvider` 这个 i18n namespace。当前文件用到的 key 包括：

- `providerModels.list.title`
- `providerModels.list.total`
- `providerModels.list.fetcher.clear`
- `providerModels.list.fetcher.fetch`
- `providerModels.list.fetcher.fetching`
- `providerModels.list.resetAll.title`
- `providerModels.list.resetAll.conform`
- `providerModels.list.resetAll.success`

注意这里的 `conform` 看起来像拼写误差，但代码中实际使用的是这个 key，阅读时不要自动改成 `confirm`。

### 3. Store 状态和 action

组件主要通过 `useAiInfraStore` 读取模型列表状态和操作方法：

```ts
const [
  searchKeyword,
  totalModels,
  isEmpty,
  hasRemoteModels,
  fetchRemoteModelList,
  clearObtainedModels,
  clearModelsByProvider,
  useFetchAiProviderModels,
] = useAiInfraStore((s) => [
  s.modelSearchKeyword,
  aiModelSelectors.totalAiProviderModelList(s),
  aiModelSelectors.isEmptyAiProviderModelList(s),
  aiModelSelectors.hasRemoteModels(s),
  s.fetchRemoteModelList,
  s.clearRemoteModels,
  s.clearModelsByProvider,
  s.useFetchAiProviderModels,
]);
```

这些值含义如下：

- `searchKeyword`：当前模型搜索关键词，来自 `s.modelSearchKeyword`
- `totalModels`：当前 provider 模型列表总数，来自 `aiModelSelectors.totalAiProviderModelList`
- `isEmpty`：模型列表是否为空，来自 `aiModelSelectors.isEmptyAiProviderModelList`
- `hasRemoteModels`：当前列表中是否有来源为远程的模型，来自 `aiModelSelectors.hasRemoteModels`
- `fetchRemoteModelList`：从远程服务获取模型列表
- `clearObtainedModels`：实际对应 `s.clearRemoteModels`，清除远程来源模型
- `clearModelsByProvider`：清空当前 provider 下的模型
- `useFetchAiProviderModels`：SWR hook，用于加载 provider 模型列表

在 `src/store/aiInfra/slices/aiModel/selectors.ts` 中可以看到相关 selector 的依据：

```ts
const totalAiProviderModelList = (s) => s.aiProviderModelList.length;

const isEmptyAiProviderModelList = (s) => totalAiProviderModelList(s) === 0;

const hasRemoteModels = (s) =>
  s.aiProviderModelList.some((m) => m.source === AiModelSourceEnum.Remote);
```

因此，`ModelTitle` 展示的总数和远程模型状态都不是局部计算出来的，而是直接依赖全局 `aiInfra` store 中的 `aiProviderModelList`。

### 4. 加载状态

组件调用：

```ts
const { isLoading } = useFetchAiProviderModels(provider);
```

这个 hook 来自 store action。根据 `src/store/aiInfra/slices/aiModel/action.ts`，它内部使用 `useClientDataSWR`，key 是：

```ts
[FETCH_AI_PROVIDER_MODEL_LIST_KEY, id]
```

请求数据来自：

```ts
aiModelService.getAiProviderModelList(id)
```

成功后会把数据写入 store：

```ts
{ aiProviderModelList: data, isAiModelListInit: true }
```

所以 `ModelTitle` 的 `isLoading` 和下面模型列表内容的 `isLoading` 使用的是同一套 provider 模型列表加载机制。

当 `isLoading` 为 `true` 时：

- 标题右侧的模型总数区域显示 `Skeleton.Button`
- 右侧操作区显示一个宽度约 `120px` 的小型 `Skeleton.Button`
- 搜索、获取远程模型、新增、更多菜单不会显示

### 5. 本地 loading 状态

组件内部维护了三个局部状态：

```ts
const [fetchRemoteModelsLoading, setFetchRemoteModelsLoading] = useState(false);
const [clearRemoteModelsLoading, setClearRemoteModelsLoading] = useState(false);
const [showModal, setShowModal] = useState(false);
```

它们分别控制：

- `fetchRemoteModelsLoading`：远程获取模型按钮的 loading
- `clearRemoteModelsLoading`：清除远程模型图标按钮的 loading
- `showModal`：新增模型弹窗是否打开

这些状态只影响头部工具栏自己的 UI，不属于全局模型数据状态。

### 6. 搜索重置逻辑

组件有一个重要副作用：

```ts
useEffect(() => {
  useAiInfraStore.setState({ modelSearchKeyword: '' });
}, [provider]);
```

含义是：当切换 provider 时，自动清空模型搜索关键词。

这是合理的，因为不同 provider 的模型列表不同，如果保留上一个 provider 的搜索词，切换后可能导致新 provider 的列表看起来“莫名为空”。所以这里在 `provider` 变化时把搜索状态重置。

### 7. 响应式布局

组件使用：

```ts
const mobile = useIsMobile();
```

根据是否移动端调整布局。

外层 `Flexbox` 是 sticky 的：

```ts
position: 'sticky',
top: mobile ? -2 : -32,
zIndex: 15,
```

并设置背景色：

```ts
background: cssVar.colorBgContainer
```

这表示模型列表顶部工具栏会在滚动时保持吸附，避免用户滚动长模型列表时丢失搜索和操作入口。

桌面端：

- 搜索框放在标题栏右侧操作区
- 标题、总数、操作按钮在同一行

移动端：

- 标题和按钮在第一行
- 搜索框单独渲染在下一行，并使用 `variant="filled"`

对应代码：

```tsx
{!mobile && (
  <Search
    value={searchKeyword}
    onChange={(value) => {
      useAiInfraStore.setState({ modelSearchKeyword: value });
    }}
  />
)}
```

以及：

```tsx
{mobile && (
  <Search
    value={searchKeyword}
    variant={'filled'}
    onChange={(value) => {
      useAiInfraStore.setState({ modelSearchKeyword: value });
    }}
  />
)}
```

### 8. Search 子组件

`ModelTitle` 引入：

```ts
import Search from './Search';
```

同目录的 `Search.tsx` 是一个封装过的搜索输入框。它内部使用 `SearchBar` 和 `useDebounce`，会把输入变更延迟 `200ms` 后再通知父组件。

这意味着：

- 用户输入时，`Search` 先维护自己的 `localValue`
- 经过 debounce 后调用 `onChange`
- `ModelTitle` 的 `onChange` 再写入 `useAiInfraStore.modelSearchKeyword`
- 父级 `ModelList` 根据 `modelSearchKeyword` 决定是否展示搜索结果

`Search` 还处理了外部 `value` 变化同步到本地输入框的问题，避免 provider 切换清空关键词时输入框不同步。

### 9. 远程获取模型

当 `showModelFetcher` 为 `true` 时显示远程获取按钮：

```tsx
<Button
  icon={LucideRefreshCcwDot}
  loading={fetchRemoteModelsLoading}
  size={'small'}
  onClick={async () => {
    setFetchRemoteModelsLoading(true);
    try {
      await fetchRemoteModelList(provider);
    } catch (e) {
      console.error(e);
    }
    setFetchRemoteModelsLoading(false);
  }}
>
```

点击后流程是：

1. 设置 `fetchRemoteModelsLoading = true`
2. 调用 `fetchRemoteModelList(provider)`
3. 如果出错，打印 `console.error(e)`
4. 设置 `fetchRemoteModelsLoading = false`

根据 store action，`fetchRemoteModelList` 内部会：

1. 动态 import `@/services/models`
2. 调用 `modelsService.getModels(providerId)`
3. 把远程返回的 model 映射成 `AiProviderModelListItem` 结构
4. 标记 `source: 'remote'`
5. 设置默认 `type: model.type || 'chat'`
6. 调用 `batchUpdateAiModels`
7. 刷新模型列表

所以这个按钮不是简单刷新本地列表，而是主动去远程服务获取 provider 支持的模型定义，并写入当前 provider 的模型配置。

### 10. 清除远程模型

当 `hasRemoteModels` 为 `true` 时，总数旁边会显示一个 `CircleX` 图标按钮：

```tsx
{hasRemoteModels && (
  <ActionIcon
    icon={CircleX}
    loading={clearRemoteModelsLoading}
    size={'small'}
    title={t('providerModels.list.fetcher.clear')}
    onClick={async () => {
      setClearRemoteModelsLoading(true);
      await clearObtainedModels(provider);
      setClearRemoteModelsLoading(false);
    }}
  />
)}
```

这里的 `clearObtainedModels` 实际来自：

```ts
s.clearRemoteModels
```

根据 store action，它会调用：

```ts
aiModelService.clearRemoteModels(provider);
```

然后刷新模型列表。

所以这个按钮只针对远程来源模型，不等同于“清空全部模型”。

### 11. 新增模型弹窗

当 `showAddNewModel` 为 `true` 时显示新增按钮：

```tsx
<Button
  icon={PlusIcon}
  size={'small'}
  onClick={() => {
    setShowModal(true);
  }}
/>
<CreateNewModelModal open={showModal} setOpen={setShowModal} />
```

点击后打开：

```ts
../CreateNewModelModal
```

这个 modal 负责实际新增模型表单，`ModelTitle` 只负责打开/关闭入口。

注意 `CreateNewModelModal` 被放在按钮旁边一起渲染，但它的可见性由 `open={showModal}` 控制。

### 12. 重置全部模型

更多菜单里只有一个菜单项：

```tsx
<DropdownMenu
  items={[
    {
      key: 'reset',
      label: t('providerModels.list.resetAll.title'),
      onClick: async () => {
        modal.confirm({
          content: t('providerModels.list.resetAll.conform'),
          onOk: async () => {
            await clearModelsByProvider(provider);
            message.success(t('providerModels.list.resetAll.success'));
          },
          title: t('providerModels.list.resetAll.title'),
        });
      },
    },
  ]}
>
  <Button icon={EllipsisVertical} size={'small'} />
</DropdownMenu>
```

点击菜单项后不会立即清空，而是先弹出确认框。用户确认后：

1. 调用 `clearModelsByProvider(provider)`
2. 成功后显示 `message.success`

根据 store action，`clearModelsByProvider` 会调用：

```ts
aiModelService.clearModelsByProvider(provider);
```

然后刷新模型列表。

它和 `clearRemoteModels` 的区别是：

- `clearRemoteModels`：只清理远程获取的模型
- `clearModelsByProvider`：清空该 provider 下的模型配置，范围更大，所以需要确认弹窗

## 上下游关系

### 上游：谁调用它

直接调用方是：

`src/routes/(main)/settings/provider/features/ModelList/index.tsx`

父组件中这样使用：

```tsx
<ModelTitle
  provider={id}
  showAddNewModel={showAddNewModel}
  showModelFetcher={showModelFetcher}
/>
```

这里的 `id` 就是当前 provider id。

`ModelList` 自身接收：

```ts
interface ModelListProps extends ProviderSettingsContextValue {
  id: string;
}
```

并把这些配置放进 `ProviderSettingsContext`：

```tsx
<ProviderSettingsContext
  value={{ modelEditable, sdkType, showAddNewModel, showDeployName, showModelFetcher }}
>
```

同时也把其中两个配置继续传给 `ModelTitle`：

- `showAddNewModel`
- `showModelFetcher`

这说明某些 provider 的模型列表页面可能不允许新增模型，或者不支持远程拉取模型列表。

更上层的配置来源之一是：

`src/routes/(main)/settings/provider/features/ProviderConfig/index.tsx`

其中 `ProviderConfigProps` 有：

```ts
modelList?: {
  azureDeployName?: boolean;
  notFoundContent?: ReactNode;
  placeholder?: string;
  showModelFetcher?: boolean;
};
```

根据当前片段推断，provider 配置页可以通过 `modelList.showModelFetcher` 控制模型列表是否展示远程获取按钮。依据是 `ProviderConfigProps` 中存在该字段，而 `ModelList` 和 `ModelTitle` 都接收 `showModelFetcher`。

### 下游：它调用谁

`ModelTitle` 的下游主要有三类。

第一类是 UI 子组件：

- `./Search`
- `../CreateNewModelModal`

`Search` 负责搜索输入框和 debounce；`CreateNewModelModal` 负责新增模型弹窗。

第二类是 store selector：

- `aiModelSelectors.totalAiProviderModelList`
- `aiModelSelectors.isEmptyAiProviderModelList`
- `aiModelSelectors.hasRemoteModels`

这些 selector 都基于 `useAiInfraStore` 中的 `aiProviderModelList`。

第三类是 store action：

- `fetchRemoteModelList`
- `clearRemoteModels`
- `clearModelsByProvider`
- `useFetchAiProviderModels`

它们最终会访问 service 层，例如：

- `aiModelService.getAiProviderModelList`
- `aiModelService.clearRemoteModels`
- `aiModelService.clearModelsByProvider`
- `modelsService.getModels`

### 和列表内容的关系

`ModelTitle` 不直接过滤列表，但它写入：

```ts
modelSearchKeyword
```

父级 `ModelList` 的 `Content` 会读取这个字段：

```ts
const [isSearching, isEmpty, useFetchAiProviderModels] = useAiInfraStore((s) => [
  !!s.modelSearchKeyword,
  aiModelSelectors.isEmptyAiProviderModelList(s),
  s.useFetchAiProviderModels,
]);
```

如果 `isSearching` 为 `true`，`Content` 渲染：

```tsx
<SearchResult />
```

否则再根据是否为空渲染：

```tsx
<EmptyModels provider={id} />
```

或正常列表：

```tsx
<EnabledModelList activeTab={currentActiveTab} />
<DisabledModels activeTab={currentActiveTab} providerId={id} />
```

所以搜索流程是跨组件完成的：

- `ModelTitle` 负责输入和写 store
- `ModelList.Content` 负责根据 store 切换到搜索结果视图
- `SearchResult` 负责展示搜索后的模型结果

### 和 provider 切换的关系

`ModelTitle` 在 `provider` 变化时清空搜索词：

```ts
useEffect(() => {
  useAiInfraStore.setState({ modelSearchKeyword: '' });
}, [provider]);
```

这使它和 provider 切换强绑定。每切换一个 provider，顶部搜索框和下面的搜索结果状态都会被重置。

## 运行/调用流程

### 页面进入某个 provider 的模型列表

1. 上层 provider 设置页确定当前 provider id。
2. `ModelList` 接收 `id`，渲染 `ModelTitle provider={id}`。
3. `ModelTitle` 调用 `useFetchAiProviderModels(provider)`。
4. `useFetchAiProviderModels` 通过 SWR 请求当前 provider 的模型列表。
5. 请求未完成时，`ModelTitle` 显示标题和按钮区域的 `Skeleton`。
6. 请求成功后，store 中的 `aiProviderModelList` 被更新。
7. `ModelTitle` 从 selector 得到模型总数、是否为空、是否有远程模型。
8. 页面显示标题、总数、搜索框和操作按钮。

### 用户搜索模型

1. 用户在 `Search` 输入关键词。
2. `Search` 内部先更新 `localValue`。
3. `useDebounce` 等待约 `200ms`。
4. `Search` 调用 `onChange(debouncedValue)`。
5. `ModelTitle` 执行：

   ```ts
   useAiInfraStore.setState({ modelSearchKeyword: value });
   ```

6. `ModelList.Content` 读取到 `modelSearchKeyword` 非空。
7. `Content` 渲染 `SearchResult`。
8. 搜索结果基于 `aiModelSelectors.filteredAiProviderModelList` 过滤模型。该 selector 会匹配：

   - `model.id`
   - `model.displayName`

### 用户切换 provider

1. `ModelTitle` 的 `provider` prop 变化。
2. `useEffect` 执行。
3. `modelSearchKeyword` 被重置为空字符串。
4. 搜索框同步清空。
5. `useFetchAiProviderModels(provider)` 使用新的 provider id 加载模型列表。
6. 列表内容也切换到新 provider 对应的数据。

### 用户点击“获取远程模型”

1. 用户点击带 `LucideRefreshCcwDot` 图标的按钮。
2. `fetchRemoteModelsLoading` 设置为 `true`。
3. 调用 `fetchRemoteModelList(provider)`。
4. store action 调用远程模型服务获取模型定义。
5. 返回的模型被转换成内部模型项，标记 `source: 'remote'`。
6. 调用批量更新，并刷新模型列表。
7. `fetchRemoteModelsLoading` 设置为 `false`。
8. UI 中模型总数和列表内容随 store 刷新而更新。
9. 如果现在列表中存在远程模型，总数旁边会出现清除图标。

### 用户点击“清除远程模型”

1. 只有 `hasRemoteModels` 为 `true` 时才会显示清除按钮。
2. 用户点击 `CircleX` 图标。
3. `clearRemoteModelsLoading` 设置为 `true`。
4. 调用 `clearRemoteModels(provider)`。
5. service 层清除该 provider 的远程来源模型。
6. 刷新模型列表。
7. `clearRemoteModelsLoading` 设置为 `false`。
8. 如果远程模型已清空，清除按钮消失。

### 用户点击“新增模型”

1. 用户点击 `PlusIcon` 按钮。
2. `showModal` 设置为 `true`。
3. `CreateNewModelModal` 打开。
4. 新增表单的具体逻辑由 `CreateNewModelModal` 处理。
5. 关闭弹窗时通过 `setOpen={setShowModal}` 回写状态。

### 用户点击“重置全部模型”

1. 用户点击 `EllipsisVertical` 更多按钮。
2. 下拉菜单显示 `reset` 菜单项。
3. 用户点击重置。
4. 调用 `modal.confirm` 弹出确认框。
5. 用户确认后执行：

   ```ts
   await clearModelsByProvider(provider);
   ```

6. 清空当前 provider 的模型配置。
7. 刷新模型列表。
8. 显示成功消息。

## 小白阅读顺序

1. 先看组件 props：

   ```ts
   interface ModelFetcherProps {
     provider: string;
     showAddNewModel?: boolean;
     showModelFetcher?: boolean;
   }
   ```

   先理解这个组件只关心当前 provider，以及两个按钮是否显示。

2. 再看 store 取值：

   ```ts
   useAiInfraStore((s) => [
     s.modelSearchKeyword,
     aiModelSelectors.totalAiProviderModelList(s),
     aiModelSelectors.isEmptyAiProviderModelList(s),
     aiModelSelectors.hasRemoteModels(s),
     s.fetchRemoteModelList,
     s.clearRemoteModels,
     s.clearModelsByProvider,
     s.useFetchAiProviderModels,
   ])
   ```

   这一段决定了组件的数据来源和能触发的动作。

3. 然后看加载态：

   ```ts
   const { isLoading } = useFetchAiProviderModels(provider);
   ```

   这是理解页面首次进入时为什么显示骨架屏的关键。

4. 接着看 `useEffect`：

   ```ts
   useEffect(() => {
     useAiInfraStore.setState({ modelSearchKeyword: '' });
   }, [provider]);
   ```

   它解释了为什么切换 provider 后搜索词会被清空。

5. 再看 JSX 最外层 `Flexbox`：

   ```tsx
   <Flexbox
     gap={12}
     paddingBlock={8}
     style={{
       background: cssVar.colorBgContainer,
       marginTop: mobile ? 0 : -12,
       paddingTop: mobile ? 0 : 20,
       position: 'sticky',
       top: mobile ? -2 : -32,
       zIndex: 15,
     }}
   >
   ```

   这能帮助你理解它为什么是一个吸顶工具栏。

6. 然后按 UI 区块看：

   - 左侧标题和总数
   - 桌面端搜索框
   - 获取远程模型按钮
   - 新增模型按钮
   - 更多菜单
   - 移动端搜索框

7. 最后再跳到父组件：

   `src/routes/(main)/settings/provider/features/ModelList/index.tsx`

   看 `ModelTitle` 和 `Content` 的组合方式。这样就能明白：`ModelTitle` 负责控制条件，`Content` 负责展示列表内容。

## 常见误区

1. **误以为 `ModelTitle` 负责渲染模型列表**

   它只负责标题、搜索和操作按钮。真正的模型列表由 `ModelList/index.tsx` 里的 `Content` 以及 `EnabledModelList`、`DisabledModels` 等组件渲染。

2. **误以为搜索过滤发生在 `ModelTitle` 内部**

   `ModelTitle` 只写入 `modelSearchKeyword`。过滤逻辑在 selector 中：

   ```ts
   aiModelSelectors.filteredAiProviderModelList
   ```

   搜索结果页面由 `SearchResult` 负责展示。

3. **误以为 `clearRemoteModels` 和 `clearModelsByProvider` 一样**

   它们范围不同：

   - `clearRemoteModels(provider)`：清除远程来源模型
   - `clearModelsByProvider(provider)`：清空该 provider 的模型配置

   后者影响更大，所以通过 `modal.confirm` 二次确认。

4. **误以为 `showModelFetcher` 只控制 loading**

   `showModelFetcher` 控制的是“获取远程模型”按钮是否渲染。即使模型列表可以加载，也不代表一定允许用户手动远程拉取模型。

5. **误以为 `showAddNewModel` 影响新增弹窗逻辑本身**

   在这个文件里，它只控制新增按钮和 `CreateNewModelModal` 是否渲染。新增模型的表单、提交、校验逻辑在 `CreateNewModelModal` 内部。

6. **误以为 provider 切换后搜索词保留是 bug**

   实际上代码明确在 provider 变化时清空搜索词。这是为了避免上一个 provider 的搜索条件影响当前 provider 的模型列表。

7. **误以为 `isEmpty` 时整个标题栏不显示**

   不是。`isEmpty` 只影响右侧操作区的部分展示：

   ```tsx
   isEmpty ? null : (...)
   ```

   标题区域仍然会显示。空列表内容由父组件 `Content` 渲染 `EmptyModels`。

8. **误以为移动端和桌面端用的是两个不同搜索逻辑**

   移动端和桌面端都使用同一个 `Search` 组件，也都写入同一个 `modelSearchKeyword`。区别只是布局位置和移动端传了：

   ```tsx
   variant={'filled'}
   ```

9. **误以为远程获取失败会显示错误提示**

   当前代码只做了：

   ```ts
   console.error(e);
   ```

   没有调用 `message.error` 或其他用户可见提示。因此用户界面上未必能看到失败原因。

10. **误以为 `hasRemoteModels` 是针对当前 provider 之外的全局远程模型**

   根据当前 selector，它检查的是 store 中当前 `aiProviderModelList` 是否存在 `source === AiModelSourceEnum.Remote` 的模型。由于 `aiProviderModelList` 是通过当前 provider 加载进 store 的列表，所以在这个页面上下文里可以理解为“当前 provider 的模型列表中是否存在远程来源模型”。
