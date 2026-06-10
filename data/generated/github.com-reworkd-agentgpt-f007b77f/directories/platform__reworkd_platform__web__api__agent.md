# 子系统：platform/reworkd_platform/web/api/agent

## 解决什么问题

`platform/reworkd_platform/web/api/agent` 是 AgentGPT 后端中“代理循环”的 HTTP API 子系统。它把前端发来的目标、任务、执行结果、模型设置和工具选择，转换成一组可调用的 Agent 操作：初始化任务、分析下一步该用什么工具、执行工具、根据结果生成后续任务、汇总结果，以及基于历史结果继续对话。

这个目录本身不是持久化层，也不是前端状态机；它更像一个编排层。它负责校验请求、记录每个 loop step、创建 LLM 实例、调用 LangChain/OpenAI、选择工具类，并把部分执行结果以 `text/event-stream` 形式流式返回给客户端。

## 相关目录和文件

入口文件是 `platform/reworkd_platform/web/api/agent/views.py`，定义 `/agent/start`、`/agent/analyze`、`/agent/execute`、`/agent/create`、`/agent/summarize`、`/agent/chat`、`/agent/tools` 等路由。总路由在 `platform/reworkd_platform/web/api/router.py` 中把该 router 挂到 `/agent` 前缀。

`platform/reworkd_platform/web/api/agent/dependancies.py` 负责 FastAPI 依赖注入和请求校验，同时通过 `AgentCRUD` 创建 run/task 记录。文件名里的 `dependancies` 是现有拼写，修改导入时不要按常见拼写 `dependencies` 误改。

`platform/reworkd_platform/web/api/agent/agent_service/` 是服务抽象和实现层。`agent_service.py` 定义 `AgentService` 协议，`agent_service_provider.py` 根据设置创建真实服务或 mock 服务，`open_ai_agent_service.py` 承载主要 LLM 编排逻辑，`mock_agent_service.py` 用于 mock 模式。

`platform/reworkd_platform/web/api/agent/tools/` 是工具系统。`tool.py` 定义工具基类，`tools.py` 维护可用工具列表和名称映射，`search.py`、`code.py`、`image.py`、`sidsearch.py`、`reason.py` 等提供具体能力。`open_ai_function.py` 把工具描述转换为 OpenAI function calling 所需的 function schema。

`analysis.py`、`task_output_parser.py`、`helpers.py`、`model_factory.py`、`prompts.py` 是支撑模块：分别处理工具分析结果模型、任务列表解析、OpenAI 异常包装、模型实例创建和 prompt 模板。

## 核心对象

`AgentService` 是路由层依赖的核心接口，暴露 `start_goal_agent`、`analyze_task_agent`、`execute_task_agent`、`create_tasks_agent`、`summarize_task_agent`、`chat`。路由只依赖这个协议，因此可以在 mock 模式下切换到 `MockAgentService`。

`OpenAIAgentService` 是主要实现。它持有 `WrappedChatOpenAI` 或 `WrappedAzureChatOpenAI`、`ModelSettings`、`TokenService`、当前用户和 `OAuthCrud`。它的职责不是保存业务状态，而是围绕 prompt、token 预算、工具选择和流式响应完成一次 Agent step。

`Analysis` 表示 “分析阶段” 产物，包含 `reasoning`、`action`、`arg`。其中 `action` 必须是工具注册表里的合法工具名；如果选择 `search`，`arg` 不能为空。解析失败时会回退到默认 `search` 分析。

`Tool` 是工具契约。每个工具类提供 `description`、`public_description`、`arg_description`、`image_url`，并实现异步 `call(goal, task, input_str, user, oauth_crud)`。`available()` 和 `dynamic_available()` 分别处理静态配置可用性和用户/OAuth 相关可用性。

`ModelSettings` 定义在 `platform/reworkd_platform/schemas/agent.py`，包含模型名、用户自定义 API key、temperature、max_tokens、language，并按模型上限校验 token 数。

## 运行流程

一次典型循环从 `/agent/start` 开始。`agent_start_validator` 先通过 `AgentCRUD.create_run` 创建 run，返回带 `run_id` 的 `AgentRun`。随后 `OpenAIAgentService.start_goal_agent` 使用 `start_goal_prompt` 让模型把目标拆成初始任务，并由 `TaskOutputParser` 解析成字符串列表，响应为 `NewTasksResponse`。

客户端选择任务后调用 `/agent/analyze`。后端记录 `analyze` step，再根据请求中的 `tool_names` 加上默认工具构造可用工具列表。`OpenAIAgentService.analyze_task_agent` 把工具转换成 OpenAI function schema，让模型返回 function call。function 名成为 `Analysis.action`，arguments 被解析为 `reasoning` 和 `arg`。

随后 `/agent/execute` 根据 `Analysis.action` 找到具体工具类。比如 `search` 会调用外部搜索服务并用模型总结带来源片段，`code` 会基于 `code_prompt` 流式生成代码相关回答，`image` 会调用图像生成服务并流式返回 Markdown 图片内容。执行接口返回 `StreamingResponse`，因此调用方要按 SSE/流式文本处理。

执行结果回传到 `/agent/create` 后，服务使用 `create_tasks_prompt` 结合目标、现有任务、上一任务和结果生成新任务，并避免返回已完成或重复任务。`/agent/summarize` 和 `/agent/chat` 则面向最终结果汇总和后续问答，代码中会强制使用 `gpt-3.5-turbo-16k` 并重新计算 token 预算。

## 上下游依赖

上游主要是 FastAPI 路由系统、前端 Agent 循环调用方，以及认证依赖 `get_current_user`。所有需要写入 run/task 的接口都会经由 `dependancies.py`，因此还依赖数据库会话 `get_db_session` 和 `AgentCRUD`。

中游依赖 `platform/reworkd_platform/schemas/agent.py` 的请求/响应模型、`TokenService` 的 token 计算、`settings` 中的 OpenAI/Azure/Helicone/mock/搜索/图像服务配置，以及 `OAuthCrud` 的用户授权信息。

下游是 LangChain、OpenAI ChatCompletion/function calling、Lanarky streaming response、搜索服务、Replicate 或 OpenAI 图片服务。根据当前片段推断，SID 工具还会依赖用户 OAuth 或外部数据源，因为工具可用性判断接受 `user` 和 `OAuthCrud`。

## 修改时最容易踩的坑

第一，路由依赖链会产生副作用。`agent_analyze_validator`、`agent_execute_validator` 等不只是校验请求，还会创建 `AgentTask` 并检查循环次数。如果绕过这些 validator，数据库中的 step 统计和限流逻辑会失效。

第二，工具名是隐式协议。`get_tool_name()` 会把类名小写，例如 `Search` 变成 `search`。`Analysis.action`、OpenAI function name、`get_tool_from_name()` 都依赖同一套命名规则。新增或重命名工具时，要同时检查工具注册、function 描述、前端传入的 `tool_names` 和历史数据兼容性。

第三，流式接口和非流式接口混在同一服务里。`start`、`analyze`、`create` 返回结构化 JSON；`execute`、`summarize`、`chat` 返回 `StreamingResponse`。修改返回类型时要同步客户端消费方式和 FastAPI 类型标注。

第四，token 预算会被多处修改。`TokenService.calculate_max_tokens()` 会根据 prompt 调整模型参数，`execute_task_agent` 还会在大 token 场景下手动减少 `max_tokens`，`summarize_task_agent` 会强行覆盖模型名和 token 数。排查模型输出变短或模型不符合请求时，要先看这些覆盖逻辑。

第五，错误处理并不完全在路由层。`helpers.py` 会把 OpenAI SDK 异常包装成 `OpenAIError`；`analyze_task_agent` 捕获解析失败后会静默回退到默认搜索。新增异常路径时，要决定是暴露错误、回退默认工具，还是返回流式失败文本。

第六，`ModelSettings` 使用 Pydantic 字段 `model_settings`，请求示例里出现 `modelSettings`。这通常依赖项目的 Pydantic alias 或前端序列化约定；修改 schema 命名时要特别确认请求体兼容性。

## 推荐阅读顺序

先读 `platform/reworkd_platform/web/api/router.py`，确认 `/agent` 的挂载位置。然后读 `platform/reworkd_platform/web/api/agent/views.py`，把每个 HTTP 端点和 Agent 循环阶段对应起来。

接着读 `platform/reworkd_platform/web/api/agent/dependancies.py` 和 `platform/reworkd_platform/db/crud/agent.py`，理解 run/task 如何落库、如何限制最大循环和多次 summary。

第三步读 `platform/reworkd_platform/web/api/agent/agent_service/agent_service.py`、`platform/reworkd_platform/web/api/agent/agent_service/agent_service_provider.py`、`platform/reworkd_platform/web/api/agent/agent_service/open_ai_agent_service.py`，掌握服务抽象、mock 切换和真实 LLM 编排。

最后读 `platform/reworkd_platform/web/api/agent/analysis.py`、`platform/reworkd_platform/web/api/agent/tools/tool.py`、`platform/reworkd_platform/web/api/agent/tools/tools.py`、`platform/reworkd_platform/web/api/agent/tools/open_ai_function.py`，再按需要深入 `search.py`、`code.py`、`image.py` 等具体工具实现。
