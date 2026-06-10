# 目录：plugins/memory/hindsight

## 它负责什么

`plugins/memory/hindsight` 是 Hermes 的一个外部长期记忆提供器插件，把 Hindsight 接入统一的 `MemoryProvider` 抽象。它不是普通工具插件，也不是内置记忆本体，而是通过 `memory.provider: hindsight` 被选中后，由 `agent/memory_manager.py` 注册和调度的外部 memory provider。

它面向的能力是“跨会话长期记忆”：把对话内容写入 Hindsight 的 memory bank，并在后续回合通过 recall 或 reflect 找回相关上下文。Hindsight 侧提供知识图谱、实体解析、多策略检索和 LLM 综合能力；Hermes 侧负责配置、生命周期、工具暴露、自动召回、自动保留和会话切换时的状态处理。

这个目录支持三种连接模式：`cloud`、`local_embedded`、`local_external`。`cloud` 连接 Hindsight Cloud API；`local_embedded` 由 Hermes 启动本地 Hindsight daemon，并用本地配置的 LLM 做抽取和综合；`local_external` 指向用户已经运行的 Hindsight HTTP 服务。README 中提到的外部页面和服务地址在本文中不展开，统一视为 `[URL已移除]`。

## 直接子目录地图

这个目录没有直接子目录，只有三个顶层文件：

`plugins/memory/hindsight/__init__.py` 是核心实现文件，包含配置读取、依赖/运行时检查、异步事件循环复用、Hindsight client 创建、`HindsightMemoryProvider` 类、工具 schema、自动 recall/retain、会话切换、关闭清理和插件注册入口。

`plugins/memory/hindsight/plugin.yaml` 是插件元数据，声明名称 `hindsight`、版本、描述、pip 依赖 `hindsight-client>=0.4.22`，以及插件钩子信息。`hermes memory setup` 会读取这里的依赖声明来尝试安装缺失包。

`plugins/memory/hindsight/README.md` 是面向用户的配置说明，覆盖三种模式、配置文件位置、memory bank、recall/retain 参数、`memory_mode`、本地嵌入模式的 LLM 配置、暴露给模型的工具和环境变量。

## 关键入口

最关键的入口是 `plugins/memory/hindsight/__init__.py` 末尾的 `register(ctx)`。它调用 `ctx.register_memory_provider(HindsightMemoryProvider())`，把插件实例注册给 memory provider 插件系统。插件发现逻辑不在本目录，而在 `plugins/memory/__init__.py`：那里会扫描 `plugins/memory/` 和用户插件目录，判断目录是否像 memory provider，然后按名字加载。

核心类是 `HindsightMemoryProvider`，继承自 `agent.memory_provider.MemoryProvider`。它实现了 provider 框架期望的接口：`name`、`is_available()`、`initialize()`、`system_prompt_block()`、`prefetch()`、`queue_prefetch()`、`sync_turn()`、`get_tool_schemas()`、`handle_tool_call()`、`on_session_switch()`、`shutdown()`，并扩展了 `get_config_schema()`、`save_config()`、`post_setup()` 等 setup 相关能力。

配置入口主要有两个：`_load_config()` 读取 `$HERMES_HOME/hindsight/config.json`，并兼容旧的 `~/.hindsight/config.json`；`get_config_schema()` 为通用 setup wizard 描述可配置字段。`post_setup()` 是 Hindsight 的定制安装/配置流程，会让用户选择 cloud、local embedded 或 local external，并根据模式安装不同依赖、保存 config 和 secret。

运行时工具入口是 `get_tool_schemas()` 和 `handle_tool_call()`。当 `memory_mode` 不是 `context` 时，它暴露三个工具：`hindsight_retain`、`hindsight_recall`、`hindsight_reflect`。这些工具不是放在 `tools/` 目录注册的普通工具，而是由 `MemoryManager.get_all_tool_schemas()` 汇总进 agent 的工具面。

## 主流程位置

启动阶段的主流程根据当前片段推断如下：`agent/agent_init.py` 读取配置中的 `memory.provider`，如果值为 `hindsight`，会通过 `plugins.memory.load_memory_provider("hindsight")` 加载该目录，然后把返回的 provider 加入 `MemoryManager`，再调用 `initialize_all()`。依据是 `agent/agent_init.py` 中对 `memory.provider`、`load_memory_provider`、`MemoryManager()` 和 `initialize_all()` 的引用，以及 `plugins/memory/__init__.py` 中的 provider 加载逻辑。

初始化的核心在 `HindsightMemoryProvider.initialize()`。它会合并配置和环境变量，决定模式、API URL、bank id、budget、`memory_mode`、prefetch 方法、retain/recall 参数、session/document 标识等；还会探测 Hindsight API 是否支持 `update_mode='append'`，以决定 retain 时是使用稳定 session document 追加，还是退回到每进程唯一 document id。`local_embedded` 模式还会准备 profile env，并在后台线程中启动 embedded daemon。

对话前后的主流程分两条。第一条是召回：`MemoryManager.queue_prefetch_all()` 会让 provider 在后台为下一轮准备 recall/reflect；下一轮进入模型前，`MemoryManager.prefetch_all()` 调 `prefetch()` 取出缓存结果，并作为持久记忆上下文注入系统上下文。`HindsightMemoryProvider.queue_prefetch()` 负责根据 `recall_prefetch_method` 选择 `arecall` 或 `areflect`，并把结果存在 `_prefetch_result`。

第二条是写入：对话完成后，`MemoryManager.sync_all()` 调 `sync_turn()`。Hindsight 这里不是每次直接阻塞写入，而是把当前轮打包到 `_session_turns`，按 `retain_every_n_turns` 控制节奏，然后把实际 retain 操作放进 `_retain_queue`。后台单写者线程 `_writer_loop()` 顺序执行 `aretain_batch`，避免多个线程同时写同一 document，也避免解释器退出时 aiohttp 资源泄漏。

会话切换流程在 `on_session_switch()`。它覆盖 `/resume`、`/branch`、`/reset`、`/new` 和压缩导致的 session id 旋转。切换前，如果旧 session 有未 flush 的 turns，会先把它们排进同一个 writer 队列；然后等待旧 prefetch 结束并清空缓存；最后更新 `_session_id`、`_parent_session_id`、`_document_id` 和 turn buffer，保证后续写入落到新 session。

关闭流程在 `shutdown()`。它先设置 `_shutting_down`，停止接受新 retain，再向 writer 队列发送 sentinel 并等待后台线程退出；随后等待 prefetch 线程结束，关闭 Hindsight client。模块级共享 async loop 不在这里停止，因为同一进程里可能有多个 provider 实例共享它。

## 推荐阅读顺序

建议先读 `plugins/memory/hindsight/README.md`，建立用户视角：三种模式、配置文件、`memory_mode`、三个工具和 recall/retain 参数分别是什么。

然后读 `plugins/memory/hindsight/plugin.yaml`，确认这是 memory provider 插件，依赖是 `hindsight-client>=0.4.22`，而不是 core tool 或普通 lifecycle plugin。

第三步读 `agent/memory_provider.py`，只需要理解 `MemoryProvider` 抽象要求的生命周期方法。这样再看 `HindsightMemoryProvider` 时，不会被大量 Hindsight 细节淹没。

第四步读 `agent/memory_manager.py` 的注册、`prefetch_all()`、`queue_prefetch_all()`、`sync_all()`、tool routing 和 `shutdown_all()`，理解 Hermes 如何调度外部记忆 provider。

最后回到 `plugins/memory/hindsight/__init__.py`，按段落看：文件头配置和常量、API capability probe、共享 async loop、工具 schema、配置加载、embedded profile/env 构造、`HindsightMemoryProvider` 初始化、prefetch、sync retain、tool call、session switch、shutdown、`register(ctx)`。

## 常见误区

不要把 `hindsight_retain`、`hindsight_recall`、`hindsight_reflect` 当成 `tools/` 下的普通内置工具。它们由 memory provider 动态提供，是否出现取决于 `memory.provider` 和 `memory_mode`。

不要以为 `plugin.yaml` 里的 `pip_dependencies` 就代表所有模式只需要 `hindsight-client`。README 和 `post_setup()` 显示，`local_embedded` 还涉及本地 Hindsight runtime 和 LLM 配置；cloud 模式则主要需要 API key。

不要忽略 `memory_mode`。`context` 只做自动上下文注入，不暴露工具；`tools` 只暴露工具，不做自动注入；`hybrid` 两者都启用。调试“为什么模型没有工具”或“为什么上下文没自动出现”时，先看这个字段。

不要把 `prefetch()` 理解成同步请求 Hindsight。实际请求通常在上一轮通过 `queue_prefetch()` 后台发起，`prefetch()` 更像是取回已经准备好的缓存结果。

不要轻易改动 session/document 逻辑。`on_session_switch()`、`_resolve_retain_target()`、API version probe 和 writer 队列共同处理“跨 session 写错文档”“旧 API 覆盖文档”“切换时丢未 flush turns”等问题，是这个 provider 中风险较高的部分。

不要把配置只看作环境变量。该插件优先围绕 `$HERMES_HOME/hindsight/config.json` 做 profile-scoped 配置，同时兼容旧路径和若干环境变量覆盖；Hermes 当前 profile 会影响实际读写位置。
