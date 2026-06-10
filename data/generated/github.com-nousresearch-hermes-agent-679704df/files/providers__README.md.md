# 文件：providers/README.md

## 一句话定位

`providers/README.md` 是 Hermes 推理模型 provider 注册体系的架构说明页，用来解释 `providers/` 包如何作为全局“ProviderProfile 注册表”，把认证、端点、模型列表、请求参数差异和运行时 provider 识别统一收敛到一套声明式 profile 上。

## 它暴露/定义了什么

这个文件本身不暴露 Python API，也不参与运行时导入；它定义的是开发约定和维护边界。核心对象是 `ProviderProfile`，实际定义在 `providers/base.py`，包括 `name`、`api_mode`、`aliases`、`display_name`、`env_vars`、`base_url`、`models_url`、`auth_type`、`fallback_models`、`default_headers`、`fixed_temperature`、`default_max_tokens`、`default_aux_model` 等字段。

README 还说明了注册入口来自 `providers/__init__.py`：`register_provider()`、`get_provider_profile()`、`list_providers()`。其中 `register_provider()` 由 provider 插件在 import 时调用，`get_provider_profile()` 和 `list_providers()` 会触发懒发现。文档明确指出 provider profile 的主要落点不是 `providers/*.py`，而是 `plugins/model-providers/<name>/` 和用户目录下的 `$HERMES_HOME/plugins/model-providers/<name>/`。

## 谁调用它

严格说没有代码“调用” `providers/README.md`，它是人读的架构文档。真正被调用的是 README 描述的 `providers` 包。

根据当前片段可确认，`hermes_cli/auth.py` 会调用 `list_providers()`，把 `auth_type="api_key"` 且带 `env_vars` 的 provider 自动补进认证注册表。`hermes_cli/config.py` 也会调用 `list_providers()`，把 profile 的环境变量注入 `OPTIONAL_ENV_VARS`，供 setup/config 流程识别。`hermes_cli/main.py` 的 `_is_profile_api_key_provider()` 会通过 `get_provider_profile()` 判断新 provider 是否能走通用 API key 模型选择流程。`run_agent.py` 会通过 `get_provider_profile()` 取 `default_headers` 等 profile 信息，并把 `provider_profile` 传给 transport。`agent/transports/chat_completions.py` 在请求构造阶段使用 `provider_profile` 进入 profile-driven 路径。

README 还列出 `hermes_cli/models.py`、`hermes_cli/doctor.py`、`hermes_cli/runtime_provider.py`、`agent/model_metadata.py`、`agent/auxiliary_client.py` 等消费者；这些模块共同把 provider profile 当作单一事实来源。

## 它调用谁

README 文件自身不调用任何模块。它描述的运行时链路是：`providers/__init__.py` 调用文件系统扫描与动态 import，导入 `plugins/model-providers/<name>/__init__.py`；每个插件再调用 `providers.register_provider(profile)` 完成注册。用户目录中的 provider 插件后加载，因此同名 profile 会覆盖内置 profile。

`ProviderProfile.fetch_models()` 的默认实现会调用标准库 `urllib.request` 访问 `{models_url or base_url}/models`，并解析返回 JSON 中的模型 id。复杂 provider 可以通过子类重写 `fetch_models()`、`build_extra_body()`、`build_api_kwargs_extras()`、`prepare_messages()` 等 hook，把差异留在 profile 层，而不是散落到 CLI、agent 和 transport 中。

## 核心流程

第一步是懒发现。任何模块首次调用 `get_provider_profile()` 或 `list_providers()` 时，`providers/__init__.py` 的 `_discover_providers()` 才会执行。它按顺序扫描内置 `plugins/model-providers/`、用户 `$HERMES_HOME/plugins/model-providers/`，最后兼容旧式 `providers/<name>.py` 单文件 profile。

第二步是插件自注册。每个 provider 插件的 `__init__.py` 构造一个 `ProviderProfile` 或其子类实例，然后调用 `register_provider()`。注册表按 canonical `profile.name` 保存 profile，并额外维护 alias 到 canonical name 的映射。

第三步是消费者读取。认证层读取 `env_vars` 和 `auth_type`，配置层读取环境变量元数据，模型选择层读取 `fallback_models` 和 `fetch_models()`，运行时层读取 `api_mode`，agent/transport 层读取请求期 hook 和默认参数。

第四步是请求构造。对已注册 provider，`ChatCompletionsTransport.build_kwargs()` 会优先走 `provider_profile` 路径，把消息预处理、`extra_body`、top-level kwargs、max token、temperature 等差异交给 profile 或其 hook 处理。未注册 provider 才回退到 legacy flag/URL 判断路径。

## 关键函数的高层作用

`register_provider(profile)` 是注册入口，负责把 profile 放入 `_REGISTRY`，并把 `aliases` 写入 `_ALIASES`。它允许后注册覆盖先注册，这是用户插件覆盖内置 provider 的基础。

`get_provider_profile(name)` 是运行时查询入口。它会先确保 `_discover_providers()` 已执行，再把 alias 解析成 canonical name，最后返回对应 `ProviderProfile`，不存在则返回 `None`，让调用方走 generic fallback。

`list_providers()` 返回所有 canonical profile，并用对象 id 去重。它主要服务于批量接入场景，例如认证注册表扩展、配置环境变量注入、模型列表和 doctor 健康检查。

`_discover_providers()` 是最关键的装配流程，决定发现顺序、覆盖规则和旧版兼容路径。它导入插件目录的副作用就是触发 `register_provider()`。

`ProviderProfile` 的 hook 是扩展点：`prepare_messages()` 处理 provider 特定消息结构，`build_extra_body()` 添加 provider 特定请求体，`build_api_kwargs_extras()` 处理 extra_body 与顶层参数的拆分，`fetch_models()` 获取实时模型目录，`get_hostname()` 支撑 URL 到 provider 的反查。

## 修改风险

最大风险是破坏“profile 是单一事实来源”的边界。如果新增 provider 时绕过 `plugins/model-providers/<name>/`，直接在 `auth.py`、`models.py`、`runtime_provider.py` 或 transport 里硬编码分支，会让认证、模型选择、doctor、辅助模型和请求参数逐渐分叉，后续维护成本会迅速上升。

第二个风险是发现顺序和覆盖语义。`_discover_providers()` 现在是内置插件先、用户插件后、legacy 单文件最后；改变顺序会影响用户覆盖内置 provider 的能力，也可能让旧式 `providers/*.py` 意外覆盖插件。

第三个风险是 import 副作用。provider 插件在导入时注册 profile，因此插件顶层代码应保持轻量，避免网络请求、读取敏感状态或依赖未初始化的运行时配置。否则一次 `list_providers()` 就可能引发慢启动或隐式失败。

第四个风险是 hook 参数契约。`build_extra_body()`、`build_api_kwargs_extras()`、`prepare_messages()` 被 transport 在每次请求时调用，返回结构错误会直接导致 provider 请求 400/422，甚至污染后续会话消息。复杂 provider 应在自己的插件内局部重写，不应修改通用 transport 的 profile 路径。

第五个风险是文档漂移。`providers/README.md` 是关键文件页，虽然不执行，但它描述的是添加 provider 的主路径。如果实际代码变更了注册入口、目录布局或消费者清单，必须同步更新此 README 和 `plugins/model-providers/README.md`，否则贡献者会按旧流程接入，造成半注册、能配置但不能运行、能运行但不出现在模型选择器等问题。
