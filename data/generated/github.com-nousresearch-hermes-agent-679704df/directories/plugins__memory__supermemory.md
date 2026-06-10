# 目录：plugins/memory/supermemory

## 它负责什么

`plugins/memory/supermemory` 是 Hermes 的一个外部记忆提供者插件，用来把 Hermes 的长期记忆能力接到 Supermemory 服务上。它不实现通用的 memory 调度框架，而是实现 `agent.memory_provider.MemoryProvider` 约定的一个具体后端：负责检查依赖和密钥、初始化 Supermemory SDK 客户端、在对话前召回相关记忆、在对话后写入清洗后的 turn、在会话结束时上传完整会话，并向模型暴露一组显式记忆工具。

这个目录的定位可以概括为“Supermemory 适配层”。Hermes 的 memory 生命周期、工具路由和 provider 管理在邻近框架里完成，例如 `agent/memory_provider.py` 定义接口，`agent/memory_manager.py` 负责统一编排，`agent/agent_init.py` 在初始化阶段加载 provider，`agent/tool_executor.py` 把 memory tool call 转交给 `MemoryManager`。本目录只关心 Supermemory 这一种 provider 的配置、API 调用、数据清洗和工具实现。

插件支持两类记忆写入：一类是自动写入，即每轮对话完成后把 user/assistant 内容组合成结构化文本写入；另一类是显式工具写入，即模型调用 `supermemory_store` 保存某条长期记忆。此外，它还会在 `on_session_end()` 中把完整会话发给 Supermemory 的 conversation ingest 接口，用于更丰富的后端提取。代码里包含外部服务端点常量，但学习文档中不展开真实地址。

## 直接子目录地图

该目录当前没有直接子目录。根据 `find plugins/memory/supermemory -maxdepth 2 -type d` 的结果，目录树只有根目录本身：

`plugins/memory/supermemory`

根目录下主要文件是：

`plugins/memory/supermemory/__init__.py`：插件主体，包含配置加载、Supermemory 客户端封装、`SupermemoryMemoryProvider` 实现、工具 schema 和 `register(ctx)` 注册入口。

`plugins/memory/supermemory/plugin.yaml`：插件元信息，声明名称、版本、描述和 `pip_dependencies`，其中依赖包含 `supermemory`。

`plugins/memory/supermemory/README.md`：面向使用者的说明，描述安装、配置、环境变量、工具列表、profile-scoped containers 和 multi-container mode。

## 关键入口

最重要的入口是 `plugins/memory/supermemory/__init__.py` 末尾的 `register(ctx)`。它调用 `ctx.register_memory_provider(SupermemoryMemoryProvider())`，把当前 provider 注册进 Hermes 的 memory plugin 系统。也就是说，插件发现机制只需要导入这个模块并执行 `register()`，后续生命周期就由 `MemoryManager` 接管。

核心类是 `SupermemoryMemoryProvider`。它继承 `MemoryProvider`，并实现了 provider 必需和可选的生命周期方法。`name` 返回固定标识 `supermemory`；`is_available()` 检查 `SUPERMEMORY_API_KEY` 是否存在以及 `supermemory` Python 包是否可导入；`get_config_schema()` 告诉 `hermes memory setup` 只需要提示 API key；`save_config()` 将非密钥配置保存到 `$HERMES_HOME/supermemory.json`。

实际访问 Supermemory 的封装类是 `_SupermemoryClient`。它包住 `supermemory.Supermemory` SDK，并提供 `add_memory()`、`search_memories()`、`get_profile()`、`forget_memory()`、`forget_by_query()`、`ingest_conversation()` 等方法。Provider 自身不直接把 SDK 调用散落在各生命周期中，而是通过这个小客户端集中处理 container tag、search mode、metadata、entity context 和返回值整理。

工具入口由四个 schema 定义：`STORE_SCHEMA`、`SEARCH_SCHEMA`、`FORGET_SCHEMA`、`PROFILE_SCHEMA`。`get_tool_schemas()` 返回这些 schema；如果启用了 multi-container mode，还会给每个工具动态加上可选的 `container_tag` 参数。真正执行工具的是 `handle_tool_call()`，它根据 tool name 分派到 `_tool_store()`、`_tool_search()`、`_tool_forget()`、`_tool_profile()`。

## 主流程位置

初始化流程从 `initialize(session_id, **kwargs)` 开始。它读取 Hermes home，保存当前 `session_id`，加载 `$HERMES_HOME/supermemory.json`，读取 `SUPERMEMORY_API_KEY`，解析 container tag，并根据 `agent_identity` 支持 `{identity}` 模板。随后它读取自动召回、自动捕获、召回数量、profile 频率、capture mode、search mode、entity context、timeout，以及 multi-container 相关配置。最后，如果 API key 存在，就创建 `_SupermemoryClient`。

对话前召回主要在 `prefetch(query, session_id="")`。当 provider active、`auto_recall` 开启且 query 非空时，它调用 `_client.get_profile(query=query[:200])`。是否带上 profile facts 由 `_turn_count` 和 `profile_frequency` 决定：第一轮会带，之后每隔 N 轮带一次。召回结果通过 `_format_prefetch_context()` 格式化成 `<supermemory-context>...</supermemory-context>` 块，供上层注入上下文。

对话后写入在 `sync_turn(user_content, assistant_content, session_id="")`。它先检查 active、`auto_capture`、写权限和 client；然后用 `_clean_text_for_capture()` 去掉已注入的 `<supermemory-context>` 与 `<supermemory-containers>` 块，再过滤空内容、过短内容和简单寒暄。通过过滤后，会把一轮对话包装为 `[role: user]... [user:end]` 与 `[role: assistant]... [assistant:end]` 的文本，并在后台线程 `supermemory-sync` 中调用 `add_memory()`。

会话结束流程在 `on_session_end(messages)`。它筛选 `user` 和 `assistant` 消息，清洗内容，忽略过短会话，然后调用 `_client.ingest_conversation()` 上传完整会话。这个流程和逐 turn 的 `sync_turn()` 不同：前者是会话级 ingest，后者是 turn 级 memory document 写入。

显式记忆工具流程由 `handle_tool_call()` 统一入口分发。`supermemory_store` 会保存模型指定的 content，并自动补 metadata；`supermemory_search` 语义搜索并返回 id、content、similarity；`supermemory_forget` 支持按 id 删除或按 query 找到最佳匹配后删除；`supermemory_profile` 返回 persistent profile 与 recent context 的摘要。multi-container mode 下，`_resolve_tool_container_tag()` 会校验工具传入的 tag 必须在 primary container 和 `custom_containers` 白名单内。

此外，`on_memory_write(action, target, content)` 会镜像 Hermes 内置 memory 写入。当上层发生内置 memory add 行为时，Supermemory provider 会把这条显式记忆也写入 Supermemory，并标记 metadata 来源为 `hermes_memory`。

## 推荐阅读顺序

1. 先读 `plugins/memory/supermemory/plugin.yaml`，确认这是一个 memory provider 插件，并注意它声明的 `supermemory` pip 依赖。

2. 再读 `plugins/memory/supermemory/README.md`，建立使用层面的概念：需要 `SUPERMEMORY_API_KEY`，通过 `memory.provider` 选择 provider，配置文件是 `$HERMES_HOME/supermemory.json`，工具包括 store/search/forget/profile。

3. 然后读 `agent/memory_provider.py`，理解 Hermes 对 provider 的生命周期要求：`initialize()`、`system_prompt_block()`、`prefetch()`、`sync_turn()`、`get_tool_schemas()`、`handle_tool_call()`、`shutdown()`，以及可选的 `on_turn_start()`、`on_session_end()`、`on_memory_write()` 等钩子。

4. 回到 `plugins/memory/supermemory/__init__.py` 顶部，先看默认配置和辅助函数，如 `_default_config()`、`_load_supermemory_config()`、`_sanitize_tag()`、`_format_prefetch_context()`、`_clean_text_for_capture()`。这些函数解释了 provider 的行为边界。

5. 再看 `_SupermemoryClient`，把外部 SDK 调用和 provider 生命周期分开理解。

6. 最后看 `SupermemoryMemoryProvider`，按 `initialize()`、`system_prompt_block()`、`prefetch()`、`sync_turn()`、`on_session_end()`、`get_tool_schemas()`、`handle_tool_call()`、`shutdown()` 的顺序串起主流程。

## 常见误区

不要把 `plugins/memory/supermemory` 理解成完整的 memory 系统。它只是一个 provider 实现；provider 的选择、生命周期调用、工具 schema 合并和 tool call 路由由 `MemoryManager` 及 agent 主流程完成。

不要把 `plugin.yaml` 当成运行逻辑入口。它只声明元信息和依赖；真正注册 provider 的入口是 `__init__.py` 里的 `register(ctx)`。

不要认为每次用户发消息都会立即进行后台预取线程。这个 provider 实现了同步的 `prefetch()`，但没有覆盖 `queue_prefetch()`；根据当前片段推断，它依赖上层在每轮前直接调用 `prefetch()` 获取召回上下文，依据是 `SupermemoryMemoryProvider` 中没有自定义 `queue_prefetch()`，而 `MemoryProvider` 默认实现为空。

不要把自动记忆和显式工具记忆混为一谈。`sync_turn()` 保存的是清洗后的 user/assistant turn，metadata 类型是 `conversation_turn`；`supermemory_store` 保存的是模型主动请求的 memory，metadata 来源是 `hermes_tool`；`on_memory_write()` 镜像的是 Hermes 内置 memory add 行为，metadata 来源是 `hermes_memory`。

不要忽略写入开关 `_write_enabled`。`initialize()` 会根据 `agent_context` 判断是否允许写入；当上下文是 `cron`、`flush`、`subagent` 时会关闭写入，避免后台任务或子代理污染主用户记忆。

不要以为 multi-container 会影响所有自动流程。README 和代码都显示，工具可以通过 `container_tag` 访问白名单中的容器，但自动操作，如 turn sync、prefetch、memory write mirroring、session ingest，默认仍使用 primary container。
