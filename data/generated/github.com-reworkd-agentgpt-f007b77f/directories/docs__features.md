# 目录：docs/features

## 它负责什么

`docs/features` 是 Reworkd 文档体系中面向“产品功能”的说明目录，位于 `docs/docs.json` 的 `Documentation -> Features` 导航组下。它不承载运行时代码，也不是 API schema 或 SDK 实现，而是把用户在使用 Reworkd 抓取、保存、复跑、导出数据时会遇到的核心能力拆成若干专题页。

从当前片段看，这个目录覆盖的功能集中在数据抓取后的生命周期：如何避免重复数据、如何导出数据、如何定时复跑 scraper、如何复用模板，以及如何处理文件下载。它更偏用户手册和功能概念解释，目标读者是正在配置 Reworkd group、job、schema、export 的使用者，而不是只面向内部开发者。

在整个 `docs` 目录中，`docs/features` 处于 `introduction.mdx` 和 `key-concepts.mdx` 之后。也就是说，读者应该先理解 Reworkd 的基本对象，例如 `Groups`、`Jobs`、`Schemas`、`Stages`、`Run`，再进入这里学习具体功能。`docs/features` 里的页面会频繁默认读者已经知道 group、job、schema、field、stage、output 这些概念。

## 直接子目录地图

`docs/features` 当前只有一个直接子目录：

`docs/features/exports`

这个子目录负责“导出数据”这一组功能，内部包含 `overview.mdx`、`api-exports.mdx`、`bulk-exports.mdx`。其中 `overview.mdx` 是导出专题入口，负责把 API 导出和 Bulk 导出两个路径并列展示；`api-exports.mdx` 说明通过 API 端点按需拉取数据，尤其强调 `created_after` 这种增量同步思路；`bulk-exports.mdx` 说明通过 UI 创建 JSON 或 CSV 快照导出，更适合一次性或全量导出。

除了 `exports` 子目录，`docs/features` 根下还有几个独立功能页：`deduplication.mdx`、`file-downloads.mdx`、`scheduling.mdx`、`templates.mdx`。这些页面不是按技术模块组织，而是按用户任务组织：去重、下载、调度、模板复用。根据当前片段推断，这个目录的组织原则是“每个用户可见能力一页，复杂能力再拆子目录”，依据是只有 Exports 被拆成 overview/API/Bulk 三页，其他能力都保持单页。

## 关键入口

最直接的入口是 `docs/docs.json` 中的 `Features` 导航组。这里明确列出了页面顺序：`features/deduplication`，然后是 `Exports` 分组，接着是 `features/scheduling`、`features/templates`、`features/file-downloads`。因此在生成站点侧边栏时，`docs/docs.json` 是这个目录的导航入口和顺序来源。

另一个入口是 `docs/introduction.mdx`。它的卡片区包含 “Exporting data”，指向 `features/exports/overview`。这说明 Exports 是从首页介绍页直接引流的重点功能，可能是用户完成首次 scraping 后最常访问的能力。

概念入口是 `docs/key-concepts.mdx`。虽然它不属于 `docs/features`，但它解释了 `Groups`、`Jobs`、`Schemas`、`Stages`、`Run` 等基础术语。`docs/features/scheduling.mdx` 中的 group schedule、job override、category/listing/detail page 复跑逻辑，都依赖这些概念；`docs/features/deduplication.mdx` 中的 schema field 和 primary/deduplication key，也需要先理解 schema。

跨目录入口还有 `docs/developers`。`docs/features/exports/api-exports.mdx` 会引导用户先创建 API key，并链接到开发者文档；`docs/features/file-downloads.mdx` 在说明动态下载时提到更技术化的文件下载处理，导航配置中也存在 `developers/file-downloads`。因此功能页负责“怎么用”，开发者页更可能负责“怎么接入或实现细节”。

## 主流程位置

`docs/features` 描述的是 Reworkd 用户流程中“配置完成后如何稳定产出数据”的部分。按产品使用链路看，主流程大致是：先通过 `docs/introduction.mdx` 认识 Reworkd，再通过 `docs/key-concepts.mdx` 理解 group、job、schema、stage、run，然后进入 feature 文档解决实际使用问题。

`deduplication.mdx` 位于数据保存阶段。它说明 Reworkd 保存数据时使用唯一 key 或 composite key 判断新数据、重复数据和更新数据。这里的主流程是：用户创建 schema 时选择哪些字段作为 primary/deduplication key；运行 scraper 后，系统根据这个 key 插入新记录、跳过重复记录，或更新已有记录。它和长期复跑、增量导出关系密切，因为没有稳定去重 key，后续复跑会产生脏数据或重复数据。

`exports/overview.mdx` 是导出流程入口。用户如果需要把数据送入自己的系统，应先从这里判断导出方式。`api-exports.mdx` 对应持续集成式的主流程：创建 API key，调用 outputs API，使用 `created_after` 记录上次同步时间，只获取新增数据。`bulk-exports.mdx` 对应 UI 快照式流程：在界面选择 group，可选 job 或日期过滤，生成 JSON/CSV 文件。

`scheduling.mdx` 位于复跑流程。它说明 group 可以设置固定 cadence，job 可以覆盖 group 的默认 schedule。它还解释了页面重访策略：category/listing 这类上层 stage 会在后续 run 中重新执行并 enqueue 下层页面；detail pages 默认会去重，不会反复访问。这个页面是理解长期抓取行为的关键位置。

`templates.mdx` 位于 scraper 复用流程。它说明当多个网站具有相同结构或相同底层服务商时，可以复用预构建 scraper code。根据当前片段推断，它主要面向降低重复编写 scraper 和 LLM token 消耗的场景。

`file-downloads.mdx` 位于输出增强流程。它说明当 schema 中某个 URL 字段启用 `Download file from URL` 后，job 保存 URL 时系统会异步下载文件，并在 export 的 `files` 数组里返回文件元数据和下载链接。它区分 regular downloads 和 dynamic downloads：前者通过可直接访问的 canonical URL 异步下载，后者在浏览器 worker 中下载，用当前页面作为 source URL。

## 推荐阅读顺序

建议先读 `docs/introduction.mdx`，确认 Reworkd 的整体定位是用 LLM 辅助规模化抓取网页数据。随后读 `docs/key-concepts.mdx`，把 `Groups`、`Jobs`、`Schemas`、`Stages`、`Run` 这些词对齐，否则后续功能页会显得跳跃。

进入 `docs/features` 后，第一篇建议读 `docs/features/deduplication.mdx`。原因是去重 key 是 schema 设计的一部分，会影响后续每次保存、更新、复跑和导出。特别是 SKU、UPC、Brand + Model + Color 这类稳定 key，与 price、availability、timestamp 这类易变字段的区别，需要在建 schema 时先想清楚。

第二步读 `docs/features/scheduling.mdx`，理解 group schedule、job override，以及 category/listing/detail page 在重复运行时的差异。这样能知道哪些页面会被重新访问，哪些 detail page 默认不会复抓。

第三步读 `docs/features/exports/overview.mdx`，再根据需求选择 `docs/features/exports/api-exports.mdx` 或 `docs/features/exports/bulk-exports.mdx`。如果是日常数据管道，优先读 API exports；如果只是需要一次性文件快照，再读 Bulk exports。

最后读 `docs/features/file-downloads.mdx` 和 `docs/features/templates.mdx`。文件下载是特定 schema 字段能力，只有抓取目标包含 PDF、附件或下载资源时才是主线；模板复用则适合多个结构相同站点的规模化场景。

## 常见误区

第一个误区是把 `docs/features` 当成代码实现目录。它实际是 Mintlify 风格的 `.mdx` 文档目录，核心入口来自 `docs/docs.json` 的导航配置，不包含 scraper、API route 或 worker 的实现代码。

第二个误区是认为所有 feature 都是平级单页。当前只有 `exports` 被拆成子目录，因为导出能力本身有 overview、API、Bulk 三种阅读层次；其他功能仍是单页专题。新增功能文档时，应先判断是否真的需要子目录，而不是机械拆分。

第三个误区是把 Bulk exports 当作默认推荐方式。`bulk-exports.mdx` 明确说 Bulk exports 适合获取某一时点的完整快照，但多数用例应优先使用 API exports。持续同步场景应关注 `api-exports.mdx` 中的 `created_after`。

第四个误区是忽略 deduplication key 的稳定性。`deduplication.mdx` 强调 key 必须唯一、稳定、一致；价格、库存、时间戳这类字段会变化，不适合作为主去重依据。这个选择会直接影响更新识别和重复数据控制。

第五个误区是以为定时复跑会重新访问所有 detail page。`scheduling.mdx` 说明 category/listing 会复跑，但 detail pages 默认去重，不会在初次抓取后反复访问。需要 detail page 重访时，文档暗示这不是默认能力，需要额外沟通或配置。

第六个误区是认为文件下载在 export 中立即可见。`file-downloads.mdx` 明确说明下载是异步发生的，文件可能需要一段时间才出现在导出结果中；因此使用 `files` 数组时要考虑延迟和文件保留周期。
