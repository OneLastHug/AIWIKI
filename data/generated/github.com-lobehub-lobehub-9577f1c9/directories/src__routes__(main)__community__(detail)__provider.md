# 目录：src/routes/(main)/community/(detail)/provider

## 它负责什么

`src/routes/(main)/community/(detail)/provider` 是社区发现页里“模型服务商详情页”的 SPA 路由段，对应路径主要是：

- 桌面端：`/community/provider/:slug`
- 移动端：同一路由模块导出 `MobileProviderPage`，由 mobile router 复用到 `/community/provider/:slug`

这里的“provider”指模型服务商，例如 OpenAI、Anthropic、Google、LobeHub 等。这个目录负责在用户进入某个 provider 详情页时，根据 URL 中的 `slug` 拉取服务商详情数据，然后展示：

- provider 标识、名称、官网、源码链接
- provider 描述文案
- 支持的模型列表
- 集成/配置指南 README
- 相关 provider
- 右侧操作区：配置 provider、分享、相关模型、相关 provider

从代码形态看，它仍然是一个“旧式 route 内含 features”的目录。根据当前仓库的 `spa-routes` 约定，理想结构是 `src/routes/` 只放薄路由入口，复杂 UI 和业务逻辑迁到 `src/features/`。但当前这个目录内的 `features/` 仍然承载了大量页面实现，属于渐进迁移前的既有结构。

## 关键组成

### `index.tsx`

这是目录的核心入口文件。

它是一个 client component，主要做四件事：

1. 通过 `useParams<{ slug: string }>()` 从 React Router 读取 URL 参数。
2. 使用 `decodeURIComponent(params.slug ?? '')` 得到 provider 的 `identifier`。
3. 从 `useDiscoverStore` 取出 `useProviderDetail`，调用：

```ts
useProviderDetail({ identifier, withReadme: true })
```

其中 `withReadme: true` 表示详情数据需要包含 README/指南内容，供后面的 Guide tab 渲染。

4. 根据状态分支渲染：

- `isLoading` 为 true：返回 `Loading`
- `data` 不存在：返回上级 detail 公共组件 `NotFound`
- 有数据：用 `DetailProvider` 包住页面内容，内部渲染 `Header` 和 `Details`

核心结构大致是：

```tsx
<DetailProvider config={data}>
  <Flexbox gap={16}>
    <Header mobile={mobile} />
    <Details mobile={mobile} />
  </Flexbox>
</DetailProvider>
```

该文件还导出：

```ts
export const MobileProviderPage = memo(() => {
  return <ProviderDetailPage mobile={true} />;
});
```

移动端并没有单独实现一套 provider 详情页，而是复用同一个组件，通过 `mobile={true}` 调整布局。

### `loading.tsx`

这个文件非常薄：

```ts
export { DetailsLoading as default } from '../../components/ListLoading';
```

它复用 detail 公共 loading 组件 `DetailsLoading`，用于数据加载阶段。这里没有 provider 专属 skeleton，说明 provider、model、agent 等 detail 页可能共享类似加载态。

### `features/DetailProvider.tsx`

这是本目录内部的详情上下文。

它定义：

- `DetailContextConfig = Partial<DiscoverProviderDetail>`
- `DetailContext = createContext<DetailContextConfig>({})`
- `DetailProvider`
- `useDetailContext`

`index.tsx` 拉到的 provider detail 数据会作为 `config` 放进 `DetailContext`。之后 `Header`、`Details`、`Sidebar`、`ModelList`、`Guide` 等组件都通过 `useDetailContext()` 读取同一份详情数据。

这种写法避免了逐层传递 `identifier`、`models`、`readme`、`related`、`url`、`modelsUrl` 等字段。

需要注意的是，这里的 context 类型是 `Partial<DiscoverProviderDetail>`，所以子组件通常会写默认值，例如：

```ts
const { models = [] } = useDetailContext();
```

这意味着组件要容忍字段缺失。

### `features/Header.tsx`

`Header` 渲染 provider 详情页顶部信息。

它读取：

```ts
const { identifier, url, modelsUrl, name } = useDetailContext();
```

主要展示：

- provider 图标：`ProviderCombine`
- provider 名称：`@{name}`
- 官网/模型站点跳转图标：`GlobeIcon`
- GitHub 源码跳转图标：`Github`
- provider 描述：`t(`${identifier}.description`)`

这里使用了两个 i18n namespace：

- `providers`：用于 provider 描述文案
- 文案 key 由 provider identifier 动态拼接，例如 `openai.description`

GitHub 链接指向：

```txt
[URL已移除]}
```

根据当前片段推断，这个链接可能用于查看 provider 相关的社区配置或本地化资源，因为它拼到的是 `lobe-chat-agents` 仓库的 `locales/{identifier}` 路径。

### `features/Details/index.tsx`

这是详情主体区域的布局控制组件。

它维护当前 tab：

```ts
const [activeTab, setActiveTab] = useQueryState('activeTab', {
  clearOnDefault: true,
  defaultValue: ProviderNavKey.Overview,
});
```

也就是说 tab 状态写在 URL query 里，例如：

```txt
/community/provider/openai?activeTab=guide
```

默认 tab 是 `ProviderNavKey.Overview`，默认值会被清理，不强制留在 URL 上。

它渲染三个主要区域：

- `Nav`：顶部 tab 导航
- 左侧/主区域内容：`Overview`、`Guide`、`Related`
- `Sidebar`：右侧操作栏

移动端布局会调整：

```ts
style={mobile ? { flexDirection: 'column-reverse' } : undefined}
```

也就是说移动端会把侧栏操作区和主体内容做上下顺序调整。

### `features/Details/Nav.tsx`

`Nav` 定义 provider 详情页的 tab：

- `Overview`：概览
- `Guide`：接入指南
- `Related`：相关服务商

它使用 `ProviderNavKey` 作为 tab key。

一个特殊逻辑是：

```ts
const showGuideTab = identifier !== BRANDING_PROVIDER;
```

如果当前 provider 是 `BRANDING_PROVIDER`，就隐藏 Guide tab。注释说明原因是 branding provider 没有集成文档。

桌面端的 `Nav` 除了 tab，还显示右侧外链：

- Discord 帮助入口：`SOCIAL_URL.discord`
- 查看源码：`src/config/modelProviders/{identifier}.ts`
- 反馈问题：GitHub issues new choose

移动端只渲染 tab 本身，不显示这些额外链接。

### `features/Details/Overview/index.tsx`

概览页展示当前 provider 支持的模型数量和模型列表。

它读取：

```ts
const { models = [] } = useDetailContext();
```

标题为：

```ts
t('providers.supportedModels')
```

右侧用 `Tag` 显示 `models.length`。

真正的表格由 `ModelList` 渲染。

### `features/Details/Overview/ModelList/index.tsx`

这是 provider 详情中最重要的数据展示组件之一。

它使用 `InlineTable` 展示 `models`，每一行是一个 provider 支持的模型。表格列包括：

- 模型名称和 ID
- 模型能力：`ModelInfoTags`
- 上下文长度：`contextWindowTokens`
- 最大输出：`maxOutput`
- 输入价格：`getTextInputUnitRate(record.pricing)`
- 输出价格：`getTextOutputUnitRate(record.pricing)`
- 跳转操作：链接到 `/community/model/{modelId}`

它还使用：

- `formatTokenNumber` 格式化 token 数字
- `formatPriceByCurrency` 格式化价格
- `ModelIcon` 展示模型图标
- `Tooltip` 解释价格/输出等字段

这里说明 provider 详情页并不只是展示 provider 自身信息，还承担了“从 provider 反查模型”的入口职责。

### `features/Details/Guide/index.tsx`

`Guide` 展示 provider 的 README/接入说明。

它读取：

```ts
const { readme = '' } = useDetailContext();
```

如果没有 `readme`，渲染一个 `Block + Empty` 空状态。

如果有 `readme`，用 `@lobehub/ui/mdx` 的 `Mdx` 组件渲染：

```tsx
<Mdx enableImageGallery={false} enableLatex={false} fontSize={14} headerMultiple={0.3}>
  {readme}
</Mdx>
```

这说明 `useProviderDetail({ withReadme: true })` 拉到的 readme 内容是 Markdown/MDX 风格文本，但这里关闭了图片画廊和 LaTeX。

### `features/Details/Related/index.tsx`

这个 Related 是主内容 tab 里的“相关 provider”列表。

它复用列表页的 provider List：

```ts
import List from '../../../../../(list)/provider/features/List';
```

然后把详情数据中的 `related` 传进去：

```tsx
<List data={related} rows={2} />
```

这体现了一个上游复用关系：详情页没有重新实现 provider 卡片列表，而是复用了 provider 列表页的列表组件。

### `features/Sidebar/index.tsx`

`Sidebar` 是桌面端右侧栏，移动端则简化为只显示操作按钮。

移动端：

```tsx
<Flexbox gap={32}>
  <ActionButton />
</Flexbox>
```

桌面端：

```tsx
<ScrollShadow width={360} position="sticky">
  <ActionButton />
  {activeTab !== ProviderNavKey.Related && <Related />}
  {activeTab !== ProviderNavKey.Overview && <RelatedModels />}
</ScrollShadow>
```

它通过 `useQuery()` 读取 URL query 中的 `activeTab`，根据当前 tab 避免重复展示内容：

- 如果主内容已经是 `Related` tab，侧栏就不再展示 `Related`
- 如果主内容已经是 `Overview` tab，侧栏就不再展示 `RelatedModels`

这种设计避免同一屏里主内容和侧栏展示重复模块。

### `features/Sidebar/ActionButton/index.tsx`

`ActionButton` 负责详情页右侧/移动端顶部的主要操作。

它包含：

- `ProviderConfig`
- `ShareButton`

`ShareButton` 的 meta 包括：

- provider avatar：`ProviderIcon`
- 描述：`t(`${identifier}.description`)`
- 标签：最多展示前 4 个模型的 `ModelTag`
- 标题：`name`
- 分享 URL：`OFFICIAL_URL/community/provider/{identifier}`

这里 `ShareButton` 来自上级 detail features：

```ts
import ShareButton from '../../../../features/ShareButton';
```

说明 agent/model/provider 等 detail 页可能共享同一个分享组件。

### `features/Sidebar/ActionButton/ProviderConfig.tsx`

这是“配置 provider”按钮。

它读取：

```ts
const { url, modelsUrl, identifier } = useDetailContext();
```

点击主按钮时：

- 如果是桌面端 `isDesktop`，动态导入 Electron IPC：

```ts
ensureElectronIpc().windows.openSettingsWindow({
  path: `/settings/provider/${identifier}`,
});
```

- 否则使用 `useNavigate()` 跳转：

```ts
navigate(`/settings/provider/${identifier}`);
```

如果 provider 有 `url` 或 `modelsUrl`，按钮会变成 `Dropdown.Button`，下拉项包括：

- 官方站点
- 模型站点

如果没有外链，则显示普通主按钮。

一个细节是：无外链分支目前只渲染了按钮文字，没有绑定 `onClick={openSettings}`。根据当前片段看，这可能意味着无外链 provider 的配置按钮不能打开设置页；也可能是外部样式或父级逻辑未在当前片段中体现。证据不足，只能根据当前文件推断。

## 上下游关系

### 上游：路由注册

该目录被三个 router 配置引用。

桌面动态路由：

```ts
path: 'provider/:slug'
element: dynamicElement(() => import('@/routes/(main)/community/(detail)/provider'))
```

桌面同步路由：

```tsx
import CommunityDetailProviderPage from '@/routes/(main)/community/(detail)/provider';

{
  element: <CommunityDetailProviderPage />,
  path: 'provider/:slug',
}
```

移动端路由：

```ts
import('@/routes/(main)/community/(detail)/provider').then((m) => m.MobileProviderPage)
```

因此这个目录既服务桌面端，也服务移动端。移动端没有从 `src/routes/(mobile)/community` 下重新实现 provider detail，而是复用 main 目录下的页面模块。

### 上游：列表页跳转

provider 列表项会跳到：

```ts
/community/provider/{identifier}
```

相关代码在 provider list item 中通过 `urlJoin('/community/provider', identifier)` 生成链接。

模型详情页也会链接到 provider 详情。例如模型详情的 provider list 中，每个 provider 会跳转到：

```ts
/community/provider/{providerId}
```

所以这个详情页的入口至少包括：

- 社区 provider 列表
- 模型详情页的 provider 列表
- 相关 provider 模块
- 直接访问 URL

### 数据上游：`useDiscoverStore`

`index.tsx` 从 `@/store/discover` 获取：

```ts
const useProviderDetail = useDiscoverStore((s) => s.useProviderDetail);
```

然后调用：

```ts
useProviderDetail({ identifier, withReadme: true })
```

根据当前片段推断，`useProviderDetail` 是一个封装过的数据获取 hook，可能内部使用 SWR 或服务层 API，返回 `{ data, isLoading }`。因为调用写法是 store selector 取 hook，再在组件内执行，所以它属于 LobeHub 常见的 Zustand + 数据 hook 混合模式。

### 下游：详情子组件

`DetailProvider` 是本目录的核心数据分发点。下游组件都依赖 `useDetailContext()`：

- `Header` 读取 `identifier`、`url`、`modelsUrl`、`name`
- `Nav` 读取 `identifier`
- `Overview` 和 `ModelList` 读取 `models`
- `Guide` 读取 `readme`
- `Related` 读取 `related`
- `Sidebar` 下的 `ActionButton`、`ProviderConfig`、`RelatedModels` 读取 provider detail 的多个字段

### 下游：外部页面跳转

该目录会跳转到几个外部或内部页面：

- `/community/model/{modelId}`：点击支持模型
- `/community/provider`：查看更多相关 provider
- `/community/model?category={identifier}`：查看更多相关模型
- `/settings/provider/{identifier}`：配置该 provider
- GitHub provider 源码：`src/config/modelProviders/{identifier}.ts`
- GitHub issue 页面
- Discord 帮助页面
- provider 官网或模型站点

## 运行/调用流程

1. 用户进入 `/community/provider/openai` 这样的 URL。
2. React Router 匹配 `provider/:slug`，加载 `src/routes/(main)/community/(detail)/provider/index.tsx`。
3. `ProviderDetailPage` 通过 `useParams` 取得 `slug`，并 `decodeURIComponent` 成 `identifier`。
4. 页面通过 `useDiscoverStore` 取得 `useProviderDetail`，用 `identifier` 和 `withReadme: true` 请求详情。
5. 请求期间显示 `loading.tsx` 导出的 `DetailsLoading`。
6. 如果没有返回数据，显示上级 detail 公共 `NotFound`。
7. 如果有数据，把 `data` 放入 `DetailProvider`。
8. `Header` 从 context 中读取 provider 基础信息，展示图标、名称、描述和外链。
9. `Details` 初始化 `activeTab`，默认是 `Overview`，并渲染 `Nav`。
10. 当 `activeTab=overview` 时，`Overview` 渲染支持模型表格。
11. 当 `activeTab=guide` 时，`Guide` 渲染 README/MDX 接入指南。
12. 当 `activeTab=related` 时，`Related` 渲染相关 provider 列表。
13. 桌面端同时渲染 `Sidebar`，展示配置、分享、相关模块；移动端只保留操作按钮区。
14. 用户点击配置按钮时，Web 端跳 `/settings/provider/{identifier}`，桌面端打开 Electron 设置窗口。

## 小白阅读顺序

1. 先读 `index.tsx`  
   重点看 URL 参数如何变成 `identifier`，以及 `useProviderDetail` 如何拿到页面数据。理解这个入口后，整个目录的数据来源就清楚了。

2. 再读 `features/DetailProvider.tsx`  
   这是全目录的数据中转站。理解它之后，就知道为什么很多子组件不接收 props，却能拿到 `models`、`readme`、`identifier`。

3. 接着读 `features/Header.tsx`  
   它最直观，能快速看到 provider detail 的基础展示：图标、名称、描述、官网、GitHub 链接。

4. 然后读 `features/Details/index.tsx` 和 `features/Details/Nav.tsx`  
   这两个文件解释了页面主体为什么有三个 tab，以及 tab 状态如何同步到 URL query。

5. 继续读 `features/Details/Overview/index.tsx` 和 `features/Details/Overview/ModelList/index.tsx`  
   这里是 provider 详情最核心的信息：支持哪些模型、模型能力、上下文长度、价格等。

6. 再读 `features/Details/Guide/index.tsx`  
   理解 `withReadme: true` 拉回来的 README 如何被渲染成文档。

7. 最后读 `features/Sidebar/index.tsx` 和 `features/Sidebar/ActionButton/ProviderConfig.tsx`  
   这里能看到详情页如何连接到设置页、分享能力、相关模型和相关 provider。

8. 如果还想理解入口来源，再去看 router 配置和列表页 Item  
   router 里看 `provider/:slug` 如何注册；列表页里看 `/community/provider/{identifier}` 如何生成。

## 常见误区

1. 误以为 `src/routes/` 里只有薄路由入口  
   按当前项目约定，新代码应尽量把业务 UI 放到 `src/features/`。但这个目录是既有实现，内部仍有 `features/` 子目录，并承载大量页面逻辑。阅读时不要把它当成最佳新代码模板。

2. 误以为移动端有独立 provider 详情实现  
   移动端复用的是同一个 `index.tsx`，只通过 `MobileProviderPage` 传入 `mobile={true}`。所以修改这个目录会同时影响桌面端和移动端。

3. 误以为 tab 状态只在 React state 里  
   `Details` 使用的是 `useQueryState('activeTab')`，tab 会体现在 URL query 中。调试相关问题时要同时看地址栏参数。

4. 误以为 `Guide` 一定有内容  
   `Guide` 依赖 detail 数据中的 `readme`。虽然入口请求传了 `withReadme: true`，但组件仍然处理了空 readme，并显示 Empty 状态。

5. 误以为 `Header` 的描述来自 detail API  
   `Header` 的描述文案是通过 i18n 动态 key 读取的：`providers:{identifier}.description`。如果描述不对，要查 locale/provider 文案，而不一定是 API 数据问题。

6. 误以为 `Sidebar` 总是显示完整内容  
   移动端 `Sidebar` 只显示 `ActionButton`。桌面端才显示 sticky 的滚动侧栏，并且会根据 `activeTab` 隐藏重复模块。

7. 误以为 provider 配置按钮总是普通站内跳转  
   在桌面端，它会通过 Electron IPC 打开设置窗口；Web 端才使用 `navigate('/settings/provider/{identifier}')`。这类逻辑修改时要同时考虑 Web 与 Electron。

8. 误以为相关模型和支持模型是同一个展示位置  
   `Overview` 里的 `ModelList` 是主内容的支持模型表格；`Sidebar/RelatedModels` 是侧栏中的相关模型简略列表，并会在 `Overview` tab 下隐藏，避免重复。

9. 误以为 `related` 自己实现卡片  
   主内容 `Details/Related` 复用了 provider 列表页的 `List` 组件。样式或行为问题可能来自列表页组件，而不是当前 detail 目录本身。
