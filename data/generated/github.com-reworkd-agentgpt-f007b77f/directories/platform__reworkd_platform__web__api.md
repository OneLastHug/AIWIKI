# 子系统：platform/reworkd_platform/web/api

## 解决什么问题

`platform/reworkd_platform/web/api` 是 Reworkd Platform 后端的 HTTP API 层，负责把 FastAPI 路由、认证依赖、请求校验、业务服务注入、错误响应和 AI Agent 执行能力组织在一起。它不是纯粹的 controller 目录：除了 `auth`、`models`、`monitoring`、`metadata` 这类常规接口外，`agent` 子目录还承载了 AgentGPT 核心循环的编排逻辑，包括任务启动、任务分析、工具选择、任务执行、后续任务生成、总结和聊天。

应用入口在 `platform/reworkd_platform/web/application.py` 中创建 FastAPI 实例，并通过 `app.include_router(router=api_router, prefix="/api")` 挂载本目录的总路由。因此本目录对外暴露的接口统一位于 `/api/...` 命名空间下。`router.py` 再把 `monitoring`、`agent`、`models`、`auth`、`metadata` 分别挂到 `/monitoring`、`/agent`、`/models`、`/auth`、`/metadata`。

## 相关目录和文件

`router.py` 是 API 子系统的汇总入口，所有新增业务路由通常需要从这里接入。

`dependencies.py` 提供跨 API 使用的 FastAPI 依赖，当前最重要的是 `get_current_user`：它从 `Authorization` Bearer token 中取 session token，通过 `UserCrud.get_user_session` 查库，并检查过期时间，最后返回 `UserBase`。

`agent/views.py` 是 Agent HTTP 接口层，定义 `/start`、`/analyze`、`/execute`、`/create`、`/summarize`、`/chat`、`/tools`。这些函数本身较薄，主要通过 `Depends(...)` 调用校验器和 `AgentService`。

`agent/dependancies.py` 负责 Agent 请求的副作用型校验：`agent_start_validator` 会创建一次 `AgentRun`，其余步骤通过 `validate` 创建对应 `AgentTask`，并将新的 task id 回填到 `run_id`。文件名是 `dependancies.py`，拼写与常见的 `dependencies` 不同，引用时不能改错。

`agent/agent_service` 定义服务协议和实现。`agent_service.py` 给出 `AgentService` Protocol；`agent_service_provider.py` 根据配置选择 `MockAgentService` 或 `OpenAIAgentService`；`open_ai_agent_service.py` 是真实 LLM 编排实现。

`agent/tools` 定义工具抽象和具体工具。`tool.py` 是基类，`tools.py` 维护工具注册、默认工具、名称转换和动态可用性检查；`search.py`、`code.py`、`image.py`、`sidsearch.py`、`reason.py`、`conclude.py` 是具体能力。

`models/views.py` 暴露模型列表及用户访问状态；`auth/views.py` 处理 OAuth 安装、卸载、回调和组织信息；`metadata.py` 抓取页面标题、host、favicon；`monitoring/views.py` 提供健康检查和错误检查；`errors.py`、`error_handling.py`、`http_responses.py` 统一异常类型和常用 HTTP 响应。

`memory` 子目录定义 `AgentMemory` 抽象、`MemoryWithFallback` 和 `NullAgentMemory`。根据当前片段推断，它是给外部记忆服务或向量检索服务使用的接口层，因为 `services/pinecone/pinecone.py` 引用了 `AgentMemory`，但本目录内没有直接暴露 HTTP 端点。

## 核心对象

`api_router` 是整个 API 子系统的根路由对象，最终被 `application.py` 挂载到 `/api`。

`get_current_user` 是大多数受保护接口的认证入口。`auth`、`models`、`agent` 相关接口都依赖它，因此 session 存储、过期判断和 `UserBase` 字段会影响整个 API 层。

`AgentRun`、`AgentTaskAnalyze`、`AgentTaskExecute`、`AgentTaskCreate`、`AgentSummarize`、`AgentChat` 来自 `platform/reworkd_platform/schemas/agent.py`，是 Agent 循环各阶段的请求模型。`ModelSettings` 包含模型名、custom API key、temperature、max_tokens、language，并校验 token 上限。

`AgentCRUD` 位于 `platform/reworkd_platform/db/crud/agent.py`，虽然不在目标目录内，但它是 Agent API 的关键依赖：`create_run` 创建运行记录，`create_task` 创建步骤记录，`validate_task_count` 限制每类步骤的最大循环次数，并禁止多次 summary。

`AgentService` 是业务服务协议，`OpenAIAgentService` 是主要实现。它把 LangChain prompt、OpenAI function calling、工具执行、token 预算和 streaming response 串起来。

`Analysis` 和 `AnalysisArguments` 表示分析阶段的结果。`Analysis.action` 会校验是否属于可用工具名；当 search 工具被选中时还要求 `arg` 非空。分析失败时会通过 `Analysis.get_default_analysis` 回退到默认工具。

`Tool` 是工具基类。每个工具需要实现 `call(...)`，并可通过 `available()`、`dynamic_available(user, oauth_crud)` 控制静态和用户维度的可用性。`get_tool_function` 会把工具描述转换为 OpenAI function calling 所需的 schema。

`PlatformaticError` 是预期业务异常基类，派生出 `OpenAIError`、`ReplicateError`、`MaxLoopsError`、`MultipleSummaryError`。这些异常由 `platformatic_exception_handler` 转成 JSON 响应。

## 运行流程

典型 Agent 流程从前端调用 `/api/agent/start` 开始。请求体先进入 `agent_start_validator`，该校验器依赖 `AgentCRUD` 和当前用户，在数据库中创建 `AgentRun`，然后返回带 `run_id` 的 `AgentRun`。随后 `get_agent_service` 会读取同一个请求模型、当前用户、`TokenService`、`OAuthCrud`，并根据 `settings.ff_mock_mode_enabled` 选择 mock 服务或真实的 `OpenAIAgentService`。

`start_goal_agent` 使用 `start_goal_prompt` 让模型基于 goal 生成初始任务列表，并用 `TaskOutputParser` 解析为 `NewTasksResponse`。

之后 `/analyze` 会为当前 run 创建 `analyze` 类型任务记录，读取用户选择的工具名，通过 `get_user_tools` 合并默认工具并过滤可用工具，再把工具转换成 OpenAI function schema。模型返回 function call 后，服务将 arguments 解析成 `Analysis`，包含 `reasoning`、`action`、`arg`。

`/execute` 根据 `Analysis.action` 查找工具类，实例化后调用工具的 `call` 方法，返回 `text/event-stream` 风格的流式响应。搜索工具会调用外部搜索服务，根据当前片段可知服务地址在源码中写为外部 URL；文档中不展开真实地址。搜索失败时会回退到 `Reason` 工具。

`/create` 根据已有任务、最后任务、执行结果和已完成任务生成下一批任务。`/summarize` 和 `/chat` 强制使用 `gpt-3.5-turbo-16k`，前者对结果做截断和总结，后者把历史结果作为 `HumanMessage` 注入聊天链并流式返回。

## 上下游依赖

上游主要是 FastAPI 应用构造器、前端客户端和认证会话。`application.py` 控制 CORS、OpenAPI 路径、默认响应类和异常处理器；前端通过 `/api/...` 调用本目录路由；认证依赖来自数据库中的 user session。

下游包括数据库、schema、LLM、LangChain、tokenizer、OAuth 安装信息和外部工具服务。数据库侧涉及 `UserCrud`、`AgentCRUD`、`OAuthCrud`、`OrganizationCrud`。模型侧通过 `model_factory.py` 创建 `WrappedChatOpenAI` 或 `WrappedAzureChatOpenAI`，并支持 Helicone header、Azure OpenAI、用户自定义 API key。工具侧依赖外部搜索、图片生成或 SID OAuth 安装状态；`auth/views.py` 又依赖 `services.oauth_installers` 完成第三方 OAuth 流程。

错误处理的上游挂载在 `application.py`，下游依赖本目录的 `PlatformaticError` 层级。普通权限错误则多用 `http_responses.forbidden`、`not_found` 生成 FastAPI `HTTPException`。

## 修改时最容易踩的坑

第一，`agent/dependancies.py` 的校验器会写数据库，不只是校验请求体。给某个 Agent endpoint 增加 `Depends(...)` 时，要意识到它可能创建 `AgentTask`，并触发 `max_loops` 或多 summary 限制。

第二，`get_agent_service` 同时依赖请求模型和用户认证。新增 Agent 接口如果绕过这个 provider，可能漏掉 mock mode、token service、OAuthCrud、streaming 参数或强制模型设置。

第三，工具名称来自类名小写化，例如 `Search` 对应 `search`。`Analysis.action` 校验依赖 `get_available_tools_names()`，新增工具必须在 `tools.py` 注册，否则模型即使返回该 action 也会校验失败或回退默认工具。

第四，`execute_task_agent` 返回的是流式响应，工具实现也多返回 `StreamingResponse`。不要把它当普通 JSON endpoint 改造，否则前端消费方式会断。

第五，`ModelSettings.max_tokens` 在 schema 层按模型上限校验，`OpenAIAgentService` 还会在执行阶段临时调整 `self.model.max_tokens`。修改 token 逻辑时需要同时看 schema、`TokenService.calculate_max_tokens` 和各服务方法。

第六，`metadata.py` 会请求用户传入的 URL 并解析 HTML。它捕获网络异常后仍返回 hostname 和 favicon 推断值，但其他异常会包装为 `PlatformaticError`。改这里要注意 SSRF、超时和错误日志策略。

第七，异常处理器返回的 HTTP status 固定为 409，但响应体内还有 `code` 字段；`MaxLoopsError` 等会传入 429。调用方如果只看 HTTP status，可能与业务 code 不一致。

## 推荐阅读顺序

1. 先读 `platform/reworkd_platform/web/application.py`，理解 API 如何挂载到 FastAPI，以及异常处理和 CORS 在哪里配置。
2. 再读 `platform/reworkd_platform/web/api/router.py`，建立 `/api` 下各子路由的地图。
3. 阅读 `platform/reworkd_platform/web/api/dependencies.py`、`platform/reworkd_platform/web/api/http_responses.py`、`platform/reworkd_platform/web/api/errors.py`、`platform/reworkd_platform/web/api/error_handling.py`，掌握认证和错误模型。
4. 阅读 `platform/reworkd_platform/schemas/agent.py` 和 `platform/reworkd_platform/db/crud/agent.py`，理解 Agent 请求模型、run/task 持久化和循环限制。
5. 阅读 `platform/reworkd_platform/web/api/agent/views.py`、`platform/reworkd_platform/web/api/agent/dependancies.py`，看 HTTP endpoint 如何转换为服务调用。
6. 阅读 `platform/reworkd_platform/web/api/agent/agent_service/agent_service_provider.py`、`platform/reworkd_platform/web/api/agent/agent_service/open_ai_agent_service.py`，理解真实 Agent 流程。
7. 最后读 `platform/reworkd_platform/web/api/agent/tools/tool.py`、`platform/reworkd_platform/web/api/agent/tools/tools.py` 和具体工具文件，再补看 `auth/views.py`、`models/views.py`、`metadata.py`、`monitoring/views.py`。
