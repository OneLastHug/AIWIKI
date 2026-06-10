# 目录：plugins/memory/openviking

## 它负责什么

`plugins/memory/openviking` 是 Hermes 的一个内置 memory provider 插件，用来把对话记忆接入 OpenViking context database。它不是普通工具目录，而是挂在 Hermes 记忆系统下的 provider：通过 `MemoryProvider` 接口参与会话初始化、上下文预取、回合写入、会话结束提交、显式记忆写入镜像，以及向模型暴露一组 `viking_*` 工具。

从代码结构看，这个插件的定位是“会话托管式长期记忆”。它会把用户和 assistant 的对话回合同步到 OpenViking session，并在 session 结束时调用 commit，让 OpenViking 侧执行自动记忆抽取。代码注释提到抽取类别包括 profile、preferences、entities、events、cases、patterns。与此同时，它也支持知识库浏览和检索：OpenViking 的知识组织方式被抽象成类似文件系统的 `viking://` URI 层级，插件提供搜索、读取、浏览、写入事实、导入资源等能力。

这个目录的实现有两个层次：一层是 Hermes memory provider 生命周期，核心类是 `OpenVikingMemoryProvider`；另一层是 OpenViking REST API 的轻量封装，核心类是 `_VikingClient`。插件没有依赖 OpenViking SDK，而是通过 `httpx` 直接请求服务端接口。配置主要来自环境变量，例如 `OPENVIKING_ENDPOINT`、`OPENVIKING_API_KEY`、`OPENVIKING_ACCOUNT`、`OPENVIKING_USER`、`OPENVIKING_AGENT`。

## 直接子目录地图

这个目标目录当前没有直接子目录，只有三个顶层文件：

`plugins/memory/openviking/__init__.py` 是全部主要实现所在，包含 HTTP client、tool schema、路径/资源辅助函数、`OpenVikingMemoryProvider` 类和插件注册函数。

`plugins/memory/openviking/plugin.yaml` 是插件元信息，声明名称 `openviking`、版本、描述、`pip_dependencies`、`requires_env` 和 hooks。它告诉插件系统这是一个需要 `httpx`、依赖 `OPENVIKING_ENDPOINT` 的 memory 插件。

`plugins/memory/openviking/README.md` 是使用说明，简要描述依赖、配置方式和提供的工具列表。它面向使用者，不是运行时入口。

因为目录很小，阅读时不需要按子目录分层展开；真正的“地图”应围绕 `__init__.py` 内部的几个代码区域理解：HTTP 封装、工具 schema、辅助函数、provider 生命周期、工具实现、注册函数。

## 关键入口

最外层入口是 `register(ctx)`，位于 `plugins/memory/openviking/__init__.py` 末尾。它调用 `ctx.register_memory_provider(OpenVikingMemoryProvider())`，把 OpenViking 注册为 Hermes 的记忆 provider。根据仓库的 memory 插件约定，插件发现系统加载该模块后，会通过这个函数把 provider 交给 memory 管理层。

运行时核心入口是 `OpenVikingMemoryProvider`。它继承 `agent.memory_provider.MemoryProvider`，实现了 Hermes 记忆系统期望的一组方法：

`name` 返回 provider 名称 `openviking`，用于配置项 `memory.provider` 匹配。

`is_available()` 判断是否配置了 `OPENVIKING_ENDPOINT`。它不做网络探测，只检查环境。

`get_config_schema()` 描述 setup 过程中需要收集或写入的配置，包括 endpoint、api_key、account、user、agent。

`initialize(session_id, **kwargs)` 是每个会话启动时的关键入口。它读取环境变量，创建 `_VikingClient`，调用 `health()` 做服务可达性检查，并记录当前 session id。

`system_prompt_block()` 在知识库存在内容时生成一段 system prompt，提示模型可以使用 `viking_search`、`viking_read`、`viking_browse`、`viking_remember`、`viking_add_resource`。

`queue_prefetch()` 与 `prefetch()` 负责上下文预取。前者在后台线程中搜索 OpenViking，后者在下一轮取回结果并包装成 `## OpenViking Context`。

`sync_turn()` 把每轮 user/assistant 消息写入 OpenViking session。它使用后台线程，避免阻塞主对话流程。

`on_session_end()` 在会话结束时提交 session，触发 OpenViking 的自动记忆抽取。

`on_memory_write()` 监听 Hermes 内置 memory 写入，并把新增内容镜像写到 OpenViking 的 `viking://user/.../memories/...` 路径下。

`get_tool_schemas()` 和 `handle_tool_call()` 是工具暴露入口。前者返回全部 `viking_*` schema，后者按工具名分发到内部 `_tool_*` 方法。

## 主流程位置

主流程可以按“注册、初始化、对话中、会话结束、工具调用”五段理解。

注册阶段发生在 `register(ctx)`。插件被发现后，`OpenVikingMemoryProvider()` 被加入 Hermes 的 memory provider 管理体系。相邻上下文里，`agent/memory_manager.py` 的 `MemoryManager.add_provider()`、`initialize_all()`、`prefetch_all()`、`queue_prefetch_all()`、`sync_all()`、`on_session_end()`、`handle_tool_call()` 等方法负责统一调度 provider。也就是说，OpenViking 自己不控制 agent loop，而是被 `MemoryManager` 在合适时机调用。

初始化阶段发生在 `OpenVikingMemoryProvider.initialize()`。它读取配置，构造 `_VikingClient`，再通过 `_VikingClient.health()` 检查服务。如果缺少 `httpx` 或服务不可达，会把 `_client` 置空，后续工具调用会返回 “OpenViking server not connected” 一类错误。

对话中有两条并行路径。第一条是 recall：`queue_prefetch(query)` 在后台调用 `/api/v1/search/find`，提取 memories 和 resources 的摘要，存入 `_prefetch_result`；下一轮 `prefetch(query)` 把结果交给 `MemoryManager.prefetch_all()`，再被注入上下文。第二条是 write：`sync_turn(user_content, assistant_content, session_id=...)` 把当前回合的 user 和 assistant 消息写入 session messages。它会等待上一条 sync 线程有限时间完成，再启动新的后台写入线程。

会话结束阶段在 `on_session_end(messages)`。该方法先等待 pending sync，然后检查 `_turn_count`，有实际回合才调用 session commit。文件顶部还注册了 `_atexit_commit_sessions()`，作为进程退出时的兜底提交机制；根据当前片段推断，这是为了 gateway 崩溃或正常 shutdown 未触发时尽量不丢失 session commit，依据是代码注释明确称其为 process-level atexit safety net。

工具调用主流程集中在 `handle_tool_call()`，它识别五个工具：`viking_search`、`viking_read`、`viking_browse`、`viking_remember`、`viking_add_resource`。实际实现分别在 `_tool_search()`、`_tool_read()`、`_tool_browse()`、`_tool_remember()`、`_tool_add_resource()`。这些方法再通过 `_VikingClient.get()`、`_VikingClient.post()`、`upload_temp_file()` 请求 OpenViking API。辅助函数如 `_zip_directory()`、`_path_from_file_uri()`、`_is_remote_resource_source()` 用于处理本地文件、目录压缩、远程资源和 URI 归一化。

## 推荐阅读顺序

先读 `plugins/memory/openviking/plugin.yaml`，确认这个插件的身份、依赖和环境变量要求。这里能快速知道它是 memory provider，而不是普通 Hermes tool。

第二步读 `plugins/memory/openviking/README.md`，建立使用层面的概念：需要 OpenViking server、通过 `hermes memory setup` 选择 provider，并提供五个 `viking_*` 工具。

第三步读 `plugins/memory/openviking/__init__.py` 顶部注释、常量和 `_VikingClient`。这部分解释了插件依赖的 OpenViking 能力、默认配置来源、认证 header、HTTP 响应解析和健康检查。

第四步跳到 `OpenVikingMemoryProvider` 类，从 `initialize()`、`system_prompt_block()`、`queue_prefetch()`、`prefetch()`、`sync_turn()`、`on_session_end()` 连起来看。这是理解记忆生命周期的主线。

第五步看 `get_tool_schemas()`、`handle_tool_call()` 和各个 `_tool_*` 方法。此时再回头看 schema 区域，会更容易理解工具参数为什么这样设计，例如读取层级、搜索模式、资源导入和显式记忆分类。

最后再看相邻的 `agent/memory_provider.py` 和 `agent/memory_manager.py`。前者定义 provider 接口，后者说明 Hermes 何时调用这些接口。对 overview 深度来说，不需要逐行展开 manager，只要知道 OpenViking 是被 `MemoryManager` 调度即可。

## 常见误区

第一个误区是把 `plugins/memory/openviking` 当作普通工具插件。它确实暴露 `viking_search` 等工具，但工具不是通过 `tools/registry.py` 的普通核心工具路径注册，而是由 `MemoryProvider.get_tool_schemas()` 交给 memory manager，再由 memory manager 统一接入工具调用。

第二个误区是以为 `is_available()` 会验证 OpenViking 服务可用。实际上它只检查 `OPENVIKING_ENDPOINT` 是否存在；真正的网络健康检查在 `initialize()` 创建 `_VikingClient` 后执行。配置存在但服务不可达时，provider 可能被注册，但 `_client` 会为空，工具调用和上下文能力不会正常工作。

第三个误区是以为每次 `sync_turn()` 都立刻完成长期记忆抽取。代码显示 `sync_turn()` 只是把回合消息写入 session；自动抽取发生在 `on_session_end()` 的 commit 之后。也就是说，对话中写 session 和会话结束提交是两个阶段。

第四个误区是忽略后台线程。`queue_prefetch()`、`sync_turn()`、`on_memory_write()` 都使用 daemon thread 或异步式后台写入。阅读问题时要注意 `_prefetch_lock`、`_prefetch_thread`、`_sync_thread` 的状态，否则容易误判上下文何时可见、消息何时真正写入。

第五个误区是把 `viking://` 当成本地文件路径。这里的 `viking://` 是 OpenViking 知识库 URI。`viking_read`、`viking_browse` 操作的是 OpenViking 的层级资源；只有 `viking_add_resource` 处理本地路径或远程资源，并在需要时先临时上传或压缩目录。

第六个误区是只看 README 而忽略 `get_config_schema()`。README 只列出最基本配置，而代码实际还支持 account、user、agent 等多租户相关环境变量。这些值会进入 `_VikingClient` header，并影响写入 URI 和 OpenViking 侧的用户隔离。
