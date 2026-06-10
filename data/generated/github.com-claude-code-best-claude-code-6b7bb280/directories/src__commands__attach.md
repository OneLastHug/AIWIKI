# 目录：src/commands/attach

## 它负责什么

`src/commands/attach` 负责实现 CLI 里的 `/attach` 这类本地命令，用来把当前 Claude CLI 会话接到一个已有的子会话 pipe 上。根据当前片段推断，它属于“主控 / 子会话”这套 pipe 协作机制的一部分，核心目标不是启动新会话，而是把当前实例切换成 master，并开始监控指定的 sub session。

这个目录对应的能力很明确：接入已有 pipe、发送 attach 请求、等待对端接受或拒绝、把结果写回 `AppState`，并把连接登记到模块级监控结构里。它还带有一些前置约束，比如只能在支持 `UDS_INBOX` 的功能路径下加载，且非交互场景不支持。

## 直接子目录地图

这个目录下面没有再往下的子目录，只有两个直接文件：

- `src/commands/attach/index.ts`：命令元数据与懒加载入口
- `src/commands/attach/attach.ts`：真正的 `/attach` 执行逻辑

也就是说，这里是一个很薄的命令封装目录，没有按职责继续拆分成子层级。根据当前片段推断，所有 attach 行为都收束在这两个文件里。

## 关键入口

最外层入口是 `src/commands/attach/index.ts`。它导出一个 `Command` 对象，声明：

- `type: 'local'`
- `name: 'attach'`
- `description: 'Attach to a sub Claude CLI instance via named pipe'`
- `supportsNonInteractive: false`
- `load: () => import('./attach.js')`

这说明它不是常驻功能，而是按需加载的本地命令；真正执行时才动态导入 `attach.ts` 对应的实现。

第二个入口是 `src/commands/attach/attach.ts` 里的 `call` 函数。它接收命令参数和上下文，是 `/attach` 的实际处理点。

在全局注册层，`src/commands.ts` 里 `attachCmd` 只在 `feature('UDS_INBOX')` 打开时才会被装配，并且最终通过命令列表展开进主 CLI。换句话说，`attach` 不是始终可用的基础命令，而是受特性开关控制的子系统能力。

## 主流程位置

主流程基本都在 `src/commands/attach/attach.ts` 的 `call` 中，顺序很清楚：

1. 解析目标 pipe 名称，空参数直接返回用法提示。
2. 从 `context.getAppState()` 取当前状态。
3. 检查是否已经附着到同名 slave，避免重复 attach。
4. 检查当前实例是否已经被 master 控制；如果是，就拒绝继续 attach。
5. 在 `feature('LAN_PIPES')` 打开时，尝试从 `discoveredPipes` 和 `lanBeacon` 推断 TCP 端点。
6. 通过 `connectToPipe(...)` 连接目标 pipe，失败则返回错误文本。
7. 发送 `attach_request`，并设置 5 秒超时等待响应。
8. 收到 `attach_accept` 后：
   - 调 `addSlaveClient(targetName, client)` 注册连接
   - 更新 `AppState`，把自身角色切到 `master`
   - 在 `slaves` 里新增一条会话记录
   - 返回“已附着并开始监控”的说明
9. 收到 `attach_reject` 后断开连接并返回拒绝原因。

这里的关键依赖是 `pipeTransport` 和 `useMasterMonitor`。前者负责真正的 pipe 通信，后者负责把 slave client 放进模块级监控表里，让后续 `/send`、`/status`、`/detach` 之类命令能继续工作。

## 推荐阅读顺序

如果你要快速建立这个目录的 ذهن模型，建议按这个顺序看：

1. `src/commands.ts` 里 `attachCmd` 的注册位置，先确认它如何进入主命令表。
2. `src/commands/attach/index.ts`，看它的命令元信息和懒加载方式。
3. `src/commands/attach/attach.ts`，这是核心流程，重点看状态检查、连接、响应处理。
4. `src/utils/pipeTransport.ts`，理解 `connectToPipe`、`PipeClient`、`PipeMessage` 的通信语义。
5. `src/hooks/useMasterMonitor.ts`，理解 `addSlaveClient` 之后连接如何被纳入监控体系。
6. 如果要看整套协作命令，再对照 `src/commands/detach`、`src/commands/send`、`src/commands/pipes`、`src/commands/pipe-status`。

## 常见误区

第一，`attach` 不是“创建一个新子会话”，而是“连接到已有 pipe”。它前提是目标已经存在，并且能完成握手。

第二，它不是无条件可用的。`src/commands.ts` 里明确用 `feature('UDS_INBOX')` 包住了加载逻辑，所以这个目录的功能属于特性开关控制区，不是基础路径。

第三，它也不是纯 CLI 文本命令。`supportsNonInteractive: false` 说明它依赖交互式运行环境，和后台批处理路径不是一回事。

第四，attach 成功后会改变当前会话的角色状态。它不是单次请求就结束的“连接动作”，而是把当前实例纳入 master 监控状态，后续 `/send`、`/status`、`/detach` 都会依赖这次状态切换。

第五，`LAN_PIPES` 只是附加分支，不是主路径。根据当前片段推断，默认 attach 更偏向本地命名 pipe；只有特性打开且发现到 LAN peer 时，才会尝试走 TCP 端点。
