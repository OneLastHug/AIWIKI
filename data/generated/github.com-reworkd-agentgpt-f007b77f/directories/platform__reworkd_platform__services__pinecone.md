# 子系统：platform/reworkd_platform/services/pinecone

## 解决什么问题

`platform/reworkd_platform/services/pinecone` 是后端为 Agent 记忆能力预留的 Pinecone 向量数据库适配层。它把“任务文本”转换成 OpenAI embedding，写入 Pinecone index，并在后续根据输入文本做相似任务检索。这个目录不直接处理 Agent 推理、任务编排或 HTTP 请求，而是实现 `AgentMemory` 抽象的一种具体后端。

从当前代码看，这个子系统更像“可插拔但暂未启用”的记忆实现：`PineconeMemory.should_use()` 固定返回 `False`，且 `init_pinecone()` 在仓库当前片段中未看到被启动流程调用。根据当前片段推断，项目曾计划或曾经使用 Pinecone 作为长期记忆存储，但当前默认运行路径可能依赖 `NullAgentMemory` 或其他 memory fallback，而不是 Pinecone。

## 相关目录和文件

`platform/reworkd_platform/services/pinecone/pinecone.py` 是核心实现文件，定义 Pinecone 向量行模型、查询结果模型和 `PineconeMemory`。它负责连接 Pinecone index、生成 embedding、执行 `upsert`、`query` 和 namespace 级清理。

`platform/reworkd_platform/services/pinecone/lifetime.py` 提供 `init_pinecone()`，根据 `settings.pinecone_api_key` 和 `settings.pinecone_environment` 调用 `pinecone.init()`。它属于应用生命周期初始化工具，但当前检索结果中没有看到它接入 `platform/reworkd_platform/web/lifetime.py`。

`platform/reworkd_platform/services/pinecone/__init__.py` 只是包标记文件，没有业务逻辑。

邻近依赖主要在 `platform/reworkd_platform/web/api/memory/`：`memory.py` 定义 `AgentMemory` 抽象接口，`null.py` 定义空实现，`memory_with_fallback.py` 定义失败时降级到备用 memory 的包装器。配置来自 `platform/reworkd_platform/settings.py` 中的 `pinecone_api_key`、`pinecone_index_name`、`pinecone_environment` 以及 `openai_api_key`。

## 核心对象

`Row` 是写入 Pinecone 的数据结构，包含 `id`、`values` 和 `metadata`。其中 `values` 是 embedding 向量，`metadata` 默认存放原始任务文本，例如 `{"text": task}`。`id` 使用 `uuid.uuid4()` 生成，避免调用方自己维护向量主键。

`QueryResult` 是查询返回结果的内部模型，包含 Pinecone match 的 `id`、`score` 和 `metadata`。它保留了相似度分数和原始文本元信息，便于上层决定如何利用相似任务。

`PineconeMemory` 继承 `AgentMemory`，是这个目录的主类。构造函数接收 `index_name` 和可选 `namespace`，但实际创建 Pinecone `Index` 时使用的是 `settings.pinecone_index_name`，而 `namespace` 默认使用传入的 `index_name`。这意味着参数名容易让人误解：传入的 `index_name` 更像 namespace 默认值，真正的 Pinecone index 名称由全局配置决定。

`OPENAI_EMBEDDING_DIM = 1536` 表示预期 embedding 维度，与旧版 OpenAI embedding 模型常见维度一致。不过当前文件没有直接用它做校验，更多是文档化常量。

## 运行流程

应用若要使用 Pinecone，理论上启动时先调用 `init_pinecone()`。该函数只在同时存在 `pinecone_api_key` 和 `pinecone_environment` 时初始化 Pinecone SDK；如果配置为空，它静默跳过，不抛错。

业务侧创建 `PineconeMemory(index_name, namespace)` 后，通过上下文管理器进入使用阶段。`__enter__()` 会创建 `OpenAIEmbeddings`，并注入 `settings.openai_api_key`。这个设计表明 embedding client 的生命周期被绑定到一次 memory 使用上下文，而不是模块加载时立即创建。

写入时，上层调用 `add_tasks(tasks)`。空列表会直接返回空结果；非空列表先通过 `embed_documents()` 批量生成向量。代码会检查任务数量和向量数量是否一致，随后为每条任务构造 `Row`，把原始文本放入 metadata，最后调用 `self.index.upsert(..., namespace=self.namespace)` 写入 Pinecone。返回值是新生成的向量 id 列表。

检索时，上层调用 `get_similar_tasks(text, score_threshold=0.95)`。实现先用 `embed_query()` 把查询文本转成向量，再调用 Pinecone `query`，固定取 `top_k=5`，并要求返回 metadata 和 values。最终只保留 `score > score_threshold` 的 match，封装成 `QueryResult` 列表。

清理时，`reset_class()` 会在当前 namespace 下执行 `delete(delete_all=True)`，相当于清空该 Agent 或该逻辑分区的记忆。

## 上下游依赖

上游抽象是 `platform/reworkd_platform/web/api/memory/memory.py` 中的 `AgentMemory`。Pinecone 子系统需要遵守 `__enter__()`、`__exit__()`、`add_tasks()`、`get_similar_tasks()`、`reset_class()` 和 `should_use()` 这组接口，才能被 memory provider 或 fallback 包装器统一调用。

下游外部服务包括 Pinecone 和 OpenAI。Pinecone 负责向量索引存储与相似度查询，OpenAI 通过 LangChain 的 `OpenAIEmbeddings` 负责文本向量化。依赖包在 `platform/pyproject.toml` 中可见，包括 `pinecone-client`，LangChain 相关依赖则间接提供 embedding 封装。

配置依赖来自 `reworkd_platform.settings.settings`。Pinecone SDK 初始化依赖 `pinecone_api_key` 和 `pinecone_environment`；Index 选择依赖 `pinecone_index_name`；embedding 依赖 `openai_api_key`。如果这些配置缺失，`init_pinecone()` 可能跳过初始化，`PineconeMemory` 的构造或使用阶段则可能在 SDK、Index 或 embedding 调用时失败。

测试邻近区域有 `platform/reworkd_platform/tests/memory/memory_with_fallback_test.py`，覆盖 fallback 行为，但当前片段没有看到专门针对 `PineconeMemory` 的单元测试。

## 修改时最容易踩的坑

第一，`PineconeMemory.should_use()` 当前固定返回 `False`。如果只配置了环境变量但不改启用逻辑，Pinecone 仍不会自动成为默认 memory provider。修改启用策略时要同步检查 provider 选择代码，而不仅是 `lifetime.py`。

第二，构造函数参数和实际 index 来源不一致。`__init__(self, index_name, namespace="")` 中 `Index(settings.pinecone_index_name)` 使用全局配置，`namespace` 才默认来自 `index_name`。如果改名或改调用方，需要明确区分 Pinecone index 与 namespace，避免把不同 Agent 的记忆写入同一命名空间，或误删共享 namespace。

第三，接口返回类型存在偏差。`AgentMemory.get_similar_tasks()` 抽象声明返回 `List[str]`，但 `PineconeMemory.get_similar_tasks()` 实际返回 `List[QueryResult]`。如果上层按字符串列表处理，会出现运行时不兼容。修改这个子系统时应先统一 memory 抽象契约。

第四，`MemoryWithFallback.get_similar_tasks()` 接收 `score_threshold`，但调用 primary 时没有把该参数继续传下去。即使调用方传入不同阈值，Pinecone 实现也可能使用默认 `0.95`。这不是 Pinecone 目录内的问题，但会直接影响检索效果。

第五，`reset_class()` 是 namespace 级全量删除。任何 namespace 计算错误都会造成整段记忆丢失；引入新调用点时要特别确认 namespace 的粒度是用户、Agent、会话还是任务类型。

第六，embedding 维度必须和 Pinecone index 维度一致。文件中有 `OPENAI_EMBEDDING_DIM = 1536`，但没有运行时校验；如果更换 embedding 模型或 Pinecone index 配置，写入可能失败或查询结果异常。

## 推荐阅读顺序

先读 `platform/reworkd_platform/web/api/memory/memory.py`，理解 `AgentMemory` 抽象希望暴露什么能力。

再读 `platform/reworkd_platform/web/api/memory/null.py` 和 `platform/reworkd_platform/web/api/memory/memory_with_fallback.py`，理解项目如何容忍 memory 后端不可用，以及为什么 Pinecone 这类外部依赖需要 fallback。

接着读 `platform/reworkd_platform/services/pinecone/lifetime.py`，确认 Pinecone SDK 初始化依赖哪些配置。

然后重点读 `platform/reworkd_platform/services/pinecone/pinecone.py`，按 `__enter__()`、`add_tasks()`、`get_similar_tasks()`、`reset_class()` 的顺序理解数据如何从文本变成向量、再从向量恢复到相似任务。

最后查看 `platform/reworkd_platform/settings.py` 的 Pinecone 和 OpenAI 配置项，以及 `platform/pyproject.toml` 中的 `pinecone-client` 依赖版本。这样可以把代码行为、运行配置和外部 SDK 约束串起来。
