# 目录：apps

## 它负责什么

`apps` 是 LobeHub 仓库里的“独立应用层”，用于承载不属于主 Next.js / SPA Web 应用的可运行产物。它不是业务页面目录，也不是共享库目录，而是把 LobeHub 能力包装成不同运行形态：

- `apps/cli`：命令行客户端，发布为 `@lobehub/cli`，提供 `lh` / `lobe` / `lobehub` 三个 bin 入口，用终端管理和调用 LobeHub 服务。
- `apps/desktop`：Electron 桌面客户端，负责原生窗口、系统菜单、托盘、快捷键、更新、桌面权限、IPC、嵌入 CLI、文件与工具探测等桌面能力。
- `apps/device-gateway`：Cloudflare Worker + Durable Object 服务，用于把远端 HTTP 请求桥接到用户在线的桌面设备 WebSocket，支持设备状态、工具调用、系统信息、agent run 等 RPC。

可以把 `apps` 理解为“LobeHub 主体能力的外壳适配层”：主产品核心在根目录 `src/` 和 `packages/`，而 `apps` 负责让这些能力在 CLI、Electron、边缘网关等环境中运行。

## 关键组成

`apps/cli` 的入口是 `src/index.ts`，只做一件事：调用 `createProgram().parse(process.argv, { from: 'node' })`。真正的命令注册在 `src/program.ts`，它使用 `commander` 创建 `lh` 程序，并依次注册 `login`、`logout`、`completion`、`connect`、`device`、`doc`、`search`、`kb`、`memory`、`agent`、`bot`、`generate`、`file`、`hetero`、`task`、`message`、`model`、`provider`、`plugin`、`eval`、`migrate` 等命令。它依赖 `@lobechat/agent-gateway-client`、`@lobechat/device-gateway-client`、`@lobechat/heterogeneous-agents`、`@lobechat/local-file-shell`，说明 CLI 并不只是普通管理工具，还会触达 agent、设备网关、本地文件和异构 agent 能力。

`apps/desktop` 是体量最大的子应用。入口 `src/main/index.ts` 先执行 `fixPath()` 修复桌面环境中的 `PATH`，然后实例化 `App` 并调用 `app.bootstrap()`。核心类在 `src/main/core/App.ts`，它初始化 `StoreManager`、`RendererUrlManager`、`LocalFileProtocolManager`、`ProtocolManager`，通过 `import.meta.glob('@/controllers/*Ctr.ts', { eager: true })` 自动加载控制器，通过 `import.meta.glob('@/services/*Srv.ts', { eager: true })` 自动加载服务，再启动 IPC、i18n、窗口、菜单、快捷键、托盘、更新器、静态文件服务、工具探测器、屏幕捕获等模块。`src/preload` 是 Electron preload 层，`src/overlay` 是屏幕捕获/悬浮层相关 React UI。

`apps/device-gateway` 的入口是 `src/index.ts`，使用 `Hono` 暴露 `/health`、`/ws` 和 `/api/device/*`。`/ws` 根据 `userId` 路由到 Durable Object；`/api/device/*` 通过 `SERVICE_TOKEN` 做服务间鉴权，再把请求转发给同一个用户对应的 `DeviceGatewayDO`。`DeviceGatewayDO.ts` 维护每个用户的 WebSocket 连接、认证状态、心跳和 pending RPC 请求。

## 上下游关系

上游看，`apps` 依赖根仓库和 `packages` 里的共享能力。例如 CLI 和 Desktop 都引用 `@lobechat/device-gateway-client`、`@lobechat/heterogeneous-agents`、`@lobechat/local-file-shell` 等 workspace 包；Desktop 还依赖 `@lobechat/electron-client-ipc`、`@lobechat/electron-server-ipc`、`@lobechat/desktop-bridge` 来完成主进程、preload 和渲染侧通信。

下游看，`apps/cli` 面向终端用户或自动化脚本，最终通过 HTTP/TRPC/WebSocket 与 LobeHub 服务通信；`apps/desktop` 面向桌面用户，同时作为“本地能力执行端”，把文件系统、Shell、截图、MCP、Git、CLI agent 等本机能力开放给 LobeHub；`apps/device-gateway` 位于云端和桌面端之间，远端服务调用它的 `/api/device/*`，它再把请求转成 WebSocket 消息发给在线桌面端。

根 `package.json` 中有 `dev:desktop`、`desktop:build:main`、`desktop:package:*` 等脚本，说明 Desktop 是被根工作流显式编排的。根 `workspaces` 包含 `apps/desktop/src/main`，而 `apps/cli`、`apps/device-gateway` 各自有独立 `package.json` 和运行脚本；根据当前片段推断，它们更像相对独立的发布/部署单元，而不是主 Web 构建的一部分。

## 运行/调用流程

CLI 的流程最简单：用户执行 `lh xxx`，bin 指向 `dist/index.js`；开发时可用 `bun run dev -- <command>` 直接跑 `src/index.ts`。`index.ts` 进入 `createProgram()`，`program.ts` 注册所有子命令，具体命令再调用 `src/api`、`src/auth`、`src/settings`、`src/tools` 等模块完成鉴权、请求、格式化输出或本地动作。默认服务地址是 `[URL已移除] `LOBEHUB_SERVER` 或 `lh login --server` 覆盖。

Desktop 的流程是：`electron-vite dev/build` 启动 Electron 主进程，`src/main/index.ts` 创建 `App`；构造阶段注册协议、加载 controllers/services、初始化基础 manager；`bootstrap()` 阶段申请单实例锁、启动 IPC server、等待 `app.whenReady()`、初始化 i18n 和菜单、启动静态文件服务、注册全局快捷键、创建浏览器窗口、初始化托盘和自动更新。之后控制器接收 IPC 或协议请求，服务层处理本地文件、网关连接、搜索等实际能力。

Device Gateway 的流程是：Cloudflare Worker 接收请求；桌面端通过 `/ws?userId=...&deviceId=...` 建立 WebSocket，Durable Object 保存连接附件并要求 10 秒内认证；云端服务通过 `/api/device/status`、`/api/device/tool-call`、`/api/device/system-info`、`/api/device/agent/run` 等接口发起请求；Durable Object 选择目标在线设备，生成 `requestId` 或使用 `operationId`，把请求发到 WebSocket，等待桌面端回传响应，超时则返回 504。

## 小白阅读顺序

1. 先看 `apps` 的一层目录，明确这里只有 `cli`、`desktop`、`device-gateway` 三个应用，不要把它和 `src/app` 混淆。
2. 读三个 `package.json`，重点看 `name`、`scripts`、`dependencies`：这能最快判断每个应用的运行环境和边界。
3. 读 `apps/cli/src/index.ts` 和 `apps/cli/src/program.ts`，理解 CLI 是如何用 `commander` 聚合命令的。
4. 读 `apps/desktop/src/main/index.ts` 和 `apps/desktop/src/main/core/App.ts`，先抓生命周期，不要一开始陷入大量 controller。
5. 再看 `apps/desktop/src/main/controllers` 和 `apps/desktop/src/main/services` 文件名，按能力域建立索引，例如 `AuthCtr`、`GatewayConnectionCtr`、`HeterogeneousAgentCtr`、`ScreenCaptureCtr`。
6. 最后读 `apps/device-gateway/src/index.ts` 和 `DeviceGatewayDO.ts`，重点理解 Worker 路由、Durable Object 按用户分片、WebSocket 认证和请求-响应映射。

## 常见误区

第一，`apps/desktop` 不是主 Web SPA 的源码目录。它是 Electron 壳和本机能力层，渲染内容可能加载本地/远端 LobeHub 页面，但窗口、IPC、协议、托盘、更新等都在这里处理。

第二，`apps/cli` 不是简单脚本集合。它有正式 npm 包名、bin、man page、测试和构建流程，并且命令覆盖 agent、bot、知识库、文件、异构 agent、迁移等复杂场景。

第三，`apps/device-gateway` 不是普通 REST API。它的核心是 Durable Object 中的长连接状态：HTTP 接口只是入口，真正的设备在线状态和 RPC 转发依赖 WebSocket 和 `pendingRequests`。

第四，不要把 `src/app` 和 `apps` 混为一谈。`src/app` 是 Next.js App Router / 后端 API 结构；`apps` 是 monorepo 下的独立应用产物。

第五，阅读 Desktop 时不要从所有 controller 逐个展开。更有效的方式是先掌握 `App` 的启动顺序和 manager 分层，再按具体功能追某个 controller 到 service、IPC 或协议处理器。
