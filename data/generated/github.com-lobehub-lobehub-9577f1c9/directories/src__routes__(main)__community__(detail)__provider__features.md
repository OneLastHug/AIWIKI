# 目录：src/routes/(main)/community/(detail)/provider/features

## 它负责什么

这个目录承载“社区 Provider 详情页”的主要前端展示逻辑。它不是数据源，也不是路由入口本身，而是被父级页面 `src/routes/(main)/community/(detail)/provider/index.tsx` 调用的一组详情页组件。

父级页面会从 URL 参数中读取 `slug`，解码成 provider `identifier`，再通过 `useDiscoverStore((s) => s.useProviderDetail)` 获取 provider 详情数据：

- `identifier`
- `name`
- `url`
- `modelsUrl`
- `readme`
- `models`
- `related`
- 以及其他 `DiscoverProviderDetail` 字段

拿到数据后，父级页面用 `DetailProvider` 把详情数据放进 React Context，然后渲染：

- `Header`
- `Details`

所以这个目录的核心职责可以概括为：**消费 Provider 详情数据，并把它组织成头部、标签页详情区、侧边栏操作区、相关 Provider 和相关模型列表。**

它本身不负责发请求，数据获取发生在父级路由页面；它也不直接注册路由，路由由 `src/spa/router` 和 `src/routes` 上层结构负责。

## 关键组成

### `DetailProvider.tsx`

这是整个目录的数据上下文中心。

它定义了：

- `DetailContextConfig = Partial<DiscoverProviderDetail>`
- `DetailContext`
- `DetailProvider`
- `useDetailContext`

父级页面把完整的 provider 详情数据作为 `config` 传入：

```tsx
<DetailProvider config={data}>
  <Header mobile={mobile} />
  <Details mobile={mobile} />
</DetailProvider>
```

目录内大部分组件都通过 `useDetailContext()` 读取当前 provider 数据，而不是层层传 props。这让 `Header`、`ModelList`、`Sidebar` 等组件都能直接拿到同一份详情数据。

需要注意的是，Context 类型是 `Partial<DiscoverProviderDetail>`，所以组件里经常使用默认值，例如：

- `const { models = [] } = useDetailContext()`
- `const { readme = '' } = useDetailContext()`

这说明组件设计上允许部分字段为空，但某些地方仍默认 `identifier`、`name` 等字段存在。根据当前片段推断，正常页面进入时这些字段由 `useProviderDetail` 保证。

### `Header.tsx`

`Header` 是详情页顶部信息区，展示 provider 图标、名称、外链按钮和描述。

它从 Context 读取：

- `identifier`
- `url`
- `modelsUrl`
- `name`

主要 UI：

- `ProviderCombine` 显示 provider 图标
- `@{name}` 显示 provider 名称
- 如果存在 `url` 或 `modelsUrl`，名称和地球图标会链接到外部站点
- GitHub 图标链接到 `[URL已移除]}`
- 描述文案来自 `providers` i18n namespace：`t(`${identifier}.description`)`

这里的 `mobile` 会影响图标尺寸和间距。组件内部也调用 `useResponsive()`，允许外部传入 `mobile` 作为覆盖值。

### `Details/index.tsx`

这是详情主体区域的调度组件。

它负责三件事：

1. 渲染顶部标签导航 `Nav`
2. 根据 `activeTab` 切换展示 `Overview`、`Guide`、`Related`
3. 安排内容区和 `Sidebar` 的响应式布局

`activeTab` 来自 URL query：

```ts
useQueryState('activeTab', {
  clearOnDefault: true,
  defaultValue: ProviderNavKey.Overview,
})
```

因此标签页状态会反映到地址栏中。默认是 `ProviderNavKey.Overview`，默认值会被 `clearOnDefault` 清理掉，避免 URL 中出现冗余 query。

桌面端布局是内容区和侧边栏横向排列；移动端使用 `column-reverse`，让侧边栏相关内容在移动端的位置重新排列。移动端的 `Sidebar` 本身也会简化，只保留操作按钮。

### `Details/Nav.tsx`

`Nav` 是详情页标签栏。

它包含三个逻辑 tab：

- `ProviderNavKey.Overview`：概览
- `ProviderNavKey.Guide`：接入指南 / README
- `ProviderNavKey.Related`：相关 provider

其中 `Guide` tab 对 `BRANDING_PROVIDER` 会被隐藏：

```ts
const showGuideTab = identifier !== BRANDING_PROVIDER;
```

桌面端除了 tabs，还会在右侧显示几个外链：

- Discord 帮助链接：`SOCIAL_URL.discord`
- 查看源码：指向 `src/config/modelProviders/{identifier}.ts`
- 报告问题：GitHub issue 创建页

移动端只返回 tabs 本身，不显示右侧链接区。

### `Details/Overview/index.tsx` 和 `Details/Overview/ModelList/index.tsx`

`Overview` 展示当前 provider 支持的模型数量和模型表格。

`Overview` 本身很薄：

- 从 Context 读取 `models`
- 用 `Title` 显示 `providers.supportedModels`
- 用 `Tag` 显示模型数量
- 渲染 `ModelList`

`ModelList` 是较核心的表格组件，使用 `InlineTable` 展示模型列表。列包括：

- 模型名称和模型 ID
- 模型能力标签 `ModelInfoTags`
- 上下文长度 `contextWindowTokens`
- 最大输出 `maxOutput`
- 输入价格
- 输出价格
- 跳转操作按钮

它依赖的格式化工具包括：

- `formatTokenNumber`
- `formatPriceByCurrency`
- `getTextInputUnitRate`
- `getTextOutputUnitRate`

模型名称和操作按钮都会链接到：

```ts
/community/model/{model.id}
```

所以 provider 详情页和 model 详情页之间通过这里建立了跳转关系。

### `Details/Guide/index.tsx`

`Guide` 展示 provider 的 README 文档。

它从 Context 读取 `readme`：

- 如果没有 `readme`，展示 `Block + Empty`
- 如果有 `readme`，用 `Mdx` 渲染 Markdown/MDX 内容

`Mdx` 配置中关闭了部分能力：

- `enableImageGallery={false}`
- `enableLatex={false}`
- `headerMultiple={0.3}`

这说明这里更偏向轻量的说明文档渲染，而不是完整文档站渲染。

### `Details/Related/index.tsx`

这是详情内容区里的“相关 Provider”列表。

它从 Context 读取 `related`，然后复用列表页的 Provider 列表组件：

```tsx
import List from '../../../../../(list)/provider/features/List';
```

这意味着详情页没有重新实现 provider 卡片列表，而是复用了社区 provider 列表页的 `List`。它设置 `rows={2}`，并通过 `Title` 提供“查看更多”入口，跳转到：

```ts
/community/provider
```

### `Sidebar/index.tsx`

`Sidebar` 是桌面端右侧栏，移动端则简化为只显示操作按钮。

它从 query 中读取 `activeTab`：

```ts
const { activeTab = ProviderNavKey.Overview } = useQuery()
```

桌面端固定宽度 `360`，使用 `ScrollShadow`，并设置 sticky：

```ts
position: 'sticky'
top: 16
maxHeight: 'calc(100vh - 76px)'
```

侧边栏内容根据当前 tab 动态变化：

- 始终显示 `ActionButton`
- 当 `activeTab !== ProviderNavKey.Related` 时显示 `Related`
- 当 `activeTab !== ProviderNavKey.Overview` 时显示 `RelatedModels`

也就是说：

- 在 Overview tab：显示操作按钮 + 相关 Provider
- 在 Guide tab：显示操作按钮 + 相关 Provider + 相关模型
- 在 Related tab：显示操作按钮 + 相关模型

这种设计避免当前主内容和侧边栏展示完全重复的信息。

### `Sidebar/ActionButton`

`ActionButton` 包含两个操作：

- `ProviderConfig`
- `ShareButton`

`ProviderConfig` 是进入 provider 设置页或打开外部站点菜单的按钮。

点击主按钮时：

- Desktop 环境：动态导入 `@/utils/electron/ipc`，调用 `windows.openSettingsWindow({ path: '/settings/provider/{identifier}' })`
- Web 环境：使用 `useNavigate()` 跳转到 `/settings/provider/{identifier}`

如果 provider 有 `url` 或 `modelsUrl`，按钮会以 `Dropdown.Button` 的形式显示，菜单里包含：

- 官方网站
- 模型站点

`ActionButton` 还会构造分享卡片元信息：

- avatar：`ProviderIcon`
- title：provider `name`
- desc：`providers` namespace 下的描述
- tags：最多展示前 4 个模型标签
- url：`OFFICIAL_URL + /community/provider/{identifier}`

这里有一个细节：当前片段中，如果 `url` 和 `modelsUrl` 都不存在，`ProviderConfig` 返回的是普通 `Button`，但没有绑定 `onClick={openSettings}`。阅读时不要默认两个分支行为完全一致；如果要确认是否为刻意设计，需要继续查交互测试或线上行为。

### `Sidebar/Related`

这是侧边栏里的相关 Provider 小列表。

它从 Context 读取 `related`，每项链接到：

```ts
/community/provider/{item.identifier}
```

单项组件 `Item.tsx` 使用：

- `ProviderIcon`
- provider `name`
- `providers` namespace 中的 `${identifier}.description`

与详情内容区的 `Details/Related` 不同，这里是紧凑侧栏卡片，不复用列表页大卡片。

### `Sidebar/RelatedModels`

这是侧边栏里的相关模型列表。

它从 Context 读取：

- `models`
- `identifier`

标题的“更多”链接会跳到模型社区列表，并带上 query：

```ts
/community/model?category={identifier}
```

列表最多展示前 6 个模型，每项链接到：

```ts
/community/model/{model.id}
```

单项组件使用 `ModelIcon`、模型显示名和 `models` namespace 下的 `${id}.description`。

## 上下游关系

上游主要是父级路由页面：

```ts
src/routes/(main)/community/(detail)/provider/index.tsx
```

该页面负责：

1. 从 `react-router-dom` 的 `useParams` 读取 `slug`
2. `decodeURIComponent` 得到 provider `identifier`
3. 调用 `useDiscoverStore` 中的 `useProviderDetail`
4. 处理 loading 和 not found
5. 用 `DetailProvider` 注入详情数据
6. 渲染本目录内的 `Header` 和 `Details`

数据层上游根据当前片段可追踪到：

- `src/store/discover/slices/provider/action.ts`
- `src/services/discover.ts`
- `src/server/services/discover/index.ts`
- `packages/types/src/discover/providers.ts`

由于本次只读取了当前目录和必要邻近上下文，具体服务端如何组装 `DiscoverProviderDetail` 没有展开。根据当前片段推断，`useProviderDetail({ identifier, withReadme: true })` 会返回包含 README、模型列表和相关 provider 的完整详情对象。

下游主要是页面跳转和复用组件：

- 跳转到模型详情：`/community/model/{id}`
- 跳转到 provider 详情：`/community/provider/{identifier}`
- 跳转到 provider 列表：`/community/provider`
- 跳转到模型列表并筛选分类：`/community/model?category={identifier}`
- 跳转到设置页：`/settings/provider/{identifier}`
- 复用列表页 Provider `List`
- 复用社区通用组件 `Title`、`ShareButton`
- 使用全局 UI 组件 `@lobehub/ui`
- 使用图标库 `@lobehub/icons` 和 `lucide-react`

## 运行/调用流程

1. 用户访问某个 provider 详情页，例如 `/community/provider/openai`。

2. 父级 `ProviderDetailPage` 通过 `useParams<{ slug: string }>()` 读取 `slug`，并解码成 `identifier`。

3. 页面从 `useDiscoverStore` 中拿到 `useProviderDetail`，调用：

   ```ts
   useProviderDetail({ identifier, withReadme: true })
   ```

4. 如果 `isLoading` 为 true，渲染 `loading.tsx`，它实际导出的是 `../../components/ListLoading` 中的 `DetailsLoading`。

5. 如果没有 `data`，渲染 `NotFound`。

6. 如果成功拿到数据，父级页面渲染：

   ```tsx
   <DetailProvider config={data}>
     <Flexbox gap={16}>
       <Header mobile={mobile} />
       <Details mobile={mobile} />
     </Flexbox>
   </DetailProvider>
   ```

7. `Header` 从 Context 读取 provider 基本信息，展示图标、名称、外链和描述。

8. `Details` 读取 URL query 中的 `activeTab`。如果没有 query，默认显示 `Overview`。

9. `Nav` 根据 `activeTab` 高亮当前 tab，并在 tab 切换时调用 `setActiveTab` 更新 URL query。

10. 主内容区根据当前 tab 渲染：

    - `Overview`：支持模型表格
    - `Guide`：README / 空状态
    - `Related`：相关 Provider 列表

11. `Sidebar` 同样读取 `activeTab`，根据当前 tab 决定显示哪些侧边栏模块。

12. 用户可以通过侧边栏进行配置、分享、查看相关 provider 或相关模型；也可以通过模型表格跳转到模型详情页。

## 小白阅读顺序

1. 先读父级入口：`src/routes/(main)/community/(detail)/provider/index.tsx`

   重点看数据从哪里来、loading/not found 怎么处理、`DetailProvider` 怎么包住页面。

2. 再读 `features/DetailProvider.tsx`

   理解这个目录为什么很多组件不接收 props，而是直接调用 `useDetailContext()`。

3. 然后读 `features/Header.tsx`

   这是最直观的组件，能快速看到 provider 的基础字段如何被展示。

4. 接着读 `features/Details/index.tsx`

   这是主体布局和 tab 切换的中枢。读懂这里后，就知道 `Overview`、`Guide`、`Related` 三块如何切换。

5. 再读 `features/Details/Nav.tsx`

   重点看 `ProviderNavKey`、`activeTab`、`setActiveTab`，以及为什么 `BRANDING_PROVIDER` 不显示 Guide tab。

6. 继续读 `features/Details/Overview/ModelList/index.tsx`

   这是信息密度最高的展示组件，包含模型跳转、能力标签、价格格式化和排序逻辑。

7. 最后读 `features/Sidebar/index.tsx` 及其子目录

   理解右侧栏如何根据当前 tab 补充操作入口、相关 provider 和相关模型。

## 常见误区

1. **误以为这个目录负责请求数据**

   实际请求在父级 `provider/index.tsx` 中触发。本目录只消费 `DetailProvider` 注入的数据。

2. **误以为 `features` 一定在全局 `src/features` 下**

   这个目录是路由局部的 `features`。在 LobeHub 的新约定里，复杂业务通常建议放到 `src/features/<Domain>`，但这里是已有的 route-local feature 结构。阅读时要以当前代码为准，不要机械套用目录规则。

3. **误以为 tab 状态只存在 React state 中**

   `Details` 使用的是 `useQueryState('activeTab')`，tab 状态会同步到 URL query。刷新页面或复制链接时，tab 状态可以保留。

4. **误以为移动端只是缩小桌面布局**

   移动端逻辑有专门处理：`Details` 会调整 flex 方向，`Sidebar` 在 mobile 下只渲染 `ActionButton`，`Nav` 也不显示桌面端右侧的帮助/源码/问题链接。

5. **误以为 `Guide` tab 永远存在**

   `Nav` 中对 `BRANDING_PROVIDER` 做了特殊判断，这类 provider 不显示 Guide tab。

6. **误以为侧边栏内容固定不变**

   `Sidebar` 会根据 `activeTab` 变化：

   - Overview 时不显示相关模型
   - Related 时不显示相关 Provider
   - Guide 时两者都显示

7. **误以为模型列表只是静态展示**

   `ModelList` 里的多列都支持排序，例如模型名、上下文长度、最大输出、输入价格、输出价格。模型名称和右侧按钮也都能跳转到模型详情页。

8. **误以为所有文案都来自同一个 i18n namespace**

   这里至少用了三个 namespace：

   - `discover`：详情页标题、tab、列表标题等
   - `providers`：provider 描述、配置相关文案
   - `models`：模型描述等

9. **误以为外链都用普通 `<a>`，站内跳转都用 `<Link>`**

   大体上是这样，但 `ProviderConfig` 的下拉菜单里对外部链接使用了 `react-router-dom` 的 `Link target="_blank"`。阅读时要看具体实现，不要只按习惯判断。

10. **误以为 `ProviderConfig` 的两个分支行为一致**

   当前片段中，有外链菜单时使用 `Dropdown.Button`，主按钮点击会打开设置；没有外链菜单时返回普通 `Button`，但未绑定点击处理。根据当前片段只能确认代码如此，是否为预期行为需要结合测试或产品交互继续判断。
