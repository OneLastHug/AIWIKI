# 文件：platform/reworkd_platform/web/api/agent/agent_service/agent_service_provider.py

## 一句话定位

`agent_service_provider.py` 是 Agent API 层的服务工厂和 FastAPI 依赖注入适配器：它把“请求校验后的 AgentRun / AgentTask* 数据、当前用户、token 服务、OAuth CRUD、模型配置”组装成一个符合 `AgentService` 协议的具体服务实例，供路由直接调用。

## 它暴露/定义了什么

该文件只定义并暴露一个核心函数：`get_agent_service(...)`。

它不是直接返回 `AgentService` 实例，而是返回一个可被 `Depends(...)` 使用的内部函数 `func(...)`。这是典型的 FastAPI 依赖工厂模式：外层 `get_agent_service` 接收每个接口不同的 `validator`、是否 `streaming`、是否强制 `llm_model`；内层 `func` 再通过 FastAPI 自动注入运行时依赖，并最终创建服务对象。

它可能返回两类实现：

- `MockAgentService`：当 `settings.ff_mock_mode_enabled` 打开时使用，避免真实调用模型或外部服务。
- `OpenAIAgentService`：默认真实实现，封装 LangChain / OpenAI 风格模型调用、token 计算、工具执行、总结和聊天逻辑。

返回类型标注为 `Callable[..., AgentService]`，其中 `AgentService` 是 `platform/reworkd_platform/web/api/agent/agent_service/agent_service.py` 中的 `Protocol`，约束了 `start_goal_agent`、`analyze_task_agent`、`execute_task_agent`、`create_tasks_agent`、`summarize_task_agent`、`chat` 等能力。

## 谁调用它

直接调用方是 `platform/reworkd_platform/web/api/agent/views.py` 中的 Agent 路由。每个接口把自己的请求 validator 传给 `get_agent_service`：

- `/start` 使用 `agent_start_validator`
- `/analyze` 使用 `agent_analyze_validator`
- `/execute` 使用 `agent_execute_validator`，并设置 `streaming=True`
- `/create` 使用 `agent_create_validator`
- `/summarize` 使用 `agent_summarize_validator`，设置 `streaming=True`，并强制 `llm_model="gpt-3.5-turbo-16k"`
- `/chat` 使用 `agent_chat_validator`，同样开启 streaming 并强制 16k 模型

这些路由拿到 `agent_service: AgentService` 后，不关心具体实现是 mock 还是真实 OpenAI 服务，只按协议调用对应方法。

## 它调用谁

该文件本身主要调用依赖构造函数和服务构造函数：

- `get_current_user`：从 `platform/reworkd_platform/web/api/dependencies.py` 注入当前用户。
- `get_token_service`：注入 `TokenService`，用于后续模型调用前的 token 预算计算。
- `OAuthCrud.inject`：注入 OAuth 数据访问对象，供工具调用访问用户授权信息。
- `create_model`：来自 `platform/reworkd_platform/web/api/agent/model_factory.py`，根据全局 `settings`、请求里的 `run.model_settings`、当前用户、`streaming` 和 `force_model` 创建具体聊天模型包装对象。
- `MockAgentService`：mock 模式下直接返回。
- `OpenAIAgentService`：真实模式下返回，并传入模型、模型设置、token 服务、用户和 OAuth CRUD。

根据当前片段推断，`callbacks=None` 表示这个 provider 当前没有注入额外 LangChain callback，真实服务内部仍保留 callback 扩展位。

## 核心流程

第一步，路由层通过 `Depends(get_agent_service(...))` 注册依赖。注意外层 `get_agent_service` 在应用装配依赖时执行，生成针对当前接口的 `func`。

第二步，请求进入某个 Agent 接口时，FastAPI 先执行传入的 `validator`。这些 validator 位于 `platform/reworkd_platform/web/api/agent/dependancies.py`，会读取请求体，并通过 `AgentCRUD` 创建 run 或 task 记录，然后返回带 `run_id` / task id 的请求模型。

第三步，FastAPI 执行 provider 内部的 `func`，注入 `run`、`user`、`token_service` 和 `oauth_crud`。

第四步，provider 检查 `settings.ff_mock_mode_enabled`。若开启，短路返回 `MockAgentService`，后续路由调用会得到固定 mock 响应或 mock 流式响应。

第五步，真实模式下调用 `create_model(...)`。这里会把请求中的 `run.model_settings` 与用户、全局配置、streaming 需求、强制模型名合并，形成后续 `OpenAIAgentService` 使用的模型对象。

第六步，构造 `OpenAIAgentService`。路由再调用它的业务方法，例如 `/execute` 会调用 `execute_task_agent`，真实服务内部会根据分析结果选择工具并返回流式响应。

## 关键函数的高层作用

`get_agent_service` 是唯一关键函数。它的高层职责不是执行 Agent 业务，而是统一服务创建策略：同一套路由可以复用它，同时通过参数微调 validator、流式模型、强制模型版本。

`validator` 参数决定请求体如何被解析和持久化。例如 `/start` 会创建 run，其他 loop step 会创建 task。provider 不直接理解这些差异，只要求 validator 最终返回兼容 `AgentRun` 的对象，并从中读取 `model_settings`。

`streaming` 参数传给 `create_model`，影响底层模型是否以流式方式工作。它主要用于 `/execute`、`/summarize`、`/chat` 这类返回 `FastAPIStreamingResponse` 的接口。

`llm_model` 参数用于覆盖请求或默认配置中的模型选择。当前路由中，`summarize` 和 `chat` 强制使用 `"gpt-3.5-turbo-16k"`，推断是为了处理更长上下文。

内部 `func` 是真正的 FastAPI dependency。它把“当前请求上下文”转成“可执行业务的服务对象”，也是 mock 模式和真实模式的切换点。

## 修改风险

最大风险是破坏 FastAPI 依赖注入顺序。`run: AgentRun = Depends(validator)` 不只是校验请求体，还会触发数据库写入 run/task；如果改成普通参数、提前调用或移除，会影响任务记录创建和后续 `run_id` 关联。

第二个风险是模型配置传递。`create_model(settings, run.model_settings, user, streaming=streaming, force_model=llm_model)` 是请求级模型行为的入口。改错 `streaming` 或 `force_model` 会导致流式接口不再流式、长上下文接口模型不匹配，或者用户自定义模型设置失效。

第三个风险是 mock 分支。`settings.ff_mock_mode_enabled` 当前在最早阶段短路，不需要用户 token、OAuth 工具、真实模型能力。如果把 mock 放到 `create_model` 之后，mock 模式也可能触发真实模型配置错误、密钥校验或额外成本。

第四个风险是 `OpenAIAgentService` 构造参数。真实服务的方法依赖 `model`、`settings`、`token_service`、`user`、`oauth_crud`：分析任务需要用户工具和 OAuth，执行任务需要工具授权，总结和聊天需要 token 预算。删除或替换这些依赖会在特定接口才暴露问题，不一定能在 `/start` 这类简单路径发现。

第五个风险是类型表面看起来宽松。`get_agent_service` 的 `validator` 标注返回 `AgentRun`，但实际路由会传入返回 `AgentTaskAnalyze`、`AgentTaskExecute` 等 validator；这些 schema 需要至少具备 `model_settings` 等 provider 使用字段。若后续新增请求类型却缺少相同字段，错误会出现在服务构造阶段，而不是类型检查阶段。

总体上，这个文件适合做“服务选择和依赖装配”的小改动，不适合塞入具体 Agent 业务逻辑。业务行为应优先放在 `open_ai_agent_service.py` 或对应 validator / model factory 中，保持 provider 只负责把请求上下文装配成 `AgentService`。
