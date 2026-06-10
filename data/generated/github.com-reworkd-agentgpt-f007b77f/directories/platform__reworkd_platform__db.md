# 子系统：platform/reworkd_platform/db

## 解决什么问题

`platform/reworkd_platform/db` 是后端平台的数据访问层，负责把 FastAPI 请求、认证上下文、Agent 运行状态、组织/OAuth 信息映射到关系型数据库。它不是单纯的模型目录，而是同时承担三类职责：定义 SQLAlchemy ORM 模型、提供请求级 `AsyncSession` 注入、封装面向业务的 CRUD 查询与写入逻辑。

从代码看，该子系统使用 SQLAlchemy async API，数据库连接地址来自 `reworkd_platform.settings.settings.db_url`。运行时由 Web 生命周期代码创建 `AsyncEngine` 和 `async_sessionmaker`，并把 session factory 放到 `app.state.db_session_factory`；API 层通过 `get_db_session` 取得 session，在请求结束后统一 `commit` 和 `close`。

## 相关目录和文件

`platform/reworkd_platform/db/base.py` 定义所有 ORM 模型的共同基类 `Base`，包含字符串 UUID 主键、`get`、`get_or_404`、`save`、`delete` 等通用方法；`TrackedModel` 在此基础上增加 `create_date`、`update_date`、`delete_date`，并把删除行为改成软删除。

`platform/reworkd_platform/db/models` 保存数据库表映射。`agent.py` 定义 `AgentRun` 和 `AgentTask`，记录一次 Agent 目标运行及其循环步骤；`auth.py` 定义 `Organization`、`OrganizationUser`、`OauthCredentials`，承载组织成员和外部 OAuth 安装凭据；`user.py` 定义 `User`、`UserSession`，表名和字段名保持了 NextAuth 风格的 `"User"`、`"Session"`、`sessionToken`、`emailVerified` 等命名。

`platform/reworkd_platform/db/crud` 是业务查询封装层。`agent.py` 提供 Agent run/task 创建和循环次数校验；`oauth.py` 负责 OAuth 安装状态、凭据查询和已安装 provider 汇总；`organization.py` 查询组织及成员列表；`user.py` 根据 session token 找用户会话，并检查用户是否属于某组织；`base.py` 仅保存共享的 `AsyncSession`。

`platform/reworkd_platform/db/dependencies.py` 是 FastAPI 依赖入口；`utils.py` 创建数据库引擎，并提供测试/初始化场景下的建库和删库工具；`meta.py` 暴露共享 `MetaData`；`models/__init__.py` 的 `load_all_models()` 会动态导入模型模块，确保 SQLAlchemy metadata 能收集到所有表。

## 核心对象

`Base` 是本目录的中心抽象。所有表默认继承它，因此都获得统一的 `id` 主键和基础持久化方法。`get_or_404` 直接依赖 Web 层的 `not_found` 响应构造，这说明 DB 层与 API 错误语义存在一定耦合。

`TrackedModel` 适用于需要审计字段和软删除的模型，目前组织、组织用户、OAuth 凭据继承它。与之相比，`AgentRun`、`AgentTask`、`User`、`UserSession` 直接继承 `Base`，删除时会走 SQLAlchemy 的真实删除。

`AgentCRUD` 是 Agent 运行数据的业务门面。`create_run()` 保存用户目标；`create_task()` 先调用 `validate_task_count()` 再插入任务。校验逻辑会检查 run 是否存在，并按 `run_id` 和 `type_` 统计任务数量，超过 `settings.max_loops` 时抛出 `MaxLoopsError`，对 `summarize` 类型还限制重复摘要。

`OAuthCrud` 负责 OAuth 安装生命周期。安装开始时通过 `secrets.token_hex(16)` 生成 `state`，之后可按 `state` 回查安装记录，也可按用户或组织查询已经写入 `access_token_enc` 的有效安装。字段名中的 `_enc` 表明 token 应由上层服务加密后存入。

## 运行流程

一次典型 API 请求进入 FastAPI 后，路由或依赖函数声明 `Depends(get_db_session)`。`get_db_session()` 从 `request.app.state.db_session_factory()` 创建 `AsyncSession`，把它交给 CRUD 对象或业务逻辑。请求处理期间，CRUD 通过 SQLAlchemy `select`、`session.execute()`、模型 `save()` 完成查询和写入；依赖退出时执行 `session.commit()`，最后关闭 session。

应用启动阶段，根据 `web/lifetime.py` 中的引用关系，生命周期代码会调用 `create_engine()` 创建 async engine，并构造 session factory。`load_all_models()` 也在生命周期和测试夹具中被调用，用于导入 `models` 下的模块，使 `meta` 中能包含完整表定义。根据当前片段推断，这个项目没有在 `platform` 下展示 Alembic migration 文件，表结构同步可能依赖外部迁移、已有数据库或测试中的 `metadata.create_all()` 逻辑；依据是仓库片段中只看到模型加载和建删库工具，未看到迁移目录输出。

## 上下游依赖

上游主要是 `reworkd_platform.web`。`web/api/dependencies.py` 依赖 `UserCrud` 从 session token 解析当前用户；`web/api/auth/views.py` 依赖 `OAuthCrud`、`OrganizationCrud` 处理组织和 OAuth API；`web/api/agent/dependancies.py` 依赖 `AgentCRUD` 做 Agent 请求校验；Agent service 和 tools 也会读取 OAuth 安装状态来决定外部工具是否可用。

下游是 SQLAlchemy async、数据库驱动和配置系统。`utils.create_engine()` 根据 `settings.environment` 决定是否配置 SSL；非 development 环境通过 `reworkd_platform.services.ssl.get_ssl_context()` 构造 SSL 参数。模型层依赖 `reworkd_platform.schemas.user.UserBase`、`schemas.agent.Loop_Step` 等 Pydantic schema 来接收当前用户和步骤类型。错误处理依赖 `reworkd_platform.web.api.errors`、`http_responses`，这让 DB/CRUD 层会直接抛出 HTTP 语义异常。

## 修改时最容易踩的坑

第一，`get_db_session()` 在依赖退出时统一 `commit`，所以 CRUD 方法里通常只 `flush` 不 `commit`。如果在 CRUD 内部额外提交，容易破坏请求级事务边界，测试中的回滚策略也可能失效。

第二，`TrackedModel.delete()` 是软删除，但多数查询没有过滤 `delete_date is None`。新增软删除模型或查询时，需要明确是否要排除已删除记录，否则“删除后仍可查到”的行为可能被误认为 bug。

第三，`User`、`UserSession` 使用大写表名和驼峰数据库字段，明显在兼容既有认证表结构。修改这些模型时不能简单按 Python 命名习惯重命名，否则会影响登录会话读取。

第四，`AgentCRUD.validate_task_count()` 的限制与业务循环强相关。`settings.max_loops`、`Loop_Step` 取值、`AgentTask.type_` 字段名三者要保持一致，否则可能出现无法创建任务、重复摘要未被拦截或错误 429 的问题。

第五，OAuth token 字段只保存加密结果，不在此目录处理加解密。写 OAuth 回调逻辑时应在服务层完成加密后再写入 `access_token_enc`、`refresh_token_enc`，不要把明文 token 直接持久化。

## 推荐阅读顺序

先读 `platform/reworkd_platform/db/base.py`，理解模型基类、软删除和 `save()` 的事务风格。然后读 `platform/reworkd_platform/db/models/user.py`、`platform/reworkd_platform/db/models/auth.py`、`platform/reworkd_platform/db/models/agent.py`，建立表结构和业务域的整体印象。

接着读 `platform/reworkd_platform/db/dependencies.py` 和 `platform/reworkd_platform/db/utils.py`，弄清 session 生命周期、engine 创建和环境差异。之后阅读 `platform/reworkd_platform/db/crud/user.py`、`organization.py`、`oauth.py`、`agent.py`，重点看它们如何把模型查询组合成 API 需要的业务对象。最后沿调用方回到 `platform/reworkd_platform/web/api/dependencies.py`、`platform/reworkd_platform/web/api/auth/views.py`、`platform/reworkd_platform/web/api/agent/dependancies.py`，就能理解这个 DB 子系统在请求链路中的位置。
