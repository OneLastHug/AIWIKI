# 目录：hermes_cli

## 它负责什么

`hermes_cli` 是 Hermes Agent 的“命令行外壳与本地管理面”目录。它不承载核心对话循环本身，核心 Agent 仍主要在 `run_agent.py`、工具分发在 `model_tools.py`、工具集合在 `toolsets.py`；`hermes_cli` 负责把这些能力包装成用户可运行的 `hermes` 命令、交互式 CLI/TUI 启动流程、配置读写、模型/Provider 选择、网关管理、Dashboard 后端、插件发现、技能管理、日志/调试/备份/迁移等运维入口。

可以把它理解为三层：第一层是启动和命令分发，例如 `hermes_cli/main.py`、`hermes_cli/_parser.py`；第二层是配置、认证、模型、插件、技能、网关等“管理域”；第三层是本地 Web Dashboard 与嵌入式 TUI 的桥接，例如 `hermes_cli/web_server.py`、`hermes_cli/pty_bridge.py`、`hermes_cli/dashboard_auth/`。

## 直接子目录地图

`hermes_cli` 下面只有少量直接子目录，大部分代码是扁平 `.py` 模块：

- `hermes_cli/dashboard_auth`：Dashboard 的 OAuth 登录、会话 Cookie、鉴权中间件、审计、WebSocket ticket 等。`routes.py` 定义 `/login`、`/auth/login`、`/auth/callback`、`/auth/logout`、`/api/auth/*` 这一类认证路由；`middleware.py` 提供 Dashboard 非本地访问时的鉴权门禁；`cookies.py`、`base.py`、`registry.py` 管理认证 Provider 抽象和会话数据。
- `hermes_cli/proxy`：本地 OpenAI-compatible proxy。`server.py` 提供代理服务，`cli.py` 提供命令行入口，`adapters/` 下放上游适配器抽象与实现，例如 `adapters/base.py`、`adapters/nous_portal.py`、`adapters/xai.py`。它的用途是把本地客户端请求转发到已登录的上游 Provider，而不是让每个外部应用单独保存静态 API key。
- `hermes_cli/proxy/adapters`：代理上游适配器层，定义 `UpstreamAdapter`、`UpstreamCredential` 以及具体 Provider 的凭据刷新、请求改写逻辑。

其余大量文件位于 `hermes_cli/*.py`，按职责大致分为：命令启动与解析、配置与环境、模型与 Provider、认证与账户、网关与平台、Dashboard、插件与技能、会话与日志、备份迁移、安全审计、Kanban/cron/curator 等功能模块。

## 关键入口

`hermes_cli/main.py` 是最重要的进程入口。`main()` 负责设置进程名、Windows stdio、清理旧可执行文件、处理 Termux 快速启动，然后调用 `hermes_cli._parser.build_top_level_parser()` 创建顶层 argparse，再继续注册大量子命令，例如 `model`、`fallback`、`secrets`、`migrate`、`gateway`、`dashboard`、`sessions`、`logs`、`config` 等。各子命令最终通过 `set_defaults(func=...)` 绑定到 `cmd_*` 函数。

`hermes_cli/_parser.py` 只负责顶层 parser 和 `chat` 子命令的基础参数。源码注释明确说明，其他子命令仍在 `main.py` 内联构建，因为它们和模块级 `cmd_*` 函数耦合较强。这里还能看到通用参数，如 `--model`、`--provider`、`--toolsets`、`--resume`、`--continue`、`--worktree`、`--skills`、`--yolo`、`--tui`。

`hermes_cli/commands.py` 是 slash command 的中心注册表。`COMMAND_REGISTRY` 是 CLI 帮助、Gateway dispatch、Telegram BotCommands、Slack subcommand mapping、自动补全共同派生的单一数据源。新增 slash 命令通常先加 `CommandDef`，别直接在多个消费者里散落维护同一命令。

`hermes_cli/config.py` 是配置系统主文件，提供 `DEFAULT_CONFIG`、`OPTIONAL_ENV_VARS`、`load_config()`、`load_config_readonly()`、`save_config()`、路径解析、版本检查、敏感值脱敏等。注意 `load_config_readonly()` 是只读快路径，返回缓存对象，调用方不能修改。

`hermes_cli/web_server.py` 是 Dashboard 的 FastAPI 后端入口，创建 `app = FastAPI(...)`，负责 REST API、WebSocket、静态前端挂载、配置/环境变量管理、会话查询、日志、cron、profiles、skills、toolsets、usage analytics、dashboard plugins，以及 `/api/pty` 嵌入式 TUI 通道。

`hermes_cli/plugins.py` 是通用插件发现和生命周期管理核心。`PluginManager.discover_and_load()` 会扫描 bundled plugins、用户插件、项目插件，并维护 hooks、plugin tools、CLI commands、plugin slash commands、plugin skills、auxiliary tasks 等注册结果。

## 主流程位置

交互式命令主流程从 `hermes_cli/main.py:main()` 开始：先构建 argparse，再根据命令进入对应 `cmd_*`。默认聊天或 `chat` 子命令会进入 CLI/TUI 启动路径；真正的经典交互式 REPL 类在根目录 `cli.py` 的 `HermesCLI`，而不是 `hermes_cli` 内。根据当前片段推断，`hermes_cli/main.py` 更多是命令分发器，经典对话 UI 的长生命周期逻辑仍在根级 `cli.py` 中，依据是 `cli.py` 中存在 `HermesCLI`、`ChatConsole` 和大量 slash 处理逻辑，而 `main.py` 负责注册命令和调用入口函数。

配置主流程位于 `hermes_cli/config.py`：命令或 Dashboard 调用 `load_config()` 读取 `$HERMES_HOME/config.yaml`，和默认配置深合并后供 CLI、Provider、Gateway、Dashboard 使用；需要高频只读访问时走 `load_config_readonly()`。

Dashboard 主流程位于 `hermes_cli/web_server.py`：HTTP API 由 `@app.get`、`@app.post`、`@app.put` 等装饰器定义；敏感 API 通过 session token 和 Dashboard auth gate 保护；前端 SPA 由 `mount_spa()` 挂载；浏览器内 `/chat` 不是 React 重写聊天，而是通过 `/api/pty` WebSocket 和 `hermes_cli/pty_bridge.py` 启动真实 `hermes --tui`，把 PTY 字节流交给浏览器终端。

Gateway 管理主流程在 `hermes_cli/gateway.py`，其中 `run_gateway()` 负责前台运行消息网关，服务安装、启动、停止、状态等命令也在该模块附近。真正平台适配器在根目录 `gateway/`，`hermes_cli/gateway.py` 主要是本地管理和服务包装层。

插件主流程在 `hermes_cli/plugins.py`：`discover_plugins()` 调到全局 `PluginManager`，扫描清单并加载 `register(ctx)`，插件可注册工具、hook、CLI 子命令、平台适配器、技能等。注意模型 Provider 插件和 memory 插件有自己的发现系统，不完全走通用 `PluginManager`。

## 推荐阅读顺序

1. 先读 `hermes_cli/_parser.py`，理解顶层 `hermes` 命令有哪些通用参数，以及为什么只把基础 parser 放在独立模块。
2. 再读 `hermes_cli/main.py` 的 `main()` 附近和各 `subparsers.add_parser(...)` 区块，建立“命令到处理函数”的总地图，不必逐行看完。
3. 读 `hermes_cli/commands.py` 的 `CommandDef` 和 `COMMAND_REGISTRY`，理解 slash command 与 CLI/Gateway/补全之间的共享注册机制。
4. 读 `hermes_cli/config.py` 的 `DEFAULT_CONFIG`、`load_config()`、`load_config_readonly()`，再回看具体命令如何读写配置。
5. 如果关注 Dashboard，读 `hermes_cli/web_server.py` 顶部鉴权、核心 API 分区、`/api/pty`、`mount_spa()`，再进入 `hermes_cli/dashboard_auth/`。
6. 如果关注扩展能力，读 `hermes_cli/plugins.py` 的 `PluginContext`、`PluginManager.discover_and_load()`，再结合仓库根目录 `plugins/` 看实际插件结构。
7. 如果关注消息平台，读 `hermes_cli/gateway.py` 的运行/服务管理入口，再跳到根目录 `gateway/` 看平台适配器和会话逻辑。

## 常见误区

- 不要把 `hermes_cli` 当成 Agent 核心推理目录。对话循环、模型调用、工具调用主干在 `run_agent.py`、`model_tools.py` 等根级模块；`hermes_cli` 主要负责启动、配置、管理和本地界面。
- 不要以为 slash command 只服务经典 CLI。`hermes_cli/commands.py` 的注册表同时影响 CLI 帮助、Gateway、Telegram、Slack、自动补全等，新增命令应优先维护 `COMMAND_REGISTRY`。
- 不要把 Dashboard 的 `/chat` 理解成一套独立 React 聊天实现。当前设计是通过 `hermes_cli/pty_bridge.py` 嵌入真实 `hermes --tui`，所以聊天体验变更通常应改 TUI，而不是在 Dashboard 里重写 transcript/composer。
- 不要混淆配置加载路径。`hermes_cli/config.py` 的 `load_config()` 是很多 CLI 子命令和 Dashboard 的配置入口；根级 `cli.py` 还有 `load_cli_config()`；Gateway 运行时也可能直接读取 YAML。新增配置时要确认三个路径是否都需要覆盖。
- 不要认为 `plugins.py` 会加载所有插件类型。通用插件走 `PluginManager`，但 memory provider、model provider 等有独立发现机制；如果某类插件“看起来没被通用扫描加载”，可能是有意分流。
- 不要在阅读 `main.py` 时陷入逐行细节。它体量很大，overview 阶段应按命令区块和 `cmd_*` 绑定关系阅读，把它当路由表和启动器，而不是业务逻辑唯一来源。
