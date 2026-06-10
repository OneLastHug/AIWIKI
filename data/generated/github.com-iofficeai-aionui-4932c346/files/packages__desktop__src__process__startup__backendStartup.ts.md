# 文件：packages/desktop/src/process/startup/backendStartup.ts

## 一句话定位

`packages/desktop/src/process/startup/backendStartup.ts` 是 Electron 主进程启动链路里的“后端启动保护壳”：它不直接知道 `aioncore` 怎么启动，而是把调用方传入的 `startBackend` 包装成统一的成功返回、失败上报、可选退出应用流程。

## 它暴露/定义了什么

这个文件主要定义并导出一个函数：`startBackendOrExit(options)`。

它还定义了两个内部类型：

`BackendStartupResult` 表示启动结果，成功时是 `{ ok: true; port: number }`，失败或取消时是 `{ ok: false }`。调用方不需要捕获异常，而是根据 `ok` 判断是否继续后续启动流程。

`StartBackendOrExitOptions` 描述调用方必须注入的依赖，包括 `startBackend`、`onStarted`、`captureFailure`、`exitApp`，以及可选的 `exitOnFailure`、`logError`。这种设计让该文件不直接依赖 Electron 的 `app`、Sentry、`BackendLifecycleManager` 或具体日志实现。

内部还有一个辅助函数 `isBackendStartupCancelledError(error)`，只通过 `error.name === 'BackendStartupCancelledError'` 判断取消类错误。

## 谁调用它

当前片段中明确调用它的是 `packages/desktop/src/index.ts`。主入口在 `handleAppReady` / 初始化流程中先执行 `initializeProcess()`，再调用 `startBackendOrExit` 启动后端。调用点传入的 `startBackend` 会进行架构兼容性检查，动态导入路径工具与存储目录工具，然后调用 `backendManager.start(...)`。

`packages/desktop/src/index.ts` 还根据返回值处理后续逻辑：如果 `backendStartup.ok` 为 `false`，在 WebUI 模式或重置密码模式下会直接停止继续启动；普通模式下则允许继续走后续路径，配合渲染端展示启动失败信息。根据当前片段推断，这个函数是应用启动阶段后端失败分流的中心入口，依据是 `preload` 和 `renderer` 会读取 `backendStartupFailed` / `backendStartupFailure` 并展示对应错误界面。

## 它调用谁

`backendStartup.ts` 本身只调用调用方注入的函数，不直接 import 业务模块。核心调用顺序是：

先调用 `options.startBackend()` 获取后端端口；成功后调用 `options.onStarted(port)`；失败时根据错误类型决定是否吞掉、记录、上报和退出。

在 `packages/desktop/src/index.ts` 的实际注入中，这些回调分别会间接触达：

`BackendLifecycleManager.start(...)`，负责真正启动 `aioncore` 后端子进程。

`assertStartupArchitectureCompatible(...)`，用于在启动前检查运行架构是否兼容。

`markBackendStartupFailed(...)`、`classifyBackendStartupFailure(...)`、`captureBackendStartupFailure(...)`，用于标记失败状态、分类失败原因并上报诊断。

`app.exit(code)`，用于在特定模式或默认策略下终止 Electron 应用。

`exposeBackendPort(...)`、`markBackendReady(...)`，用于把后端端口和 ready 状态暴露给后续主进程、preload、renderer 逻辑。

## 核心流程

成功路径很短：`startBackendOrExit` 等待 `options.startBackend()` 完成，拿到 `port` 后立即执行 `options.onStarted(port)`，最后返回 `{ ok: true, port }`。这意味着它把“后端启动成功”和“端口已通知外部系统”绑定在同一个成功结果里。

失败路径分三类。

第一类是 `BackendStartupCancelledError`。这类错误被视为主动取消或可预期中止，不记录错误、不上报、不退出，只返回 `{ ok: false }`。这里没有直接 import 错误类，而是用 `name` 字符串判断，说明它刻意降低了与错误定义来源的耦合。

第二类是普通启动失败。函数会调用可选的 `logError` 输出 `"[AionUi] Failed to start aioncore:"`，随后等待 `captureFailure(error)` 完成。这个等待很关键：如果后续要退出应用，诊断采集有机会先落盘或上报。

第三类是是否退出应用。`exitOnFailure` 默认为 `true`，即调用方不传时失败会执行 `exitApp(1)`。在实际主入口里，`exitOnFailure` 被设置为 `isWebUIMode || isResetPasswordMode`，表示某些专用模式启动后端失败时必须退出，而普通桌面模式可以继续启动到错误提示界面。

## 关键函数的高层作用

`startBackendOrExit` 是核心函数。它的职责不是“启动后端的所有细节”，而是规定启动后端这一阶段的控制协议：成功时必须返回端口并执行成功回调，失败时必须区分取消、捕获诊断、按策略退出，并且始终用 `BackendStartupResult` 告诉上层是否能继续。

`isBackendStartupCancelledError` 是辅助判断函数。它只识别一种特殊错误名，用来避免把用户取消、流程取消或 pending 启动中止当成真实故障处理。

## 修改风险

最大风险是改变失败语义。`exitOnFailure` 当前默认是 `true`，但主入口会显式传入模式相关布尔值；如果改成默认不退出，可能导致某些必须终止的模式继续运行在半初始化状态。如果强制总是退出，则普通桌面模式可能无法进入后端启动失败提示界面。

第二个风险是调整 `BackendStartupCancelledError` 的判断方式。现在使用 `error.name` 而不是 `instanceof SomeImportedClass`，可能是为了跨模块、跨包或动态导入边界下仍能识别取消错误。如果改成严格类判断，可能导致取消被误判为普通失败，从而触发上报和退出。

第三个风险是移除或不等待 `captureFailure`。后端启动失败通常是安装不完整、运行时架构不兼容、子进程启动失败等关键问题；如果退出前不等待采集，`renderer` 错误展示、Sentry 诊断或启动日志可能缺失。

第四个风险是让该文件直接依赖 Electron、Sentry 或 `BackendLifecycleManager`。目前它通过依赖注入保持很薄，容易测试，也避免主进程启动模块之间出现更复杂的 import 顺序问题。扩展时应优先保持这种“只编排，不拥有具体实现”的边界。
