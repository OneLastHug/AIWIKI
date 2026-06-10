# 文件：toolsets.py

## 一句话定位

`toolsets.py` 是 Hermes Agent 的“工具集目录和解析器”：它把底层工具名组织成可启用、可禁用、可组合的平台/场景 toolset，并为 `model_tools.py` 装配 LLM tool schema 提供工具名清单。

## 它暴露/定义了什么

这个文件的核心数据是 `TOOLSETS`，每个条目通常包含 `description`、`tools`、`includes`。`tools` 是直接包含的工具名，`includes` 用来组合其他 toolset，例如 `debugging` 包含 `web` 和 `file`，`hermes-gateway` 则汇总多个消息平台 toolset。

它还定义了两个重要基础列表：`_HERMES_CORE_TOOLS` 和 `_HERMES_WEBHOOK_SAFE_TOOLS`。前者是 CLI、Telegram、Slack、cron 等多数平台默认继承的核心工具集合；后者是 webhook 场景的受限安全集合，用于避免第三方 webhook 内容通过 prompt injection 获得本地文件或命令执行能力。

公开函数包括 `get_toolset()`、`resolve_toolset()`、`resolve_multiple_toolsets()`、`get_all_toolsets()`、`get_toolset_names()`、`validate_toolset()`、`create_custom_toolset()`、`get_toolset_info()`。其中真正影响运行时的是查询、校验和递归解析函数；`__main__` 部分只是演示输出。

## 谁调用它

最关键调用方是 `model_tools.py`。它从 `toolsets.py` 导入 `resolve_toolset` 和 `validate_toolset`，在 `get_tool_definitions()` 的内部流程中根据 `enabled_toolsets`、`disabled_toolsets` 计算最终允许暴露给模型的工具名，再交给 `tools.registry` 取 schema。

配置和 UI 层也会调用它。`hermes_cli/tools_config.py` 用 `resolve_toolset()` 和 `TOOLSETS` 推导某个平台实际启用哪些单项工具集，处理默认平台 toolset、显式配置、插件 toolset、MCP server 和全局 `agent.disabled_toolsets`。`hermes_cli/web_server.py` 的工具配置 API、`hermes_cli/kanban_db.py` 的 assignee profile 校验、`acp_adapter` 的编辑器集成也会间接依赖它。根据当前片段推断，`run_agent.py` 通常不直接解析 `TOOLSETS`，而是通过 `model_tools.get_tool_definitions()` 间接使用。

## 它调用谁

`toolsets.py` 自身尽量保持轻量，主要调用 `tools.registry.registry` 来合并插件注册的工具和 toolset。`get_toolset()` 会从 registry 读取某个 toolset 下的动态工具、处理 alias target，并为插件或 MCP server 生成临时定义。`get_all_toolsets()`、`get_toolset_names()`、`validate_toolset()` 也会查询 registry 中的插件 toolset 和别名。

`resolve_toolset()` 在处理 `hermes-<platform>` 但静态 `TOOLSETS` 不存在时，会尝试调用 `gateway.platform_registry.platform_registry` 判断插件平台是否已注册；若存在，就把 `_HERMES_CORE_TOOLS` 与该平台注册的工具合并成自动平台 toolset。

## 核心流程

运行时通常从用户或配置得到 `enabled_toolsets`。`model_tools._compute_tool_definitions()` 逐个调用 `validate_toolset()` 判断名称是否有效，再调用 `resolve_toolset()` 展开工具名。若配置了 `disabled_toolsets`，同样解析后从集合中扣除。最后，工具名集合交给 `registry.get_definitions()`，只有注册存在且 `check_fn` 通过的工具才会真正出现在模型 schema 中。

`resolve_toolset()` 的解析逻辑是递归的：先处理特殊别名 `all` 和 `*`，表示展开所有已知 toolset；再用 `visited` 防止循环依赖和 diamond dependency 重复展开；随后读取当前 toolset 的直接 `tools`，再递归展开 `includes`，最终返回排序后的去重工具名列表。

插件/MCP 处理是这个文件的另一个重点。静态 `TOOLSETS` 没有覆盖的 toolset，可能来自 `tools.registry`。因此新增插件工具不一定要改 `TOOLSETS`，只要注册到 registry 并暴露 toolset 名，就能被 `get_all_toolsets()`、`validate_toolset()` 和 `resolve_toolset()` 纳入正常链路。

## 关键函数的高层作用

`get_toolset(name)` 负责返回单个 toolset 定义。它不仅读取静态 `TOOLSETS`，还会把 registry 中同名 toolset 的工具合并进去，并为插件 toolset 或 MCP alias 生成描述和工具列表。

`resolve_toolset(name, visited=None)` 是最关键的展开函数，负责把一个逻辑 toolset 变成最终工具名列表。它处理 `all`、递归 includes、循环保护、插件平台自动 toolset，是模型工具暴露链路的核心入口。

`get_all_toolsets()` 和 `get_toolset_names()` 负责枚举静态与插件 toolset，用于 UI、配置页、帮助信息和默认全量展开。

`validate_toolset(name)` 用于判断配置中的 toolset 名是否可用，接受静态名称、插件名称、registry alias，以及 `all`、`*` 这类特殊别名。

`create_custom_toolset()` 是运行时写入 `TOOLSETS` 的简易扩展点；它不会持久化配置，也不会自动注册工具 schema，只是增加一个组合定义。

`get_toolset_info()` 生成包含直接工具、includes、resolved tools、工具数量、是否组合型的详情，适合展示和调试。

## 修改风险

最大风险是误改 `_HERMES_CORE_TOOLS`。它被多个 `hermes-*` 平台复用，添加一个工具可能让 CLI、cron、Telegram、Slack、Email 等平台同时获得新能力；删除一个工具则可能造成大量平台默认能力回退。尤其是 `terminal`、`write_file`、`patch`、`send_message`、`computer_use`、`kanban_*` 这类有安全或运行环境门槛的工具，必须确认 registry 的 `check_fn`、平台默认值和 UI 开关是否匹配。

第二个风险是组合 toolset 的包含关系。`includes` 递归展开，某个小 toolset 被 `hermes-gateway` 或 `all` 间接包含后，影响面会放大。循环依赖不会崩溃，但会静默跳过，容易造成“配置看起来包含了，实际工具缺失”的排查困难。

第三个风险是静态定义与插件/MCP 动态注册的边界。`get_toolset()`、`validate_toolset()` 已经兼容 registry toolset 和 alias；如果绕过这些函数直接读 `TOOLSETS`，就会漏掉插件能力。新增调用方应优先使用 `get_all_toolsets()`、`get_toolset_names()`、`resolve_toolset()`，而不是自行遍历字典。

第四个风险是安全场景差异。`hermes-webhook` 明确使用 `_HERMES_WEBHOOK_SAFE_TOOLS`，不能为了“能力一致”改成 `_HERMES_CORE_TOOLS`。webhook 输入可能来自不可信第三方内容，这里的受限设计是安全边界，不只是功能裁剪。
