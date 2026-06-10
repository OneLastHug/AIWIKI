# 目录：src/commands/job

## 它负责什么

`src/commands/job` 是 Claude Code 内部 “template job” 功能在交互式 REPL 里的斜杠命令入口，核心职责是提供 `/job` 命令，让用户在会话中执行模板任务相关操作。它本身不负责模板发现、任务状态持久化、任务目录创建等底层逻辑，而是一个很薄的命令适配层：把 REPL 中输入的 `/job list`、`/job new ...`、`/job reply ...`、`/job status ...` 转交给已有的 CLI handler。

从代码结构看，这个目录的定位是“命令注册 + REPL 调用桥接”。真正的业务逻辑分散在邻近模块中：`src/cli/handlers/templateJobs.ts` 负责 CLI 子命令分发，`src/jobs/templates.ts` 负责发现和加载模板，`src/jobs/state.ts` 负责 job 状态与目录读写。`src/commands/job` 只是把这些能力暴露成一个可被主 REPL 命令系统加载的 local-jsx command。

该命令受 `TEMPLATES` feature flag 控制。`src/commands/job/index.ts` 中通过 `feature('TEMPLATES')` 决定 `/job` 是否启用；`src/entrypoints/cli.tsx` 中也用同一个 flag 控制 `claude job <subcommand>` 的 fast-path。因此，理解这个目录时要把它看作 feature-gated 的模板任务入口，而不是始终可用的基础命令。

## 直接子目录地图

`src/commands/job` 下面只有一个直接子目录：

`src/commands/job/__tests__`：测试目录，覆盖 `/job` 命令的基本导出形态和模块加载行为。它用于确认命令名、描述、以及 `job.tsx` 是否导出 `call` 函数。这个测试目录不是业务流程的一部分，只是保证命令注册层没有断裂。

目录根部的两个关键文件是：

`src/commands/job/index.ts`：命令声明文件，默认导出 `job` command 配置。它定义命令类型为 `local-jsx`，命令名为 `job`，描述为 `Manage template jobs`，参数提示为 `[list|new|reply|status]`，并通过 `load: () => import('./job.js')` 延迟加载真正实现。

`src/commands/job/job.tsx`：命令执行实现。它导出 `call(onDone, context, args)`，负责解析 REPL 传入的字符串参数，动态导入 `src/cli/handlers/templateJobs.ts` 中的 `templatesMain`，调用后把输出交给 `onDone` 显示。

## 关键入口

第一个入口是 REPL 斜杠命令入口：`src/commands/job/index.ts`。主命令系统扫描或导入 commands 时，会拿到这里的 command metadata。这个入口只描述命令，不执行业务逻辑。它的 `isEnabled()` 逻辑是关键：只有 `feature('TEMPLATES')` 为真时，`/job` 才会出现在可用命令集合中。

第二个入口是实际执行入口：`src/commands/job/job.tsx` 的 `call()`。用户在 REPL 中输入 `/job` 后，最终会进入这个函数。它将参数用空白字符拆分，默认子命令设为 `list`，然后调用 `templatesMain([sub, ...parts.slice(1)])`。这里有一个重要细节：REPL 里的 `/job` 不带参数时会被当作 `/job list`。

第三个相关入口在 `src/entrypoints/cli.tsx`。这不是 `src/commands/job` 目录内部代码，但它是命令行模式下的同一功能入口。当用户执行 `claude job <subcommand>` 时，CLI fast-path 会在 `feature('TEMPLATES')` 打开时动态导入 `src/cli/handlers/templateJobs.ts`，并调用 `templatesMain(args.slice(1))`。另外，代码中还保留了 `new`、`list`、`reply` 到 `job <subcommand>` 的 backward-compat 映射，根据当前片段可知这是旧命令兼容路径。

## 主流程位置

主流程可以分为两条：REPL 斜杠命令流程和 CLI fast-path 流程。

REPL 流程从 `src/commands/job/index.ts` 开始。命令系统看到 `job` 是一个 `local-jsx` command，启用后按需加载 `src/commands/job/job.tsx`。`call()` 收到原始参数字符串后，用 `args.trim().split(/\s+/)` 拆成数组，取第一个 token 作为子命令；如果没有 token，则默认使用 `list`。随后它临时替换 `console.log` 和 `console.error`，把 handler 的输出收集到 `lines` 数组中。调用结束后恢复原来的 console 方法，并通过 `onDone(lines.join('\n') || 'Done.', { display: 'system' })` 把文本输出回 REPL。

CLI 流程从 `src/entrypoints/cli.tsx` 的 fast-path 开始。代码检查 `args[0] === 'job'` 且 `feature('TEMPLATES')` 成立，然后导入 `src/cli/handlers/templateJobs.ts` 的 `templatesMain()`。这个 handler 根据第一个参数分发到 `list`、`new`、`reply`、`status` 四类操作。`list` 会调用 `src/jobs/templates.ts` 的 `listTemplates()`；`new` 会调用 `loadTemplate()`，生成短 job id，并通过 `src/jobs/state.ts` 的 `createJob()` 创建任务；`reply` 会通过 `readJobState()` 确认任务存在，再用 `appendJobReply()` 追加回复；`status` 会读取 job state 并打印模板名、状态、创建时间、更新时间和参数。

模板发现流程位于 `src/jobs/templates.ts`。它会查找项目层级中的 `.claude/templates`，再补充用户级配置目录下的 `templates`。每个 `.md` 文件被视为一个模板，文件名去掉 `.md` 后作为模板名；frontmatter 中的 `description` 优先作为描述，否则从 Markdown 内容中提取描述。根据当前片段推断，`src/commands/job` 目录不会直接接触文件系统模板细节，而是完全复用 `src/jobs/templates.ts` 和 `src/jobs/state.ts`。

## 推荐阅读顺序

建议先读 `src/commands/job/index.ts`。这个文件最短，能快速明确 `/job` 是如何注册到命令系统里的，以及它为什么会受到 `TEMPLATES` feature flag 控制。

然后读 `src/commands/job/job.tsx`。重点看 `call()` 如何把 REPL 输入转换成 `templatesMain()` 参数，以及为什么要捕获 `console.log` / `console.error`。这能解释一个设计选择：底层 handler 本来是为 CLI 打印设计的，REPL 命令层通过捕获 console 输出复用它，而不是重写一套展示逻辑。

第三步读 `src/cli/handlers/templateJobs.ts`。这里是 `list`、`new`、`reply`、`status` 的实际分发点，也是理解 “job 命令到底能做什么” 的核心位置。读到这里即可形成 overview 级别的主流程认识。

最后按需读 `src/jobs/templates.ts` 和 `src/jobs/state.ts`。前者解释模板从哪里来，后者解释 job 状态存到哪里、如何创建和追加回复。如果只是理解 `src/commands/job` 的目录角色，读到 handler 已经足够；如果要修改模板任务行为，才需要深入这两个底层模块。

测试可以最后看 `src/commands/job/__tests__/job.test.ts`。它更多是命令导出层的烟雾测试，不是完整业务规格。

## 常见误区

第一个误区是把 `src/commands/job` 当成 template job 的业务核心。实际上它只是 REPL 命令适配层。业务核心在 `src/cli/handlers/templateJobs.ts`、`src/jobs/templates.ts`、`src/jobs/state.ts`，尤其是模板发现和状态持久化都不在这个目录里。

第二个误区是忽略 REPL `/job` 和 CLI `claude job` 的差异。REPL 中 `/job` 不带参数会默认执行 `list`；但从 `src/cli/handlers/templateJobs.ts` 当前实现看，`templatesMain([])` 会进入 default 分支，打印 unknown command 和 usage，并设置 `process.exitCode = 1`。也就是说，两条入口复用同一个 handler，但入口层对空参数的处理并不完全相同。

第三个误区是随意改写 `feature('TEMPLATES')`。本仓库对 `bun:bundle` 的 `feature()` 有编译约束，通常要求直接出现在 `if` 或三元条件位置。`src/commands/job/index.ts` 当前写法是 `if (feature('TEMPLATES')) return true`，不要为了“简化”改成变量缓存或复杂表达式，否则可能破坏构建期处理。

第四个误区是低估 `console` 捕获的影响。`job.tsx` 为了复用 CLI handler，会临时替换全局 `console.log` 和 `console.error`。虽然 finally 中会恢复，但这仍然是进程级副作用。如果未来让 `/job` 执行更长时间的异步任务，或者 handler 内部并发执行其他输出逻辑，就需要重新评估这种捕获方式是否足够稳妥。

第五个误区是以为 `/job reply` 会直接推动模型继续执行。根据当前片段推断，`reply` 只是通过 `appendJobReply()` 把文本追加到已有 job 的状态或目录中；它不在 `src/commands/job` 里启动主 query loop，也没有直接调用模型 API。后续如何消费这些回复，需要继续看 `src/jobs/state.ts` 以及其他 job runner 相关模块。
