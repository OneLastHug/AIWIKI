# 目录：src/commands/fork

## 它负责什么

`src/commands/fork` 负责实现交互式 REPL 里的 `/fork <directive>` 斜杠命令。它的作用不是复制当前会话生成一个可继续操作的“会话分支”，而是把用户给出的指令包装成一个后台运行的 fork sub-agent 任务：子 agent 继承父会话上下文、已渲染的 system prompt、模型和工具池，然后异步执行用户给出的 directive。

这个目录本身很薄，更像是 slash command 到 `AgentTool` fork 路径的适配层。真正复杂的 fork agent 行为不在这里，而在 `packages/builtin-tools/src/tools/AgentTool/AgentTool.tsx` 和 `packages/builtin-tools/src/tools/AgentTool/forkSubagent.ts`。`src/commands/fork` 主要做输入校验、递归 fork 防护、找出 fork 起点消息、调用 `AgentTool.call()`，并向主对话返回“已启动”的系统提示。

根据当前片段推断，这个命令属于实验/可选能力：它受 `FORK_SUBAGENT` feature flag 控制。注册阶段在 `src/commands.ts` 里按 feature 动态加载，执行阶段 `fork.tsx` 又再次检查 `feature('FORK_SUBAGENT')`，属于双层保护。

## 直接子目录地图

`src/commands/fork` 没有直接子目录，是一个扁平的小目录。当前只包含两个文件：

`src/commands/fork/index.ts` 是命令元信息声明文件，定义命令类型、名称、描述、参数提示和懒加载入口。

`src/commands/fork/fork.tsx` 是命令执行体，导出 `call()`，处理 `/fork` 的实际运行逻辑。

这个目录没有测试文件、共享工具、UI 子组件或嵌套模块。阅读时不需要按树状结构展开，重点看它如何接入全局命令表，以及如何把请求转交给 `AgentTool`。

## 关键入口

第一层入口是 `src/commands.ts`。这里通过：

`feature('FORK_SUBAGENT') ? require('./commands/fork/index.js').default : null`

决定是否把 `/fork` 命令加入全局 `commands` 列表。后面在命令数组中通过 `...(forkCmd ? [forkCmd] : [])` 注入。也就是说，如果 `FORK_SUBAGENT` 没启用，正常命令列表里不会出现这个 `/fork`。

第二层入口是 `src/commands/fork/index.ts`。它声明：

`type: 'local-jsx'`、`name: 'fork'`、`description: 'Fork the current session into a new sub-agent'`、`argumentHint: '<prompt>'`，并用 `load: () => import('./fork.js')` 懒加载执行模块。这里遵循本仓库 slash command 的常见模式：轻量 index 参与注册，重逻辑放到实际实现文件里按需加载。

第三层入口是 `src/commands/fork/fork.tsx` 的 `call(onDone, context, args)`。这是本目录最核心的函数。它接收命令完成回调、当前命令上下文和用户输入参数，最后返回 `React.ReactNode | null`。当前实现始终返回 `null`，因为它不渲染持续性的 Ink 组件，只通过 `onDone()` 输出系统消息，并在后台启动 agent。

## 主流程位置

主流程集中在 `src/commands/fork/fork.tsx` 的 `call()` 中，可以按几个阶段理解。

第一步是 feature flag 检查。即使命令理论上只在 `src/commands.ts` 中 feature 开启时才注册，`call()` 里仍然再次检查 `feature('FORK_SUBAGENT')`。如果未启用，会通过 `onDone()` 返回系统提示：需要设置 `FEATURE_FORK_SUBAGENT=1`。

第二步是递归 fork 防护。代码调用 `isInForkChild(context.messages)` 判断当前会话是否已经处在 fork worker 里。如果是，就拒绝继续 fork，并提示用户在当前 worker 中直接完成任务。`isInForkChild()` 来自 `packages/builtin-tools/src/tools/AgentTool/forkSubagent.ts`，其依据是历史用户消息中是否包含 fork boilerplate 标记。这个设计说明 fork 子进程虽然可能保留 `AgentTool` 在工具池中，但运行时会禁止继续嵌套创建 fork。

第三步是参数校验。`args.trim()` 后得到 `directive`。如果为空，返回用法提示：`/fork <directive>`。这里的参数不是会话名，也不是分支名，而是交给子 agent 执行的自然语言任务指令。

第四步是寻找 fork 起点。实现从 `context.messages` 反向查找最后一条 `assistant` 消息作为 `lastAssistantMessage`。如果当前会话历史里还没有 assistant 响应，则无法 fork。这说明 `/fork` 的语义是从已有对话状态中派生任务，而不是从空白上下文直接启动 agent。

第五步是构造 `AgentTool` 输入并异步调用。传入对象包含 `prompt: directive`、`fork: true`、`run_in_background: true`、`description: 'forked from main'`。注释明确说明：不传 `subagent_type`，配合 `fork: true`，触发 `AgentTool` 的 implicit fork 路径。随后执行：

`AgentTool.call(input, context, context.canUseTool!, lastAssistantMessage).catch(...)`

这里没有 `await`，所以 `/fork` 命令本身会立即结束，后台 agent 生命周期由 `AgentTool` 和任务系统接管。同步启动成功后，主会话只收到 `Forked subagent started with directive: "..."`
这样的系统提示。异步错误会写入 `logForDebugging()`，不会阻塞当前命令返回。

更深一层的 fork 行为在 `packages/builtin-tools/src/tools/AgentTool/forkSubagent.ts`。其中 `isForkSubagentEnabled()` 说明该能力启用后，`subagent_type` 可省略，省略时创建继承父上下文和 system prompt 的 implicit fork；同时它会在 coordinator mode 或 non-interactive session 下关闭。`FORK_AGENT` 则描述了 fork agent 的合成定义：`agentType` 为 `fork`，`tools: ['*']`，`model: 'inherit'`，`permissionMode: 'bubble'`，并强调 system prompt 使用父会话已渲染字节，避免重新生成导致 prompt cache 不一致。

另外要注意 `src/commands/branch/index.ts`。当 `FORK_SUBAGENT` 未启用时，`/branch` 会把 `fork` 作为 alias；当 `/fork` 作为独立命令存在时，`/branch` 的 `aliases` 变为空。这解释了为什么同一个词 `fork` 在不同 feature 状态下可能指向不同能力。

## 推荐阅读顺序

建议先读 `src/commands/fork/index.ts`，确认它只是一个 `local-jsx` slash command 声明，理解 `/fork` 是如何被命令系统发现和懒加载的。

然后读 `src/commands.ts` 中 `forkCmd` 的注册片段，确认 `FORK_SUBAGENT` 是命令是否出现的第一道开关。顺手看 `src/commands/branch/index.ts`，理解 `/branch` 与 `/fork` 名称关系，避免把两者混成同一种“分支”能力。

接着读 `src/commands/fork/fork.tsx` 的 `call()`。这是本目录的主逻辑，重点关注 feature 检查、`isInForkChild()`、`directive`、`lastAssistantMessage` 和 `AgentTool.call()` 这几个点。

最后再跳到 `packages/builtin-tools/src/tools/AgentTool/forkSubagent.ts` 和 `packages/builtin-tools/src/tools/AgentTool/AgentTool.tsx`。前者解释 fork sub-agent 的启用条件、合成 agent 定义和递归防护；后者承载真正的 agent 启动、后台任务、工具池、权限、进度和生命周期管理。对于 overview 深度，读到 fork 相关注释和 import 关系即可，不必展开整个 `AgentTool`。

## 常见误区

第一个误区是把 `/fork` 理解成 `/branch`。`/branch` 复制 transcript，创建可恢复的会话分支；`/fork` 启动后台 sub-agent，处理一条 directive。两者都可能和“fork”这个词有关，但用户体验和数据流不同。

第二个误区是认为 `/fork` 会同步返回 agent 结果。当前实现没有等待 `AgentTool.call()` 完成，而是 fire-and-forget 式启动后台任务。命令本身只负责通知“已启动”。

第三个误区是忽略 feature flag。`FORK_SUBAGENT` 不仅控制命令注册，也在运行时再次校验；同时 `forkSubagent.ts` 里还会在 coordinator mode、non-interactive session 下关闭 fork subagent 能力。

第四个误区是以为 fork 可以无限嵌套。`isInForkChild()` 会检测 fork boilerplate，并拒绝在 fork worker 内再次 `/fork`。这是为了避免递归派生导致任务失控，也符合注释中“fork child 保留 Agent tool 只是为了缓存一致”的设计背景。

第五个误区是把 `description: 'forked from main'` 当成用户任务内容。真正传给子 agent 的任务是 `prompt: directive`；`description` 只是后台任务选择器或进度界面的短标签，代码注释也说明不要重复展示用户输入的 prompt。

第六个误区是只看 `src/commands/fork` 就试图理解完整 fork 机制。这个目录只是适配层；上下文继承、工具过滤、权限冒泡、后台任务注册、prompt cache 保护等核心逻辑都在 `AgentTool` 及其 fork helper 中。
