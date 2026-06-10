# 文件：README.md

## 一句话定位

`README.md` 是 Hermes Agent 仓库的项目门面和入门导航页：它不参与运行时逻辑，但定义了用户、贡献者、包索引和代码托管平台首先看到的产品定位、安装路径、主要入口命令与文档分流。

## 它暴露/定义了什么

这个文件主要暴露四类信息。第一是项目定位：Hermes Agent 被描述为一个可自我改进的 AI agent，强调技能创建、技能自改进、持久记忆、历史会话搜索、跨平台网关、定时任务、子代理并行和多终端后端。第二是安装入口：Linux、macOS、WSL2、Termux 使用 `scripts/install.sh`，Windows PowerShell 使用 `scripts/install.ps1`，贡献者可用 `setup-hermes.sh` 或手动 `uv venv`、`uv pip install -e ".[all,dev]"`。第三是用户操作入口：`hermes`、`hermes model`、`hermes tools`、`hermes config set`、`hermes gateway`、`hermes setup`、`hermes claw migrate`、`hermes update`、`hermes doctor` 等。第四是生态导航：文档站、CLI 指南、消息网关、配置、安全、工具、技能、Memory、MCP、Cron、Context Files、Architecture、Contributing、CLI Reference、Environment Variables 等。

从 `pyproject.toml` 可见，`[project].readme = "README.md"`，因此它也是 Python 包元数据的一部分，会被打包/发布系统读取为项目长描述。

## 谁调用它

严格说，`README.md` 不被 Python 运行时代码“调用”。它的调用方主要是工具链和人：代码托管平台会渲染它作为仓库首页；Python 打包工具会按 `pyproject.toml` 的 `readme` 字段读取它；用户会根据其中的安装命令拉取 `scripts/install.sh` 或 `scripts/install.ps1`；贡献者会根据 Contributing 小节进入本地开发流程；中文用户可通过语言徽章跳转到 `README.zh-CN.md`。根据当前片段推断，文档站也会从 README 链接获得流量，但未看到 Docusaurus 直接导入根 README 的证据。

## 它调用谁

作为 Markdown 文档，它没有函数调用，但它“指向”了多个仓库内外部对象。仓库内包括 `assets/banner.png`、`README.zh-CN.md`、`LICENSE`、`scripts/install.sh`、`scripts/install.ps1`、`setup-hermes.sh`。命令层面，它引导用户进入 `hermes_cli.main:main` 暴露的 `hermes` 命令；`pyproject.toml` 中还定义了 `hermes-agent = "run_agent:main"` 和 `hermes-acp = "acp_adapter.entry:main"`。功能层面，它把用户引向 CLI、gateway、setup、portal、claw migration、doctor、update、cron、skills、tools 等子系统。外部链接在本文档中不展开，统一视为 `[URL已移除]`。

## 核心流程

README 的阅读路径是典型的“从认知到执行”。顶部先通过 banner、徽章和一句话定位建立项目认知；随后用表格压缩介绍核心能力，包括 TUI、消息平台、学习闭环、调度、子代理、终端后端和研究用途。接着进入 Quick Install，按操作系统分流到 shell 或 PowerShell 安装脚本，并说明 Termux 与 Windows 的限制。安装后进入 Getting Started，用户通过 `hermes` 启动交互式 CLI，再用 `hermes model`、`hermes tools`、`hermes setup` 等命令完成配置。之后 README 介绍 Nous Portal 作为简化 API key 管理的路径，再用 CLI vs Messaging 表格说明终端和消息平台之间的命令对应关系。后半部分承担导航作用：把深入内容交给文档站，把迁移交给 `hermes claw migrate`，把开发者引到贡献流程和测试命令，最后落到社区与许可证。

## 关键函数的高层作用

`README.md` 本身没有函数、类或可执行逻辑，因此“关键函数”应理解为它展示的关键命令入口。`hermes` 是主交互入口，对应 `pyproject.toml` 中的 `hermes_cli.main:main`，默认进入聊天/TUI 或 CLI 调度流程。`hermes model` 管理模型提供商和模型选择。`hermes tools` 管理工具启用状态。`hermes gateway` 启动或管理 Telegram、Discord、Slack、WhatsApp、Signal、Email 等消息平台网关。`hermes setup` 运行完整配置向导，`hermes setup --portal` 走 Nous Portal 登录和 Tool Gateway 配置。`hermes claw migrate` 负责从 OpenClaw 导入设置、记忆、技能、密钥和工作区说明。`hermes doctor` 用于诊断配置与依赖问题。`scripts/install.sh` 和 `scripts/install.ps1` 是 README 中最重要的非 Python 执行入口，分别覆盖类 Unix/Termux 和 Windows 原生安装。

## 修改风险

修改这个文件的主要风险不是破坏运行时，而是破坏用户获取项目的第一路径。安装命令如果与 `scripts/install.sh`、`scripts/install.ps1` 参数或支持平台不一致，会直接导致新用户失败；命令列表如果与 `hermes_cli.main`、CLI 子命令或 gateway 行为脱节，会制造错误预期；Windows、Termux、WSL2 等平台说明若滞后，会引发大量安装问题。由于 `pyproject.toml` 把它作为包 readme，Markdown 中的图片、HTML 表格、徽章和链接还会影响包索引展示，外部链接变更也可能造成发布页展示异常。另一个风险是中文 README 与英文 README 内容漂移：当前 `README.zh-CN.md` 的 Windows 描述与英文 README 已不完全一致，继续改动时需要同步审查。最后，README 承载产品定位，夸大或过时的能力描述会影响用户信任；涉及 provider、Tool Gateway、平台支持、依赖安装和迁移范围的内容应以实际代码和脚本为准。
