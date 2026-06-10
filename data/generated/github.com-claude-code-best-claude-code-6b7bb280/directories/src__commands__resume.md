# 目录：src/commands/resume

## 它负责什么

`src/commands/resume` 实现的是交互式 REPL 内部的 slash command：`/resume`，别名是 `/continue`。它的职责不是完整恢复会话本身，而是提供“从当前 REPL 中选择或定位一个历史会话，然后把恢复请求交给 REPL 上下文”的本地命令入口。

这个目录处理的核心问题包括：加载可恢复的历史会话列表、过滤当前会话和 sidechain 会话、支持按 session id 精确恢复、支持按自定义标题精确匹配、在无参数时展示会话选择器、处理跨项目或跨 worktree 的恢复提示，以及把选中的 `LogOption`、`sessionId` 和入口来源 `ResumeEntrypoint` 传给 `context.resume`。

需要特别区分：这里不是 CLI 启动参数 `claude --resume` 或 `claude --continue` 的主实现。命令行参数恢复主要在 `src/main.tsx` 中处理；启动时的交互式会话选择器主要由 `src/screens/ResumeConversation.tsx` 承担；真正把已选会话切换进当前 REPL 的逻辑在 `src/screens/REPL.tsx` 的 `resume` callback 中。`src/commands/resume` 更像是“REPL 内部恢复会话的前台入口”。

## 直接子目录地图

`src/commands/resume` 下面只有一个直接子目录：

`src/commands/resume/__tests__`：测试目录。目前看到的 `resume.test.ts` 主要覆盖用户可见提示文案，例如 session 未找到、多重匹配时应引导用户运行 `/resume` 打开列表。这个测试文件还包含其他命令文案相关测试，因此它不是 resume 行为的完整单元测试集合。

目录根部有两个关键文件：

`src/commands/resume/index.ts`：命令元数据注册文件，声明命令名、别名、描述、参数提示和懒加载入口。

`src/commands/resume/resume.tsx`：命令主体，包含 React/Ink UI 组件、日志加载、选择器交互、参数解析、错误展示和最终调用 `context.resume` 的逻辑。

## 关键入口

第一层入口是 `src/commands/resume/index.ts` 中的默认导出 `resume`。它声明：

`type: 'local-jsx'`，说明这是一个会在本地渲染 JSX 的 slash command。

`name: 'resume'`，主命令是 `/resume`。

`aliases: ['continue']`，因此 `/continue` 会复用同一套实现。

`argumentHint: '[conversation id or search term]'`，提示参数可以是会话 ID 或搜索词。

`load: () => import('./resume.js')`，说明真正实现被懒加载到 `resume.tsx` 中。

第二层入口是 `src/commands/resume/resume.tsx` 导出的 `call: LocalJSXCommandCall`。这是 slash command 框架实际执行的函数。它接收 `onDone`、`context` 和 `args`，内部定义 `onResume` 包装器，最后通过 `context.resume?.(sessionId, log, entrypoint)` 把恢复动作交给外层 REPL。

第三层入口是无参数时渲染的 `ResumeCommand` 组件。它会加载同仓库或 worktree 范围内的历史日志，展示 `LogSelector`，允许用户切换到 all projects，并在选择后决定是直接恢复，还是提示用户到对应目录运行恢复命令。

## 主流程位置

无参数 `/resume` 的主流程在 `ResumeCommand` 中：

1. 组件初始化时调用 `getWorktreePaths(getOriginalCwd())` 获取当前仓库相关 worktree 路径。
2. 默认通过 `loadSameRepoMessageLogs(paths)` 加载同仓库会话；如果用户切换 all projects，则使用 `loadAllProjectsMessageLogs()`。
3. `filterResumableSessions(logs, getSessionId())` 会过滤掉 sidechain 会话和当前正在运行的 session，避免恢复到自己。
4. UI 使用 `LogSelector` 展示列表，并支持 `agenticSessionSearch`。
5. 用户选择一条 `LogOption` 后，先用 `getSessionIdFromLog` 和 `validateUuid` 得到合法 session id。
6. 如果日志是 lite log，则通过 `loadFullLog(log)` 补全完整内容。
7. `checkCrossProjectResume(fullLog, showAllProjects, worktreePaths)` 判断是否跨项目。相同 repo 的 worktree 可以直接恢复；不同项目会生成命令、复制到剪贴板，并提示用户去对应目录执行。
8. 同目录或同 repo worktree 时，调用 `onResume(sessionId, fullLog, 'slash_command_picker')`。

带参数 `/resume <arg>` 的主流程在 `call` 中：

1. 先 trim 参数。
2. 如果没有参数，直接返回 `ResumeCommand`。
3. 有参数时，加载同 repo/worktree 的日志。
4. 先把参数当作 UUID 解析。若匹配日志，则恢复入口标记为 `'slash_command_session_id'`。
5. 如果 enriched logs 没找到 UUID 对应会话，会 fallback 到 `getLastSessionLog(maybeSessionId)`，用于处理某些日志因为首条 prompt 过大等原因未进入 enriched 列表的情况。
6. 如果不是 UUID，并且自定义标题功能开启，则通过 `searchSessionsByCustomTitle(arg, { exact: true })` 做精确标题匹配。唯一命中时入口标记为 `'slash_command_title'`；多重命中时显示错误提示。
7. 所有路径都找不到时，显示 `ResumeError`，提示用户运行 `/resume` 浏览列表。

真正的“恢复状态”不在这个目录内完成。`context.resume` 由 `src/screens/REPL.tsx` 提供，关键位置是 `resume` callback。它负责反序列化消息、执行当前会话的 SessionEnd hooks、执行新会话的 SessionStart hooks、切换 `sessionId`、恢复文件历史、恢复 agent 设置、恢复 standalone agent 上下文、恢复 worktree、重置 loading/input/tool JSX 状态、重建 content replacement state，并最终 `setMessages` 到恢复后的消息列表。

CLI 启动参数的恢复主流程在 `src/main.tsx`：`options.continue` 处理最近会话；`options.resume` 处理指定 session id、标题、文件、ccshare、teleport/remote 等场景；如果没有直接解析出会话，则调用 `launchResumeChooser` 进入 `src/screens/ResumeConversation.tsx` 的选择器流程。

## 推荐阅读顺序

建议先读 `src/commands/resume/index.ts`，确认它只是 slash command 注册层，避免一开始误以为这里覆盖了所有恢复能力。

然后读 `src/commands/resume/resume.tsx` 的导出 `call`，从参数分支理解 `/resume` 的三种用户路径：无参数打开选择器、UUID 精确恢复、标题精确恢复。

接着读同文件中的 `ResumeCommand`，重点看 `loadLogs`、`handleToggleAllProjects`、`handleSelect`，这里体现了日志加载、跨项目判断和 `LogSelector` 的连接方式。

再读 `filterResumableSessions`，这个函数虽小，但解释了为什么当前会话和 sidechain 不出现在 `/resume` 列表里。

之后跳到 `src/screens/REPL.tsx` 的 `resume` callback，理解 `context.resume` 背后的状态迁移，这才是真正恢复当前 REPL 的核心。

最后读 `src/main.tsx` 的 `options.continue` 和 `options.resume` 分支，以及 `src/screens/ResumeConversation.tsx`。这样可以把“REPL 内部 `/resume`”和“进程启动时 `--resume`/`--continue`”两条恢复链区分清楚。

## 常见误区

第一个误区是把 `/resume` 和 `--resume` 当成同一个入口。`src/commands/resume` 只服务于已经进入 REPL 后的 slash command；命令行参数恢复在 `src/main.tsx`，无直接命中时才会进入 `ResumeConversation` 选择器。

第二个误区是认为 `resume.tsx` 会直接修改全局 session 状态。实际它只做选择、校验、提示和派发，真正的 session 切换、消息恢复、worktree 恢复、metadata 恢复由 `REPL.tsx` 的 `context.resume` 执行。

第三个误区是忽略 lite log。列表中可能是轻量日志，选中后需要 `loadFullLog` 才能恢复完整消息，否则后续流程拿不到足够信息。

第四个误区是以为 all projects 下可以直接恢复任意项目会话。代码会通过 `checkCrossProjectResume` 区分同 repo worktree 和完全不同项目。不同项目不会在当前目录硬切恢复，而是提示一条可执行命令并复制到剪贴板。

第五个误区是把 `aliases: ['continue']` 理解成等价于 CLI 的 `--continue`。在 slash command 层，`/continue` 只是 `/resume` 的别名；CLI 的 `--continue` 是“继续最近会话”的启动路径，处理逻辑在 `src/main.tsx`。
