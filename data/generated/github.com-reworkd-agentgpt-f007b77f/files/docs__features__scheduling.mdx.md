# 文件：docs/features/scheduling.mdx

## 一句话定位

`docs/features/scheduling.mdx` 是 Reworkd 文档站里“Scheduling”功能页，负责向用户解释抓取 `group` 如何按固定频率重复运行、单个 `job/source` 如何覆盖组级调度，以及重复运行时不同页面阶段的再访问策略。它不是业务代码入口，而是面向产品使用者和开发者的概念说明页。

## 它暴露/定义了什么

这个文件暴露的是一页 MDX 文档内容，主要由两部分组成：文件头部的 frontmatter 和正文说明。frontmatter 定义 `title: Scheduling` 与 `description: Re-use scrapers across identical sites`，供文档站生成侧边栏、页面标题、搜索摘要或 SEO 信息使用。正文定义三个核心知识点：组可以按指定 cadence 重新运行；组内特定 source/job 可以单独覆盖默认 schedule；后续 run 中，category/listing 等高层页面会重新运行并继续 enqueue 下游阶段，而 detail page 默认会去重，不会在初次抓取后反复访问。

从内容边界看，它定义的是“调度语义”，不是调度实现。文档没有给出 cron 表达式、调度枚举、数据库字段、API 参数或后台 worker 逻辑，因此不能仅凭此文件判断具体调度器如何触发任务。

## 谁调用它

直接调用方是文档站配置。`docs/docs.json` 的导航树在 `Features` 分组下引用了 `features/scheduling`，因此根据当前片段推断，Mintlify 或类似 MDX 文档渲染系统会按该配置加载 `docs/features/scheduling.mdx`，把它展示为功能文档页面。

间接使用者包括阅读 Reworkd 文档的终端用户、需要理解抓取重跑策略的客户、以及维护调度/爬虫功能的开发者。它不是被应用运行时导入的模块，也没有被 `next`、`platform` 或 CLI 业务代码以代码形式引用；当前仓库搜索只发现 `docs/features/scheduling.mdx` 自身和 `docs/docs.json` 的导航引用。

## 它调用谁

作为静态 MDX 文档，它不调用业务函数、API、组件或外部服务。它依赖文档构建系统解析 frontmatter、Markdown 标题与段落。正文中也没有导入 React 组件、没有嵌入代码块、没有链接到真实外部地址。

概念上，它会“引用”项目文档体系中的几个领域对象：`Groups`、`Jobs`、`Run`、`Stages`。这些对象在 `docs/key-concepts.mdx` 中有更完整定义：group 是共享 schema 和 scraping frequency 的 source url/job 集合；job 是抓取组中的具体 source URL；run 是一次抓取执行；stage 则区分 category、listing、detail 等页面层级。因此本页对调度行为的解释需要和这些基础概念保持一致。

## 核心流程

用户侧流程是：先创建或进入一个 `group`，在 group 的 settings tab 中选择要使用的 schedule，使整个组按固定频率重复运行。如果组内某些 source 需要不同频率，用户进入该 job 的 settings tab，为具体 source 设置 override schedule。这样组级 schedule 提供默认值，job/source 级 schedule 提供例外值。

运行侧流程可以按页面阶段理解。后续调度触发时，高层 stage，例如 category page 和 listing page，会重新执行。它们会继续发现链接、入队下游阶段，并驱动后续抓取链路。detail page 的处理不同：它们默认会被 deduplicate，系统不会在初次保存数据后继续反复访问同一个 detail page。文档给出的理由是 detail page 的变更很难在不打开页面、不重新执行抽取逻辑的情况下可靠检测，所以默认策略偏向节省运行成本、避免重复访问。

这个流程与 `docs/features/deduplication.mdx` 的数据去重页面互补：调度决定何时重跑，去重决定重复保存时如何识别 create/update/duplicate；本页额外强调 detail page 访问本身也有去重策略。

## 关键函数的高层作用

本文件没有定义函数、类或可执行逻辑，因此不存在需要展开的关键函数。若把文档中的关键段落当作“功能块”看，可以分为三块：

`schedule groups`：说明 group 级别的调度入口和默认行为，即同一个组里的 source/jobs 可以按统一 cadence 重跑。

`overriding schedules`：说明 job/source 级别的例外配置，用于处理某些 source 需要更高或更低抓取频率的情况。它的高层作用是避免为了不同频率拆分过多 group，同时保留精细控制能力。

`How are pages re-visited?`：说明调度重跑后的页面访问策略。category/listing 页面始终重跑，负责重新发现下游页面；detail 页面默认去重，除非用户有重新访问 detail page 的需求并联系维护方开启或支持相关能力。根据当前片段推断，这里强调的是平台默认产品行为，而不是完整可配置 API。

## 修改风险

第一类风险是概念漂移。`docs/key-concepts.mdx` 中 group 被定义为共享 schema 和 scraping frequency 的 job 集合；本页又说 job/source 可以覆盖 schedule。如果修改措辞时只强调 group 统一频率，可能让用户误以为不能做单 source 例外；如果只强调 override，又可能弱化 group schedule 是默认配置的事实。

第二类风险是误导实现能力。当前文档没有说明 cron、timezone、最小频率、失败重试、暂停/禁用、权限、计费影响等细节。如果贸然补充这些内容，除非有业务代码或产品规格佐证，否则容易写出不存在的能力。证据不足时应明确写“根据当前片段推断”。

第三类风险是页面阶段语义。category/listing/detail 的重跑差异是本页最关键的行为承诺。若改成“所有页面都会重跑”或“所有页面都去重”，都会改变用户对数据新鲜度和成本的预期。尤其 detail page 默认不重访，会影响价格、库存、状态等易变字段的更新策略，修改时需要同步检查去重文档、key concepts 以及实际抓取运行逻辑。

第四类风险是文档导航。`docs/docs.json` 通过 `features/scheduling` 暴露该页，重命名文件、移动路径或修改 slug 时，必须同步更新导航配置，否则文档站可能出现断页或导航缺失。
