# Hermes Agent 中文源码导读索引

这组文档面向第一次阅读 `hermes-agent` 的中文读者，目标是先建立项目地图，再进入关键源码。内容只依据当前仓库中的 `README.md`、`pyproject.toml`、`package.json`、入口文件、配置加载代码、模块目录和源码注释整理；涉及运行行为的判断会在对应章节标注依据或“根据当前文件推断”。

## 推荐阅读顺序

1. [00-overview.md](00-overview.md)：先看项目要解决的问题、核心能力、主要模块，以及初学者从哪里切入。
2. [01-tech-stack.md](01-tech-stack.md)：再看 Python、Node/TypeScript、前端、测试、包管理和配置文件给出的技术栈信号。
3. [02-architecture.md](02-architecture.md)：理解目录分层、模块边界、工具注册、插件、技能、网关和前端之间的依赖方向。
4. [03-runtime-flow.md](03-runtime-flow.md)：按启动、配置加载、Agent 初始化、模型调用、工具执行、会话持久化和网关/TUI 流转追踪一次请求。
5. [04-reading-guide.md](04-reading-guide.md)：最后按“必须先读、可以后读、暂时跳过”的顺序安排继续下钻。

## 后续最值得看的目录

- `hermes_cli/`：`hermes` 命令入口、配置、setup、gateway/service 管理、dashboard、插件扫描等 CLI 外壳。
- `agent/`：`AIAgent` 的实际初始化、对话循环、压缩、记忆、模型适配、错误分类、工具执行辅助。
- `tools/`：内置工具实现和 `tools/registry.py` 自注册机制。
- `gateway/`：Telegram、Discord、Slack、WhatsApp、Signal、Email、API Server 等消息平台入口。
- `plugins/`：模型供应商、记忆供应商、搜索/图像/视频/浏览器后端、平台适配和观测插件。
- `skills/` 与 `optional-skills/`：内置技能和可选技能，适合理解“过程记忆”如何被组织。
- `ui-tui/`：Ink/React 终端 UI，和 Python `tui_gateway/` 通过 stdio JSON-RPC 通信。
- `web/`：Vite/React dashboard，包含配置、日志、会话、插件、技能、聊天页面等。
- `tests/`：按 `agent`、`tools`、`gateway`、`plugins`、`tui_gateway` 等分区组织的回归测试。

## 后续最值得看的文件

- `pyproject.toml`：Python 包名、入口脚本、依赖、extras、测试配置和打包范围。
- `README.md` / `README.zh-CN.md`：项目能力说明和用户级入口。
- `hermes_cli/main.py`：`hermes` 命令总入口。
- `cli.py`：经典交互式 CLI。
- `run_agent.py`：`AIAgent` 门面和兼容入口。
- `agent/agent_init.py`：Agent 初始化主体。
- `agent/conversation_loop.py`：一轮对话的核心循环。
- `model_tools.py`：工具 schema 选择、toolset 过滤和工具调用调度。
- `toolsets.py`：内置工具集合定义。
- `tools/registry.py`：工具自注册和发现机制。
- `hermes_state.py`：SQLite 会话库与 FTS5 搜索。
- `gateway/run.py`：消息网关主循环。
- `tui_gateway/server.py` 与 `ui-tui/src/entry.tsx`：TUI 前后端通信入口。
- `hermes_cli/plugins.py` 与 `providers/__init__.py`：插件和模型 provider 的发现机制。
