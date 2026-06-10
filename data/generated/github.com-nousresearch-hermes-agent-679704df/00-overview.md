# 项目整体介绍

`hermes-agent` 是一个以 Python 为核心的工具调用型 AI Agent 项目。根据 `README.md`、`pyproject.toml` 和入口脚本可以确认，它的目标不是只提供一个聊天壳，而是把模型调用、终端/文件/浏览器/网络/图像/语音等工具、持久会话、记忆、技能、消息平台网关、定时任务、插件系统和前端界面组织成一个可长期运行的个人或团队 Agent。`pyproject.toml` 中的包名是 `hermes-agent`，脚本入口包括 `hermes = "hermes_cli.main:main"`、`hermes-agent = "run_agent:main"`、`hermes-acp = "acp_adapter.entry:main"`，这说明项目同时支持普通 CLI、直接 Agent 入口和 ACP 编辑器协议入口。

项目解决的核心问题可以概括为：让用户用自然语言驱动一个可调用工具、可保存状态、可跨平台接入、可扩展后端的 Agent。`README.md` 中列出的能力包括终端界面、消息平台接入、技能系统、记忆、计划任务、子 Agent 委托、不同终端后端、批量轨迹生成等。源码结构与这些能力对应：`run_agent.py` 定义 `AIAgent` 门面，实际初始化已拆到 `agent/agent_init.py`，一轮对话循环拆到 `agent/conversation_loop.py`；`model_tools.py` 负责把 `tools/registry.py` 中注册的工具按 `toolsets.py` 过滤成模型 API 可用的 function/tool schema；`gateway/run.py` 负责长驻消息网关；`hermes_state.py` 用 SQLite 保存会话；`cron/` 保存和调度计划任务；`plugins/` 提供多类扩展；`skills/` 与 `optional-skills/` 存放可被 Agent 加载的任务说明、脚本和模板。

从能力边界看，项目不是单模型 SDK。它把模型供应商看成可插拔后端：`plugins/model-providers/` 下有多种 provider 插件，`providers/__init__.py` 的注释说明模型 provider 会从内置插件、用户插件和旧式 `providers/*.py` 懒加载注册。`agent/transports/` 还区分了 `chat_completions`、`codex`、`anthropic`、`bedrock` 等传输/适配层。根据当前文件推断，主循环会尽量把不同供应商统一到 OpenAI 风格消息和工具调用形状，再在边界处处理各家 API 差异。

项目的核心能力主要分为六组。第一组是交互入口：`hermes_cli/main.py` 处理 `hermes` 命令族，`cli.py` 是经典 prompt_toolkit/Rich 交互 CLI，`ui-tui/` 是 Ink/React 终端 UI，`web/` 是 dashboard 前端，`gateway/` 是消息平台入口。第二组是 Agent 内核：`agent/agent_init.py` 解析 provider、模型、工具、记忆、压缩和 context engine；`agent/conversation_loop.py` 执行模型调用、工具调用、错误重试、fallback、压缩和回合收尾。第三组是工具系统：`tools/*.py` 通过 `registry.register()` 自注册，`toolsets.py` 定义 `web`、`terminal`、`file`、`browser`、`skills`、`memory`、`delegation` 等集合。第四组是状态与记忆：`hermes_state.py` 使用 SQLite/WAL/FTS5 管理会话，`agent/memory_manager.py` 和 `plugins/memory/` 管理外部记忆 provider。第五组是扩展系统：`hermes_cli/plugins.py` 支持内置、用户、项目和 pip entry point 插件；不同插件可注册 hooks、tools、CLI 子命令或后端实现。第六组是自动化和研究用途：`cron/` 运行计划任务，`batch_runner.py` 支持数据集批处理、轨迹保存和工具统计。

初学者最适合从“入口到一次对话”切入，而不是先读所有目录。建议先看 `pyproject.toml` 的脚本入口，确认 `hermes` 进入 `hermes_cli.main:main`；再看 `hermes_cli/main.py` 顶部说明和命令分发；然后看 `run_agent.py` 中 `AIAgent.__init__` 与 `run_conversation()` 的 thin forwarder，理解它们把工作转给 `agent/agent_init.py` 和 `agent/conversation_loop.py`。接着读 `model_tools.py` 与 `tools/registry.py`，就能理解模型为什么会看到某些工具、工具调用如何转成 Python handler。最后再读 `hermes_state.py`、`gateway/run.py`、`ui-tui/`、`plugins/` 和 `skills/`。

需要注意的是，仓库很大，目录数量多，且存在多个用户界面和多种插件路径。对新读者来说，不必一开始深入 `optional-skills/`、`website/`、大量 provider 插件或所有消息平台适配器。它们体现项目的覆盖面，但理解主干只需要掌握四条线：命令入口线、Agent 对话线、工具注册线、状态/配置线。本文档后续章节会围绕这四条线组织阅读。
