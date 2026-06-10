# 文件：plugins/memory/openviking/README.md

## 一句话定位

`plugins/memory/openviking/README.md` 是 OpenViking memory provider 的使用说明页，面向安装者和维护者说明该插件依赖什么、如何启用、需要哪些环境变量，以及启用后会给 Hermes agent 增加哪些 `viking_*` 记忆与知识库工具。它本身不参与运行时执行，但对应的实现集中在 `plugins/memory/openviking/__init__.py`。

## 它暴露/定义了什么

这个 README 暴露的是插件能力边界，而不是 Python API。它说明 OpenViking 是一个外部上下文数据库，提供类似文件系统的知识层级、分层检索和自动记忆抽取。文档定义了三类使用信息：安装要求、配置方式、工具清单。

安装要求包括 `openviking` 包、OpenViking server、以及 OpenViking 自身配置中的 embedding 和 VLM 模型。配置上，它要求将 `memory.provider` 设为 `openviking`，并通过 `.env` 提供 `OPENVIKING_ENDPOINT`、可选的 `OPENVIKING_API_KEY`。根据 `plugin.yaml` 和实现文件，实际实现还支持 `OPENVIKING_ACCOUNT`、`OPENVIKING_USER`、`OPENVIKING_AGENT`，README 对这些租户字段没有展开，维护时要注意文档可能滞后于代码。

工具层面，README 列出五个 agent 可调用工具：`viking_search`、`viking_read`、`viking_browse`、`viking_remember`、`viking_add_resource`。这些工具的 schema 和处理逻辑由同目录 `__init__.py` 注册。

## 谁调用它

README 不会被程序直接调用。它的“调用者”主要是人：配置 Hermes memory provider 的用户、维护该插件的开发者、以及排查 OpenViking 集成问题的人。

运行时真正被 Hermes 调用的是 `plugins/memory/openviking/__init__.py` 中的 `OpenVikingMemoryProvider`。根据当前片段推断，加载链路是：Hermes memory setup 或配置读取选择 `openviking` 后，`plugins/memory/__init__.py` 通过 memory provider 发现机制加载插件；插件的 `register(ctx)` 调用 `ctx.register_memory_provider(OpenVikingMemoryProvider())`；随后 `agent/memory_manager.py` 在会话生命周期中调用 provider 的 `initialize`、`prefetch`、`queue_prefetch`、`sync_turn`、`on_session_end`、`on_memory_write`、`shutdown` 等方法。

## 它调用谁

README 只描述依赖，不主动调用任何对象。对应实现会调用三类对象。

第一类是 Hermes 内部接口：`agent.memory_provider.MemoryProvider` 提供 memory provider 抽象；`tools.registry.tool_error` 用于工具错误格式；插件上下文 `ctx` 用于注册 provider。

第二类是 OpenViking 服务 API。`_VikingClient` 用 `httpx` 访问服务端，封装 `get`、`post`、`upload_temp_file`、`health` 等操作。根据当前片段可见，它会访问健康检查、文件系统列表、搜索、session messages、临时上传等 REST 端点。

第三类是 Python 标准库：`threading` 用于异步 prefetch 和 turn sync，`atexit` 用于进程退出时尽量提交 session，`zipfile`、`tempfile`、`pathlib` 用于本地目录资源打包上传，`urlparse` 和 `url2pathname` 用于处理 `file://` 输入。

## 核心流程

启用流程是：用户安装并启动 OpenViking server，配置 Hermes 的 `memory.provider=openviking` 和相关环境变量，然后 Hermes 在初始化 memory manager 时加载 `OpenVikingMemoryProvider`。

会话开始时，provider 的 `initialize` 从环境变量读取 endpoint、API key、account、user、agent，创建 `_VikingClient` 并做健康检查。若服务不可达，插件不会硬失败，而是把 `_client` 置空，后续方法大多直接跳过。

每轮对话前后有两条路径：`queue_prefetch` 会在后台按用户查询请求 OpenViking 搜索，把摘要结果缓存起来；下一轮 `prefetch` 取出缓存并注入为 `## OpenViking Context`。对话完成后，`sync_turn` 将 user 和 assistant 内容截断后写入 OpenViking session message，采用后台线程减少主对话阻塞。

会话结束时，`on_session_end` 等待最后一次写入完成，然后提交 session，触发 OpenViking 侧的自动记忆抽取。显式记忆写入有两种入口：agent 调用 `viking_remember`，或 Hermes 内置 memory 工具触发 `on_memory_write`，实现会按类别映射到 `viking://` 子目录。资源导入则通过 `viking_add_resource`，本地文件或目录会先上传或压缩，远程资源直接交给 OpenViking 处理。

## 关键函数的高层作用

`OpenVikingMemoryProvider.initialize` 负责连接配置、健康检查和注册进程退出兜底，是插件能否工作的入口。

`system_prompt_block` 负责给 agent 注入简短提示，告诉模型当前 OpenViking knowledge base 可用，以及该优先使用哪些 `viking_*` 工具。

`queue_prefetch` 和 `prefetch` 组成异步召回链路：前者后台搜索，后者把搜索结果作为上下文返回给 memory manager。

`sync_turn` 负责把会话轮次同步到 OpenViking session，是后续自动抽取长期记忆的原始材料来源。

`on_session_end` 负责提交 session，触发 OpenViking 侧对 profile、preferences、entities、events、cases、patterns 等类别的抽取。这个函数对长期记忆质量影响最大。

`on_memory_write` 负责镜像 Hermes 内置 memory 写入，把 user profile 或 agent notes 映射到 OpenViking 的偏好、模式等目录。

`_VikingClient` 是薄 HTTP 客户端，统一处理 headers、租户字段、错误解析、上传和健康检查。辅助函数如 `_zip_directory`、`_is_local_path_reference` 只服务于资源导入和路径识别，一句理解即可。

## 修改风险

最大风险是 README 与实现不一致。当前 README 只写了 `OPENVIKING_ENDPOINT` 和 `OPENVIKING_API_KEY`，但实现和 `get_config_schema` 还支持租户相关环境变量；如果文档继续简化，用户在多租户或 ROOT key 场景下可能无法正确配置。

第二个风险是工具语义变化。README 中五个 `viking_*` 工具是用户和模型理解 OpenViking 能力的入口；如果修改工具名、参数、检索层级或记忆类别，必须同步 `__init__.py` 的 schema、README 工具表、以及可能依赖这些工具名的 system prompt。

第三个风险是安装依赖表述。`plugin.yaml` 的 `pip_dependencies` 是 `httpx`，而 README 要求 `pip install openviking`。实现片段显示运行时代码直接用 `httpx` REST 调用，并不依赖 OpenViking SDK。根据当前片段推断，`openviking` 包需求可能是为了本地 server/CLI，而不是 Hermes 插件导入所必需；维护文档时应区分“运行服务端需要”和“插件 Python 代码需要”。

第四个风险是 endpoint 文档。不要在面向公开文档或学习页中泄露真实外部地址；本文件只应描述本地默认端口、环境变量名和配置意图。
