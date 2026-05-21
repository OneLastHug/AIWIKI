# 目录：src/routes/(main)/settings/provider/features/ModelList/ModelTitle

## 它负责什么

`ModelTitle` 是“模型供应商设置页”里 `ModelList` 顶部的标题与工具栏区域。它不负责真正渲染每一个模型条目，而是负责模型列表上方的一组控制能力：

- 显示模型列表标题：`providerModels.list.title`
- 显示当前模型总数：`providerModels.list.total`
- 提供模型搜索框，并把搜索关键词写入 `useAiInfraStore.modelSearchKeyword`
- 支持拉取远程模型列表：`fetchRemoteModelList(provider)`
- 支持清除已经获取的远程模型：`clearRemoteModels(provider)`
- 支持新增自定义模型：打开 `CreateNewModelModal`
- 支持重置当前 provider 下的模型配置：`clearModelsByProvider(provider)`
- 根据移动端/桌面端调整搜索框位置和工具栏布局
- 在 provider 切换时自动清空搜索关键词

这个目录可以理解为 `ModelList` 的“列表头部控制区”。它的核心关注点是“用户如何管理当前 provider 的模型列表”，而不是“模型数据如何存储”或“每个模型如何展示”。

## 关键组成

这个目录下有 3 个文件：

- `index.tsx`
- `Search.tsx`
- `Search.test.tsx`

### `index.tsx`

`index.tsx` 默认导出 `ModelTitle` 组件。

组件签名大致是：

```ts
interface ModelFetcherProps {
  provider: string;
  showAddNewModel?: boolean;
  showModelFetcher?: boolean;
}
```

其中：

- `provider`：当前模型供应商标识，例如某个 AI provider 的 id。所有拉取、清除、重置操作都围绕它执行。
- `showAddNewModel`：是否展示“新增模型”按钮，默认 `true`。
- `showModelFetcher`：是否展示“拉取远程模型”按钮，默认 `true`。

它使用的主要外部依赖包括：

- `@lobehub/ui`：`ActionIcon`、`Button`、`DropdownMenu`、`Flexbox`、`Skeleton`、`Text`
- `antd`：`App`、`Space`
- `antd-style`：`cssVar`
- `lucide-react`：`CircleX`、`EllipsisVertical`、`LucideRefreshCcwDot`、`PlusIcon`
- `react-i18next`：`useTranslation`
- `@/hooks/useIsMobile`：判断移动端布局
- `@/store/aiInfra`：读取和更新 AI provider/model 相关状态
- `@/store/aiInfra/selectors`：计算模型总数、空状态、是否存在远程模型等派生数据
- `../CreateNewModelModal`：新增模型弹窗
- `./Search`：本目录下的搜索框子组件

它从 `useAiInfraStore` 中一次性取出：

```ts
[
  searchKeyword,
  totalModels,
  isEmpty,
  hasRemoteModels,
  fetchRemoteModelList,
  clearObtainedModels,
  clearModelsByProvider,
  useFetchAiProviderModels,
]
```

这些值分别对应：

- `searchKeyword`：当前搜索关键词，来自 `s.modelSearchKeyword`
- `totalModels`：模型总数，来自 `aiModelSelectors.totalAiProviderModelList(s)`
- `isEmpty`：模型列表是否为空，来自 `aiModelSelectors.isEmptyAiProviderModelList(s)`
- `hasRemoteModels`：是否有远程获取到的模型，来自 `aiModelSelectors.hasRemoteModels(s)`
- `fetchRemoteModelList`：拉取远程模型列表
- `clearObtainedModels`：清除远程获取模型，实际绑定的是 `s.clearRemoteModels`
- `clearModelsByProvider`：清除当前 provider 的模型配置
- `useFetchAiProviderModels`：获取当前 provider 模型列表的 hook

组件内部还有三个局部状态：

```ts
const [fetchRemoteModelsLoading, setFetchRemoteModelsLoading] = useState(false);
const [clearRemoteModelsLoading, setClearRemoteModelsLoading] = useState(false);
const [showModal, setShowModal] = useState(false);
```

它们分别控制：

- 远程拉取按钮 loading
- 清除远程模型按钮 loading
- 新增模型弹窗是否打开

另外有一个关键副作用：

```ts
useEffect(() => {
  useAiInfraStore.setState({ modelSearchKeyword: '' });
}, [provider]);
```

这表示只要切换了 provider，搜索关键词就会被重置，避免把上一个 provider 的筛选条件错误地带到下一个 provider。

### `Search.tsx`

`Search.tsx` 默认导出 `Search` 组件，是一个带防抖逻辑的搜索输入框。

组件参数：

```ts
interface SearchProps {
  onChange: (value: string) => void;
  value: string;
  variant?: InputProps['variant'];
}
```

它内部维护 `localValue`，并通过 `ahooks` 的 `useDebounce` 做 200ms 防抖：

```ts
const [localValue, setLocalValue] = useState(value);
const debouncedValue = useDebounce(localValue, { wait: 200 });
```

这里的设计重点是：输入框本地值和外部 store 值不是完全同步立即提交的关系。用户输入时先更新 `localValue`，等 200ms 后再通过 `onChange(debouncedValue)` 通知外部。

它还用了一个 `skipDebouncedEmitRef`：

```ts
const skipDebouncedEmitRef = useRef(false);
```

这个 ref 用来处理“外部 value 被重置”时的竞态问题。比如用户刚输入了 `abcd`，但外部马上把 `value` 重置成空字符串，如果旧的 debounced 值稍后再触发，就可能把 `abcd` 又写回 store。`skipDebouncedEmitRef` 的作用就是跳过这类由外部同步引起的防抖回放。

清空输入框时，它不会等 200ms，而是尽快触发：

```ts
if (!localValue) {
  if (value) onChange('');

  return;
}
```

所以搜索框的行为是：

- 普通输入：200ms 防抖后更新外部关键词
- 清空输入：立即通知外部清空
- 外部重置：同步本地输入值，并避免旧防抖值回写

最终渲染的是 `@lobehub/ui` 的 `SearchBar`：

```tsx
<SearchBar
  allowClear
  placeholder={t('providerModels.list.search')}
  size={'small'}
  value={localValue}
  variant={variant}
  onInputChange={setLocalValue}
/>
```

### `Search.test.tsx`

这个测试文件只覆盖 `Search` 的关键交互，不测试整个 `ModelTitle`。

它 mock 了：

- `react-i18next`：让 `t(key)` 直接返回 key
- `@lobehub/ui` 的 `SearchBar`：用普通 `<input>` 模拟

测试重点有两个：

1. 清空搜索框时应立即触发 `onChange('')`，不等待防抖。
2. 外部把 `value` 重置为空后，不应在 200ms 后把旧的 debounced 值重新提交。

第二个测试对应 `skipDebouncedEmitRef` 的存在意义，是这个搜索组件里最容易被忽略的边界情况。

## 上下游关系

### 上游：`ModelList`

根据当前调用片段，`ModelTitle` 被 `src/routes/(main)/settings/provider/features/ModelList/index.tsx` 引入：

```ts
import ModelTitle from './ModelTitle';
```

调用位置在 `ModelList/index.tsx` 附近，传入了：

- `provider={id}`
- `showAddNewModel={showAddNewModel}`
- `showModelFetcher={showModelFetcher}`

也就是说，`ModelTitle` 自己不知道当前 provider 是从路由参数、配置对象还是父组件状态来的。它只依赖父级传入的 `provider` 字符串，并把它作为所有 store action 的操作对象。

同一层还存在 `ProviderSettingsContext.ts`，其中也包含：

- `showAddNewModel?: boolean`
- `showModelFetcher?: boolean`

根据当前片段推断，`ModelList` 会把这些开关放入上下文，供模型列表内部其他组件共同判断是否允许新增、远程拉取或展示某些能力。`ModelTitle` 则通过 props 直接消费其中两个开关。

### 下游：`useAiInfraStore`

`ModelTitle` 的主要业务下游是 `useAiInfraStore`。

它读取 store 中的模型列表状态和派生状态：

- 当前搜索关键词
- 当前模型总数
- 模型列表是否为空
- 是否有远程模型
- 当前 provider 的模型列表加载状态

它也调用 store action 修改数据：

- `fetchRemoteModelList(provider)`：从远程获取模型列表
- `clearRemoteModels(provider)`：清除已获取的远程模型
- `clearModelsByProvider(provider)`：重置当前 provider 的模型
- `useAiInfraStore.setState({ modelSearchKeyword: value })`：更新搜索关键词

注意：`Search` 组件自身不直接依赖 store。它只通过 `value` 和 `onChange` 与外部通信。真正把关键词写进 store 的逻辑在 `ModelTitle` 中完成。

### 下游：新增模型弹窗

`ModelTitle` 引入：

```ts
import CreateNewModelModal from '../CreateNewModelModal';
```

当 `showAddNewModel` 为真时，工具栏显示一个带 `PlusIcon` 的按钮。点击后：

```ts
setShowModal(true);
```

然后通过：

```tsx
<CreateNewModelModal open={showModal} setOpen={setShowModal} />
```

把弹窗开关传给新增模型弹窗组件。

根据当前片段推断，新增模型的实际表单和保存逻辑不在 `ModelTitle` 中，而是在 `CreateNewModelModal` 里。

### 下游：Ant Design App 上下文

`ModelTitle` 使用：

```ts
const { modal, message } = App.useApp();
```

用于重置所有模型时弹出确认框，并在成功后展示消息：

- `modal.confirm(...)`
- `message.success(...)`

这意味着 `ModelTitle` 依赖上层存在 antd 的 `App` provider。通常 LobeHub 应用的布局层会统一提供这个上下文。

### i18n 文案

所有用户可见文案都从 `modelProvider` 命名空间读取，例如：

- `providerModels.list.title`
- `providerModels.list.total`
- `providerModels.list.fetcher.clear`
- `providerModels.list.fetcher.fetch`
- `providerModels.list.fetcher.fetching`
- `providerModels.list.resetAll.title`
- `providerModels.list.resetAll.conform`
- `providerModels.list.resetAll.success`
- `providerModels.list.search`

因此这个目录没有硬编码业务文案，而是通过 `react-i18next` 走统一国际化。

## 运行/调用流程

### 初始渲染流程

1. 父组件 `ModelList` 渲染 `ModelTitle`，传入当前 `provider` 和功能开关。
2. `ModelTitle` 调用 `useTranslation('modelProvider')` 获取文案函数 `t`。
3. 通过 `App.useApp()` 获取 `modal` 和 `message`。
4. 从 `useAiInfraStore` 读取模型列表状态、selector 计算结果和 action。
5. 调用 `useFetchAiProviderModels(provider)` 获取当前 provider 模型列表加载状态。
6. 调用 `useIsMobile()` 判断当前布局是否为移动端。
7. 渲染 sticky 顶部区域。

如果模型列表仍在加载：

- 标题旁显示 `Skeleton.Button`
- 右侧工具区也显示 skeleton

如果加载完成但列表为空：

- 不展示右侧搜索、拉取、新增和更多菜单区域

如果加载完成且列表非空：

- 桌面端：搜索框展示在右侧工具区内
- 移动端：搜索框展示在标题行下方，并传入 `variant="filled"`

### 切换 provider 流程

当 `provider` 变化时：

1. `useEffect([provider])` 触发。
2. 执行：

```ts
useAiInfraStore.setState({ modelSearchKeyword: '' });
```

3. 搜索关键词被清空。
4. `Search` 收到新的 `value`。
5. `Search` 同步本地 `localValue`，并通过 `skipDebouncedEmitRef` 避免旧的防抖值回写。

这个流程防止了一个常见问题：用户在 provider A 搜了 “gpt”，切到 provider B 后列表仍被 “gpt” 过滤。

### 搜索流程

桌面端和移动端都使用同一个 `Search` 组件，只是位置和 `variant` 不同。

流程如下：

1. 用户输入关键词。
2. `SearchBar` 触发 `onInputChange`。
3. `Search` 更新内部 `localValue`。
4. `useDebounce` 等待 200ms。
5. 如果防抖后的值和外部 `value` 不同，则调用：

```ts
onChange(debouncedValue);
```

6. `ModelTitle` 中的 `onChange` 执行：

```ts
useAiInfraStore.setState({ modelSearchKeyword: value });
```

7. 模型列表的其他部分根据 `modelSearchKeyword` 过滤展示。

清空时比较特殊：

1. 用户点击 clear 或删除全部内容。
2. `localValue` 变成空字符串。
3. 如果外部 `value` 原本不为空，立即调用 `onChange('')`。
4. 不等待 200ms。

### 拉取远程模型流程

当 `showModelFetcher` 为真时，会显示“拉取”按钮。

点击后：

1. 设置 `fetchRemoteModelsLoading` 为 `true`。
2. 调用：

```ts
await fetchRemoteModelList(provider);
```

3. 如果抛错，当前代码只执行：

```ts
console.error(e);
```

4. 设置 `fetchRemoteModelsLoading` 为 `false`。

按钮文案根据 loading 状态变化：

- 未加载：`providerModels.list.fetcher.fetch`
- 加载中：`providerModels.list.fetcher.fetching`

这里的 `try/catch` 只负责避免异常打断 UI 状态恢复。错误提示是否在 store action 内部处理，根据当前片段无法确认。

### 清除远程模型流程

当 `hasRemoteModels` 为真时，总数旁会显示一个 `CircleX` 图标按钮。

点击后：

1. 设置 `clearRemoteModelsLoading` 为 `true`。
2. 调用：

```ts
await clearObtainedModels(provider);
```

这里的 `clearObtainedModels` 实际来自：

```ts
s.clearRemoteModels
```

3. 设置 `clearRemoteModelsLoading` 为 `false`。

它清除的是“远程获取到的模型”，不是重置所有模型配置。重置所有模型走的是更多菜单里的 `clearModelsByProvider(provider)`。

### 新增模型流程

当 `showAddNewModel` 为真时，会显示一个带 `PlusIcon` 的小按钮。

点击后：

1. 执行 `setShowModal(true)`。
2. `CreateNewModelModal` 的 `open` 变为 `true`。
3. 用户在弹窗里完成新增模型操作。

`ModelTitle` 只负责打开弹窗，不处理表单字段、校验或保存。

### 重置模型流程

更多菜单 `DropdownMenu` 中只有一个菜单项：`reset`。

点击后：

1. 调用 `modal.confirm(...)`。
2. 弹出确认框，标题是 `providerModels.list.resetAll.title`。
3. 内容是 `providerModels.list.resetAll.conform`。
4. 用户确认后执行：

```ts
await clearModelsByProvider(provider);
```

5. 成功后调用：

```ts
message.success(t('providerModels.list.resetAll.success'));
```

注意这里是“重置当前 provider 的模型”，不是全局所有 provider。

## 小白阅读顺序

1. 先看 `index.tsx` 的 props

   从 `ModelFetcherProps` 开始看，先明确这个组件只接收三个参数：`provider`、`showAddNewModel`、`showModelFetcher`。这能帮助你理解它为什么不关心路由，也不关心 provider 的完整配置对象。

2. 再看 `useAiInfraStore` 取值

   重点看它从 store 里取了哪些值。这里能看出组件的真实职责：搜索、总数、空状态、远程模型状态、拉取、清除、重置。

3. 看 `useEffect([provider])`

   这段很短，但很关键。它解释了为什么切换 provider 时搜索框会自动清空。

4. 看 JSX 的三层条件渲染

   重点理解这几个条件：

   - `isLoading`
   - `isEmpty`
   - `mobile`
   - `showModelFetcher`
   - `showAddNewModel`
   - `hasRemoteModels`

   这些条件决定用户最终看到哪些按钮和输入框。

5. 再看 `Search.tsx`

   不要一开始就纠结防抖细节。先理解它是一个“受控 value + 本地输入 localValue + 防抖提交”的搜索框。

6. 最后看 `Search.test.tsx`

   测试能反向说明 `Search` 最重要的行为：清空要立即生效，外部重置不能被旧防抖值覆盖。

## 常见误区

1. 误以为 `ModelTitle` 只是标题组件

   它虽然叫 `ModelTitle`，但实际是模型列表顶部工具栏。标题只是其中一部分，它还包含搜索、拉取远程模型、新增模型、清除远程模型和重置模型等操作入口。

2. 误以为 `Search` 直接操作 store

   `Search` 不知道 `useAiInfraStore` 的存在。它只接收 `value` 和 `onChange`。真正写入 store 的地方在 `ModelTitle`：

   ```ts
   useAiInfraStore.setState({ modelSearchKeyword: value });
   ```

3. 误以为所有搜索变化都有 200ms 延迟

   普通输入有 200ms 防抖，但清空是立即触发的。`Search.test.tsx` 的第一个测试专门保护了这个行为。

4. 误删 `skipDebouncedEmitRef`

   这个 ref 看起来像额外复杂度，但它是为了解决外部 value 重置和旧 debounced 值回放之间的竞态。如果删掉，可能出现“搜索框已经清空，但旧关键词又被写回去”的问题。

5. 误以为 `clearRemoteModels` 和 `clearModelsByProvider` 是同一个操作

   它们语义不同：

   - `clearRemoteModels(provider)`：清除远程获取到的模型
   - `clearModelsByProvider(provider)`：重置当前 provider 的模型配置

   前者是标题总数旁边的 `CircleX` 图标触发，后者是更多菜单里的 `reset` 触发。

6. 误以为移动端和桌面端只是样式不同

   两端不仅样式不同，搜索框的位置也不同。桌面端搜索框在标题行右侧工具区，移动端搜索框在标题行下方，并使用 `variant="filled"`。

7. 误以为空列表时仍能新增模型或拉取模型

   当前 JSX 逻辑是：加载完成后如果 `isEmpty` 为真，右侧工具区返回 `null`。也就是说搜索、拉取、新增和更多菜单都不会显示。这个行为是否符合产品预期，需要结合 `ModelList` 其他空状态 UI 判断；仅根据当前片段可确认 `ModelTitle` 自身在空列表时隐藏这些工具。

8. 误以为 `showAddNewModel` 和 `showModelFetcher` 默认关闭

   它们在 `ModelTitle` 内默认都是 `true`：

   ```ts
   ({ provider, showAddNewModel = true, showModelFetcher = true })
   ```

   只有父组件显式传 `false` 时，对应按钮才会隐藏。
