# 目录：tests

## 它负责什么

`tests` 是 `hermes-agent` 的主测试目录，覆盖范围不是单一模块，而是围绕 Hermes 的几个主要系统边界展开：核心 agent 循环、工具注册与执行、CLI/TUI、gateway 平台适配、插件体系、状态存储、安装脚本、网站与少量端到端场景。根据当前片段推断，这个目录承担三类职责：一是给核心 Python 包提供回归测试，二是约束跨进程、跨平台、配置隔离等工程行为，三是为插件和平台集成提供局部契约测试。

测试套件的公共约束集中在 `tests/conftest.py`。它会把项目根目录加入 `sys.path`，并通过 autouse fixture 清理凭证类环境变量、隔离 `HERMES_HOME`、固定 `TZ=UTC`、`LANG=C.UTF-8`、`PYTHONHASHSEED=0`，同时避免 `HERMES_SESSION_*` 等运行期变量从开发者 shell 泄漏进测试。这里的设计重点是“测试必须接近 CI、不能读写真实用户配置”。

运行入口不直接鼓励裸跑 `pytest`。仓库配置里 `pyproject.toml` 的 `[tool.pytest.ini_options]` 指定 `testpaths = ["tests"]`，默认排除 `integration` 标记，并设置单测超时；而 `scripts/run_tests.sh` 会调用 `scripts/run_tests_parallel.py`，按测试文件启动独立的 `python -m pytest <file>` 子进程，以降低跨文件状态污染。

## 直接子目录地图

`tests/acp`、`tests/acp_adapter` 覆盖 ACP 协议和编辑器/适配层相关行为。

`tests/agent` 是 agent 内部模块测试，包含上下文压缩、辅助传输、LSP、transport、限速、视觉参数解析等主题，是理解 agent 子系统的主要测试入口。

`tests/run_agent` 更靠近 `run_agent.py` 的会话主循环、工具调用、预算、消息处理等核心行为，和 `tests/agent` 相比更偏顶层编排。

`tests/tools` 数量很大，覆盖内置工具、工具注册、工具执行、环境后端、权限和错误处理等。它对应源码中的 `tools/`、`model_tools.py`、`toolsets.py` 一带。

`tests/cli` 覆盖经典交互 CLI：slash command、压缩、resume、状态栏、复制、背景任务、快捷键、编辑器、审批 UI、工作树安全等。

`tests/hermes_cli` 覆盖 `hermes_cli/` 包内的配置、setup、dashboard、插件命令、provider 配置、skin、更新流程、kanban 命令等。它和 `tests/cli` 的区别是：前者更偏 CLI 支撑库和子命令，后者更偏交互式 `HermesCLI` 行为。

`tests/tui_gateway` 对应 `tui_gateway/`，验证 TUI 的 JSON-RPC 后端、事件流和命令调度边界。

`tests/gateway` 是消息 gateway 的大块测试，包含 `tests/gateway/platforms`，覆盖 Telegram、Discord、Slack、Matrix、Webhook、API server 等平台适配的公共流程和平台差异。

`tests/plugins` 覆盖通用插件目录，下面按能力分成 `browser`、`dashboard_auth`、`image_gen`、`memory`、`model_providers`、`transcription`、`tts`、`video_gen`、`web` 等。旁边的 `tests/honcho_plugin`、`tests/openviking_plugin` 是特定内置 memory/provider 插件的独立测试。

`tests/hermes_state` 和根目录的 `tests/test_hermes_state*.py` 共同覆盖 SQLite session store、resume、上下文窗口、压缩锁、WAL fallback 等状态存储行为。

`tests/cron` 覆盖调度器和计划任务；`tests/docker` 覆盖 Docker/容器相关脚本与环境行为；`tests/scripts` 覆盖脚本层回归；`tests/skills` 覆盖 skill 加载、安装和索引规则；`tests/providers` 覆盖模型 provider profile 或 provider 解析；`tests/website` 覆盖文档站点或网站构建相关约束。

`tests/integration` 存放带 `integration` 性质的测试，默认 pytest 配置会排除，需要显式选择。`tests/e2e` 是更端到端的场景，例如矩阵签名引导这类完整流程。`tests/stress` 是压力或并发稳定性场景。`tests/fakes` 用作测试替身资源目录，根据当前片段显示没有 `test*.py` 文件。

根目录下大量 `tests/test_*.py` 是跨模块或历史回归测试，覆盖安装脚本、日志、项目元数据、工具定义缓存、模型工具、Yuanbao、MCP、环境加载、路径隔离、SQL 注入防护等主题。

## 关键入口

`tests/conftest.py` 是最重要的测试基础设施入口。读任何测试失败前，都应该先知道它会自动清理哪些环境变量、如何设置 `HERMES_HOME`、哪些 marker 会被注册、哪些真实系统访问会被 guard 拦截。

`scripts/run_tests.sh` 是推荐运行入口。它负责选择虚拟环境、挂载可选 live guard，并把参数交给 `scripts/run_tests_parallel.py`。注释里明确给出用法：全量运行、限制并发、指定目录、指定单文件、透传 pytest 参数。

`scripts/run_tests_parallel.py` 是实际并行调度器。根据 `tests/conftest.py` 注释，测试文件级隔离依赖它：每个测试文件一个新 Python 解释器，避免模块级缓存、ContextVar、全局 dict 在文件之间泄漏。

`pyproject.toml` 的 `[tool.pytest.ini_options]` 是 pytest 默认策略入口：`testpaths = ["tests"]`、默认 `-m 'not integration'`、`--timeout=30`、`--timeout-method=signal`。这解释了为什么某些 integration 测试不会在普通测试命令里出现。

`tests/run_interrupt_test.py` 看名字是中断行为的专项入口，属于根目录级的特殊测试脚本，不宜和普通 `test_*.py` 等同理解；具体行为需打开文件后确认。

## 主流程位置

核心 agent 主流程的测试主要落在 `tests/run_agent`、`tests/agent` 和根目录的 `tests/test_model_tools.py`、`tests/test_model_tools_async_bridge.py`、`tests/test_toolsets.py`。这些文件共同覆盖 `run_agent.py`、`model_tools.py`、`toolsets.py`、`agent/` 内部模块之间的调用关系。

CLI 主流程分两层：交互层在 `tests/cli`，支撑命令和配置层在 `tests/hermes_cli`。如果要追 slash command，从 `tests/hermes_cli/test_commands.py`、`tests/cli/test_quick_commands.py`、`tests/cli/test_slash_command_interrupt.py` 这类文件入手；如果要追 setup、provider、dashboard、update，则优先看 `tests/hermes_cli`。

Gateway 主流程在 `tests/gateway` 和 `tests/gateway/platforms`。它对应源码中的 `gateway/run.py`、`gateway/session.py`、`gateway/platforms/`。根据目录形态推断，公共 gateway 行为和各平台适配行为是分层测试的。

插件主流程在 `tests/plugins` 及特定插件目录。模型 provider、memory provider、dashboard auth、image/audio/video/web 能力都被分目录隔离，便于对应 `plugins/` 下的不同插件表面。

工具主流程在 `tests/tools`，并和根目录的 `tests/test_get_tool_definitions_cache_isolation.py`、`tests/test_model_tools.py` 互相补充。前者更偏工具实现，后者更偏工具定义收集、缓存隔离和调用桥接。

## 推荐阅读顺序

1. 先读 `tests/conftest.py`，理解测试隔离、环境变量清理、`HERMES_HOME` 临时目录、真实系统 guard 和 marker 规则。
2. 再读 `pyproject.toml` 的 pytest 配置，以及 `scripts/run_tests.sh`、`scripts/run_tests_parallel.py`，理解为什么这个仓库按“文件级子进程”运行测试。
3. 如果关注 agent 主链路，读 `tests/run_agent`，再读 `tests/agent`，最后补根目录的 `tests/test_model_tools.py`、`tests/test_toolsets.py`。
4. 如果关注命令行体验，先看 `tests/cli` 的交互行为，再看 `tests/hermes_cli` 的配置、setup、dashboard 和子命令。
5. 如果关注对外入口，按 `tests/gateway`、`tests/tui_gateway`、`tests/acp`、`tests/acp_adapter` 的顺序阅读。
6. 如果关注扩展能力，读 `tests/plugins`、`tests/honcho_plugin`、`tests/openviking_plugin`、`tests/providers`、`tests/skills`。
7. 最后再看 `tests/integration`、`tests/e2e`、`tests/stress`，它们更适合在理解局部契约后验证跨系统场景。

## 常见误区

不要把 `tests` 理解成按源码目录一一镜像的结构。它既有镜像式目录，如 `tests/tools`、`tests/gateway`，也有按行为聚合的根目录 `tests/test_*.py`，还有插件、安装脚本、状态存储等横切测试。

不要默认直接运行 `pytest` 就等价于 CI。仓库注释明确推荐 `scripts/run_tests.sh`，因为它提供文件级进程隔离；裸跑 pytest 可能暴露或隐藏由全局状态导致的问题。

不要在测试里依赖真实 `~/.hermes`、真实 API key 或当前 shell 的 Hermes 会话变量。`tests/conftest.py` 的核心目标就是清除这些输入，违反这一点通常说明代码没有通过 `get_hermes_home()` 或测试设计不够 hermetic。

不要把 `tests/integration` 当作默认会跑的测试。默认 addopts 排除了 `integration` marker，相关场景需要显式开启。

不要看到 `tests/fakes` 没有测试文件就认为无用。它更可能是测试替身资源或辅助模块目录，是否被引用需要结合具体测试导入关系确认。

不要逐叶子文件找“唯一入口”。这个目录的入口是分层的：运行入口在 `scripts/run_tests.sh`，pytest 公共入口在 `tests/conftest.py`，业务入口则按 agent、CLI、gateway、tools、plugins 等子系统分散。
