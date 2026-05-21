# 目录：apps/desktop/src

## 它负责什么

`apps/desktop/src` 是 LobeHub Desktop 的 Electron 端源码入口，负责把 Web/SPA 形态的 LobeHub 包装成桌面应用。它主要处理四类事情：Electron main process 生命周期、桌面窗口与系统能力、preload 安全桥接、以及独立的截图 overlay 渲染入口。

从架构上看，它不是重新实现一套聊天前端，而是让桌面壳承载仓库主应用的 renderer 代码：主窗口加载 `/`，开发工具窗口加载 `/desktop/devtools`，弹窗会加载 `/popup/...`，截图层加载 `/overlay`。桌面专属能力通过 IPC 暴露给 renderer，例如窗口控制、系统菜单、快捷键、自动更新、本地文件、Shell/Git/MCP、网络代理、屏幕截图、异构 agent、设备网关等。

## 关键组成

`apps/desktop/src/main` 是 Electron 主进程代码。入口是 `main/index.ts`，只做三件事：创建 `App`、调用 `fixPath()`、执行 `app.bootstrap()`。真正的启动协调器是 `main/core/App.ts`，它初始化 `StoreManager`、协议管理器、控制器、服务、i18n、窗口、菜单、快捷键、托盘、更新器、工具探测器、截图管理器等。

`main/controllers` 是 renderer 调用桌面能力的 IPC 控制器层。所有控制器继承 `ControllerModule`，通过 `static groupName` 定义通道前缀，通过 `@IpcMethod()` 暴露方法。例如 `ScreenCaptureCtr` 暴露 `screenCapture.previewWindow`、`screenCapture.previewRect`、`screenCapture.submit`；`BrowserWindowsCtr` 暴露窗口打开、最小化、最大化、多实例窗口、路由拦截等能力。`controllers/registry.ts` 汇总控制器构造器，并导出 `DesktopIpcServices` 类型，供 renderer 侧获得类型提示。

`main/core/browser` 是窗口系统。`BrowserManager` 管理所有窗口实例，静态窗口来自 `appBrowsers.ts`，包括 `app` 主窗口和 `devtools` 窗口；动态窗口来自 `windowTemplates`，包括单聊窗口 `chatSingle` 和话题弹窗 `topicPopup`。`Browser` 封装单个 `BrowserWindow`，统一配置 `preload/index.js`、`contextIsolation: true`、窗口主题、状态恢复、URL 加载、外链拦截和事件处理。

`main/core/infrastructure` 是基础设施层。`RendererUrlManager` 决定 renderer 从开发服务器还是生产静态资源加载，并把 `/overlay`、`/popup`、普通 SPA 路由映射到不同 HTML 入口。`ProtocolManager` 注册自定义协议并处理冷启动、macOS `open-url`、二次启动 URL。`StoreManager` 基于 `electron-store` 保存桌面配置。还有本地文件协议、后端代理协议、静态文件服务、自动更新、工具探测等管理器。

`main/services` 是更偏业务/能力封装的服务层，例如文件、文件搜索、内容搜索、设备网关连接。控制器一般调用 `this.app.xxxManager` 或 `this.app.getService(...)`，把 IPC 请求转成实际桌面操作。

`apps/desktop/src/preload` 是 renderer 与 main 之间的安全桥。`preload/index.ts` 调用 `setupElectronApi()` 和 `setupRouteInterceptors()`。`electronApi.ts` 用 `contextBridge.exposeInMainWorld` 暴露 `window.electron`、`window.electronAPI.invoke`、`window.electronAPI.onStreamInvoke`、截图 session 监听，以及 `window.lobeEnv`。`routeInterceptor.ts` 会拦截 `<a>` 点击：外链交给 `system.openExternalLink`，内部特殊路由如 `/desktop/devtools` 交给 `windows.interceptRoute`。

`apps/desktop/src/overlay` 是截图选择层的独立 React 入口。`overlay/entry.tsx` 渲染 `ScreenCaptureOverlay`。该组件监听 `window.electronAPI.onScreenCaptureSession` 获取窗口和屏幕信息，支持拖拽选区、窗口高亮、预览截图、提交截图到主窗口、监听上传状态，并通过 `screenCapture.*` IPC 与主进程的 `ScreenCaptureManager` 协作。

`apps/desktop/src/common` 目前包含共享路由拦截配置。`common/routes.ts` 定义 `interceptRoutes`，例如 `/desktop/devtools` 应打开 `devtools` 窗口。preload 和 main 控制器都会引用它，避免两边规则不一致。

## 上下游关系

上游入口主要来自 Electron 运行时和构建配置。`apps/desktop/package.json` 的 `main` 指向 `dist/main/index.js`，开发时通过 `electron-vite dev` 启动。`electron.vite.config.ts` 分别构建 main、preload、renderer，并配置三个 renderer HTML 入口：`index.html`、`overlay.html`、`popup.html`。

下游一侧是仓库主应用 renderer。桌面窗口加载的页面实际来自根项目的 SPA/React 代码，桌面专属服务则在根目录 `src/services/electron/*` 中调用 `window.electronAPI.invoke(...)`，再到 `apps/desktop/src/main/controllers/*Ctr.ts`。这就是桌面能力从前端到主进程的主链路。

另一个重要下游是共享包：`@lobechat/electron-client-ipc` 提供事件和参数类型，`@lobechat/electron-server-ipc` 提供 server IPC 能力，`@lobechat/desktop-bridge` 提供桌面常量和路由变体。根据当前片段推断，桌面端用这些包把 main、preload、renderer 三侧的类型边界收紧，避免通道名和参数散落成裸字符串。

## 运行/调用流程

启动流程是：Electron 加载 `dist/main/index.js`，执行 `new App()`。构造阶段会注册协议 scheme、加载所有 `*Ctr.ts` 控制器和 `*Srv.ts` 服务、注册 IPC 方法、初始化各种 manager，并配置 renderer 加载策略。之后 `bootstrap()` 申请单实例锁，启动 IPC server，等待 `app.whenReady()`，初始化 i18n、菜单、静态文件服务、全局快捷键、浏览器窗口、托盘和自动更新，最后处理启动期间积压的协议 URL。

窗口加载流程是：`BrowserManager.initializeBrowsers()` 根据 `appBrowsers` 创建主窗口等静态窗口；`Browser` 创建 `BrowserWindow` 时挂上 `preload/index.js`；`RendererUrlManager.buildRendererUrl(path)` 把业务路径拼成开发服务器 URL 或生产 `app://` 协议 URL；页面加载完成后，renderer 可以通过 preload 暴露的 `window.electronAPI.invoke` 调用主进程。

IPC 调用流程是：控制器方法加 `@IpcMethod()`，`IpcService` 在实例化时读取元数据并注册 `groupName.methodName` 通道；renderer 调用如 `screenCapture.previewRect`；`ipcMain.handle` 收到请求后用 `AsyncLocalStorage` 保存当前 IPC 上下文，再执行控制器方法。需要知道调用来源窗口时，控制器可通过 `getIpcContext()` 取得 sender，再映射回窗口 identifier。

截图流程比较典型：快捷键或窗口控制器触发 `screenCaptureManager.startSession()`；主进程打开 overlay 窗口并发送 `screenCaptureSession`；`ScreenCaptureOverlay` 让用户选窗口或选区；用户预览时调用 `screenCapture.previewWindow` 或 `screenCapture.previewRect`；提交时调用 `screenCapture.submit`；上传状态由主窗口上报给 main，再转发给 overlay 更新按钮状态。

## 小白阅读顺序

1. 先看 `apps/desktop/src/main/index.ts`，建立“入口很薄，核心在 `App`”的印象。
2. 再看 `apps/desktop/src/main/core/App.ts`，重点读 constructor 和 `bootstrap()`，理解桌面应用生命周期。
3. 看 `apps/desktop/src/main/appBrowsers.ts`，弄清楚有哪些固定窗口和动态窗口模板。
4. 看 `apps/desktop/src/main/core/browser/BrowserManager.ts` 与 `Browser.ts`，理解窗口如何创建、复用、跳转、广播。
5. 看 `apps/desktop/src/main/controllers/index.ts`、`registry.ts` 和一个具体控制器，例如 `BrowserWindowsCtr.ts` 或 `ScreenCaptureCtr.ts`，理解 IPC 暴露模式。
6. 看 `apps/desktop/src/preload/electronApi.ts`、`invoke.ts`、`routeInterceptor.ts`，理解 renderer 为什么不能直接碰 Electron API，而是通过 context bridge。
7. 最后看 `apps/desktop/src/overlay/ScreenCaptureOverlay.tsx`，这是一个较完整的桌面专属 UI 到 main process 的闭环案例。

## 常见误区

不要把 `apps/desktop/src` 当成完整前端应用。主聊天、设置等大部分 UI 仍在根目录 `src/` 下，桌面目录主要负责 Electron 壳、系统能力和少量独立入口。

不要以为所有窗口都加载同一个 HTML。普通主窗口走 `index.html`，截图层走 `overlay.html`，话题弹窗走 `popup.html`；`RendererUrlManager` 和 `electron.vite.config.ts` 都围绕这个多入口设计工作。

不要绕过 preload 直接在 renderer 使用 `ipcRenderer`。当前设计通过 `contextBridge` 暴露受控 API，并启用 `contextIsolation`，这是 Electron 安全边界的一部分。

不要只改 renderer 路由而忽略桌面路由拦截。像 `/desktop/devtools` 这种路径由 `common/routes.ts`、`preload/routeInterceptor.ts`、`BrowserWindowsCtr.interceptRoute()` 共同完成，规则不一致会导致点击链接后没有打开预期窗口。

不要把 `controllers/registry.ts` 看成运行时唯一注册源。运行时 `App` 使用 `import.meta.glob('@/controllers/*Ctr.ts', { eager: true })` 自动加载控制器；`registry.ts` 更重要的作用是整理类型和服务形状，方便客户端 IPC 类型推导。

不要忽略构建层的限制。`electron.vite.config.ts` 对 main chunk、native dependency external、renderer base、SPA deep link 重写都有专门处理；看似普通的模块拆分或资源路径改动，可能会影响 Electron 生产包里的协议加载和窗口路由。
