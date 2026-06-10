# 目录：packages/desktop/src

## 它负责什么

`packages/desktop/src` 是 AionUi 桌面端的核心源码目录，整体是一个 Electron + React 应用。它同时承载三类运行环境的代码：Electron main process、preload 隔离桥、renderer 前端界面，以及跨环境共享的配置、类型、适配器和工具。

从结构看，这个目录不是单纯的前端目录，而是桌面应用的“应用层总入口”。`src/index.ts` 负责 Electron 主进程启动、窗口创建、后端生命周期、IPC 注册、托盘/菜单/更新等桌面能力；`src/preload` 负责把受控 API 暴露给渲染进程；`src/renderer` 负责 React UI、页面路由、主题、i18n、API 调用和用户交互；`src/common` 放置 main 与 renderer 都可能复用的抽象，例如配置服务、平台服务、adapter bridge、模型 API 封装、主题解析和通用类型。

根据当前片段推断，这个桌面端还会启动或连接一个本地后端运行时。依据是 `src/index.ts` 中存在 `BackendLifecycleManager`、`get-backend-port`、`backendStartupFailed`、`runBackendMigrations`、`ensureAdminUser` 等逻辑，`preload/main.ts` 又同步读取后端端口并暴露给 renderer。

## 直接子目录地图

`common` 是共享层。它下面的 `adapter` 处理浏览器端、主进程端和 HTTP/IPC 桥接，例如 `browser.ts`、`main.ts`、`ipcBridge.ts`、`httpBridge.ts`；`api` 封装多种模型供应商客户端和协议转换；`chat` 放聊天相关的解析、工具调用规范化、图片生成核心等；`config` 负责配置 key、迁移、存储、i18n 配置；`platform` 抽象 Electron/Node 平台服务；`theme` 管主题解析与迁移；`types`、`update`、`utils` 提供跨层类型和工具。

`process` 是 Electron main process 的业务层。`backend` 处理后端二进制定位和生命周期；`bridge` 集中注册应用、窗口、通知、主题、更新、反馈、WebUI 等 IPC 桥；`feedback` 处理日志采集；`pet` 是桌面宠物相关的窗口、状态机和事件桥；`services` 放自动更新服务和诊断；`startup` 放启动前后的兼容性、后端安装诊断、失败分类和退出清理；`utils` 放主进程初始化、托盘、菜单、窗口尺寸、深链、存储、GPU 恢复、缩放等支撑能力。

`preload` 是隔离桥目录。`main.ts` 是主窗口 preload，使用 `contextBridge` 暴露 `electronAPI`、后端端口、初始语言、启动失败信息，并把托盘 IPC 事件转换成 DOM 事件。`petPreload.ts`、`petHitPreload.ts`、`petConfirmPreload.ts` 分别服务桌面宠物的不同窗口或交互层。

`renderer` 是 React 渲染层。`main.tsx` 是前端启动入口，初始化 Sentry、runtime patches、adapter、配置服务、i18n、Arco、UnoCSS、主题样式、全局 providers、布局与路由。`components` 放通用 UI 和布局，`pages` 放页面级功能，`hooks` 放 React hooks 和 context，`services` 放文件、粘贴、语音、PWA 等前端服务，`api` 放 HTTP/WebSocket 客户端，`styles` 和 `theme` 放全局样式与主题资源，`pet` 放宠物窗口对应的 HTML 和 renderer 脚本。

此外，`src/index.ts` 是主进程顶层入口，`src/sentry.ts` 是 Sentry 初始化与上报辅助，`src/types.d.ts` 是全局类型声明，`src/common/electronSafe.ts` 用来安全引用 Electron 相关能力。

## 关键入口

构建入口在邻近文件 `packages/desktop/electron.vite.config.ts` 中声明。它定义 Electron Vite 的 main、preload、renderer 构建关系，配置别名 `@`、`@common`、`@renderer`、`@process`，接入 UnoCSS、Sentry、静态资源复制和 Icon Park 转换逻辑。阅读源码时应把它当作“入口索引”，因为很多路径别名和构建期行为都从这里解释。

主进程入口是 `packages/desktop/src/index.ts`。这个文件导入 Electron 的 `app`、`BrowserWindow`、`ipcMain`、`powerMonitor` 等能力，持有 `mainWindow`，创建 `BackendLifecycleManager`，注册同步 IPC：`get-backend-port`、`get-initial-language`、`get-backend-startup-failed`、`get-backend-startup-failure`。核心窗口创建逻辑在 `createWindow`，它设置窗口尺寸、标题栏、preload、`webviewTag`、启动显示时机，并在渲染加载完成后安排后端迁移等动作。

preload 主入口是 `packages/desktop/src/preload/main.ts`。它是 main 与 renderer 的安全边界，暴露 `electronAPI.emit`、`electronAPI.on`、拖拽文件路径获取、反馈日志采集、截图采集，以及后端启动状态。renderer 不应直接访问 Node/Electron API，而应通过这里暴露的接口或 `common/adapter` 体系通信。

renderer 入口是 `packages/desktop/src/renderer/main.tsx`，HTML 宿主是 `packages/desktop/src/renderer/index.html`。`main.tsx` 先初始化运行时补丁、adapter、配置服务与 i18n，再加载 Arco/UnoCSS/主题样式，最后挂载 React providers、布局和路由。这里也是理解 UI 初始化顺序、主题语言加载、运行时失败弹窗、全局状态的第一位置。

## 主流程位置

桌面启动主流程大致是：Electron 读取构建配置后进入 `src/index.ts`；主进程初始化配置、日志、桥接、后端生命周期和平台能力；后端运行时启动成功后记录端口，并通过 `ipcMain` 提供给 preload；`createWindow` 创建 `BrowserWindow`，指定 `preload/index.js`，加载 renderer 页面；`preload/main.ts` 在隔离上下文中同步取得后端端口和初始语言，并暴露到 `window`；`renderer/main.tsx` 初始化前端应用，`configService.initialize()` 先行拉取权威配置，随后加载 i18n、主题、providers、Layout 和 Router。

跨进程通信主流程分两层。底层是 Electron IPC：`preload/main.ts` 使用 `ipcRenderer.invoke` 和 `ipcRenderer.on`，`common/adapter/main.ts` 使用 `ipcMain.handle` 并广播到窗口。上层是 `common/adapter` 抽象，renderer 侧通过 `common/adapter/browser.ts`，main 侧通过 `common/adapter/main.ts`，业务代码更多应依赖 `ipcBridge`、`httpBridge` 这类封装，而不是散落直接写 IPC channel。

后端相关主流程集中在 `src/index.ts`、`process/backend`、`process/startup`、`process/utils/runBackendMigrations.ts`、`process/utils/ensureAdminUser.ts`。启动失败分类在 `process/startup/backendStartupFailure.ts` 一类文件，安装完整性和运行时资源失败会反馈到 renderer 的安装完整性弹窗逻辑。

UI 主流程集中在 `renderer/main.tsx`、`renderer/components/layout/Layout`、`renderer/components/layout/Router`、`renderer/components/layout/Sider` 和 `renderer/pages`。具体业务页面应从 Router 进入，再顺着对应 page、hooks、services、api 往下读。

桌面宠物是一个相对独立的旁路流程。主进程侧在 `process/pet`，preload 侧在 `preload/pet*.ts`，渲染侧在 `renderer/pet` 的 HTML 与脚本。它不像主窗口那样走完整 React 应用入口，而是有专门窗口和专门 IPC。

## 推荐阅读顺序

1. 先读 `packages/desktop/electron.vite.config.ts`，确认 main/preload/renderer 的构建边界、路径别名和插件行为。
2. 再读 `packages/desktop/src/index.ts`，抓住 Electron 生命周期、后端启动、窗口创建、IPC 同步数据和退出逻辑。
3. 接着读 `packages/desktop/src/preload/main.ts`，理解 renderer 能拿到哪些安全 API，以及哪些数据是启动时注入的。
4. 然后读 `packages/desktop/src/renderer/main.tsx`，看前端初始化顺序、全局 providers、样式、主题、i18n 和路由布局如何接起来。
5. 之后读 `packages/desktop/src/common/adapter`，尤其是 `browser.ts`、`main.ts`、`ipcBridge.ts`、`httpBridge.ts`，这是跨进程和本地后端通信的关键抽象。
6. 最后按专题深入：后端生命周期看 `process/backend` 与 `process/startup`；系统能力看 `process/bridge` 和 `process/utils`；UI 页面看 `renderer/pages`；主题与配置看 `common/config`、`common/theme`、`renderer/theme`。

## 常见误区

不要把 `renderer` 当成普通 Web 项目随意访问 Node.js 或 Electron API。项目约束是 renderer 不直接使用 Node 能力，跨进程能力应走 preload 或 IPC bridge。

不要在 main process 中使用 DOM 或浏览器 API。`process` 和 `src/index.ts` 属于 Electron 主进程，职责是窗口、系统能力、后端进程、托盘、菜单、更新和 IPC 注册。

不要绕过 `common/adapter` 到处新增 IPC channel。当前代码已经有 `ADAPTER_BRIDGE_EVENT_KEY`、`ipcBridge`、`httpBridge` 和 main/browser 双端适配，新增通信前应先确认是否能复用现有桥接模式。

不要把 `packages/desktop/package.json` 的版本当成用户可见版本。构建配置注释说明桌面包内版本是 workspace placeholder，真实用户版本来自仓库根 `package.json`。

不要在 UI 中硬编码用户可见文本。该项目有 i18n 配置，renderer 侧新增界面文案应走翻译 key。

不要混淆主窗口和宠物窗口。主窗口入口是 `renderer/main.tsx` 与 `preload/main.ts`；宠物相关有独立的 `preload/pet*.ts`、`renderer/pet/*.html` 和 `process/pet` 管理逻辑。

不要只读 `renderer/pages` 就判断业务链路。很多前端行为依赖 `common/config` 的初始化、后端端口注入、adapter bridge、主进程 bridge，以及 `process/startup` 的运行时状态。整体理解应从启动链路向页面链路推进。
