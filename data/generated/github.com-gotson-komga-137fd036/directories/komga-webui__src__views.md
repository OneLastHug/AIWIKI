# 目录：komga-webui/src/views

## 它负责什么

`komga-webui/src/views` 是 Komga Web UI 的“页面层”目录，里面的 `.vue` 文件基本都对应一个路由页面。它不负责底层 HTTP 封装、通用控件、数据类型定义或全局状态定义，而是把这些能力组合成用户能访问的完整页面：主页框架、书库浏览、系列/图书详情、阅读器、搜索、账号设置、服务器设置、导入、媒体管理、登录和异常页等。

从 `komga-webui/src/router.ts` 可以看出，`views` 里的组件通过 Vue Router 懒加载挂到具体 path 上，例如 `/dashboard` 对应 `DashboardView.vue`，`/series/:seriesId` 对应 `BrowseSeries.vue`，`/book/:bookId/read` 对应 `DivinaReader.vue`，`/settings/users` 对应 `SettingsUsers.vue`。因此阅读这个目录时，应把它理解成“路由入口页面集合”，而不是一个普通组件库。

## 关键组成

`HomeView.vue` 是主应用壳。它挂在根路由 `/` 下，内部包含 `v-app-bar`、侧边导航抽屉、搜索框、书库列表、导入入口、媒体管理入口、设置入口、账号入口以及 `router-view`。它会读取 Vuex 中的登录用户、书库、任务数、公告、主题和语言等状态；管理员登录后还会请求 actuator info、待检查图书数、公告和 release 信息。子页面大多渲染在 `HomeView.vue` 的嵌套路由中。

浏览类页面是目录中数量最多的一组，包括 `BrowseLibraries.vue`、`BrowseBooks.vue`、`BrowseSeries.vue`、`BrowseBook.vue`、`BrowseCollection.vue`、`BrowseCollections.vue`、`BrowseReadList.vue`、`BrowseReadLists.vue`、`BrowseOneshot.vue`。它们负责展示书库、系列、图书、集合和阅读列表，并处理分页、排序、过滤、选择、多选操作、详情展示、上下文返回等交互。以 `BrowseSeries.vue` 为例，它组合 `ToolbarSticky`、`ItemBrowser`、`ItemCard`、`MultiSelectBar`、`FilterDrawer`、`FilterList`、`FilterPanels`、`SortList`、`SeriesActionsMenu` 等组件；数据来自 `$komgaSeries`、`$komgaBooks`、`$komgaReferential`，并通过路由 query 保存排序、过滤、页码等状态。

阅读器页面包括 `DivinaReader.vue` 和 `EpubReader.vue`。`DivinaReader.vue` 面向图片页式阅读，使用 `PagedReader` 和 `ContinuousReader` 两种阅读组件，并提供全屏、快捷键、页面跳转、缩略图浏览、阅读设置、下载当前页、设置封面、阅读进度上报等能力。`EpubReader.vue` 根据命名和路由推断负责 EPUB 阅读，入口是 `/book/:bookId/read-epub`。

管理和设置类页面包括 `SettingsUsers.vue`、`SettingsServer.vue`、`UISettings.vue`、`UIUserSettings.vue`、`MetricsView.vue`、`AnnouncementsView.vue`、`UpdatesView.vue`、`ServerManagement.vue`、`ServerSettings.vue`、`MediaAnalysis.vue`、`MissingPosters.vue`、`DuplicateFiles.vue`、`DuplicatePagesKnown.vue`、`DuplicatePagesUnknown.vue`、`ImportBooks.vue`、`ImportReadList.vue`。这些页面多数受 `adminGuard` 保护，只允许管理员访问。`SettingsUsers.vue` 是一个很薄的页面，只负责摆放 `UsersList` 和 `AuthenticationActivityTable`，说明该目录中不少 view 是“页面容器”，具体表格、表单和业务动作下沉到了 `components`。

认证、账号和辅助页面包括 `LoginView.vue`、`StartupView.vue`、`WelcomeView.vue`、`NoPinnedLibraries.vue`、`PageNotFound.vue`、`AccountView.vue`、`ApiKeys.vue`、`SelfAuthenticationActivity.vue`、`SearchView.vue`、`HistoryView.vue`。它们覆盖登录启动、无书库引导、无置顶书库提示、404、账号资料、API key、认证活动、搜索和历史记录等场景。

## 上下游关系

上游入口主要是 `komga-webui/src/router.ts`。路由文件负责把 URL、路由名、props、权限守卫和 `views` 组件绑定起来。`HomeView.vue` 是大部分页面的父级 layout；`StartupView.vue`、`LoginView.vue`、`DivinaReader.vue`、`EpubReader.vue`、`PageNotFound.vue` 则是顶层独立路由，不挂在主导航壳内。

`views` 的下游依赖主要有四类。

第一类是 `components`。页面层大量复用 `components/bars`、`components/menus`、`components/dialogs`、`ItemBrowser`、`SearchBox`、`FilterDrawer`、`UsersList` 等组件。页面负责组织布局和业务状态，组件负责局部 UI 和交互。

第二类是 API 插件或服务对象，例如 `$komgaBooks`、`$komgaSeries`、`$komgaReadLists`、`$komgaReferential`、`$komgaAnnouncements`、`$komgaReleases`、`$actuator`。这些对象不是在 `views` 中定义的，而是被注入到 Vue 实例上。页面通过它们加载图书、系列、阅读列表、过滤候选项、公告、版本信息等。

第三类是 Vuex store。`HomeView.vue` 读取 `getLibraries`、`getLibrariesPinned`、`meAdmin`、`authenticated` 等 getter，并提交 `setTheme`、`setLocale`、`setBooksToCheck`、`setAnnouncements` 等 mutation。阅读器也会把阅读设置持久化到 `persistedState.webreader` 相关字段。

第四类是类型、工具函数和枚举，例如 `@/types/komga-books`、`@/types/komga-series`、`@/types/komga-search`、`@/types/context`、`@/functions/urls`、`@/functions/query-params`、`@/functions/book-format`、`@/functions/shortcuts/*`。这些模块让页面能构造搜索条件、生成文件或页面 URL、解析排序参数、决定阅读路由、处理快捷键。

## 运行/调用流程

应用启动后，`router.beforeEach` 先执行全局检查：部分页面切换时重置 `document.title`；如果 OAuth2 弹窗登录完成，会通知父窗口并关闭弹窗；如果目标不是 `startup` 或 `login` 且用户未认证，则重定向到 `startup`，并把原目标写入 `redirect` query。

认证通过后，访问 `/` 会重定向到 `dashboard`。`dashboard`、书库浏览、设置等页面大多作为 `HomeView.vue` 的 children 渲染。`HomeView.vue` 创建时会根据管理员身份预加载一些服务端信息，并用 `checkRoute` 根据当前 path 展开侧边栏对应分组，例如 `/settings/` 展开设置，`/media-management/` 展开媒体管理，`/account/` 展开账号。

访问 `/libraries/:libraryId?` 时不会直接渲染页面，而是根据用户对该书库的默认入口配置调用 `getLibraryRoute`，再重定向到推荐、系列、图书、集合或阅读列表页面。如果没有书库，`noLibraryGuard` 会跳到 `welcome`；如果没有置顶书库，`noLibraryNorPinGuard` 会跳到 `no-pins`。

访问 `/series/:seriesId` 时，`BrowseSeries.vue` 接收 `seriesId` prop。组件挂载后从路由 query 恢复排序、过滤、页码和分页大小；再调用 `$komgaSeries.getOneSeries` 加载系列详情，调用 `$komgaBooks.getBooksList` 加载图书页，调用 `$komgaSeries.getCollections` 加载所属集合。它还订阅 `SERIES_CHANGED`、`BOOK_CHANGED`、`READPROGRESS_CHANGED`、`LIBRARY_DELETED` 等事件，收到 SSE 变化后刷新当前页面或跳转离开已删除资源。

访问 `/book/:bookId/read` 时，`DivinaReader.vue` 接收 `bookId` prop。它从持久化设置恢复阅读方向、动画、缩放、边距、背景色等；调用 `$komgaBooks.getBook`、`$komgaSeries.getOneSeries`、`$komgaBooks.getBookPages` 获取图书、系列和页面列表；给每页生成 `bookPageUrl`；根据 query page、已有阅读进度或默认值跳到对应页。页码变化时通过 debounce 调用 `$komgaBooks.updateReadProgress`，但 incognito 模式下不会上报进度。上一册/下一册通过 `$komgaBooks` 或 `$komgaReadLists` 的 sibling API 决定，并用 `getBookReadRouteFromMedia` 选择图片阅读器或 EPUB 阅读器。

## 小白阅读顺序

1. 先读 `komga-webui/src/router.ts`。重点看 `routes` 数组、`adminGuard`、`noLibraryGuard`、`router.beforeEach`，理解每个 view 对应哪个 URL，以及哪些页面需要管理员权限或登录状态。

2. 再读 `komga-webui/src/views/HomeView.vue`。它是主界面的壳，掌握侧边栏、顶部搜索、主题语言、管理员入口、账号入口和 `router-view` 的关系后，后续页面会容易很多。

3. 接着读一个简单容器页，比如 `komga-webui/src/views/SettingsUsers.vue`。它展示了很多 view 的基本形态：页面只组合业务组件，不在本文件内实现复杂表格逻辑。

4. 然后读一个典型浏览页，比如 `komga-webui/src/views/BrowseSeries.vue`。重点看 props、data、computed、mounted、beforeRouteUpdate、methods，以及排序过滤如何同步到 route query。这是理解 Komga Web UI 页面状态管理的代表样本。

5. 最后读阅读器，例如 `komga-webui/src/views/DivinaReader.vue`。它比普通页面复杂，涉及全屏、快捷键、阅读进度、兄弟图书跳转、阅读设置持久化和页面资源 URL 生成，适合在理解前面结构后再看。

## 常见误区

不要把 `views` 当成纯 UI 静态模板。很多页面虽然模板很长，但真正的业务流在 lifecycle、watch、computed setter 和 methods 里，例如 `BrowseSeries.vue` 会把过滤条件写入路由并重新加载分页，`DivinaReader.vue` 会在页码变化时更新阅读进度。

不要以为所有页面都挂在 `HomeView.vue` 下。登录、启动、阅读器和 404 是顶层路由；阅读器不会显示主导航壳，这是为了提供沉浸式阅读体验。

不要在 `views` 里寻找所有业务实现。用户列表、过滤器、菜单、浏览卡片、阅读器核心渲染等很多逻辑在 `components`；HTTP 细节在注入的 `$komga*` 服务；搜索条件和 DTO 在 `types`；URL 和参数处理在 `functions`。

不要忽略路由 query。浏览页的排序、过滤、页码、上下文和阅读器页码都可能通过 query 保存。直接只看 data 初始值，会误判页面刷新、浏览器前进后退和分享链接时的行为。

不要忽略权限守卫。`SettingsUsers.vue` 本身没有检查管理员权限，但路由上的 `beforeEnter: adminGuard` 已经处理了访问控制。判断页面是否受限时要看 `router.ts`，不能只看 view 文件。

不要把 `BrowseLibraries.vue` 的命名简单理解为“书库列表页”。从路由 `/libraries/:libraryId/series` 和重定向逻辑看，它实际承担某个书库下的系列浏览入口；真正“全部书库/指定书库”由 `libraryId` 参数和 `LIBRARIES_ALL` 共同决定。
