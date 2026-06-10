# 文件：docs/features/exports/overview.mdx

## 一句话定位

`docs/features/exports/overview.mdx` 是 Reworkd 文档站中 “Exports” 功能组的入口概览页，职责不是解释具体导出机制，而是把用户从“导出数据”这个高层主题分流到两条实际路径：`API Exports` 和 `Bulk Exports`。

## 它暴露/定义了什么

这个文件定义了一个 Mintlify/MDX 文档页面，包含三部分核心内容：

第一，frontmatter 元信息：`title: Exports Overview`、`sidebarTitle: Overview`、`description: Exporting your data out of Reworkd`。这些字段会被文档框架用于页面标题、侧边栏展示名、搜索/SEO 摘要或页面预览描述。

第二，一个 `CardGroup cols={2}` 容器，用两列卡片展示导出方式。它没有正文段落，也没有步骤说明，说明该页被设计成“导航页”而不是“教程页”。

第三，两个 `Card` 入口：一个指向 `/features/exports/api-exports`，介绍通过 API 动态导出 group 数据；另一个指向 `/features/exports/bulk-exports`，介绍通过 UI 创建整个 group 的单文件导出。

## 谁调用它

从仓库当前片段看，调用它的主要是文档站配置和其他文档页面，而不是应用运行时代码。

`docs/docs.json` 在 Documentation 标签页下的 Features 分组中声明了一个子分组 `Exports`，其 pages 列表包含 `features/exports/overview`、`features/exports/api-exports`、`features/exports/bulk-exports`。这意味着文档构建系统会把 `overview.mdx` 注册进侧边栏导航，并把它作为 Exports 分组下的第一页。

`docs/introduction.mdx` 中也有一张标题为 `Exporting data` 的卡片，`href` 指向 `/features/exports/overview`。因此首页/介绍页会把想了解数据导出的用户引导到这个概览页。

根据当前片段推断，真正“调用”该文件的是 Mintlify 文档框架的路由、侧边栏和 MDX 渲染流程；依据是仓库存在 `docs/docs.json` 的 Mintlify 配置，以及页面使用了 Mintlify 常见的 `CardGroup`、`Card`、`Warning` 等组件。

## 它调用谁

该文件通过 MDX 组件间接依赖文档框架提供的 `CardGroup` 和 `Card` 组件。它没有显式 `import`，说明这些组件大概率由 Mintlify 全局注入。

在内容层面，它“调用”或链接到两个下游页面：

`docs/features/exports/api-exports.mdx`：对应 `/features/exports/api-exports`，讲 API 导出方式。该页进一步指向 API Reference 中的 Outputs API，并说明常见增量拉取方式是使用 `created_after` 查询参数。

`docs/features/exports/bulk-exports.mdx`：对应 `/features/exports/bulk-exports`，讲 UI 批量导出。该页说明 Bulk exports 是 JSON 或 CSV 文件，可按 group、job、date 过滤，并提示大 group 导出可能耗时较长。它还包含一个指向 Reworkd 导出页面的外部入口，真实地址在本文档中省略为 `[URL已移除]`。

## 核心流程

用户通常有两条进入路径：一是在文档侧边栏点击 Features 下的 Exports 分组，二是在 `docs/introduction.mdx` 的 `Exporting data` 卡片进入。进入 `overview.mdx` 后，页面只做一次高层选择：如果用户希望持续、程序化地消费数据，应点击 `API Exports`；如果用户想一次性获得某个 group 或 job 的数据快照，应点击 `Bulk Exports`。

从信息架构看，这个文件承担“分岔路口”的角色。它避免在入口页堆叠 API 参数、UI 操作、文件格式等细节，而是把复杂度下沉到两个专题页中。这样的结构也让 `docs/docs.json` 的侧边栏层级更清晰：`overview` 负责概览，`api-exports` 和 `bulk-exports` 负责具体说明。

## 关键函数的高层作用

该文件没有 JavaScript/TypeScript 函数，也没有业务类或可执行逻辑。所谓“关键函数”在这里应理解为关键 MDX 组件的页面职责：

`CardGroup`：负责把导出方式组织成卡片网格。`cols={2}` 表示在支持的视口下以两列呈现，使 API 导出和批量导出成为并列选项，而不是主次关系。

`Card`：负责定义一个可点击的功能入口。每张卡片包含 `title`、`icon`、`href` 和简短描述。`API Exports` 卡片强调通过 APIs 动态导出 group 数据；`Bulk Exports` 卡片强调通过 UI 创建整个 group 的单文件导出。

frontmatter：不是函数，但对该页非常关键。`sidebarTitle: Overview` 让侧边栏名称更短，避免显示完整的 `Exports Overview`；`description` 提供页面摘要，影响文档站的搜索、索引或页面元数据展示。

## 修改风险

最大的风险是导航断链。`href="/features/exports/api-exports"` 和 `href="/features/exports/bulk-exports"` 必须与实际 MDX 路由一致；如果重命名文件或移动目录，需要同步修改这里、`docs/docs.json` 以及可能存在的其他入口，否则用户会从概览页进入 404。

第二个风险是信息架构偏移。当前页面明确是轻量概览页，如果在这里加入大量 API 参数、UI 步骤或外部链接，会与 `api-exports.mdx`、`bulk-exports.mdx` 产生重复，增加维护成本。更合适的做法是保持本页只做分流，把细节写入对应专题页。

第三个风险是文案承诺不一致。`API Exports` 描述为 “Dynamically export data from your groups via our APIs”，而子页面强调 Outputs API 和 `created_after` 增量拉取；`Bulk Exports` 描述为通过 UI 创建整个 group 的单文件导出，而子页面又说明可按 job/date 过滤。修改卡片文案时需要和子页面能力保持一致，避免让用户误解 API 与 UI 导出的适用场景。

第四个风险是组件兼容性。该文件依赖 Mintlify 全局组件，不应随意改成未确认支持的自定义组件或 HTML 结构。特别是 `CardGroup`、`Card` 的属性名如 `cols`、`title`、`icon`、`href` 应保持符合文档框架语法，否则页面可能能构建但展示异常。

最后，外部链接合规也需要注意。虽然本文件当前只使用站内相对路径，但相邻的 `bulk-exports.mdx` 和 `introduction.mdx` 包含外部链接；如果未来在 overview 中加入外部入口，需要确认文档站允许的跳转策略、链接可用性和是否应优先使用内部说明页承接。
