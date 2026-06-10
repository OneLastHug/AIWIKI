# 目录：src/commands/history

## 它负责什么

`src/commands/history` 实现的是一个面向 pipe IPC 主从会话的本地 slash command：`/history`。它的职责不是查看当前 CLI 的普通输入历史，也不是展示 Claude 对话的完整 transcript，而是在 master CLI 已经通过 `/attach <pipe-name>` 连接到某个 sub/slave CLI 后，读取该 slave 在 `AppState.pipeIpc.slaves[name].history` 中累计的会话事件，并格式化成一段文本返回给终端 UI。

这个目录属于 UDS/pipe inbox 功能的一部分。根据 `src/commands.js` 中的条件加载逻辑，`historyCmd` 只在 `feature('UDS_INBOX')` 为真时注册。因此它和 `/attach`、`/send`、`/pipe-status`、`/detach`、`/pipes` 等命令处在同一组能力里，服务于“一个主 CLI 控制、观察多个子 CLI”的工作流。

它输出的历史条目是轻量事件流，常见类型包括 `prompt`、`prompt_ack`、`stream`、`tool_start`、`tool_result`、`done`、`error` 等。每条记录包含 `type`、`content`、`from`、`timestamp`，可能还有 `meta`。`/history` 会把时间截成 `HH:MM:SS`，把事件类型转成类似 `[PROMPT]`、`[AI]`、`[TOOL>]` 的前缀，并把单条内容截断到 200 字符以内，避免终端输出过长。

## 直接子目录地图

`src/commands/history` 当前没有直接子目录，只有两个文件：

`src/commands/history/index.ts`：命令元数据入口。声明命令名 `history`、别名 `hist`、描述、是否支持非交互模式，以及懒加载实现模块。

`src/commands/history/history.ts`：命令执行逻辑。导出 `call: LocalCommandCall`，负责校验当前 pipe 角色、解析参数、读取目标 slave 的历史数组、格式化输出。

因此这个目录可以看作一个非常薄的命令封装：`index.ts` 负责接入命令系统，`history.ts` 负责真正的业务处理。它没有自己的状态管理、网络连接、持久化或 UI 组件。

## 关键入口

第一层入口是 `src/commands.js`。这里在 `feature('UDS_INBOX')` 条件成立时通过 `require('./commands/history/index.js').default` 加载命令定义，并把它纳入全局 slash command 列表。也就是说，`/history` 是否可用首先取决于 `UDS_INBOX` feature flag。

第二层入口是 `src/commands/history/index.ts`。这里导出的对象满足 `Command` 类型，关键字段包括：

`type: 'local'` 表示它是本地命令，不会作为普通用户消息发给模型。

`name: 'history'` 和 `aliases: ['hist']` 表示用户可以输入 `/history` 或 `/hist`。

`supportsNonInteractive: false` 表示它不面向非交互模式使用。

`load: () => import('./history.js')` 表示实现按需加载，真正执行时才导入 `history.ts` 编译后的模块。

第三层入口是 `src/commands/history/history.ts` 中的 `call(args, context)`。这是命令系统调用的实际处理函数。它通过 `context.getAppState()` 读取当前应用状态，再用 `getPipeIpc(currentState)` 获取 pipe IPC 子状态。

## 主流程位置

主流程集中在 `src/commands/history/history.ts` 的 `call` 函数内，可以按五步理解。

第一步，确认当前 CLI 是 master。代码检查 `getPipeIpc(currentState).role !== 'master'`，如果不是 master，就返回 `Not in master mode. Use /attach <pipe-name> first.`。这说明 `/history` 的观察视角只能来自主控端，sub/slave 自己不能用它查看 master 收集到的历史。

第二步，解析参数。实现用 `args.trim().split(/\s+/)` 把参数拆成数组，并把第一个 token 当作 `targetName`。所以主要调用形式是 `/history <pipe-name>`。如果没有传入 pipe 名称，它不会默认展示所有历史，而是列出当前已连接的 slave 名称，返回用法提示：`Usage: /history <pipe-name>`。

第三步，查找目标 slave。命令从 `getPipeIpc(currentState).slaves[targetName]` 里取状态。如果找不到，就提示当前没有 attached 到这个 pipe，并建议用 `/status` 查看连接的 sub sessions。这里的 `/status` 文案和 `src/commands/pipe-status/pipe-status.ts` 的用途有交集；根据当前片段推断，项目里可能存在通用 `/status` 或 pipe 状态命令的命名演进，`/pipe-status` 中也会提示 `/history <name>` 用来查看 sub session transcript。

第四步，处理 `--last N`。默认 `limit = slave.history.length`，也就是展示该 slave 的全部已记录事件。如果参数中包含 `--last` 且后面是正整数，就只取最后 N 条：`slave.history.slice(-limit)`。这个解析非常朴素，只识别独立 token `--last`，不支持 `--last=10` 这类写法。

第五步，格式化输出。如果没有 entries，返回 `No session history for "<targetName>" yet.`。否则先输出标题 `Session history for "<targetName>" (展示条数/总条数 entries):`，再逐条输出 `[时间] [类型] 内容`。事件类型转换由内部函数 `formatEntryType(type)` 完成，未知类型会退回成 `[${type}]`。

历史数据本身主要由邻近模块维护。`src/commands/send/send.ts` 在 master 发送 `/send <pipe-name> <message>` 时，会把发送出去的 prompt 追加进对应 slave 的 `history`。`src/hooks/useMasterMonitor.ts` 负责监听 slave client 发回的 pipe 消息，将 `prompt_ack`、`stream`、`tool_start`、`tool_result`、`done`、`error` 等事件转换为 `SessionEntry`，再通过 `applyPipeEntryToSlaveState` 追加到 slave state 的 `history`。`src/utils/pipeTransport.ts` 定义了 `PipeIpcSlaveState.history` 的结构和 `getPipeIpc` 的默认兜底读取方式。

## 推荐阅读顺序

建议先读 `src/commands/history/index.ts`，因为它最短，可以马上确认这是一个 local slash command，并看到命令名、别名、懒加载方式和非交互限制。

然后读 `src/commands/history/history.ts`，重点看 `call` 的角色校验、参数解析、slave 查找、`--last` 截取和 `formatEntryType`。这一文件已经覆盖 `/history` 自身的全部行为。

接着读 `src/utils/pipeTransport.ts` 中 `PipeIpcSlaveState`、`PipeIpcState`、`getPipeIpc` 的定义，理解 `history` 字段从属于 `AppState.pipeIpc.slaves`，而不是全局对话历史。

再读 `src/hooks/useMasterMonitor.ts`，重点看 `SessionEntry`、`applyPipeEntryToSlaveState`、`attachPipeEntryEmitter`、`useMasterMonitor`。这里解释了 slave 返回的流式消息如何进入 history。

最后按需读 `src/commands/send/send.ts` 和 `src/commands/pipe-status/pipe-status.ts`。前者展示 master 主动发送 prompt 时如何记录历史，后者展示 pipe 状态页如何把 `/history <name>` 暴露给用户作为后续操作。

## 常见误区

第一，不要把这个目录和根部的 `src/history.js` 或 `src/history.ts` 混淆。`src/screens/REPL.tsx`、`src/components/PromptInput/PromptInput.tsx` 里引用的 `../history.js` 更偏向普通 prompt 历史、粘贴引用和输入框历史搜索；`src/commands/history` 则是 pipe slave session history 查看命令。

第二，`/history` 不是模型上下文历史查看器。它不会读取完整 Claude conversation messages，也不会展示 compaction 前后的完整 UI scrollback。它只展示 master 记录到某个 slave 连接状态里的 pipe 事件。

第三，`/history` 必须在 master mode 下使用。通常需要先通过 `/attach <pipe-name>` 建立 master/slave 关系；否则即使当前 CLI 有自己的对话，也会返回“Not in master mode”。

第四，`/history` 不负责收集历史。它只是读取和格式化已经存在的 `slave.history`。历史的写入来自 `/send`、master monitor、pipe client message listener 等邻近模块。如果这些监听没有运行，或者 slave 被 mute 后相关业务消息被丢弃，这里的输出就会变少或为空。

第五，`--last` 只是简单参数，不是完整命令行 parser。正确形式是 `/history <name> --last 20`。根据当前实现，`/history <name> --last=20` 不会生效，非法数字或非正数也会退回展示全部历史。

第六，输出内容会截断。每条 `entry.content` 超过 200 字符时会被截成前 200 字符并追加 `...`。所以它适合快速浏览 sub session transcript 的事件脉络，不适合做完整日志导出或精确复盘。
