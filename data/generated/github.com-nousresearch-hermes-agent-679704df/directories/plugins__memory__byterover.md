# 目录：plugins/memory/byterover

## 它负责什么

`plugins/memory/byterover` 是 Hermes 的一个外部 memory provider 插件目录，用来把 ByteRover 接入 Hermes 的长期记忆系统。它不是普通的工具插件，也不是内置 memory 本体，而是实现 `agent.memory_provider.MemoryProvider` 接口后，通过 `ctx.register_memory_provider(...)` 注册为可选的外部记忆后端。

这个插件的核心职责有三层：

第一，封装 ByteRover CLI，也就是 `brv` 命令。目录内的 `__init__.py` 会解析 `brv` 可执行文件位置，优先从 `PATH` 查找，找不到时再检查几个常见安装位置。所有实际读写记忆的操作最终都会走 `_run_brv(...)`，由它调用 `brv query`、`brv curate`、`brv status`。

第二，给 Hermes agent 提供长期记忆生命周期能力。`ByteRoverMemoryProvider` 实现了 `initialize`、`system_prompt_block`、`prefetch`、`sync_turn`、`on_memory_write`、`on_pre_compress`、`get_tool_schemas`、`handle_tool_call`、`shutdown` 等方法。也就是说，它既能在每轮对话前检索旧记忆，也能在每轮对话后异步沉淀新信息，还能在上下文压缩前把即将丢弃的片段刷入 ByteRover。

第三，向模型暴露三个 ByteRover 相关工具：`brv_query`、`brv_curate`、`brv_status`。这些工具不是通过 `tools/registry.py` 直接注册的普通核心工具，而是由 memory provider 的 `get_tool_schemas()` 返回，再由 `MemoryManager` 注入 agent 的工具面。

它的存储工作目录是 `$HERMES_HOME/byterover/`，因此是 profile-scoped 的；可选云同步凭据是 `BRV_API_KEY`。README 和插件元数据里出现的安装链接在本文中省略为 `[URL已移除]`。

## 直接子目录地图

这个目录当前没有直接子目录，是一个很小的单文件实现型插件目录。根据当前文件列表，它包含三个顶层文件：

`plugins/memory/byterover/__init__.py` 是主实现文件，包含 ByteRover CLI 调用封装、工具 schema、`ByteRoverMemoryProvider` 类以及 `register(ctx)` 插件入口。

`plugins/memory/byterover/plugin.yaml` 是插件元数据，声明 `name: byterover`、版本、描述、外部依赖 `brv`，并标出 `on_pre_compress` 这类 hook 能力。它主要供插件发现、展示和配置界面读取。

`plugins/memory/byterover/README.md` 是使用说明，说明如何安装 `brv`、如何通过 `hermes memory setup` 选择 `byterover`，以及 `BRV_API_KEY`、工作目录和工具列表。

因为没有 `scripts/`、`cli.py`、`templates/` 或更多 package 子模块，所以阅读时不需要按子目录展开；重点集中在 `__init__.py` 的 provider 实现。

## 关键入口

最关键的入口是 `plugins/memory/byterover/__init__.py` 末尾的 `register(ctx)`。这个函数调用 `ctx.register_memory_provider(ByteRoverMemoryProvider())`，把 provider 实例交给 Hermes 的 memory plugin 系统。和普通插件的工具注册不同，这里注册的是一个 `MemoryProvider`，后续由 `plugins/memory/__init__.py` 的发现和加载逻辑，以及 `agent/agent_init.py` 中读取 `memory.provider` 的初始化逻辑接上主 agent。

核心类是 `ByteRoverMemoryProvider`。它的 `name` 属性返回 `byterover`，这也是用户配置 `memory.provider: byterover` 时使用的名字。`is_available()` 只检查本机是否能找到 `brv`，不做网络调用；这符合 memory provider 抽象中“可用性检查应轻量”的约定。

`get_config_schema()` 暴露配置项 `api_key`，并映射到环境变量 `BRV_API_KEY`。该字段是 secret，用于可选的 ByteRover 云同步；本地优先模式不强依赖它。

`get_tool_schemas()` 返回 `QUERY_SCHEMA`、`CURATE_SCHEMA`、`STATUS_SCHEMA` 三个工具定义。`handle_tool_call()` 根据工具名分派到 `_tool_query()`、`_tool_curate()`、`_tool_status()`，它们最终都通过 `_run_brv(...)` 调用外部 CLI，并返回 JSON 字符串或 `tool_error(...)`。

## 主流程位置

主流程可以按“加载、注入、检索、写入、压缩前保存、关闭”理解。

加载阶段，Hermes 的 memory 插件系统会扫描 `plugins/memory/<name>/`。根据 `plugins/memory/__init__.py` 的职责描述和搜索结果，目录是否像 memory provider 会通过 `register_memory_provider` 或 `MemoryProvider` 这类特征判断；当用户配置 `memory.provider` 为 `byterover` 时，会加载该目录并执行 `register(ctx)`。根据当前片段推断，`agent/agent_init.py` 负责在 agent 初始化期间读取配置并把选中的 provider 加入 `MemoryManager`，依据是搜索结果中该文件附近有“Reads memory.provider from config to select which plugin to activate”和“Inject memory provider tool schemas into the tool surface”的注释。

注入阶段，`agent/memory_manager.py` 的 `MemoryManager.add_provider()` 会登记 provider，并把 provider 返回的工具 schema 建立 `tool_name -> provider` 映射。这样 `brv_query`、`brv_curate`、`brv_status` 后续可以由 memory manager 路由回 ByteRover provider。

检索阶段，`prefetch(query, session_id=...)` 在每轮用户消息进入模型前运行。ByteRover 版本采用同步检索：如果 query 太短会直接返回空，否则执行 `brv query -- <query>`，超时为 `_QUERY_TIMEOUT`，并把足够长的输出包装为 `## ByteRover Context\n...`。`queue_prefetch()` 在这里是 no-op，因为当前实现选择 turn start 同步检索，而不是上一轮提前排队。

写入阶段，`sync_turn(user_content, assistant_content, ...)` 在对话轮完成后运行。它过滤过短用户输入，把用户和助手内容截断合并为一段文本，然后在后台线程中执行 `brv curate -- <combined>`。这里有一个顺序保护：如果上一轮同步线程还活着，会先最多等待 5 秒，避免多个 curate 写入过度重叠。

额外写入有两个入口。`on_memory_write(action, target, content)` 会把 Hermes 内置 memory 的 `add`、`replace` 操作镜像到 ByteRover。`on_pre_compress(messages)` 会在上下文压缩前取最后若干条 user/assistant 消息，后台执行 `brv curate`，把即将被压缩丢弃的上下文先保存起来。这个 hook 与 `plugin.yaml` 中的 `hooks: on_pre_compress` 对应。

关闭阶段，`shutdown()` 会等待活跃的 `_sync_thread` 最多 10 秒，尽量让后台写入收尾。

## 推荐阅读顺序

建议先读 `plugins/memory/byterover/README.md`，快速知道它依赖 `brv`、通过 `hermes memory setup` 启用、暴露哪些工具。

第二步读 `plugins/memory/byterover/plugin.yaml`，确认这个目录在插件系统里的身份：名字是 `byterover`，外部依赖是 `brv`，并声明了压缩前 hook。

第三步读 `plugins/memory/byterover/__init__.py` 的顶部注释、`_resolve_brv_path()`、`_run_brv()`、`_get_brv_cwd()`。这部分说明它不是直接调用 ByteRover SDK，而是通过 CLI 子进程工作，并且把数据放在 profile-scoped 的 Hermes home 下。

第四步读 `ByteRoverMemoryProvider` 的生命周期方法：`is_available()`、`initialize()`、`system_prompt_block()`、`prefetch()`、`sync_turn()`、`on_memory_write()`、`on_pre_compress()`。这能看清它如何嵌入 agent 的每轮对话。

第五步读工具相关方法：`get_tool_schemas()`、`handle_tool_call()`、`_tool_query()`、`_tool_curate()`、`_tool_status()`。这部分解释模型在对话中主动调用 ByteRover 的路径。

最后再回看邻近框架文件 `agent/memory_provider.py`、`agent/memory_manager.py`、`plugins/memory/__init__.py`。前者定义 provider 合同，中者负责编排和工具路由，后者负责发现与加载 memory provider。对于 overview 深度，不需要深入每个其他 provider 的实现。

## 常见误区

第一个误区是把它当作 `tools/` 下的核心工具。实际上 `brv_query` 等工具 schema 是由 `MemoryProvider.get_tool_schemas()` 提供的，路由也经过 `MemoryManager`，不是在 `tools.registry` 中注册的普通工具。

第二个误区是认为配置了 `BRV_API_KEY` 才能使用。当前实现和 README 都表明 ByteRover 是 local-first，`BRV_API_KEY` 是云同步相关的可选项；真正的硬依赖是本机可执行的 `brv` CLI。

第三个误区是忽略 `$HERMES_HOME/byterover/`。这个目录不是仓库内目录，而是运行时 profile-scoped 工作目录。不同 Hermes profile 理论上会有不同 ByteRover 上下文树。

第四个误区是以为 `prefetch()` 是后台异步。ByteRover 这个实现明确让 `prefetch()` 在 turn start 同步执行，最多等 `_QUERY_TIMEOUT`；`queue_prefetch()` 反而是 no-op。

第五个误区是认为每轮写入会阻塞主回复。`sync_turn()`、`on_memory_write()`、`on_pre_compress()` 的 curate 操作都走后台线程，主流程只在必要时短暂等待上一条同步线程或在 shutdown 时收尾。

第六个误区是把 `plugin.yaml` 的 hook 当成完整逻辑。真正的行为在 `__init__.py`，`plugin.yaml` 更像发现、展示和依赖声明；读主流程时应以 `ByteRoverMemoryProvider` 为中心。
