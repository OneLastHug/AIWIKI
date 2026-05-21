# 目录：src/routes/(main)/community

## 它负责什么

`src/routes/(main)/community` 是 LobeHub 桌面端“社区 / Discover”页面树的主体实现，负责展示可发现资源的列表页和详情页。这里的资源包括：

- `agent`：助手市场列表与助手详情
- `group_agent`：群组助手详情
- `mcp`：MCP 工具列表与详情
- `model`：模型列表与详情
- `provider`：模型服务商列表与详情
- `skill`：技能列表与详情
- `user`：社区用户详情
- 根路径 `/community`：社区首页，展示推荐助手和推荐 MCP 工具

它不是一个纯粹的“路由壳目录”。虽然位于 `src/routes/` 下，但当前实现中也放了不少页面级 UI、列表组件、详情组件和局部 feature，例如 `components/`、`features/`、`(list)/*/features/`、`(detail)/*/features/`。根据仓库约定，新代码更倾向于把复杂业务 UI 下沉到 `src/features/`，但这个目录是较完整的社区页面实现，属于历史上较“厚”的 route subtree。

## 关键组成

顶层结构可以先分成三层看：

第一层是总布局：

- `src/routes/(main)/community/_layout/index.tsx`

它渲染社区左侧导航 `Sidebar`，再用 `Outlet` 承接子路由内容。也就是说，只要进入 `/community` 这棵路由，外层都会先经过这个布局。

第二层是列表页区域：

- `src/routes/(main)/community/(list)/_layout/index.tsx`
- `src/routes/(main)/community/(list)/(home)/index.tsx`
- `src/routes/(main)/community/(list)/agent/index.tsx`
- `src/routes/(main)/community/(list)/mcp/index.tsx`
- `src/routes/(main)/community/(list)/model/index.tsx`
- `src/routes/(main)/community/(list)/provider/index.tsx`
- `src/routes/(main)/community/(list)/skill/index.tsx`

`(list)/_layout/index.tsx` 提供列表页通用的顶部 `Header`、内容容器 `WideScreenContainer` 和 `Footer`。各个列表页再负责读取 URL query、调用 `useDiscoverStore` 中的 SWR hook、渲染列表和分页。

例如 `agent/index.tsx` 会：

- 用 `useQuery()` 读取 `q`、`page`、`category`、`sort`、`order`、`source`
- 从 `useDiscoverStore` 取 `useAssistantList`
- 请求助手列表，默认 `sort` 为 `AssistantSorts.Recommended`
- 渲染 `agent/features/List`
- 使用公共 `Pagination`

`provider/index.tsx` 类似，只是调用 `useProviderList`，并使用 `DiscoverTab.Providers` 作为分页 tab。

第三层是详情页区域：

- `src/routes/(main)/community/(detail)/_layout/index.tsx`
- `src/routes/(main)/community/(detail)/agent/index.tsx`
- `src/routes/(main)/community/(detail)/group_agent/index.tsx`
- `src/routes/(main)/community/(detail)/mcp/index.tsx`
- `src/routes/(main)/community/(detail)/model/index.tsx`
- `src/routes/(main)/community/(detail)/provider/index.tsx`
- `src/routes/(main)/community/(detail)/skill/index.tsx`
- `src/routes/(main)/community/(detail)/user/index.tsx`

`(detail)/_layout/index.tsx` 是详情页通用壳，设置 `SCROLL_PARENT_ID = 'discover-scroll'`，包裹 `Header`、`WideScreenContainer`、`Outlet` 和 `Footer`。详情页通常有一套 `DetailProvider`，把请求到的详情数据放进 React context，下面的 `Header`、`Details`、`Sidebar` 等组件通过 context 消费。

公共组件主要在：

- `components/`：偏通用的社区 UI，如 `Title`、`Statistic`、`CategoryMenu`、`SearchResultCount`、`GitHubAvatar`、`VirtuosoGridList`
- `features/`：社区通用 feature，如 `Search`、`LikeButton`、`CreateButton`、各种 Empty 状态、`useNav`
- `(list)/features/`：列表页公共能力，如 `Pagination`、`SortButton`
- `(detail)/features/`：详情页公共能力，如 `DetailLayout`、`Breadcrumb`、`Back`、`Toc`、`ShareButton`、`MarkdownRender`

## 上下游关系

上游路由注册在 `src/spa/router/desktopRouter.config.tsx` 和 `src/spa/router/desktopRouter.config.desktop.tsx` 中。`/community` 被注册为一棵嵌套路由：

- 外层：`community/_layout`
- 列表分支：`(list)/_layout`
- 详情分支：`(detail)/_layout`

桌面端路径大致对应如下：

- `/community` -> `(list)/(home)`
- `/community/agent` -> `(list)/agent`
- `/community/model` -> `(list)/model`
- `/community/provider` -> `(list)/provider`
- `/community/skill` -> `(list)/skill`
- `/community/mcp` -> `(list)/mcp`
- `/community/agent/:slug` -> `(detail)/agent`
- `/community/group_agent/:slug` -> `(detail)/group_agent`
- `/community/model/:slug` -> `(detail)/model`
- `/community/provider/:slug` -> `(detail)/provider`
- `/community/skill/:slug` -> `(detail)/skill`
- `/community/mcp/:slug` -> `(detail)/mcp`
- `/community/user/:slug` -> `(detail)/user`

下游数据主要来自 `src/store/discover`。页面本身不直接拼后端请求，而是通过 discover store 暴露的 SWR hook 获取数据，例如：

- `useAssistantList`
- `useAssistantDetail`
- `useFetchMcpList`
- `useModelDetail`
- `useProviderList`

类型主要来自 `@/types/discover`，如 `DiscoverTab`、`AssistantSorts`、`McpSorts`、`AssistantQueryParams`、`ProviderQueryParams`。

UI 依赖较多：

- `@lobehub/ui`：`Flexbox` 等基础布局组件
- `lucide-react`、`@lobehub/ui/icons`、`@lobehub/icons`：导航和资源图标
- `react-router-dom`：`Outlet`、`Link`、`useNavigate`、`useParams`
- `react-i18next`：读取 `discover` namespace 下的文案
- `antd-style`：响应式能力，如 `useResponsive`

此外，移动端路由也复用了部分这里的页面组件。根据 `mobileRouter.config.tsx` 片段，移动端详情页会 import 这里的 detail 页面并取出移动版本导出，例如 `MobileDiscoverAssistantDetailPage`、`MobileModelPage` 等，再搭配移动端自己的 layout。

## 运行/调用流程

以访问 `/community/agent?page=1&q=xxx` 为例，流程大致是：

1. React Router 命中 `community` 路由。
2. 加载 `src/routes/(main)/community/_layout/index.tsx`。
3. 外层布局渲染社区侧边栏 `Sidebar`，内容区域交给 `Outlet`。
4. 命中列表分支，加载 `(list)/_layout/index.tsx`。
5. 列表布局渲染通用 `Header`、宽屏容器、页脚，并继续渲染子 `Outlet`。
6. 加载 `(list)/agent/index.tsx`。
7. 页面用 `useQuery()` 解析 query 参数。
8. 页面从 `useDiscoverStore` 取 `useAssistantList`。
9. SWR hook 请求助手列表数据。
10. 加载中显示 `loading.tsx`。
11. 数据返回后渲染 `agent/features/List` 和公共 `Pagination`。

以访问 `/community/agent/some-slug?version=1.0&source=xxx` 为例：

1. 命中 `community/_layout`。
2. 进入详情分支 `(detail)/_layout`。
3. 详情布局设置滚动容器 `id={SCROLL_PARENT_ID}`，用于目录锚点、分类区域等依赖滚动父级的交互。
4. 加载 `(detail)/agent/index.tsx`。
5. 页面用 `useParams<{ slug: string }>()` 获取动态参数，并用 `decodeURIComponent` 得到 `identifier`。
6. 页面用 `useQuery()` 读取 `version` 和 `source`。
7. 调用 `useDiscoverStore((s) => s.useAssistantDetail)` 获取详情。
8. 加载中显示 `Loading`，没有数据时显示 `NotFound`。
9. 如果状态是 `unpublished`、`archived`、`deprecated`，显示 `StatusPage`。
10. 正常数据会包进 `TocProvider` 和 `DetailProvider`。
11. 子组件 `Header`、`Details`、`Sidebar` 等通过 context 和局部 hooks 渲染完整详情页。

## 小白阅读顺序

建议按“路由壳 -> 列表页 -> 详情页 -> 公共组件 -> 数据层”的顺序读。

1. 先读 `src/spa/router/desktopRouter.config.tsx` 中 `community` 相关片段，理解 URL 如何映射到目录。
2. 读 `src/routes/(main)/community/_layout/index.tsx`，确认社区总布局只有侧边栏和 `Outlet`。
3. 读 `src/routes/(main)/community/_layout/Sidebar/Header/Nav.tsx`，理解左侧导航有哪些 tab，以及 URL 是怎样跳转的。
4. 读 `src/routes/(main)/community/(list)/_layout/index.tsx`，理解列表页统一外壳。
5. 读 `src/routes/(main)/community/(list)/(home)/index.tsx`，这是最简单的首页示例，会展示推荐助手和推荐 MCP。
6. 再读 `src/routes/(main)/community/(list)/agent/index.tsx` 或 `provider/index.tsx`，理解列表页如何通过 query + store hook 获取数据。
7. 读 `src/routes/(main)/community/(detail)/_layout/index.tsx`，理解详情页通用容器和滚动容器。
8. 读 `src/routes/(main)/community/(detail)/agent/index.tsx`，它包含 slug 解析、详情请求、NotFound、状态页、context provider、目录 provider，是详情页模式最完整的样本。
9. 读 `src/routes/(main)/community/(detail)/features/DetailLayout.tsx`，理解详情页桌面端和移动端布局差异。
10. 最后再追 `src/store/discover`，看 `useAssistantList`、`useAssistantDetail` 等 hook 背后的数据请求和缓存逻辑。

## 常见误区

第一，`community` 和 `discover` 是同一业务域的两个命名视角。URL 和目录叫 `community`，但很多类型、文案 namespace、store slice 使用的是 `discover`，例如 `DiscoverTab`、`useDiscoverStore`、`useTranslation('discover')`。不要误以为这是两个无关模块。

第二，`(list)`、`(detail)` 不是 URL 片段。它们是目录分组，用来组织列表页和详情页。真实 URL 是 `/community/agent`、`/community/agent/:slug` 这种形式。

第三，`plugin` 和 `mcp` 容易混淆。`useNav` 里有一段兼容逻辑：如果路径包含 `/${DiscoverTab.Plugins}`，会激活 `DiscoverTab.Mcp`。这说明历史上可能存在 plugin 命名，当前主要入口是 MCP。

第四，不要只看 `desktopRouter.config.tsx`。这个项目桌面路由还有 `desktopRouter.config.desktop.tsx`，两边需要保持同构。仓库说明也明确提到更新桌面 route tree 时必须同步两个配置，否则可能出现某个构建路径下空白页。

第五，详情页不是每个子组件自己请求数据。多数详情页先在页面入口请求一次详情，再通过局部 `DetailProvider` 放入 context，让 `Header`、`Details`、`Sidebar` 等组件消费。读代码时要先找对应资源下的 `features/DetailProvider.tsx`。

第六，列表页分页不是路由自动处理的。页面会从 `useQuery()` 读取 `page`、`sort`、`order`、`category`、`q` 等参数，然后传给 store hook，再把返回的 `currentPage`、`pageSize`、`totalCount` 交给 `Pagination`。

第七，`src/routes/(main)/community` 当前比较“厚”，里面有大量业务 UI。按照仓库最新约定，新业务更推荐放到 `src/features/<Domain>/`，route 文件保持薄。但理解现有代码时，应先尊重当前结构，不要简单套用“routes 只能放壳”的理想模型。
