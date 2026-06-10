# 目录：plugins/memory/honcho

## 它负责什么

`plugins/memory/honcho` 是 Hermes 的 Honcho 记忆提供者插件目录，负责把 Hermes 的通用 `MemoryProvider` 接口接到 Honcho 后端上。它的核心职责不是普通会话存档，而是“AI-native memory”：跨会话的用户建模、peer card、语义检索、dialectic reasoning、持久结论写入，以及把当前对话 turn 同步到 Honcho。

从架构位置看，它属于 `plugins/memory/` 下的内置记忆 provider。上层的统一抽象在 `agent/memory_provider.py`，调度器在 `agent/memory_manager.py`；本目录实现 provider 本身，并提供 Honcho 专属配置解析、CLI 管理命令和会话管理。`MemoryManager` 会调用 provider 的 `initialize()`、`system_prompt_block()`、`prefetch()`、`queue_prefetch()`、`sync_turn()`、`get_tool_schemas()`、`handle_tool_call()`、`shutdown()` 等生命周期方法，而 Honcho 插件在这些钩子里决定是否自动注入上下文、是否暴露工具、什么时候写入远端、什么时候做后台预取。

这个插件支持三种 recall 模式：`hybrid`、`context`、`tools`。`hybrid` 同时自动注入上下文并暴露 Honcho 工具；`context` 只自动注入，不暴露工具；`tools` 不自动注入，首次工具调用时再懒初始化 session。它还专门处理 cron/flush 场景跳过、网关用户 ID 到 Honcho peer 的映射、不同 Hermes profile 对应不同 Honcho host block、长 session ID 截断加 hash、消息超长分块、后台异步写入、dialectic cadence 和 reasoning depth 等运行细节。

## 直接子目录地图

这个目录当前没有直接子目录，只有一组顶层文件。地图可以按角色理解：

`plugins/memory/honcho/__init__.py` 是插件主入口和 `HonchoMemoryProvider` 实现，集中定义工具 schema、MemoryProvider 生命周期、自动上下文注入、工具调用分发和 turn 同步。

`plugins/memory/honcho/client.py` 负责 Honcho 客户端与配置解析，包括 `HonchoClientConfig`、配置文件查找、profile host key、session 名称解析，以及 `get_honcho_client()` 单例创建。

`plugins/memory/honcho/session.py` 负责 Honcho session 层封装，包括 `HonchoSession`、`HonchoSessionManager`、peer/session 创建、消息缓存与 flush、上下文获取、搜索、conclusion、peer card、迁移旧记忆文件等。

`plugins/memory/honcho/cli.py` 提供 `hermes honcho ...` 子命令树，处理 setup、status、sessions、map、peer、mode、strategy、tokens、identity、migrate、enable、disable、sync 等管理动作。

`plugins/memory/honcho/plugin.yaml` 是插件元数据，声明插件名、版本、描述、标签和依赖。

`plugins/memory/honcho/README.md` 是使用与配置说明，适合作为行为语义的补充材料，但读代码时不要把它当作唯一事实来源。

## 关键入口

运行时最关键的入口是 `plugins/memory/honcho/__init__.py` 中的 `HonchoMemoryProvider`。它通过 `name` 返回 `honcho`，通过 `is_available()` 判断是否有可用配置，通过 `initialize()` 建立或延迟建立 Honcho session manager。

`initialize()` 是理解插件启动的第一站。它先检查 cron/flush 场景，随后通过 `HonchoClientConfig.from_global_config()` 读取配置。如果未启用或没有 `api_key`/`base_url`，插件静默不激活。激活后它读取 `recall_mode`、注入频率、context cadence、dialectic cadence、reasoning heuristic 等参数。若是 `tools` 模式且未配置 `initOnSessionStart`，则只保存懒初始化参数；否则进入 `_do_session_init()`。

`_do_session_init()` 是真正连接客户端和 session 的位置。它调用 `get_honcho_client()` 创建 Honcho SDK client，再创建 `HonchoSessionManager`，并用 `HonchoClientConfig.resolve_session_name()` 解析 Honcho session key。随后它会创建 session、尝试迁移旧的 memory 文件，并预热 context 与 dialectic 结果。

工具入口也在 `HonchoMemoryProvider` 内。`get_tool_schemas()` 根据 recall mode 决定是否暴露 `honcho_profile`、`honcho_search`、`honcho_reasoning`、`honcho_context`、`honcho_conclude`。`handle_tool_call()` 则把这些工具名分发到 `HonchoSessionManager` 的 peer card、search、dialectic query、session context、conclusion 创建/删除等方法上。

CLI 入口是 `plugins/memory/honcho/cli.py` 的 `register_cli(subparser)`，它构建 `hermes honcho` 下的 argparse 子命令。注意内存插件 CLI 只会为当前 active memory provider 注册，这一点由仓库级插件机制控制，不是在本目录里硬编码完成的。

## 主流程位置

配置解析主流程在 `client.py`。`resolve_config_path()` 按 `$HERMES_HOME/honcho.json`、默认 profile 的 `honcho.json`、全局 Honcho config 的顺序查找配置。`HonchoClientConfig.from_global_config()` 再按 host block、根配置、环境变量、默认值的优先级解析字段。这里会决定 `workspace_id`、`api_key`、`base_url`、`peer_name`、`ai_peer`、`write_frequency`、`context_tokens`、`recall_mode`、`observation`、`session_strategy` 等核心运行参数。

session 命名主流程也在 `client.py` 的 `resolve_session_name()`。优先级大致是：目录手动映射、Hermes session title、gateway session key、`per-session` 的 Hermes session id、`per-repo` 的 git repo 名、`per-directory` 的目录名、最后退回 workspace。网关场景优先使用 `gateway_session_key`，因为 cwd 策略不能区分不同平台用户或聊天室。

对话运行主流程横跨 `__init__.py` 和 `session.py`。每轮开始时 `on_turn_start()` 记录 turn number；生成前 `prefetch()` 读取 base context 和 dialectic supplement，必要时截断到 token 预算；生成后 `sync_turn()` 把 user/assistant 内容清洗、分块并写入 Honcho；下一轮前 `queue_prefetch()` 根据 cadence 后台刷新 context 和 dialectic。session 侧由 `HonchoSessionManager.save()`、`_flush_session()`、`flush_all()`、`shutdown()` 处理同步策略和收尾。

工具调用主流程集中在 `handle_tool_call()`。例如 `honcho_search` 走 `search_context()`，`honcho_reasoning` 走 `dialectic_query()`，`honcho_context` 走 `get_session_context()`，`honcho_profile` 读写 peer card，`honcho_conclude` 创建或删除 conclusion。工具模式下如果 session 尚未初始化，会先通过 `_ensure_session()` 懒加载。

## 推荐阅读顺序

建议先读 `plugin.yaml`，确认这是 memory provider 插件，而不是通用工具插件或模型 provider 插件。

第二步读 `__init__.py` 顶部的 tool schema 和 `HonchoMemoryProvider` 方法列表。先抓住五个工具、三种 recall mode、生命周期方法这三条主线，不要一开始陷进 dialectic depth 的细节。

第三步读 `client.py` 的 `HonchoClientConfig`、`from_global_config()`、`resolve_session_name()`、`get_honcho_client()`。这能解释为什么同一个插件在 CLI、profile、gateway、自托管 Honcho 场景下表现不同。

第四步读 `session.py` 的 `HonchoSessionManager.get_or_create()`、`_resolve_user_peer_id()`、`_flush_session()`、`dialectic_query()`、`get_session_context()`、`search_context()`、`create_conclusion()`。这些是 provider 调用 Honcho 后端的实际工作层。

最后读 `cli.py` 的 `register_cli()` 和相关 `cmd_*` 函数，用来理解运维入口如何改写 `honcho.json`，以及 profile clone/sync、peer 配置、mode/strategy/tokens 设置如何影响运行时。

## 常见误区

第一，不要把 `plugins/memory/honcho` 理解成普通聊天记录存储。它确实会保存消息，但更重要的是围绕 user peer、AI peer、session context、peer card、dialectic reasoning 构建长期记忆。

第二，不要以为只要存在 `HONCHO_API_KEY` 就一定完整启用。`HonchoClientConfig.from_global_config()` 会综合 host block、root config、环境变量和显式 `enabled` 字段；profile 也会影响 host key。排查时应看解析后的 config，而不是只看单个环境变量。

第三，`context`、`tools`、`hybrid` 的差异很大。`context` 模式不会暴露 Honcho 工具；`tools` 模式不会自动注入上下文，而且默认可能延迟到首次工具调用才初始化 session；`hybrid` 才是两者都有。

第四，网关用户身份和 Honcho peer 不是天然一一等同。`session.py` 会根据 `pinPeerName`/`pinUserPeer`、`userPeerAliases`、`runtimePeerPrefix` 和运行时 user id 解析最终 peer。多用户机器人如果错误 pin 到同一个 peer，可能造成记忆混用。

第五，session 名称不是简单等于 Hermes session id。默认策略可能按目录、repo、gateway key 或全局 workspace 归并。遇到“为什么不同会话共享记忆”或“为什么记忆没有共享”时，应优先检查 `sessionStrategy`、目录映射和 gateway session key。

第六，Honcho CLI 子命令不是无条件注册的全局核心命令。根据仓库约定，memory provider 的 CLI 只为当前 active provider 暴露；所以 fresh install 场景通常要走 `hermes memory setup honcho`，而不是假设 `hermes honcho setup` 总可用。
