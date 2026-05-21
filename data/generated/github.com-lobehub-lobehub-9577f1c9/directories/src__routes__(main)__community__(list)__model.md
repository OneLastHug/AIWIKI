# 目录：src/routes/(main)/community/(list)/model

## 它负责什么

`src/routes/(main)/community/(list)/model` 是社区页里“模型列表”这一分支的 SPA route 目录，核心职责是渲染 `/community/model` 页面：读取 URL 查询参数，向 `discover` store 请求模型列表和模型分类统计，然后展示左侧模型供应商分类、右侧模型卡片列表和分页器。

从当前目录可以看出，它不是一个纯粹的“薄 route 文件”目录，而是把一部分页面 UI 直接放在 route 目录内部：`_layout` 负责页面布局，`features/Category` 负责分类菜单，`features/List` 负责模型卡片列表。这和仓库说明中“新代码尽量把复杂 UI 放到 `src/features/*`”的推荐方向略有差异，更像社区模块已有的局部组织方式。

它处理的是“列表页”，不是模型详情页。模型卡片点击后会跳转到 `/community/model/{identifier}`，详情页根据当前片段推断在相邻目录 `src/routes/(main)/community/(detail)/model` 中实现。

## 关键组成

`index.tsx` 是模型列表页主体。

它通过 `useQuery()` 读取 URL 参数：

```ts
const { q, page, category, sort, order } = useQuery() as ModelQueryParams;
```

这些参数分别用于搜索关键词、页码、分类、排序字段和排序方向。随后从 `useDiscoverStore` 取出 `useModelList`，请求列表数据：

```ts
const { data, isLoading } = useModelList({
  category,
  order,
  page,
  pageSize: 21,
  q,
  sort,
});
```

加载中或没有数据时返回 `Loading`，有数据后解构 `items/currentPage/pageSize/totalCount`，渲染：

- `List data={items}`：模型卡片网格
- `Pagination`：通用社区分页器，`tab` 传入 `DiscoverTab.Models`

`_layout/index.tsx` 是模型列表分支的布局。

它使用 `@lobehub/ui` 的 `Flexbox` 做横向布局：

- 左侧：`CategoryContainer` 包住 `Category`
- 右侧：`Outlet`

这里的 `Outlet` 说明该目录下可能存在嵌套路由结构：布局先固定分类栏，实际列表内容由子 route 渲染。根据当前片段推断，`model/_layout` 应该被路由配置挂到 `/community/model` 分支外层。

`_layout/style.ts` 只定义了一个静态样式：

```ts
mainContainer: css`
  position: relative;
`
```

它使用 `createStaticStyles`，符合仓库偏好的零运行时 CSS-in-JS 写法。

`features/Category/index.tsx` 是左侧分类菜单。

它读取查询参数中的 `category` 和 `q`，默认分类为 `all`。然后通过 `useDiscoverStore((s) => s.useModelCategories)` 请求模型分类统计：

```ts
const { data: items = [] } = useModelCategories({ q });
```

分类数据来自两个来源：

- 菜单结构来自 `useCategory()`
- 每个分类的数量来自 `useModelCategories({ q })`

它用 `query-string` 的 `qs.stringifyUrl` 生成跳转 URL：

```ts
/community/model?category=xxx&q=...
```

当点击 `all` 时，`category` 会被设为 `null`，并通过 `skipNull: true` 从 URL 中省略。这意味着“全部模型”不是 `category=all`，而是没有 `category` 参数。

点击分类后，它还会找到 `SCROLL_PARENT_ID` 对应的滚动容器并滚动到顶部，避免切换分类后用户仍停留在列表中部或底部。

`features/Category/useCategory.tsx` 负责生成模型分类配置。

它从 `model-bank/modelProviders` 的 `DEFAULT_MODEL_PROVIDER_LIST` 读取供应商列表，用 `uniqBy` 按 `id` 去重，再生成菜单项：

- `key`: provider id
- `label`: provider name
- `icon`: `ProviderIcon`

同时在最前面插入一个 `all` 分类，显示文案来自 `discover` 命名空间：

```ts
t('mcp.categories.all.name')
```

这里复用了 `mcp.categories.all.name` 这个 i18n key。功能上可用，但从语义上看容易让读者误以为模型页依赖 MCP 分类。更准确的 key 理想上应该属于 model 分类，但当前实现选择了复用已有“全部”文案。

`features/List/index.tsx` 是列表容器。

它接收 `DiscoverModelItem[]`，默认 `rows=3`。如果没有数据，展示 `ModelEmpty`；否则使用 `@lobehub/ui` 的 `Grid` 渲染每个 `Item`。

需要注意，这里 `key` 用的是数组下标：

```tsx
<Item key={index} {...item} />
```

如果列表排序、过滤或分页变化频繁，用稳定的 `identifier` 通常会更合适。不过当前代码没有在这个任务中修改，只作为阅读时的注意点。

`features/List/Item.tsx` 是单个模型卡片。

它接收 `DiscoverModelItem` 的主要字段：

- `identifier`
- `displayName`
- `contextWindowTokens`
- `releasedAt`
- `type`
- `abilities`
- `providers`

卡片展示内容包括：

- 模型头像：`ModelIcon`
- 模型显示名：`displayName`
- 模型标识：`identifier`
- 模型类型图标：`ModelTypeIcon`
- 能力标签和上下文窗口：`ModelInfoTags`
- 模型描述：`t(`${identifier}.description`)`
- 发布时间：`PublishedTime`
- 支持该模型的 providers 图标列表

卡片整体和标题链接都会指向：

```ts
/community/model/{identifier}
```

这里用 `urlJoin('/community/model', identifier)` 拼出详情页路径。卡片外层也绑定了 `onClick={() => navigate(link)}`，所以点击卡片区域会进入详情。

`features/List/ModelTypeIcon.tsx` 是模型类型到图标的映射。

它把 `AiModelType` 映射到 lucide icon：

- `chat`：`MessageSquareTextIcon`
- `embedding`：`BoltIcon`
- `image`：`ImageIcon`
- `realtime`：`PhoneIcon`
- `stt`：`MicIcon`
- `text2music`：`MusicIcon`
- `tts`：`AudioLines`
- `video`：`VideoIcon`

图标外层带 `Tooltip`，标题为 `${startCase(type)} Model`，例如 `Chat Model`、`Text 2 Music Model`。

`features/const.ts` 构建了一个 `providerMap`。

它遍历 `DEFAULT_MODEL_PROVIDER_LIST`，只保留 `chatModels.length > 0` 的 provider，把 `id -> name` 放入对象并导出。根据当前片段，目标目录中没有看到它被使用，可能是历史遗留、被其他文件间接引用，或曾用于展示 provider 名称。

`loading.tsx` 直接复用社区列表通用 loading：

```ts
export { default } from '../../components/ListLoading';
```

## 上下游关系

上游主要有三类。

第一类是路由系统。根据目录结构和 `react-router-dom` 的 `Outlet`、`Link`、`useNavigate` 使用方式推断，该目录由 `src/spa/router` 中的 SPA 路由配置挂载到社区列表分支。它对应的公开路径是 `/community/model`，这个结论来自代码中的显式 URL：

```ts
url: '/community/model'
urlJoin('/community/model', identifier)
```

第二类是社区公共布局和组件。当前目录复用了上层社区模块的多个组件：

- `../../../components/CategoryContainer`
- `../../../../components/CategoryMenu`
- `../features/Pagination`
- `../../components/ListLoading`
- `../../../../features/ModelEmpty`

这些相对路径说明 `model` 页面不是孤立页面，而是社区列表体系的一员，与 `agent`、`mcp`、`provider`、`skill` 等相邻列表页共享布局、空状态、分页、loading 和分类菜单样式。

第三类是数据和类型来源。页面不直接调用 API，而是通过 store hook 获取数据：

- `useDiscoverStore((s) => s.useModelList)`
- `useDiscoverStore((s) => s.useModelCategories)`

类型来自：

- `ModelQueryParams`
- `DiscoverModelItem`
- `DiscoverTab`

模型供应商和模型类型来自 `model-bank`：

- `DEFAULT_MODEL_PROVIDER_LIST`
- `AiModelType`

下游主要是两个方向。

一个方向是模型详情页。`Item.tsx` 中生成 `/community/model/{identifier}`，点击模型卡片后进入详情页。根据当前片段推断，详情页在相邻的 `src/routes/(main)/community/(detail)/model` 目录中。

另一个方向是滚动容器和 URL 状态。分类点击不仅更新 URL，还会操作 `SCROLL_PARENT_ID` 对应的 DOM 元素滚动到顶部。也就是说，分类状态由 URL query 表达，滚动行为由社区外层布局提供的容器配合完成。

## 运行/调用流程

用户访问 `/community/model` 时，SPA 路由进入社区模型列表分支。

如果路由匹配到 `model/_layout/index.tsx`，页面先渲染横向布局：左侧分类栏，右侧嵌套路由出口。分类栏中的 `Category` 会立即读取当前 URL 查询参数，尤其是 `q` 和 `category`。

`Category` 调用 `useModelCategories({ q })` 获取当前搜索条件下各模型供应商分类的数量。与此同时，`useCategory()` 从 `DEFAULT_MODEL_PROVIDER_LIST` 生成供应商菜单，并插入 `all` 项。最终 `CategoryMenu` 根据当前 `category` 高亮对应项，并在每项右侧展示数量 `Tag`。

右侧列表页由 `model/index.tsx` 渲染。它读取 URL 中的 `q/page/category/sort/order`，调用 `useModelList` 请求分页模型数据。请求参数固定包含 `pageSize: 21`，所以单页最多展示 21 个模型。

如果数据还在加载，渲染 `ListLoading`。加载完成后，页面把 `items` 交给 `List`。`List` 如果发现 `items` 为空，则展示 `ModelEmpty`；否则使用 `Grid` 渲染模型卡片。

每个 `Item` 展示模型基本信息、能力标签、描述、发布时间和 provider 图标。描述文案不是从接口字段直接取，而是通过 `models` i18n 命名空间按 `identifier.description` 查找。这意味着新增模型时，除了数据本身，还需要有对应的模型描述翻译，否则描述可能缺失或显示 fallback。

用户点击左侧分类时，`Category` 会用 `qs.stringifyUrl` 生成新的 `/community/model` URL，并保留当前搜索词 `q`。点击后执行 `navigate`，页面 URL 改变，`useQuery()` 读到新参数，分类统计和模型列表重新请求。同时滚动容器回到顶部。

用户点击模型卡片时，`Item` 使用 `navigate(link)` 跳转到 `/community/model/{identifier}`。标题本身也包了一层 `Link`，所以直接点标题同样进入详情页。

## 小白阅读顺序

1. 先看 `index.tsx`。这是列表页主入口，能最快理解“从 URL 取参数 -> 调 store -> loading -> list + pagination”的主线。

2. 再看 `features/List/index.tsx`。它很短，只负责判断空状态和渲染网格，适合理解列表数据如何进入卡片。

3. 接着看 `features/List/Item.tsx`。这里是页面信息密度最高的文件，能看到一个模型卡片到底展示了哪些字段，以及点击后如何进入详情页。

4. 然后看 `_layout/index.tsx`。它解释为什么模型页左侧有分类栏，右侧是列表内容，也能帮助理解 `Outlet` 在这个目录中的作用。

5. 再看 `features/Category/index.tsx`。重点关注 `useQuery()`、`useModelCategories()`、`genUrl()` 和 `handleClick()`，这几个点串起来就是分类筛选的完整流程。

6. 最后看 `features/Category/useCategory.tsx` 和 `features/List/ModelTypeIcon.tsx`。这两个文件分别是“供应商分类配置”和“模型类型图标配置”，属于辅助映射，适合在理解主流程后再读。

## 常见误区

不要把这个目录理解成模型详情页。它负责的是 `/community/model` 列表；`/community/model/{identifier}` 是从卡片跳转出去的详情路径，根据当前片段推断由相邻的 `(detail)/model` 目录处理。

不要以为 `category=all` 会出现在 URL 中。代码里点击 `all` 时会把 `category` 设置为 `null`，并通过 `skipNull: true` 省略该参数。因此“全部”状态通常表现为没有 `category` query。

不要以为左侧分类来自服务端完整返回。分类菜单的主体来自本地 `model-bank/modelProviders` 的 `DEFAULT_MODEL_PROVIDER_LIST`；服务端或 store 返回的 `useModelCategories({ q })` 更像是给这些分类补充数量统计。

不要以为模型描述一定来自 `DiscoverModelItem`。卡片描述使用的是：

```ts
t(`${identifier}.description`)
```

也就是从 `models` i18n 资源里按模型 identifier 查描述。数据项里即使有其他描述字段，当前卡片也没有使用。

不要忽略 `q` 对分类统计的影响。`Category` 调 `useModelCategories({ q })`，所以当用户搜索时，左侧分类数量应该是搜索结果范围内的统计，而不是全站总数。

不要把 `features/const.ts` 当成主流程必读文件。它导出了 `providerMap`，但在当前读取到的目标目录文件中没有使用。根据当前片段推断，它可能是历史遗留或供未来/外部文件使用；理解页面运行不依赖它。

不要误解 `ModelTypeIcon` 的 `icons?.[type]` 一定总能取到图标。它的类型声明覆盖了当前 `AiModelType`，但如果上游模型类型扩展而这里没同步，运行时可能出现没有对应 icon 的情况。阅读时可以把它看成一个需要随 `model-bank` 类型演进而维护的映射表。

不要忽视这个目录的组织方式和仓库新约定之间的差异。仓库说明建议 route 文件保持轻薄，把业务 UI 放到 `src/features/*`；但这里仍在 route 目录内放了 `features`。读代码时应以现有社区模块结构为准，新增或重构时再考虑是否迁移到全局 `src/features` 体系。
