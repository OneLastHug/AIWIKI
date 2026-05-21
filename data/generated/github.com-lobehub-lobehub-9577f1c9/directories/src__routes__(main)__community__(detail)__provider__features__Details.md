# 目录：src/routes/(main)/community/(detail)/provider/features/Details

## 它负责什么

`Details` 是社区 Provider 详情页中“详情内容区”的组织组件。它不负责拉取 Provider 数据，也不负责决定当前 Provider 是否存在；这些事情由上层页面 `src/routes/(main)/community/(detail)/provider/index.tsx` 完成。`Details` 的核心职责是：

1. 根据 URL 查询参数 `activeTab` 控制当前打开的详情标签页。
2. 渲染 Provider 详情页的三个主要内容标签：
   - `Overview`：模型概览，展示该 Provider 支持的模型列表。
   - `Guide`：接入指南，展示 Provider 的 `readme` Markdown 内容。
   - `Related`：相关 Provider 推荐列表。
3. 根据桌面端/移动端布局差异，安排 `Nav`、主内容和右侧 `Sidebar` 的位置。
4. 从上层 `DetailProvider` 提供的 React Context 中读取 Provider 详情数据，但自身不直接请求 API。

换句话说，这个目录是 Provider 详情页的“内容编排层”：它把已经拿到的数据拆给导航、概览表格、文档渲染和相关推荐几个子视图。

## 关键组成

### `index.tsx`

这是目录入口，默认导出 `Details`。

它的主要 import 分为几类：

- UI 与响应式：
  - `Flexbox` from `@lobehub/ui`
  - `useResponsive` from `antd-style`
- 状态与类型：
  - `useQueryState` from `@/hooks/useQueryParam`
  - `ProviderNavKey` from `@/types/discover`
- 同级/邻近组件：
  - `Sidebar` from `../Sidebar`
  - `Guide`、`Nav`、`Overview`、`Related`

核心逻辑是：

```tsx
const [activeTab, setActiveTab] = useQueryState('activeTab', {
  clearOnDefault: true,
  defaultValue: ProviderNavKey.Overview,
});
```

也就是说，当前 tab 被同步到 URL query 的 `activeTab`。默认是 `ProviderNavKey.Overview`，并且当值等于默认值时会从 URL 中清掉 query，避免默认页也带冗余参数。

渲染时根据 `activeTab` 选择内容：

- `ProviderNavKey.Overview` -> `<Overview />`
- `ProviderNavKey.Guide` -> `<Guide />`
- `ProviderNavKey.Related` -> `<Related />`

布局上，桌面端是主内容和 `Sidebar` 横向排列；移动端会把方向改成 `column-reverse`，让侧边信息在移动端视觉顺序上更适配详情页阅读。

### `Nav.tsx`

`Nav` 是标签页导航组件，默认导出 `Nav`。

它接收：

- `activeTab?: ProviderNavKey`
- `mobile?: boolean`
- `setActiveTab?: (tab: ProviderNavKey) => void`

它通过 `useDetailContext()` 读取当前 Provider 的 `identifier`，并使用 `BRANDING_PROVIDER` 做一个特殊判断：

```tsx
const showGuideTab = identifier !== BRANDING_PROVIDER;
```

如果当前 Provider 是品牌 Provider，则隐藏 `Guide` 标签。代码注释说明原因是这个 Provider 没有 integration docs。

`Nav` 使用 `Tabs` from `@lobehub/ui`，三个 tab 对应：

- Overview：`BookOpenIcon`
- Guide：`BrainCircuitIcon`
- Related：`ListIcon`

文案来自 `useTranslation('discover')`，例如：

- `providers.details.overview.title`
- `providers.details.guide.title`
- `providers.details.related.title`

桌面端额外显示右侧外链：

- Discord 求助链接：`SOCIAL_URL.discord`
- 查看源码：拼到 GitHub `src/config/modelProviders/${identifier}.ts`
- Report issue：GitHub issue 创建页

移动端只返回紧凑版 tab，不显示这些辅助链接。

样式使用 `createStaticStyles`，符合仓库倾向的 zero-runtime 样式写法。

### `Overview/index.tsx`

`Overview` 是概览页，默认导出 `Overview`。

它通过 `useDetailContext()` 读取：

```tsx
const { models = [] } = useDetailContext();
```

然后渲染：

- 标题：`Title`
- 数量标签：`<Tag>{models.length}</Tag>`
- 模型表格：`<ModelList />`

这里本身不处理模型字段，只负责给用户一个“支持的模型”区域标题。真正的表格列定义在 `Overview/ModelList/index.tsx`。

### `Overview/ModelList/index.tsx`

这是 `Overview` 中最重要的展示组件，默认导出 `ModelList`。

它从 `DetailProvider` 上下文读取 `models`，并把它们作为 `InlineTable` 的 `dataSource`。表格 `rowKey` 是模型 `id`，横向滚动宽度是 `x: 900`，说明列较多，移动或窄屏下需要横向滚动。

主要列包括：

- 模型名列：
  - 显示 `ModelIcon`
  - 显示 `record.displayName`
  - 显示模型 id
  - 点击跳转到 `/community/model/${record.id}`
  - 支持按 `displayName` 排序
- 能力列：
  - 读取 `record.abilities`
  - 如果没有任何能力为 `true`，显示 `--`
  - 否则用 `ModelInfoTags` 展示能力标签
- 上下文长度：
  - 字段 `contextWindowTokens`
  - 用 `formatTokenNumber` 格式化
  - 支持排序
- 最大输出：
  - 字段 `maxOutput`
  - 用 `Tooltip` 解释含义
  - 支持排序
- 输入价格：
  - 从 `record.pricing` 通过 `getTextInputUnitRate` 取文本输入单价
  - 用 `formatPriceByCurrency` 格式化
  - 支持排序
- 输出价格：
  - 从 `record.pricing` 通过 `getTextOutputUnitRate` 取文本输出单价
  - 用 `formatPriceByCurrency` 格式化
  - 支持排序
- 操作列：
  - 使用 `ChevronRightIcon`
  - 点击同样跳到 `/community/model/${record.id}`

这个组件连接了多个仓库公共能力：`InlineTable`、模型图标、模型能力标签、价格工具、token 数格式化工具和 React Router 的 `Link`。

### `Guide/index.tsx`

`Guide` 是 Provider 接入指南页，默认导出 `Guide`。

它从上下文读取：

```tsx
const { readme = '' } = useDetailContext();
```

如果没有 `readme`，返回一个 outlined `Block`，里面用 `Empty` 展示空态，图标是 `BookOpen`，文案使用 `providers.details.guide.title`。

如果有 `readme`，则用：

```tsx
<Mdx enableImageGallery={false} enableLatex={false} fontSize={14} headerMultiple={0.3}>
  {readme}
</Mdx>
```

这说明指南内容是 Markdown/MDX 风格文本，但这里关闭了图片画廊和 LaTeX，并把字号、标题缩放调小，适合嵌在详情页正文中。

### `Related/index.tsx`

`Related` 是相关 Provider 区域，默认导出 `Related`。

它从上下文读取：

```tsx
const { related } = useDetailContext();
```

然后复用 Provider 列表页的 `List` 组件：

```tsx
<List data={related} rows={2} />
```

标题使用社区通用的 `Title`，并带有更多链接：

```tsx
moreLink="/community/provider"
```

需要注意：这里的 i18n key 使用的是 `assistants.details.related.*`，不是 `providers.details.related.*`。根据当前片段推断，这是复用了社区详情页通用的“相关推荐”文案，而不是 Provider 专属文案。

## 上下游关系

上游入口是：

`src/routes/(main)/community/(detail)/provider/index.tsx`

这个页面组件做了几件关键事情：

1. 通过 `useParams<{ slug: string }>()` 读取 URL 中的 `slug`。
2. `decodeURIComponent(params.slug ?? '')` 得到 Provider 的 `identifier`。
3. 从 `useDiscoverStore` 取出 `useProviderDetail`。
4. 调用：

```tsx
useProviderDetail({ identifier, withReadme: true })
```

5. loading 时渲染 `Loading`。
6. 没有数据时渲染 `NotFound`。
7. 有数据时用：

```tsx
<DetailProvider config={data}>
  <Header mobile={mobile} />
  <Details mobile={mobile} />
</DetailProvider>
```

包住详情页内容。

因此，`Details` 的所有业务数据都来自 `DetailProvider`，而不是 props。

`DetailProvider` 位于：

`src/routes/(main)/community/(detail)/provider/features/DetailProvider.tsx`

它定义了：

- `DetailContextConfig = Partial<DiscoverProviderDetail>`
- `DetailContext = createContext<DetailContextConfig>({})`
- `DetailProvider`
- `useDetailContext`

下游方面，`Details` 会把数据消费分散到几个子组件：

- `Nav` 使用 `identifier` 判断是否显示 Guide，并生成源码链接。
- `Overview` / `ModelList` 使用 `models` 展示模型数量和模型表格。
- `Guide` 使用 `readme` 渲染 MDX。
- `Related` 使用 `related` 渲染相关 Provider。
- `Sidebar` 虽然不在目标目录内，但由 `Details/index.tsx` 直接引入。根据读取到的片段，它会继续消费 `identifier`、`url`、`modelsUrl`、`models`、`name` 等字段，用于配置按钮、官网/模型站链接、分享信息等。

数据请求链路上，根据当前片段可以确认：

`ProviderDetailPage` -> `useDiscoverStore((s) => s.useProviderDetail)` -> `discoverService.getProviderDetail(params)`

`useProviderDetail` 使用 SWR，并把当前语言 `locale` 纳入 key：

```tsx
['provider-details', locale, params.identifier].filter(Boolean).join('-')
```

根据当前片段推断，`discoverService.getProviderDetail` 下游会走 `lambdaClient.market` 相关 TRPC 接口；依据是 `src/services/discover.ts` 中同类 `getAssistantDetail` 使用了 `lambdaClient.market.getAssistantDetail.query(...)`，而 Provider action 明确调用了 `discoverService.getProviderDetail(params)`。

## 运行/调用流程

1. 用户访问类似 `/community/provider/openai` 的路由。
2. Provider 详情页入口从路由参数中拿到 `slug`，解码为 `identifier`。
3. 页面通过 `useProviderDetail({ identifier, withReadme: true })` 请求详情数据。
4. 请求期间显示 `loading.tsx` 导出的详情 loading。
5. 如果没有返回数据，显示 `NotFound`。
6. 如果有数据，页面把数据放进 `DetailProvider config={data}`。
7. `Header` 和 `Details` 都在同一个 Provider 详情上下文中读取数据。
8. `Details` 初始化 `activeTab`：
   - URL 没有 `activeTab` 时，默认是 `overview`。
   - 用户切换 tab 时，`Nav` 调用 `setActiveTab`，URL query 同步更新。
9. `Details` 根据当前 tab 渲染对应子组件：
   - Overview：展示支持模型总数和模型表格。
   - Guide：展示 `readme`，没有则展示空态。
   - Related：展示相关 Provider 列表。
10. 桌面端同时展示右侧 `Sidebar`；移动端调整布局顺序。

## 小白阅读顺序

1. 先看 `src/routes/(main)/community/(detail)/provider/index.tsx`  
   这是页面入口，能理解数据从哪里来、loading/not found 怎么处理、`DetailProvider` 如何包住 `Details`。

2. 再看 `features/DetailProvider.tsx`  
   这个文件很短，但非常关键。理解它之后，就知道为什么 `Details` 子组件都不传 props，却能读到 `models`、`readme`、`related`、`identifier`。

3. 再看 `features/Details/index.tsx`  
   重点看 `useQueryState('activeTab')`、`ProviderNavKey` 和三个条件渲染。这里是整个目录的主控逻辑。

4. 再看 `features/Details/Nav.tsx`  
   理解 tab 项怎么生成、移动端和桌面端差异、为什么 `BRANDING_PROVIDER` 会隐藏 Guide。

5. 再看 `Overview/index.tsx` 和 `Overview/ModelList/index.tsx`  
   `Overview/index.tsx` 很薄，真正的信息密度在 `ModelList`：模型字段、排序、价格、跳转都在这里。

6. 最后看 `Guide/index.tsx` 和 `Related/index.tsx`  
   这两个组件逻辑单纯，分别对应 Markdown 渲染和相关列表复用。

## 常见误区

1. 不要把 `Details` 理解成数据请求组件。  
   它没有直接调 API。数据请求发生在 Provider 详情页入口，`Details` 只是消费 `DetailProvider` 的上下文。

2. `activeTab` 不是普通 React state。  
   它通过 `useQueryState` 绑定到 URL query。切换 tab 会影响 URL，刷新或分享链接时也可能保留当前 tab。

3. `mobile` 的来源有两层。  
   `Details` 接收上层传入的 `mobile`，同时调用 `useResponsive()`。代码里：

   ```tsx
   const { mobile = isMobile } = useResponsive();
   ```

   这表示响应式 hook 的结果优先；如果 hook 没给出值，则回退到 props 传入的 `mobile`。

4. `Guide` tab 可能不存在。  
   对 `BRANDING_PROVIDER`，`Nav` 会隐藏 Guide tab。但 `Details/index.tsx` 仍然保留了 `activeTab === ProviderNavKey.Guide && <Guide />` 的渲染条件。也就是说，隐藏入口不等于完全删除渲染能力；如果 URL 强行带上 Guide tab，根据当前片段推断仍可能进入 Guide 内容判断。

5. `Overview` 的模型数量来自 `models.length`，不是单独统计接口。  
   如果上游 `DiscoverProviderDetail` 的 `models` 为空或缺失，标题数量会显示 `0`，表格也会是空数据。

6. `ModelList` 中价格不是直接读 `inputPrice` / `outputPrice` 字段。  
   虽然列名叫 `inputPrice`、`outputPrice`，但实际渲染和排序都从 `record.pricing` 通过 `getTextInputUnitRate`、`getTextOutputUnitRate` 计算。

7. `Related` 复用了 Provider 列表页组件。  
   它不是自己实现卡片列表，而是 import `../../../../../(list)/provider/features/List`。阅读样式或卡片行为时，需要跳到 Provider list 功能目录继续看。

8. 目标目录虽然位于 `src/routes/.../features`，但不是理想的“薄 route”形态。  
   仓库规范提到新 SPA route 通常应让 `src/routes` 只保留页面段，业务 UI 放到 `src/features`。这个目录属于已有实现：Provider 详情页的业务组件仍放在 route 局部 `features` 下面。阅读时应尊重现状，不要误以为所有新代码都应该继续放在这里。
