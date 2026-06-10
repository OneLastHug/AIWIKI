# 目录：src/commands/install-github-app

## 它负责什么
这个目录实现的是 Claude Code 里“为仓库安装 GitHub App / 配置 GitHub Actions”的整套命令流程。根据当前片段推断，它不是一个单纯的 UI 目录，而是一个把命令注册、交互式步骤、GitHub CLI 校验、仓库权限检查、工作流文件创建、secret 写入、OAuth/API key 选择都串起来的功能包。

它的目标很明确：让用户把 Claude 相关的 GitHub Actions 模板快速装到指定仓库里，并在必要时处理权限不足、已有 workflow、已有 secret、GitHub CLI 未登录等现实问题。

## 直接子目录地图
这个目录下面**没有子目录**，只有一组并列文件。可以按职责理解成 4 层：

- 命令入口层：`index.ts`
- 主状态机和交互编排层：`install-github-app.tsx`
- 具体执行层：`setupGitHubActions.ts`
- 类型与步骤展示层：`types.ts`、`ApiKeyStep.tsx`、`CheckGitHubStep.tsx`、`ChooseRepoStep.tsx`、`WarningsStep.tsx`、`InstallAppStep.tsx`、`OAuthFlowStep.tsx`、`CheckExistingSecretStep.tsx`、`ExistingWorkflowStep.tsx`、`CreatingStep.tsx`、`SuccessStep.tsx`、`ErrorStep.tsx`、`CreatingStep.tsx`

如果只看结构，这里是“一个命令 + 一台状态机 + 一组步骤视图 + 一个 GitHub 写入器”的组合，而不是按业务拆成多个独立模块。

## 关键入口
最外层入口是 `index.ts`。它导出一个 `Command` 描述对象，命名为 `install-github-app`，并通过 `load: () => import('./install-github-app.js')` 做懒加载。这里还带了环境开关 `DISABLE_INSTALL_GITHUB_APP_COMMAND`，说明这个命令是可被整体禁用的。

真正的执行入口在 `install-github-app.tsx` 里的 `InstallGitHubApp` 组件。它不是普通展示组件，而是命令运行时的状态机宿主：初始化状态、触发 `gh` 检查、根据步骤切换不同页面、最终调用 `setupGitHubActions()`。

## 主流程位置
主流程核心集中在两个文件：

1. `install-github-app.tsx`
   - `INITIAL_STATE` 定义了整个交互状态。
   - `checkGitHubCLI()` 负责检查 `gh --version`、`gh auth status -a`、权限 scope、当前仓库等。
   - `handleSubmit()` 是主分支分发器，按 `state.step` 进入不同阶段。
   - `runSetupGitHubActions()` 是从交互态切到执行态的桥梁。

2. `setupGitHubActions.ts`
   - 这里是实际写 GitHub 内容的地方。
   - 先检查仓库是否存在、默认分支是什么、默认分支 SHA 是什么。
   - 然后决定是否创建临时分支、写 workflow 文件、设置 secret、最后打开 compare/PR 页面。
   - 这部分还负责把 `claude.yml`、`claude-code-review.yml` 之类的 workflow 内容拼装好。

从流程上看，`install-github-app.tsx` 负责“做什么、下一步去哪”，`setupGitHubActions.ts` 负责“怎么真正改仓库”。

## 推荐阅读顺序
1. 先看 `index.ts`，确认这个命令是怎么被挂到 CLI 系统里的。
2. 再看 `types.ts`，先认识 `State`、`Warning`、`Workflow`，后面读状态机不会丢。
3. 然后读 `install-github-app.tsx`，重点盯 `INITIAL_STATE`、`checkGitHubCLI()`、`handleSubmit()`、`runSetupGitHubActions()`。
4. 再看 `setupGitHubActions.ts`，理解真正的 GitHub API / `gh` 调用顺序。
5. 最后扫一遍各个 `*Step.tsx`，把每个步骤对应的界面和状态名对上。

## 常见误区
- 容易把 `index.ts` 当成主逻辑，但它只是命令描述和懒加载入口，真正流程在 `install-github-app.tsx`。
- 容易把一堆 `*Step.tsx` 当成独立业务模块；实际上它们主要是状态机的展示分支，不是主流程本体。
- 容易忽略 `setupGitHubActions.ts` 的重要性。它不是辅助函数，而是仓库修改的执行核心。
- 容易误判“安装 GitHub App”只做授权；实际上这里还会检查 repo 权限、创建 workflow 文件、设置 secret、打开 compare 页面。
- `State` 里有 `[key: string]: unknown`，说明它允许动态字段；根据当前片段推断，这通常是为了适配运行时状态扩展，但也意味着读代码时不能只盯静态字段名。
- 这个命令并不总是可用：`DISABLE_INSTALL_GITHUB_APP_COMMAND` 会直接关掉它，availability 也限定在 `claude-ai`、`console` 场景。
