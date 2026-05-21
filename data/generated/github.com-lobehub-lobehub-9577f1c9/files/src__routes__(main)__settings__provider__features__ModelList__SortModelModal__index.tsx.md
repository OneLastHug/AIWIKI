# 文件：src/routes/(main)/settings/provider/features/ModelList/SortModelModal/index.tsx

## 它负责什么

`SortModelModal/index.tsx` 实现的是“模型排序弹窗”。

它出现在模型供应商设置页中，用来让用户拖拽调整当前供应商下“已启用模型”的展示顺序。用户打开弹窗后，可以通过 `SortableList` 拖动模型条目；点击确认按钮后，组件会把当前列表顺序转换成 `{ id, sort, type }` 形式，调用 `useAiInfraStore` 里的 `updateAiModelsSort` 保存排序，然后提示成功并关闭弹窗。

这个文件只负责前端交互和提交排序，不直接访问后端 API，也不直接操作数据库。真正的保存链路在 store、service、TRPC/database 层继续完成。

## 关键组成

### import 依赖

这个文件的依赖可以分成几类：

`@lobehub/ui`：

- `Modal`：弹窗容器。
- `SortableList`：可拖拽排序列表。
- `Button`：底部确认按钮。
- `Flexbox`：布局容器。

`antd`：

- `App.useApp()`：获取 antd 的 `message` 实例，用于保存成功后的提示。

`antd-style`：

- `createStaticStyles`：定义静态 CSS 样式。这里符合仓库规范，优先使用 zero-runtime 的静态样式。

`model-bank`：

- `AiProviderModelListItem`：模型列表项类型。每个模型条目包含 `id`、`displayName`、`type` 等信息。

`react`：

- `memo`：包裹组件，减少无意义重渲染。
- `useState`：保存弹窗内排序后的临时列表和提交 loading 状态。

`react-i18next`：

- `useTranslation('modelProvider')`：读取 `modelProvider` 命名空间下的文案，例如 `sortModal.title`、`sortModal.update`、`sortModal.success`。

本地依赖：

- `useAiInfraStore`：AI 基础设施相关 Zustand store。
- `ListItem`：同目录下的单个排序项展示组件。

### `styles`

```ts
const styles = createStaticStyles(({ css, cssVar }) => ({
  container: css`
    height: 36px;
    padding-inline: 8px;
    border-radius: ${cssVar.borderRadius};
    transition: background 0.2s ease-in-out;

    &:hover {
      background: ${cssVar.colorFillTertiary};
    }
  `,
}));
```

这里只定义了排序列表中每个 item 的外观：

- 固定高度 `36px`。
- 横向内边距 `8px`。
- 使用主题变量 `cssVar.borderRadius` 和 `cssVar.colorFillTertiary`。
- hover 时改变背景色。

注意这里没有使用运行时 `token`，而是使用 `cssVar`，说明样式不依赖组件运行时动态计算，适合 `createStaticStyles`。

### `SortModelModalProps`

```ts
interface SortModelModalProps {
  defaultItems: AiProviderModelListItem[];
  onCancel: () => void;
  open: boolean;
}
```

组件接收三个 props：

- `defaultItems`：弹窗初始模型列表，也是用户拖拽排序的基础数据。
- `open`：是否显示弹窗。
- `onCancel`：关闭弹窗的回调。

这里没有接收 `providerId`，因为当前激活的 provider 从 `useAiInfraStore` 里读取。

### `SortModelModal`

核心组件定义如下：

```ts
const SortModelModal = memo<SortModelModalProps>(({ open, onCancel, defaultItems }) => {
  ...
});
```

内部状态和 store 读取：

```ts
const { t } = useTranslation('modelProvider');

const [providerId, updateAiModelsSort] = useAiInfraStore((s) => [
  s.activeAiProvider,
  s.updateAiModelsSort,
]);

const [loading, setLoading] = useState(false);
const { message } = App.useApp();

const [items, setItems] = useState(defaultItems);
```

关键点：

- `providerId` 来自 `s.activeAiProvider`，代表当前设置页选中的供应商。
- `updateAiModelsSort` 是保存排序的 store action。
- `loading` 控制确认按钮的 loading 状态。
- `items` 是弹窗内部的临时排序结果，初始化自 `defaultItems`。
- `message` 用于成功提示。

一个值得注意的细节是：`items` 只在组件首次挂载时用 `defaultItems` 初始化。调用方当前是 `{open && <SortModelModal ... />}` 的形式，关闭时会卸载组件，下一次打开会重新初始化，所以这个写法在当前调用方式下是合理的。

### `Modal`

```tsx
<Modal
  allowFullscreen
  footer={null}
  open={open}
  title={t('sortModal.title')}
  width={400}
  onCancel={onCancel}
>
```

弹窗配置：

- `allowFullscreen`：允许全屏。
- `footer={null}`：不用默认 footer，而是在内容底部自定义一个按钮。
- `open={open}`：由父组件控制显示状态。
- `title={t('sortModal.title')}`：标题走 i18n。
- `width={400}`：弹窗宽度固定为 400。
- `onCancel={onCancel}`：点击关闭或遮罩取消时通知父组件关闭。

### `SortableList`

```tsx
<SortableList
  items={items}
  renderItem={(item: AiProviderModelListItem) => (
    <SortableList.Item
      horizontal
      align={'center'}
      className={styles.container}
      gap={4}
      id={item.id}
      justify={'space-between'}
    >
      <ListItem {...item} />
    </SortableList.Item>
  )}
  onChange={async (items: AiProviderModelListItem[]) => {
    setItems(items);
  }}
/>
```

这是弹窗的核心 UI。

它做了几件事：

1. 把当前 `items` 交给 `SortableList`。
2. 每个模型渲染为一个 `SortableList.Item`。
3. 每个 item 使用 `item.id` 作为拖拽排序标识。
4. item 内容交给 `ListItem` 展示。
5. 当用户拖拽导致顺序变化时，`onChange` 接收新的数组顺序，并调用 `setItems(items)` 更新本地状态。

这里的 `onChange` 被声明成 `async`，但内部没有 `await`。从当前逻辑看，不需要异步；不过这不影响运行，只是略显多余。

### `ListItem`

同目录 `ListItem.tsx` 负责展示每个模型排序项：

```tsx
const ListItem = memo<AiProviderModelListItem>(({ id, displayName }) => {
  return (
    <>
      <Flexbox horizontal gap={8}>
        <ModelIcon model={id} size={24} type={'avatar'} />
        {displayName || id}
      </Flexbox>
      <SortableList.DragHandle />
    </>
  );
});
```

它展示：

- `ModelIcon`：根据模型 `id` 显示模型图标。
- `displayName || id`：优先显示模型名称，没有名称则显示 id。
- `SortableList.DragHandle`：拖拽手柄。

也就是说，`SortModelModal/index.tsx` 负责列表结构和提交逻辑，`ListItem.tsx` 负责单行视觉内容。

### 确认按钮

```tsx
<Button
  block
  loading={loading}
  style={{ bottom: 0, position: 'sticky' }}
  type={'primary'}
  onClick={async () => {
    if (!providerId) return;

    const sortMap = items.map((item, index) => ({
      id: item.id,
      sort: index,
      type: item.type,
    }));

    setLoading(true);
    await updateAiModelsSort(providerId, sortMap);
    setLoading(false);
    message.success(t('sortModal.success'));
    onCancel();
  }}
>
  {t('sortModal.update')}
</Button>
```

按钮逻辑是：

1. 如果没有 `providerId`，直接返回。
2. 将当前 `items` 顺序转换为 `sortMap`。
3. 每个模型生成：
   - `id`：模型 id。
   - `sort`：当前数组下标，也就是新的排序值。
   - `type`：模型类型。
4. 设置 `loading=true`。
5. 调用 `updateAiModelsSort(providerId, sortMap)`。
6. 设置 `loading=false`。
7. 显示成功提示。
8. 调用 `onCancel()` 关闭弹窗。

这里没有 `try/finally`，所以如果 `updateAiModelsSort` 抛错，`setLoading(false)`、成功提示和关闭弹窗都不会执行。根据当前片段推断，错误可能由上层请求机制或全局错误处理接管，但这个文件本身没有显式错误处理。

## 上下游关系

### 上游：谁打开它

直接调用方是：

`src/routes/(main)/settings/provider/features/ModelList/EnabledModelList/index.tsx`

调用方式大致是：

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

在 `EnabledModelList` 中，用户点击排序按钮打开弹窗：

```tsx
<ActionIcon
  icon={ArrowDownUpIcon}
  size={'small'}
  title={t('providerModels.list.enabledActions.sort')}
  onClick={() => {
    setOpen(true);
  }}
/>
```

这里有一个重要点：传给 `SortModelModal` 的是 `enabledModels`，不是 `filteredModels`。

`EnabledModelList` 会根据当前 tab 过滤展示模型：

```ts
const filteredModels = useMemo(() => {
  if (activeTab === 'all') return enabledModels;
  return enabledModels.filter((model) => model.type === activeTab);
}, [enabledModels, activeTab]);
```

但排序弹窗拿到的是完整的 `enabledModels`。因此，排序操作针对当前 provider 的全部已启用模型，而不是只排序当前 tab 下的模型。

### 中游：store action

`SortModelModal` 调用的是：

```ts
updateAiModelsSort(providerId, sortMap)
```

它来自：

`src/store/aiInfra/slices/aiModel/action.ts`

对应实现：

```ts
updateAiModelsSort = async (id: string, items: AiModelSortMap[]): Promise<void> => {
  await aiModelService.updateAiModelOrder(id, items);
  await this.#get().refreshAiModelList();
};
```

这说明保存排序后会刷新模型列表。刷新逻辑通过 SWR 的 `mutate` 重新获取当前 provider 的模型列表，并异步刷新 provider runtime state。

### 下游：service 和 API

store action 调用：

`src/services/aiModel/index.ts`

```ts
updateAiModelOrder = async (providerId: string, items: AiModelSortMap[]) => {
  return lambdaClient.aiModel.updateAiModelOrder.mutate({ providerId, sortMap: items });
};
```

这里通过 `lambdaClient.aiModel.updateAiModelOrder.mutate` 发起后端 mutation。

### 更下游：数据库模型

数据库层相关实现位于：

`packages/database/src/models/aiModel.ts`

```ts
updateModelsOrder = async (providerId: string, sortMap: AiModelSortMap[]) => {
  if (this.isEmptyArray(sortMap)) {
    return;
  }

  await this.db.transaction(async (tx) => {
    const updates = sortMap.map(({ id, sort, type }) => {
      const now = new Date();
      const insertValues: typeof aiModels.$inferInsert = {
        enabled: true,
        id,
        providerId,
        sort,
        updatedAt: now,
        userId: this.userId,
      };

      if (type) insertValues.type = type;

      const updateValues: Partial<typeof aiModels.$inferInsert> = {
        sort,
        updatedAt: now,
      };

      if (type) updateValues.type = type;

      return tx
        .insert(aiModels)
        .values(insertValues)
        .onConflictDoUpdate({
          set: updateValues,
          target: [aiModels.id, aiModels.userId, aiModels.providerId],
        });
    });

    await Promise.all(updates);
  });
};
```

这个实现说明排序保存不是简单 update，而是 insert + conflict update：

- 如果模型记录不存在，会插入一条启用状态为 `enabled: true` 的记录。
- 如果已经存在同一 `id + userId + providerId`，则更新 `sort` 和 `updatedAt`。
- 如果传入了 `type`，也会写入或更新 `type`。

这解释了为什么前端 `sortMap` 里带上了 `type`：后端保存排序时可能需要同步模型类型。

### 类型关系

`AiModelSortMap` 定义在：

`packages/model-bank/src/types/aiModel.ts`

```ts
export interface AiModelSortMap {
  id: string;
  sort: number;
  type?: AiModelType;
}
```

`SortModelModal` 生成的 `sortMap` 正好符合这个类型。

## 运行/调用流程

1. 用户进入设置页的 provider 模型列表区域。
2. `EnabledModelList` 从 `useAiInfraStore` 中读取 `enabledModels`。
3. 如果已启用模型列表不为空，页面右侧展示排序按钮。
4. 用户点击排序按钮。
5. `EnabledModelList` 设置 `open=true`。
6. 因为 JSX 中有 `{open && <SortModelModal ... />}`，所以 `SortModelModal` 被挂载。
7. `SortModelModal` 用 `defaultItems` 初始化内部状态 `items`。
8. 弹窗渲染 `SortableList`。
9. 每个模型项通过 `ListItem` 展示图标、名称和拖拽手柄。
10. 用户拖动模型改变顺序。
11. `SortableList` 触发 `onChange`，把新顺序传回。
12. `SortModelModal` 调用 `setItems(items)` 保存新的临时顺序。
13. 用户点击确认按钮。
14. 组件检查 `providerId` 是否存在。
15. 组件把 `items` 转成 `sortMap`：
    ```ts
    [
      { id: 'model-a', sort: 0, type: 'chat' },
      { id: 'model-b', sort: 1, type: 'embedding' },
      ...
    ]
    ```
16. 组件进入 loading 状态。
17. 调用 `updateAiModelsSort(providerId, sortMap)`。
18. store 调用 `aiModelService.updateAiModelOrder`。
19. service 通过 `lambdaClient.aiModel.updateAiModelOrder.mutate` 请求后端。
20. 后端最终更新数据库中的模型排序。
21. store 调用 `refreshAiModelList()` 刷新模型列表。
22. 前端弹出成功提示 `sortModal.success`。
23. 调用 `onCancel()`，父组件设置 `open=false`。
24. 因为调用方用了 `{open && ...}`，弹窗组件被卸载。

## 小白阅读顺序

建议按下面顺序读：

1. 先读 `SortModelModalProps`

   先弄清楚这个组件需要什么输入：`defaultItems`、`open`、`onCancel`。这能帮助你判断它是一个受父组件控制的弹窗组件。

2. 再读组件开头的 hooks

   重点看这几行：

   ```ts
   const [providerId, updateAiModelsSort] = useAiInfraStore(...)
   const [loading, setLoading] = useState(false);
   const [items, setItems] = useState(defaultItems);
   ```

   这三块分别代表：当前供应商、提交动作、弹窗内部状态。

3. 再读 `Modal`

   看它的标题、宽度、关闭行为和 footer 设置。理解它为什么不用默认 footer，而是自己放一个确认按钮。

4. 再读 `SortableList`

   这是交互核心。重点看：

   ```ts
   items={items}
   renderItem={...}
   onChange={(items) => setItems(items)}
   ```

   理解“拖拽改变数组顺序，数组顺序就是最终排序”的关系。

5. 再读确认按钮 `onClick`

   这是业务核心。重点看：

   ```ts
   const sortMap = items.map((item, index) => ({
     id: item.id,
     sort: index,
     type: item.type,
   }));
   ```

   这里把 UI 顺序变成后端可保存的数据结构。

6. 然后读 `ListItem.tsx`

   它只是单个排序项的展示层，理解它之后就知道每一行为什么有图标、名称和拖拽手柄。

7. 最后读调用方 `EnabledModelList/index.tsx`

   重点确认：
   - 排序按钮在哪里。
   - 弹窗什么时候打开。
   - `defaultItems` 是从哪里传进来的。
   - 为什么弹窗排序的是 `enabledModels`。

8. 如果还想继续追保存链路，再读：

   - `src/store/aiInfra/slices/aiModel/action.ts`
   - `src/services/aiModel/index.ts`
   - `packages/database/src/models/aiModel.ts`

## 常见误区

1. 误以为这个组件会直接修改数据库

   不会。它只调用 `updateAiModelsSort`。真正的 API 请求在 `aiModelService.updateAiModelOrder`，数据库操作在更下游的 database model 中。

2. 误以为排序只影响当前 tab

   从调用方看，传入的是 `enabledModels`，不是 `filteredModels`。所以排序弹窗处理的是全部已启用模型，而不是当前分类 tab 中的模型。

3. 误以为 `defaultItems` 会在弹窗打开期间自动同步

   `items` 初始化方式是：

   ```ts
   const [items, setItems] = useState(defaultItems);
   ```

   `useState` 只在首次挂载时使用初始值。当前调用方通过 `{open && <SortModelModal />}` 控制挂载和卸载，所以每次重新打开都会重新初始化。若未来改成一直挂载、只切换 `open`，就需要额外处理 `defaultItems` 变化，否则可能出现旧数据。

4. 误以为拖拽后马上保存

   拖拽只会更新本地 `items` 状态。只有点击底部确认按钮时，才会调用 `updateAiModelsSort` 保存。

5. 误以为 `sort` 来自模型原始字段

   保存时的 `sort` 是当前数组下标：

   ```ts
   sort: index
   ```

   也就是说，用户拖拽后的数组顺序才是最终排序依据。

6. 误以为 `type` 是展示用字段

   在这个组件里，`type` 没有用于 UI 展示，但会随 `sortMap` 一起提交。根据 database model 的实现，后端在 insert 或 conflict update 时会写入 `type`，所以它对保存数据有意义。

7. 误以为 `ListItem` 负责拖拽排序逻辑

   `ListItem` 只展示模型图标、名称和拖拽手柄。排序行为主要由 `SortableList` 和 `SortableList.Item` 提供。

8. 误以为 `loading` 一定会被重置

   正常成功路径会执行：

   ```ts
   setLoading(true);
   await updateAiModelsSort(providerId, sortMap);
   setLoading(false);
   ```

   但这里没有 `try/finally`。如果请求抛错，`setLoading(false)` 不会执行。根据当前片段推断，错误处理可能依赖全局请求层，但这个组件内部没有兜底。

9. 误以为没有 `providerId` 是异常

   组件中有保护：

   ```ts
   if (!providerId) return;
   ```

   如果当前没有激活 provider，点击确认不会执行任何保存操作。这是防御性逻辑，避免发出缺少 provider 的请求。

10. 误以为 `footer={null}` 表示弹窗没有操作按钮

   它只是关闭了 `Modal` 默认 footer。实际确认按钮被放在弹窗内容底部，并设置了：

   ```ts
   style={{ bottom: 0, position: 'sticky' }}
   ```

   这样在内容滚动时按钮可以贴在底部位置，方便用户提交排序。
