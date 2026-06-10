# 文件：plugins/memory/retaindb/README.md

## 一句话定位

`plugins/memory/retaindb/README.md` 是 RetainDB 记忆插件的用户入口说明页，用来告诉使用者如何启用 `retaindb` 作为 Hermes 的外部 memory provider、需要哪些环境变量，以及启用后模型会获得哪些 RetainDB 相关工具；它不是执行逻辑本体，真正的 provider、HTTP 客户端、异步写入队列和工具分发都在 `plugins/memory/retaindb/__init__.py`。

## 它暴露/定义了什么

README 暴露的是配置和能力契约。它定义 RetainDB 是一个云端记忆后端，提供混合检索能力，依赖 RetainDB 账号和 `requests` 包。配置入口有两类：通过 `hermes memory setup` 选择 `retaindb`，或手动设置 `memory.provider retaindb` 并在 `.env` 写入 `RETAINDB_API_KEY`。环境变量包括 `RETAINDB_API_KEY`、`RETAINDB_BASE_URL`、`RETAINDB_PROJECT`；文档里出现的真实服务地址在这里不展开，按外部地址理解即可。

工具表列出 `retaindb_profile`、`retaindb_search`、`retaindb_context`、`retaindb_remember`、`retaindb_forget`。根据当前实现片段推断，README 已落后于实现：`plugins/memory/retaindb/__init__.py` 还定义了文件存储相关工具，如 `retaindb_upload_file`、`retaindb_list_files`、`retaindb_read_file`、`retaindb_ingest_file`、`retaindb_delete_file`。

## 谁调用它

README 本身不会被运行时代码调用，主要被人类使用者、文档站或插件浏览流程阅读。运行时真正被调用的是同目录的插件模块：插件发现系统加载 `plugins/memory/retaindb/__init__.py`，其 `register(ctx)` 调用 `ctx.register_memory_provider(RetainDBMemoryProvider())`，再由 `MemoryManager` 纳入 agent 的统一 memory 生命周期。

配置层面，`hermes memory setup` 对应 `hermes_cli/memory_setup.py`，它会枚举 memory provider 插件、安装 `plugin.yaml` 中声明的依赖，并把 `memory.provider` 写入配置。agent 启动后，如果配置选中了 `retaindb` 且 `RETAINDB_API_KEY` 存在，`RetainDBMemoryProvider.is_available()` 才会允许该 provider 生效。

## 它调用谁

README 不调用任何代码。它描述的行为映射到实现后，主要调用链是：`RetainDBMemoryProvider` 调用内部 `_Client`，`_Client` 再通过 `requests` 访问 RetainDB API；异步写入由 `_WriteQueue` 使用 SQLite 持久化待写入回合，再由后台线程调用 `_Client.ingest_session()`；工具调用则由 `MemoryManager.handle_tool_call()` 路由到 `RetainDBMemoryProvider.handle_tool_call()`，最后进入 `_dispatch()` 分派到搜索、记忆写入、删除、文件操作等具体 API。

它还间接依赖 `agent.memory_provider.MemoryProvider` 的抽象接口、`agent.memory_manager.MemoryManager` 的生命周期编排、`tools.registry.tool_error` 的错误包装，以及 `hermes_constants.get_hermes_home()` 提供 profile-aware 的本地路径。

## 核心流程

第一步是配置启用。用户按照 README 执行 `hermes memory setup` 或手动配置 `memory.provider` 与 `RETAINDB_API_KEY`。启动 agent 时，memory 插件被发现并注册，`MemoryManager.add_provider()` 为 provider 建立工具名到 provider 的映射；系统限制一次只能启用一个外部 memory provider，避免多个后端同时暴露工具造成 schema 膨胀和语义冲突。

第二步是初始化。`RetainDBMemoryProvider.initialize()` 读取 API key、base URL、project，创建 `_Client`，并在 Hermes home 下创建 `retaindb_queue.db` 作为写后队列。若存在 `SOUL.md`，它会后台调用 RetainDB 的 agent identity seed 接口，把代理身份信息写入云端记忆。

第三步是每轮对话。`agent/conversation_loop.py` 在回合开始调用 `MemoryManager.prefetch_all()`，把 provider 返回的上下文包进 `<memory-context>` 后注入当前用户消息；回合结束时调用外部记忆同步逻辑，将用户输入和最终回答交给 `sync_turn()`，同时 `queue_prefetch()` 为下一轮提前拉取上下文、用户综合画像和 agent self-model。

第四步是工具调用。当模型选择 `retaindb_search` 等工具时，`MemoryManager` 根据工具名路由到 `RetainDBMemoryProvider.handle_tool_call()`，再由 `_dispatch()` 调用 `_Client` 的对应 API 方法。

## 关键函数的高层作用

README 没有函数定义；下面是其描述内容对应的核心实现函数。

`register(ctx)` 是插件入口，把 `RetainDBMemoryProvider` 注册到 Hermes memory 插件系统。

`RetainDBMemoryProvider.is_available()` 只检查 `RETAINDB_API_KEY`，用于决定 provider 是否可用，不应做网络请求。

`initialize()` 建立 RetainDB 客户端、解析 project、创建 SQLite 写入队列，并触发可选的 `SOUL.md` 身份种子写入。

`system_prompt_block()` 返回静态系统提示，告诉模型 RetainDB memory 已启用以及可用工具。

`prefetch()` 消费上一轮 `queue_prefetch()` 准备好的上下文缓存，返回可注入模型的记忆块；`queue_prefetch()` 则启动后台线程并发准备 context、dialectic synthesis、agent self-model。

`sync_turn()` 把完整用户/助手回合写入 `_WriteQueue`，避免主对话被云端写入延迟阻塞。

`get_tool_schemas()` 暴露 RetainDB 工具 schema；`handle_tool_call()` 和 `_dispatch()` 负责工具名分派、参数校验和 JSON 结果返回。

`_Client` 是 RetainDB API 的薄封装；`_WriteQueue` 是崩溃可恢复的本地异步写入缓冲；`_build_overlay()` 负责把 profile 和检索结果去重后整理成模型可读上下文。

## 修改风险

最大风险是 README 与实现不一致。当前 README 只列出 5 个工具，但实现已经暴露 10 个工具；如果用户依赖 README 了解能力，会漏掉文件存储相关功能。反过来，如果 README 宣称某个工具存在而 `get_tool_schemas()` 未暴露，模型就无法真正调用。

配置风险集中在环境变量命名和密钥处理。`RETAINDB_API_KEY` 是必需项，若 README 改成配置文件字段但实现仍只读环境变量，会导致 setup 成功但运行时不可用。外部服务地址、账号价格、安装方式都属于容易变化的信息，文档更新时应避免写死不可验证细节。

生命周期风险来自异步队列和预取机制。README 如果把 `sync_turn()` 描述成同步持久化，会误导使用者对数据落库时机的判断；实际写入是 SQLite-backed write-behind，崩溃后会重放，但仍依赖后台线程和 shutdown 刷新。修改实现时要注意 `conversation_loop` 假定 `prefetch()` 足够快，真正的慢请求应放在 `queue_prefetch()` 后台完成。

工具风险在于 schema 名称一旦改变，会影响 `MemoryManager` 的工具路由、模型提示、已有用户工作流和历史文档。删除或重命名 `retaindb_remember`、`retaindb_search` 这类入口属于破坏性变更；新增工具则应同步 README、`plugin.yaml` 描述和测试覆盖。
