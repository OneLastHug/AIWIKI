# 文件：platform/reworkd_platform/web/api/agent/views.py

## 一句话定位

`platform/reworkd_platform/web/api/agent/views.py` 是 Agent 运行循环的 FastAPI HTTP 入口层，负责把 `/api/agent/*` 请求转换为对 `AgentService` 的调用，并统一返回任务列表、流式响应或工具清单。

## 它暴露/定义了什么

该文件定义了一个 `APIRouter`：`router`，并挂载 7 个接口：`POST /start`、`POST /analyze`、`POST /execute`、`POST /create`、`POST /summarize`、`POST /chat`、`GET /tools`。前 6 个接口对应 Agent 生命周期中的不同步骤，`/tools` 用于返回当前可用的外部工具。

它还定义了两个轻量响应模型：`ToolModel` 和 `ToolsResponse`。业务请求与主要响应模型来自 `reworkd_platform.schemas.agent`，例如 `AgentRun`、`AgentTaskAnalyze`、`AgentTaskExecute`、`AgentTaskCreate`、`AgentSummarize`、`AgentChat`、`NewTasksResponse`。

## 谁调用它

在服务端路由装配链路中，`platform/reworkd_platform/web/api/agent/__init__.py` 导出这里的 `router`；`platform/reworkd_platform/web/api/router.py` 通过 `api_router.include_router(agent.router, prefix="/agent", tags=["agent"])` 挂载；`platform/reworkd_platform/web/application.py` 再以 `prefix="/api"` 挂载总路由。因此最终外部访问路径是 `/api/agent/start` 等。

根据当前片段推断，直接调用者通常是前端页面或 API 客户端，因为这里是 Web API 层，函数本身不被业务模块直接调用，而是由 FastAPI 根据 HTTP 请求、依赖注入和路由匹配触发。

## 它调用谁

每个业务接口都依赖 `platform/reworkd_platform/web/api/agent/dependancies.py` 中的 validator。validator 会读取请求体、获取当前用户和数据库会话，并通过 `AgentCRUD` 创建 run 或 task 记录；其中 `/start` 创建新的 run，其他步骤会为已有 run 创建对应 loop step 的 task 记录，并把生成的数据库 id 写回 `run_id`。

`AgentService` 由 `get_agent_service(...)` 注入。该 provider 会根据配置选择 `MockAgentService` 或 `OpenAIAgentService`，并通过 `create_model` 构造模型实例，同时注入 `TokenService`、当前用户和 `OAuthCrud`。`/tools` 则调用 `get_external_tools()` 和 `get_tool_name()`，过滤 `tool.available()` 后组装返回。

## 核心流程

一次典型 Agent 运行从 `/start` 开始：请求只需要目标 `goal` 和模型设置，validator 先落库创建 run，视图层调用 `agent_service.start_goal_agent(goal)` 生成初始任务，再用 `NewTasksResponse` 返回 `newTasks` 和 `run_id`。

后续循环通常是 `/analyze`、`/execute`、`/create`。`/analyze` 根据目标、当前任务和可用工具名，让服务层判断任务应如何执行；`/execute` 根据分析结果执行任务，并使用 streaming 版本的模型服务返回 `FastAPIStreamingResponse`；`/create` 根据已有任务、上个任务结果、已完成任务列表生成下一批任务。

`/summarize` 和 `/chat` 也是流式接口，并强制使用 `gpt-3.5-turbo-16k`。这说明它们面向长上下文结果聚合或对话，避免普通模型上下文窗口不足。`/tools` 不进入 AgentService，而是直接暴露当前服务端可用工具的展示元数据。

## 关键函数的高层作用

`start_tasks` 是运行入口，负责把用户目标变成初始任务列表；它不关心 LLM 细节，核心委托给 `AgentService.start_goal_agent`。

`analyze_tasks` 是任务决策入口，把 `goal`、`task` 和 `tool_names` 交给 `analyze_task_agent`，返回 `Analysis`，后续 `/execute` 会消费这个分析结构。

`execute_tasks` 是执行入口，也是高风险接口之一，因为它启用了 streaming，并把 `Analysis` 传入 `execute_task_agent`，服务层可能会调用工具、模型或外部 OAuth 能力。

`create_tasks` 是任务规划续写入口，根据历史任务、最后结果和已完成任务生成新任务，用来维持 Agent loop。

`summarize` 和 `chat` 分别处理结果总结与基于结果的对话，二者都返回流式响应，且在 provider 中指定更大的上下文模型。

`get_user_tools` 是工具目录接口，只返回可用工具的名称、描述、颜色占位和图片地址；其中 `color` 目前是 TODO 文本，说明展示层字段尚未真正实现。

## 修改风险

最大风险是依赖注入链路。视图函数里的 `req_body` 和 `agent_service` 使用了同一个 validator，但 `get_agent_service(validator)` 内部也依赖该 validator。FastAPI 会缓存同一请求内的依赖结果；如果改动 validator、依赖参数或缓存行为，可能导致重复创建 run/task 记录，直接污染数据库中的 Agent 执行历史。

第二个风险是 `run_id` 语义不直观。请求中的 `run_id` 在非 `/start` validator 中会被替换为 `crud.create_task(...).id`，也就是说进入视图函数后它更像 task id，而不是原始 run id。修改响应字段或把它继续当 run id 使用，可能造成前后端状态错位。

第三个风险是 streaming 配置。`/execute`、`/summarize`、`/chat` 依赖 `streaming=True` 返回 `FastAPIStreamingResponse`；如果改成普通响应，前端消费方式、超时行为和 token 输出体验都可能变化。

第四个风险是模型选择。`/summarize`、`/chat` 强制 `gpt-3.5-turbo-16k`，会覆盖用户 `model_settings.model`。如果要允许用户自选模型，需要同时考虑 `LLM_MODEL_MAX_TOKENS`、成本、上下文长度和前端预期。

最后，`/tools` 直接暴露所有 `available()` 的工具元数据。新增工具或修改 `available()` 逻辑时，要注意不要把未配置、未授权或仅内部使用的工具展示给用户。
