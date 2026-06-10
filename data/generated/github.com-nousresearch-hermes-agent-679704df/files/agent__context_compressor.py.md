# 文件：agent/context_compressor.py

## 一句话定位

`agent/context_compressor.py` 是 Hermes 默认的上下文压缩引擎：当会话消息接近模型上下文上限时，它把“中间历史”压缩成结构化摘要，同时保留系统提示、早期关键消息和最新尾部上下文，避免长对话因 token 超限中断。

## 它暴露/定义了什么

文件核心定义是 `ContextCompressor`，它继承 `agent.context_engine.ContextEngine`，实现默认 `name == "compressor"` 的上下文管理策略。对外最重要的接口包括 `should_compress()`、`compress()`、`update_from_response()`、`update_model()`、`has_content_to_compress()` 和生命周期方法 `on_session_reset()`。

文件还定义了一组压缩相关常量和辅助函数。`SUMMARY_PREFIX` 是插入到摘要前的强约束提示，明确告诉后续模型“摘要只是背景，不是当前指令”。`LEGACY_SUMMARY_PREFIX`、`_HISTORICAL_SUMMARY_PREFIXES` 用于兼容旧版本摘要格式。`_MIN_SUMMARY_TOKENS`、`_SUMMARY_RATIO`、`_SUMMARY_TOKENS_CEILING` 控制摘要预算。多模态相关的 `_IMAGE_TOKEN_ESTIMATE`、`_strip_historical_media()` 用于避免旧图片或截图在压缩后继续撑爆请求体。

辅助函数大多服务于三类工作：估算内容长度，如 `_content_length_for_budget()`；安全拼接和提取消息内容，如 `_append_text_to_content()`、`_content_text_for_contains()`；裁剪工具调用和工具结果，如 `_truncate_tool_call_args_json()`、`_summarize_tool_result()`。

## 谁调用它

初始化入口在 `agent/agent_init.py`。根据检索结果，`agent_init` 会导入 `ContextCompressor`，并在没有被插件 context engine 替换时创建内置压缩器，同时调用 `update_model()` 同步模型、provider、上下文长度等运行时信息。

运行期主要由 `agent/conversation_loop.py` 和 `agent/conversation_compression.py` 调用。`conversation_loop` 在请求前后检查 token 使用、触发预压缩或真实使用量后的压缩；`conversation_compression.compress_context()` 是 `run_agent.py` 中 `_compress_context()` 的实际转发目标，负责持有压缩锁、调用 `agent.context_compressor.compress(...)`，并根据 `_last_compress_aborted`、`_last_summary_error` 等状态向 CLI 或 gateway 暴露警告。

`agent/chat_completion_helpers.py`、`agent/agent_runtime_helpers.py` 会在模型切换、fallback、响应 usage 更新等场景中读取或更新 `context_compressor`。`agent/tool_executor.py` 也会把 context engine 提供的工具调用转发给 `handle_tool_call()`，不过内置 `ContextCompressor` 默认不暴露额外工具。

## 它调用谁

它调用 `agent.model_metadata` 中的 `get_model_context_length()`、`estimate_messages_tokens_rough()` 和 `MINIMUM_CONTEXT_LENGTH` 来决定上下文窗口、阈值和压缩后估算大小。它调用 `agent.auxiliary_client.call_llm()` 生成摘要，并使用 `_is_connection_error()` 辅助判断摘要模型失败类型。它调用 `agent.redact.redact_sensitive_text()` 在发送给摘要模型和持久化摘要前清理 API key、token、密码等敏感信息。

它还依赖 `agent.context_engine.ContextEngine` 的抽象契约：压缩器必须维护 `last_prompt_tokens`、`threshold_tokens`、`context_length`、`compression_count` 等字段，因为 `run_agent.py` 和周边运行时会直接读取这些状态。

## 核心流程

压缩主流程集中在 `ContextCompressor.compress()`。

第一步是重置本次压缩状态，例如 `_last_summary_error`、`_last_summary_fallback_used`、`_last_compress_aborted`。如果是手动 `/compress`，`force=True` 会清除摘要失败冷却，让用户可以立即重试。

第二步判断消息数量是否足够压缩。压缩器不会动太短的会话，因为它至少要保护系统提示、头部消息和最低尾部消息。

第三步执行 cheap pre-pass：`_prune_old_tool_results()` 会先处理旧工具结果，不调用 LLM。它会去重重复工具输出，把长工具结果替换成一行信息摘要，裁剪旧 `tool_calls` 的长 JSON 参数，并剥离旧截图或多模态 payload。这一步可以显著降低摘要模型输入和最终上下文体积。

第四步计算边界。`_protect_head_size()` 保留系统消息和前几个非系统消息；`_align_boundary_forward()` 防止压缩起点切断 assistant tool call 与 tool result 的配对；`_find_tail_cut_by_tokens()` 从尾部按 token 预算保留最近上下文，并调用 `_ensure_last_user_message_in_tail()` 确保最新用户消息不会被压进摘要里。这个设计很关键，因为 `SUMMARY_PREFIX` 要求模型只响应摘要之后的最新用户消息，如果最新用户消息被压缩掉，当前任务就可能“消失”。

第五步生成摘要。`_generate_summary()` 会把中间消息通过 `_serialize_for_summary()` 转成带角色标签的文本，构造结构化 prompt，调用 `call_llm(task="compression", ...)`。摘要模板要求包含 `Active Task`、`Goal`、`Completed Actions`、`Active State`、`Pending User Asks`、`Relevant Files`、`Remaining Work` 等章节。若已有 `_previous_summary`，它不是从零摘要，而是做迭代更新。

第六步组装新消息列表。压缩器保留 head，插入摘要，再拼回 tail；如果单独插入摘要会造成相邻消息角色不合适，就把摘要前置合并到第一个 tail 消息。之后调用 `_sanitize_tool_pairs()` 清理孤立 tool call 或 tool result，最后 `_strip_historical_media()` 移除历史图片 payload，并更新压缩次数、节省比例和 anti-thrashing 计数。

## 关键函数的高层作用

`__init__()` 负责根据模型和配置计算 `context_length`、`threshold_tokens`、`tail_token_budget`、`max_summary_tokens`，并初始化压缩状态。它是压缩策略的参数中心。

`update_model()` 用于模型切换或 fallback 后重新校准压缩阈值和摘要预算。修改模型路由相关逻辑时必须同步关注它，否则上下文窗口变化后压缩器可能继续使用旧预算。

`update_from_response()` 保存真实 API usage。`should_defer_preflight_to_real_usage()` 利用真实 prompt token 抵消粗略估算的噪声，避免工具 schema 很大时反复误触发压缩。

`should_compress()` 判断是否超过阈值，同时带 anti-thrashing：连续两次压缩节省低于 10% 时会暂停自动压缩，避免无限压缩循环。

`_prune_old_tool_results()` 是压缩前的低成本瘦身层，重点保护最近 tail，处理旧工具输出、重复输出、长参数和截图。它不改变语义主线，但会丢失旧工具结果的完整原文。

`_generate_summary()` 是最核心的 LLM 摘要函数。它负责摘要预算、序列化、prompt 模板、focus topic、summary model fallback、失败冷却和敏感信息保护。这里的 prompt 文案会直接影响压缩后模型是否继续当前任务、是否重复旧任务。

`_build_static_fallback_summary()` 在摘要模型不可用时生成本地确定性 fallback。它提取最近用户请求、工具动作、路径、错误和最后丢弃的 turns，信息不如 LLM 摘要完整，但能保留恢复锚点。

`_find_tail_cut_by_tokens()` 决定哪些最新消息必须原样保留。它不仅按预算累计，还避免切断工具调用组，并保证最新用户消息在 tail 中。

`_sanitize_tool_pairs()` 修复压缩后可能产生的 tool call/result 不匹配，避免 OpenAI 格式消息被 provider 拒绝。

`has_content_to_compress()` 是手动 `/compress` 的快速判断，用相同边界逻辑判断是否存在可压缩中间区间。

## 修改风险

最大风险是破坏消息序列合法性。OpenAI 格式要求 assistant 的 `tool_calls` 与后续 `tool` 消息成对；如果改动边界对齐、工具结果裁剪或 `_sanitize_tool_pairs()`，可能导致 provider 返回 400，甚至每一轮都重复发送坏历史。

第二个风险是当前任务丢失或旧任务复活。`SUMMARY_PREFIX`、`_ensure_last_user_message_in_tail()`、摘要模板里的 `Active Task` 共同维持“摘要是背景、最新用户消息优先”的语义。如果随意改摘要前缀或 tail 保护策略，模型可能把旧请求当成新指令，或者忽略真正最新的用户请求。

第三个风险是摘要泄露敏感信息。`_serialize_for_summary()` 和 fallback 都使用 `redact_sensitive_text()`，修改序列化路径时必须保证工具参数、工具输出、用户文本、旧摘要都经过脱敏。

第四个风险是压缩预算失衡。`threshold_percent`、`summary_target_ratio`、`tail_token_budget`、`max_summary_tokens` 互相影响。预算过小会丢上下文，预算过大则压缩后仍可能超限。多模态消息还依赖 `_IMAGE_TOKEN_ESTIMATE` 的保守估算，低估图片会导致请求体或 token 超限。

第五个风险是故障恢复行为变化。`abort_on_summary_failure` 为真时摘要失败会放弃压缩；否则会插入 deterministic fallback 并丢弃中间窗口。这里的状态字段被 `conversation_compression`、gateway 和 CLI 用来展示警告，改字段语义会影响用户可见行为。

根据当前片段推断，这个文件处在上下文管理的核心路径，任何改动都应配合长对话、工具调用、多模态、摘要模型失败、手动 `/compress <focus>`、模型切换和 provider 400 场景测试。
