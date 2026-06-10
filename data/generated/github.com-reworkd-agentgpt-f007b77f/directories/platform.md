# 目录：platform

## 它负责什么

`platform` 是这个仓库的 Python 后端服务目录，包名是 `reworkd_platform`。从 `platform/README.md`、`platform/pyproject.toml` 和目录结构看，它是一个基于 FastAPI 的 API 服务，负责承接前端或客户端请求，组织 Agent 相关能力、认证、模型列表、监控、记忆存储、数据库访问和外部服务集成。

这个目录不是前端，也不是 CLI 主体；它更像 AgentGPT/Reworkd 系统中的“平台后端”。它通过 `uvicorn` 启动 FastAPI 应用，依赖 MySQL/SQLAlchemy 做持久化，使用 Pydantic v1 做配置和 schema，集成 OpenAI、LangChain、Anthropic、Pinecone、S3、Stripe、OAuth 等服务能力。根据当前片段推断，Agent 任务分析、模型选择、任务输出解析、记忆读写等主业务逻辑主要落在 `reworkd_platform/web/api/agent` 和 `reworkd_platform/web/api/memory`，数据库模型与 CRUD 则在 `reworkd_platform/db`。

## 直接子目录地图

`platform/reworkd_platform` 是实际 Python 包，里面是后端服务源码。`platform` 根部的 `Dockerfile`、`entrypoint.sh`、`pyproject.toml`、`poetry.lock`、`README.md` 是运行、依赖和开发说明，不承载主要业务逻辑。

`platform/reworkd_platform/db` 负责数据库层。它包含 `models` 和 `crud` 两类核心子目录：`models` 定义 ORM 模型，例如 agent、auth、user；`crud` 封装数据库读写操作，例如 agent、oauth、organization、user。`db/base.py`、`db/meta.py`、`db/dependencies.py`、`db/utils.py` 则承担数据库基础配置、元数据、依赖注入和工具函数角色。

`platform/reworkd_platform/schemas` 是 API 和服务层使用的数据结构定义区，当前能看到 `agent.py`、`user.py`。它通常用于 FastAPI 请求体、响应体、内部 DTO 或校验模型。

`platform/reworkd_platform/services` 放外部服务和跨 API 的基础能力。当前包括 `anthropic.py`、`security.py`、`ssl.py`、`oauth_installers.py`，以及 `aws`、`pinecone`、`tokenizer` 子目录。`aws/s3.py` 对接对象存储；`pinecone` 处理向量数据库生命周期和客户端；`tokenizer` 管理 token 计算服务；`security.py` 处理安全相关能力。

`platform/reworkd_platform/web` 是 Web 服务层。`web/application.py` 配置 FastAPI 应用，`web/lifetime.py` 处理启动和关闭生命周期，`web/api` 是路由和接口实现区。

`platform/reworkd_platform/tests` 是后端测试目录。它覆盖 agent、memory、依赖、schema、security、S3、tokenizer、OAuth installer、settings 等模块，适合作为理解行为边界的辅助材料。

## 关键入口

服务启动入口是 `platform/reworkd_platform/__main__.py`。`platform/README.md` 明确说明可以通过 `poetry run python -m reworkd_platform` 启动服务，因此 Python 模块入口会落到 `__main__.py`。根据 FastAPI 模板惯例和 README 描述，它会启动 `uvicorn`，并加载 Web 应用。

应用构造入口是 `platform/reworkd_platform/web/application.py`。这个文件通常负责创建 `FastAPI` 实例、挂载路由、配置中间件、错误处理、文档地址和生命周期逻辑。

API 总路由入口是 `platform/reworkd_platform/web/api/router.py`。它是各业务 API 的汇聚点，负责把 `agent`、`auth`、`models`、`monitoring` 等子路由注册到主应用。根据当前片段推断，具体业务路由再分散到各子目录的 `views.py` 中。

配置入口是 `platform/reworkd_platform/settings.py`。README 说明环境变量统一使用 `REWORKD_PLATFORM_` 前缀，例如 `REWORKD_PLATFORM_PORT`、`REWORKD_PLATFORM_RELOAD`、`REWORKD_PLATFORM_ENVIRONMENT`。因此启动参数、数据库连接、外部服务密钥、运行模式等大概率都从这里读取。

容器入口是 `platform/Dockerfile` 和 `platform/entrypoint.sh`。本地开发主要看 Poetry，部署或容器运行时再看这两个文件。

## 主流程位置

后端启动主流程大致是：`python -m reworkd_platform` 进入 `reworkd_platform/__main__.py`，读取 `settings.py` 中的配置，启动 `uvicorn`，加载 `web/application.py` 创建的 FastAPI 应用，再由 `web/api/router.py` 挂载各 API 模块。应用启动和关闭时的资源初始化、清理动作根据当前片段推断位于 `web/lifetime.py`，并可能联动 `services/pinecone/lifetime.py`、`services/tokenizer/lifetime.py` 这类服务生命周期文件。

Agent 请求的主流程位置集中在 `web/api/agent`。其中 `views.py` 是接口层入口；`dependancies.py` 提供 FastAPI 依赖；`helpers.py` 放辅助逻辑；`model_factory.py` 负责模型实例或模型配置选择；`analysis.py` 承担任务分析；`prompts.py` 管理提示词；`task_output_parser.py` 解析 Agent 任务输出；`stream_mock.py` 可能用于流式响应的模拟或测试场景。根据测试文件 `tests/agent/test_analysis.py`、`test_model_factory.py`、`test_task_output_parser.py`、`test_tools.py` 判断，这里是业务复杂度最高的区域。

记忆能力主流程在 `web/api/memory`。`memory.py` 应该定义抽象或主要实现，`memory_with_fallback.py` 表示带降级策略的记忆实现，`null.py` 表示空实现或禁用实现。它与 `services/pinecone` 的关系值得重点关注，因为 Pinecone 依赖通常用于向量记忆检索。

数据库主流程在 `db/models` 和 `db/crud`。API 层不应直接拼 SQL，而是通过 `db/crud/*.py` 访问模型。`schemas` 则在 API 边界和业务对象之间提供结构化校验。

认证相关主流程分布在 `web/api/auth/views.py`、`db/models/auth.py`、`db/crud/oauth.py`、`services/oauth_installers.py`、`services/security.py`。用户和组织数据则继续关联 `db/models/user.py`、`db/crud/user.py`、`db/crud/organization.py`。

## 推荐阅读顺序

第一步读 `platform/README.md` 和 `platform/pyproject.toml`，先确认这是 FastAPI + Poetry 项目，掌握启动方式、依赖组成和测试方式。

第二步读 `reworkd_platform/__main__.py`、`reworkd_platform/settings.py`、`reworkd_platform/web/application.py`、`reworkd_platform/web/lifetime.py`、`reworkd_platform/web/api/router.py`，建立“服务如何启动、配置如何进入、路由如何挂载”的主干地图。

第三步读 `reworkd_platform/web/api/agent/views.py`，再顺着它进入 `analysis.py`、`model_factory.py`、`prompts.py`、`task_output_parser.py`、`helpers.py`。这是理解 Agent 后端行为的核心路径。

第四步读 `reworkd_platform/web/api/memory` 和 `reworkd_platform/services/pinecone`，理解记忆、向量检索和降级策略如何组织。

第五步读 `reworkd_platform/db/models`、`reworkd_platform/db/crud`、`reworkd_platform/schemas`，把 API 入参、响应、数据库模型和持久化操作对应起来。

第六步看 `reworkd_platform/tests` 中与当前主题对应的测试。比如改 Agent 行为时优先看 `tests/agent`，改记忆时看 `tests/memory`，改鉴权和外部服务时看 `test_security.py`、`test_oauth_installers.py`、`test_s3.py`。

## 常见误区

不要把 `platform` 理解成整个产品的全部后端边界。仓库根部还存在 `next`、`cli`、`db`、`docs` 等目录，`platform` 只是 Python FastAPI 服务这一块；前端页面和 Next.js API 不在这里。

不要只看 `web/api/*/views.py` 就认为业务都在路由层。这个项目把不少业务拆到了 `services`、`db/crud`、`schemas` 以及 `web/api/agent` 的辅助模块中，尤其 Agent 流程需要沿着 `views.py` 往 `analysis.py`、`model_factory.py`、`task_output_parser.py` 继续追。

不要忽略 `settings.py`。README 明确说明配置来自 `REWORKD_PLATFORM_` 前缀环境变量，很多行为差异可能不是代码分支造成，而是环境变量、外部服务密钥或运行模式造成。

不要把 `services` 都当成独立微服务。这里的 `services` 更像后端内部的集成层或基础能力层，例如 S3、Pinecone、tokenizer、安全、SSL、OAuth installer，并不是单独部署的服务目录。

不要逐个叶子文件平均阅读。`platform` 的主线是启动入口、应用构造、路由聚合、业务 API、服务集成、数据库访问。overview 阶段先把这些路径角色串起来，比逐文件解释更有效。
