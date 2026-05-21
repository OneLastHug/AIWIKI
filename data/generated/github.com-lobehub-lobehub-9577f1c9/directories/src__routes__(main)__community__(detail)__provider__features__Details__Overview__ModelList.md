# 目录：src/routes/(main)/community/(detail)/provider/features/Details/Overview/ModelList

## 它负责什么

`ModelList` 是社区「Provider 详情页」里 `Overview` 标签页的模型列表组件。它把当前 Provider 支持的模型渲染成一个可排序的表格，让用户快速比较模型名称、能力标签、上下文长度、最大输出、输入价格、输出价格，并能点击跳转到对应的「Model 详情页」。

这个目录目前只有一个文件：

- `index.tsx`：默认导出 `ModelList` React 组件。

它不是数据获取层，也不是路由入口。它的职责非常聚焦：从上层 `DetailProvider` 的 React Context 中读取 `models`，然后使用 `InlineTable` 展示这些模型。

## 关键组成

### `ModelList`

文件：`src/routes/(main)/community/(detail)/provider/features/Details/Overview/ModelList/index.tsx`

组件定义：

```tsx
const ModelList = memo(() => {
  const { models = [] } = useDetailContext();
  const { t } = useTranslation('discover');

  return (...)
});
```

它被 `memo` 包裹，说明作者希望在 props 不变时减少重复渲染。不过这个组件没有显式 props，真正影响它渲染的是 `useDetailContext()` 返回的 Context 值。

### 数据来源：`useDetailContext`

`ModelList` 通过：

```tsx
const { models = [] } = useDetailContext();
```

读取 Provider 详情数据里的 `models` 字段。`models = []` 是兜底处理，避免数据缺失时表格因为 `undefined` 报错。

`useDetailContext` 来自：

```tsx
import { useDetailContext } from '../../../DetailProvider';
```

对应文件是：

`src/routes/(main)/community/(detail)/provider/features/DetailProvider.tsx`

其中类型是：

```tsx
export type DetailContextConfig = Partial<DiscoverProviderDetail>;
```

也就是说，Context 里放的是 `DiscoverProviderDetail` 的部分字段。`ModelList` 只关心其中的 `models`。

### UI 容器：`TooltipGroup`、`Block`、`InlineTable`

渲染结构大致是：

```tsx
<TooltipGroup>
  <Block variant="outlined">
    <InlineTable ... />
  </Block>
</TooltipGroup>
```

含义如下：

- `TooltipGroup`：统一管理表头或按钮里的 tooltip 表现。
- `Block variant="outlined"`：给表格一个带边框的区块容器。
- `InlineTable`：项目内封装过的表格组件，用来展示紧凑型列表数据。

表格配置：

```tsx
dataSource={models}
rowKey="id"
scroll={{ x: 900 }}
```

`rowKey="id"` 表示每个模型用 `id` 作为唯一 key。`scroll={{ x: 900 }}` 表示表格在较窄屏幕下会横向滚动，避免列太多导致布局挤压。

### 列 1：模型名称

这一列使用：

- `ModelIcon`
- `Link`
- `urlJoin('/community/model', record.id)`
- `record.displayName`
- `record.id`

渲染效果是左侧模型头像，右侧上方显示模型展示名，下方显示模型 ID。点击整块内容会跳转到：

```txt
/community/model/{modelId}
```

排序逻辑：

```tsx
sorter: (a, b) => a.displayName.localeCompare(b.displayName)
```

也就是按模型展示名称字母顺序排序。

### 列 2：模型能力

字段：

```tsx
dataIndex: 'abilities'
```

渲染逻辑：

```tsx
if (!record?.abilities || !Object.values(record?.abilities).includes(true)) return '--';
return <ModelInfoTags {...record?.abilities} />;
```

如果模型没有能力信息，或者所有能力值都不是 `true`，显示 `--`。否则把 `abilities` 传给 `ModelInfoTags`，由公共组件渲染能力标签。

这里的能力通常包括类似视觉、函数调用、推理、文件、搜索等模型能力。具体有哪些能力由 `ModelInfoTags` 和模型类型定义决定，`ModelList` 本身不解释能力含义，只负责展示。

### 列 3：上下文长度

字段：

```tsx
contextWindowTokens
```

渲染逻辑：

```tsx
record.contextWindowTokens ? formatTokenNumber(record.contextWindowTokens) : '--'
```

有值时通过 `formatTokenNumber` 格式化 token 数量，没有值时显示 `--`。

排序逻辑：

```tsx
(a.contextWindowTokens || 0) - (b.contextWindowTokens || 0)
```

没有值的模型按 `0` 处理。

### 列 4：最大输出

字段：

```tsx
maxOutput
```

渲染逻辑：

```tsx
record.maxOutput ? formatTokenNumber(record.maxOutput) : '--'
```

表头不是纯文本，而是带 tooltip：

```tsx
<Tooltip title={t('models.providerInfo.maxOutputTooltip')}>
  <span>{t('models.providerInfo.maxOutput')}</span>
</Tooltip>
```

这说明「最大输出」这个概念需要额外解释，文案来自 `discover` i18n namespace。

注意：在相邻的「Model 详情页 ProviderList」中，最大输出会 fallback 到 `maxDimension`；但当前 `ModelList` 只看 `record.maxOutput`。所以如果某些模型只有 `maxDimension`，这里会显示 `--`。这是阅读时需要注意的一个差异。

### 列 5：输入价格

字段：

```tsx
inputPrice
```

但它不是直接读取 `record.inputPrice`，而是从 `record.pricing` 中计算：

```tsx
const inputRate = getTextInputUnitRate(record.pricing);
return inputRate
  ? '$' + formatPriceByCurrency(inputRate, record.pricing?.currency)
  : '--';
```

也就是说价格结构被封装在 `pricing` 里，`ModelList` 通过 `getTextInputUnitRate` 拿到「文本输入」单价，再用 `formatPriceByCurrency` 做格式化。

排序时同样先计算 input rate：

```tsx
const aRate = getTextInputUnitRate(a.pricing) || 0;
const bRate = getTextInputUnitRate(b.pricing) || 0;
return aRate - bRate;
```

### 列 6：输出价格

输出价格和输入价格结构几乎一致，只是工具函数换成：

```tsx
getTextOutputUnitRate(record.pricing)
```

表头 tooltip 文案使用：

```tsx
models.providerInfo.outputTooltip
models.providerInfo.output
```

### 列 7：操作入口

最后一列右对齐，只展示一个 `ChevronRightIcon` 图标按钮：

```tsx
<Link to={urlJoin('/community/model', record.id)}>
  <ActionIcon icon={ChevronRightIcon} ... />
</Link>
```

它和模型名称列的跳转目标一致，都是进入模型详情页。区别是这一列给用户一个更明显的「进入详情」操作入口。

## 上下游关系

### 上游：Provider 详情页

调用链从页面入口开始：

1. `src/routes/(main)/community/(detail)/provider/index.tsx`
2. 使用 `useParams` 读取 URL 中的 `slug`
3. 解码成 `identifier`
4. 调用 `useDiscoverStore((s) => s.useProviderDetail)`
5. 执行 `useProviderDetail({ identifier, withReadme: true })`
6. 成功后把 `data` 放入 `<DetailProvider config={data}>`
7. 渲染 `<Header />` 和 `<Details />`

简化后是：

```tsx
<DetailProvider config={data}>
  <Flexbox gap={16}>
    <Header mobile={mobile} />
    <Details mobile={mobile} />
  </Flexbox>
</DetailProvider>
```

所以 `ModelList` 并不直接请求接口。它只是站在 Context 下游消费 `data.models`。

### 中游：Details 与 Overview

`Details` 负责 Provider 详情页的 tab 切换：

```tsx
{activeTab === ProviderNavKey.Overview && <Overview />}
{activeTab === ProviderNavKey.Guide && <Guide />}
{activeTab === ProviderNavKey.Related && <Related />}
```

默认 tab 是：

```tsx
ProviderNavKey.Overview
```

`Overview` 再渲染标题和模型列表：

```tsx
const { models = [] } = useDetailContext();

return (
  <Flexbox gap={16}>
    <Title tag={<Tag>{models.length}</Tag>}>
      {t('providers.supportedModels')}
    </Title>
    <ModelList />
  </Flexbox>
);
```

所以 `ModelList` 的直接调用方是 `Overview`，`Overview` 的调用方是 `Details`。

### 下游：Model 详情页

`ModelList` 里的两处链接都会跳向：

```txt
/community/model/{record.id}
```

这会进入模型详情页。相邻目录中存在类似的反向组件：

`src/routes/(main)/community/(detail)/model/features/Details/Overview/ProviderList/index.tsx`

它是在「Model 详情页」展示支持该模型的 Provider 列表。两者互为镜像关系：

- Provider 详情页：Provider -> ModelList
- Model 详情页：Model -> ProviderList

这两个组件的表格结构、价格展示、能力标签、跳转按钮都很相似，只是主维度不同。

### 数据服务链路

Provider 详情数据从 store 到服务端的大致链路是：

```txt
ProviderDetailPage
  -> useDiscoverStore().useProviderDetail
  -> discoverService.getProviderDetail
  -> lambdaClient.market.getProviderDetail.query
  -> server discoverService.getProviderDetail
```

服务端 `getProviderDetail` 会：

1. 加载内置模型列表 `loadBuiltinModels()`
2. 获取 Provider 列表 `_getProviderList()`
3. 根据 `identifier` 找到当前 Provider
4. 如果 `withReadme` 为 true，读取对应 provider 文档
5. 过滤出当前 Provider 支持且可见的模型：

```tsx
builtinModels.filter((m) => m.providerId === provider.id && isAiModelVisible(m))
```

6. 使用 `uniqBy(..., item => item.id)` 去重
7. 返回：

```tsx
{
  ...provider,
  models,
  readme,
  related,
}
```

因此，`ModelList` 中的 `models` 实际来自服务端整理后的内置模型数据，而不是组件本地拼出来的。

## 运行/调用流程

1. 用户访问 Provider 详情页，例如：

```txt
/community/provider/openai
```

2. 页面入口读取路由参数：

```tsx
const params = useParams<{ slug: string }>();
const identifier = decodeURIComponent(params.slug ?? '');
```

3. 页面通过 discover store 请求 Provider 详情：

```tsx
useProviderDetail({ identifier, withReadme: true })
```

4. 请求期间显示 `Loading`；没有数据时显示 `NotFound`。

5. 请求成功后，页面把详情数据注入 `DetailProvider`。

6. `Details` 读取 query 参数 `activeTab`，默认显示 `overview`。

7. `Overview` 从 `DetailProvider` 读取 `models`，用 `models.length` 显示支持模型数量。

8. `Overview` 渲染 `ModelList`。

9. `ModelList` 再次从 `DetailProvider` 读取同一份 `models`，传给 `InlineTable`。

10. 表格逐行渲染模型：

```txt
模型名称 / 能力 / 上下文长度 / 最大输出 / 输入价格 / 输出价格 / 跳转按钮
```

11. 用户点击模型名称或右侧箭头，跳转到对应模型详情页。

## 小白阅读顺序

1. 先读页面入口：

```txt
src/routes/(main)/community/(detail)/provider/index.tsx
```

重点看 `useParams`、`useProviderDetail`、`DetailProvider config={data}`。这能理解「数据从哪里来」。

2. 再读 Context：

```txt
src/routes/(main)/community/(detail)/provider/features/DetailProvider.tsx
```

重点看 `DetailContextConfig = Partial<DiscoverProviderDetail>` 和 `useDetailContext()`。这能理解为什么子组件都能直接拿到 provider 详情数据。

3. 再读 tab 容器：

```txt
src/routes/(main)/community/(detail)/provider/features/Details/index.tsx
```

重点看 `activeTab` 和 `ProviderNavKey.Overview`。这能理解 `Overview` 什么时候出现。

4. 然后读 `Overview`：

```txt
src/routes/(main)/community/(detail)/provider/features/Details/Overview/index.tsx
```

重点看标题里的 `models.length` 和 `<ModelList />`。

5. 最后读目标组件：

```txt
src/routes/(main)/community/(detail)/provider/features/Details/Overview/ModelList/index.tsx
```

建议按表格列一列一列读，不要从上到下硬啃 JSX。可以按这些问题理解：

- 这一列展示哪个字段？
- 没有数据时显示什么？
- 是否支持排序？
- 是否有 tooltip？
- 是否会跳转？

6. 如果还想理解字段类型，再读：

```txt
packages/types/src/discover/providers.ts
```

这里定义了：

```tsx
export interface DiscoverProviderDetailModelItem extends LobeDefaultAiModelListItem {
  maxOutput?: number;
}

export interface DiscoverProviderDetail extends Omit<DiscoverProviderItem, 'models'> {
  models: DiscoverProviderDetailModelItem[];
  readme?: string;
  related: DiscoverProviderItem[];
}
```

这能解释 `models` 数组中每个模型大致有哪些字段。

## 常见误区

1. **误以为 `ModelList` 自己请求数据**

`ModelList` 没有调用 service、store、SWR 或 API。它只通过 `useDetailContext()` 读取上层已经准备好的 `models`。真正的数据请求发生在 Provider 详情页入口 `index.tsx` 和 discover store/service 中。

2. **误以为 `dataIndex` 就一定对应直接字段**

表格里有 `dataIndex: 'inputPrice'` 和 `dataIndex: 'outputPrice'`，但真实价格并不是从 `record.inputPrice`、`record.outputPrice` 读取的，而是从 `record.pricing` 经过 `getTextInputUnitRate`、`getTextOutputUnitRate` 计算出来。

3. **误以为所有列都是纯文本**

`maxOutput`、`inputPrice`、`outputPrice` 的表头都带 `Tooltip`。这是为了给用户解释价格和输出字段的含义。阅读时要注意 `title` 可以是 ReactNode，不一定是字符串。

4. **误以为 `models` 一定存在**

Context 类型是 `Partial<DiscoverProviderDetail>`，所以 `models` 在类型层面可能不存在。组件里使用 `models = []` 是必要的防御式写法。

5. **误以为 `ModelList` 和 `ProviderList` 完全一致**

`ModelList` 和模型详情页里的 `ProviderList` 很像，但不是完全相同。比如 `ProviderList` 在最大输出列会 fallback 到 `maxDimension`，而当前 `ModelList` 只使用 `maxOutput`。如果某类模型的输出限制存在于 `maxDimension`，这里可能显示 `--`。

6. **误以为点击箭头才可以进入模型详情**

模型名称区域本身也包了一层 `Link`，点击模型名称或模型 ID 区域同样会进入 `/community/model/{modelId}`。右侧箭头只是另一个操作入口。

7. **误以为 `record.id` 和 Provider ID 有关**

在 `ModelList` 里，`record.id` 是模型 ID，不是 Provider ID。跳转路径是 `/community/model/{record.id}`，说明它指向模型详情页。Provider 的标识来自上层 provider detail，不在这一行里作为跳转目标使用。

8. **误以为这个目录是 route segment**

虽然路径位于 `src/routes/...` 下，但 `ModelList` 不是路由文件，也不负责注册路由。它是 provider detail 页面内部的 feature component。真正的页面入口是上层的：

```txt
src/routes/(main)/community/(detail)/provider/index.tsx
```

9. **误以为价格一定以美元为单位**

渲染代码里固定拼了 `'$'`，同时又把 `record.pricing?.currency` 传给 `formatPriceByCurrency`。根据当前片段推断，价格显示主要面向美元样式，但实际格式化仍参考 `pricing.currency`。如果未来支持非美元货币，这里是否应该继续固定 `'$'` 需要结合 `formatPriceByCurrency` 的实现再判断。

10. **误以为排序会修改原始数据**

表格列上的 `sorter` 只是给 `InlineTable` / 底层表格组件使用的排序函数。`ModelList` 没有显式修改 `models` 数组，也没有写回 store 或 Context。
