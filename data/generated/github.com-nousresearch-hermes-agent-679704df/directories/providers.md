# 目录：providers

## 它负责什么

`providers` 是 Hermes 推理模型供应商的“注册表与声明层”，不是具体供应商实现目录。它把每个 LLM provider 的身份、认证方式、默认端点、模型列表获取方式、请求参数差异、消息预处理钩子等统一收敛到 `ProviderProfile` 这个声明对象里。上层代码不需要到处写 `if provider == ...`，而是通过 `get_provider_profile()` 取到 profile，再由 auth、model picker、doctor、runtime routing、transport 等模块读取同一份声明。

这个目录的边界很清楚：它不负责真正创建 API client，不负责 credential rotation，不负责 streaming，也不直接实现具体模型调用。`providers/base.py` 里的注释明确说明，`ProviderProfile` 是 declarative 的；传输执行仍留在 `AIAgent` 和 `agent/transports/` 一侧。根据当前片段推断，这个目录的主要价值是降低 provider 差异在全仓库里的扩散，让新增 provider 通过插件注册进入统一流程。

## 直接子目录地图

`providers` 当前没有直接子目录，只有三个文件：

- `providers/__init__.py`：provider registry。暴露 `register_provider()`、`get_provider_profile()`、`list_providers()`，并负责 lazy discovery。
- `providers/base.py`：定义 `ProviderProfile` dataclass 和 `OMIT_TEMPERATURE` sentinel，是所有 provider profile 的基础结构。
- `providers/README.md`：说明该目录的职责、接入点和 provider plugin 的布局。

需要注意的是，实际 profile 实现主要不在 `providers` 下，而在邻近目录 `plugins/model-providers/<name>/`。当前仓库里可见的内置 provider plugin 包括 `anthropic`、`bedrock`、`custom`、`deepseek`、`gemini`、`gmi`、`kimi-coding`、`nous`、`nvidia`、`openai-codex`、`openrouter`、`qwen-oauth`、`xai`、`zai` 等。每个插件通常包含 `__init__.py` 和 `plugin.yaml`：前者 import 时调用 `register_provider(profile)`，后者声明插件元数据。

## 关键入口

最核心的入口是 `providers/__init__.py`。

`register_provider(profile)` 用 provider 的 canonical `name` 注册 `ProviderProfile`，同时把 `aliases` 写入 `_ALIASES`。同名注册会覆盖旧值，因此用户目录下的 provider plugin 可以覆盖内置 profile，这也是“last-writer-wins”的设计基础。

`get_provider_profile(name)` 是最常见的读取入口。第一次调用时会触发 `_discover_providers()`，之后会先用 `_ALIASES` 把别名解析为 canonical name，再从 `_REGISTRY` 返回对应的 `ProviderProfile`。找不到时返回 `None`，调用方可退回 generic provider 逻辑。

`list_providers()` 返回已注册的 canonical profiles。它同样会在首次访问时触发发现流程，并按对象 id 去重，避免 alias 指向同一个对象时重复出现在结果里。

`providers/base.py` 的关键入口是 `ProviderProfile`。它的字段可分为几组：身份字段如 `name`、`api_mode`、`aliases`；展示字段如 `display_name`、`description`、`signup_url`；认证和端点字段如 `env_vars`、`base_url`、`models_url`、`auth_type`；模型目录字段如 `fallback_models`、`hostname`；请求差异字段如 `default_headers`、`fixed_temperature`、`default_max_tokens`、`default_aux_model`。它还提供一组可覆写 hook：`get_hostname()`、`prepare_messages()`、`build_extra_body()`、`build_api_kwargs_extras()`、`get_max_tokens()`、`fetch_models()`。

## 主流程位置

provider discovery 的主流程在 `providers/__init__.py::_discover_providers()`。它是 lazy 的，不在 import `providers` 时立即扫描，而是在第一次调用 `get_provider_profile()` 或 `list_providers()` 时执行。发现顺序是：

1. 扫描仓库内置 `plugins/model-providers/<name>/`。
2. 扫描用户侧 `$HERMES_HOME/plugins/model-providers/<name>/`。
3. 兼容旧式 `providers/<name>.py` 单文件 profile。

这个顺序很重要：用户插件在内置插件之后加载，因此可以覆盖同名内置 provider；旧式 `providers/*.py` 仍被保留是为了 backward compatibility，新 provider 应优先走 plugin layout。

运行时主流程大致是：某个上层模块需要 provider 信息，调用 `get_provider_profile()`；registry 首次发现并 import 各 provider plugin；plugin 的 `__init__.py` 构造 `ProviderProfile` 或其子类并调用 `register_provider()`；调用方拿到 profile 后，把它传给后续流程。`providers/README.md` 指出，`run_agent.py` 会把 `provider_profile=<ProviderProfile>` 传入 transport，使请求构建走 profile 路径而不是旧式 flags 路径；`agent/transports/chat_completions.py::_build_kwargs_from_profile()` 会调用 `prepare_messages()`、`build_extra_body()`、`build_api_kwargs_extras()` 等 hook，把 provider 差异转成实际 API kwargs。

其他重要消费点包括：`hermes_cli/auth.py` 用 profile 扩展 API key provider 注册；`hermes_cli/models.py` 用 profile 扩展 canonical providers，并在 `provider_model_ids()` 中调用 `profile.fetch_models()`；`hermes_cli/doctor.py` 基于 `auth_type="api_key"` 添加 `/models` 健康检查；`hermes_cli/config.py` 把 `env_vars` 注入 setup wizard 可识别的环境变量列表；`hermes_cli/runtime_provider.py` 用 `profile.api_mode` 作为 URL 检测失败时的 fallback；`agent/model_metadata.py` 通过 `profile.get_hostname()` 做 hostname 到 provider 的映射；`agent/auxiliary_client.py` 优先读取 `profile.default_aux_model`。

## 推荐阅读顺序

建议先读 `providers/README.md`，建立“这里是 registry，不是 provider 实现”的边界意识。然后读 `providers/base.py`，重点看 `ProviderProfile` 的字段分组和 hook，而不是记每个字段。接着读 `providers/__init__.py`，理解 lazy discovery、bundled plugin、user plugin、legacy module 三段加载顺序，以及 alias 和覆盖规则。

之后再跳到 `plugins/model-providers/README.md` 和一两个具体插件，例如 `plugins/model-providers/openrouter/__init__.py`、`plugins/model-providers/kimi-coding/__init__.py` 或 `plugins/model-providers/nvidia/__init__.py`。选择这些是因为它们通常能展示不同复杂度：有的只是静态 profile，有的会覆写请求参数或模型目录逻辑。最后再看调用侧：`agent/transports/chat_completions.py`、`run_agent.py`、`hermes_cli/models.py`、`hermes_cli/auth.py`，这样能从“声明”走到“请求执行”和“CLI 展示”。

## 常见误区

第一，容易误以为 `providers` 目录里应该放每个供应商的实现。当前设计已经把具体 provider profiles 插件化，主位置是 `plugins/model-providers/<name>/` 和用户侧 `$HERMES_HOME/plugins/model-providers/<name>/`。`providers` 只提供注册表、基类和兼容旧单文件 profile 的发现逻辑。

第二，`ProviderProfile` 不是 transport，也不是 SDK adapter。它描述 provider 行为，例如是否省略 temperature、如何构造 `extra_body`、如何取模型列表，但真正的 HTTP 调用、streaming、client 生命周期仍在 agent/transport 层。

第三，`register_provider()` 的覆盖规则是有意设计，不是 bug。同名 profile 后注册者覆盖先注册者，所以用户 plugin 可以替换内置 provider。调试“为什么某个 provider 行为变了”时，要检查 `$HERMES_HOME/plugins/model-providers/` 是否有同名插件。

第四，`get_provider_profile()` 支持 alias。比如用户输入的 provider 名可能不是 canonical name，registry 会先查 `_ALIASES`。因此调用侧不应自行散落维护 provider 别名表，应该优先走该入口。

第五，新增 provider 不应优先修改 `providers/__init__.py` 或在 `providers` 下新增文件。根据当前片段和仓库说明，新 provider 的推荐路径是新增 `plugins/model-providers/<name>/__init__.py` 与 `plugin.yaml`，在插件导入时调用 `register_provider()`。旧式 `providers/<name>.py` 只是兼容历史用法。
