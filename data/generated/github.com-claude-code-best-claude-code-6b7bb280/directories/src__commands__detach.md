# 目录：src/commands/detach

## 它负责什么

这个目录实现的是 CLI 里的 `/detach` 本地命令，作用是把当前会话从一个子会话中断开，或者一次性断开所有已连接的子会话。根据当前片段推断，它属于“管道式主从会话”这条功能链的一部分，因为实现里直接操作了 `pipeIpc`、`master`、`slave` 这些状态概念，并且还会向对端发送 `type: 'detach'` 的控制消息。

从职责上看，它不是一个独立业务模块，而是会话管理层的一个命令入口，主要和 `attach`、`status`、`send` 这些命令配套使用，帮助用户在主会话与子会话之间切换、解除绑定和清理连接。

## 直接子目录地图

这个目录下没有子目录，只有两个文件：

- `src/commands/detach/index.ts`：命令定义与懒加载入口
- `src/commands/detach/detach.ts`：`/detach` 的实际执行逻辑

所以这里是一个很小的命令目录，结构上是“描述文件 + 实现文件”的标准模式，没有再拆分出更细的辅助模块。

## 关键入口

真正对外暴露的是 `src/commands/detach/index.ts`。它导出一个 `Command` 对象，核心字段包括：

- `type: 'local'`：说明这是本地命令，不是远程工具调用
- `name: 'detach'`
- `description: 'Detach from a sub CLI (or all connected subs)'`
- `supportsNonInteractive: false`
- `load: () => import('./detach.js')`：按需加载实现文件

也就是说，命令系统先读到 `index.ts` 里的元信息，再在真正触发时动态加载 `detach.ts`。从目录角色上看，`index.ts` 是挂载点，`detach.ts` 才是业务入口。

## 主流程位置

主流程集中在 `src/commands/detach/detach.ts` 的 `call` 函数里。它的执行顺序很清楚：

1. 通过 `context.getAppState()` 读取当前应用状态。
2. 用 `getPipeIpc(currentState)` 判断当前是不是主模式。
   - 如果 `role === 'main'`，直接返回“未连接任何 CLI”的提示。
3. 再用 `isPipeControlled(getPipeIpc(currentState))` 判断当前子会话是否被上游 master 控制。
   - 如果是，就拒绝本地 detach，并提示“必须由 master 来 detach”。
4. 否则进入 master 模式处理：
   - 如果用户传了名字参数，就只断开指定 slave。
   - 如果没传参数，就断开所有 slave。

单个目标的流程是：

- `removeSlaveClient(targetName)` 找到并移除客户端
- `client.send({ type: 'detach' })` 通知对端
- `client.disconnect()` 关闭连接
- `context.setAppState(...)` 清理 `pipeIpc.slaves`
- 根据剩余 slave 数量，把 `role` 和 `displayRole` 切回 `master` 或 `main`

全量断开的流程则更直接：

- `getAllSlaveClients()` 拿到所有 slave
- 循环调用 `removeSlaveClient(name)`、发送 detach、断开连接
- 最后把 `pipeIpc.role`、`displayRole` 统一设为 `main`，并把 `slaves` 置空

这个文件的主流程本质上是“状态校验 -> 目标选择 -> 连接通知 -> 本地状态收尾”。

## 推荐阅读顺序

1. `src/commands/detach/index.ts`  
   先看命令元数据，确认它在命令系统里的定位。

2. `src/commands/detach/detach.ts`  
   再看真正的执行逻辑，重点理解三种分支：main、被 master 控制、master 自主 detach。

3. `src/hooks/useMasterMonitor.js`  
   这里定义了 `removeSlaveClient`、`getAllSlaveClients`，是 detach 操作的连接管理基础。

4. `src/utils/pipeTransport.js`  
   这里能补上 `getPipeIpc`、`isPipeControlled` 的语义，帮助理解角色判断从哪里来。

5. `src/commands/attach/attach.ts`、`src/commands/pipe-status/pipe-status.ts`  
   这两个位置能看到 `/detach` 在命令交互上的上下游关系。

## 常见误区

1. 把 `/detach` 当成“退出 CLI”  
   它不是退出程序，而是解除主从会话连接。主会话可能还在，子会话也可能只是被解绑。

2. 以为所有模式都能本地 detach  
   代码明确禁止在 `role === 'main'` 时执行 detach，也禁止被 master 控制的子会话自行 detach。

3. 只改连接，不改状态  
   这个命令不只是 `disconnect()`，还会同步更新 `pipeIpc.slaves`、`role`、`displayRole`，否则 UI 和实际连接会不一致。

4. 误以为“detach 一个”与“detach 全部”是两套独立逻辑  
   实际上两者共享同一个 `call` 入口，只是是否传入 `targetName` 决定了分支。

5. 忽略它和 `attach` 的配对关系  
   这个目录单独看很小，但它是 attach 后的反向操作；理解它时最好连同 attach 一起看，否则会丢掉会话生命周期的全貌。
