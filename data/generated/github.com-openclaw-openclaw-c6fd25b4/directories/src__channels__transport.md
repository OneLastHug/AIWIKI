# 子系统：src/channels/transport

## 解决什么问题

`src/channels/transport` 是 `src/channels/**` 下的通道传输辅助层。根据当前片段，它目前只承担一个明确职责：为长时间运行的 channel transport 操作提供“可武装”的停滞检测器，避免传输层已经没有活动却仍然无限等待。

这里的核心不是消息解析、路由、插件注册或具体平台适配，而是一个很小的生命周期工具：调用方在开始等待传输活动时 `arm()`，收到进展时 `touch()`，暂时不需要监控时 `disarm()`，结束或取消时 `stop()`。如果已武装状态下超过 `timeoutMs` 没有活动，它会记录运行时错误并触发 `onTimeout` 回调，让上层决定如何中断、重连、失败或清理。

从 `src/channels/AGENTS.md` 的边界说明看，`src/channels/**` 属于核心 channel 实现，插件作者不应直接导入。因此这个目录服务的是 OpenClaw 内部 channel runtime，而不是 plugin SDK 的公开 API。

## 相关目录和文件

`src/channels/transport/stall-watchdog.ts` 是当前目录的主体，实现 `createArmableStallWatchdog`、`ArmableStallWatchdog` 和超时元数据类型 `StallWatchdogTimeoutMeta`。

`src/channels/transport/stall-watchdog.test.ts` 是对应 Vitest 行为测试，覆盖已武装后超时触发、解除武装后不触发、`touch()` 延长空闲窗口这三类基本语义。

邻近上下文主要是 `src/channels/AGENTS.md`。它定义了 channel 层边界：`src/channels/**` 是核心实现；扩展或第三方 channel 需要通过 `openclaw/plugin-sdk/*`、typed SDK contract 或 facade 暴露能力；channel hot path 要避免静态拉入重型 async runtime。`transport` 目录的实现很轻量，只依赖 timer、`AbortSignal` 和 `RuntimeEnv` 类型，符合这种边界定位。

## 核心对象

`createArmableStallWatchdog(params)` 是工厂函数。参数包括 `label`、`timeoutMs`、可选 `checkIntervalMs`、可选 `abortSignal`、可选 `runtime`，以及必需的 `onTimeout(meta)`。

`ArmableStallWatchdog` 是返回给调用方的控制句柄，包含 `arm()`、`touch()`、`disarm()`、`stop()`、`isArmed()`。它把“是否正在监控”和“最后一次活动时间”封装起来，调用方不需要直接管理 interval。

`StallWatchdogTimeoutMeta` 是超时事件的最小信息载体，包含 `idleMs` 和 `timeoutMs`。这让上层可以基于实际空闲时长和阈值做日志、错误消息或诊断。

`RuntimeEnv` 只作为可选日志入口使用。超时时如果传入 `runtime.error`，watchdog 会输出带 `label` 的错误信息；没有 runtime 时仍然会调用 `onTimeout`，所以日志不是功能前提。

## 运行流程

创建时，函数会把 `timeoutMs` 向下取整并保证至少为 `1`。`checkIntervalMs` 如果未传入，会根据 timeout 自动计算，默认取 `timeoutMs / 6` 的附近值，并限制在至少 `100ms`、通常不超过 `5000ms` 的区间。这样短超时不会完全失去精度，长超时也不会频繁轮询。

实例创建后会启动一个 `setInterval(check, checkIntervalMs)`。如果运行在 Node 环境，timer 会调用 `unref()`，避免仅因 watchdog timer 存在而阻止进程退出。

初始状态下 `armed=false`。调用 `arm(atMs?)` 会记录最后活动时间并进入已武装状态。调用 `touch(atMs?)` 只刷新最后活动时间，不改变是否已武装。`disarm()` 关闭监控但不销毁 timer。`stop()` 是最终清理：标记 stopped、解除武装、清掉 interval，并移除 `abortSignal` 监听。

每次 interval tick 执行 `check()`：如果未武装或已停止，直接返回；否则计算 `Date.now() - lastActivityAt`。当 `idleMs >= timeoutMs` 时，watchdog 会先 `disarm()`，再写 runtime 错误日志，最后调用 `onTimeout({ idleMs, timeoutMs })`。先解除武装意味着同一次停滞只触发一次，除非上层再次显式 `arm()`。

如果传入的 `abortSignal` 已经是 aborted，创建阶段会立即 `stop()`；否则会注册一次性 abort listener，使外部取消能同步停止 watchdog。

## 上下游依赖

上游调用方根据当前片段无法精确定位；目录内没有引用搜索结果，且本任务未展开全仓库调用链。因此只能根据命名和 `src/channels` 边界推断：它应被 channel transport、stream、send/receive loop 或长连接读取流程调用，用来检测“等待传输进展但长时间没有 activity”的状态。

下游依赖很少。源码只导入 `src/runtime.js` 的 `RuntimeEnv` 类型，运行时使用标准 `Date.now()`、`setInterval()`、`clearInterval()`、`AbortSignal`。测试依赖 `vitest` 的 fake timers，证明该对象设计为纯时间状态机，适合在 channel 层复用，而不是绑定具体平台、插件或网络库。

## 修改时最容易踩的坑

第一，`touch()` 不会自动 `arm()`。这很重要：调用方如果只刷新活动时间但从未武装，watchdog 不会触发超时。修改语义前要确认所有上游调用是否依赖这种显式状态机。

第二，超时后会自动 `disarm()`。如果想在一次超时后继续监控，必须由上层重新 `arm()`。不要在 `onTimeout` 内假设 watchdog 仍处于 armed 状态。

第三，`stop()` 必须保持幂等。它可能由正常结束、外部 abort、错误清理等路径重复调用。当前实现用 `stopped` 防重入，并清理 interval 和 abort listener。

第四，timer 使用 `unref()` 是 Node 进程生命周期细节。删除它可能导致后台 watchdog 让 CLI 或测试进程无法自然退出。

第五，`checkIntervalMs` 不是超时时间本身。实际触发点取决于 interval tick，因此测试和用户可见诊断应允许一定调度误差。当前测试用 fake timers 验证行为窗口，而不是依赖真实时间。

第六，`runtime.error` 是可选链。不要把日志成功当成超时处理成功；真正的行为入口是 `onTimeout`。

## 推荐阅读顺序

1. 先读 `src/channels/AGENTS.md`，理解 channel 树的边界：这里是核心实现，不是插件公开 API。
2. 再读 `src/channels/transport/stall-watchdog.ts`，重点看 `createArmableStallWatchdog` 的参数、内部状态和 `check()`。
3. 接着读 `src/channels/transport/stall-watchdog.test.ts`，用三条测试确认 `arm()`、`disarm()`、`touch()` 的行为差异。
4. 如果继续追上下游，再在 `src/channels/**` 内搜索 `createArmableStallWatchdog` 或 `ArmableStallWatchdog`，从具体调用点理解它保护的是哪类 transport 等待流程。
