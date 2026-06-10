# 目录：src/commands/daemon

## 它负责什么

这个目录是 `daemon` 命令在“命令系统”这一层的适配入口，负责把用户在 REPL 或命令体系里输入的 `/daemon` 或 `claude daemon ...`，转成真正的后台守护进程管理与背景会话操作。根据当前片段推断，它本身不承载守护进程核心逻辑，而是做一层很薄的分发：一边决定这个命令是否可见，另一边把具体动作交给 `src/daemon/main.ts` 和 `src/cli/bg.ts`。

它的定位更像“命令壳”而不是“业务实现”。`index.ts` 提供命令元数据，`daemon.tsx` 提供 REPL 里的执行函数，测试文件只验证这两个出口是否还保持着正确形状。

## 直接子目录地图

这个目录本身很小，直接子项只有一层文件和一个测试子目录：

- `index.ts`：命令描述与加载入口。
- `daemon.tsx`：命令执行逻辑，面向 REPL slash command。
- `__tests__/`：目录级回归测试，目前只看到 `daemon.test.ts`。

这里没有更深的业务子目录，说明它不是一个功能树，而是一个接口壳。真正的复杂度在旁边的 `src/daemon/`、`src/cli/bg.ts` 等目录里。

## 关键入口

最关键的入口是 `src/commands/daemon/index.ts`。它导出一个 `Command` 对象，名字固定为 `daemon`，类型是 `local-jsx`，描述是“Manage background sessions and daemon”，并通过 `load: () => import('./daemon.js')` 动态加载执行模块。也就是说，命令定义和命令执行是拆开的，`index.ts` 只负责告诉上层“有这么个命令，什么时候启用、加载谁”。

第二个入口是 `src/commands/daemon/daemon.tsx` 的 `call()`。它接收 `args`，把空参数默认解释为 `status`，并处理 `attach` 这种不能在 REPL 内直接完成的交互场景。除此之外，它会把输出捕获后回传给 `onDone`，让命令结果以系统消息形式落回界面。

## 主流程位置

真正的主流程不在这个目录里，而在外层实现：

- `src/daemon/main.ts`：守护进程主管线。这里包含 `daemonMain()`，负责解析 `start`、`stop`、`status/ps`、`bg`、`attach`、`logs`、`kill` 等子命令，并进一步调度 supervisor、状态查询和会话管理。
- `src/cli/bg.ts`：背景会话相关操作的实际实现。`daemon.tsx` 里对 `bg` 的处理，以及 `src/daemon/main.ts` 里对 `bg/attach/logs/kill` 的处理，最终都会落到这里。
- `src/entrypoints/cli.tsx`：CLI 级别的快速路径入口。这里有 `claude daemon ...` 的分支，也有 `--bg`、`ps/logs/attach/kill` 之类的兼容路径。也就是说，命令系统里的 `/daemon` 和 CLI 里的 `claude daemon` 最终会汇流到同一套后台逻辑。

如果只看这个目录，很容易误以为它实现了整个 daemon；实际上它只是把用户输入接到正确的总线上的接口层。

## 推荐阅读顺序

1. 先看 `src/commands/daemon/index.ts`，建立这个命令在系统中的身份感。
2. 再看 `src/commands/daemon/daemon.tsx`，理解 REPL 场景下的分发和特殊处理。
3. 接着看 `src/daemon/main.ts`，把 `start/stop/status` 的真实流程串起来。
4. 然后看 `src/cli/bg.ts`，理解 `bg`、`attach`、`logs`、`kill` 这些会话操作的落点。
5. 最后看 `src/commands/daemon/__tests__/daemon.test.ts`，确认当前目录的回归保护只覆盖了哪些契约。

## 常见误区

- 把这个目录当成 daemon 核心实现。实际上核心在 `src/daemon/main.ts`，这里更多是命令适配。
- 忽略 `attach` 的限制。`daemon.tsx` 明确把 REPL 内的 `attach` 拦下来，提示去 CLI 里执行。
- 混淆 `bg` 和 supervisor。`bg` 是背景会话启动，不等于启动 daemon supervisor；它们只是共享了 `daemon` 这个命名空间。
- 只看 `index.ts` 以为命令逻辑很少。真正的行为分发在 `daemon.tsx`，而且它还会动态导入外部模块。
- 以为 `status` 只是查看 daemon 状态。实际上它是统一状态视图，既查 supervisor，也查背景会话。
- 低估 feature flag 的作用。`index.ts` 里的 `isEnabled()` 受 `DAEMON` 和 `BG_SESSIONS` 控制，命令是否出现是运行时决定的，不是静态常量。
