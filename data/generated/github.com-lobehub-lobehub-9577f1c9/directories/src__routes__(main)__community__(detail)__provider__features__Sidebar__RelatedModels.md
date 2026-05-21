# 目录：src/routes/(main)/community/(detail)/provider/features/Sidebar/RelatedModels

## 它负责什么

`RelatedModels` 是 provider 详情页侧边栏里的“相关模型”模块。它的职责很集中：从当前 provider 详情上下文中读取模型列表，只展示前 6 个模型，并把每个模型渲染成可点击卡片，跳转到对应的 model 详情页。

它位于：

`src/routes/(main)/community/(detail)/provider/features/Sidebar/RelatedModels`

这是一个很小的 UI 子目录，只包含两个文件：

- `index.tsx`：模块入口，负责取数据、标题、更多链接、列表渲染和路由跳转。
- `Item.tsx`：单个相关模型卡片，负责展示模型图标、名称和描述。

从位置上看，它不是通用组件，而是 provider 详情页 `Sidebar` 的局部功能组件。

## 关键组成

`index.tsx` 导出默认组件 `Related`，也就是上游以 `RelatedModels` 名称引入的侧边栏模块。

它的主要 import 可以分成几类：

- UI 组件：`Flexbox` 来做纵向布局。
- 路由与 URL 工具：`Link`、`query-string`、`url-join`。
- React 工具：`memo`。
- i18n：`useTranslation('discover')`。
- 本地组件与上下文：`Title`、`useDetailContext`、`Item`。

核心逻辑是：

```tsx
const { models = [], identifier } = useDetailContext();
```

这里从 `DetailProvider` 上下文里拿到当前 provider 的 `models` 和 `identifier`。`models` 是相关模型列表；`identifier` 用来生成“查看更多”的过滤链接。

标题部分使用同级上层的 `Title` 组件：

```tsx
<Title
  more={t('models.details.related.more')}
  moreLink={qs.stringifyUrl({
    query: {
      category: identifier,
    },
    url: '/community/model',
  })}
>
  {t('models.details.related.listTitle')}
</Title>
```

这里有两个关键点：

- 标题文字来自 `discover` namespace 下的 `models.details.related.listTitle`。
- “更多”链接跳到 `/community/model?category=<identifier>`，也就是模型社区页，并按当前 provider/category 过滤。

列表部分只取前 6 个模型：

```tsx
{models?.slice(0, 6)?.map((item, index) => {
  const link = urlJoin('/community/model', item.id);

  return (
    <Link key={index} style={{ color: 'inherit', overflow: 'hidden' }} to={link}>
      <Item {...item} />
    </Link>
  );
})}
```

每个 item 的目标地址是：

`/community/model/<modelId>`

其中 `urlJoin('/community/model', item.id)` 用来避免手工拼接路径时出现多余或缺失的斜杠。

`Item.tsx` 导出默认组件 `RelatedItem`，它接收 `DiscoverProviderDetailModelItem` 类型的数据，目前使用到的字段是：

- `id`
- `displayName`

它的 import 也比较明确：

- `ModelIcon`：根据模型 id 渲染模型头像。
- `Block`、`Flexbox`、`Text`：卡片、布局和文本。
- `createStaticStyles`：定义静态样式。
- `useTranslation('models')`：读取模型描述文案。
- `DiscoverProviderDetailModelItem`：相关模型的数据类型。

`Item.tsx` 的展示结构是：

```tsx
<Block horizontal gap={12} padding={12} variant="outlined">
  <ModelIcon model={id} size={40} type="avatar" />
  <Flexbox flex={1} gap={6}>
    <Text ellipsis as="h2">
      {displayName || id}
    </Text>
    <Text as="p" ellipsis={{ rows: 2 }}>
      {t(`${id}.description`)}
    </Text>
  </Flexbox>
</Block>
```

也就是说，一个相关模型卡片由三部分组成：

- 左侧模型图标：`ModelIcon model={id}`。
- 第一行标题：优先显示 `displayName`，没有则回退到 `id`。
- 第二行描述：从 `models` namespace 中按 `${id}.description` 查 i18n 文案。

样式通过 `createStaticStyles` 创建：

- `title`：14px、500 字重，hover 时变成链接色。
- `desc`：14px、使用 `cssVar.colorTextSecondary`，最多两行省略。

这里使用的是 `createStaticStyles(({ css, cssVar }) => ...)`，符合仓库中偏好的零运行时 CSS-in-JS 风格。

## 上下游关系

上游调用方是 provider 详情页的侧边栏：

`src/routes/(main)/community/(detail)/provider/features/Sidebar/index.tsx`

在 `Sidebar` 中有这样的引用关系：

```tsx
import RelatedModels from './RelatedModels';
```

并且只在特定 tab 条件下渲染：

```tsx
{activeTab !== ProviderNavKey.Overview && <RelatedModels />}
```

这说明 `RelatedModels` 不会在 provider 的 `Overview` tab 中出现，而是在非 Overview 的 tab 下显示。结合旁边逻辑：

```tsx
{activeTab !== ProviderNavKey.Related && <Related />}
{activeTab !== ProviderNavKey.Overview && <RelatedModels />}
```

可以看出侧边栏里可能同时存在两类“相关内容”：

- `Related`：可能是相关 provider 或其他相关实体，根据当前片段无法完全确定。
- `RelatedModels`：明确是当前 provider 下的相关模型列表。

`Sidebar` 本身通过 `useQuery()` 读取 URL query 中的 `activeTab`：

```tsx
const { activeTab = ProviderNavKey.Overview } = useQuery() as { activeTab: ProviderNavKey };
```

因此 `RelatedModels` 是否出现，取决于当前 URL/query 表示的 provider 详情页 tab 状态。

下游方面，`RelatedModels/index.tsx` 调用：

- `Title`：负责模块标题和 “more” 链接展示。
- `Item`：负责每个模型卡片展示。
- `Link`：负责跳转到 `/community/model/<id>`。
- `useDetailContext`：负责提供当前 provider 详情数据。

`Item.tsx` 再往下依赖：

- `ModelIcon`：根据模型 id 找图标。
- `models` i18n namespace：根据模型 id 查描述。

数据来源方面，当前读取到的片段只显示 `useDetailContext()` 来自 `../../DetailProvider`，没有进一步展开 `DetailProvider` 的实现。因此这里可以确定的是：`RelatedModels` 自身不发请求、不调用 service、不管理状态，它只消费上层 provider detail context 已经准备好的 `models` 和 `identifier`。

根据当前片段推断，`DetailProvider` 应该是 provider 详情页上层的数据上下文，负责把 provider 详情数据注入到页面各个子组件中。依据是 `RelatedModels` 直接从 `useDetailContext` 读取 `models`、`identifier`，且组件内部没有其他数据获取逻辑。

## 运行/调用流程

1. 用户进入 provider 详情页。

2. provider 详情页上层通过 `DetailProvider` 或同名上下文准备当前 provider 的详情数据。

3. `Sidebar` 被渲染。

4. `Sidebar` 读取 URL query 中的 `activeTab`。如果没有 `activeTab`，默认使用 `ProviderNavKey.Overview`。

5. 如果是移动端：

```tsx
if (mobile) {
  return (
    <Flexbox gap={32}>
      <ActionButton />
    </Flexbox>
  );
}
```

移动端侧边栏只显示 `ActionButton`，不会显示 `RelatedModels`。

6. 如果是桌面端，`Sidebar` 渲染为一个固定宽度 `360px` 的 `ScrollShadow`，并使用 sticky 定位：

```tsx
position: 'sticky',
top: 16,
maxHeight: 'calc(100vh - 76px)'
```

这表示侧边栏会在页面滚动时保持在视口附近，并且内部可以滚动。

7. 当 `activeTab !== ProviderNavKey.Overview` 时，渲染：

```tsx
<RelatedModels />
```

8. `RelatedModels` 通过 `useDetailContext()` 获取：

```tsx
models = []
identifier
```

如果 `models` 缺失，默认是空数组，因此不会报错，只是不展示模型卡片。

9. `RelatedModels` 渲染标题：

- 标题：`discover:models.details.related.listTitle`
- 更多按钮文字：`discover:models.details.related.more`
- 更多链接：`/community/model?category=<identifier>`

10. `RelatedModels` 对 `models.slice(0, 6)` 做遍历。

每个模型生成一个链接：

```tsx
/community/model/<item.id>
```

然后渲染：

```tsx
<Item {...item} />
```

11. `Item` 渲染单个模型卡片。

模型图标由：

```tsx
<ModelIcon model={id} type="avatar" />
```

决定。

模型名称由：

```tsx
displayName || id
```

决定。

模型描述由：

```tsx
t(`${id}.description`)
```

决定，也就是到 `models` namespace 中找 `<modelId>.description` 这类 key。

## 小白阅读顺序

1. 先看 `Sidebar/index.tsx`

从这里理解 `RelatedModels` 什么时候出现。重点看这几行：

```tsx
const { activeTab = ProviderNavKey.Overview } = useQuery() as { activeTab: ProviderNavKey };
```

以及：

```tsx
{activeTab !== ProviderNavKey.Overview && <RelatedModels />}
```

这样能先建立“这个模块不是页面主体，而是桌面侧边栏的一块内容”的认识。

2. 再看 `RelatedModels/index.tsx`

重点看三件事：

- `useDetailContext()` 提供了什么数据。
- `Title` 的 `moreLink` 怎么拼出来。
- `models.slice(0, 6).map(...)` 怎么生成模型链接。

理解完这个文件，就知道这个目录的主要业务逻辑：从当前 provider 拿相关模型，最多展示 6 个，点击进入模型详情页。

3. 最后看 `RelatedModels/Item.tsx`

这里没有复杂业务，主要是 UI 呈现。重点看：

- `DiscoverProviderDetailModelItem` 类型说明它吃的是 provider detail 下的 model item。
- `ModelIcon model={id}` 说明图标和模型 id 绑定。
- `t(`${id}.description`)` 说明描述文案不是接口字段，而是从 i18n 里按模型 id 查出来的。

4. 如果继续深入，再看 `DetailProvider`

当前片段中 `RelatedModels` 的数据全部来自 `useDetailContext`。如果想知道 `models`、`identifier` 是接口返回、静态配置还是组合计算出来的，需要继续阅读：

`src/routes/(main)/community/(detail)/provider/features/Sidebar/../../DetailProvider`

也就是 provider 详情页的 `DetailProvider` 实现。

## 常见误区

1. 误以为 `RelatedModels` 自己请求数据

这个目录没有 service 调用、没有 SWR、没有 zustand action，也没有 tRPC 调用。它只是消费 `useDetailContext()` 提供的 `models` 和 `identifier`。数据获取发生在更上层。

2. 误以为它在所有 provider 详情 tab 都显示

不是。`Sidebar` 里明确限制：

```tsx
activeTab !== ProviderNavKey.Overview
```

所以在 `Overview` tab 不显示 `RelatedModels`。并且移动端 `Sidebar` 只显示 `ActionButton`，也不会显示这个模块。

3. 误以为“更多”链接进入 provider 页面

“更多”链接不是 provider 详情页，而是模型社区列表页：

```tsx
/community/model?category=<identifier>
```

也就是说，它把当前 provider 的 `identifier` 当成模型列表页的 `category` 查询参数。

4. 误以为卡片描述来自 `models` 数据项

`Item.tsx` 只从 props 中解构了 `id` 和 `displayName`。描述来自：

```tsx
t(`${id}.description`)
```

所以如果某个模型描述不显示或显示 key，本质上更可能是 `models` i18n namespace 缺少对应 `<id>.description`，而不是接口少返回了 description 字段。

5. 误以为列表会展示全部模型

这里只展示：

```tsx
models?.slice(0, 6)
```

所以最多 6 个。要看完整列表，需要点击 “more” 跳到 `/community/model?category=<identifier>`。

6. 误以为 `key={index}` 代表模型没有稳定 id

这里虽然 `Link` 使用了 `key={index}`，但模型本身是有 `item.id` 的，并且跳转地址也基于 `item.id`。这里只能说明当前实现使用数组下标作为 React key，不代表数据模型缺少唯一标识。

7. 误以为 `RelatedModels` 是通用模型列表组件

它强依赖 provider 详情页上下文：

```tsx
useDetailContext()
```

并且路径也在 provider sidebar 内部。因此它更像 provider detail 的局部组件，不适合直接拿去其他页面复用。
