# 子系统：platform/reworkd_platform/services/tokenizer

## 解决什么问题

`platform/reworkd_platform/services/tokenizer` 是后端平台里负责“token 估算与上下文预算控制”的小型服务层。它不直接调用 LLM，也不决定 prompt 内容，而是在 agent 调用 OpenAI 兼容聊天模型前，计算 prompt 已经占用了多少 token，并据此压缩 `WrappedChatOpenAI.max_tokens`，避免一次请求的 prompt token 与 completion token 总和超过模型上限。

这个目录的职责可以概括为三件事：统一使用 `tiktoken` 编码器；提供文本与 token id 之间的转换和计数；根据模型最大上下文长度，为当前请求动态计算还能留给模型输出的 token 数。它是 agent 执行链路中的基础设施组件，尤其影响 `start_goal_agent`、`analyze_task_agent`、`create_tasks_agent`、`summarize_task_agent`、`chat` 等路径的稳定性。

## 相关目录和文件

目标目录下的核心文件很少：

`platform/reworkd_platform/services/tokenizer/token_service.py` 定义 `TokenService`，是实际业务逻辑所在。它封装 `tiktoken.Encoding`，提供 `tokenize`、`detokenize`、`count`、`get_completion_space`、`calculate_max_tokens` 等方法。

`platform/reworkd_platform/services/tokenizer/lifetime.py` 负责应用启动时初始化 tokenizer。`init_tokenizer(app)` 会调用 `tiktoken.get_encoding("cl100k_base")`，并把结果放到 `app.state.token_encoding`。

`platform/reworkd_platform/services/tokenizer/dependencies.py` 是 FastAPI 依赖注入入口。`get_token_service(request)` 从 `request.app.state.token_encoding` 取出已初始化的编码器，并构造 `TokenService`。

`platform/reworkd_platform/services/tokenizer/__init__.py` 仅用于包声明，根据当前片段看没有额外导出逻辑。

相关调用方主要在 `platform/reworkd_platform/web/api/agent/agent_service/open_ai_agent_service.py`。这里的 `OpenAIAgentService` 接收 `TokenService`，并在多个 agent 方法里调用 `calculate_max_tokens` 或直接使用 `tokenize`、`detokenize` 截断长文本。`platform/reworkd_platform/web/lifetime.py` 会导入并调用 `init_tokenizer`，说明 tokenizer 生命周期绑定在 Web 应用启动流程上。`platform/reworkd_platform/web/api/agent/agent_service/agent_service_provider.py` 通过 `get_token_service` 把服务注入 agent service。测试侧有 `platform/reworkd_platform/tests/test_token_service.py`，覆盖 tokenize/detokenize、计数和 max token 计算边界。

## 核心对象

`TokenService` 是本目录唯一核心对象。它的构造函数接收一个 `tiktoken.Encoding`，而不是每次调用时重新加载编码器。这一点很重要，因为 `tiktoken.get_encoding` 可能在首次使用时下载或加载编码资源，所以项目选择在应用启动时完成初始化，再通过 FastAPI state 复用。

`TokenService.create` 是一个便捷构造方法，默认编码名为 `cl100k_base`。这适合测试或非 FastAPI 场景直接创建服务实例。

`tokenize(text)` 把字符串编码为 `list[int]`；`detokenize(tokens)` 把 token id 列表解码回字符串；`count(text)` 返回编码后的 token 数。`get_completion_space(model, *prompts)` 会先从 `LLM_MODEL_MAX_TOKENS` 中读取模型上下文上限，找不到时默认按 `4000` 处理，然后把所有 prompt 的 token 数相加，返回剩余可用空间。

`calculate_max_tokens(model, *prompts)` 直接修改传入的 `WrappedChatOpenAI` 实例。它先计算剩余 completion 空间，再将 `model.max_tokens` 收敛到“用户/配置请求值”和“剩余上下文空间”两者的较小值，最后保证结果至少为 `1`。这意味着该方法有副作用，不是纯函数。

## 运行流程

应用启动时，`web/lifetime.py` 调用 `init_tokenizer(app)`。`init_tokenizer` 使用 `tiktoken.get_encoding("cl100k_base")` 创建编码器，并存入 `app.state.token_encoding`。注释中说明该编码适用于 `gpt-4`、`gpt-3.5-turbo`、`text-embedding-ada-002` 等模型。

请求进入 agent API 后，`agent_service_provider.py` 通过 FastAPI `Depends(get_token_service)` 获取 `TokenService`。`get_token_service` 不重新初始化编码器，而是从 `request.app.state.token_encoding` 包装一个新的服务对象。

在 `OpenAIAgentService` 执行具体任务时，会先构造 LangChain prompt，再调用 `calculate_max_tokens`。例如启动目标拆解时，会把 `goal` 和 `language` 格式化进 `start_goal_prompt`，转换为字符串后交给 tokenizer 计数；任务分析时，还会把 OpenAI function schema 的字符串形式一并计入 token 预算；创建后续任务和聊天也会根据完整 prompt 重新计算输出空间。

总结任务路径略有不同。`summarize_task_agent` 会强制切换模型名为 `gpt-3.5-turbo-16k`，把 `max_tokens` 设置为 `8000`，然后把历史结果拼接后 token 化，只保留前 `7000` 个 token，再 detokenize 回文本用于总结。这里 tokenizer 不只是估算预算，还直接承担了长文本截断功能。

## 上下游依赖

上游依赖包括 `tiktoken`、FastAPI 的 `Request`/`FastAPI`、以及模型上限配置 `reworkd_platform.schemas.agent.LLM_MODEL_MAX_TOKENS`。`TokenService.calculate_max_tokens` 的类型依赖是 `reworkd_platform.web.api.agent.model_factory.WrappedChatOpenAI`，并假设该对象至少有 `model_name` 和 `max_tokens` 属性。

下游主要是 agent 服务层。`OpenAIAgentService` 在调用 LangChain、OpenAI function calling、工具执行、总结和聊天前依赖 tokenizer 调整输出预算。若 tokenizer 计算偏差过大，表现出来的问题通常不在 tokenizer 目录内，而是 OpenAI 请求失败、模型输出被截断、任务生成为空、总结缺失后半部分等。

测试依赖集中在 `tests/test_token_service.py`。根据当前片段推断，测试验证了空字符串、普通字符串、长文本、超大 prompt 后最小 `max_tokens` 为 `1` 等行为，依据是搜索结果中出现了 `test_calculate_max_tokens_with_negative_result`、`test_calculate_max_tokens_with_high_completion_tokens` 等测试名。

## 修改时最容易踩的坑

第一，`calculate_max_tokens` 会原地修改 `WrappedChatOpenAI.max_tokens`。如果同一个 model 实例在一个请求流程中被复用，前一次调用压低的 `max_tokens` 会影响后续步骤。修改调用顺序或复用策略时要特别留意。

第二，`get_completion_space` 对未知模型默认使用 `4000`。如果新增模型但忘记更新 `LLM_MODEL_MAX_TOKENS`，系统不会直接报错，而是可能保守地压低输出空间，导致模型能力没有被充分使用。

第三，`cl100k_base` 并不一定精确匹配所有未来模型。当前实现把编码器作为全局固定配置，适合现有 `gpt-3.5`、`gpt-4` 时代的模型；如果引入不同 tokenizer 的模型，需要重新评估 `ENCODING_NAME` 或按模型选择编码器。

第四，`detokenize(text_tokens[0:snippet_max_tokens])` 是按 token 截断，不是按语义段落截断。这样能控制长度，但可能切断上下文、列表或结构化文本。总结质量问题不一定来自 summarizer，也可能来自这里的截断策略。

第五，任务分析时把 `str(functions)` 计入 prompt 预算。这个值依赖工具 schema 的字符串表示，如果工具数量或 schema 变复杂，会明显挤占 completion 空间。

## 推荐阅读顺序

建议先读 `platform/reworkd_platform/services/tokenizer/lifetime.py`，理解编码器何时初始化、为什么放在 `app.state`。然后读 `platform/reworkd_platform/services/tokenizer/dependencies.py`，确认 FastAPI 如何把 tokenizer 服务注入请求链路。

接着读 `platform/reworkd_platform/services/tokenizer/token_service.py`，重点看 `get_completion_space` 和 `calculate_max_tokens`，它们定义了整个子系统的行为边界。

之后阅读 `platform/reworkd_platform/web/api/agent/agent_service/open_ai_agent_service.py` 中使用 `token_service` 的几个方法，尤其是 `start_goal_agent`、`analyze_task_agent`、`create_tasks_agent`、`summarize_task_agent` 和 `chat`。最后再看 `platform/reworkd_platform/tests/test_token_service.py`，用测试反推该服务被期望保持的边界行为。
