# 目录：src/routes/(main)/community/(detail)/model

## 它负责什么

`src/routes/(main)/community/(detail)/model` 负责社区模型详情页，也就是类似 `/community/model/:slug` 的页面。它展示某个模型的基础信息、支持的服务商、模型参数说明、相关模型，以及侧边栏里的“开始聊天/查看接入指南/分享”等操作。

这个目录虽然位于 `src/routes` 下，但它不是纯粹的薄路由文件：`index.tsx` 是路由入口，`features/` 下则放了该详情页专用的局部 UI 和上下文。它仍然遵循社区详情页的整体布局：外层由 `src/routes/(main)/community/(detail)/_layout/index.tsx` 提供 `Header`、`WideScreenContainer`、`Footer` 和 `Outlet`，本目录只填充模型详情页主体内容。

入口导出有两个：

- `default ModelDetailPage`：桌面端模型详情页。
- `MobileModelPage`：移动端包装版本，内部只是给 `ModelDetailPage` 传入 `mobile={true}`。

## 关键组成

`index.tsx` 是页面总入口。它通过 `useParams<{ slug: string }>()` 读取 URL 中的 `slug`，再用 `decodeURIComponent` 得到模型 `identifier`。随后从 `useDiscoverStore` 取出 `useModelDetail`，调用 `useModelDetail({ identifier })` 获取模型详情数据。加载中返回 `loading.tsx` 导出的 `DetailsLoading`，无数据返回共享的 `NotFound`，成功后用 `DetailProvider` 包住 `Header` 和 `Details`。

`loading.tsx` 很薄，只是把 `../../components/ListLoading` 里的 `DetailsLoading` 作为默认导出。也就是说模型详情页的 loading 态复用了社区详情页公共 loading 组件。

`features/DetailProvider.tsx` 定义本目录的数据上下文。它创建 `DetailContext`，类型是 `Partial<DiscoverModelDetail>`，并导出 `useDetailContext()`。页面拿到的模型详情数据会作为 `config` 注入，后续 `Header`、`Details`、`Sidebar`、`ProviderList` 等组件都不再单独请求数据，而是从这个 context 中读取。

`features/Header.tsx` 展示模型头部信息。它读取 `identifier`、`releasedAt`、`displayName`、`type`、`abilities`、`contextWindowTokens`，使用 `ModelIcon` 展示模型图标，使用 `ModelTypeIcon` 展示模型类型，使用 `ModelInfoTags` 展示能力标签，使用 `PublishedTime` 展示发布时间。描述文案来自 `useTranslation('models')`，key 是 `${identifier}.description`，因此模型描述依赖 `models` 命名空间下按模型 identifier 组织的翻译文本。

`features/Details/index.tsx` 是详情主体的 tab 容器。它用 `useQueryState('activeTab')` 把当前 tab 同步到 URL query，默认值是 `ModelNavKey.Overview`。根据当前 tab 渲染三个子页面：

- `Overview`：概览，主要是支持该模型的 provider 列表。
- `Parameter`：参数说明，如 `temperature`、`top_p`、`presence_penalty`、`frequency_penalty`、`max_tokens`、`reasoning_effort`。
- `Related`：相关模型列表。

`features/Details/Nav.tsx` 定义 tab 导航。三个 tab 分别使用 `BookOpenIcon`、`Settings2Icon`、`ListIcon`。桌面端右侧还提供外链：Discord 求助、源码位置、GitHub issue 反馈。移动端只显示 tabs，不显示这些辅助链接。

`features/Details/Overview/ProviderList/index.tsx` 是模型详情页最核心的信息表。它读取 `providers`，用 `InlineTable` 展示每个 provider 对当前模型的支持情况，包括 provider 名称、模型能力、上下文长度、最大输出、输入价格、输出价格和操作。操作列里会区分 `lobehub` 官方 provider 与普通 API provider，并提供文档链接和 provider 详情页链接。

`features/Details/Parameter/index.tsx` 不读取后端的完整参数 schema，而是在前端固定列出常见模型参数。它会根据详情数据里的 `maxOutput` 或 `maxDimension` 推导 `max_tokens` 的范围，其余参数的默认值、范围和说明来自本地定义与 `discover` i18n 文案。

`features/Sidebar/index.tsx` 负责右侧栏。移动端只展示 `ActionButton`；桌面端使用 `ScrollShadow` 做 sticky 侧边栏，宽度固定为 `360`，并根据当前 `activeTab` 控制相关模块显示：不在 Related tab 时显示相关模型，不在 Overview tab 时显示相关 providers。

`features/Sidebar/ActionButton` 包含两个动作：`ChatWithModel` 和 `ShareButton`。分享信息由模型 icon、描述、provider 名称 hashtags、标题、官方 URL 组成。`ChatWithModel` 会检查 providers 中是否包含 `id === 'lobehub'`：如果包含，主按钮点击跳转 `/agent`，下拉菜单列出其他 provider 的接入指南；如果只有一个非 LobeHub provider，则按钮直接跳到对应 `/community/provider/:id`；如果有多个 provider，则用下拉菜单让用户选择。

## 上下游关系

上游路由注册在 SPA router 中。桌面路由里 `path: 'model/:slug'` 动态导入 `@/routes/(main)/community/(detail)/model`；移动路由里同样注册 `model/:slug`，但导入后取 `MobileModelPage`。因此这个目录既服务桌面端，也服务移动端，只是通过 `mobile` prop 调整布局。

数据上游是 `src/store/discover/slices/model/action.ts` 中的 `useModelDetail`。它内部使用 `useSWR`，key 由 `model-details`、当前语言和 `params.identifier` 组成，fetcher 调用 `discoverService.getModelDetail(params)`。根据当前片段推断，真正的远程接口封装在 `@/services/discover`，本目录不直接碰接口，也不处理缓存策略，只消费 SWR 的 `data` 和 `isLoading`。

类型上游是 `@/types/discover`，其中至少提供 `DiscoverModelDetail` 和 `ModelNavKey`。本目录把 `DiscoverModelDetail` 作为 context 数据形状，把 `ModelNavKey` 作为 tab key，避免手写字符串分支。

UI 下游主要是社区详情页公共组件和社区列表组件。例如：

- `../components/NotFound`：详情页通用未找到状态。
- `../../components/ListLoading`：详情页 loading。
- `../../features/Title`、`ShareButton`：社区详情页公共标题和分享能力。
- `src/routes/(main)/community/(list)/model/features/List`：相关模型复用列表页的模型列表组件。
- `src/routes/(main)/community/(list)/model/features/List/ModelTypeIcon`：头部复用模型类型图标。

跨页面跳转关系也很明显：模型详情页会链接到 `/community/provider/:id`、`/community/model/:identifier`、`/agent`，还会跳到外部 provider 文档地址和 GitHub 源码/issue 页面。

## 运行/调用流程

1. 用户访问 `/community/model/:slug`。
2. React Router 匹配 community detail layout，再通过 `Outlet` 渲染本目录的 `ModelDetailPage`。
3. `ModelDetailPage` 从 URL params 读取 `slug`，解码为 `identifier`。
4. 页面调用 `useDiscoverStore((s) => s.useModelDetail)` 得到 SWR hook，再请求 `discoverService.getModelDetail({ identifier })`。
5. 如果 `isLoading` 为真，渲染 `DetailsLoading`；如果请求完成但 `data` 为空，渲染 `NotFound`。
6. 请求成功后，`DetailProvider` 把 `data` 放进 React context。
7. `Header` 从 context 读取模型名称、能力、类型、发布时间等，渲染顶部摘要。
8. `Details` 读取 URL query 中的 `activeTab`，默认进入 `Overview`。
9. `Nav` 切换 tab 时调用 `setActiveTab`，URL query 随之变化。
10. 当前 tab 渲染对应内容：`Overview` 展示 provider 表，`Parameter` 展示参数说明，`Related` 展示相关模型。
11. `Sidebar` 同步读取 `activeTab`，决定是否展示相关模型和相关 providers，并提供聊天、指南和分享动作。
12. 移动端通过 `MobileModelPage` 传入 `mobile`，布局会改为更紧凑的 tab 和按钮区域。

## 小白阅读顺序

建议先读 `index.tsx`。它能让你快速理解这个目录的页面生命周期：取 URL 参数、请求详情、处理 loading/not-found、注入 context、渲染头部和详情。

第二步读 `features/DetailProvider.tsx`。这个文件很短，但它解释了为什么很多子组件没有 props 却能拿到模型数据。理解这个 context 后，再看其他组件会轻松很多。

第三步读 `features/Header.tsx`。它展示的是最直观的模型基础信息，也能帮助你认识 `DiscoverModelDetail` 中常用字段，比如 `identifier`、`displayName`、`abilities`、`contextWindowTokens`、`releasedAt`。

第四步读 `features/Details/index.tsx` 和 `features/Details/Nav.tsx`。这里是 tab 状态的中心，重点看 `useQueryState('activeTab')` 和 `ModelNavKey`。理解它之后，再分别读 `Overview`、`Parameter`、`Related`。

第五步读 `features/Details/Overview/ProviderList/index.tsx`。这是信息密度最高的组件，涉及 provider、pricing、abilities、文档链接、详情页跳转。读它能理解“一个模型被多个 provider 支持”这一业务关系。

第六步读 `features/Sidebar/ActionButton/ChatWithModel.tsx`。这个文件体现了用户操作逻辑：如果 LobeHub 官方支持，就可以直接去 `/agent` 聊天；否则引导用户去 provider 页面查看接入指南。

最后再回头看 `features/Sidebar/index.tsx`，理解桌面端和移动端的布局差异，以及侧边栏内容为什么会随着 active tab 改变。

## 常见误区

不要把 `slug` 当成数据库 id。这里的 `slug` 会被解码成 `identifier`，并传给 `useModelDetail`。从代码看，模型详情页围绕模型 identifier 工作，而不是数字 id。

不要以为每个子组件都会自己请求数据。本目录只有入口页通过 discover store 获取详情数据，子组件通过 `useDetailContext()` 读取同一份数据。排查字段缺失时，应先看 `DiscoverModelDetail` 和 `discoverService.getModelDetail` 的返回，而不是在子组件里找请求逻辑。

不要把 `activeTab` 理解成纯 React state。它来自 `useQueryState('activeTab')`，会反映到 URL query 中。刷新页面或分享链接时，tab 状态可能保留在 URL 里。

不要忽略桌面端和移动端差异。`MobileModelPage` 不是独立实现，而是给同一个 `ModelDetailPage` 加 `mobile={true}`。很多组件同时又调用 `useResponsive()`，所以实际布局取决于 prop 和响应式断点共同结果。

不要认为 `Parameter` tab 展示的是 provider 返回的完整参数能力。当前代码里参数列表主要是前端固定配置，只有 `max_tokens` 的范围会根据 `maxOutput` 或 `maxDimension` 做一点动态推导。

不要把 provider 表里的文档链接和站内 provider 详情页混淆。`ProviderList` 同时提供外部文档链接 `BASE_PROVIDER_DOC_URL/:providerId` 和站内链接 `/community/provider/:id`，前者是指南文档，后者是社区 provider 详情。

注意 `Details/Related/index.tsx` 中“查看更多”的 `moreLink` 当前指向 `/community/plugin` 并带上 `category` query，而侧边栏 `Related` 指向 `/community/model`。根据当前片段推断，这可能是历史复用或潜在不一致点；阅读时不要简单假设所有相关模型入口都跳向同一个列表页。
