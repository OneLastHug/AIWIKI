# 目录：plugins/model-providers

## 它负责什么

`plugins/model-providers` 是 Hermes 的“模型服务商配置插件”目录。它不直接发送模型请求，也不负责构造底层客户端；它的职责是用一组 `ProviderProfile` 描述不同推理服务商的身份、认证方式、默认端点、模型列表获取方式、请求参数差异和少量 provider 专属兼容逻辑。

从架构上看，这个目录把“provider 差异”从 `run_agent.py`、`agent/transports/chat_completions.py` 这类主流程代码里抽离出来。每个子目录通常对应一个服务商或一种接入形态，例如 `openrouter`、`anthropic`、`gemini`、`bedrock`、`custom`、`qwen-oauth` 等。目录内的 `__init__.py` 在导入时创建一个或多个 `ProviderProfile`，然后调用 `providers.register_provider(...)` 注册到全局 provider registry。

这个目录属于插件体系，但它不是由通用 `PluginManager` 直接导入执行。`hermes_cli/plugins.py` 会记录 `kind: model-provider` 的 manifest 供内省使用，但真正加载由 `providers/__init__.py` 的懒发现逻辑完成。这样可以避免同一个 provider 被双重导入，也能保留“用户插件覆盖内置插件”的 last-writer-wins 语义。

## 直接子目录地图

该目录下的直接子目录大体可以按接入类型理解，而不是逐个文件阅读：

`openrouter`、`gmi`、`nous`、`novita`、`nvidia`、`arcee`、`zai`、`stepfun`、`xai`、`deepseek`、`minimax`、`alibaba`、`xiaomi` 等，主要是 OpenAI-compatible 或近似兼容的云端推理服务商 profile。

`anthropic`、`gemini`、`bedrock`、`azure-foundry` 等，代表有更明显平台特性的 provider。它们可能需要定制 auth、endpoint、reasoning 参数、消息格式或 native client 路径。

`copilot`、`copilot-acp`、`qwen-oauth`、`kimi-coding`、`alibaba-coding-plan`、`opencode-zen`、`kilocode`、`openai-codex` 等，更偏“编码代理/门户/OAuth/特殊产品线”接入，通常不只是设置一个 API key 和 base URL。

`custom` 是本地或用户自定义 endpoint 的兜底 profile，覆盖 `ollama`、`local`、`vllm`、`llama.cpp` 等 alias。它的 `base_url` 留空，由用户配置注入，且包含 Ollama context window、thinking 关闭等本地服务常见差异。

每个 provider 子目录通常只有两个核心文件：`__init__.py` 和 `plugin.yaml`。`plugin.yaml` 声明插件元信息，例如 `name`、`kind: model-provider`、`version`、`description`；`__init__.py` 才是行为入口。

## 关键入口

最重要的目录内入口是 `plugins/model-providers/README.md`。它说明了 provider 插件约定：创建 `plugins/model-providers/<name>/__init__.py`，实例化或继承 `ProviderProfile`，最后调用 `register_provider(profile)`；同时创建 `plugin.yaml` 声明 manifest。

真正的注册表入口在相邻目录 `providers/__init__.py`。这里定义了：

`register_provider(profile)`：按 `profile.name` 注册 provider，并把 `profile.aliases` 写入 alias 映射。后注册覆盖先注册。

`get_provider_profile(name)`：按 provider 名或 alias 查找 profile。首次调用时触发 `_discover_providers()`。

`list_providers()`：返回所有已注册的 canonical provider profile，也会触发懒发现。

`_discover_providers()`：按顺序扫描内置 `plugins/model-providers/<name>/`、用户 `$HERMES_HOME/plugins/model-providers/<name>/`、以及旧式 `providers/<name>.py` 单文件模块。这个顺序意味着用户目录中的同名 provider 可以覆盖仓库内置 provider。

`providers/base.py` 定义 `ProviderProfile`。它是这个目录所有插件共同使用的核心数据结构，字段包括 `name`、`api_mode`、`aliases`、`display_name`、`description`、`signup_url`、`env_vars`、`base_url`、`models_url`、`auth_type`、`fallback_models`、`default_headers`、`fixed_temperature`、`default_max_tokens`、`default_aux_model` 等。

`ProviderProfile` 还提供几个可覆盖 hook：`prepare_messages()`、`build_extra_body()`、`build_api_kwargs_extras()`、`get_max_tokens()`、`fetch_models()`。简单 provider 直接实例化 `ProviderProfile` 即可；复杂 provider 会继承它，比如 `openrouter` 处理 provider routing 和 reasoning 透传，`gemini` 转换 `thinking_config`，`custom` 处理 Ollama 的 `num_ctx` 和 `think=false`。

## 主流程位置

主流程可以概括为“配置选择 provider → registry 找 profile → transport 按 profile 构造请求”。

在 agent 请求路径中，`agent/chat_completion_helpers.py` 会根据 `agent.provider` 调用 `providers.get_provider_profile(agent.provider)`。如果找到 profile，就把它作为 `provider_profile` 传给 `agent/transports/chat_completions.py` 的请求构造逻辑。

`agent/transports/chat_completions.py` 中，`build_kwargs()` 会优先判断 `provider_profile`。存在 profile 时走 `_build_kwargs_from_profile()`，这里会调用 profile 的 hook：先 `prepare_messages()`，再处理 temperature、max_tokens、tools、`build_extra_body()`、`build_api_kwargs_extras()` 等。没有 profile 时才进入 legacy flag path。也就是说，已注册 provider 的差异应尽量沉淀到 `ProviderProfile`，而不是继续在 transport 里增加 provider 特判。

配置、模型选择和诊断路径也会读取这个 registry。根据 `plugins/model-providers/README.md` 和代码引用，`auth.py`、`config.py`、`models.py`、`doctor.py`、`model_metadata.py`、`runtime_provider.py` 等会围绕 provider registry 自动工作；当前片段中可见 `hermes_cli/models.py`、`hermes_cli/doctor.py`、`hermes_cli/config.py`、`agent/model_metadata.py` 等都调用了 `get_provider_profile()` 或 `list_providers()`。

## 推荐阅读顺序

1. 先读 `plugins/model-providers/README.md`，理解目录契约：每个子目录自注册 `ProviderProfile`，`plugin.yaml` 只做 manifest。

2. 再读 `providers/base.py`，掌握 `ProviderProfile` 字段和 hook。这里决定“一个 provider 能声明什么”。

3. 接着读 `providers/__init__.py`，重点看 `_discover_providers()`、`register_provider()`、`get_provider_profile()`，理解懒加载、alias、用户覆盖和 legacy fallback。

4. 然后选简单 provider 看一遍，例如 `plugins/model-providers/nvidia/__init__.py`、`plugins/model-providers/alibaba/__init__.py` 或 `plugins/model-providers/xai/__init__.py`。它们通常只是填字段并注册，适合理解最小形态。

5. 再看复杂 provider，例如 `plugins/model-providers/openrouter/__init__.py`、`plugins/model-providers/gemini/__init__.py`、`plugins/model-providers/custom/__init__.py`、`plugins/model-providers/qwen-oauth/__init__.py`。这些展示了何时需要继承 `ProviderProfile` 并覆盖 hook。

6. 最后读 `agent/chat_completion_helpers.py` 和 `agent/transports/chat_completions.py` 中与 `provider_profile` 相关的片段，把静态 profile 如何进入真实请求串起来。

## 常见误区

不要把 `plugin.yaml` 当作 provider 的运行入口。它主要提供 manifest；真正注册发生在子目录的 `__init__.py`，通过 `register_provider()` 完成。

不要以为通用 `PluginManager` 会导入这些 provider。`hermes_cli/plugins.py` 对 `kind: model-provider` 的处理是记录而不导入，导入由 `providers/__init__.py` 在首次 `get_provider_profile()` 或 `list_providers()` 时完成。

不要在新增 provider 时改 `run_agent.py` 或 `chat_completions.py` 加大量特判。已有设计是把 provider 差异放入 `ProviderProfile` 字段或 hook。只有通用 transport 能力不足时，才应考虑扩展 profile hook 或 transport 公共能力。

不要忽略 alias。用户可能用 `or` 查到 `openrouter`，用 `ollama` 查到 `custom`，用 `qwen` 查到 `qwen-oauth`。排查 provider 选择问题时，要同时看 `name` 和 `aliases`。

不要假设内置 provider 永远最终生效。`$HERMES_HOME/plugins/model-providers/<name>/` 下的用户 provider 会在内置 provider 之后加载，同名注册会覆盖前者。这是有意设计，用于第三方替换或修补内置 profile。

不要把 `fetch_models()` 理解为必然成功的在线目录。它失败时应返回 `None`，调用方需要回退到静态或备用模型列表。部分 provider 还会有专门的模型过滤逻辑，不一定放在 profile 的 `fetch_models()` 内。
