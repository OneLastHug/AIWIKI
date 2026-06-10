# 目录：scripts

## 它负责什么

`scripts` 是仓库根目录下的轻量级维护脚本目录，用来承载与仓库同步、依赖锁文件刷新相关的自动化操作。它不是业务代码目录，也不是 AgentGPT 的运行时入口；从当前片段看，它更像是给维护者或 CI 流程使用的辅助工具层。

这个目录目前只有两个 shell 脚本：`scripts/prepare-sync.sh` 和 `scripts/post-sync.sh`。二者命名上形成一前一后的同步流程：`prepare-sync.sh` 负责在 Git 层面准备一个同步分支环境，`post-sync.sh` 负责同步后进入 Python 后端目录重新生成 Poetry 依赖锁文件。

仓库整体是多模块结构：根目录下有 `next`、`platform`、`cli`、`db`、`docs` 等主要区域。`scripts` 不直接实现这些模块的业务能力，而是围绕这些模块做维护操作。尤其是 `post-sync.sh` 明确进入 `platform`，说明它目前与 Python 后端依赖管理关系最直接；`prepare-sync.sh` 则面向整个 Git 仓库状态。

需要注意的是，`scripts` 中的脚本带有较强的“维护自动化”属性：它们会执行 `git reset --hard`、切换分支、删除并重建 `poetry.lock` 这类具有破坏性或重写性的操作。学习时应把它理解为仓库同步流水线的一部分，而不是开发者日常启动项目的脚本集合。

## 直接子目录地图

当前 `scripts` 目录没有直接子目录。

目录结构可以概括为：

```text
scripts/
  prepare-sync.sh
  post-sync.sh
```

因此它不是一个分层复杂的大目录，不需要按子模块展开。阅读重点应放在这两个脚本在维护流程中的角色差异：

`prepare-sync.sh`：准备同步分支与本地 Git 状态。

`post-sync.sh`：同步完成后刷新 `platform` 的 Poetry 依赖锁文件。

## 关键入口

第一个关键入口是 `scripts/prepare-sync.sh`。它的主线动作是：

```text
进入 scripts 所在目录
git reset --hard
git fetch origin
git checkout main
git pull
强制删除本地 actions/sync 分支
从 origin/actions/sync 创建新的本地 actions/sync 分支
```

这个脚本的重点不在应用构建，而在仓库状态归位。它先清理当前工作区改动，再拉取远端更新，然后以远端 `actions/sync` 为基础重建本地同步分支。由于它使用了 `git reset --hard` 和 `git branch -d actions/sync --force`，运行前必须明确当前工作区没有需要保留的未提交改动。

第二个关键入口是 `scripts/post-sync.sh`。它的主线动作是：

```text
进入 scripts 所在目录
回到仓库根目录
进入 platform
删除 poetry.lock
poetry install
poetry lock
```

这个脚本聚焦于 `platform`。`platform` 是仓库中的 Python 后端或服务端模块，从其 `pyproject.toml`、`poetry.lock`、`Dockerfile`、`entrypoint.sh` 等文件可以看出它使用 Poetry 管理依赖。`post-sync.sh` 删除旧的 `poetry.lock` 后重新安装并锁定依赖，意图是让同步后的 Python 依赖锁文件与当前 `pyproject.toml` 或依赖解析结果保持一致。

## 主流程位置

根据当前片段推断，`scripts` 的主流程可能服务于“同步上游或同步分支”的自动化链路，依据是两个脚本名称分别叫 `prepare-sync.sh`、`post-sync.sh`，并且 `prepare-sync.sh` 明确操作 `actions/sync` 分支。

这一流程可以理解为三个阶段：

第一阶段，运行 `scripts/prepare-sync.sh`，把本地仓库恢复到干净状态，更新 `main`，并切到基于 `origin/actions/sync` 的本地 `actions/sync` 分支。

第二阶段，外部同步动作发生。当前目录没有包含这个同步动作本身的实现，因此只能说“根据当前片段推断”，中间步骤可能由 GitHub Actions、外部同步工具或维护者手动操作完成。依据是分支名 `actions/sync` 暗示它与自动化动作有关，但当前已读片段中没有看到具体 workflow 内容。

第三阶段，运行 `scripts/post-sync.sh`，进入 `platform`，重建 Poetry 锁文件。这个阶段的目的不是启动服务，而是把同步后的依赖状态固定下来，方便后续提交或构建。

在仓库地图中，`scripts` 位于根目录，作用范围跨越 Git 仓库和 `platform` 子项目。它不参与 `next` 前端启动，不参与 `cli` 命令行包安装，也不直接触碰 `db/setup.sql` 或 `docs` 文档目录。

## 推荐阅读顺序

建议先看仓库根目录结构，建立模块边界：`next` 是前端应用区域，`platform` 是 Python 服务端区域，`cli` 是命令行工具区域，`db` 是数据库初始化区域，`docs` 是文档区域。这样再看 `scripts` 时，不会误以为它是某个业务模块的内部脚本。

然后阅读 `scripts/prepare-sync.sh`。重点关注它的 Git 操作顺序，尤其是 `git reset --hard`、`git fetch origin`、`git checkout main`、`git pull`、`git checkout -b actions/sync origin/actions/sync`。这个脚本说明同步流程从 Git 分支准备开始。

接着阅读 `scripts/post-sync.sh`。重点关注它如何从 `scripts` 回到仓库根目录，再进入 `platform`，并通过 `poetry install`、`poetry lock` 重建依赖锁。这里可以顺手查看 `platform/pyproject.toml` 与 `platform/poetry.lock`，理解为什么同步后需要刷新 Python 依赖。

最后再结合根目录的 `setup.sh`、`docker-compose.yml`、`next/package.json`、`platform/README.md` 等文件理解项目的日常开发流程。这样可以区分“项目启动脚本”和“仓库维护脚本”：`scripts` 主要属于后者。

## 常见误区

第一个误区是把 `scripts` 当成项目启动入口。当前片段中没有看到 `scripts` 提供启动前端、启动后端或初始化数据库的通用命令；它只包含同步准备和同步后处理脚本。真正的运行入口更可能分布在 `setup.sh`、`docker-compose.yml`、`next`、`platform` 等位置。

第二个误区是低估 `prepare-sync.sh` 的破坏性。它会执行 `git reset --hard`，这会丢弃未提交的本地修改；它还会强制删除本地 `actions/sync` 分支并重新创建。学习或实验时不应在有本地重要改动的工作区直接运行它。

第三个误区是认为 `post-sync.sh` 只是普通安装依赖。它会先删除 `platform/poetry.lock`，再执行 Poetry 命令重新生成锁文件。这意味着它改变的是依赖锁定结果，不只是安装当前依赖。若 Poetry 版本、Python 版本或依赖源环境不同，生成的锁文件可能出现差异。

第四个误区是把 `actions/sync` 理解成业务分支。根据当前片段推断，它更像是自动同步流程使用的维护分支，依据是分支名包含 `actions` 与脚本名包含 `sync`。但当前片段没有完整 CI 配置证据，所以不能进一步断言它一定由某个特定 workflow 调用。

第五个误区是逐文件研究 `scripts` 时过度扩展。这个目录很小，没有子目录，也没有隐藏的复杂框架。正确阅读方式是把它放回仓库维护流程中理解：`prepare-sync.sh` 管 Git 分支准备，`post-sync.sh` 管 `platform` 依赖锁刷新。
