# 子系统：platform/reworkd_platform/web/api/agent/agent_service

## 解决什么问题

`platform/reworkd_platform/web/api/agent/agent_service` 是 AgentGPT 后端中“代理执行循环”的服务层。它把上层 FastAPI 路由传入的目标、任务、工具选择、执行结果等请求，转换为对 LLM、工具系统、token 预算和流式响应的调用。

这个目录不直接定义 HTTP endpoint，也不直接实现具体搜索、代码、图片等工具能力；它负责组织这些能力：创建初始任务、分析当前任务应使用哪个工具、执行工具、根据执行结果生成后续任务，以及对多轮结果做总结或聊天问答。可以把它理解为 `/agent` API 与底层 LLM/Tool/DB/Auth 能力之间的编排层。

## 相关目录和文件

核心文件集中在目标目录内：

`platform/reworkd_platform/web/api/agent/agent_service/agent_service.py` 定义 `AgentService` Protocol，是该子系统对外暴露的服务接口。它规定了 `start_goal_agent`、`analyze_task_agent`、`execute_task_agent`、`create_tasks_agent`、`summarize_task_agent`、`chat` 六个异步方法。

`platform/reworkd_platform/web/api/agent/agent_service/open_ai_agent_service.py` 是真实实现，类名为 `OpenAIAgentService`。它使用 LangChain、OpenAI function calling、项目内工具系统和 token 服务完成完整 Agent 流程。

`platform/reworkd_platform/web/api/agent/agent_service/mock_agent_service.py` 是 `MockAgentService`，在 `settings.ff_mock_mode_enabled` 开启时返回固定结果或模拟流式文本，主要用于避免真实调用 OpenAI API。

`platform/reworkd_platform/web/api/agent/agent_service/agent_service_provider.py` 提供 `get_agent_service`，这是 FastAPI 依赖注入工厂。它根据 validator、当前用户、token 服务、OAuth CRUD、模型设置等构造 `OpenAIAgentService` 或 `MockAgentService`。

重要邻近文件包括：`platform/reworkd_platform/web/api/agent/views.py` 定义 `/start`、`/analyze`、`/execute`、`/create`、`/summarize`、`/chat` 路由；`platform/reworkd_platform/web/api/agent/dependancies.py` 负责请求校验和 run/task 记录创建；`platform/reworkd_platform/web/api/agent/prompts.py` 提供各阶段 prompt；`platform/reworkd_platform/web/api/agent/analysis.py` 定义工具分析结果结构；`platform/reworkd_platform/web/api/agent/tools` 提供具体工具和 OpenAI function schema；`platform/reworkd_platform/web/api/agent/model_factory.py` 创建 OpenAI 或 Azure OpenAI chat model。

## 核心对象

`AgentService` 是服务契约。上层路由只依赖这个 Protocol，因此可以在真实 LLM 实现和 Mock 实现之间切换。它的六个方法基本对应 Agent 循环的六类动作：启动目标、分析任务、执行任务、创建后续任务、汇总结果、基于结果聊天。

`OpenAIAgentService` 是核心编排对象。构造时注入 `WrappedChatOpenAI` 或 `WrappedAzureChatOpenAI`、`ModelSettings`、`TokenService`、callbacks、`UserBase` 和 `OAuthCrud`。这些依赖分别用于模型调用、语言和 token 配置、token 预算计算、流式回调、按用户判断工具可用性，以及检查 OAuth 授权。

`MockAgentService` 是替身实现。它返回固定任务、固定 `Analysis` 和通过 `stream_string` 构造的模拟流式响应。注意它在 async 方法里使用 `time.sleep`，适合开发模拟，不适合高并发真实性能测试。

`Analysis` 和 `AnalysisArguments` 描述“任务分析”的结果。`Analysis` 包含 `action`、`arg`、`reasoning`。其中 `action` 会通过 validator 校验是否属于可用工具名；如果 action 是 search，还会要求 `arg` 非空。`Analysis.get_default_analysis` 在模型输出不可解析或校验失败时回退到默认工具。

## 运行流程

请求首先进入 `platform/reworkd_platform/web/api/agent/views.py`。每个 endpoint 通过 `Depends(get_agent_service(...))` 获取服务实例，同时通过 `agent_start_validator`、`agent_analyze_validator` 等 validator 解析请求体并写入 run/task 记录。

`get_agent_service` 内部先拿到 `AgentRun`、当前用户、`TokenService` 和 `OAuthCrud`。如果 `settings.ff_mock_mode_enabled` 为真，直接返回 `MockAgentService`。否则调用 `create_model` 创建模型，再构造 `OpenAIAgentService`。对于需要流式输出的 `/execute`、`/summarize`、`/chat`，调用方会把 `streaming=True` 传给模型工厂；摘要和聊天还会强制使用 `gpt-3.5-turbo-16k`。

`start_goal_agent` 使用 `start_goal_prompt`，根据用户目标生成最多若干初始搜索查询。返回内容通过 `TaskOutputParser` 解析成 `List[str]`，并过滤掉无效任务文本。

`analyze_task_agent` 根据前端传入的 `tool_names` 加上默认工具，调用 `get_user_tools` 过滤当前用户可用工具，再用 `get_tool_function` 转成 OpenAI function descriptions。模型通过 function calling 选择工具，并返回 `reasoning` 与 `arg`。解析成功后生成 `Analysis`；解析失败则使用默认 search 分析。

`execute_task_agent` 根据 `analysis.action` 找到工具类，实例化后调用工具的 `call(goal, task, analysis.arg, user, oauth_crud)`。该方法返回 `StreamingResponse`，因此执行结果通常以 SSE 或类似流式形式返回给前端。

`create_tasks_agent` 在某个任务执行完成后，使用 `create_tasks_prompt`、当前未完成任务、刚完成任务和结果生成一个新的后续任务。如果新任务已经存在于 `completed_tasks + tasks` 中，则返回空列表，避免重复。

`summarize_task_agent` 会把结果拼接后按 token 截断到约 7000 tokens，再调用 `tools.utils.summarize` 生成流式总结。`chat` 则把历史 results 作为 `HumanMessage` 上下文，加上当前 message，通过 `LLMChain` 产生流式回答。

## 上下游依赖

上游主要是 `platform/reworkd_platform/web/api/agent/views.py` 和 `platform/reworkd_platform/web/api/agent/dependancies.py`。前者暴露 HTTP 路由，后者负责创建 run/task 记录并返回带 `run_id` 的 schema 对象。请求数据结构来自 `platform/reworkd_platform/schemas/agent.py`，例如 `AgentRun`、`AgentTaskAnalyze`、`AgentTaskExecute`、`AgentTaskCreate`、`AgentSummarize`、`AgentChat`。

下游依赖包括 LLM、tokenizer、工具系统和持久化辅助。模型由 `model_factory.create_model` 创建，可能走 OpenAI、Azure OpenAI 或 Helicone 代理配置；token 预算由 `TokenService.calculate_max_tokens`、`tokenize`、`detokenize` 处理；工具从 `platform/reworkd_platform/web/api/agent/tools/tools.py` 获取，当前默认工具是 `Search`，外部工具包括 `Image`、`Code`、`SID`；OAuth 状态通过 `OAuthCrud` 参与 `dynamic_available` 和工具执行。

错误处理主要通过 `helpers.openai_error_handler` 和 `helpers.call_model_with_handling` 包装 OpenAI 异常，将认证、限流、服务不可用、模型权限等错误转换为项目内 `OpenAIError`。

## 修改时最容易踩的坑

第一，`AgentService` 是 Protocol，路由只看方法签名。新增或修改服务方法时，需要同时更新 `AgentService`、`OpenAIAgentService`、`MockAgentService` 和上层 `views.py`，否则类型上看似松散，运行时却会缺方法或参数不一致。

第二，`analyze_task_agent` 依赖 OpenAI function calling 的返回格式。`AnalysisArguments` 只包含 `reasoning` 和 `arg`，`action` 来自 `function_call.name`。如果修改工具 schema、工具名格式或 `get_tool_name`，会影响 `Analysis` validator 和 `get_tool_from_name` 的匹配。

第三，token 预算不是纯只读逻辑。`execute_task_agent` 会在 `self.model.max_tokens > 3000` 时直接调整模型对象；`summarize_task_agent` 和 `chat` 也会直接改 `self.model.model_name`。如果未来复用同一个 service/model 实例处理多个阶段，需要注意这些可变状态的副作用。

第四，Mock 实现里使用同步 `time.sleep`。它能模拟延迟，但会阻塞事件循环；如果拿它做并发压测，结果不能代表真实异步链路。

第五，`create_tasks_agent` 只返回单个 completion，且只用字符串完全相等判断重复。prompt 输出中的空白、大小写或轻微改写不会被去重；如果要增强去重，应在这里统一规范化或引入更明确的任务 ID 机制。

第六，工具可用性分为静态 `available()` 和动态 `dynamic_available(user, crud)`。只在 `/tools` 展示可见，不代表 `analyze_task_agent` 一定会选择；实际分析阶段还会结合用户授权和默认工具重新过滤。

## 推荐阅读顺序

建议先读 `platform/reworkd_platform/web/api/agent/views.py`，理解六个 endpoint 如何映射到服务方法。然后读 `platform/reworkd_platform/web/api/agent/agent_service/agent_service.py`，建立服务接口轮廓。

接着读 `platform/reworkd_platform/web/api/agent/agent_service/agent_service_provider.py`，看依赖注入、Mock 切换、模型创建和用户上下文如何进入服务层。

然后重点阅读 `platform/reworkd_platform/web/api/agent/agent_service/open_ai_agent_service.py`，按 `start_goal_agent`、`analyze_task_agent`、`execute_task_agent`、`create_tasks_agent`、`summarize_task_agent`、`chat` 的顺序串起完整 Agent 循环。

最后补读 `platform/reworkd_platform/web/api/agent/prompts.py`、`platform/reworkd_platform/web/api/agent/analysis.py`、`platform/reworkd_platform/web/api/agent/task_output_parser.py` 和 `platform/reworkd_platform/web/api/agent/tools/tools.py`。这几处解释了模型为什么按当前格式输出、输出如何被解析，以及 action 最终怎样落到具体工具执行。
