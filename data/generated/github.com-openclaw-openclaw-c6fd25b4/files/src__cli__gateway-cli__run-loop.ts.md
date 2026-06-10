# 文件：src/cli/gateway-cli/run-loop.ts

## 一句话定位

`src/cli/gateway-cli/run-loop.ts` 是 gateway CLI 的进程生命周期主循环：它负责持有 gateway 单实例锁、启动 `startGatewayServer`、监听进程信号，并在停止、普通重启、更新后重启之间选择合适的关停和拉起策略。

## 它暴露/定义了什么

这个文件对外主要暴露 `runGatewayLoop(params)`。调用方传入 `start`、`runtime`、可选 `lockPort`、`healthHost` 和测试用的 `waitForHealthyChild`，它会把一次 gateway 启动包装成长期运行的生命周期循环。

文件内部还定义了几类辅助能力：

`GatewayRunSignalRequest`、`GatewayRunSignalAction`、`RestartIntentOptions` 描述停止或重启请求的意图；`createRestartIterationHook` 用来区分首次启动和后续重启迭代；`waitForGatewayPortReady`、`waitForHealthyGatewayChild` 用 TCP 连接探测子进程是否已经接管端口；若干超时常量控制 drain、shutdown、supervisor handoff 和 update respawn 的等待预算。

## 谁调用它

直接调用点在 `src/cli/gateway-cli/run.ts`。从符号搜索看，`run.ts` 在普通 gateway 启动路径里调用 `runGatewayLoop`，并且还有 `runGatewayLoopWithSupervisedLockRecovery` 这样的外层包装，用于 supervisor 管理场景下的锁恢复。测试覆盖集中在 `src/cli/gateway-cli/run-loop.test.ts`，另有 `src/cli/gateway-cli/run.option-collisions.test.ts` 通过 mock 验证 CLI 参数路径会正确进入该循环。

因此它不是用户直接调用的 API，而是 `openclaw gateway` 类命令启动后进入的底层守护循环。

## 它调用谁

它首先调用 `acquireGatewayLock` 获取 gateway 单实例锁，防止同一端口或同一运行环境下重复启动。实际服务启动通过调用方注入的 `start` 完成，类型上对应 `src/gateway/server.ts` 的 `startGatewayServer` 返回值。

重启相关能力通过 `createLazyImportLoader` 延迟加载 `src/cli/gateway-cli/lifecycle.runtime.ts`，其中包括 `respawnGatewayProcessForUpdate`、`restartGatewayProcessWithFreshPid`、`detectRespawnSupervisor`、`writeGatewayRestartHandoffSync`、`markGatewayDraining`、`waitForActiveTasks`、`waitForActiveEmbeddedRuns`、`abortEmbeddedPiRun` 等生命周期和运行中任务管理函数。它还调用 `src/gateway/restart-trace.ts` 里的 trace/handoff 工具记录重启路径，调用 `clearRuntimeConfigSnapshot` 清理运行时配置快照，并用 `createSubsystemLogger("gateway")` 输出 gateway 子系统日志。

## 核心流程

`runGatewayLoop` 进入后会先 eagerly 加载 `lifecycle.runtime.ts`。源码注释说明这是为了避免 in-place package upgrade 后磁盘上的动态 import chunk 名称变化，导致后续 `SIGUSR1` 重启路径加载失败；也就是说，这里把生命周期运行时代码提前拉进内存，是更新重启可靠性的一部分。

随后它获取 gateway lock，初始化运行状态，包括当前 server handle、是否正在关闭、待处理启动期信号、restart resolver、进程实例 ID 等。主循环会调用 `start` 启动 gateway server，并在每轮运行中等待停止或重启信号。根据当前片段推断，文件下半部分安装 `SIGTERM`、`SIGINT`、`SIGUSR1` 处理器：`SIGINT`/`SIGTERM` 更偏停止，`SIGUSR1` 驱动重启；如果信号发生在 server 已报告 ready 但 `start` 尚未返回 close handle 的窗口，会先排队到 `pendingStartupRequest`，避免没有 close handle 时无法有序关停。

收到重启请求后，它先进入 drain 阶段：标记 gateway 正在重启、拒绝新任务入队，然后等待 active tasks 和 embedded runs 结束。普通重启会按配置或请求中的 `waitMs` 等待；`force` 重启会跳过等待并标记相关主会话为 restart aborted。drain 超时后，它会记录警告、标记受影响 session，并尽力 abort embedded runs。

server close 完成后，它根据重启原因选择路径。`restartReason === "update.run"` 时优先尝试 update respawn：如果能 spawn 新子进程并且健康探测成功，当前进程退出；如果由 supervisor 接管，则写 handoff 信息并退出；失败时回落到进程内重启。普通重启则优先尝试 fresh PID full-process restart，同样支持 spawned、supervised 和 failed fallback。最终 fallback 是重新获取 lock，清除 shutdown 状态，唤醒循环进入下一轮 `start`。

## 关键函数的高层作用

`runGatewayLoop` 是核心入口，职责是把“启动一次 gateway server”提升为“可被信号控制、可 drain、可 supervisor/update handoff、可回退到进程内重启”的长期运行循环。

`handleRestartAfterServerClose` 负责 server 已关闭之后的重启决策。它先释放 lock，再判断是 `update.run` 还是普通重启；能交给新进程或 supervisor 就退出当前进程，不能则重新获取 lock 并在本进程内启动下一轮。

`runAcceptedRequest` 负责执行已接受的 stop/restart 请求。它设置 watchdog 超时，重启时等待活动任务和 embedded runs drain，随后调用 `server.close`，最后分派到 stop 或 restart 的后续处理。

`resolveRestartDrainTimeoutMs` 统一计算重启 drain 预算：强制重启为 `0`，显式 `waitMs` 优先，否则读取 runtime config 中 gateway reload 的 deferral timeout，失败时使用默认值。

`waitForHealthyGatewayChild` 和 `waitForGatewayPortReady` 是 update respawn 的健康探测辅助函数，只验证新进程是否在指定 host/port 上可连接。

`createRestartIterationHook` 只是一个迭代标记工具，用于首次启动不触发 restart hook，后续轮次才执行传入的 `onRestart`。

## 修改风险

这个文件处在 CLI、gateway server、进程信号、supervisor、更新机制和运行中 agent 任务之间，修改风险很高。最敏感的是锁释放和重新获取顺序：如果 release lock、spawn child、health check、fallback reacquire 的顺序出错，可能导致双 gateway、端口抢占失败，或更新后 gateway 不再可用。

第二类风险是 drain 语义。`markGatewayDraining`、`waitForActiveTasks`、`waitForActiveEmbeddedRuns`、`markRestartAbortedMainSessions`、`abortEmbeddedPiRun` 共同保证重启时不静默丢任务、不跨生命周期持有 session 写锁。改变 timeout、force、close drain 的逻辑，可能让用户正在运行的任务丢消息、重复恢复，或让 restart 永久卡住。

第三类风险是动态 import 和打包边界。文件开头特意 eager load `lifecycle.runtime.ts`，说明这里曾经受过升级后 chunk 旋转影响。把相关 import 改回普通懒加载、合并到不稳定模块、或引入静态/动态混用，都可能破坏 update.run 自重启路径。

第四类风险是 supervisor 行为。`launchd` 等 supervisor 有自己的 stop budget 和 crash-loop 策略，文件中保留了退出延迟、handoff 文件、非零超时退出等细节。随意调整 exit code、延迟或 handoff 写入，会影响 macOS/系统服务安装的自动恢复行为。

修改这里时应至少覆盖 `src/cli/gateway-cli/run-loop.test.ts` 中与信号、startup window、drain、update respawn、supervised restart、timeout fallback 相关的用例；涉及真实进程拉起、端口健康探测或安装后更新时，还需要额外做端到端验证。
