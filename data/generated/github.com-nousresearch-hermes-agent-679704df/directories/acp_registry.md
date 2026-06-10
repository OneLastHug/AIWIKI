# 目录：acp_registry

## 它负责什么

`acp_registry` 是 Hermes Agent 面向 ACP Registry 的发布元数据目录。它本身不实现 ACP 协议、不启动服务、不处理编辑器会话，而是提供让外部 ACP 客户端或 registry 识别、展示和安装 Hermes 的最小资产包。当前目录只有两个文件：`agent.json` 和 `icon.svg`。

从 `acp_registry/agent.json` 可以看出，它描述的是一个名为 `Hermes Agent` 的 agent 条目，核心字段包括 `id`、`name`、`version`、`description`、`repository`、`website`、`authors`、`license` 和 `distribution`。其中 `distribution.uvx.package` 固定为 `hermes-agent[acp]==<version>`，`distribution.uvx.args` 为 `["hermes-acp"]`。这说明 registry 安装路径并不是直接运行源码目录里的 Python 模块，而是通过 `uvx` 安装并执行 PyPI 包中的 ACP 入口命令。

`icon.svg` 是 registry 展示用图标。测试要求它是 `16x16`、使用 `currentColor`、不包含硬编码颜色和渐变。这类限制说明图标要适配不同宿主界面主题，而不是在 Hermes 内部渲染使用。

根据当前片段推断，`acp_registry` 的主要消费者有两类：一类是外部 ACP Registry 或编辑器集成读取该目录；另一类是仓库内部的发布脚本与测试，确保 registry 元数据和项目版本保持一致。依据是 `website/docs/user-guide/features/acp.md` 中提到 registry 元数据源文件位于 `acp_registry/agent.json`、`acp_registry/icon.svg`，以及 `tests/acp/test_registry_manifest.py`、`scripts/release.py` 明确校验和更新该目录。

## 直接子目录地图

当前 `acp_registry` 没有直接子目录，只有两个顶层文件：

`acp_registry/agent.json`：ACP Registry manifest。它是这个目录的核心文件，声明 Hermes Agent 在 registry 中的身份、描述、作者、许可证、版本和安装方式。最重要的运行分发信息在 `distribution.uvx` 下，指定通过 `hermes-agent[acp]==<version>` 安装，并以 `hermes-acp` 作为启动参数或入口。

`acp_registry/icon.svg`：registry 展示图标。它不参与运行时协议，只服务于编辑器或 registry 的 UI 展示。测试约束它必须保持简单、主题友好，不能带固定颜色或渐变。

这个目录没有 `__init__.py`，也没有 Python 包结构，因此不要把它理解成 Hermes 的 ACP adapter 实现目录。真正的协议适配代码在邻近的 `acp_adapter/`。

## 关键入口

对 `acp_registry` 来说，关键入口不是函数，而是文件契约：

`acp_registry/agent.json` 是外部 registry 的入口。它的 `id` 固定为 `hermes-agent`，`name` 固定为 `Hermes Agent`，`distribution` 当前只允许并实际使用 `uvx`。内部测试还明确禁止老字段或非官方字段回流，例如 `schema_version`、`display_name`，以及 `distribution` 下的 `type`、`command`。

`acp_registry/icon.svg` 是展示入口。`tests/acp/test_registry_manifest.py` 会解析 SVG，并检查 `viewBox`、`width`、`height` 以及颜色策略。它的存在是为了让 registry 展示 Hermes 条目，而不是为了 Hermes CLI、TUI 或 ACP server 运行。

运行时入口位于目录外：`hermes_cli/main.py` 中注册了 `hermes acp` 子命令。该命令导入 `acp_adapter.entry.main`，并把 `--version`、`--check`、`--setup`、`--setup-browser`、`--yes` 等参数转交给 ACP adapter。也就是说，registry manifest 只是告诉宿主“如何启动 Hermes ACP”，实际启动逻辑仍在 `hermes_cli/main.py` 和 `acp_adapter/`。

发布维护入口是 `scripts/release.py` 中的 `_update_acp_registry_versions()`。它会在版本发布流程里同步更新 `agent.json` 的 `version` 和 `distribution.uvx.package`，确保 manifest 与 `pyproject.toml` 的版本一致。

## 主流程位置

从 registry 安装到 ACP 服务运行，可以把主流程理解为四段：

第一段是 registry 发现。外部 ACP Registry 或兼容编辑器读取 `acp_registry/agent.json`，拿到 Hermes 的名称、描述、图标、版本和分发方式。这里不涉及 Hermes 业务逻辑，只是元数据解析。

第二段是分发安装。`agent.json` 的 `distribution.uvx.package` 指向 `hermes-agent[acp]==<version>`，并要求精确版本。测试说明 upstream registry CI 会拒绝 `@latest` 或浮动版本，因此这里必须和项目版本锁定。`args` 为 `["hermes-acp"]`，表示通过打包后的 ACP 入口启动，而不是手写本地命令。

第三段是 CLI 转接。用户或宿主也可以通过 `hermes acp` 启动，相关参数定义在 `hermes_cli/main.py`。该命令只是外层桥接，真正调用 `acp_adapter.entry.main`。如果 ACP 依赖未安装，会提示安装 `.[acp]` extra。

第四段是 ACP adapter 会话处理。真正的协议实现集中在 `acp_adapter/server.py`，其中 `HermesACPAgent` 继承 `acp.Agent`，负责 `initialize()`、`authenticate()`、session 管理、模型选择状态、上下文用量更新、MCP server 注册、编辑审批模式等。它再包装底层 `AIAgent`，让 VS Code、Zed、JetBrains 等 ACP 客户端通过 stdio JSON-RPC 与 Hermes 对话。

版本主流程则是另一条线：发布脚本 `scripts/release.py` 在 `update_version_files()` 中调用 `_update_acp_registry_versions()`，同步 bump `agent.json`；`tests/acp/test_registry_manifest.py` 和 `tests/scripts/test_release_acp_registry.py` 负责防止 manifest 漂移。

## 推荐阅读顺序

建议先读 `acp_registry/agent.json`，只关注字段结构，尤其是 `version` 和 `distribution.uvx`。读完后要形成一个判断：这个目录是“给 registry 看”的，不是“给 Hermes runtime import 的”。

第二步读 `tests/acp/test_registry_manifest.py`。这比单看 JSON 更能说明哪些字段是稳定契约：`id`、`name`、`authors`、`license`、`uvx.package`、`uvx.args`、图标尺寸和颜色策略都被测试固定。

第三步读 `scripts/release.py` 里的 `_update_acp_registry_versions()` 以及相关测试 `tests/scripts/test_release_acp_registry.py`。这能理解为什么 `agent.json` 里的版本不能随便改，也不能用浮动依赖。

第四步再读 `hermes_cli/main.py` 的 `acp` 子命令注册，理解用户执行 `hermes acp` 或 registry 间接启动 Hermes 时，会如何进入 `acp_adapter.entry.main`。

最后读 `acp_adapter/server.py` 中的 `HermesACPAgent`。这是 ACP 功能真正复杂的地方，包括初始化能力声明、认证、session、模型选择、审批策略、工具面刷新和上下文用量通知。不要从这里反推 `acp_registry` 的职责；它们是发布元数据和运行时实现的关系。

## 常见误区

第一个误区是把 `acp_registry` 当成 ACP server 实现目录。它不是。它没有 Python 模块，也没有协议处理逻辑。ACP server 在 `acp_adapter/`，CLI 启动桥在 `hermes_cli/main.py`。

第二个误区是随手修改 `agent.json` 的 `version` 或 `distribution.uvx.package`。这些字段必须与 `pyproject.toml` 精确同步，发布脚本和测试都围绕这个约束设计。浮动版本、`latest`、不带精确 pin 的包名都不符合当前契约。

第三个误区是把 `repository`、`website` 当成本地运行依赖。它们是 registry 展示或跳转元数据，不是 Hermes 启动 ACP 所需的运行配置。本文档中外部地址均省略为 `[URL已移除]`，但源码里这些字段存在。

第四个误区是认为 `icon.svg` 可以自由替换为复杂品牌图。当前测试明确限制尺寸、颜色和渐变，目的是让图标适配宿主主题。改图标时应先看 `tests/acp/test_registry_manifest.py`，否则很容易破坏 registry 约束。

第五个误区是把 `hermes-acp` 和 `hermes acp` 混为一谈。`agent.json` 的 registry 分发使用 `uvx` 包和 `hermes-acp` 入口；本地 CLI 则有 `hermes acp` 子命令，内部再转到 `acp_adapter.entry.main`。两者最终都进入 ACP adapter，但入口形态不同。
