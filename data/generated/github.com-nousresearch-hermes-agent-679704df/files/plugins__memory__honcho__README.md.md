# 文件：plugins/memory/honcho/README.md

## 一句话定位

`plugins/memory/honcho/README.md` 是 Honcho memory provider 的设计与运维说明页，面向开发者解释 Hermes 如何把 Honcho 接入为外部长期记忆后端，包括配置解析、上下文注入、工具暴露、会话/身份映射和成本控制策略。它不是运行时代码，但它描述的契约直接对应 `plugins/memory/honcho/__init__.py`、`plugins/memory/honcho/client.py`、`plugins/memory/honcho/session.py`、`plugins/memory/honcho/cli.py` 的实现。

## 它暴露/定义了什么

该 README 主要定义 Honcho 插件的行为约定：安装依赖 `honcho-ai`，通过 `hermes memory setup honcho` 或手工设置 `memory.provider: honcho` 激活；读取 `honcho.json` 与 `HONCHO_API_KEY`；在 `recallMode` 为 `context`、`tools`、`hybrid` 时分别决定是否自动注入上下文和是否暴露工具。

文档还定义五个模型可见工具：`honcho_profile`、`honcho_search`、`honcho_context`、`honcho_reasoning`、`honcho_conclude`。这些 schema 在 `plugins/memory/honcho/__init__.py` 中以 `PROFILE_SCHEMA`、`SEARCH_SCHEMA`、`CONTEXT_SCHEMA`、`REASONING_SCHEMA`、`CONCLUDE_SCHEMA` 落地，并由 `ALL_TOOL_SCHEMAS` 汇总。

此外，它定义了 Honcho 的核心配置面：身份与连接、gateway 多用户身份映射、记忆召回、写入频率、session 命名策略、多 profile 共享 workspace 的方式，以及与外部 Honcho 文档相关的入口；真实网址在此处记为 `[URL已移除]`。

## 谁调用它

README 本身不会被程序调用。根据当前片段推断，它的“读者型调用方”是维护者、插件使用者和排障人员，依据是文件内容包含安装、配置、架构和完整配置表。

运行时真正被调用的是同目录 provider。`agent/agent_init.py` 从配置 `memory.provider` 读取 provider 名称，通过 `plugins.memory.load_memory_provider("honcho")` 加载 `HonchoMemoryProvider`，再交给 `MemoryManager` 管理。`agent/conversation_loop.py` 在每轮对话开始调用 `MemoryManager.on_turn_start()` 和 `prefetch_all()`，在回合结束调用外部记忆同步逻辑，间接触发 Honcho 的 `sync_turn()` 与 `queue_prefetch()`。CLI 侧，`hermes_cli/memory_setup.py` 和 `plugins/memory/honcho/cli.py` 支撑 `hermes memory setup honcho`、`hermes honcho setup/status/...` 等配置入口。

## 它调用谁

作为 Markdown 文档，README 不调用任何代码。其描述对应的实现调用链如下：`HonchoMemoryProvider` 调用 `plugins/memory/honcho/client.py` 中的 `HonchoClientConfig.from_global_config()` 和 `get_honcho_client()` 读取配置并创建 Honcho SDK client；调用 `plugins/memory/honcho/session.py` 中的 `HonchoSessionManager` 创建或获取 session、读取 context、执行 dialectic query、写入 conclusion、迁移本地记忆文件。

它还依赖 `agent.memory_manager.sanitize_context()` 清理注入过的 `<memory-context>`，避免把记忆块再次写回后端；依赖 `tools.registry.tool_error()` 生成工具错误 JSON；配置写入使用 `utils.atomic_json_write()`；profile 路径通过 `hermes_constants.get_hermes_home()` 获得。

## 核心流程

核心流程可以理解为“配置选择 provider -> 初始化 Honcho session -> 每轮召回 -> 注入或暴露工具 -> 回合后写入”。启动时，Hermes 读取 `config.yaml` 的 `memory.provider`，若为 `honcho`，加载 `HonchoMemoryProvider` 并检查 `is_available()`。初始化阶段读取 `honcho.json`、环境变量和 host block，解析 workspace、peer、AI peer、session strategy、recall mode、cadence 等设置。

对话开始时，`on_turn_start()` 记录当前 turn，用于节流。随后 `prefetch()` 按 README 描述拼两层上下文：第一层是 session summary、user representation、peer card、AI representation、AI card；第二层是 dialectic `.chat()` 得到的补充推理。最终内容由 `MemoryManager.build_memory_context_block()` 包装进 `<memory-context>`，作为用户消息前置背景，而不是写入 system prompt，从而保留 prompt cache。

回合结束后，`sync_turn()` 清理记忆上下文标记，按长度切块后把 user/assistant 消息写入 Honcho session；`queue_prefetch()` 根据 `contextCadence` 和 `dialecticCadence` 异步准备下一轮上下文。工具模式下，模型可以显式调用五个 `honcho_*` 工具，由 `MemoryManager.handle_tool_call()` 路由给 provider。

## 关键函数的高层作用

`HonchoMemoryProvider.initialize()` 负责总入口：跳过 cron/flush 场景，读取配置，确定 `recallMode`，并根据 tools-only 或 context/hybrid 选择懒初始化或立即建 session。

`_do_session_init()` 负责真正连接 Honcho、创建 `HonchoSessionManager`、解析 session key、迁移旧的 `MEMORY.md`/`USER.md`/`SOUL.md` 类文件，并启动 context/dialectic 预热。

`system_prompt_block()` 只返回静态说明，告诉模型当前 Honcho 模式和可用工具；动态记忆不放这里。

`prefetch()` 是自动召回主流程，合并 base context 与 dialectic supplement，并调用 `_truncate_to_budget()` 控制 token 预算。

`queue_prefetch()` 是下一轮预取调度器，按 cadence、空结果退避和线程存活状态控制成本与并发。

`_run_dialectic_depth()` 实现 README 中的多 pass dialectic：冷启动/暖会话选择不同 prompt，按 `dialecticDepth` 和 reasoning level 执行，信号足够时提前退出。

`sync_turn()` 把完成的对话写入 Honcho；`handle_tool_call()` 根据工具名执行 profile/search/context/reasoning/conclude。辅助函数如 `_is_trivial_prompt()`、`_chunk_message()`、`_empty_profile_hint()` 分别处理无意义输入过滤、长消息切块和空 profile 的诊断提示。

## 修改风险

最大风险是 README 与实现漂移。该文件是关键文档页，若新增、改名或删除 `honcho_*` 工具，必须同步 `ALL_TOOL_SCHEMAS` 和 README 的工具表，否则模型使用者会误判可用能力。`recallMode`、`contextCadence`、`dialecticCadence`、`dialecticDepth` 的语义也要谨慎修改，因为它们影响成本、延迟和上下文注入频率。

身份映射是高风险区域。`pinUserPeer`、`userPeerAliases`、`runtimePeerPrefix` 决定 gateway 多用户记忆是否混到同一 peer；文档若表达不清，可能导致不同用户共享记忆或已有个人记忆断档。session 策略同样敏感，`per-session`、`per-repo`、`per-directory`、gateway session key 会影响记忆归档粒度。

上下文注入也有安全风险。README 强调 `<memory-context>` 是背景数据而不是新用户输入；实现依赖 sanitizer 防止上下文泄漏和重复持久化。修改相关说明或实现时，需要确认 `sanitize_context()`、streaming scrubber、`build_memory_context_block()` 的契约仍一致。

最后，README 中配置路径、命令和外部服务说明涉及用户操作。改动前应对照 `plugins/memory/honcho/cli.py`、`plugins/memory/honcho/client.py` 与 `hermes_cli/memory_setup.py`，避免写出已经不存在的命令、字段或默认值。
