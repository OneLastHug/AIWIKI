# 目录：plugins

## 它负责什么

`plugins` 是 Hermes Agent 的扩展插件集合目录，承担“把核心能力做成可发现、可注册、可替换的外部模块”的角色。它不是单一插件系统，而是多个插件发现机制的汇合点：通用插件由 `hermes_cli/plugins.py` 管理；模型供应商插件由 `providers/__init__.py` 单独懒加载；记忆插件由 `plugins/memory/__init__.py` 单独发现；上下文引擎由 `plugins/context_engine/__init__.py` 单独发现。

从职责上看，这个目录覆盖几类扩展：模型后端、记忆后端、图像/视频/网页/浏览器等工具后端、网关平台适配器、Dashboard 相关插件、可观测性、独立工具插件以及部分产品化功能插件。多数插件通过 `plugin.yaml` 描述元信息，通过 `__init__.py` 中的 `register(ctx)` 向宿主注册能力；少数专用插件体系直接通过自己的注册表或发现器加载。

## 直接子目录地图

`plugins/model-providers` 是推理模型供应商插件区，包含 `openrouter`、`anthropic`、`gemini`、`deepseek`、`xai`、`qwen-oauth`、`openai-codex` 等后端。它们通常在 `__init__.py` 中调用 `providers.register_provider(...)` 注册 `ProviderProfile`，由 `providers/__init__.py` 负责发现和覆盖规则。

`plugins/memory` 是记忆提供者插件区，包含 `honcho`、`mem0`、`supermemory`、`byterover`、`hindsight`、`holographic`、`openviking`、`retaindb`。这类插件是“同一时间只能激活一个”的 exclusive 类能力，通过 `memory.provider` 选择。

`plugins/context_engine` 是上下文引擎插件区。当前片段显示它有独立发现器，但一级列表没有展开出具体引擎子目录；根据当前片段推断，它用于加载实现 `agent.context_engine.ContextEngine` 的插件，并通过 `context.engine` 选择。

`plugins/image_gen`、`plugins/video_gen`、`plugins/web`、`plugins/browser` 是工具后端类插件区。它们分别提供图像生成、视频生成、网页搜索/抽取、浏览器能力的不同后端，例如 `image_gen/openai`、`image_gen/fal`、`web/tavily`、`web/searxng`、`browser/browserbase` 等。它们一般是 `kind: backend`，内置后端会自动加载，具体使用哪个由相应配置如 `image_gen.provider`、`web.provider` 等决定。

`plugins/platforms` 是网关平台适配器插件区，包含 `discord`、`google_chat`、`irc`、`line`、`mattermost`、`ntfy`、`simplex`、`teams` 等。插件通过 `ctx.register_platform(...)` 注册到 `gateway.platform_registry`，使网关可以识别新的消息平台。

`plugins/observability` 目前包含 `langfuse`，偏向日志、指标、追踪等观测能力。`plugins/dashboard_auth` 提供 Dashboard 认证后端。`plugins/kanban`、`plugins/hermes-achievements`、`plugins/example-dashboard` 带有 dashboard 子目录，说明它们还包含前端或控制台展示相关资源。

`plugins/disk-cleanup`、`plugins/google_meet`、`plugins/security-guidance`、`plugins/spotify`、`plugins/teams_pipeline` 是较独立的功能插件。它们通常有自己的 `plugin.yaml` 和 `register(ctx)`，可能注册工具、CLI 子命令、生命周期 hook 或外部服务集成。

## 关键入口

通用插件系统的核心入口是 `hermes_cli/plugins.py`。其中 `PluginManager.discover_and_load()` 负责扫描插件来源、读取 `plugin.yaml`、处理启用/禁用策略、导入模块并调用 `register(ctx)`。模块级函数 `discover_plugins()` 是外部触发发现的常用入口，`get_plugin_manager()` 返回全局单例，`invoke_hook()` 用来调用插件注册的生命周期 hook。

插件向宿主暴露能力的关键对象是 `PluginContext`。它提供 `register_tool()`、`register_hook()`、`register_cli_command()`、`register_image_gen_provider()`、`register_video_gen_provider()`、`register_web_search_provider()`、`register_platform()`、`register_dashboard_auth_provider()`、`register_auxiliary_task()`、`register_skill()` 等方法。插件作者主要面向的是这个上下文对象，而不是直接改核心代码。

模型供应商插件的入口是 `providers/__init__.py`，不是 `hermes_cli/plugins.py`。`plugins/model-providers/<name>/__init__.py` 被发现后调用 `register_provider(profile)`，后续 `get_provider_profile()` 或 `list_providers()` 触发懒加载。这里有一个重要规则：用户目录中的同名 provider 可以覆盖内置 provider。

记忆插件入口是 `plugins/memory/__init__.py`，核心函数是 `discover_memory_providers()`、`load_memory_provider(name)`、`discover_plugin_cli_commands()`。上下文引擎入口是 `plugins/context_engine/__init__.py`，核心函数是 `discover_context_engines()` 和 `load_context_engine(name)`。

## 主流程位置

通用插件发现通常发生在核心运行路径需要插件能力之前。`model_tools.py` 会导入并调用 `discover_plugins()`，这使插件工具和 hook 能进入工具编排流程。`cli.py`、`hermes_cli/main.py`、`gateway/run.py`、`gateway/config.py`、`hermes_cli/gateway.py`、`hermes_cli/oneshot.py` 中也有显式调用，用于 CLI、Gateway、一次性任务和配置界面提前加载插件。

主流程可以概括为：扫描插件目录或 entry point；解析 `plugin.yaml` 为 `PluginManifest`；根据 `kind`、来源和配置判断是否加载；导入插件模块；调用 `register(ctx)`；插件通过 `ctx` 写入工具注册表、provider 注册表、平台注册表、hook 列表或 CLI 命令表；运行期由工具调用、模型路由、Gateway、CLI 或生命周期事件消费这些注册结果。

通用插件扫描支持两种布局：`plugins/<plugin>/plugin.yaml` 这种 flat 布局，以及 `plugins/<category>/<plugin>/plugin.yaml` 这种 category 布局，例如 `image_gen/openai`。但 `memory`、`context_engine`、`model-providers` 不是普通通用插件路径：它们被通用扫描记录或跳过，实际加载由各自专用发现器负责。

## 推荐阅读顺序

建议先读 `hermes_cli/plugins.py`，重点看 `PluginManifest`、`PluginContext`、`PluginManager.discover_and_load()`、`_scan_directory()`、`_load_plugin()`、`invoke_hook()`，理解通用插件的生命周期。

第二步读 `plugins/disk-cleanup/plugin.yaml` 和 `plugins/disk-cleanup/__init__.py` 这类独立插件，用最小样例理解 `plugin.yaml` + `register(ctx)` 的常规写法。

第三步读 `plugins/image_gen/openai/__init__.py` 或 `plugins/web/tavily/__init__.py`，理解 backend 类插件如何注册 provider，并由配置选择实际后端。

第四步读 `providers/__init__.py` 和 `plugins/model-providers/README.md`，理解模型 provider 为什么不走通用导入流程，以及 `register_provider()` 的懒加载和覆盖规则。

第五步读 `plugins/memory/__init__.py`、`agent/memory_provider.py` 和某个记忆插件如 `plugins/memory/honcho/__init__.py`，理解 exclusive 插件和 `memory.provider` 的关系。

最后再读 `plugins/context_engine/__init__.py`、`agent/context_engine.py`，以及 `agent/agent_init.py` 中加载上下文引擎的位置，补齐上下文压缩/外部上下文引擎的运行链路。

## 常见误区

不要以为 `plugins` 下所有目录都由同一个加载器导入。`model-providers`、`memory`、`context_engine` 都有自己的发现路径，通用 `PluginManager` 对它们会跳过、记录或只做元信息处理。

不要以为加了 `plugin.yaml` 就一定会启用。通用 standalone 插件默认受 `plugins.enabled` 控制；内置 backend 和 platform 插件会自动加载；memory 这类 exclusive 插件则通过 `memory.provider` 激活。

不要把模型 provider 插件写成普通 `register(ctx)` 工具插件。模型 provider 的主入口是 `providers.register_provider(ProviderProfile(...))`，重复由通用插件系统导入反而会破坏 provider 覆盖语义。

不要在插件里直接修改 `run_agent.py`、`cli.py`、`gateway/run.py` 等核心文件。现有设计意图是通过 `PluginContext` 扩展能力；如果缺注册点，应扩展通用插件表面，而不是把某个插件硬编码进核心。

不要把 `plugins/memory/<name>` 当作可以无限新增的普通内置目录。根据仓库说明，内置 memory provider 集合是关闭的，新记忆后端应作为用户或外部插件安装，而不是继续加到这个树里。
