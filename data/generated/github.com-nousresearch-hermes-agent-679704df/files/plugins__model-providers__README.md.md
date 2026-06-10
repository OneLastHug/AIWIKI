# 文件：plugins/model-providers/README.md

## 一句话定位

`plugins/model-providers/README.md` 是 Hermes 模型推理后端插件体系的入口说明文档，定义了 `plugins/model-providers/<name>/` 这类 provider profile 插件应该如何组织、如何被发现、如何注册到全局 provider registry，以及新增或覆盖模型服务商时应遵守的最小契约。

## 它暴露/定义了什么

这个文件本身不暴露 Python API，也不会在运行时被 import；它暴露的是开发约定。核心约定有三层。

第一层是目录结构：每个模型 provider 都是一个独立子目录，例如 `plugins/model-providers/openrouter/`、`plugins/model-providers/anthropic/`。子目录至少包含 `__init__.py` 和 `plugin.yaml`。其中 `__init__.py` 负责构造并注册 `ProviderProfile`，`plugin.yaml` 负责声明插件元信息，例如 `name`、`kind: model-provider`、`version`、`description`。

第二层是注册契约：provider 插件在模块加载时调用 `providers.register_provider(profile)`。`profile` 通常是 `providers.base.ProviderProfile` 的实例，也可以是其子类实例，用来描述 provider 的名称、别名、展示名、鉴权环境变量、默认 `base_url`、默认辅助模型、请求参数差异等。

第三层是覆盖规则：内置插件位于仓库的 `plugins/model-providers/`，用户插件位于 `$HERMES_HOME/plugins/model-providers/`。发现顺序让用户插件后加载，因此同名 provider 会以“后注册者覆盖前注册者”的方式替换内置实现。

## 谁调用它

严格说，没有运行时代码“调用”这个 README。它的读者是新增模型 provider、维护 provider 插件、排查 provider 加载问题的开发者。

README 描述的机制由 `providers/__init__.py` 实现，并被多个运行时模块间接消费。典型入口是 `get_provider_profile()` 和 `list_providers()`：当这些函数第一次被调用时，会触发 provider 插件发现。调用方包括模型请求组装路径、CLI 配置与鉴权流程、模型列表与健康检查等。根据当前片段可见，`agent/chat_completion_helpers.py` 会通过 `get_provider_profile(agent.provider)` 获取当前 provider profile；`hermes_cli/auth.py`、`hermes_cli/config.py`、`hermes_cli/models.py`、`hermes_cli/doctor.py` 等会通过 `list_providers()` 或 `get_provider_profile()` 自动把新 provider 纳入鉴权、配置、模型选择和诊断流程。

## 它调用谁

README 本身不调用任何代码。它要求每个 provider 插件调用 `providers.register_provider()`，并依赖 `providers.base.ProviderProfile` 表达 provider 能力。

实际运行链路中，`providers/__init__.py` 会扫描 `plugins/model-providers/<name>/__init__.py`，通过 `importlib.util.spec_from_file_location()` 导入插件模块。插件模块导入 `providers.register_provider` 和 `providers.base.ProviderProfile`，创建 profile 后注册到 `_REGISTRY`。请求发送前，chat completions transport 会读取 `ProviderProfile` 上的 hook，例如 `prepare_messages()`、`build_extra_body()`、`build_api_kwargs_extras()`、`get_max_tokens()`，把 provider 差异转换成最终 API kwargs。

## 核心流程

核心流程从“第一次需要 provider 信息”开始，而不是程序启动时立即扫描。调用方执行 `get_provider_profile(name)` 或 `list_providers()` 时，`providers/__init__.py` 检查 `_discovered` 标志；如果尚未发现，就进入 `_discover_providers()`。

发现过程先扫描仓库内置目录 `plugins/model-providers/`，跳过隐藏目录和下划线开头目录，对每个含 `__init__.py` 的 provider 子目录执行导入。导入时，provider 的 `__init__.py` 在模块顶层构造一个或多个 `ProviderProfile`，并调用 `register_provider()`。随后发现器再扫描 `$HERMES_HOME/plugins/model-providers/` 下的用户 provider。因为用户目录后扫描，同名 `profile.name` 会覆盖内置 `_REGISTRY` 中的旧值，别名映射 `_ALIASES` 也会被更新到新的 canonical provider 名称。

完成注册后，调用方拿到 `ProviderProfile`。在聊天请求路径中，`agent/chat_completion_helpers.py` 如果找到 profile，就走 profile path，把请求构造委托给 chat completions transport。transport 根据 profile 处理消息预处理、temperature、tools、max tokens、reasoning 配置、`extra_body`、request overrides 等。找不到 profile 时才回退到 legacy flag path。

## 关键函数的高层作用

`register_provider(profile)` 是注册入口，把 `ProviderProfile.name` 写入 `_REGISTRY`，把 `aliases` 写入 `_ALIASES`。它没有复杂校验，核心语义是 last-writer-wins，因此覆盖能力来自这个函数。

`get_provider_profile(name)` 是按 provider 名或别名查找 profile 的入口。它负责触发懒发现，然后把别名解析为 canonical name，最后从 `_REGISTRY` 返回 profile；返回 `None` 表示走通用或旧逻辑。

`list_providers()` 返回所有已注册 provider profile，并按对象身份去重。CLI 的 provider 列表、setup、doctor、模型目录等功能依赖它自动感知新增 provider。

`_discover_providers()` 是发现流程的总控：按内置插件、用户插件、legacy `providers/*.py` 的顺序加载。它是 README 中“Nothing else needs to change”的运行时依据。

`_import_plugin_dir(plugin_dir, source)` 负责导入单个 provider 目录。内置插件使用稳定模块名，用户插件使用 `_hermes_user_provider_<name>` 形式的独立模块名，降低不同 profile 目录间的模块名冲突风险。

`ProviderProfile` 是 provider 差异的承载对象。简单 provider 可以直接实例化；复杂 provider 通过子类覆盖 hook，例如请求前消息转换、额外请求体、顶层 API 参数、模型列表拉取或默认 token 上限。

## 修改风险

这个 README 看似只是文档，但它描述的是 provider 插件的稳定契约，修改时最大的风险是让文档与 `providers/__init__.py` 的真实行为不一致。比如发现顺序、覆盖规则、插件位置、`plugin.yaml` 的 `kind`、或“首次调用才懒加载”的说法一旦写错，会直接误导第三方 provider 作者。

新增 provider 示例也有风险。示例中的 `ProviderProfile` 字段会被 setup、auth、doctor、models 和 chat transport 多处消费；如果文档暗示某些字段可随意省略，可能导致 provider 能注册但无法正确鉴权、无法拉模型列表、无法构造请求，或在运行时回落到不符合预期的默认行为。

覆盖规则尤其敏感。用户插件覆盖内置 provider 依赖 `register_provider()` 的后写覆盖语义和发现顺序。如果文档改成“同名禁止覆盖”或没有说明 last-writer-wins，用户侧热修 provider、替换内置 profile 的能力就会被误解。

还有一个边界是 general `PluginManager`。根据仓库说明，model-provider 插件有独立发现系统，普通插件管理器只记录或识别这类插件，不负责导入它们，以避免重复实例化 `ProviderProfile`。如果 README 把它写成普通插件加载路径，开发者可能会把 provider 写到错误目录，或期待 `register(ctx)` 风格的生命周期，导致 provider 不会进入 `get_provider_profile()` 的注册表。

最后，非平凡 provider 的 hook 文档需要谨慎。`build_extra_body()`、`build_api_kwargs_extras()`、`prepare_messages()` 等会影响每一次模型请求；错误示例可能造成 reasoning 参数位置错误、工具 schema 不兼容、temperature 被错误发送、或 max tokens 覆盖用户设置。修改 README 时应同时对照 `providers/base.py`、`providers/__init__.py`、`agent/chat_completion_helpers.py`、`agent/transports/chat_completions.py`，确认文档仍然匹配实际调用链。
