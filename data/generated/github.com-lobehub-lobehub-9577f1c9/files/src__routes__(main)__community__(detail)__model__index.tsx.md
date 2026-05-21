# 文件：src/routes/(main)/community/(detail)/model/index.tsx

## 它负责什么

`src/routes/(main)/community/(detail)/model/index.tsx` 是社区发现页里“模型详情页”的 SPA 路由入口，负责把 URL 中的模型标识解析出来，拉取对应模型详情数据，并根据数据状态渲染加载页、404 页或详情内容。

它对应的路由形态是：

```txt
/community/model/:slug
```

在桌面端路由中，它作为 `Desktop > Discover > Detail > Model` 被注册；在移动端路由中，同一个文件导出的 `MobileModelPage` 会被注册为 `Mobile > Discover > Detail > Model`。

这个文件不是完整业务实现的集中地，而是一个“页面装配层”。它做三件事：

1. 从 `react-router-dom` 的 `useParams` 读取 `slug`。
2. 通过 `useDiscoverStore((s) => s.useModelDetail)` 获取模型详情请求 hook。
3. 把请求到的 `data` 注入 `DetailProvider`，再组合 `Header` 和 `Details` 展示页面主体。

从 `spa-routes` 约定看，`src/routes/` 下的文件理想状态应尽量薄，只负责路由页面入口和组合。这个文件虽然在路由目录内带有本地 `features/`，属于项目中仍在渐进迁移的旧结构，但整体职责仍然偏“入口装配”，核心数据展示逻辑被拆到了同目录的 `features` 子模块里。

## 关键组成

文件顶部声明：

```tsx
'use client';
```

说明这是客户端组件，需要在浏览器侧执行。原因很直接：它使用了 `useParams`、SWR 数据 hook、zustand store 和响应式组件组合，这些都依赖客户端运行时。

主要 imports 可以分成几类：

- UI 组件：`Flexbox` 来自 `@lobehub/ui`，用于纵向布局。
- React 能力：`memo` 用于记忆化组件，减少无意义重渲染。
- 路由参数：`useParams` 来自 `react-router-dom`。
- 数据来源：`useDiscoverStore` 来自 `@/store/discover`。
- 状态页面：`NotFound` 和 `Loading`。
- 本页详情模块：`DetailProvider`、`Details`、`Header`。

核心类型是：

```ts
interface ModelDetailPageProps {
  mobile?: boolean;
}
```

它只接收一个可选的 `mobile` 标记。这个标记会继续传给 `Header` 和 `Details`，让下游组件按移动端布局处理。

核心组件是 `ModelDetailPage`：

```tsx
const ModelDetailPage = memo<ModelDetailPageProps>(({ mobile }) => {
  const params = useParams<{ slug: string }>();
  const identifier = decodeURIComponent(params.slug ?? '');

  const useModelDetail = useDiscoverStore((s) => s.useModelDetail);
  const { data, isLoading } = useModelDetail({ identifier });

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

这里有几个关键点：

- `params.slug ?? ''`：当 URL 参数不存在时，兜底为空字符串。
- `decodeURIComponent(...)`：URL 中的模型名可能被编码，例如包含特殊字符，因此进入请求前先解码。
- `useModelDetail({ identifier })`：根据模型 identifier 拉取详情。
- `isLoading` 时直接返回 `Loading`。
- `data` 为空时返回 `NotFound`。
- 有数据时，用 `DetailProvider config={data}` 把模型详情放进 React Context，供 `Header`、`Details`、`Sidebar`、`Overview`、`Parameter`、`Related` 等子组件读取。

文件还导出移动端包装组件：

```tsx
export const MobileModelPage = memo<{ mobile?: boolean }>(() => {
  return <ModelDetailPage mobile={true} />;
});
```

注意它虽然声明了 `{ mobile?: boolean }` 类型，但实际不读取外部 props，而是固定传入 `mobile={true}`。这表示移动端路由使用同一个详情页实现，只是强制启用移动端展示模式。

默认导出是桌面/通用入口：

```ts
export default ModelDetailPage;
```

## 上下游关系

上游首先是 SPA 路由配置。

桌面动态路由配置里，模型详情页被挂在：

```txt
path: 'model/:slug'
element: import('@/routes/(main)/community/(detail)/model')
```

同步桌面路由配置 `desktopRouter.config.desktop.tsx` 中也有对应静态 import：

```ts
import CommunityDetailModelPage from '@/routes/(main)/community/(detail)/model';
```

移动端路由配置中，它不是使用默认导出，而是读取命名导出：

```ts
import('@/routes/(main)/community/(detail)/model').then((m) => m.MobileModelPage)
```

所以这个文件同时服务桌面端和移动端，只是移动端通过 `MobileModelPage` 固定传递 `mobile={true}`。

数据上游是 `useDiscoverStore` 中的 `useModelDetail`。该 hook 定义在 discover store 的 model slice 里，内部使用 `useSWR`：

```ts
useSWR(
  ['model-details', locale, params.identifier].filter(Boolean).join('-'),
  async () => discoverService.getModelDetail(params),
  {
    revalidateOnFocus: false,
  },
);
```

这里的 SWR key 包含：

- 固定前缀：`model-details`
- 当前语言：`locale`
- 模型标识：`params.identifier`

这意味着同一个模型在不同语言下会拥有不同缓存 key。`revalidateOnFocus: false` 表示窗口重新获得焦点时不会自动重新验证，避免详情页频繁刷新。

再往下游，`discoverService.getModelDetail` 会调用：

```ts
lambdaClient.market.getModelDetail.query({
  ...params,
  locale,
});
```

也就是说，页面本身不直接请求 HTTP API，而是通过：

```txt
ModelDetailPage
  -> useDiscoverStore
  -> useModelDetail
  -> discoverService.getModelDetail
  -> lambdaClient.market.getModelDetail.query
```

这一层层封装拿到市场模型详情。

组件下游关系如下：

```txt
ModelDetailPage
  ├─ Loading
  ├─ NotFound
  └─ DetailProvider config={data}
      └─ Flexbox
          ├─ Header
          └─ Details
              ├─ Nav
              ├─ Overview
              ├─ Parameter
              ├─ Related
              └─ Sidebar
                  ├─ ActionButton / ChatWithModel
                  ├─ Related
                  └─ RelatedProviders
```

`DetailProvider` 定义了：

```tsx
export const DetailContext = createContext<DetailContextConfig>({});
export const useDetailContext = () => use(DetailContext);
```

`DetailContextConfig` 是 `Partial<DiscoverModelDetail>`。因此下游组件读取字段时通常要能接受字段缺失的情况。比如 `Header` 从 context 中读取：

```ts
const { identifier, releasedAt, displayName, type, abilities, contextWindowTokens } =
  useDetailContext();
```

然后展示模型图标、名称、identifier、类型、能力标签、发布时间和描述。

`Header` 还会使用：

- `ModelIcon`：根据模型 identifier 渲染模型图标。
- `ModelInfoTags`：展示上下文窗口、能力等信息。
- `PublishedTime`：展示发布时间。
- `ModelTypeIcon`：展示模型类型图标。
- `useTranslation('models')`：读取模型描述文案，key 形式是 `${identifier}.description`。

这说明模型详情数据并不完全来自接口，描述文本至少有一部分来自 `models` i18n namespace。

## 运行/调用流程

一次典型访问流程如下：

1. 用户进入模型详情 URL，例如：

   ```txt
   /community/model/openai%2Fgpt-4.1
   ```

2. React Router 匹配到 `model/:slug`，加载 `src/routes/(main)/community/(detail)/model/index.tsx`。

3. `ModelDetailPage` 执行：

   ```ts
   const params = useParams<{ slug: string }>();
   ```

   取得：

   ```ts
   params.slug
   ```

4. 页面把 `slug` 解码成真实 identifier：

   ```ts
   const identifier = decodeURIComponent(params.slug ?? '');
   ```

   如果 URL 中是 `openai%2Fgpt-4.1`，解码后会变成类似：

   ```txt
   openai/gpt-4.1
   ```

5. 从 discover store 中取出请求 hook：

   ```ts
   const useModelDetail = useDiscoverStore((s) => s.useModelDetail);
   ```

6. 调用 hook 发起或复用 SWR 请求：

   ```ts
   const { data, isLoading } = useModelDetail({ identifier });
   ```

7. 如果请求中：

   ```tsx
   return <Loading />;
   ```

   这里的 `Loading` 实际从 `loading.tsx` 导出，而 `loading.tsx` 又复用：

   ```ts
   export { DetailsLoading as default } from '../../components/ListLoading';
   ```

8. 如果请求结束但没有数据：

   ```tsx
   return <NotFound />;
   ```

   这通常表示 identifier 无效、市场接口没有返回对应模型，或数据不可用。

9. 如果拿到数据：

   ```tsx
   <DetailProvider config={data}>
     <Flexbox gap={16}>
       <Header mobile={mobile} />
       <Details mobile={mobile} />
     </Flexbox>
   </DetailProvider>
   ```

10. `DetailProvider` 把 `data` 放进 `DetailContext`。

11. `Header` 调用 `useDetailContext()` 读取模型基础信息并渲染头部。

12. `Details` 读取查询参数 `activeTab`：

    ```ts
    const [activeTab, setActiveTab] = useQueryState('activeTab', {
      clearOnDefault: true,
      defaultValue: ModelNavKey.Overview,
    });
    ```

    默认展示 `Overview`，也可以切换到：

    - `ModelNavKey.Overview`
    - `ModelNavKey.Parameter`
    - `ModelNavKey.Related`

13. `Details` 根据当前 tab 渲染对应内容：

    ```tsx
    {activeTab === ModelNavKey.Overview && <Overview />}
    {activeTab === ModelNavKey.Parameter && <Parameter />}
    {activeTab === ModelNavKey.Related && <Related />}
    ```

14. 同时渲染 `Sidebar`，展示操作按钮、相关内容、相关 providers 等侧边信息。

15. 如果是移动端入口 `MobileModelPage`，流程基本相同，只是 `mobile` 固定为 `true`，`Header` 和 `Details` 会按移动端布局处理。

## 小白阅读顺序

建议按“入口到数据，再到展示”的顺序阅读。

第一步，先读当前文件：

```txt
src/routes/(main)/community/(detail)/model/index.tsx
```

重点理解四个分支：

```tsx
if (isLoading) return <Loading />;
if (!data) return <NotFound />;
return <DetailProvider config={data}>...</DetailProvider>;
```

这就是页面的状态机：加载中、无数据、有数据。

第二步，读 provider：

```txt
src/routes/(main)/community/(detail)/model/features/DetailProvider.tsx
```

这里会明白为什么 `Header`、`Details`、`Sidebar` 不需要层层传 `data` props，而是通过 `useDetailContext()` 直接拿模型详情。

第三步，读头部：

```txt
src/routes/(main)/community/(detail)/model/features/Header.tsx
```

它最容易建立直观认识：模型图标、显示名、identifier、类型、能力、发布时间、描述文案都在这里。

第四步，读详情主体入口：

```txt
src/routes/(main)/community/(detail)/model/features/Details/index.tsx
```

重点看 `activeTab` 如何控制 `Overview`、`Parameter`、`Related` 三块内容，以及 `Sidebar` 在桌面和移动端布局上的差异。

第五步，按需展开：

```txt
src/routes/(main)/community/(detail)/model/features/Details/Nav.tsx
src/routes/(main)/community/(detail)/model/features/Details/Overview/index.tsx
src/routes/(main)/community/(detail)/model/features/Details/Parameter/index.tsx
src/routes/(main)/community/(detail)/model/features/Details/Related/index.tsx
src/routes/(main)/community/(detail)/model/features/Sidebar/index.tsx
```

这些文件负责具体展示内容。阅读时可以先不用纠结每个 UI 细节，先确认它们从 `DetailContext` 里拿了哪些字段。

第六步，看数据来源：

```txt
src/store/discover/slices/model/action.ts
src/services/discover.ts
```

这里能看到 `useModelDetail` 使用 SWR，并最终通过 `lambdaClient.market.getModelDetail.query` 请求市场详情数据。

第七步，看路由注册：

```txt
src/spa/router/desktopRouter.config.tsx
src/spa/router/desktopRouter.config.desktop.tsx
src/spa/router/mobileRouter.config.tsx
```

关注 `model/:slug` 如何指向当前文件，以及为什么移动端使用 `MobileModelPage`。

## 常见误区

误区一：以为 `slug` 就是可以直接请求的模型 identifier。

实际上文件中做了：

```ts
decodeURIComponent(params.slug ?? '')
```

这说明 URL 中的 `slug` 可能经过编码。模型 identifier 如果包含 `/`、空格或其他特殊字符，必须先解码再交给数据层。忽略这一点，可能会导致接口查不到数据。

误区二：以为 `ModelDetailPage` 负责展示所有详情 UI。

当前文件只负责页面入口、数据状态判断和组合。真正的详情展示分散在：

```txt
features/Header.tsx
features/Details/*
features/Sidebar/*
```

所以修改标题、参数、相关模型、侧边栏按钮时，不应该只盯着 `index.tsx`。

误区三：以为 `DetailProvider` 是可有可无的包装。

`DetailProvider` 是下游组件读取详情数据的关键。`Header`、`Details` 内部的子组件会通过 `useDetailContext()` 读取模型数据。如果去掉它，页面可能不会立刻类型报错，但运行时会只能拿到默认 `{}`，导致大量字段为空。

误区四：以为 `data` 一定是完整的 `DiscoverModelDetail`。

`DetailContextConfig` 定义为：

```ts
Partial<DiscoverModelDetail>
```

这表示下游组件要接受字段缺失。根据当前片段推断，这是为了让 provider 的默认值 `{}` 合法，也让某些数据字段缺失时页面不至于直接崩溃。阅读或修改下游组件时，不应假设每个字段都必然存在。

误区五：以为移动端和桌面端是两套页面。

实际上移动端复用同一个 `ModelDetailPage`，只是通过：

```tsx
<ModelDetailPage mobile={true} />
```

强制进入移动布局。也就是说，大部分详情逻辑是共用的。改动共享组件时，桌面端和移动端都会受影响。

误区六：以为 `mobile` 只由 props 决定。

`Header` 和 `Details` 内部还使用了：

```ts
useResponsive()
```

例如 `Header` 中：

```ts
const { mobile = isMobile } = useResponsive();
```

这表示组件会优先使用响应式检测结果；当响应式结果没有提供时，才使用外部传入的 `mobile`。因此移动端路由传 `mobile={true}` 是一种强制兜底，但组件仍然保留响应式判断能力。

误区七：以为描述文本来自接口。

`Header` 中描述文案来自：

```ts
t(`${identifier}.description`)
```

并且使用 namespace：

```ts
useTranslation('models')
```

所以模型描述至少有一部分依赖 i18n 资源，而不是完全来自 `data`。如果某个模型详情页描述显示异常，除了接口数据，还要检查 `models` locale 里是否有对应 key。

误区八：以为 `Loading` 是本目录自定义骨架屏。

当前 `loading.tsx` 只是转导：

```ts
export { DetailsLoading as default } from '../../components/ListLoading';
```

也就是说，模型详情页加载态复用了社区详情公共 loading 组件，而不是这个目录里单独实现的 loading UI。

误区九：以为路由只需要改一个 desktop config。

项目约定要求桌面路由树在：

```txt
src/spa/router/desktopRouter.config.tsx
src/spa/router/desktopRouter.config.desktop.tsx
```

保持同步。当前文件已经同时出现在动态桌面路由和同步桌面路由里。以后如果调整模型详情路由路径、移动文件或替换页面入口，两个 desktop config 都要同步检查，移动端 `mobileRouter.config.tsx` 也要视情况更新。
