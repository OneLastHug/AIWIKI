# 子系统：platform/reworkd_platform/db/models

## 解决什么问题

`platform/reworkd_platform/db/models` 是后端数据库 ORM 模型层，负责把业务里的用户、会话、组织、OAuth 授权凭据、Agent 运行记录和任务记录映射为数据库表结构。它不直接处理 HTTP 请求、业务编排或数据库连接生命周期，而是提供 SQLAlchemy 模型对象，供 `db/crud`、API 服务层、认证逻辑和 Agent 执行相关代码读写持久化数据。

这个目录的定位可以理解为“数据库实体定义中心”：每个类描述一张表，字段通过 `mapped_column` 声明，公共字段和基础方法来自 `platform/reworkd_platform/db/base.py` 中的 `Base` 与 `TrackedModel`。模型层本身很薄，重点是统一表名、字段名、主键策略、时间戳字段、软删除语义，以及少量关系映射。

## 相关目录和文件

`platform/reworkd_platform/db/models/agent.py` 定义 Agent 执行相关表，包括 `AgentRun` 和 `AgentTask`。它记录一次 Agent 运行的用户、目标，以及运行过程中产生的任务类型。

`platform/reworkd_platform/db/models/user.py` 定义用户和登录会话模型，包括 `User` 与 `UserSession`。这里的表名和字段名明显兼容外部认证体系的命名风格，例如表名 `"User"`、`"Session"`，字段名 `"sessionToken"`、`"emailVerified"`、`"userId"`、`"createDate"`。

`platform/reworkd_platform/db/models/auth.py` 定义组织、组织成员关系和 OAuth 凭据，包括 `Organization`、`OrganizationUser`、`OauthCredentials`。这些模型使用 `TrackedModel`，具备创建、更新和软删除时间字段。

`platform/reworkd_platform/db/base.py` 是模型层的基础设施，提供统一 `id` 主键、`get`、`get_or_404`、`save`、`delete` 等异步辅助方法，并定义 `TrackedModel` 的审计字段和软删除行为。

`platform/reworkd_platform/db/meta.py` 提供共享的 SQLAlchemy `MetaData`，所有模型通过 `Base.metadata = meta` 纳入同一元数据集合，方便迁移、建表或元数据扫描。

`platform/reworkd_platform/db/dependencies.py` 负责从 Starlette/FastAPI 的 `Request` 中取出 `AsyncSession`，请求结束后提交事务并关闭 session。模型对象通常通过这里提供的 session 完成持久化。

`platform/reworkd_platform/db/crud` 是模型层的主要下游之一。根据目录名和文件名推断，`crud/user.py`、`crud/oauth.py`、`crud/organization.py`、`crud/agent.py` 会围绕这些模型封装查询和写入逻辑。

## 核心对象

`Base` 是所有模型的声明基类。它使用 SQLAlchemy 2.x 风格的 `DeclarativeBase`，默认给每张表注入字符串类型 `id` 主键，值由 `uuid.uuid4()` 生成。它还提供几个轻量方法：`get` 用 `session.get` 按主键查询；`get_or_404` 查询不到时抛出 HTTP 404；`save` 将对象加入 session 并 `flush`；`delete` 默认执行物理删除。

`TrackedModel` 继承 `Base`，用于需要审计字段的业务实体。它提供 `create_date`、`update_date`、`delete_date` 三个字段，并重写 `delete`，将删除动作改为设置 `delete_date` 后保存，因此属于软删除模型。`Organization`、`OrganizationUser`、`OauthCredentials` 都继承它。

`User` 表示系统用户，字段包括 `name`、`email`、`email_verified`、`image`、`create_date`。`email` 有唯一约束，并声明了索引。`User.sessions` 通过 SQLAlchemy `relationship` 关联到 `UserSession`。

`UserSession` 表示用户登录会话，包含唯一的 `session_token`、外键 `user_id` 和过期时间 `expires`。它通过 `ForeignKey("User.id", ondelete="CASCADE")` 指向 `User`，意味着用户删除时会级联处理会话。根据当前片段推断，这部分可能用于兼容前端或 NextAuth 风格的会话表结构，依据是表名和字段名采用 `"Session"`、`"sessionToken"`、`"userId"` 等大小写敏感命名。

`Organization` 表示组织，记录组织名和创建者 `created_by`。`OrganizationUser` 是用户与组织的关联表，包含 `user_id`、`organization_id` 和 `role`，默认角色为 `"member"`。这里没有显式外键关系，根据当前片段推断，组织成员关系可能由 CRUD 或服务层通过字符串 ID 维护。

`OauthCredentials` 存储 OAuth 安装或授权流程中的凭据状态。授权前字段包括 `user_id`、`organization_id`、`provider`、`state`、`redirect_uri`；授权后字段包括 `token_type`、`access_token_enc`、`access_token_expiration`、`refresh_token_enc`、`scope`。字段名中的 `_enc` 表明 token 存储前应经过加密，具体加密逻辑不在模型层。

`AgentRun` 表示一次 Agent 运行，保存 `user_id`、`goal` 和 `create_date`。`AgentTask` 表示运行中的任务记录，保存 `run_id`、`type_` 和 `create_date`。`type_` 映射到数据库列名 `"type"`，这是为了避开 Python 内置名或常见关键语义冲突。

## 运行流程

典型请求进入 Web 层后，通过 `get_db_session` 获取 `AsyncSession`。业务代码或 CRUD 层创建、查询、更新模型对象，例如创建 `User`、写入 `OauthCredentials`、记录 `AgentRun`。模型对象调用 `save(session)` 时会被加入当前事务并执行 `flush`，但提交由 `get_db_session` 在请求结束时统一完成。

查询时，代码可以直接使用 `Model.get(session, id_)` 或 `Model.get_or_404(session, id_)`。后者把“查不到数据”转换成 Web API 语义下的 404 响应，说明模型层虽然主要是 ORM 定义，但已经承担了一点 API 便利逻辑。

删除时要区分继承层级。普通 `Base` 模型的 `delete` 会调用 `session.delete`，偏向物理删除；继承 `TrackedModel` 的模型会设置 `delete_date`，偏向软删除。因此组织、组织成员、OAuth 凭据删除后可能仍保留记录，而用户、会话、Agent 运行和任务是否物理删除取决于它们当前继承的基类。

## 上下游依赖

上游依赖主要是 SQLAlchemy 异步 ORM：`DeclarativeBase`、`Mapped`、`mapped_column`、`relationship`、`ForeignKey`、`Index`、`func.now()` 等。模型还依赖 `platform/reworkd_platform/db/meta.py` 里的共享 `MetaData`，以及 `platform/reworkd_platform/web/api/http_responses` 中的 `not_found` 来实现 `get_or_404`。

下游依赖包括 `platform/reworkd_platform/db/crud` 下的 CRUD 封装、Web API 路由、认证会话逻辑、组织管理逻辑、OAuth 集成逻辑和 Agent 执行记录逻辑。根据当前片段推断，`db/crud/oauth.py` 会操作 `OauthCredentials`，`db/crud/organization.py` 会操作 `Organization` 与 `OrganizationUser`，`db/crud/agent.py` 会操作 `AgentRun` 和 `AgentTask`，依据是文件命名与模型分组高度对应。

数据库连接和事务并不由模型目录创建，而由 `db/dependencies.py` 从应用状态中的 `db_session_factory` 生成。也就是说，模型层依赖调用方传入 session，不负责 session 生命周期。

## 修改时最容易踩的坑

第一，表名和列名大小写不能随意改。`User`、`Session`、`sessionToken`、`emailVerified`、`userId`、`createDate` 这类命名可能与已有数据库、认证库或迁移历史兼容，改成 Python 风格蛇形命名会破坏现有数据访问。

第二，`TrackedModel.delete` 是软删除，`Base.delete` 是物理删除。新增模型时如果选错基类，会改变删除语义。需要保留审计和可恢复记录的业务表应优先考虑 `TrackedModel`。

第三，部分关联只用字符串 ID，没有声明 `ForeignKey`。例如 `AgentTask.run_id`、`OrganizationUser.user_id`、`organization_id`、`OauthCredentials.user_id` 等字段在当前片段里没有数据库外键约束。修改查询或删除逻辑时不能假设数据库会自动级联或保证引用完整性。

第四，`save` 只 `flush` 不 `commit`。调用 `save` 后数据进入当前事务，但最终提交依赖请求生命周期或上层事务管理。测试或脚本中如果绕开 `get_db_session`，需要自己处理提交。

第五，OAuth token 字段名称带有 `enc`，模型层没有强制加密。写入 `access_token_enc`、`refresh_token_enc` 前应确认上游已经完成加密，否则会把敏感 token 明文落库。

第六，`AgentTask.type_` 的 Python 属性名和数据库列名不同。写 ORM 查询时应使用 `type_` 属性；写原生 SQL、迁移或排查数据库时看到的是 `type` 列。

## 推荐阅读顺序

先读 `platform/reworkd_platform/db/base.py`，理解所有模型共享的主键、保存、查询、删除和软删除规则。

再读 `platform/reworkd_platform/db/models/user.py`，因为用户和会话是认证与数据归属的基础，也能看到项目中大小写敏感表名、列名的兼容方式。

然后读 `platform/reworkd_platform/db/models/auth.py`，重点关注组织、多租户归属和 OAuth 凭据字段，这部分解释了用户之外的权限和外部服务授权数据如何落库。

接着读 `platform/reworkd_platform/db/models/agent.py`，了解 Agent 运行记录和任务记录的最小持久化结构。

最后结合 `platform/reworkd_platform/db/dependencies.py` 和 `platform/reworkd_platform/db/crud` 阅读，确认这些模型如何被异步 session 管理、如何被 API 或服务层查询和写入。
