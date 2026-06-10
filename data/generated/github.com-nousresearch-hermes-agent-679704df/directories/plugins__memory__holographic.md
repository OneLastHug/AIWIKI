# 目录：plugins/memory/holographic

## 它负责什么

`plugins/memory/holographic` 是 Hermes 的一个 memory provider 插件， provider 名称是 `holographic`。它把长期记忆实现为本地 SQLite 事实库：事实以 `facts` 表保存，支持 FTS5 全文搜索、实体抽取与关联、信任分数、反馈调权，并在安装了 `numpy` 时启用 HRR（Holographic Reduced Representations）向量代数检索。

它不是普通聊天历史存档，也不是默认会把每轮对话都写入数据库的记忆层。`sync_turn()` 明确为空，说明常规回合不会自动同步；事实主要通过工具 `fact_store` 显式写入，或在配置 `auto_extract` 开启时由 `on_session_end()` 从用户消息中用规则抽取偏好、项目决策类事实。它也会通过 `on_memory_write()` 镜像内置 memory 的 `add` 写入，把用户偏好或一般内容同步成结构化 fact。

从定位上看，它偏“深层事实记忆”：适合保存用户偏好、项目约定、工具使用习惯、实体关系和可能需要组合查询的信息。它暴露的两个工具是 `fact_store` 和 `fact_feedback`，前者负责添加、搜索、实体探测、关联发现、多实体推理、矛盾检测、更新、删除、列表浏览；后者负责把已使用事实标记为 helpful 或 unhelpful，从而调整 trust score。

## 直接子目录地图

这个目录当前没有直接子目录，所有实现都放在同一级文件中：

`plugins/memory/holographic/plugin.yaml` 是插件元数据，声明名称 `holographic`、版本、描述和 `on_session_end` hook。

`plugins/memory/holographic/__init__.py` 是插件入口和 MemoryProvider 适配层，定义工具 schema、配置读取、`HolographicMemoryProvider`，并通过 `register(ctx)` 注册 provider。

`plugins/memory/holographic/store.py` 是 SQLite 存储层，负责建表、FTS5、实体解析、事实 CRUD、信任分数、HRR 向量写入和分类 memory bank 重建。

`plugins/memory/holographic/retrieval.py` 是检索层，封装 `FactRetriever`，把 FTS5、Jaccard、trust score、时间衰减和 HRR 相似度组合起来。

`plugins/memory/holographic/holographic.py` 是 HRR 数学工具层，提供 atom 编码、bind、unbind、bundle、similarity、fact/text 编码和向量序列化。

`plugins/memory/holographic/README.md` 是简短使用说明，覆盖 setup、配置项和工具列表。

## 关键入口

最重要的入口是 `plugins/memory/holographic/__init__.py` 里的 `register(ctx)`。插件系统发现该插件后，会调用它创建 `HolographicMemoryProvider(config=config)`，再执行 `ctx.register_memory_provider(provider)`。根据当前片段推断，Hermes 的 memory provider 发现机制会通过这个注册点把 `holographic` 加入可选 memory provider 列表，依据是该类继承 `agent.memory_provider.MemoryProvider`，并实现了 `name`、`initialize()`、`prefetch()`、`get_tool_schemas()`、`handle_tool_call()` 等 provider 接口。

`HolographicMemoryProvider.name` 返回固定值 `"holographic"`，这就是配置 `memory.provider: holographic` 对应的 provider 名。注意插件私有配置不在 `memory.holographic` 下，而是在 `plugins.hermes-memory-store` 下读取和保存，这一点由 `_load_plugin_config()`、`save_config()` 和 README 共同体现。

`initialize(session_id, **kwargs)` 是运行期初始化入口。它解析 `$HERMES_HOME`、默认数据库路径 `memory_store.db`、`default_trust`、`hrr_dim`、`hrr_weight`、`temporal_decay_half_life`，然后构造 `MemoryStore` 和 `FactRetriever`。后续工具调用、预取、自动抽取都依赖这两个对象。

`get_tool_schemas()` 和 `handle_tool_call()` 是工具入口。`get_tool_schemas()` 暴露 `FACT_STORE_SCHEMA`、`FACT_FEEDBACK_SCHEMA`；`handle_tool_call()` 根据工具名分派到 `_handle_fact_store()` 或 `_handle_fact_feedback()`。其中 `_handle_fact_store()` 再按 `action` 分支调用 `store` 或 `retriever`。

## 主流程位置

写入主流程在 `plugins/memory/holographic/__init__.py` 的 `_handle_fact_store(action="add")` 和 `plugins/memory/holographic/store.py` 的 `MemoryStore.add_fact()`。调用 `fact_store` 添加事实后，provider 把 `content`、`category`、`tags` 传给 store。store 先去重插入 `facts`，再通过 `_extract_entities()` 用正则抽取实体，通过 `_resolve_entity()`、`_link_fact_entity()` 写入 `entities` 和 `fact_entities`。如果 HRR 可用，`_compute_hrr_vector()` 会把内容和实体编码为向量写回 `facts.hrr_vector`，随后 `_rebuild_bank(category)` 重建该分类的 `memory_banks` 聚合向量。

搜索主流程在 `plugins/memory/holographic/retrieval.py` 的 `FactRetriever.search()`。它先调用 `_fts_candidates()` 从 SQLite FTS5 取候选，再用 `_tokenize()` 和 `_jaccard_similarity()` 计算词重合度；若 fact 有 HRR 向量且 `numpy` 可用，会额外计算 query 与 fact vector 的相似度。最终分数由 FTS、Jaccard、HRR 加权合成，再乘以 `trust_score`，可选再乘时间衰减。

实体和组合推理主流程也在 `retrieval.py`。`probe(entity)` 偏向查“关于某实体的事实”，`related(entity)` 偏向查“与实体有结构关联的事实”，`reason(entities)` 对多个实体做 AND 语义的结构匹配，`contradict()` 找共享实体但内容向量差异较大的事实对。没有 `numpy` 时，`probe`、`related`、`reason` 会退化为关键词搜索或空结果，说明 HRR 是增强能力，不是基本可用性的硬依赖。

反馈主流程在 `_handle_fact_feedback()` 和 `MemoryStore.record_feedback()`。helpful 会把 trust 增加 `0.05` 并增加 `helpful_count`，unhelpful 会把 trust 降低 `0.10`，分数被限制在 `0.0` 到 `1.0`。

会话结束自动抽取在 `HolographicMemoryProvider.on_session_end()` 和 `_auto_extract_facts()`。只有 `auto_extract` 为真时才运行；它扫描用户消息，用偏好模式和项目决策模式匹配文本，然后分别写入 `user_pref` 或 `project` 分类。

## 推荐阅读顺序

1. 先读 `plugins/memory/holographic/README.md` 和 `plugin.yaml`，建立 provider 名称、启用方式、配置位置和工具能力的直觉。
2. 再读 `plugins/memory/holographic/__init__.py`，重点看 `HolographicMemoryProvider` 的生命周期方法：`initialize()`、`system_prompt_block()`、`prefetch()`、`get_tool_schemas()`、`handle_tool_call()`、`on_session_end()`、`on_memory_write()`。
3. 接着读 `plugins/memory/holographic/store.py`，理解 SQLite schema：`facts`、`entities`、`fact_entities`、`facts_fts`、`memory_banks`。这里决定了事实、实体、全文索引和 HRR bank 的持久化形态。
4. 然后读 `plugins/memory/holographic/retrieval.py`，把 `search`、`probe`、`related`、`reason`、`contradict` 的差异分清楚。
5. 最后读 `plugins/memory/holographic/holographic.py`。这部分是底层数学工具，不影响理解插件如何接入 Hermes，但有助于理解 HRR 为什么能做结构化组合检索。

## 常见误区

不要把 `holographic` 理解成自动记录全部对话的记忆系统。当前实现里 `sync_turn()` 是空操作，主要写入路径是 `fact_store(action="add")`、内置 memory 写入镜像，以及可选的 `auto_extract` 会话结束抽取。

不要以为没有 `numpy` 插件就不可用。SQLite、FTS5、CRUD、trust score 仍可工作；只是 HRR 相关的结构化向量能力会降级，部分操作会退回关键词搜索，`contradict()` 在无 HRR 时直接返回空列表。

不要把配置路径写错。provider 名是 `holographic`，但插件专属配置读取的是 `plugins.hermes-memory-store`，包括 `db_path`、`auto_extract`、`default_trust`、`hrr_dim`、`hrr_weight`、`temporal_decay_half_life` 等。

不要把 `search`、`probe`、`related`、`reason` 当成同一种查询。`search` 是关键词和混合排序；`probe` 是围绕单个实体的结构查询；`related` 是发现结构关联；`reason` 是多个实体同时成立的组合查询；`contradict` 是记忆卫生检查，用于发现可能冲突的事实对。

不要忽略 trust score。检索排序不是只看文本相似度，最终会乘以 `trust_score`，并可能受 `min_trust` 过滤。`fact_feedback` 不是附属功能，而是影响后续召回质量的核心机制。
