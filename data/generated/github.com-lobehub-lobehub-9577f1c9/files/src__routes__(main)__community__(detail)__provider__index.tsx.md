# 文件：src/routes/(main)/community/(detail)/provider/index.tsx

## 它负责什么

`src/routes/(main)/community/(detail)/provider/index.tsx` 是社区发现页里 “Provider 详情页” 的路由入口组件，对应 URL 形态：

```text
/community/provider/:slug
```

它的职责很集中：

1. 从 React Router 的 URL 参数里读取 `slug`。
2. 将 `slug` 解码成 provider 的 `identifier`。
3. 通过 `useDiscoverStore` 中的 `useProviderDetail` 拉取 provider 详情数据。
4. 根据加载状态渲染 `Loading`、`NotFound` 或真正的详情页内容。
5. 把详情数据放入 `DetailProvider` 上下文，让下层 `Header`、`Details`、`Sidebar` 等组件共享读取。
6. 同时导出一个移动端包装组件 `MobileProviderPage`，供移动端路由配置使用。

这个文件本身不实现复杂 UI，也不直接处理 provider 的业务展示细节。它更像一个“页面装配器”：负责把路由参数、数据请求、页面状态和详情页组件串起来。

从 `spa-routes` 约定看，`src/routes/` 下的文件理想上应是 thin route，即只做页面入口和组件组合。这个文件符合这个方向：核心展示逻辑都放在同目录 `features/` 下。

## 关键组成

文件顶部声明：

```tsx
'use client';
```

这说明它是客户端组件。因为它使用了 `useParams`、zustand store hook、SWR 数据请求以及 React 客户端状态，所以必须运行在浏览器侧。

主要 import 可以分为几类。

第一类是基础 UI 和 React 能力：

```tsx
import { Flexbox } from '@lobehub/ui';
import { memo } from 'react';
import { useParams } from 'react-router-dom';
```

`Flexbox` 用来做详情页内容的纵向布局；`memo` 用于减少无必要重渲染；`useParams` 从当前 SPA 路由中读取 `:slug`。

第二类是数据来源：

```tsx
import { useDiscoverStore } from '@/store/discover';
```

这里不是直接调用 service，而是从 discover store 中取出 `useProviderDetail`。根据相邻上下文，`useProviderDetail` 定义在：

```text
src/store/discover/slices/provider/action.ts
```

它内部使用 `useSWR`，再调用：

```ts
discoverService.getProviderDetail(params)
```

也就是说，本文件只知道“我要 provider 详情”，不关心 HTTP 请求、缓存 key、服务层实现细节。

第三类是页面状态和页面片段：

```tsx
import NotFound from '../components/NotFound';
import { DetailProvider } from './features/DetailProvider';
import Details from './features/Details';
import Header from './features/Header';
import Loading from './loading';
```

这些都是详情页本地或邻近组件：

- `NotFound`：通用详情页未找到状态，位于 `community/(detail)/components/NotFound`。
- `DetailProvider`：provider 详情页上下文提供者。
- `Header`：provider 详情页头部，展示 provider 图标、名称、官网/GitHub 链接、描述等。
- `Details`：详情主体，包含 tab 导航、Overview、Guide、Related 和 Sidebar。
- `Loading`：加载态，实际从 `../../components/ListLoading` 导出 `DetailsLoading`。

核心组件是：

```tsx
const ProviderDetailPage = memo<ProviderDetailPageProps>(({ mobile }) => {
  const params = useParams<{ slug: string }>();
  const identifier = decodeURIComponent(params.slug ?? '');

  const useProviderDetail = useDiscoverStore((s) => s.useProviderDetail);
  const { data, isLoading } = useProviderDetail({ identifier, withReadme: true });

  if (isLoading) return <Loading />;
  if (!data) return <NotFound />;

  return (
    <DetailProvider config={data}>
      <Flexbox gap={16}>
        <Header mobile={mobile} />
        <Details mobile={mobile} />
      </Flexbox>
    </DetailProvider>
  );
});
```

这里有几个关键点。

`params.slug ?? ''` 保证即使 URL 中没有 `slug`，也不会直接传 `undefined` 给 `decodeURIComponent`。不过如果没有 slug，最终 `identifier` 会是空字符串，然后数据请求大概率拿不到结果，页面会进入 `NotFound`。

`decodeURIComponent` 用来处理 URL 编码后的 provider 标识。例如某些 slug 里如果包含特殊字符，路由里可能是编码形式，进入数据查询前需要还原。

`withReadme: true` 表明这个详情页需要带 README 或文档内容的数据。根据当前片段推断，这主要服务于 `Details/Guide` 或详情正文渲染，因为 provider 详情页有 Guide tab。

加载分支很简单：

```tsx
if (isLoading) return <Loading />;
if (!data) return <NotFound />;
```

所以页面状态有三种：

1. 正在请求：显示 loading。
2. 请求结束但没有数据：显示 not found。
3. 有数据：进入详情页上下文并渲染内容。

`DetailProvider config={data}` 是下游组件读取数据的关键。它在 `features/DetailProvider.tsx` 中创建 React context：

```tsx
export const DetailContext = createContext<DetailContextConfig>({});
```

并提供：

```tsx
export const useDetailContext = () => {
  return use(DetailContext);
};
```

因此 `Header`、`Details`、`Sidebar` 等子组件不需要一层层传 props，只要调用 `useDetailContext()` 就能拿到当前 provider 的 `identifier`、`name`、`url`、`models` 等数据。

文件最后还导出移动端页面：

```tsx
export const MobileProviderPage = memo<{ mobile?: boolean }>(() => {
  return <ProviderDetailPage mobile={true} />;
});
```

这个组件固定给 `ProviderDetailPage` 传入 `mobile={true}`。移动端路由配置会 import 这个 named export，而桌面端使用默认导出的 `ProviderDetailPage`。

## 上下游关系

上游主要来自 SPA 路由配置。

桌面动态路由配置中，`provider/:slug` 指向这个文件：

```text
src/spa/router/desktopRouter.config.tsx
```

对应片段是：

```tsx
{
  element: dynamicElement(
    () => import('@/routes/(main)/community/(detail)/provider'),
    'Desktop > Discover > Detail > Provider',
  ),
  path: 'provider/:slug',
}
```

桌面同步路由配置中也有同样路径：

```text
src/spa/router/desktopRouter.config.desktop.tsx
```

它静态 import：

```tsx
import CommunityDetailProviderPage from '@/routes/(main)/community/(detail)/provider';
```

然后配置：

```tsx
{
  element: <CommunityDetailProviderPage />,
  path: 'provider/:slug',
}
```

移动端路由配置中使用的是 named export：

```text
src/spa/router/mobileRouter.config.tsx
```

对应逻辑是：

```tsx
import('@/routes/(main)/community/(detail)/provider').then(
  (m) => m.MobileProviderPage,
)
```

所以这个文件同时服务桌面端和移动端，只是移动端通过 `MobileProviderPage` 强制开启 mobile 布局。

另一个重要上游是列表页。provider 列表项会构造详情页链接：

```text
src/routes/(main)/community/(list)/provider/features/List/Item.tsx
```

根据搜索结果，它会生成类似：

```tsx
urlJoin('/community/provider', identifier)
```

这意味着用户从 provider 列表点击某个 provider 后，就会进入当前文件对应的详情页。这里的 `identifier` 会成为 URL 中的 `:slug`。

下游主要有三层。

第一层是数据层：

```text
src/store/discover/slices/provider/action.ts
```

`ProviderDetailPage` 调用：

```tsx
const useProviderDetail = useDiscoverStore((s) => s.useProviderDetail);
const { data, isLoading } = useProviderDetail({ identifier, withReadme: true });
```

而 `useProviderDetail` 内部大致是：

```ts
const locale = globalHelpers.getCurrentLanguage();

return useSWR(
  ['provider-details', locale, params.identifier].filter(Boolean).join('-'),
  async () => discoverService.getProviderDetail(params),
  {
    revalidateOnFocus: false,
  },
);
```

这说明 provider 详情数据会按当前语言和 provider identifier 做 SWR 缓存。`revalidateOnFocus: false` 表示窗口重新聚焦时不会自动刷新。

第二层是上下文层：

```text
src/routes/(main)/community/(detail)/provider/features/DetailProvider.tsx
```

它把 `DiscoverProviderDetail` 的局部数据放进 React context。下游组件通过 `useDetailContext()` 读取，不需要每个组件都接收大量 props。

第三层是 UI 展示层：

```text
src/routes/(main)/community/(detail)/provider/features/Header.tsx
src/routes/(main)/community/(detail)/provider/features/Details/index.tsx
src/routes/(main)/community/(detail)/provider/features/Sidebar/index.tsx
src/routes/(main)/community/(detail)/provider/features/Details/Overview/index.tsx
src/routes/(main)/community/(detail)/provider/features/Details/Guide/index.tsx
src/routes/(main)/community/(detail)/provider/features/Details/Related/index.tsx
```

`Header` 展示 provider 的顶部信息，例如：

- `ProviderCombine` 图标。
- `@{name}` 名称。
- 官网或模型页链接。
- GitHub locales 目录链接。
- provider 描述文案。

`Details` 管理详情内容区。它通过 query 参数 `activeTab` 控制当前 tab：

```tsx
const [activeTab, setActiveTab] = useQueryState('activeTab', {
  clearOnDefault: true,
  defaultValue: ProviderNavKey.Overview,
});
```

它会在三个 tab 间切换：

- `ProviderNavKey.Overview`
- `ProviderNavKey.Guide`
- `ProviderNavKey.Related`

`Nav` 里还有一个特殊判断：

```tsx
const showGuideTab = identifier !== BRANDING_PROVIDER;
```

也就是说，如果当前 provider 是 `BRANDING_PROVIDER`，Guide tab 会被隐藏。注释说明原因是 branding provider 没有集成文档。

## 运行/调用流程

完整流程可以按一次用户访问 `/community/provider/openai` 来理解。

第一步，React Router 匹配路由。

SPA 路由配置里有：

```text
community -> provider/:slug
```

当路径是：

```text
/community/provider/openai
```

时，`:slug` 的值就是：

```text
openai
```

桌面端会加载默认导出的 `ProviderDetailPage`；移动端会加载 `MobileProviderPage`，再由它渲染：

```tsx
<ProviderDetailPage mobile={true} />
```

第二步，页面组件读取并解码路由参数。

```tsx
const params = useParams<{ slug: string }>();
const identifier = decodeURIComponent(params.slug ?? '');
```

如果 URL 里是普通字符串，`identifier` 和 `slug` 基本相同。如果 URL 中有被编码的字符，则会被还原。

第三步，页面通过 discover store 发起数据请求。

```tsx
const useProviderDetail = useDiscoverStore((s) => s.useProviderDetail);
const { data, isLoading } = useProviderDetail({ identifier, withReadme: true });
```

`useProviderDetail` 使用 SWR。它的缓存 key 包含：

- 固定前缀：`provider-details`
- 当前语言：`locale`
- 当前 provider：`params.identifier`

然后调用：

```ts
discoverService.getProviderDetail(params)
```

根据当前片段推断，`discoverService` 是真正访问后端或静态 discover 数据服务的客户端 service。依据是 store action 中只负责 SWR 包装，实际详情获取委托给了 `discoverService.getProviderDetail`。

第四步，根据请求状态分支渲染。

如果 `isLoading` 为 true：

```tsx
return <Loading />;
```

这里显示详情页加载骨架或加载占位。

如果请求完成但 `data` 为空：

```tsx
return <NotFound />;
```

说明当前 `identifier` 没有对应 provider 详情。

如果有数据，页面进入正常展示：

```tsx
return (
  <DetailProvider config={data}>
    <Flexbox gap={16}>
      <Header mobile={mobile} />
      <Details mobile={mobile} />
    </Flexbox>
  </DetailProvider>
);
```

第五步，详情数据通过 context 向下传递。

`DetailProvider` 将 `data` 放进 `DetailContext`。之后 `Header`、`Details/Nav`、`Sidebar`、`Overview`、`Guide`、`Related` 等组件都可以调用：

```tsx
useDetailContext()
```

读取当前 provider 的信息。

第六步，详情主体根据 tab 展示内容。

`Details` 默认展示 Overview：

```tsx
defaultValue: ProviderNavKey.Overview
```

如果用户切换 tab，会更新 URL query 中的 `activeTab`。这使 tab 状态可以体现在 URL 中，便于刷新或分享时保留当前页签。

主体内容区会根据 `activeTab` 渲染：

```tsx
{activeTab === ProviderNavKey.Overview && <Overview />}
{activeTab === ProviderNavKey.Guide && <Guide />}
{activeTab === ProviderNavKey.Related && <Related />}
```

旁边还会渲染：

```tsx
<Sidebar mobile={mobile} />
```

移动端和桌面端布局不同。`Details` 会结合 `mobile` prop 和 `useResponsive()` 决定是否横向排列，以及移动端是否反转主内容和侧栏顺序。

## 小白阅读顺序

建议按下面顺序读，不要一开始就钻进所有 feature 子组件。

第一步，先读当前文件：

```text
src/routes/(main)/community/(detail)/provider/index.tsx
```

重点看四件事：

1. `useParams` 怎么拿到 `slug`。
2. `identifier` 怎么从 `slug` 得到。
3. `useProviderDetail` 怎么触发数据请求。
4. `Loading`、`NotFound`、正常详情页三种状态怎么分支。

读完这个文件，你就知道 provider 详情页的页面入口是怎么工作的。

第二步，读数据 hook：

```text
src/store/discover/slices/provider/action.ts
```

重点看：

```ts
useProviderDetail
```

它会告诉你这个页面不是自己发请求，而是通过 discover store + SWR + discover service 获取详情数据。

需要注意的是，`useProviderDetail` 虽然名字像普通函数，但它内部调用了 `useSWR`，所以本质上是一个 hook 风格的方法。当前文件把它从 zustand store 里取出来，然后在组件渲染期间调用。

第三步，读上下文提供者：

```text
src/routes/(main)/community/(detail)/provider/features/DetailProvider.tsx
```

重点理解：

```tsx
<DetailProvider config={data}>
```

和：

```tsx
useDetailContext()
```

它们解释了为什么 `Header`、`Sidebar`、`Overview` 这些组件没有从 `ProviderDetailPage` 接收大量 props，却仍然能访问 provider 详情数据。

第四步，读头部组件：

```text
src/routes/(main)/community/(detail)/provider/features/Header.tsx
```

这个文件比较直观，适合用来理解 `useDetailContext()` 的实际用法。你会看到它读取：

```tsx
const { identifier, url, modelsUrl, name } = useDetailContext();
```

然后渲染 provider 图标、名称、外链和描述。

第五步，读详情主体：

```text
src/routes/(main)/community/(detail)/provider/features/Details/index.tsx
```

重点看 `activeTab`。它说明 provider 详情页不是一个静态页面，而是分成多个 tab：

- Overview
- Guide
- Related

第六步，再读 tab 导航：

```text
src/routes/(main)/community/(detail)/provider/features/Details/Nav.tsx
```

重点看 `ProviderNavKey` 和 `BRANDING_PROVIDER`。这里会解释为什么某些 provider 没有 Guide tab。

第七步，最后按兴趣读具体内容组件：

```text
src/routes/(main)/community/(detail)/provider/features/Details/Overview/index.tsx
src/routes/(main)/community/(detail)/provider/features/Details/Guide/index.tsx
src/routes/(main)/community/(detail)/provider/features/Details/Related/index.tsx
src/routes/(main)/community/(detail)/provider/features/Sidebar/index.tsx
```

这些才是真正的业务展示细节。初学时不建议一开始就深入这里，否则容易被 UI 细节分散注意力。

## 常见误区

第一个误区：以为 `slug` 就是直接可用的 provider id。

当前文件做了：

```tsx
const identifier = decodeURIComponent(params.slug ?? '');
```

这说明 URL 里的 `slug` 可能是编码后的字符串。真正用于查询的是解码后的 `identifier`。如果在别处构造详情页链接，也要注意 URL 编码和解码的一致性。

第二个误区：以为这个页面直接请求后端。

当前文件没有直接 import API client，也没有直接调用 fetch。它通过：

```tsx
useDiscoverStore((s) => s.useProviderDetail)
```

拿到 store action，再由 action 使用 `useSWR` 和 `discoverService.getProviderDetail`。所以排查数据问题时，不要只看 `index.tsx`，还要继续看：

```text
src/store/discover/slices/provider/action.ts
src/services/discover
```

第三个误区：以为 `DetailProvider` 是全局 provider。

这里的 `DetailProvider` 只是 provider 详情页局部的 React context，路径在：

```text
src/routes/(main)/community/(detail)/provider/features/DetailProvider.tsx
```

它不是应用级 provider，也不是设置页 provider。它只服务当前 provider 详情页下方的组件树。

第四个误区：以为 `mobile` 是由当前文件自动判断出来的。

当前文件的默认导出 `ProviderDetailPage` 只是接收一个可选 prop：

```tsx
interface ProviderDetailPageProps {
  mobile?: boolean;
}
```

桌面端通常不传；移动端路由使用：

```tsx
<ProviderDetailPage mobile={true} />
```

真正的响应式判断还会在子组件中结合 `useResponsive()`。所以 `mobile` 在这里更像是路由层传入的布局提示，而不是唯一的屏幕判断来源。

第五个误区：以为没有数据时一定是接口报错。

当前文件只判断：

```tsx
if (!data) return <NotFound />;
```

从这个页面看，`data` 为空就显示 `NotFound`。但 `data` 为空的原因可能有多种：identifier 不存在、service 返回 undefined、请求失败后没有有效数据等。要确认真实原因，需要继续看 `useSWR` 的 `error` 是否被处理、`discoverService.getProviderDetail` 的实现，以及上层错误边界。

第六个误区：以为所有 provider 都有 Guide tab。

`Nav.tsx` 中有明确判断：

```tsx
const showGuideTab = identifier !== BRANDING_PROVIDER;
```

branding provider 不展示 Guide tab，因为它没有集成文档。看到某个 provider 没有 Guide，不一定是 bug，可能是业务规则。

第七个误区：把当前文件当成主要 UI 实现文件。

这个文件只有页面入口逻辑。真正 UI 分散在：

```text
src/routes/(main)/community/(detail)/provider/features/Header.tsx
src/routes/(main)/community/(detail)/provider/features/Details/
src/routes/(main)/community/(detail)/provider/features/Sidebar/
```

如果要修改详情页样式或具体字段展示，大概率不应该改当前 `index.tsx`，而应该去对应 feature 组件中改。

第八个误区：忘记这个文件同时被桌面端和移动端复用。

默认导出服务桌面端，`MobileProviderPage` 服务移动端。改动当前文件会同时影响两端 provider 详情页。尤其是数据请求、NotFound 判断、`DetailProvider` 包裹范围这些基础逻辑，影响范围不只一个视图。
