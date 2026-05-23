# 目录：apps/desktop

## 它负责什么

`apps/desktop` 是 LobeHub 的 Electron 桌面端应用外壳。它不重新实现一套完整业务前端，而是把仓库主应用里的 SPA 渲染层装进 Electron，同时补上桌面环境特有的能力：窗口管理、系统菜单、托盘、全局快捷键、自动更新、文件访问、本地协议、屏幕捕获、CLI 嵌入、MCP 安装、异构 Agent、系统通知、网络代理等。

从架构上看，这里主要分三层：Electron Main Process 位于 `apps/desktop/src/main`，负责生命周期和系统资源；Preload 位于 `apps/desktop/src/preload`，通过 `contextBridge` 向渲染进程暴露受控 API；Renderer 入口由 `apps/desktop/index.html`、`apps/desktop/popup.html`、`apps/desktop/overlay.html` 指向仓库里的 SPA 或桌面专用 overlay 代码。也就是说，`apps/desktop` 更像“桌面运行时 + 打包工程 + 原生能力适配层”，而不是普通页面目录。

## 直接子目录地图

`apps/desktop/src` 是核心源码目录，下面按运行位置继续拆分。`src/main` 是主进程代码，包含 `core`、`controllers`、`services`、`menus`、`modules`、`utils`、`const`、`locales` 等区域；`src/preload` 是主进程和渲染进程之间的安全桥；`src/overlay` 是屏幕捕获/窗口选择相关的独立渲染界面；`src/common` 放桌面端主进程、预加载、渲染层都可能复用的常量，例如路由定义。

`apps/desktop/build` 放图标、macOS entitlement、Windows 安装器图片等打包素材。`apps/desktop/resources` 放运行时资源，例如 `splash.html`、`error.html`、托盘图标，以及多语言资源目录 `resources/locales`。`apps/desktop/scripts` 是辅助脚本，包含托盘模板生成、agent-browser 下载、i18n 工作流和更新测试脚本。`apps/desktop/stubs` 提供桌面应用独立构建时需要的 workspace stub 包。根目录下的 `electron.vite.config.ts`、`electron-builder.mjs`、`package.json`、`tsconfig.json`、`vitest.config.mts` 是构建、打包、依赖和测试的主要配置入口。

## 关键入口

桌面端 Node 入口由 `apps/desktop/package.json` 的 `main` 指向构建后的 `./dist/main/index.js`，源码对应 `apps/desktop/src/main/index.ts`。这个文件很薄，只创建 `App`，执行 `fixPath()`，然后调用 `app.bootstrap()`。真正的主进程编排集中在 `apps/desktop/src/main/core/App.ts`。

渲染入口有三个 HTML。`apps/desktop/index.html` 加载主桌面 SPA，脚本指向 `src/spa/entry.desktop.tsx`；`apps/desktop/popup.html` 加载弹窗 SPA，脚本指向 `src/spa/entry.popup.tsx`；`apps/desktop/overlay.html` 加载桌面 overlay，脚本指向 `apps/desktop/src/overlay/entry.tsx`。这些入口通过 `apps/desktop/electron.vite.config.ts` 的 renderer input 注册为 `main`、`popup`、`overlay` 三个构建入口。

Preload 入口是 `apps/desktop/src/preload/index.ts`。它调用 `setupElectronApi()` 暴露 `window.electron`、`window.electronAPI`、`window.lobeEnv`，并在 `DOMContentLoaded` 后安装路由拦截逻辑。IPC 的渲染侧调用最终走 `apps/desktop/src/preload/invoke.ts`、`streamer.ts`，主进程侧能力由 `apps/desktop/src/main/controllers` 下的控制器提供。

## 主流程位置

启动主流程在 `apps/desktop/src/main/core/App.ts`。构造阶段会初始化 `StoreManager`、`RendererUrlManager`、`LocalFileProtocolManager`，注册 `app://` 一类自定义协议，扫描并加载 `controllers/*Ctr.ts` 与 `services/*Srv.ts`，创建 `I18nManager`、`BrowserManager`、`MenuManager`、`UpdaterManager`、`ShortcutManager`、`TrayManager`、`StaticFileServerManager`、`ProtocolManager`、`ToolDetectorManager`、`ScreenCaptureManager` 等管理器。

`bootstrap()` 是运行期主线：先申请单实例锁，然后启动 IPC server，等待 Electron app ready，生成 CLI wrapper，初始化 i18n 与菜单，启动静态文件管理器、全局快捷键、浏览器窗口、托盘和更新器，最后注册窗口关闭、激活等 Electron 生命周期事件。窗口创建和 URL 加载主要看 `apps/desktop/src/main/core/browser` 相关代码；菜单看 `apps/desktop/src/main/menus` 和 `core/ui/MenuManager`；托盘看 `core/ui/TrayManager`；快捷键看 `core/ui/ShortcutManager`；协议和静态资源看 `core/infrastructure/ProtocolManager`、`RendererUrlManager`、`StaticFileServerManager`、`LocalFileProtocolManager`。

桌面能力的业务入口主要在 `apps/desktop/src/main/controllers`。例如 `AuthCtr.ts`、`BrowserWindowsCtr.ts`、`CliCtr.ts`、`GatewayConnectionCtr.ts`、`HeterogeneousAgentCtr.ts`、`LocalFileCtr.ts`、`McpCtr.ts`、`ScreenCaptureCtr.ts`、`ShellCommandCtr.ts`、`ToolDetectorCtr.ts`、`UpdaterCtr.ts` 等。`apps/desktop/src/main/controllers/registry.ts` 维护了类型层面的 controller IPC 构造器列表，`controllers/index.ts` 定义 `ControllerModule`、`IpcMethod`、快捷键装饰器和协议处理装饰器。

## 推荐阅读顺序

第一步读 `apps/desktop/package.json`，先理解可用脚本、Electron 版本、桌面端依赖和打包命令。第二步读 `apps/desktop/electron.vite.config.ts`，确认 main、preload、renderer 三套构建配置，以及 `index.html`、`popup.html`、`overlay.html` 如何进入不同渲染入口。

第三步读 `apps/desktop/src/main/index.ts` 和 `apps/desktop/src/main/core/App.ts`，这是理解桌面端生命周期的核心。第四步读 `apps/desktop/src/main/controllers/index.ts`、`apps/desktop/src/main/controllers/registry.ts`，再选择几个代表性控制器，如 `ScreenCaptureCtr.ts`、`LocalFileCtr.ts`、`UpdaterCtr.ts`，观察 IPC 如何把渲染层请求落到主进程能力。

第五步读 `apps/desktop/src/preload/index.ts`、`apps/desktop/src/preload/electronApi.ts`、`apps/desktop/src/preload/invoke.ts`，理解安全桥暴露了哪些全局对象。最后再读 `apps/desktop/src/overlay/entry.tsx` 和 `ScreenCaptureOverlay.tsx`，它们代表桌面端区别于 Web SPA 的独立 UI 流程。

## 常见误区

不要把 `apps/desktop` 当成完整前端页面目录。主聊天、设置、路由页面大多仍在仓库根部的 `src/spa`、`src/routes`、`src/features` 中，桌面目录只是选择 `entry.desktop.tsx` 或 `entry.popup.tsx` 作为渲染入口，并提供 Electron 外壳能力。

不要绕过 preload 直接让渲染层访问 Electron 或 Node API。当前结构通过 `contextBridge` 暴露 `electronAPI.invoke`、`onStreamInvoke`、`onScreenCaptureSession` 等受控接口，这是桌面端安全边界。

不要只改一个入口或一套配置。桌面端同时有主窗口、popup、overlay 三个 renderer input，且开发服务器还有 HTML rewrite 逻辑；涉及路由、资源路径、构建 base 时，需要同时考虑深层 `/popup/...` 路径和 `app://` 协议下的资源解析。

不要认为 `controllers/registry.ts` 是唯一运行时注册来源。根据当前片段推断，`App` 构造函数使用 `import.meta.glob('@/controllers/*Ctr.ts', { eager: true })` 加载控制器，而 `registry.ts` 更偏类型合成和 IPC 类型导出依据；判断实际运行行为应以 `App.ts` 的加载逻辑为准。
