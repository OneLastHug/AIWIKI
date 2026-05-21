# 目录：src/routes/(main)/community/(list)

## 它负责什么

`src/routes/(main)/community/(list)` 是桌面端 Community / Discover 页面里的“列表页族”。它不负责详情页，而是负责 `/community` 及其一级分类列表：

- `/community`：社区首页，展示精选助手和精选 MCP 工具。
- `/community/agent`：助手列表。
- `/community/mcp`：MCP 工具列表。
- `/community/model`：模型列表。
- `/community/provider`：模型服务商列表。
- `/community/skill`：Skill 列表。

从 React Router 的配置看，这个目录被挂在 `src/routes/(main)/community/_layout` 下面，并作为 `community` 路由的列表分支。也就是说，上层 `community/_layout` 提供社区整体外壳和侧边导航；本目录的 `_layout` 提供列表页专用的顶部搜索、排序、用户入口、宽屏内容容器和页脚；具体分类目录再负责拉取数据、渲染列表和分页。

它的核心职责可以概括为：把 URL 查询参数转换为市场数据查询参数，再用 `useDiscoverStore` 的各类 SWR hook 拉取列表数据，最后交给对应的 List 组件展示。

## 关键组成

### 公共列表布局：`_layout`

`_layout/index.tsx` 是本目录的公共壳层。它导入：

- `Header`：列表页顶部栏。
- `Footer`：列表页底部区域。
- `WideScreenContainer`：控制内容最大宽度。
- `Outlet`：承载子路由页面。
- `MAX_WIDTH`：来自 `../../features/const`，用于宽屏容器宽度控制。
- `styles`：来自 `_layout/style.ts`。

渲染结构大致是：

```tsx
<Header />
<Flexbox className={styles.mainContainer}>
  <WideScreenContainer>
    <Flexbox>
      <Outlet />
    </Flexbox>
    <div className={styles.spacer} />
    <Footer />
  </WideScreenContainer>
</Flexbox>
```

这里的 `Outlet` 是关键：`/community`、`/community/agent`、`/community/model` 等页面最终都在这个公共布局内部渲染。

`_layout/Header.tsx` 是列表页顶部栏。它使用 `useLocation()` 判断当前是否是首页：

```ts
const isHome = location.pathname === '/';
```

根据当前片段推断，这里的判断在实际 `/community` 路径下可能依赖上层路由或路由库封装行为；如果按浏览器完整路径理解，`/community` 并不等于 `/`。不过代码意图很明确：首页不显示排序和用户头像，分类列表页显示 `SortButton` 与 `UserAvatar`。

Header 的左侧是：

- `StoreSearchBar`：来自 `src/routes/(main)/community/features/Search`，负责搜索。

右侧在非首页时显示：

- `SortButton`：本目录公共排序按钮。
- `UserAvatar`：社区用户入口。

`_layout/Footer.tsx` 根据登录状态显示不同页脚：

- 已登录：显示 `DefaultFooter`。
- 未登录：显示带背景图的引导页脚、标题、描述和登录按钮。

它通过 `useMarketAuth()` 获取：

- `isAuthenticated`
- `signIn`

登录按钮点击后调用 `signIn()`，并用本地 `loading` 状态控制按钮加载态。

`_layout/style.ts` 只提供几个静态样式：

- `mainContainer`：设置 `overflow-y: auto`，是列表页主要滚动容器。
- `contentContainer`：保证内容区域 `min-height: 100%`。
- `spacer`：用 `flex: 1` 把页脚推到底部。

### 首页：`(home)`

`(home)/index.tsx` 是 `/community` 首页。它导入：

- `useDiscoverStore`
- `AssistantSorts`
- `McpSorts`
- `Title`
- `AssistantList`
- `McpList`
- `CreatorRewardBanner`
- `Loading`

首页会从 store 里取两个 hook：

```ts
const useAssistantList = useDiscoverStore((s) => s.useAssistantList);
const useMcpList = useDiscoverStore((s) => s.useFetchMcpList);
```

然后分别拉取：

- 推荐助手：`page: 1, pageSize: 12, sort: AssistantSorts.Recommended`
- 推荐 MCP：`page: 1, pageSize: 12, sort: McpSorts.Recommended`

两个请求任意一个还在 loading，或数据不存在，就返回 `(home)/loading.tsx`。加载完成后显示：

1. `CreatorRewardBanner`
2. “精选助手”标题和 “more” 链接到 `/community/agent`
3. `AssistantList`
4. “精选工具”标题和 “more” 链接到 `/community/mcp`
5. `McpList`

`CreatorRewardBanner.tsx` 是首页的创作者奖励横幅，使用 `useIsDark()` 区分深浅色背景，使用 `discover` 命名空间里的 i18n 文案，并跳转到外部链接：

```tsx
[URL已移除]
```

### 公共分页：`features/Pagination.tsx`

`Pagination` 封装了 antd 的 `Pagination`。它接收：

- `currentPage`
- `pageSize`
- `total`
- `tab`

点击页码后，它会：

1. 读取当前 `location.search`。
2. 设置新的 `page` 查询参数。
3. 跳转到 `/community/${tab}?${searchParams}`。
4. 滚动列表容器到顶部。

桌面端滚动容器来自：

```ts
SCROLL_PARENT_ID
```

移动端滚动容器硬编码为：

```ts
lobe-mobile-scroll-container
```

这说明该分页组件兼容移动端列表页复用，但当前目标目录主要是 `(main)` 桌面路由。

### 公共排序：`features/SortButton`

`SortButton/index.tsx` 根据当前 pathname 推导 active tab：

```ts
const activeTab = pathname.split('community/')[1] as DiscoverTab;
```

然后按不同 `DiscoverTab` 生成不同排序项：

- `DiscoverTab.Assistants`：`Recommended`、`UpdatedAt`、`MostUsage`、`HaveSkills`
- `DiscoverTab.Plugins`：`CreatedAt`、`Title`、`Identifier`
- `DiscoverTab.Models`：`ReleasedAt`、`Identifier`、`ContextWindowTokens`、`InputPrice`、`OutputPrice`、`ProviderCount`
- `DiscoverTab.Providers`：`Default`、`Identifier`、`ModelCount`
- `DiscoverTab.Mcp`：`Recommended`、`IsFeatured`、`IsValidated`、`InstallCount`、`RatingCount`、`UpdatedAt`、`CreatedAt`
- `DiscoverTab.Skills`：`InstallCount`、`UpdatedAt`、`CreatedAt`、`Stars`、`Name`

当前选中的排序来自 URL query 的 `sort`。如果 URL 没有 `sort`，默认取该 tab 的第一个排序项。选择排序后调用：

```ts
router.push(pathname, { query: { sort: config } });
```

注意它只更新 `sort`，不会显式清空 `page`。如果用户在第 N 页切换排序，是否仍停留第 N 页取决于 `useQueryRoute` 的 query 合并策略和后端返回结果。

### 分类列表页：`agent`、`mcp`、`model`、`provider`、`skill`

这几个目录的 `index.tsx` 模式高度一致：

1. `useQuery()` 读取 URL 参数。
2. 从 `useDiscoverStore` 取对应列表 hook。
3. 传入 `q`、`page`、`category`、`sort`、`order` 等参数。
4. loading 或无数据时返回 `loading.tsx`。
5. 解构 `items/currentPage/pageSize/totalCount`。
6. 渲染 `List` 和公共 `Pagination`。

例如 `agent/index.tsx`：

```ts
const { q, page, category, sort, order, source } = useQuery() as AssistantQueryParams;
const useAssistantList = useDiscoverStore((s) => s.useAssistantList);

const { data, isLoading } = useAssistantList({
  category,
  includeAgentGroup: true,
  order,
  page,
  pageSize: 21,
  q,
  sort: sort ?? AssistantSorts.Recommended,
  source,
});
```

它有几个特征：

- 默认 `pageSize` 是 21。
- `agent` 会传 `includeAgentGroup: true`，表示助手列表里也包含 group agent。
- `agent` 默认排序是 `AssistantSorts.Recommended`。
- `mcp` 默认排序是 `McpSorts.Recommended`。
- `skill` 默认排序是 `SkillSorts.InstallCount`。
- `model` 和 `provider` 没有在页面层设置默认排序，直接把 `sort` 传下去。

`provider` 没有自己的分类 `_layout`，直接是单页列表；`agent`、`mcp`、`model`、`skill` 有各自的 `_layout` 和 `features/Category`，用于左侧分类筛选。

### `agent` 子目录代表逻辑

`agent/_layout/index.tsx` 在列表主体左侧加入分类栏：

```tsx
<CategoryContainer>
  <Category />
</CategoryContainer>
<Flexbox flex={1}>
  <Outlet />
</Flexbox>
```

`agent/features/Category/index.tsx` 会：

- 从 query 读取 `category`、`q`、`source`。
- 调用 `useDiscoverStore((s) => s.useAssistantCategories)` 获取分类计数。
- 用 `useCategory()` 生成本地分类配置和图标。
- 点击分类后跳转到 `/community/agent`，并写入新的 `category` 参数。
- 如果选中 `Discover` 分类，会把 `category` 置空，并把 `sort` 设为 `AssistantSorts.Recommended`。
- 跳转后滚动到 `SCROLL_PARENT_ID` 顶部。

`agent/features/List/index.tsx` 接收 `DiscoverAssistantItem[]`，为空时显示 `AssistantEmpty`，否则用 `Grid` 渲染 `Item`。

`agent/features/List/Item.tsx` 是列表卡片。它负责：

- 构造详情链接：普通 agent 到 `/community/agent/:identifier`，group agent 到 `/community/group_agent/:identifier`。
- 保留 `source` query。
- 点击卡片时调用 `discoverService.reportAgentEvent({ event: 'click', identifier, source: location.pathname })` 上报点击事件。
- 点击作者时跳转 `/community/user/:userName`。
- 展示头像、标题、作者、描述、token 使用量、fork 数、插件数、知识库数和发布时间等信息。

这里有一个细节：`reportAgentEvent(...).catch(() => {})` 会吞掉上报错误。它适合非关键埋点，但阅读时不要误以为点击导航依赖上报成功；导航和上报是弱耦合的。

`agent/features/MarketSourceSwitch.tsx` 提供 `new/legacy` 市场源切换，但在当前读取到的 `agent/index.tsx` 和 `_layout` 片段里没有发现它被直接使用。根据当前片段推断，它可能是预留组件、被移动端或其他历史代码使用，或暂时未挂载。

## 上下游关系

上游路由关系：

- `src/spa/router/desktopRouter.config.tsx`
- `src/spa/router/desktopRouter.config.desktop.tsx`

这两个配置都注册了相同的 community 列表路由树。懒加载版本和 desktop 直接 import 版本都包含：

```txt
community
  ├─ list layout: src/routes/(main)/community/(list)/_layout
  │  ├─ index: (home)
  │  ├─ agent
  │  │  └─ agent/_layout + agent/index
  │  ├─ model
  │  │  └─ model/_layout + model/index
  │  ├─ provider
  │  ├─ skill
  │  │  └─ skill/_layout + skill/index
  │  └─ mcp
  │     └─ mcp/_layout + mcp/index
  └─ detail layout: src/routes/(main)/community/(detail)/_layout
     ├─ agent/:slug
     ├─ group_agent/:slug
     ├─ model/:slug
     ├─ provider/:slug
     ├─ skill/:slug
     ├─ mcp/:slug
     └─ user/:slug
```

再上一层是：

```ts
src/routes/(main)/community/_layout/index.tsx
```

它渲染社区 `Sidebar` 和一个主内容 `Outlet`。因此本目录不是整个社区页面的最高层，只是主内容里的列表分支。

同级详情页关系：

- 列表项点击后会进入 `src/routes/(main)/community/(detail)` 下的详情页。
- 例如 agent 列表项链接到 `/community/agent/:identifier`。
- provider 列表项链接到 `/community/provider/:identifier`。
- model 列表项链接到 `/community/model/:identifier`。
- skill 列表项链接到 `/community/skill/:identifier`。
- mcp 列表项链接到 `/community/mcp/:identifier`。

下游数据关系：

列表页不直接请求 HTTP API，而是通过 `useDiscoverStore`：

- `useAssistantList`
- `useFetchMcpList`
- `useModelList`
- `useProviderList`
- `useFetchSkillList`
- `useAssistantCategories`
- `useMcpCategories`
- `useSkillCategories`
- 等

这些 action slice 内部再调用：

```ts
discoverService
```

例如 `useAssistantList` 会调用：

```ts
discoverService.getAssistantList({
  ...params,
  page: params.page ? Number(params.page) : 1,
  pageSize: params.pageSize ? Number(params.pageSize) : 21,
});
```

SWR key 中会包含当前语言：

```ts
globalHelpers.getCurrentLanguage()
```

因此语言变化会影响缓存 key 和数据请求。

UI 组件依赖关系：

- 基础布局和控件主要来自 `@lobehub/ui`、`antd`、`antd-style`。
- 图标主要来自 `lucide-react` 和 `@lobehub/ui/icons`。
- 文案来自 `react-i18next` 的 `discover` namespace。
- URL query 读取主要使用 `useQuery()` 或 `useQuery()` from `@/libs/router/navigation`。
- URL 更新主要使用 `useQueryRoute()`、`useNavigate()` 和 `Link`。

## 运行/调用流程

以访问 `/community/agent?q=code&page=2&sort=recommended` 为例：

1. React Router 命中 `community` 路由。
2. 先渲染 `src/routes/(main)/community/_layout/index.tsx`：
   - 显示社区侧边栏。
   - 主区域留出 `Outlet`。
3. 进入列表分支，渲染 `src/routes/(main)/community/(list)/_layout/index.tsx`：
   - 显示列表页 Header。
   - Header 左侧显示搜索框。
   - Header 右侧显示排序按钮和用户头像。
   - 内容区域通过 `Outlet` 渲染具体分类页。
   - 底部显示 Footer。
4. 命中 `agent` 子路由，先渲染 `agent/_layout/index.tsx`：
   - 左侧显示分类菜单 `Category`。
   - 右侧通过 `Outlet` 渲染 `agent/index.tsx`。
5. `agent/index.tsx` 调用 `useQuery()` 读取：
   - `q`
   - `page`
   - `category`
   - `sort`
   - `order`
   - `source`
6. 页面从 `useDiscoverStore` 取 `useAssistantList`。
7. `useAssistantList` 内部构造 SWR key，并调用 `discoverService.getAssistantList`。
8. 请求未完成时渲染 `agent/loading.tsx`，它实际 re-export 公共 `ListLoading`。
9. 请求完成后得到：
   - `items`
   - `currentPage`
   - `pageSize`
   - `totalCount`
10. 页面渲染：
    - `List data={items}`
    - `Pagination currentPage={currentPage} pageSize={pageSize} total={totalCount}`
11. 用户点击分页时：
    - `Pagination` 修改 URL 的 `page`。
    - 跳转到 `/community/agent?page=新页码...`。
    - 滚动容器回到顶部。
12. 用户点击排序时：
    - `SortButton` 修改 URL 的 `sort`。
    - URL 变化触发页面重新读取 query。
    - SWR key 变化，重新拉取列表。
13. 用户点击列表卡片时：
    - agent item 异步上报 click 事件。
    - 页面跳转到详情路由 `/community/agent/:identifier` 或 `/community/group_agent/:identifier`。

首页 `/community` 的流程略有不同：它不走分类页，不展示完整分页，而是固定拉取第一页推荐数据，并展示两个精选区块。

搜索流程：

1. Header 里的 `StoreSearchBar` 读取当前 pathname。
2. 根据 pathname 推导 active tab：

```ts
const activeTab = pathname.split('/')[2] || 'agent';
```

3. 输入搜索词后跳转：

```ts
router.push(urlJoin('/community', activeTab), {
  query: value ? { q: value } : {},
  replace: true,
});
```

所以在 `/community/mcp` 搜索会留在 `/community/mcp`，并把 `q` 写到 URL；在 `/community` 首页搜索时，根据 fallback，可能会跳到 `/community/agent`。

## 小白阅读顺序

1. 先读 `src/spa/router/desktopRouter.config.tsx` 里 `community` 这一段  
   目的是搞清楚 `/community`、`/community/agent`、`/community/model` 等 URL 到底映射到哪些文件。重点看列表分支和详情分支的分界。

2. 再读 `src/routes/(main)/community/_layout/index.tsx`  
   这是 community 总外壳。理解它之后，就知道本目录只负责右侧主内容，不负责侧边栏整体。

3. 再读 `src/routes/(main)/community/(list)/_layout/index.tsx`  
   这里是列表页公共布局。重点看 `Header`、`Outlet`、`Footer` 的组合。

4. 继续读 `_layout/Header.tsx` 和 `features/SortButton/index.tsx`  
   这两个文件能解释搜索、排序和用户入口为什么出现在所有分类列表页上。

5. 读 `(home)/index.tsx`  
   这是最简单的数据页：固定拉推荐助手和推荐 MCP，没有复杂分类和分页，适合理解 `useDiscoverStore` 的基本用法。

6. 读 `agent/index.tsx`  
   这是最典型的分类列表页：读 URL query、请求列表、处理 loading、渲染 List、渲染 Pagination。

7. 读 `agent/_layout/index.tsx` 和 `agent/features/Category/index.tsx`  
   这里能理解分类筛选如何通过 query 参数驱动。

8. 读 `agent/features/List/index.tsx` 和 `agent/features/List/Item.tsx`  
   这里能看到列表数据如何变成卡片，以及列表页如何跳转详情页。

9. 最后横向对比 `mcp/index.tsx`、`model/index.tsx`、`provider/index.tsx`、`skill/index.tsx`  
   你会发现它们共享同一种页面模型，只是 store hook、类型、默认排序和 List 组件不同。

10. 如果要继续追数据来源，再读 `src/store/discover/slices/*/action.ts`  
   重点看这些 hook 如何把 page/pageSize 转成 number，如何构造 SWR key，如何调用 `discoverService`。

## 常见误区

1. 不要把 `(list)` 当成真实 URL 片段  
   `(list)` 是路由分组目录名，不会出现在浏览器 URL 中。真实路径是 `/community`、`/community/agent`、`/community/mcp` 等。

2. 不要以为 `src/routes/(main)/community/(list)` 是社区页面的最外层  
   最外层是 `src/routes/(main)/community/_layout`。本目录只是 community 下的列表分支；详情分支在 `src/routes/(main)/community/(detail)`。

3. 不要忽略两个 desktop router 配置  
   仓库同时有 `desktopRouter.config.tsx` 和 `desktopRouter.config.desktop.tsx`。它们都注册了 community 列表路由。改路由时只改一个，可能导致某个构建路径下页面空白。

4. 不要把 `useDiscoverStore` 理解成普通全局状态读取  
   这里的 store action 很多是以 hook 形式封装 SWR 请求，例如 `useAssistantList`、`useFetchMcpList`。页面组件调用它们会触发数据请求和缓存，而不是只读取本地状态。

5. 不要以为排序、分页、分类是组件内部状态  
   这些状态主要放在 URL query 中：`q`、`page`、`category`、`sort`、`order`、`source`。因此刷新页面、复制链接、浏览器前进后退都能保留筛选状态。

6. 不要以为所有分类页都有左侧分类栏  
   `agent`、`mcp`、`model`、`skill` 有各自的 `_layout` 和分类组件；`provider` 当前是直接列表页，没有同级 `_layout` 分类栏。

7. 不要把首页和列表页的数据规模混淆  
   首页 `(home)` 拉的是精选数据，`pageSize` 是 12；分类列表页通常 `pageSize` 是 21，并带分页控件。

8. 不要认为点击列表项必须等待埋点成功  
   以 agent item 为例，点击时会调用 `discoverService.reportAgentEvent(...).catch(() => {})`，但错误被吞掉，导航不会依赖这个请求成功。

9. 注意 `SortButton` 的 active tab 来自 pathname 字符串切分  
   它通过 `pathname.split('community/')[1]` 推导 tab。如果未来 URL 层级变复杂，或者 pathname 包含更深层详情路径，这种推导方式可能需要重新审视。

10. 注意当前目录和仓库“route thin、feature heavy”的理想规范不完全一致  
   AGENTS.md 说明 route 文件应尽量薄，把业务 UI 放到 `src/features`。但当前目录里仍有不少 `features` 放在 route 目录内部，例如 `agent/features/List/Item.tsx`。阅读时应以现有代码为准；如果未来重构，可能会把这些业务组件迁移到 `src/features/Community` 之类的位置。
