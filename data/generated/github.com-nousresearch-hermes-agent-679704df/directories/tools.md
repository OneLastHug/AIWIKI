# 目录：tools

## 它负责什么

`tools` 是 Hermes Agent 的“可调用能力层”。它把模型能看到的函数工具拆成一批自注册模块：每个工具模块在 import 时调用 `tools.registry.registry.register()`，声明工具名、所属 toolset、OpenAI function schema、handler、可用性检查 `check_fn`、环境变量依赖、结果大小限制等元数据。真正进入模型上下文前，这些工具还会经过 `model_tools.py` 和 `toolsets.py` 的筛选、动态 schema 修正、可用性检查与兼容性清洗。

从职责上看，这个目录不是单一业务模块，而是一组横向能力：终端执行、文件读写与补丁、Web 搜索与抽取、浏览器自动化、图像/语音/视频、MCP、技能管理、记忆、todo、委派子 agent、cron、消息发送、Home Assistant、Discord、飞书、元宝平台、kanban、多 agent 协调、computer use 等。工具实现通常返回 JSON 字符串，部分多模态工具会返回约定结构，让 `run_agent.py` 构造带图片内容的 tool message。

## 直接子目录地图

`tools/environments` 是终端执行后端目录。`terminal_tool.py` 面向模型暴露统一的 `terminal` / `process` 类工具，而具体执行环境拆到这里：`local.py`、`docker.py`、`ssh.py`、`modal.py`、`managed_modal.py`、`daytona.py`、`singularity.py` 等。`base.py` 定义共享抽象、进程句柄协议、活动回调、sandbox 目录和命令等待逻辑。根据当前片段推断，这里采用“每次命令新起进程，但保存会话环境快照和 cwd”的模型，既兼容本地也兼容远程/云沙箱。

`tools/computer_use` 是桌面控制工具的后端目录。`tool.py` 是 `computer_use` 工具入口，`backend.py` 定义后端接口，`cua_backend.py` 接入 `cua-driver`，`schema.py` 放 schema，`vision_routing.py` 处理视觉路由。它强调通过标准 OpenAI function calling 暴露桌面操作，因此不绑定某个特定模型提供商。动作被分成只读操作和会改变桌面状态的操作，后者要走审批与安全拦截。

`tools/neutts_samples` 是 TTS 示例资源目录，当前包含 `jo.wav`、`jo.txt`，服务于 `neutts_synth.py` 等语音合成相关代码，不是核心调度路径。

## 关键入口

`tools/registry.py` 是工具注册中心，也是理解本目录的第一入口。它提供 `discover_builtin_tools()` 扫描 `tools/*.py` 中顶层 `registry.register(...)` 调用并 import 对应模块；`ToolRegistry.register()` 写入工具元数据；`get_definitions()` 按工具名集合返回 OpenAI 格式工具 schema，并执行 `check_fn` 过滤；`dispatch()` 根据工具名调用 handler，并统一捕获异常、返回 JSON 错误。它还维护 toolset alias、注册代际 `_generation`、可用性检查 TTL 缓存等，供上层做 memoization。

`model_tools.py` 是 `tools` 目录之外但最关键的编排入口。它 import `discover_builtin_tools()` 后触发内置工具发现，同时调用 plugin discovery。对外主要提供 `get_tool_definitions()` 和 `handle_function_call()`。前者把 enabled/disabled toolsets 解析成工具名，再向 registry 要 schema；后者是运行时工具调用分发入口。它还处理 async handler 到 sync agent loop 的桥接、工具参数类型纠正、工具错误净化、schema sanitizer、`execute_code` 动态 schema、Discord 动态 schema、tool search 渐进披露等兼容层。

`toolsets.py` 定义“哪些工具能被哪个场景启用”。`_HERMES_CORE_TOOLS` 是 CLI 和大多数 gateway 平台共享的核心工具列表；`TOOLSETS` 里定义 `web`、`file`、`browser`、`terminal`、`skills`、`code_execution`、`delegation`、`hermes-cli`、`hermes-discord`、`hermes-webhook` 等工具集。注意，工具文件自注册只表示“系统知道这个工具”，不等于“agent 会看到这个工具”；工具还必须被某个有效 toolset 解析出来。

`tools/terminal_tool.py` 是执行命令能力的业务入口。它暴露终端工具，管理本地/容器/云沙箱后端、前台超时、后台进程、危险命令审批、sudo 密码回调、磁盘使用提示和中断处理。其后端实现落在 `tools/environments`。

`tools/file_tools.py`、`tools/file_operations.py`、`tools/patch_parser.py`、`tools/file_state.py` 是文件读写、搜索、补丁和状态保护的核心区域。根据文件名和 toolset 配置，`read_file`、`write_file`、`patch`、`search_files` 这一组能力由这里承载。

`tools/browser_tool.py`、`tools/browser_cdp_tool.py`、`tools/browser_dialog_tool.py`、`tools/browser_supervisor.py`、`tools/browser_camofox.py`、`tools/browser_camofox_state.py` 组成浏览器自动化工具面。`toolsets.py` 中的 browser 工具集把 navigate、snapshot、click、type、scroll、console、CDP、dialog 等动作合在一起，并通常附带 `web_search`。

## 主流程位置

工具主流程可以概括为四步。

第一步是发现与注册。`model_tools.py` import 时调用 `discover_builtin_tools()`；`tools/registry.py` 用 AST 查找顶层 `registry.register(...)`，跳过 `__init__.py`、`registry.py`、`mcp_tool.py`，然后 import 自注册模块。模块 import 成功后，工具元数据进入全局 `registry`。

第二步是工具集解析。agent、CLI、gateway、cron、ACP 等入口会传入 enabled/disabled toolsets。`model_tools.get_tool_definitions()` 调用 `toolsets.validate_toolset()`、`toolsets.resolve_toolset()`，把 `hermes-cli`、`browser`、`file` 之类的集合展开成具体工具名，并在最后应用 disabled toolsets 做减法。kanban worker 还会根据 `HERMES_KANBAN_TASK` 自动补充 kanban 生命周期工具。

第三步是 schema 生成。`registry.get_definitions()` 根据工具名集合取出 schema，执行 `check_fn` 判断依赖是否可用，并应用 `dynamic_schema_overrides`。随后 `model_tools.py` 会按运行环境二次调整：例如 `execute_code` 只列出实际可用的 sandbox tools，Discord schema 根据权限和 allowlist 改写，浏览器描述会在 Web 工具不可用时去掉相关提示，最后经过 schema sanitizer 和 tool search 组装。

第四步是调用分发。模型返回 tool call 后，agent loop 通常走 `model_tools.handle_function_call()`。普通工具最终进入 `registry.dispatch()`，由对应 handler 执行业务逻辑；async handler 通过 `_run_async()` 桥接。`todo`、`memory`、`session_search`、`delegate_task` 这类需要 agent 级状态的工具在 `model_tools.py` 中被标记为 agent-loop tools，实际处理会在 `run_agent.py` 的会话循环附近完成，而不是简单 registry dispatch。

## 推荐阅读顺序

1. 先读 `tools/registry.py`，理解自注册、schema 获取、可用性检查、dispatch 和错误封装。
2. 再读 `toolsets.py`，建立“工具模块”和“场景工具集”之间的映射关系，特别是 `_HERMES_CORE_TOOLS`、`hermes-cli`、`hermes-webhook`、平台专用 toolset。
3. 接着读 `model_tools.py`，重点看 `get_tool_definitions()`、`_compute_tool_definitions()`、`handle_function_call()` 相关区域，理解工具如何进入模型请求和如何被执行。
4. 然后按能力面阅读核心工具：文件能力看 `tools/file_tools.py`、`tools/patch_parser.py`；终端能力看 `tools/terminal_tool.py` 和 `tools/environments/base.py`；浏览器能力看 `tools/browser_tool.py` 及 CDP/dialog 辅助模块。
5. 最后读扩展型工具：`tools/mcp_tool.py`、`tools/tool_search.py`、`tools/code_execution_tool.py`、`tools/delegate_tool.py`、`tools/computer_use/tool.py`，这些更能体现 Hermes 对大型工具面、子 agent 和多模态工具的设计。

## 常见误区

不要以为 `tools` 下新增一个文件就会自动暴露给模型。自动发现只负责 import 并注册 schema，是否可用还取决于 `registry.register()`、`check_fn`、toolset 解析、enabled/disabled 配置和运行平台。

不要把 `toolset` 理解成 Python 包目录。多数 toolset 只是 `toolsets.py` 里的逻辑分组；一个顶层 `tools/*.py` 文件可以注册一个或多个工具，工具也可能通过插件或 MCP 动态进入 registry。

不要绕过 `tools/registry.py` 直接维护平行映射。当前架构已经把 schema、handler、可用性检查、emoji、结果大小限制、toolset 查询集中在 registry；`model_tools.py` 中的常量主要是兼容和缓存用途。

不要忽略 `check_fn`。很多工具在源码层存在，但运行时可能因为缺少 API key、Docker/Playwright/Modal/cua-driver 不可用、gateway 未启动或平台权限不足而不会出现在模型 schema 中。

不要把所有工具调用都理解为普通函数分发。`todo`、`memory`、`session_search`、`delegate_task` 依赖 agent 会话状态，会被 agent loop 特殊处理；`computer_use` 还可能返回多模态 tool message；`execute_code` 的 schema 会根据当前可用工具动态收缩。

不要把 `tools/environments` 当成独立产品入口。它是 `terminal_tool.py` 的执行后端层，用户和模型看到的是统一终端工具，后端选择、sandbox、cwd、进程控制和清理由工具内部协调。
