# 文件：plugins/memory/holographic/README.md

## 一句话定位

`plugins/memory/holographic/README.md` 是 Holographic memory provider 的使用说明入口，用很短的篇幅说明这个 memory 插件的能力、启用方式、配置项和对模型暴露的工具。它不是运行时代码，但对理解 `plugins/memory/holographic/__init__.py`、`store.py`、`retrieval.py` 这组实现的职责边界很关键：该插件把 Hermes 的长期记忆扩展为本地 SQLite fact store，并支持 FTS5 搜索、信任分、实体关系和 HRR 组合检索。

## 它暴露/定义了什么

README 暴露的是面向用户和维护者的插件契约，而不是 Python API。它定义了四类信息：

第一，插件能力：本地 SQLite fact store、FTS5 search、trust scoring、entity resolution，以及基于 HRR 的 compositional retrieval。这里的 HRR 指向 `plugins/memory/holographic/holographic.py` 提供的向量代数能力；NumPy 可选，缺失时会退化到关键词检索。

第二，安装与启用方式：通过 `hermes memory setup` 选择 `holographic`，或手动设置 `memory.provider holographic`。这对应 Hermes memory provider 的插件发现和激活流程，而不是在 README 中直接注册。

第三，配置命名空间：README 写明配置位于 `config.yaml` 的 `plugins.hermes-memory-store` 下，包含 `db_path`、`auto_extract`、`default_trust`、`hrr_dim`。实际实现中 `__init__.py` 的 `_load_plugin_config()` 也读取同一命名空间，并额外支持 `min_trust_threshold`、`temporal_decay_half_life`、`hrr_weight` 等内部配置。

第四，对模型暴露的工具：`fact_store` 和 `fact_feedback`。`fact_store` 覆盖 add、search、probe、related、reason、contradict、update、remove、list 九类动作；`fact_feedback` 用于把某条事实标为 helpful 或 unhelpful，从而调整 trust score。

## 谁调用它

严格说，README 不被运行时代码调用；它由开发者、用户、文档系统或代码审阅者阅读。运行时真正被调用的是同目录的 `register(ctx)` 和 `HolographicMemoryProvider`。

根据当前片段推断，调用链大致是：Hermes 根据 `memory.provider: holographic` 发现 `plugins/memory/holographic` 插件，加载 `__init__.py`，调用 `register(ctx)`，再通过 `ctx.register_memory_provider(provider)` 把 `HolographicMemoryProvider` 注册给 `agent.memory_manager.MemoryManager`。依据是 `agent/memory_provider.py` 明确说明 memory providers 通过 `plugins/memory/<name>/` 和 `memory.provider` 激活；`__init__.py` 末尾也提供了 `register(ctx)`。

之后，`MemoryManager` 是主要调用方。它会调用 provider 的 `initialize()`、`system_prompt_block()`、`prefetch()`、`sync_turn()`、`get_tool_schemas()`、`handle_tool_call()`、`on_session_end()`、`on_memory_write()`、`shutdown()` 等生命周期方法，并负责把工具名路由到对应 provider。

## 它调用谁

README 本身不调用任何模块。其描述对应的实现调用关系如下：

`HolographicMemoryProvider` 调用 `MemoryStore` 负责本地 SQLite 存储、建表、FTS5 表、触发器、实体抽取、事实增删改查、信任分更新和 HRR 向量保存。

`HolographicMemoryProvider` 调用 `FactRetriever` 负责检索层逻辑，包括关键词搜索、实体 probe、related 查询、多实体 reason、contradict 检测，以及基于 trust score、Jaccard、FTS5 rank、HRR similarity 和可选时间衰减的排序。

`MemoryStore` 和 `FactRetriever` 调用 `plugins/memory/holographic/holographic.py` 中的 HRR 工具函数。若 NumPy 不可用，检索器会重新分配权重或回退到关键词搜索。

配置读取侧调用 `hermes_constants.get_hermes_home()`、`display_hermes_home()` 和 `hermes_cli.config.cfg_get()`，保证路径跟随当前 Hermes profile，而不是硬编码 `~/.hermes`。

错误输出通过 `tools.registry.tool_error()` 统一包装为工具调用可消费的 JSON 字符串。

## 核心流程

启用阶段：用户按 README 设置 `memory.provider holographic`。插件系统加载 `plugins/memory/holographic/__init__.py`，执行 `register(ctx)`，创建 `HolographicMemoryProvider` 并注册到 memory provider 体系。

初始化阶段：`MemoryManager` 调用 `initialize(session_id, **kwargs)`。provider 读取 `plugins.hermes-memory-store` 配置，解析 `$HERMES_HOME`，创建 `MemoryStore` 和 `FactRetriever`。`MemoryStore` 打开 SQLite，启用 WAL fallback，创建 `facts`、`entities`、`fact_entities`、`facts_fts`、`memory_banks` 等结构，并建立 FTS5 同步触发器。

提示词阶段：`system_prompt_block()` 根据 fact 数量返回一段系统提示，告诉模型 holographic memory 已启用、是否为空，以及应该用 `fact_store` 查询或写入事实。

回忆阶段：每轮用户输入前，`prefetch(query)` 通过 `FactRetriever.search()` 查找相关事实，按信任分过滤后注入为 `## Holographic Memory` 上下文。`MemoryManager` 会把多个 provider 的上下文合并，并通过 memory context fence 注入主对话。

工具阶段：模型调用 `fact_store` 或 `fact_feedback` 时，`MemoryManager.handle_tool_call()` 根据工具名找到 provider，再交给 `HolographicMemoryProvider.handle_tool_call()`。具体动作由 `_handle_fact_store()` 或 `_handle_fact_feedback()` 分派。

写入阶段：`fact_store(action="add")` 调用 `MemoryStore.add_fact()`，插入事实、抽取实体、建立 fact-entity 关联、计算 HRR 向量并重建 memory bank。内置 memory 工具写入时，`on_memory_write()` 也会把 add 动作镜像成 fact。

结束阶段：如果 `auto_extract` 为 true，`on_session_end()` 会扫描用户消息，用少量正则抽取偏好和项目决策，写入 `user_pref` 或 `project` 类别。这个机制偏保守，不是完整信息抽取器。

## 关键函数的高层作用

`register(ctx)` 是插件入口，把 `HolographicMemoryProvider` 注册进 Hermes memory provider 系统。

`HolographicMemoryProvider.initialize()` 连接配置、数据库和检索器，是插件从“已注册”进入“可服务”的关键步骤。

`get_tool_schemas()` 返回 README 中提到的 `fact_store`、`fact_feedback` schema，决定模型能看到哪些 memory 工具。

`handle_tool_call()` 是工具总入口，只做工具名分流；真正行为在 `_handle_fact_store()` 和 `_handle_fact_feedback()`。

`_handle_fact_store()` 是主要业务分发器，把 add/search/probe/related/reason/contradict/update/remove/list 映射到 `MemoryStore` 或 `FactRetriever`。

`prefetch()` 是对话前召回入口，把用户 query 转成简短 memory context；它影响模型回答，但不直接修改事实库。

`on_memory_write()` 用于和 Hermes 内置 memory 工具联动，把普通 memory add 镜像到 holographic fact store。

`_auto_extract_facts()` 是会话结束时的可选抽取逻辑，只基于正则模式识别偏好和项目决策，能力有限但风险也相对可控。

`MemoryStore.add_fact()` 是持久化核心，负责去重、实体抽取、关系写入、HRR 向量生成和类别 bank 重建。

`FactRetriever.search()` 是混合检索核心，把 FTS5 候选、Jaccard、HRR similarity、trust score 和可选 temporal decay 合成最终排序。

`FactRetriever.probe()`、`related()`、`reason()` 是 HRR 组合检索入口；NumPy 不可用时会退回普通搜索。

## 修改风险

最大风险是 README 与实现漂移。README 当前只列出四个配置项，但实现还读取 `min_trust_threshold`、`temporal_decay_half_life`、`hrr_weight`；如果后续新增或删除配置，不同步 README 会让用户误配。

工具 schema 风险较高。`fact_store` 的 action 枚举直接决定模型可调用能力；改名、删 action、改必填参数都会影响已有 prompt、测试和用户习惯。尤其是 `reason` 需要 `entities`，`add` 需要 `content`，`search` 需要 `query`，这些约束主要在运行时捕获，schema 描述不充分时模型容易发错参数。

数据库结构风险也高。`store.py` 创建 FTS5 表、触发器、实体关联表和 HRR BLOB 字段；修改 schema、trigger 或唯一约束可能破坏既有 `memory_store.db`。迁移必须兼容旧库，并考虑 profile-scoped `$HERMES_HOME`。

检索排序改动会改变用户可感知行为。`FactRetriever.search()` 的权重、trust threshold、时间衰减和 NumPy fallback 都会影响哪些记忆被注入上下文；过度召回会污染回答，过度过滤会让长期记忆“失效”。

`auto_extract` 风险在于误写长期事实。它基于简单英文正则，可能把临时表达或上下文片段持久化。默认值是 false，修改默认值前需要非常谨慎。

最后，Holographic provider 是 external memory provider。`MemoryManager` 限制同一时间只有一个外部 provider，工具名也会建立全局路由。新增工具或改名时，要避免与 built-in memory 或其他 provider 发生 schema 名称冲突。
