# 目录：src/routes/(main)/community/(detail)/model/features/Details

## 它负责什么

`Details` 是社区模型详情页的“详情内容区”。它不负责拉取模型数据，也不负责页面级路由匹配；它的职责是在已经拿到某个模型详情数据后，根据当前 tab 展示对应内容：

- `Overview`：展示该模型被哪些 provider 支持，以及每个 provider 下该模型的能力、上下文长度、输出长度、价格、跳转入口等。
- `Parameter`：展示模型常见调用参数说明，例如 `temperature`、`top_p`、`max_tokens`、`reasoning_effort`。
- `Related`：展示相关模型列表。
- `Sidebar`：在详情内容旁边展示操作按钮、相关模型、相关 provider 等侧边信息。虽然 `Sidebar` 不在本目录内部，但被 `Details/index.tsx` 直接组合进来。

这个目录本质上是模型详情页的“tab 容器 + tab 页面集合”。它依赖上层的 `DetailProvider` 提供数据，依赖 URL query 中的 `activeTab` 决定当前展示哪个详情页签。

## 关键组成

### `index.tsx`

这是目录入口，默认导出 `Details` 组件。

核心逻辑：

- 使用 `useResponsive()` 判断当前是否为移动端。
- 使用 `useQueryState('activeTab', ...)` 把当前 tab 状态同步到 URL query。
- 默认 tab 是 `ModelNavKey.Overview`。
- 渲染 `Nav` 作为页签导航。
- 根据 `activeTab` 条件渲染：
  - `ModelNavKey.Overview` -> `<Overview />`
  - `ModelNavKey.Parameter` -> `<Parameter />`
  - `ModelNavKey.Related` -> `<Related />`
- 同时在内容区域旁边组合 `Sidebar`。
- 移动端通过 `flexDirection: 'column-reverse'` 调整内容和侧边栏顺序。

它只接收一个可选 props：

```ts
{
  mobile?: boolean;
}
```

这里的 `mobile` 既可以由上层显式传入，也可以由 `useResponsive()` 计算得到。代码中：

```ts
const { mobile = isMobile } = useResponsive();
```

表示如果响应式 hook 没有给出 `mobile`，就使用 props 中传入的 `isMobile` 作为兜底。

### `Nav.tsx`

`Nav` 是 tab 导航组件。

它使用 `@lobehub/ui` 的 `Tabs`，每个 tab 对应一个 `ModelNavKey`：

- `overview`
- `parameter`
- `related`

对应类型定义位于 `packages/types/src/discover/models.ts`：

```ts
export enum ModelNavKey {
  Overview = 'overview',
  Parameter = 'parameter',
  Related = 'related',
}
```

`Nav` 的 props 是：

```ts
interface NavProps {
  activeTab?: ModelNavKey;
  mobile?: boolean;
  setActiveTab?: (tab: ModelNavKey) => void;
}
```

点击 tab 时：

```ts
onChange={(key) => setActiveTab?.(key as ModelNavKey)}
```

上层传入的 `setActiveTab` 来自 `useQueryState`，所以 tab 切换会写入 URL query，而不是只保存在 React 内存状态里。

桌面端 `Nav` 除了 tab，还会展示三个外链：

- Discord 求助链接：`SOCIAL_URL.discord`
- 查看源码：`[URL已移除]
- 反馈问题：`[URL已移除]

移动端只渲染 tab，不显示右侧链接。

### `Overview/index.tsx`

`Overview` 是“支持的供应商”概览区。

它通过：

```ts
const { providers = [] } = useDetailContext();
```

从模型详情上下文中读取 `providers`，然后显示标题：

```tsx
<Title tag={<Tag>{providers.length}</Tag>}>
  {t('models.supportedProviders')}
</Title>
```

真正的表格内容交给 `ProviderList`。

### `Overview/ProviderList/index.tsx`

这是 `Overview` 里最重要的组件，负责展示 provider 表格。

数据来源：

```ts
const { providers = [] } = useDetailContext();
```

表格组件使用项目内的 `InlineTable`，外层包在 `Block variant="outlined"` 和 `TooltipGroup` 中。

每一行代表一个支持当前模型的 provider。主要列包括：

- provider 名称和头像：
  - 使用 `ProviderIcon`
  - 点击跳转到 `/community/provider/:id`
- 模型能力：
  - 使用 `ModelInfoTags`
  - 读取 `record.model?.abilities`
- 上下文长度：
  - 读取 `record.model?.contextWindowTokens`
  - 使用 `formatTokenNumber` 格式化
- 最大输出：
  - 优先读 `record.model?.maxOutput`
  - 否则读 `record.model?.maxDimension`
- 输入价格：
  - 使用 `getTextInputUnitRate(record.model?.pricing)`
  - 再用 `formatPriceByCurrency` 格式化
- 输出价格：
  - 使用 `getTextOutputUnitRate(record.model?.pricing)`
  - 再用 `formatPriceByCurrency` 格式化
- 操作列：
  - `lobehub` provider 显示官方认证图标
  - 非 `lobehub` provider 显示 API Key 图标
  - 文档链接跳到 `BASE_PROVIDER_DOC_URL + provider.id`
  - 详情入口跳到 `/community/provider/:id`

这个组件里有较多 sorter，所以它不仅是展示列表，也承担了用户在表格中按 provider 名称、上下文长度、最大输出、输入价格、输出价格排序的交互能力。

### `Parameter/index.tsx`

`ParameterList` 展示模型调用参数说明。

它不是从后端直接拿一组参数配置，而是在组件内部写死一组通用参数：

- `temperature`
- `top_p`
- `presence_penalty`
- `frequency_penalty`
- `max_tokens`
- `reasoning_effort`

每个参数对象包含：

```ts
interface Parameter {
  defaultValue: string | number;
  desc: string;
  icon: LucideIcon;
  key: string;
  label: string;
  range?: (string | number)[];
  type: string;
}
```

其中 `max_tokens` 的范围会结合当前模型详情动态计算：

```ts
range: Boolean(data?.maxOutput || data?.maxDimension)
  ? [0, formatTokenNumber(data?.maxOutput || data?.maxDimension || 0)]
  : undefined
```

这说明 `Parameter` 页不是完全静态的：大部分参数说明是固定的，但 `max_tokens` 的上限会根据当前模型的 `maxOutput` 或 `maxDimension` 变化。

UI 上使用 `Collapse`，默认展开所有参数：

```ts
defaultActiveKey={items.map((item) => item.key)}
```

### `Parameter/ParameterItem.tsx`

`ParameterItem` 是单个参数说明项。

它展示三类信息：

- 参数描述 `desc`
- 参数类型 `type`
- 默认值 `defaultValue`
- 可选范围 `range`

默认文档链接是：

```ts
const DEFAULT_DOC_URL = '[URL已移除]';
```

数值格式化逻辑由 `formatNum` 处理：

```ts
const formatNum = (num: string | number) => {
  return typeof num === 'number' ? num.toFixed(2) : num.toUpperCase();
};
```

所以数字默认显示两位小数，字符串会转成大写。例如 `low` 会显示为 `LOW`。

### `Related/index.tsx`

`Related` 展示相关模型列表。

数据来自：

```ts
const { related, category } = useDetailContext();
```

列表组件复用模型列表页的组件：

```ts
import List from '../../../../../(list)/model/features/List';
```

标题使用社区通用的 `Title` 组件，并设置 `more` 和 `moreLink`。

需要注意的是，当前代码中的 `moreLink` 指向：

```ts
url: '/community/plugin'
```

但本组件展示的是 model 详情下的 related model，并且复用了 model list 的 `List`。根据当前片段推断，这里可能是沿用 assistant/plugin 详情页代码时留下的路径或文案复用点；也可能是产品上有意跳到 plugin 社区。单看本目录无法完全确认，需要结合页面实际行为或产品设计判断。

## 上下游关系

上游页面入口是：

```txt
src/routes/(main)/community/(detail)/model/index.tsx
```

调用链大致是：

1. `ModelDetailPage` 从 `react-router-dom` 的 `useParams()` 里读取 `slug`。
2. 将 `slug` 解码为模型 `identifier`。
3. 通过 `useDiscoverStore((s) => s.useModelDetail)` 获取 SWR hook。
4. 调用 `useModelDetail({ identifier })` 拉取模型详情。
5. 加载中显示 `<Loading />`。
6. 没有数据显示 `<NotFound />`。
7. 有数据时用 `<DetailProvider config={data}>` 包住 `<Header />` 和 `<Details />`。

数据提供者是：

```txt
src/routes/(main)/community/(detail)/model/features/DetailProvider.tsx
```

它创建了一个 React context：

```ts
export const DetailContext = createContext<DetailContextConfig>({});
```

`DetailContextConfig` 是：

```ts
export type DetailContextConfig = Partial<DiscoverModelDetail>;
```

也就是说，下游组件拿到的详情字段都要按“可能不存在”处理。本目录里的 `providers = []`、`related`、`maxOutput || maxDimension` 这些写法，都是围绕这个不完整数据类型做的防御。

详情数据类型来自：

```txt
packages/types/src/discover/models.ts
```

核心结构是：

```ts
export interface DiscoverModelDetail extends Omit<DiscoverModelItem, 'providers'> {
  maxOutput?: number;
  providers: DiscoverModelDetailProviderItem[];
  related: DiscoverModelItem[];
}
```

provider 项结构是：

```ts
export interface DiscoverModelDetailProviderItem extends ModelProviderCard {
  model?: LobeDefaultAiModelListItem;
}
```

这解释了为什么 `ProviderList` 中大量使用 `record.model?.xxx`：某个 provider 记录不一定带完整 model 信息。

再往上，客户端服务在：

```txt
src/services/discover.ts
```

`getModelDetail` 调用：

```ts
lambdaClient.market.getModelDetail.query(...)
```

`useModelDetail` 则通过 SWR 以 `model-details-locale-identifier` 形式缓存请求。

下游方面，本目录主要调用这些组件和工具：

- `Sidebar`：模型详情侧边栏。
- `Title`：社区详情页标题组件。
- `InlineTable`：项目内表格组件。
- `ModelInfoTags`：模型能力标签。
- `Statistic`：参数详情中的小型指标展示组件。
- `List`：社区模型列表组件，用于展示 related models。
- `formatTokenNumber`、`formatPriceByCurrency`、`getTextInputUnitRate`、`getTextOutputUnitRate`：格式化模型数值和价格。
- `ProviderIcon`：provider 图标。
- `react-router-dom` 的 `Link`：站内跳转。
- `url-join`、`query-string`：拼接详情页链接和 query URL。

## 运行/调用流程

用户进入某个模型详情页时，流程如下：

1. 路由匹配到 `src/routes/(main)/community/(detail)/model/index.tsx`。
2. 页面从 URL path 中拿到 `slug`，解码得到模型 `identifier`。
3. `useDiscoverStore` 暴露的 `useModelDetail` 使用 SWR 请求模型详情。
4. 请求成功后，`data` 被传入 `DetailProvider`。
5. `Header` 和 `Details` 都在 `DetailProvider` 内部，因此可以调用 `useDetailContext()` 读取同一份模型详情。
6. `Details` 读取 URL query 中的 `activeTab`。
7. 如果 URL 没有 `activeTab`，默认进入 `overview`。
8. `Nav` 根据 `activeTab` 高亮当前 tab。
9. 用户点击 tab 时，`Nav` 调用 `setActiveTab`。
10. `setActiveTab` 更新 URL query。
11. `Details` 因 query 状态变化重新渲染对应内容。
12. 内容区根据 tab 展示 `Overview`、`Parameter` 或 `Related`。
13. `Sidebar` 同时根据 `activeTab` 调整侧边栏内容：
    - 当前不是 `related` 时展示侧边栏相关模型。
    - 当前不是 `overview` 时展示侧边栏相关 providers。
    - 移动端侧边栏只展示 `ActionButton`。

更具体地看三个 tab：

`overview` 流程：

1. `Overview` 从 context 读取 `providers`。
2. 标题显示 provider 数量。
3. `ProviderList` 将 `providers` 渲染成表格。
4. 每行展示 provider、模型能力、上下文、输出、价格和跳转动作。

`parameter` 流程：

1. `ParameterList` 从 context 读取当前模型详情。
2. 内部构造固定参数数组。
3. 用当前模型的 `maxOutput` 或 `maxDimension` 计算 `max_tokens` 范围。
4. 将参数数组转成 `Collapse` 面板。
5. 每个面板内部由 `ParameterItem` 渲染描述、类型、默认值、范围和文档链接。

`related` 流程：

1. `Related` 从 context 读取 `related` 和 `category`。
2. `Title` 构造“查看更多”的链接。
3. 复用模型列表页 `List` 组件展示相关模型。

## 小白阅读顺序

1. 先读 `src/routes/(main)/community/(detail)/model/index.tsx`  
   了解模型详情页从哪里拿 `identifier`、如何请求数据、什么时候渲染 `Details`。

2. 再读 `features/DetailProvider.tsx`  
   明白本目录里为什么到处可以用 `useDetailContext()`，以及上下文数据类型为什么是 `Partial<DiscoverModelDetail>`。

3. 再读 `Details/index.tsx`  
   这是本目录主入口。重点看 `useQueryState('activeTab')`、`Nav`、三个 tab 组件和 `Sidebar` 的组合方式。

4. 接着读 `Nav.tsx`  
   理解 tab 的 key 来自 `ModelNavKey`，以及为什么切换 tab 会影响 URL query。

5. 然后读 `Overview/index.tsx` 和 `Overview/ProviderList/index.tsx`  
   这是业务信息最密集的部分。重点看 `providers` 的表格列如何从 `record.model` 中取字段。

6. 再读 `Parameter/index.tsx` 和 `ParameterItem.tsx`  
   这部分适合理解“静态配置 + 当前模型字段动态补充”的写法。

7. 最后读 `Related/index.tsx`  
   它很短，主要看如何复用模型列表组件，以及如何构造 more link。

8. 如果还想继续追数据来源，再去看：
   - `src/store/discover/slices/model/action.ts`
   - `src/services/discover.ts`
   - `packages/types/src/discover/models.ts`

## 常见误区

1. 不要把 `Details` 当成数据请求组件  
   它不直接请求模型详情。数据请求发生在上层 `ModelDetailPage`，本目录通过 `useDetailContext()` 消费数据。

2. 不要以为 tab 状态只是 React 本地 state  
   当前 tab 存在 URL query 的 `activeTab` 中。刷新页面、复制链接时，tab 状态可以保留。

3. 不要忽略 `Partial<DiscoverModelDetail>`  
   `DetailProvider` 的 config 类型是 `Partial`，所以子组件必须防御字段缺失。`providers = []`、`record.model?.pricing`、`data?.maxOutput` 都是必要写法。

4. 不要把 `providers` 理解成字符串数组  
   在列表页 `DiscoverModelItem.providers` 是 `string[]`，但详情页 `DiscoverModelDetail.providers` 是 `DiscoverModelDetailProviderItem[]`。详情页 provider 项里还可能带有 `model` 字段。

5. `Parameter` 页不是后端参数 schema 的真实反射  
   当前参数列表是在前端组件中手写的通用说明。只有 `max_tokens` 的范围会参考当前模型的 `maxOutput` 或 `maxDimension`。

6. `Overview` 的价格显示依赖 pricing 工具函数  
   表格不是直接展示 `pricing` 原始对象，而是通过 `getTextInputUnitRate`、`getTextOutputUnitRate` 和 `formatPriceByCurrency` 转换后显示。阅读价格逻辑时要追这些工具函数。

7. `Related` 里的文案和链接可能有复用痕迹  
   它使用了 `assistants.details.related.*` 的 i18n key，并且 more link 指向 `/community/plugin`。根据当前片段推断，这可能是历史复用或产品设计遗留点，不能仅凭文件名断定它一定应该跳到模型列表页。

8. 移动端布局和桌面端布局不同  
   `Details/index.tsx` 在移动端会把内容区改成 `column-reverse`；`Sidebar` 在移动端也只显示操作按钮。因此调试 UI 时不能只看桌面端。

9. `Nav` 桌面端才显示外链  
   移动端 `Nav` 只返回 tab 本身，不展示 Discord、源码、反馈问题这些链接。

10. `ProviderList` 的站内跳转用的是 `react-router-dom` 的 `Link`  
   这里是 SPA 路由跳转，不是 Next.js `next/link`。在 `src/routes` 下阅读页面时，要记住这是 React Router 管理的 SPA 页面。
