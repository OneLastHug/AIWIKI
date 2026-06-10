# 子系统：packages/desktop/src/common/adapter

## 解决什么问题
根据当前片段推断，这个目录是桌面端的“适配层”和“通信胶水层”：把后端、Electron 主进程、Renderer、WebUI 浏览器模式之间差异很大的接口，统一成前端可以直接调用的对象和方法。它解决的不是业务逻辑本身，而是“怎么连通、怎么换协议、怎么做数据形状转换”的问题。

这里最核心的价值有三点：一是把 `@office-ai/platform` 的 bridge 能力包装成桌面端自己的 API；二是把 HTTP、IPC、WebSocket 三种传输方式收敛到一套调用习惯；三是把后端返回的 snake_case、嵌套结构或平台对象，映射成 `packages/desktop/src/common/types`、`packages/desktop/src/common/chat`、`packages/desktop/src/renderer` 里更适合 UI 消费的类型。

## 相关目录和文件
这个目录下大致分成三类文件：

`main.ts`、`browser.ts`、`httpBridge.ts`、`ipcBridge.ts`、`registry.ts`、`constant.ts`：负责桥接、注册、通信和运行时分发。  
`apiModelMapper.ts`、`fileSnapshotMapper.ts`、`searchMapper.ts`、`teamMapper.ts`、`workspaceMapper.ts`：负责后端数据到前端模型的转换。  
`constant.ts` 提供事件键名，例如 `ADAPTER_BRIDGE_EVENT_KEY`、`SHOW_OPEN_REQUEST_EVENT`，被 preload、renderer 和主进程共同引用。

从引用关系看，`packages/desktop/src/index.ts`、`packages/desktop/src/preload/main.ts`、`packages/desktop/src/process/*`、`packages/desktop/src/renderer/*` 都在大量使用这里的导出；同时它还依赖 `@office-ai/platform`、Electron API、以及后端的 HTTP/WebSocket 服务。

## 核心对象
最重要的对象是 `ipcBridge.ts` 里导出的分组式 API，例如 `application`、`dialog`、`fs`、`mcpService`、`webui`、`cron`、`extensions`、`channel`、`team` 等。它们通常表现为一组 `invoke / provider / emitter` 风格的方法，作用是让调用方不用关心底层是 IPC 还是 WebSocket。

`httpBridge.ts` 里的 `httpRequest`、`httpGet`、`httpPost`、`wsEmitter`、`stubProvider`、`stubEmitter` 也很关键。它们把“请求一个后端资源”抽象成统一入口，并且提供 `BackendHttpError`、`isBackendHttpError` 这样的错误判断能力，方便上层按错误码分支处理。

`main.ts` 负责 Electron 主进程侧的桥接初始化：维护 `BrowserWindow` 列表，处理 `bridge.adapter({...})`，把事件广播到所有窗口，并同步转发到 WebSocket 客户端。`registry.ts` 则保存 WebSocket 广播器和 bridge emitter 引用，是跨模块共享状态的小型注册表。

## 运行流程
典型流程是：启动应用后，`packages/desktop/src/index.ts` 初始化主进程适配器，`main.ts` 通过 `bridge.adapter` 把 bridge 事件绑定到 `ipcMain.handle` 和各个 `BrowserWindow`。

Renderer 侧会先加载 `browser.ts`。在 Electron 环境下，它使用 `window.electronAPI` 走 IPC；在 Web 环境下，则改为 WebSocket 连接到 `/ws`，并处理心跳、重连、登录态失效跳转等逻辑。也就是说，同一个页面代码在两种运行模式下走的传输层不同，但上层调用方式尽量一致。

当业务代码调用 `ipcBridge.ts` 暴露的方法时，实际可能被路由到主进程、后端 REST 接口，或者 WebSocket 事件流。返回的数据再通过各类 mapper 转成前端类型，减少页面层对后端结构的直接依赖。

## 上下游依赖
上游主要是三类来源：`@office-ai/platform` 提供桥能力；Electron 提供 `ipcMain`、`BrowserWindow` 等主进程能力；后端 API 和 WebSocket 提供真正的数据与事件。

下游则非常广，几乎覆盖桌面端所有需要系统能力或后端数据的页面与 hook。比如文件树、工作区、会话、扩展、MCP、Cron、系统设置、预览、主题、通知等模块，都从这里拿类型、拿请求器或拿桥对象。`searchMapper.ts`、`workspaceMapper.ts` 这类文件还会进一步服务 `renderer` 中的搜索、文件浏览和会话页面。

## 修改时最容易踩的坑
第一，别把 `main.ts`、`browser.ts`、`httpBridge.ts` 里的职责混掉。一个是主进程广播，一个是渲染端运行时适配，一个是 HTTP/WS 请求抽象，混写后很容易出现“在错误进程引用 Electron API”或“WebUI 模式下路径不对”的问题。

第二，`ipcBridge.ts` 很大，改动前要先确认调用方分布。很多导出不仅是类型，还承载方法命名和事件约定，改一个字段名会连带影响 renderer、process、preload 和测试。

第三，mapper 里最危险的是数据形状变化。这里大量把后端原始字段转成前端对象，若后端字段名、枚举值或空值语义变化，页面可能不报错但展示错位。

第四，`httpBridge.ts` 对错误和日志有专门处理，尤其是 `BackendHttpError`、敏感字段脱敏、payload 大小限制和 WebUI 同源策略。修改时不能只看“请求成功”，还要考虑失败路径和跨模式兼容。

## 推荐阅读顺序
1. 先看 `constant.ts`，弄清楚桥接事件键。  
2. 再看 `registry.ts`，理解共享注册表如何保存 emitter 和 WebSocket 广播器。  
3. 然后看 `main.ts`，把主进程广播和窗口管理串起来。  
4. 接着看 `browser.ts`，理解 Electron 与 WebUI 两种运行模式如何切换。  
5. 再看 `httpBridge.ts`，掌握 HTTP/WS 封装和错误模型。  
6. 最后按需阅读 `ipcBridge.ts` 和各个 `*Mapper.ts`，把具体业务 API 和数据映射补齐。
