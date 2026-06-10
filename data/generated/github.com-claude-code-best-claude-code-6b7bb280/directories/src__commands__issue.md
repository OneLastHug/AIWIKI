# 目录：src/commands/issue

## 它负责什么

`src/commands/issue` 实现 Claude Code 内置斜杠命令 `/issue`。它的职责不是管理本地 issue 数据，也不是提供完整 GitHub 客户端，而是把当前 Claude Code 会话上下文整理成 GitHub Issue，并尽量通过本机 `gh` CLI 直接创建。

从代码结构看，这个目录目前是一个很小的命令模块：核心实现集中在 `src/commands/issue/index.ts`，对外通过默认导出一个 `Command` 对象接入全局命令系统。用户在交互式或非交互式场景中输入 `/issue` 后，会进入这个本地命令的 `call` 逻辑。

它覆盖的主要能力包括：解析 `/issue` 参数、识别当前 Git 仓库的 GitHub remote、检测 `gh` CLI 是否可用、判断仓库是否启用了 Issues、读取本地 `.github/ISSUE_TEMPLATE` 中的 Markdown issue 模板、提取最近会话日志摘要、调用 `gh issue create` 创建 issue，以及在无法直接创建时返回浏览器预填链接或本地草稿路径。

需要注意的是，这个命令会读写本地辅助文件：它会读取 Claude Code session 的 `.jsonl` 日志来生成 issue 上下文；当浏览器 URL body 过长时，会尝试把完整草稿写到用户 home 下的 `.claude/issue-drafts`。这属于命令运行时行为，不代表该目录本身保存 issue 数据。

## 直接子目录地图

`src/commands/issue` 当前没有直接子目录。

目录下只有两个文件：

`src/commands/issue/index.ts`：命令主实现，包含参数解析、GitHub 仓库识别、模板读取、会话摘要生成、`gh` 调用和降级输出。

`src/commands/issue/index.d.ts`：类型声明文件，声明默认导出为 `Command`。根据当前片段推断，它可能来自构建、反编译或类型补全产物，用于让外部模块识别该命令的导出类型；实际业务逻辑不在这里。

## 关键入口

最关键入口是 `src/commands/issue/index.ts` 中的默认导出对象 `issue: Command`。这个对象声明了命令元信息：

`type: 'local'` 表示它是本地命令，不是提示词型命令或远程工具命令。

`name: 'issue'` 决定用户通过 `/issue` 触发它。

`description` 说明它通过 `gh` CLI 创建 GitHub issue，并支持 `--label`、`--assignee` 参数。

`supportsNonInteractive: true` 表示它可以在非交互式上下文中运行。

`bridgeSafe: true` 表示它被标记为可在 bridge/remote 相关场景中安全使用。

真正的执行入口在 `load: async () => ({ call: async (args) => ... })`。全局命令系统会加载这个命令，然后在用户触发 `/issue ...` 时把斜杠命令后面的文本作为 `args` 传入 `call`。

它被接入全局命令列表的位置在 `src/commands.ts`：该文件导入 `./commands/issue/index.js`，然后把 `issue` 放进命令集合。再往上，`src/main.tsx`、`src/QueryEngine.ts`、`src/setup.ts` 等模块会通过 `getCommands` 或命令类型使用这些斜杠命令。因此，`src/commands/issue` 本身只实现一个命令单元，注册和分发由外层 `src/commands.ts` 与 REPL/QueryEngine 体系负责。

## 主流程位置

主流程全部在 `src/commands/issue/index.ts` 的 `call` 函数中。

第一步是 `parseIssueArgs(args)`。它支持形如 `/issue Fix login bug`、`/issue --label bug --assignee alice Fix login bug` 的参数。`--label` 可简写为 `-l`，`--assignee` 可简写为 `-a`。未知 flag、缺少 flag 值都会返回文本错误和用法提示。标题由剩余普通词拼接得到，因此这里的解析较简单，不支持复杂 shell quote 语义；这是阅读时容易忽略的点。

第二步是环境探测。`tryDetectGitRemoteUrl()` 通过 `git remote get-url origin` 获取 remote，`parseOwnerRepo(remote)` 只识别 GitHub 的 SSH 和 HTTP(S) remote 格式，并解析出 `owner`、`repo`。`ghCliAvailable()` 通过 `gh --version` 判断本机是否安装 GitHub CLI。`getOriginalCwd()` 用于定位当前项目目录。

第三步是无标题分支。如果用户只输入 `/issue`，命令不会创建任何东西，而是返回用法、示例、当前仓库提示和 `gh` 可用性提示。这里的 “New issue URL” 是给用户的方向性提示。

第四步是降级分支。如果没有 `gh` CLI 或没有可解析的 GitHub remote，命令会走 fallback：调用 `getTranscriptSummary()` 读取当前 session 日志，生成 “Context from Claude Code session” 文本；如果 body 太长，会截断 URL 中的 body，并尝试把完整内容保存到 `.claude/issue-drafts`。如果能识别仓库，会返回预填 issue 的浏览器链接；如果不能识别仓库，则提示当前目录没有 GitHub remote。文档中不要把源码里的真实外部地址展开，可理解为“GitHub issue 新建页”。

第五步是仓库能力检查。若 `gh` 和 GitHub remote 都可用，`repoHasIssuesEnabled(owner, repo)` 会通过 `gh api repos/{owner}/{repo} --jq .has_issues` 判断 Issues 是否开启。返回 `false` 时不会继续创建 issue，而是提示仓库禁用了 Issues，并给出 Discussions 的替代方向。返回 `null` 代表无法判断，流程会继续尝试创建 issue。

第六步是构造 issue body。`detectIssueTemplate(cwd)` 会读取 `.github/ISSUE_TEMPLATE` 下第一个 Markdown 模板，并剥离 YAML front matter。`getTranscriptSummary(5)` 会读取最近会话日志，提取最近用户/助手消息片段，并附带最近工具错误片段。最终 body 由“Claude Code 会话上下文”、可选 issue 模板、以及“Created via `/issue` command in Claude Code”标记组成。

第七步是执行创建。代码组装 `gh issue create --title ... --body ...`，追加多个 `--label` 和 `--assignee`，并用 `--repo owner/repo` 明确目标仓库。成功时返回 issue 标题、URL、标签和 assignee；失败时返回错误，并提示用户确认 `gh auth login`。

另外，主流程中穿插了 `logEvent` 埋点，例如 `tengu_issue_started`、`tengu_issue_fallback`、`tengu_issue_created`、`tengu_issue_failed`。这些埋点只记录元信息，例如是否有 `gh`、是否有 remote、是否有 labels、失败错误摘要等，不是业务主路径。

## 推荐阅读顺序

1. 先看 `src/commands.ts` 中对 `issue` 的 import 和命令集合位置，理解 `/issue` 作为普通 slash command 被纳入全局命令系统。

2. 再看 `src/commands/issue/index.ts` 底部的 `const issue: Command`，优先理解命令元信息、`load`、`call` 三层结构。

3. 接着看 `parseIssueArgs`，确认用户输入如何变成 `title`、`labels`、`assignees`。这能帮助理解后续分支为什么先检查 `opts.valid` 和 `title`。

4. 然后看 GitHub 环境相关函数：`tryDetectGitRemoteUrl`、`parseOwnerRepo`、`ghCliAvailable`、`repoHasIssuesEnabled`。这些函数决定命令能否直接创建 issue。

5. 最后看内容构造函数：`detectIssueTemplate` 和 `getTranscriptSummary`。它们解释了 issue body 的来源：一部分来自项目 issue 模板，一部分来自 Claude Code 当前会话日志。

## 常见误区

第一个误区是把 `/issue` 理解成纯提示词命令。它实际是 `type: 'local'` 的命令，会执行本地进程，包括 `git`、`gh`，也会读取 session 日志，并在特定情况下写入本地草稿文件。

第二个误区是以为它一定会联网创建 issue。事实上，只有同时满足可解析 GitHub remote、安装 `gh` CLI、仓库 Issues 可用、`gh issue create` 执行成功等条件时，才会真正创建。否则它更像一个 issue 草稿/链接生成器。

第三个误区是认为它支持所有 Git remote。`parseOwnerRepo` 只识别 GitHub SSH 和 HTTP(S) remote 格式。GitLab、Gitea、企业自定义域名、非 origin remote 都不会被当前逻辑识别。根据当前片段推断，这个命令是专门服务 GitHub 仓库的轻量集成，而不是通用 issue tracker 抽象。

第四个误区是忽略会话日志依赖。`getTranscriptSummary` 依赖 `getSessionId`、`getSessionProjectDir`、`getOriginalCwd` 和 Claude 配置目录推导 `.jsonl` 路径。如果日志不存在、格式异常或读取失败，issue body 会退化为占位文本，而不是抛出致命错误。

第五个误区是把 issue 模板处理看得过重。`detectIssueTemplate` 只优先使用第一个 Markdown 模板，并剥离 front matter；虽然它会扫描 `.md`、`.yml`、`.yaml`，但当前实现并不会解析 YAML issue forms。也就是说，GitHub issue forms 在这里不会被结构化填充。

第六个误区是忽略 URL 长度保护。在 fallback 模式下，body 会被限制到固定长度，超长时才写草稿。这说明 fallback 输出适合“辅助打开新 issue 页面”，而不是保证完整内容都能进入浏览器 URL。
