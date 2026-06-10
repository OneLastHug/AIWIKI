# 源码阅读指南

建议按“先入口、再主循环、再工具、再状态、最后扩展”的顺序阅读。这个项目目录很多，如果从 `plugins/` 或 `skills/` 随机进入，很容易被大量后端和平台细节淹没。更稳妥的方式是先建立一次请求的骨架，再把每个扩展点挂回骨架。

第一阶段读入口和包配置。先看 `pyproject.toml`，确认 Python 版本、依赖 extras、脚本入口、打包模块和 pytest 配置。然后看 `README.md` 或 `README.zh-CN.md`，只抓能力清单，不需要跟随外部链接。接着看 `hermes_cli/main.py` 顶部到命令注册附近，重点理解 `hermes` 命令如何处理 bootstrap、profile、日志、setup、gateway、dashboard、doctor、cron 等命令。这个阶段可以暂时不读 update、OAuth、平台 setup 的长实现，只需要知道它们是 CLI 子命令。

第二阶段读 Agent 主干。打开 `run_agent.py`，只看 `class AIAgent` 的构造函数、`run_conversation()`、`chat()` 和 `main()`。注意很多方法是 forwarder。随后转到 `agent/agent_init.py`，从 `init_agent()` 开始读模型/provider/client 初始化、tool schema 加载、memory manager、context compressor、context engine 注入。再读 `agent/conversation_loop.py` 的文件头、初始化消息部分、主 while 循环、工具调用处理、压缩和 fallback 分支。这个文件很长，第一次不用逐行读完；先找 `while`、`tool_calls`、`context_compressor`、`_try_activate_fallback`、`handle_function_call` 等关键词建立地图。

第三阶段读工具系统。按顺序看 `tools/registry.py`、`toolsets.py`、`model_tools.py`。`tools/registry.py` 告诉你工具如何被发现和注册；`toolsets.py` 告诉你哪些工具组合默认暴露；`model_tools.py` 告诉你 schema 如何过滤、动态改写和派发。再挑几个工具实现读即可，例如 `tools/file_tools.py`、`tools/terminal_tool.py`、`tools/web_tools.py`、`tools/browser_cdp_tool.py`、`tools/delegate_tool.py`、`tools/todo_tool.py`。不要一开始通读所有 `tools/*.py`，因为很多工具是后端适配或边缘能力。

第四阶段读状态、配置和入口复用。`hermes_constants.py` 是 Hermes home/profile 路径根；`hermes_cli/config.py` 是配置默认值、`.env` 写入约束和加载逻辑；`hermes_state.py` 是 SQLite session store；`hermes_logging.py` 是日志；`agent/memory_manager.py` 和 `tools/memory_tool.py` 是记忆相关主线；`cron/jobs.py` 与 `cron/scheduler.py` 是计划任务。读完这些后，再看 `gateway/run.py`，理解长驻消息网关如何把平台消息转成 Agent turn。平台 adapter 可以只读 `gateway/platforms/base.py` 和一个熟悉的平台，例如 `telegram.py` 或 `slack.py`。

第五阶段读 UI 和扩展。TUI 先看 `ui-tui/package.json`、`ui-tui/src/entry.tsx`、`ui-tui/src/gatewayClient.ts`、`ui-tui/src/app.tsx`、`tui_gateway/server.py`。dashboard 先看 `web/package.json`、`web/src/App.tsx`、`web/src/pages/ChatPage.tsx`、`web/src/lib/api.ts`、`hermes_cli/web_server.py`、`hermes_cli/pty_bridge.py`。插件先看 `hermes_cli/plugins.py` 和 `providers/__init__.py`，再看一个 `plugins/model-providers/<name>/__init__.py`、一个 `plugins/memory/<name>/__init__.py`、一个 `plugins/web/<name>/plugin.yaml`。技能先看 `skills/software-development/hermes-agent-skill-authoring/SKILL.md` 或任意短技能，理解 `SKILL.md`、`scripts/`、`templates/` 的组织。

可以后读或暂时跳过的模块包括：`optional-skills/` 下的大量领域技能、`website/` 文档站、`infographic/`、`datagen-config-examples/`、每一个具体消息平台 adapter、每一个模型 provider 插件、`tests/stress/` 和大量端到端测试。它们对完整项目很重要，但不是理解核心架构的必要前置。

继续下钻时建议带着问题读。想改工具，就从 `tools/registry.py`、`toolsets.py`、一个现有工具和对应测试开始；想改模型 provider，就从 `providers/__init__.py`、`providers/base.py`、`plugins/model-providers/` 和 `agent/transports/` 开始；想改网关，就从 `gateway/run.py`、`gateway/platforms/base.py`、`hermes_cli/commands.py` 开始；想改 TUI，就从 `ui-tui/src/app/useSubmission.ts`、`gatewayClient.ts`、`tui_gateway/server.py` 开始；想改配置，就从 `hermes_cli/config.py:DEFAULT_CONFIG`、`load_config()` 和相关命令处理处开始。
