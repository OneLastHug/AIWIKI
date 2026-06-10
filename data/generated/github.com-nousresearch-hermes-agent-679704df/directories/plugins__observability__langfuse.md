# 目录：plugins/observability/langfuse

## 它负责什么

`plugins/observability/langfuse` 是 Hermes 内置但默认不启用的 Langfuse 可观测性插件。它的职责不是改变 agent 的推理、工具执行或对话结果，而是在 Hermes 的插件 hook 生命周期中旁路采集数据，把一次用户 turn、其中的 LLM 请求、工具调用、token 用量和估算成本组织成 Langfuse trace / observation。

这个目录的定位可以概括为“观测适配层”：上游接入 Hermes 的通用插件系统，下游接入 `langfuse` Python SDK。插件启用后，仍需要运行时满足 SDK 可导入、环境变量凭据存在且格式有效；否则多数 hook 会 no-op，整体设计偏 fail-open，避免观测系统故障影响主流程。

它观测的核心对象包括：

- 一次 Hermes turn：对应 Langfuse 中名为 `Hermes turn` 的 root observation。
- 每次模型请求：对应 `LLM call {api_call_count}` generation observation。
- 每次工具调用：对应 `Tool: {tool_name}` tool observation。
- 模型用量与成本：通过 `agent.usage_pricing` 的 `normalize_usage`、`estimate_usage_cost` 等逻辑归一化后写入 Langfuse。
- 工具输出摘要：尤其对 `read_file` 这类可能返回大文本或 base64 的结果做裁剪和结构化预览，避免观测 payload 过大。

## 直接子目录地图

当前片段中，`plugins/observability/langfuse` 没有直接子目录，只有三个顶层文件：

- `plugins/observability/langfuse/plugin.yaml`：插件元数据与 hook 声明。
- `plugins/observability/langfuse/__init__.py`：插件的全部运行时逻辑，包括 Langfuse client 初始化、trace 状态管理、hook 回调、payload 归一化和注册入口。
- `plugins/observability/langfuse/README.md`：面向使用者的启用、凭据配置、验证和可选调参说明。

因此这是一个“小而集中”的插件目录，不是分层包结构。阅读时应把 `__init__.py` 当成主模块，而不是去寻找更深的 `client.py`、`hooks.py` 或 `tracing.py`。

## 关键入口

最关键的入口是 `plugins/observability/langfuse/__init__.py` 末尾的 `register(ctx)`。Hermes 插件系统加载该插件后，会调用这个函数，插件在这里注册六类 hook：

- `pre_api_request` -> `on_pre_llm_request`
- `post_api_request` -> `on_post_llm_call`
- `pre_llm_call` -> `on_pre_llm_call`
- `post_llm_call` -> `on_post_llm_call`
- `pre_tool_call` -> `on_pre_tool_call`
- `post_tool_call` -> `on_post_tool_call`

`plugin.yaml` 是插件发现与展示层入口，声明 `name: langfuse`、版本、描述、作者、所需环境变量以及 hooks。它本身不执行逻辑，但告诉 Hermes 这个插件依赖哪些 hook 事件，以及需要 `HERMES_LANGFUSE_PUBLIC_KEY`、`HERMES_LANGFUSE_SECRET_KEY` 这类凭据。

运行时初始化入口是 `_get_langfuse()`。这个函数负责延迟创建并缓存 `Langfuse` client。它会检查 `langfuse` SDK 是否可导入，读取 `HERMES_LANGFUSE_PUBLIC_KEY` / `LANGFUSE_PUBLIC_KEY`、`HERMES_LANGFUSE_SECRET_KEY` / `LANGFUSE_SECRET_KEY` 等环境变量，并校验 key 前缀，防止 placeholder 配置导致 Langfuse SDK 表面初始化成功、实际 flush 时才失败。初始化失败会缓存为 `_INIT_FAILED`，后续 hook 快速返回。

状态入口是 `TraceState` dataclass 和全局 `_TRACE_STATE`。`TraceState` 保存当前 turn 的 `trace_id`、root span、未结束的 generation、工具 observation、按名称暂存的工具调用以及本 turn 收集到的 tool call 输出。

## 主流程位置

主流程从 Hermes 触发插件 hook 开始。根据当前片段和邻近搜索结果推断，工具调用 hook 在 `model_tools.py` 中触发，API 请求相关 hook 在 `run_agent.py` 的模型请求流程附近触发；插件自身通过 `hermes_cli.plugins.PluginContext.register_hook` 挂接这些事件。

一次典型 turn 的观测流程如下：

1. LLM 请求前，`on_pre_llm_request()` 被调用。它先通过 `_get_langfuse()` 获取 client，再用 `_trace_key(task_id, session_id)` 确定状态键。如果当前 turn 还没有 trace，就调用 `_start_root_trace()` 创建 root observation；随后创建一个 generation observation，存入 `state.generations[api_call_count]`。
2. LLM 请求后，`on_post_llm_call()` 被调用。它找到对应 generation，序列化 assistant message 或 API 摘要，调用 `_usage_and_cost()` 整理 token 与成本，再用 `_end_observation()` 结束该 generation。如果 assistant 没有工具调用且已经有最终内容，会调用 `_finish_trace()` 结束 root trace 并 flush。
3. 如果 assistant 发起工具调用，`on_pre_tool_call()` 在工具执行前创建 tool observation，并按 `tool_call_id` 或 `tool_name` 暂存。
4. 工具执行后，`on_post_tool_call()` 找回 observation，解析和裁剪 `result`，对 `read_file` 结果走 `_normalize_read_file_payload()`，再结束 tool observation。同时它会把工具输出回填到 `state.turn_tool_calls` 中对应的 tool call 记录里。
5. 后续 LLM 请求再次走 `on_pre_llm_request()` / `on_post_llm_call()`。当最终 assistant 响应不再包含工具调用时，`_finish_trace()` 合并最终输出和本 turn 的工具调用记录，结束 root span，调用 `client.flush()`。

`on_pre_llm_call()` 是兼容入口。注释说明旧版 Hermes 可能直接用 `pre_llm_call` 传 API messages；新版还会用这个 hook 做 turn 级上下文注入。插件只在 `messages` 是 list 时才追踪，避免创建多余孤立 trace。

## 推荐阅读顺序

1. 先读 `plugins/observability/langfuse/README.md`，理解这个插件是 opt-in、需要哪些环境变量、如何验证是否有 trace。
2. 再读 `plugins/observability/langfuse/plugin.yaml`，确认插件名、hook 列表和所需凭据。这一步能建立“它接入 Hermes 生命周期的哪些点”的地图。
3. 进入 `plugins/observability/langfuse/__init__.py`，先看顶部 docstring、`TraceState`、全局变量和 `_get_langfuse()`，理解运行时门禁和状态模型。
4. 接着读 `register(ctx)`，把六个 hook 和对应函数建立索引。
5. 按主流程读 `on_pre_llm_request()`、`on_post_llm_call()`、`on_pre_tool_call()`、`on_post_tool_call()`、`_finish_trace()`。
6. 最后再补读 `_safe_value()`、`_normalize_payload()`、`_normalize_read_file_payload()`、`_usage_and_cost()` 这些辅助函数。它们不是流程入口，但决定了最终送到 Langfuse 的数据形态、大小和成本字段。

## 常见误区

一个常见误区是以为启用插件就一定会发送 trace。实际上 Hermes 插件启用只是第一层条件；运行时还必须安装 `langfuse` SDK，并配置有效的 key。`_get_langfuse()` 一旦判定不可用，会让后续 hook 快速 no-op。

第二个误区是把 `pre_llm_call` 当成唯一模型请求入口。这个插件更偏向使用 `pre_api_request` / `post_api_request` 做逐 API 请求追踪，`pre_llm_call` / `post_llm_call` 主要用于跨 Hermes 版本兼容。阅读时应优先理解 `on_pre_llm_request()` 和 `on_post_llm_call()`。

第三个误区是认为它会记录完整原始数据。插件大量使用 `_safe_value()`、`_truncate_text()`、`_serialize_messages()` 限制深度、条数和字符数；`read_file` 结果还会被转换为 head / tail 预览，base64 内容只保留长度。这是有意设计，用来控制观测系统中的敏感面和 payload 体积。

第四个误区是把这个目录当成通用 observability 框架。它只是 Langfuse 适配插件；Hermes 的通用插件发现、hook 调度和阻断逻辑在 `hermes_cli/plugins.py`，工具执行 hook 的触发在 `model_tools.py`，LLM/API 请求 hook 的触发在 `run_agent.py`。本目录只实现“收到 hook 后如何构造 Langfuse trace”。

第五个误区是忽略 `_TRACE_STATE` 的 key 规则。`_trace_key()` 优先使用 `task_id`，其次使用 `session_id`，最后退回线程 id。也就是说 trace 聚合依赖 Hermes 调用 hook 时传入的任务和会话标识；如果这些标识缺失，根据当前片段推断，插件会尽量用线程级 fallback 保证同一执行线程内仍能关联观测。
