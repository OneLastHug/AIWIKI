# 文件：docs/key-concepts.mdx

## 一句话定位

`docs/key-concepts.mdx` 是 Reworkd 文档站“Get Started”部分的核心概念页，用来向新用户解释产品里的基础业务对象：`Groups`、`Schemas`、`Jobs`、`Stages` 和 `Run`，帮助用户在进入功能页或 API 文档前建立统一术语理解。

## 它暴露/定义了什么

这个文件本质上暴露的是一页 Mintlify/MDX 文档内容，而不是代码模块。文件顶部 frontmatter 定义了页面元信息：`title: Key Concepts` 和 `description: Everything you need to get started with Reworkd`。这些字段会被文档站生成器读取，用于页面标题、SEO 摘要、侧边导航或搜索索引。

正文定义了三个主要概念区块：

`Groups`：解释 group 是用户使用 Reworkd 时首先创建的对象，是共享同一 schema 和抓取频率的一组 source urls/jobs。它还用“多个在线书店抓取书籍数据”的例子说明 group 的组织边界。

`Schemas`：作为 `Groups` 下的子概念出现，说明 schema 是要从网站抓取的数据结构定义，并强调同一 group 下所有 jobs 共享同一个 schema。页面还指向更完整的 schema 功能页。

`Jobs`：解释 job 是 scraping group 中的一个独立 source URL，并引入 source job 与 child jobs 的关系。这里的重点不是任务调度实现，而是让用户理解爬虫会从入口页面继续 enqueue 后续页面。

`Stages`：作为 job 的子概念，借电商网站举例说明 category、listing、detail 三阶段的层级流转。

`Run`：解释一次 scraping job 的单次执行，用于追踪状态、结果、失败重试和输出列表。

## 谁调用它

根据 `docs/docs.json`，`docs/key-concepts.mdx` 被 Mintlify 文档系统纳入导航：它位于 `navigation.tabs` 下的 `Documentation` 标签页、`Get Started` 分组中，页面标识为 `"key-concepts"`。因此文档站构建或运行时会根据这个配置加载并渲染该 MDX 文件。

`docs/introduction.mdx` 也通过一个 `Card` 入口引用了该页面，卡片标题是 `Key terms`，目标为 `/key-concepts`。用户从 introduction 首页点击“Key terms”时，会进入这个文件生成的页面。

此外，文档站搜索、页面索引、侧边栏导航也会间接消费这个文件的 frontmatter 和正文内容。根据当前片段推断，这是由 Mintlify 的文档生成流程完成的，依据是 `docs/docs.json` 顶部声明了 Mintlify schema，并使用了 Mintlify 风格的 `navigation`、`tabs`、`groups`、`pages` 配置。

## 它调用谁

这个文件没有 JavaScript/TypeScript 层面的函数调用。它“调用”的主要是 MDX/Mintlify 语义能力：

第一，frontmatter 被文档框架解析，用于生成页面标题与描述。

第二，Markdown 标题如 `# Groups`、`### Schemas`、`# Jobs` 会被渲染为页面结构，并可能形成右侧目录或锚点。

第三，正文中的内部文档链接 `[Schemas](/features/schemas)` 会交给文档站路由处理，指向 schema 相关页面。需要注意的是，仓库中实际存在 `docs/schemas.mdx`，而当前链接写的是 `/features/schemas`。根据当前片段推断，这可能是历史路径、计划中的路由，或 Mintlify 层面的别名配置；仅从已读文件无法确认该路径一定有效。

## 核心流程

页面阅读流程是典型的新手概念铺垫流程。

先从 `Groups` 开始，把 Reworkd 的工作空间抽象讲清楚：用户不是直接孤立地抓一个 URL，而是把一批相关 source urls/jobs 放在同一个 group 中，并让它们共享 schema 与抓取频率。

接着引出 `Schemas`，说明 group 内数据输出必须服从同一结构定义。这一步把“抓什么字段、输出什么形状”与“抓哪些网站或页面”解耦，是后续理解数据一致性和 schema validation 的基础。

然后进入 `Jobs`，把 group 内的具体抓取单元定义为一个 distinct source URL，并说明爬虫在页面流转过程中会继续 enqueue child jobs。这里隐含了 Reworkd 的抓取模型：入口 job 负责发现后续页面，后续页面再承担列表或详情处理。

`Stages` 进一步把 job 的动态流转拆成业务阶段。电商例子中，category 页面发现 listing 页面，listing 页面发现 product detail 页面，detail 页面抽取最终产品数据。这个例子承担了把抽象 job graph 讲成可理解抓取链路的作用。

最后用 `Run` 收束到执行层面：job 是定义或来源，run 是某次执行实例。run 负责状态、结果、重试和输出追踪，是观察一次抓取是否成功的核心单位。

## 关键函数的高层作用

该文件没有定义函数、类或可执行逻辑，因此不存在传统意义上的“关键函数”。

可以把页面中的几个一级/三级标题视为“概念入口”：

`Groups` 负责定义业务集合边界，说明哪些 jobs 应该被放在一起，以及为什么 schema 和频率在 group 级共享。

`Schemas` 负责承接数据结构定义，强调 group 内输出格式一致。辅助说明是跳转到 schema 专页，详细规则不在本页展开。

`Jobs` 负责定义抓取单元和父子关系，解释 source job 与 child jobs 的来源。

`Stages` 负责说明 job 在真实网站中的分层流转，核心价值是通过 category、listing、detail 的例子解释 enqueue 链路。

`Run` 负责定义执行实例，强调状态追踪、结果收集、失败重试和 outputs 生成。

## 修改风险

最大的风险是术语漂移。这个文件是入门概念页，如果 `Group`、`Job`、`Run` 等定义与产品 UI、API Reference、SDK 或后端模型不一致，会让用户在后续阅读 `docs/schemas.mdx`、`docs/features/scheduling.mdx`、`docs/developers/sdk.mdx` 时产生认知冲突。

第二个风险是导航路径失效。`docs/docs.json` 中以 `"key-concepts"` 注册该页，`docs/introduction.mdx` 中也通过 `/key-concepts` 入口跳转。如果重命名文件或改 slug，需要同步更新导航和入口卡片。正文里的 `[Schemas](/features/schemas)` 也要重点检查，因为当前仓库可见的 schema 页面是 `docs/schemas.mdx`，路径是否匹配取决于文档站路由配置。

第三个风险是概念层级被写得过细。用户明确进入的是 key concepts 页面，本页应该保持高层解释，不适合塞入 API 参数、调度实现、数据库字段或爬虫执行细节。过度展开会削弱它作为“术语地图”的作用。

第四个风险是示例语义影响用户建模。当前电商 category/listing/detail 示例非常关键，如果修改为不具备层级发现关系的例子，`source job`、`child jobs`、`enqueue`、`stages` 之间的关系会变得不直观。

第五个风险是 frontmatter 破坏。`title` 和 `description` 是文档站消费的元数据，删除或格式错误可能影响页面标题、搜索摘要、导航展示或构建结果。
