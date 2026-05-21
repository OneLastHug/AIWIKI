# 目录：src/routes/(main)/community/(detail)/provider/features/Sidebar

## 它负责什么

`Sidebar` 是社区页里“模型服务商详情页”的右侧辅助栏组件，目标页面路径属于：

`src/routes/(main)/community/(detail)/provider`

它不负责拉取数据，也不负责决定当前 provider 是谁；它只消费上层 `DetailProvider` 注入的服务商详情数据，并根据当前详情页的 tab 状态渲染辅助操作和推荐内容。

从职责上看，这个目录主要做三件事：

1. 提供服务商操作区：配置当前 provider、打开 provider 官网/模型页、分享当前 provider。
2. 提供相关 provider 列表：展示同类或推荐的其他服务商。
3. 提供相关 model 列表：展示当前 provider 下的部分模型，并跳转到模型详情页。

在桌面端，它表现为一个固定宽度、可滚动、sticky 的右侧栏；在移动端，它只保留顶部操作按钮区，不展示“相关服务商”和“相关模型”列表。

## 关键组成

这个目录的直接结构是：

```text
Sidebar/
├── index.tsx
├── ActionButton/
│   ├── index.tsx
│   └── ProviderConfig.tsx
├── Related/
│   ├── index.tsx
│   └── Item.tsx
└── RelatedModels/
    ├── index.tsx
    └── Item.tsx
```

`Sidebar/index.tsx` 是目录入口组件。

它从 `useQuery()` 中读取 URL query 里的 `activeTab`，默认值是 `ProviderNavKey.Overview`。然后根据 `mobile` 参数分支渲染：

```tsx
const { activeTab = ProviderNavKey.Overview } = useQuery() as { activeTab: ProviderNavKey };
```

移动端只渲染：

```tsx
<ActionButton />
```

桌面端渲染：

```tsx
<ActionButton />
{activeTab !== ProviderNavKey.Related && <Related />}
{activeTab !== ProviderNavKey.Overview && <RelatedModels />}
```

这意味着不同 tab 下右侧栏会有不同内容：

| 当前 tab | Sidebar 内容 |
| --- | --- |
| `Overview` | 操作按钮 + 相关 provider |
| `Guide` | 操作按钮 + 相关 provider + 相关 models |
| `Related` | 操作按钮 + 相关 models |

这个逻辑避免了页面主体和侧边栏展示完全重复的信息。例如当前主内容已经在看“Related provider”时，侧边栏就不再展示 `Related`；当前主内容是 Overview 时，也不急着展示模型列表。

`ActionButton/index.tsx` 是操作区容器。

它从 `useDetailContext()` 中读取：

```tsx
const { models = [], identifier, name } = useDetailContext();
```

然后组合两个组件：

1. `ProviderConfig`
2. `ShareButton`

`ShareButton` 接收一组 `meta` 信息，用来生成分享卡片或分享内容：

```tsx
meta={{
  avatar: <ProviderIcon provider={identifier} size={64} type={'avatar'} />,
  desc: t(`${identifier}.description`),
  tags: ...,
  title: name,
  url: urlJoin(OFFICIAL_URL, '/community/provider', identifier as string),
}}
```

这里的 `tags` 会取当前 provider 的前几个模型，用 `ModelTag` 展示；如果模型数量较多，还会显示一个 `+N` 的 `Tag`。

需要注意一个细节：代码里是 `models.slice(0, 4)`，但数量提示是：

```tsx
{models.length > 3 && <Tag>+{models.length - 3}</Tag>}
```

也就是说，展示数量和 `+N` 的计算基准并不完全一致。根据当前片段推断，这可能是为了最多展示 4 个标签，但 `+N` 逻辑沿用了“展示 3 个后显示剩余数”的写法。阅读时不要把它理解成严格的模型总数展示规则。

`ActionButton/ProviderConfig.tsx` 是“配置 provider”按钮。

它从详情上下文读取：

```tsx
const { url, modelsUrl, identifier } = useDetailContext();
```

核心交互是 `openSettings`：

```tsx
const openSettings = async () => {
  if (isDesktop) {
    const { ensureElectronIpc } = await import('@/utils/electron/ipc');
    await ensureElectronIpc().windows.openSettingsWindow({
      path: `/settings/provider/${identifier}`,
    });
    return;
  }
  navigate(`/settings/provider/${identifier}`);
};
```

这里区分了桌面端和 Web 端：

- 桌面端：通过 Electron IPC 打开设置窗口，路径是 `/settings/provider/${identifier}`。
- Web/SPA：通过 `react-router-dom` 的 `navigate` 跳转到设置页。

如果 provider 没有 `url` 和 `modelsUrl`，组件会退化为一个普通 `Button`：

```tsx
<Button block size={'large'} style={{ flex: 1 }} type={'primary'}>
  {t('providers.config')}
</Button>
```

如果存在 `url` 或 `modelsUrl`，则渲染 `Dropdown.Button`：

- 主按钮点击：进入 provider 配置页。
- 下拉菜单：打开官网或模型站点。
- 下拉项使用 `Link target="_blank"` 外链打开。

这里的文案来自 `discover` 命名空间，例如：

```tsx
t('providers.config')
t('providers.officialSite')
t('providers.modelSite')
```

`Related/index.tsx` 展示相关服务商列表。

它从 `useDetailContext()` 读取：

```tsx
const { related } = useDetailContext();
```

标题使用共享组件 `Title`：

```tsx
<Title more={t('providers.details.related.more')} moreLink={'/community/provider'}>
  {t('providers.details.related.listTitle')}
</Title>
```

每个 related provider 会跳转到：

```tsx
/community/provider/{item.identifier}
```

构造方式是：

```tsx
const link = urlJoin('/community/provider', item.identifier);
```

列表项 UI 由 `Related/Item.tsx` 负责。它接收 `DiscoverProviderItem` 类型的数据，主要用到：

```tsx
identifier
name
```

渲染内容包括：

- `ProviderIcon`：服务商头像。
- `name`：服务商名称。
- `t(`${identifier}.description`)`：服务商描述，来自 `providers` i18n 命名空间。

样式上使用 `createStaticStyles`，标题和描述都限制为紧凑字号；描述支持两行省略：

```tsx
ellipsis={{ rows: 2 }}
```

`RelatedModels/index.tsx` 展示当前 provider 下的相关模型。

它从 `useDetailContext()` 读取：

```tsx
const { models = [], identifier } = useDetailContext();
```

标题的 “more” 链接会跳到模型社区列表，并带上 category query：

```tsx
qs.stringifyUrl({
  query: {
    category: identifier,
  },
  url: '/community/model',
})
```

也就是类似：

```text
/community/model?category=openai
```

列表只取前 6 个模型：

```tsx
models?.slice(0, 6)?.map(...)
```

每个模型跳转到：

```tsx
/community/model/{item.id}
```

`RelatedModels/Item.tsx` 接收 `DiscoverProviderDetailModelItem`，主要使用：

```tsx
id
displayName
```

渲染内容包括：

- `ModelIcon`：模型头像。
- `displayName || id`：优先展示模型显示名，没有则展示模型 id。
- `t(`${id}.description`)`：模型描述，来自 `models` i18n 命名空间。

## 上下游关系

上游数据入口在 provider detail 页面：

`src/routes/(main)/community/(detail)/provider/index.tsx`

该页面通过 URL 参数拿到 provider 标识：

```tsx
const params = useParams<{ slug: string }>();
const identifier = decodeURIComponent(params.slug ?? '');
```

然后从 `useDiscoverStore` 取出 `useProviderDetail`：

```tsx
const useProviderDetail = useDiscoverStore((s) => s.useProviderDetail);
const { data, isLoading } = useProviderDetail({ identifier, withReadme: true });
```

页面根据数据状态渲染：

- `isLoading`：显示 `Loading`
- `!data`：显示 `NotFound`
- 有数据：用 `DetailProvider` 包住详情页

```tsx
<DetailProvider config={data}>
  <Flexbox gap={16}>
    <Header mobile={mobile} />
    <Details mobile={mobile} />
  </Flexbox>
</DetailProvider>
```

`Sidebar` 的直接调用方是：

`src/routes/(main)/community/(detail)/provider/features/Details/index.tsx`

`Details` 负责读取和维护当前 tab：

```tsx
const [activeTab, setActiveTab] = useQueryState('activeTab', {
  clearOnDefault: true,
  defaultValue: ProviderNavKey.Overview,
});
```

然后渲染：

```tsx
<Nav activeTab={activeTab as ProviderNavKey} mobile={mobile} setActiveTab={setActiveTab} />
...
<Sidebar mobile={mobile} />
```

也就是说，`Sidebar` 本身没有接收 `activeTab` prop，而是自己通过 `useQuery()` 再读一次 URL query。`Details` 和 `Sidebar` 之间通过 URL query 间接同步状态。

中间的数据上下文由：

`src/routes/(main)/community/(detail)/provider/features/DetailProvider.tsx`

提供。

它定义了：

```tsx
export type DetailContextConfig = Partial<DiscoverProviderDetail>;

export const DetailContext = createContext<DetailContextConfig>({});
```

然后：

```tsx
export const DetailProvider = memo<{ children: ReactNode; config?: DetailContextConfig }>(
  ({ children, config = {} }) => {
    return <DetailContext value={config}>{children}</DetailContext>;
  },
);
```

消费方式是：

```tsx
export const useDetailContext = () => {
  return use(DetailContext);
};
```

`Sidebar` 及其子组件都通过 `useDetailContext()` 读取 provider detail 数据，不直接访问 store，也不直接请求接口。

根据当前片段可确认，`Sidebar` 依赖的详情字段至少包括：

```text
identifier
name
url
modelsUrl
models
related
```

根据 `DetailProvider` 的类型定义，它们来自 `DiscoverProviderDetail`。类型定义位于 `packages/types/src/discover/providers.ts`，当前读取片段只确认了该文件中存在：

```text
ProviderNavKey
DiscoverProviderDetailModelItem
DiscoverProviderDetail
```

字段完整定义没有在当前片段中展开，因此字段全集需以该类型文件为准。

下游关系主要是页面导航和 UI 子组件：

| 子组件 | 下游依赖 |
| --- | --- |
| `ProviderConfig` | `/settings/provider/{identifier}` 设置页、Electron settings window、provider 官网/模型站点 |
| `ShareButton` | 社区详情页分享能力 |
| `Related` | `/community/provider/{identifier}` |
| `RelatedModels` | `/community/model/{id}` 和 `/community/model?category={identifier}` |
| `ProviderIcon` / `ModelIcon` / `ModelTag` | `@lobehub/icons` 中的 provider/model 展示体系 |
| `Title` | provider detail 下共享的 section 标题组件 |
| i18n | `discover`、`providers`、`models` 命名空间 |

## 运行/调用流程

一次完整的 provider 详情页访问流程可以按下面理解。

用户访问：

```text
/community/provider/{slug}
```

顶层 `ProviderDetailPage` 从路由参数中解析出 `identifier`：

```tsx
decodeURIComponent(params.slug ?? '')
```

然后调用 discover store 的 `useProviderDetail`，请求 provider 详情数据：

```tsx
useProviderDetail({ identifier, withReadme: true })
```

数据返回后，页面把 `data` 放进 `DetailProvider`：

```tsx
<DetailProvider config={data}>
  ...
</DetailProvider>
```

`Details` 组件读取 URL query 中的 `activeTab`，默认是 `ProviderNavKey.Overview`。它渲染三块内容：

1. `Nav`：顶部 tab 导航。
2. 主内容区域：根据 `activeTab` 显示 `Overview`、`Guide` 或 `Related`。
3. `Sidebar`：右侧栏或移动端操作区。

`Sidebar` 再次读取 `activeTab`。如果是移动端：

```tsx
<Flexbox gap={32}>
  <ActionButton />
</Flexbox>
```

如果是桌面端：

```tsx
<ScrollShadow width={360} ...>
  <ActionButton />
  {activeTab !== ProviderNavKey.Related && <Related />}
  {activeTab !== ProviderNavKey.Overview && <RelatedModels />}
</ScrollShadow>
```

桌面端容器是 `ScrollShadow`，关键样式是：

```tsx
maxHeight: 'calc(100vh - 76px)',
paddingBottom: 24,
position: 'sticky',
top: 16,
```

所以它会在视口内形成一个固定在顶部附近的可滚动侧栏。

`ActionButton` 内部渲染配置按钮和分享按钮。

点击配置按钮时：

- 如果是桌面端，动态 import `@/utils/electron/ipc`，然后打开 settings window。
- 如果不是桌面端，调用 `navigate('/settings/provider/{identifier}')`。

点击下拉菜单时：

- `officialSite` 打开 `url`
- `modelSite` 打开 `modelsUrl`

`ShareButton` 使用 `OFFICIAL_URL + /community/provider/{identifier}` 生成公开分享链接，同时用 provider icon、名称、描述和模型标签组成分享元信息。

`Related` 根据 `related` 数组生成 provider 推荐卡片；点击后跳转到另一个 provider 详情页。

`RelatedModels` 根据 `models` 数组生成模型推荐卡片；点击后跳转到模型详情页。标题上的 more link 会跳到模型社区列表，并用 `category=identifier` 过滤当前 provider。

## 小白阅读顺序

建议按这个顺序读：

1. 先读 `src/routes/(main)/community/(detail)/provider/index.tsx`

   这里能看到 provider 详情页的最外层逻辑：如何从 URL 拿 `slug`，如何通过 `useDiscoverStore` 获取详情数据，以及如何用 `DetailProvider` 包住页面。

2. 再读 `src/routes/(main)/community/(detail)/provider/features/DetailProvider.tsx`

   这个文件很短，但非常关键。它解释了为什么 Sidebar 子组件不需要层层传 props，而是直接 `useDetailContext()` 取数据。

3. 再读 `src/routes/(main)/community/(detail)/provider/features/Details/index.tsx`

   这里能看到详情页整体布局：tab 导航、主内容区域、Sidebar 是如何组合在一起的。尤其要注意 `activeTab` 是通过 `useQueryState('activeTab')` 写进 URL query 的。

4. 再读 `Sidebar/index.tsx`

   这是当前目录入口。重点看两个分支：

   ```tsx
   if (mobile) { ... }
   ```

   以及桌面端根据 `activeTab` 控制 `Related` 和 `RelatedModels` 显隐的条件。

5. 再读 `ActionButton/index.tsx` 和 `ActionButton/ProviderConfig.tsx`

   这两个文件解释“配置”和“分享”如何工作。尤其是 `ProviderConfig` 里 Web 和 Desktop 的分支：

   ```tsx
   if (isDesktop) { ... } else { navigate(...) }
   ```

6. 最后读 `Related` 和 `RelatedModels`

   这两组代码结构几乎平行：

   - `index.tsx` 负责标题、列表、链接。
   - `Item.tsx` 负责单个卡片 UI。
   - provider 用 `ProviderIcon` 和 `providers` 文案。
   - model 用 `ModelIcon` 和 `models` 文案。

## 常见误区

第一个误区是把 `Sidebar` 当成数据请求组件。

它不是。数据请求发生在 provider 详情页顶层：

```tsx
useProviderDetail({ identifier, withReadme: true })
```

`Sidebar` 只消费 `DetailProvider` 里的数据。

第二个误区是以为 `Sidebar` 的 tab 状态来自 props。

实际上 `Sidebar` 的 props 只有：

```tsx
{ mobile?: boolean }
```

它自己通过 `useQuery()` 读取 `activeTab`。而 `Details` 里通过 `useQueryState('activeTab')` 更新 URL query。两者通过 URL query 间接同步。

第三个误区是忽略移动端行为。

移动端 `Sidebar` 只显示 `ActionButton`，不会显示相关 provider 和相关 model。因为 `Details` 在移动端会改变布局方向：

```tsx
style={mobile ? { flexDirection: 'column-reverse' } : undefined}
```

所以小屏场景下 Sidebar 更像“操作区”，不是完整侧栏。

第四个误区是认为 `Related` 和 `RelatedModels` 总是同时展示。

桌面端展示逻辑和当前 tab 有关：

```tsx
{activeTab !== ProviderNavKey.Related && <Related />}
{activeTab !== ProviderNavKey.Overview && <RelatedModels />}
```

当前主内容如果已经是 Related，就隐藏侧边栏的 Related；当前主内容是 Overview，就隐藏侧边栏的 RelatedModels。

第五个误区是混淆 provider 描述和 model 描述的 i18n 命名空间。

provider 相关描述来自 `providers`：

```tsx
t(`${identifier}.description`)
```

model 相关描述来自 `models`：

```tsx
t(`${id}.description`)
```

而按钮、标题等页面文案多来自 `discover`：

```tsx
t('providers.config')
t('providers.details.related.listTitle')
t('models.details.related.listTitle')
```

第六个误区是把 `ProviderConfig` 的下拉菜单当成配置入口。

`Dropdown.Button` 的主按钮点击才是配置入口：

```tsx
onClick={openSettings}
```

下拉菜单只是外链入口，包括官网和模型站点。没有外链时，组件会退化成普通主按钮，但根据当前片段看，退化后的普通按钮没有绑定 `onClick={openSettings}`。如果用户发现“无外链 provider 的配置按钮无法点击”，这里会是需要重点检查的位置；不过是否为真实 bug，还要结合实际 provider 数据判断。
