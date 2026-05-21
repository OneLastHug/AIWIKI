# 目录：src/routes/(main)/community/(detail)/model/features/Sidebar/RelatedProviders

## 它负责什么

`RelatedProviders` 是社区模型详情页右侧栏里的“相关服务提供商 / Supported providers”列表组件。它读取当前模型详情上下文里的 `providers` 数据，把支持该模型的 provider 以卡片列表形式展示出来，并把每一项链接到对应的 provider 详情页：

```txt
/community/provider/{providerId}
```

它本身不负责请求数据、不负责筛选模型、不负责维护状态，只做三件事：

1. 从 `DetailProvider` 提供的模型详情上下文中取出 `providers`。
2. 最多展示前 6 个 provider。
3. 渲染 provider 图标、名称、描述，并提供跳转链接。

这个目录属于 `src/routes/(main)/community/(detail)/model/...` 下的路由内功能片段，位置比较深，说明它是“模型详情页 Sidebar 的局部 UI”，不是全局通用组件。

## 关键组成

该目录只有两个文件：

```txt
RelatedProviders/
├── index.tsx
└── Item.tsx
```

`index.tsx` 是列表入口组件，默认导出 `Related`：

```ts
export default Related;
```

它的关键依赖包括：

- `Flexbox`：来自 `@lobehub/ui`，用于纵向布局。
- `useTranslation('discover')`：读取 discover 命名空间下的标题和 “more” 文案。
- `Link`：来自 `react-router-dom`，用于 SPA 内部跳转。
- `urlJoin`：拼接 provider 详情页路径。
- `Title`：来自上层 `features/Title`，用于侧边栏区块标题。
- `useDetailContext`：来自 `../../DetailProvider`，读取当前模型详情上下文。
- `Item`：同目录的 provider 卡片组件。

核心逻辑很短：

```tsx
const { providers = [] } = useDetailContext();

providers.slice(0, 6).map((item, index) => {
  const link = urlJoin('/community/provider', item.id);

  return (
    <Link key={index} to={link}>
      <Item {...item} />
    </Link>
  );
});
```

这里有几个重点：

- `providers = []` 是兜底，避免上下文里没有 providers 时渲染报错。
- `slice(0, 6)` 表示侧边栏只展示最多 6 个 provider。
- `urlJoin('/community/provider', item.id)` 生成详情页路由。
- `Link` 外层设置了 `color: 'inherit'` 和 `overflow: 'hidden'`，避免链接默认颜色破坏卡片样式。
- 标题使用：
  - `t('providers.details.related.listTitle')`
  - `t('providers.details.related.more')`
- `moreLink` 固定指向 `/community/provider`，也就是 provider 社区列表页。

`Item.tsx` 是单个 provider 卡片组件，默认导出 `RelatedItem`：

```ts
export default RelatedItem;
```

它接收的 props 类型是：

```ts
DiscoverModelDetailProviderItem
```

从当前代码片段可以确定它至少使用了两个字段：

```ts
({ id, name })
```

因此该类型至少包含：

```ts
id: string;
name: string;
```

根据当前片段推断，`DiscoverModelDetailProviderItem` 应该是模型详情数据里 `providers` 数组的元素类型，来源于 `@/types/discover`。本次读取中没有看到类型定义原文，因此字段全集不能完全确认。

`Item.tsx` 的 UI 结构是：

```tsx
<Block horizontal gap={12} padding={12} variant="outlined">
  <ProviderIcon provider={id} size={40} type="avatar" />
  <Flexbox>
    <Text as="h2">{name}</Text>
    <Text as="p">{t(`${id}.description`)}</Text>
  </Flexbox>
</Block>
```

其中：

- `ProviderIcon` 来自 `@lobehub/icons`，根据 provider id 渲染头像图标。
- `Block`、`Flexbox`、`Text` 来自 `@lobehub/ui`。
- `useTranslation('providers')` 读取 provider 描述文案。
- 描述文案 key 是动态拼出来的：`${id}.description`。
- 标题和描述都设置了 `ellipsis`，避免侧边栏文字过长撑破布局。
- 样式使用 `createStaticStyles`，符合仓库中偏好的零运行时 CSS-in-JS 风格。

`Item.tsx` 中定义了两个样式类：

```ts
title
desc
```

`title`：

- 字号 14px。
- 字重 500。
- hover 时变成 `cssVar.colorLink`。

`desc`：

- 字号 14px。
- 使用 `cssVar.colorTextSecondary`。
- 在 UI 上最多显示两行。

## 上下游关系

上游数据来自模型详情页的 `DetailProvider`。

相关文件是：

```txt
src/routes/(main)/community/(detail)/model/features/DetailProvider.tsx
```

`DetailProvider` 创建了一个 React context：

```ts
export type DetailContextConfig = Partial<DiscoverModelDetail>;

export const DetailContext = createContext<DetailContextConfig>({});
```

然后通过：

```ts
export const useDetailContext = () => {
  return use(DetailContext);
};
```

让子组件读取模型详情数据。

`RelatedProviders/index.tsx` 正是通过这个 hook 获取数据：

```ts
const { providers = [] } = useDetailContext();
```

所以 `RelatedProviders` 的直接上游不是 service、store 或请求函数，而是 `DetailProvider` 注入的 `config`。至于 `config` 的原始数据从哪里请求，本目录没有体现；根据当前片段推断，它应该在模型详情页更上层加载 `DiscoverModelDetail` 后包进 `DetailProvider`。

直接调用方是：

```txt
src/routes/(main)/community/(detail)/model/features/Sidebar/index.tsx
```

该文件中导入：

```ts
import RelatedProviders from './RelatedProviders';
```

并在桌面侧边栏里条件渲染：

```tsx
{activeTab !== ModelNavKey.Overview && <RelatedProviders />}
```

这说明它不是所有 tab 都显示。当前模型详情页的侧边栏逻辑大致是：

```tsx
<ActionButton />
{activeTab !== ModelNavKey.Related && <Related />}
{activeTab !== ModelNavKey.Overview && <RelatedProviders />}
```

也就是说：

- `Overview` tab 下不显示 `RelatedProviders`。
- 非 `Overview` tab 下显示 `RelatedProviders`。
- 移动端 `mobile` 模式下，Sidebar 只显示 `ActionButton`，不显示相关模型或相关 provider。

下游关系主要是两个页面跳转：

1. 点击标题右侧的 more：

```txt
/community/provider
```

进入 provider 列表页。

2. 点击单个 provider 卡片：

```txt
/community/provider/{id}
```

进入 provider 详情页。

此外，`Item.tsx` 还依赖 `providers` i18n 命名空间里的描述文案：

```ts
t(`${id}.description`)
```

这意味着 provider id 必须能对应到 `providers` 翻译资源里的 key。否则 UI 上可能显示原始 key 或 fallback 文案。

## 运行/调用流程

一次完整渲染流程可以按下面理解：

1. 模型详情页上层拿到某个模型的详情数据。

2. 上层把详情数据作为 `config` 传给 `DetailProvider`：

```tsx
<DetailProvider config={modelDetail}>
  ...
</DetailProvider>
```

根据当前片段推断，`modelDetail` 的类型接近 `DiscoverModelDetail`，其中包含 `providers` 字段。

3. `Sidebar` 被渲染。

4. `Sidebar` 通过 `useQuery()` 读取 URL 查询参数里的 `activeTab`：

```ts
const { activeTab = ModelNavKey.Overview } = useQuery() as { activeTab: ModelNavKey };
```

5. 如果是移动端：

```tsx
if (mobile) {
  return <ActionButton />;
}
```

此时不会调用 `RelatedProviders`。

6. 如果是桌面端，Sidebar 渲染为一个固定宽度 360px 的 `ScrollShadow`，并根据当前 tab 判断是否展示 `RelatedProviders`：

```tsx
{activeTab !== ModelNavKey.Overview && <RelatedProviders />}
```

7. `RelatedProviders` 通过 `useDetailContext()` 读取上下文：

```ts
const { providers = [] } = useDetailContext();
```

8. 组件渲染区块标题：

```tsx
<Title more={t('providers.details.related.more')} moreLink="/community/provider">
  {t('providers.details.related.listTitle')}
</Title>
```

9. 组件取前 6 个 provider：

```ts
providers.slice(0, 6)
```

10. 每个 provider 生成链接：

```ts
const link = urlJoin('/community/provider', item.id);
```

11. 每个 provider 交给 `Item` 渲染：

```tsx
<Item {...item} />
```

12. `Item` 内部用 `id` 渲染图标和描述：

```tsx
<ProviderIcon provider={id} />
{t(`${id}.description`)}
```

最终用户看到的是一个右侧栏小列表：标题、more 链接、最多 6 个 provider 卡片。

## 小白阅读顺序

建议按这个顺序读：

1. 先看 `Sidebar/index.tsx`

理解 `RelatedProviders` 在哪里出现。重点看这句：

```tsx
{activeTab !== ModelNavKey.Overview && <RelatedProviders />}
```

这能先建立“它是侧边栏的一部分，并且只在部分 tab 出现”的概念。

2. 再看 `RelatedProviders/index.tsx`

这是目录入口。重点看三件事：

```ts
const { providers = [] } = useDetailContext();
```

```ts
providers.slice(0, 6)
```

```ts
urlJoin('/community/provider', item.id)
```

读完这三个点，就知道它的数据来源、数量限制和跳转目标。

3. 再看 `RelatedProviders/Item.tsx`

理解单个 provider 卡片长什么样。重点看：

```tsx
<ProviderIcon provider={id} />
<Text>{name}</Text>
<Text>{t(`${id}.description`)}</Text>
```

这说明卡片显示的是 provider 图标、名称和本地化描述。

4. 最后看 `DetailProvider.tsx`

理解 `useDetailContext()` 背后只是一个 React context：

```ts
createContext<Partial<DiscoverModelDetail>>({})
```

这能避免误以为 `RelatedProviders` 自己发起了网络请求。

5. 如果继续深入，再去找模型详情页上层哪里包了 `DetailProvider`

本次目标目录只展示了消费数据的部分。真正的数据加载逻辑应该在更上层页面或详情容器中。

## 常见误区

1. 误以为 `RelatedProviders` 会请求 provider 数据

它不会。它只从 `useDetailContext()` 读已经存在的 `providers`。如果页面没有传入 providers，它会用空数组兜底，然后渲染为空列表。

2. 误以为这里展示的是“相关 provider 推荐算法”

不是。这里没有排序、搜索、推荐算法。它只是取模型详情数据里的 `providers` 前 6 个：

```ts
providers.slice(0, 6)
```

如果顺序有业务含义，也应该来自上游数据，而不是这个组件内部计算。

3. 误以为所有 tab 都显示这个模块

不是。`Sidebar` 里明确写了：

```tsx
activeTab !== ModelNavKey.Overview
```

所以 `Overview` tab 下不会显示 `RelatedProviders`。

4. 误以为移动端也显示

不是。`Sidebar` 在 `mobile` 为 true 时只渲染 `ActionButton`，不会渲染 `Related` 或 `RelatedProviders`。

5. 忽略 i18n 命名空间差异

`RelatedProviders/index.tsx` 用的是：

```ts
useTranslation('discover')
```

用于标题和 more 文案。

`Item.tsx` 用的是：

```ts
useTranslation('providers')
```

用于 provider 描述：

```ts
t(`${id}.description`)
```

所以维护文案时要注意两个 namespace，不要把 key 加错地方。

6. 把 `key={index}` 当作 provider id

列表外层 `Link` 当前使用的是 `key={index}`，而不是 `key={item.id}`。这只是 React 列表 key，不参与业务跳转。真正的 provider id 用在：

```ts
urlJoin('/community/provider', item.id)
```

以及：

```tsx
<ProviderIcon provider={id} />
```

7. 误以为 `Item` 可以脱离 provider 翻译资源独立使用

`Item` 的描述依赖：

```ts
t(`${id}.description`)
```

如果传入的 `id` 没有对应的 `providers` 翻译 key，描述区域可能不会显示预期文本。因此它更适合渲染仓库已知 provider，而不是任意外部 provider。
