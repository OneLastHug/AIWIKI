# 文件：platform/reworkd_platform/web/api/agent/tools/search.py

## 一句话定位

`search.py` 定义了 AgentGPT 默认的联网搜索工具 `Search`：当 agent 判断当前任务需要获取公开、实时或外部信息时，它调用 Serper 的 Google Search API 拉取搜索结果，再把带来源的片段交给语言模型总结成流式回答。

## 它暴露/定义了什么

本文件主要定义两类能力。

第一是内部异步函数 `_google_serper_search_results(search_term, search_type="search")`，负责向 Serper Google Search 接口发起 HTTP 请求并返回 JSON 搜索结果。它不是工具系统直接暴露的接口，而是 `Search._call()` 的底层搜索实现。

第二是 `Search(Tool)` 类，这是对 agent 工具协议的具体实现。它通过类属性声明工具描述、公开描述、参数说明和前端图标路径，例如 `description`、`public_description`、`arg_description`、`image_url`。这些元数据会被工具注册、OpenAI function schema 和前端工具列表间接使用。

`Search.available()` 用于判断当前环境是否配置了 `settings.serp_api_key`。如果没有 key，这个工具理论上不应出现在可用工具中。

## 谁调用它

直接注册点在 `platform/reworkd_platform/web/api/agent/tools/tools.py`。其中 `get_default_tools()` 返回 `[Search]`，`get_default_tool()` 也返回 `Search`，所以搜索是该 agent 系统的默认工具和兜底工具。

实际执行链路在 `platform/reworkd_platform/web/api/agent/agent_service/open_ai_agent_service.py`：`execute_task_agent()` 根据 `analysis.action` 通过 `get_tool_from_name()` 找到工具类，然后实例化 `tool_class(self.model, self.settings.language)`，最后调用 `.call(goal, task, analysis.arg, self.user, self.oauth_crud)`。当 action 是 `search`，最终就进入本文件的 `Search.call()`。

分析阶段也依赖它。`platform/reworkd_platform/web/api/agent/analysis.py` 中的 validator 会检查：如果 action 是 `Search` 对应的工具名，则 `arg` 不能为空；`Analysis.get_default_analysis()` 会把默认 action 设置为默认工具名，也就是搜索，并把当前 task 当作搜索参数。

根据当前片段推断，API 层 `platform/reworkd_platform/web/api/agent/views.py` 通过工具列表接口展示可用工具信息，间接读取 `Search.public_description`、`Search.available()` 等元数据；实际 agent 运行时则经由 `OpenAIAgentService` 调用。

## 它调用谁

本文件调用的关键外部依赖包括：

`aiohttp.ClientSession`：用于异步 POST 请求 Serper API。请求头里带 `X-API-KEY`，值来自 `settings.serp_api_key`。

`settings`：读取 Serper API key，决定工具是否可用，并用于实际请求鉴权。

`Reason`：当 Serper 请求抛出 `ClientResponseError` 时，`Search.call()` 会记录异常并降级调用 `Reason(self.model, self.language).call(...)`，让模型直接推理，而不是让任务失败。

`CitedSnippet` 和 `summarize_with_sources()`：搜索结果会被整理成带编号、文本和 URL 的引用片段，然后交给 `summarize_with_sources()`。该函数内部使用 LangChain `LLMChain` 和 `summarize_with_sources_prompt` 生成 `text/event-stream` 流式响应。

`stream_string()`：当没有任何可用 snippet 时，返回一个简单的流式字符串 `"No good Google Search Result was found"`。

## 核心流程

`Search.call()` 是对外入口。它先调用私有 `_call()`，如果 Serper API 返回 HTTP 错误并触发 `ClientResponseError`，则进入降级路径，改用 `Reason` 工具处理同一个 goal、task 和 input。

`Search._call()` 执行真实搜索。它把 `input_str` 作为查询词传给 `_google_serper_search_results()`，默认请求 Serper 的 `search` 类型。拿到结果后，它最多处理 5 条 organic 搜索结果，同时优先处理 `answerBox`。

结果整理分两步：如果响应里有 `answerBox`，优先抽取 `answer`、`snippet` 或 `snippetHighlighted`，并构造一个指向 Google 查询页的 `CitedSnippet`。随后遍历 `results["organic"][:5]`，把每条结果的 `snippet`、`link` 和 `attributes` 拼成文本，再追加为引用片段。

如果最终没有片段，则直接返回失败提示流。否则调用 `summarize_with_sources(self.model, self.language, goal, task, snippets)`，让模型基于搜索片段和用户目标生成总结，并通过 SSE 风格的 streaming response 返回给前端。

## 关键函数的高层作用

`_google_serper_search_results()` 是搜索 API 适配层。它隐藏了 Serper 请求细节，包括 header、query 参数、endpoint 拼接、HTTP 状态检查和 JSON 解析。修改搜索供应商时，这里是最集中的替换点。

`Search.available()` 是环境可用性判断。它只检查 `settings.serp_api_key` 是否非空，不验证 key 是否真实有效。因此配置错误可能要到实际调用时才暴露。

`Search.call()` 是稳定性边界。它把 Serper HTTP 响应错误转成 `Reason` 工具兜底，避免整个 agent 任务因搜索服务异常中断。但它只捕获 `ClientResponseError`，网络连接错误、JSON 结构异常等不一定会被兜住。

`Search._call()` 是核心业务流程，负责把原始搜索结果转成模型可消费的 `CitedSnippet`，并触发带来源总结。它并不直接返回原始搜索结果，而是返回模型加工后的流式总结。

## 修改风险

最大风险是响应结构假设较强。代码直接访问 `results["organic"][:k]`，如果 Serper 返回缺少 `organic` 的结构，可能抛出 `KeyError`。`answerBox` 逻辑相对稳健，但 organic 部分没有同等兜底。

第二个风险是错误处理范围有限。当前只捕获 `ClientResponseError`，这覆盖了 HTTP 状态错误，但不覆盖连接超时、DNS 问题、`aiohttp.ClientError` 的其他子类、JSON 解析失败或响应字段缺失。若要增强稳定性，需要谨慎扩大异常捕获范围，同时避免吞掉真实编程错误。

第三个风险是工具默认地位很高。`Search` 同时是 `get_default_tools()` 和 `get_default_tool()` 的返回值，`Analysis.get_default_analysis()` 也会 fallback 到搜索。因此修改它的工具名、可用性、参数要求或返回类型，会影响 agent 的兜底行为，而不只是“搜索功能”。

第四个风险是引用与外部链接处理。`CitedSnippet` 会把搜索结果链接传给总结 prompt。若要做 URL 脱敏、来源过滤、域名白名单或安全审查，应在构造 snippet 时处理，否则下游模型和前端都可能接触原始外部链接。

第五个风险是 prompt 输入质量。`attributes` 被简单拼接为 `"key: value."`，answer box 和 organic snippets 也未做长度控制、去重或可信度排序。增加更多搜索结果或字段可能提高召回，但也会增加 token 消耗、噪声和摘要偏差。
