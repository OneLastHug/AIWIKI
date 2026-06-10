# 目录：packaging/homebrew

## 它负责什么

`packaging/homebrew` 是 Hermes Agent 面向 Homebrew 生态的打包入口目录。它不包含应用运行时代码，也不实现 CLI、agent loop、gateway 或插件逻辑；它的职责是把仓库发布出来的 Python 包装成 Homebrew formula，让 macOS/Homebrew 用户可以用 `brew install`、`brew upgrade hermes-agent` 这类包管理器流程安装和升级 Hermes。

这个目录的核心关注点有三类：第一，声明 Homebrew 如何取得 Hermes 的稳定源码包；第二，说明 Python virtualenv 安装、入口命令包装、运行时资源安装这些打包动作；第三，通过环境变量告诉 Hermes “当前安装由 Homebrew 托管”，从而让 `hermes update` 之类的自更新路径改为提示用户走 `brew upgrade hermes-agent`。

根据当前片段推断，这个目录更多是“给维护者和 downstream packager 使用的模板/起点”，不是仓库日常开发的构建系统。依据是 `packaging/homebrew/README.md` 明确说 `packaging/homebrew/hermes-agent.rb` 可作为 tap 或 `homebrew-core` 的 starting point，同时 formula 中的 `sha256` 仍是占位值 `<replace-with-release-asset-sha256>`。

## 直接子目录地图

`packaging/homebrew` 当前没有直接子目录，只有两个文件：

`packaging/homebrew/hermes-agent.rb` 是 Homebrew formula 本体。它定义 `HermesAgent < Formula`，使用 `Language::Python::Virtualenv`，声明依赖、资源处理、安装逻辑和 Homebrew 测试逻辑。

`packaging/homebrew/README.md` 是维护说明。它解释 formula 应如何作为 tap 或 `homebrew-core` 起点使用，并列出更新 formula 时要遵守的关键选择，例如使用 semver 命名的 sdist、保留 `ignore_packages`、运行 `brew audit` 和 `brew test`。

因为目录很小，阅读时不需要把它当成一个独立子系统展开；更合适的理解方式是：`hermes-agent.rb` 是机器可执行的打包规格，`README.md` 是维护者流程注释。

## 关键入口

最关键入口是 `packaging/homebrew/hermes-agent.rb`。

formula 顶部的元信息定义了包名对应的 Ruby 类 `HermesAgent`，描述文本 `desc`、项目主页 `homepage`、源码 `url`、校验 `sha256` 和许可证 `license`。其中源码 `url` 的注释很重要：稳定源码应指向 release 附带的 semver 命名 sdist 资产，而不是 CalVer tag tarball。也就是说，Homebrew 侧更关心 Python 包版本资产，例如 `hermes_agent-0.6.0.tar.gz`，而不是只按日期命名的 git tag 包。

依赖入口集中在 `depends_on` 和 `pypi_packages`。当前 formula 依赖 `python@3.14`、`libyaml`，并把 `certifi`、`cryptography` 作为 `:no_linkage` 依赖处理。`pypi_packages ignore_packages: %w[certifi cryptography pydantic]` 说明 Python 依赖资源由 Homebrew 的 Python resource 机制维护，但这几个包需要特殊忽略，避免和 Homebrew 自身或构建策略冲突。

安装入口是 `def install`。它创建 Homebrew 管理的 virtualenv，把 Python resources 和当前 buildpath 安装进去，然后把仓库中的 `skills`、`optional-skills` 安装到 `pkgshare`。最后它为 `hermes`、`hermes-agent`、`hermes-acp` 三个可能存在的可执行入口写入 Homebrew wrapper。

验证入口是 `test do`。测试首先运行 `#{bin}/hermes version`，确认输出包含当前 formula 版本；然后运行 `#{bin}/hermes update`，确认它不会尝试自行更新，而是提示 “managed by Homebrew” 和 `brew upgrade hermes-agent`。

## 主流程位置

这个目录的主流程可以按“发布资产 → 更新 formula → 安装包装 → 运行期识别托管安装”理解。

发布资产的上游位置在 `scripts/release.py`。其中 `build_release_artifacts()` 会构建 sdist 和 wheel，发布流程中也有注释说明：构建 semver 命名的 Python artifacts，是为了让 Homebrew 等 downstream packager 不依赖 CalVer tag 名称。`packaging/homebrew/hermes-agent.rb` 顶部的源码注释与这里相互呼应。

Python 包元数据的上游位置在 `pyproject.toml`。这里定义项目名 `hermes-agent`、版本、核心依赖、extras，以及三个 console scripts：`hermes = "hermes_cli.main:main"`、`hermes-agent = "run_agent:main"`、`hermes-acp = "acp_adapter.entry:main"`。Homebrew formula 安装后包装的三个命令，正是这些 entry points 在 virtualenv 中生成的可执行文件。

运行时资源定位的主流程在 `hermes_constants.py`。`get_bundled_skills_dir()` 会优先读取 `HERMES_BUNDLED_SKILLS`，`get_optional_skills_dir()` 会优先读取 `HERMES_OPTIONAL_SKILLS`。formula 在 wrapper 中设置这两个变量，指向 `pkgshare/"skills"` 和 `pkgshare/"optional-skills"`，使 Homebrew 安装的 Hermes 能找到随包分发的技能目录，而不是误用源码树路径或用户 home 下的默认路径。

包管理器托管识别的主流程在 `hermes_cli/config.py`。`get_managed_system()` 会读取 `HERMES_MANAGED`，其中 `homebrew` 会被映射为 `Homebrew`；`get_managed_update_command()` 和 `recommended_update_command_for_method()` 会把 Homebrew 安装的更新建议解析为 `brew upgrade hermes-agent`；`format_managed_message()` 会生成 “managed by Homebrew” 的用户提示。formula 的 `HERMES_MANAGED: "homebrew"` 正是接入这条逻辑的关键。

## 推荐阅读顺序

建议先读 `packaging/homebrew/README.md`，它最短，能先建立维护者视角：这个目录是 formula 起点，更新时要改 `url`、`version`、`sha256`，刷新 Python resources，并保留特定 ignore 列表。

然后读 `packaging/homebrew/hermes-agent.rb`。重点看四块：元信息和源码 `url` 注释、`depends_on` 与 `pypi_packages`、`def install`、`test do`。这能把 Homebrew 的安装模型和 Hermes 的运行时需求连起来。

接着跳到 `pyproject.toml` 的 `[project]`、`[project.optional-dependencies]`、`[project.scripts]`。这里能解释 formula 为什么要包装 `hermes`、`hermes-agent`、`hermes-acp`，也能理解 README 为什么强调 `voice` extra 中的 `faster-whisper` 不应进入基础 Homebrew formula：它会带来 wheel-only 的重型传递依赖，不适合基础源码构建包。

最后读 `hermes_constants.py` 和 `hermes_cli/config.py` 中与 `HERMES_BUNDLED_SKILLS`、`HERMES_OPTIONAL_SKILLS`、`HERMES_MANAGED` 相关的函数。这样可以确认 formula 设置环境变量后，实际运行的 Hermes 如何定位技能资源、如何阻止自更新、如何提示用户改用 Homebrew 升级。

## 常见误区

一个常见误区是把 `packaging/homebrew` 当成 Hermes 的通用安装器。实际通用安装脚本主要在 `scripts/install.sh`、`scripts/install.ps1` 等路径；Homebrew 目录只服务 Homebrew packaging，不负责普通用户的一键安装流程。

第二个误区是认为 formula 应直接指向 git tag 自动生成的 tarball。当前说明明确要求稳定构建使用 release 附带的 semver 命名 sdist 资产。这样 Homebrew 看到的是 Python 包语义下的发布物，而不是只反映仓库快照的 tag tarball。

第三个误区是忽略 wrapper 环境变量。`HERMES_BUNDLED_SKILLS` 和 `HERMES_OPTIONAL_SKILLS` 不是装饰性变量，它们决定 packaged install 如何找到随包安装的技能资源；`HERMES_MANAGED=homebrew` 也不是只用于显示，它会改变更新命令和受管安装保护逻辑。

第四个误区是把 `hermes update` 当成 Homebrew 安装后的升级入口。formula 的测试明确验证 `hermes update` 会提示 Homebrew 托管，并推荐 `brew upgrade hermes-agent`。这说明 Homebrew 安装路径下，升级职责属于包管理器，而不是 Hermes 自己修改安装目录。

第五个误区是随意把 extras 全部塞进 Homebrew 基础包。`pyproject.toml` 和 README 都暗示了打包边界：基础安装要保持可构建、可审核、依赖面尽量小；例如 `voice` extra 中的 `faster-whisper` 被移出基础路径，就是为了避免 Homebrew formula 被 wheel-only 或重型传递依赖拖住。
