# 文件：plugins/observability/langfuse/README.md

## 一句话定位

`plugins/observability/langfuse/README.md` 是 Hermes 内置 `observability/langfuse` 插件的使用说明页，面向操作者说明如何启用 Langfuse 链路观测、配置凭据、验证 Trace 是否产生，以及用环境变量调整采样和字段截断策略。它本身不是运行时代码，但它描述的开关和环境变量会直接影响 `plugins/observability/langfuse/__init__.py` 中的 Hook 是否真正工作。

## 它暴露/定义了什么

该 README 暴露的是插件的“运维契约”，不是 Python API。核心内容包括：

- 启用方式：安装 `langfuse` SDK 后执行 `hermes plugins enable observability/langfuse`，或在 `hermes plugins` 交互 UI 中勾选。
- 必需凭据：`HERMES_LANGFUSE_PUBLIC_KEY`、`HERMES_LANGFUSE_SECRET_KEY`、`HERMES_LANGFUSE_BASE_URL`，放在 `~/.hermes/.env`。
- 验证方式：通过 `hermes plugins list` 确认插件 enabled，再运行一次 `hermes chat -q "hello"`，然后在 Langfuse 侧查看名为 `Hermes turn` 的 trace。
- 可选调优项：`HERMES_LANGFUSE_ENV`、`HERMES_LANGFUSE_RELEASE`、`HERMES_LANGFUSE_SAMPLE_RATE`、`HERMES_LANGFUSE_MAX_CHARS`、`HERMES_LANGFUSE_DEBUG`。
- 禁用方式：`hermes plugins disable observability/langfuse`。

需要注意，README 中强调“SDK 或凭据缺失时 hooks no-op silently，插件 fail open”。这一点与代码里的 `_get_langfuse()` 行为一致：初始化失败后返回 `None`，不阻断主 Agent 流程。

## 谁调用它

README 文件不会被 Hermes 运行时主动调用。它的直接消费者是人：开发者、部署者、测试者，以及可能的插件 UI/文档浏览入口。

运行时真正被 Hermes 调用的是同目录下的 `plugins/observability/langfuse/__init__.py`。插件发现流程由 `hermes_cli.plugins.PluginManager` 负责；`model_tools.py` 在导入阶段会尝试 `discover_plugins()`，CLI、Gateway、TUI 等入口也会在各自启动路径中触发插件发现。插件启用状态来自 Hermes 插件系统的配置，而不是 README。

## 它调用谁

README 本身不调用任何模块。根据当前片段推断，它描述的命令会间接触发以下关系：

- `hermes plugins enable observability/langfuse` 修改插件启用配置，使 `PluginManager` 后续加载 `plugins/observability/langfuse/plugin.yaml` 和 `__init__.py`。
- `pip install langfuse` 提供运行时依赖，使 `__init__.py` 能导入 `Langfuse`、`propagate_attributes`。
- `.env` 中的 `HERMES_LANGFUSE_*` 变量被 `_get_langfuse()` 读取，用来构造 Langfuse 客户端。
- `hermes chat` 进入 Agent 对话循环后，`agent/conversation_loop.py`、`model_tools.py` 等调用 `hermes_cli.plugins.invoke_hook()`，从而触发 Langfuse 插件注册的 hook。

插件运行时会调用 Langfuse SDK 创建 trace、chain observation、generation observation、tool observation，并在结束时 flush。README 只负责告诉用户如何让这些调用具备前置条件。

## 核心流程

整体流程可以理解为“显式启用、运行时探测、Hook 观测、失败不影响主流程”。

1. 用户根据 README 安装 `langfuse` SDK，并通过 `hermes plugins enable observability/langfuse` 启用插件。
2. Hermes 插件管理器发现 `plugins/observability/langfuse/plugin.yaml`。该 manifest 声明插件名、版本、所需环境变量以及 hooks：`pre_api_request`、`post_api_request`、`pre_llm_call`、`post_llm_call`、`pre_tool_call`、`post_tool_call`。
3. 插件模块加载后执行 `register(ctx)`，把上述 hook 名称绑定到 `on_pre_llm_request`、`on_post_llm_call`、`on_pre_llm_call`、`on_pre_tool_call`、`on_post_tool_call`。
4. 每次模型请求前，`pre_api_request` 优先创建或复用一次 `Hermes turn` 根 trace，并为单次 LLM 请求创建 `generation` observation。
5. 模型响应后，`post_api_request` 或 `post_llm_call` 结束 generation，记录输出、tool call 摘要、usage token 和估算 cost。
6. 工具调用前后，`pre_tool_call` 和 `post_tool_call` 创建并结束 tool observation，同时把工具结果回填到当前 turn 的 tool call 记录中。
7. 若本轮没有后续工具调用且已有最终内容，插件结束根 trace，并调用 Langfuse client flush。

## 关键函数的高层作用

README 对应的关键运行时代码在 `plugins/observability/langfuse/__init__.py`：

- `register(ctx)`：插件入口函数，把 Langfuse 观测逻辑挂到 Hermes 的生命周期 hooks 上。它同时注册 API 级和 LLM 级 hook，是为了兼容不同 Hermes 版本。
- `_get_langfuse()`：运行时可用性门禁。它检查 SDK 是否可导入、凭据是否存在、key 前缀是否像真实 Langfuse key，并缓存成功或失败结果。失败后走 fail-open，不让观测问题破坏 Agent 对话。
- `_start_root_trace()`：创建一轮对话的根 trace，名称为 `Hermes turn`，写入 `session_id`、`task_id`、`platform`、`provider`、`model`、`api_mode` 等元数据。
- `on_pre_llm_request()`：每次 API 请求前启动 generation observation，输入是裁剪和安全序列化后的 messages。
- `on_post_llm_call()`：结束 generation，整理 assistant 输出、tool calls、token usage 和 cost。若该响应已经是最终内容，会触发 `_finish_trace()`。
- `on_pre_tool_call()` / `on_post_tool_call()`：围绕工具调用创建 tool observation，并记录参数和结果。对 `read_file` 结果有额外归一化，避免大文件内容或 base64 内容直接灌入观测系统。
- `_safe_value()`、`_normalize_payload()` 等辅助函数：负责截断、解析 JSON 字符串、限制嵌套深度、规整工具输出，主要是控制隐私、体积和 Langfuse 字段可读性。

## 修改风险

修改该 README 的主要风险不是编译失败，而是“文档与插件真实行为漂移”。如果启用命令、环境变量名、默认值或验证步骤写错，用户会以为插件不可用；如果把缺少 SDK/凭据描述成硬失败，则与当前 fail-open 设计冲突。

更高风险来自外部地址和凭据示例。文档中不应鼓励提交真实 key，也不应让示例 base URL 被误解为唯一可用部署；在对外文档场景中，真实网址还需要按发布规范脱敏。

如果未来修改 `__init__.py` 的 hook 名称、manifest 的 `requires_env`、采样变量或 key 校验逻辑，必须同步更新 README。尤其是 `HERMES_LANGFUSE_SAMPLE_RATE`、`HERMES_LANGFUSE_MAX_CHARS`、`HERMES_LANGFUSE_DEBUG` 这类调优项，文档一旦落后，会直接影响排障效率。

还要谨慎调整“hooks no-op silently / fail open”的表述。当前代码对缺失 SDK 或缺失凭据静默返回，但对疑似 placeholder key 会打一条 warning；如果 README 继续说完全静默，可能掩盖这类一次性告警行为。
