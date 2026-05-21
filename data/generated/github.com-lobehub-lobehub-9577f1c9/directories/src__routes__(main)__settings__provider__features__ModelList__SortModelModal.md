# 目录：src/routes/(main)/settings/provider/features/ModelList/SortModelModal

## 它负责什么

`SortModelModal` 是模型供应商设置页里“已启用模型列表”的自定义排序弹窗。它让用户通过拖拽调整当前 provider 下已启用模型的顺序，然后点击更新，把新的顺序写回后端并刷新模型列表。

它所在的功能链路大致是：

`Provider settings page` → `ModelList` → `EnabledModelList` → `SortModelModal` → `useAiInfraStore.updateAiModelsSort` → `aiModelService.updateAiModelOrder` → `lambdaClient.aiModel.updateAiModelOrder` → `ctx.aiModelModel.updateModelsOrder`

这个目录只包含两个文件：

- `index.tsx`：弹窗主体，管理拖拽后的列表状态、提交按钮、调用 store action。
- `ListItem.tsx`：排序列表里的单行展示组件，负责显示模型图标、模型名称和拖拽手柄。

它不负责模型数据获取、tab 过滤、启用/禁用逻辑，也不直接访问数据库。它只消费父组件传入的 `defaultItems`，并在用户确认后提交排序结果。

## 关键组成

`index.tsx` 导出默认组件 `SortModelModal`。

组件 props 是：

```ts
interface SortModelModalProps {
  defaultItems: AiProviderModelListItem[];
  onCancel: () => void;
  open: boolean;
}
```

含义分别是：

- `defaultItems`：初始排序列表，类型来自 `model-bank` 的 `AiProviderModelListItem[]`。
- `open`：控制 `Modal` 是否打开。
- `onCancel`：关闭弹窗的回调，既用于取消，也用于提交成功后关闭。

组件内部依赖：

- `@lobehub/ui` 的 `Modal`、`SortableList`、`Button`、`Flexbox`。
- `antd` 的 `App.useApp()`，用于提交成功后显示 `message.success`。
- `antd-style` 的 `createStaticStyles`，定义拖拽行的 hover 背景和布局样式。
- `react-i18next` 的 `useTranslation('modelProvider')`，读取 `sortModal.title`、`sortModal.update`、`sortModal.success`。
- `useAiInfraStore`，取出：
  - `activeAiProvider`：当前正在配置的 provider id。
  - `updateAiModelsSort`：提交模型排序的 store action。

核心状态：

```ts
const [items, setItems] = useState(defaultItems);
const [loading, setLoading] = useState(false);
```

`items` 是弹窗内当前拖拽顺序。`SortableList` 的 `onChange` 会把拖拽后的数组写入 `items`。点击更新按钮时，组件把 `items` 转成后端需要的排序映射：

```ts
const sortMap = items.map((item, index) => ({
  id: item.id,
  sort: index,
  type: item.type,
}));
```

这里提交的是 `id`、`sort` 和可选的 `type`。`sort` 使用数组下标，从 `0` 开始。

`ListItem.tsx` 导出默认组件 `ListItem`，接收完整的 `AiProviderModelListItem`，但实际只使用：

- `id`
- `displayName`

渲染内容是：

- `ModelIcon model={id} size={24} type="avatar"`：根据模型 id 展示模型图标。
- `{displayName || id}`：优先展示模型显示名，缺失时回退到模型 id。
- `SortableList.DragHandle`：拖拽手柄。

`ListItem` 本身不处理点击、排序、保存逻辑，只是 `SortableList.Item` 的视觉内容。

## 上下游关系

上游调用方是：

`src/routes/(main)/settings/provider/features/ModelList/EnabledModelList/index.tsx`

`EnabledModelList` 做了几件事：

- 从 `useAiInfraStore(aiModelSelectors.enabledAiProviderModelList, isEqual)` 取出所有已启用模型。
- 根据 `activeTab` 计算 `filteredModels`，用于页面上的分类展示。
- 在已启用模型标题右侧渲染排序按钮 `ActionIcon`，图标是 `ArrowDownUpIcon`。
- 点击排序按钮后执行 `setOpen(true)`。
- 当 `open` 为 true 时挂载 `SortModelModal`：

```tsx
<SortModelModal
  defaultItems={enabledModels}
  open={open}
  onCancel={() => {
    setOpen(false);
  }}
/>
```

一个细节是：排序弹窗拿到的是完整的 `enabledModels`，不是当前 tab 的 `filteredModels`。也就是说，即使用户当前只看 `chat` 或 `image` tab，打开排序弹窗时调整的是全部已启用模型的全局顺序，而不是某个分类内的局部顺序。

中游状态层是：

`src/store/aiInfra/slices/aiModel/action.ts`

相关 action 是：

```ts
updateAiModelsSort = async (id: string, items: AiModelSortMap[]): Promise<void> => {
  await aiModelService.updateAiModelOrder(id, items);
  await this.#get().refreshAiModelList();
};
```

它先调用 service 更新顺序，再刷新当前模型列表。刷新后，页面上的 `enabledModels` 会从新的 store 数据重新计算。

下游 service 是：

`src/services/aiModel/index.ts`

相关方法是：

```ts
updateAiModelOrder = async (providerId: string, items: AiModelSortMap[]) => {
  return lambdaClient.aiModel.updateAiModelOrder.mutate({ providerId, sortMap: items });
};
```

它通过 tRPC lambda client 调用后端 mutation。

后端 router 是：

`src/server/routers/lambda/aiModel.ts`

`updateAiModelOrder` 接收：

```ts
{
  providerId: string;
  sortMap: {
    id: string;
    sort: number;
    type?: AiModelType;
  }[];
}
```

然后调用：

```ts
ctx.aiModelModel.updateModelsOrder(input.providerId, input.sortMap)
```

数据库模型层是：

`packages/database/src/models/aiModel.ts`

`updateModelsOrder` 会在事务里遍历 `sortMap`，对每个模型执行 `insert ... onConflictDoUpdate`。根据当前片段推断，这样做的目的不是单纯更新已有行，而是确保内置模型或尚未有用户自定义记录的模型，也能因为排序行为被写入用户维度的 `aiModels` 表。依据是插入值包含 `enabled: true`、`id`、`providerId`、`sort`、`userId`，冲突目标是 `[aiModels.id, aiModels.userId, aiModels.providerId]`，冲突时只更新 `sort`、`updatedAt` 和可选 `type`。

类型来源是：

`packages/model-bank/src/types/aiModel.ts`

```ts
export interface AiModelSortMap {
  id: string;
  sort: number;
  type?: AiModelType;
}
```

i18n 文案在：

- `src/locales/default/modelProvider.ts`
- `locales/zh-CN/modelProvider.json`
- `locales/en-US/modelProvider.json`

相关 key 是：

- `sortModal.title`
- `sortModal.update`
- `sortModal.success`

中文分别是“自定义排序”“更新”“排序更新成功”。

## 运行/调用流程

1. 用户进入某个 provider 的模型设置页。

`ModelList` 接收 provider id，并通过 `Content` 调用 `useFetchAiProviderModels(id)` 加载模型列表。

2. `ModelList` 渲染 `EnabledModelList`。

`EnabledModelList` 从 `aiModelSelectors.enabledAiProviderModelList` 取出已启用模型。页面上会按当前 tab 展示 `filteredModels`，但排序入口始终基于完整的 `enabledModels`。

3. 用户点击排序图标。

`EnabledModelList` 里的 `ActionIcon` 执行 `setOpen(true)`，随后条件渲染 `SortModelModal`。因为组件是 `open && <SortModelModal ... />` 这种挂载方式，所以每次打开时 `useState(defaultItems)` 都会用当时最新的 `enabledModels` 初始化列表。

4. 弹窗展示拖拽列表。

`SortModelModal` 使用 `SortableList` 渲染 `items`。每个 item 包在 `SortableList.Item` 中，`id={item.id}` 作为排序项标识，内部交给 `ListItem` 展示图标、名称和拖拽手柄。

5. 用户拖拽调整顺序。

`SortableList` 的 `onChange` 收到新的 `items` 数组，执行 `setItems(items)`。此时变更只存在于弹窗本地 state，还没有写入 store 或后端。

6. 用户点击“更新”。

组件先检查 `providerId`：

```ts
if (!providerId) return;
```

如果当前没有 active provider，直接返回，不提交。正常情况下，组件会生成：

```ts
[
  { id: 'model-a', sort: 0, type: 'chat' },
  { id: 'model-b', sort: 1, type: 'image' },
]
```

然后：

- `setLoading(true)`
- `await updateAiModelsSort(providerId, sortMap)`
- `setLoading(false)`
- `message.success(t('sortModal.success'))`
- `onCancel()`

7. store action 刷新模型列表。

`updateAiModelsSort` 调用 service 后，会执行 `refreshAiModelList()`。因此排序提交成功后，页面上的模型列表会拿到后端更新后的顺序。

8. 后端持久化排序。

后端 tRPC router 校验入参，再调用数据库模型的 `updateModelsOrder`。数据库层在事务中逐条 upsert，保证每个模型的 `sort` 写入当前用户、当前 provider 的模型记录。

## 小白阅读顺序

1. 先看 `EnabledModelList/index.tsx`

重点看 `open` 状态、排序按钮、`SortModelModal` 的挂载位置，以及传入的 `defaultItems={enabledModels}`。这能先理解弹窗从哪里来、排序的是哪批模型。

2. 再看 `SortModelModal/index.tsx`

重点看三个部分：

- `useState(defaultItems)`：弹窗内部维护排序数组。
- `SortableList`：拖拽改变 `items`。
- 更新按钮 `onClick`：把 `items` 转成 `sortMap` 并调用 `updateAiModelsSort`。

3. 再看 `SortModelModal/ListItem.tsx`

这个文件很简单，只负责单行 UI。理解它后，就能把“列表容器”和“列表项展示”分开。

4. 接着看 `src/store/aiInfra/slices/aiModel/action.ts`

找到 `updateAiModelsSort`，看清楚 UI 不直接调 service，而是通过 store action。这个 action 还负责提交后刷新模型列表。

5. 再看 `src/services/aiModel/index.ts`

找到 `updateAiModelOrder`，理解前端 service 如何通过 `lambdaClient.aiModel.updateAiModelOrder.mutate` 进入后端。

6. 最后看 `src/server/routers/lambda/aiModel.ts` 和 `packages/database/src/models/aiModel.ts`

这一步用于理解排序如何真正落库。尤其注意 `updateModelsOrder` 用的是事务加 upsert，而不是简单批量 update。

## 常见误区

1. 误以为排序只影响当前 tab

`EnabledModelList` 页面展示会受 `activeTab` 影响，但传给 `SortModelModal` 的是完整 `enabledModels`，不是 `filteredModels`。所以弹窗排序是所有已启用模型的全局排序。

2. 误以为拖拽后立即保存

拖拽只更新本地 `items` state。只有点击弹窗底部的“更新”按钮后，才会调用 `updateAiModelsSort` 写入后端。

3. 误以为 `SortModelModal` 自己负责获取模型列表

它不获取数据。模型数据由上游 `ModelList` / `EnabledModelList` 和 `useAiInfraStore` 提供。`SortModelModal` 只接收 `defaultItems` 并提交排序结果。

4. 误以为 `defaultItems` 改了弹窗内 `items` 会自动同步

`items` 只在组件初次挂载时由 `defaultItems` 初始化。当前调用方用了 `open && <SortModelModal />`，关闭时会卸载，重新打开会重新初始化，所以这里通常没问题。但如果未来改成始终挂载、只切换 `open`，就要注意 `defaultItems` 更新不会自动同步到 `items`。

5. 误以为 `type` 是排序必需字段

`AiModelSortMap` 里 `type` 是可选的。排序的核心字段是 `id` 和 `sort`。不过当前 UI 提交时会带上 `item.type`，数据库 upsert 时如果有 `type` 也会写入或更新。根据当前片段推断，这有助于在排序时为尚未持久化的模型记录补充类型信息。

6. 误以为 provider id 来自 props

`SortModelModal` 的 props 里没有 provider id。它从 `useAiInfraStore` 的 `activeAiProvider` 读取当前 provider。如果 `activeAiProvider` 缺失，点击更新会直接返回。

7. 误以为成功提示来自组件硬编码

弹窗标题、按钮、成功提示都来自 `modelProvider` i18n namespace，不是硬编码中文或英文。对应 key 是 `sortModal.title`、`sortModal.update`、`sortModal.success`。

8. 误以为 `ListItem` 可以独立完成拖拽

真正的拖拽能力来自外层 `SortableList` 和 `SortableList.Item`。`ListItem` 只是渲染 `SortableList.DragHandle`，提供一个可拖拽的手柄 UI。
