# 文件：src/routes/(main)/settings/provider/ProviderMenu/index.tsx

## 它负责什么

这个文件定义了“模型提供商设置页”的左侧菜单容器。它不是详情页本身，而是负责把 provider 列表页的导航、搜索框、加载态和新增入口组织起来，再根据当前状态切换显示 `ProviderList`、`SearchResult` 或 `SkeletonList`。

它还是一个典型的 client component，首行的 `'use client';` 说明这里依赖了 React hooks、zustand store 和路由上下文，不能当成纯服务端组件来读。

## 关键组成

文件里实际上有两层结构：

- `Layout`：外层壳，负责宽度、边框、顶部 sticky 搜索栏和“新增 provider”按钮。
- `ProviderMenu`：状态分发器，决定当前展示列表、搜索结果还是骨架屏。

几个关键点：

- `useTranslation('modelProvider')`：所有文案都来自 `modelProvider` 这个 i18n 命名空间。
- `useAiInfraStore`：菜单状态依赖全局 store，尤其是 `providerSearchKeyword`、`initAiProviderList` 和 `useFetchAiProviderList`。
- `SearchBar`：输入内容会直接写回 store，所以搜索状态不是局部 state，而是全局共享状态。
- `AddNew`：右上角的加号按钮，打开创建新 provider 的弹窗。
- `ProviderList` / `SearchResult` / `SkeletonList`：三个核心显示分支。

这里有一个容易忽略的小细节：`Layout` 里这段选择器写成了 `[providerSearchKeyword, useFetchAiProviderList, initAiProviderList]`，但只解构了前两个值。根据当前片段推断，第三个值只是为了让这个组件订阅初始化状态变化，实际并没有在 `Layout` 中使用。

## 上下游关系

上游调用者主要是这些地方：

- `src/routes/(main)/settings/provider/index.tsx`
- `src/routes/(main)/settings/provider/_layout/Desktop/index.tsx`
- `src/routes/(main)/settings/provider/_layout/Mobile.tsx`
- `src/routes/(mobile)/settings/provider/_layout/index.tsx`

这些父组件会传入 `onProviderSelect(providerKey)`，一般逻辑是跳转到 `/settings/provider/${providerKey}`。

下游则是它自己拼出来的几个子模块：

- `AddNew`：打开新增 provider 的 modal。
- `List`：显示已启用、已禁用、自定义 provider 的分组列表。
- `SearchResult`：按关键字过滤 `aiProviderList`。
- `SkeletonList`：初始化列表还没准备好时显示。

再往下，`List.tsx` 会继续依赖 `Actions`、`All`、`Item`、`SortProviderModal` 等更细的展示组件。

## 运行/调用流程

1. 父页面先把 `ProviderMenu` 挂上来，并传入一个 provider 选择回调。
2. `ProviderMenu` 从 `useAiInfraStore` 里读取 `initAiProviderList` 和 `providerSearchKeyword`。
3. `Layout` 内部调用 `useFetchAiProviderList()`，用来触发 provider 数据拉取或初始化流程。
4. 顶部渲染搜索框，用户输入后把内容写回 `providerSearchKeyword`。
5. `ProviderMenu` 按优先级决定主体内容：
   - 只要有搜索词，就显示 `SearchResult`
   - 否则如果还没初始化完成，就显示 `SkeletonList`
   - 否则显示完整的 `ProviderList`
6. 用户点某个 provider，子组件回调 `onProviderSelect(providerKey)`，父页面再负责路由跳转。

这个优先级很重要：搜索状态会覆盖加载态和普通列表态。

## 小白阅读顺序

建议按这个顺序看，会比较顺：

1. 先看 `src/routes/(main)/settings/provider/index.tsx`，明白这个菜单挂在整个 settings/provider 页的什么位置。
2. 再看当前文件 `ProviderMenu/index.tsx`，理解它怎么切三种状态。
3. 接着看 `ProviderMenu/List.tsx`，理解默认列表页的分组结构。
4. 再看 `ProviderMenu/SearchResult.tsx`，理解搜索是怎么过滤的。
5. 最后看 `ProviderMenu/AddNew.tsx`，补上“新增 provider”的入口。
6. 如果还想追数据来源，再看 `useAiInfraStore` 和 `aiProviderSelectors`。

## 常见误区

- 它不是 provider 详情页，只是左侧菜单和状态切换容器。
- 搜索词放在全局 store 里，不是这个组件自己的局部 state，所以切路由后可能仍然保留，除非别处主动清理。
- `SearchResult` 的优先级高于加载态；只要 `providerSearchKeyword` 非空，就不会继续显示 `SkeletonList`。
- `Layout` 里多选了一个 `initAiProviderList` 但没解构出来，别误以为这里真的在用这个变量。
- 移动端和桌面端传入的 `mobile` 值不同，影响宽度、滚动和列表布局；这不是同一个视觉组件的简单缩放，而是适配不同页面容器的壳。
