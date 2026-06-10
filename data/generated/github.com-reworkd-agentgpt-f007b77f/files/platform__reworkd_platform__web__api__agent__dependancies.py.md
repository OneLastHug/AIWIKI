# 文件：platform/reworkd_platform/web/api/agent/dependancies.py

## 一句话定位

`platform/reworkd_platform/web/api/agent/dependancies.py` 是 Agent API 的 FastAPI 依赖层：它把“读取请求体、取得当前用户和数据库会话、创建 run/task 记录、把校验后的请求对象交给路由和 AgentService”串在一起，属于 Web 入口和数据库记录之间的薄适配层。

## 它暴露/定义了什么

该文件主要定义两类内容。

第一类是依赖工厂 `agent_crud`，它通过 `Depends(get_current_user)` 和 `Depends(get_db_session)` 拿到当前登录用户与异步数据库会话，然后构造 `AgentCRUD(session, user)`。因此路由层不直接关心数据库 session 和用户上下文如何取得。

第二类是请求体 validator，包括 `agent_start_validator`、`agent_analyze_validator`、`agent_execute_validator`、`agent_create_validator`、`agent_summarize_validator`、`agent_chat_validator`。这些函数并不是传统意义上只做字段校验的 validator，而是在 FastAPI 依赖解析阶段产生副作用：创建一条 `AgentRun` 或 `AgentTask` 数据库记录，并把返回的 id 写回请求模型。

文件还定义了通用辅助函数 `validate(body, crud, type_)`，用于把 analyze、execute、create、summarize、chat 这些 loop step 统一映射成 `AgentCRUD.create_task(run_id, type_)` 调用。

## 谁调用它

直接调用者是 `platform/reworkd_platform/web/api/agent/views.py`。其中 `/start` 使用 `agent_start_validator`，`/analyze` 使用 `agent_analyze_validator`，`/execute` 使用 `agent_execute_validator`，`/create` 使用 `agent_create_validator`，`/summarize` 使用 `agent_summarize_validator`，`/chat` 使用 `agent_chat_validator`。

这些 validator 同时也被传给 `platform/reworkd_platform/web/api/agent/agent_service/agent_service_provider.py` 的 `get_agent_service(...)`。`get_agent_service` 内部通过 `run: AgentRun = Depends(validator)` 再次声明对同一个 validator 的依赖，用这个解析后的请求对象创建模型和 `OpenAIAgentService`。根据当前片段推断，FastAPI 的依赖缓存会避免同一个请求内相同 validator 被重复执行；依据是 `views.py` 同时在 `req_body` 和 `agent_service` 两处依赖同一个 callable。

测试侧，`platform/reworkd_platform/tests/test_dependancies.py` 直接调用各个 task validator，断言它们会以正确的 step 字符串调用 `crud.create_task`。

## 它调用谁

`agent_crud` 调用 `reworkd_platform.web.api.dependencies.get_current_user` 获取 `UserBase`，调用 `reworkd_platform.db.dependencies.get_db_session` 获取 `AsyncSession`，再实例化 `reworkd_platform.db.crud.agent.AgentCRUD`。

`agent_start_validator` 调用 `AgentCRUD.create_run(body.goal)`，创建一次 Agent run，并返回 `AgentRun(**body.dict(), run_id=str(id_))`。

其他 validator 通过 `validate` 调用 `AgentCRUD.create_task(body.run_id, type_)`。`AgentCRUD.create_task` 位于 `platform/reworkd_platform/db/crud/agent.py`，内部会先执行 `validate_task_count`，检查 run 是否存在、同类型 task 数量是否超过 `settings.max_loops`，并对 summarize 做额外限制，然后保存 `AgentTask`。

请求与返回模型来自 `platform/reworkd_platform/schemas/agent.py`，包括 `AgentRunCreate`、`AgentRun`、`AgentTaskAnalyze`、`AgentTaskExecute`、`AgentTaskCreate`、`AgentSummarize`、`AgentChat` 和 `Loop_Step`。

## 核心流程

`/start` 的流程是：FastAPI 解析 `AgentRunCreate` 请求体；`agent_crud` 注入当前用户和数据库 session；`agent_start_validator` 用 goal 创建 `AgentRun` 数据库记录；把数据库生成的 run id 填入 schema 的 `run_id`；路由拿到 `AgentRun` 后调用 `AgentService.start_goal_agent` 生成初始任务。

后续 loop step 的流程是：客户端携带已有 `run_id` 和当前步骤需要的字段；对应的 `agent_*_validator` 解析请求体；`validate` 用传入的 `run_id` 创建一条对应类型的 `AgentTask`；`AgentCRUD` 负责校验 run 存在和循环次数；创建成功后，`validate` 把 `body.run_id` 改成新建 task 的 id，然后返回同一个 body 对象；路由继续调用 `AgentService` 的 analyze、execute、create、summarize 或 chat 方法。

这里的一个重要细节是：除 `/start` 外，`run_id` 在 validator 执行后不再是客户端传入的原始 run id，而被替换为 `AgentTask.id`。从命名看这容易误解；根据当前片段推断，它可能被用作前端继续追踪 loop step 的 id，依据是 `validate` 明确把 `create_task(...).id` 写回 `body.run_id`。

## 关键函数的高层作用

`agent_crud` 是数据库访问对象的依赖入口，负责把用户上下文绑定到 `AgentCRUD`。这使得 `create_run` 能记录 `user_id`，也让后续任务创建天然运行在当前用户会话下。

`agent_start_validator` 是 run 生命周期的起点。它接收 `AgentRunCreate`，创建 `AgentRun` 记录，并补齐 API 后续流程需要的 `run_id`。它还在 `Body(example=...)` 中提供 OpenAPI 示例，但业务核心是“先落库，再把 id 合并进请求模型”。

`validate` 是本文件的核心复用逻辑。它把不同 endpoint 的共同动作抽象为“根据 run_id 和 loop step 创建 task，然后用 task id 覆盖 body.run_id”。它不负责字段完整性、模型调用或响应构造，只负责 loop step 的持久化前置动作。

`agent_analyze_validator`、`agent_execute_validator`、`agent_create_validator`、`agent_summarize_validator`、`agent_chat_validator` 是 step-specific 包装器。它们的主要价值是把请求体类型和 `Loop_Step` 字面量绑定起来，例如 execute 绑定 `"execute"`，chat 绑定 `"chat"`。其中 `agent_execute_validator` 额外提供了较完整的请求体示例。

## 修改风险

最大风险是 `run_id` 语义。`validate` 会把请求中的 run id 覆盖为 task id，但字段名仍叫 `run_id`，且 schema 继承自 `AgentRun`。如果下游代码、前端或新接口假设 validator 后的 `run_id` 仍是 run id，就可能出现任务归属错乱、响应 id 不符合预期或后续步骤无法找到 run 的问题。修改这里前需要确认前端协议到底把该字段当 run id 还是 loop/task id 使用。

第二个风险是依赖副作用。FastAPI dependency 通常应该偏向解析和注入，但这里会写数据库。新增路由或调整 `get_agent_service` 依赖时，如果不理解依赖缓存和 callable 复用，可能导致同一请求创建多条 task/run。尤其是把同一个 validator 包装成不同函数对象时，缓存键可能变化。

第三个风险是 step 字符串必须与 `Loop_Step`、数据库 `AgentTask.type_`、`AgentCRUD.validate_task_count` 的限制逻辑保持一致。新增 loop step 时，只改 schema 不够，还要补 validator、路由、服务方法和测试，否则可能出现未记录任务、次数限制失效或类型不被接受。

第四个风险是异常路径来自 `AgentCRUD`。例如 run 不存在会抛 `HTTPException(404)`，超过循环次数会抛 `MaxLoopsError`，多次 summarize 会抛 `MultipleSummaryError`。这些异常不是本文件显式处理的，修改 validator 的调用顺序或绕过 `AgentCRUD.create_task` 会改变 API 的错误语义。

第五个风险是文件名拼写为 `dependancies.py`，不是常见的 `dependencies.py`。仓库中已有多个 import 指向这个拼写，重命名会造成较大影响，除非做全局迁移并覆盖路由、测试和包导入。
