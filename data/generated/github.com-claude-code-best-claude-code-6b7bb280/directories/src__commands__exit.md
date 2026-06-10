# 目录：src/commands/exit

## 它负责什么

`src/commands/exit` 是 Claude Code 交互式 REPL 中 `/exit` 与 `/quit` 的本地退出命令实现目录。它不负责所有进程退出场景，也不是全局 `process.exit` 的集中封装；它只覆盖用户在 TUI/REPL 内主动触发退出时的命令入口，并把退出动作交给更底层的 UI 流程、worktree 清理流程和 `gracefulShutdown`。

从当前代码看，这个目录的职责很克制：声明一个 slash command，按当前运行环境决定“退出”到底意味着什么，然后调用已有基础设施完成后续动作。普通交互会展示随机 goodbye message 并进入优雅关闭；如果当前处于 worktree session，会进入 `ExitFlow` / `WorktreeExitDialog` 让用户选择保留或删除 worktree；如果启用了 `BG_SESSIONS` 且当前是后台 tmux session，则 `/exit` 的语义变成 detach，而不是杀掉 REPL 进程。

## 直接子目录地图

这个目录没有直接子目录，只有两个文件：

`src/commands/exit/index.ts` 是命令元数据声明层，负责告诉命令系统这里有一个名为 `exit` 的 `local-jsx` 命令。

`src/commands/exit/exit.tsx` 是命令执行层，导出 `call()`，负责根据后台会话、worktree 会话、普通 REPL 三种情况分流。

因此阅读这个目录时，不需要按子目录拆解；更应该把它看成一个很薄的命令适配器：上接命令注册与 REPL 输入，下接 `ExitFlow`、worktree 状态与 `gracefulShutdown`。

## 关键入口

最直接入口是 `src/commands/exit/index.ts` 中的默认导出 `exit`。这个对象满足 `Command` 类型，关键字段包括：

`type: 'local-jsx'` 表示这是在本地 TUI 中执行、可返回 React/Ink 节点的命令。

`name: 'exit'` 和 `aliases: ['quit']` 表示 `/exit` 是主命令，`/quit` 是别名。

`immediate: true` 表示命令应立即执行，而不是排入普通对话处理流程。

`load: () => import('./exit.js')` 表示实际实现被懒加载。这样主命令列表可以很轻，只在真正执行 `/exit` 时加载 `exit.tsx` 及其依赖。

实际执行入口是 `src/commands/exit/exit.tsx` 中的 `call(onDone)`。它的返回类型是 `Promise<React.ReactNode>`，说明它既可能直接完成关闭，也可能返回一个需要在 Ink UI 中渲染的退出流程组件。

## 主流程位置

主流程从命令注册开始。`src/commands.ts` 引入 `src/commands/exit/index.ts`，并把 `exit` 放进 `COMMANDS` 数组，因此它会出现在内置 slash command 集合中。同时，`REMOTE_SAFE_COMMANDS` 也包含 `exit`，说明远程模式下它被视为安全命令，作用范围是退出本地 TUI，而不是执行本地文件系统、shell 或 IDE 相关动作。

用户输入层还有一条快捷路径：`src/utils/handlePromptSubmit.ts` 会把裸输入 `exit`、`quit`、`:q`、`:q!`、`:wq`、`:wq!` 转换成 `/exit` 提交，而不是直接调用 `process.exit`。这保证 Vim 风格退出输入也能走同一套 slash command 逻辑，包括 worktree 提示和优雅关闭。代码中还特别跳过 remote bridge 消息，避免远端输入的 `exit` 意外杀掉本地 session。

在 REPL 层，`src/screens/REPL.tsx` 引入 `exit` 命令，并在 `handleExit` 中处理 Ctrl+C、Ctrl+D 等退出快捷键。这里有一个与 `exit.tsx` 相似的分流：后台 session 先 detach；worktree session 直接挂载 `ExitFlow`；普通路径再懒加载 `exit.load()` 并调用 `call()`。根据当前片段推断，REPL 的快捷键退出和 slash command 退出被刻意收敛到同一套语义，只是在 worktree 与后台 session 上做了更早的 UI 层保护。

`exit.tsx` 内部的核心分支如下：

第一，`feature('BG_SESSIONS') && isBgSession()` 成立时，调用 `onDone()`，再执行 `tmux detach-client`，返回 `null`。这里退出的是客户端连接，而不是后台 REPL 进程。

第二，`getCurrentWorktreeSession() !== null` 时，返回 `<ExitFlow showWorktree={...} />`。`ExitFlow` 位于 `src/components/ExitFlow.tsx`，它会在 worktree 场景下渲染 `WorktreeExitDialog`。后者负责检查 git 状态、统计相对原始提交的新 commit、让用户选择 keep/remove，并在完成后调用 `gracefulShutdown(0, 'prompt_input_exit')`。

第三，普通场景下，`call()` 会通过 `onDone(getRandomGoodbyeMessage())` 输出 `Goodbye!`、`See ya!` 等随机消息，然后调用 `gracefulShutdown(0, 'prompt_input_exit')`。真正的终端模式恢复、cleanup registry、遥测关闭、resume hint、最终 `process.exit` 都在 `src/utils/gracefulShutdown.ts` 中处理，不属于本目录直接实现。

## 推荐阅读顺序

建议先读 `src/commands/exit/index.ts`，确认它在命令系统里的形态：这是一个 `local-jsx`、`immediate`、懒加载命令。

然后读 `src/commands/exit/exit.tsx`，重点看 `call()` 的三个分支：后台 tmux detach、worktree 退出确认、普通优雅关闭。

接着读 `src/commands.ts` 中 `COMMANDS` 和 `REMOTE_SAFE_COMMANDS` 的相关位置，理解 `/exit` 如何进入全局命令集合，以及为什么它在 remote mode 仍被保留。

再读 `src/utils/handlePromptSubmit.ts` 中裸 `exit` 输入转换成 `/exit` 的逻辑，这能解释为什么用户不输入 slash command 也会触发同一流程。

最后按需读 `src/screens/REPL.tsx` 的 `handleExit`、`src/components/ExitFlow.tsx`、`src/components/WorktreeExitDialog.tsx` 和 `src/utils/gracefulShutdown.ts`。这些文件不是本目录成员，但它们承载了大部分退出体验与关闭副作用。

## 常见误区

第一个误区是把 `src/commands/exit` 当成全项目退出机制。实际上，CLI 参数错误、非交互模式、信号处理、子命令失败等大量路径会在 `src/main.tsx` 或其他工具函数中退出；本目录只代表 REPL 内的用户主动退出命令。

第二个误区是认为 `/exit` 一定会终止进程。在 `BG_SESSIONS` 后台会话中，它会执行 `tmux detach-client`，让 REPL 继续运行，方便之后通过 attach 恢复。

第三个误区是忽略 worktree 场景。普通退出可以直接 `gracefulShutdown`，但 worktree session 需要让用户决定保留还是删除工作树，并可能处理 tmux session、git dirty state、新 commit、目录切换和 session 状态记录。

第四个误区是把 goodbye message 或 UI 弹窗看成本目录的核心业务。它们只是退出命令的外层体验；真正关键的是把多种用户触发方式统一导向可靠的关闭流程，并在特殊会话类型下避免数据或会话被误删。

第五个误区是直接在新增退出入口里调用 `process.exit`。从当前实现风格看，交互式退出应优先走 `gracefulShutdown`，因为它负责恢复终端状态、运行清理函数、关闭遥测与打印 resume 提示。
