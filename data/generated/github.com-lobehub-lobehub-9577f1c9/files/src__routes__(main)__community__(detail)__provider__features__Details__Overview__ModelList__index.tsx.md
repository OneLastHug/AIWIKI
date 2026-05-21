# 文件：src/routes/(main)/community/(detail)/provider/features/Details/Overview/ModelList/index.tsx

## 它负责什么

这个文件定义了社区 `provider` 详情页里的“模型列表”展示组件 `ModelList`。它不是做数据拉取，也不是做编辑逻辑，而是把 `DetailProvider` 提供的 `models` 以表格形式渲染出来，供用户快速比较一个 provider 支持哪些模型，以及每个模型的能力、上下文长度、最大输出、输入/输出单价等信息。

从实现上看，它是一个纯展示型的客户端组件：

- `use client` 表示它运行在客户端
- `memo` 包裹，减少不必要重渲染
- `useDetailContext()` 从上层上下文拿数据
- `InlineTable` 负责表格布局
- 每一行的主入口和右侧箭头，都跳转到 `/community/model/:id`

## 关键组成

这个组件的核心由几块拼起来：

1. 数据来源  
   `const { models = [] } = useDetailContext();`  
   这里的 `models` 来自 `DetailProvider`，类型上是 `DiscoverProviderDetail` 的部分字段。这个文件本身不关心数据怎么来的，只关心怎么展示。

2. 表格容器  
   外层是 `TooltipGroup` + `Block variant="outlined"`，说明它希望和同页面其他信息块保持一致的视觉语义。真正的表格由 `InlineTable` 渲染，`scroll={{ x: 900 }}` 说明列比较多，横向滚动是预期行为。

3. 第一列：模型名  
   - 用 `ModelIcon` 显示模型头像
   - 显示 `record.displayName` 和 `record.id`
   - 点击整块跳到模型详情页
   - 支持按 `displayName` 排序

4. 能力与规格列  
   - `abilities`：如果没有任何 `true` 值，就显示 `--`，否则用 `ModelInfoTags`
   - `contextWindowTokens`：用 `formatTokenNumber` 格式化
   - `maxOutput`：同样用 token 格式化，并给表头加了 tooltip 解释
   - `inputPrice` / `outputPrice`：先通过 `getTextInputUnitRate`、`getTextOutputUnitRate` 取文本单价，再用 `formatPriceByCurrency` 格式化，最后手动加 `$`

5. 动作列  
   最后一列只有一个右箭头 `ActionIcon`，本质上和第一列的链接一致，都是把用户带到模型详情页。这个设计更像“行内快捷入口”，而不是新增功能按钮。

6. 文案与国际化  
   所有表头标题都来自 `useTranslation('discover')`，说明这个组件依赖 `discover` 命名空间的文案，而不是写死英文。

## 上下游关系

上游关系很清楚：

- [`DetailProvider`](./DetailProvider.tsx) 提供 `DetailContext`
- [`Overview`](../index.tsx) 从同一个 context 里取 `models`，先显示数量标签，再渲染 `ModelList`
- 这个文件再把 `models` 具体展开为表格

根据当前片段推断，整个 provider 详情页应该是先由路由层或页面容器把 provider 详情数据塞进 `DetailProvider config`，然后 `Overview`、`Nav`、`Sidebar` 等子模块按需消费。证据是同目录下多个组件都在使用 `useDetailContext()`，说明这是整页共享状态，而不是局部状态。

下游关系主要有两类：

- UI 组件依赖：`InlineTable`、`ModelIcon`、`ModelInfoTags`、`ActionIcon`
- 工具函数依赖：`formatPriceByCurrency`、`formatTokenNumber`、`getTextInputUnitRate`、`getTextOutputUnitRate`

路由跳转依赖则是：

- `Link` + `urlJoin('/community/model', record.id)`  
  这意味着这里从 provider 视角切到单个 model 视角，形成“provider 详情 -> model 详情”的浏览链路。

## 运行/调用流程

1. 上层页面把 provider 详情数据装入 `DetailProvider`
2. `Overview` 读取 `models`
3. `Overview` 先显示“支持模型数量”的标题标签
4. `Overview` 渲染 `ModelList`
5. `ModelList` 从 `useDetailContext()` 拿到 `models`
6. `InlineTable` 按列定义渲染每个模型
7. 用户点击模型名或右侧箭头，跳转到 `/community/model/:id`

表格内部还有几条隐含流程：

- 排序时，`displayName`、`contextWindowTokens`、`maxOutput`、价格字段都分别走自己的比较函数
- 空值统一显示 `--`
- `abilities` 为空时不展示标签，避免把无意义信息硬塞进界面
- `TooltipGroup` 让一组 tooltip 的交互体验更一致

## 小白阅读顺序

1. 先看 [`DetailProvider.tsx`](./DetailProvider.tsx)  
   搞清楚 `useDetailContext()` 的数据来源和类型边界。

2. 再看 [`Overview/index.tsx`](../index.tsx)  
   理解这个列表在整个详情页里处于什么位置，以及标题和数量是怎么来的。

3. 然后回到这个 `ModelList/index.tsx`  
   按列看：模型名、能力、上下文、最大输出、价格、跳转按钮。

4. 最后追工具函数和组件  
   如果你想知道价格怎么格式化、能力标签长什么样，再去看：
   - `@/utils/format`
   - `@/utils/pricing`
   - `@/components/ModelSelect`
   - `@/components/InlineTable`

## 常见误区

1. 它不是数据获取层  
   这里没有请求接口、没有 SWR、没有状态写入，只是消费 `DetailProvider` 里的 `models`。

2. 它不是 provider 详情页的主逻辑  
   这个文件只负责“模型列表”这一块，页面结构、标题、侧边栏、导航都在别的组件里。

3. `abilities` 不是总会显示  
   只有 `record.abilities` 里存在至少一个 `true` 时才会渲染标签，否则直接显示 `--`。

4. 价格显示并不等于完整计费逻辑  
   这里展示的是文本单价，来自 `pricing` 和单位费率工具函数，不代表后端结算规则的全部。

5. 两个跳转入口是重复但有意的  
   第一列整块可点，最后一列箭头也可点，这不是冗余 bug，而是为了提高表格行的可发现性和可点击性。

6. 排序是前端表格排序，不是服务端排序  
   这意味着它依赖当前 `models` 数组内容，在已有数据范围内做比较，并不会自己重新拉取或重排后端数据。
