# 目录：apps/desktop/src/main

## 它负责什么

`apps/desktop/src/main` 是 LobeHub Desktop 的 Electron 主进程代码区，承担“桌面壳”的核心职责：应用生命周期、窗口管理、系统权限、原生菜单/托盘/快捷键、IPC 服务端、协议处理、本地文件访问、自动更新、工具检测、MCP/异构 Agent 等桌面能力都从这里发起或注册。

入口非常薄：`apps/desktop/src/main/index.ts` 只做三件事：引入 `fix-path` 修正桌面应用里的 `PATH`，创建 `new App()`，然后调用 `app.bootstrap()`。真正的组织者是 `core/App.ts`。它在构造阶段创建一组 Manager，加载 controller/service，注册自定义协议；在 `bootstrap()` 阶段等待 Electron ready、启动 IPC、初始化窗口、菜单、托盘、快捷键、更新器等运行时能力。

这个目录不是 React 页面层，也不是业务 UI 层。渲染进程仍主要复用仓库根部的 `src/` SPA 代码；`main` 更像原生能力后端，负责把系统 API 包装成 renderer 可调用的能力。

## 关键组成

直接结构大致可以分为几类。

`core/` 是主进程骨架。`core/App.ts` 是总入口类；`core/browser/BrowserManager.ts` 负责创建、查找、聚焦、广播和关闭 Electron 窗口；`core/infrastructure/` 下按名称推断承载 `StoreManager`、`ProtocolManager`、`RendererUrlManager`、`StaticFileServerManager`、`LocalFileProtocolManager`、`UpdaterManager`、`I18nManager`、`ToolDetectorManager` 等基础设施；`core/ui/` 下则是菜单、快捷键、托盘这类 UI 外壳管理。

`controllers/` 是 renderer 调主进程的主要入口。每个 `*Ctr.ts` 通常继承 `ControllerModule`，定义静态 `groupName`，再用 `@IpcMethod()` 暴露方法。例如 `SystemCtr.ts` 的 `groupName = 'system'`，方法会变成 `system.getAppState`、`system.openExternalLink`、`system.updateLocale` 等 IPC channel。`controllers/index.ts` 提供 `ControllerModule`、`IpcMethod`、`shortcut`、`createProtocolHandler` 等装饰器和基类；`controllers/registry.ts` 则把 controller 列成 `controllerIpcConstructors`，用于导出类型 `DesktopIpcServices`。

`utils/ipc/` 是 IPC 注册机制。`IpcMethod()` 把方法元数据挂到类上；`IpcService` 构造时读取这些元数据，并通过 Electron `ipcMain.handle(channel, handler)` 注册调用。channel 规则是 `${groupName}.${methodName}`。`AsyncLocalStorage` 保存当前 IPC 上下文，方便方法内部知道调用来源 `event.sender`。

`services/` 是主进程内部服务基类和若干服务模块。`ServiceModule` 只保存 `app` 引用，具体服务如 `fileSrv.ts`、`contentSearchSrv.ts`、`gatewayConnectionSrv.ts` 给 controller 或 manager 复用。它们不是 renderer 直接访问的前端 service；前端侧 service 位于根目录 `src/services/electron/`。

`modules/` 放更大块的桌面功能模块，比如 `heterogeneousAgent`、`contentSearch`、`fileSearch`、`networkProxy`、`cliEmbedding`、`screenCapture`、`toolDetectors`、`updater`、`openInApp`。这些通常被 `App`、controller 或 manager 组合使用。比如 `App` 会注册内置 tool detector，并调用 `generateCliWrapper()` 生成终端可用的 CLI wrapper。

`appBrowsers.ts` 定义窗口配置。`appBrowsers` 里有主窗口 `app` 和 `devtools` 窗口；`windowTemplates` 里有可多开的 `chatSingle`、`topicPopup` 模板。`BrowserManager` 根据这些配置创建实际 `BrowserWindow`，并处理 topic popup、quick chat popup 等多窗口场景。

`const/`、`types/`、`locales/`、`menus/`、`libs/`、`__mocks__/` 分别提供常量、类型、本地化资源、菜单实现、底层库集成和测试 mock。`package.json` 暴露包名 `@lobehub/desktop-ipc-typings`，其导出指向 `exports.d.ts`；`exports.ts` 只导出 `DesktopIpcServices` 类型，给 renderer/preload 获得类型化 IPC 形状。

## 上下游关系

上游启动来自 Electron main entry。构建后的桌面应用启动 `apps/desktop/src/main/index.ts`，进而进入 `App`。`App` 依赖 Electron 的 `app`、`protocol`、`nativeTheme`，也依赖项目内的 manager、controller、service 和模块。

下游主要有三类。

第一类是 Electron 原生 API：`BrowserWindow`、`ipcMain`、`dialog`、`shell`、`nativeTheme`、`protocol`、全局快捷键、托盘、菜单、自动更新等。`SystemCtr.ts` 中的权限检查、文件夹选择、打开外链、读取系统路径都是典型例子。

第二类是 renderer/preload。renderer 不能直接碰主进程 API，而是通过 preload 暴露的 IPC 客户端调用。调用方示例包括 `src/utils/electron/ipc.ts` 的 `ensureElectronIpc()`，以及 `src/services/electron/system`、`src/routes/(desktop)/desktop-onboarding/...`、`src/features/Electron/...` 等。比如 onboarding 会调用 `ipc.system.getAppState()`、`ipc.system.getMediaAccessStatus()`、`ipc.system.requestScreenAccess()`；路由拦截会调用 `system.openExternalLink` 打开外部链接。

第三类是主进程内部模块互相协作。`App` 持有 `StoreManager`、`BrowserManager`、`I18nManager` 等实例，并把自身传给 controller/service。controller 内部可通过 `this.app.browserManager`、`this.app.storeManager`、`this.app.i18n` 访问全局能力。例如 `SystemCtr.updateLocale()` 会写 store、切换 i18n，并通过 `browserManager.broadcastToAllWindows('localeChanged', { locale })` 通知所有窗口。

## 运行/调用流程

应用启动时，`index.ts` 调用 `fixPath()`，再执行 `app.bootstrap()`。`App` 构造函数先打印系统信息，扩展 `PATH`，创建 `StoreManager`、`RendererUrlManager`、`LocalFileProtocolManager`，并注册 `lobehub` 自定义协议、renderer loader 协议、本地文件协议等 privileged scheme。

随后 `App` 通过 `import.meta.glob('@/controllers/*Ctr.ts', { eager: true })` 自动加载所有 controller 类，并逐个 `addController()`。这里会实例化 controller，收集 `@shortcut` 和 `createProtocolHandler` 注册的元数据。接着类似地加载 `services/*Srv.ts`，再初始化 IPC server、i18n、browser、menu、updater、shortcut、tray、static file server、protocol、tool detector、screen capture 等 manager。

`bootstrap()` 阶段先用 `app.requestSingleInstanceLock()` 保证单实例；启动 `ElectronIPCServer`；调用 `makeAppReady()`，其中 controller 的 `beforeAppReady()` 会在 `app.whenReady()` 前运行，`afterAppReady()` 会在 ready 后运行。之后初始化 i18n、菜单、静态文件服务、快捷键、窗口、托盘、更新器，并注册 `window-all-closed`、`activate` 等生命周期事件。

renderer 发起调用时，流程通常是：React 组件或前端 service 调用 `ensureElectronIpc().system.getAppState()`；preload/IPC 客户端把它转换成 `ipcRenderer.invoke('system.getAppState')`；主进程 `IpcService` 已经通过 `ipcMain.handle('system.getAppState', ...)` 注册处理器；最终执行 `SystemCtr.getAppState()`，返回平台、架构、locale、用户目录等数据。窗口事件或状态变化则反向通过 `BrowserManager.broadcastToAllWindows()` 发送给 renderer。

## 小白阅读顺序

1. 先读 `apps/desktop/src/main/index.ts`，建立“入口很薄，核心在 `App`”的直觉。
2. 再读 `apps/desktop/src/main/core/App.ts`，重点看 constructor 和 `bootstrap()`，理解初始化顺序。
3. 读 `apps/desktop/src/main/controllers/index.ts` 和 `apps/desktop/src/main/utils/ipc/base.ts`，搞清楚 `@IpcMethod()` 如何变成 IPC channel。
4. 读一个简单 controller，比如 `controllers/SystemCtr.ts`，观察主进程如何封装系统 API。
5. 读 `appBrowsers.ts` 和 `core/browser/BrowserManager.ts`，理解主窗口、devtools、popup 窗口怎么创建和复用。
6. 最后按兴趣进入 `modules/`：想看 Agent/CLI/MCP/搜索/截图/更新时，再读对应模块，不要一开始就展开全部。

## 常见误区

不要把 `apps/desktop/src/main` 当成前端页面目录。它运行在 Electron main process，不能直接使用 React hooks，也不应该写页面 UI。真正页面和业务 UI 多在根目录 `src/routes`、`src/features`、`src/services`。

不要以为 `controllers/registry.ts` 就是运行时唯一注册来源。根据当前片段可见，`App` 运行时使用 `import.meta.glob('@/controllers/*Ctr.ts')` 自动加载 controller；`registry.ts` 更明显的作用是维护 `DesktopIpcServices` 类型导出，让 renderer 获得类型化 IPC 服务形状。因此新增 controller 时既要考虑运行时文件命名 `*Ctr.ts`，也要考虑类型注册是否同步。

不要绕过 `@IpcMethod()` 手写零散 `ipcMain.handle`。该目录已经形成了 `ControllerModule` + `IpcMethod` + `groupName` 的统一模式，channel 命名、类型推导、上下文保存都依赖这套结构。

不要在 controller 中直接假设主窗口一定存在。很多方法会通过 `this.app.browserManager.getMainWindow()?.browserWindow` 取窗口，再传给 `dialog`；窗口初始化顺序、Linux/macOS/Windows 生命周期差异都可能影响行为。

不要混淆主进程 service 和 renderer service。`apps/desktop/src/main/services/*Srv.ts` 是主进程内部服务；`src/services/electron/*` 是前端调用 IPC 的包装层。两者同名“service”，但运行环境和职责不同。

不要忽略协议和本地文件安全边界。`LocalFileProtocolManager` 会维护允许访问的 workspace roots；`SystemCtr.selectFolder()` 选择目录后会 approve root 并写入 store。这说明本地文件预览不是任意路径裸放给 renderer，而是经过主进程授权管理。
