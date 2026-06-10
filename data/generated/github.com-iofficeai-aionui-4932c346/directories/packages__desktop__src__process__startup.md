# 子系统：packages/desktop/src/process/startup

## 解决什么问题

`packages/desktop/src/process/startup` 是桌面端 Electron 主进程启动链路中的“启动保护与故障归因”子系统。它不直接承担窗口渲染或业务功能初始化，而是围绕 `aioncore` 后端进程启动这件事，处理三个关键问题：启动前的环境兼容性检查、启动失败后的结构化分类与诊断信息收集、应用退出时的清理收束。

这个目录的价值在于把启动阶段最容易变成“只剩一条日志”的问题，拆成可测试、可上报、可给前端展示的结构化状态。例如 macOS 包架构不匹配、Linux 缺少指定 `GLIBC` 版本、打包产物缺少 `bundled-aioncore` 或运行时二进制，都不是普通的“启动失败”，而是可以被识别、分类并传给 Sentry 或 renderer 的具体原因。

## 相关目录和文件

核心目录是 `packages/desktop/src/process/startup`，当前包含 `architectureCompatibility.ts`、`backendInstallDiagnostics.ts`、`backendStartup.ts`、`backendStartupFailure.ts`、`quitCleanup.ts`。

相邻的上游入口主要在 `packages/desktop/src/process/index.ts`。它是 Electron 主进程的启动编排位置，通常会调用后端启动、窗口创建、IPC bridge 初始化、退出处理等逻辑。`packages/desktop/src/process/backend/index.ts` 与 `packages/desktop/src/process/backend/binaryResolver.ts` 负责解析和启动 `aioncore` 二进制，启动失败时会把 `details` 附在错误对象上，供 `startup` 目录分类。

下游展示和桥接相关代码在 `packages/desktop/src/preload/main.ts`、`packages/desktop/src/renderer`。从已有片段可见，preload 会同步读取 `get-backend-startup-failed` 和 `get-backend-startup-failure`，说明启动失败信息会穿过 IPC 暴露给渲染进程。`packages/desktop/src/sentry.ts` 会读取失败分类和诊断上下文，为 Sentry 打 tag、context 和 extra。

类型定义来自 `packages/desktop/src/common/types/platform/electron`，其中的 `BackendStartupFailureInfo` 是 `backendStartupFailure.ts` 输出的公共结构。

## 核心对象

`StartupArchitectureMismatchError` 是 macOS 架构校验失败时抛出的专用错误。它的 `details.stage` 固定为 `startup_architecture_check`，并携带 `packageArch`、`deviceArch`、`expectedDownloadArch`、`isRosettaTranslated` 等字段。`detectStartupArchitectureMismatch` 通过 `process.platform`、`process.arch`、`isPackaged` 以及 `sysctl` 结果判断是否在 Apple Silicon 设备上运行了 x64 打包产物。`assertStartupArchitectureCompatible` 是更适合启动链路直接调用的包装函数。

`collectBackendInstallDiagnostics` 负责生成 `BackendInstallDiagnostics`。它根据错误 `details` 和运行环境，收集 `resourcesPath`、`runtimeKey`、`binaryName`、`bundled-aioncore` 路径、runtime 目录、二进制文件、`manifest.json` 的存在性、大小、mtime 和 manifest 字段。这个对象用于回答“安装包里到底缺了什么、文件是否存在、manifest 是否能解析”。

`startBackendOrExit` 是后端启动的控制器。它接收 `startBackend`、`onStarted`、`captureFailure`、`exitApp` 等回调，成功时返回 `{ ok: true, port }`，失败时记录错误、捕获故障并默认以退出码 `1` 结束应用。特殊的 `BackendStartupCancelledError` 会被视为取消启动，不进入致命失败流程。

`classifyBackendStartupFailure` 是失败归因入口。它会优先识别 `startup_architecture_check`，其次识别 packaged app 中 `bundled-aioncore/`、runtime 目录、`managed-resources/` 或后端二进制缺失，再从错误文本中提取 `GLIBC_x.y not found`，最后才回落为通用 `backend_startup_failed`。

`quitCleanup.ts` 根据当前片段只能推断为退出清理编排模块。依据是文件名、所在目录，以及输出中出现的 `pet not initialized` 注释。它大概率负责在 Electron 退出阶段收束后端进程、pet 相关资源或持久化任务，避免主进程退出时留下后台进程或未完成状态。

## 运行流程

主进程启动后，首先会完成 Electron 基础配置和环境准备。进入后端启动阶段前，启动链路会执行架构兼容性检查。对于 packaged macOS x64 包，如果运行环境实际是 arm64 或 Rosetta 场景，会抛出 `StartupArchitectureMismatchError`，后续被分类为 `backend_package_architecture_mismatch`。

随后启动链路调用 `startBackendOrExit`。它通过传入的 `startBackend` 启动 `aioncore`，拿到端口后调用 `onStarted(port)`，供后续 bridge、renderer 或 WebUI 配置使用。如果启动失败，`startBackendOrExit` 会调用 `captureFailure(error)`。这个捕获流程通常会组合 `classifyBackendStartupFailure` 与 `collectBackendInstallDiagnostics`：前者产出面向业务的失败原因，后者补充面向排障的安装包状态。

如果失败不是取消启动，并且 `exitOnFailure` 没有显式关闭，应用会调用 `exitApp(1)` 结束。这表明 `aioncore` 对桌面端是强依赖：主进程不会在后端不可用的情况下继续作为完整应用运行。失败状态则可通过 preload 暴露给 renderer，用于展示错误页或引导用户处理。

退出阶段由 `quitCleanup.ts` 参与清理。根据当前片段推断，它与 `packages/desktop/src/process/utils/persistOnQuit.ts`、pet 子系统和后端进程生命周期有关，目标是让退出顺序可控且幂等。

## 上下游依赖

上游依赖主要来自 Node.js 和 Electron 主进程环境。`architectureCompatibility.ts` 使用 `node:child_process` 的 `execFileSync` 调用 `sysctl`；`backendInstallDiagnostics.ts` 使用 `node:fs` 和 `node:path` 读取打包资源状态。由于该目录位于 `packages/desktop/src/process`，不能依赖 DOM 或 renderer API。

它依赖 `packages/desktop/src/process/backend` 提供真实启动与错误 details。尤其是 `binaryResolver.ts` 需要在错误中提供 `stage: 'resolve_binary'`、`isPackaged`、`resourcesDirEntries`、`runtimeDirEntries`、`runtimeKey`、`binaryName` 等字段，否则 `classifyBackendStartupFailure` 无法识别不完整安装。

下游依赖包括 `packages/desktop/src/sentry.ts`、`packages/desktop/src/preload/main.ts` 和 renderer 错误展示逻辑。Sentry 会将分类结果映射为 tag，例如包架构、缺失资源、GLIBC 版本、backend boundary code 等；preload 则把失败状态桥接给前端。

## 修改时最容易踩的坑

第一，不要把所有启动失败都吞成普通 `Error.message`。这个目录依赖 `error.details.stage` 做分类，新增后端启动阶段时应同步设计稳定的 `stage` 和字段名。

第二，`classifyBackendStartupFailure` 的判断顺序很重要。架构不匹配和安装包不完整比通用运行时错误更具体，应优先返回；否则 Sentry 和前端都会看到低价值的 `backend_startup_failed`。

第三，`collectBackendInstallDiagnostics` 会读取真实文件状态。修改路径拼接时必须注意 Windows 使用 `path.win32`、其他平台使用 `path.posix`，不能简单硬编码 `/` 或 `\`。

第四，macOS 架构检查只应在 packaged app 中启用。开发环境、非 darwin 平台、非 x64 包都应直接返回兼容，否则会影响本地开发和 CI。

第五，退出清理应保持幂等。Electron 退出事件、后端进程退出、pet 子系统未初始化等情况可能交错出现，清理函数不能假设所有资源都已成功创建。

## 推荐阅读顺序

先读 `packages/desktop/src/process/index.ts`，了解主进程启动总线在哪里调用后端、窗口、bridge 和退出逻辑。

再读 `packages/desktop/src/process/startup/backendStartup.ts`，掌握启动成功、失败、取消和退出的主控制流。

随后读 `packages/desktop/src/process/backend/index.ts` 与 `packages/desktop/src/process/backend/binaryResolver.ts`，理解 `aioncore` 如何解析、启动，以及失败 details 从哪里来。

接着读 `packages/desktop/src/process/startup/backendStartupFailure.ts` 和 `packages/desktop/src/process/startup/backendInstallDiagnostics.ts`，把“错误分类”和“安装诊断”对应起来。

最后读 `packages/desktop/src/process/startup/architectureCompatibility.ts`、`packages/desktop/src/process/startup/quitCleanup.ts`、`packages/desktop/src/sentry.ts`、`packages/desktop/src/preload/main.ts`，分别补齐启动前保护、退出收束、上报和前端可见状态。
