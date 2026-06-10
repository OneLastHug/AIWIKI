# 文件：hermes_constants.py

## 一句话定位

`hermes_constants.py` 是 Hermes Agent 的“低依赖基础常量与路径解析层”，核心职责是统一解析 `HERMES_HOME`、profile 目录、打包资源目录、运行环境特征和少量全局常量，供 CLI、gateway、cron、插件、工具和测试在任何导入阶段安全使用。

## 它暴露/定义了什么

这个文件主要暴露四类能力。

第一类是 Hermes 数据根目录解析：`get_hermes_home()`、`get_default_hermes_root()`、`display_hermes_home()`、`get_config_path()`、`get_env_path()`、`get_skills_dir()`。它们把“当前 Hermes 实例的数据目录在哪里”集中到一个入口，避免各处硬编码 `~/.hermes`。

第二类是 profile 与任务级覆盖：`set_hermes_home_override()`、`reset_hermes_home_override()`、`get_hermes_home_override()` 使用 `ContextVar` 做上下文局部覆盖，适合 cron job 等同一进程内临时切换 profile 的场景。

第三类是资源目录和兼容路径：`get_optional_skills_dir()`、`get_optional_mcps_dir()`、`get_bundled_skills_dir()` 会优先读取环境变量，再查 wheel 安装时的 data files，最后回退到源码或 `HERMES_HOME` 下目录；`get_hermes_dir()` 负责新旧目录兼容。

第四类是运行环境与公共配置：`is_termux()`、`is_wsl()`、`is_container()` 判断平台；`secure_parent_dir()` 做安全 chmod；`get_subprocess_home()` 为子进程提供 profile 隔离的 `HOME`；`parse_reasoning_effort()` 解析 reasoning 配置；`apply_ipv4_preference()` 可选择性修改 DNS 解析偏好；还定义了流式响应常量、OpenRouter 相关常量，其中真实外部地址此处不展开，记为 `[URL已移除]`。

## 谁调用它

调用面非常广。启动层 `hermes_cli/main.py` 会在早期 profile 覆盖、配置加载、IPv4 偏好等流程中使用它。交互 CLI `cli.py`、配置模块 `hermes_cli/config.py`、日志/诊断/状态相关模块 `hermes_cli/logs.py`、`hermes_cli/doctor.py`、`hermes_cli/status.py` 都依赖它定位配置、日志和用户提示路径。

gateway 侧的 `hermes_cli/gateway.py`、`gateway/*`、平台插件和 Windows 服务逻辑会用它确定服务运行目录、日志目录、会话目录和 profile root。`cron/scheduler.py` 用它在单个调度任务内临时切换 profile。`run_agent.py`、`mcp_serve.py`、`hermes_state.py` 相关路径也会间接或直接依赖 `get_hermes_home()`。插件系统与内置插件，如 `plugins/memory/*`、`plugins/google_meet/*`、`plugins/platforms/*`，也通过它把状态文件落到正确 profile 下。测试中大量 monkeypatch `hermes_constants.get_hermes_home`，说明它是路径行为的测试锚点。

## 它调用谁

该文件刻意只依赖标准库：`os`、`sysconfig`、`contextvars.ContextVar`、`pathlib.Path`，在 `apply_ipv4_preference()` 内部懒加载 `socket`，在 fallback 警告里懒加载 `sys`。它不导入 Hermes 内部模块，这是设计重点：因为很多模块会在 module import 阶段调用它，如果它反向依赖 CLI、日志或配置层，很容易产生循环导入或启动顺序问题。

## 核心流程

最核心流程是 `get_hermes_home()` 的解析顺序：先看上下文局部 override；再看环境变量 `HERMES_HOME`；如果都没有，则回退到 `Path.home() / ".hermes"`。回退时还有一个防错逻辑：如果默认根目录下存在 `active_profile` 且内容不是 `default`，说明当前进程可能忘记传递 profile 对应的 `HERMES_HOME`，函数会向 `stderr` 输出一次强警告，但仍返回默认目录。这样既能暴露跨 profile 写错数据的风险，又不会让大量导入期调用直接崩溃。

profile root 的流程由 `get_default_hermes_root()` 处理：如果没有 `HERMES_HOME`，返回默认 `~/.hermes`；如果 `HERMES_HOME` 位于默认目录下，也返回默认 root；如果路径形如 `<root>/profiles/<name>`，返回 `<root>`；否则把 `HERMES_HOME` 当作 Docker 或自定义部署 root。

资源目录解析流程则是：环境变量显式覆盖优先，其次查 `sysconfig` 的 `data`、`purelib`、`platlib` 下是否存在打包资源目录，再使用调用方传入的源码默认目录，最后才落到 `HERMES_HOME` 下。

## 关键函数的高层作用

`get_hermes_home()` 是本文件最关键函数，是所有 profile 安全路径的单一事实来源。任何状态文件、配置、缓存、日志、插件数据都应该从这里派生，而不是直接写 `Path.home() / ".hermes"`。

`display_hermes_home()` 面向用户展示路径，会尽量把用户主目录下路径压缩成 `~/...`，适合 CLI 文案、错误提示和日志标题；代码内部需要真实路径时不应使用它。

`set_hermes_home_override()` 和 `reset_hermes_home_override()` 提供进程内、上下文级别的临时目录切换，不修改 `os.environ`，因此比全局环境变量更适合异步或多任务场景。但当前片段中 `cron/scheduler.py` 仍会在 profile job 中同时快照/恢复环境变量，说明部分旧路径仍依赖环境变量。

`get_subprocess_home()` 不改变 Python 进程自身的 `HOME`，只告诉调用方：如果 `{HERMES_HOME}/home` 存在，子进程可以把它作为 `HOME`，让 git、ssh、npm 等工具的配置也隔离在 profile 内。

`secure_parent_dir()` 是安全防护函数，只在父目录不是 `/` 或一级系统目录时 chmod，避免错误路径导致对 `/usr`、`/home`、`/tmp` 等宿主目录做危险权限修改。

`apply_ipv4_preference()` 是全局 monkey patch，启用后会影响所有使用 `socket.getaddrinfo` 的库，因此虽然函数可重复调用，但属于高影响开关。

## 修改风险

最大风险是启动顺序和循环导入。这个文件被大量模块在导入期使用，新增任何 Hermes 内部依赖都可能破坏 CLI、gateway、测试或打包安装启动。

第二个风险是 profile 数据串写。`get_hermes_home()`、`get_default_hermes_root()`、`get_subprocess_home()` 的解析规则一旦改变，配置、会话、记忆、日志、cron、插件状态都可能写到错误目录。尤其要注意 `HERMES_HOME` 指向 root 和指向 `profiles/<name>` 时语义不同。

第三个风险是测试兼容性。测试大量 monkeypatch `get_hermes_home()` 或依赖其回退行为；如果改成缓存、提前 resolve、抛异常或读取配置文件，可能造成广泛回归。

第四个风险是平台误判和全局副作用。`is_wsl()`、`is_container()` 有进程级缓存；`apply_ipv4_preference()` 修改标准库 socket 行为；`secure_parent_dir()` 操作文件权限。修改这些函数时应优先保持幂等、懒加载、失败静默和标准库-only 的特性。
