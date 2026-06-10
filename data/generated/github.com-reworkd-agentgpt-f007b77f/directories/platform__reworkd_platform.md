# 目录：platform/reworkd_platform

## 它负责什么

`platform/reworkd_platform` 是这个仓库中的后端平台服务包，整体形态是一个 Python FastAPI 应用。它负责对外暴露平台 API、组织 Agent 相关接口、加载配置、管理数据库连接、初始化运行期服务，并把 LLM、工具调用、认证、模型信息、健康检查等能力组合成一个后端服务。

从入口链路看，它不是一个零散工具目录，而是可运行的服务模块：`__main__.py` 通过 `uvicorn` 启动 `reworkd_platform.web.application:get_app`；`web/application.py` 构造 FastAPI app；`web/api/router.py` 把各业务路由挂到 `/api` 下；`web/lifetime.py` 注册启动和关闭生命周期，初始化数据库连接与 tokenizer。也就是说，这个目录是平台后端的主体，不只是 Agent 逻辑本身。

它与外部系统的接触面主要集中在配置和服务层：`settings.py` 管理环境变量、数据库、OpenAI/Azure OpenAI、Helicone、Replicate、SerpAPI、Pinecone、Sentry、Kafka、Pusher、SID 等配置；`services` 目录封装安全、SSL、S3、Pinecone、tokenizer、OAuth installer 等支撑能力；`db` 目录负责 SQLAlchemy 模型、CRUD 和依赖注入。

## 直接子目录地图

`db` 是数据库层。它包含 `models`、`crud` 以及数据库连接辅助文件。`db/models` 定义持久化模型，当前可以看到 Agent、auth、user 相关模型；`db/crud` 放通用 CRUD 基类以及 agent、oauth、organization、user 的数据访问逻辑；`db/dependencies.py`、`db/utils.py`、`db/meta.py` 则承担 FastAPI 依赖注入、engine 创建和 SQLAlchemy metadata 管理。

`schemas` 是 API 和内部服务共享的数据结构层，主要基于 Pydantic。`schemas/agent.py` 定义 Agent 请求、模型设置、任务创建/执行/分析/总结/聊天等结构；`schemas/user.py` 定义用户基础结构。接口层大量通过这些 schema 约束请求体和响应。

`services` 是平台支撑服务集合。顶层文件包括 `anthropic.py`、`oauth_installers.py`、`security.py`、`ssl.py`；子目录包括 `aws`、`pinecone`、`tokenizer`。其中 `aws/s3.py` 处理 S3 相关能力，`pinecone` 处理向量库生命周期和访问，`tokenizer` 提供 token 计数服务并在应用启动时初始化。

`web` 是 FastAPI Web 层，也是阅读后端请求流的核心目录。`web/application.py` 创建应用、配置 CORS、注册生命周期和异常处理；`web/lifetime.py` 管理 startup/shutdown；`web/api` 放具体 API 模块。

`tests` 是测试目录，覆盖配置、依赖、schema、安全、S3、OAuth installer、token service、Agent model factory、memory 等场景。它不是运行主链路的一部分，但适合用来确认模块契约和边界行为。

## 关键入口

最外层启动入口是 `platform/reworkd_platform/__main__.py`。它调用 `uvicorn.run`，目标是 `reworkd_platform.web.application:get_app`，并从 `settings` 读取 host、port、worker、reload、log level 等运行参数。理解“服务怎么跑起来”，先看这个文件。

应用构造入口是 `platform/reworkd_platform/web/application.py`。这里创建 `FastAPI` 实例，设置标题、版本、文档路径、默认响应类，注册 CORS，中间接入 `register_startup_event`、`register_shutdown_event`，最后把 `api_router` 挂到 `/api`。同时它注册了 `PlatformaticError` 的异常处理器，是全局 Web 行为的中心。

API 聚合入口是 `platform/reworkd_platform/web/api/router.py`。当前它挂载了 `monitoring`、`agent`、`models`、`auth`、`metadata` 五类路由，路径分别是 `/api/monitoring`、`/api/agent`、`/api/models`、`/api/auth`、`/api/metadata`。虽然 `web/api/memory` 目录存在，但根据当前片段推断，它没有在 `api_router` 中被挂载，因为 `router.py` 未 include `memory.router`。

配置入口是 `platform/reworkd_platform/settings.py`。`Settings` 继承 `BaseSettings`，通过统一前缀读取环境变量，并提供 `db_url`、`pusher_enabled`、`kafka_enabled`、`helicone_enabled`、`sid_enabled` 等派生属性。许多业务行为是由这里的开关决定的，例如 mock mode、最大循环次数、外部 API key、数据库连接和跨域来源。

生命周期入口是 `platform/reworkd_platform/web/lifetime.py`。启动时 `_setup_db` 创建数据库 engine 和 session factory，并挂到 `app.state`；同时调用 `init_tokenizer(app)` 初始化 tokenizer。关闭时释放数据库 engine。这个文件解释了“请求进来前应用准备了什么资源”。

## 主流程位置

Agent 主流程集中在 `platform/reworkd_platform/web/api/agent`。入口路由是 `web/api/agent/views.py`，它定义了 `/start`、`/analyze`、`/execute`、`/create`、`/summarize`、`/chat`、`/tools` 等接口。每个接口先通过 `dependancies.py` 中的 validator 解析和校验请求，再通过 `get_agent_service(...)` 获得 `AgentService` 实例，最后调用对应服务方法。

Agent 服务抽象位于 `web/api/agent/agent_service`。根据当前片段推断，`agent_service.py` 定义统一接口，`open_ai_agent_service.py` 是真实 LLM 驱动实现，`mock_agent_service.py` 是 mock 实现，`agent_service_provider.py` 根据配置和依赖选择具体服务。这个目录是理解“请求如何变成 LLM 调用和流式响应”的关键。

模型选择和 LLM 参数组装位于 `web/api/agent/model_factory.py`，它使用 `schemas.agent.ModelSettings` 和全局 `Settings` 决定使用默认模型、自定义 API key、流式模式或特定模型名。相关测试在 `tests/agent/test_model_factory.py`，适合辅助理解各种配置组合。

工具调用能力在 `web/api/agent/tools`。从文件名可以看出它包含 `search`、`image`、`code`、`reason`、`conclude`、`sidsearch`、`utils`、`tools` 等模块。`views.py` 的 `/tools` 接口会通过 `get_external_tools()` 获取可用工具，并按 `available()` 过滤后返回给前端。根据当前片段推断，具体工具的执行通常返回 `FastAPIStreamingResponse`，因为多个工具文件都围绕流式响应构建。

认证相关流程在 `web/api/auth` 和 `services/oauth_installers.py`。`auth/views.py` 包含 provider 登录、卸载、callback、组织查询、SID 信息等接口；底层会结合 `db/crud/oauth.py` 和配置中的 SID/OAuth 设置工作。

模型列表和元信息接口分别在 `web/api/models`、`web/api/metadata.py`。健康检查和错误测试入口在 `web/api/monitoring/views.py`，其中 `/health` 是常见探活接口。

数据库主流程是：应用启动时 `web/lifetime.py` 创建 engine 和 session factory；请求处理时通过 `db/dependencies.py` 获取 session；业务层或认证层调用 `db/crud/*`；数据结构落到 `db/models/*`。这条线适合用来追踪持久化行为。

## 推荐阅读顺序

1. 先读 `platform/reworkd_platform/__main__.py`，确认服务启动方式和 uvicorn factory 入口。

2. 再读 `platform/reworkd_platform/web/application.py`，理解 FastAPI app 如何构造、CORS 如何设置、路由和异常处理在哪里接入。

3. 接着读 `platform/reworkd_platform/web/api/router.py`，建立 API 分组地图，知道哪些模块是真正对外挂载的。

4. 然后读 `platform/reworkd_platform/web/api/agent/views.py`，因为 Agent 是这个目录最核心的业务面。重点看每个 endpoint 对应哪个 schema、validator 和 service 方法。

5. 继续读 `platform/reworkd_platform/web/api/agent/agent_service`、`web/api/agent/model_factory.py`、`web/api/agent/tools`，把 Agent 请求、模型选择、工具调用、流式响应串起来。

6. 回头读 `platform/reworkd_platform/settings.py` 和 `platform/reworkd_platform/web/lifetime.py`，理解运行环境、数据库、tokenizer、外部服务开关如何影响主流程。

7. 最后读 `platform/reworkd_platform/db`、`platform/reworkd_platform/services`、`platform/reworkd_platform/tests`。这些目录更适合作为“遇到具体问题时查证”的支撑层，不建议一开始逐文件钻。

## 常见误区

不要把 `platform/reworkd_platform` 理解成纯 Agent 算法目录。它首先是一个后端服务包，Agent 只是其中最大的业务模块之一。服务启动、配置、数据库、认证、模型列表、健康检查都在这个目录下。

不要从 `services` 目录开始读主流程。`services` 是支撑能力集合，里面有 S3、Pinecone、tokenizer、安全、OAuth 等横向能力；真正的请求入口在 `web/api`，特别是 `web/api/router.py` 和各模块的 `views.py`。

不要看到 `web/api/memory` 就默认它已经对外开放。根据当前 `web/api/router.py` 片段，实际挂载的路由没有包含 memory，因此它可能是未接入、历史遗留或由其他机制使用的目录。判断 API 是否生效，应优先看 router 聚合文件。

不要忽略 `settings.py`。很多行为不是写死在业务代码里的，而是由环境变量和配置属性控制，例如是否启用 mock、是否启用 Helicone、Kafka、Pusher、SID，以及数据库连接目标。读业务分支前先确认配置开关会更省时间。

不要把 `schemas` 当成简单 DTO 跳过。Agent 的请求字段、默认模型设置、任务结构和响应结构都在这里定义；接口层依赖它做校验，服务层也依赖它做模型选择和参数传递。

不要只看同步返回。Agent 的 `/execute`、`/summarize`、`/chat` 以及多个 tools 都使用 `FastAPIStreamingResponse`，说明主流程中存在流式输出。调试时如果按普通 JSON 响应理解，容易误判响应结构和前端消费方式。
