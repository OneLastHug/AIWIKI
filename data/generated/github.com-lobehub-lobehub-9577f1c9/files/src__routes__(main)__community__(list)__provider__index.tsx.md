# 文件：src/routes/(main)/community/(list)/provider/index.tsx

## 它负责什么

这个文件是社区发现页里“Provider 列表”这一屏的路由入口。它本身不承载业务逻辑，更像一个薄壳：从 URL 读取筛选和分页参数，调用 discover store 拉取 Provider 列表，然后在数据可用时组合渲染列表和分页器。

从结构上看，它属于 `src/routes/(main)` 下的页面段文件，符合仓库里“`routes` 只负责页面组装，具体 UI 和业务下沉到 features/store”的约定。当前文件就是这种典型写法。

## 关键组成

核心代码只有一层，阅读重点很集中：

- `useQuery()`：从地址栏读取 `q`、`page`、`sort`、`order`，并断言成 `ProviderQueryParams`。
- `useDiscoverStore((s) => s.useProviderList)`：从 discover 的 zustand store 里取出 Provider 列表查询方法。
- `useProviderList({...})`：用查询参数发起数据请求，固定 `pageSize: 21`。
- `Loading`：当 `isLoading` 或 `data` 为空时，直接返回加载态。
- `List`：拿到 `items` 后渲染 Provider 列表。
- `Pagination`：把 `currentPage`、`pageSize`、`totalCount` 传给分页组件，并用 `DiscoverTab.Providers` 标记当前 tab。

这个页面还被 `memo` 包了一层，说明它希望在 props 恒定时减少无意义重渲染。由于它本身没有 props，主要收益来自避免父级重渲染时重复执行页面树。

## 上下游关系

上游主要有三类：

- 路由系统：它是 `src/routes/(main)/community/(list)/provider/` 下的页面入口，通常由同目录路由配置或上层 layout 挂载。
- URL 查询参数：`useQuery` 读到的 `q/page/sort/order` 决定列表内容，说明这个页面是“可被地址栏驱动”的。
- discover 数据层：`useDiscoverStore` 来自 `src/store/discover`，而该入口又导出 `getDiscoverStoreState`、`useDiscoverStore` 等，说明真正的数据和缓存逻辑都在 store/slice 里。

下游主要有两个本地组件和一个加载页：

- `./features/List`：负责 Provider 卡片或条目本身的展示。
- `../features/Pagination`：这是列表级共用分页组件，说明社区列表页之间共享分页 UI。
- `./loading`：专门给这个页面的骨架屏或占位态。

根据当前片段推断，`useProviderList` 最终对应的是 `src/store/discover/slices/provider/*`，并且很可能通过 discover 的服务层去请求后端数据。依据是 store 目录里确实存在 `slices/provider/action.ts` 和 `src/services/discover.ts` 这类配套文件。

## 运行/调用流程

1. 用户进入 Provider 列表路由。
2. 页面组件先执行 `useQuery()`，从 URL 里取出筛选条件和页码。
3. 组件通过 `useDiscoverStore` 取到 `useProviderList` 查询函数。
4. `useProviderList` 按 `order/page/pageSize/q/sort` 发起请求或读取缓存。
5. 请求未完成时，页面直接返回 `Loading`。
6. 数据到位后，取出 `items/currentPage/pageSize/totalCount`。
7. 页面渲染 `List` 展示 Provider 条目，再渲染 `Pagination` 负责翻页。
8. 分页或筛选变化后，URL 参数变动，下一轮渲染重新走查询流程。

## 小白阅读顺序

1. 先读 [本文件](src/routes/(main)/community/(list)/provider/index.tsx)，把页面骨架看明白。
2. 再看 `src/hooks/useQuery.ts`，理解它怎么把 URL 参数喂给页面。
3. 然后看 `src/store/discover/index.ts`，确认 discover store 的导出入口。
4. 接着沿 `src/store/discover/slices/provider/*` 找 `useProviderList` 的实现。
5. 最后补看 `./features/List`、`../features/Pagination` 和 `./loading`，把展示层补全。

## 常见误区

- 误以为这个文件负责数据请求细节。实际上它只是调用 store 的查询方法，真正的请求逻辑大概率在 `store/discover` 或其 provider slice 里。
- 误以为 `pageSize: 21` 是页面可配置项。这里是硬编码常量，说明这个列表的展示密度是产品设计的一部分。
- 只看 `List` 不看 `Pagination`。这个页面的分页状态依赖 URL 和分页组件，单看列表会漏掉翻页链路。
- 忽略 `Loading`。这个页面把“无数据”和“加载中”都统一拦截掉了，真实列表只会在 `data` 存在时渲染。
- 把它当成通用列表壳。其实它是 `DiscoverTab.Providers` 的专用页，和同目录下的 `agent`、`model`、`skill`、`mcp` 等列表页是兄弟关系，复用的是模式，不是同一个实现。
