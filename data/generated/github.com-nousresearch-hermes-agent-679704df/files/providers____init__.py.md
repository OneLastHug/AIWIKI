# 文件：providers/__init__.py

## 一句话定位

`providers/__init__.py` 是 Hermes 推理模型 provider 的懒加载注册中心，负责把 `plugins/model-providers/<name>/` 和用户目录中的 provider 插件导入成 `ProviderProfile` 注册表，并向运行时、CLI、配置和模型选择器提供按名称或别名查询 provider 能力的统一入口。

## 它暴露/定义了什么

这个文件主要暴露三类内容：`register_provider(profile)`、`get_provider_profile(name)`、`list_providers()`。其中 `ProviderProfile` 和 `OMIT_TEMPERATURE` 从 `providers/base.py` 重新导出，方便插件直接写 `from providers import register_provider`，再从 `providers.base` 取 profile 类型。

内部状态包括 `_REGISTRY`、`_ALIASES`、`_discovered`。`_REGISTRY` 以 canonical provider name 保存 `ProviderProfile`，`_ALIASES` 把别名映射到 canonical name，`_discovered` 保证插件扫描只执行一次。它还定义了 `_BUNDLED_PLUGINS_DIR`，指向仓库内置的 `plugins/model-providers`。

## 谁调用它

主要调用方分成三层。

运行时层：`agent/chat_completion_helpers.py` 调用 `get_provider_profile(agent.provider)`，命中后把 `ProviderProfile` 传给 `agent/transports/chat_completions.py` 构造请求参数；`run_agent.py` 也会查询 profile 的 `default_headers`，用于客户端默认请求头。

辅助任务层：`agent/auxiliary_client.py` 用 `get_provider_profile()` 读取 `default_aux_model`、`default_headers` 等信息，为压缩、视觉、标题生成等旁路模型调用选择更便宜或更合适的模型。

CLI/配置层：`hermes_cli/models.py` 用 `list_providers()` 自动扩展模型选择器里的 provider 列表；`hermes_cli/config.py` 用它把 provider profile 中声明的环境变量注入配置元数据；`hermes_cli/doctor.py`、`hermes_cli/auth.py` 等也会读取 provider 列表做健康检查、认证提示或注册表补全。

另外，`hermes_cli/plugins.py` 明确识别 `kind: model-provider` 插件，但不导入它们，而是把生命周期交给本文件，避免重复实例化 `ProviderProfile`。

## 它调用谁

它直接依赖 `providers.base.ProviderProfile` 作为注册对象类型；通过 `hermes_constants.get_hermes_home()` 定位用户级 `$HERMES_HOME/plugins/model-providers`；通过 `importlib.util.spec_from_file_location()` 导入插件目录的 `__init__.py`；通过 `pkgutil.iter_modules()` 和 `importlib.import_module()` 兼容旧式 `providers/<name>.py` 单文件 provider。

被导入的插件反过来会在模块顶层调用 `register_provider(ProviderProfile(...))`，所以本文件不是解析 `plugin.yaml` 的地方，也不主动读取 profile 字段；它只负责导入、注册、别名映射和查询。

## 核心流程

第一次调用 `get_provider_profile()` 或 `list_providers()` 时，如果 `_discovered` 为 false，就进入 `_discover_providers()`。发现顺序是：先扫描仓库内置 `plugins/model-providers/<name>/`，再扫描用户目录 `$HERMES_HOME/plugins/model-providers/<name>/`，最后扫描 legacy 的 `providers/*.py`。

每个插件目录必须有 `__init__.py`。导入时，本文件会为内置插件构造类似 `plugins.model_providers.<safe_name>` 的模块名，为用户插件构造 `_hermes_user_provider_<safe_name>`，并放入 `sys.modules` 防止重复导入。插件模块执行后，通过顶层 `register_provider()` 把 profile 写入 `_REGISTRY`。

覆盖语义是“后注册者胜出”：用户插件在内置插件之后加载，所以同名用户 provider 可以替换内置 provider。legacy 单文件 provider 又在最后加载，因此也可能覆盖前面的同名注册。根据当前片段推断，这种顺序是有意设计的，因为文件注释和 `register_provider()` 文档都强调 last-writer-wins。

## 关键函数的高层作用

`register_provider(profile)` 是唯一写入口。它把 `profile.name` 写入 `_REGISTRY`，再把 `profile.aliases` 中的每个别名写入 `_ALIASES`。它不做类型校验，也不阻止覆盖，这让插件机制简单，但也意味着错误 profile 会在更下游才暴露。

`get_provider_profile(name)` 是运行时最常用的读入口。它先触发懒发现，再把传入 name 通过 `_ALIASES` 归一到 canonical name，最后从 `_REGISTRY` 取 profile。找不到时返回 `None`，调用方通常会回退到 legacy provider 逻辑或 generic OpenAI-compatible 路径。

`list_providers()` 用于 UI、配置和诊断。它同样触发懒发现，然后按对象 id 去重返回 profile 列表。当前 `_REGISTRY` 本身只按 canonical name 保存，去重更像防御性处理，避免未来或异常注册导致重复对象外泄。

`_import_plugin_dir(plugin_dir, source)` 负责把一个插件目录导入成 Python 模块。它处理模块名安全化、`sys.modules` 缓存、导入失败日志和失败后的缓存清理，是插件加载稳定性的关键点。

`_discover_providers()` 是总调度。它设置 `_discovered = True` 后依次导入内置、用户、legacy provider。注意它在扫描开始前就置 true，因此如果导入过程中有插件失败，后续普通查询不会自动重试。

`_user_plugins_dir()` 只是解析用户插件目录；失败时返回 `None`，避免 provider 系统因配置路径异常影响主流程。

## 修改风险

最高风险是改变发现顺序。内置、用户、legacy 的顺序决定覆盖语义；一旦调整，用户自定义 provider 覆盖内置实现的能力可能失效，模型选择器、认证配置和运行时请求都会受到影响。

第二个风险是模块名和导入方式。内置插件使用稳定模块名以支持相对导入，用户插件使用独立模块名以避免不同 `HERMES_HOME` profile 互相污染。修改 `_import_plugin_dir()` 时如果破坏 `submodule_search_locations` 或 `sys.modules` 清理，可能导致相对导入失败、重复注册或跨 profile 串状态。

第三个风险是懒加载状态。`_discovered` 是进程级全局开关，测试、动态安装插件或多 profile 场景如果需要重新发现，当前文件没有公开 reset API。给它增加重载能力时要同时处理 `_REGISTRY`、`_ALIASES`、`sys.modules` 中已导入插件的残留。

第四个风险是错误处理。当前导入失败只记录 warning 并继续，保证坏插件不阻断主程序。如果改成抛异常，可能让一次 provider 查询拖垮 CLI 启动、doctor、模型列表或聊天请求。

最后，`register_provider()` 没有校验 name、alias 冲突和 profile 类型。这对插件作者友好，但也意味着新增校验可能破坏现有第三方插件；如果必须加强，应优先在文档、doctor 或测试辅助函数中提示，而不是直接改变运行时容错语义。
