# 子系统：platform/reworkd_platform/db/crud

## 解决什么问题

`platform/reworkd_platform/db/crud` 是后端数据库访问层的一组轻量封装，负责把 API 层、服务层对数据库的读写请求收敛到少数 CRUD 对象中。它不是通用 ORM 仓库层，也没有复杂的领域服务编排；它更像 FastAPI 依赖注入体系下的“数据库操作门面”。

这个目录主要解决三类问题：第一，统一持有 `AsyncSession`，让上层不直接拼接所有 SQLAlchemy 查询；第二，给 agent run/task、OAuth installation、organization、user session 等核心业务对象提供可复用查询；第三，在写入前放置少量业务约束，例如 agent task 数量上限、summary task 重复限制、OAuth token 必须已安装后才返回等。

需要注意，事务提交不在这些 CRUD 方法中显式完成。模型实例通常通过 `Base.save(session)` 执行 `session.add()` 和 `flush()`，而请求结束时由 `platform/reworkd_platform/db/dependencies.py` 中的 `get_db_session()` 统一 `commit()`。因此该目录的职责边界是“构造查询、执行读写、触发 flush、抛出业务异常”，不是完整事务管理器。

## 相关目录和文件

`platform/reworkd_platform/db/crud/base.py` 定义 `BaseCrud`，只保存 `AsyncSession`，是所有 CRUD 类的共同父类。

`platform/reworkd_platform/db/crud/agent.py` 定义 `AgentCRUD`，围绕 `AgentRun`、`AgentTask` 创建 agent 运行记录和步骤任务，并校验 loop 次数。

`platform/reworkd_platform/db/crud/oauth.py` 定义 `OAuthCrud`，处理 `OauthCredentials` 的创建、按 `state`、`user_id`、`organization_id` 查询，以及按组织汇总已安装 provider。

`platform/reworkd_platform/db/crud/organization.py` 定义 `OrganizationCrud`，处理 organization 创建和按名称查询当前用户可见的组织及成员列表，同时定义响应用的 `OrgUser`、`OrganizationUsers`。

`platform/reworkd_platform/db/crud/user.py` 定义 `UserCrud`，用于从 session token 读取 `UserSession` 和查询用户在组织中的关系。

相邻依赖中，`platform/reworkd_platform/db/models/agent.py`、`platform/reworkd_platform/db/models/auth.py`、`platform/reworkd_platform/db/models/user.py` 定义数据库模型；`platform/reworkd_platform/db/base.py` 定义 `Base.save()`、`Base.get()`、`TrackedModel`；`platform/reworkd_platform/web/api/dependencies.py`、`platform/reworkd_platform/web/api/agent/dependancies.py`、`platform/reworkd_platform/web/api/auth/views.py` 是主要调用入口。

## 核心对象

`BaseCrud` 是最小基类，仅保存 `self.session`。这说明本目录没有统一的泛型 CRUD 模板，也没有内置分页、软删除过滤、权限过滤等通用机制；每个子类都按业务场景写查询。

`AgentCRUD` 需要 `AsyncSession` 和 `UserBase`。`create_run(goal)` 创建 `AgentRun`，写入当前用户 id 和目标；`create_task(run_id, type_)` 先调用 `validate_task_count()`，再创建 `AgentTask`。`validate_task_count()` 会先确认 run 存在，然后统计同一 `run_id`、同一 `type_` 的 task 数量，并根据 `settings.max_loops` 抛出 `MaxLoopsError`，对 `summarize` 类型还会抛出 `MultipleSummaryError`。

`OAuthCrud` 只依赖 session，并提供 `inject()` 类方法接入 FastAPI `Depends(get_db_session)`。`create_installation()` 会生成随机 `state`，保存 provider、user、organization 和 redirect_uri。查询方法普遍只返回 `access_token_enc is not None` 的记录，表示“已完成安装”的 OAuth 凭据，而不是任意创建中的安装流程。

`OrganizationCrud` 同时依赖 session 和当前用户。`get_by_name()` 使用 `Organization`、`OrganizationUser`、`User` 联表，并通过一个 `owner` alias 确保当前用户属于该组织。根据当前片段推断，这里的 `owner` 命名更像“访问者成员关系”，并未校验角色必须为 owner，依据是 join 条件只判断 `OrganizationUser.user_id == self.user.id`，没有过滤 `role`。

`UserCrud` 是认证路径的基础。`get_user_session()` 根据 bearer token 查询 `UserSession`，并通过 `selectinload(UserSession.user)` 预加载用户；`get_user_organization()` 查询用户与组织的关联，但源码注释提示当前只返回第一个匹配组织关系。

## 运行流程

典型请求进入 FastAPI route 后，先通过依赖函数创建 CRUD 实例。数据库 session 来自 `get_db_session()`，该依赖从 `request.app.state.db_session_factory()` 创建 `AsyncSession`，yield 给业务代码，请求结束后执行 `commit()` 并关闭 session。

agent 流程中，`platform/reworkd_platform/web/api/agent/dependancies.py` 的 `agent_crud()` 注入当前用户和 session，构造 `AgentCRUD`。开始 agent 时，`agent_start_validator()` 调用 `create_run()` 生成 run id；后续 analyze、execute、create、summarize、chat 等步骤通过统一的 `validate()` 调用 `create_task()`，把原请求体里的 `run_id` 替换成新建 task id。这里的命名容易误读：传入的 `body.run_id` 是原 run id，返回后被改写为 task id。

认证流程中，`get_current_user()` 从 bearer token 读取 `UserSession`，若无记录或过期则抛出 forbidden，然后组装 `UserBase`。组织接口再通过 `OrganizationCrud.inject()` 拿到当前用户，查询其可见组织。

OAuth 流程中，安装入口通过 `installer_factory()` 注入 `OAuthCrud` 并创建具体 installer。安装时先查已完成安装；没有则 `create_installation()` 生成 state。回调时按 state 找回凭据，服务层写入加密后的 access token、refresh token，再调用 `creds.save(self.crud.session)` flush。卸载时服务层直接使用 `self.crud.session.delete(creds)` 删除记录。

## 上下游依赖

上游主要是 Web API 和服务层：`platform/reworkd_platform/web/api/auth/views.py` 调用 organization 和 OAuth CRUD；`platform/reworkd_platform/web/api/dependencies.py` 调用 `UserCrud` 做当前用户认证；`platform/reworkd_platform/web/api/agent/dependancies.py` 调用 `AgentCRUD` 做 agent run/task 记录；`platform/reworkd_platform/services/oauth_installers.py` 调用 `OAuthCrud` 完成第三方 OAuth 安装流程；agent tools 中也会读取 OAuth 凭据。

下游主要是 SQLAlchemy async session、数据库模型和 schema。模型来自 `platform/reworkd_platform/db/models/*`，其中 `AgentRun`、`AgentTask`、`Organization`、`OrganizationUser`、`OauthCredentials`、`UserSession`、`User` 是直接操作对象。schema 主要是 `UserBase` 和 agent 的 `Loop_Step`。错误类型来自 `platform/reworkd_platform/web/api/errors.py` 和 `platform/reworkd_platform/web/api/http_responses.py`。

配置依赖包括 `settings.max_loops`，影响 agent task 限流；OAuth installer 还依赖 settings 中的第三方 client 配置，但具体 HTTP 调用不在 CRUD 目录内。

## 修改时最容易踩的坑

第一，别在 CRUD 方法里随意 `commit()`。当前事务模型依赖 `get_db_session()` 在请求结束统一提交，模型的 `save()` 只 `flush()`。如果局部 commit，可能破坏同一请求内后续失败时的事务一致性。

第二，`OAuthCrud.get_installation_by_user_id()` 只返回 `access_token_enc` 非空的记录。安装刚创建但未 callback 的记录不会被这个方法返回。如果想处理“安装中”的状态，需要新增语义明确的方法，而不是直接改掉现有过滤条件，否则会影响 `sid/info`、installer install/uninstall 等路径。

第三，`AgentCRUD.create_task()` 会把业务校验和写入绑定在一起。新增 task 类型时要检查 `validate_task_count()` 的统计维度是否符合预期，尤其是 `summarize` 的特殊限制和 `settings.max_loops` 的全局影响。

第四，`OrganizationCrud.get_by_name()` 的权限判断只是“当前用户在该组织中”。如果要区分 owner/admin/member，不能只依赖现有 `owner` alias 名称，需要显式检查 `OrganizationUser.role`。

第五，`UserCrud.get_user_session()` 使用 `scalar_one()`，无记录会抛 `NoResultFound`，这是上层 `get_current_user()` 当前依赖的控制流。改成 `scalar_one_or_none()` 后必须同步修改上层异常处理。

## 推荐阅读顺序

1. 先读 `platform/reworkd_platform/db/base.py`，理解 `Base.save()`、`Base.get()`、`TrackedModel.delete()` 和 id 生成方式。
2. 再读 `platform/reworkd_platform/db/dependencies.py`，确认 session 生命周期、commit 和 close 发生在哪里。
3. 接着读 `platform/reworkd_platform/db/models/agent.py`、`platform/reworkd_platform/db/models/auth.py`、`platform/reworkd_platform/db/models/user.py`，掌握 CRUD 操作的表结构。
4. 然后读 `platform/reworkd_platform/db/crud/base.py`、`agent.py`、`oauth.py`、`organization.py`、`user.py`，重点看每个方法的查询条件和异常语义。
5. 最后读调用点：`platform/reworkd_platform/web/api/dependencies.py`、`platform/reworkd_platform/web/api/agent/dependancies.py`、`platform/reworkd_platform/web/api/auth/views.py`、`platform/reworkd_platform/services/oauth_installers.py`，把 CRUD 方法放回请求流程中理解。
