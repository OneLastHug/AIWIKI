# 目录：acp_adapter

## 它负责什么

`acp_adapter` 是 Hermes Agent 面向 ACP（Agent Client Protocol）的适配层。它把仓库核心的 `AIAgent` 包装成一个可通过 ACP stdio JSON-RPC 交互的 agent server，供编辑器或 IDE 集成使用，例如 VS Code、Zed、JetBrains 一类客户端。它不是一个新的智能体实现，也不是前端 UI；它主要做协议翻译、会话管理、权限审批、工具调用展示、历史恢复和模型/模式切换。

从职责上看，这个目录站在三者之间：上游是 ACP SDK 的协议对象和 `acp.run_agent()`；中间是 `HermesACPAgent`；下游是 Hermes 的 `run_agent.AIAgent`、`hermes_state.SessionDB`、工具系统、MCP 工具发现、运行时 provider 配置。ACP 客户端发来的 prompt、resource、image、session 操作会被转换成 Hermes 能理解的 OpenAI 风格消息和会话状态；Hermes 的 reasoning、tool progress、todo plan、permission request、final response 又会被转换回 ACP session update。

## 直接子目录地图

`acp_adapter` 当前没有直接子目录，是一个平铺的 Python 包。按角色可以把文件分成几组：

`acp_adapter/entry.py`、`acp_adapter/__main__.py` 是启动入口组，负责命令行参数、环境变量、日志和启动 ACP server。

`acp_adapter/server.py` 是协议主体组，定义 `HermesACPAgent`，承接 ACP 生命周期方法、prompt 处理、session load/resume/list/fork/cancel、模型切换、slash command、resource 转换和主对话调用。

`acp_adapter/session.py` 是会话状态组，定义 `SessionState`、`SessionManager`，负责 ACP session 到 Hermes `AIAgent` 实例的映射，以及持久化到 `~/.hermes/state.db` 对应的 `SessionDB`。

`acp_adapter/events.py`、`acp_adapter/tools.py` 是事件和工具展示组，前者把 `AIAgent` callback 转成 ACP update，后者把 Hermes 工具名、参数和结果整理成 ACP `ToolCall` 的标题、种类、内容和完成状态。

`acp_adapter/permissions.py`、`acp_adapter/edit_approval.py` 是审批组，分别处理危险命令审批和文件编辑审批，把 Hermes 内部的 approval callback 连接到 ACP 客户端的 permission UI。

`acp_adapter/auth.py` 是认证/配置引导组，检测 Hermes 当前 provider 凭据，并向 ACP registry/client 宣告可用 auth method，包括终端内配置 Hermes provider 的 `hermes-setup` 方法。

## 关键入口

最外层入口有三个。

第一是 `pyproject.toml` 中的 console script：`hermes-acp = "acp_adapter.entry:main"`。这说明安装后可以直接运行 `hermes-acp` 启动 ACP adapter。

第二是 CLI 子命令入口：`hermes_cli/main.py` 里注册了 `hermes acp` 子命令，并在 `cmd_acp()` 中导入 `acp_adapter.entry.main`。该子命令支持 `--version`、`--check`、`--setup`、`--setup-browser`、`--yes` 等参数。这里是普通 Hermes CLI 和 ACP 运行模式之间的桥。

第三是模块入口：`acp_adapter/__main__.py` 允许 `python -m acp_adapter`，它只是导入并调用 `entry.main()`。

真正进入服务循环的位置在 `acp_adapter/entry.py` 的 `main()`：它先解析参数，必要时执行版本输出、依赖检查、provider 设置或 browser 工具安装；正常启动时会配置 stderr 日志、加载 Hermes `.env`，把项目根加入 `sys.path`，执行 MCP 工具发现，然后创建 `HermesACPAgent()` 并调用 `asyncio.run(acp.run_agent(agent, use_unstable_protocol=True))`。这里也能看出 stdout 被保留给 ACP JSON-RPC transport，普通日志必须走 stderr。

## 主流程位置

主流程核心在 `acp_adapter/server.py` 的 `HermesACPAgent` 类。根据当前片段推断，它实现的是 ACP SDK 期望的 agent 接口，依据是它继承 `acp.Agent`，并定义了 `initialize()`、`authenticate()`、`new_session()`、`load_session()`、`resume_session()`、`cancel()`、`fork_session()`、`list_sessions()`、`prompt()`、`set_session_model()`、`set_session_mode()`、`set_config_option()` 等协议方法。

一次典型对话大致是这样流动的：ACP 客户端连接后调用 `initialize()`，服务端返回协议版本、auth methods、session 能力、model/mode 状态等信息；客户端创建或恢复 session 时，`HermesACPAgent` 委托 `SessionManager` 创建或还原 `SessionState`，每个状态里有一个 Hermes `AIAgent` 实例、cwd、model、history、cancel event、queue 等字段；客户端发送 prompt 后，`prompt()` 会把 ACP content blocks 转成 Hermes/OpenAI 兼容的 user content，绑定 cwd、审批 callback、编辑审批 requester、tool progress callback、thinking callback、step callback，然后在线程池中运行 `AIAgent.run_conversation()`；执行过程中 `events.py` 负责把工具开始、工具完成、thinking 文本、todo plan 更新推送给 ACP 客户端；最终 assistant response 再通过 ACP message update 返回，并把 session history 持久化。

会话恢复主线在 `acp_adapter/session.py`。`SessionManager.create_session()` 创建新 UUID、构造 `AIAgent`、注册 task cwd override、持久化 session；`get_session()` 会先查内存，找不到时调用 `_restore()` 从 `SessionDB` 恢复；`list_sessions()` 合并内存 session 和数据库中的 `source="acp"` session，并支持按 cwd 过滤；`fork_session()` 深拷贝历史并生成新 session；`save_session()` 和 `_persist()` 负责把历史写回数据库。这里还有 WSL 路径翻译逻辑，用来把 Windows ACP 客户端传来的 `E:\...` 类路径转换成 `/mnt/e/...`。

工具展示主线在 `acp_adapter/tools.py` 和 `acp_adapter/events.py`。`events.make_tool_progress_cb()` 在 Hermes 工具开始时生成 ACP tool call id，并调用 `build_tool_start()`；`events.make_step_cb()` 在 Hermes step 完成后读取工具结果，调用 `build_tool_complete()`，如果工具是 `todo`，还会生成 ACP 原生 plan update。`tools.py` 则包含大量格式化函数，目的不是改变工具执行，而是让 ACP 客户端的工具面板更可读，避免把过长的文件内容、skill 内容、memory 列表或 web extract 成功全文直接刷到 UI。

审批主线有两条。危险命令审批在 `permissions.make_approval_callback()`，它把 Hermes 的 approval 语义映射成 ACP `request_permission()`，再把 ACP outcome 映射回 `"once"`、`"session"`、`"always"`、`"deny"`。文件编辑审批在 `edit_approval.py`，它通过 `ContextVar` 在单次 ACP agent run 中绑定 requester，对 `write_file` 和部分 `patch` 生成 `EditProposal`，并根据策略判断是否自动批准；敏感路径如 `.env`、`.ssh`、`.git` 仍会保守处理。

## 推荐阅读顺序

建议先读 `acp_adapter/entry.py`，弄清楚 ACP adapter 是如何被启动、为什么日志走 stderr、为什么要提前发现 MCP 工具。然后读 `acp_adapter/server.py` 的 `HermesACPAgent` 类，只看大块注释和方法名即可，先建立协议生命周期地图，不要陷入 resource block 转换和 slash command 的细节。

第二步读 `acp_adapter/session.py`，重点看 `SessionState`、`SessionManager.create_session()`、`get_session()`、`_persist()`、`_restore()`、`_make_agent()`。这能解释 ACP session 与 Hermes `AIAgent`、`SessionDB`、cwd、model/provider 配置之间的关系。

第三步读 `acp_adapter/events.py` 和 `acp_adapter/tools.py`。先看 `make_tool_progress_cb()`、`make_step_cb()`、`build_tool_start()`、`build_tool_complete()`，理解“工具真实执行在 Hermes，ACP 这里只负责展示和状态同步”。

最后读 `acp_adapter/auth.py`、`acp_adapter/permissions.py`、`acp_adapter/edit_approval.py`，它们属于边界能力：首次配置、危险操作确认、编辑审批。读完这些，再回到 `server.py` 的 `prompt()`，主流程会比较清楚。

## 常见误区

第一个误区是把 `acp_adapter` 当成独立 agent。它本身不负责模型调用和核心推理，真正运行对话的是 `run_agent.AIAgent`；`acp_adapter` 负责把 ACP 协议事件转换成 Hermes 运行时能接受的输入和回调。

第二个误区是认为 ACP session 只在内存里。`SessionManager` 会把 `source="acp"` 的 session 写入共享 `SessionDB`，所以重启或编辑器重连后可以通过 `load_session()`、`resume_session()` 恢复历史。

第三个误区是忽略 stdout/stderr 的分工。ACP stdio transport 使用 stdout 传 JSON-RPC，任何普通日志或人类可读输出写到 stdout 都可能破坏协议。因此 `entry.py` 和 `session.py` 都刻意把日志、状态输出或 agent print 路由到 stderr。

第四个误区是把 `tools.py` 看成工具实现。它不是 Hermes 工具注册处，也不执行工具；它主要是 ACP UI 的格式化层。真实工具注册和执行仍在仓库的工具系统与 `model_tools.py` 附近。

第五个误区是认为编辑器端的 model/mode picker 会直接改全局配置。根据当前片段推断，ACP 的 `set_session_model()`、`set_session_mode()` 更偏向 session 级状态更新，原因是 `SessionState` 中保存了 `model`，`server.py` 也有 `_build_model_state()`、`_session_modes()`、`_send_session_info_update()` 这类 per-session 方法。全局 Hermes 配置仍由普通 CLI/config 体系管理。
