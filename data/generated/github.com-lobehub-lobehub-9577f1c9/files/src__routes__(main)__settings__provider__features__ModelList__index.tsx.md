# 文件：src/routes/(main)/settings/provider/features/ModelList/index.tsx

## 它负责什么

这个文件是 provider 设置页里“模型列表”区域的入口组件，默认导出 `ModelList`。它把“标题、筛选、已启用模型、已禁用模型、空态、搜索态、加载态”这些子能力组装起来，是整个 provider 模型管理界面的容器层。

从调用方看，它被 `src/routes/(main)/settings/provider/detail/default/index.tsx` 和 `src/routes/(main)/settings/provider/detail/default/ClientMode.tsx` 引用，用在 provider 详情页里，负责展示某个 provider 下的模型集合。

## 关键组成

这个文件里主要有两个组件：

1. `Content`
   - 负责真正的数据展示逻辑。
   - 读取 `useAiInfraStore` 里的模型搜索状态、模型列表和拉取 hook。
   - 根据 `modelSearchKeyword` 决定是否进入搜索结果态。
   - 根据 `useFetchAiProviderModels(id)` 的加载状态决定是否显示 `SkeletonList`。
   - 根据 `filteredAiProviderModelList` 统计各类型模型数量，构造 Tabs。
   - 将列表拆成 `EnabledModelList` 和 `DisabledModels` 两块。

2. `ModelList`
   - 对外暴露的主组件。
   - 通过 `ProviderSettingsContext` 向下传递 `modelEditable`、`sdkType`、`showAddNewModel`、`showDeployName`、`showModelFetcher` 等配置。
   - 根据 `useIsMobile()` 调整内边距和背景色。
   - 先渲染 `ModelTitle`，再用 `Suspense` 包住 `Content`，让子树在需要时可以异步加载并回退到 `SkeletonList`。

这个文件还依赖一批子组件：
- `ModelTitle`：标题和入口操作区。
- `EnabledModelList`：已启用模型列表。
- `DisabledModels`：未启用模型列表，支持分页加载和排序。
- `SearchResult`：搜索结果页。
- `EmptyModels`：空状态页。
- `SkeletonList`：骨架屏。

## 上下游关系

上游输入主要来自两类：

- 页面路由层传入的 provider 标识 `id`，以及 `ProviderSettingsContextValue` 里的配置项。
- Zustand store `useAiInfraStore` 和其 selector，提供模型列表、搜索状态、拉取方法等数据。

下游输出主要是三个方向：

- 视觉输出：Tabs、列表、空态、搜索态、加载态。
- 状态输出：通过上下文把 provider 设置分发给子组件，供 `ModelItem`、`EnabledModelList`、`ModelTitle` 等继续判断是否可编辑、是否显示新增按钮。
- 交互输出：用户切换 tab、搜索模型、启用/停用模型、批量关闭、排序、删除、编辑配置等，都会继续下沉到子组件和 store action。

根据当前片段推断，这个文件本身不直接改写模型数据，而是作为“编排层”把 store、hook 和展示组件串起来。

## 运行/调用流程

1. 进入 provider 详情页时，路由层渲染 `ProviderDetail` 或 `ClientMode`。
2. 页面把 `id` 传给 `ModelList`。
3. `ModelList` 先建立 `ProviderSettingsContext`，再渲染 `ModelTitle` 和 `Content`。
4. `Content` 内部调用 `useFetchAiProviderModels(id)` 拉取该 provider 的模型数据。
5. 如果正在加载，直接显示 `SkeletonList`。
6. 如果 `modelSearchKeyword` 存在，切到 `SearchResult`。
7. 如果列表为空，显示 `EmptyModels`。
8. 否则根据模型类型统计 Tabs，用户切换 tab 后更新 `activeTab`。
9. 当前 tab 下的已启用模型交给 `EnabledModelList`，未启用模型交给 `DisabledModels`。
10. `DisabledModels` 继续负责分页懒加载、排序和滚动加载更多。

这里有一个小细节：`activeTab` 会在 tabs 被过滤后做一次兜底，如果当前 tab 被隐藏，就回退到 `all`，避免出现“当前 tab 不存在但状态还停留在那里”的空白问题。

## 小白阅读顺序

1. 先读 `index.tsx`，理解它是整体容器，不是具体业务细节。
2. 再看 `ProviderSettingsContext.ts`，确认哪些配置会被向下传递。
3. 接着看 `ModelTitle/index.tsx`，理解标题区有哪些操作入口。
4. 再看 `EnabledModelList/index.tsx`，理解启用模型如何渲染和批量操作。
5. 再看 `DisabledModels.tsx`，理解未启用模型如何分页、排序、懒加载。
6. 最后看 `ModelItem.tsx`，把单个模型行的开关、编辑、删除和价格展示串起来。

## 常见误区

1. 容易把这个文件当成“列表渲染本体”，其实它更像编排器，真正的列表逻辑分散在多个子组件里。
2. `Tabs` 统计的是“全部模型的类型数量”，不是只统计已启用模型。
3. `SearchResult` 会覆盖正常列表态，所以搜索关键词存在时，不要期待还能看到 Tabs 和双列表。
4. `activeTab` 不是永远有效的，文件里专门做了可用 tab 兜底。
5. `Suspense` 不是纯装饰，它是为了让异步子树在加载时稳定回退到骨架屏。
6. `ProviderSettingsContext` 很关键，很多“是否可编辑、是否显示新增按钮”的判断不是写死在子组件里，而是从这里继承下去。
