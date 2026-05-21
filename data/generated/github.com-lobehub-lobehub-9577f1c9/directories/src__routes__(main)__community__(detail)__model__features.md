# 目录：src/routes/(main)/community/(detail)/model/features

## 它负责什么

`src/routes/(main)/community/(detail)/model/features` 是社区模型详情页的页面级功能实现目录，服务于路由页面 `src/routes/(main)/community/(detail)/model/index.tsx`。它不负责拉取模型详情数据本身，而是在父页面拿到 `DiscoverModelDetail` 后，负责把这份详情数据渲染成可浏览、可跳转、可分享、可进入聊天或 Provider 指南的 UI。

从页面入口看，`model/index.tsx` 会：

1. 通过 `useParams<{ slug: string }>()` 读取 URL 中的模型标识。
2. `decodeURIComponent(params.slug ?? '')` 得到 `identifier`。
3. 从 `useDiscoverStore((s) => s.useModelDetail)` 取出 SWR hook。
4. 调用 `useModelDetail({ identifier })` 请求模型详情。
5. 加载时显示 `loading`，无数据时显示 `NotFound`。
6. 有数据时用 `<DetailProvider config={data}>` 包住 `<Header />` 和 `<Details />`。

因此，这个目录的核心职责可以概括为：**消费模型详情数据上下文，渲染模型详情页的头部、导航 Tab、正文内容、侧栏推荐、操作按钮和 Provider 支持表格。**

需要注意的是，按照当前项目新的 `spa-routes` 约定，`src/routes/` 理想上应保持“薄路由”，复杂 UI 更推荐迁移到 `src/features/`。但这里仍是旧式结构：`features` 放在 route 目录内部，说明它属于尚未完全迁移的社区详情页实现。

## 关键组成

这个目录可以分成四组来看。

第一组是数据上下文：`DetailProvider.tsx`。

它定义了：

- `DetailContextConfig = Partial<DiscoverModelDetail>`
- `DetailContext = createContext<DetailContextConfig>({})`
- `DetailProvider`
- `useDetailContext`

父页面把接口返回的 `data` 放进 `DetailProvider config={data}`，后代组件统一通过 `useDetailContext()` 读取字段，比如 `identifier`、`displayName`、`providers`、`related`、`category`、`abilities`、`contextWindowTokens`、`maxOutput`、`maxDimension` 等。

这里用的是 React 19 风格的 `use(DetailContext)`，而不是传统的 `useContext(DetailContext)`。小白阅读时不要误以为 `useDetailContext` 是异步 hook；这里的 `use` 是 React API，用于读取 context。

第二组是页面头部：`Header.tsx`。

`Header` 从详情上下文中读取：

- `identifier`
- `releasedAt`
- `displayName`
- `type`
- `abilities`
- `contextWindowTokens`

它负责渲染模型详情页顶部信息，包括：

- `ModelIcon` 模型图标
- 模型名称，优先 `displayName`，否则用 `identifier`
- `ModelTypeIcon` 模型类型图标
- 原始模型标识 `identifier`
- `ModelInfoTags`，展示模型能力与上下文窗口等标签
- `PublishedTime`，展示发布时间
- `models` i18n 命名空间下的模型描述：`t(`${identifier}.description`)`

这说明模型描述不是直接来自详情接口字段，而是通过 `models` 翻译资源按模型 ID 查出来的。`ActionButton` 的分享描述则使用了 `description` 字段，两者来源不同，阅读时要区分。

第三组是正文区域：`Details/`。

`Details/index.tsx` 是正文总入口。它用 `useQueryState('activeTab')` 把当前 Tab 同步到 URL query，默认值是 `ModelNavKey.Overview`。它包含三个 Tab：

- `Overview`
- `Parameter`
- `Related`

`Details/Nav.tsx` 用 `@lobehub/ui` 的 `Tabs` 渲染导航。三个 key 来自 `ModelNavKey`：

- `ModelNavKey.Overview`
- `ModelNavKey.Parameter`
- `ModelNavKey.Related`

桌面端导航右侧还放了三个外链：

- Discord 帮助链接：`SOCIAL_URL.discord`
- 源码链接：`[URL已移除]
- issue 反馈链接：`[URL已移除]

`Details/Overview/index.tsx` 负责“支持的 Providers”总览。它读取 `providers = []`，用 `Title` 显示数量标签，然后交给 `ProviderList` 渲染表格。

`Details/Overview/ProviderList/index.tsx` 是这个目录里信息密度最高的组件。它使用 `InlineTable` 展示每个 Provider 对当前模型的支持情况，列包括：

- Provider 图标和名称，点击进入 `/community/provider/:id`
- 模型能力 `record.model?.abilities`
- 上下文长度 `record.model?.contextWindowTokens`
- 最大输出或最大维度 `record.model?.maxOutput || record.model?.maxDimension`
- 输入价格，通过 `getTextInputUnitRate(record.model?.pricing)` 和 `formatPriceByCurrency` 格式化
- 输出价格，通过 `getTextOutputUnitRate(record.model?.pricing)` 和 `formatPriceByCurrency` 格式化
- 操作区：官方标记、API key 提示、Provider 文档链接、详情页跳转

这里的 Provider 行数据不是简单的 provider 基本信息，而是包含 `record.model` 的模型级信息，所以表格能显示“同一个模型在不同 Provider 下的能力、上下文、价格差异”。

`Details/Parameter/index.tsx` 负责参数说明页。它没有从后端拿完整参数 schema，而是在前端写死了一组常见参数：

- `temperature`
- `top_p`
- `presence_penalty`
- `frequency_penalty`
- `max_tokens`
- `reasoning_effort`

其中 `max_tokens` 的范围会根据详情上下文中的 `maxOutput` 或 `maxDimension` 计算；其他参数的范围是静态配置。每个参数交给 `ParameterItem.tsx` 展示描述、类型、默认值和范围，并带一个默认文档链接 `[URL已移除]

`Details/Related/index.tsx` 负责相关模型列表。它读取 `related` 和 `category`，用社区模型列表页的 `List` 组件渲染：`../../../../../(list)/model/features/List`。根据当前片段，正文里的 `moreLink` 拼到了 `/community/plugin` 并附带 `category` query；而侧栏相关模型的更多链接是 `/community/model`。这可能是历史复制留下的差异，也可能是当前业务有意为之；仅根据当前片段无法确认，应以运行结果或产品需求为准。

第四组是侧栏：`Sidebar/`。

`Sidebar/index.tsx` 根据 `mobile` 和当前 `activeTab` 决定展示内容。

移动端只显示：

- `ActionButton`

桌面端使用 `ScrollShadow` 固定宽度 `360`，并设置 sticky：

- `ActionButton`
- 当前 Tab 不是 `Related` 时显示 `Related`
- 当前 Tab 不是 `Overview` 时显示 `RelatedProviders`

这个设计避免正文和侧栏重复展示同类内容。例如正文已经在 `Overview` 展示 Provider 表格时，侧栏不显示 `RelatedProviders`；正文已经在 `Related` 展示相关模型时，侧栏不显示 `Related`。

`Sidebar/ActionButton/index.tsx` 包含两个动作：

- `ChatWithModel`
- `ShareButton`

`ShareButton` 的分享元信息包括模型头像、描述、Provider 名称 hashtags、标题和官方 URL。URL 使用 `urlJoin(OFFICIAL_URL, '/community/model', identifier as string)` 拼出。

`Sidebar/ActionButton/ChatWithModel.tsx` 负责“聊天/指南”主按钮逻辑。它读取 `providers`：

- 如果 providers 中包含 `id === 'lobehub'`，主按钮文案是 `models.chat`，点击后 `navigate('/agent')`，下拉菜单中列出其他 Provider 的指南入口。
- 如果不包含 `lobehub` 且只有一个 Provider，则直接渲染一个链接按钮，跳到 `/community/provider/:id`。
- 如果有多个非 LobeHub Provider，则渲染 `DropdownMenu`，让用户选择 Provider 指南。

这表示“能否直接聊天”不是由模型能力字段决定，而是由是否存在 `lobehub` Provider 决定。

`Sidebar/Related/index.tsx` 展示相关模型卡片。每项使用 `Related/Item.tsx`，里面用 `ModelIcon`、模型名和 `models` 命名空间下的描述。点击跳转 `/community/model/:identifier`。

`Sidebar/RelatedProviders/index.tsx` 展示支持该模型的 Provider，最多取 `providers.slice(0, 6)`。每项使用 `RelatedProviders/Item.tsx`，里面用 `ProviderIcon`、Provider 名称和 `providers` 命名空间下的描述。点击跳转 `/community/provider/:id`。

## 上下游关系

上游主要有三层。

第一层是路由入口：`src/routes/(main)/community/(detail)/model/index.tsx`。它负责拿 URL 参数、调用数据 hook、处理 loading/not found，并把详情数据注入到 `DetailProvider`。

第二层是 discover store：`src/store/discover/slices/model/action.ts`。其中 `useModelDetail` 使用 SWR，key 形如 `['model-details', locale, params.identifier].filter(Boolean).join('-')`，请求函数是 `discoverService.getModelDetail(params)`，并设置 `revalidateOnFocus: false`。

第三层是 discover service：`src/services/discover.ts`。`getModelDetail` 会读取当前语言 `globalHelpers.getCurrentLanguage()`，再调用 `lambdaClient.market.getModelDetail.query({ ...params, locale })`。也就是说，模型详情页的数据最终来自后端 market tRPC 接口，并且带有 locale。

下游主要是 UI 和导航目标。

这个目录会使用很多通用或邻近组件：

- `@lobehub/ui`：`Flexbox`、`Tabs`、`Block`、`Button`、`DropdownMenu`、`Tooltip`、`ActionIcon` 等。
- `@lobehub/icons`：`ModelIcon`、`ProviderIcon`。
- `@/components/ModelSelect`：`ModelInfoTags`。
- `@/components/PublishedTime`。
- `@/components/InlineTable`。
- `@/routes/(main)/community/features/Title`。
- `@/routes/(main)/community/(list)/model/features/List`。
- `@/routes/(main)/community/(list)/model/features/List/ModelTypeIcon`。
- `@/utils/format` 和 `@/utils/pricing`，用于 token 与价格格式化。

它产生的页面跳转包括：

- `/community/provider/:providerId`
- `/community/model/:modelIdentifier`
- `/agent`
- `/community/provider`
- `/community/model`
- 根据当前代码片段，正文 Related 的更多链接为 `/community/plugin?category=...`

它产生的外链包括：

- Provider 文档：`urlJoin(BASE_PROVIDER_DOC_URL, record.id)`
- Discord、GitHub 源码、GitHub issue
- 参数文档：`[URL已移除]

## 运行/调用流程

一个典型访问流程如下。

1. 用户进入社区模型详情页，例如 `/community/model/gpt-4.1`。
2. `model/index.tsx` 从 React Router params 里取 `slug`，解码成 `identifier`。
3. 页面调用 `useDiscoverStore` 中的 `useModelDetail({ identifier })`。
4. store 层通过 SWR 调用 `discoverService.getModelDetail`。
5. service 层调用 `lambdaClient.market.getModelDetail.query`，并带上当前语言 `locale`。
6. 页面处于请求中时显示 `Loading`。
7. 请求结束但无数据时显示 `NotFound`。
8. 请求成功后，页面将 `data` 传入 `DetailProvider`。
9. `Header` 从 `useDetailContext()` 读取模型基础信息，渲染图标、名称、能力、发布时间和描述。
10. `Details` 读取 URL query 中的 `activeTab`，没有时默认 `Overview`。
11. `Nav` 根据 `activeTab` 渲染 Tab，并在切换时通过 `setActiveTab` 写回 query。
12. 如果当前是 `Overview`，正文展示 Provider 支持表格。
13. 如果当前是 `Parameter`，正文展示参数说明折叠面板。
14. 如果当前是 `Related`，正文展示相关模型列表。
15. `Sidebar` 根据移动端/桌面端和当前 Tab 决定侧栏内容。
16. `ActionButton` 始终提供聊天/指南和分享能力。
17. 用户点击 Provider、相关模型、文档或分享按钮后，分别进入站内详情页、外部文档或分享流程。

从状态角度看，这个目录本身几乎没有复杂业务状态。主要状态只有：

- `DetailContext`：由父页面注入的模型详情。
- URL query `activeTab`：控制当前 Tab。
- 响应式状态 `useResponsive()`：控制桌面/移动布局。

## 小白阅读顺序

建议按“数据从哪里来，到哪里去”的顺序读。

第一步，读 `src/routes/(main)/community/(detail)/model/index.tsx`。先理解父页面如何取 `slug`、如何调用 `useModelDetail`、如何处理加载和空状态，以及如何把 `data` 注入 `DetailProvider`。这是整个目录的数据入口。

第二步，读 `DetailProvider.tsx`。确认后代组件不是各自请求数据，而是统一通过 `useDetailContext()` 读详情上下文。之后看到任何组件里直接解构 `providers`、`related`、`identifier`，都知道来源是这里。

第三步，读 `Header.tsx`。它最直观，字段也少，适合理解模型详情页顶部展示了什么。重点看 `displayName || identifier`、`ModelInfoTags`、`PublishedTime` 和 `t(`${identifier}.description`)`。

第四步，读 `Details/index.tsx` 和 `Details/Nav.tsx`。这里能理解 `activeTab` 如何控制三个正文页面，以及为什么 URL query 会影响当前 Tab。

第五步，读 `Details/Overview/index.tsx` 和 `Details/Overview/ProviderList/index.tsx`。这是模型详情页最核心的信息表，展示“哪些 Provider 支持这个模型，以及各自价格、上下文、最大输出等差异”。

第六步，读 `Details/Parameter/index.tsx` 和 `ParameterItem.tsx`。这里可以看到参数说明不是后端动态 schema，而是前端静态参数列表加少量详情字段补充。

第七步，读 `Sidebar/index.tsx`。先理解移动端和桌面端差异，再理解为什么某些 Tab 下会隐藏侧栏中的相关模型或 Provider。

第八步，读 `Sidebar/ActionButton/ChatWithModel.tsx`。这里包含页面动作的业务判断：是否能直接聊天，取决于 providers 中是否有 `lobehub`。

第九步，读 `Sidebar/Related` 和 `Sidebar/RelatedProviders`。这两组结构相似，一个展示相关模型，一个展示支持 Provider，适合最后快速对照。

## 常见误区

不要把这个目录理解成数据请求层。真正的数据请求在父页面、discover store 和 discover service 中完成；这里主要是消费 `DetailProvider` 提供的详情数据。

不要看到 `features` 就以为它是全局 `src/features` 里的新架构功能模块。它位于 `src/routes/(main)/community/(detail)/model/features`，属于 route 内部的旧式页面实现。根据项目约定，未来如果重构，复杂 UI 更可能迁移到 `src/features/<Domain>/`。

不要误以为 `Header` 中的模型描述一定来自接口字段。`Header` 使用 `useTranslation('models')` 和 `identifier` 拼 i18n key；分享按钮使用的 `description` 才来自详情上下文。

不要误以为参数页展示的是某个 Provider 的精确 API 参数定义。`Parameter` 中大多数参数是前端静态写死的通用说明，只有 `max_tokens` 的范围会参考 `maxOutput` 或 `maxDimension`。

不要把 `providers` 当成纯 Provider 列表。至少在 `ProviderList` 中，每个 provider item 还带有 `model` 信息，例如 `model.abilities`、`model.contextWindowTokens`、`model.pricing`，用于展示当前模型在该 Provider 下的差异。

不要忽略 `activeTab` 是 URL query 状态。`Details` 用 `useQueryState('activeTab')`，`Sidebar` 用 `useQuery()` 读取它；所以页面刷新、复制链接、侧栏显示逻辑都可能受 query 影响。

不要把“聊天”按钮的判断和模型能力混为一谈。`ChatWithModel` 判断是否显示直接聊天，是看 providers 里是否存在 `id === 'lobehub'`；不是看 `abilities` 是否支持 chat。

不要想当然认为桌面端和移动端侧栏一致。移动端只显示操作按钮；桌面端才有 sticky 侧栏，并根据当前 Tab 显示或隐藏相关模型、相关 Provider。

不要忽略当前代码里的路径差异。侧栏相关模型更多链接指向 `/community/model`，但正文 `Details/Related` 的 `moreLink` 根据当前片段指向 `/community/plugin`。这可能是历史遗留或业务特殊逻辑；如果要修改，需要结合产品预期和运行页面确认。
