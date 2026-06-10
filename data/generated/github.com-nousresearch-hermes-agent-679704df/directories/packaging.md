# 目录：packaging

## 它负责什么

`packaging` 是 Hermes Agent 面向系统级包管理器的打包材料目录。根据当前目录片段，它目前只承载 Homebrew 相关内容，也就是把 Python 项目 `hermes-agent` 包装成 macOS / Linux Homebrew formula 的参考实现。它不是项目的通用构建入口，也不负责运行时安装脚本、Docker 镜像、Windows 安装器或 PyPI 元数据；这些能力分别分散在 `pyproject.toml`、`scripts/install.sh`、`scripts/install.ps1`、`Dockerfile`、`scripts/release.py` 等邻近位置。

这个目录的核心职责可以概括为三件事：第一，定义 Homebrew 如何下载 Hermes 的发布源码包；第二，定义 Homebrew 环境里应该如何创建 Python virtualenv、安装 Python 依赖、暴露 CLI 可执行文件；第三，为包管理器托管安装写入运行时环境变量，让 Hermes 知道自己由 Homebrew 管理，从而在 `hermes update` 等自更新路径上提示用户使用包管理器升级，而不是尝试修改包管理器安装的文件。

## 直接子目录地图

`packaging` 下面目前只有一个直接子目录：`packaging/homebrew`。

`packaging/homebrew` 是 Homebrew formula 的存放区。它包含 `packaging/homebrew/hermes-agent.rb` 和 `packaging/homebrew/README.md`。前者是实际 formula 草案，后者是维护说明。根据当前片段推断，`packaging` 目前不是多平台打包目录，而是先为 Homebrew 留出的打包空间；如果未来加入 Debian、RPM、Nix、AUR 等材料，应该也会以同级子目录的形式扩展，但当前仓库片段中没有这些目录。

## 关键入口

最关键入口是 `packaging/homebrew/hermes-agent.rb`。它定义 `HermesAgent < Formula`，并引入 `Language::Python::Virtualenv`，说明 Homebrew 安装流程会创建独立 Python virtualenv，而不是直接使用系统 Python site-packages。formula 中的 `desc`、`homepage`、`url`、`sha256`、`license` 描述包元信息和源码包来源；真实链接在文档中不展开，源码里由 formula 字段维护。

依赖入口也在这个 formula 中。它声明 `certifi`、`cryptography`、`libyaml`、`python@3.14` 等 Homebrew 依赖，并通过 `pypi_packages ignore_packages: %w[certifi cryptography pydantic]` 控制 Python 资源生成时的排除项。这里的意图是让部分底层包由 Homebrew 或特定策略管理，避免 formula 盲目内联所有 PyPI 资源。

安装入口是 formula 的 `install` 方法。它先执行 `virtualenv_create(libexec, "python3.14")` 创建运行环境，再 `venv.pip_install resources` 安装 Homebrew 生成的 Python 资源，接着 `venv.pip_install buildpath` 安装当前源码包。随后它把仓库中的 `skills` 和 `optional-skills` 安装到 `pkgshare`，最后为 `hermes`、`hermes-agent`、`hermes-acp` 这些可执行文件写入 Homebrew wrapper。

另一个入口是 `packaging/homebrew/README.md`。它不是运行时文件，而是 formula 维护者的更新清单，提醒维护者更新 `url`、`version`、`sha256`，重新生成 Python resources，并运行 Homebrew audit 和 test。

## 主流程位置

Homebrew 打包的主流程从发布产物开始，而不是从 Git tag tarball 直接开始。`packaging/homebrew/README.md` 明确说明稳定构建应指向每次 GitHub release 附带的 semver 命名 sdist 资产，而不是 CalVer tag tarball。对应的发布侧逻辑在 `scripts/release.py` 的 `build_release_artifacts(semver)`：它优先执行 `uv build --sdist --wheel`，没有 `uv` 时回退到 `python -m build --sdist --wheel`，并筛选文件名中包含 semver 的产物。发布脚本中的注释也说明，这些 semver 命名的 Python artifacts 是给下游打包器，例如 Homebrew，避免依赖 CalVer tag 名称。

安装侧主流程在 `packaging/homebrew/hermes-agent.rb` 的 `install` 方法。安装完成后，wrapper 会导出三个关键环境变量：`HERMES_BUNDLED_SKILLS`、`HERMES_OPTIONAL_SKILLS`、`HERMES_MANAGED`。前两个把运行时技能目录指向 Homebrew 安装的共享资源目录，使 `tools/skills_sync.py` 这类技能同步逻辑能找到打包进来的 `skills` 和 `optional-skills`。第三个设置为 `homebrew`，让 Hermes 进入包管理器托管模式。

托管模式的主流程在 `hermes_cli/config.py`。`get_managed_system()` 会读取 `HERMES_MANAGED`，把 `homebrew` 或 `brew` 识别为 `Homebrew`；`get_managed_update_command()` 和 `recommended_update_command_for_method()` 会返回 `brew upgrade hermes-agent`；`format_managed_message()` 会在用户尝试执行不适合托管安装的自修改动作时，输出由 Homebrew 管理的说明。formula 的 `test` 方法正是验证这一点：先检查 `hermes version`，再运行 `hermes update`，确认输出中包含 Homebrew 托管提示和升级命令。

项目元数据主流程在 `pyproject.toml`。这里定义包名 `hermes-agent`、版本、依赖、optional dependencies、console scripts，以及 setuptools 的包数据规则。Homebrew formula 最终安装的是这个 Python 项目，因此 `pyproject.toml` 中的 `[project.scripts]` 决定了 `hermes`、`hermes-agent`、`hermes-acp` 这些命令从哪里来；`[tool.setuptools.package-data]` 和 `[tool.setuptools.packages.find]` 决定 wheel / sdist 中哪些包和资源会被带上。`packaging/homebrew` 本身只消费这些定义，不重新定义 Python 包结构。

## 推荐阅读顺序

建议先读 `packaging/homebrew/README.md`，它短而直接，能先建立 Homebrew 打包的维护模型：使用 semver sdist、刷新 Python resources、保留 ignore packages、执行 audit 和 test。

第二步读 `packaging/homebrew/hermes-agent.rb`。重点看四块：元信息字段、`depends_on` 和 `pypi_packages`、`install` 方法、`test` 方法。读完这份 formula，基本就能理解 Homebrew 安装时下载什么、安装什么、包装哪些命令、如何标记托管模式。

第三步读 `pyproject.toml` 的 `[project]`、`[project.optional-dependencies]`、`[project.scripts]`、`[tool.setuptools]`、`[tool.setuptools.package-data]`。这里解释 formula 中 `venv.pip_install buildpath` 到底会安装出什么，以及为什么某些重依赖，例如 `voice` extra 中的 `faster-whisper`，不会进入 Homebrew 基础安装。

第四步读 `scripts/release.py` 中 `build_release_artifacts(semver)` 及其附近发布流程，理解 formula 的 `url` 应该指向哪类 release asset。最后再看 `hermes_cli/config.py` 中 `get_managed_system()`、`recommended_update_command_for_method()`、`format_managed_message()`，确认 `HERMES_MANAGED=homebrew` 对运行时行为的影响。

## 常见误区

第一个误区是把 `packaging` 当成项目构建系统入口。实际 Python 包构建入口是 `pyproject.toml`，发布产物构建在 `scripts/release.py`，安装脚本在 `scripts/install.sh` 和 `scripts/install.ps1`。`packaging/homebrew` 只是 Homebrew 这个下游包管理器的打包描述。

第二个误区是认为 formula 应该指向仓库 tag tarball。当前维护说明明确要求稳定构建指向 release 附带的 semver 命名 sdist。原因是项目标签可能使用另一套命名节奏，而 Python 包版本和下游打包更适合绑定 semver 产物。

第三个误区是忽略 `skills` 和 `optional-skills`。Hermes 的运行时不只是 Python 模块，还依赖这些技能资源。Homebrew wrapper 设置 `HERMES_BUNDLED_SKILLS` 和 `HERMES_OPTIONAL_SKILLS`，就是为了让打包安装后的技能同步逻辑能找到正确资源目录。

第四个误区是让 `hermes update` 在 Homebrew 安装中直接更新自身。formula 设置 `HERMES_MANAGED=homebrew` 后，运行时会把升级动作交还给包管理器。这样做可以避免 Hermes 自更新破坏 Homebrew 管理的 virtualenv、链接和文件归属。

第五个误区是把 optional dependencies 全部塞进 Homebrew 基础 formula。`pyproject.toml` 注释显示，项目有意把 provider-specific、语音、消息平台等依赖放到 extras 或 lazy install 路径中。Homebrew formula 的基础安装应保持较小依赖面，尤其避免 wheel-only 或平台敏感的重依赖污染基础包。
