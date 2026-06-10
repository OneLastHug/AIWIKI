# 目录：packages/remote-control-server

## 它负责什么

`packages/remote-control-server` 是项目里的自托管 Remote Control Server，简称 RCS。它的职责不是直接运行 Claude Code 的核心对话循环，而是作为“远程控制中枢”：接收 CLI/worker/浏览器控制台/ACP 客户端的连接，把环境、会话、工作项、事件流和权限动作组织起来，再通过 HTTP、WebSocket、SSE 等通道转发状态与消息。

从当前代码片段看，它主要覆盖四类能力：

1. 后端 API 服务：基于 `Hono`，入口在 `src/index.ts`，提供 `/v1`、`/v2`、`/web`、`/acp` 等路由组。
2. 远程环境与会话管理：环境、session、work item、worker 状态都暂存在 `src/store.ts` 的内存 `Map` 中，启动日志也明确提示 `In-memory store ready (no SQLite)`。
3. 实时传输：`src/transport` 负责 WebSocket、SSE、ACP relay、事件总线、payload 归一化等。
4. Web 控制台：`web` 是 React + Vite 前端，构建后由后端挂在 `/code` 路径下，用于查看环境、会话、事件流、权限请求和 ACP 直连视图。

这套目录更像一个“控制平面”而不是模型调用层。真正的 Claude Code 执行、桥接客户端和 worker 逻辑在仓库其他位置与它协作；本目录负责注册、分发、展示和转发。

## 直接子目录地图

`src` 是后端服务源码。它包含服务入口、路由、认证、状态存储、传输层和类型定义，是理解 RCS 的主线。

`src/auth` 放认证与跨域相关逻辑，包括 `api-key.ts`、`jwt.ts`、`middleware.ts`、`token.ts`、`cors.ts`。它支撑 `/web` 控制台鉴权、API key 校验、token 绑定等外围能力。

`src/routes` 是 HTTP 路由层，按协议和使用方分组。`routes/v1` 偏环境与传统 session ingress；`routes/v2` 偏 code session、worker、worker events；`routes/web` 服务 Web 控制台 API；`routes/acp` 处理 ACP 协议接入。

`src/services` 是业务服务层，放环境、会话、自动化状态、断连监控、传输和 work dispatch 等逻辑。路由通常不应直接承载复杂状态流，核心规则会下沉到这里。

`src/transport` 是实时通信层，包含普通 WebSocket、ACP WebSocket、ACP relay、SSE writer、event bus、client/ws payload 处理等。它是理解“消息如何在浏览器、server、worker/agent 之间流动”的关键目录。

`src/types` 放 API 与消息类型，例如 `types/api.ts`、`types/messages.ts`，用于约束路由响应、事件、payload 结构。

`src/__tests__` 是后端测试，覆盖 auth、routes、services、store、event bus、SSE writer、WebSocket handler、work dispatch 等。从测试文件名可以看出这个包的风险重点在认证、状态一致性和实时传输。

`web` 是前端控制台。顶层有 `index.html`、`vite.config.ts`、`tsconfig.json`，源码在 `web/src`，UI 组件在 `web/src/components`，页面在 `web/src/pages`，API 客户端和 SSE/ACP 客户端分别在 `web/src/api`、`web/src/acp`、`web/src/lib`。

`web/components` 是独立的 UI 组件目录。根据当前片段未展开其内容，推断可能与 Radix/shadcn 风格组件或复用 UI 基础件有关，依据是包内存在 `components.json`，依赖中也包含多项 Radix UI 包。

## 关键入口

后端总入口是 `src/index.ts`。它创建 `Hono` app，注册通用 logger、中间件、CORS、健康检查、静态文件服务和所有 API 路由。这里也是理解路由挂载关系的第一站。

前端入口是 `web/src/main.tsx` 和 `web/src/App.tsx`。`App.tsx` 使用浏览器路径实现简单路由：`/code/` 显示 `Dashboard`，`/code/:sessionId` 显示 `SessionDetail`，查询参数 `sid` 用于绑定 CLI session，`acp=1` 用于进入 ACP direct 视图。

包入口和命令定义在 `package.json`。后端开发命令是 `bun run --watch src/index.ts`，前端开发命令是进入 `web` 后跑 Vite，生产时可先构建 `web/dist`，再由后端从 `/code` 提供 SPA。

容器入口相关文件是 `Dockerfile`。当前未展开 Dockerfile 内容，但按目录角色看，它服务于 RCS 自托管部署。

配置入口是 `src/config.ts`。`src/index.ts` 从这里读取 `port`、`host`、`version`、`baseUrl`、`disconnectTimeout`、`wsIdleTimeout`、`wsKeepaliveInterval` 等运行参数。

## 主流程位置

服务启动主流程在 `src/index.ts`：创建 Hono app，标准化双斜杠路径，挂 `/health`，配置 `/code` 静态资源与 SPA fallback，然后依次挂载 `/v1/environments`、`/v1/sessions`、`/v1/session_ingress`、`/v2/session_ingress`、`/v1/code/sessions`、`/web` 和 `/acp`。最后导出 Bun server 配置，并在 `SIGINT`、`SIGTERM` 时关闭普通 WS、ACP WS、ACP relay 连接。

环境注册和工作分发主线在 `src/routes/v1/environments.ts`、`src/routes/v1/environments.work.ts`、`src/services/environment.ts`、`src/services/work-dispatch.ts`。根据命名推断，环境先注册并保持 active 状态，然后 server 将 session work 派发给合适环境或 worker。

会话主流程在 `src/routes/v1/sessions.ts`、`src/routes/v2/code-sessions.ts`、`src/services/session.ts`、`src/store.ts`。`services/session.ts` 负责创建普通 session 和 code session，并处理 `cse_` 与 `session_` 前缀之间的兼容转换。它还提供 session 归档、状态更新、owner UUID 绑定和事件发布。

worker 状态与事件主线在 `src/routes/v2/worker.ts`、`src/routes/v2/worker-events.ts`、`src/routes/v2/worker-events-stream.ts`、`src/services/automationState.ts`、`src/services/transport.ts`、`src/transport/event-bus.ts`。状态变更会进入 event bus，再通过 SSE 或 WebSocket 被前端/客户端消费。

Web 控制台主流程在 `web/src/App.tsx`、`web/src/pages/Dashboard.tsx`、`web/src/pages/SessionDetail.tsx`。`Dashboard` 是列表和入口页，`SessionDetail` 是单个会话的控制与事件视图；配套 API 在 `web/src/api/client.ts`、实时流在 `web/src/api/sse.ts`。

ACP 主流程在 `src/routes/acp/index.ts`、`src/transport/acp-ws-handler.ts`、`src/transport/acp-relay-handler.ts`、`src/transport/acp-sse-writer.ts`，前端对应 `web/src/acp/client.ts`、`web/src/acp/relay-client.ts`、`web/src/components/ACPDirectView.tsx`。根据当前片段推断，它既支持 ACP agent WebSocket 接入，也支持浏览器侧 ACP direct/relay 体验，依据是后端关闭函数包含 `closeAllAcpConnections`、`closeAllRelayConnections`，前端也有 ACP direct 参数分支。

## 推荐阅读顺序

1. 先读 `package.json`，确认这是独立包、运行命令和主要依赖：`Hono`、React、Vite、Radix、SSE/WebSocket 相关工具。
2. 再读 `src/index.ts`，把所有路由组、静态资源路径、WebSocket 配置和 shutdown 流程画出来。
3. 接着读 `src/store.ts`，理解核心数据模型：user、token、environment、session、work item、session worker、session owner。
4. 然后读 `src/services/session.ts` 和 `src/services/environment.ts`，掌握 session/environment 的业务规则，而不是直接陷入每个 route 文件。
5. 再看 `src/routes/v1`、`src/routes/v2`、`src/routes/web`、`src/routes/acp`，把 HTTP API 与服务层函数对应起来。
6. 最后读 `src/transport` 和 `web/src`。实时传输和前端状态依赖前面的概念，放后面读更顺。

## 常见误区

不要把这个目录理解成完整 Claude Code CLI。它是 RCS server 和 Web 控制台，核心模型请求、CLI REPL、工具执行体系主要在仓库其他目录。

不要以为这里有持久数据库。当前 `src/store.ts` 是内存 `Map`，服务重启后状态会丢失。代码中也明确有 `no SQLite` 的启动提示。

不要把 `/web` 和 `/code` 混为一谈。`/web` 是给 Web 控制台调用的后端 API 路由；`/code` 是前端 SPA 的静态访问路径和页面路由前缀。

不要只看 REST route。这个目录的重要行为很多在 `src/transport`：WebSocket、SSE、ACP relay、event bus 才是远程控制体验“实时”的来源。

不要忽略 session ID 前缀转换。`services/session.ts` 中存在 `cse_` 与 `session_` 的兼容逻辑，前端展示和后端 code session 可能不是同一个外观 ID。

不要把 `web/src/App.tsx` 当成复杂路由系统。当前它是轻量路径解析：根据 `/code/:sessionId`、`?sid=`、`?uuid=`、`?acp=1` 切换 Dashboard、SessionDetail 或 ACPDirectView。
