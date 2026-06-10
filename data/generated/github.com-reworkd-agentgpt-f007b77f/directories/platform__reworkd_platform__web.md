# 子系统：platform/reworkd_platform/web

## 解决什么问题

`platform/reworkd_platform/web` 是 Reworkd Platform 的后端 Web/API 子系统，负责把内部的 agent 编排、认证、模型列表、OAuth 安装、网页元信息提取、健康检查等能力暴露为 FastAPI HTTP 接口。它不是业务算法的唯一实现位置，而是一个“应用装配 + API 边界层”：在这里创建 `FastAPI` 应用、挂载路由、注册生命周期事件、注入数据库会话和当前用户、把内部异常转换成统一 JSON 响应，并把请求转发给更下层的 `db`、`schemas`、`services`、LangChain/OpenAI 相关服务。

从代码结构看，这个目录的核心职责有三类：第一，`application.py` 和 `lifetime.py` 管理应用启动、CORS、API 文档路径、数据库连接、tokenizer 初始化与关闭释放；第二，`api/*/views.py` 定义 HTTP 端点；第三，`api/agent/*` 负责 AgentGPT 核心交互流程的 API 适配，包括任务启动、分析、执行、创建后续任务、总结、聊天和工具列表。

## 相关目录和文件

`application.py` 是应用工厂，`get_app()` 创建 `FastAPI` 实例，配置 `UJSONResponse`、CORS、`/api/docs`、`/api/openapi.json`，并把 `api_router` 挂到 `/api` 下。

`lifetime.py` 管理启动和关闭事件。启动时通过 `create_engine()` 创建 SQLAlchemy async engine 和 `async_sessionmaker`，存入 `app.state`，并调用 `init_tokenizer(app)`；关闭时释放数据库 engine。

`api/router.py` 是总路由聚合点，挂载 `monitoring`、`agent`、`models`、`auth`、`metadata` 五组 API。`api/dependencies.py` 定义通用依赖，最重要的是 `get_current_user()`，它读取 bearer token，经 `UserCrud.get_user_session()` 校验 session，并返回 `UserBase`。`api/error_handling.py` 与 `api/errors.py` 共同定义平台内可预期错误的响应格式。

`api/agent/views.py` 是 agent API 门面；`api/agent/dependancies.py` 负责请求校验时顺手写入 run/task 记录；`api/agent/agent_service/*` 定义 `AgentService` 协议并选择 `OpenAIAgentService` 或 `MockAgentService`；`api/agent/model_factory.py` 负责构造 LangChain 的 `ChatOpenAI` 或 `AzureChatOpenAI` 包装对象；`api/agent/tools/*` 管理 Search、Image、Code、SID 等工具；`api/memory/*` 定义 agent memory 抽象、空实现和 fallback 包装。

## 核心对象

`FastAPI app` 是该子系统的运行容器，由 `get_app()` 返回。它持有中间件、路由、异常处理器和 `app.state` 中的数据库、tokenizer 等运行期资源。

`api_router` 是所有 API 的汇总入口。最终 HTTP 路径形态大致是 `/api/agent/start`、`/api/models`、`/api/auth/{provider}`、`/api/metadata`、`/api/monitoring/health`。

`get_current_user()` 是认证边界。它依赖 `HTTPBearer()` 和 `UserCrud`，把外部请求中的 token 转换成内部 `UserBase`。agent、models、auth 多个接口都依赖它，因此认证逻辑改动会影响较大。

`AgentService` 是 agent 能力的协议层，定义 `start_goal_agent()`、`analyze_task_agent()`、`execute_task_agent()`、`create_tasks_agent()`、`summarize_task_agent()`、`chat()`。`views.py` 不直接关心 OpenAI 调用细节，而是通过 `get_agent_service()` 注入具体实现。

`ModelSettings`、`AgentRun`、`AgentTaskAnalyze`、`AgentTaskExecute` 等 schema 来自 `reworkd_platform.schemas.agent`，是请求体、运行配置和响应对象的主要数据契约。

`AgentMemory` 是记忆能力抽象，提供 `add_tasks()`、`get_similar_tasks()`、`reset_class()`。`MemoryWithFallback` 说明系统允许主 memory provider 故障时退回备用实现；`NullAgentMemory` 则用于连接不可用时保持流程可运行。

## 运行流程

应用启动时，外部 ASGI 服务器会调用 `get_app()`。该函数先配置日志，再创建 FastAPI 实例，设置 CORS 允许来源来自 `settings.frontend_url` 和 `settings.allowed_origins_regex`，随后注册 startup/shutdown，挂载 `/api` 路由，并注册 `PlatformaticError` 的统一异常处理。

请求进入 `/api/agent/start` 时，FastAPI 先执行 `agent_start_validator()`。该 validator 使用 `AgentCRUD` 创建一次 run，返回带 `run_id` 的 `AgentRun`。随后 `get_agent_service()` 根据 `settings.ff_mock_mode_enabled` 决定使用 mock 还是真实 OpenAI 服务；真实路径会调用 `create_model()`，结合用户、模型设置、是否 streaming、是否强制模型，创建 LangChain chat model。最后 `start_tasks()` 调用 `agent_service.start_goal_agent()` 并返回 `NewTasksResponse`。

后续 `/analyze`、`/execute`、`/create`、`/summarize`、`/chat` 的流程类似：validator 会通过 `AgentCRUD.create_task()` 记录当前 loop step，再由 `AgentService` 完成具体逻辑。其中 `execute`、`summarize`、`chat` 返回 `FastAPIStreamingResponse`，说明调用方需要按流式响应消费模型输出。

非 agent 路由更轻量：`/api/models` 根据 `LLM_MODEL_MAX_TOKENS` 返回模型名和 token 上限；`/api/auth/*` 调用 OAuth installer 完成安装、卸载和 callback；`/api/metadata` 使用 `httpx.AsyncClient` 抓取页面并用 `BeautifulSoup` 提取 title、hostname、favicon；`/api/monitoring/health` 用于健康检查。

## 上下游依赖

上游主要是前端应用和外部 HTTP 客户端。CORS 中的 `settings.frontend_url` 表明它面向一个独立前端，前端通过 bearer token 调用 `/api/*`。

下游依赖包括 `reworkd_platform.db` 中的 CRUD、model、session 设施；`reworkd_platform.schemas` 中的 Pydantic 数据结构；`reworkd_platform.services.tokenizer`；OAuth installer 服务；LangChain 的 `ChatOpenAI`、`AzureChatOpenAI`；OpenAI/Azure OpenAI 兼容接口；可选 Helicone 代理；以及 `httpx`、`BeautifulSoup` 等网页解析依赖。agent 工具层还会连接搜索、图片、代码、SID 等具体工具实现。

根据当前片段推断，`web` 目录本身不直接承担数据库模型定义、OAuth provider 细节、token 计算实现或 OpenAI prompt 全部逻辑；这些能力由相邻的 `db`、`services`、`schemas` 以及 `api/agent/agent_service/open_ai_agent_service.py` 等模块承接。依据是当前目录内大量通过 `Depends()`、schema import、CRUD import 和 service provider 进行跨模块调用。

## 修改时最容易踩的坑

认证依赖是共享入口。修改 `get_current_user()`、`HTTPBearer()` 或 session 校验逻辑时，会影响 agent、models、auth 等多个路由，尤其要确认未破坏 OAuth callback 这类可能不要求当前用户的路径。

`agent/dependancies.py` 的 validator 不只是校验请求，还会写数据库 run/task。不要把它当作纯数据校验函数随意复用，否则可能产生额外任务记录。

流式接口和非流式接口的 service 构造参数不同。`execute`、`summarize`、`chat` 使用 `streaming=True`，并返回 `FastAPIStreamingResponse`；如果更换模型工厂或 agent service，要保留这种响应契约。

`create_model()` 同时处理普通 OpenAI、自定义 API key、Azure OpenAI 和 Helicone。这里的 `openai_api_base`、headers、deployment name、model name 关系比较脆弱，改动时需要分别验证这些模式。

`PlatformaticError` 的 handler 当前固定返回 HTTP 409，但 body 内还有 `code` 字段。若要改变状态码策略，需要同时检查前端是否依赖这个固定行为。

`MemoryWithFallback.__enter__()` 返回的是 primary 或 secondary 的 `__enter__()` 结果，但后续 `__exit__()` 仍先尝试 primary。修改 memory provider 时要注意上下文管理和连接释放一致性。

`metadata` 接口会访问用户传入的 URL。若面向生产环境，需要特别关注超时、重定向、内网地址访问、异常信息和安全策略；当前片段主要处理了请求失败和 HTTP 状态异常。

## 推荐阅读顺序

1. 先读 `platform/reworkd_platform/web/application.py`，理解 FastAPI 应用如何创建、路由挂载在哪里、异常如何统一处理。
2. 再读 `platform/reworkd_platform/web/lifetime.py`，确认数据库连接和 tokenizer 这类运行期资源的生命周期。
3. 阅读 `platform/reworkd_platform/web/api/router.py`，建立 API 分组地图。
4. 阅读 `platform/reworkd_platform/web/api/dependencies.py`、`platform/reworkd_platform/web/api/errors.py`、`platform/reworkd_platform/web/api/error_handling.py`，掌握认证和错误边界。
5. 重点阅读 `platform/reworkd_platform/web/api/agent/views.py` 与 `platform/reworkd_platform/web/api/agent/dependancies.py`，理解 agent 请求如何变成 run/task 记录。
6. 继续看 `platform/reworkd_platform/web/api/agent/agent_service/agent_service.py`、`platform/reworkd_platform/web/api/agent/agent_service/agent_service_provider.py`、`platform/reworkd_platform/web/api/agent/model_factory.py`，把 API 层和模型调用层串起来。
7. 最后按需要补读 `platform/reworkd_platform/web/api/agent/tools/tools.py`、`platform/reworkd_platform/web/api/memory/memory.py`、`platform/reworkd_platform/web/api/auth/views.py`、`platform/reworkd_platform/web/api/metadata.py`，理解工具、记忆、OAuth 和辅助接口。
