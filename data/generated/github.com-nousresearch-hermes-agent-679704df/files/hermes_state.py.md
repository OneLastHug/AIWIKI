# 文件：hermes_state.py

## 一句话定位

`hermes_state.py` 是 Hermes Agent 的 SQLite 会话状态层，核心职责是把 CLI、TUI、gateway、多平台消息会话的元数据、消息历史、检索索引、压缩链路、标题、计费统计和少量平台状态统一持久化到 `state.db`。

## 它暴露/定义了什么

这个文件主要定义三类内容。

第一类是数据库常量与 schema：`DEFAULT_DB_PATH`、`SCHEMA_VERSION`、`SCHEMA_SQL`、`FTS_SQL`、`FTS_TRIGRAM_SQL`。其中 `sessions` 保存会话元数据，`messages` 保存逐条消息，`state_meta` 保存通用 key/value 状态，`compression_locks` 保存压缩并发锁。FTS5 表 `messages_fts` 和 `messages_fts_trigram` 用于全文检索，后者重点解决 CJK/子串搜索。

第二类是跨库辅助函数：`apply_wal_with_fallback()`、`format_session_db_unavailable()`、`get_last_init_error()`。这些不只服务 `SessionDB`，也被 `hermes_cli/kanban_db.py`、部分 memory plugin 复用，用来在 WAL 不可用的文件系统上降级到 `DELETE` journal mode，并把初始化失败原因传给上层命令。

第三类是核心类 `SessionDB`。它是本文件的主 API，提供会话创建/结束/重开、消息追加/替换/读取、会话列表、标题管理、FTS 搜索、压缩链处理、清理导出、Telegram topic-mode 状态、handoff 状态等能力。

## 谁调用它

主要调用方是 Hermes 的会话运行入口和用户界面层。

`run_agent.py` 在 agent 运行和 recall 场景里懒加载 `SessionDB`，并通过会话数据库保存或恢复对话。`cli.py` 在交互式 CLI 中初始化 `_session_db`，处理 `/resume`、`/title`、`/history`、`/branch`、`/status` 等命令时大量读取和更新会话。`tui_gateway/server.py` 在 TUI 后端中用于会话恢复、标题、分支和压缩后续会话处理。`hermes_cli/web_server.py` 为 dashboard 的会话列表、搜索、详情接口创建 `SessionDB` 实例。`mcp_serve.py` 用它读取 transcript 并轮询新消息。`hermes_cli/main.py` 的若干子命令也直接打开 `SessionDB` 查询或操作会话。

外围模块也依赖它的“状态库”属性：`hermes_cli/goals.py` 使用 `state_meta` 保存 goals 状态；`agent/insights.py` 基于 `SessionDB` 扫描历史；`plugins/hermes-achievements` 读取会话统计；`hermes_cli/kanban_db.py`、`plugins/memory/holographic/store.py` 复用 `apply_wal_with_fallback()`。

## 它调用谁

底层主要调用 Python 标准库 `sqlite3`、`threading`、`time`、`json`、`re`、`random` 和 `pathlib.Path`。路径来源通过 `hermes_constants.get_hermes_home()` 解析，因此 `state.db` 是 profile-aware 的，不是硬编码到用户主目录。

唯一显式业务依赖是 `agent.memory_manager.sanitize_context`，用于 `get_messages_as_conversation()` 回放 user/assistant 文本时清理上下文。除此之外，它基本不反向调用 agent 或 UI 层，设计上是一个低层存储服务。

## 核心流程

初始化流程从 `SessionDB.__init__()` 开始：确定 `db_path`，创建父目录，打开 SQLite 连接，设置 `row_factory`，调用 `apply_wal_with_fallback()` 尝试开启 WAL，启用 foreign keys，然后进入 `_init_schema()`。如果初始化失败，会记录 `_last_init_error`，让 `/resume` 等命令能输出具体原因。

schema 初始化流程由 `_init_schema()` 驱动：先执行 `SCHEMA_SQL` 创建核心表和索引，再用 `_reconcile_columns()` 对比当前库和声明式 schema，自动补齐新增列。随后探测 FTS5 能力；如果不可用，删除 FTS triggers，保证普通消息写入不被虚拟表失败拖垮；如果可用，则创建或修复 FTS 表、triggers，并执行必要的数据迁移与重建。

写入流程统一走 `_execute_write()`：使用 Python 锁包裹连接访问，显式 `BEGIN IMMEDIATE` 获取写锁，执行调用方传入的 SQL 函数，成功后 commit，失败 rollback。遇到 `database is locked` 或 busy 时，会带随机抖动重试，降低多个 Hermes 进程共享 `state.db` 时的写锁拥塞。每成功写入一定次数后尝试 passive WAL checkpoint。

会话保存流程通常是：上层先 `create_session()` 或 `ensure_session()` 写入 `sessions`，运行过程中 `append_message()` 写入 `messages` 并更新计数，模型调用后 `update_token_counts()` 累加 token、费用和 billing 信息，结束时 `end_session()` 标记结束原因。压缩场景会通过 `parent_session_id` 形成父子链，并用 `get_compression_tip()`、`resolve_resume_session_id()` 把用户恢复目标指向实际有消息的 continuation session。

搜索流程由 `search_messages()` 负责：普通文本走 `messages_fts MATCH`，CJK 或短 token 会按情况切换到 trigram FTS 或 `LIKE` 回退；结果会附带 session 元信息、snippet 和前后文。`search_sessions()`、`list_sessions_rich()` 则负责会话级列表，后者还能把压缩 root 投影到最新 tip，让用户看到“逻辑上的同一段会话”。

## 关键函数的高层作用

`apply_wal_with_fallback()` 是跨数据库的 journal mode 保护层。它优先启用 WAL；如果文件系统不支持 WAL 锁协议，则降级到 `DELETE`，牺牲并发换取可用性。

`_init_schema()` 是 schema 中枢。它把声明式建表、列补齐、FTS 兼容、版本迁移和索引修复集中在启动阶段处理，是修改表结构时最需要理解的地方。

`_execute_write()` 是所有写事务的安全入口。新增写方法时应复用它，否则容易绕过锁、重试、rollback 和 checkpoint 策略。

`create_session()`、`ensure_session()`、`end_session()`、`reopen_session()` 管理会话生命周期；`update_token_counts()` 管理 token、费用、模型和 API 调用计数，是 `/status`、dashboard、历史统计的基础数据来源。

`append_message()` 和 `replace_messages()` 是 transcript 写入核心。它们负责 JSON 序列化 `tool_calls`、reasoning 字段、Codex items、multimodal content，并维护 `message_count`、`tool_call_count`。

`get_messages_as_conversation()` 把数据库行恢复成 OpenAI 风格消息列表，是恢复上下文时的关键路径；它还会按需包含 ancestor lineage，并避免压缩链回放时重复用户消息。

`search_messages()` 是消息全文检索入口，承担 FTS5 查询清洗、CJK 搜索分流、source/role 过滤、排序和上下文拼接。`_sanitize_fts5_query()`、`_contains_cjk()` 等是它的辅助函数。

`list_sessions_rich()` 是高级会话列表 API，负责 preview、last_active、子会话隐藏、压缩链 tip 投影和按最近活动排序。相比 `search_sessions()`，它更面向用户界面。

`try_acquire_compression_lock()`、`release_compression_lock()` 用 SQLite 行锁语义防止多个 agent 对同一个 session 同时压缩，避免一个 parent 分裂出多个 orphan continuation。

`apply_telegram_topic_migration()` 及相关 `enable_telegram_topic_mode()`、`bind_telegram_topic()` 等方法是平台专用扩展。注意它们刻意不在普通 `SessionDB()` 启动时创建 topic-mode 表，而是在 `/topic` opt-in 后显式迁移。

## 修改风险

最大风险是 schema 兼容性。`SCHEMA_SQL` 是列定义的事实来源，新增列通常只需加到这里，但涉及数据回填、虚拟表重建、外键变更、索引语义变化时，必须通过版本迁移或显式迁移处理，不能只改 CREATE TABLE。

第二个风险是并发写入。这个库被 CLI、gateway、TUI、dashboard、插件和后台任务同时使用，绕过 `_execute_write()`、扩大事务范围、在锁内执行慢逻辑，都会导致 UI 卡顿或 `database is locked` 放大。

第三个风险是 FTS5 降级路径。某些 Python/SQLite 构建缺 FTS5，代码当前保证“搜索失效但会话保存继续”。修改 triggers、虚拟表或搜索逻辑时，要确保 FTS5 不可用时 `append_message()` 仍然能写入。

第四个风险是压缩链语义。`parent_session_id` 同时表示压缩 continuation、branch、delegate/subagent 等关系，`get_compression_tip()`、`list_sessions_rich()` 和 `resolve_resume_session_id()` 依赖 `end_reason`、`started_at >= ended_at`、消息存在性来区分它们。随意改变结束原因或父子关系判断，会影响 `/resume`、历史列表和压缩后的可见性。

第五个风险是平台耦合逐渐进入存储层。Telegram topic-mode、handoff、platform message id 已经存在于本文件；继续加入平台字段时要注意不要让普通 `SessionDB()` 启动产生不必要的迁移副作用，尤其是 gateway 多平台共用同一状态库的场景。
