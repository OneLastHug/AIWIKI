# 文件：docs/features/exports/bulk-exports.mdx

## 一句话定位

`docs/features/exports/bulk-exports.mdx` 是 Reworkd 文档站中“Bulk Exports”功能页，负责向用户说明如何通过产品 UI 导出某个 scraping group 或 job 的全量数据快照，并引导用户进入导出页面。

## 它暴露/定义了什么

该文件定义的是一个 Mintlify MDX 文档页面，而不是应用运行时代码。它通过 frontmatter 暴露页面元信息：`title: Bulk Exports` 和 `description: Export data via our UI`，供文档站生成页面标题、侧边栏展示和 SEO/摘要信息使用。

正文层面，它定义了三个核心信息点：Bulk exports 的输出格式是 JSON 或 CSV；导出范围来自 group 或 job，并可按日期过滤；该方式适合获取某个时间点的数据完整快照，但多数场景更推荐 API exports。页面还包含一个 `<Warning>` 提醒大 group 导出可能耗时很久，以及一个 `<CardGroup>` 内的 `<Card>`，指向 Reworkd 的导出 UI。原文件中的真实外部地址在本文档中记为 `[URL已移除]`。

## 谁调用它

直接调用方是文档站构建与路由系统。根据 `docs/docs.json`，`features/exports/bulk-exports` 被注册在 `Documentation` tab 下的 `Features -> Exports` 分组中，因此它会出现在文档导航中。

另外，`docs/features/exports/overview.mdx` 中的 “Bulk Exports” 卡片通过 `href="/features/exports/bulk-exports"` 链接到该页面；用户也可能从侧边栏、搜索或文档站内部路由直接进入。根据当前片段推断，这个文件没有被业务前端或后端代码导入，它主要服务于 Mintlify 文档渲染链路。

## 它调用谁

该页面“调用”的不是代码函数，而是 Mintlify/MDX 提供的文档组件与站点能力。它使用了 `<Warning>` 展示醒目的注意事项，使用 `<CardGroup cols={1}>` 和 `<Card>` 渲染一个单列跳转卡片。`Card` 的 `title`、`icon`、`href` 和子文本共同决定卡片外观、图标和目标页面。

在内容关系上，它与 `docs/features/exports/overview.mdx`、`docs/features/exports/api-exports.mdx` 构成同一功能组：overview 负责总览和分流，api-exports 说明 API 导出，bulk-exports 说明 UI 批量导出。导航由 `docs/docs.json` 统一装配。

## 核心流程

用户进入文档站后，`docs/docs.json` 把该页面挂到 `Features -> Exports` 导航分组。用户可以从侧边栏选择 `Bulk Exports`，也可以先打开 `docs/features/exports/overview.mdx`，再点击 “Bulk Exports” 卡片进入。

页面渲染时，Mintlify 先读取 frontmatter 生成页面标题和描述，然后渲染正文：先解释 bulk exports 的定义，即把 group 或 job 中抓取到的数据导出成 JSON/CSV；再说明用户需要在 UI 中选择 group，并可选 job 或日期作为过滤条件；接着对比 API exports，强调 bulk exports 更适合一次性快照，而不是常规集成；最后渲染 Warning 和导出页面卡片，让用户知道大数据量导出存在耗时风险，并能跳转到产品导出入口。

## 关键函数的高层作用

该文件没有定义 JavaScript/TypeScript 函数，也没有自定义组件实现。这里的“关键函数”应理解为关键 MDX 组件的页面职责。

`<Warning>` 的作用是提升风险提示的可见性，避免用户误以为大 group 导出会即时完成。它承载的是性能和等待时间预期管理。

`<CardGroup>` 用于组织跳转卡片布局；此处 `cols={1}` 表示单列展示，适合只有一个后续操作入口的页面。

`<Card>` 用于呈现“Reworkd Exports Page”入口，结合 `icon="files"` 传达文件导出语义，`href` 指向产品中的 exports 页面。根据当前片段推断，Mintlify 在构建时负责解析这些组件并生成最终 HTML。

## 修改风险

最大风险是导航和链接一致性。若修改文件路径或 slug，需要同步更新 `docs/docs.json` 中的 `features/exports/bulk-exports`，以及 `docs/features/exports/overview.mdx` 里指向 `/features/exports/bulk-exports` 的卡片链接，否则会出现导航缺页或跳转 404。

第二类风险是产品语义漂移。该页面明确说 bulk exports 是 JSON/CSV，范围是 group 或 job，并支持日期过滤；如果后端或 UI 实际能力发生变化，例如新增格式、取消 job 过滤、改变异步处理方式，文档需要同步，否则会误导用户。

第三类风险是推荐路径表达。页面强调多数场景应优先使用 API exports，这和 `docs/features/exports/api-exports.mdx` 的定位一致。若改成强推 bulk exports，可能与 API 文档、开发者集成路径和产品最佳实践冲突。

第四类风险是外部入口。`<Card>` 指向真实产品导出页，若域名、登录流程或 exports 路径变化，应更新该 href；同时文案中最好保留“大 group 可能耗时很久”的提醒，因为这是用户体验和支持成本相关的关键预期。
