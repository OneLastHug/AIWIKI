# 目录：apps

## 它负责什么

`apps` 是这个 monorepo 里的“独立应用层”，放的是可以单独开发、构建、发布或部署的应用，而不是通用业务代码。根项目的主体 Web/SPA 仍主要在 `src/`、`packages/` 中；`apps` 更像围绕 LobeHub 主产品扩展出来的端侧与工具侧入口。

从当前目录看，`apps` 下面有三个核心应用：`apps/desktop`、`apps/cli`、`apps/device-gateway`。它们分别对应 Electron 桌面端、命令行工具、Cloudflare Worker 设备网关。三者都依赖根仓库或 workspace packages 中的能力，但运行时边界不同：桌面端负责本地窗口、系统能力、Electron IPC 与桌面渲染入口；CLI 负责通过命令管理 LobeHub 的数据、配置、知识库、Agent、模型等；device-gateway 负责为桌面端和服务端之间提供按用户隔离的 WebSocket / HTTP 转发通道。

因此，阅读 `apps` 时不要把它当成主 Web 应用的页面目录。主 Web SPA 的路由入口在 `src/spa/` 和 `src/routes/`，而 `apps` 主要是“产品外壳、工具入口、边缘服务”。

## 直接子目录地图

`apps/desktop` 是 Electron 桌面应用。它有独立的 `package.json`、`electron.vite.config.ts`、`electron-builder.mjs`、`index.html`、`popup.html`、`overlay.html`，并在 `src/` 下区分 `main`、`preload`、`overlay`、`common`。其中 `src/main` 是 Electron 主进程核心区域，包含窗口、菜单、控制器、模块、服务、更新、网络代理、屏幕捕获、异构 Agent 等能力；`src/preload` 负责主进程和渲染进程之间的桥接；`src/overlay` 对应 overlay 独立入口。`build` 和 `resources` 主要放图标、安装包资源、启动页、错误页等发行资源。

`apps/cli` 是 `@lobehub/cli` 包。它通过 `bin` 暴露 `lh`、`lobe`、`lobehub` 三个命令别名，源码集中在 `apps/cli/src`。目录下的 `commands` 是命令注册与实现主区，`api`、`auth`、`settings`、`daemon`、`tools`、`utils` 提供调用服务、鉴权、本地配置、后台能力与工具函数；`e2e` 放 CLI 端到端用例；`man` 放命令手册输出。根据当前片段推断，CLI 是面向开发者或高级用户的管理入口，因为它覆盖了 doc、search、kb、memory、agent、model、provider、plugin、topic、message 等命令域。

`apps/device-gateway` 是 `@lobechat/device-gateway`，一个基于 Hono 和 Cloudflare Workers / Durable Objects 的设备网关服务。它的 `src/index.ts` 建立 HTTP 路由，`src/DeviceGatewayDO.ts` 应该是每个用户连接态的 Durable Object，`src/auth.ts` 负责认证相关逻辑，`wrangler.toml` 是 Worker 部署配置，`scripts/extract-public-key.mjs` 是辅助脚本。

## 关键入口

桌面端的开发与构建入口主要看 `apps/desktop/package.json` 和 `apps/desktop/electron.vite.config.ts`。`package.json` 中 `dev` 运行 `electron-vite dev`，`build:main` 运行 `electron-vite build`，`package:mac`、`package:win`、`package:linux` 通过 `electron-builder` 打包。Electron 主入口由 `main` 字段指向 `./dist/main/index.js`，源头则应从 `apps/desktop/src/main` 继续追踪。渲染侧 HTML 入口在 `apps/desktop/index.html`、`apps/desktop/popup.html`、`apps/desktop/overlay.html`，并由 `electron.vite.config.ts` 的 renderer input 显式注册。

CLI 的命令入口是 `apps/cli/src/index.ts` 与 `apps/cli/src/program.ts`。其中 `program.ts` 创建 commander `Command`，设置名称、描述、版本，然后逐个调用 `registerLoginCommand`、`registerConnectCommand`、`registerDocCommand`、`registerAgentCommand`、`registerModelCommand`、`registerPluginCommand` 等注册函数。想理解“一个 CLI 命令如何挂进去”，优先从 `createProgram()` 看起，再跳到 `apps/cli/src/commands/*`。

device-gateway 的服务入口是 `apps/device-gateway/src/index.ts`。它创建 `Hono` app，暴露 `/health` 健康检查、`/ws` 桌面 WebSocket 连接入口，以及 `/api/device/*` 服务端 HTTP API 入口。`package.json` 的 `dev`、`deploy` 分别对应 `wrangler dev` 和 `wrangler deploy`。

## 主流程位置

桌面端主流程大致是：`electron-vite` 根据 `apps/desktop/electron.vite.config.ts` 分别构建 main、preload、renderer；主进程从 `apps/desktop/src/main` 启动 Electron 应用，初始化窗口、协议、菜单、模块和服务；preload 将受控能力暴露给渲染层；renderer 使用根仓库共享的 SPA 渲染配置加载桌面平台页面。配置中还可以看到对 `/popup/*`、`/overlay`、`/index.html` 的 HTML rewrite，说明桌面端有主窗口、弹窗窗口和 overlay 窗口三类渲染入口。

CLI 主流程是：`apps/cli/src/index.ts` 启动程序，`apps/cli/src/program.ts` 组装 commander 命令树，各 `apps/cli/src/commands/*` 注册具体命令，命令实现再调用 `api`、`auth`、`settings`、`tools` 等支撑模块。构建产物输出到 `dist`，发布包只包含 `dist` 和 `man`。

device-gateway 主流程是：客户端或服务端请求进入 Worker；`/ws` 根据 query 中的 `userId` 选择 `DEVICE_GATEWAY.idFromName("user:<userId>")` 对应的 Durable Object，并把请求转交给该对象；`/api/device/*` 先用 `SERVICE_TOKEN` 做 Bearer 鉴权，再从请求 body 读取 `userId` 并转发到同一个用户级 Durable Object。根据当前片段推断，`DeviceGatewayDO` 负责维持桌面设备连接状态和处理后续消息路由，依据是入口文件将 WebSocket 与服务 API 都转发给它。

## 推荐阅读顺序

1. 先看 `apps` 的一层目录：确认这里只包含 `cli`、`desktop`、`device-gateway` 三个应用，不要急着进入叶子文件。
2. 阅读三个 `package.json`：`apps/desktop/package.json`、`apps/cli/package.json`、`apps/device-gateway/package.json`。它们最直接说明应用名称、运行命令、构建方式和关键依赖。
3. 对桌面端，接着读 `apps/desktop/electron.vite.config.ts`，再进入 `apps/desktop/src/main`、`apps/desktop/src/preload`。这是理解 Electron 分层的主线。
4. 对 CLI，先读 `apps/cli/src/program.ts`，再按命令域进入 `apps/cli/src/commands`，最后看 `api`、`auth`、`settings` 等支撑目录。
5. 对设备网关，先读 `apps/device-gateway/src/index.ts`，再读 `apps/device-gateway/src/DeviceGatewayDO.ts` 和 `apps/device-gateway/src/auth.ts`。
6. 如果要联系主产品能力，再回到根目录的 `src/spa`、`src/routes`、`src/server`、`packages/*`，因为 `apps` 很多能力是应用壳层，真实业务模型和共享协议通常在这些目录里。

## 常见误区

第一个误区是把 `apps/desktop` 当成完整前端页面实现。桌面端确实有 renderer HTML 入口，但大量页面和共享渲染能力来自根仓库 SPA 配置与共享包；`apps/desktop` 更偏 Electron 壳、主进程、本地能力和打包配置。

第二个误区是只看 `apps/desktop/src/main`，忽略 `preload`。Electron 应用的安全边界通常在 preload，渲染层不能随意直接访问 Node/Electron 能力，主进程能力需要通过桥接暴露。

第三个误区是把 `apps/cli/src/commands` 看成孤立脚本集合。实际上 `apps/cli/src/program.ts` 是命令树汇总点，命令之间共享认证、配置、API client、工具函数和 e2e 测试框架。新增或排查命令时，应同时检查注册入口和支撑模块。

第四个误区是把 `device-gateway` 理解成普通 REST 服务。当前片段显示它围绕 Cloudflare Durable Object 按 `userId` 分配连接对象，并同时承接 `/ws` 和 `/api/device/*` 两种入口，更像“用户设备连接网关”而不是传统业务 API。

第五个误区是认为 `apps` 是主项目所有运行入口。根项目还有 Next.js / SPA 的入口和大量 package 级构建入口；`apps` 只覆盖 CLI、Desktop、Device Gateway 这些独立应用形态。
