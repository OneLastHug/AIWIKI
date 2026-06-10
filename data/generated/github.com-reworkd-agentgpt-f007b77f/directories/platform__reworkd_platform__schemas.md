# 子系统：platform/reworkd_platform/schemas

## 解决什么问题

`platform/reworkd_platform/schemas` 是平台后端的“数据契约层”，集中定义 API 请求体、响应体、用户上下文和模型配置等 Pydantic schema。它的作用不是执行业务，而是把 `web/api`、`db/crud`、`services` 之间共享的数据形状固定下来，避免同一类对象在各层里各写一套字段、校验和默认值。

从当前代码看，这个目录主要服务两类场景：一类是 agent 工作流的请求参数和运行状态，例如 `AgentRun`、`AgentTaskAnalyze`、`AgentSummarize`；另一类是认证后用户信息的轻量封装，例如 `UserBase`。这也是为什么很多业务代码都直接依赖这里，而不是直接依赖数据库模型。根据当前片段推断，它是整个平台后端的稳定输入边界之一。

## 相关目录和文件

核心文件只有两个：`platform/reworkd_platform/schemas/agent.py` 和 `platform/reworkd_platform/schemas/user.py`，再加上入口式重导出 `platform/reworkd_platform/schemas/__init__.py`。其中 `__init__.py` 把 `ModelSettings` 和 `UserBase` 直接暴露给上层，方便 `from reworkd_platform.schemas import ...` 这种写法。

和它最紧密的邻近目录是 `platform/reworkd_platform/web/api/agent`、`platform/reworkd_platform/web/api/auth`、`platform/reworkd_platform/db/crud`、`platform/reworkd_platform/services/tokenizer`。这些地方都把 `schemas` 当成公共语言使用，而不是临时 DTO。

## 核心对象

`agent.py` 里最关键的是 `ModelSettings`。它定义了模型选择、`custom_api_key`、`temperature`、`max_tokens`、`language`，并通过校验器限制 `max_tokens` 不超过 `LLM_MODEL_MAX_TOKENS`。与之配套的 `LLM_Model`、`Loop_Step` 是两组 `Literal` 常量，前者约束模型名，后者约束 agent 生命周期阶段。

围绕它还定义了 `AgentRunCreate`、`AgentRun`、`AgentTaskAnalyze`、`AgentTaskExecute`、`AgentTaskCreate`、`AgentSummarize`、`AgentChat` 等结构，分别对应不同 API 阶段需要的字段组合。`NewTasksResponse` 和 `RunCount` 则属于返回对象。

`user.py` 里最核心的是 `UserBase` 和 `OrganizationRole`。`UserBase` 保存当前会话用户的基础身份信息，并提供 `organization_id` 属性，供权限判断、组织隔离和外部服务调用使用。

## 运行流程

典型流程是：`web/api/agent/dependancies.py` 先用 FastAPI `Body` 把 JSON 解析成 `AgentRunCreate`、`AgentTaskAnalyze` 等 schema，再通过 `AgentCRUD` 创建数据库里的 `AgentRun` 或 `AgentTask`，最后把数据库生成的 `id` 回填到 schema 的 `run_id` 中。随后 `web/api/agent/views.py` 接收这些已验证对象，交给 `AgentService` 执行分析、创建任务、总结或聊天。

`get_current_user` 会从 session token 解析出 `UserBase`，之后这个对象会一路传给 `AgentCRUD`、模型工厂、工具选择器、OAuth 安装器等模块。`web/api/agent/model_factory.py` 和 `services/tokenizer/token_service.py` 也依赖 `ModelSettings`、`LLM_Model` 来选择具体模型、计算 token 空间并限制输出长度。

## 上下游依赖

上游主要是 HTTP 请求、认证会话和数据库记录。下游主要是 FastAPI 路由、CRUD 层、LLM 构造器和 token 计算逻辑。`schemas` 自身依赖的外部概念很少，主要是 `pydantic`、`typing.Literal`、`datetime`，以及 `reworkd_platform.web.api.agent.analysis.Analysis` 这类邻近业务类型。

反过来，`platform/reworkd_platform/web/api/agent/views.py`、`platform/reworkd_platform/web/api/auth/views.py`、`platform/reworkd_platform/db/crud/agent.py`、`platform/reworkd_platform/services/oauth_installers.py`、`platform/reworkd_platform/services/tokenizer/token_service.py` 都把这里当成公共依赖。根据当前片段推断，它是“请求校验 -> 业务处理 -> 数据持久化”链路中的统一输入层。

## 修改时最容易踩的坑

第一，`AgentRunCreate`、`ModelSettings` 这类 schema 被多个模块共享，改字段名或默认值会同时影响 API、测试和模型工厂。第二，`ModelSettings.max_tokens` 有上限校验，新增模型时必须同步更新 `LLM_MODEL_MAX_TOKENS`，否则测试和运行时都会失败。第三，`Literal` 限定很硬，`Loop_Step` 或 `LLM_Model` 多加、少加一个值，都会立刻影响依赖它的 CRUD、token 服务和路由验证。第四，`Field(default=[])` 这类可变默认值在 Pydantic 场景里要非常谨慎，虽然当前代码这样写能工作，但改动时要注意是否会引入共享状态问题。

## 推荐阅读顺序

先看 `platform/reworkd_platform/schemas/agent.py`，理解 agent 工作流的所有数据形状；再看 `platform/reworkd_platform/schemas/user.py`，理解用户上下文如何在系统里流动；然后看 `platform/reworkd_platform/web/api/agent/dependancies.py` 和 `platform/reworkd_platform/web/api/agent/views.py`，把 schema 和路由串起来；最后看 `platform/reworkd_platform/db/crud/agent.py`、`platform/reworkd_platform/web/api/agent/model_factory.py`、`platform/reworkd_platform/services/tokenizer/token_service.py`，确认这些 schema 如何进入持久化、模型选择和 token 预算控制。
