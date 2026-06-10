# 架构与模块边界

这个仓库的架构可以按“入口层、Agent 内核层、工具层、扩展层、状态层、界面层、自动化/研究层”来理解。入口层负责把不同用户界面或命令转换成一次 Agent 调用；Agent 内核层负责构造 prompt、调用模型、执行工具、处理压缩和错误；工具层提供可被模型调用的函数；扩展层让模型 provider、记忆 provider、搜索/图像/视频/浏览器后端和平台适配器可插拔；状态层保存会话、记忆、cron 作业和配置；界面层包括经典 CLI、TUI 和 dashboard；自动化/研究层包括 cron 和 batch trajectory 生成。

顶层入口首先看 `pyproject.toml`。`hermes` 指向 `hermes_cli.main:main`，这是用户最常用的命令入口；`hermes-agent` 指向 `run_agent:main`，更接近直接运行 Agent；`hermes-acp` 指向 `acp_adapter.entry:main`，服务编辑器集成。`hermes_cli/main.py` 顶部注释列出 `hermes`、`hermes chat`、`hermes gateway`、`hermes setup`、`hermes doctor`、`hermes cron`、`hermes dashboard` 等命令。这个文件还在导入其他 Hermes 模块前处理 `--profile/-p`，设置 `HERMES_HOME`，因为很多模块会在 import 时读取路径。这个顺序是架构上的重要约束。

Agent 内核的外观仍在 `run_agent.py`。当前文件中 `AIAgent.__init__`、`run_conversation()`、工具并发执行等方法大多是 forwarder：初始化转给 `agent/agent_init.py:init_agent`，对话循环转给 `agent/conversation_loop.py:run_conversation`，工具执行转给 `agent/tool_executor.py`。这种结构保留了历史 API 面，同时把大型逻辑拆进 `agent/`。因此新读者不要被 `run_agent.py` 的体量误导：理解运行主线时应同时阅读 `run_agent.py` 的门面和 `agent/` 下的真实实现。

工具层的依赖方向很稳定：`tools/registry.py` 不依赖工具文件；每个 `tools/*.py` 在模块顶层调用 `registry.register()`；`model_tools.py` 导入 registry 并触发 `discover_builtin_tools()`；`run_agent.py`、`cli.py`、`batch_runner.py` 等再从 `model_tools.py` 获取工具定义或派发工具调用。`tools/registry.py` 的注释也明确列出这一链路。工具是否进入模型上下文，不只取决于是否存在实现，还取决于 `toolsets.py` 是否把工具名放入某个 toolset，以及 `check_fn` 是否通过。`toolsets.py` 中 `_HERMES_CORE_TOOLS` 是默认工具束，覆盖 web、terminal、file、vision、image、skills、browser、tts、todo、memory、session_search、clarify、execute_code、delegate_task、cronjob、messaging、homeassistant、kanban、computer_use 等核心能力。

扩展层分为多套发现机制。通用插件由 `hermes_cli/plugins.py` 管理，支持 bundled、user、project、pip entry point 四种来源，插件目录需要 `plugin.yaml` 和 `__init__.py register(ctx)`。它们可以注册 hooks、tools 或 CLI 子命令。模型 provider 不是由通用插件直接导入，而是由 `providers/__init__.py` 懒加载 `plugins/model-providers/<name>/` 和用户 provider 插件；这避免重复实例化 provider profile。memory provider 又有 `plugins/memory/` 的专用加载路径，由 `agent/memory_manager.py` 统一调度。context engine、image_gen、video_gen、web、browser、platform 等也各有 backend/plugin 风格。结论是：看到 `plugins/` 目录时，要先判断插件类型，再找对应加载器。

状态层围绕 Hermes home。`hermes_constants.py:get_hermes_home()` 是根路径解析来源，`hermes_cli/config.py` 管理 `config.yaml` 和 `.env`，`hermes_logging.py` 管理日志路径，`hermes_state.py` 管理 `state.db`。`hermes_state.py` 的注释说明它替代了按会话 JSONL 存储，使用 SQLite、WAL、FTS5、session metadata、message history 和 model config。`cron/jobs.py` 把计划任务存到 Hermes home 下的 `cron/jobs.json`，输出写到 `cron/output/`。这些路径都应通过 `get_hermes_home()` 或相关封装获得，避免跨 profile 写错数据。

界面层有三个重点。经典 `cli.py` 使用 Rich 与 prompt_toolkit，直接构造 `AIAgent` 并处理 slash command、会话和显示。`ui-tui/` 是 TypeScript/Ink 终端 UI，`tui_gateway/server.py` 是 Python JSON-RPC 后端，二者通过 stdio 通信。`web/` 是 React dashboard，后端在 `hermes_cli/web_server.py`；根据 `AGENTS.md` 和源码结构，dashboard 的聊天页嵌入真实 `hermes --tui` 的 PTY，而不是另写一套聊天内核。消息平台 `gateway/` 则由 `gateway/run.py` 管理生命周期，并使用 `gateway/platforms/` 下的具体 adapter。

关键依赖方向可以简化为：入口层调用 Agent；Agent 调用 provider client 和 `model_tools`；`model_tools` 调用 `tools.registry`；工具可以使用配置、文件、网络、浏览器或环境后端；Agent 和入口层共同写入状态库与日志；插件可在工具、LLM、网关、审批、会话生命周期等点挂 hook。反方向依赖应尽量避免，例如工具注册层不应依赖 `run_agent.py`，provider 插件不应硬编码到 core。仓库中的注释和 `AGENTS.md` 都强调插件扩展应走通用扩展面，而不是修改核心文件。
