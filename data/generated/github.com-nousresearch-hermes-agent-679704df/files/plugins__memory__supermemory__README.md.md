# 文件：plugins/memory/supermemory/README.md

## 一句话定位

`plugins/memory/supermemory/README.md` 是 Hermes 内置 `supermemory` 记忆提供者的使用与配置说明页，面向启用该 memory plugin 的用户和维护者，解释它如何把 Supermemory 作为长期语义记忆后端接入 Hermes 的 `MemoryProvider` 生命周期。

## 它暴露/定义了什么

这个文件本身不定义 Python API，也不参与运行时导入；它暴露的是插件契约的文档化入口。README 说明了启用条件、配置文件位置、环境变量、对模型暴露的工具、自动召回/自动写入行为、按 profile 分容器以及多容器模式。

核心概念包括：

`memory.provider=supermemory`：通过 Hermes 配置选择该外部记忆提供者。

`SUPERMEMORY_API_KEY`：必需密钥，运行时由 `SupermemoryMemoryProvider.is_available()` 和 `initialize()` 读取。

`$HERMES_HOME/supermemory.json`：插件私有配置文件，由 `plugins/memory/supermemory/__init__.py` 中的 `_load_supermemory_config()` 读取。

`container_tag`：Supermemory 端的隔离标签，支持 `{identity}` 模板，用于按 Hermes profile 生成不同容器。

四个模型工具：`supermemory_store`、`supermemory_search`、`supermemory_forget`、`supermemory_profile`，实际 schema 和 dispatch 都在 `plugins/memory/supermemory/__init__.py` 中实现。

README 还记录了 `enable_custom_container_tags`、`custom_containers`、`custom_container_instructions` 这组三个多容器配置，它们会改变工具 schema：当多容器启用时，四个工具会额外接受 `container_tag` 参数，并通过白名单校验。

## 谁调用它

严格来说，没有代码“调用”这个 README。它被人的工作流调用：用户配置 Supermemory、维护者理解插件行为、`hermes memory setup` 的使用者查看依赖和配置方式时会参考它。

从运行时链路看，README 描述的是 `plugins/memory/supermemory/__init__.py` 的行为。插件由 `plugins/memory/__init__.py` 的 memory provider discovery/load 机制加载；`agent/agent_init.py` 根据配置中的 `memory.provider` 调用 `load_memory_provider()`，再把返回的 `SupermemoryMemoryProvider` 注册到 `MemoryManager`。之后 `run_agent.py`、`agent/conversation_loop.py`、`agent/tool_executor.py` 等通过 `MemoryManager` 间接使用该 provider。

根据当前片段推断，`hermes memory setup` 会通过 `hermes_cli/memory_setup.py` 发现 memory provider，并读取 provider 的 `get_config_schema()` 以提示用户填写密钥；依据是 `hermes_cli/memory_setup.py` 中出现了 `discover_memory_providers`、`load_memory_provider`，而 `SupermemoryMemoryProvider.get_config_schema()` 返回的正是 API key 配置项。

## 它调用谁

README 不调用任何模块，但它所描述的实现会调用以下组件：

`agent.memory_provider.MemoryProvider`：`SupermemoryMemoryProvider` 继承的抽象接口，规定 `initialize()`、`prefetch()`、`sync_turn()`、`get_tool_schemas()`、`handle_tool_call()`、`shutdown()` 等生命周期。

`agent.memory_manager.MemoryManager`：统一编排 provider，合并 system prompt、prefetch context、tool schemas，并路由 memory tool call。

`supermemory` SDK：`_SupermemoryClient` 内部通过 `Supermemory(api_key=..., timeout=..., max_retries=0)` 连接外部服务，执行 `documents.add`、`search.memories`、`profile`、`memories.forget`。

`urllib.request`：用于会话结束时向 conversations 接口提交完整会话 ingest。README 中不要保留真实服务地址；源码常量 `_CONVERSATIONS_URL` 指向外部 API。

`tools.registry.tool_error`：工具调用失败时生成统一 JSON 错误结果。

`utils.atomic_json_write`：`save_config()` 写入 `supermemory.json` 时使用，避免配置文件半写入。

## 核心流程

启用流程是：用户通过 `hermes memory setup` 选择 `supermemory`，或手动设置 `memory.provider supermemory` 并配置 `SUPERMEMORY_API_KEY`。Agent 初始化时，`agent/agent_init.py` 创建 `MemoryManager`，加载当前配置指定的 provider，并调用 `initialize_all()`。`SupermemoryMemoryProvider.initialize()` 读取 `$HERMES_HOME/supermemory.json`、环境变量和 profile identity，生成最终 `container_tag`，再创建 `_SupermemoryClient`。

对话开始前，`MemoryManager.build_system_prompt()` 会收集 `system_prompt_block()`，告诉模型 Supermemory 已启用以及可用工具。每一轮用户输入开始时，`on_turn_start()` 记录 turn number；随后 `MemoryManager.prefetch_all()` 调用 `prefetch()`，插件通过 profile/search 召回相关长期记忆，并格式化为 `<supermemory-context>` 块交给上层再包装为 memory context。

对话完成后，`run_agent.py` 的 post-response 路径会通过 `MemoryManager.sync_all()` 调用 `sync_turn()`。插件清理掉已注入的 memory context，过滤过短或寒暄类内容，把用户和助手回复拼成结构化文本，异步写入 Supermemory。会话真正结束时，`MemoryManager.on_session_end()` 调用 provider 的 `on_session_end()`，它会清理完整消息列表并提交 conversation ingest，用于更丰富的图谱更新。

显式工具调用走另一条路径：模型请求 `supermemory_search` 等工具时，`agent/tool_executor.py` 发现工具属于 `MemoryManager`，调用 `MemoryManager.handle_tool_call()`，再路由到 `SupermemoryMemoryProvider.handle_tool_call()`。具体动作由 `_tool_store()`、`_tool_search()`、`_tool_forget()`、`_tool_profile()` 完成。

## 关键函数的高层作用

`_load_supermemory_config()` 负责读取并规范化 `supermemory.json`。它会限制数值范围、校验 `search_mode`、裁剪 `entity_context`，并处理多容器配置。修改配置项时通常要同步更新 README 的 Config 表，否则文档会失真。

`initialize()` 是 provider 的运行时装配点。它解析 `SUPERMEMORY_CONTAINER_TAG` 优先级、`{identity}` 模板、自动召回/捕获开关、多容器白名单，以及是否允许写入。`agent_context` 为 `cron`、`flush`、`subagent` 时会关闭写入，避免非主会话污染长期记忆。

`system_prompt_block()` 生成静态系统提示，告诉模型当前容器和可用工具。多容器启用时，它还注入允许的容器列表和用户配置的容器使用说明。

`prefetch()` 负责自动召回。它调用 `_SupermemoryClient.get_profile()`，按 turn 频率决定是否带上 persistent profile，再用 `_format_prefetch_context()` 生成可注入上下文。

`sync_turn()` 负责每轮自动捕获。它清洗上下文、过滤低价值消息，并用后台线程写入 `documents.add`，避免阻塞主对话。

`on_session_end()` 负责会话级 ingest，与逐轮 `sync_turn()` 不同，它提交完整清理后的 user/assistant 消息序列，更适合后端做整体抽取。

`get_tool_schemas()` 决定模型能看到哪些 Supermemory 工具，以及多容器模式下是否增加 `container_tag` 参数。

`handle_tool_call()` 是工具分发入口。它先检查 provider 是否 active，再按工具名路由到 store/search/forget/profile。辅助的 `_resolve_tool_container_tag()` 用白名单限制多容器写入范围，是防止模型随意指定容器的重要保护点。

## 修改风险

最大风险是 README 与实现不一致。这个文件虽然不影响运行，但它是配置和能力边界的权威说明之一；如果实现中新增配置、改变默认值、调整工具参数或改变自动写入策略，必须同步更新 README，否则用户会按旧契约配置，表现为记忆不生效、写入到错误容器，或多容器工具调用失败。

第二类风险是安全与隐私描述不足。`auto_capture`、`on_session_end()` 和显式 `supermemory_store` 都会把对话内容发送到外部服务；README 若弱化这些行为，用户可能误以为只做本地记忆。修改时应清楚区分自动召回、逐轮捕获、会话结束 ingest 和显式工具写入。

第三类风险是容器隔离。`container_tag` 支持 `{identity}`，多容器模式又允许模型传入 `container_tag`。文档若把“自动操作只使用 primary container”讲错，会影响 profile 隔离预期。实现中自动 prefetch、sync、memory write mirror、session ingest 默认都走 primary container；只有显式工具在白名单范围内可选容器。

第四类风险是工具 schema 变更。README 列出的四个工具由 provider 动态暴露给模型，不经过普通 `tools/registry.py` 的工具发现流程，而是由 `MemoryManager.get_all_tool_schemas()` 注入。如果维护者误以为要在核心 toolset 中添加这些工具，可能造成重复 schema 或路由冲突。

最后，README 中的外部链接和支持渠道属于用户文档内容；在生成源码学习文档时不应输出真实网址。若需要提到外部服务，只保留服务名或写成 `[URL已移除]`。
