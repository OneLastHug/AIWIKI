# 文件：pyproject.toml

## 一句话定位

`pyproject.toml` 是 Hermes Agent 的 Python 项目元数据、依赖边界、打包规则、命令行入口和测试/静态检查策略的集中声明文件；它决定“安装什么、发布什么、命令从哪里启动、CI 如何约束代码质量”。

## 它暴露/定义了什么

它首先通过 `[build-system]` 声明使用 `setuptools.build_meta` 构建，并要求 `setuptools>=61.0`。`[project]` 定义包名 `hermes-agent`、版本 `0.15.1`、Python 下限 `>=3.11`、作者、许可证、README，以及核心依赖。这个仓库的依赖策略非常明确：核心依赖使用精确版本 `==`，注释中说明这是为了降低供应链风险；只有“每个 Hermes session 都会用到”的包才能进入核心依赖。

`[project.optional-dependencies]` 定义大量可选 extras，例如 `anthropic`、`exa`、`firecrawl`、`fal`、`messaging`、`mcp`、`web`、`voice`、`google`、`youtube`、`all` 等。它们对应不同 provider、搜索后端、TTS/STT、网关平台、Dashboard、ACP、技能依赖和开发依赖。这里的关键设计是：很多后端依赖不放进 `[all]`，而是依赖运行时 lazy install 机制，避免某个可选后端的坏版本拖垮所有安装。

`[project.scripts]` 暴露三个可执行命令：`hermes` 指向 `hermes_cli.main:main`，`hermes-agent` 指向 `run_agent:main`，`hermes-acp` 指向 `acp_adapter.entry:main`。这意味着用户安装 wheel 后，终端命令不是 shell 脚本手写分发，而是由 Python packaging 生成入口。

`[tool.setuptools]`、`[tool.setuptools.package-data]`、`[tool.setuptools.packages.find]` 控制 wheel 内包含哪些顶层模块、包和非 Python 文件。特别是 `hermes_cli` 的 `web_dist`、`tui_dist`、安装脚本，`gateway` 的 assets，以及 `plugins` 的 `plugin.yaml`、`plugin.yml` 都被显式纳入包数据。注释表明，插件 manifest 如果没有进入 wheel，插件扫描会找不到内置插件，导致 gateway platform、web-search provider 等功能缺失。

`[tool.pytest.ini_options]` 定义测试发现目录、marker 和默认 `addopts`。默认排除 `integration`，并为每个测试设置 30 秒超时。`[tool.ty.*]` 配置类型检查环境与规则。`[tool.ruff.*]` 只启用 `PLW1514`，用于禁止文本模式下未显式 encoding 的 `open()`、`read_text()`、`write_text()`，并为 tests、skills、optional-skills、plugins 做 per-file ignore。

## 谁调用它

安装和构建工具直接读取它：`pip`、`uv`、`python -m build`、`setuptools` 会使用 `[build-system]`、`[project]`、`[project.optional-dependencies]` 和 setuptools 配置生成 sdist/wheel。

运行入口由 packaging 读取 `[project.scripts]` 后生成，最终把 `hermes` 路由到 `hermes_cli.main:main`，把 `hermes-agent` 路由到 `run_agent:main`，把 `hermes-acp` 路由到 `acp_adapter.entry:main`。

发布流程会修改它。`scripts/release.py` 的 `update_version_files()` 会用正则更新 `pyproject.toml` 的 `version`，并同步更新 `hermes_cli/__init__.py` 与 ACP registry manifest，说明该文件是 release version 的权威来源之一。

安装脚本也依赖它。根据当前片段推断，`scripts/install.ps1` 会解析 `[project.optional-dependencies].all`，分层安装 extras，而不是维护一份手写镜像；依据是脚本注释提到从 `pyproject.toml` 解析 `[all]`，避免版本漂移。

测试和 CI 也调用它。`scripts/run_tests.sh` 最终执行 pytest，pytest 会读取 `[tool.pytest.ini_options]`。`tests/test_lint_config.py` 直接用 `tomllib` 读取 `pyproject.toml`，断言 `ruff.preview = true` 且 `PLW1514` 保留在 select 列表中。

## 它调用谁

`pyproject.toml` 本身不是可执行代码，不主动调用函数或模块；它通过声明把控制权交给外部工具和入口模块。构建时交给 `setuptools.build_meta`。命令运行时交给 `hermes_cli.main:main`、`run_agent:main`、`acp_adapter.entry:main`。测试时把默认参数交给 pytest。lint/typecheck 时分别把规则交给 `ruff` 和 `ty`。打包时 setuptools 根据声明收集 `agent`、`tools`、`hermes_cli`、`gateway`、`tui_gateway`、`cron`、`acp_adapter`、`plugins`、`providers` 等包，以及指定 package data。

## 核心流程

安装流程大致是：包管理器读取 `pyproject.toml`，确认 build backend，解析项目元数据和依赖；用户选择基础安装或 extras，例如 `hermes-agent[web]`、`hermes-agent[all]`；setuptools 根据 `py-modules`、`packages.find` 和 `package-data` 构建 wheel；安装后生成 `hermes` 等 console scripts；运行命令时进入对应 Python 模块。

发布流程是：`scripts/release.py` 计算新版本，更新 `pyproject.toml` 的 `version`，同步相关版本文件，再构建发布产物。由于 `uv.lock` 被注释要求与依赖变更同步，依赖更新的标准流程是修改此文件中的 pin，然后执行 `uv lock` 重新解析传递依赖。

测试流程是：开发者通常运行 `scripts/run_tests.sh`，脚本激活虚拟环境并进入隔离环境，再调用并行测试 runner；每个 pytest 子进程会读取这里的 pytest 配置，默认跳过 integration，并套用 timeout。CI 的 lint 流程则读取 Ruff 配置并运行 `ruff check .`。

## 关键函数的高层作用

这个文件没有 Python 函数，但它定义了三个关键“入口函数”映射：`hermes_cli.main:main` 是主 CLI 入口，承载用户日常 `hermes` 命令；`run_agent:main` 是较直接的 agent 运行入口；`acp_adapter.entry:main` 是 ACP 集成入口。

与它强相关的核心函数是 `scripts/release.py` 中的 `update_version_files()`：它负责把 release 版本写回 `pyproject.toml`，并保持其他版本声明同步。`tests/test_lint_config.py` 中的 `_load_pyproject()` 是辅助函数，只负责把 TOML 解析成 dict，用于保护 Ruff 配置不被误删。

## 修改风险

最高风险是依赖区。核心依赖使用精确 pin，任何新增、删除或升级都会影响所有用户安装；如果忘记同步 `uv.lock`，本地、CI、发布产物可能出现解析漂移。把 provider、TTS/STT、搜索、平台网关等可选依赖误放入核心或 `[all]`，会扩大安装体积和供应链攻击面，也可能破坏 Windows、macOS、Termux、Homebrew、Nix 等环境。

第二类风险是打包规则。`package-data` 中的 `web_dist`、`tui_dist`、插件 manifest、gateway assets 看似只是资源文件，但缺失后会造成运行期功能“安装成功但不可用”。尤其是 `plugins` 的 `plugin.yaml`/`plugin.yml`，注释已经说明它们是插件发现的关键输入。

第三类风险是命令入口。修改 `[project.scripts]` 会直接影响用户终端命令、安装脚本、文档和自动化集成。入口模块移动时必须同步这里，否则 wheel 安装后命令会启动失败。

第四类风险是测试与 lint 配置。`PLW1514` 是为 Windows 编码问题设置的硬约束，并有测试专门防删除；移除 `preview = true` 或 `select = ["PLW1514"]` 会让规则失效。pytest 默认排除 integration 和设置 timeout，也影响 CI 运行成本与稳定性，随意放宽可能导致测试变慢或外部服务依赖泄漏到普通测试。
