# 目录：src/commands/send

## 它负责什么

`src/commands/send` 实现交互式命令 `/send`，作用是在当前 CLI 已经处于 master 模式时，把一段用户输入的任务文本发送给某个已连接的 sub CLI。它属于 pipe IPC / UDS inbox 这组能力的一环：`/attach` 负责建立 master 到 sub 的连接，`/send` 负责向指定 sub 下发 prompt，`/status` 和 `/history` 负责查看连接状态与回传历史，`/detach` 负责断开连接。

这个目录本身不负责创建 pipe server、发现 pipe、建立连接，也不负责处理 sub 端收到 prompt 后如何进入模型查询流程。它只做 master 侧的“定向发送”动作：校验当前角色、解析目标名称和消息、找到已注册的 `PipeClient`、发送 `relay_unmute` 和 `prompt` 两类 pipe 消息，并同步更新当前 AppState 中对应 slave 的状态和历史。

根据当前片段推断，`/send` 是 master-slave bridge 模式里的显式调度入口：用户通过 `/send <pipe-name> <message>` 把任务交给某个 sub session，master 继续通过 `useMasterMonitor` 收集该 sub 的 `prompt_ack`、`stream`、`tool_start`、`tool_result`、`done`、`error` 等事件，用于 UI 展示、状态更新和历史查询。

## 直接子目录地图

`src/commands/send` 没有直接子目录，只有两个文件：

`src/commands/send/index.ts` 是命令声明文件，导出一个 `Command` 对象，告诉命令系统这里有一个名为 `send` 的 local command。

`src/commands/send/send.ts` 是命令执行文件，导出 `call: LocalCommandCall`，包含 `/send` 的实际业务逻辑。

由于目录规模很小，阅读时不需要按模块树展开。它更像是 pipe IPC 命令族中的一个叶子入口，真正的上下文分布在相邻目录和共享工具里，例如 `src/commands/attach`、`src/commands/detach`、`src/commands/pipe-status`、`src/commands/history`、`src/commands/pipes`、`src/hooks/useMasterMonitor.ts`、`src/utils/pipeTransport.ts`、`src/utils/pipeMuteState.ts`。

## 关键入口

命令注册入口在 `src/commands/send/index.ts`。这里声明：

`type: 'local'` 表示它是本地 slash command，不是外部 CLI 子命令。

`name: 'send'` 对应用户输入的 `/send`。

`description: 'Send a message to a connected sub CLI'` 用于命令描述。

`supportsNonInteractive: false` 表示该命令不支持非交互模式。它依赖当前 REPL/AppState 中已有的 pipe 连接状态，因此天然属于交互会话内命令。

`load: () => import('./send.js')` 使用延迟加载，把真正执行逻辑放到 `send.ts`，命令被调用时再加载。

命令是否进入全局命令列表由 `src/commands.ts` 控制。`sendCmd` 只有在 `feature('UDS_INBOX')` 为真时才会 `require('./commands/send/index.js').default`，随后被插入 commands 数组。因此 `/send` 是 feature flag 保护下的能力，不是基础命令常开的一部分。

执行入口在 `src/commands/send/send.ts` 的 `call(args, context)`。`args` 是 `/send` 后面的原始参数字符串，`context` 提供 `getAppState()` 和 `setAppState()`，用于读取和更新当前 CLI 的应用状态。

## 主流程位置

主流程集中在 `src/commands/send/send.ts`，可以按五步理解。

第一步，确认当前 CLI 是否是 master。代码通过 `context.getAppState()` 取得当前状态，再用 `getPipeIpc(currentState).role` 判断。如果不是 `master`，直接返回文本提示：需要先执行 `/attach <pipe-name>`。这说明 `/send` 不负责建立连接，只能操作已经 attach 的 sub。

第二步，解析参数。`/send` 的参数格式是第一段为 pipe 名称，后面全部作为消息内容。实现上先 `trim()`，再找第一个空格：空格前是 `targetName`，空格后是 `message`。如果没有空格，或者 message 为空，返回 `Usage: /send <pipe-name> <message>`。这意味着消息本身可以包含空格，但目标名不能包含空格。

第三步，查找并校验连接。代码调用 `getSlaveClient(targetName)`，这个 client 来自 `src/hooks/useMasterMonitor.ts` 中的模块级 registry。该 registry 由 `/attach` 成功后通过 `addSlaveClient(targetName, client)` 写入。如果找不到 client，提示用户未 attach；如果 client 存在但 `connected` 为假，提示先 `/detach` 再重新 attach。

第四步，发送 pipe 消息。成功路径里会先调用 `addSendOverride(targetName)` 和 `removeMasterPipeMute(targetName)`，再通过 `client.send({ type: 'relay_unmute' })` 临时解除该 slave 的静音状态，然后发送真正的 prompt：`client.send({ type: 'prompt', data: message })`。这里的 `relay_unmute` 和 `prompt` 都是 `src/utils/pipeTransport.ts` 中定义的 `PipeMessageType`。`prompt` 是 master 到 slave 的数据流消息，代表“请 sub 执行这段用户任务”。

第五步，更新 AppState。发送后，`context.setAppState()` 会把对应 slave 标记为 `busy`，更新 `lastActivityAt`、`lastSummary`、`lastEventType`，并向 `history` 追加一条 `type: 'prompt'` 的记录。记录里的 `from` 来自当前 master 的 `serverName`，如果没有则用 `'master'`。这使 `/status` 和 `/history` 能立即看到刚刚下发的任务，而不必等待 sub 回传 acknowledgement。

异常路径也很短：如果发送过程中抛错，会调用 `removeSendOverride(targetName)` 回滚临时 override，避免目标 slave 在失败后一直处于非静音状态，然后返回失败原因。

## 推荐阅读顺序

建议先读 `src/commands/send/index.ts`，确认它只是 command metadata 和 lazy load 入口。

然后读 `src/commands.ts` 中 `sendCmd` 的注册位置，理解 `/send` 受 `UDS_INBOX` feature gate 控制，并且与 `attach`、`detach`、`pipes`、`pipe-status`、`history`、`claim-main` 同属一组 pipe 命令。

接着读 `src/commands/attach/attach.ts`。`/send` 的前置条件来自这里：`/attach` 连接目标 pipe，收到 `attach_accept` 后调用 `addSlaveClient()`，并把 AppState 的 `pipeIpc.role` 设置成 `master`。没有这一步，`/send` 会因为不是 master 或找不到 client 而退出。

之后读 `src/commands/send/send.ts`，重点看参数解析、`getSlaveClient()`、`relay_unmute`、`prompt`、AppState 更新这几个点。

再读 `src/hooks/useMasterMonitor.ts`。这里解释了 `/send` 之后为什么能看到 sub 回传：`attachPipeEntryEmitter()` 会监听 client 的 pipe message，把 `prompt_ack`、`stream`、`tool_start`、`tool_result`、`done`、`error` 等消息转换成 `SessionEntry`，并在 `done` 或 `error` 时清理 `/send` override。

最后读 `src/utils/pipeTransport.ts` 和 `src/utils/pipeMuteState.ts`。前者定义 pipe 协议和 `PipeMessageType`，后者定义 master 侧逻辑静音和 `/send` 临时 override 的状态管理。

## 常见误区

不要把 `/send` 理解成普通聊天发送入口。普通用户消息进入模型查询主循环的位置不在这个目录；这里发送的是 pipe IPC 层面的 `prompt` 消息，目标是另一个已连接的 sub CLI。

不要以为 `/send` 会自动发现或连接 pipe。发现可用 pipe 与选择 pipe 更接近 `src/commands/pipes` 的职责，建立 master-slave 连接是 `src/commands/attach` 的职责。`/send` 只面向已经 attach 且仍 connected 的 slave client。

不要忽略 master 角色校验。`/send` 只能在 `getPipeIpc(state).role === 'master'` 时工作。如果当前 CLI 是 `main`，或者是被其他 master 控制的 sub，会被拒绝或无法找到目标 client。

不要把 `relay_unmute` 当作永久状态切换。`send.ts` 会添加 send override 并移除 master mute，是为了让这次显式发送后的响应可见；`useMasterMonitor` 在收到 `done` 或 `error` 后会清理 override。根据当前片段推断，这是一种“显式发送临时放行”的设计，用来配合逻辑断开/静音机制。

不要认为 AppState 里的 history 完全来自 sub 回传。`/send` 自己会先写入一条 `prompt` 历史，这样 master 侧状态能立即反映“任务已排队”。后续流式输出、工具事件和完成状态才由 monitor 从 pipe message 中补充。

不要绕开 `src/utils/pipeTransport.ts` 直接猜消息格式。`send.ts` 使用的 `prompt`、`relay_unmute` 都属于 pipe 协议枚举，相关类型和语义以 `PipeMessageType` 为准。
