# 文件：docs/features/exports/api-exports.mdx

## 一句话定位

`docs/features/exports/api-exports.mdx` 是 Reworkd 文档站里“通过 API 导出数据”的功能说明页，用来告诉用户 API Exports 的适用场景、入口 API、鉴权前置条件，以及如何用 `created_after` 做增量拉取。

## 它暴露/定义了什么

这个文件暴露的是一个 Mintlify/MDX 文档页面，而不是运行时代码模块。它通过 frontmatter 定义页面元信息：`title: API Exports` 和 `description: Export data via our APIs`，供文档站生成标题、SEO 描述和侧边栏展示使用。

正文定义了三类信息：第一，说明客户最常见的数据接入方式是 API endpoints；第二，引导用户先创建 API key，并链接到 `docs/developers/api-keys.mdx` 对应的 `/developers/api-keys` 文档；第三，用 `<CardGroup>` 和 `<Card>` 暴露 “Outputs API” 入口，指向 `/api-reference/public/get-outputs-for-a-scraping-group`，让用户跳转到完整 API reference。最后的 `Getting only new data` 小节定义了增量同步建议：调用方保存上次请求时的精确时间，并在后续请求中通过 `created_after` 查询参数只获取新数据。

## 谁调用它

直接调用者是文档站构建与路由系统。根据 `docs/docs.json`，该页面被注册在 `navigation.tabs[0]` 的 `Documentation` 标签下，位于 `Features -> Exports` 分组中，路径条目是 `features/exports/api-exports`。因此 Mintlify 会把它渲染为文档站中的一个可访问页面。

用户侧入口主要有两个：一是侧边栏导航中的 `Features / Exports / API Exports`；二是 `docs/features/exports/overview.mdx` 中的卡片链接，该页面用 `<Card title="API Exports" ... href="/features/exports/api-exports">` 把用户导向当前文件。根据当前片段推断，`docs/introduction.mdx` 先导向 exports overview，再间接进入本页，依据是搜索结果中 introduction 指向 `/features/exports/overview`。

## 它调用谁

该 MDX 页面“调用”的不是 TypeScript 函数，而是文档组件和文档路由。

它使用 Mintlify 提供的 `<CardGroup>` 与 `<Card>` 组件组织跳转卡片；通过 Markdown 链接引用 `/developers/api-keys`；通过 `href="/api-reference/public/get-outputs-for-a-scraping-group"` 连接到 API Reference 中的 Outputs API 端点页面。API Reference 本身在 `docs/docs.json` 中由 `openapi` 配置驱动，真实 OpenAPI 地址不在本文档中展开，按要求记为 `[URL已移除]`。

它还隐式依赖 API 后端支持 `created_after` 查询参数。当前仓库片段没有展开该 API endpoint 的实现代码，因此关于后端过滤逻辑只能根据文档内容推断：Outputs API 应该支持按创建时间筛选 scraping group 的输出数据。

## 核心流程

用户阅读流程很短但很明确：先进入 API Exports 页面，确认 API 是推荐的数据摄取方式；如果还没有 API key，先跳转到 API key 文档完成组织级 API key 创建，并在请求中使用 `Authorization: Bearer <YOUR-API-KEY>` 形式鉴权；然后点击 “Outputs API” 卡片进入 API Reference，查看 `/api-reference/public/get-outputs-for-a-scraping-group` 的完整参数和响应定义；最后，如果要做持续同步，调用方每天或按固定频率请求一次，并记录本次请求发生的精确 datetime，下一次请求把这个时间作为 `created_after` 参数传入，从而只拉取上次同步后的新增数据。

从产品语义看，它服务的是“持续摄取”而不是“一次性下载”。这一点也被 `docs/features/exports/bulk-exports.mdx` 侧面印证：Bulk Exports 更适合生成某个时间点的完整 JSON/CSV 快照，而 API exports 被描述为多数场景下更推荐的导出方法。

## 关键函数的高层作用

本文件没有定义 JavaScript/TypeScript 函数、类或可复用业务方法，因此不存在传统意义上的“关键函数”。

关键结构可以这样理解：frontmatter 负责页面身份；开头两段负责建立 API Exports 的用途和鉴权前置；`<CardGroup>`/`<Card>` 负责把当前说明页连接到具体 Outputs API 参考文档；`Getting only new data` 小节负责描述增量同步协议，其中最核心的接口约定是 `created_after`。辅助性的 Markdown 链接和组件属性只承担导航作用，不影响业务逻辑本身。

## 修改风险

最高风险是改错 API 路径或参数名。`/api-reference/public/get-outputs-for-a-scraping-group`、`created_after`、`/developers/api-keys` 都是用户按文档操作的关键线索；如果其中任一项与真实 API 或文档路由不一致，会直接导致用户无法鉴权、无法找到接口，或做出错误的增量同步实现。

第二类风险是语义误导。当前页面把 API exports 描述为最常见、通常推荐的摄取方式；`bulk-exports.mdx` 也说多数场景应优先使用 API exports。如果修改本页时弱化或反转这一定位，可能会和 Bulk Exports 页面冲突，造成产品文档口径不一致。

第三类风险是时间同步细节。文档建议记录“发起 API 调用的精确 datetime”，再作为下一次的 `created_after`。如果未来要改成记录“响应中最大 created_at”或使用游标分页，需要同步更新本页、API Reference 和可能存在的 SDK 示例，否则用户可能遇到漏数据或重复数据问题。

第四类风险是 MDX/Mintlify 组件兼容性。`<CardGroup cols={1}>`、`<Card title icon href>` 是文档站渲染依赖的组件语法；随意改成普通 HTML 或错误属性，可能不会影响源码编译之外的业务系统，但会破坏文档站页面展示和导航体验。
