# 文件：agent/tool_executor.py

## 一句话定位

`agent/tool_executor.py` 是 Hermes Agent 的“工具调用执行器”：它接收模型返回的 `assistant_message.tool_calls`，负责按顺序或并发执行工具、处理拦截与 guardrail、写回 `tool` 消息，并把工具执行过程同步给 CLI、TUI、Gateway、ACP 等上层显示或集成通道。

## 它暴露/定义了什么

这个文件主要暴露两个模块级函数：`execute_tool_calls_concurrent(agent, assistant_message, messages, effective_task_id, api_call_count=0)` 和 `execute_tool_calls_sequential(agent, assistant_message, messages, effective_task_id, api_call_count=0)`。它们原本语义上属于 `AIAgent` 的方法，现在被抽到独立模块，但仍以 `agent` 作为第一个参数操作父对象状态。文件还定义 `_MAX_TOOL_WORKERS`、`_ra()`、`_tool_search_scoped_names()` 等辅助逻辑，并通过 `__all__` 只导出两个执行入口。

## 谁调用它

主调用链是 `agent/conversation_loop.py` 在模型返回 tool calls 后调用 `agent._execute_tool_calls(...)`。`run_agent.py` 中的 `AIAgent._execute_tool_calls()` 先用 `_should_parallelize_tool_batch()` 判断是否可并行，然后转发到 `AIAgent._execute_tool_calls_concurrent()` 或 `AIAgent._execute_tool_calls_sequential()`。这两个方法本身只是薄封装，真正实现就在 `agent/tool_executor.py`。测试中也大量直接或间接覆盖这两条路径，说明该文件是工具执行行为的稳定边界。

## 它调用谁

底层工具派发主要有两类。并发路径通过 `agent._invoke_tool()` 进入 `agent/agent_runtime_helpers.py` 的 `invoke_tool()`，再分发到内置 agent 级工具、memory manager、context engine 或 `run_agent.handle_function_call()`。顺序路径为了保留历史显示行为，仍在本文件中内联处理 `todo`、`session_search`、`memory`、`clarify`、`delegate_task`、context engine、memory provider 等特殊工具，普通工具再走 `handle_function_call()`。

周边依赖包括 `agent.display` 负责工具预览、可爱提示和失败检测；`agent.tool_dispatch_helpers` 负责危险命令识别、多模态结果处理和 `make_tool_result_message()`；`tools.tool_result_storage` 负责大结果持久化和单轮预算裁剪；`tools.thread_context.propagate_context_to_thread` 负责把 ContextVar 与线程本地回调传播到并发 worker；`hermes_cli.plugins.get_pre_tool_call_block_message` 提供插件级工具拦截；`agent._tool_guardrails` 提供重复失败、无进展等运行时保护。

## 核心流程

整体流程可以理解为“解析、预检、执行、收尾、回写”。

首先从 `assistant_message.tool_calls` 取出每个调用，解析 JSON 参数；如果模型实际调用的是 Tool Search 的桥接工具 `tool_call`，会尝试解包为底层工具名和参数。这里有一个重要安全点：解包后会用 `_tool_search_scoped_names(agent)` 检查该底层工具是否在当前 session 的 enabled/disabled toolset 范围内，避免受限子代理通过桥接绕过作用域。

然后执行插件拦截和 `ToolGuardrailController.before_call()`。若被拦截，不会触发 checkpoint、callback 或真实工具执行，而是合成错误结果。若允许执行，则对文件写入工具 `write_file`、`patch` 或危险 `terminal` 命令创建 checkpoint。并发路径会先统一完成这些 pre-flight，再用 `ThreadPoolExecutor` 启动最多 `_MAX_TOOL_WORKERS` 个 worker；顺序路径则每个工具依次完成同样步骤。

执行阶段会设置活动心跳、工具开始/完成 callback、quiet spinner、`_current_tool` 等 UI 与网关状态。并发 worker 会注册自身线程 id，使 `AIAgent.interrupt()` 能把中断传播到正在执行的工具线程；同时用 `propagate_context_to_thread()` 继承审批、sudo、secret 等线程上下文。执行结果返回后，会经过 `_detect_tool_failure()`、`agent._append_guardrail_observation()`、文件变更结果记录、`maybe_persist_tool_result()`、子目录提示追加、多模态内容转换，最后用 `make_tool_result_message()` 追加到 `messages`。每个工具结果后还会应用 pending `/steer`，整轮结束再用 `enforce_turn_budget()` 控制总输出大小。

## 关键函数的高层作用

`execute_tool_calls_concurrent()` 面向可安全并行的工具批次。它的重点不是简单并发，而是保持结果顺序与原始 `tool_call_id` 对齐，同时处理线程中断、上下文传播、心跳、插件拦截、guardrail、checkpoint、回调和预算裁剪。它先把所有调用解析成 `parsed_calls`，阻塞项直接填入结果槽，可执行项进入线程池，最后按原顺序统一写回 `messages`。

`execute_tool_calls_sequential()` 面向单工具、交互式工具或不能并行的批次。它的行为更接近旧版 `AIAgent` 内联逻辑，因此保留了许多特殊工具分支和 spinner 展示细节。它每执行完一个工具就立即写回结果，并检查是否有用户中断，适合 `clarify`、`delegate_task`、memory 写入等有顺序语义或交互语义的场景。

`_tool_search_scoped_names()` 是 Tool Search 解包的安全辅助函数。它基于当前 agent 的 enabled/disabled toolsets 和工具 registry generation 缓存可延迟调用的工具名集合，用来确保桥接调用不能访问本 session 未授权的工具。根据当前片段推断，这个缓存主要是为了避免每次工具调用都重建完整工具定义，依据是函数注释明确提到 registry generation 与 toolset scope 组成 cache key。

`_ra()` 是兼容性辅助函数，延迟导入 `run_agent`。它存在的原因是测试或旧代码可能 patch `run_agent._set_interrupt`、`run_agent.handle_function_call` 等符号，执行器需要回到 `run_agent` 模块取这些符号以保持行为兼容。

## 修改风险

最大风险是消息协议破坏。工具结果必须追加为 provider 期望的 `role: tool` 消息，并保持 `tool_call_id` 与模型原始调用一致；并发路径还必须按原始顺序写回，否则后续 LLM API 可能拒绝请求或把结果对应到错误工具。

第二类风险是安全边界回退。Tool Search 解包、插件 pre-tool hook、`ToolGuardrailController`、危险命令 checkpoint、`make_tool_result_message()` 的不可信内容包装共同构成执行前后安全层。随意调整顺序可能导致未授权工具执行、间接提示注入防护失效，或被 guardrail 阻断的工具仍触发副作用。

第三类风险是并发与中断。`_tool_worker_threads` 注册、`_set_interrupt()` 清理、`propagate_context_to_thread()`、activity heartbeat 都是为了让并发工具在 Gateway、TUI、审批流和 `/stop` 下正常工作。遗漏 finally 清理可能污染线程池复用线程；不传播上下文可能让审批或 secret 回调在线程内不可见。

第四类风险是输出体积与多模态结果。`maybe_persist_tool_result()`、`enforce_turn_budget()`、`_tool_result_content_for_active_model()` 共同决定大输出、图片结果和文本模型降级如何进入上下文。修改这里会影响长工具输出是否撑爆上下文、vision provider 是否能接收图片、session history 是否保持可序列化。

最后，顺序路径和并发路径存在大量“相同语义的两份实现”。新增工具类型、回调、guardrail 后处理或结果记录时，需要确认两条路径都覆盖；否则某些场景只在单工具时正常，批量并发时行为会分叉。
