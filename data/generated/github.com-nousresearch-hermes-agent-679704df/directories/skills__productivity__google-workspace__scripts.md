# 目录：skills/productivity/google-workspace/scripts

## 它负责什么

`skills/productivity/google-workspace/scripts` 是 `google-workspace` 技能的脚本层，负责把 Hermes 与 Google Workspace 的 OAuth 授权、令牌存储、命令行调用和具体 Google API 操作连接起来。它不是一个通用 SDK，也不是 Hermes 核心工具注册目录，而是技能内部自带的可执行辅助脚本目录。

从相邻的 `skills/productivity/google-workspace/SKILL.md` 看，这个技能覆盖 Gmail、Calendar、Drive、Contacts、Sheets、Docs 等能力。`scripts` 目录承担两类职责：第一类是一次性或维护性的授权流程，例如保存 OAuth client secret、生成授权 URL、交换授权码、检查或撤销 token；第二类是日常调用入口，例如搜索邮件、发送邮件、创建日历事件、检索 Drive 文件、读写 Sheets、创建或追加 Docs 内容。

这个目录的设计重点是“独立可运行”。脚本会自行处理 sibling import，把当前 `scripts` 目录加入 `sys.path`，并通过 `_hermes_home.py` 统一解析 Hermes profile 下的状态文件位置。这样即使脚本由系统 Python、CI、Nix 环境或外部 shell 直接运行，也能找到 `google_token.json`、`google_client_secret.json`、`google_oauth_pending.json` 这类状态文件。

## 直接子目录地图

当前片段显示该目录没有直接子目录，只有四个 Python 文件：

`skills/productivity/google-workspace/scripts/_hermes_home.py`：Hermes home 路径解析适配层。优先复用仓库里的 `hermes_constants.get_hermes_home()` 和 `display_hermes_home()`；如果 Hermes 模块不可导入，就退回到 `HERMES_HOME` 环境变量或默认 `~/.hermes`。这是其他脚本共享的路径基础。

`skills/productivity/google-workspace/scripts/setup.py`：OAuth2 设置入口。负责依赖检查、授权状态检查、保存 client secret、生成授权 URL、保存 PKCE pending 状态、交换授权码、写入 token、撤销 token。

`skills/productivity/google-workspace/scripts/google_api.py`：主要业务 CLI。它是日常使用 Google Workspace 功能的主入口，内部按服务拆成 Gmail、Calendar、Drive、Contacts、Sheets、Docs 多组函数，并在 `main()` 中注册 argparse 子命令。

`skills/productivity/google-workspace/scripts/gws_bridge.py`：`gws` CLI 桥接脚本。它读取 Hermes 管理的 Google token，必要时刷新 access token，然后以环境变量形式把有效 token 传给外部 `gws` 命令执行。

## 关键入口

最重要的入口是 `google_api.py` 和 `setup.py`。

`setup.py` 面向初始化和维护流程。它的 `main()` 使用互斥参数分发到 `check_auth()`、`check_auth_live()`、`store_client_secret()`、`get_auth_url()`、`exchange_auth_code()`、`revoke()`、`install_deps()`。从技能说明和脚本注释看，推荐流程是先运行 `--check` 判断是否已授权，再用 `--client-secret` 保存 OAuth client secret，随后用 `--auth-url` 生成授权链接，用户完成浏览器授权后把 code 或 redirect URL 交回给 `--auth-code`，最后再 `--check` 验证。

`google_api.py` 是使用期入口。它的 `main()` 通过 argparse 建立顶层服务名：`gmail`、`calendar`、`drive`、`contacts`、`sheets`、`docs`。每个服务下继续分发 action，例如 `gmail search/get/send/reply/labels/modify`，`calendar list/create/delete`，`drive search/get/upload/download/create-folder/share/delete`，`sheets get/update/append/create`，`docs get/create/append`。最终每个子命令都通过 `set_defaults(func=...)` 绑定到同名处理函数。

`gws_bridge.py` 的入口较窄，`main()` 只做三步：检查命令参数，调用 `get_valid_token()` 获取或刷新 access token，然后执行 `gws` 并透传退出码。它适合需要显式桥接外部 `gws` 命令的场景。

`_hermes_home.py` 没有命令行主入口，它是依赖入口。其他脚本通过 `from _hermes_home import get_hermes_home` 或同时导入 `display_hermes_home` 来确定 profile-aware 的状态目录。

## 主流程位置

授权主流程集中在 `setup.py`。`store_client_secret()` 负责把用户下载的 OAuth client JSON 校验后保存到 Hermes home；`get_auth_url()` 使用 client secret、scope 集合、localhost redirect 和 PKCE verifier 生成授权 URL，并把 `state`、`code_verifier`、`redirect_uri` 写入 `google_oauth_pending.json`；`exchange_auth_code()` 读取 pending 状态，接受原始 code 或完整 redirect URL，校验 state 后换取 token，并把授权结果写入 `google_token.json`；`check_auth()` 和 `check_auth_live()` 负责验证本地凭据是否仍可用；`revoke()` 负责远端撤销和本地清理。

业务调用主流程集中在 `google_api.py`。所有命令先经过 `_ensure_authenticated()` 或 `get_credentials()` 保障 token 存在并可刷新。脚本优先检测 `_gws_binary()`：如果系统中有 `gws` 或设置了 `HERMES_GWS_BIN`，部分操作会走 `_run_gws()`，把 Hermes token 文件作为 `GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE` 交给外部 CLI；如果没有 `gws`，则通过 `googleapiclient.discovery.build()` 构造对应服务对象，直接调用 Google Python client。根据当前片段推断，这种“双后端”设计是为了让 Hermes 保持原有 JSON 输出契约，同时在可用时借助 `gws` 获得更广的 Workspace 覆盖。

令牌刷新和桥接流程分散在 `google_api.py` 与 `gws_bridge.py`。`google_api.py` 的 `get_credentials()` 使用 Google auth 库从 `google_token.json` 加载凭据，过期时刷新并回写标准化 payload。`gws_bridge.py` 则用标准库手写 refresh token 请求，刷新后把 access token 放入 `GOOGLE_WORKSPACE_CLI_TOKEN`，再调用外部 `gws`。

路径解析主流程在 `_hermes_home.py`。它屏蔽了脚本运行环境差异，避免每个脚本重复写 `Path.home() / ".hermes"`，也让 profile、Docker 或未来 Hermes home 逻辑能从核心常量模块继承。

## 推荐阅读顺序

建议先读 `skills/productivity/google-workspace/SKILL.md` 的 `Scripts`、`First-Time Setup` 和 `Usage` 部分，建立用户视角：这个技能如何被 Hermes 调用，哪些命令是公开约定。

然后读 `_hermes_home.py`，因为它很短，但解释了所有状态文件为什么写到 Hermes home，以及脚本为何不直接依赖当前工作目录。

第三步读 `setup.py` 的顶部常量、`main()` 和 OAuth 相关函数。重点看 `TOKEN_PATH`、`CLIENT_SECRET_PATH`、`PENDING_AUTH_PATH`，以及 `get_auth_url()` 到 `exchange_auth_code()` 的状态流转。

第四步读 `google_api.py` 的 `main()`，先从 argparse 子命令地图理解能力边界，再按服务挑选函数阅读。概览阶段不需要逐个操作深挖，先掌握“命令解析 → 认证 → 可选 gws 后端 → Python client fallback → JSON 输出”的模式即可。

最后读 `gws_bridge.py`，它是补充入口，帮助理解 Hermes 管理的 token 如何复用于外部 `gws` CLI。

## 常见误区

不要把 `scripts` 目录理解成 Hermes 核心 toolset。它没有在 `tools/registry.py` 里注册工具，而是技能说明中暴露的一组可执行脚本，通常由 agent 通过 shell 命令调用。

不要以为只有 `google_api.py` 需要读。日常 API 操作依赖 `google_token.json`，而 token 的生成、scope、刷新失败处理和撤销都在 `setup.py`。排查认证问题时直接看业务函数往往会漏掉 pending OAuth、PKCE state、client secret 存储这些关键状态。

不要假设 `gws` 一定存在。`google_api.py` 明确做了 `_gws_binary()` 检测：存在时优先使用外部 `gws`，不存在时回退到 Google Python client。因此行为差异可能来自运行环境是否安装了 `gws` 或是否设置了 `HERMES_GWS_BIN`。

不要手写固定的 `~/.hermes` 路径。这个目录已经通过 `_hermes_home.py` 统一处理 `HERMES_HOME` 和 Hermes 核心路径逻辑；新增脚本或排查状态文件时，应沿用 `get_hermes_home()`。

不要把 `setup.py --auth-url` 生成的 pending 状态当成可长期复用。`exchange_auth_code()` 依赖 `google_oauth_pending.json` 中的 state 和 code verifier；如果用户用了旧浏览器页、旧 code 或 state 不匹配，正确处理方式是重新生成授权 URL。
