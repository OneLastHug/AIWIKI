# 目录：packages/desktop/src/common/platform

## 它负责什么

`packages/desktop/src/common/platform` 是桌面端公共层里的“运行时平台服务抽象层”。它把一些只在特定运行环境中存在的能力统一收口成 `IPlatformServices`，让上层代码不必直接依赖 `electron.app`、`electron.utilityProcess`、`powerSaveBlocker`、`Notification`、`net.fetch` 或 Node.js 的 `child_process.fork`、`os`、`fetch` 等具体实现。

这个目录解决的核心问题是：同一批 common / process 代码既可能运行在 Electron 主进程里，也可能运行在 Electron utility process 或较纯粹的 Node.js 环境里。平台相关 API 如果散落在业务代码中，会导致调用顺序、打包顺序、运行时能力差异都变得难以控制。这里通过 `getPlatformServices()` 提供统一入口，通过 `registerPlatformServices()` 在 Electron 主进程启动时注入真实实现。

从职责上看，它主要覆盖五类能力：路径与应用元信息、子进程/utility process 创建、系统休眠控制、系统通知、网络请求。它不是“模型平台”或“AI 平台配置”目录，和 `renderer/utils/model/modelPlatforms.ts` 里那种 provider / platform 概念不是同一层含义。

## 直接子目录地图

这个目标目录当前没有直接子目录，只有一组平台抽象相关的 TypeScript 文件：

`IPlatformServices.ts` 定义平台服务接口，是所有实现必须遵守的契约。

`ElectronPlatformServices.ts` 提供 Electron 主进程实现，内部直接导入 `electron`，封装 `app`、`utilityProcess`、`powerSaveBlocker`、`Notification`、`net.fetch` 等能力。

`NodePlatformServices.ts` 提供 Node.js / utility process 可用的降级实现，使用 `os`、`path`、`child_process.fork` 和全局 `fetch`。

`index.ts` 是对外入口，维护当前注册的 `_services`，导出 `getPlatformServices()`、`registerPlatformServices()` 和相关类型。

`register-electron.ts` 是副作用注册模块，导入后会执行 `registerPlatformServices(new ElectronPlatformServices())`。

因此这里不是按功能拆成多级目录，而是以“接口 + Electron 实现 + Node 实现 + 注册入口”的扁平结构组织。根据当前片段推断，这个目录被刻意保持很小，用来约束 Electron 依赖的边界。

## 关键入口

最重要的读取入口是 `packages/desktop/src/common/platform/index.ts`。

上层代码通常不会直接 new `ElectronPlatformServices` 或 `NodePlatformServices`，而是调用：

`getPlatformServices()`

它返回当前注册好的 `IPlatformServices`，然后调用者再按能力访问，例如 `getPlatformServices().paths.getDataDir()`、`getPlatformServices().power.preventDisplaySleep()`、`getPlatformServices().notification.send()`。

最重要的注册入口是：

`registerPlatformServices(services: IPlatformServices)`

Electron 主进程通过 `packages/desktop/src/common/platform/register-electron.ts` 调用它，把 `ElectronPlatformServices` 注入为当前平台服务。项目中 `packages/desktop/src/process/index.ts` 导入了 `@/common/platform/register-electron`，这说明主进程启动早期会执行这个注册动作。

接口入口是：

`packages/desktop/src/common/platform/IPlatformServices.ts`

这里定义了 `IPlatformPaths`、`IWorkerProcess`、`IWorkerProcessFactory`、`IPowerManager`、`INotificationService`、`INetworkService`、`IPlatformServices`。如果后续要扩展平台能力，应该先从这个接口文件理解边界，再分别补齐 Electron 和 Node 两套实现。

还有一个小但重要的工具入口：

`getDevAppName()`

它集中处理开发模式下的应用名隔离。`index.ts` 中的自动注册逻辑会在 Electron browser process 且非 packaged 时调用 `app.setName()` 和 `app.setPath('userData', ...)`，避免开发环境多实例或打包顺序导致 userData 路径不一致。

## 主流程位置

主流程可以按“启动注册”和“业务调用”两条线理解。

启动注册线在 `packages/desktop/src/process/index.ts`。该文件导入 `@/common/platform/register-electron`，触发 `register-electron.ts` 的副作用注册。`register-electron.ts` 创建 `ElectronPlatformServices`，并通过 `registerPlatformServices()` 写入 `index.ts` 里的模块级变量 `_services`。此后主进程中的其他模块调用 `getPlatformServices()` 时，就会拿到 Electron 实现。

业务调用线分布在 process 和 common 的多个位置。比如 `packages/desktop/src/common/config/appEnv.ts` 使用 `getPlatformServices().paths.isPackaged()` 判断环境；`packages/desktop/src/process/utils/utils.ts` 使用 `paths` 获取目录和判断是否需要 CLI 安全 symlink；`packages/desktop/src/process/utils/initStorage.ts` 使用 `paths.isPackaged()`、`paths.getLogsDir()` 初始化存储路径；`packages/desktop/src/process/bridge/notificationBridge.ts` 通过 `notification.send()` 发送通知；`packages/desktop/src/process/bridge/systemSettingsBridge.ts` 通过 `power.preventDisplaySleep()` 控制显示器休眠；`packages/desktop/src/process/utils/configureChromium.ts` 使用 `getDevAppName()` 保持开发环境命名一致。

还有一条特殊兜底线在 `index.ts` 的 `getPlatformServices()` 内部。注释说明 Rollup 打包后，某些 shared chunk 可能在副作用导入前先执行，导致模块级代码提前调用平台 API。为处理这种调用顺序问题，`getPlatformServices()` 在检测到 `process.versions.electron` 时会自动构造一个内联 Electron 服务；如果当前是 Electron utility process，即 `process.type !== 'browser'`，则退回 `NodePlatformServices`。根据当前片段推断，这个兜底是为了让 `initStorage.ts` 这类可能被提前求值的模块不因注册尚未发生而崩溃。

## 推荐阅读顺序

建议先读 `packages/desktop/src/common/platform/IPlatformServices.ts`。这个文件给出了平台抽象的完整边界，能快速建立“这里到底抽象了哪些能力”的全局图。

第二步读 `packages/desktop/src/common/platform/index.ts`。重点看 `_services`、`registerPlatformServices()`、`getPlatformServices()`、Electron 自动注册分支、utility process 降级分支，以及开发模式 `getDevAppName()` 的路径隔离逻辑。这个文件决定了调用者实际拿到哪套实现。

第三步读 `packages/desktop/src/common/platform/ElectronPlatformServices.ts`。关注它如何把 Electron API 映射到接口：`app.getPath()` 对应 `paths`，`utilityProcess.fork()` 对应 `worker.fork()`，`powerSaveBlocker` 对应 `power`，`Notification` 对应 `notification`，`net.fetch()` 对应 `network.fetch()`。

第四步读 `packages/desktop/src/common/platform/NodePlatformServices.ts`。这里能看出非 Electron 环境的降级策略：数据目录默认是 `~/.aionui-server`，日志目录可由 `LOGS_DIR` 覆盖，打包状态由 `IS_PACKAGED` 控制，通知和休眠控制是 no-op，worker 使用 `child_process.fork()`。

最后再看调用点，例如 `packages/desktop/src/process/index.ts`、`packages/desktop/src/process/utils/initStorage.ts`、`packages/desktop/src/process/bridge/notificationBridge.ts`、`packages/desktop/src/process/bridge/systemSettingsBridge.ts`。这些位置能帮助理解平台服务如何进入真实业务流程。

## 常见误区

第一个误区是把这里的 `platform` 理解成 AI 模型平台。这个目录处理的是运行时平台能力，和模型 provider、OpenAI-compatible 平台、Gemini 平台等配置没有直接关系。

第二个误区是随手在 common 或 process 代码中直接导入 `electron`。当前文件注释明确指出，`ElectronPlatformServices.ts` 是 `src/common/platform/` 中唯一允许直接从 `electron` 导入的文件。其他模块应通过 `getPlatformServices()` 获取能力，否则会破坏运行时隔离，也可能在 utility process 或 Node 环境中失败。

第三个误区是认为 `getPlatformServices()` 永远只返回显式注册的 `ElectronPlatformServices`。实际上它有 Electron 环境下的自动兜底逻辑，也可能在 utility process 中返回 `NodePlatformServices`。因此调用者应依赖接口契约，而不是假设底层一定有完整 Electron 能力。

第四个误区是忽略 no-op 行为。`NodePlatformServices` 中的 `power` 和 `notification` 基本是静默降级，`getSystemPath()` 返回 `null`。调用方如果需要真实系统路径或通知反馈，必须考虑这些能力在非 Electron 环境下不可用。

第五个误区是扩展接口时只改一处。`IPlatformServices.ts` 增加新能力后，至少需要同步考虑 `ElectronPlatformServices.ts`、`NodePlatformServices.ts`，以及 `index.ts` 中自动注册的内联 Electron fallback。否则 TypeScript 或运行时行为会出现不一致。
