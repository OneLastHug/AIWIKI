# 文件：platform/reworkd_platform/web/api/agent/tools/tools.py

## 一句话定位

`tools.py` 是 Agent 工具系统的“注册表 + 名称解析层”：它集中声明哪些 `Tool` 子类对 Agent 可见，负责把前端或模型传入的工具名解析成具体工具类，并提供默认工具兜底。

## 它暴露/定义了什么

这个文件没有定义新的工具实现，只定义一组工具管理函数：

- `get_user_tools(tool_names, user, crud)`：根据用户选择的工具名生成工具类列表，并附加默认工具，再按 `dynamic_available()` 做用户态可用性过滤。
- `get_available_tools()`：返回系统层面可被识别的工具集合，即 external tools 加 default tools。
- `get_available_tools_names()`：返回所有可识别工具的规范化名称。
- `get_external_tools()`：声明外部/可选工具，目前是 `Image`、`Code`、`SID`，`Wikipedia` 被注释掉。
- `get_default_tools()`：声明默认工具，目前只有 `Search`。
- `get_tool_from_name(tool_name)`：把字符串工具名解析为 `Tool` 子类，找不到时返回默认工具。
- `get_default_tool()` / `get_default_tool_name()`：默认工具固定为 `Search`。
- `get_tool_name()` / `format_tool_name()`：把工具类名统一转为小写名称。
- `get_tools_overview()`：把工具列表格式化为 `name: description` 文本，并去重。

它依赖的核心类型是 `reworkd_platform.web.api.agent.tools.tool.Tool`。所有被注册的工具都必须遵守 `Tool` 基类约定：有类级别描述字段，并实现异步 `call()`。

## 谁调用它

主要调用方有四类。

第一类是 Agent 执行服务：`platform/reworkd_platform/web/api/agent/agent_service/open_ai_agent_service.py`。其中 `analyze_task_agent()` 调用 `get_user_tools()` 获取本轮可供模型选择的工具，再交给 `get_tool_function()` 转成 OpenAI function schema；`execute_task_agent()` 调用 `get_tool_from_name()` 根据分析结果实例化工具并执行；异常兜底时还使用 `get_default_tool()` 和 `get_tool_name()`。

第二类是 API 路由：`platform/reworkd_platform/web/api/agent/views.py` 的 `GET /tools` 调用 `get_external_tools()` 和 `get_tool_name()`，用于返回前端可展示的外部工具列表。这里会额外检查每个工具的静态 `available()`。

第三类是数据校验：`platform/reworkd_platform/web/api/agent/analysis.py` 的 `Analysis` validator 调用 `get_available_tools_names()` 验证模型返回的 `action` 是否是合法工具名，也用 `get_default_tool_name()` 构造默认分析结果。

第四类是函数描述生成与测试：`tools/open_ai_function.py` 使用 `get_tool_name()` 生成 function name；`tests/agent/test_tools.py` 覆盖名称格式化、默认工具、概览去重、名称解析等行为。需要注意，当前测试中仍断言 `Conclude` 可由 `get_tool_from_name()` 解析，但当前注册表没有把 `Conclude` 放进 `get_available_tools()`，根据当前片段推断这可能是测试与实现不同步的遗留问题。

## 它调用谁

`tools.py` 直接导入并注册这些工具类：`Search`、`Image`、`Code`、`SID`。它还依赖 `Tool` 基类、`UserBase` 用户模型和 `OAuthCrud`。

其中 `get_user_tools()` 会调用每个工具类的 `dynamic_available(user, crud)`。默认实现来自 `Tool`，总是返回 `True`；`SID` 覆盖了该方法，会通过 `OAuthCrud.get_installation_by_user_id(user_id=user.id, provider="sid")` 检查用户是否安装并保存了 SID access token。也就是说，用户态可用性主要通过工具类自身的静态/动态方法表达，而不是在注册表里写业务条件。

`get_available_tools()` 本身只拼接 `get_external_tools()` 和 `get_default_tools()`，不调用工具的 `available()`。静态 `available()` 目前主要由 `views.py` 的工具列表接口使用，例如 `Search.available()` 依赖 Serper 配置，`SID.available()` 依赖 `settings.sid_enabled`。

## 核心流程

一次典型 Agent 工具使用流程如下。

用户或前端提交可选工具名后，`OpenAIAgentService.analyze_task_agent()` 调用 `get_user_tools(tool_names, user, oauth_crud)`。这个函数先把每个名称交给 `get_tool_from_name()` 解析成工具类，再追加默认工具 `Search`。随后逐个调用 `dynamic_available()`，过滤掉当前用户没有授权或不能使用的工具。

过滤后的工具类列表会被 `get_tool_function()` 转成 OpenAI function 描述，交给模型选择。模型返回 `function_call.name` 后，系统构造 `Analysis(action=..., reasoning=..., arg=...)`。`Analysis` 会通过 `get_available_tools_names()` 校验 action 是否在注册表中。

执行阶段，`OpenAIAgentService.execute_task_agent()` 调用 `get_tool_from_name(analysis.action)`，拿到工具类后用当前 `model` 和语言实例化，再调用工具实例的 `call(goal, task, arg, user, oauth_crud)`。如果传入的 action 不存在，`get_tool_from_name()` 不抛错，而是返回 `Search` 作为兜底。

工具展示流程则更简单：`views.py` 的 `GET /tools` 只读取 `get_external_tools()`，过滤 `tool.available()`，然后返回 `name`、`public_description`、`image_url` 等信息给前端。因此默认工具 `Search` 不会作为外部工具卡片展示，除非路由逻辑被改动。

## 关键函数的高层作用

`get_user_tools()` 是最关键的入口。它把“用户请求的工具名”转换成“本轮模型可调用的工具类”，并注入默认工具。它的行为会直接影响模型在分析阶段能选择哪些 function，也影响 SID 这类需要用户授权的工具是否出现。

`get_tool_from_name()` 是执行阶段的安全兜底。它遍历 `get_available_tools()`，用小写名称匹配工具类名；匹配失败返回 `Search`。这个设计提升了容错性，但也会掩盖拼写错误、注册遗漏或模型返回非法工具名的问题。

`get_available_tools()` 是全局合法工具集合。`Analysis` 校验、名称解析、默认可用工具名都依赖它。新增或移除工具时，最核心的改动点通常就是 `get_external_tools()` 或 `get_default_tools()`。

`get_external_tools()` 和 `get_default_tools()` 表达产品语义上的分类：外部工具用于前端展示和用户选择，默认工具总是被加入 Agent 分析候选。当前默认工具只有 `Search`。

`get_tools_overview()` 只是辅助格式化函数，主要价值是把工具描述聚合成文本，并通过 `set` 去重；但由于 `set` 不保证顺序，它不适合用于要求稳定输出顺序的场景。

## 修改风险

最大风险是“注册表改动会同时影响模型可选 function、执行解析、校验和前端展示”。新增工具如果只创建了 `Tool` 子类但没有加入 `get_external_tools()` 或 `get_default_tools()`，模型和 API 都不会识别它；反过来，如果移除工具但历史数据或模型仍返回该名称，执行阶段会静默落到 `Search`，行为可能难以排查。

第二个风险是静态可用性与动态可用性不一致。`GET /tools` 会检查 `available()`，但 `get_user_tools()` 只检查 `dynamic_available()`。因此某些配置不可用的工具可能不在前端展示，却仍可能通过传入名称进入分析候选；默认 `Search` 也会无条件追加，尽管 `Search.available()` 可能为 `False`。根据当前片段推断，`Search.call()` 自身有失败后降级到 `Reason` 的逻辑，但注册层并不表达这个降级关系。

第三个风险是默认兜底会隐藏错误。`get_tool_from_name("NonExistingTool")` 返回 `Search`，适合保证 Agent 不崩溃，但对调试、审计和测试不友好。若要改成抛错，需要同步调整 `Analysis` 校验、服务层异常处理和现有测试预期。

第四个风险是名称规范过于简单。`format_tool_name()` 只是 `lower()`，所以工具名必须依赖类名小写结果，例如 `SID` 变成 `sid`。如果未来需要短横线、下划线、别名或向后兼容旧名称，这个文件需要扩展映射关系，不能只靠类名推导。

第五个风险是测试可能已经滞后。`tests/agent/test_tools.py` 中对 `Conclude` 的解析断言与当前注册表不一致；修改注册列表前应先确认产品是否仍需要 `Conclude`、`Reason` 这类内部工具对外可解析，避免为了通过测试而错误暴露不该由模型直接选择的工具。
