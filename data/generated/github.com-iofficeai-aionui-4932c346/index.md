# AionUi 源码学习索引

这组文档面向第一次阅读 AionUi 仓库的中文读者，内容只依据当前仓库中的 `readme.md`、`package.json`、`packages/desktop/electron.vite.config.ts`、`packages/desktop/src`、`packages/web-host/src`、`packages/web-cli/src`、`mobile`、`docs` 与测试目录等真实文件整理。README 中包含多个外部站点、下载和社区入口，本学习文档不展开真实网址；需要提及外部来源时统一视为 `[URL已移除]`。

## 推荐阅读顺序

1. [00-overview.md](00-overview.md)：先了解项目解决什么问题、核心能力、主要模块与适合新手切入的代码位置。
2. [01-tech-stack.md](01-tech-stack.md)：再看运行环境、包管理、Electron/Vite/Bun/React/SQLite/WebUI 等技术栈信号。
3. [02-architecture.md](02-architecture.md)：接着理解 `desktop`、`common`、`process`、`renderer`、`web-host`、`web-cli`、`mobile` 的边界和依赖方向。
4. [03-runtime-flow.md](03-runtime-flow.md)：最后串起启动、配置加载、后端进程、窗口、请求、消息流和定时任务的运行链路。
5. [04-reading-guide.md](04-reading-guide.md)：读完总览后，按这里的顺序继续下钻源码，避免一开始陷入页面细节或测试夹具。

## 后续最值得看的目录/文件

优先看根配置：`package.json`、`bun.lock`、`tsconfig.json`、`vitest.config.ts`、`uno.config.ts`、`packages/desktop/electron.vite.config.ts`。这些文件决定工作区、脚本、构建目标、测试框架、路径别名和样式体系。

桌面主线建议从 `packages/desktop/src/index.ts`、`packages/desktop/src/process/index.ts`、`packages/desktop/src/preload/main.ts`、`packages/desktop/src/renderer/main.tsx`、`packages/desktop/src/renderer/components/layout/Router.tsx` 开始。它们分别对应 Electron main、进程初始化、preload 安全桥、React 入口和页面路由。

业务交互建议看 `packages/desktop/src/common/adapter/ipcBridge.ts`、`packages/desktop/src/common/adapter/httpBridge.ts`、`packages/desktop/src/common/config/configService.ts`、`packages/desktop/src/renderer/pages/guid/hooks/useGuidSend.ts`、`packages/desktop/src/renderer/pages/conversation/platforms/acp/useAcpMessage.ts`。这些文件能解释“首页创建会话、进入会话、发送消息、接收流式事件”的最短路径。

WebUI 和无 Electron 运行建议看 `packages/web-host/src/index.ts`、`packages/web-host/src/static-server.ts`、`packages/web-host/src/backend-launcher.ts`、`packages/web-cli/src/index.ts`、`docs/guides/webui.md`、`docs/guides/deploy-server.md`。移动端只需先扫 `mobile/package.json`、`mobile/src/services/api.ts`、`mobile/src/context/WebSocketContext.tsx`，确认它是基于后端 HTTP/WebSocket 的客户端。
