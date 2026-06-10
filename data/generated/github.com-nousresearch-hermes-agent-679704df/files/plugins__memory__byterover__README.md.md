# 文件：plugins/memory/byterover/README.md

## 一句话定位

`plugins/memory/byterover/README.md` 是 ByteRover 外部记忆提供器的使用说明页，用极短篇幅说明它依赖 `brv` CLI、如何通过 `hermes memory setup` 或 `memory.provider=byterover` 启用，以及启用后向模型暴露的 `brv_query`、`brv_curate`、`brv_status` 三个记忆工具。

## 它暴露/定义了什么

这个 README 本身不暴露 Python API，也不会被运行时直接 import；它定义的是面向用户和维护者的配置契约：安装 ByteRover CLI、选择 `byterover` 作为 `memory.provider`、可选设置 `BRV_API_KEY` 做云同步、工作目录使用 `$HERMES_HOME/byterover/`。它还列出插件的工具面：`brv_query` 用于查询知识树，`brv_curate` 用于写入事实/决策/模式，`brv_status` 用于检查 CLI、树状态和同步状态。

与 README 对应的真实实现位于 `plugins/memory/byterover/__init__.py`，核心类是 `ByteRoverMemoryProvider`，它实现 `agent.memory_provider.MemoryProvider` 抽象，并通过 `register(ctx)` 调用 `ctx.register_memory_provider(ByteRoverMemoryProvider())` 注册到记忆插件系统。

## 谁调用它

严格说，README 不被代码调用；它被开发者、用户、`hermes memory setup/status` 的使用场景间接参考。运行时真正调用的是同目录的 `__init__.py`。根据当前片段推断，启用路径是：配置中的 `memory.provider` 设为 `byterover` 后，`agent/agent_init.py` 通过 `plugins.memory.load_memory_provider()` 加载 provider，创建 `MemoryManager`，再把 provider 加入 `MemoryManager.add_provider()`。

会继续调用该 provider 的主要入口包括：`agent/conversation_loop.py` 在每轮开始调用 `prefetch_all()` 拉取上下文，在每轮结束调用 `sync_all()` 与 `queue_prefetch_all()`；`agent/tool_executor.py` 和 `agent/agent_runtime_helpers.py` 在模型调用 `brv_*` 工具时通过 `MemoryManager.handle_tool_call()` 转发；`agent/conversation_compression.py` 在压缩前调用 `on_pre_compress()`。

## 它调用谁

README 描述的外部依赖是 `brv` CLI。实现中 `_resolve_brv_path()` 会查找 `brv` 可执行文件，先查 `PATH`，再查若干常见安装位置；`_run_brv()` 统一封装 `subprocess.run()`，以 `$HERMES_HOME/byterover/` 为工作目录执行 `brv query`、`brv curate`、`brv status`。内部框架依赖包括 `MemoryProvider` 抽象、`MemoryManager` 调度层、`tools.registry.tool_error()` 错误包装，以及 `hermes_constants.get_hermes_home()` 提供 profile-aware 的状态目录。

## 核心流程

启用阶段：用户按 README 安装 `brv`，再通过 `hermes memory setup` 选择 `byterover`，或手动写入 `memory.provider byterover`。插件发现系统扫描 `plugins/memory/byterover/`，加载 `register(ctx)`，取得 `ByteRoverMemoryProvider` 实例。

初始化阶段：`MemoryManager.add_provider()` 注册 provider，并读取 `get_tool_schemas()` 建立工具名到 provider 的路由表。`ByteRoverMemoryProvider.initialize()` 创建 `$HERMES_HOME/byterover/`，记录当前 `session_id`。

对话前置召回：每轮用户输入进入模型前，`prefetch()` 过滤过短 query，然后同步执行 `brv query -- <query>`，把足够长的结果包装成 `## ByteRover Context` 注入记忆上下文。

模型工具调用：模型看到 `brv_query`、`brv_curate`、`brv_status` 后可主动调用。`MemoryManager.handle_tool_call()` 按工具名路由到 `ByteRoverMemoryProvider.handle_tool_call()`，后者分派到具体 `_tool_*` 方法。

对话后写入：`sync_turn()` 把用户和助手内容合并，后台线程执行 `brv curate`。内置 memory 写入也会经 `on_memory_write()` 镜像到 ByteRover。上下文压缩前，`on_pre_compress()` 会把最近若干 user/assistant 消息异步 curate，避免压缩丢失重要内容。

## 关键函数的高层作用

`_resolve_brv_path()` 负责定位并缓存 `brv` CLI 路径，是可用性判断和所有命令执行的前置条件。

`_run_brv()` 是所有 ByteRover CLI 交互的统一出口，负责创建工作目录、设置环境变量、处理超时、返回 `{success, output, error}` 结构。

`ByteRoverMemoryProvider.is_available()` 只检查本地 CLI 是否存在，不做网络调用，符合 `MemoryProvider` 的初始化约束。

`initialize()` 绑定本次会话并准备 profile 级工作目录。

`system_prompt_block()` 向系统提示说明 ByteRover 已启用，并提示模型使用 `brv_query`、`brv_curate`、`brv_status`。

`prefetch()` 是自动召回入口，直接影响每轮模型调用前能否获得历史知识。

`sync_turn()` 是自动写入入口，以后台线程保存完整问答片段，避免阻塞主对话。

`on_memory_write()` 将内置记忆工具的 add/replace 操作同步镜像到 ByteRover。

`on_pre_compress()` 在上下文压缩前异步保存即将被压缩的最近消息。

`get_tool_schemas()` 与 `handle_tool_call()` 构成模型工具暴露和分发边界。

## 修改风险

最大风险是 README 与实现不一致。比如 README 中工具名、环境变量、工作目录或启用命令一旦写错，用户会配置成功但运行期无法调用正确工具。第二类风险是外部 CLI 依赖：`brv` 的命令参数、输出格式、安装路径或超时特征变化，会影响 `_run_brv()`、`prefetch()` 和三个工具方法；README 如果继续承诺旧行为，会误导排障。

修改工具表时要同步检查 `QUERY_SCHEMA`、`CURATE_SCHEMA`、`STATUS_SCHEMA` 和 `handle_tool_call()`，否则模型可见工具与实际路由可能脱节。修改配置说明时要注意 Hermes 的 memory provider 是单外部 provider 模式，`MemoryManager` 会拒绝第二个外部 provider；README 不应暗示 ByteRover 可与其他外部记忆后端并行启用。修改安装说明时还要避免泄露真实外部地址，文档展示可用 `[URL已移除]` 代替。
