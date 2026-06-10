# 文件：packaging/homebrew/README.md

## 一句话定位

`packaging/homebrew/README.md` 是 Hermes Agent 的 Homebrew 打包维护说明页，面向维护 formula 的发布者或贡献者，说明 `packaging/homebrew/hermes-agent.rb` 应该如何随版本更新、如何处理 Python 资源依赖、以及 Homebrew 安装形态需要保留哪些运行时约束。

## 它暴露/定义了什么

这个文件不暴露程序接口，也不定义可执行逻辑；它定义的是一组打包约定。核心内容有四类：

第一，指定 `packaging/homebrew/hermes-agent.rb` 可作为 tap 或 `homebrew-core` formula 的起点。也就是说，README 把旁边的 Ruby formula 文件视为 canonical packaging template，而不是临时示例。

第二，强调稳定版本应指向 GitHub release 中 semver 命名的 sdist 资产，而不是 CalVer tag tarball。这个约定和 `scripts/release.py` 中“为下游打包方构建 semver-named Python artifacts”的注释互相印证，目的是让 Homebrew 这种下游包管理器依赖语义化 Python 包版本，而不是仓库 tag 的日历版本命名。

第三，说明 `faster-whisper` 被放进 `voice` extra，避免 base Homebrew formula 拉入 wheel-only 的传递依赖。邻近的 `pyproject.toml` 注释也说明 `voice` 包含 `ctranslate2`、`onnxruntime` 等对源码构建型打包器不友好的依赖，因此默认 formula 不应包含它。

第四，要求 wrapper 导出 `HERMES_BUNDLED_SKILLS`、`HERMES_OPTIONAL_SKILLS` 和 `HERMES_MANAGED=homebrew`。这些变量让 Homebrew 安装包能够找到随包安装的 `skills`、`optional-skills` 运行时资源，并让 Hermes 自身知道升级应交给 Homebrew，而不是走内置 self-update 路径。

## 谁调用它

没有代码“调用”这个 README。它的直接消费者是维护 Homebrew formula 的人，包括项目维护者、tap 维护者、或准备提交 `homebrew-core` 的贡献者。

根据当前片段推断，发布流程间接依赖这里的规则：`scripts/release.py` 会构建 semver 命名的 release artifact，而 formula 更新者再根据 README 的流程把 `packaging/homebrew/hermes-agent.rb` 中的 `url`、`version`、`sha256` 更新到对应资产。依据是 `scripts/release.py` 对 Homebrew 的注释，以及 README 明确写出的 “Typical update flow”。

## 它调用谁

README 自身不调用任何函数或模块，但它要求维护者使用几个外部命令和邻近文件：

`packaging/homebrew/hermes-agent.rb` 是主要被维护对象，里面定义 `HermesAgent < Formula`，使用 `Language::Python::Virtualenv` 安装 Python 包和资源文件。

`brew update-python-resources --print-only hermes-agent` 用于刷新 Homebrew formula 的 Python resource stanzas。README 特别要求保留 `ignore_packages: %w[certifi cryptography pydantic]`，对应 formula 中的 `pypi_packages ignore_packages` 配置。

`brew audit --new --strict hermes-agent` 和 `brew test hermes-agent` 是验证入口。前者检查 formula 是否符合 Homebrew 新包规范，后者运行 formula 中的 `test do` 块，确认 `hermes version` 和 `hermes update` 的行为符合 Homebrew 管理预期。

## 核心流程

典型更新流程从发布产物开始。维护者先选择 GitHub release 中 semver 命名的 sdist 文件，更新 `packaging/homebrew/hermes-agent.rb` 的 `url`、`version` 和 `sha256`。这里的风险点是不要误用 CalVer tag tarball，因为 tag 名和 Python 包版本并不是同一个稳定接口。

随后刷新 Python 依赖资源。Homebrew 的 Python virtualenv formula 通常需要显式列出 PyPI 资源，README 指定使用 `brew update-python-resources --print-only hermes-agent` 生成候选内容，再人工合入 formula。刷新时必须保留 `ignore_packages: %w[certifi cryptography pydantic]`，避免把这些由 Homebrew 或基础环境处理的包错误地 vendoring 进资源列表。

安装阶段由 `hermes-agent.rb` 的 `install` 方法完成：创建 Python 3.14 virtualenv，安装 resources，再安装当前 buildpath；然后把 `skills` 和 `optional-skills` 安装到 `pkgshare`；最后为 `hermes`、`hermes-agent`、`hermes-acp` 这些可执行文件生成带环境变量的 wrapper。这样 CLI 运行时可以从 Homebrew 的共享目录读取技能资源，并知道自己处于 Homebrew 管理模式。

验证阶段执行 Homebrew audit 和 test。formula 的测试会检查 `hermes version` 输出版本，并运行 `hermes update`，断言它提示 “managed by Homebrew” 和 `brew upgrade hermes-agent`，防止包管理器安装的应用绕过 Homebrew 自行升级。

## 关键函数的高层作用

`packaging/homebrew/README.md` 没有函数。与它最相关的关键逻辑在 `packaging/homebrew/hermes-agent.rb`：

`install` 是 Homebrew 安装流程入口，负责创建隔离 Python 环境、安装 Python resources 和项目本体、复制运行时技能目录、并生成带 `HERMES_BUNDLED_SKILLS`、`HERMES_OPTIONAL_SKILLS`、`HERMES_MANAGED` 的命令 wrapper。它决定了 Homebrew 包安装后能否正常找到 Hermes 的内置技能和可选技能。

`test` 是 Homebrew 包验收入口，负责验证安装后的 CLI 可执行、版本输出正确，并且升级命令不会走 Hermes 自身更新器，而是提示用户使用 Homebrew 升级。它覆盖的是打包行为，不是完整业务功能测试。

`pypi_packages ignore_packages` 不是函数定义，但在 formula 中承担依赖资源生成策略的作用。它配合 README 的更新流程，约束资源刷新时哪些包不应被纳入 formula resources。

## 修改风险

最大风险是破坏 Homebrew 管理边界。如果移除或改错 `HERMES_MANAGED=homebrew`，`hermes update` 可能不再提示用户使用 `brew upgrade hermes-agent`，导致包管理器安装的文件被应用自更新逻辑绕过，产生不可追踪的安装状态。

第二个风险是运行时资源丢失。`skills` 和 `optional-skills` 不是普通 Python 模块，formula 需要通过 `pkgshare.install` 和 wrapper 环境变量显式暴露它们。若 README 或 formula 更新时忽略这点，Homebrew 安装后的 Hermes 可能启动正常，但技能加载、可选技能安装或相关命令在运行时失败。

第三个风险是依赖膨胀或构建失败。把 `voice` extra 或 `faster-whisper` 相关依赖带入 base formula，可能让 Homebrew 遇到 wheel-only 或平台构建问题；移除 `ignore_packages` 也可能让 Homebrew 资源列表和系统/公式提供的基础包冲突。

第四个风险是版本源选错。使用 CalVer tag tarball 替代 semver sdist 会让 Homebrew formula 的 `version`、源码包元数据和发布资产命名出现不一致，后续自动化资源刷新、audit 或用户侧版本显示都可能出现偏差。

第五个风险是 README 与 formula 脱节。这个 README 是维护约定，不会被测试直接执行；如果修改 `hermes-agent.rb` 的安装逻辑，却不同步更新 README，后续维护者会按旧流程刷新资源或验证包，错误可能只在发布时暴露。
