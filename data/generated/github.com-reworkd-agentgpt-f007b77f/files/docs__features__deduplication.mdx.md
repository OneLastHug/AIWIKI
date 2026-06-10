# 文件：docs/features/deduplication.mdx

## 一句话定位

`docs/features/deduplication.mdx` 是 Reworkd 文档站里解释“数据去重/更新判定”的功能说明页，面向创建 scraper 和 schema 的用户，说明为什么需要选择稳定的 primary/deduplication key，以及 Reworkd 在重复运行 scraper 时如何避免插入重复数据。

## 它暴露/定义了什么

这个文件暴露的是一个 Mintlify MDX 文档页面，而不是运行时代码模块。文件顶部 frontmatter 定义了页面元信息：`title: Deduplication` 和 `description: Automatically generate scrapers`。其中 `title` 会作为文档站页面标题和导航展示依据之一；`description` 用于页面摘要或 SEO 元信息，但当前描述与正文主题略有偏差，正文实际讲的是数据去重，不是自动生成 scraper。

正文定义了几个面向用户的概念：第一，Reworkd 在保存数据时会基于某个 unique key 或 composite key 判断数据是否已存在；第二，新数据会插入并标记为 `CREATE`；第三，重复数据不会重复插入；第四，已存在 key 对应的数据再次出现时，会更新已有记录并标记为 `UPDATE`；第五，用户在创建 schema 时必须选择可作为 primary/deduplication key 的字段。它还给出好坏 key 的示例，例如 `SKU`、`UPC`、`Brand + Model + Color` 是较好的选择，而价格、库存状态、更新时间戳因为频繁变化，不适合作为去重 key。

## 谁调用它

直接“调用”它的是文档站构建/渲染系统，而不是业务代码。根据 `docs/docs.json`，`features/deduplication` 被挂在 `Documentation` tab 下的 `Features` 分组中。因此用户从文档站导航点击 Features 里的 Deduplication 页面时，Mintlify 会解析并渲染 `docs/features/deduplication.mdx`。

仓库内搜索只发现 `docs/docs.json` 和该文件自身引用了 `deduplication`，没有发现应用代码、SDK 或 API 文档直接引用它。因此根据当前片段推断，它是独立的产品说明文档页，调用入口主要是 Mintlify 的导航配置，而不是某个 React 组件或后端模块。

## 它调用谁

这个 MDX 文件没有 `import`，也没有使用 `<Card>`、`<Info>`、`<Frame>` 等 Mintlify 组件；它只使用 frontmatter、Markdown 标题、粗体、列表、表格和 inline code。因此它没有代码意义上的依赖调用。

从内容关系上，它依赖读者已经理解 Reworkd 的 `schema`、`group`、`run` 和输出数据保存流程。相关概念在 `docs/key-concepts.mdx`、`docs/schemas.mdx` 中有铺垫：`key-concepts.mdx` 说明 group 共享 schema、run 是一次 scraping job 执行；`schemas.mdx` 说明 schema 定义输出数据格式，并强调字段应稳定、清晰、与页面内容一致。`docs/features/scheduling.mdx` 也和它有功能邻接关系，因为 scheduling 会让 group 重复运行，而重复运行后的数据保存正是 deduplication 需要解决的问题。

## 核心流程

这个页面描述的用户心智流程可以概括为四步。

第一步，用户创建 scraping schema。schema 决定每一行输出数据有哪些字段，也决定哪些字段有资格承担去重标识。去重 key 的选择发生在 schema 设计阶段，而不是数据导出或后处理阶段。

第二步，用户选择一个或多个字段作为 primary/deduplication key。如果单个字段天然唯一，例如商品 `SKU` 或 `UPC`，可以直接使用；如果没有单个稳定字段，则使用 composite key，例如 `Brand + Model + Color`。页面强调 key 必须唯一、长期稳定，并且跨网站保持一致。

第三步，scraper 运行并保存数据。Reworkd 在保存每条记录时，根据记录字段生成或识别 unique key。若 key 没见过，则写入新行，并把变更类型标记为 `CREATE`。

第四步，scraper 后续重跑时再次保存数据。若 key 已存在且内容完全重复，则跳过插入，避免产生重复行；若 key 已存在但记录内容代表已有实体的新状态，则更新旧记录，并标记为 `UPDATE`。因此该功能既解决重复插入，也支撑同一实体的持续更新。

## 关键函数的高层作用

这个文件没有函数、类或可执行逻辑，因此不存在需要展开的核心函数。若从文档语义看，可以把页面中的三个概念块理解为“逻辑单元”。

`How It Works` 是核心说明块，负责定义 Reworkd 保存数据时的判定规则：根据 unique key 或 composite key 区分新记录、重复记录和已有记录更新。这里是整页最关键的行为契约，后续产品实现和用户预期都应与它保持一致。

`Defining your Deduplication Key` 是用户操作指导块，负责把去重机制落到 schema 设计动作上。它强调 key 的三个约束：唯一、稳定、一致。这个部分决定用户是否能正确使用去重能力，也是最容易影响数据质量的地方。

`Good vs. Poor Key Examples` 是风险提示块，用具体例子帮助用户避开不稳定字段。它没有引入新机制，但能降低误用概率，尤其是避免把价格、库存状态、更新时间这类动态字段当成实体身份。

## 修改风险

最大风险是把文档行为写得比系统实际能力更强。当前页面承诺了三种保存行为：`CREATE`、跳过重复、`UPDATE`。如果后端实际没有完整支持更新标记、变更历史或 composite key，那么这页会造成用户误解。修改前最好对照真实保存逻辑、API 返回字段和导出结果，确认 `CREATE`、`UPDATE` 是否为真实枚举或只是概念性描述。

第二个风险是 key 选择规则会直接影响用户的数据建模。若把“唯一”描述得过于宽泛，用户可能选择在单站点内唯一但跨网站不一致的字段，导致同一商品、职位、房源或公司被拆成多条记录。相反，如果过度强调全局唯一，也可能让用户以为必须存在官方 ID，忽略 composite key 的可行性。

第三个风险是与 `docs/schemas.mdx`、`docs/key-concepts.mdx`、`docs/features/scheduling.mdx` 的术语不一致。该页提到 schema 创建、重复运行 scraper、保存数据和更新记录；这些概念在其他文档中分别叫 `schema`、`group`、`run`、`job`、`detail page`。如果后续改名或扩展功能，需要同步检查这些页面，避免用户在“重复运行”和“去重保存”之间建立错误联系。

第四个风险是 `description` 当前写成 `Automatically generate scrapers`，与页面主题不匹配。若文档站使用 description 做搜索结果、页面卡片或 SEO 摘要，用户可能被错误摘要误导。修正文案属于低风险改动，但应保持与 Mintlify frontmatter 格式一致。

第五个风险是表格中的行为描述很简略。若未来系统支持软删除、历史版本、字段级 diff、冲突解决、手动覆盖 key、重新计算 key 等能力，当前三行情景表会显得不完整。扩展时应优先补充高层行为和用户决策点，而不是加入实现细节，否则这页会从功能说明变成难以维护的内部机制说明。
