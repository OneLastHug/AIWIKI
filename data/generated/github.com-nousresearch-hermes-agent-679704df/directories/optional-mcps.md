# 目录：optional-mcps

## 它负责什么

`optional-mcps` 是 Hermes 内置的“官方可选 MCP 目录”。它不直接实现 MCP server，也不在启动时默认启用任何工具；它只保存一组经过仓库 PR 审核的 MCP catalog manifest。用户通过 `hermes mcp catalog` 发现这些条目，通过 `hermes mcp install <name>` 或 `hermes mcp install official/<name>` 安装，安装后才会写入用户侧 `config.yaml` 的 `mcp_servers.<name>` 配置，并在后续 Hermes 会话中作为 MCP 工具源参与运行。

这个目录的定位和 `optional-skills` 类似：仓库随附、默认禁用、按需安装。不同点是 `optional-skills` 存的是技能说明和脚本，而 `optional-mcps` 存的是 MCP server 的连接、安装、鉴权和工具选择元数据。目录中的条目被视为 Nous-approved，代码注释明确说明“存在于 `optional-mcps/` 即代表 approval”，没有额外的社区信任层级。

当前目录很小，只有两个 catalog entry：`linear` 和 `n8n`。每个 entry 只有一个 `manifest.yaml`，说明这个目录目前是清单仓库，不是运行时代码目录。

## 直接子目录地图

`optional-mcps/linear`：Linear MCP 的官方可选条目。它声明 `transport.type: http`，通过远程 MCP endpoint 连接；`auth.type: oauth`，走原生 MCP OAuth 流程。manifest 注释说明 Hermes 的 MCP client 和 `mcp_oauth_manager` 会处理 discovery、PKCE、token exchange 和 refresh，本地不需要安装 server。它没有显式声明 `tools.default_enabled`，因此安装时如果 probe 成功，工具选择清单默认全选，用户再手动裁剪。

`optional-mcps/n8n`：n8n MCP bridge 的官方可选条目。它声明 `transport.type: stdio`，启动命令指向 `${INSTALL_DIR}/.venv/bin/python` 和 `${INSTALL_DIR}/server.py`。它带有 `install.type: git`，安装时会 clone 上游仓库并运行 bootstrap：创建 `.venv`、安装 `requirements.txt`。鉴权类型是 `api_key`，需要 `N8N_BASE_URL` 和 `N8N_API_KEY`。它还声明了 `tools.default_enabled`，默认只启用偏只读的工作流和执行记录相关工具，把 activate/deactivate 等真实变更操作排除在默认选择之外。

## 关键入口

清单本身的关键入口是每个子目录下的 `manifest.yaml`。字段大致分为几组：

`manifest_version`：当前解析器只接受版本 `1`。

`name`、`description`、`source`：catalog 展示和查找用的基础元数据。`source` 指向外部来源，文档中只需理解为上游项目或服务来源，不应把它当成本地代码入口。

`transport`：安装后写入 `mcp_servers.<name>` 的连接方式。`stdio` 需要 `command` 和可选 `args`；`http` 需要 `url`，如果配合 OAuth，还会在配置中标记 `auth: oauth`。

`install`：可选安装步骤。当前 `n8n` 使用 `git` 安装，包含 `url`、`ref` 和 `bootstrap`。`linear` 没有这个字段，因为它连接远程 HTTP MCP server。

`auth`：安装时的凭据流程。`api_key` 会提示用户输入 env 项并写入 `~/.hermes/.env`；`oauth` 则交给 OAuth 相关流程；`none` 表示无凭据。

`tools.default_enabled`：安装时工具选择清单的默认勾选项，也是 probe 失败时的 fallback 选择。没有该字段时，语义是默认全开或不写工具过滤。

`post_install`：安装完成后展示给用户的提示文本，例如重新启动 Hermes session、运行 `hermes mcp configure <name>` 重新选择工具等。

## 主流程位置

目录读取和 manifest 解析的主流程在 `hermes_cli/mcp_catalog.py`。其中 `_catalog_root()` 通过 `get_optional_mcps_dir()` 找到 catalog 根目录；`_parse_manifest()` 读取并校验 `manifest.yaml`，把 YAML 转成 `CatalogEntry`、`TransportSpec`、`AuthSpec`、`InstallSpec`、`ToolsSpec` 等 dataclass；`list_catalog()` 遍历 `optional-mcps` 的直接子目录，只识别存在 `manifest.yaml` 的条目，并按名称排序返回；`get_entry()` 支持直接用 `name` 查找，也支持去掉 `official/` 前缀后查找。

目录定位的兼容逻辑在 `hermes_constants.py` 的 `get_optional_mcps_dir()`。它优先看 `HERMES_OPTIONAL_MCPS`，其次看打包安装的数据目录，再退回调用方传入的源码 checkout 默认路径，最后才落到 `get_hermes_home() / "optional-mcps"`。这说明 catalog 不只服务源码运行，也考虑了 wheel、Nix 或其他包管理器把数据文件放在 Python 包树外的情况。

安装主流程也在 `hermes_cli/mcp_catalog.py`。根据当前片段推断，`install_entry()` 会先处理 `install` 块：如果是 git 类型，就 clone 到 profile-aware 的 `~/.hermes/mcp-installs/<name>`，按 manifest 的 `ref` checkout，并执行 bootstrap。之后 `_build_server_config()` 把 manifest 的 `transport` 转成 `mcp_servers.<name>` 配置；`_prompt_env_vars()` 收集 `auth.env` 并写入 `.env`；`_apply_tool_selection()` 尝试 probe MCP server 的工具列表，让用户选择启用哪些工具，最后通过 `tools.include` 写回配置。这个推断依据是 `_do_git_install()`、`_build_server_config()`、`_prompt_env_vars()`、`_probe_tools()`、`_write_tools_include()` 和 `_apply_tool_selection()` 的注释与函数职责。

命令入口在 `hermes_cli/main.py` 和 `hermes_cli/mcp_config.py`。`main.py` 注册 `hermes mcp catalog`、`hermes mcp install`、`hermes mcp configure` 等子命令；`mcp_config.py` 实现配置、测试、列出、工具选择等交互逻辑。`optional-mcps` 目录本身不处理 CLI，只作为这些命令的输入数据源。

## 推荐阅读顺序

先读 `optional-mcps/linear/manifest.yaml` 和 `optional-mcps/n8n/manifest.yaml`，建立对 manifest 字段的直观认识：一个是远程 HTTP + OAuth，一个是本地 git 安装 + stdio + API key。

再读 `hermes_cli/mcp_catalog.py` 的顶部注释和 dataclass 区域，理解 catalog 的政策、数据模型和 schema 约束。重点看 `CatalogEntry`、`TransportSpec`、`AuthSpec`、`InstallSpec`、`ToolsSpec`。

然后读 `_parse_manifest()`、`list_catalog()`、`get_entry()`，掌握目录如何被扫描、哪些 YAML 会被接受、`official/<name>` 前缀如何兼容。

接着读安装相关函数：`_do_git_install()`、`_build_server_config()`、`_prompt_env_vars()`、`_apply_tool_selection()`。这些函数解释了 manifest 如何变成用户配置和可用 MCP 工具。

最后再看 `hermes_cli/mcp_config.py` 的 `cmd_mcp_configure()`、`_probe_single_server()` 以及 `hermes_cli/main.py` 的 mcp 子命令注册，确认用户命令如何落到 catalog 和配置层。

## 常见误区

不要把 `optional-mcps` 理解成“所有 MCP server 的实现目录”。当前这里没有 Python server 代码，只有 manifest。真正运行的 server 可能是远程 HTTP 服务，比如 `linear`；也可能是安装到用户目录下的外部项目，比如 `n8n`。

不要以为放进这个目录就会自动启用。catalog 条目默认禁用，必须由用户安装，安装后才写入 `mcp_servers`，并且通常需要新 session 才能加载工具。

不要把 `source` 或 `install.url` 当成运行时请求入口。运行时入口由 `transport` 决定：HTTP 看 `transport.url`，stdio 看 `transport.command` 和 `transport.args`。`source` 更多是来源说明，`install.url` 是安装来源。

不要忽略 `tools.default_enabled` 的安全含义。它不是工具全集，而是默认勾选或 probe 失败时的 fallback。`n8n` 选择偏只读工具作为默认，是为了降低安装后误触变更操作的风险。

不要在 manifest 里让依赖浮动。注释和代码都强调 MCP 不自动更新，git 安装应通过 manifest 的 `ref` 固定版本；用户需要重新执行 `hermes mcp install <name>` 才会刷新安装内容。

不要把凭据写入 catalog。manifest 只声明需要哪些 env 变量，安装时才提示用户输入，实际值进入用户的 `~/.hermes/.env`。这也符合仓库中 `.env` 只放 secrets 的配置约定。
