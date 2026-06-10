# 项目整体介绍

AionUi 是一个围绕 AI Agent 协作的跨平台应用。根 `package.json` 的描述是“把命令行 AI agent 转成现代、高效的 AI Chat interface”，根 `readme.md` 进一步说明它不只是聊天客户端，而是让 agent 能在用户电脑上读写文件、执行多步骤任务、接入多种 CLI agent、远程访问、定时自动化和多 agent 团队协作的界面。这里的能力判断主要依据：`readme.md` 的功能说明、`packages/desktop/src/renderer/pages/conversation` 的会话页面、`packages/desktop/src/common/adapter/ipcBridge.ts` 的 REST/WebSocket API 映射、`packages/web-host/src` 的 WebUI 服务、`packages/desktop/src/process/services/database/schema.ts` 的本地表结构，以及 `docs/prds` 下的产品需求目录。

## 它解决什么问题

从当前源码看，AionUi 解决的是“把多个 AI 执行后端统一到一个可视化工作台”的问题。传统聊天 UI 主要展示输入框和消息，而 AionUi 的会话模型包含 `workspace`、`files`、`mcp`、`skills`、`agent backend`、`model`、`runtime`、`pending_confirmations` 等概念。`packages/desktop/src/common/config/storage.ts` 中的 `TChatConversation` 类型把会话分成 `acp`、`aionrs` 等后端类型；`packages/desktop/src/renderer/pages/guid/hooks/useGuidSend.ts` 在创建会话时会根据选中的 agent 类型构造不同参数，并把初始消息暂存在 `sessionStorage`，再跳转到 `/conversation/:id`。这说明项目把“选择 agent、选择模型、选择工作区、选择技能/MCP、创建会话、发送首条消息”作为一个完整工作流处理。

## 核心能力

第一类能力是桌面应用。`packages/desktop/src/index.ts` 是 Electron main 入口，负责单实例锁、系统 PATH 修正、Sentry 初始化、后端启动、窗口创建、托盘、菜单、自动更新、深链、窗口尺寸持久化等。`packages/desktop/src/preload/main.ts` 用 `contextBridge` 向 renderer 暴露 `electronAPI`、`__backendPort`、`__initialLanguage` 和后端启动失败信息。`packages/desktop/src/renderer/main.tsx` 初始化 React、Arco Design、UnoCSS、主题、i18n、认证、预览上下文和运行时失败弹窗。

第二类能力是 agent 会话。`packages/desktop/src/renderer/pages/conversation/platforms/acp/AcpChat.tsx` 与 `packages/desktop/src/renderer/pages/conversation/platforms/aionrs/AionrsChat.tsx` 分别代表 ACP 后端和内置 Aion CLI/aionrs 后端的会话页面。它们都复用 `MessageList`、`ConversationProvider`、`ConversationArtifactProvider`，差异主要在 send box 和消息状态 hook。`useAcpMessage.ts`、`useAionrsMessage.ts` 都订阅 `ipcBridge.conversation.responseStream`，处理 `start`、`thought`、`thinking`、`content`、`finish`、错误提示、token usage 等事件。

第三类能力是 WebUI。`packages/web-host/src/index.ts` 暴露 `startWebHost`，组合 `backend-launcher` 和 `static-server`。`static-server.ts` 用 Node 原生 `http` 与 `net` 服务静态 SPA，并把 `/api/*`、`/login`、`/logout`、`/ws` 代理到后端。`packages/web-cli/src/index.ts` 则把这个能力包装成独立 CLI，支持 `start`、`resetpass`、`--remote`、`--port`、`--data-dir`、`--backend-bin` 等运行参数。由此可见，WebUI 不是单独实现业务，而是复用同一个后端 API 和同一套 renderer 产物。

第四类能力是配置、数据和自动化。`packages/desktop/src/common/config/configService.ts` 从 `/api/settings/client` 拉取客户端配置，并提供缓存、订阅、批量写入和主题迁移。`packages/desktop/src/process/utils/initStorage.ts` 保留了旧版文件存储迁移逻辑，并导出 `ProcessConfig` 等主进程配置入口。`packages/desktop/src/process/services/database/schema.ts` 定义本地 SQLite 表：`users`、`conversations`、`messages`、`teams`、`mailbox`、`team_tasks`，并启用外键、busy timeout 和 WAL。`packages/desktop/src/renderer/pages/cron/useCronJobs.ts` 通过 `ipcBridge.cron` 管理定时任务，并监听任务创建、更新、删除事件。

## 主要模块

`packages/desktop` 是桌面主应用，内部再分 `common`、`process`、`preload`、`renderer`。`common` 是跨 main/renderer 的类型、配置、adapter 与工具层；`process` 是 Electron main 可使用的 Node/Electron 能力；`preload` 是隔离上下文下的安全桥；`renderer` 是 React UI。`packages/web-host` 是无 Electron 依赖的 WebUI host；`packages/web-cli` 是 WebUI 的命令行入口；`packages/shared-scripts` 放共享构建脚本；`mobile` 是 Expo/React Native 客户端；`examples` 存放扩展示例；`tests` 存放单元、集成、端到端测试；`docs` 放指南、PRD、贡献说明和翻译版 README。

## 初学者切入点

如果目标是理解启动链路，先读 `packages/desktop/src/index.ts`，再读 `packages/desktop/src/process/startup/backendStartup.ts`、`packages/web-host/src/backend-launcher.ts`、`packages/desktop/src/preload/main.ts` 和 `packages/desktop/src/renderer/main.tsx`。如果目标是理解一条消息怎么发送和显示，先读 `packages/desktop/src/renderer/pages/guid/hooks/useGuidSend.ts`，再读 `packages/desktop/src/renderer/pages/conversation/index.tsx`、`AcpSendBox.tsx`、`useAcpMessage.ts`、`MessageList.tsx`。如果目标是扩展 agent、技能或 MCP，先读 `packages/desktop/src/common/config/storage.ts`、`packages/desktop/src/common/adapter/ipcBridge.ts`、`examples/hello-world-extension/aion-extension.json` 和 `packages/desktop/src/renderer/pages/settings/CapabilitiesSettings.tsx`。需要注意：aioncore 后端本体不是以完整源码形式放在这个仓库里，当前仓库只包含解析、启动和代理它的 TypeScript 代码；后端内部 API 行为只能根据 `ipcBridge.ts` 的路径映射、`schema.ts`、WebUI 代理和前端调用点推断。
