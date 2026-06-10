# 架构与模块边界

AionUi 的架构可以理解为“Electron 壳 + React renderer + aioncore 后端 + 可复用 WebUI host + 移动/扩展客户端”。当前仓库中，后端二进制的源码不完整出现，TypeScript 侧主要负责解析后端路径、启动后端进程、代理 HTTP/WebSocket、展示 UI、管理 Electron 原生能力和做旧数据迁移。因此解释架构时，要把“仓库内源码能证明的部分”和“根据调用点推断的后端行为”区分开。

## 顶层目录分层

根目录的 `package.json` 是工作区和脚本中心，`packages` 是桌面/WebUI 的主要源码，`mobile` 是 Expo 移动端，`examples` 是扩展示例，`docs` 是指南、PRD 和贡献文档，`tests` 是单元、集成和端到端测试，`resources`、`public` 是应用资源，`scripts` 是构建、发布、i18n、安装、WebUI、调试脚本。`docs/README.md` 中提到 `docs/architecture/overview.md`，但当前文件列表里没有 `docs/architecture` 目录，因此本总览以实际存在的源码和配置为依据，不把缺失目录当作事实来源。

## `packages/desktop` 的内部边界

`packages/desktop/src/index.ts` 是 Electron main 的实际入口。它可以访问 Node、Electron、文件系统、进程、系统托盘和 BrowserWindow。这个文件负责应用启动主流程：早期配置 Chromium 与 Sentry，申请单实例锁，处理 deep link，修复 GUI 环境 PATH，初始化进程存储，启动 aioncore，创建窗口，注册菜单/托盘/自动更新/缩放/窗口持久化，加载 renderer。

`packages/desktop/src/process` 是 main 进程支撑层。`process/index.ts` 调用 `initStorage` 并初始化主进程 i18n。`process/startup` 放后端启动、架构兼容检查、失败分类、退出清理。`process/backend` 负责解析 `aioncore` binary。`process/bridge` 放仍需要 Electron IPC 的原生能力桥，如 dialog、notification、update、webui、theme、window controls。`process/services/database` 放本地数据库 schema 和迁移。`process/pet` 是桌面宠物相关状态机和事件桥。

`packages/desktop/src/preload` 是安全桥层。`preload/main.ts` 使用 `contextBridge.exposeInMainWorld` 暴露 `electronAPI.emit/on`、文件拖拽路径、反馈日志、截图、后端端口、初始语言、后端启动失败信息和托盘事件转 DOM 事件。preload 不能成为业务巨石，它的职责是把 renderer 必须知道的少量能力安全注入。

`packages/desktop/src/renderer` 是 React UI。入口是 `main.tsx`，路由是 `components/layout/Router.tsx`，主要页面有 `guid`、`conversation`、`team`、`settings`、`cron`、`login`。`components` 放通用 UI，`hooks` 放上下文和业务 hook，`services` 放文件、粘贴、语音和 i18n，`utils` 放 chat、workspace、theme、file 等工具，`styles` 放全局样式和主题。

`packages/desktop/src/common` 是跨进程共享层。它不能依赖 DOM 或 Electron 特有 UI。这里有配置类型、API adapter、平台抽象、主题迁移、chat 工具、类型定义和 bridge。`common/adapter/ipcBridge.ts` 是关键文件，它把业务调用统一成 typed API：renderer 仍通过 `ipcBridge.conversation.create.invoke(...)` 这种形式调用，但底层多数已映射为 HTTP REST/WS。这样可以让 Electron renderer 与 WebUI browser 共享调用模型。

## WebUI 的复用边界

`packages/web-host` 是一个无 Electron 依赖的包。`index.ts` 的 `startWebHost` 同时负责启动后端和静态服务；如果调用方已经有后端，则可用 `useExistingBackend` 模式。`static-server.ts` 只做三件事：提供 renderer 静态文件、把 `/api/*`/`/login`/`/logout` 代理到后端、把 `/ws` 连接用 TCP splice 转给后端。文件注释明确写着“无 Express、无业务路由”，这说明业务并不在 web-host 中实现。

`packages/web-cli` 是 `aionui-web` 命令行包装。它解析 `--port`、`--remote`、`--backend-bin`、`--static-dir`、`--data-dir`、`--log-dir` 等，找到 tarball 内的 `bundled-aioncore` 和 `static` 目录，启动 `startWebHost`。如果找不到后端二进制，它会进入 frontend-only 模式，此时 API 会失败，UI 只作为壳加载。`resetpass` 命令则短暂启动 WebHost，调用后端重置管理员密码。

## 依赖方向

推荐把依赖方向记成：`renderer -> common adapter/config/types -> backend HTTP/WS`，`renderer -> preload exposed electronAPI -> main process native bridge`，`main process -> web-host BackendLifecycleManager -> aioncore binary`，`web-cli -> web-host -> aioncore + static renderer`。反方向不应该出现：renderer 不应直接使用 Node 文件系统；common 不应依赖 renderer 组件；web-host 不应依赖 Electron；后端进程只通过 HTTP/WS 与 UI 通信。

这个方向在源码中有多个证据。`electron.vite.config.ts` 为 main、preload、renderer 分别设置入口和 alias；`preload/main.ts` 明确通过 `contextBridge` 暴露最小 API；`configService.ts` 在浏览器模式下没有 `window.__backendPort` 就使用 same-origin，依赖 web-host 反向代理；`static-server.ts` 把 `/api` 和 `/ws` 转给 backend；`ipcBridge.ts` 文件头说明业务桥接从 IPC 转向 HTTP/WS。

## 扩展点

显式扩展点包括 agent、assistant、skills、MCP、主题、设置页、channel 和 WebUI。`examples/hello-world-extension` 下的 `aion-extension.json`、`contributes/agents.json`、`contributes/assistants.json`、`contributes/mcp-servers.json`、`contributes/settings-tabs.json`、`contributes/skills.json`、`contributes/themes.json` 给出扩展 manifest 的样例。设置页中的 `AgentSettings`、`AssistantSettings`、`CapabilitiesSettings`、`ExtensionSettingsPage`、`ToolsSettings/McpManagement.tsx` 是阅读扩展管理 UI 的入口。后端 API 的具体扩展加载行为在当前仓库中证据不足，只能根据示例目录和前端调用点推断：扩展被读取后会向 agent、assistant、MCP、settings tab、theme 等 catalog 注入条目。

## 模块风险点

阅读时最容易混淆的是三个“桥”：preload 的 `electronAPI` 是 Electron 安全桥，`common/adapter/ipcBridge.ts` 是业务 API 门面，`web-host/static-server.ts` 是浏览器到后端的反向代理。第二个混淆点是后端：`aioncore` 的完整实现不在 TypeScript 目录里，`process/services/database/schema.ts` 更像迁移/兼容/测试所需的主进程 SQLite schema，不能据此断言所有后端业务都在 Electron main 内完成。第三个混淆点是桌面模式与 WebUI 模式：它们共享 renderer 和后端 API，但桌面模式有 BrowserWindow、托盘、自动更新、原生对话框；WebUI 模式没有这些原生能力，需要通过 HTTP/WS 和浏览器限制来工作。
