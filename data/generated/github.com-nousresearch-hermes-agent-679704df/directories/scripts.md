# 目录：scripts

## 它负责什么

`scripts` 是 Hermes Agent 仓库里的“工程操作脚本层”，不承载核心 agent 推理逻辑，而是把安装、测试、发布、索引生成、平台桥接、诊断和一次性维护任务包装成可直接运行的命令。它面向的使用者主要有三类：普通用户安装 Hermes，开发者本地验证改动，维护者执行发布或更新静态清单。

从当前片段看，这个目录的角色可以概括为四组：

第一组是安装与环境准备，例如 `scripts/install.sh`、`scripts/install.ps1`、`scripts/install.cmd`、`scripts/install_psutil_android.py`、`scripts/setup_open_webui.sh`。它们处理 Linux/macOS/Android/Termux、Windows PowerShell/CMD 等不同入口，负责准备 Python、Node、虚拟环境、依赖和 Hermes 命令入口。

第二组是测试与质量保障，例如 `scripts/run_tests.sh`、`scripts/run_tests_parallel.py`、`scripts/lint_diff.py`、`scripts/check-windows-footguns.py`、`scripts/tests`。其中 `run_tests.sh` 是仓库推荐的测试入口，它激活虚拟环境、清理环境变量，并调用 `run_tests_parallel.py` 做按文件隔离的 pytest 并行运行。

第三组是发布、目录索引和维护生成物，例如 `scripts/release.py`、`scripts/build_skills_index.py`、`scripts/build_model_catalog.py`。这些脚本通常会读取仓库内模块、生成 `website/static/api/...` 下的静态 JSON，或更新版本、changelog、release artifact。

第四组是平台/工具诊断和外部桥接，例如 `scripts/hermes-gateway`、`scripts/whatsapp-bridge`、`scripts/discord-voice-doctor.py`、`scripts/keystroke_diagnostic.py`、`scripts/benchmark_browser_eval.py`、`scripts/tool_search_livetest.py`。它们帮助 gateway、WhatsApp、Discord voice、TUI 输入、浏览器工具等周边能力做独立启动或排障。

## 直接子目录地图

`scripts/lib` 是脚本共享辅助层。目前可见的关键文件是 `scripts/lib/node-bootstrap.sh`，根据名称和位置推断，它用于安装或准备 Node.js 相关运行时，供安装脚本或前端/TUI 构建流程复用。

`scripts/tests` 是脚本自身的测试目录。当前片段里有 `scripts/tests/test-install-ps1-stage-protocol.ps1`，说明 Windows 安装脚本的 stage protocol 有专门测试覆盖。这里不是主项目 `tests/` 的替代品，而是围绕 `scripts` 内脚本行为的局部验证。

`scripts/whatsapp-bridge` 是一个独立 Node.js 桥接服务目录，包含 `bridge.js`、`allowlist.js`、`allowlist.test.mjs`、`package.json`、`package-lock.json`。它连接 WhatsApp/Baileys，并通过 HTTP endpoints 给 Python gateway 的 WhatsApp adapter 调用。它属于 gateway 平台适配的旁路进程，而不是 Python agent loop 本身。

## 关键入口

最重要的开发测试入口是 `scripts/run_tests.sh`。它是注释中明确标出的 canonical test runner，用来保证本地测试行为接近 CI：激活 `.venv`、`venv` 或 `$HOME/.hermes/hermes-agent/venv`，设置 `TZ=UTC`、`LANG=C.UTF-8`、`PYTHONHASHSEED=0`，清空大部分环境变量，然后执行 `scripts/run_tests_parallel.py`。

`run_tests_parallel.py` 是测试主执行器。它发现 `tests/` 下的 `test_*.py`，默认跳过 `integration`、`e2e`、`docker` 这些需要外部服务或独立 CI job 的目录，然后按“每个测试文件一个新 Python 进程”的模型运行 `python -m pytest <file>`。这里的重点不是最快，而是隔离跨文件的模块级状态泄漏。

安装入口有三条：`scripts/install.sh` 面向 Linux、macOS、Android/Termux；`scripts/install.ps1` 面向 Windows PowerShell；`scripts/install.cmd` 是 CMD 用户的薄包装，会转入 PowerShell installer。`install.sh` 和 `install.ps1` 都包含分支/目录/跳过 setup 等参数，并处理不同平台上的依赖准备。

发布入口是 `scripts/release.py`。它负责 CalVer tag、changelog、GitHub release、版本文件和构建产物。它会触达 `hermes_cli/__init__.py`、`pyproject.toml`、`acp_registry/agent.json` 等版本相关文件；根据当前片段，ACP registry manifest 需要和 `pyproject.toml` 保持版本锁定。

运行 gateway 服务的入口是 `scripts/hermes-gateway`。它是独立消息平台集成服务的启动/安装脚本，支持 foreground 运行，也支持安装、启动、停止、重启、状态查看、卸载 systemd/launchd 服务。真正的 gateway 业务代码在 `gateway/`，这个脚本负责服务化包装。

## 主流程位置

安装主流程从 `scripts/install.sh` 或 `scripts/install.ps1` 开始：解析参数，确定 `HERMES_HOME` 和安装目录，准备 Python 3.11、Node 22、uv/venv、仓库 checkout 和依赖，然后根据参数决定是否运行 setup。Windows 版本还额外暴露 stage protocol，用于程序化安装驱动。

测试主流程是 `scripts/run_tests.sh` → `scripts/run_tests_parallel.py` → `python -m pytest <file>`。前者负责环境标准化，后者负责发现测试文件、统计测试数、并发调度、超时控制、进程树清理、失败输出摘要和 exit code 汇总。

发布主流程集中在 `scripts/release.py`。从脚本头部和常量看，它会读取 git 历史和版本文件，生成 release note，按 CalVer 和 semver bump 规则更新版本，再在 `--publish` 时创建 release。这个流程属于维护者路径，普通开发不应随手运行带发布副作用的参数。

索引生成主流程分散在 `scripts/build_skills_index.py` 和 `scripts/build_model_catalog.py`。前者导入 `tools.skills_hub` 中的多个 skill source，爬取或汇总技能元数据，输出 `website/static/api/skills-index.json`；后者导入 `hermes_cli.models` 的模型列表，输出 `website/static/api/model-catalog.json`。根据当前片段推断，这些 JSON 由 docs site 静态托管，运行时 CLI 可拉取使用，失败时再回退到仓库内硬编码列表。

WhatsApp 主流程在 `scripts/whatsapp-bridge/bridge.js`：Node 进程连接 Baileys，维护 session/cache，暴露 `/messages`、`/send`、`/edit`、`/send-media`、`/typing`、`/chat/:id`、`/health` 等接口，Python gateway 的 WhatsApp 平台适配器再通过这些接口和 WhatsApp 通信。

## 推荐阅读顺序

建议先读 `scripts/run_tests.sh`，它短而清晰，能快速理解仓库对测试环境、虚拟环境和环境变量隔离的要求。接着读 `scripts/run_tests_parallel.py` 的顶部说明、`_discover_files`、`_count_tests`、单文件运行和汇总输出部分，了解为什么 Hermes 不直接依赖 pytest-xdist。

然后读安装入口：Linux/macOS/Termux 看 `scripts/install.sh`，Windows 看 `scripts/install.ps1`，只需要先关注参数、路径布局、依赖安装和 post-setup 分段，不必一次读完整个脚本。

维护者再读 `scripts/release.py`、`scripts/build_model_catalog.py`、`scripts/build_skills_index.py`。这三者会触达版本、网站静态 API 和外部 catalog，副作用更强，适合在理解仓库发布流程后阅读。

最后读平台桥接和诊断脚本，例如 `scripts/hermes-gateway`、`scripts/whatsapp-bridge/bridge.js`、`scripts/discord-voice-doctor.py`、`scripts/keystroke_diagnostic.py`。这些依赖具体平台背景，适合遇到 gateway、WhatsApp、Discord voice、TUI 输入问题时按需进入。

## 常见误区

不要把 `scripts` 当成业务核心目录。Agent 对话循环在 `run_agent.py`，工具发现和执行在 `model_tools.py`、`tools/registry.py`，gateway 业务实现主要在 `gateway/`。`scripts` 多数只是把这些能力包装成命令或维护任务。

不要绕过 `scripts/run_tests.sh` 直接跑全量 `pytest` 后就认为结果等价。仓库明确把 `run_tests.sh` 作为 canonical test runner，它会清理环境并通过 `run_tests_parallel.py` 做 per-file subprocess isolation。直接跑 pytest 可能暴露或掩盖不同问题。

不要误以为 `run_tests_parallel.py` 默认跑所有测试。它默认跳过 `tests/integration`、`tests/e2e`、`tests/docker`，除非显式指定这些路径。这个设计是为了避免本地或普通 CI shard 依赖外部服务、Docker 镜像构建等重型条件。

不要把 `scripts/whatsapp-bridge` 看成 Python gateway 的普通子模块。它是独立 Node.js 进程，使用自己的 `package.json` 和 Node 依赖，通过 HTTP 与 Python 侧适配器通信；调试时要同时关注 Node 进程、session 目录和 gateway adapter。

不要随意运行 `scripts/release.py --publish` 或索引生成脚本并提交结果。`release.py` 可能改版本、生成 changelog、构建并发布；`build_skills_index.py` 和 `build_model_catalog.py` 会写入网站静态 API 文件。它们属于维护流程，运行前应明确当前分支、凭据和预期产物。
