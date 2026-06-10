# 文件：platform/reworkd_platform/web/api/agent/model_factory.py

## 一句话定位

`model_factory.py` 是 Agent 后端的 LLM 实例创建入口：它把全局 `Settings`、请求级 `ModelSettings`、当前 `UserBase` 组合成可被 LangChain 调用的 `ChatOpenAI` 或 `AzureChatOpenAI` 包装对象，并统一处理 OpenAI、Azure OpenAI、Helicone、用户自定义 API Key、流式输出等差异。

## 它暴露/定义了什么

该文件主要定义三类内容。

第一类是模型包装类：`WrappedChatOpenAI` 继承 `langchain.chat_models.ChatOpenAI`，补充了 `client`、`max_tokens`、`model_name` 字段声明；`WrappedAzureChatOpenAI` 同时继承 `AzureChatOpenAI` 和 `WrappedChatOpenAI`，补充 Azure 所需的 `openai_api_base`、`openai_api_version`、`deployment_name`。这些包装类的目的不是重写推理逻辑，而是让项目内类型检查、token 计算和运行时字段访问更稳定。

第二类是类型别名：`WrappedChat = Union[WrappedAzureChatOpenAI, WrappedChatOpenAI]`，表达工厂函数可能返回普通 OpenAI 或 Azure OpenAI 实例。

第三类是两个函数：`create_model(...)` 是主入口；`get_base_and_headers(...)` 是辅助函数，用于决定请求 base、Helicone headers 以及是否启用 Helicone。

## 谁调用它

直接调用 `create_model` 的核心位置是 `platform/reworkd_platform/web/api/agent/agent_service/agent_service_provider.py`。`get_agent_service(...)` 是 FastAPI 依赖工厂：它从请求 validator 得到 `AgentRun`，从依赖注入得到当前用户、token service、OAuth CRUD；如果未启用 mock 模式，就调用 `create_model(...)` 创建模型，再注入到 `OpenAIAgentService`。

`WrappedChatOpenAI` 还被 `platform/reworkd_platform/web/api/agent/agent_service/open_ai_agent_service.py` 用作构造函数参数类型，被 `platform/reworkd_platform/services/tokenizer/token_service.py` 用作 `calculate_max_tokens` 的参数类型。测试覆盖集中在 `platform/reworkd_platform/tests/agent/test_model_factory.py`，验证 Helicone、Azure、streaming、自定义模型设置等分支。

## 它调用谁

该文件直接依赖 LangChain 的 `ChatOpenAI`、`AzureChatOpenAI`，用它们作为真正的 LLM 客户端实现。它读取 `reworkd_platform.schemas.agent` 中的 `LLM_Model`、`ModelSettings`，读取 `reworkd_platform.schemas.user.UserBase` 中的 `id`、`email`，读取 `reworkd_platform.settings.Settings` 中的 OpenAI、Azure、Helicone 配置。

运行时真正被调用的是返回对象的 LangChain 方法，例如后续 `OpenAIAgentService` 会调用 `self.model.apredict_messages(...)`、把模型传给 `LLMChain`，或者交给工具执行与总结逻辑。也就是说，本文件只负责“建模配置”，不负责 prompt、agent 循环或结果解析。

## 核心流程

`create_model(...)` 首先判断是否使用 Azure：条件是请求没有 `custom_api_key`，且 `settings.openai_api_base` 中包含 `azure`。这是一种基于配置字符串的环境判断。

然后它确定实际模型名：如果传入 `force_model`，优先使用它；否则使用 `model_settings.model`。`force_model` 来自 `get_agent_service(..., llm_model=...)`，用于某些路由或步骤强制覆盖请求里的模型选择。

接着调用 `get_base_and_headers(...)`，得到三项结果：实际 API base、额外 headers、是否使用 Helicone。随后组装通用 `kwargs`：包含 `openai_api_base`、API key、`temperature`、`model`、`max_tokens`、`streaming`、`max_retries=5`，以及 `model_kwargs`。其中 `model_kwargs` 放入 `user.email` 和 headers，意图是把用户标识和 Helicone 追踪信息透传给下游。

如果判定为 Azure，则把目标类切换为 `WrappedAzureChatOpenAI`，将模型名中的点号去掉作为 `deployment_name`，例如测试中 `gpt-3.5-turbo` 会变成 `gpt-35-turbo`；同时加入 `openai_api_version`、`openai_api_type="azure"`，并对 base 做 `rstrip("v1")` 处理。若 Azure 同时走 Helicone，则 `kwargs["model"]` 会被替换为 deployment name，以匹配代理层或 Azure 部署名的要求。

最后执行 `return model(**kwargs)`，返回 LangChain chat model 实例。

## 关键函数的高层作用

`create_model` 是本文件的关键函数。它承担“把业务请求转换为 LLM 客户端配置”的职责，屏蔽普通 OpenAI、Azure OpenAI、Helicone 代理、自定义 API Key、streaming 开关之间的组合差异。调用方只需要拿到一个 `WrappedChat`，后续按 LangChain 模型使用即可。

`get_base_and_headers` 是网络路由和观测配置的决策点。它的规则是：只有当全局 Helicone 启用且请求没有自定义 API Key 时，才使用 Helicone base 和 Helicone headers；如果用户提供了 `custom_api_key`，则禁用 Helicone，并使用官方 OpenAI base；否则使用全局 `settings.openai_api_base`。headers 中包含 Helicone 鉴权、缓存开关、用户 ID、原始 OpenAI base。根据当前片段推断，这样做是为了避免把用户自带 API Key 发送到平台级 Helicone 代理，同时仍让平台自有 key 的请求可被观测和缓存；依据是测试明确覆盖了 “Helicone enabled with custom api key” 时 headers 为 `None`、`use_helicone` 为 `False`。

`WrappedChatOpenAI` 和 `WrappedAzureChatOpenAI` 是类型与字段适配层。它们的高层作用是让项目内代码可以稳定访问 `max_tokens`、`model_name` 等字段，尤其是 `TokenService.calculate_max_tokens(...)` 会直接读取并修改这些字段。

## 修改风险

第一，Azure 判断依赖 `"azure" in settings.openai_api_base`，这是脆弱约定。修改 `openai_api_base` 格式、引入新的代理域名或私有网关时，可能误判是否走 Azure。若要增强，应考虑显式配置开关，但这会影响现有部署方式。

第二，`deployment_name = llm_model.replace(".", "")` 假设 Azure 部署名与模型名只有点号差异。测试验证了该假设，但真实 Azure 部署名常由用户自定义；仓库中 `Settings` 还存在 `azure_openai_deployment_name` 字段，不过当前工厂没有使用。修改这里会影响所有 Azure 调用。

第三，Helicone 与自定义 API Key 的组合是安全敏感逻辑。当前规则避免用户自定义 key 经过平台 Helicone；如果改动 `get_base_and_headers`，需要重新确认密钥归属、日志记录、代理 headers 和缓存行为，避免泄露用户凭据或破坏可观测性。

第四，`model_kwargs` 中传入 `user.email`。`UserBase.email` 是可选字段，部分测试只提供 `id`。如果 LangChain 或下游 API 对 `user` 字段要求更严格，可能产生运行时问题；但现有测试没有覆盖 email 缺失对请求发送的影响。

第五，`WrappedChatOpenAI.model_name` 的类型限定为 `LLM_Model`，当前只允许 `gpt-3.5-turbo`、`gpt-3.5-turbo-16k`、`gpt-4`。如果要新增模型，需要同时更新 `schemas/agent.py` 的 `LLM_Model`、`LLM_MODEL_MAX_TOKENS`、测试，以及任何依赖 token 上限的逻辑，否则可能出现类型、校验或 token 预算不一致。

第六，返回对象后会被 `OpenAIAgentService` 多处原地修改，例如 `execute_task_agent` 调整 `max_tokens`，`summarize_task_agent` 和 `chat` 会把 `model_name` 改成 `gpt-3.5-turbo-16k`。因此工厂返回的不是不可变配置对象。修改初始化字段、字段名或包装类继承关系时，要检查这些后续原地修改是否仍然有效。
