# 目录：src/routes/(main)/community/(detail)/model/features/Sidebar

## 它负责什么

`Sidebar` 是社区模型详情页右侧栏的 UI 模块，路径位于 `src/routes/(main)/community/(detail)/model/features/Sidebar`。它不负责拉取模型详情数据，也不负责决定页面主内容展示哪个 tab，而是消费上层已经准备好的模型详情上下文，把“操作按钮”“相关模型”“相关服务商”组合成详情页的侧边区域。

从职责上看，它主要做三件事：

1. 提供模型详情页的主要操作入口：和模型聊天、查看模型使用指南、分享当前模型。
2. 在桌面端展示辅助推荐信息：相关模型列表、相关服务商列表。
3. 根据当前 `activeTab` 和 `mobile` 状态调整侧边栏内容，避免在主内容和侧边栏重复展示同一类信息。

它的默认导出是 `Sidebar` 组件，由 `features/Details/index.tsx` 调用：

```tsx
<Sidebar mobile={mobile} />
```

在桌面端，它渲染为一个宽度 `360px` 的 sticky 滚动侧栏；在移动端，它只保留 `ActionButton`，并且在 `Details` 中通过 `column-reverse` 放到主内容后方。

## 关键组成

### `index.tsx`

这是目录入口，导出默认组件 `Sidebar`。

它导入：

- `Flexbox`、`ScrollShadow`：来自 `@lobehub/ui`，用于布局和滚动阴影。
- `useQuery`：读取 URL query。
- `ModelNavKey`：模型详情页 tab 枚举。
- `ActionButton`：操作按钮区域。
- `Related`：相关模型。
- `RelatedProviders`：相关服务商。

核心逻辑是：

```tsx
const { activeTab = ModelNavKey.Overview } = useQuery() as { activeTab: ModelNavKey };
```

然后根据 `mobile` 和 `activeTab` 做条件渲染。

移动端：

```tsx
if (mobile) {
  return (
    <Flexbox gap={32}>
      <ActionButton />
    </Flexbox>
  );
}
```

桌面端：

```tsx
<ActionButton />
{activeTab !== ModelNavKey.Related && <Related />}
{activeTab !== ModelNavKey.Overview && <RelatedProviders />}
```

这说明：

- 无论哪个 tab，操作按钮都会显示。
- 当前主内容是 `Related` tab 时，侧栏不再显示 `Related`，避免重复。
- 当前主内容是 `Overview` tab 时，侧栏不显示 `RelatedProviders`。
- 当主内容是 `Parameter` tab 时，根据当前片段推断，侧栏会同时显示 `Related` 和 `RelatedProviders`，因为它既不是 `Related`，也不是 `Overview`。

桌面侧栏使用 `ScrollShadow`，并设置：

- `width={360}`
- `maxHeight: calc(100vh - 76px)`
- `position: sticky`
- `top: 16`
- `paddingBottom: 24`

所以它是一个固定宽度、随页面滚动保持在视口内的辅助区域。

### `ActionButton/index.tsx`

`ActionButton` 是侧栏顶部的操作区。它是 client component，使用：

- `ModelIcon`：显示模型头像。
- `ShareButton`：复用社区详情页通用分享按钮。
- `useDetailContext`：读取当前模型详情数据。
- `ChatWithModel`：聊天或跳转指南按钮。
- `OFFICIAL_URL` 和 `urlJoin`：拼出官方分享 URL。

它从 `DetailProvider` 中读取：

```tsx
const { description, providers, displayName, identifier } = useDetailContext();
```

然后渲染：

1. `<ChatWithModel />`
2. `<ShareButton />`

分享元数据包括：

- `avatar`：`ModelIcon`
- `desc`：模型描述
- `hashtags`：服务商名称列表
- `title`：优先使用 `displayName`，否则使用 `identifier`
- `url`：`OFFICIAL_URL + /community/model/{identifier}`

这里可以看出，`ActionButton` 本身不关心数据来源，只依赖 `DetailContext` 中已经存在的模型详情字段。

### `ActionButton/ChatWithModel.tsx`

这是侧栏里行为最复杂的组件。它根据模型是否包含 `lobehub` 服务商，决定按钮行为。

它读取：

```tsx
const { providers = [] } = useDetailContext();
const includeLobeHub = providers.some((item) => item.id === 'lobehub');
const list = providers.filter((provider) => provider.id !== 'lobehub');
```

也就是说：

- `lobehub` 服务商被视为“可以直接聊天”的特殊服务商。
- 其他服务商被转换成“模型指南”下拉项。
- 每个下拉项跳转到 `/community/provider/{provider.id}`。

下拉项结构：

```tsx
{
  icon: <ProviderIcon provider={item.id} size={20} type="avatar" />,
  key: item.id,
  label: (
    <Link to={urlJoin('/community/provider', item.id)}>
      {[item.name, t('models.guide')].join(' ')}
    </Link>
  ),
}
```

它有三种渲染分支：

1. 包含 `lobehub`：

   渲染 `antd` 的 `Dropdown.Button`。主按钮点击后执行：

   ```tsx
   navigate('/agent');
   ```

   下拉菜单中展示其他服务商的指南入口。

2. 不包含 `lobehub`，但只有一个服务商：

   渲染普通 `Link + Button`，直接跳转到该服务商页面。

3. 不包含 `lobehub`，且有多个服务商：

   渲染 `DropdownMenu`，让用户选择服务商指南。

这里的用户意图很清晰：如果当前模型能在 LobeHub 内直接使用，就优先给“聊天”入口；否则引导用户去服务商页面查看使用方式。

需要注意一个边界：如果 `providers` 为空，`items` 也是空数组，当前代码仍会走最后的 `DropdownMenu` 分支，显示一个 `models.guide` 按钮，但没有菜单项。根据当前片段推断，正常数据应当保证模型详情至少有 provider，否则这个 UI 体验会比较弱。

### `Related/index.tsx`

`Related` 展示相关模型列表。

它读取：

```tsx
const { related, category } = useDetailContext();
```

然后渲染一个标题区和列表区。

标题使用上级目录的通用 `Title` 组件：

```tsx
<Title
  more={t('models.details.related.more')}
  moreLink={qs.stringifyUrl({
    query: { category },
    url: '/community/model',
  })}
>
  {t('models.details.related.listTitle')}
</Title>
```

所以“查看更多”链接会跳到 `/community/model?category={category}`，即当前模型同分类的模型列表。

列表部分：

```tsx
related?.map((item, index) => {
  const link = urlJoin('/community/model', item.identifier);
  return (
    <Link key={index} to={link}>
      <Item {...item} />
    </Link>
  );
})
```

每个相关模型会跳转到另一个模型详情页。

### `Related/Item.tsx`

这是相关模型的单个卡片项，类型是 `DiscoverModelItem`。

它展示：

- 模型头像：`ModelIcon`
- 标题：`displayName || identifier`
- 描述：从 `models` i18n namespace 中读取 `${identifier}.description`

也就是说，它不直接使用 `DiscoverModelItem` 里的描述字段，而是根据模型 `identifier` 到 `models` 翻译资源里取描述文本。

样式使用 `createStaticStyles`，主要控制：

- 标题和描述字号都是 `14px`
- 描述使用 `cssVar.colorTextSecondary`
- 标题 hover 时变成 `cssVar.colorLink`
- 描述最多显示 2 行

卡片外层是：

```tsx
<Block horizontal gap={12} padding={12} variant="outlined">
```

所以它是一个横向、带边框的紧凑列表项。

### `RelatedProviders/index.tsx`

`RelatedProviders` 展示当前模型相关的服务商列表。

它读取：

```tsx
const { providers = [] } = useDetailContext();
```

标题区域：

```tsx
<Title more={t('providers.details.related.more')} moreLink="/community/provider">
  {t('providers.details.related.listTitle')}
</Title>
```

列表只取前 6 个：

```tsx
providers.slice(0, 6).map(...)
```

每个服务商跳转到：

```tsx
/community/provider/{provider.id}
```

这里和 `Related` 的差异是：

- `Related` 来自 `related` 字段，跳模型详情。
- `RelatedProviders` 来自 `providers` 字段，跳服务商详情。
- `RelatedProviders` 最多展示 6 个。
- “查看更多”固定跳 `/community/provider`，没有带当前模型相关过滤条件。

### `RelatedProviders/Item.tsx`

这是相关服务商的单个卡片项，类型是 `DiscoverModelDetailProviderItem`。

它展示：

- 服务商头像：`ProviderIcon`
- 标题：`name`
- 描述：从 `providers` i18n namespace 中读取 `${id}.description`

结构和 `Related/Item.tsx` 非常相似，只是图标和翻译 namespace 不同：

- 模型项使用 `ModelIcon` 和 `models`
- 服务商项使用 `ProviderIcon` 和 `providers`

## 上下游关系

上游数据来自模型详情页入口：

`src/routes/(main)/community/(detail)/model/index.tsx`

该页面通过路由参数读取模型标识：

```tsx
const params = useParams<{ slug: string }>();
const identifier = decodeURIComponent(params.slug ?? '');
```

然后从 discover store 获取模型详情：

```tsx
const useModelDetail = useDiscoverStore((s) => s.useModelDetail);
const { data, isLoading } = useModelDetail({ identifier });
```

如果加载中，显示 `Loading`；如果没有数据，显示 `NotFound`；如果有数据，则包裹：

```tsx
<DetailProvider config={data}>
  <Flexbox gap={16}>
    <Header mobile={mobile} />
    <Details mobile={mobile} />
  </Flexbox>
</DetailProvider>
```

`Sidebar` 并不直接调用 `useDiscoverStore`，而是通过：

```tsx
useDetailContext()
```

读取 `DetailProvider` 注入的 `data`。

因此它的数据依赖链是：

```text
URL slug
  -> useDiscoverStore().useModelDetail({ identifier })
  -> DetailProvider config={data}
  -> useDetailContext()
  -> Sidebar / ActionButton / Related / RelatedProviders
```

布局调用链是：

```text
ModelDetailPage
  -> DetailProvider
  -> Details
  -> Sidebar
      -> ActionButton
          -> ChatWithModel
          -> ShareButton
      -> Related
          -> Related/Item
      -> RelatedProviders
          -> RelatedProviders/Item
```

`Sidebar` 的 tab 状态来自 URL query。上层 `Details` 使用：

```tsx
const [activeTab, setActiveTab] = useQueryState('activeTab', {
  clearOnDefault: true,
  defaultValue: ModelNavKey.Overview,
});
```

然后传给 `Nav` 控制主内容：

```tsx
<Nav activeTab={activeTab as ModelNavKey} ... />
```

而 `Sidebar` 自己又通过 `useQuery()` 读取 `activeTab`，用于决定侧栏是否显示 `Related` 或 `RelatedProviders`。

这意味着 `activeTab` 是通过 URL query 在 `Details` 和 `Sidebar` 之间间接同步的，而不是通过 props 显式传递。

## 运行/调用流程

1. 用户访问某个模型详情页，例如：

   ```text
   /community/model/{identifier}
   ```

2. `ModelDetailPage` 从路由参数中取出 `slug`，解码成模型 `identifier`。

3. `useDiscoverStore().useModelDetail({ identifier })` 拉取或读取模型详情数据。

4. 数据存在时，页面用 `DetailProvider config={data}` 包住 `Header` 和 `Details`。

5. `Details` 根据响应式状态和 props 判断是否是移动端：

   ```tsx
   const { mobile = isMobile } = useResponsive();
   ```

6. `Details` 根据 `activeTab` 渲染主内容：

   - `Overview`
   - `Parameter`
   - `Related`

7. `Details` 同时渲染：

   ```tsx
   <Sidebar mobile={mobile} />
   ```

8. `Sidebar` 在移动端只渲染 `ActionButton`。

9. `Sidebar` 在桌面端渲染 sticky 侧栏：

   - 总是显示 `ActionButton`
   - 如果当前 tab 不是 `Related`，显示相关模型
   - 如果当前 tab 不是 `Overview`，显示相关服务商

10. `ActionButton` 内部渲染 `ChatWithModel` 和 `ShareButton`。

11. `ChatWithModel` 根据 `providers` 判断：

   - 有 `lobehub`：主按钮跳 `/agent`，下拉菜单展示其他 provider 指南。
   - 没有 `lobehub` 且只有一个 provider：按钮直接跳对应 provider 页面。
   - 没有 `lobehub` 且多个 provider：按钮打开 provider 指南下拉菜单。

12. 用户点击相关模型或服务商时，通过 `react-router-dom` 的 `Link` 在 SPA 内跳转到对应详情页。

## 小白阅读顺序

建议按这个顺序读：

1. `src/routes/(main)/community/(detail)/model/index.tsx`

   先理解模型详情页的数据是怎么来的。重点看 `useParams`、`useDiscoverStore`、`DetailProvider`。

2. `src/routes/(main)/community/(detail)/model/features/DetailProvider.tsx`

   理解 `useDetailContext()` 是怎么把模型详情数据传给深层组件的。这个文件很短，是理解整个目录数据来源的关键。

3. `src/routes/(main)/community/(detail)/model/features/Details/index.tsx`

   看 `Sidebar` 是在哪里被挂载的，以及它和 `Overview`、`Parameter`、`Related` 主内容之间的关系。

4. `src/routes/(main)/community/(detail)/model/features/Sidebar/index.tsx`

   理解侧栏的总装逻辑：移动端分支、桌面 sticky 布局、按 `activeTab` 条件展示相关模块。

5. `src/routes/(main)/community/(detail)/model/features/Sidebar/ActionButton/index.tsx`

   看操作区如何组合聊天按钮和分享按钮。

6. `src/routes/(main)/community/(detail)/model/features/Sidebar/ActionButton/ChatWithModel.tsx`

   重点理解 provider 列表如何影响按钮行为，这是本目录中业务判断最多的文件。

7. `src/routes/(main)/community/(detail)/model/features/Sidebar/Related/index.tsx` 和 `Related/Item.tsx`

   看相关模型列表如何生成链接、标题、描述。

8. `src/routes/(main)/community/(detail)/model/features/Sidebar/RelatedProviders/index.tsx` 和 `RelatedProviders/Item.tsx`

   对照 `Related` 阅读，会发现两者结构几乎相同，只是数据源、图标、跳转目标和 i18n namespace 不同。

## 常见误区

1. 误以为 `Sidebar` 自己请求数据。

   实际上它不请求数据，只通过 `useDetailContext()` 消费上层 `DetailProvider` 注入的模型详情。真正的数据获取在模型详情页入口 `model/index.tsx` 中完成。

2. 误以为 `mobile` 只是改变样式。

   不是。`mobile` 会改变渲染内容。移动端 `Sidebar` 只返回 `ActionButton`，不会展示 `Related` 和 `RelatedProviders`。

3. 误以为 `Related` 总是在侧栏显示。

   不是。当当前 `activeTab` 是 `ModelNavKey.Related` 时，主内容区已经展示相关模型，侧栏会隐藏 `Related`，避免重复。

4. 误以为 `RelatedProviders` 总是在侧栏显示。

   不是。当当前 `activeTab` 是 `ModelNavKey.Overview` 时，侧栏不显示 `RelatedProviders`。只有在非 Overview 的 tab 下才显示。

5. 误以为 `ChatWithModel` 的按钮永远是“聊天”。

   不是。只有 `providers` 中包含 `id === 'lobehub'` 时，主按钮才是聊天入口，并跳转到 `/agent`。否则按钮文案是 `models.guide`，行为是跳转或下拉选择 provider 指南。

6. 误以为 `lobehub` provider 也会出现在指南下拉菜单中。

   不会。代码中先判断是否包含 `lobehub`，再用：

   ```tsx
   providers.filter((provider) => provider.id !== 'lobehub')
   ```

   把它从下拉项中排除。

7. 误以为相关模型描述来自接口字段。

   `Related/Item.tsx` 中的描述来自 `models` 翻译资源：

   ```tsx
   t(`${identifier}.description`)
   ```

   不是直接从 `DiscoverModelItem` 的某个 `description` 字段读取。

8. 误以为相关服务商描述来自接口字段。

   `RelatedProviders/Item.tsx` 中的描述来自 `providers` 翻译资源：

   ```tsx
   t(`${id}.description`)
   ```

   所以如果服务商 id 没有对应 i18n key，描述文本可能显示异常或 fallback。

9. 误以为 `activeTab` 是从 `Details` 通过 props 传进 `Sidebar` 的。

   实际不是。`Details` 用 `useQueryState` 管理 `activeTab`，`Sidebar` 用 `useQuery` 自己读取 URL query。两者通过 URL query 间接保持一致。

10. 误以为这个目录符合“routes 只放薄页面”的新约定。

   从当前路径看，这些组件仍位于 `src/routes/.../features/Sidebar` 下，包含较多 UI 和业务逻辑。根据仓库说明，新的 SPA 约定更倾向于把业务组件放到 `src/features/`，route tree 保持较薄。这里应理解为现有代码结构，而不是新代码一定要照搬的最佳位置。
