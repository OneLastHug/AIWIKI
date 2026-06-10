# 目录：plugins/memory/retaindb

## 它负责什么

`plugins/memory/retaindb` 是 Hermes 的一个内置 memory provider 插件目录，作用是把 Hermes 的长期记忆能力接到 RetainDB 云端记忆服务上。它不是一个通用工具目录，也不是本地向量库实现，而是一个实现 `agent.memory_provider.MemoryProvider` 接口的外部记忆后端：负责读取用户长期画像、检索历史记忆、为当前任务合成上下文、异步写入每轮对话，并暴露一组 `retaindb_*` 工具给 agent 调用。

从实现看，这个插件覆盖三类能力。第一类是记忆读写，包括 `retaindb_profile`、`retaindb_search`、`retaindb_context`、`retaindb_remember`、`retaindb_forget`。第二类是会话生命周期集成，包括 `initialize()`、`queue_prefetch()`、`prefetch()`、`sync_turn()`、`shutdown()` 等 MemoryProvider 钩子。第三类是共享文件存储工具，包括上传、列出、读取、摄取和删除 RetainDB 文件，入口分别是 `retaindb_upload_file`、`retaindb_list_files`、`retaindb_read_file`、`retaindb_ingest_file`、`retaindb_delete_file`。

这个目录的设计重点是“外部云端记忆 + Hermes provider 生命周期”。它把 RetainDB API 包成一个私有 `_Client`，再由 `RetainDBMemoryProvider` 对接 Hermes 的 memory manager。写入路径还加了 SQLite-backed write-behind queue：对话轮次不会同步阻塞在远端 ingest 上，而是先写入本地队列数据库，再由后台线程慢慢提交，失败后保留 pending row 以便后续重试。

## 直接子目录地图

该目录当前没有直接子目录，只有三个顶层文件：

`plugins/memory/retaindb/__init__.py` 是核心实现文件，包含工具 schema、HTTP client、SQLite 写队列、上下文 overlay 格式化函数、`RetainDBMemoryProvider` 主类，以及插件注册函数 `register(ctx)`。

`plugins/memory/retaindb/plugin.yaml` 是插件元数据，声明插件名 `retaindb`、版本、描述、依赖 `requests`，以及必需环境变量 `RETAINDB_API_KEY`。它用于插件发现、依赖提示和配置检查。

`plugins/memory/retaindb/README.md` 是面向使用者的简短说明，讲如何启用 `memory.provider retaindb`、需要哪些环境变量，以及主要工具列表。文档里出现的外部服务地址在这里不展开，按要求记为 `[URL已移除]`。

## 关键入口

最关键的入口是 `plugins/memory/retaindb/__init__.py` 末尾的 `register(ctx)`。Hermes 插件系统加载该目录后，会调用这个函数；函数内部执行 `ctx.register_memory_provider(RetainDBMemoryProvider())`，把 provider 实例注册进全局 memory manager。也就是说，插件被发现是一回事，真正进入 memory 生命周期的是 `RetainDBMemoryProvider` 这个类实例。

`RetainDBMemoryProvider.name` 返回固定名称 `retaindb`，这与配置项 `memory.provider: retaindb` 对应。`is_available()` 通过 `RETAINDB_API_KEY` 判断是否可用。`get_config_schema()` 描述 setup 需要采集的配置，包括 API key、base URL 和 project，其中真实默认服务地址不在本文展开，记为 `[URL已移除]`。

`initialize(session_id, **kwargs)` 是运行期初始化入口。它读取环境变量，解析 project，创建 `_Client`，设置当前 `session_id`、`user_id`、`agent_id`，并在 Hermes home 下创建 `retaindb_queue.db` 作为异步写入队列。它还会根据当前 profile 的 `SOUL.md` 在后台调用 `_seed_soul()`，把 agent 身份或指令信息同步到 RetainDB 的 agent model 中。

工具入口集中在 `get_tool_schemas()` 和 `handle_tool_call()`。前者把所有 `retaindb_*` schema 暴露给 Hermes；后者收到工具调用后交给 `_dispatch()`，再由 `_Client` 发起对应 HTTP 请求。工具错误统一通过 `tools.registry.tool_error` 包装。

## 主流程位置

读取流程主要分两条。显式工具调用路径是：agent 选择 `retaindb_search`、`retaindb_context` 等工具，Hermes memory manager 识别这是 memory provider 工具，然后调用 `RetainDBMemoryProvider.handle_tool_call()`，最终进入 `_dispatch()`。例如 `retaindb_context` 会调用 `_Client.query_context()` 和 `_Client.get_profile()`，再通过 `_build_overlay()` 去重并拼成 `[RetainDB Context]` 文本块。

隐式上下文预取路径是 provider 生命周期的一部分。`queue_prefetch(query)` 会在后台启动三个线程：`_prefetch_context()` 查询任务相关上下文和 profile，`_prefetch_dialectic()` 请求用户理解 synthesis，`_prefetch_agent_model()` 读取 agent self-model。下一轮开始时，`prefetch(query)` 消费这些缓存，把它们合并为注入模型上下文的文本。根据当前片段推断，调度这些 provider 生命周期方法的位置在 `agent/memory_manager.py` 的 `MemoryManager.prefetch_all()`、`queue_prefetch_all()`、`initialize_all()` 一类方法中，因为这些方法统一遍历已注册的 `MemoryProvider`。

写入流程由 `sync_turn()` 和 `_WriteQueue` 组成。每轮对话结束后，`sync_turn(user_content, assistant_content, session_id=...)` 把 user/assistant 消息包装成带 timestamp 的列表，调用 `_WriteQueue.enqueue()` 先落地到 SQLite 表 `pending`，再把 row 放入内存队列。后台线程 `_WriteQueue._loop()` 取出任务并调用 `_Client.ingest_session()`；成功后删除 pending row，失败时记录 `last_error` 并稍后重试。这个设计避免 RetainDB 网络波动直接拖慢主对话循环。

文件流程也在 `_dispatch()` 内。上传工具读取本地文件、推断 MIME、调用 `_Client.upload_file()`；如果参数 `ingest` 为真，会紧接着调用 `_Client.ingest_file()`。读取工具会先拿 metadata，再下载 content；对文本文件返回最多 32000 字符，对二进制文件只返回提示，让 agent 使用 ingest 工具提取成可搜索记忆。

## 推荐阅读顺序

建议先读 `plugin.yaml`，确认这个目录在插件系统中的身份：名称、依赖和必需环境变量。然后读 `README.md`，建立使用层面的心智模型：它通过 `memory.provider retaindb` 启用，并提供一批 `retaindb_*` 工具。

接着进入 `__init__.py`，先看顶部 docstring 和 schema 常量，理解它对外暴露哪些能力。之后看 `_Client`，这是所有远端 API 的集中封装，能快速知道 profile、search、context、memory、file 各自对应什么操作。再看 `_WriteQueue`，这是理解“异步且可恢复写入”的关键。最后读 `RetainDBMemoryProvider`，按 `initialize()`、`system_prompt_block()`、`queue_prefetch()`、`prefetch()`、`sync_turn()`、`get_tool_schemas()`、`handle_tool_call()`、`shutdown()` 的顺序看，就能把 Hermes 生命周期和 RetainDB API 串起来。

如果需要理解它如何被上层调用，再跳到 `agent/memory_provider.py` 看抽象接口，到 `agent/memory_manager.py` 看 provider 集合如何统一初始化、预取、同步、分发工具调用和关闭。这里不需要先读整个插件系统；对 overview 深度来说，知道 `register(ctx)` 注册 provider 已足够。

## 常见误区

第一个误区是把 `retaindb` 当成普通 Hermes tool 插件。它的核心身份是 memory provider，工具只是 provider 暴露出来的一部分能力；注册入口不是 `registry.register()`，而是 `ctx.register_memory_provider(...)`。

第二个误区是以为所有记忆写入都是同步完成的。`sync_turn()` 只是把本轮对话放进 SQLite-backed 队列，真正调用远端 ingest 的是后台 writer 线程。看到短时间内远端没有立即出现新记忆时，应先考虑异步队列、失败重试和网络状态。

第三个误区是忽略 `RETAINDB_PROJECT` 的解析逻辑。若没有显式设置 project，`initialize()` 会根据 Hermes home/profile 推导 `hermes-<profile>`，否则回退到 `default`。因此不同 profile 可能天然分到不同 RetainDB project。

第四个误区是混淆 `retaindb_context` 工具和生命周期里的 `prefetch()`。前者是 agent 显式调用的工具，会即时查询并返回 context；后者是 memory manager 在对话轮次之间预取并在下一轮注入的隐式上下文，两者都可能调用 context/profile 相关 API，但触发时机不同。

第五个误区是只看 README 的工具表。README 当前只列了核心 memory 工具，而 `__init__.py` 还实现了文件存储相关工具。判断实际能力应以 `get_tool_schemas()` 返回的 schema 列表为准。
