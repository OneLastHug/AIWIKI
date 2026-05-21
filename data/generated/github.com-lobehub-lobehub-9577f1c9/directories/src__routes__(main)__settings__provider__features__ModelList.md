# 目录：src/routes/(main)/settings/provider/features/ModelList

## 它负责什么

`ModelList` 是“设置 → 模型服务商 provider 详情页”里的模型列表管理区域。它负责把某个 provider 下的模型拉取出来，并提供一整套面向用户的模型管理能力：

- 展示模型总数、搜索框、刷新远程模型、清空远程模型、重置 provider 模型配置。
- 按模型类型分 Tab：`all`、`chat`、`image`、`video`、`embedding`、`stt`、`tts`。
- 分区展示已启用模型和已禁用模型。
- 对模型执行启用、禁用、批量启用、批量禁用、删除、自定义新增、编辑配置、排序等操作。
- 在移动端和桌面端采用不同布局，例如移动端搜索框单独占一行，模型项布局更紧凑。
- 通过 `ProviderSettingsContext` 接收 provider 级别配置，控制是否允许编辑模型、是否显示新增模型、是否显示远程拉取按钮、是否显示部署名字段等。

从目录位置看，它仍属于 `src/routes/(main)/settings/provider/features` 下的路由内 feature，而不是全局 `src/features`。根据当前片段推断，这是这个设置页面较早或局部化的 feature 组织方式；它被 provider detail 页面直接引用。

## 关键组成

### `index.tsx`

这是目录主入口，默认导出 `ModelList`。

它的外层组件接收：

- `id`：当前 provider id。
- `showModelFetcher`：是否显示“获取/刷新远程模型”按钮。
- `sdkType`：SDK 类型，传入上下文供子组件使用。
- `showAddNewModel`：是否显示新增模型按钮。
- `showDeployName`：新增/编辑模型时是否展示 deployment name 字段。
- `modelEditable`：是否允许编辑模型，默认 `true`。

`ModelList` 主要做三件事：

1. 用 `ProviderSettingsContext` 把 provider 设置传给后代组件。
2. 渲染顶部 `ModelTitle`。
3. 在 `Suspense` 中渲染内部 `Content`，加载中使用 `SkeletonList`。

内部 `Content` 负责真实列表逻辑：

- 从 `useAiInfraStore` 读取 `modelSearchKeyword`、`useFetchAiProviderModels`。
- 用 `aiModelSelectors.filteredAiProviderModelList` 拿当前 provider 过滤后的模型。
- 调用 `useFetchAiProviderModels(id)` 拉取 provider 模型列表。
- 根据模型 `type` 统计数量，生成带 icon 和数量的 Tabs。
- 搜索中显示 `SearchResult`。
- 加载中显示 `SkeletonList`。
- 空列表显示 `EmptyModels`。
- 普通状态显示 `EnabledModelList` 和 `DisabledModels`。

这里有一个重要细节：Tab 的数量统计基于 `filteredAiProviderModelList`，注释写的是“all models, not just enabled”。因此 Tab 是按当前 provider 的全部过滤结果统计，而不是只统计启用模型。

### `ProviderSettingsContext.ts`

定义了 `ProviderSettingsContextValue`：

- `modelEditable?: boolean`
- `sdkType?: string`
- `showAddNewModel?: boolean`
- `showDeployName?: boolean`
- `showModelFetcher?: boolean`

这个 context 是本目录的轻量配置总线。`ModelList` 顶层写入，`EnabledModelList`、`ModelItem`、`CreateNewModelModal`、`ModelConfigModal` 等组件读取。

它不保存业务状态，只保存“这个 provider 页面允许哪些能力”的 UI/行为开关。

### `ModelTitle/index.tsx`

这是列表头部区域。

它从 `useAiInfraStore` 读取：

- `modelSearchKeyword`
- `totalAiProviderModelList`
- `isEmptyAiProviderModelList`
- `hasRemoteModels`
- `fetchRemoteModelList`
- `clearRemoteModels`
- `clearModelsByProvider`
- `useFetchAiProviderModels`

它负责：

- 显示标题和模型总数。
- provider 变化时清空 `modelSearchKeyword`。
- 显示搜索框，桌面端在右侧，移动端在下一行。
- 点击刷新按钮调用 `fetchRemoteModelList(provider)`。
- 如果存在远程模型，显示清除按钮，调用 `clearRemoteModels(provider)`。
- 点击新增按钮打开 `CreateNewModelModal`。
- 通过下拉菜单提供 reset 操作，确认后调用 `clearModelsByProvider(provider)`。

这里的错误处理比较轻：`fetchRemoteModelList` 的 catch 只是 `console.error(e)`，没有对用户展示失败提示。阅读时不要误以为这里有完整错误 UI。

### `EnabledModelList/index.tsx`

展示已启用模型区域。

核心数据来自：

- `aiModelSelectors.enabledAiProviderModelList`
- `batchToggleAiModels`

主要逻辑：

- 根据 `activeTab` 过滤已启用模型。
- 如果 `activeTab === 'all'`，展示全部已启用模型。
- 否则只展示 `model.type === activeTab` 的模型。
- 顶部显示“已启用”标题。
- 如果列表非空，右侧显示批量禁用按钮和排序按钮。
- 批量禁用调用 `batchToggleAiModels(ids, false)`。
- 排序打开 `SortModelModal`。
- 空状态区分两种：
  - 已启用模型整体为空：显示 enabled empty。
  - 当前分类没有模型：显示 no models in category。
- 每个模型交给 `ModelItem` 渲染。

有一个容易忽略的规则：当 `modelEditable` 为 false 时，`embedding` 模型不会出现在可批量切换列表里。对应逻辑是：

```ts
modelEditable ? filteredModels : filteredModels.filter((model) => model.type !== 'embedding')
```

也就是说，`modelEditable` 不只是影响“编辑按钮”，还影响某些模型类型的启停能力。

### `DisabledModels.tsx`

展示禁用模型区域，逻辑比启用区更复杂。

它从 store 先拿：

- `aiModelSelectors.disabledAiProviderModelList`

然后用 `useSWRInfinite` 在需要时继续远程分页加载禁用模型：

- service：`aiModelService.getAiProviderModelList`
- 参数：`enabled: false`
- 分页大小：`PAGE_SIZE = 30`
- offset：`disabledModels.length + pageIndex * PAGE_SIZE`

它的加载策略分两层：

1. 先显示 store 中已有的禁用模型，但首屏最多显示 `PAGE_SIZE` 条。
2. 用户滚动到底部时，通过 `IntersectionObserver` 增加本地可见数量。
3. 当 store 里的禁用模型都展示完后，才启用 SWR 远程分页加载更多禁用模型。

这样设计的目的，是避免禁用模型很多时首屏一次性渲染太多，同时又能在已有 store 数据耗尽后继续从服务端拿更多。

它还支持禁用模型排序，排序状态保存在 `useGlobalStore` 的 system status 中：

- `default`
- `alphabetical`
- `alphabeticalDesc`
- `releasedAt`
- `releasedAtDesc`

排序入口是右侧 `DropdownMenu`，当前排序项用 `LucideCheck` 标记。

禁用列表也会按 `activeTab` 过滤，所以 Tab 不只影响启用区，也影响禁用区。

### `ModelItem.tsx`

这是单个模型行的核心渲染组件，接收 `AiProviderModelListItem`，并额外要求：

- `id`
- `enabled`
- `isAzure?`
- `releasedAt?`
- `removed?`

它负责展示：

- 模型图标：`ModelIcon`
- 显示名：`displayName || id`
- 模型 id 标签，点击复制 id
- 新模型 badge：`NewModelBadge`
- 发布时间
- 价格信息
- 能力标签：`ModelInfoTags`
- 启停开关：`Switch`
- 编辑按钮
- 删除按钮

它从 `useAiInfraStore` 读取：

- `activeAiProvider`
- `isModelLoading(id)`
- `toggleModelEnabled`
- `removeAiModel`

启停时调用：

```ts
toggleModelEnabled({ enabled: e, id, source, type })
```

删除时有保护：只有 `source !== AiModelSourceEnum.Builtin` 的模型才显示删除按钮。内置模型不能删除。

价格展示根据 `type` 分支处理：

- `chat`：输入 token、输出 token。
- `embedding`：输入 token。
- `tts`：音频输入字符。
- `stt`：音频输入分钟。
- `image` 和默认分支：不展示价格。

编辑按钮打开 `ModelConfigModal`。新增和编辑复用同一个表单组件 `CreateNewModelModal/Form.tsx`，只是编辑时 `idEditable={false}`，且传入当前模型作为 `initialValues`。

### `CreateNewModelModal`

包含：

- `CreateNewModelModal/index.tsx`
- `CreateNewModelModal/Form.tsx`
- `CreateNewModelModal/ExtendParamsSelect.tsx`

`index.tsx` 是新增模型弹窗，读取：

- `activeAiProvider`
- `createNewAiModel`

确认时：

1. 从 form 中读取字段。
2. `validateFields()`。
3. 调用 `createNewAiModel({ ...data, providerId: editingProvider })`。
4. 成功后关闭弹窗。

`Form.tsx` 是模型配置表单，字段包括：

- `id`
- `config.deploymentName`
- `displayName`
- `contextWindowTokens`
- `settings.extendParams`
- `abilities.functionCall`
- `abilities.vision`
- `abilities.reasoning`
- `abilities.search`
- `abilities.imageOutput`
- `abilities.video`
- `type`

`type` 选项来自 `model-bank` 的 `AiModelType` 语义，当前列出了：

- `chat`
- `embedding`
- `tts`
- `stt`
- `image`
- `video`
- `text2music`
- `realtime`

`showDeployName` 控制是否展示 deployment name 字段，通常对 Azure 这类 provider 更重要。

### `ModelConfigModal/index.tsx`

这是编辑模型配置弹窗。

它复用 `CreateNewModelModal/Form`，但有几个差异：

- 标题来自 `setting` namespace：`llm.customModelCards.modelConfig.modalTitle`。
- 根据 `id` 通过 `aiModelSelectors.getAiModelById(id)` 读取模型。
- 表单 `initialValues={model}`。
- `idEditable={false}`，不能改模型 id。
- 确认时调用 `updateAiModelsConfig(id, editingProvider, data)`。

因此，新增模型和编辑模型在 UI 字段上基本一致，但写入动作不同。

### `SortModelModal`

用于调整已启用模型顺序。

它接收：

- `defaultItems`
- `open`
- `onCancel`

内部使用 `@lobehub/ui` 的 `SortableList`，拖拽后更新本地 `items`。点击确认时构造：

```ts
items.map((item, index) => ({
  id: item.id,
  sort: index,
  type: item.type,
}))
```

然后调用：

```ts
updateAiModelsSort(providerId, sortMap)
```

排序成功后显示成功消息并关闭弹窗。

这里排序只从 `EnabledModelList` 打开，传入的是 `enabledModels`，所以它主要管理“已启用模型”的展示顺序，而不是全部模型顺序。

### `SearchResult.tsx`

当 `modelSearchKeyword` 非空时，`Content` 不再展示启用/禁用分区，而是展示搜索结果。

它读取：

- `modelSearchKeyword`
- `aiModelSelectors.filteredAiProviderModelList`
- `batchToggleAiModels`

行为：

- 显示搜索结果数量。
- 如果结果不为空，提供批量启用按钮，调用 `batchToggleAiModels(ids, true)`。
- 如果搜索词存在但结果为空，显示搜索无结果。
- 每个搜索结果仍用 `ModelItem` 渲染。

注意：搜索模式下不会显示 `EnabledModelList` 和 `DisabledModels` 的两个分区，而是统一列表。

### 其他文件

`EmptyModels.tsx` 根据文件名和调用位置可知用于 provider 模型为空时的空状态。结合 `ModelTitle` 和 `rg` 结果，它也会调用 `fetchRemoteModelList(provider)`，用于引导用户拉取远程模型。这里没有完整阅读该文件，因此细节属于根据当前片段推断。

`SkeletonList.tsx` 是加载占位组件，用在初始加载和 `Suspense fallback`。

`ModelTitle/Search.tsx` 是搜索框组件，`ModelTitle/Search.test.tsx` 是它的测试文件，测试名为 `ModelList Search`。

## 上下游关系

### 上游调用方

根据搜索结果，`ModelList` 主要被 provider detail 页面引用：

- `src/routes/(main)/settings/provider/detail/default/index.tsx`
- `src/routes/(main)/settings/provider/detail/default/ClientMode.tsx`

其中默认详情页大致是：

```tsx
<ModelList id={card.id} {...card.settings} />
```

也就是说，provider 配置卡片里的 `settings` 会直接展开传给 `ModelList`，控制当前 provider 的模型管理能力。

`ClientMode.tsx` 则使用：

```tsx
<ModelList id={id} />
```

说明也存在一种只依赖 provider id、使用默认行为的客户端模式。

### 下游依赖

这个目录主要依赖几类下游模块。

第一类是状态层：

- `@/store/aiInfra`
- `@/store/aiInfra/selectors`
- `@/store/global`
- `@/store/global/selectors`

`aiInfra` 是核心状态来源，提供当前 provider 的模型列表、搜索词、加载状态，以及模型增删改查、启停、排序、远程拉取等动作。

`global` 在这里主要保存禁用模型排序偏好：`disabledModelsSortType`。

第二类是服务层：

- `@/services/aiModel`

`DisabledModels` 直接调用 `aiModelService.getAiProviderModelList` 分页获取禁用模型。其他大部分数据操作通过 `useAiInfraStore` action 间接完成。

第三类是模型类型与数据结构：

- `model-bank`
- `AiProviderModelListItem`
- `AiModelSourceEnum`
- `AiModelType`

这说明模型列表的数据形状不是本目录自定义的，而是来自共享模型库。

第四类是 UI 与工具：

- `@lobehub/ui`
- `antd`
- `antd-style`
- `lucide-react`
- `@lobehub/icons`
- `react-i18next`
- `swr/infinite`

其中 `@lobehub/ui` 提供 `Flexbox`、`ActionIcon`、`Modal`、`SortableList`、`Tabs` 等主要 UI。`antd` 负责 `Form`、`Switch`、`Checkbox`、`Select`、`App` 消息/确认弹窗等能力。`react-i18next` 负责所有显示文本。

## 运行/调用流程

一次典型渲染流程如下：

1. provider detail 页面渲染 `ModelList`，传入 `id` 和 provider settings。
2. `ModelList` 把 settings 放入 `ProviderSettingsContext`。
3. `ModelTitle` 渲染标题、总数、搜索框、刷新、新增、重置等操作。
4. `Content` 调用 `useFetchAiProviderModels(id)` 拉取当前 provider 模型。
5. 如果正在加载，显示 `SkeletonList`。
6. 如果 `modelSearchKeyword` 非空，进入搜索模式，显示 `SearchResult`。
7. 如果模型列表为空，显示 `EmptyModels`。
8. 如果有模型，先根据全部模型的 `type` 生成 Tabs。
9. 当前 Tab 下方展示 `EnabledModelList`。
10. 再展示 `DisabledModels`。
11. 用户点击某个模型的开关时，`ModelItem` 调用 `toggleModelEnabled`。
12. 用户点击编辑时，打开 `ModelConfigModal`，提交后调用 `updateAiModelsConfig`。
13. 用户点击新增时，打开 `CreateNewModelModal`，提交后调用 `createNewAiModel`。
14. 用户点击启用区排序时，打开 `SortModelModal`，提交后调用 `updateAiModelsSort`。
15. 用户滚动禁用区底部时，`DisabledModels` 先增加本地可见数量，再通过 `useSWRInfinite` 远程加载更多禁用模型。

几个分支要特别注意：

- 搜索模式会替代正常的启用/禁用分区。
- Tab 过滤同时作用于启用列表和禁用列表。
- 禁用列表有本地 store 数据和远程分页数据的合并逻辑。
- `modelEditable=false` 时，不代表所有开关都消失；非 embedding 模型仍可能允许启停。
- 内置模型不能删除，但可以显示编辑入口，是否真的能改取决于 store action 和表单提交逻辑。

## 小白阅读顺序

1. 先读 `index.tsx`  
   目标是理解总入口：`ModelList` 如何包 context，`Content` 如何决定加载、搜索、空状态、正常列表。

2. 再读 `ProviderSettingsContext.ts`  
   先弄清楚 `modelEditable`、`showAddNewModel`、`showModelFetcher`、`showDeployName` 这些开关从哪里来、传给谁。

3. 读 `ModelTitle/index.tsx`  
   这里是用户最先看到的操作区。重点看搜索词如何写入 store，以及刷新、新增、重置分别调用哪个 action。

4. 读 `EnabledModelList/index.tsx`  
   理解已启用模型如何按 Tab 过滤、如何批量禁用、如何打开排序弹窗。

5. 读 `DisabledModels.tsx`  
   这是本目录最复杂的文件。建议重点看三块：分页加载、排序、Tab 过滤。不要一开始陷入 JSX 细节。

6. 读 `ModelItem.tsx`  
   这是所有列表共用的模型行。重点看启停、复制 id、价格展示、编辑、删除，以及移动端/桌面端布局差异。

7. 读 `CreateNewModelModal/Form.tsx`  
   这个表单是新增和编辑共用的。理解字段结构后，再回头看新增弹窗和编辑弹窗会更轻松。

8. 最后读 `SortModelModal/index.tsx`、`SearchResult.tsx`、`EmptyModels.tsx`  
   它们分别覆盖排序、搜索、空状态这些辅助流程。

## 常见误区

1. 误以为 `ModelList` 只展示模型  
   实际上它是模型管理中心，包含拉取远程模型、搜索、增删改、启停、排序、分页加载等完整交互。

2. 误以为 Tab 只过滤启用模型  
   Tab 同时影响 `EnabledModelList` 和 `DisabledModels`。搜索模式下则不走这两个分区。

3. 误以为禁用列表一次性来自 store  
   `DisabledModels` 先展示 store 中的禁用模型，再通过 `IntersectionObserver` 和 `useSWRInfinite` 分页加载更多远程禁用模型。

4. 误以为 `modelEditable=false` 会禁用全部模型开关  
   实际代码里，`modelEditable=false` 时主要限制 embedding 模型的切换，并隐藏编辑/删除动作；其他类型模型仍可能显示启停开关。

5. 误以为新增和编辑有两套表单  
   新增弹窗和编辑弹窗共用 `CreateNewModelModal/Form.tsx`。区别在于新增允许编辑 id，编辑时 `idEditable={false}` 且传入 `initialValues`。

6. 误以为删除按钮对所有模型都出现  
   `ModelItem` 中明确判断 `source !== AiModelSourceEnum.Builtin` 才显示删除按钮，内置模型不会显示删除操作。

7. 误以为排序是禁用和启用共用一套  
   已启用模型排序使用 `SortModelModal` 并调用 `updateAiModelsSort`。禁用模型排序是本地展示排序，排序偏好存在 `global` system status 中。

8. 误以为搜索结果保持启用/禁用分组  
   搜索时 `Content` 直接返回 `SearchResult`，不会再渲染启用区和禁用区。搜索结果是统一列表，并提供“批量启用”。

9. 误以为 `showDeployName` 只影响 Azure 页面标题  
   它实际传入表单，控制是否显示 `config.deploymentName` 字段。根据当前片段推断，它主要用于需要 deployment name 的 provider，例如 Azure。

10. 误以为这个目录管理 provider 的连接配置  
   它只管理 provider 下的模型列表。provider 的密钥、代理、连接检查等配置属于邻近的 `ProviderConfig` 等目录，不在 `ModelList` 的职责范围内。
