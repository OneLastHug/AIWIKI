# 文件：platform/reworkd_platform/web/api/agent/tools/tool.py

## 一句话定位

`platform/reworkd_platform/web/api/agent/tools/tool.py` 定义了 Agent 工具体系的抽象基类 `Tool`，它不是具体工具实现，而是约束所有工具必须具备的元信息、可用性判断入口和统一的异步执行接口 `call()`。

## 它暴露/定义了什么

这个文件核心只暴露一个抽象类：`Tool(ABC)`。

`Tool` 定义了几类契约：

- 工具展示与模型选择所需的类属性：`description`、`public_description`、`arg_description`、`image_url`。
- 运行时依赖：实例属性 `model: BaseChatModel` 和 `language: str`，由构造函数注入。
- 静态可用性接口：`available()`，默认返回 `True`。
- 动态可用性接口：`dynamic_available(user, oauth_crud)`，默认返回 `True`，用于按用户或 OAuth 状态筛选工具。
- 抽象执行接口：`call(goal, task, input_str, user, oauth_crud)`，返回 `lanarky.responses.StreamingResponse` 类型的流式响应。

它的设计重点是“接口统一”，让上层 Agent 不关心具体工具是搜索、代码、图片还是其他能力，只要按 `Tool` 协议实例化并调用 `call()` 即可。

## 谁调用它

直接继承 `Tool` 的具体工具包括 `platform/reworkd_platform/web/api/agent/tools/search.py` 中的 `Search`、`image.py` 中的 `Image`、`code.py` 中的 `Code`、`sidsearch.py` 中的 `SID`、`reason.py` 中的 `Reason`、`conclude.py` 中的 `Conclude`，以及 `wikipedia_search.py` 中的 `Wikipedia`。

工具注册与查询逻辑在 `platform/reworkd_platform/web/api/agent/tools/tools.py`。该文件通过 `Type[Tool]` 维护工具列表，例如 `get_external_tools()` 返回 `Image`、`Code`、`SID`，`get_default_tools()` 返回 `Search`。`get_user_tools()` 会把用户请求的工具和默认工具合并，再调用每个工具类的 `dynamic_available()` 过滤。

真正的运行调用来自 `platform/reworkd_platform/web/api/agent/agent_service/open_ai_agent_service.py`。其中 `analyze_task_agent()` 用工具元信息构造 OpenAI function 说明，`execute_task_agent()` 根据分析结果找到工具类，实例化后调用 `call()`。

## 它调用谁

`tool.py` 本身调用很少，主要是类型依赖和接口约束：

- `ABC`、`abstractmethod`：声明抽象基类和抽象方法。
- `BaseChatModel`：规定工具持有的语言模型类型。
- `StreamingResponse`：规定 `call()` 的返回形态是流式输出。
- `UserBase`：传入当前用户上下文。
- `OAuthCrud`：传入 OAuth 数据访问对象，让工具可以检查或使用用户授权信息。

文件内部没有业务逻辑调用外部服务。具体调用外部 API、LLM chain、数据库或摘要工具的行为都发生在各个子类中。

## 核心流程

整体流程可以概括为四步。

第一步，系统启动或请求处理时，上层通过 `tools.py` 维护的注册表获得可用工具类。每个工具类都必须继承 `Tool`，因此天然拥有统一的描述字段和执行接口。

第二步，`OpenAIAgentService.analyze_task_agent()` 调用 `get_user_tools(tool_names, user, oauth_crud)`，筛出当前用户可用的工具。随后 `open_ai_function.py` 的 `get_tool_function()` 读取工具类的 `description` 和 `arg_description`，把它们转换为 OpenAI function calling 所需的 schema。这里说明 `Tool` 的类属性不仅服务 UI，也直接影响模型如何选择工具和填写参数。

第三步，模型返回 `function_call` 后，`Analysis.action` 记录工具名，`Analysis.arg` 记录工具参数。`execute_task_agent()` 用 `get_tool_from_name()` 找到对应的 `Tool` 子类。

第四步，上层执行 `tool_class(self.model, self.settings.language).call(goal, task, analysis.arg, self.user, self.oauth_crud)`。也就是说，`Tool.__init__()` 注入模型和语言，`call()` 再接收目标、任务、输入参数、用户和 OAuth CRUD，最终由具体子类完成实际工作并返回流式响应。

## 关键函数的高层作用

`__init__(model, language)` 是所有工具实例的依赖注入口。它把当前 Agent 使用的聊天模型和输出语言保存到实例上，供子类在 `call()` 中继续调用 LLM、摘要链或降级工具。例如 `Search` 在搜索失败时会实例化 `Reason(self.model, self.language)` 作为 fallback。

`available()` 是静态开关，默认认为工具可用。具体工具可以覆盖它，例如 `Search.available()` 会根据配置里的搜索 API key 判断搜索工具是否启用。根据当前片段推断，这个方法更偏向全局环境级别的可用性，因为它不接收用户参数，依据是其签名没有 `user` 或 `oauth_crud`。

`dynamic_available(user, oauth_crud)` 是用户级可用性判断入口。默认返回 `True`，但它为需要 OAuth 授权或用户权限的工具预留了扩展点。`get_user_tools()` 明确会 await 这个方法，因此子类可以在这里异步查询数据库或授权状态。

`call(goal, task, input_str, user, oauth_crud)` 是最关键的抽象方法。它定义工具执行时必须接收完整上下文：`goal` 表示总体目标，`task` 表示当前任务，`input_str` 是模型选择工具时生成的参数，`user` 和 `oauth_crud` 提供用户与授权上下文。该方法被声明为 `abstractmethod`，所以任何具体工具不实现它都无法正常实例化。

## 修改风险

最高风险是修改 `call()` 的签名。`OpenAIAgentService.execute_task_agent()`、多个工具子类以及工具间 fallback 都依赖当前参数顺序和异步返回形态。即使 Python 允许部分子类用 `*args, **kwargs` 放宽签名，上层仍然按固定方式传入 `goal, task, arg, user, oauth_crud`，改动会引发运行时错误或丢失用户授权上下文。

第二个风险是修改 `description` 和 `arg_description` 的语义。它们会进入 `get_tool_function()`，直接影响模型 function calling 的工具选择和参数生成。描述写得过窄、过宽或不准确，可能不会导致代码报错，但会导致 Agent 选错工具或生成空参数。

第三个风险是更改 `available()`、`dynamic_available()` 的默认行为。默认返回 `True` 让普通工具无需额外配置即可参与注册；如果改成默认不可用，未覆盖该方法的工具会被隐藏。特别是 `get_user_tools()` 会异步调用 `dynamic_available()`，如果这里引入数据库异常、网络请求或过重逻辑，会影响每次任务分析前的工具列表构建。

第四个风险是替换 `StreamingResponse` 类型。当前 Agent 的执行、摘要和前端消费都围绕流式响应设计。具体工具如搜索工具会返回 FastAPI 或 Lanarky 的流式响应对象；如果基类契约改变为普通字符串或其他结构，需要同步调整所有工具实现和上层响应处理。

第五个风险是把业务逻辑塞进 `Tool` 基类。这个文件的价值在于稳定契约和低耦合，具体能力应留在子类。基类一旦依赖某个外部服务、配置项或特定工具逻辑，会让所有工具都承担无关依赖，增加测试和初始化成本。
