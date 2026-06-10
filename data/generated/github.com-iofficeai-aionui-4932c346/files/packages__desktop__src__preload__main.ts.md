# 文件：packages/desktop/src/preload/main.ts

## 一句话定位

`packages/desktop/src/preload/main.ts` 是桌面端主窗口的 Electron preload 入口，负责在启用 `contextIsolation` 的 renderer 页面和 main 进程之间建立受控通信桥，并把启动期必需的后端状态、语言状态、反馈能力、托盘事件转发能力注入到 `window` 上。

## 它暴露/定义了什么

这个文件主要通过 `contextBridge.exposeInMainWorld` 暴露两类全局对象/值。

第一类是 `window.electronAPI`，它是 renderer 可见的桌面运行时能力集合，包含：

- `emit(name, data)`：把 renderer 侧事件封装为 `{ name, data }`，通过 `ipcRenderer.invoke(ADAPTER_BRIDGE_EVENT_KEY, JSON.stringify(...))` 发送给 main 进程。
- `on(callback)`：监听 main 进程通过同一个 `ADAPTER_BRIDGE_EVENT_KEY` 发回的桥接事件，并返回取消监听函数。
- `getPathForFile(file)`：使用 Electron 的 `webUtils.getPathForFile` 从拖拽 `File` 取本地绝对路径。
- `collectFeedbackLogs()`：请求 main 进程收集并压缩反馈日志。
- `captureFeedbackScreenshot()`：请求 main 进程截取当前窗口截图。

第二类是启动期全局值：

- `window.__backendPort`
- `window.__initialLanguage`
- `window.__backendStartupFailed`
- `window.__backendStartupFailure`

这些值通过同步 IPC 从 main 进程读取，并在 renderer 初始化前暴露出来，供配置服务、HTTP bridge、i18n 和启动失败 UI 判断使用。

此外，它还定义了 `trayEvents` 列表，把来自 main 进程的托盘 IPC 事件转换成浏览器原生 `CustomEvent`，派发到 `window`。

## 谁调用它

它不是由业务代码手动 import 调用，而是由 Electron 窗口加载机制调用。根据 `packages/desktop/electron.vite.config.ts`，preload 构建入口 `index` 指向 `packages/desktop/src/preload/main.ts`；根据 `packages/desktop/src/index.ts`，主窗口创建时 `webPreferences.preload` 指向构建后的 `../preload/index.js`。因此主窗口创建后，Electron 会先执行这个 preload，再加载 renderer 页面。

renderer 侧通过 `window.electronAPI`、`window.__backendPort` 等全局字段间接使用它。典型调用方包括 `packages/desktop/src/common/adapter/browser.ts`、`packages/desktop/src/common/adapter/httpBridge.ts`、`packages/desktop/src/common/config/configService.ts`、`packages/desktop/src/renderer/components/settings/SettingsModal/contents/FeedbackReportModal.tsx`、`packages/desktop/src/renderer/pages/conversation/Workspace/hooks/useWorkspaceDragImport.ts` 和 `packages/desktop/src/renderer/components/layout/Layout.tsx`。

## 它调用谁

它直接调用 Electron preload 可用 API：`contextBridge`、`ipcRenderer`、`webUtils`。

桥接通信依赖 `packages/desktop/src/common/adapter/constant.ts` 中的 `ADAPTER_BRIDGE_EVENT_KEY`，对应 main 侧 `packages/desktop/src/common/adapter/main.ts` 里的 `ipcMain.handle(ADAPTER_BRIDGE_EVENT_KEY, ...)` 和 `win.webContents.send(ADAPTER_BRIDGE_EVENT_KEY, ...)`。

启动信息读取调用 main 侧在 `packages/desktop/src/index.ts` 注册的同步 IPC channel：`get-backend-port`、`get-initial-language`、`get-backend-startup-failed`、`get-backend-startup-failure`。

反馈功能调用 main 侧 `packages/desktop/src/process/bridge/feedbackBridge.ts` 注册的 `feedback:collect-logs` 和 `feedback:capture-screenshot`。

托盘事件来自 main/process 工具层，例如 `packages/desktop/src/process/utils/tray.ts` 会向主窗口发送 `tray:navigate-to-guid`、`tray:navigate-to-conversation` 等事件。

文件顶部还 import `@sentry/electron/preload`。它的作用是让 renderer SDK 走 Sentry 的 IPC 通道；根据文件注释，这是为了避免 sandbox preload 在运行时从 `node_modules` 解析依赖，并减少 DevTools Network 面板里的异常请求噪音。

## 核心流程

启动流程可以概括为四步。

第一步，preload 被 Electron 在主窗口页面之前执行，并加载 `@sentry/electron/preload`，完成 Sentry renderer/main 通道的预挂接。

第二步，调用 `contextBridge.exposeInMainWorld('electronAPI', ...)` 注入桌面能力。这里没有把完整 `ipcRenderer` 暴露给 renderer，而是只暴露受控方法，这是 Electron 安全模型下的关键边界。

第三步，通过 `ipcRenderer.sendSync(...)` 同步读取后端端口、初始语言、后端启动失败标记和失败详情，然后暴露为 `window.__backendPort` 等全局值。同步读取的目的，是确保 renderer 早期模块初始化时就能拿到这些值；例如 HTTP 请求基地址需要知道 aioncore 端口，i18n 初始化需要知道初始语言。

第四步，注册托盘事件监听。main 进程通过 `webContents.send(channel, payload)` 发来的托盘指令，被 preload 转换为 `window.dispatchEvent(new CustomEvent(channel, { detail }))`。这样 renderer 的 React 组件只需要监听 DOM 事件，而不需要直接接触 Electron IPC。

## 关键函数的高层作用

`electronAPI.emit` 是 renderer 到 main 的主要桥接出口。它把业务事件名和数据序列化为 JSON，经由 `ADAPTER_BRIDGE_EVENT_KEY` 交给 main 侧 adapter，再由 `@office-ai/platform` 的 `bridge` 体系分发。这里的错误处理只记录并重新抛出 IPC 错误，不吞掉异常。

`electronAPI.on` 是 main 到 renderer 的桥接入口。它监听同一个 `ADAPTER_BRIDGE_EVENT_KEY`，把收到的 IPC payload 包装成 `{ event, value }` 交给回调。真正的 JSON 解析发生在 `packages/desktop/src/common/adapter/browser.ts`，该文件会把 `value` 解析成 `{ name, data }` 并转交给 renderer 侧 bridge emitter。

`getPathForFile` 是拖拽导入的桌面增强能力。浏览器标准 `File` 出于安全限制通常不给真实路径，而 Electron 的 `webUtils.getPathForFile` 可以在 preload 安全边界内取到路径，再交给 renderer 做本地文件/目录导入。

`collectFeedbackLogs` 和 `captureFeedbackScreenshot` 是反馈模块的窄接口。preload 只转发 IPC，不做日志查找、压缩或截图实现，实际逻辑在 main/process 侧。

`trayEvents` 循环是 IPC 到 DOM 事件的适配层。它把托盘菜单等 OS 入口转换成 renderer 内部可以统一处理的导航或操作事件，降低 React 组件对 Electron API 的直接依赖。

## 修改风险

最大风险是安全边界退化。这个文件运行在 preload，天然靠近 `ipcRenderer` 和本地能力；如果为了方便把任意 IPC channel、原始 `ipcRenderer`、文件系统能力或未校验的函数暴露给 `window`，会扩大 renderer 被 XSS 或第三方脚本利用后的攻击面。

第二个风险是桥接协议不兼容。`electronAPI.emit/on` 与 `packages/desktop/src/common/adapter/browser.ts`、`packages/desktop/src/common/adapter/main.ts` 共同约定了 `ADAPTER_BRIDGE_EVENT_KEY`、JSON 字符串格式以及 `{ name, data }` 结构。改字段名、改序列化方式、改回调参数形状，都会影响平台 bridge 的双向通信。

第三个风险是启动时序。`__backendPort` 等值使用 `sendSync` 是有意为之：renderer 早期配置代码依赖它们。如果改成异步获取，需要同步调整所有早期读取方，否则可能退回默认端口、请求错误服务，或无法正确展示后端启动失败状态。反过来，新增同步 IPC 也要谨慎，因为 main 侧未及时注册 handler 或处理过慢会阻塞页面启动。

第四个风险是事件生命周期。`electronAPI.on` 返回了取消监听函数，调用方如果忽略清理可能造成重复订阅；托盘事件监听则在 preload 生命周期内常驻，新增事件时要确保 renderer 侧有对应消费逻辑，并注意 payload 结构稳定。

第五个风险是类型漂移。`packages/desktop/src/common/types/platform/electron.ts` 中声明了 `ElectronBridgeAPI` 和 `Window` 扩展。修改 preload 暴露字段后，应同步更新类型，否则 TypeScript 层和运行时行为会不一致。当前片段中 `emit`、`on` 参数仍有 `any`，根据当前片段推断这是历史遗留的宽类型边界；收紧类型时要同时覆盖 main adapter、browser adapter 和 renderer 调用点，避免只改一侧导致运行时协议断裂。
