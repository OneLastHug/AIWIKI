# 目录：src/commands/claim-main

## 它负责什么

`src/commands/claim-main` 是一个很小但职责明确的本地命令目录，负责把“当前这台机器”提升为 pipe 体系里的 main 角色。它属于命令层的一个操作入口，不负责网络发现、pipe 列表展示，也不负责子机广播逻辑本身；它做的事情更像是一次主机身份切换和本地状态同步。

根据当前片段推断，这个目录的设计目标是配合 `pipes` 相关命令使用：先通过 `claim-main` 把本机登记为主机，再让既有的 sub 绑定到这台实例上。它输出的是纯文本结果，适合终端交互和脚本式执行结果查看。

## 直接子目录地图

这个目录下面没有更深层的子目录，只有两个文件：

- `src/commands/claim-main/index.ts`：命令定义与懒加载入口
- `src/commands/claim-main/claim-main.ts`：真正执行命令的处理逻辑

从结构上看，这是典型的“一个目录对应一个 local command”的组织方式，`index.ts` 只负责把命令挂进统一命令系统，业务流程放在同名实现文件里。目录本身没有工具类、子模块或额外拆分层级，所以阅读成本很低，属于薄封装命令目录。

## 关键入口

最关键的入口是 `src/commands/claim-main/index.ts`。它导出一个 `Command` 配置对象，核心字段有：

- `type: 'local'`：说明这是本地命令，不是远程或非交互式流水线命令
- `name: 'claim-main'`：命令名
- `description`：说明其用途是为当前机器抢占 main 角色
- `supportsNonInteractive: false`：明确禁止非交互模式
- `load: () => import('./claim-main.js')`：使用动态导入加载实现

真正的执行入口在 `src/commands/claim-main/claim-main.ts` 里的 `call: LocalCommandCall`。也就是说，命令系统先读 `index.ts`，再在需要时加载实现文件并执行 `call`。

另外，`src/commands/pipes/pipes.ts` 里有帮助文案把 `/claim-main` 暴露给用户，说明它是 `pipes` 交互命令集合的一部分，而不是孤立功能。

## 主流程位置

主流程几乎都集中在 `src/commands/claim-main/claim-main.ts`，顺序很清楚：

1. 从 `context.getAppState()` 取当前应用状态。
2. 通过 `getPipeIpc(currentState)` 取 pipe IPC 状态。
3. 读取 `serverName`，如果 pipe server 没启动，就直接返回错误文本。
4. 调用 `getMachineId()` 和 `readRegistry()`，拿到本机机器 ID 和 registry。
5. 如果 registry 里已经记录“当前机器就是 main”，并且 `main.id` 也匹配当前 serverName，就直接提示无需变更。
6. 否则组装一条主机 entry，包含 `id`、`pid`、`machineId`、`startedAt`、`ip`、`mac`、`hostname`、`pipeName`。
7. 调用 `claimMain(machineId, entry)`，把 registry 中的 main 切换到本机。
8. 更新本地 `appState.pipeIpc`，把 `role` 和 `displayRole` 设为 `main`，并清空 `subIndex`、`attachedBy`。
9. 拼出结果文本，提示主角色已成功 claim，并显示旧 main 的机器 ID 前缀。

这里的关键依赖都来自相邻基础设施层：`pipeTransport.ts` 提供 IPC 和本地 IP 读取，`pipeRegistry.ts` 提供机器身份和 registry 读写。`claim-main` 本身不实现这些底层机制，只负责调用它们并收敛成一条命令流程。

## 推荐阅读顺序

1. 先看 `src/commands/claim-main/index.ts`，确认它在命令系统里的定位。
2. 再看 `src/commands/claim-main/claim-main.ts`，理解实际的 claim 逻辑和状态更新。
3. 接着对照 `src/commands/pipes/pipes.ts` 中 `/claim-main` 的帮助文案，理解它在用户可见命令集合中的位置。
4. 如果要继续追根到底，再看 `src/utils/pipeRegistry.ts` 和 `src/utils/pipeTransport.ts`，补齐 registry 与 IPC 的底层语义。

## 常见误区

- 这不是一个可非交互执行的命令。`supportsNonInteractive: false` 已经说明它依赖当前会话状态。
- 它不是“创建 main”那么简单，而是“抢占 main 角色并重写 registry 记录”。如果已有主机，它会替换旧主机。
- 它不会单独处理所有子机生命周期，真正的子机绑定关系是通过 registry 和本地 state 间接生效的。
- 如果 `serverName` 为空，说明 pipe server 根本没起来，此时命令不会继续执行。
- 它的输出是文本状态反馈，不是结构化对象或 UI 组件，因此适合终端提示和简单脚本消费。
- 目录虽小，但不要忽略它对 `pipeIpc.role`、`displayRole` 和 `machineId` 的本地同步，这一步决定了当前实例在后续 pipes 流程里的身份。
