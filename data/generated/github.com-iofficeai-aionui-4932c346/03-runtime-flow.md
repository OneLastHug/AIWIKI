# 运行流程与关键调用链

本页把 AionUi 的运行流分成桌面启动、WebUI 启动、renderer 初始化、配置加载、会话创建、消息收发、定时任务和团队模式。所有链路都基于当前仓库文件整理；涉及 aioncore 后端内部实现的部分，因仓库内没有完整后端源码，只能根据前端 API 路径、启动参数和事件名推断，并明确标注“根据当前文件推断”。

## 桌面启动流程

桌面入口是 `packages/desktop/src/index.ts`。文件开头先导入 `./process/utils/configureChromium`，注释说明它必须早于任何调用 `app.getPath('userData')` 的模块，因为 Electron 会缓存 userData 路径。随后初始化 Sentry、控制台日志、Electron 模块、主进程 adapter、后端启动工具、托盘/窗口/菜单/深链/WebUI 配置等。

启动早期会申请单实例锁。除 `AIONUI_E2E_TEST=1` 或 `AIONUI_MULTI_INSTANCE=1` 外，第二个实例会通过 `second-instance` 事件把 deep link 参数交给第一个实例，然后退出。macOS/Linux 下会执行 `fix-path`，并补充 nvm node 路径，解决 GUI 应用 PATH 不等于终端 PATH 的问题。Windows installer 相关事件由 `electron-squirrel-startup` 处理。

`handleAppReady` 是主流程。它先在开发模式安装 React DevTools，再处理 `--version`，随后调用 `initializeProcess()`。`packages/desktop/src/process/index.ts` 中的 `initializeProcess` 会先注册 Electron platform、配置 Chromium、设置 packaged 下的 `PREBUILDS_ONLY`，再调用 `initStorage()`，并初始化主进程 i18n。`initStorage.ts` 包含旧数据目录迁移、JSON 文件存储、环境目录配置、旧会话存储代理和数据库迁移相关逻辑。

存储初始化完成后，main 启动后端。`packages/desktop/src/index.ts` 调用 `startBackendOrExit`，内部执行 `assertStartupArchitectureCompatible`、计算数据目录和系统目录，然后使用 `BackendLifecycleManager.start(...)`。`BackendLifecycleManager` 来自 `@aionui/web-host`，实际源码是 `packages/web-host/src/backend-launcher.ts`。它通过 `resolveBinaryPath` 找到 `aioncore`，选取 fetch 兼容端口，spawn 子进程，传入 `--port`、`--data-dir`、`--log-level`、`--app-version`、`--parent-pid`、`--log-dir`、`--work-dir`、packaged 下的 `--managed-resources-mode bundled` 和 `--local`，并轮询健康状态。

后端成功后，`markBackendReady` 会把端口写到 `globalThis.__backendPort`，注册系统恢复时通知后端的 bridge，设置 `backendStartedOk`，调用 `ensureAdminUserOnce`，并安排后端迁移。代码注释说明，部分后端迁移依赖 renderer 经 BroadcastChannel 响应，所以 `scheduleBackendMigrations` 会推迟到 renderer `did-finish-load` 后执行，避免 main 在 renderer 尚未存在时死锁。

## 窗口与 preload

`createWindow` 创建 `BrowserWindow`。macOS 使用 hidden titlebar，其他平台使用 frameless window；`webPreferences.preload` 指向构建产物中的 preload；`webviewTag` 打开，用于 HTML 预览。窗口创建后会绑定 main adapter、窗口引用、菜单、缩放、最大化监听、窗口边界持久化、自动更新服务、崩溃恢复和关闭到托盘逻辑。开发模式优先加载 `process.env.ELECTRON_RENDERER_URL`，生产模式加载 `out/renderer/index.html`。

`packages/desktop/src/preload/main.ts` 在隔离上下文里执行。它暴露 `electronAPI.emit/on`，底层通过 `ipcRenderer.invoke(ADAPTER_BRIDGE_EVENT_KEY, JSON.stringify(...))` 与 main 通信；暴露 `getPathForFile`、反馈日志收集、截图；同步请求 `get-backend-port`、`get-initial-language`、`get-backend-startup-failed`、`get-backend-startup-failure`，并把结果放到 `window.__backendPort`、`window.__initialLanguage`、`window.__backendStartupFailed`、`window.__backendStartupFailure`。托盘事件被转成 DOM `CustomEvent`，renderer 直接监听 window 事件即可。

## Renderer 初始化和配置加载

React 入口是 `packages/desktop/src/renderer/main.tsx`。它先根据 `window.electronAPI` 决定是否加载 Electron renderer Sentry，然后导入运行时 patch、browser adapter、React、Arco、样式、`configService`、i18n 和 PWA 注册。`configService.initialize()` 很早就启动，注释说明它必须早于 i18n/theme 模块读取配置，这样这些模块能拿到后端中的权威设置。

`configService.ts` 的 base URL 逻辑体现桌面和 WebUI 的差异：如果在浏览器文档环境且没有 `window.__backendPort`，就使用空字符串同源请求，让 web-host 代理 `/api/*`；否则用本机后端地址加 `window.__backendPort` 组成请求前缀。它从 `GET /api/settings/client` 拉取配置，缓存到 Map；如果缺少 `theme.activeId`，会执行主题迁移并异步 `PUT /api/settings/client`。之后 `get/set/remove/setBatch/subscribe` 都围绕这个缓存和后端设置 API 工作。

`main.tsx` 中的 `Main` 组件等待认证状态 `ready`，然后并行执行 `configService.initialize()` 和 `fetchDetectedAgents()`，后者预热 SWR cache，供 `Guid` 页的模型/模式选择器首屏使用。准备完成后渲染 `Router`，外层包有 `AuthProvider`、`ThemeProvider`、`PreviewProvider`、`FeedbackProvider` 和 `ConversationHistoryProvider`。如果 preload 暴露了后端启动失败，入口会直接渲染 `BackendStartupFailureDialog`。

## 路由与页面流

路由在 `packages/desktop/src/renderer/components/layout/Router.tsx`。未认证用户跳 `/login`，认证后默认跳 `/guid`。核心页面包括 `/guid` 创建会话，`/conversation/:id` 进入会话，`/team/:id` 进入团队模式，`/settings/model`、`/settings/assistants`、`/settings/agent`、`/settings/capabilities`、`/settings/appearance`、`/settings/webui`、`/settings/pet`、`/settings/system` 管理设置，`/scheduled` 和 `/scheduled/:job_id` 管理定时任务。

`/conversation/:id` 的入口是 `packages/desktop/src/renderer/pages/conversation/index.tsx`。它用 SWR 读取 `getConversationOrNull(id)`，监听 `ipcBridge.conversation.listChanged` 以刷新当前会话，切换会话时关闭预览面板，并在新会话默认标题时尝试自动同步标题。具体渲染由 `ChatConversation` 决定，根据会话类型选择 ACP、aionrs 或 legacy 只读路径。

## 创建会话和首条消息

首页发送逻辑在 `packages/desktop/src/renderer/pages/guid/hooks/useGuidSend.ts`。它收集输入文本、文件、工作区、选中 agent、模式、模型、预设助手、启用技能、禁用内置技能、MCP server 快照等信息。若选中 `aionrs` 或预设助手的有效 agent 是 `aionrs`，它调用 `ipcBridge.conversation.create.invoke({ type: 'aionrs', ... })`；否则使用 `buildAgentConversationParams` 构造 ACP/custom/remote agent 参数，再调用同一个 `conversation.create`。创建成功后更新工作区历史、触发 `chat.history.refresh`，把首条消息写入 `sessionStorage` 的 `aionrs_initial_message_<id>` 或 `acp_initial_message_<id>`，然后跳转到 `/conversation/<id>`。

`ipcBridge.ts` 中 `conversation.create` 映射到 `POST /api/conversations`。根据当前文件推断，后端收到请求后创建会话记录，并保存 `extra` 中的 workspace、默认文件、技能快照、MCP 快照、预设助手 id、session mode、model 等。首条消息不是在创建接口中直接发出，而是由会话页的 `useAcpInitialMessage` 或 aionrs 对应逻辑读取 `sessionStorage` 后再发。

## 消息发送和流式响应

ACP 会话页面由 `AcpChat.tsx` 组合 `MessageList`、`AcpSendBox`、`ConversationProvider` 和 `ConversationArtifactProvider`。`AcpSendBox.tsx` 管理草稿、附件、模式切换、模型切换、slash commands、预览面板填充、团队权限、命令队列和初始消息发送。实际业务发送通过 `ipcBridge.conversation.sendMessage`，在 `ipcBridge.ts` 中映射到 `POST /api/conversations/:conversation_id/messages`，body 包含 `content`、`files`、`loading_id`、`inject_skills`。

响应流由 `useAcpMessage.ts` 订阅 `ipcBridge.conversation.responseStream`，也就是 WebSocket 的 `message.stream` 事件。它会过滤非当前会话消息，把后端事件转换成 UI 消息，并维护 running、aiProcessing、thought、tokenUsage、slashCommands、context limit、thinking 状态。`finish` 到达时记录终止事件并收束运行状态；错误 tip 会直接停止当前 turn。`useAionrsMessage.ts` 也订阅同一 `responseStream`，但处理 aionrs 的本地 cron 响应、工具状态、token usage 和 active message id 过滤逻辑。

## WebUI 运行流

桌面应用可以通过 `--webui` 进入 WebUI 模式；独立 CLI 则由 `packages/web-cli/src/index.ts` 启动。CLI 解析参数后寻找静态目录和后端 binary，创建 data/log 目录。如果后端存在，调用 `startWebHost`；如果不存在，调用 `startStaticServer` 进入 frontend-only。`startWebHost` 会先用 `startBackend` 启动后端，再启动 static server。`static-server.ts` 对外监听默认 25808 端口；普通 HTTP 请求进入内部 HTTP server，`/api/*`、`/login`、`/logout` 代理到后端，其余走静态文件和 SPA fallback；`GET /ws` 用原始 TCP splice 转到后端。浏览器 renderer 因为没有 preload 的 `__backendPort`，所以 `configService` 和 `httpBridge` 使用同源路径，交给 static server 代理。

## 定时任务和团队模式

定时任务 UI 的代表入口是 `packages/desktop/src/renderer/pages/cron/useCronJobs.ts`。它通过 `ipcBridge.cron.listJobsByConversation` 或 `ipcBridge.cron.listJobs` 拉取任务，通过 `updateJob/removeJob` 暂停、恢复、删除、更新任务，并订阅 `onJobCreated/onJobUpdated/onJobRemoved` 事件刷新本地状态。`main.tsx` 启动后还会调用 `repairAllCronJobTimeZonesOnce()`，而 main 进程在系统 resume 时会向后端 `/api/cron/internal/system-resume` 发内部请求。

团队模式入口是 `/team/:id` 和 `packages/desktop/src/renderer/pages/team/index.tsx`，它通过 `ipcBridge.team.get` 拉取团队，再渲染 `TeamPage`。数据库 schema 中存在 `teams`、`mailbox`、`team_tasks` 表；README 也描述 leader、teammate、共享 workspace、mailbox、任务板等概念。根据当前文件推断，团队协作的状态由后端维护，renderer 负责展示团队、代理权限、同步 mode/model 和成员消息，具体多 agent 调度在后端或 agent runtime 中完成。
