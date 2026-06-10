# 目录：src/commands/peers

## 它负责什么

`src/commands/peers` 是一个很小的本地命令目录，负责实现 Claude Code 进程之间的“peer 发现”列表视图。它的职责不是建立 peer 通信服务本身，也不是维护 session registry，而是把已有的 UDS（Unix Domain Socket）会话发现能力包装成一个可由命令系统调用的本地命令。

从代码看，这个命令面向“当前机器上是否还有其他 Claude Code 实例正在运行并可通过 UDS 收消息”这个问题。它会读取当前进程自己的 messaging socket，列出其他带 `messagingSocketPath` 的 live session，并对每个 peer 做一次 ping/pong 可达性探测。最终输出文本内容，包括当前 socket、peer 数量、peer 的 PID、状态、工作目录、启动时间、socket 地址和 session id。

它依赖的核心能力在目录外部：`src/utils/udsClient.ts` 提供 `listPeers()`、`isPeerAlive()`；`src/utils/udsMessaging.ts` 提供 `getUdsMessagingSocketPath()` 和 `formatUdsAddress()`。因此可以把本目录理解为“命令层适配器”：把底层 UDS/session registry 设施转换成用户可读的 `/peers` 或别名 `/who` 输出。

## 直接子目录地图

这个目录没有直接子目录，只有两个文件：

`src/commands/peers/index.ts`：命令元信息入口。定义命令名、别名、描述、是否支持非交互模式，以及懒加载实现模块。

`src/commands/peers/peers.ts`：命令执行逻辑。负责读取 peer 列表、检查可达性、格式化输出文本。

由于目录规模很小，这里没有进一步的分层，例如没有 `components`、`utils`、`tests` 或子命令目录。目录边界非常清晰：声明在 `index.ts`，执行在 `peers.ts`，底层发现和通信能力全部委托给 `src/utils` 下的 UDS 工具模块。

## 关键入口

最重要的入口是 `src/commands/peers/index.ts` 中导出的默认命令对象：

`name: 'peers'` 表示主命令名是 `peers`。

`aliases: ['who']` 表示它也可以通过 `who` 调用。

`type: 'local'` 表示这是本地命令，不是远程 API 命令或复杂子命令。

`supportsNonInteractive: true` 表示它可以在非交互场景下执行，适合脚本或 headless 调用。

`load: () => import('./peers.js')` 是关键的懒加载入口。命令注册阶段只加载元信息，真正执行时才动态导入 `peers.ts` 编译后的模块。这符合该仓库命令系统常见模式：命令声明轻量，实际逻辑延迟加载，减少 CLI 启动路径上的模块成本。

真正的执行入口在 `src/commands/peers/peers.ts`：

`export const call: LocalCommandCall = async (_args, _context) => { ... }`

命令系统加载模块后会调用这个 `call`。它不使用传入参数，也不依赖命令上下文，说明 `/peers` 当前是一个只读查询命令，没有筛选、删除、连接等操作参数。

## 主流程位置

主流程集中在 `src/commands/peers/peers.ts` 的 `call` 函数中，可以按五步理解。

第一步，获取当前进程自己的 UDS messaging socket：

`getUdsMessagingSocketPath()`

输出的第一行是 `Your socket: ...`。如果当前进程没有启动 messaging socket，就显示 `(not started)`。这能帮助用户知道自己是否也能被其他 peer 消息投递。

第二步，发现 peer：

`listPeers()`

这个函数来自 `src/utils/udsClient.ts`。根据当前片段推断，它会读取 Claude 配置目录下的 `sessions` registry，过滤出 PID 仍在运行、不是当前进程、且带有 `messagingSocketPath` 的会话。也就是说，`peers` 命令看到的不是所有历史 session，而是当前机器上“可能可通信”的其他 Claude Code 进程。

第三步，处理空列表。如果 `peers.length === 0`，输出 `No other Claude Code peers found.`。这里不会报错，因为“没有 peer”是正常状态。

第四步，对每个 peer 做可达性检测：

`isPeerAlive(peer.messagingSocketPath)`

这个检测不是单纯判断 PID，而是尝试连接 UDS socket，并使用认证 token 发起 ping，等待 pong 响应。可达则显示 `[reachable]`，否则显示 `[unreachable]`。这能区分“registry 中存在且 PID 存活”与“socket 实际可用”两种状态。

第五步，格式化 peer 信息。每个 peer 输出 PID、标签、cwd、启动时长、socket 地址和 session id。标签优先取 `peer.name`，其次取 `peer.kind`，最后回退为 `interactive`。启动时间通过本文件内的 `formatAge()` 转换成 `Xs ago`、`Xm ago`、`Xh Ym ago` 这种简短形式。socket 地址通过 `formatUdsAddress()` 转为用户可复制的 `uds:<socket-path>` 形式。

最后，命令会追加提示：

`To message a peer: use SendMessage with the shown uds:<socket-path> address`

这说明 `peers` 命令本身只负责发现和展示，真正向 peer 发消息的能力在其他工具链中，例如注释提到的 `SendMessage`。根据当前片段推断，该能力最终会走 `src/utils/udsClient.ts` 中的 `sendToUdsSocket()` 或相近路径。

## 推荐阅读顺序

建议先读 `src/commands/peers/index.ts`。这个文件最短，能快速确认它在命令系统里的身份：本地命令、命令名 `peers`、别名 `who`、支持非交互执行、执行模块懒加载。

第二步读 `src/commands/peers/peers.ts`。重点看 `call` 函数，而不是先追到底层 UDS 实现。这里能看到用户最终会看到什么输出，也能理解命令的实际职责边界：查询、探测、格式化。

第三步读 `src/utils/udsClient.ts` 的 discovery 部分，尤其是 `listAllLiveSessions()` 和 `listPeers()`。这能解释 peer 从哪里来：不是网络扫描，而是本地 session registry 文件加 PID 过滤。

第四步读 `src/utils/udsClient.ts` 的 `isPeerAlive()`。这能理解 `reachable` 的含义：它要求 socket 可连接、token 可读取、ping/pong 成功，而不是只要进程存在就算可达。

第五步再读 `src/utils/udsMessaging.ts` 中和 socket path、地址格式、token 相关的函数。这个文件能补足为什么输出中会出现 `uds:<socket-path>`，以及 peer 消息为什么需要 capability token。

如果只是写功能概览，读到第二步已经足够；如果要调试 peer 不显示或显示 unreachable，则需要继续读第三到第五步。

## 常见误区

第一个误区是把 `src/commands/peers` 当成 peer 通信服务。它不是服务端，也不负责监听 socket。监听、认证、消息协议和 registry 写入都在其他模块中完成，本目录只是命令层展示入口。

第二个误区是认为 `peers` 会显示所有 Claude Code 历史会话。实际它通过 `listPeers()` 过滤，只保留当前进程以外、PID 存活、并且具有 `messagingSocketPath` 的 session。没有 socket 的 session 不会作为可消息 peer 展示。

第三个误区是把 `[reachable]` 理解成“进程存在”。从依赖实现看，可达性更严格：需要 socket 连接成功，并完成带 token 的 ping/pong。一个 PID 存活但 socket 不通、token 缺失或响应超时的 peer，会显示为 `[unreachable]`。

第四个误区是期待 `/peers` 直接发送消息或 attach 到 peer。它只输出 `uds:<socket-path>` 地址，并提示使用 `SendMessage`。如果要研究实际发送路径，应转到 `src/utils/udsClient.ts` 的 `sendToUdsSocket()` 以及调用该 helper 的工具实现，而不是继续在本目录里寻找。

第五个误区是忽略 `supportsNonInteractive: true`。这个标记说明该命令适合非交互输出，因此 `peers.ts` 返回的是 `{ type: 'text', value: ... }`，没有 Ink UI 组件、交互选择器或确认弹窗。这也是它实现保持简单的原因。
