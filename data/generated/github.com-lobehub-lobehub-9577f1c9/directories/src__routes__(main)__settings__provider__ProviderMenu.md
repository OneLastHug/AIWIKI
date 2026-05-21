# 目录：src/routes/(main)/settings/provider/ProviderMenu

## 它负责什么

`src/routes/(main)/settings/provider/ProviderMenu` 负责“模型服务商设置页”的左侧 Provider 导航菜单。它不是 Provider 详情页本身，而是围绕 Provider 列表提供一组导航与管理入口：

- 拉取并展示 AI Provider 列表。
- 按启用状态分组展示：`enabled`、`custom`、`disabled`。
- 支持搜索 Provider。
- 支持点击 Provider 后跳转或切换详情页。
- 支持新增自定义 Provider。
- 支持启用 Provider 的拖拽排序。
- 支持禁用内置 Provider 的显示排序方式切换。

它属于 `src/routes/(main)/settings/provider` 路由页面的一部分，主要面向设置页中的 Provider 导航区域。桌面端表现为左侧固定宽度菜单；移动端会根据布局条件只显示菜单或详情内容。

## 关键组成

该目录下的文件可以分成五类。

第一类是入口与整体布局：

- `index.tsx`

这是目录的默认导出文件，导出 `ProviderMenu`。它内部还有一个 `Layout` 组件，负责菜单容器、搜索栏、添加按钮和子内容区域。

`ProviderMenu` 从 `useAiInfraStore` 读取：

- `initAiProviderList`：Provider 列表是否已经初始化。
- `providerSearchKeyword`：当前搜索关键词。

然后决定渲染哪种内容：

- 未初始化时渲染 `SkeletonList`。
- 有搜索关键词时渲染 `SearchResult`。
- 默认渲染 `ProviderList`。

`Layout` 里调用 `useFetchAiProviderList()`，因此这个菜单挂载后会触发 Provider 列表请求。它还渲染 `SearchBar`，输入变化时直接通过 `useAiInfraStore.setState({ providerSearchKeyword: v })` 写入 store。

第二类是主列表：

- `List.tsx`

`ProviderList` 是菜单主体。它从 `aiProviderSelectors` 里读取三组 Provider：

- `enabledAiProviderList`：已启用 Provider，会按 `sort` 升序排序。
- `disabledAiProviderList`：未启用且不是自定义来源的 Provider。
- `disabledCustomAiProviderList`：未启用且来源为 `custom` 的 Provider。

组件用 `Accordion` 分成三个分组：

- `Enabled Providers`
- `Custom Providers`
- `Disabled Providers`

其中桌面端还会在顶部显示 `All` 入口，移动端不会显示这个 `All` 菜单项。

`enabled` 分组右侧有一个排序按钮，点击后打开 `SortProviderModal`，用于拖拽调整已启用 Provider 的顺序。

`disabled` 分组右侧有 `Actions` 下拉菜单，用于切换禁用 Provider 的排序方式。排序偏好保存在 `useGlobalStore` 的 `status.disabledModelProvidersSortType` 中，默认值是 `'default'`。

第三类是单项与特殊入口：

- `Item.tsx`
- `All.tsx`
- `AddNew.tsx`

`Item.tsx` 导出 `ProviderItem`，它接收 `AiProviderListItem` 以及 `onClick`。核心职责是把 Provider 数据渲染成 `NavItem`。

它会根据当前 `location.pathname` 解析 active provider：

```text
/settings/provider/all
/settings/provider/openai
/settings/provider/xxx
```

如果路径第三段是 `provider`，第四段就是当前激活的 Provider key。然后通过 `active={activeKey === id}` 控制菜单项高亮。

图标逻辑也在这里处理：

- 自定义 Provider 且有 `logo` 时，用 `Avatar`。
- 如果是自定义品牌并且 id 等于 `BRANDING_PROVIDER`，用 `ProductLogo`。
- 其他情况用 `ProviderIcon`。

如果 Provider 已启用，右侧显示一个绿色 `Badge`。

`All.tsx` 渲染“全部 Provider”入口，常量 `PROVIDER_ALL_PATH` 为 `'all'`。它同样根据 pathname 判断是否 active，点击时调用 `onClick('all')`。

`AddNew.tsx` 渲染右上角的加号按钮。点击后打开相邻目录中的 `../features/CreateNewProvider` 弹窗。创建成功后的具体导航逻辑不在本目录内，但调用方中可以看到新建 Provider 会导航到 `/settings/provider/${values.id}`。

第四类是搜索：

- `SearchResult.tsx`

`SearchResult` 从 `useAiInfraStore` 读取：

- `providerSearchKeyword`
- `aiProviderList`

然后根据关键词过滤完整 Provider 列表。匹配字段包括：

- `provider.id`
- `provider.name`
- `provider.description`

搜索结果继续复用 `ProviderItem` 渲染，因此点击行为和普通列表一致。如果有关键词但没有结果，会显示 `menu.notFound` 对应的国际化文案。

这里需要注意：当前 `useMemo` 的依赖数组只有 `[searchKeyword]`，但过滤逻辑里也使用了 `aiProviderList`。如果 Provider 列表在搜索词不变时更新，搜索结果可能不会立刻重新计算。根据当前片段推断，这可能依赖外层列表初始化时机规避问题，但从 React 依赖完整性角度看，`aiProviderList` 应该也是依赖项。

第五类是排序操作：

- `useDropdownMenu.tsx`
- `Actions.tsx`
- `SortProviderModal/index.tsx`
- `SortProviderModal/GroupItem.tsx`

`useDropdownMenu.tsx` 定义了禁用 Provider 的排序枚举：

```ts
export enum SortType {
  Alphabetical = 'alphabetical',
  AlphabeticalDesc = 'alphabeticalDesc',
  Default = 'default',
}
```

`useProviderDropdownMenu` 返回 `DropdownMenu` 可用的 items。当前选中的排序项会显示 `LucideCheck` 图标。菜单项包括：

- 默认排序
- 字母升序
- 字母降序

`Actions.tsx` 是一个很薄的包装组件，把 `DropdownMenu` 和 `MoreHorizontalIcon` 组合起来。

`SortProviderModal/index.tsx` 用于排序已启用 Provider。它接收 `defaultItems`，内部用 `SortableList` 维护拖拽后的 `items`。点击确认按钮时，会把列表转换成：

```ts
{
  id: item.id,
  sort: index,
}
```

然后调用 `useAiInfraStore((s) => s.updateAiProviderSort)`。store action 内部会调用 `aiProviderService.updateAiProviderOrder(items)`，随后刷新 Provider 列表。

`SortProviderModal/GroupItem.tsx` 是排序弹窗里的单行展示项，左侧是 Provider 图标和名称，右侧是 `SortableList.DragHandle()`。

## 上下游关系

上游主要来自三个方向。

第一，路由和页面布局调用它。

`ProviderMenu` 被 `src/routes/(main)/settings/provider/index.tsx` 中的 `ProviderLayout` 使用。桌面路由模式下，整体结构大致是：

```tsx
<ProviderMenu mobile={false} onProviderSelect={handleProviderSelect} />
<DesktopLayoutContainer>
  <Outlet />
  <Footer />
</DesktopLayoutContainer>
```

其中 `handleProviderSelect(providerKey)` 会调用：

```ts
navigate(`/settings/provider/${providerKey}`);
```

所以菜单项本身不直接知道路由跳转细节，只是把 Provider key 传给父组件。

它也被旧的非路由 fallback 页面 `src/routes/(main)/settings/provider/(list)/index.tsx` 通过 `DesktopLayout` / `MobileLayout` 间接使用。在这个旧模式里，点击菜单不会 `navigate('/settings/provider/xxx')`，而是通过 `setSearchParams({ active: 'provider', provider })` 更新 query 参数并更新本地 state。

第二，数据来自 `useAiInfraStore`。

本目录依赖 `src/store/aiInfra` 下的 Provider 状态和 action：

- `aiProviderList`
- `initAiProviderList`
- `providerSearchKeyword`
- `useFetchAiProviderList`
- `updateAiProviderSort`

列表分组来自 `src/store/aiInfra/slices/aiProvider/selectors.ts`：

- `enabledAiProviderList`
- `disabledAiProviderList`
- `disabledCustomAiProviderList`

其中 `AiProviderListItem` 的核心字段来自 `packages/types/src/aiProvider.ts`：

```ts
interface AiProviderListItem {
  description?: string;
  enabled: boolean;
  id: string;
  logo?: string;
  name?: string;
  sort?: number;
  source: AiProviderSourceType;
}
```

`source` 只有两类：

- `builtin`
- `custom`

第三，排序偏好来自 `useGlobalStore`。

禁用 Provider 的排序方式不是保存在 aiInfra store，而是保存在 global store 的 `status.disabledModelProvidersSortType`。默认值是 `'default'`，读取 selector 是 `systemStatusSelectors.disabledModelProvidersSortType`。

下游主要是 Provider 详情页。

菜单点击后传出 `providerKey`，父组件会把它转成路由或 query 参数。最终详情页由 `src/routes/(main)/settings/provider/detail/index.tsx` 根据 id 决定渲染：

- `all` 渲染 `ProviderGrid`
- `openai` 渲染 OpenAI 配置页
- `azure` 渲染 Azure 配置页
- `ollama` 渲染 Ollama 配置页
- 其他 Provider 走 `DefaultPage`

所以 `ProviderMenu` 的职责边界很清晰：它负责“选谁”，不负责“选中后详情页怎么配置”。

## 运行/调用流程

典型桌面路由流程如下。

1. 用户进入 `/settings/provider/all` 或 `/settings/provider/openai`。

2. `src/spa/router/desktopRouter.config.tsx` 或 `desktopRouter.config.desktop.tsx` 命中 provider 设置路由。空 provider 路径会被重定向到 `/settings/provider/all`。

3. 路由渲染 `ProviderLayout`。

4. `ProviderLayout` 渲染左侧 `ProviderMenu` 和右侧 `Outlet`。

5. `ProviderMenu` 挂载后，`Layout` 调用 `useFetchAiProviderList()`，通过 SWR 获取 Provider 列表。成功后 store 设置：

   - `aiProviderList`
   - `initAiProviderList: true`

6. 在 `initAiProviderList` 为 false 时，菜单显示 `SkeletonList`。初始化完成后显示 `ProviderList`。

7. `ProviderList` 从 store selector 拿到三组 Provider：

   - 已启用 Provider
   - 未启用自定义 Provider
   - 未启用内置 Provider

8. 菜单项由 `ProviderItem` 渲染。每个 `ProviderItem` 会读取当前 pathname，判断自己是否 active。

9. 用户点击某个 Provider，例如 `openai`。

10. `ProviderItem` 调用 `onClick(id)`，一路传回 `ProviderLayout` 的 `handleProviderSelect`。

11. `handleProviderSelect` 调用：

```ts
navigate('/settings/provider/openai');
```

12. 右侧详情区域根据 route param `providerId` 渲染对应 Provider 配置页。

搜索流程如下。

1. 用户在顶部 `SearchBar` 输入关键词。
2. `onInputChange` 把关键词写入 `useAiInfraStore.providerSearchKeyword`。
3. `ProviderMenu` 检测到 `providerSearchKeyword` 非空，不再渲染 `ProviderList`，改为渲染 `SearchResult`。
4. `SearchResult` 在完整 `aiProviderList` 中匹配 `id`、`name`、`description`。
5. 搜索结果仍然用 `ProviderItem` 展示，点击后仍然走 `onProviderSelect`。

已启用 Provider 排序流程如下。

1. 用户点击 enabled 分组右侧的 `ArrowDownUpIcon`。
2. `ProviderList` 设置 `open=true`。
3. 渲染 `SortProviderModal`，传入当前 `enabledModelProviderList`。
4. 用户拖拽 `SortableList`。
5. 点击确认按钮后，组件生成 `{ id, sort }[]`。
6. 调用 `updateAiProviderSort(sortMap)`。
7. store action 调用服务端更新顺序，然后刷新 Provider 列表。
8. 弹窗提示成功并关闭。

禁用 Provider 排序流程如下。

1. disabled 分组如果有超过一个 Provider，会显示 `Actions`。
2. 用户打开下拉菜单。
3. 点击默认、升序或降序。
4. `useGlobalStore.updateSystemStatus` 更新 `disabledModelProvidersSortType`。
5. `ProviderList` 重新计算 `sortedDisabledProviders` 并展示。

## 小白阅读顺序

建议按这个顺序读：

1. 先读 `index.tsx`  
   重点看 `ProviderMenu` 如何在 `SkeletonList`、`ProviderList`、`SearchResult` 之间切换，以及 `Layout` 如何放置搜索框和新增按钮。

2. 再读 `List.tsx`  
   这是菜单业务最集中的文件。先理解三个 selector：`enabledAiProviderList`、`disabledAiProviderList`、`disabledCustomAiProviderList`，再看三个 `AccordionItem`。

3. 然后读 `Item.tsx` 和 `All.tsx`  
   这两个文件解释了菜单项如何高亮、点击和展示图标。尤其要注意 active 状态来自 `location.pathname`，不是从父组件传入。

4. 接着读 `SearchResult.tsx`  
   理解搜索不是请求后端，而是在当前 `aiProviderList` 上做前端过滤。

5. 再读 `SortProviderModal/index.tsx` 和 `GroupItem.tsx`  
   看拖拽排序如何把列表顺序转换成 `{ id, sort }[]` 并提交给 store。

6. 最后读调用方 `src/routes/(main)/settings/provider/index.tsx`  
   这里能看到 `onProviderSelect` 最终如何变成 `navigate('/settings/provider/${providerKey}')`，也能理解菜单和右侧详情页之间的关系。

如果还想继续追数据来源，可以再读：

- `src/store/aiInfra/slices/aiProvider/action.ts`
- `src/store/aiInfra/slices/aiProvider/selectors.ts`
- `packages/types/src/aiProvider.ts`

## 常见误区

第一个误区：以为 `ProviderMenu` 负责详情页渲染。  
实际上它只负责菜单导航、搜索、新增入口和排序入口。详情页选择逻辑在 `src/routes/(main)/settings/provider/detail/index.tsx`。

第二个误区：以为所有 Provider 都按同一种规则排序。  
不是。已启用 Provider 由 `enabledAiProviderList` 按 `sort` 字段排序；禁用内置 Provider 可以按 global store 中的 `disabledModelProvidersSortType` 做默认、字母升序、字母降序；禁用自定义 Provider 单独分组展示。

第三个误区：以为搜索会改变路由。  
搜索只改变 `providerSearchKeyword`，并切换菜单内容为 `SearchResult`。只有点击某个搜索结果时，才会通过 `onProviderSelect` 触发路由或 query 参数变化。

第四个误区：以为 `ProviderItem` 的 active 状态来自父组件。  
当前实现中，`ProviderItem` 自己用 `useLocation()` 解析 pathname。也就是说，在旧的 query 参数 fallback 页面中，如果路径没有 `/settings/provider/:providerId` 结构，active 判断可能和 query state 不完全一致。根据当前片段推断，这也是为什么新路由模式下它更自然：pathname 本身就包含 providerId。

第五个误区：以为新增 Provider 的完整逻辑在 `AddNew.tsx`。  
`AddNew.tsx` 只是打开 `CreateNewProvider` 弹窗。创建表单、提交、创建后跳转等逻辑在 `src/routes/(main)/settings/provider/features/CreateNewProvider` 中。

第六个误区：把 `custom` 分组理解为“所有自定义 Provider”。  
这里展示的是 `disabledCustomProviderList`，即“未启用的自定义 Provider”。已启用的自定义 Provider 会进入 enabled 分组。

第七个误区：忽略 `mobile` 参数。  
`mobile` 会影响容器宽度、滚动方式，并且移动端不会显示 `All` 菜单项。在移动布局中，`MobileLayout` 还会根据 query 参数决定显示菜单还是详情内容。

第八个误区：认为排序弹窗能排序所有 Provider。  
`SortProviderModal` 传入的是 `enabledModelProviderList`，因此它调整的是已启用 Provider 的顺序。禁用 Provider 的排序只是本地展示偏好，不会调用 `updateAiProviderSort`。

第九个误区：忽略 Provider 数据来自 SWR hook。  
`useFetchAiProviderList()` 是在 `ProviderMenu` 的 `Layout` 中调用的。这个 hook 既负责请求，也在 `onSuccess` 中写入 aiInfra store。阅读时不要只看 `ProviderList`，否则会找不到列表数据从哪里初始化。

第十个误区：认为 `SearchResult` 的过滤逻辑一定随列表变化实时更新。  
当前 `SearchResult` 的 `useMemo` 依赖只有 `searchKeyword`，但内部使用了 `aiProviderList`。如果列表在关键词不变时发生变化，搜索结果可能不会重新计算。这个判断基于当前文件片段，是阅读和维护时需要特别留意的点。
