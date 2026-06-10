# 目录：src/commands/pipes

## 它负责什么

`src/commands/pipes` 实现的是交互式命令 `/pipes`。它不是底层 IPC 传输层，而是 pipe 多实例协作能力的“查看与选择”入口：读取当前 CLI 的 pipe 状态、清理并展示 registry 中的 main/sub 会话、更新 UI 中的 pipe selector 状态，并维护“哪些 pipe 会接收广播消息”的选择列表。

从功能边界看，这个目录只做三类事情：

1. 打开或切换 pipe 状态展示：执行 `/pipes` 时会把 `AppState.pipeIpc.statusVisible` 设为 `true`，并切换 `selectorOpen`，让 REPL 底部或选择面板进入可见状态。
2. 管理广播目标：支持 `/pipes select <name>`、`/pipes deselect <name>`、`/pipes all`、`/pipes none`，本质上是在 `pipeIpc.selectedPipes` 中增删 pipe 名称。
3. 输出 registry 概览：读取 `src/utils/pipeRegistry.ts` 维护的 main/sub 信息，并用 `src/utils/pipeTransport.ts` 的探活与状态辅助函数生成文本报告。

它和 `/attach`、`/detach`、`/send`、`/pipe-status`、`/claim-main` 属于同一组 UDS pipe 协作命令。`/pipes` 偏“列表、选择、概览”，`/send` 偏“定向发送”，`/attach` 和 `/detach` 偏“建立或解除控制关系”。

## 直接子目录地图

该目录没有直接子目录，只有两个文件：

`src/commands/pipes/index.ts`：命令元数据声明文件。它把 `/pipes` 注册为 local command，并通过 `load: () => import('./pipes.js')` 懒加载实际实现。

`src/commands/pipes/pipes.ts`：命令执行逻辑。核心导出是 `call: LocalCommandCall`，所有 `/pipes` 参数解析、状态更新、registry 读取、LAN peers 合并展示都在这里完成。

因为目录规模很小，阅读时不需要按“子模块”拆分理解；更合适的方式是把它看成一个 local command 的标准两段式结构：`index.ts` 负责声明，`pipes.ts` 负责运行。

## 关键入口

第一层入口是 `src/commands.ts`。这里在 `feature('UDS_INBOX')` 为真时加载 `./commands/pipes/index.js`，并把 `pipesCmd` 加入命令列表。也就是说，`/pipes` 是否存在不是由目录自身决定的，而是由 feature flag `UDS_INBOX` 控制。

第二层入口是 `src/commands/pipes/index.ts`。这个文件定义：

`name: 'pipes'` 表示用户输入 `/pipes` 会命中该命令。

`description: 'Inspect pipe registry state and toggle the pipe selector'` 概括了它的定位：查看 pipe registry 并切换 selector。

`supportsNonInteractive: true` 表示它允许在非交互模式下被调用。需要注意，这不代表底层 pipe UI 一定完整可见，只表示命令系统允许执行它。

`load: () => import('./pipes.js')` 说明实现是懒加载的，只有真正调用时才进入 `pipes.ts`。

第三层入口是 `src/commands/pipes/pipes.ts` 中的 `call(_args, context)`。这是实际执行 `/pipes` 的函数。它通过 `context.getAppState()` 读取当前 UI 状态，通过 `context.setAppState()` 写回 `pipeIpc` 相关字段，并返回 `{ type: 'text', value: ... }` 作为命令输出。

## 主流程位置

主流程集中在 `src/commands/pipes/pipes.ts` 的 `call` 函数中，可以按执行顺序理解。

首先，函数会清理参数：`const args = _args.trim()`。随后无论用户传入什么子命令，它都会先更新 `AppState.pipeIpc`：把 `statusVisible` 设为 `true`，并反转 `selectorOpen`。这意味着 `/pipes` 本身也承担“打开/关闭选择面板”的 UI 动作。

接着进入参数分支。`select` 或 `sel` 会解析目标 pipe 名称，并把它追加到 `selectedPipes`。如果已经选中，则保持原状态。`deselect`、`desel`、`unsel` 会从 `selectedPipes` 中移除目标。`all` 或 `select-all` 会读取当前 `pipeState.slaves`，把所有已连接的 sub pipe 名称设为广播目标。`none` 或 `deselect-all` 会清空 `selectedPipes`，让后续消息只在本地执行。

如果没有命中特定选择子命令，流程进入状态概览生成。代码会读取当前 `pipeIpc`，取得当前 pipe 名称 `serverName`、显示角色 `getPipeDisplayRole(pipeState)`、机器 ID、IP、hostname，以及是否被其他 pipe 控制 `isPipeControlled(pipeState)`。

然后调用 `cleanupStaleEntries()` 清理过期 registry，再用 `readRegistry()` 读取最新 registry。registry 中的 main 会话和 sub 会话会分别通过 `isPipeAlive(pipeName, 1000)` 探活，并被格式化到输出文本里。sub 条目还会显示是否被选中、是否已连接、是否是当前会话。

如果启用了 `feature('LAN_PIPES')`，`pipes.ts` 会动态 require `src/utils/lanBeacon.ts`，从 LAN beacon 中获取 peers，再通过 `mergeWithLanPeers(registry, lanPeers)` 合并本地 registry 和局域网发现结果。这里根据当前片段推断，LAN peers 是对本机 registry 的补充发现渠道，依据是代码只在 `LAN_PIPES` 打开后读取 `getLanBeacon().getPeers()`，并把 `source === 'lan'` 的条目单独输出为 `LAN Peers`。

最后，命令会把活跃的本地 sub 和 LAN peer 写回 `pipeIpc.discoveredPipes`，并在文本末尾输出当前选中列表和可用命令提示，包括 `/pipes select`、`/pipes deselect`、`/pipes all`、`/pipes none`、`/send`、`/claim-main`。

## 推荐阅读顺序

1. 先读 `src/commands.ts` 中 `pipesCmd` 的 feature-gated 注册逻辑，确认 `/pipes` 只在 `UDS_INBOX` 打开时加入命令系统。
2. 再读 `src/commands/pipes/index.ts`，理解 local command 的声明方式，以及为什么实现文件是懒加载的。
3. 然后读 `src/commands/pipes/pipes.ts` 的前半部分，重点看 `select`、`deselect`、`all`、`none` 如何修改 `pipeIpc.selectedPipes`。
4. 接着读同一文件后半部分，关注 `cleanupStaleEntries()`、`readRegistry()`、`isPipeAlive()`、`mergeWithLanPeers()` 如何参与生成状态报告。
5. 最后再跳到邻近上下文：`src/utils/pipeTransport.ts` 看 `PipeIpcState`、`getPipeIpc`、`getPipeDisplayRole`、`isPipeControlled`；到 `src/utils/pipeRegistry.ts` 看 registry 的 main/sub 数据结构与清理逻辑；到 `src/hooks/usePipeRouter.ts` 看 `selectedPipes` 后续如何影响用户输入路由。

## 常见误区

第一，`src/commands/pipes` 不是 pipe 通信协议实现。真正的 server/client、socket path、named pipe、TCP endpoint、ping 探活等逻辑在 `src/utils/pipeTransport.ts`，registry 文件读写在 `src/utils/pipeRegistry.ts`。这个目录只是命令层。

第二，`/pipes all` 选择的是当前 `pipeState.slaves` 中已经连接的 pipe，而不是 registry 里所有发现到的 pipe，也不是 LAN peers 的全集。它的语义更接近“选择所有已连接 sub”。

第三，`/pipes` 每次执行都会切换 `selectorOpen`。所以它不只是“打印状态”，还会影响 UI 面板开关。阅读时如果只看返回文本，容易漏掉前面的 `context.setAppState` 副作用。

第四，LAN peers 展示受 `LAN_PIPES` 控制，而命令本身受 `UDS_INBOX` 控制。不要把这两个 feature flag 混为一谈：`UDS_INBOX` 决定 `/pipes` 是否注册，`LAN_PIPES` 只决定是否额外展示局域网发现的 peers。

第五，`discoveredPipes` 是由 `/pipes` 执行时刷新的一份 UI/路由辅助状态，不等同于底层 registry 的完整真实状态。它只收集当前命令探测后认为 alive 的 sub 和可见 LAN peer。
