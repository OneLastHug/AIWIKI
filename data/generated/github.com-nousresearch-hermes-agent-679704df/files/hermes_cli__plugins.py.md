# 文件：hermes_cli/plugins.py

## 一句话定位

`hermes_cli/plugins.py` 是 Hermes 通用插件系统的核心入口，负责发现插件、解析插件清单、按配置决定是否加载、向插件提供 `PluginContext` 注册能力，并在运行期分发 hook、插件工具、插件命令、平台适配器和若干后端 provider。

## 它暴露/定义了什么

这个文件主要定义三类东西。

第一类是数据结构：`PluginManifest` 表示从 `plugin.yaml` / `plugin.yml` 解析出的插件元信息，包括 `name`、`version`、`source`、`kind`、`key`、`path` 等；`LoadedPlugin` 表示运行期加载结果，包括模块对象、已注册工具、hook、命令、是否启用和错误信息。

第二类是插件对宿主的注册 facade：`PluginContext`。插件的 `register(ctx)` 函数拿到的就是它。它提供 `register_tool()`、`register_hook()`、`register_command()`、`register_cli_command()`、`register_platform()`、`register_skill()`、`register_auxiliary_task()`，以及 image/video/web/browser/TTS/STT/dashboard auth/context engine 等 provider 注册方法。它还暴露 `ctx.llm`，让受信插件通过 `agent.plugin_llm.PluginLlm` 使用宿主侧模型能力。

第三类是管理器和模块级入口：`PluginManager` 负责实际发现和加载；`get_plugin_manager()` 提供全局单例；`discover_plugins()` 触发幂等发现；`invoke_hook()` 分发生命周期 hook；底部还有 `get_pre_tool_call_block_message()`、`get_plugin_context_engine()`、`get_plugin_command_handler()`、`resolve_plugin_command_result()`、`get_plugin_commands()`、`get_plugin_auxiliary_tasks()`、`get_plugin_toolsets()` 等查询或适配函数。

## 谁调用它

插件发现的核心调用点包括 `model_tools.py`，它在内置工具发现后调用 `discover_plugins()`，使插件工具进入工具注册表；`cli.py` 和 `hermes_cli/main.py` 在 CLI 启动、延迟启动或插件命令相关路径中调用；`gateway/run.py` 和 `gateway/config.py` 在 gateway 启动、平台注册、配置解析时调用；`tui_gateway/server.py` 在 TUI gateway 初始化和展示插件状态时访问；`cron/scheduler.py` 为支持插件平台注册的 cron 投递能力也会触发发现。

运行期 hook 侧，根据当前片段和仓库检索结果推断，`model_tools.py`、`run_agent.py`、approval、terminal output transform、shell hooks、gateway pre-dispatch 等路径会通过 `invoke_hook()` 或管理器对象调用插件回调。`tools/skills_tool.py` 会通过 `get_plugin_manager()` 查询插件 skill。`hermes_cli/tools_config.py` 会用 `get_plugin_toolsets()` 将插件工具集纳入工具配置界面。

## 它调用谁

文件内部依赖 `hermes_constants.get_hermes_home()` 定位用户插件目录，依赖 `hermes_cli.config.load_config()` 和 `cfg_get()` 读取 `plugins.enabled`、`plugins.disabled`，依赖 `utils.env_var_enabled()` 判断项目插件开关。目录插件通过 `importlib.util.spec_from_file_location()` 动态导入，pip 插件通过 `importlib.metadata.entry_points()` 扫描 `hermes_agent.plugins` entry point。

注册能力会进一步调用多个子系统：`tools.registry.registry` 接收插件工具；`gateway.platform_registry.platform_registry` 接收平台适配器；`agent.image_gen_registry`、`agent.video_gen_registry`、`agent.web_search_registry`、`agent.browser_registry`、`agent.tts_registry`、`agent.transcription_registry` 接收各类 provider；`hermes_cli.dashboard_auth` 接收 dashboard auth provider；`agent.context_engine.ContextEngine` 用于类型校验；`agent.skill_utils` 用于 skill 名称校验；`hermes_cli.commands.resolve_command()` 用于防止插件 slash command 和内置命令冲突。

## 核心流程

核心入口是 `discover_plugins(force=False)`，它委托全局 `PluginManager.discover_and_load()`。如果已经发现过且不是强制刷新，会直接返回；强制刷新时会清空已加载插件、hook、插件工具名、插件命令、插件 skill、辅助任务和 context engine。

发现阶段按来源收集 manifest：先扫描 bundled 插件目录，跳过 `memory`、`context_engine`、`platforms`、`model-providers` 等有独立发现路径的目录；然后单独扫描 `plugins/platforms`；再扫描用户目录 `$HERMES_HOME/plugins`；如果 `HERMES_ENABLE_PROJECT_PLUGINS` 打开，再扫描当前项目的 `.hermes/plugins`；最后扫描 pip entry point。目录扫描支持两种布局：`plugins/foo/plugin.yaml` 的 flat 插件，以及 `plugins/image_gen/openai/plugin.yaml` 这种 category 插件，后者的 `key` 会是 `image_gen/openai`，避免同名插件跨类别冲突。

筛选阶段会做“后来源覆盖前来源”的 winners 去重，并读取 `plugins.disabled` 与 `plugins.enabled`。显式 disabled 永远跳过；`kind: exclusive` 只记录不加载，交给 memory 等专属发现系统；`kind: model-provider` 只记录不导入，交给 `providers/__init__.py`，避免重复实例化 ProviderProfile；bundled 的 `backend` 和 `platform` 自动加载；其他 standalone、用户安装 backend、entry point 插件默认必须出现在 `plugins.enabled` 中才加载。

加载阶段 `_load_plugin()` 动态导入模块，查找 `register(ctx)`，构造 `PluginContext` 并调用它。插件在 `register()` 中调用各种 `ctx.register_*()`，这些注册会落到工具注册表、hook 表、平台注册表或 provider 注册表。加载完成后，`LoadedPlugin` 记录启用状态和该插件注册出的工具、hook、slash command 信息。任何加载异常会记录到 `LoadedPlugin.error`，不让单个插件直接打断宿主启动。

运行期阶段，核心系统调用 `invoke_hook(hook_name, **kwargs)` 分发给对应 hook 的所有 callback。每个 callback 单独 try/except，返回值中非 `None` 的结果会被收集。对于 `pre_tool_call`，`get_pre_tool_call_block_message()` 还会解释插件返回的 `{"action": "block", "message": "..."}`，用于阻止工具调用。

## 关键函数的高层作用

`PluginManager.discover_and_load()` 是主流程编排器，决定扫描哪里、谁覆盖谁、哪些插件应该加载、哪些只记录元信息。

`_scan_directory()` / `_scan_directory_level()` 负责目录插件发现，处理 flat 与 category 两种布局，并限制递归深度，避免把任意深层目录都当成插件。

`_parse_manifest()` 负责读取 YAML 清单、生成 `PluginManifest`，并带有两个重要启发式：未声明 `kind` 的用户插件如果源码中出现 `register_memory_provider` / `MemoryProvider`，会被当作 `exclusive`；如果出现 `register_provider` 和 `ProviderProfile`，会被当作 `model-provider`。

`_load_plugin()` 负责导入插件并调用 `register(ctx)`，也是插件从“可见”变成“生效”的边界。`_load_directory_module()` 用 `hermes_plugins.<slug>` 命名空间加载目录插件，category key 中的 `/` 会转成 `__`，避免模块名冲突。

`PluginContext.register_tool()` 将插件工具注册到 `tools.registry`，并记录插件工具名。它支持 `override=True`，因此具备替换内置工具的能力，风险也最高。

`PluginContext.register_hook()` 将 callback 挂到 `_hooks`。未知 hook 只警告仍保存，这让未来版本 hook 对旧宿主有一定前向兼容。

`PluginContext.register_command()` 注册会话内 slash command，会先检查是否和 `hermes_cli.commands` 内置命令冲突。`register_cli_command()` 注册的是 `hermes <subcommand>` 级别的 CLI 命令，两者不是同一类扩展点。

`PluginContext.register_platform()` 把 gateway 平台适配器注册到 `gateway.platform_registry`，使插件平台能被 gateway、cron 等路径发现。

`resolve_plugin_command_result()` 处理插件 slash command 的同步/异步返回值。若当前没有 event loop，会直接 `asyncio.run()`；若已有 event loop，会开辅助线程等待，且有 30 秒超时，避免同步调用点被 async handler 卡死。

`get_plugin_toolsets()` 把插件注册的工具按 toolset 聚合，供工具配置界面展示和开关。

辅助函数如 `_get_enabled_plugins()`、`_get_disabled_plugins()`、`_env_enabled()`、`get_bundled_plugins_dir()` 主要服务配置读取和路径定位，不是业务主干。

## 修改风险

最大风险是加载策略和信任边界。`plugins.enabled`、`plugins.disabled`、bundled backend/platform 自动加载、user/project/pip 插件 opt-in、`exclusive` / `model-provider` 只记录不导入，这些规则共同保证兼容性和安全性。随意改变会导致用户插件突然失效、未授权插件自动执行，或模型 provider 被重复加载。

第二个风险是 key 和覆盖语义。`manifest.key` 是路径派生的稳定标识，支持 `image_gen/openai` 这类 category 插件；如果改成只按 `name` 去重，会让不同类别同名插件互相覆盖，也会破坏已有配置中的启用/禁用项。

第三个风险是导入副作用。插件模块的 `register(ctx)` 可以注册工具、hook、provider、平台，甚至通过 `ctx.llm` 使用宿主模型能力。新增调用点时应避免在不合适的时机触发 `discover_plugins()`，尤其是异步 gateway 热路径，否则可能引入阻塞或重复副作用。

第四个风险是 provider 专属发现系统。`memory`、`context_engine`、`model-providers` 等并不完全由本文件加载。特别是 `model-provider` 插件在这里不能导入，只能记录 manifest；否则会破坏 provider 注册的“最后写入者获胜”语义。

第五个风险是工具覆盖。`register_tool(..., override=True)` 可以替换已有工具名。如果放宽校验或默认允许覆盖，插件可以无声改变核心工具行为；如果收紧过度，又会破坏已有自定义 backend 或测试场景。

第六个风险是 hook 返回值协议。大多数 hook 是观察型，但 `pre_tool_call`、`transform_*`、`pre_gateway_dispatch` 等会影响控制流或输出内容。修改 `invoke_hook()` 的异常处理、返回值过滤或顺序，可能改变安全策略、输出转换和 gateway 消息处理结果。
