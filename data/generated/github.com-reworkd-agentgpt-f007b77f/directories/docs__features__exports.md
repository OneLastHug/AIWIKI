# 子系统：docs/features/exports

## 解决什么问题

`docs/features/exports` 是 Reworkd 文档站里“数据导出”功能的子系统入口，负责向用户解释如何把 scraping 产生的数据从平台中取出。它不是导出逻辑的实现代码，而是一组面向产品使用者和开发者的 MDX 文档，主要回答三个问题：导出能力有哪些、推荐使用哪种导出方式、不同方式适合什么场景。

根据当前片段推断，Reworkd 的导出能力被分成两条路径：一条是 `API Exports`，用于通过 API 持续、动态地拉取 group 中的数据；另一条是 `Bulk Exports`，用于在 UI 中生成某个 group 或 job 的 JSON/CSV 快照文件。文档明确表达了产品推荐：多数场景优先使用 API 导出，bulk export 更适合一次性获取某个时间点的完整数据快照。

这个目录的价值在于把“数据采集之后如何进入用户自己的系统”讲清楚。它承接前面的 scraping、group、job、schema 等概念，也连接后面的 API reference、API key、file downloads 等开发者文档。

## 相关目录和文件

`docs/features/exports/overview.mdx` 是导出子系统的总览页。它只保留非常薄的一层导航，用 `CardGroup` 展示 `API Exports` 和 `Bulk Exports` 两个入口，说明该目录本身被设计成子功能聚合页，而不是长篇说明页。

`docs/features/exports/api-exports.mdx` 说明 API 导出方式。它强调客户最常用的数据摄入方式是 API endpoint，并引导用户先通过 `developers/api-keys` 创建 API key，再查看 `api-reference/public/get-outputs-for-a-scraping-group`。该页还介绍了增量同步模式：使用 `created_after` query parameter，只获取上次摄入之后新创建的数据。

`docs/features/exports/bulk-exports.mdx` 说明 UI 批量导出方式。它定义 bulk export 是包含某个 group 或 job 内 scraped data 的 JSON 或 CSV 文件，并说明创建时可以选择 group， optionally 选择 job 和/或 date 作为过滤条件。页面还用 `Warning` 提醒大 group 的导出可能耗时很久。

`docs/docs.json` 是导航配置，负责把该目录挂到 Documentation tab 的 Features 分组下，并把 `overview`、`api-exports`、`bulk-exports` 组织成名为 `Exports` 的二级分组。也就是说，用户在文档站侧边栏中看到的导出章节结构，主要由这个文件决定。

相邻文档中，`docs/features/file-downloads.mdx` 与导出有直接关系：它说明文件下载链接会出现在所有 export formats 的 `files` array 中，并且文件下载是异步的，可能需要等待后才会出现在导出结果里。`docs/developers/api-keys` 和 API Reference 也属于导出流程的必要上下文，但当前片段未读取其完整内容。

## 核心对象

`exports` 是文档层面的子系统对象，代表“把 Reworkd 中已抓取数据交付给用户”的能力集合。它本身没有独立运行时代码，而是由多个文档页共同定义使用模型。

`group` 是导出的主要边界。API export 和 bulk export 都围绕 group 展开：API 文档指向“get outputs for a scraping group”，bulk export 也说明可以导出 group 内所有 scraped data。根据当前片段推断，group 是 Reworkd 中组织 scraping outputs 的核心容器。

`job` 是 bulk export 的可选过滤维度。用户可以在 UI 中选择某个 group，再进一步限定到某个 job。它更像一次采集任务或执行记录的范围标识。

`output` 或 `scraped data` 是最终被导出的数据实体。API export 通过 Outputs API 返回它们；bulk export 则把它们打包为 JSON 或 CSV 文件。

`created_after` 是 API 增量导出的核心参数。它允许调用方只请求某个 datetime 之后创建的数据，从而避免每天重复拉取完整数据集。

`API key` 是 API export 的认证前置条件。文档没有展开认证细节，而是把用户导向 `developers/api-keys`，说明导出文档只负责使用路径，认证机制由开发者文档维护。

`Bulk export file` 是 UI 导出的产物，格式为 JSON 或 CSV。它强调的是快照性质，适合一次性下载或归档，而不是持续数据摄入。

## 运行流程

从用户视角看，导出流程先从 `docs/features/exports/overview.mdx` 进入。该页将用户分流到 API 导出或批量导出两条路径。

API 导出的流程是：用户先准备 API key，然后调用 Outputs API 获取某个 scraping group 的数据。如果用户需要持续同步，调用方应记录每次 API 请求发生的精确 datetime；下一次请求时，把这个时间作为 `created_after` 参数传入，只获取之后创建的新数据。该模式适合定时任务、数据仓库摄入、业务系统同步等场景。文档中提到典型客户会每天调用一次 API，这暗示 API export 是稳定、周期性的集成方式。

Bulk export 的流程是：用户进入 Reworkd UI 的 exports 页面，选择要导出的 group，并按需要选择 job 或 date 进行过滤，然后生成一个包含 scraped data 的 JSON 或 CSV 文件。该流程更适合人工操作、临时分析、迁移、审计或某个时间点的全量快照。大 group 导出耗时较长，因此它不适合作为高频自动同步的首选路径。

对于包含文件下载的 scraping 结果，导出结果中还会包含 `files` array。由于文件下载是异步完成的，导出数据刚生成时不一定立即包含完整文件链接；这是使用 export 结果时需要考虑的延迟因素。

## 上下游依赖

上游依赖主要是 Reworkd 的 scraping 数据模型。导出文档不断提到 `group`、`job`、`scraped data`、`outputs`，说明导出并不生产数据，而是读取已经由 scraping 任务产生并归档到 group/job 下的数据。

API export 依赖开发者认证体系和 API Reference。`api-exports.mdx` 直接引用 `developers/api-keys`，并把正式接口说明交给 `api-reference/public/get-outputs-for-a-scraping-group`。因此修改 API 导出文档时，需要确认 API key 创建流程、Outputs API 路径、query parameter 名称是否仍然一致。

Bulk export 依赖 Reworkd Web UI 的 exports 页面。文档把 UI 页面作为入口，并说明用户在界面中选择 group、job、date。根据当前片段推断，真实导出任务的创建、过滤、文件生成和下载状态都由平台后端和 UI 完成，文档只描述使用方式。

下游依赖是用户的数据消费系统，包括客户自己的数据库、ETL、报表、分析脚本、归档流程等。API export 面向机器读取，bulk export 面向文件交付。`docs/features/file-downloads.mdx` 还说明导出格式会承载文件下载链接，因此使用者可能需要继续调用文件下载相关能力。

## 修改时最容易踩的坑

第一，不要把 bulk export 写成推荐的默认方案。现有文档明确说 API exports should be the preferred export method for most use cases，bulk export 只是适合获取某个时间点的完整快照。

第二，修改 `created_after` 的描述时要特别谨慎。它是增量同步的关键契约，涉及“记录上次 API call 的 exact datetime，再用于后续请求”。如果把它写成按日期、按 job 或按更新时间过滤，可能误导用户实现错误的摄入逻辑。

第三，注意 `group` 和 `job` 的层级。bulk export 是先选择 group，再可选选择 job/date；API export 当前文档强调的是从 group 获取 outputs。不要在没有证据的情况下声称 API export 也支持完全相同的 job/date 过滤。

第四，外部入口不要写死为裸 URL。当前文档中 bulk export card 和站点配置包含真实外部地址，但在学习文档或二次整理中应避免输出真实网址，可用 `[URL已移除]` 代替。

第五，`docs/docs.json` 和 MDX 文件需要同步维护。新增、重命名或删除 `docs/features/exports/*.mdx` 时，如果没有更新导航配置，页面可能存在但不会出现在文档站侧边栏中，或导航指向不存在的页面。

第六，文件下载与导出的关系容易被忽略。`file-downloads` 文档说明下载链接会出现在所有导出格式中，但文件处理是异步的；如果导出文档补充文件字段示例，应提醒用户可能存在延迟。

## 推荐阅读顺序

1. 先读 `docs/features/exports/overview.mdx`，理解导出子系统被拆成 API exports 和 bulk exports 两类入口。

2. 再读 `docs/features/exports/api-exports.mdx`，重点关注 API key 前置条件、Outputs API 入口，以及 `created_after` 增量同步模式。

3. 然后读 `docs/features/exports/bulk-exports.mdx`，理解 UI 批量导出的适用场景、JSON/CSV 输出、group/job/date 过滤和大数据量耗时风险。

4. 接着读 `docs/features/file-downloads.mdx`，补齐导出结果中 `files` array 和异步文件下载的行为。

5. 最后读 `docs/docs.json`，确认这些页面如何被挂载到 Mintlify 文档站导航中，以及导出章节在整个 Features 分组里的位置。
