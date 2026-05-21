# 文件：src/routes/(main)/community/(list)/model/index.tsx

## 它负责什么

`src/routes/(main)/community/(list)/model/index.tsx` 是社区模型列表页的页面组件，负责渲染 `/community/model` 这个列表入口下的主体内容。

它本身不直接写复杂 UI，也不直接请求后端接口，而是做三件事：

1. 从当前 URL 查询参数中读取筛选、排序、分页条件。
2. 通过 `useDiscoverStore` 取出 `useModelList`，交给 discover store / SWR 去拉取模型列表数据。
3. 根据加载状态渲染 `Loading`，数据就绪后渲染模型 `List` 和通用 `Pagination`。

从架构上看，它是一个典型的“薄路由页面组件”：页面文件只负责把路由参数、数据 hook、展示组件连接起来，具体列表项 UI、分类栏、分页跳转、数据服务都放在邻近 feature 或 store/service 中。

## 关键组成

这个文件的核心代码结构很短：

```tsx
'use client';

const ModelPage = memo<{ mobile?: boolean }>(() => {
  const { q, page, category, sort, order } = useQuery() as ModelQueryParams;
  const useModelList = useDiscoverStore((s) => s.useModelList);

  const { data, isLoading } = useModelList({
    category,
    order,
    page,
    pageSize: 21,
    q,
    sort,
  });

  if (isLoading || !data) return <Loading />;

  const { items, currentPage, pageSize, totalCount } = data;

  return (
    <Flexbox gap={32} width={'100%'}>
      <List data={items} />
      <Pagination
        currentPage={currentPage}
        pageSize={pageSize}
        tab={DiscoverTab.Models}
        total={totalCount}
      />
    </Flexbox>
  );
});

export default ModelPage;
```

关键 import 可以分成几类：

`@lobehub/ui`

- `Flexbox`：页面主体容器，用来垂直排列列表和分页器。
- 这里没有自己写 CSS，布局只依赖 `Flexbox gap={32} width="100%"`。

`react`

- `memo`：包裹 `ModelPage`，减少无意义重渲染。
- 组件声明里有 `memo<{ mobile?: boolean }>`，说明外部可能按统一页面接口传入 `mobile`，但当前实现没有使用这个 prop。

本地 hook / store

- `useQuery` 来自 `@/hooks/useQuery`，用于读取当前路由的 query string。
- `useDiscoverStore` 来自 `@/store/discover`，这里通过 selector 只取 `s.useModelList`，避免订阅整个 store。
- `ModelQueryParams` 来自 `@/types/discover`，用于告诉 TypeScript 当前 query 参数形状包含 `q`、`page`、`category`、`sort`、`order` 等字段。
- `DiscoverTab` 来自 `@/types/discover`，其中 `DiscoverTab.Models` 被传给分页组件，用来生成 `/community/model?...` 这样的分页跳转地址。

邻近组件

- `Pagination` 来自 `../features/Pagination`，是社区列表页共用分页器。
- `List` 来自 `./features/List`，是模型列表专用网格组件。
- `Loading` 来自 `./loading`，是模型列表页的加载骨架屏。

`List` 的邻近实现显示，它接收 `DiscoverModelItem[]`，为空时显示 `ModelEmpty`，否则用 `Grid` 渲染每个 `Item`：

```tsx
const ModelList = memo<ModelListProps>(({ data = [], rows = 3 }) => {
  if (data.length === 0) return <ModelEmpty />;

  return (
    <Grid rows={rows} width={'100%'}>
      {data.map((item, index) => (
        <Item key={index} {...item} />
      ))}
    </Grid>
  );
});
```

这说明目标文件只关心“有没有数据”和“把 items 交给 List”，并不关心每张模型卡片怎么展示。

`Loading` 的邻近实现只是：

```tsx
export { default } from '../../components/ListLoading';
```

也就是说模型页没有独立骨架屏，而是复用社区列表页通用的 `ListLoading`。

## 上下游关系

上游入口主要来自社区路由和导航。

在社区侧边导航中，`DiscoverTab.Models` 对应的 URL 是：

```ts
/community/model
```

目标文件就是这个路径下的列表页面主体。它不是整个页面的唯一内容，因为同目录还有 `_layout/index.tsx`：

```tsx
const Layout = () => {
  return (
    <Flexbox horizontal className={styles.mainContainer} gap={24} width={'100%'}>
      <CategoryContainer>
        <Category />
      </CategoryContainer>
      <Flexbox flex={1} gap={16}>
        <Outlet />
      </Flexbox>
    </Flexbox>
  );
};
```

因此实际页面结构是：

1. `model/_layout/index.tsx` 先渲染左右结构。
2. 左侧 `CategoryContainer` 内放 `Category` 分类筛选。
3. 右侧 `Outlet` 才渲染当前目标文件的 `ModelPage`。
4. `ModelPage` 内部再渲染 `List` 和 `Pagination`。

数据下游链路是：

```txt
ModelPage
  -> useQuery()
  -> useDiscoverStore((s) => s.useModelList)
  -> useModelList(params)
  -> useSWR(...)
  -> discoverService.getModelList(...)
  -> data.items / currentPage / pageSize / totalCount
  -> List + Pagination
```

`useModelList` 在 `src/store/discover/slices/model/action.ts` 中定义。它会读取当前语言：

```ts
const locale = globalHelpers.getCurrentLanguage();
```

然后用 SWR 缓存键：

```ts
['model-list', locale, ...Object.values(params)].filter(Boolean).join('-')
```

并调用：

```ts
discoverService.getModelList({
  ...params,
  page: params.page ? Number(params.page) : 1,
  pageSize: params.pageSize ? Number(params.pageSize) : 21,
})
```

这说明目标文件传入的 `page` 可能来自 URL 字符串，最终在 store 层会被转成数字。目标文件强制传入 `pageSize: 21`，store 里也有默认值 `21`，两边保持一致。

分页组件的下游行为也很关键。`Pagination` 接收 `tab={DiscoverTab.Models}` 后，在翻页时会：

1. 读取当前 `location.search`。
2. 修改其中的 `page`。
3. 跳转到：

```ts
/community/${tab}?${searchParams.toString()}
```

当 `tab` 是 `DiscoverTab.Models` 时，目标就是 `/community/model?page=...`。

它还会根据桌面/移动端滚动到顶部：

- 移动端滚动容器：`lobe-mobile-scroll-container`
- 桌面端滚动容器：`SCROLL_PARENT_ID`

这意味着目标文件只传递分页元数据，真正的 URL 更新和滚动行为由共用 `Pagination` 负责。

另外，模型列表项本身还会链接到详情页。邻近 `Item.tsx` 中可以看到它会构造类似：

```ts
/community/model/${identifier}
```

的详情链接。因此列表页的下游还包括模型详情页：

```txt
/community/model
  -> 点击某个模型
  -> /community/model/:identifier
```

## 运行/调用流程

一次完整访问 `/community/model` 的流程可以按下面理解：

1. 用户从社区导航进入 `/community/model`，或者手动访问带 query 的地址，例如：

```txt
/community/model?q=gpt&page=2&category=llm&sort=createdAt&order=desc
```

2. React Router 匹配到社区列表路由，并先渲染 `model/_layout/index.tsx`。

3. `_layout` 渲染分类栏 `Category`，再通过 `<Outlet />` 渲染目标文件导出的 `ModelPage`。

4. `ModelPage` 执行：

```ts
const { q, page, category, sort, order } = useQuery() as ModelQueryParams;
```

从 URL query 中取出查询词、页码、分类、排序字段和排序方向。

5. `ModelPage` 从 discover store 中取出模型列表 hook：

```ts
const useModelList = useDiscoverStore((s) => s.useModelList);
```

注意这里取得的是一个 hook 风格的 action，而不是直接取得列表数据。

6. `ModelPage` 调用 `useModelList`：

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

7. `useModelList` 内部通过 SWR 请求 `discoverService.getModelList`。SWR 会负责缓存、加载状态和响应数据管理。

8. 请求未完成或数据为空时，目标文件返回：

```tsx
<Loading />
```

这个 `Loading` 实际复用社区列表通用 `ListLoading`。

9. 数据回来后，目标文件解构：

```ts
const { items, currentPage, pageSize, totalCount } = data;
```

这些字段分别用于：

- `items`：传给 `List data={items}`，渲染模型网格。
- `currentPage`：传给分页器当前页。
- `pageSize`：传给分页器每页数量。
- `totalCount`：传给分页器总数量。

10. 页面最终渲染结构是：

```tsx
<Flexbox gap={32} width="100%">
  <List data={items} />
  <Pagination
    currentPage={currentPage}
    pageSize={pageSize}
    tab={DiscoverTab.Models}
    total={totalCount}
  />
</Flexbox>
```

11. 用户点击分页器时，`Pagination` 会更新 URL 中的 `page` 参数并导航到新的 `/community/model?...` 地址。URL 变化后，`useQuery()` 读到新参数，`useModelList()` 的 SWR key 变化，从而触发新一页数据加载。

根据当前片段推断，分类切换和排序切换也应该通过修改 URL query 实现，因为目标文件唯一的数据输入来源就是 `useQuery()`，且它把 `category`、`sort`、`order` 原样传入 `useModelList`。

## 小白阅读顺序

建议按下面顺序读，不要一上来就跳进 store 或 service：

1. 先读目标文件 `src/routes/(main)/community/(list)/model/index.tsx`

先理解它只有三个状态：

- 正在加载：返回 `Loading`
- 没有数据对象：也返回 `Loading`
- 有数据：返回 `List + Pagination`

重点看这行：

```ts
const { q, page, category, sort, order } = useQuery() as ModelQueryParams;
```

它说明这个页面是“URL query 驱动”的。

2. 再读 `model/_layout/index.tsx`

理解目标文件不是独立占满整个页面，而是放在模型列表布局右侧。左侧分类栏由 layout 负责，目标文件只负责右侧列表内容。

3. 再读 `model/features/List/index.tsx`

这里可以看到 `items` 到 UI 的第一层转换：

- 空数组显示 `ModelEmpty`
- 非空数组用 `Grid` 渲染 `Item`

这一步能帮助你明确：目标文件不管卡片细节，只把 `items` 交给 `List`。

4. 再读 `src/routes/(main)/community/(list)/features/Pagination.tsx`

重点看 `handlePageChange`。它解释了为什么目标文件要传 `tab={DiscoverTab.Models}`：分页器需要知道当前是 models tab，才能导航到 `/community/model?...`。

5. 最后读 `src/store/discover/slices/model/action.ts`

重点看 `useModelList`：

```ts
useModelList = (params: ModelQueryParams = {}): SWRResponse<ModelListResponse> => {
  const locale = globalHelpers.getCurrentLanguage();
  return useSWR(
    ['model-list', locale, ...Object.values(params)].filter(Boolean).join('-'),
    async () =>
      discoverService.getModelList({
        ...params,
        page: params.page ? Number(params.page) : 1,
        pageSize: params.pageSize ? Number(params.pageSize) : 21,
      }),
    {
      revalidateOnFocus: false,
    },
  );
};
```

读懂这里后，目标文件的数据来源、缓存刷新条件、默认分页大小就都清楚了。

## 常见误区

1. 误以为 `ModelPage` 直接请求接口

它没有直接 import `discoverService`，也没有写 `fetch`。真正的数据请求被封装在 `useDiscoverStore` 的 `useModelList` 中，而 `useModelList` 又通过 SWR 调用 `discoverService.getModelList`。

2. 误以为 `page` 一定是数字

`page` 来自 `useQuery()`，通常是 URL query 字符串。目标文件直接把它传给 `useModelList`，实际转数字发生在 store 层：

```ts
page: params.page ? Number(params.page) : 1
```

所以不要在目标文件里假设 `page` 已经是 number。

3. 误以为 `pageSize: 21` 只在一个地方定义

目标文件显式传了 `pageSize: 21`，store 层也有默认 `21`。这意味着当前模型列表页每页 21 条是页面和数据层共同维持的约定。修改时要注意两边是否需要同步。

4. 误以为空列表会显示 Loading

目标文件只在 `isLoading || !data` 时显示 `Loading`。如果请求成功但 `items` 是空数组，目标文件会继续渲染 `List data={items}`，然后 `List` 内部显示 `ModelEmpty`。所以“没有 data”和“data.items 为空”是两个不同状态。

5. 误以为 `mobile?: boolean` 已经生效

组件类型声明里有：

```ts
memo<{ mobile?: boolean }>
```

但函数参数没有接收 props，内部也没有使用 `mobile`。移动端差异目前主要由外层路由、布局或 `Pagination` 里的 `useResponsive()` 处理，不是这个文件处理。

6. 误以为分页器只改变 UI 状态

分页器不是本地 state 分页，它会修改 URL：

```ts
navigate(`/community/${tab}?${searchParams.toString()}`);
```

URL 改变后，`useQuery()` 重新读参数，SWR key 变化，再重新请求数据。这是典型的“URL 作为列表状态来源”的实现。

7. 误以为 `List` 的 `key={index}` 一定代表稳定身份

当前 `List` 用数组下标作为 key：

```tsx
<Item key={index} {...item} />
```

这在纯列表展示中通常可运行，但如果列表项未来有复杂内部状态、局部动画或可重排交互，使用稳定 ID 会更稳。这里目标文件不处理这个问题，只负责传入 `items`。

8. 误以为分类栏属于目标文件

分类栏在 `model/_layout/index.tsx` 中渲染：

```tsx
<CategoryContainer>
  <Category />
</CategoryContainer>
```

目标文件只渲染右侧列表内容。因此如果要改分类 UI，不应该优先改 `index.tsx`，而应该看 `model/features/Category` 和 `_layout`。

9. 误以为 `DiscoverTab.Models` 只是显示标签

在目标文件中，`DiscoverTab.Models` 被传给 `Pagination`，会影响分页跳转路径。它不仅是语义枚举，也参与 URL 拼接。

10. 误以为这个文件可以随意加业务逻辑

根据仓库约定，`src/routes` 下的页面段应该保持薄，只组合 feature，不承载复杂业务逻辑。这个文件目前符合这种风格：查询参数、store hook、加载态、列表、分页。新增复杂 UI 或业务逻辑时，更合适的位置通常是 `src/features` 或当前路由邻近的 `features` 目录。
