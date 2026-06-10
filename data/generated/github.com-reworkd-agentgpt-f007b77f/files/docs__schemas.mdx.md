# 文件：docs/schemas.mdx

## 一句话定位
`docs/schemas.mdx` 是 Reworkd 文档里专门讲“Schema（数据结构定义）”的概念页，负责向使用者说明：什么是 schema、字段类型有哪些、如何设计更稳定的 schema，以及当页面缺字段时系统会怎样处理。

## 它暴露/定义了什么
这个文件本身不暴露运行时代码，而是定义一篇文档内容。它主要提供四类信息：  
1. schema 的概念定义：它是对目标网站输出数据格式的统一约束。  
2. schema 字段类型：当前片段里明确提到了 `URL`、`Phone Number`、`Currency` 等高级字段，并强调这些字段会附带转换或校验行为。  
3. schema 设计原则：例如字段要简单、只保留当前需要的字段、字段要真实出现在页面上、避免派生字段、尽量用可解释的命名和示例值。  
4. 缺字段时的默认行为：缺失字段会变成 `null`，数组会变成空数组。

## 谁调用它
根据当前片段推断，它主要被文档站点的导航系统调用。`docs/docs.json` 把 `schemas` 放进了 `Documentation > Get Started` 分组，因此它是一个可直接从左侧导航进入的页面。  
另外，`docs/key-concepts.mdx` 里通过 `Read more about schemas in our [Schemas](/features/schemas) page.` 引用了它，说明“Key Concepts”页会把读者导流到这里。  
`docs/features/file-downloads.mdx`、`docs/features/deduplication.mdx`、`docs/developers/sdk.mdx` 也在概念上依赖 schema 的定义，但它们不是直接执行调用，而是作为相关主题互相补充。

## 它调用谁
这个文件不调用业务代码，也不直接调用其他程序模块。它的“调用关系”更多是文档层面的交叉引用：  
- `docs/key-concepts.mdx` 会链接到它，用来解释 group 和 schema 的关系。  
- `docs/features/file-downloads.mdx` 依赖这里提到的 `URL` 字段类型，因为文件下载功能要求 schema 里先定义 URL 字段。  
- `docs/developers/sdk.mdx` 间接受它约束，因为 `save_data` 的核心语义是“保存的数据必须符合当前 schema”。  
- `docs/features/deduplication.mdx` 也与它相关，因为去重键是在创建 schema 时选定的字段集合。

## 核心流程
这页的核心叙事很清楚：先定义 schema，再用 schema 约束抓取结果。流程大致是：  
1. 用户为某个 group 设计 schema，决定要采集哪些字段。  
2. 系统在处理每一行数据时，会做严格的 schema validation，确保输出一致。  
3. 如果字段使用了高级类型，比如 `URL`，系统会自动做格式转换或校验。  
4. 如果页面缺少某个字段，系统不会报成结构性失败，而是按约定填 `null` 或空数组。  
5. 文档进一步提醒用户，schema 设计越简单、越贴近页面真实内容，抓取越稳定。

## 关键函数的高层作用
这个文件没有函数。若从“文档中隐含的核心能力”来理解，最重要的是以下几个概念接口：  
- `schema validation`：把页面抓到的数据和 schema 对齐，保证输出格式稳定。  
- `URL` 字段类型：负责把相对地址转绝对地址，并对非法 URL 做失败处理，同时支撑文件下载能力。  
- 缺省值策略：把缺字段统一映射成 `null` 或空数组，减少下游处理分支。  
- schema 设计建议：通过限制字段数量、避免派生字段、使用清晰命名，降低 LLM 抽取错误率。

## 修改风险
这页是关键概念文档，改动风险主要在“概念误导”而不是代码回归。  
1. 如果修改 schema 的定义或字段类型说明，可能会让用户错误理解 `save_data`、文件下载、去重键这些功能的前置条件。  
2. 如果把“缺字段填 `null` / 空数组”的规则写得不准确，会直接影响用户对输出稳定性的预期。  
3. 如果删改字段设计建议，可能导致后续文档里的 SDK、去重、文件下载页面失去统一语义。  
4. 由于它被 `docs/docs.json` 纳入主导航，任何表述变化都会影响整站入门路径。
