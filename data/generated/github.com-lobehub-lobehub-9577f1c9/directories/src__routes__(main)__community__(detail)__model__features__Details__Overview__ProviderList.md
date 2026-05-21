# 目录：src/routes/(main)/community/(detail)/model/features/Details/Overview/ProviderList

## 它负责什么

`ProviderList` 是模型详情页「Overview」页签里的“支持该模型的供应商列表”组件。它的职责很集中：从模型详情上下文 `DetailProvider` 中读取 `providers` 数组，然后把每个供应商渲染成一行表格，展示供应商名称、模型能力、上下文长度、最大输出、输入价格、输出价格，以及跳转/文档/API Key/官方认证等操作入口。

它不负责拉取数据，也不负责决定当前页面展示哪个 tab。数据获取发生在模型详情页入口 `src/routes/(main)/community/(detail)/model/index.tsx`，tab 切换发生在 `src/routes/(main)/community/(detail)/model/features/Details/index.tsx`。`ProviderList` 只是详情页数据进入 Overview 后的一个表格展示层。

从路径上看，它位于：

`src/routes/(main)/community/(detail)/model/features/Details/Overview/ProviderList/index.tsx`

虽然它在 `src/routes` 下，但实际已经属于模型详情页内部 feature 的深层 UI 组件，不是路由入口文件。

## 关键组成

这个目录只有一个文件：

`ProviderList/index.tsx`

核心导出是默认组件：

```tsx
const ProviderList = memo(() => {
  const { providers = [] } = useDetailContext();
  const { t } = useTranslation('discover');

  return (
    <TooltipGroup>
      <Block variant={'outlined'}>
        <InlineTable ... />
      </Block>
    </TooltipGroup>
  );
});

export default ProviderList;
```

关键点如下。

`useDetailContext`

`ProviderList` 通过：

```tsx
const { providers = [] } = useDetailContext();
```

读取模型详情数据中的 `providers`。这个 hook 来自上层：

`src/routes/(main)/community/(detail)/model/features/DetailProvider.tsx`

`DetailProvider` 内部用 React `createContext` 保存 `Partial<DiscoverModelDetail>`，所以 `providers` 可能不存在。组件用 `providers = []` 做了兜底，避免空数据时报错。

`InlineTable`

表格组件来自：

```tsx
import InlineTable from '@/components/InlineTable';
```

`ProviderList` 把 `providers` 作为 `dataSource`，并设置：

```tsx
rowKey="id"
scroll={{ x: 1000 }}
```

这说明表格以供应商 `id` 作为唯一键，并且横向内容较多，最小横向滚动宽度为 `1000`。这对移动端或窄屏很重要，因为列包含价格、能力、操作按钮等多项信息。

表格列定义

`columns` 是这个组件的主体逻辑，包含以下几类信息：

1. 供应商列 `provider`

显示 `ProviderIcon`、供应商名称，并用 `Link` 跳转到：

```tsx
/community/provider/:providerId
```

链接由：

```tsx
urlJoin('/community/provider', record.id)
```

生成。

这一列支持按供应商名称排序：

```tsx
sorter: (a, b) => a.name.localeCompare(b.name)
```

2. 模型能力列 `abilities`

读取：

```tsx
record.model?.abilities
```

如果存在，则用：

```tsx
<ModelInfoTags {...record.model.abilities} />
```

展示能力标签；如果不存在，显示 `--`。

这里的 `ModelInfoTags` 来自：

```tsx
import { ModelInfoTags } from '@/components/ModelSelect';
```

根据当前片段推断，它应该是统一展示模型能力标签的通用组件，比如视觉、函数调用、推理、文件、联网等能力。依据是字段名 `abilities` 和组件名 `ModelInfoTags`。

3. 上下文长度列 `contextLength`

读取：

```tsx
record.model?.contextWindowTokens
```

存在时用：

```tsx
formatTokenNumber(record.model.contextWindowTokens)
```

格式化 token 数，否则显示 `--`。

排序逻辑是按 `contextWindowTokens` 数值升序：

```tsx
(a.model?.contextWindowTokens || 0) - (b.model?.contextWindowTokens || 0)
```

需要注意，`dataIndex` 写的是 `'model.contextLength'`，但实际渲染和排序使用的是 `contextWindowTokens`。这意味着 `dataIndex` 在这里更多是表格列标识，不代表真实读取字段完全一致。

4. 最大输出列 `maxOutput`

优先读取：

```tsx
record.model?.maxOutput
```

如果没有，则读取：

```tsx
record.model?.maxDimension
```

最后都用 `formatTokenNumber` 展示。

这说明该列可能同时服务文本模型和非文本模型。文本模型常见字段是最大输出 token；图像或多模态模型可能使用 `maxDimension` 这类尺寸字段。根据当前片段推断，这里是为了兼容不同模型类型的输出上限展示。

列标题带 tooltip：

```tsx
t('models.providerInfo.maxOutput')
t('models.providerInfo.maxOutputTooltip')
```

文案命名空间是 `discover`。

5. 输入价格列 `inputPrice`

通过：

```tsx
getTextInputUnitRate(record.model?.pricing)
```

从 `pricing` 中提取文本输入单价。

存在价格时展示：

```tsx
'$' + formatPriceByCurrency(inputRate, record.model.pricing?.currency)
```

不存在时显示 `--`。

排序逻辑也是基于 `getTextInputUnitRate` 返回的数值。

这里有一个细节：展示字符串始终拼了 `'$'`，同时又把 `currency` 传给 `formatPriceByCurrency`。根据当前片段推断，当前 UI 可能主要面向美元价格，`formatPriceByCurrency` 负责小数位或单位格式，而不是负责货币符号完整渲染。

6. 输出价格列 `outputPrice`

与输入价格类似，但调用的是：

```tsx
getTextOutputUnitRate(record.model?.pricing)
```

展示输出 token 单价。

7. 操作列 `action`

操作列靠右展示多个小图标按钮：

- 如果供应商 `id === 'lobehub'`，显示 `BadgeCheck`，表示官方/内置供应商。
- 如果不是 `lobehub`，显示 `KeyIcon`，表示需要 API Key 或自有供应商配置。
- 显示 `BookIcon`，链接到供应商文档。
- 显示 `ChevronRightIcon`，跳转到供应商社区详情页。

文档地址由：

```tsx
urlJoin(BASE_PROVIDER_DOC_URL, record.id)
```

生成，使用普通 `<a>`，并设置：

```tsx
target="_blank"
rel="noreferrer"
```

供应商详情页使用 `react-router-dom` 的 `Link`，属于 SPA 内部跳转。

样式与 UI 组件

这个组件使用了多个 LobeHub UI 组件：

```tsx
ActionIcon
Block
Flexbox
Icon
Tooltip
TooltipGroup
```

其中：

- `Block variant="outlined"` 给表格提供外框容器。
- `TooltipGroup` 包裹整个区域，用于统一管理多个 tooltip 的交互体验。
- `ActionIcon` 用于小图标按钮。
- `Flexbox` 用于供应商名称行和操作按钮行的横向布局。
- `cssVar.colorSuccess` 给官方认证按钮设置成功色。
- `cssVar.colorTextDescription` 给进入详情的箭头按钮设置弱化文字色。

组件本身使用 `memo` 包裹，减少父组件重渲染时的无意义渲染。

## 上下游关系

上游数据来源

模型详情页入口是：

`src/routes/(main)/community/(detail)/model/index.tsx`

它从 URL 中读取模型 slug：

```tsx
const params = useParams<{ slug: string }>();
const identifier = decodeURIComponent(params.slug ?? '');
```

然后通过 discover store 拉取详情：

```tsx
const useModelDetail = useDiscoverStore((s) => s.useModelDetail);
const { data, isLoading } = useModelDetail({ identifier });
```

加载中显示 `Loading`，没有数据显示 `NotFound`。成功后把 `data` 放进上下文：

```tsx
<DetailProvider config={data}>
  <Flexbox gap={16}>
    <Header mobile={mobile} />
    <Details mobile={mobile} />
  </Flexbox>
</DetailProvider>
```

所以 `ProviderList` 的真正数据源链路是：

`URL slug` -> `useDiscoverStore().useModelDetail({ identifier })` -> `data` -> `DetailProvider` -> `useDetailContext()` -> `providers`

中间层调用

`ProviderList` 的直接调用方是：

`src/routes/(main)/community/(detail)/model/features/Details/Overview/index.tsx`

代码结构是：

```tsx
const Overview = memo(() => {
  const { t } = useTranslation('discover');
  const { providers = [] } = useDetailContext();

  return (
    <Flexbox gap={16}>
      <Title tag={<Tag>{providers.length}</Tag>}>
        {t('models.supportedProviders')}
      </Title>
      <ProviderList />
    </Flexbox>
  );
});
```

这里 `Overview` 负责显示标题和供应商数量，`ProviderList` 负责显示具体表格。

再上一层是：

`src/routes/(main)/community/(detail)/model/features/Details/index.tsx`

它通过 query 参数 `activeTab` 控制当前展示哪个 tab：

```tsx
const [activeTab, setActiveTab] = useQueryState('activeTab', {
  clearOnDefault: true,
  defaultValue: ModelNavKey.Overview,
});
```

当 `activeTab === ModelNavKey.Overview` 时，才渲染：

```tsx
<Overview />
```

也就是说，`ProviderList` 只有在模型详情页的 Overview tab 激活时才会出现。

下游跳转关系

`ProviderList` 产生两个主要下游入口：

1. 供应商社区详情页

点击供应商名称或右侧箭头，会跳转到：

```tsx
/community/provider/:providerId
```

例如 `openai` 供应商对应：

```plaintext
/community/provider/openai
```

2. 供应商文档

点击书本图标，会打开：

```tsx
BASE_PROVIDER_DOC_URL + providerId
```

这是外部新标签页链接，具体基础地址来自：

```tsx
import { BASE_PROVIDER_DOC_URL } from '@/const/url';
```

根据当前片段推断，这应该指向 LobeHub 的 provider 使用文档或官方配置指南。

类型关系

`ProviderList` 没有显式声明 props，它完全依赖 `DetailProvider` 上下文。

`DetailProvider` 的类型是：

```tsx
export type DetailContextConfig = Partial<DiscoverModelDetail>;
```

因此 `providers` 的结构应来自 `DiscoverModelDetail` 类型。当前片段没有展开 `DiscoverModelDetail`，但从使用字段可以推断每个 provider 至少包含：

```ts
{
  id: string;
  name: string;
  model?: {
    abilities?: unknown;
    contextWindowTokens?: number;
    maxOutput?: number;
    maxDimension?: number;
    pricing?: unknown;
  };
}
```

这是根据 `ProviderList` 的字段访问路径推断出来的，不是完整类型定义。

## 运行/调用流程

1. 用户进入模型详情路由

例如访问某个模型详情页，路由参数中包含 `slug`。页面组件 `ModelDetailPage` 通过 `useParams` 取出 slug，并解码成 `identifier`。

2. 页面请求模型详情数据

`ModelDetailPage` 调用：

```tsx
useDiscoverStore((s) => s.useModelDetail)
```

并传入：

```tsx
{ identifier }
```

获取模型详情数据。数据中包含模型基础信息、相关模型、供应商列表等。

3. 数据进入 `DetailProvider`

当数据加载完成后，页面渲染：

```tsx
<DetailProvider config={data}>
  ...
</DetailProvider>
```

此后，`Header`、`Details`、`Overview`、`ProviderList` 等子组件都可以通过 `useDetailContext()` 读取同一份详情数据。

4. `Details` 判断当前 tab

`Details` 读取 query 参数 `activeTab`。默认值是：

```tsx
ModelNavKey.Overview
```

如果当前 tab 是 Overview，就渲染：

```tsx
<Overview />
```

5. `Overview` 显示标题和数量

`Overview` 读取：

```tsx
const { providers = [] } = useDetailContext();
```

然后用 `providers.length` 显示支持供应商数量，标题文案来自：

```tsx
t('models.supportedProviders')
```

6. `ProviderList` 渲染供应商表格

`ProviderList` 再次读取同一份 `providers`，交给 `InlineTable`。

每一行代表一个供应商。表格列会依次渲染：

- 供应商头像和名称
- 模型能力标签
- 上下文窗口 token 数
- 最大输出 token 或最大尺寸
- 输入价格
- 输出价格
- 官方/API Key/文档/详情跳转按钮

7. 用户进行交互

用户可以：

- 点击列头排序，比如按供应商名称、上下文长度、最大输出、价格排序。
- 点击供应商名称或箭头进入供应商详情页。
- 点击文档图标打开 provider 文档。
- 鼠标悬停在图标或价格列标题上查看 tooltip 说明。

## 小白阅读顺序

建议按下面顺序读，容易建立完整链路。

1. 先读页面入口

`src/routes/(main)/community/(detail)/model/index.tsx`

重点看三件事：

- URL 参数 `slug` 怎么变成 `identifier`
- `useDiscoverStore().useModelDetail` 怎么获取详情数据
- `DetailProvider config={data}` 怎么把数据传给下层

读完这一步，你会知道 `ProviderList` 不是自己请求数据，而是消费详情页已经取回的数据。

2. 再读上下文提供者

`src/routes/(main)/community/(detail)/model/features/DetailProvider.tsx`

重点看：

```tsx
createContext<DetailContextConfig>({})
```

以及：

```tsx
useDetailContext()
```

这一步能理解为什么深层组件不需要层层传 props，而是直接从上下文拿数据。

3. 再读详情 tab 容器

`src/routes/(main)/community/(detail)/model/features/Details/index.tsx`

重点看：

```tsx
activeTab === ModelNavKey.Overview && <Overview />
```

这一步能理解 `ProviderList` 出现在哪个 tab 里，以及为什么它不是页面一加载就一定可见，而是受 `activeTab` 控制。

4. 然后读 Overview

`src/routes/(main)/community/(detail)/model/features/Details/Overview/index.tsx`

它很短，只做两件事：

- 显示标题 `models.supportedProviders`
- 显示 `providers.length`
- 渲染 `<ProviderList />`

这一步能看出 `Overview` 是一个组合层，`ProviderList` 是真正的列表展示层。

5. 最后读 ProviderList

`src/routes/(main)/community/(detail)/model/features/Details/Overview/ProviderList/index.tsx`

建议先看最外层：

```tsx
<TooltipGroup>
  <Block variant={'outlined'}>
    <InlineTable ... />
  </Block>
</TooltipGroup>
```

再看 `columns` 数组。读 `columns` 时不要从上到下一口气硬读，可以按业务含义分组：

- 第一列：供应商是谁
- 中间列：这个供应商下该模型的能力和参数
- 价格列：输入/输出价格
- 最后一列：操作按钮

这样会比逐行看 JSX 更容易理解。

## 常见误区

1. 误以为 `ProviderList` 会请求数据

它不会。`ProviderList` 没有调用 service、store、SWR 或 TRPC。它只调用：

```tsx
useDetailContext()
```

真正的数据请求在模型详情页入口 `model/index.tsx` 中，通过 `useDiscoverStore().useModelDetail` 完成。

2. 误以为 `providers` 是组件 props

`ProviderList` 没有 props。它依赖 React context。也就是说，如果单独渲染 `ProviderList`，但外层没有 `DetailProvider` 或没有传入包含 `providers` 的 config，它会拿到默认空对象，最终使用空数组：

```tsx
const { providers = [] } = useDetailContext();
```

这种情况下不会报错，但表格没有数据。

3. 误把 `dataIndex` 当成真实字段来源

例如上下文长度列写的是：

```tsx
dataIndex: 'model.contextLength'
```

但真正读取的是：

```tsx
record.model?.contextWindowTokens
```

所以理解字段时要以 `render` 和 `sorter` 里的访问路径为准，而不是只看 `dataIndex`。

4. 误以为所有模型都有 `maxOutput`

`maxOutput` 列有兼容逻辑：

```tsx
record.model?.maxOutput
  ? formatTokenNumber(record.model.maxOutput)
  : record.model?.maxDimension
    ? formatTokenNumber(record.model.maxDimension)
    : '--'
```

这表示部分模型可能没有 `maxOutput`，但有 `maxDimension`。根据当前片段推断，这是为了兼容不同类型模型的输出限制字段。

5. 误以为 `lobehub` 和其他 provider 的操作按钮一样

`record.id === 'lobehub'` 是特殊分支：

```tsx
const isLobeHub = record.id === 'lobehub';
```

如果是 `lobehub`，显示官方认证图标 `BadgeCheck`；否则显示 `KeyIcon`，提示 API 相关信息。这是产品语义上的区分：LobeHub 官方供应商与用户需要配置 API Key 的第三方供应商不同。

6. 误以为文档跳转和详情跳转都是 SPA 路由

不是。

供应商详情页使用 `Link`：

```tsx
<Link to={urlJoin('/community/provider', record.id)}>
```

这是应用内部路由。

文档按钮使用 `<a>`：

```tsx
<a href={urlJoin(BASE_PROVIDER_DOC_URL, record.id)} target="_blank">
```

这是外部链接，会打开新标签页。

7. 误以为价格格式完全由货币字段决定

价格展示代码是：

```tsx
'$' + formatPriceByCurrency(inputRate, record.model.pricing?.currency)
```

它手动拼接了 `$`。因此即使 `pricing.currency` 存在，当前 UI 仍然以美元符号开头。不要简单假设它会根据 `currency` 自动切换货币符号；至少从当前片段看，货币符号不是完全动态的。

8. 误以为这是可复用的通用 provider 表格

这个组件强依赖模型详情上下文和 discover 命名空间文案：

```tsx
useDetailContext()
useTranslation('discover')
```

并且列字段围绕 `DiscoverModelDetail.providers[].model` 设计。它更像“模型详情页的供应商支持表”，不是全站通用的 provider list。
