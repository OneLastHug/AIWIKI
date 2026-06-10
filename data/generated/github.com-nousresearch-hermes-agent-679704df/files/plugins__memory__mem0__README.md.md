# 文件：plugins/memory/mem0/README.md

## 一句话定位

`plugins/memory/mem0/README.md` 是 Mem0 记忆提供器插件的入口说明文档，用很短的篇幅告诉使用者如何启用 `mem0` 作为 Hermes 的外部 memory provider，以及它会向模型暴露哪些记忆工具。

## 它暴露/定义了什么

这个文件本身不定义 Python 代码，也不会被运行时导入。它面向用户暴露四类信息：依赖、配置方式、配置文件位置、工具清单。

依赖层面，它说明需要安装 `mem0ai`，并准备 Mem0 API key。为避免输出真实外部地址，这里只保留结论：API key 来自 Mem0 平台。

配置层面，它给出两条路径：推荐使用 `hermes memory setup` 交互式选择 `mem0`；也可以手动设置 `memory.provider` 为 `mem0`，并把 `MEM0_API_KEY` 写入 `$HERMES_HOME/.env` 或等价环境配置。

配置文件层面，它声明 `$HERMES_HOME/mem0.json` 支持 `user_id`、`agent_id`、`rerank` 三个主要键。结合 `plugins/memory/mem0/__init__.py` 可知，实际实现还会从环境变量读取 `MEM0_API_KEY`、`MEM0_USER_ID`、`MEM0_AGENT_ID`，并支持 `keyword_search` 默认项，但 README 没有展开该字段。

工具层面，它列出三项模型可调用工具：`mem0_profile` 用于拉取用户全部记忆，`mem0_search` 用于语义检索，`mem0_conclude` 用于直接写入一条事实。

## 谁调用它

严格说，运行时代码不会调用这个 README。它的“调用方”是人：安装插件的人、排查记忆配置的人、以及维护文档或插件行为的开发者。

真正的运行时调用链发生在同目录的 `plugins/memory/mem0/__init__.py`。当 `config.yaml` 中 `memory.provider` 设置为 `mem0` 后，`agent/agent_init.py` 会通过 `plugins.memory.load_memory_provider("mem0")` 加载 provider；`plugins/memory/__init__.py` 发现并导入该目录，然后调用模块里的 `register(ctx)`，收集 `Mem0MemoryProvider` 实例。随后 `agent.memory_manager.MemoryManager` 负责初始化、工具路由、prefetch、sync 和 shutdown。

## 它调用谁

README 不调用任何代码。根据当前片段推断，它描述的命令和配置最终会影响以下组件：`hermes_cli/memory_setup.py` 负责 `hermes memory setup` 的发现、依赖提示和配置写入；`plugins/memory/mem0/__init__.py` 负责读取 `$HERMES_HOME/mem0.json` 和环境变量；`agent/memory_manager.py` 负责统一调度 provider；Mem0 SDK 的 `MemoryClient` 负责实际远端读写。

在实现层面，`Mem0MemoryProvider` 会调用 `mem0.MemoryClient` 的 `search`、`get_all`、`add` 等能力；错误结果通过 `tools.registry.tool_error` 包装；配置路径通过 `hermes_constants.get_hermes_home()` 保持 profile-aware。

## 核心流程

第一步是安装与选择。用户安装 `mem0ai`，再运行 `hermes memory setup`，选择 `mem0`。配置向导会发现 `plugins/memory/mem0`，读取 provider 的 `get_config_schema()`，把 secret 字段写入 `.env`，把非 secret 配置写入 provider 自己的配置位置，最后把 `memory.provider` 保存为 `mem0`。

第二步是 agent 初始化。`agent/agent_init.py` 读取 `memory.provider`，如果值非空，就创建 `MemoryManager`，加载 `Mem0MemoryProvider`，调用 `is_available()` 判断 API key 是否存在，再执行 `initialize()`。`initialize()` 会确定 `_api_key`、`_user_id`、`_agent_id`、`_rerank`，其中 gateway 场景优先使用运行时传入的 `user_id`，CLI 场景回落到配置默认值。

第三步是对话前后记忆流转。每轮开始时，`conversation_loop` 调用 `MemoryManager.prefetch_all()`，Mem0 provider 从上一轮后台检索缓存中取出结果，作为 `## Mem0 Memory` 上下文注入。每轮结束后，agent 调用外部记忆同步逻辑，`Mem0MemoryProvider.sync_turn()` 在后台线程中把用户消息和助手回复发送给 Mem0，由服务端做事实抽取和去重；同时 `queue_prefetch()` 为下一轮查询提前发起语义搜索。

第四步是模型主动工具调用。模型看到 `mem0_profile`、`mem0_search`、`mem0_conclude` schema 后，可以通过 `MemoryManager.handle_tool_call()` 路由到 Mem0 provider。工具结果必须是 JSON 字符串，这是 `MemoryProvider` 抽象接口约束。

## 关键函数的高层作用

`_load_config()` 是配置合并入口：先读环境变量作为默认值，再用 `$HERMES_HOME/mem0.json` 覆盖非空字段，避免存在 JSON 文件时把 `.env` 中的 API key 意外遮蔽。

`Mem0MemoryProvider.is_available()` 是启用门禁，只检查是否有 API key，不做网络请求，符合 `MemoryProvider` 对可用性检查的约定。

`initialize()` 绑定本次 agent 会话的身份和配置。它不立即创建 SDK client，而是把连接延迟到 `_get_client()`，降低初始化失败面。

`_get_client()` 是线程安全的懒加载 SDK 客户端入口。它导入 `MemoryClient`，缺少 `mem0ai` 时抛出明确安装提示。

`prefetch()` 和 `queue_prefetch()` 组成异步检索机制：`queue_prefetch()` 后台查询下一轮可能需要的记忆，`prefetch()` 在下一轮快速消费缓存，避免每次模型循环都同步等待远端搜索。

`sync_turn()` 是写入主路径：把完整的一问一答交给 Mem0 服务端做事实抽取。它使用后台线程，并在上一轮同步未结束时短暂等待，避免并发写入堆积。

`handle_tool_call()` 是三种工具的统一分发器：`mem0_profile` 调 `get_all`，`mem0_search` 调 `search`，`mem0_conclude` 调 `add(..., infer=False)` 直接保存原文事实。

`_is_breaker_open()`、`_record_success()`、`_record_failure()` 是熔断保护，连续失败达到阈值后暂停 API 调用一段时间，避免远端服务故障时每轮对话持续放大失败。

`shutdown()` 等待后台 prefetch/sync 线程结束，并清空 SDK client，属于资源收尾函数。

## 修改风险

修改 README 的最大风险不是破坏运行时，而是让用户按错误路径配置插件。比如把 `memory.provider`、`MEM0_API_KEY`、`$HERMES_HOME/mem0.json` 写错，会导致 `agent/agent_init.py` 找不到 provider 或 `is_available()` 返回 false，最终 Mem0 不会激活。

工具名风险较高。README 中的 `mem0_profile`、`mem0_search`、`mem0_conclude` 必须与 `plugins/memory/mem0/__init__.py` 里的 schema 名称一致；如果文档改名但代码不改，用户会误以为模型能调用不存在的工具。如果代码改名但 README 不更新，排障时也会误导。

配置字段也需要谨慎。`user_id` 决定跨会话读取范围，`agent_id` 决定写入归属，`rerank` 影响召回质量和成本。文档如果把作用说反，可能造成不同用户或不同 gateway 身份之间的记忆边界理解错误。根据实现，读过滤只按 `user_id`，写过滤按 `user_id + agent_id`；这意味着修改身份说明时必须参考实现，而不是只看 README 表格。

最后，外部 URL、安装命令和 API key 获取说明属于易过期内容。若更新 README，应同步核对 `get_config_schema()`、`hermes_cli/memory_setup.py` 的安装流程、`hermes_cli/doctor.py` 对 `mem0` 的诊断逻辑，避免文档、setup、doctor 三者出现不一致。
