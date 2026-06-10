# 文件：platform/reworkd_platform/db/crud/agent.py

## 一句话定位

`platform/reworkd_platform/db/crud/agent.py` 是 Agent 执行链路的数据库 CRUD 封装，负责为当前用户创建一次 `AgentRun`，并为每个 agent 步骤创建 `AgentTask` 记录，同时在写入任务前执行运行存在性、最大循环次数和 summarize 次数限制校验。

## 它暴露/定义了什么

该文件主要定义 `AgentCRUD` 类，继承自 `BaseCrud`。它不是通用的 agent 业务服务，而是偏底层的数据访问对象，围绕 `AsyncSession` 和当前 `UserBase` 工作。

它暴露三个核心方法：

`create_run(goal: str) -> AgentRun`：创建一次 agent run，写入 `user_id` 和 `goal`。

`create_task(run_id: str, type_: Loop_Step) -> AgentTask`：创建一次 agent 步骤任务，写入 `run_id` 和步骤类型，创建前会先调用 `validate_task_count`。

`validate_task_count(run_id: str, type_: str) -> None`：校验 run 是否存在、同类任务数量是否超过 `settings.max_loops`，以及 `summarize` 任务是否重复。

文件还依赖 `MaxLoopsError`、`MultipleSummaryError` 这类面向 API 的异常，所以它虽然在 db/crud 层，但已经承载了一部分接口行为约束。

## 谁调用它

直接调用者在 `platform/reworkd_platform/web/api/agent/dependancies.py`。其中 `agent_crud` 作为 FastAPI 依赖，根据 `get_current_user` 和 `get_db_session` 构造 `AgentCRUD`。

`agent_start_validator` 调用 `crud.create_run(body.goal)`，把新建 run 的 id 放入返回的 `AgentRun` schema。

`agent_analyze_validator`、`agent_execute_validator`、`agent_create_validator`、`agent_summarize_validator`、`agent_chat_validator` 都通过公共函数 `validate` 调用 `crud.create_task(body.run_id, type_)`，为 analyze、execute、create、summarize、chat 等步骤落库。

这些 validator 又被 `platform/reworkd_platform/web/api/agent/views.py` 的 `/start`、`/analyze`、`/execute`、`/create`、`/summarize`、`/chat` 路由作为 `Depends(...)` 使用。因此请求进入 Agent API 时，通常会先经过这里的数据库记录和限制校验，再进入 `AgentService`。

测试覆盖主要在 `platform/reworkd_platform/tests/agent/test_crud.py`，集中验证 `validate_task_count` 的异常分支。

## 它调用谁

数据库模型来自 `platform/reworkd_platform/db/models/agent.py`：`AgentRun` 对应 `agent_run` 表，字段包括 `user_id`、`goal`、`create_date`；`AgentTask` 对应 `agent_task` 表，字段包括 `run_id`、`type_`、`create_date`。

`create_run` 和 `create_task` 调用模型实例的 `.save(self.session)`。根据当前片段推断，`.save` 应该来自项目的 SQLAlchemy 基类 `Base` 或相关 mixin，负责把实例加入 session 并提交/刷新，依据是 `AgentRun`、`AgentTask` 本身没有定义 `save`，但都继承 `reworkd_platform.db.base.Base`。

`validate_task_count` 调用 `AgentRun.get(self.session, run_id)` 判断 run 是否存在；调用 SQLAlchemy 的 `select`、`func.count`、`and_` 查询当前 run 下相同 `type_` 的任务数量；读取 `settings.max_loops` 作为最大循环限制；在异常场景抛出 FastAPI `HTTPException`、`MaxLoopsError` 或 `MultipleSummaryError`。

## 核心流程

启动 agent 时，请求先进入 `/start`，`agent_start_validator` 通过 `AgentCRUD.create_run` 写入一条 `AgentRun`。这条记录表达“某个用户发起了一次以 goal 为目标的 agent 运行”。随后路由把 goal 交给 `AgentService.start_goal_agent` 生成初始任务列表。

后续每一步，如 analyze、execute、create、summarize、chat，请求体都携带 `run_id`。对应 validator 调用 `AgentCRUD.create_task`，先执行 `validate_task_count`。校验通过后，系统写入一条 `AgentTask`，记录该 run 下发生了某种步骤。之后路由才调用 `AgentService` 的具体方法执行 LLM、工具分析、任务生成、总结或聊天逻辑。

因此，这个文件处在“API 请求进入业务服务之前”的计数与审计位置。它不负责调用 OpenAI、不负责组 prompt、不负责执行工具，也不负责返回用户可见的 agent 内容；它负责把 run/task 生命周期写入数据库，并在数据库维度阻止无限循环或重复总结。

## 关键函数的高层作用

`__init__` 保存当前异步数据库 session 和当前用户。`session` 用于所有 SQLAlchemy 操作，`user` 只在创建 run 时使用，用来把 run 归属到发起者。

`create_run` 是 run 生命周期的入口。它只接收 `goal`，从 `self.user.id` 补齐 `user_id`，创建并保存 `AgentRun`。这里没有校验 goal 内容、模型设置或用户额度，这些职责在 schema、依赖层或其他服务中。

`create_task` 是每个 agent 步骤落库的入口。它先调用 `validate_task_count`，然后创建 `AgentTask`。这意味着任何绕过 `create_task` 直接写入 `AgentTask` 的代码都会绕过最大循环和 summarize 限制。

`validate_task_count` 是文件里最重要的保护逻辑。它先确认 `run_id` 对应的 `AgentRun` 存在，不存在时抛 404。然后统计同一个 `run_id` 且同一个 `type_` 的历史任务数量。如果数量达到 `settings.max_loops`，抛出 `MaxLoopsError`，提示停止执行。最后对 `type_ == "summarize"` 做额外限制，已有 summarize 任务过多时抛出 `MultipleSummaryError`。

## 修改风险

这里的最大风险是它影响 Agent API 的全链路前置校验。修改 `create_task` 或 `validate_task_count`，会同时影响 analyze、execute、create、summarize、chat 多个接口，而不仅是单个步骤。

`run_id` 语义需要格外小心。依赖层里 `validate` 会把 `body.run_id` 改成 `(await crud.create_task(...)).id`，也就是新建 `AgentTask` 的 id，而不是原始 run id。根据当前片段推断，这可能是前端/后端协议的一部分，也可能是命名上的历史遗留；修改返回值或字段名容易破坏客户端对 `run_id` 的理解。

`summarize` 限制的边界也值得注意。当前代码在插入前统计已有 summarize 数量，并在 `task_count > 1` 时抛错。这意味着已有 1 条 summarize 时仍可能允许再创建一条；如果真实规则是“只允许一次 summarize”，条件应更接近 `>= 1`。但测试当前只覆盖 `run_count == 2` 抛错，所以直接改动会改变既有测试预期和线上行为。

异常类型属于 API 层语义。`HTTPException`、`MaxLoopsError`、`MultipleSummaryError` 会影响 HTTP 状态码、前端错误处理和日志策略，例如 `MaxLoopsError` 使用 `should_log=False`。更换异常或状态码时，需要同步检查 `platform/reworkd_platform/web/api/errors` 以及前端调用方。

并发情况下也有计数竞态风险。`validate_task_count` 先查数量再插入任务，如果同一个 run 的同类任务被并发创建，两个请求可能同时通过校验再分别写入。若未来要严格保证上限，需要数据库唯一约束、事务隔离或插入时约束配合，而不是只依赖当前应用层查询。
