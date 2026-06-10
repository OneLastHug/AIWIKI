# 文件：plugins/memory/hindsight/README.md

## 一句话定位

`plugins/memory/hindsight/README.md` 是 Hindsight memory provider 的使用与配置说明页，面向启用 Hermes 长期记忆插件的用户和维护者，解释 cloud、local embedded、local external 三种连接模式、配置项、暴露工具以及环境变量；它本身不参与运行时执行，但描述的契约会被 `plugins/memory/hindsight/__init__.py`、`plugins/memory/hindsight/plugin.yaml` 和 Hermes 的 memory plugin 框架消费。

## 它暴露/定义了什么

这个 README 暴露的是“插件配置契约”和“能力边界”，不是 Python API。核心定义包括：

- Hindsight memory provider 的定位：长期记忆、知识图谱、实体解析、多策略检索。
- 三种运行模式：`cloud`、`local_embedded`、`local_external`。
- 配置文件位置：`~/.hermes/hindsight/config.json`，对应实现中 `_load_config()` 优先读取 profile-scoped 配置。
- Memory bank 配置：`bank_id`、`bank_id_template`、`bank_mission`、`bank_retain_mission`。
- Recall 配置：`recall_budget`、`recall_prefetch_method`、`recall_max_tokens`、`recall_tags`、`recall_types` 等。
- Retain 配置：`auto_retain`、`retain_async`、`retain_every_n_turns`、`retain_context`、默认 tags/source 和 user/assistant 前缀。
- 集成模式：`memory_mode = hybrid/context/tools`。
- 暴露给 LLM 的三种 memory tool：`hindsight_retain`、`hindsight_recall`、`hindsight_reflect`。
- 环境变量入口：`HINDSIGHT_API_KEY`、`HINDSIGHT_LLM_API_KEY`、`HINDSIGHT_API_URL`、`HINDSIGHT_BANK_ID` 等。

README 中提到的 `hindsight-client >= 0.4.22` 与 `plugin.yaml` 的 `pip_dependencies`、实现里的 `_MIN_CLIENT_VERSION` 保持一致。

## 谁调用它

严格说，没有运行时代码“调用” README。它被人类使用，并作为插件行为的文档化来源。真正的调用链在代码里：

- Hermes memory 插件发现系统读取 `plugins/memory/hindsight/plugin.yaml` 和 `plugins/memory/hindsight/__init__.py`，通过 `register(ctx)` 注册 `HindsightMemoryProvider`。
- `agent/memory_manager.py` 管理所有 `MemoryProvider`，负责调用 provider 的 `initialize()`、`system_prompt_block()`、`prefetch()`、`queue_prefetch()`、`sync_turn()`、`get_tool_schemas()`、`handle_tool_call()`、`shutdown()`。
- `run_agent.py` 和相关 agent runtime helper 通过 `MemoryManager` 把记忆上下文注入 prompt、把回合内容写入长期记忆，并把 memory tool call 路由给 provider。
- `hermes memory setup` 流程会调用 provider 的 `post_setup()` 和 `get_config_schema()`，README 里的 setup/config 内容与这两个函数高度对应。

## 它调用谁

README 不调用任何模块；根据当前片段推断，它描述的能力由 `plugins/memory/hindsight/__init__.py` 调用以下外部或内部组件实现：

- `hindsight_client.Hindsight`：cloud 和 local external 模式下的 HTTP client。
- `hindsight.HindsightEmbedded` 与 `hindsight_embed.daemon_embed_manager`：local embedded 模式下启动和管理本地 daemon。
- `agent.memory_provider.MemoryProvider`：插件必须实现的抽象接口。
- `tools.registry.tool_error`：memory tool 出错时返回统一 JSON 错误。
- `hermes_constants.get_hermes_home()`：定位 profile-aware 的 Hermes home。
- `hermes_cli.config`、`hermes_cli.memory_setup`、`hermes_cli.secret_prompt`：setup wizard、配置保存和 secret 输入。
- `agent.async_utils.safe_schedule_threadsafe`：把异步 Hindsight client 调用调度到共享后台 event loop。

## 核心流程

启用流程从 `hermes memory setup` 开始。用户选择 `hindsight` 后，`post_setup()` 选择运行模式，安装或升级所需依赖，写入 Hermes 主配置的 `memory.provider = hindsight`，再把 Hindsight 专属配置保存到 `~/.hermes/hindsight/config.json`，secret 写入 `~/.hermes/.env`。local embedded 模式还会生成 Hindsight daemon 需要的 profile env 文件。

会话启动时，插件系统执行 `register(ctx)`，`ctx.register_memory_provider(HindsightMemoryProvider())` 把 provider 交给 `MemoryManager`。随后 `initialize(session_id, **kwargs)` 读取配置、解析 bank、memory mode、recall/retain 参数、平台和用户上下文；如果是 local embedded，则异步启动本地 daemon。

每轮对话中，`MemoryManager.queue_prefetch_all()` 先为下一轮排队检索，`prefetch_all()` 在下一次 prompt 组装时读取缓存结果并注入上下文。对话完成后，`sync_all()` 调用 `sync_turn()`，后者把 user/assistant 回合序列化，放入单 writer queue，由后台线程调用 Hindsight 的 `aretain_batch()` 写入长期记忆。

当 LLM 主动调用工具时，`MemoryManager.handle_tool_call()` 根据 tool name 路由到 `HindsightMemoryProvider.handle_tool_call()`，再分别执行 retain、recall 或 reflect。会话切换和退出时，`on_session_switch()`、`shutdown()` 负责 flush 缓冲、丢弃旧 prefetch、关闭 client，降低写错 session 或丢数据的风险。

## 关键函数的高层作用

`register(ctx)` 是插件入口，把 `HindsightMemoryProvider` 注册为 Hermes memory provider。

`HindsightMemoryProvider.initialize()` 是运行时配置装配中心，负责读取 Hindsight config/env、解析 `bank_id_template`、决定 `memory_mode`、设置 recall/retain 策略，并在 local embedded 模式下启动 daemon。

`post_setup()` 是交互式安装配置流程，负责模式选择、依赖安装、API key/LLM key 收集、配置和 env 文件落盘。

`get_config_schema()` 为通用 setup 体系提供字段定义，README 的 Config 表基本对应这里的 schema。

`system_prompt_block()` 根据 `memory_mode` 返回给模型看的静态说明，决定模型是否知道可用工具以及是否有自动上下文注入。

`queue_prefetch()` 和 `prefetch()` 组成自动 recall 流程：前者后台调用 `arecall()` 或 `areflect()`，后者把上一次结果包装成 prompt context。

`sync_turn()` 是自动 retain 核心，把完成的对话回合按配置节奏写入队列，并由单 writer 线程串行写入 Hindsight，避免并发写和解释器退出时的 aiohttp 资源问题。

`handle_tool_call()` 是三种工具的分发器：`hindsight_retain` 写入记忆，`hindsight_recall` 搜索结果，`hindsight_reflect` 跨记忆合成答案。

`on_session_switch()` 和 `shutdown()` 是生命周期保护函数，处理 session 轮转、缓冲 flush、prefetch 清理和 client 关闭。

辅助函数如 `_load_config()`、`_normalize_retain_tags()`、`_resolve_bank_id_template()`、`_check_api_supports_update_mode_append()` 主要做配置兼容、输入规整和 API 能力探测。

## 修改风险

最大风险是 README 与实现脱节。这里的配置项会被用户直接写入 `~/.hermes/hindsight/config.json`，如果文档新增字段但 `initialize()` 或 `get_config_schema()` 不支持，会形成静默无效配置；反过来，代码默认值变更但 README 未更新，会让用户误判行为。

`recall_types` 风险较高。README 强调默认只返回 `observation`，实现中 `initialize()` 和 `handle_tool_call()` 也共用该设置。如果修改默认值，会同时影响自动上下文注入和 `hindsight_recall` 工具，可能显著增加 token 消耗或改变模型记忆质量。

`memory_mode` 的文档必须与 `get_tool_schemas()`、`system_prompt_block()` 保持一致。`context` 模式不暴露工具，`tools` 模式不自动注入，`hybrid` 两者都有；写错会导致用户以为某些 tool 可用但实际不可用。

local embedded 相关说明涉及依赖、daemon、日志路径和 LLM key。实现会启动后台 daemon、写 profile env，并在连接失败时重建 client；文档若简化过度，排障会变困难。

最后，README 中的外部地址、命令和环境变量容易受到产品侧变更影响。维护时应同步检查 `plugin.yaml`、`HindsightMemoryProvider.get_config_schema()`、`post_setup()` 和 `_load_config()`，不要只改文档表格。
