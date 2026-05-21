# 目录：apps/desktop/src/main/controllers

## 它负责什么

`apps/desktop/src/main/controllers` 是 LobeHub Desktop 的 Electron main process 控制器层，主要职责是把 renderer 侧不能直接访问的系统能力、安全敏感能力、桌面原生能力，通过 IPC 暴露成一组 typed API。

它可以理解为桌面端的“后端控制器”目录：renderer 侧通过 `window.electronAPI.invoke` 调用类似 `system.getAppState`、`windows.openSettingsWindow`、`localFile.readFile` 这样的 IPC channel；main process 中对应的 `*Ctr` 类接收请求，再调用 Electron API、Node.js API、App manager、desktop service 或本地模块完成实际工作。

这个目录不负责 React UI，也不直接写业务页面；它负责“把桌面能力变成可调用接口”。典型能力包括窗口管理、系统权限、托盘、菜单、快捷键、通知、文件读写、Git、本地命令、MCP、异构 agent、OAuth 登录、远程服务配置、网络代理、更新检测等。

## 关键组成

`index.ts` 是 controller 基础设施入口。它导出 `ControllerModule`、`IpcMethod`、`shortcut`、`createProtocolHandler`。所有 controller 通常继承 `ControllerModule`，而 `ControllerModule` 又继承 `IpcService`，构造时会自动注册被 `@IpcMethod()` 标记的方法。`shortcut` 和 `createProtocolHandler` 不直接执行逻辑，而是把元信息写入 `IoCContainer`，等待 `App.addController` 实例化 controller 时收集。

`registry.ts` 是 IPC 类型注册清单。它显式导入所有 controller，并导出 `controllerIpcConstructors` 和 `DesktopIpcServices` 类型。这里的重点是类型层：通过 `CreateServicesResult`、`MergeIpcService` 把各 controller 的可调用方法合并成 desktop IPC 类型，供 `@lobechat/electron-client-ipc` 做类型增强。根据当前片段推断，runtime 加载 controller 主要不是靠 `registry.ts`，而是 `App.ts` 里的 `import.meta.glob('@/controllers/*Ctr.ts', { eager: true })`；`registry.ts` 更像 renderer IPC 类型契约的集中声明。

`_template.ts` 是新增 controller 的极简模板，示例继承 `ControllerModule`，用 `@IpcMethod()` 暴露方法。

主要 controller 可以按领域理解：

`BrowserWindowsCtr.ts` 管窗口。`groupName = 'windows'`，负责打开设置页、关闭/最小化/最大化窗口、设置置顶、topic popup、route interception 等。它还用 `@shortcut('showApp')`、`@shortcut('quickComposer')`、`@shortcut('quickChat')` 把方法接入全局快捷键。

`SystemCtr.ts` 管系统和 App 状态。`groupName = 'system'`，提供 `getAppState`、macOS 权限检测/请求、主题监听、打开系统设置、目录检查等能力。它实现了 `afterAppReady()`，在 Electron app ready 后初始化系统主题监听。

`LocalFileCtr.ts` 是本地文件能力核心。它导入 `@lobechat/local-file-shell`、Electron `dialog/shell`、文件搜索和内容搜索 service，提供文件选择、读写、编辑、列表、搜索、预览 URL、安全路径审计、项目文件索引、技能目录准备等能力。它是 renderer 访问用户本地文件系统的重要边界，因此路径解析、安全前缀、workspace root、真实路径等逻辑都很关键。

`GitCtr.ts` 管本地 Git 操作，提供仓库检测、状态、diff、提交等相关能力；它通常服务于本地项目/源码操作类功能。

`ShellCommandCtr.ts`、`CliCtr.ts`、`ToolDetectorCtr.ts` 偏命令行和工具检测。前者执行/检查 shell command，`CliCtr` 处理 LobeHub CLI 相关操作，`ToolDetectorCtr` 基于 `ToolDetectorManager` 探测本机可用工具、运行环境、CLI agent 等。

`McpCtr.ts` 和 `McpInstallCtr.ts` 管 MCP。`McpCtr` 处理 stdio/http MCP server manifest、连接、工具调用、序列化 payload 等；`McpInstallCtr` 负责安装相关流程。它们连接 desktop main process、本地命令、MCP client 和 renderer 插件/工具 UI。

`HeterogeneousAgentCtr.ts` 是异构 agent 控制器，负责启动、恢复、取消和驱动 Claude Code、Codex 等外部 CLI agent 会话。它会 spawn 子进程，处理 stdin/stdout/stderr 流、图片附件物化、网络代理环境、用户干预桥接、trace 文件等，是目录里复杂度较高的 controller。

`AuthCtr.ts` 管桌面端 OAuth 授权。它实现 PKCE、state、防 CSRF、打开授权页、轮询授权进度、token 刷新，并依赖 `RemoteServerConfigCtr` 获取远程服务地址。它也有 `afterAppReady()`，用于自动刷新 token。

`RemoteServerConfigCtr.ts` 和 `RemoteServerSyncCtr.ts` 管远程服务器配置与同步。前者处理远程 URL、配置校验和持久化；后者在 app ready 后执行同步类初始化。

`NetworkProxyCtr.ts` 管桌面网络代理设置。它从 `storeManager` 读写 `networkProxy`，使用 `ProxyConfigValidator` 校验配置，用 `ProxyDispatcherManager` 应用代理，用 `ProxyConnectionTester` 测试连接。它还实现 `beforeAppReady()`，说明代理需要在 app ready 前尽早生效。

`MenuCtr.ts`、`TrayMenuCtr.ts`、`ShortcutCtr.ts`、`NotificationCtr.ts` 分别对应菜单、托盘、快捷键和通知。它们通常不保存复杂业务状态，而是桥接 `menuManager`、`trayManager`、`shortcutManager`、Electron notification API 和持久化配置。

`UpdaterCtr.ts` 管更新器，向 renderer 暴露检查更新、下载、安装、状态查询等操作，实际工作下沉到 `updaterManager`。

`GatewayConnectionCtr.ts` 管 device gateway 或连接状态类能力，并在 `afterAppReady()` 后进行自动连接/监听。

`OpenInAppCtr.ts` 管“用 app 打开”的协议/跳转类能力；`DevtoolsCtr.ts` 提供打开 devtools 窗口的简单接口；`ScreenCaptureCtr.ts` 管屏幕捕获 session，与 `screenCaptureManager` 和 preload 暴露的 `onScreenCaptureSession` 配合。

`__tests__/` 是对应 controller 的 Vitest 测试目录，覆盖 IPC 方法、生命周期 hook、异常路径、配置更新等。

## 上下游关系

上游主要是 renderer 侧和 preload。

preload 中 `apps/desktop/src/preload/electronApi.ts` 通过 `contextBridge.exposeInMainWorld('electronAPI', { invoke, ... })` 暴露 `window.electronAPI.invoke`。`packages/electron-client-ipc/src/ipc.ts` 再用 Proxy 把调用包装成 `ipc.group.method(payload)` 形式：访问 `ipc.system.getAppState()` 时，实际会拼出 channel `system.getAppState` 并调用 `invoke(channel, payload)`。

类型上，`apps/desktop/src/main/exports.d.ts` 通过 module augmentation 把 `DesktopIpcServices` 合并到 `@lobechat/electron-client-ipc` 的 `DesktopIpcServicesMap`，因此 renderer 能获得 controller IPC 方法的类型提示。

中间层是 `apps/desktop/src/main/utils/ipc/base.ts`。`@IpcMethod()` 把方法名写入 metadata；`IpcService` 构造时扫描 metadata；`IpcHandler.registerMethod` 调用 Electron `ipcMain.handle(channel, handler)` 注册真正的 IPC handler。channel 命名规则是：

```text
${ControllerClass.groupName}.${methodName}
```

例如 `SystemCtr.groupName = 'system'`，`getAppState()` 暴露为 `system.getAppState`。

下游是 Electron main process 的实际能力：`App` 聚合的 `browserManager`、`storeManager`、`menuManager`、`shortcutManager`、`trayManager`、`updaterManager`、`screenCaptureManager`、`protocolManager`、`toolDetectorManager`，以及 main 侧 services、Node.js 文件系统、子进程、Electron `app/dialog/shell/nativeTheme/BrowserWindow` 等。

controller 之间也可以互相调用，但一般通过 `this.app.getController(SomeCtr)` 获取实例，例如 `AuthCtr` 通过 `RemoteServerConfigCtr` 获取远程服务器 URL。

## 运行/调用流程

启动时，`App` 构造函数先初始化 store、协议、manager 等基础对象，然后用：

```ts
import.meta.glob('@/controllers/*Ctr.ts', { eager: true })
```

加载所有 `*Ctr.ts`。每个 controller class 会被 `addController` 实例化，并放入 `this.controllers` map。

实例化时，`ControllerModule` 调用父类 `IpcService` 构造逻辑，自动注册当前 class 上所有 `@IpcMethod()` 方法。注册完成后，Electron main process 就能响应对应 channel 的 `ipcMain.handle` 调用。

`addController` 还会读取 `IoCContainer.shortcuts` 和 `IoCContainer.protocolHandlers`。如果某个方法被 `@shortcut(...)` 标记，它会被加入 `app.shortcutMethodMap`，后续由 `ShortcutManager` 注册成全局快捷键动作。如果某个方法被 `createProtocolHandler(...)` 标记，它会被加入 `protocolHandlerMap`，后续 `App.handleProtocolRequest` 根据 `urlType:action` 找到 controller 方法执行。

之后 `App.bootstrap()` 会启动 IPC server、执行 `makeAppReady()`。`makeAppReady()` 先遍历 controller，调用存在的 `beforeAppReady()`；等待 `app.whenReady()` 后，再调用存在的 `afterAppReady()`。因此 controller 有三类入口：普通 IPC 方法、快捷键/协议方法、生命周期 hook。

renderer 调用时，流程大致是：

```text
React/renderer service
→ @lobechat/electron-client-ipc Proxy
→ window.electronAPI.invoke('group.method', payload)
→ preload invoke
→ Electron ipcMain.handle
→ controller.@IpcMethod 方法
→ App manager / service / Node / Electron API
→ 返回 Promise 结果给 renderer
```

以 `system.getAppState` 为例：renderer 侧调用 `ipc.system.getAppState()`，IPC channel 是 `system.getAppState`，main process 进入 `SystemCtr.getAppState()`，读取 `process.platform`、`app.getPath(...)`、`storeManager.get('locale')`，最后返回桌面 App 状态。

以 `windows.openSettingsWindow` 为例：renderer 侧传入 tab/path，`BrowserWindowsCtr.openSettingsWindow()` 归一化参数，拿到 main window，调用 `mainWindow.show()`，再通过 `mainWindow.broadcast('navigate', { path })` 通知 renderer 导航。

## 小白阅读顺序

先读 `index.ts`。目标是弄懂 `ControllerModule`、`@IpcMethod()`、`@shortcut()` 的意义：controller 不是普通 class，它的方法会被自动注册成 IPC handler。

再读 `utils/ipc/base.ts`。重点看 `IpcMethod`、`IpcService.registerMethods`、`IpcHandler.registerMethod`，这里解释了为什么加一个装饰器就能被 renderer 调用，以及 channel 名为什么是 `group.method`。

然后读 `App.ts` 中 controller 加载和生命周期相关片段：`import.meta.glob('@/controllers/*Ctr.ts')`、`addController`、`makeAppReady`。这一步能把“文件被加载、实例被创建、hook 被调用、快捷键被收集”的过程串起来。

接着读 `registry.ts` 和 `exports.d.ts`。它们主要解决类型问题：renderer 如何知道有哪些 IPC group 和 method。注意把它和 runtime 加载区分开。

再读一个简单 controller，例如 `_template.ts`、`DevtoolsCtr.ts`、`TrayMenuCtr.ts` 或 `ShortcutCtr.ts`。这些文件短，容易看清 `groupName + @IpcMethod + this.app.xxxManager` 的基本模式。

之后读中等复杂度的 `BrowserWindowsCtr.ts`、`SystemCtr.ts`、`NetworkProxyCtr.ts`。它们能展示窗口控制、系统状态、配置读写、生命周期 hook 的常见写法。

最后再读复杂 controller：`LocalFileCtr.ts`、`GitCtr.ts`、`McpCtr.ts`、`HeterogeneousAgentCtr.ts`、`AuthCtr.ts`。这些文件更像完整子系统的 main-process facade，里面包含路径安全、进程流、协议交互、认证状态、错误恢复等细节，适合在理解基础模式后再深入。

## 常见误区

不要把 `registry.ts` 理解成唯一的 runtime 注册入口。根据当前片段，`App.ts` 用 `import.meta.glob('@/controllers/*Ctr.ts')` 实际加载 controller；`registry.ts` 更重要的作用是生成并导出 `DesktopIpcServices` 类型，保持 renderer IPC 类型完整。

不要以为所有 public 方法都会暴露给 renderer。只有加了 `@IpcMethod()` 的方法才会注册到 `ipcMain.handle`。没有 `@IpcMethod()` 的方法可能只是内部 helper、快捷键 handler 或生命周期 hook。

不要忽略 `static override readonly groupName`。IPC channel 的前缀来自它；如果新增 controller 没有定义 `groupName`，类型创建和 service 创建逻辑会报错，renderer 也无法按预期调用。

不要把 `beforeAppReady()` 和 `afterAppReady()` 当成普通 IPC 方法。它们由 `App.makeAppReady()` 主动调用，用于初始化代理、主题监听、通知、自动刷新、自动连接等启动流程，不是 renderer 直接调用的 API。

不要在 controller 里写 React/UI 逻辑。controller 的职责是 main process 能力封装；页面状态、组件、交互应在 renderer/features/store/services 层处理。

不要绕过安全边界随意开放 Node 能力。像 `LocalFileCtr`、`ShellCommandCtr`、`HeterogeneousAgentCtr` 这类 controller 能读写文件、执行命令、启动子进程，必须关注路径校验、参数校验、权限提示、错误返回和日志记录。

不要认为 IPC 只能传一个参数。当前 `packages/electron-client-ipc/src/ipc.ts` 的 Proxy 包装主要按 `payload?: unknown` 调用，一个 method 多参数虽然 main 侧 `ipcMain.handle` 支持 `...args`，但 renderer Proxy 默认只传一个 payload。新增 API 时更稳妥的模式是传一个对象参数。

不要混淆 controller 和 service。controller 面向 renderer IPC，是入口层；`apps/desktop/src/main/services` 更偏 main process 内部 service。controller 可以调用 service，但不应该把所有复杂实现都塞进 IPC 方法里。
