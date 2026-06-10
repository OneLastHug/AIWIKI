# 目录：plugins/memory/mem0

## 它负责什么

`plugins/memory/mem0` 是 Hermes 外部记忆系统中的 Mem0 Provider 插件目录。它的职责不是实现本地向量库或本地记忆文件，而是把 Hermes 的对话记忆能力接到 Mem0 Platform：通过 Mem0 SDK 做服务端事实抽取、语义搜索、rerank 和去重。它实现的是 `agent.memory_provider.MemoryProvider` 抽象接口，因此在运行时会被统一纳入 `agent/memory_manager.py` 管理。

这个目录提供三类能力：一是启动时声明 Mem0 记忆提供者，二是在 agent 对话循环中异步同步完成的 user/assistant turn，三是向模型暴露可调用的记忆工具，包括 `mem0_profile`、`mem0_search`、`mem0_conclude`。配置来源以环境变量为默认值，例如 `MEM0_API_KEY`、`MEM0_USER_ID`、`MEM0_AGENT_ID`，同时允许 `$HERMES_HOME/mem0.json` 覆盖单项配置。

## 直接子目录地图

当前片段显示 `plugins/memory/mem0` 没有直接子目录，只有三个顶层文件：

`plugins/memory/mem0/__init__.py`：插件实现主体，包含配置读取、工具 schema、`Mem0MemoryProvider` 类、插件注册函数 `register(ctx)`。

`plugins/memory/mem0/plugin.yaml`：插件元信息，声明名称 `mem0`、版本、描述和 `pip_dependencies: mem0ai`。记忆插件发现流程会读取这里的描述用于列表展示。

`plugins/memory/mem0/README.md`：面向使用者的简短说明，描述安装依赖、执行 `hermes memory setup`、配置项和三个工具的用途。

因为没有 `cli.py`、`scripts/`、`templates/` 等文件，根据当前片段推断，mem0 插件没有自己的专属 CLI 子命令，也没有额外脚本或模板资源；它主要依赖统一的 memory setup 流程和 `MemoryProvider` 生命周期。

## 关键入口

最重要的入口是 `plugins/memory/mem0/__init__.py` 里的 `register(ctx)`。记忆插件加载器会导入该模块，优先查找 `register` 函数，并用一个 collector 风格的上下文接收 `ctx.register_memory_provider(Mem0MemoryProvider())`。这一步把 Mem0 插件实例交给通用 memory 框架。

核心类是 `Mem0MemoryProvider`。它实现了 `name`、`is_available()`、`initialize()`、`system_prompt_block()`、`prefetch()`、`queue_prefetch()`、`sync_turn()`、`get_tool_schemas()`、`handle_tool_call()`、`shutdown()` 等 MemoryProvider 接口。`is_available()` 只检查配置中是否有 API key，不主动进行网络调用；`_get_client()` 懒加载 `mem0.MemoryClient`，并在缺少 `mem0ai` 依赖时报错。

配置入口是 `_load_config()`。它先从环境变量构造默认配置，再读取 `$HERMES_HOME/mem0.json` 做字段覆盖。`save_config()` 则由 `hermes memory setup` 这类配置流程调用，把用户输入写入 `mem0.json`。

## 主流程位置

发现流程在 `plugins/memory/__init__.py`。`discover_memory_providers()` 会扫描 `plugins/memory/<name>/` 和用户插件目录，读取 `plugin.yaml`，尝试加载 provider 并调用 `is_available()`。`load_memory_provider("mem0")` 会定位到 `plugins/memory/mem0`，导入 `__init__.py`，通过 `register(ctx)` 得到 `Mem0MemoryProvider` 实例。

激活流程在 `agent/agent_init.py` 附近。系统读取配置项 `memory.provider`，如果值为 `mem0`，就通过 `plugins.memory.load_memory_provider` 加载插件，创建 `MemoryManager`，再调用 `add_provider()` 注册。随后 `initialize_all()` 会把 `session_id`、`hermes_home`、`platform`、可能的 gateway `user_id` 等上下文传给 provider。Mem0 的 `initialize()` 会确定 `_user_id`、`_agent_id`、`_rerank` 等运行态字段。

对话流程分三段：系统提示、召回、写入。系统提示由 `agent/system_prompt.py` 调用 `MemoryManager.build_system_prompt()` 汇总，Mem0 返回 `# Mem0 Memory` 说明块，提示模型可用 `mem0_search`、`mem0_conclude`、`mem0_profile`。每轮开始附近，`agent/conversation_loop.py` 会触发 `prefetch_all()` 获取上一轮后台召回结果；每轮完成后，`run_agent.py` 的 `_sync_external_memory_for_turn()` 调用 `sync_all()` 把完成的 turn 写入外部记忆，并调用 `queue_prefetch_all()` 为下一轮预热搜索。Mem0 的写入和召回都使用后台线程，避免阻塞主对话。

工具调用路由在 `agent/agent_runtime_helpers.py` 和 `agent/memory_manager.py`。初始化时，`get_all_tool_schemas()` 会把 `mem0_profile`、`mem0_search`、`mem0_conclude` 注入模型工具面；当模型调用这些工具时，`MemoryManager.handle_tool_call()` 根据工具名路由回 `Mem0MemoryProvider.handle_tool_call()`。

## 推荐阅读顺序

先读 `plugins/memory/mem0/plugin.yaml`，了解这个插件的身份、依赖和一句话能力边界。

再读 `plugins/memory/mem0/__init__.py` 的顶部配置区和三个 schema：`PROFILE_SCHEMA`、`SEARCH_SCHEMA`、`CONCLUDE_SCHEMA`。这能先建立“它给模型暴露什么能力”的视角。

接着读 `Mem0MemoryProvider` 的生命周期方法：`is_available()`、`initialize()`、`system_prompt_block()`、`sync_turn()`、`queue_prefetch()`、`prefetch()`、`handle_tool_call()`。这部分是理解主流程的关键。

然后跳到 `plugins/memory/__init__.py` 看 `discover_memory_providers()`、`load_memory_provider()`、`_load_provider_from_dir()`，理解为什么 `register(ctx)` 是有效入口。

最后看邻近框架：`agent/memory_provider.py` 了解接口契约，`agent/memory_manager.py` 了解 provider 如何被汇总和路由，`agent/agent_init.py`、`agent/conversation_loop.py`、`run_agent.py` 了解它在 agent 生命周期中的位置。

## 常见误区

不要把 `plugins/memory/mem0` 当成普通工具插件。它不是通过 `tools/registry.py` 注册核心工具，而是通过 memory provider 专用发现系统加载，再由 `MemoryManager` 把工具 schema 汇入 agent 工具面。

不要以为它会在每次 `prefetch()` 时立即联网搜索。Mem0 的设计是 `queue_prefetch()` 后台线程先搜索，把结果放进 `_prefetch_result`，下一轮 `prefetch()` 再取出并清空。因此它偏向“下一轮预热召回”，不是同步阻塞式查询。

不要把 `mem0_conclude` 和 `sync_turn()` 混为一谈。`sync_turn()` 把完整对话 turn 交给 Mem0 做服务端事实抽取；`mem0_conclude` 则把模型明确决定保存的事实以 `infer=False` 方式写入，强调“原样保存”。

不要忽略 user scope。读操作使用 `_read_filters()`，按 `user_id` 过滤；写操作使用 `_write_filters()`，带 `user_id` 和 `agent_id`。gateway 场景下 `initialize()` 会优先使用传入的 `user_id`，这影响不同用户的记忆隔离。

不要认为配置只在 `.env`。`_load_config()` 明确支持 `$HERMES_HOME/mem0.json` 覆盖环境变量，`save_config()` 也是写这个 JSON 文件。排查配置问题时需要同时看 `memory.provider`、Mem0 API key、`mem0ai` 依赖和 `mem0.json`。
