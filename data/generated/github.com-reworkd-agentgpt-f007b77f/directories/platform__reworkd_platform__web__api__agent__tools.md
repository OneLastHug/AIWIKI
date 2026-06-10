# 子系统：platform/reworkd_platform/web/api/agent/tools

## 解决什么问题

`platform/reworkd_platform/web/api/agent/tools` 是 Agent 执行能力的工具层。它把“模型决定要做什么”转换成“后端实际调用哪个能力”：搜索公开网页、生成图片、编写或解释代码、访问用户授权的私有知识源、或退回到纯推理。

这个目录不负责 Agent 的完整任务编排，也不直接定义 HTTP API；它更像一个可插拔工具注册与执行框架。上游 `OpenAIAgentService.analyze_task_agent()` 会把可用工具转成 OpenAI function calling 可识别的 schema，让模型选择 `action` 和 `arg`；随后 `execute_task_agent()` 根据 `action` 找到对应 `Tool` 子类并调用 `call()`，最终返回 `StreamingResponse`，供前端按流式内容展示执行结果。

## 相关目录和文件

核心文件集中在几个层次：

`platform/reworkd_platform/web/api/agent/tools/tool.py` 定义抽象基类 `Tool`，约束所有工具必须实现 `call()`，并提供 `available()`、`dynamic_available()` 两类可用性判断。

`platform/reworkd_platform/web/api/agent/tools/tools.py` 是注册表和查找层，维护外部工具、默认工具、名称格式化、名称反查、工具概览等函数。

`platform/reworkd_platform/web/api/agent/tools/open_ai_function.py` 把 `Tool` 类转换为 OpenAI function 描述，包含函数名、说明、参数结构，以及统一的 `reasoning`、`arg` 两个参数。

`platform/reworkd_platform/web/api/agent/tools/search.py`、`sidsearch.py`、`image.py`、`code.py`、`reason.py`、`conclude.py`、`wikipedia_search.py` 是具体工具实现。其中当前注册表实际暴露的外部工具主要是 `Image`、`Code`、`SID`，默认工具是 `Search`；`Wikipedia` 存在但在注册处被注释掉，`Reason` 和 `Conclude` 主要作为内部能力或测试对象存在。

`platform/reworkd_platform/web/api/agent/tools/utils.py` 提供摘要相关的通用结构和函数，例如 `CitedSnippet`、`Snippet`、`summarize()`、`summarize_with_sources()`、`summarize_sid()`。

邻近调用方主要是 `platform/reworkd_platform/web/api/agent/agent_service/open_ai_agent_service.py`、`platform/reworkd_platform/web/api/agent/analysis.py`、`platform/reworkd_platform/web/api/agent/views.py`。测试集中在 `platform/reworkd_platform/tests/agent/test_tools.py`。

## 核心对象

`Tool` 是所有工具的统一接口。它保存 `model` 和 `language`，并要求子类实现异步 `call(goal, task, input_str, user, oauth_crud)`。`description` 面向模型，用于 function calling 的工具选择；`public_description` 面向 `/tools` 接口和前端展示；`arg_description` 描述模型应如何填充工具参数；`image_url` 用于前端展示图标。

`get_external_tools()` 返回用户可见、可选的外部能力：`Image`、`Code`、`SID`。`get_default_tools()` 返回默认工具，目前只有 `Search`。`get_user_tools(tool_names, user, crud)` 会把用户选择的工具与默认工具合并，然后按 `dynamic_available()` 过滤。这个设计保证即使用户没有显式选择任何工具，分析阶段仍然有 `Search` 可用。

`FunctionDescription` 和 `get_tool_function()` 是模型选择工具的桥。生成的 function schema 统一要求模型输出 `reasoning` 和 `arg`。`reasoning` 进入 `Analysis.reasoning`，用于解释选择理由；`arg` 是传给具体工具的输入。

`Analysis` 位于邻近文件 `platform/reworkd_platform/web/api/agent/analysis.py`，虽然不在本目录内，但和工具层强绑定。它校验 `action` 必须是 `get_available_tools_names()` 中的有效名称，并额外限制 `search` 的 `arg` 不能为空。

## 运行流程

典型链路从 `/analyze` 开始。`views.py` 接收 `AgentTaskAnalyze`，调用 `OpenAIAgentService.analyze_task_agent()`。服务层先调用 `get_user_tools()`：用户传入的 `tool_names` 会通过 `get_tool_from_name()` 映射成工具类，再追加默认工具 `Search`，最后通过 `dynamic_available()` 过滤。例如 `SID.dynamic_available()` 会检查当前用户是否已有 `sid` OAuth 安装和访问 token。

随后服务层对每个工具调用 `get_tool_function()`，把工具说明转成 OpenAI function schema。模型根据目标、当前任务和 function 列表返回 `function_call`，其中函数名成为 `Analysis.action`，函数参数中的 `reasoning`、`arg` 成为 `Analysis` 字段。如果解析失败或校验失败，会退回 `Analysis.get_default_analysis(task)`，根据当前片段推断其默认行为最终会指向默认工具。

执行阶段由 `/execute` 调用 `OpenAIAgentService.execute_task_agent()`。它通过 `get_tool_from_name(analysis.action)` 找到工具类，实例化时注入当前聊天模型和语言，然后调用 `call()`。不同工具的行为不同：`Search` 请求搜索服务，提取 answer box 和 organic snippets，再通过 `summarize_with_sources()` 让模型生成带来源摘要；`SID` 先访问用户私有索引，拿不到安装、token 或结果时退回 `Search`；`Image` 优先使用 Replicate 生成图片，缺少 Replicate key 时退回 OpenAI 图片接口；`Code` 使用 `code_prompt` 和 `LLMChain` 生成流式代码相关回答；`Reason` 使用 `execute_task_prompt` 做纯模型推理。

## 上下游依赖

上游依赖包括 API 层和 Agent 服务层。`platform/reworkd_platform/web/api/agent/views.py` 的 `/tools` 接口调用 `get_external_tools()`，只返回 `available()` 为真的工具，用于前端展示可选工具。`/analyze` 和 `/execute` 则通过 `AgentService` 间接进入工具选择和执行。

模型相关依赖主要来自 `langchain`、`lanarky.responses.StreamingResponse`、`BaseChatModel`、`LLMChain` 和项目内 prompts。工具执行普遍返回 `text/event-stream`，因此调用方预期是流式消费。

外部服务依赖包括搜索服务、Replicate、OpenAI 图片接口、SID API 和 SID OAuth。源码中出现的真实外部地址应理解为第三方服务端点，文档中不展开真实网址。配置依赖集中在 `reworkd_platform.settings`，例如 `serp_api_key`、`replicate_api_key`、`openai_api_key`、`sid_enabled`、`sid_client_id`、`sid_client_secret`、`sid_redirect_uri`。

数据层依赖主要是 `OAuthCrud`、`OauthCredentials`、`UserBase` 和 `encryption_service`。其中 `SID` 会读取并刷新 OAuth token，刷新后保存到数据库会话。

## 修改时最容易踩的坑

新增工具时只写 `Tool` 子类还不够，必须把它加入 `tools.py` 的注册函数，否则模型分析阶段和 `/tools` 展示都看不到它。若只是内部回退工具，可以不放入 `get_external_tools()`，但要确认是否需要出现在 `get_available_tools_names()` 的校验列表中。

`description` 和 `public_description` 语义不同。前者直接影响模型选择工具，写得过宽会导致误选；后者给用户看，写得过技术化会影响前端理解。`arg_description` 也很关键，因为 function schema 只有统一的 `arg` 字段，具体参数约束全靠这里提示模型。

`available()` 和 `dynamic_available()` 不要混用。`available()` 适合检查全局配置，例如 API key 或 feature flag；`dynamic_available()` 适合检查当前用户状态，例如 OAuth 授权。`/tools` 当前只检查 `available()`，而分析阶段会检查 `dynamic_available()`，所以前端展示可用不代表某个用户实际已授权。

`get_tool_from_name()` 找不到工具时会静默返回默认 `Search`。这让系统更容错，但也可能掩盖拼写错误或未注册工具的问题。测试里明确覆盖了这个行为，修改时要谨慎。

`Search` 和 `SID` 都依赖外部网络服务，并且最终会再次调用模型摘要。异常处理和空结果分支会影响用户看到的是摘要、空结果提示，还是回退工具。尤其 `SID.call()` 会在无结果时回退 `Search`，修改私有搜索逻辑时要确认不会意外泄露“本应只查私有源”的任务到公开搜索。

`Wikipedia` 文件存在但注册处注释掉，且 `call()` 当前返回固定不可用文案。根据当前片段推断，这是未完成或暂时禁用能力，不应仅因为文件存在就认为生产可用。

## 推荐阅读顺序

先读 `platform/reworkd_platform/web/api/agent/tools/tool.py`，理解统一接口、工具元数据和可用性判断。

再读 `platform/reworkd_platform/web/api/agent/tools/tools.py`，掌握哪些工具被注册、哪些是默认工具、名称如何格式化和反查。

接着读 `platform/reworkd_platform/web/api/agent/tools/open_ai_function.py` 和 `platform/reworkd_platform/web/api/agent/analysis.py`，理解工具如何变成模型可调用的 function，以及模型输出如何被校验为 `Analysis`。

然后读 `platform/reworkd_platform/web/api/agent/agent_service/open_ai_agent_service.py` 中的 `analyze_task_agent()` 和 `execute_task_agent()`，把“选择工具”和“执行工具”的完整链路串起来。

最后按具体能力阅读实现：先看 `search.py` 和 `utils.py`，因为默认工具和摘要模式最基础；再看 `sidsearch.py` 理解用户授权和私有搜索；最后看 `image.py`、`code.py`、`reason.py`、`conclude.py`，补齐各工具的差异化执行方式。
