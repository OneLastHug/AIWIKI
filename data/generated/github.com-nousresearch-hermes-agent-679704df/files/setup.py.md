# 文件：setup.py

## 一句话定位

`setup.py` 是这个仓库的补充打包入口：核心项目元数据、依赖、入口命令主要在 `pyproject.toml` 中声明，而 `setup.py` 只负责把仓库里的 `skills/` 与 `optional-skills/` 文件树递归登记为安装时的数据文件。

## 它暴露/定义了什么

这个文件没有暴露业务 API，也没有定义运行时类。它主要定义了两个全局对象/函数：

`REPO_ROOT`：通过 `Path(__file__).parent.resolve()` 定位仓库根目录，作为后续遍历 `skills/`、`optional-skills/` 的基准。

`_data_file_tree(root_name: str)`：接收一个目录名，递归扫描该目录下所有普通文件，并按相对父目录分组，返回 `setuptools.setup(data_files=...)` 需要的结构：`list[tuple[str, list[str]]]`。

文件末尾直接调用 `setup(...)`，把 `_data_file_tree("skills")` 和 `_data_file_tree("optional-skills")` 的结果展开到 `data_files` 中。

## 谁调用它

主要调用者不是 Hermes 运行时代码，而是 Python 打包工具链。根据 `pyproject.toml`，构建后端是 `setuptools.build_meta`，因此 `pip`、`uv`、`python -m build` 或下游发行版打包流程在构建 wheel、sdist 或安装项目时，会由 setuptools 读取并执行 `setup.py`。

仓库运行时入口命令来自 `pyproject.toml` 的 `[project.scripts]`：`hermes` 指向 `hermes_cli.main:main`，`hermes-agent` 指向 `run_agent:main`，`hermes-acp` 指向 `acp_adapter.entry:main`。这些入口不会直接调用 `setup.py`。根据当前片段推断，`setup.py` 是纯打包期文件，不参与 CLI、gateway、agent loop 的正常运行。

## 它调用谁

`setup.py` 只依赖标准库和 setuptools：

`pathlib.Path` 用于解析仓库根路径、递归遍历目录、计算相对路径。

`collections.defaultdict` 用于把扫描到的文件按目标安装目录分组。

`setuptools.setup` 是最终打包声明入口。

它不会调用仓库内的 `run_agent.py`、`model_tools.py`、`tools/skills_sync.py` 等运行时代码，也不会解析 skill 内容，只把文件路径交给打包系统。

## 核心流程

构建开始后，setuptools 执行 `setup.py`。文件先计算 `REPO_ROOT`，然后在 `setup(data_files=...)` 里分别扫描 `skills/` 与 `optional-skills/`。

每次扫描时，`_data_file_tree` 会把 `REPO_ROOT / root_name` 作为根目录，使用 `root.rglob("*")` 递归列出所有路径。非文件路径会被跳过，普通文件会转换成相对于仓库根目录的路径，例如 `skills/github/DESCRIPTION.md`。随后函数以相对父目录为 key 聚合文件列表，例如同一个 skill 目录下的 `SKILL.md`、`scripts/`、`references/` 文件会进入对应父目录分组。最后返回排序后的 `(目录, 文件列表)`，保证生成结果相对稳定。

`setup(...)` 收到的 `data_files` 最终影响安装产物中这些非 Python 文件是否被带上。它与 `MANIFEST.in` 中的 `graft skills`、`graft optional-skills` 形成互补：`MANIFEST.in` 保障源码包包含这些目录，`setup.py` 则把它们登记为安装数据文件。`tests/test_packaging_metadata.py` 也专门检查 `MANIFEST.in` 是否包含 bundled skills，说明技能文件随包发布是一个被测试保护的打包约束。

## 关键函数的高层作用

`_data_file_tree(root_name: str)` 是唯一值得关注的函数。它的职责不是理解 skill 语义，而是把一个目录树转换成 setuptools `data_files` 可消费的列表。高层看，它做了三件事：递归找文件、按相对目录分组、排序后返回。这个函数的设计让新增、删除、移动 `skills/` 或 `optional-skills/` 下的文件时，不需要同步维护一份手写清单。

`setup(...)` 只是声明式调用，没有复杂逻辑。它把两个目录树的扫描结果合并到 `data_files`。如果未来还要让新的顶层资源目录随安装分发，理论上可以在这里追加 `_data_file_tree("目录名")`，但应先确认该目录是否真的应该作为安装级数据文件发布。

## 修改风险

最大风险是破坏打包产物中的 skill 分发。Hermes 的技能系统依赖 bundled skills 和 optional skills 能从安装包中恢复或同步到用户环境；如果删除 `setup.py`、移除某个 `_data_file_tree(...)`、改变相对路径计算方式，可能导致安装后的环境缺少 `SKILL.md`、脚本、模板或引用文件，从而让 `hermes skills install`、技能同步、技能浏览等功能出现运行时缺文件问题。

第二类风险是安装路径语义。`setuptools.data_files` 与 `package-data` 不同，它面向安装数据目录而不是 Python 包内部资源。随意把路径改成绝对路径、只保留文件名、或改变分组 key，可能导致不同平台、不同构建后端、不同安装模式下文件落点变化，尤其会影响 Homebrew、Nix、容器镜像等下游打包场景。

第三类风险是体积与安全面。这里会递归收集目标目录下所有普通文件。如果 `skills/` 或 `optional-skills/` 中误放大文件、临时文件、凭据、缓存、测试产物，它们可能被打进发布包。当前 `MANIFEST.in` 只全局排除了 `__pycache__` 和 `*.py[cod]`，不覆盖所有敏感或临时文件类型。因此修改扫描范围或向这些目录加入新内容时，需要从发布包视角审查。

最后，排序行为虽然看起来是细节，但能减少构建结果抖动。去掉 `sorted(...)` 可能让文件枚举顺序受文件系统影响，增加 wheel 差异、缓存失效和下游复现难度。
