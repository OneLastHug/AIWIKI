# 源码阅读指南

这份阅读路线适合想快速掌握 AionUi 主体结构的新读者。不要从 `renderer/pages/settings` 或 `examples` 一头扎进去；这些目录信息量很大，但很多行为依赖启动链路、后端 API 和会话模型。推荐先按“配置入口、进程入口、桥接层、会话链路、扩展点、测试”的顺序读。

## 第一轮：核心入口

先读根 `package.json`，确认脚本、依赖、workspace 和主入口。然后读 `packages/desktop/electron.vite.config.ts`，理解 main、preload、renderer 三套 bundle 怎么生成，路径别名怎么设，renderer 为什么是 MPA，内置 MCP server 为什么在 build 后单独构建。再读 `packages/desktop/src/index.ts`，只看结构，不追每个工具函数：重点标记单实例锁、`handleAppReady`、`initializeProcess`、`startBackendOrExit`、`createWindow`、`markBackendReady`、`scheduleBackendMigrations`。

接着读 `packages/desktop/src/preload/main.ts` 和 `packages/desktop/src/renderer/main.tsx`。前者告诉你 renderer 能从 Electron main 拿到什么；后者告诉你 React 应用启动前做了哪些全局初始化。最后读 `packages/desktop/src/renderer/components/layout/Router.tsx`，把页面入口和 URL 对上。

## 第二轮：请求和数据流

第二轮从 `packages/desktop/src/common/adapter/ipcBridge.ts` 开始。这个文件很长，不需要一次读完，先看顶部注释、`conversation`、`cron`、`team`、`settings/providers/mcp` 相关段落，理解“typed bridge 调用最终映射成 HTTP/WS”的模式。配套读 `packages/desktop/src/common/adapter/httpBridge.ts`、`packages/desktop/src/common/config/configService.ts` 和 `packages/desktop/src/common/config/storage.ts`。这样能建立三个关键概念：后端 API 是业务数据中心，configService 是 renderer 的设置缓存，storage.ts 是前后端共享类型合同。

然后看会话创建和发送：`packages/desktop/src/renderer/pages/guid/hooks/useGuidSend.ts`、`packages/desktop/src/renderer/pages/conversation/index.tsx`、`packages/desktop/src/renderer/pages/conversation/platforms/acp/AcpChat.tsx`、`AcpSendBox.tsx`、`useAcpMessage.ts`、`packages/desktop/src/renderer/pages/conversation/platforms/aionrs/AionrsChat.tsx`、`useAionrsMessage.ts`。读这一组时只追一条路径：用户在 `/guid` 输入文本和文件，创建会话，跳转到 `/conversation/:id`，send box 发送初始消息，WebSocket 流事件更新 `MessageList`。

## 第三轮：后端生命周期和 WebUI

读 `packages/desktop/src/process/backend/binaryResolver.ts`，确认 `aioncore` 如何从 bundled 目录或 PATH 查找。再读 `packages/web-host/src/backend-launcher.ts`，看 spawn 参数、端口选择、健康检查、失败诊断和进程关闭。接着读 `packages/web-host/src/static-server.ts` 和 `packages/web-host/src/index.ts`，理解 WebUI 的静态文件、HTTP 反向代理和 WebSocket 转发。最后读 `packages/web-cli/src/index.ts`，看独立 `aionui-web` 如何解析 CLI 参数、启动 WebHost、处理 frontend-only 和 reset password。

## 第四轮：可以后读的模块

设置页可以后读：`packages/desktop/src/renderer/pages/settings` 内容很多，但大多是对 provider、assistant、agent、MCP、theme、WebUI、system 配置的 CRUD UI。团队模式可以后读：先读 `packages/desktop/src/renderer/pages/team/index.tsx`、`TeamPage.tsx` 和 `process/services/database/schema.ts` 中的 `teams/mailbox/team_tasks`，再进入团队 hook。定时任务可以后读：从 `packages/desktop/src/renderer/pages/cron/useCronJobs.ts` 和 `ScheduledTasksPage` 起步。桌面宠物也可以后读：`packages/desktop/src/process/pet` 与 `packages/desktop/src/renderer/pet` 独立性较强。

移动端建议放在桌面主线之后读。先扫 `mobile/package.json`，再读 `mobile/src/services/api.ts`、`mobile/src/services/websocket.ts`、`mobile/src/context/ConnectionContext.tsx`、`ConversationContext.tsx`、`ChatContext.tsx`。它的价值在于验证后端 API/WS 是否足够跨客户端，而不是解释 Electron 主流程。

## 可以暂时跳过的内容

第一次阅读可以跳过 `resources` 下的大量图片和动图、`public/pet-states` 静态资源、`docs/readme` 多语言 README、`docs/prds` 中细粒度产品需求、`tests/fixtures`、端到端 fixture、`patches` 和发布脚本细节。`examples` 不要完全跳过，但建议只读 `examples/hello-world-extension/aion-extension.json` 和 `contributes` 目录，先理解扩展 manifest 形态，等读完 settings 与 adapter 后再看 channel 和 WebUI 扩展示例。

## 继续下钻顺序

如果你关心“新增一个 agent 后端”，下一步看 `common/types/agent`、`renderer/utils/model/agentTypes.ts`、`renderer/hooks/agent`、`settings/AgentSettings`、`buildAgentConversationParams.ts` 和 `ipcBridge.acpConversation` 相关 API。如果你关心“MCP/skills”，下一步看 `settings/ToolsSettings`、`renderer/hooks/mcp`、`common/config/storage.ts` 的 `IMcpServer`、`process/resources/builtinMcp/imageGenServer.ts` 和扩展示例的 `contributes/mcp-servers.json`、`skills/*.md`。如果你关心“数据迁移和兼容”，下一步看 `initStorage.ts`、`process/services/database/migrations.ts`、`runLegacyDatabaseMigrations.ts`、`runBackendMigrations.ts`。如果你关心“测试”，从 `vitest.config.ts`、`tests/unit`、`packages/web-host/*.test.ts`、`tests/e2e/README.md` 开始。
