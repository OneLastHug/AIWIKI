# 目录：src/routes/(main)/community/(list)/provider

## 它负责什么

`src/routes/(main)/community/(list)/provider` 是社区页里“模型服务商 / Provider 列表”的 SPA 路由页，对应用户访问的列表地址大致是：

```text
/community/provider
```

它的职责很集中：读取 URL 查询参数，调用 `discover` store 里的 provider 列表数据 hook，处理加载态，然后把结果交给 provider 列表组件和分页组件渲染。

这个目录不是 provider 详情页。详情页由另一个路由负责：

```text
src/routes/(main)/community/(detail)/provider
```

列表页点击某个 provider 后，会进入类似：

```text
/community/provider/:slug
```

也就是说，本目录负责“所有 provider 的列表入口”，不负责单个 provider 的详情展示、配置页面、模型支持详情等复杂逻辑。

## 关键组成

这个目录直接包含两个文件：

```text
src/routes/(main)/community/(list)/provider
├── index.tsx
└── loading.tsx
```

`index.tsx` 是页面主体。它是一个客户端组件：

```ts
'use client';
```

核心 import 可以分成几类：

```ts
import { Flexbox } from '@lobehub/ui';
import { memo } from 'react';
```

这部分负责 UI 容器和 React 性能包装。`ProviderPage` 最后通过 `memo` 包起来，说明这个页面组件本身没有复杂本地状态，主要依赖外部 hook 返回的数据。

```ts
import { useQuery } from '@/hooks/useQuery';
import { useDiscoverStore } from '@/store/discover';
import { type ProviderQueryParams } from '@/types/discover';
import { DiscoverTab } from '@/types/discover';
```

这部分是数据和类型来源。`useQuery` 读取当前 URL 查询参数；`useDiscoverStore` 提供 discover 领域的数据 hook；`ProviderQueryParams` 描述 provider 列表支持的查询参数；`DiscoverTab.Providers` 用来告诉分页组件当前 tab 是 provider。

```ts
import Pagination from '../features/Pagination';
import List from './features/List';
import Loading from './loading';
```

这部分是页面实际渲染的下游组件。`Pagination` 来自列表页公共 features，说明 agent、model、provider 等社区列表很可能共用同一套分页组件。`List` 是 provider 自己的列表展示组件。`Loading` 是本目录的加载态入口。

`ProviderPage` 的主体逻辑如下：

```ts
const { q, page, sort, order } = useQuery() as ProviderQueryParams;
const useProviderList = useDiscoverStore((s) => s.useProviderList);
const { data, isLoading } = useProviderList({
  order,
  page,
  pageSize: 21,
  q,
  sort,
});
```

这里有几个重点：

- `q`：搜索关键词。
- `page`：当前页码。
- `sort`：排序字段。
- `order`：排序方向。
- `pageSize: 21`：provider 列表固定每页请求 21 条。
- `useProviderList`：从 `discover` store 中取出的 provider 列表 hook。

如果还在加载，或者数据为空，就直接返回 loading：

```tsx
if (isLoading || !data) return <Loading />;
```

数据回来后，页面拆出分页字段：

```ts
const { items, currentPage, pageSize, totalCount } = data;
```

然后渲染：

```tsx
<Flexbox gap={32} width={'100%'}>
  <List data={items} />
  <Pagination
    currentPage={currentPage}
    pageSize={pageSize}
    tab={DiscoverTab.Providers}
    total={totalCount}
  />
</Flexbox>
```

这里可以看出页面本身没有负责“卡片怎么长”“provider 名称怎么翻译”“点击跳哪里”等展示细节，只是把 `items` 交给 `List`。

`loading.tsx` 非常薄：

```ts
export { default } from '../../components/ListLoading';
```

它复用社区列表通用的 `ListLoading`，避免 provider 列表单独维护一份骨架屏或加载 UI。

根据当前片段推断，`./features/List` 下面负责真正的 provider 卡片列表。已有片段显示其 `Item.tsx` 会使用类似 `urlJoin('/community/provider', identifier)` 的链接规则，并使用 `ProviderCombine` / `ProviderIcon` 一类组件展示 provider 标识，同时从 `providers`、`discover` 等 i18n namespace 读取文案。

## 上下游关系

上游入口主要有三类。

第一类是 SPA router。桌面路由配置中存在 provider 列表路由注册：

```text
src/spa/router/desktopRouter.config.tsx
src/spa/router/desktopRouter.config.desktop.tsx
```

这两个配置都包含 `provider` 路径。动态版配置会动态 import：

```text
@/routes/(main)/community/(list)/provider
```

同步版配置会静态 import：

```text
CommunityListProviderPage from '@/routes/(main)/community/(list)/provider'
```

这符合 LobeHub 的 SPA 路由约定：`src/routes` 里放页面片段，`src/spa/router` 里挂载实际路由树，并且桌面两份 router 配置需要保持一致。

第二类是社区页导航。邻近代码中可以看到社区侧边栏或 tab 导航会指向：

```text
/community/provider
```

例如社区布局里的 `Sidebar/Header/Nav.tsx` 和 `features/useNav.tsx` 会把 provider tab 导航到这个列表页。

第三类是其他详情页反向跳转。模型详情页、相关 provider 区块等会链接回 provider 列表或 provider 详情。例如：

```text
/community/provider
/community/provider/:id
```

下游关系主要是：

```text
ProviderPage
  -> useQuery()
  -> useDiscoverStore((s) => s.useProviderList)
  -> List
  -> Pagination
  -> Loading/ListLoading
```

其中 `useDiscoverStore` 是最关键的数据入口。根据项目通用架构和当前 import 推断，它通常会继续通过 service/TRPC 或其他 discover 数据服务拉取数据，但本目录没有直接接触 API、TRPC router 或数据库。

`Pagination` 的 `tab={DiscoverTab.Providers}` 也很重要。它说明分页组件不是简单的页码 UI，而是知道当前属于 discover 的哪个列表 tab。切页时它需要保留或更新 provider 列表相关的 URL/query 状态。

## 运行/调用流程

用户访问：

```text
/community/provider?q=xxx&page=2&sort=identifier&order=asc
```

大致流程是：

1. `src/spa/router/desktopRouter.config.tsx` 或 `desktopRouter.config.desktop.tsx` 匹配到 community 下的 `provider` 子路由。

2. router 加载本目录的默认导出组件，也就是 `ProviderPage`。

3. `ProviderPage` 调用 `useQuery()` 读取 URL query，并把结果断言为 `ProviderQueryParams`：

   ```ts
   const { q, page, sort, order } = useQuery() as ProviderQueryParams;
   ```

4. 页面从 `useDiscoverStore` 中取出 `useProviderList`：

   ```ts
   const useProviderList = useDiscoverStore((s) => s.useProviderList);
   ```

5. 页面调用 `useProviderList` 请求列表数据：

   ```ts
   useProviderList({
     order,
     page,
     pageSize: 21,
     q,
     sort,
   });
   ```

6. 如果 `isLoading` 为 true，或者 `data` 还不存在，就渲染 `Loading`。而 `Loading` 实际上是：

   ```ts
   ../../components/ListLoading
   ```

7. 数据返回后，页面从 `data` 中拿到：

   ```ts
   items
   currentPage
   pageSize
   totalCount
   ```

8. 页面渲染 provider 列表：

   ```tsx
   <List data={items} />
   ```

9. 页面渲染分页器：

   ```tsx
   <Pagination
     currentPage={currentPage}
     pageSize={pageSize}
     tab={DiscoverTab.Providers}
     total={totalCount}
   />
   ```

10. 用户点击某个 provider 卡片时，根据当前片段和邻近搜索结果推断，列表项会跳到：

   ```text
   /community/provider/:identifier
   ```

   这个详情页由 `src/routes/(main)/community/(detail)/provider` 负责，不在本目录中。

## 小白阅读顺序

建议按这个顺序读，不要一上来就追到 store 或后端：

1. 先读：

   ```text
   src/routes/(main)/community/(list)/provider/index.tsx
   ```

   目标是看懂页面做了哪三件事：读 query、拉列表、渲染 `List` 和 `Pagination`。

2. 再读：

   ```text
   src/routes/(main)/community/(list)/provider/loading.tsx
   ```

   这个文件很短，但能帮助你理解：社区列表页的加载态是公共组件，不是 provider 独有组件。

3. 接着读 provider 自己的列表实现：

   ```text
   src/routes/(main)/community/(list)/provider/features/List
   ```

   重点看 `List` 如何接收 `data`，以及 `Item` 如何展示 provider 名称、图标、描述、模型数量、链接等。

4. 再读公共分页组件：

   ```text
   src/routes/(main)/community/(list)/features/Pagination
   ```

   重点理解 `DiscoverTab.Providers` 的作用，以及分页如何影响 URL query。

5. 然后看上游路由注册：

   ```text
   src/spa/router/desktopRouter.config.tsx
   src/spa/router/desktopRouter.config.desktop.tsx
   ```

   这里可以确认 `/community/provider` 是怎么被挂进 SPA 路由树的。

6. 最后再追数据层：

   ```text
   src/store/discover
   ```

   找 `useProviderList` 的定义，继续往 service 或接口层看。这样读会更顺，因为你已经知道页面真正需要的数据形状了。

## 常见误区

第一个误区是把这个目录当成 provider 详情页。它只负责 provider 列表。单个 provider 的详情页路径在：

```text
src/routes/(main)/community/(detail)/provider
```

列表页和详情页的 URL 很像，但职责不同：

```text
/community/provider          -> provider 列表
/community/provider/:slug    -> provider 详情
```

第二个误区是以为 `index.tsx` 里直接请求后端。实际不是。它通过：

```ts
useDiscoverStore((s) => s.useProviderList)
```

取得数据 hook。本目录不直接 import service、TRPC router 或 fetch 方法。根据当前片段推断，真实请求逻辑被封装在 discover store 或其下游 service 中。

第三个误区是忽略 URL query。这个页面的搜索、分页和排序都来自：

```ts
useQuery() as ProviderQueryParams
```

所以如果列表结果不对，不应该只看 `List` 组件，也要检查当前 URL 中的 `q`、`page`、`sort`、`order` 是否符合预期。

第四个误区是把 `pageSize` 当成后端返回值。请求时页面固定传入：

```ts
pageSize: 21
```

返回数据里也有 `pageSize`，用于传给 `Pagination`。阅读时要区分“请求参数里的 pageSize”和“响应数据里的 pageSize”。

第五个误区是认为 `loading.tsx` 是 React Router 的自动 loading boundary。这里它只是一个普通模块，被 `index.tsx` 手动 import 后在加载条件下渲染：

```tsx
if (isLoading || !data) return <Loading />;
```

它的默认导出来自公共的 `ListLoading`。

第六个误区是忘记这个目录仍然属于旧式社区 route 内聚结构。按照当前项目规范，新的复杂业务 UI 更推荐放到 `src/features`，而 `src/routes` 应保持薄页面。但这个目录下仍有 `features/List` 这样的 route-local features，属于现有社区页结构的一部分。阅读时应尊重现状：本目录的 `index.tsx` 已经很薄，真正 UI 细节在它的局部 `features/List` 中。
