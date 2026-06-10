# 文件：agent/memory_manager.py

## 一句话定位

`agent/memory_manager.py` 是 Hermes Agent 外部记忆系统的统一编排层：它把具体记忆后端抽象成 `MemoryProvider`，负责注册、初始化、上下文召回、回合同步、工具路由和生命周期通知，并隔离后端失败对主对话流程的影响。

## 它暴露/定义了什么

这个文件主要定义三类能力。

第一类是上下文清洗能力：`sanitize_context()` 会移除 `<memory-context>` fence、内部 system note 和已包裹的记忆块；`StreamingContextScrubber` 用状态机处理流式输出中跨 chunk 拆开的 `<memory-context>`，避免记忆注入内容泄露到 UI；`build_memory_context_block()` 把预取到的记忆包装成受控的 `<memory-context>` 块。

第二类是核心类 `MemoryManager`。它维护 `_providers` 和 `_tool_to_provider`，对外提供 provider 注册、系统提示拼接、预取、同步、工具 schema 收集、工具调用分发、session/turn/compression/delegation 生命周期通知，以及 `initialize_all()`、`shutdown_all()` 等批量操作。

第三类是兼容层逻辑。文件中使用 `inspect.signature()` 判断 provider 是否支持 `messages` 参数或 `metadata` 参数，用来兼容新旧 `MemoryProvider` 实现，降低插件升级成本。

## 谁调用它

初始化入口在 `agent/agent_init.py`：当 `memory.provider` 配置存在且 `skip_memory` 为 false 时，会创建 `MemoryManager`，通过 `plugins.memory.load_memory_provider()` 加载 provider，检查 `is_available()` 后 `add_provider()`，再调用 `initialize_all()`。同一阶段还会把 provider 暴露的工具 schema 注入 `agent.tools`，但会受 `enabled_toolsets` 中 `"memory"` 的配置约束。

对话主循环相关调用在 `agent/conversation_loop.py`：每个 turn 开始前调用 `on_turn_start()`，随后调用 `prefetch_all()` 取回外部记忆上下文。系统提示构造在 `agent/system_prompt.py` 调用 `build_system_prompt()`。回合完成后，`run_agent.py` 的 `_sync_external_memory_for_turn()` 调用 `sync_all()` 和 `queue_prefetch_all()`，把完成的用户输入和最终回复写入外部记忆，并预热下一轮召回。

工具执行路径在 `agent/tool_executor.py` 和 `agent/agent_runtime_helpers.py`：如果函数名属于 `MemoryManager.has_tool()`，就绕过普通工具 registry，调用 `handle_tool_call()` 转发给对应 provider。上下文压缩路径在 `agent/conversation_compression.py` 调用 `on_pre_compress()` 和 `on_session_switch()`。会话结束或切换时，`run_agent.py` 调用 `on_session_end()`、`shutdown_all()`。

## 它调用谁

`MemoryManager` 直接依赖 `agent.memory_provider.MemoryProvider` 定义的接口，包括 `initialize()`、`system_prompt_block()`、`prefetch()`、`queue_prefetch()`、`sync_turn()`、`get_tool_schemas()`、`handle_tool_call()`、`shutdown()`，以及可选 hook：`on_turn_start()`、`on_session_end()`、`on_session_switch()`、`on_pre_compress()`、`on_memory_write()`、`on_delegation()`。

错误返回使用 `tools.registry.tool_error()` 生成 JSON 字符串。`initialize_all()` 在调用方没有传 `hermes_home` 时，会延迟导入 `hermes_constants.get_hermes_home()`，保证 provider 使用 profile-aware 的 Hermes home 路径。

## 核心流程

启动阶段：`agent_init` 根据配置加载一个外部记忆 provider，创建 `MemoryManager`，执行 `add_provider()` 建立 provider 列表和工具名索引，然后 `initialize_all()` 传入 `session_id`、`platform`、`hermes_home`、用户/聊天身份等上下文。随后收集 `get_all_tool_schemas()`，把记忆工具加入模型可见工具面。

对话阶段：turn 开始时 `on_turn_start()` 通知 provider 更新计数、节奏或范围；随后 `prefetch_all()` 根据原始用户消息取回召回文本。召回文本通常会被 `build_memory_context_block()` 包装成受控的内部上下文，进入模型输入，但不应作为用户新输入处理。模型输出流式返回时，`StreamingContextScrubber` 用来清掉意外泄露的内部 memory context。

回合结束：`sync_all()` 把干净的用户消息、最终 assistant 响应以及可选完整 `messages` 传给 provider；`queue_prefetch_all()` 让 provider 在后台为下一轮预取。若回合被中断，`run_agent.py` 会跳过同步，避免把未完成的回复写成长期记忆。

工具调用阶段：模型调用记忆 provider 暴露的工具时，`has_tool()` 判断是否归属记忆系统，`handle_tool_call()` 根据 `_tool_to_provider` 找到 provider 并转发。provider 异常会被捕获并转成 tool error，不会抛出到主循环。

会话生命周期：退出、reset、compression、resume、branch 等场景会触发 `on_session_end()` 或 `on_session_switch()`。压缩前还会调用 `on_pre_compress()`，让 provider 有机会把即将被压缩/丢弃的上下文转成摘要提示材料。

## 关键函数的高层作用

`add_provider()` 是注册入口。它允许内置 provider 名称 `"builtin"` 存在，但外部 provider 只能有一个；第二个外部 provider 会被拒绝。这是为了避免工具 schema 膨胀、多个记忆后端同时写入导致语义冲突。注册时还会建立 tool name 到 provider 的路由表，并处理工具名冲突。

`build_system_prompt()` 汇总 provider 的静态提示块。它不负责召回具体记忆，只把 provider 想加入系统提示的状态或规则拼起来。

`prefetch_all()` 是每轮前的召回入口。它遍历 provider 调用 `prefetch(query, session_id=...)`，合并非空结果。单个 provider 失败只记 debug，不影响其他 provider 或主对话。

`sync_all()` 是每轮后的写入入口。它把用户输入和 assistant 输出同步给所有 provider，并根据 provider 签名决定是否传入完整 `messages`。这是外部长期记忆落盘或入库的关键位置。

`get_all_tool_schemas()`、`has_tool()`、`handle_tool_call()` 共同组成记忆工具面。前者给模型暴露工具定义，后两者在执行阶段把工具调用路由回 provider。

`on_memory_write()` 用于把内置 memory tool 的写入镜像给外部 provider，并跳过 `"builtin"` provider 自身。它通过签名检查兼容三种 metadata 传参方式。

`StreamingContextScrubber.feed()` 是流式安全的核心。它维护是否处于 `<memory-context>` 内部的状态，遇到跨 chunk 的开闭标签时会暂存可能的标签尾部，宁愿丢弃未闭合 span，也不把内部记忆内容泄露给用户界面。

辅助函数如 `_provider_sync_accepts_messages()`、`_provider_memory_write_metadata_mode()` 主要是 provider API 兼容判断；`providers`、`get_provider()`、`get_all_tool_names()` 是轻量查询接口。

## 修改风险

最大风险是破坏记忆上下文边界。`sanitize_context()`、`build_memory_context_block()`、`StreamingContextScrubber` 共同防止 provider 输出被当成用户输入或泄露到 UI；修改标签、正则或流式状态机时，要重点测试跨 chunk 标签、未闭合标签、大小写变化和普通文本中类似字符串的情况。

第二个风险是 provider 失败隔离。这个文件大量使用 `try/except`，设计目标是“记忆可选，主对话不能被记忆后端拖垮”。如果把 debug/warning 级别的异常改成向上抛出，可能导致网络型记忆后端故障时整个 agent 不可用。

第三个风险是工具 schema 和工具名路由。`add_provider()` 与 `get_all_tool_schemas()` 都在去重；`agent_init` 还会避免与已有工具重名。改动这里可能导致 OpenAI-style tool schema 重名、模型端 400、或记忆工具无法执行。

第四个风险是生命周期顺序。`on_turn_start()` 必须早于 `prefetch_all()`，回合中断不能进入 `sync_all()`，compression 后必须 `on_session_switch()` 刷新 provider 的 session 缓存。顺序变更会造成召回节奏错误、脏记忆写入或跨 session 污染。

第五个风险是向后兼容。已有记忆插件可能实现的是旧签名，例如 `sync_turn()` 不接收 `messages`，`on_memory_write()` 不接收 `metadata`。删除 `inspect` 兼容逻辑会让旧插件在运行期失败。
