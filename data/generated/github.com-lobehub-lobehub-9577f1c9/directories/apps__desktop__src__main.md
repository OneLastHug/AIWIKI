# 目录：apps/desktop/src/main

## 它负责什么

`apps/desktop/src/main` 是 LobeHub Desktop 的 Electron Main Process 代码区，负责桌面端应用的进程生命周期、系统能力接入、窗口管理、托盘菜单、全局快捷键、自定义协议、IPC 服务端、更新器、文件访问、CLI 嵌入、屏幕捕获、MCP/工具探测等偏“原生桌面”的能力。

它不是普通 React 页面目录。桌面渲染层主要复用 `src/` 下的 Web/SPA 代码，`apps/desktop/src/preload` 负责把受控 API 暴露给 renderer，而这里的 `main` 是 Electron 主进程的调度中心：创建窗口、注册系统事件、处理 renderer 发来的 IPC 调用，并把业务请求分发到各类 controller、service、manager 或 module。

## 直接子目录地图

`apps/desktop/src/main/core` 是核心运行框架，包含 `App.ts`、窗口管理、基础设施 manager、UI manager。这里是理解启动流程、浏览器窗口、协议、存储、i18n、更新、快捷键、托盘的主入口。

`apps/desktop/src/main/controllers` 是 IPC controller 层。每个 `*Ctr.ts` 通常代表一组 renderer 可调用的桌面能力，例如 `AuthCtr.ts`、`BrowserWindowsCtr.ts`、`McpCtr.ts`、`ShellCommandCtr.ts`、`ScreenCaptureCtr.ts`、`UpdaterCtr.ts`。`controllers/index.ts` 提供 `ControllerModule`、`IpcMethod`、快捷键和协议装饰器；`controllers/registry.ts` 汇总 controller 构造器与类型。

`apps/desktop/src/main/services` 是主进程内的 service 层，当前能看到文件服务、搜索服务、gateway 连接服务等。它比 controller 更偏可复用业务能力，controller 可通过 `app.getService(...)` 取用。

`apps/desktop/src/main/modules` 放相对独立的功能模块，例如 `cliEmbedding`、`heterogeneousAgent`、`networkProxy`、`openInApp`、`screenCapture`、`toolDetectors`、`updater`。这些模块不是统一入口层，而是供 `App`、controller 或 manager 调用的功能实现区。

`apps/desktop/src/main/menus` 保存菜单定义与实现，和 `core/ui/MenuManager.ts` 配合，负责应用菜单、上下文菜单或托盘菜单相关逻辑。

`apps/desktop/src/main/libs` 根据当前片段推断是第三方或协议集成的封装区，依据是其下有 `acp`、`mcp` 子目录，且主进程 controller 中存在 `McpCtr.ts`、`McpInstallCtr.ts`。

`apps/desktop/src/main/const` 保存主进程常量，例如目录、环境、协议、store、theme。

`apps/desktop/src/main/types` 保存主进程局部类型，例如 protocol、store 类型。

`apps/desktop/src/main/utils` 是通用工具层，包含文件系统、git、HTTP headers、日志、MIME、网络 fetch、路径、权限、协议和 IPC 工具。

`apps/desktop/src/main/locales` 是主进程 i18n 资源。它和 `core/infrastructure/I18nManager.ts` 相关。

`apps/desktop/src/main/__mocks__`、各层 `__tests__` 是测试与 mock 支撑，不是运行时主流程的一部分。

## 关键入口

最顶层入口是 `apps/desktop/src/main/index.ts`。它做的事很少：导入 `fix-path`，创建 `new App()`，然后调用 `app.bootstrap()`。因此阅读主进程时不要在 `index.ts` 停留太久，核心都在 `apps/desktop/src/main/core/App.ts`。

`apps/desktop/src/main/core/App.ts` 是总装配器。构造函数阶段会初始化 `StoreManager`、`RendererUrlManager`、`LocalFileProtocolManager`，注册 Electron privileged protocol scheme，动态加载 `controllers/*Ctr.ts` 和 `services/*Srv.ts`，创建 IPC server 事件表，然后初始化 `I18nManager`、`BrowserManager`、`MenuManager`、`UpdaterManager`、`ShortcutManager`、`TrayManager`、`StaticFileServerManager`、`ProtocolManager`、`ToolDetectorManager`、`ScreenCaptureManager` 等核心对象。

`apps/desktop/src/main/controllers/index.ts` 是 controller 模式的关键定义。`ControllerModule` 继承 `IpcService`，每个 controller 接收 `App` 实例；`IpcMethod` 用于声明 IPC 方法；`shortcut(...)` 和 `createProtocolHandler(...)` 会把 controller 方法登记到 `IoCContainer`，随后由 `App.addController` 收集到快捷键表或协议处理表。

`apps/desktop/src/main/controllers/registry.ts` 是类型和服务集合的显式注册表。需要注意：`App.ts` 运行时使用 `import.meta.glob('@/controllers/*Ctr.ts', { eager: true })` 动态加载 controller；`registry.ts` 则更像是类型汇总和 IPC client 类型生成/约束的中心。两者角色相近但不完全等价。

## 主流程位置

启动主流程在 `apps/desktop/src/main/index.ts` 到 `apps/desktop/src/main/core/App.ts` 的 `bootstrap`。流程大致是：修复 PATH，构造 `App`，申请单实例锁，启动 `ElectronIPCServer`，执行 `makeAppReady()`，生成 CLI wrapper，初始化 i18n、菜单、静态文件服务、全局快捷键、浏览器窗口、托盘、更新器，最后处理 pending protocol URL。

窗口主流程在 `apps/desktop/src/main/core/browser`。`BrowserManager.ts` 管多窗口创建和显示，`Browser.ts` 更接近单个窗口封装，`WindowStateManager.ts` 管窗口尺寸位置状态，`WindowThemeManager.ts` 处理窗口主题。`App.bootstrap()` 中的 `browserManager.initializeBrowsers()` 是桌面窗口真正进入可见状态的重要位置。

IPC 主流程在 `apps/desktop/src/main/controllers`、`apps/desktop/src/main/utils/ipc` 和 `App.initializeServerIpcEvents()`。从 renderer 发起的调用经 preload 暴露的 IPC API 进入 main process，再分发到对应 controller 方法。新增桌面能力通常从 controller 入手，而不是直接改 renderer。

协议和资源加载主流程在 `core/infrastructure`。`RendererUrlManager.ts` 决定开发/生产环境加载 renderer 的 URL 策略；`ProtocolManager.ts` 处理自定义协议分发；`LocalFileProtocolManager.ts` 负责本地文件协议；`StaticFileServerManager.ts` 管本地静态文件服务。`App` 构造阶段会先配置和注册协议，`bootstrap` 后期再处理待处理的协议 URL。

系统 UI 主流程在 `apps/desktop/src/main/core/ui` 与 `apps/desktop/src/main/menus`。菜单由 `MenuManager` 初始化，全局快捷键由 `ShortcutManager` 初始化，托盘由 `TrayManager` 和 `Tray.ts` 管理。

功能扩展主流程多在 `apps/desktop/src/main/modules`。例如工具检测在 `modules/toolDetectors` 定义 detector，`App.registerBuiltinToolDetectors()` 统一注册到 `ToolDetectorManager`；更新相关实现分散在 `modules/updater` 与 `core/infrastructure/UpdaterManager.ts`；屏幕捕获同时有 `modules/screenCapture` 和 `ScreenCaptureCtr.ts`。

## 推荐阅读顺序

1. 先读 `apps/desktop/src/main/index.ts`，确认主入口只有 `App.bootstrap()`。
2. 再读 `apps/desktop/src/main/core/App.ts`，重点看 constructor、`bootstrap`、`makeAppReady`、`addController`、`initializeServerIpcEvents`。
3. 接着读 `apps/desktop/src/main/controllers/index.ts` 和 `apps/desktop/src/main/controllers/registry.ts`，理解 controller、IPC、快捷键、协议 handler 的组织方式。
4. 然后按主流程读 `apps/desktop/src/main/core/browser`、`apps/desktop/src/main/core/infrastructure`、`apps/desktop/src/main/core/ui`。
5. 最后根据具体能力跳到 `controllers/*Ctr.ts` 与 `modules/*`，例如想看屏幕捕获就读 `ScreenCaptureCtr.ts`、`modules/screenCapture`；想看 MCP 就读 `McpCtr.ts`、`McpInstallCtr.ts`、`libs/mcp`。

## 常见误区

不要把 `apps/desktop/src/main` 当作 UI 页面目录。它运行在 Electron 主进程，不能直接使用 React hooks 或浏览器 DOM API；UI 页面主要在 renderer 侧。

不要只改 `controllers/registry.ts` 就以为完成运行时注册。根据当前片段，`App.ts` 运行时通过 `import.meta.glob('@/controllers/*Ctr.ts')` 自动加载 `*Ctr.ts`，而 `registry.ts` 更偏类型汇总。新增 controller 时通常还要关注 IPC 类型、preload/renderer service 是否能访问到。

不要绕过 `ControllerModule`、`IpcMethod`、service/manager 体系直接在入口里堆逻辑。这个目录的架构是 `App` 负责装配，controller 负责 IPC 边界，service/module/manager 负责具体能力。

不要忽略 `beforeAppReady` 和 `afterAppReady` 的时机。Electron 的很多能力必须在 `app.whenReady()` 前或后注册，例如 protocol、command line switch、globalShortcut、window 初始化各有时序要求。

不要把协议、静态文件服务、本地文件协议混为一谈。`RendererUrlManager`、`ProtocolManager`、`LocalFileProtocolManager`、`StaticFileServerManager` 分别处理不同层面的加载与访问问题，排查资源加载问题时应先定位是哪一类路径。

不要在主进程能力里假设所有平台行为一致。`App.ts` 已经区分 Windows、Linux、macOS 的退出、dock、托盘等行为；新增桌面功能时需要考虑平台差异。
