# 目录：src/routes/(main)/community/(detail)

## 它负责什么

`src/routes/(main)/community/(detail)` 是 Community 模块的“详情页路由组”，负责承载社区市场中各种资源的详情页面，包括：

- `/community/agent/:slug`：助手详情
- `/community/group_agent/:slug`：群组助手详情
- `/community/model/:slug`：模型详情
- `/community/provider/:slug`：模型供应商详情
- `/community/skill/:slug`：技能详情
- `/community/mcp/:slug`：MCP Server 详情
- `/community/user/:slug`：社区用户主页

它位于 `src/routes` 下，因此本质上是 SPA route segment。按项目当前的 `spa-routes` 约定，理想状态下 route 文件应该只做页面入口和布局组合，具体业务 UI 下沉到 `src/features`。但这个目录是一个还保留较多历史实现的 detail 路由组：除了页面入口，也包含了大量 `features/` 子目录和业务组件。因此阅读时要把它理解成“路由入口 + 详情页业务实现混合区”。

这个目录的核心职责可以概括为三件事：

1. 从 URL 中读取 `slug`，解析出资源标识符。
2. 通过 `useDiscoverStore` 或专用 feature hook 拉取对应资源详情。
3. 根据加载状态、空状态、资源状态，渲染详情页 Header、正文、侧边栏、TOC、分享、安装/使用操作等内容。

## 关键组成

### `_layout/`

`_layout/index.tsx` 导出 `DesktopDiscoverDetailLayout`，是桌面端详情页的统一外壳。

它做了几件事：

- 渲染顶部 `Header`。
- 用 `Flexbox` 创建可滚动主容器，容器 id 来自 `SCROLL_PARENT_ID`，供目录锚点 `Toc` 定位滚动容器使用。
- 用 `WideScreenContainer` 限制详情页最大宽度，`MAX_WIDTH` 来自 `community/features/const`。
- 通过 `<Outlet />` 承接下级详情页，如 agent、model、provider。
- 在底部放置 `Footer`。

`_layout/Header.tsx` 是详情页顶栏，左侧是返回按钮和 `StoreSearchBar`，右侧是 `UserAvatar`。返回逻辑根据当前路径第二段判断资源类型：

- `group_agent` 返回 `/community/agent`。
- `agent`、`model`、`provider`、`mcp`、`skill` 返回各自列表页。
- `user` 或未知类型返回 `/community`。

这说明该 Header 假定详情页路径形态是 `/community/{detailType}/{slug}`。

### 顶层页面入口

各资源目录下的 `index.tsx` 是真正的 route page 入口。

`agent/index.tsx`：

- 使用 `useParams<{ slug: string }>()` 读取 slug，并 `decodeURIComponent`。
- 使用 `useQuery()` 读取 `version`、`source`。
- 从 `useDiscoverStore` 取 `useAssistantDetail` 拉取详情。
- 加载中渲染 `loading.tsx`。
- 无数据渲染 `components/NotFound`。
- 如果状态是 `unpublished`、`archived`、`deprecated`，渲染 `StatusPage`。
- 正常情况下包裹 `TocProvider` 和 agent 自己的 `DetailProvider`，再渲染 `Header`、`Details`。
- 额外导出 `MobileDiscoverAssistantDetailPage`，给移动端 router 使用。

`group_agent/index.tsx`：

- 读取 `slug` 和 `version`。
- 调用 `useDiscoverStore((s) => s.useGroupAgentDetail)`。
- 对 API 返回值做了一层 `transformedData` 转换，把 `group`、`currentVersion`、`author`、`memberAgents` 等字段摊平成详情组件期望的数据结构。
- 同样处理加载、空数据和不可发布状态。
- 渲染自己的 `DetailProvider`、`Header`、`Details`。

这是目录中比较特殊的入口：它不是直接把接口数据传给下游组件，而是做了兼容转换。根据当前片段推断，这是因为群组助手接口结构和普通助手详情组件所需结构不一致。

`mcp/index.tsx`：

- 读取 `slug` 和 `version`。
- 调用 `useDiscoverStore((s) => s.useFetchMcpDetail)`。
- 调用 `useFetchInstalledPlugins()`，用于同步本地已安装插件状态。
- 使用的是 `@/features/MCPPluginDetail/DetailProvider` 和 `@/features/MCPPluginDetail/Header`，说明 MCP 详情已有一部分实现被抽到了全局 feature。
- 渲染本目录下的 `mcp/features/Details`。
- 导出 `MobileMcpPage`。

`model/index.tsx`：

- 读取并解码 `slug`。
- 调用 `useModelDetail({ identifier })`。
- 用 `model/features/DetailProvider` 注入详情上下文。
- 渲染 `Header` 和 `Details`。
- 导出 `MobileModelPage`。

`provider/index.tsx`：

- 读取并解码 `slug`。
- 调用 `useProviderDetail({ identifier, withReadme: true })`。
- `withReadme: true` 表明 provider 详情需要额外拉取 README 或说明文档。
- 用 provider 自己的 `DetailProvider` 包裹 `Header`、`Details`。
- 导出 `MobileProviderPage`。

`skill/index.tsx`：

- 读取 `slug` 和 `version`。
- 调用 `useFetchSkillDetail({ identifier, version })`。
- 包裹 `TocProvider` 和 skill 自己的 `DetailProvider`。
- 渲染 `Header`、`Details`。
- 导出 `MobileSkillPage`，但从已观察到的 mobile router 片段看，移动端 router 未必注册了 skill 详情入口；这里需要以 router 配置为准。

`user/index.tsx`：

- 读取并解码用户名。
- 调用 `useDiscoverStore((s) => s.useUserProfile)` 拉取用户主页数据。
- 通过 `useMarketAuth()` 获取登录态、当前用户、资料编辑弹窗和可认领资源检查。
- 通过 `useMarketUserProfile(currentUser?.sub)` 获取当前登录用户 profile，用来判断当前页面是否属于本人。
- 如果是本人访问自己的主页，会调用 `checkAndShowClaimableResources`，并在认领完成后 `mutate()` 刷新数据。
- `handleEditProfile` 支持编辑资料后刷新数据；如果 `userName` 变化，则 `navigate('/community/user/{newUserName}', { replace: true })`。
- 通过 `useMemo` 组装 `UserDetailProvider` 所需上下文，包括 agents、agentGroups、forkedAgents、favoriteAgents、skills、plugins、totalInstalls、isOwner 等。
- 渲染 `UserHeader` 和 `UserContent`。

用户页和其他资源详情页差异较大：它不使用通用 `TocProvider`，更像一个用户资产聚合页。

### 公共组件

`components/NotFound.tsx` 是本详情组内部的轻量空状态组件，使用 `useTranslation('error')` 读取 `notFound.title`，居中显示标题。

`not-found.tsx` 直接 re-export `@/components/404`，用于路由级 404。

`error.tsx` 直接 re-export `@/components/Error`，用于路由级错误边界。

### 公共 features

`features/DetailLayout.tsx` 是详情页通用布局组件：

- 移动端或窄屏：顺序渲染 `header`、`actions`、`statistics`、`children`、`sidebar`、`Footer`。
- 桌面端：左侧主内容，右侧 `SidebarContainer`，侧边栏里放 `actions`、`statistics` 和 `sidebar`。

很多具体详情页的 `Details` / `Sidebar` 会复用这个布局思路。

`features/Toc` 是 Markdown 文档目录系统：

- `useToc.tsx` 创建 `TocContext`，保存 `toc`、`isLoading`、`setToc`、`setFinished`。
- `Heading.tsx` 把 Markdown 的 `h1` 至 `h5` 替换成自定义组件。`h2`、`h3` 会把标题文本转成 `kebabCase` id，并写入 TOC。
- `index.tsx` 使用 antd `Anchor` 渲染目录，并通过 `getContainer` 指向 `SCROLL_PARENT_ID` 对应的滚动容器。
- `createTOCTree` 会把平铺的 h2/h3 列表转换成层级目录，并用 `unionBy(items, 'href')` 去重。

`features/MakedownRender.tsx` 是 Markdown 渲染器，注意文件名是 `MakedownRender`，拼写少了一个 `r`。它使用 `@lobehub/ui` 的 `Markdown`，并做了安全/产品侧限制：

- 没有内容时显示 `Empty`。
- 外链 `a` 使用 `target="_blank"` 和 `rel="noreferrer"`。
- 非 http 链接不直接渲染为跳转链接。
- 图片只允许 http 图片，过滤 `glama.ai` 图片，不接受 Blob 类型。
- 标题使用 TOC 体系中的 `H1` 至 `H5`。

`features/ShareButton.tsx` 是分享弹窗：

- 调用 `useShare` 生成 X、Reddit、Telegram、WhatsApp、Mastodon、微博等分享链接。
- 用 `Modal` 展示资源卡片、社交分享按钮和复制链接输入框。
- `meta` 为空时显示 Skeleton。

`features/Breadcrumb.tsx` 根据 `DiscoverTab` 和 `identifier` 渲染面包屑。`User` 类型没有中间列表页，所以路径是 `Community / @identifier`；其他类型是 `Community / tab / identifier`，并提供 `CopyButton` 复制 identifier。

`features/Block.tsx`、`HighlightBlock.tsx`、`SidebarContainer.tsx`、`Back.tsx` 是通用展示积木：标题块、带背景高亮块、固定宽度侧栏容器和返回链接。

### 各资源自己的 features

每个详情类型下都有自己的 `features`：

- `agent/features`：`DetailProvider`、`Header`、`Details`、`Sidebar`、`StatusPage`、`AgentForkTag`。
- `group_agent/features`：结构接近 agent，但有 `GroupAgentForkTag` 和群组助手专用 Overview/SystemRole/Versions。
- `model/features`：模型详情 Header、详情内容、侧边栏、关联 provider/model。
- `provider/features`：供应商详情 Header、README/Guide、关联模型。
- `mcp/features`：MCP 详情内容、连接类型提示、服务器配置、Sidebar。
- `skill/features`：技能详情内容、安装配置、平台安装说明、资源文件树、版本。
- `user/features`：用户主页 Header、关注按钮、状态过滤、资源列表、收藏/ fork 列表、提交仓库弹窗等。

这说明本目录不仅是路由入口，还承载了 Community detail 的大部分页面实现。

## 上下游关系

### 上游：router 配置

桌面端 router 会把这些页面注册进 SPA 路由树。已观察到：

- `src/spa/router/desktopRouter.config.tsx` 动态导入：
  - `@/routes/(main)/community/(detail)/agent`
  - `group_agent`
  - `model`
  - `provider`
  - `skill`
  - `mcp`
  - `user`
  - 以及 `@/routes/(main)/community/(detail)/_layout`
- `src/spa/router/desktopRouter.config.desktop.tsx` 同步静态导入同一批页面和 layout。

这符合项目要求：桌面路由树必须在 `desktopRouter.config.tsx` 与 `desktopRouter.config.desktop.tsx` 中保持一致，否则可能出现某个构建入口空白页。

移动端 router 也导入了部分详情页的 mobile export，例如 agent、model、provider、mcp、user，并使用移动端 detail layout。根据当前片段，`group_agent` 和 `skill` 的移动端注册情况没有完整证据，需以 `mobileRouter.config.tsx` 实际路由树为准。

### 上游：列表页和其他入口

Community 列表页会链接到这些详情页：

- agent 列表项根据资源是否是 group agent，跳到 `/community/agent/{identifier}` 或 `/community/group_agent/{identifier}`。
- mcp 列表项跳到 `/community/mcp/{identifier}`。
- skill 列表项跳到 `/community/skill/{identifier}`。
- provider 列表项跳到 `/community/provider/{identifier}`。
- model 列表项跳到 `/community/model/{identifier}`。
- 用户头像、作者链接、用户资源卡片会跳到 `/community/user/{userName}` 或相关资源详情页。

详情页之间也会互相跳转。例如 provider 详情里的模型列表会跳到 model 详情，model 详情里的供应商列表会跳到 provider 详情，agent 能力里的插件项可能跳到 MCP 详情。

### 下游：状态和数据层

主要数据来源是 `@/store/discover`：

- `useAssistantDetail`
- `useGroupAgentDetail`
- `useFetchMcpDetail`
- `useModelDetail`
- `useProviderDetail`
- `useFetchSkillDetail`
- `useUserProfile`

这些看起来是封装在 Zustand store 中的 SWR 风格 hook。页面入口只负责调用 hook、判断 `isLoading` 和 `data`，真正的请求实现不在本目录。

用户页额外依赖：

- `@/layout/AuthProvider/MarketAuth`
- `useMarketAuth`
- `useMarketUserProfile`
- `useUserDetail`

MCP 详情额外依赖：

- `@/features/MCPPluginDetail/DetailProvider`
- `@/features/MCPPluginDetail/Header`
- `useFetchInstalledPlugins`

### 下游：UI 基础设施

本目录大量使用：

- `@lobehub/ui`：`Flexbox`、`Skeleton`、`Button`、`ActionIcon`、`Markdown`、`Modal` 等。
- `antd`：`Breadcrumb`、`Anchor`。
- `antd-style`：`createStaticStyles`、`cssVar`、`useResponsive`。
- `react-router-dom`：`Outlet`、`useParams`、`useNavigate`、`useLocation`、`Link`。
- `react-i18next`：多语言文本。
- `lucide-react`：图标。

## 运行/调用流程

以 `/community/agent/chatgpt-helper?version=1.0` 为例，整体流程大致是：

1. SPA router 匹配到 Community detail layout。
2. `_layout/index.tsx` 渲染详情页统一外壳，包括顶部 Header、滚动容器、宽屏容器和 `<Outlet />`。
3. router 继续匹配到 `agent/index.tsx`。
4. `agent/index.tsx` 通过 `useParams` 取出 `slug`，解码为 `identifier`。
5. 通过 `useQuery` 读取 `version`、`source`。
6. 调用 `useDiscoverStore((s) => s.useAssistantDetail)` 获取数据 hook，再执行 `useAssistantDetail({ identifier, source, version })`。
7. 如果加载中，显示 agent 专用 skeleton。
8. 如果无数据，显示 `NotFound`。
9. 如果资源状态是 `unpublished`、`archived`、`deprecated`，显示 `StatusPage`。
10. 正常数据进入 `TocProvider` 和 `DetailProvider`。
11. `Header` 渲染标题、作者、标签、操作区等；`Details` 渲染 Overview、SystemRole、Capabilities、Versions、Related 等内容。
12. 如果详情正文里使用 `MarkdownRender`，Markdown 标题会通过 `Heading` 写入 TOC。
13. 侧边栏中的 TOC 组件读取 `useToc()`，生成锚点目录，并绑定到 layout 的滚动容器。

其他资源类型流程类似，差异主要在数据 hook、DetailProvider 类型、Details 内容和 Sidebar 内容。

用户页流程有所不同：

1. `/community/user/:slug` 进入 `user/index.tsx`。
2. 读取 username 后拉取用户 profile。
3. 同时读取当前登录用户信息，判断是否是 owner。
4. 如果是 owner，会检查可认领资源。
5. 将用户、资源列表、收藏、fork、技能、插件、编辑资料回调等组装成 `UserDetailProvider` config。
6. 渲染 `UserHeader` 和 `UserContent`，由下层组件展示用户主页与资源列表。

## 小白阅读顺序

1. 先看 `_layout/index.tsx`  
   了解详情页统一页面壳、滚动容器和 `<Outlet />` 是怎么组织的。

2. 再看 `_layout/Header.tsx`  
   这里能快速理解详情页 URL 结构和返回逻辑。

3. 看一个最简单的详情入口，例如 `model/index.tsx` 或 `provider/index.tsx`  
   这两个入口结构清晰：取 slug、调 store hook、loading/not found、Provider 包裹、渲染 Header 和 Details。

4. 再看 `agent/index.tsx`  
   agent 多了 `version`、`source`、`TocProvider` 和状态页，能理解详情页的通用增强逻辑。

5. 然后看 `features/DetailLayout.tsx`  
   理解详情页在桌面端和移动端如何分配主内容与侧边栏。

6. 看 `features/MakedownRender.tsx` 和 `features/Toc/*`  
   这部分解释了 README、说明文档、系统提示词等 Markdown 内容如何生成目录。

7. 最后看具体业务目录  
   如果关心助手，读 `agent/features/Header.tsx`、`agent/features/Details/index.tsx`、`agent/features/Sidebar/index.tsx`。  
   如果关心 MCP，读 `mcp/index.tsx`、`mcp/features/Details/index.tsx`、`mcp/features/Sidebar/index.tsx`。  
   如果关心用户主页，读 `user/index.tsx`、`user/features/DetailProvider.tsx`、`user/features/UserContent.tsx`。

## 常见误区

1. 不要以为 `(detail)` 会出现在真实 URL 中  
   `(detail)` 是路由分组目录名，用于组织源码，不是 URL path。真实路径是 `/community/agent/:slug`、`/community/model/:slug` 等。

2. 不要把 `_layout/Header.tsx` 和各资源自己的 `features/Header.tsx` 混淆  
   `_layout/Header.tsx` 是全局详情页顶栏，负责返回、搜索、用户头像。  
   `agent/features/Header.tsx`、`model/features/Header.tsx` 等是资源详情头部，负责展示标题、头像、作者、操作按钮等业务信息。

3. 不要认为所有详情页都使用同一个 `DetailProvider`  
   每个资源类型基本都有自己的 `DetailProvider`，上下文数据结构不同。MCP 甚至复用了 `@/features/MCPPluginDetail/DetailProvider`。

4. 不要忽略 `TocProvider` 的作用  
   agent、group_agent、mcp、skill 等详情会使用 TOC。Markdown 标题不是静态扫描出来的，而是在渲染标题组件时写入 context。

5. 不要随意移动本目录下的 `features`  
   按新约定，业务实现更适合放到 `src/features`，但当前目录仍是历史混合结构。迁移时要同时考虑 import 路径、router 配置、移动端导出和上下文 Provider，不能只移动单个组件。

6. 不要只改一个 desktop router 配置  
   如果新增、删除或重命名这个目录下的桌面详情路由，必须同步 `desktopRouter.config.tsx` 和 `desktopRouter.config.desktop.tsx`。项目已有同步测试守护这个约束。

7. 不要假设 `slug` 永远无需解码  
   agent、model、provider、user 使用了 `decodeURIComponent(params.slug ?? '')`，而 mcp、skill 当前直接使用 `params.slug ?? ''`。如果资源 identifier 可能包含 URL 编码字符，不同详情页行为可能不同。

8. 不要把 `not-found.tsx` 和 `components/NotFound.tsx` 当成同一个东西  
   `not-found.tsx` 是路由级 404，导出全局 `@/components/404`。  
   `components/NotFound.tsx` 是详情入口内部在数据为空时显示的轻量提示。

9. 注意 `MakedownRender.tsx` 的拼写  
   文件名是 `MakedownRender.tsx`，不是常见的 `MarkdownRender.tsx`。查找文件时容易漏掉。

10. 不要以为用户详情页只是普通资源详情页  
   `user/index.tsx` 还处理登录用户判断、资料编辑、资源认领、个人资源聚合，复杂度和普通详情页不同。
