# 目录：packages/desktop/src/process

## 它负责什么

`packages/desktop/src/process` 是桌面端的 Electron 主进程层。它不直接承担 React 渲染，也不应该混入 DOM 逻辑；它的职责更接近“桌面壳 + 本地运行时协调器”：初始化 Electron 应用环境、注册主进程侧 IPC bridge、启动或定位后端服务、管理窗口生命周期、托盘、菜单、深链、自动更新、数据库迁移、日志反馈、内置资源与桌宠相关主进程状态。

从已读取片段看，根入口 `packages/desktop/src/process/index.ts` 会引入 `@/common/platform/register-electron`、`@process/utils/configureChromium`、`./utils/initBridge`、`./services/i18n`，并导出 `initializeProcess`。这说明该目录是 Electron 主进程初始化链的一部分，而不是普通业务模块集合。Renderer 侧如果需要系统能力，应通过 preload/IPC 与这里的 bridge 通信，而不是直接访问这些模块。

## 直接子目录地图

`backend`：后端二进制或可执行服务的解析层。当前能看到 `binaryResolver.ts`、`binaryResolver.test.ts`、`index.ts`，其中 `backend/index.ts` 重新导出 `resolveBinaryPath`。它关心“后端程序在哪里”，不等同于完整后端业务代码。

`bridge`：主进程 IPC 能力注册区。`bridge/index.ts` 汇总调用 `initApplicationBridge`、`initDialogBridge`、`initUpdateBridge`、`initSystemSettingsBridge`、`initWindowControlsBridge`、`initNotificationBridge`、`initWebuiBridge`、`initThemeBridge` 等。这里是 Renderer 请求主进程能力的主要门面。

`feedback`：反馈与诊断材料相关，目前能看到 `logs.ts`，根据当前片段推断用于收集或定位日志，服务反馈提交、错误排查等流程。

`pet`：桌宠功能的主进程状态和事件层，包括 `petManager.ts`、`petStateMachine.ts`、`petEventBridge.ts`、`petIdleTicker.ts`、`petConfirmManager.ts`、`petTypes.ts`。它不是简单 UI 组件目录，而是主进程侧的行为编排、状态机和事件桥接。

`resources`：主进程可用的内置资源。目前展开到 `resources/builtinMcp`，包含 `constants.ts`、`imageGenServer.ts`。根据命名推断，这里保存随桌面应用打包或主进程直接管理的 MCP 相关内置能力，例如 image generation server 配置。

`services`：主进程服务层。当前包括自动更新诊断与服务、数据库服务、主进程 i18n 初始化。`services/database` 下有 schema、migrations、legacy migrations 和 SQLite driver 抽象，说明本地持久化不是散落在工具函数中，而是集中在服务层。

`startup`：启动阶段专项流程。能看到 `backendStartup.ts`、`backendStartupFailure.ts`、`backendInstallDiagnostics.ts`、`architectureCompatibility.ts`、`quitCleanup.ts`。其中 `backendStartup.ts` 暴露 `startBackendOrExit`，负责把后端启动成功、取消、失败退出等启动时分支收束起来。

`utils`：主进程通用支撑工具。这里数量较多，覆盖 `appMenu`、`tray`、`deepLink`、`gpuRecovery`、`windowBounds`、`zoom`、`webuiConfig`、`initStorage`、`initBridge`、`mainWindowLifecycle`、`persistOnQuit`、`resetPasswordCLI`、`runBackendMigrations`、`migrateAssistants` 等。它是主进程运行时“胶水层”，但其中不少文件已经接近业务流程入口，阅读时不要把它们当作无状态小工具。

## 关键入口

第一入口是 `packages/desktop/src/process/index.ts`。它导出 `initializeProcess`，并在模块加载阶段完成若干全局初始化：注册 Electron 平台适配、配置 Chromium、初始化 bridge、初始化主进程 i18n。学习这个目录时应先看它的 imports，因为主进程很多行为是通过副作用注册完成的。

第二入口是 `packages/desktop/src/process/utils/initBridge.ts`。它导入 `initAllBridges`，负责触发 bridge 注册。真正的桥接清单在 `packages/desktop/src/process/bridge/index.ts`，这里可以快速看到当前主进程向 Renderer 暴露了哪些能力域。

第三入口是 `packages/desktop/src/process/startup/backendStartup.ts`。它定义 `startBackendOrExit(options)`，内部调用 `options.startBackend()` 并返回后端端口或处理启动失败。它是理解“桌面壳如何依赖本地后端”的关键位置。

第四入口是 `packages/desktop/src/process/utils/mainWindowLifecycle.ts`。这里提供 `bindMainWindowReferences`、`showAndFocusMainWindow`、`showOrCreateMainWindow`，并把主窗口引用同步给 application bridge、deep link、tray 等模块。窗口创建本身可能在邻近的 Electron app 层，但主窗口引用的分发在这里能看清楚。

## 主流程位置

应用启动主流程大致从 `process/index.ts` 开始：先建立主进程运行环境，再初始化存储、i18n、IPC bridge，之后进入后端启动、窗口展示和退出清理等阶段。根据当前片段推断，后端启动主线会经过 `startup/backendStartup.ts`，二进制定位会用到 `backend/binaryResolver.ts`，启动失败的诊断和展示则分散在 `startup/backendStartupFailure.ts`、`startup/backendInstallDiagnostics.ts`。

IPC 主流程集中在 `utils/initBridge.ts` 到 `bridge/index.ts`。`bridge/index.ts` 是 bridge 总目录，阅读它可以先建立能力地图，再分别进入 `applicationBridge.ts`、`dialogBridge.ts`、`updateBridge.ts`、`webuiBridge.ts`、`windowControlsBridge.ts` 等具体模块。注意这里是主进程侧注册点，Renderer 侧调用入口通常在 preload 或 renderer 的封装中，需要跨目录追踪。

窗口与桌面壳流程集中在 `utils/mainWindowLifecycle.ts`、`utils/tray.ts`、`utils/appMenu.ts`、`utils/deepLink.ts`、`utils/windowBounds.ts`、`utils/closeToTraySetting.ts`。这些文件共同处理“窗口如何显示、聚焦、关闭到托盘、响应深链、恢复尺寸”等桌面应用体验。

数据与迁移流程集中在 `services/database` 和 `utils/runBackendMigrations.ts`。`services/database/schema.ts`、`migrations.ts`、`runLegacyDatabaseMigrations.ts`、`drivers/BetterSqlite3Driver.ts` 说明这里有主进程本地数据库结构与迁移责任；如果排查会话、配置或历史数据问题，应优先从这些位置建立上下文。

自动更新流程集中在 `services/autoUpdaterService.ts`、`services/autoUpdateDiagnostics.ts` 和 `bridge/updateBridge.ts`。前者更像底层服务和诊断，后者负责把能力暴露给 UI。

## 推荐阅读顺序

1. 先读 `packages/desktop/src/process/index.ts`，确认主进程初始化顺序和副作用 import。
2. 再读 `packages/desktop/src/process/bridge/index.ts` 与 `packages/desktop/src/process/utils/initBridge.ts`，建立 IPC 能力地图。
3. 接着读 `packages/desktop/src/process/startup/backendStartup.ts`、`packages/desktop/src/process/backend/binaryResolver.ts`，理解桌面应用如何找到并启动后端。
4. 然后读 `packages/desktop/src/process/utils/mainWindowLifecycle.ts`、`tray.ts`、`deepLink.ts`，串起窗口、托盘和深链。
5. 需要理解数据时，再进入 `packages/desktop/src/process/services/database`；需要理解更新时，再进入 `autoUpdaterService.ts` 和 `bridge/updateBridge.ts`。
6. 最后按功能补读 `pet`、`resources/builtinMcp`、`feedback`，这些更偏专项能力，不适合作为第一批入口。

## 常见误区

不要把 `process` 理解成后端业务目录。这里是 Electron 主进程目录，能启动或协调后端，但完整业务服务不一定在这里。

不要在 Renderer 代码中直接引用这里的模块。主进程有 Electron、Node、本地文件和进程能力；Renderer 侧应该通过 preload/IPC bridge 访问，否则会破坏进程边界。

不要只看 `utils` 名字就低估它的重要性。该目录下的 `initBridge.ts`、`mainWindowLifecycle.ts`、`runBackendMigrations.ts`、`webuiConfig.ts` 都可能处在主流程关键路径上。

不要新增 bridge 时只写一个 `xxxBridge.ts`。还需要检查 `bridge/index.ts` 是否统一注册，preload 和 Renderer 侧是否有匹配的通道定义与类型约束。

不要把自动更新、数据库迁移、后端启动失败处理混在窗口代码里。现有结构已经把这些流程拆到 `services`、`startup`、`backend` 等目录，改动时应沿用这种分层。

不要在这里引入 DOM 或 React 组件思维。`packages/desktop/src/process` 属于主进程，根据项目架构约束，它可以使用 Electron 主进程和 Node 能力，但不应该访问浏览器 DOM。
