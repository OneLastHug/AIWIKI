# 文件：platform/.pre-commit-config.yaml

## 一句话定位

`platform/.pre-commit-config.yaml` 是 `platform` Python 后端子项目的提交前质量门禁配置，负责把格式化、静态检查、类型检查和基础文件规范检查串成一条本地 Git hook 流水线，尽量在代码进入提交前发现低成本问题。

## 它暴露/定义了什么

这个文件暴露给 `pre-commit` 框架的是一组 `repos` 和 `hooks` 定义。它本身不定义业务函数、类或运行时 API，而是声明哪些检查工具会被执行、从哪里获取 hook、用哪个版本、对哪些文件类型生效、以及具体命令参数。

配置分为两类：

第一类是外部 hook 仓库，包括 `pre-commit-hooks`、`add-trailing-comma`、`language-formatters-pre-commit-hooks`。它们提供通用文件检查与 YAML 格式化能力，例如 Python AST 可解析性、行尾空白、TOML 合法性、文件末尾换行、自动补尾随逗号、YAML 自动格式化。

第二类是 `repo: local` 本地 hook，入口统一通过 `poetry run ...` 调用项目开发依赖中的工具，包括 `black`、`autoflake`、`isort`、`flake8`、`mypy`。这些 hook 与 `platform/pyproject.toml`、`platform/.flake8`、`platform/poetry.lock` 共同构成后端代码风格和质量规则。

## 谁调用它

直接调用者是 `pre-commit` 命令行工具。开发者在 `platform` 目录内执行 `pre-commit install` 后，Git 会在提交阶段触发已安装的 hook，`pre-commit` 读取 `.pre-commit-config.yaml` 并按配置运行检查。README 的 `Pre-commit` 小节明确说明该文件用于配置提交前检查，并列出默认运行 `black`、`mypy`、`isort`、`flake8`。

根据当前片段推断，CI 也可能复用这套配置运行 `pre-commit run --all-files`，但当前读取到的片段没有发现 CI 文件中的直接证据，因此不能断言它一定在远端流水线执行。

## 它调用谁

外部 hook 侧，它调用：

`check-ast` 用于确认 Python 文件能被解析为 AST；`trailing-whitespace` 清理行尾空白；`check-toml` 校验 TOML 文件；`end-of-file-fixer` 修复文件末尾换行；`add-trailing-comma` 为多行结构补尾随逗号；`pretty-format-yaml` 使用 `--autofix`、`--preserve-quotes`、`--indent=2` 格式化 YAML。

本地 hook 侧，它调用：

`poetry run black` 格式化 Python；`poetry run autoflake` 删除未使用 import 和重复 key；`poetry run isort` 排序 import；`poetry run flake8 --count .` 做 lint；`poetry run mypy reworkd_platform` 做类型检查。

这些命令依赖 `platform/pyproject.toml` 中的开发依赖和工具配置，例如 `isort` 使用 `profile = "black"`，`mypy` 使用严格模式但忽略缺失第三方类型，`flake8` 读取 `platform/.flake8` 的复杂度、行长、忽略规则和排除目录。

## 核心流程

一次提交触发后，`pre-commit` 先根据 Git 暂存文件筛选 hook 适用范围。通用 hook 会先处理跨语言或文件级规则：检查语法、空白、TOML、EOF、尾随逗号、YAML 格式。这一阶段的重点是保证文件基础结构稳定，部分 hook 会自动改写文件。

随后进入本地 Python 工具链。`black`、`autoflake`、`isort` 都属于可能改写文件的自动修复型步骤；如果它们修改了文件，提交通常会被中断，开发者需要重新查看并暂存变更。`flake8` 和 `mypy` 更偏校验型：前者检查风格、复杂度、潜在 bug 和项目约定，后者对 `reworkd_platform` 包执行类型分析。因为 `flake8` 和 `mypy` 都设置了 `pass_filenames: false`，它们不会只检查本次暂存文件，而是按参数检查更大的项目范围，这提高了发现跨文件问题的概率，也会增加提交前耗时。

## 关键函数的高层作用

该文件没有业务函数或辅助函数，核心“执行单元”应理解为 hook。

`black` 是统一代码格式的主格式器，目标是减少人工风格争议，并与 `isort` 的 `black` profile 对齐。

`autoflake` 是清理型 hook，主要删除所有未使用 import 和重复字典 key。它会直接改写 Python 文件，因此对导入副作用敏感。

`isort` 专管 import 顺序，结合 `pyproject.toml` 的 `src_paths = ["reworkd_platform"]` 区分本地包和第三方包。

`flake8` 是规则聚合检查器，受 `.flake8` 控制；当前项目启用了较严格的 `wemake-python-styleguide` 生态，但也通过大量 ignore 和 per-file-ignores 调整到项目可接受的强度。

`mypy` 是类型边界检查器，只检查 `reworkd_platform`，并排除 `tests`。它开启 `strict = true`，但又允许若干现实妥协项，例如 `ignore_missing_imports`、`allow_untyped_calls`、`allow_untyped_decorators`。

通用 hook 是基础卫生检查，职责较窄：保证可解析、无多余空白、配置文件格式合法和 YAML 风格一致。

## 修改风险

最大风险是改变 hook 顺序或范围导致开发体验和提交结果变化。比如把 `flake8` 放在格式化工具之前，会让开发者先看到可自动修复的问题；移除 `pass_filenames: false` 会让 `flake8`、`mypy` 只看局部文件，提交更快但可能漏掉跨文件类型或 lint 问题。

升级外部 hook 的 `rev` 会带来规则行为变化，尤其是 YAML 格式器、尾随逗号工具和基础文件修复工具，可能产生大量机械 diff。升级 `black`、`isort`、`mypy`、`flake8` 则主要通过 `pyproject.toml` 和 `poetry.lock` 体现，可能引入新的格式规则、类型报错或 lint 报错。

调整 `autoflake` 风险较高，因为 `--remove-all-unused-imports` 会删除看似未使用的导入。如果项目存在依赖 import 副作用、注册逻辑或动态加载，该 hook 可能造成隐性行为变化。当前配置没有对这类文件设置例外，修改前应先全量运行并检查 diff。

修改 `mypy` 的目标参数也要谨慎。当前只检查 `reworkd_platform` 且排除测试，如果扩大到 `.`，测试、脚本或迁移文件可能暴露大量新问题；如果缩小检查范围，则会削弱类型门禁。

最后，这个文件使用 `language: system` 和 `poetry run`，说明 hook 不由 pre-commit 自建隔离环境安装本地工具，而依赖开发者已在 `platform` 环境中正确安装 Poetry 依赖。若改成远程 hook 或隔离语言环境，需要同步考虑版本锁定、执行速度和与 `poetry.lock` 的一致性。
