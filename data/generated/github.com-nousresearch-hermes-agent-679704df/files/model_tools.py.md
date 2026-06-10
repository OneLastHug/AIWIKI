# 文件：model_tools.py

## 一句话定位

`model_tools.py` 是 Hermes Agent 的“工具编排门面”：它不直接实现具体工具能力，而是在 `tools.registry` 和上层 Agent/CLI/Gateway 之间，负责发现工具、筛选工具 schema、处理动态 schema、分发模型发起的 tool call，并兼容旧版工具集接口。

## 它暴露/定义了什么

它主要暴露两类能力。第一类是给模型请求准备工具定义：`get_tool_definitions()` 返回 OpenAI function tool 格式的 schema 列表，并支持 `enabled_toolsets`、`disabled_toolsets`、`quiet_mode`、`skip_tool_search_assembly` 等参数。第二类是执行工具调用：`handle_function_call()` 接收模型给出的 `function_name` 和 `function_args`，完成参数修正、权限/插件钩子检查、特殊桥接工具处理，再转交注册表执行。

此外它还保留了一组兼容接口和常量：`TOOL_TO_TOOLSET_MAP`、`TOOLSET_REQUIREMENTS`、`get_all_tool_names()`、`get_toolset_for_tool()`、`get_available_toolsets()`、`check_toolset_requirements()`、`check_tool_availability()`。这些多数是对 `registry` 查询方法的薄封装，用来让旧代码不用直接依赖 `tools.registry`。

文件内部还定义了 `_run_async()` 这一同步到异步的桥接函数，供异步工具 handler 在同步调用链中运行；`coerce_tool_args()` 负责按 JSON Schema 修正模型输出参数类型；`_sanitize_tool_error()` 负责清理工具异常文本，避免结构化标签、代码围栏等内容进入模型上下文造成干扰。

## 谁调用它

最核心调用者是 `run_agent.py` 和 `agent/tool_executor.py`。Agent 初始化阶段通过 `get_tool_definitions()` 构造 `agent.tools` 和 `valid_tool_names`，模型返回 tool call 后再通过 `handle_function_call()` 执行实际工具。`cli.py` 在工具列表展示、配置变更后刷新 agent 工具集时也调用它。`gateway/run.py`、`tui_gateway/server.py`、`acp_adapter/server.py` 在各自入口中刷新或获取会话工具定义。`batch_runner.py` 使用 `TOOL_TO_TOOLSET_MAP` 推导可用工具集合。`hermes_cli/banner.py`、`hermes_cli/doctor.py` 使用可用性检查和需求信息展示诊断结果。部分工具也反向依赖它，例如 `tools/code_execution_tool.py` 会在沙箱内通过 `handle_function_call()` 调用允许的 Hermes 工具。

## 它调用谁

它的基础依赖是 `tools.registry`：模块导入时调用 `discover_builtin_tools()`，触发 `tools/*.py` 中的 `registry.register()`；之后通过 `registry.get_definitions()` 获取 schema，通过 `registry.dispatch()` 执行工具。工具集解析依赖 `toolsets.resolve_toolset()` 和 `toolsets.validate_toolset()`。插件发现依赖 `hermes_cli.plugins.discover_plugins()`，工具执行前后还会调用 `get_pre_tool_call_block_message()`、`invoke_hook()` 等插件钩子。

它还会按需调用多个动态能力模块：`tools.code_execution_tool` 用于重建 `execute_code` schema；`tools.discord_tool` 用于按 Discord 权限和配置生成动态 schema；`tools.schema_sanitizer` 用于清洗 schema；`tools.tool_search` 用于把大量 MCP/plugin 工具折叠到 `tool_search`、`tool_describe`、`tool_call` 桥接工具后面；`hermes_cli.config` 和 `agent.model_metadata` 用于读取当前模型上下文长度。文件编辑审批路径会调用 `acp_adapter.edit_approval.maybe_require_edit_approval()`。

## 核心流程

工具发现发生在模块导入期。`discover_builtin_tools()` 扫描并导入自注册工具模块，随后尝试发现插件工具。注册表生成 `TOOL_TO_TOOLSET_MAP` 和 `TOOLSET_REQUIREMENTS`，供旧接口继续使用。

生成工具 schema 时，`get_tool_definitions()` 先在 `quiet_mode=True` 下尝试命中缓存。缓存 key 包括启用/禁用工具集、`registry._generation`、配置文件指纹、Kanban 环境变量和是否跳过 tool search 组装。未命中时进入 `_compute_tool_definitions()`：先把工具集解析成具体工具名，再扣除禁用工具集；随后向 `registry.get_definitions()` 请求通过可用性检查的工具 schema；接着按当前可用工具重建 `execute_code`、Discord、浏览器描述等动态 schema；再进行 schema sanitizer；最后根据上下文窗口和配置决定是否启用 Tool Search 渐进披露，把大量非核心工具隐藏在桥接工具后。

执行工具时，`handle_function_call()` 先按注册 schema 修正参数类型，例如把 `"42"` 转成整数、把 `"true"` 转成布尔值、把裸字符串包装成数组。然后优先处理 `tool_search`、`tool_describe`、`tool_call` 桥接工具，其中 `tool_call` 会解析出底层工具名并递归调用自身，同时检查该工具确实属于当前会话可见的延迟工具集合。普通工具路径会拒绝 `todo`、`memory`、`session_search`、`delegate_task` 这类必须由 Agent loop 直接处理的工具；随后执行插件 `pre_tool_call`、ACP 编辑审批、读循环状态通知，最后调用 `registry.dispatch()`。执行完成后触发 `post_tool_call` 和 `transform_tool_result` 钩子，并返回 JSON 字符串结果。异常会被 `_sanitize_tool_error()` 清理后包装成 JSON error。

## 关键函数的高层作用

`get_tool_definitions()` 是对外 schema 入口，重点是缓存和保持返回列表不污染缓存，避免长生命周期 Gateway 中重复工具名累积。`_compute_tool_definitions()` 是实际装配逻辑，承担工具集解析、可用性过滤、动态 schema 更新、schema 兼容清洗和 Tool Search 组装。`handle_function_call()` 是执行入口，承担安全边界、插件边界、桥接工具展开和注册表分发。`coerce_tool_args()` 提升模型工具调用容错率，降低因类型漂移导致的工具失败。`_run_async()` 是工具层异步运行的统一桥，避免不同入口、线程和事件循环之间出现 “Event loop is closed” 或运行中 loop 冲突。`_sanitize_tool_error()` 是防御性清理，减少工具异常文本对后续模型解析的污染。其余查询函数基本是 `registry` 的兼容包装。

## 修改风险

这个文件位于工具系统的中心路径，风险集中在三类。第一是工具可见性风险：`enabled_toolsets`、`disabled_toolsets`、Tool Search 桥接和 `_last_resolved_tool_names` 共同决定模型能看到和能调用什么，改错会导致受限会话越权看到工具，或正常会话丢失工具。第二是缓存一致性风险：`get_tool_definitions()` 缓存依赖 `registry._generation` 和配置指纹，动态插件、MCP 刷新、Discord 权限、代码执行模式等变化如果没有正确失效，模型会拿到过期 schema。第三是执行链风险：`handle_function_call()` 同时承载插件钩子、ACP 编辑审批、沙箱工具传递、错误清理和结果转换，任何顺序调整都可能破坏安全检查或让插件重复触发。

修改时要特别谨慎处理 Agent loop 工具，例如 `todo`、`memory`、`session_search`、`delegate_task` 不应直接走 `registry.dispatch()`，因为它们依赖 Agent 实例状态。涉及 `execute_code` 时也要保留按会话传入 `enabled_tools` 的逻辑，否则子 agent 或沙箱可能拿到错误的可用工具集合。涉及异步工具时不要绕过 `_run_async()`，因为注册表和部分工具已经把它作为同步调用异步 handler 的统一入口。总体上，新增工具优先在 `tools/*.py` 或插件中注册，再通过 `toolsets.py` 暴露；只有当需要改变工具筛选、动态 schema、分发安全边界时，才应修改 `model_tools.py`。
