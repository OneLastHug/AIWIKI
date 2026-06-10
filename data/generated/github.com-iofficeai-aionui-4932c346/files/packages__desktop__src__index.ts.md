# 文件：packages/desktop/src/index.ts

## 一句话定位

`packages/desktop/src/index.ts` 是 AionUi 桌面端 Electron **main process 的总入口**：它负责抢单实例锁、初始化主进程环境、启动后端 `aioncore`、创建主窗口或 WebUI 服务、注册协议和生命周期清理，是桌面应用从进程启动到可用状态之间的中枢调度文件。

## 它暴露/定义了什么

这个文件不是给业务模块 import 的普通库文件，基本不对外导出 API；它定义的是 Electron 进程启动时直接执行的一组全局流程和局部函数。核心状态包括 `mainWindow`、`backendManager`、`backendStartedOk`、`backendStartupFailed`、`rendererInitialLanguage`、`appReadyDone`、`isExplicitQuit` 等，用来贯穿启动、窗口、后端、迁移、托盘和退出清理。

它也注册了若干同步 IPC：`get-backend-port`、`get-initial-language`、`get-backend-startup-failed`、`get-backend-startup-failure`。这些 IPC 给 preload/renderer 侧读取启动期信息，尤其是后端端口、初始语言和后端启动失败状态。

根据构建配置 `packages/desktop/electron.vite.config.ts`，该文件被作为 main bundle 的 `index` 入口打包；`packages/desktop/package.json` 的 `main` 指向打包后的 `out/main/index.js`。因此它的“暴露”更多体现在进程入口副作用，而不是模块导出。

## 谁调用它

直接调用者是 Electron 运行时。应用启动时，Electron 根据桌面包的 `main` 字段加载 `out/main/index.js`，而这个产物来自 `packages/desktop/src/index.ts`。

间接上，开发/打包工具链由 `electron-vite` 读取 `packages/desktop/electron.vite.config.ts`，将 `packages/desktop/src/index.ts` 编译为 main process 入口。用户双击桌面应用、命令行启动、系统登录自启动、协议链接唤起、`--webui`、`--resetpass`、`--version` 等模式最终都会进入这个文件，只是在 `handleAppReady()` 内走不同分支。

## 它调用谁

启动前置阶段调用 `./process/utils/configureChromium`、`initSentry()`、`./process/utils/configureConsoleLog`，先设置 Chromium 参数、Sentry 和日志。这里顺序很关键：注释明确说明 `configureChromium` 必须早于任何调用 `app.getPath('userData')` 的模块，因为 Electron 会缓存路径。

主初始化阶段调用 `initializeProcess()`、`ProcessConfig`、`setInitialLanguage()`、`initializeZoomFactor()`、`loadSavedWindowBounds()` 等，完成配置、存储、语言、缩放和窗口尺寸恢复。

后端阶段通过 `BackendLifecycleManager`、`resolveBinaryPath`、`startBackendOrExit()`、`assertStartupArchitectureCompatible()` 启动并守护 `aioncore`。后端启动失败会交给 `classifyBackendStartupFailure()` 和 `captureBackendStartupFailure()` 归类并上报。

窗口阶段调用 `BrowserWindow`、`initMainAdapterWithWindow()`、`bindMainWindowReferences()`、`setupApplicationMenu()`、`setupZoomForWindow()`、`registerWindowMaximizeListeners()`、`attachWindowBoundsPersistence()`，并加载 renderer 的开发服务地址或打包后的 `renderer/index.html`。

桌面周边能力调用托盘模块、deep link 模块、WebUI 配置模块、自动更新模块、pet 模块、GPU crash recovery、退出清理模块，以及若干 bridge 文件，例如 `feedbackBridge`、`applicationBridge`、`systemSettingsBridge`。

## 核心流程

进程一启动，文件先注册 Sentry、日志、平台 PATH 修正、Windows Squirrel 安装事件处理、全局异常兜底，然后抢单实例锁。抢锁失败的第二实例会退出；抢锁成功的主实例监听 `second-instance`，把协议链接转给已有实例，并在需要时聚焦或重建主窗口。

随后解析命令行模式：`--webui` 进入无窗口 Web 服务模式，`--remote` 控制 WebUI 远程访问，`--resetpass` 执行重置密码 CLI，`--version` 打印版本后退出。普通桌面模式则继续创建窗口。

`app.whenReady()` 触发 `handleAppReady()`。这个函数先在开发模式安装 React DevTools，然后处理 `--version`，设置 macOS dock 图标，写入 Sentry device id。接着执行 `initializeProcess()`，读取初始语言，再启动后端。后端启动成功后会通过 `markBackendReady()` 暴露端口、注册系统 resume 通知、确保管理员用户，并尝试调度迁移。

后端之后恢复缩放和窗口边界。若是 `--resetpass`，只执行密码重置并退出；若是 `--webui`，启动 `startWebHost()`，复用刚启动的后端端口，不创建桌面窗口；否则进入普通桌面流程：读取关闭到托盘设置，创建主窗口，延迟初始化 pet，初始化主进程 i18n，恢复桌面 WebUI 偏好，并在 renderer 加载完成后处理积压的 deep link。

文件末尾注册协议处理、GPU crash handler、`window-all-closed`、`activate`、`before-quit` 清理、`will-quit` 和 `quit` 日志。整体上它把 Electron 生命周期、后端生命周期和桌面 UI 生命周期绑在一起。

## 关键函数的高层作用

`handleAppReady()` 是最核心的启动编排函数。它决定应用启动后的模式分支，并保证关键顺序：先主进程存储初始化，再启动后端，再恢复 UI 配置，最后根据模式创建窗口或 WebUI 服务。修改这个函数时要特别关注时序依赖。

`createWindow()` 负责构造主 `BrowserWindow`，恢复尺寸和位置，设置 macOS/Windows/Linux 的窗口外观差异，绑定 preload，延迟显示窗口以避免 FOUC，并把主窗口交给 adapter、bridge、菜单、缩放、窗口状态持久化、自动更新和崩溃恢复逻辑。它不是单纯的“建窗口”，而是桌面交互能力的集中挂载点。

`markBackendReady()` 标记后端真正可用。它设置全局后端端口、注册系统唤醒通知、清除失败状态、触发管理员用户修复和迁移调度。这个函数是后端从“进程已启动/健康检查 pending”进入“前后端可通信”的边界。

`scheduleBackendMigrations()` 是一个延迟迁移入口。注释说明部分迁移会通过 renderer/BroadcastChannel 间接通信，所以不能在 renderer 存在前运行，否则可能造成 main process 死锁。它只在后端已成功启动且未调度过时执行。

`registerCronResumeBridge()` 监听系统从睡眠恢复的 `powerMonitor.resume`，通知后端执行内部恢复逻辑。它同时维护 `disposeCronResumeListener`，保证退出清理时可以移除监听。

`markBackendStartupFailed()` 把未知错误归类为结构化失败信息，并写入全局失败标记，供 renderer 或启动错误 UI 查询。

`ensureAdminUserOnce()` 用 Promise 缓存保证管理员用户修复只执行一次，即使多个启动路径触发也不会重复并发执行。

## 修改风险

最大风险是启动顺序。`configureChromium` 必须最早执行；`initializeProcess()` 必须早于后端启动；后端迁移必须等 renderer 加载完成；`appReadyDone` 防止 macOS `activate` 在初始化完成前抢先创建窗口。随意移动这些调用，可能导致 userData 路径错误、SQLite 竞争、启动卡死或重复窗口。

第二类风险是模式分支耦合。普通桌面、`--webui`、`--resetpass`、`--version` 共用同一个入口，但对窗口、后端失败、退出行为的要求不同。例如 WebUI 模式失败要退出，普通桌面模式可能允许后端健康检查 pending 并展示窗口。改动 `startBackendOrExit()` 参数或分支条件时，容易破坏 CLI/headless 场景。

第三类风险是全局状态和 IPC。`globalThis.__backendPort`、`globalThis.__backendStartupFailed`、同步 `ipcMain.on` 都是跨模块约定。把它们改成异步或延后设置，可能影响 preload、httpBridge、迁移和 renderer 初始状态读取。

第四类风险是窗口生命周期。`createWindow()` 内绑定了托盘关闭拦截、自动更新、窗口尺寸持久化、devtools 状态广播、renderer crash recovery。看似只改窗口选项，也可能影响更新检查、隐藏到托盘、macOS dock 恢复和主窗口引用。

第五类风险是清理路径。`installQuitCleanup()` 会停止后端、销毁托盘和 pet，并移除系统 resume 监听。新增长期监听、子进程或后台服务时，如果只在启动处添加，不接入这里，应用退出后可能残留进程或重复监听。
