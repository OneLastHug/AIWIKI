# 文件：tools/registry.py

## 一句话定位

`tools/registry.py` 是 Hermes 工具系统的中心注册表：负责发现内置工具模块、接收各工具的自注册信息、按 toolset 输出模型可见的 OpenAI function schema，并在运行时按工具名分发调用。

## 它暴露/定义了什么

这个文件主要定义四类能力。

第一类是工具发现：`discover_builtin_tools()` 会扫描 `tools/*.py`，通过 AST 判断模块顶层是否存在 `registry.register(...)`，再导入这些模块。导入本身会触发各工具文件的自注册。

第二类是数据结构：`ToolEntry` 保存单个工具的元数据，包括 `name`、`toolset`、`schema`、`handler`、`check_fn`、`requires_env`、`is_async`、`emoji`、`max_result_size_chars`、`dynamic_schema_overrides` 等。

第三类是核心注册表：`ToolRegistry` 管理 `_tools`、`_toolset_checks`、`_toolset_aliases` 和 `_generation`。模块底部创建全局单例 `registry = ToolRegistry()`，这是外部最常用的入口。

第四类是返回值辅助函数：`tool_error()` 和 `tool_result()` 统一把工具执行结果序列化为 JSON 字符串，供各工具 handler 复用。

## 谁调用它

最直接的调用者是 `model_tools.py`。它在模块加载时执行 `discover_builtin_tools()`，随后用 `registry.get_definitions()` 生成传给模型 API 的工具定义，并在 `handle_function_call()` 中通过 `registry.dispatch()` 执行真实工具。

大量 `tools/*.py` 文件也调用它，例如 `tools/file_tools.py`、`tools/delegate_tool.py`、`tools/browser_cdp_tool.py`、`tools/skills_tool.py` 等。这些模块通常在文件底部 `from tools.registry import registry`，然后调用 `registry.register(...)` 声明工具名、toolset、schema、handler 和可用性检查。

`toolsets.py` 也会读取 registry，例如 `get_toolset()`、`resolve_toolset()`、`get_all_toolsets()` 会把静态 `TOOLSETS` 与插件或 MCP 动态注册的 toolset 合并。测试侧则有 `tests/tools/test_registry.py` 覆盖发现和注册行为。

## 它调用谁

`tools/registry.py` 本身刻意不导入具体工具模块和 `model_tools.py`，以降低循环依赖风险。它调用的主要是标准库：`ast` 用于静态识别顶层 `registry.register(...)`，`importlib` 用于导入工具模块，`json` 用于工具结果序列化，`threading` 和 `time` 用于可用性检查缓存。

运行分发时有两个延迟导入：异步工具通过 `from model_tools import _run_async` 桥接到同步调用；异常清洗通过 `from model_tools import _sanitize_tool_error`。这两个导入放在 `dispatch()` 内部，说明作者有意避免模块加载阶段形成强循环。

`get_max_result_size()` 在需要默认值时延迟导入 `tools.budget_config.DEFAULT_RESULT_SIZE_CHARS`。

## 核心流程

工具注册流程是：`model_tools.py` 加载时调用 `discover_builtin_tools()`；该函数扫描 `tools` 目录，过滤 `__init__.py`、`registry.py`、`mcp_tool.py`，并只导入顶层包含 `registry.register(...)` 的模块；工具模块被导入后执行 `registry.register()`；注册表把工具封装为 `ToolEntry`，写入 `_tools`，必要时记录 toolset 的 `check_fn`，并递增 `_generation`。

工具定义生成流程是：上层先用 `toolsets.py` 解析 enabled/disabled toolsets 得到工具名集合；再调用 `registry.get_definitions(tool_names)`；registry 对每个工具检查 `check_fn`，失败则不暴露给模型；通过检查后把 schema 包装成 `{"type": "function", "function": ...}`；如果工具提供 `dynamic_schema_overrides`，会在此时动态覆盖 schema 字段。

工具执行流程是：`model_tools.handle_function_call()` 先处理参数转换、插件 hook、审批和特殊桥接工具；最终调用 `registry.dispatch(function_name, args, ...)`。`dispatch()` 查找 `ToolEntry`，同步 handler 直接执行，异步 handler 交给 `_run_async()`，所有异常都会被捕获并返回 JSON error。

## 关键函数的高层作用

`discover_builtin_tools()` 是内置工具自动发现入口。它的关键点不是扫描所有 Python 文件后盲目导入，而是先用 AST 判断是否有顶层注册调用，降低误导入辅助模块的概率。

`register()` 是工具接入的核心入口。它负责处理同名工具冲突：不同 toolset 的同名工具默认拒绝覆盖；MCP 到 MCP 的覆盖允许；插件若要替换已有工具必须显式传 `override=True`。这对安全和可审计性很重要。

`deregister()` 用于动态工具刷新，尤其是 MCP 工具列表变化。它会删除工具，并在该 toolset 没有剩余工具时清理 toolset check 和 alias。

`get_definitions()` 是模型可见工具 schema 的出口。它承担可用性过滤、schema 名称补齐、动态 schema 覆盖和 OpenAI function 格式包装。`check_fn` 结果会通过 `_check_fn_cached()` 做约 30 秒 TTL 缓存，避免长生命周期 CLI 或 gateway 反复探测 Docker、Playwright、SDK、环境变量等外部状态。

`dispatch()` 是执行出口。它只按名字找到 handler 并调用，不负责复杂业务策略；前置 hook、审批、tool_search 桥接等逻辑在 `model_tools.py` 中完成。这个边界让 registry 保持相对通用。

`get_toolset_requirements()`、`get_available_toolsets()`、`check_tool_availability()` 等是兼容和 UI 查询辅助，用于把 registry 内部状态转换成旧接口或展示需要的数据。

## 修改风险

最大风险是破坏工具发现链路。`discover_builtin_tools()` 依赖“顶层 `registry.register(...)`”这个约定；如果工具注册被包进函数、工厂或条件分支，可能不会被自动发现。反过来，如果 AST 判断放宽，可能导入不该导入的模块，带来副作用。

第二个风险是同名覆盖策略。`register()` 当前把非 MCP、非显式 override 的跨 toolset 覆盖视为错误。放松这里可能让插件或动态工具静默替换内置工具，影响安全边界；收紧这里则可能破坏 MCP 刷新或已有插件替换场景。

第三个风险是缓存一致性。`_generation` 被 `model_tools.get_tool_definitions()` 用作缓存键的一部分；注册、注销、alias 变化都必须递增它。新增会改变工具可见性的状态时，如果忘记 bump generation，长生命周期进程可能继续使用旧 schema。

第四个风险是循环依赖。文件顶部保持轻依赖，`dispatch()` 和 `get_max_result_size()` 使用延迟导入。把 `model_tools.py`、具体工具模块或复杂配置加载提前到模块顶层，可能重新引入循环导入或 gateway 启动阻塞。

第五个风险是错误返回格式。工具 handler 约定返回 JSON 字符串，`tool_error()`、`tool_result()` 和 `dispatch()` 都围绕这个约定设计。若改成返回 dict 或抛出异常给上层，可能影响模型消息组装、插件 hook、日志和测试。

第六个风险是线程安全。registry 支持 MCP 动态刷新和多线程读取，依赖 `RLock`、快照读取和 TTL cache lock。修改 `_tools`、`_toolset_checks`、`_toolset_aliases` 的代码如果绕过锁，可能在 gateway 或并行工具调用中产生不一致。
