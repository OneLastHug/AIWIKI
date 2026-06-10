# 目录：packages/desktop/src/renderer/api

## 它负责什么

`packages/desktop/src/renderer/api` 是 renderer 侧预留的一层轻量 API 客户端封装，目标是把浏览器环境中的 HTTP 请求、WebSocket 连接和通用响应类型集中起来。它并不是业务 API 的集中目录，也不包含具体的 `agents`、`assistants`、`settings` 等资源模块；从当前片段看，它更像一个基础工具层：给上层代码提供 `createApiClient`、`createWebSocketClient`、`ApiError`、`ApiResponse` 这些通用能力。

这个目录需要放在 Electron 架构里理解。renderer 进程不能直接使用 Node.js 能力，跨进程能力主要通过 `ipcBridge` 走 `packages/desktop/src/common/adapter/ipcBridge.ts` 以及 process 侧 bridge provider。HTTP 到 aioncore/backend 的主通道，在当前代码中更多由 `packages/desktop/src/common/adapter/httpBridge.ts` 承担：它负责解析 backend port、兼容 Electron Desktop 与 WebUI browser mode、封装 `httpRequest`、`BackendHttpError`，并提供和 bridge 类似形状的 provider/emitter 工厂。因此，`renderer/api` 不是当前全局唯一的后端访问入口，而是一个较独立、较原始的 HTTP/WS 工具包。

根据当前片段推断，这个目录可能是早期或备用的 renderer API 抽象：文件内有完整实现和导出，但在 `packages/desktop/src` 范围内没有发现业务代码直接引用 `createApiClient` 或 `createWebSocketClient`。实际业务页面与 hooks 目前大量通过 `ipcBridge`、`httpBridge`、原生 `fetch`、`XMLHttpRequest`、`EventSource` 访问后端能力。

## 直接子目录地图

这个目录当前没有直接子目录，只有少量顶层文件：

`packages/desktop/src/renderer/api/index.ts` 是聚合导出口，统一 re-export HTTP client、WebSocket client 和响应类型。外部如果要使用这个目录，理论上应该从这里导入，而不是逐个深路径导入。

`packages/desktop/src/renderer/api/client.ts` 是 HTTP client 工厂。核心导出是 `createApiClient(baseURL)` 和 `ApiError`。它基于浏览器 `fetch`，提供 `get`、`post`、`put`、`patch`、`delete` 五个方法；请求体存在时自动按 JSON 序列化，并设置 `Content-Type: application/json`。

`packages/desktop/src/renderer/api/ws.ts` 是 WebSocket client 工厂。核心导出是 `createWebSocketClient(url, options?)`。它维护事件名到 handler 集合的映射，支持自动重连、指数退避、心跳 ping、订阅和取消订阅。

`packages/desktop/src/renderer/api/types.ts` 只定义通用响应形状 `ApiResponse<T>`，字段包括 `success`、`data`、`error`、`meta`。它描述的是一种常见后端响应 envelope，但 `client.ts` 本身并不会自动 unwrap `data`。

## 关键入口

最明显的入口是 `packages/desktop/src/renderer/api/index.ts`。它导出：

`createApiClient`：创建一个绑定 `baseURL` 的 HTTP client。调用者需要自己提供 baseURL，然后传入完整 path，例如 `/api/foo`。它返回的方法都是泛型方法，调用方用 `api.get<Foo>(...)` 指定返回类型。

`ApiError`：当 HTTP 状态码不是 2xx 时抛出。它携带 `status`、`statusText`、`body` 三个只读字段。错误体会优先尝试按 JSON 解析，失败后退回文本。

`createWebSocketClient`：创建一个事件式 WebSocket 客户端。消息格式被约定为 `{ event, payload }`。收消息时按 `event` 分发给订阅者；发消息时同样序列化为这个结构。

`ApiResponse<T>`：通用响应类型。注意它只是类型声明，不代表所有请求都会自动返回这个结构，也不代表请求层会自动检查 `success`。

从工程实际入口看，还需要同时关注 `packages/desktop/src/common/adapter/httpBridge.ts`。它虽然不在本目录内，但承担了当前更核心的 backend base URL 解析与 HTTP 请求职责。renderer 里 `DirectorySelectionModal.tsx`、`FileService.ts`、`WeixinConfigForm.tsx`、`OfficeWatchViewer.tsx` 等代码会使用 `getBaseUrl()` 拼接 `/api/...`，而 `hooks/mcp/catalog.ts` 等位置会直接使用 `httpRequest`。

## 主流程位置

HTTP 主流程在 `client.ts` 的内部 `request<T>()`：

调用方先通过 `createApiClient(baseURL)` 得到 client；随后调用 `get/post/put/patch/delete`；这些方法统一进入 `request<T>(baseURL, method, path, body, options)`；`request` 拼出 URL、组装 headers、把 body JSON 序列化；再调用 `fetch`；如果响应失败，解析错误体并抛出 `ApiError`；如果成功且 `Content-Type` 包含 `application/json`，返回 JSON，否则返回 `undefined as T`。

这里有两个学习重点。第一，`request` 不会自动给 path 添加 `/api`，path 完全由调用方决定。第二，它不会 unwrap `{ success, data }` 这种 envelope，返回什么取决于后端响应 JSON 本身。和它相比，`httpBridge.ts` 的 `httpRequest<T>()` 会在 JSON 对象包含 `data` 字段时返回 `json.data as T`，这是两个封装在行为上的重要差异。

WebSocket 主流程在 `ws.ts` 的 `createWebSocketClient()`：

创建时立即执行 `connect()`；`connect()` 内部 new `WebSocket(url)`，注册 `open`、`message`、`close`、`error` 监听；连接打开后重置重连次数并启动 heartbeat；收到消息后尝试 JSON.parse，再按 `msg.event` 找到 handlers 并逐个调用；连接关闭后停止 heartbeat，如果不是主动 `close()`，就进入 `scheduleReconnect()`；重连延迟从 `initialReconnectDelayMs` 开始按 2 的幂增长，并受 `maxReconnectDelayMs` 限制；主动 `close()` 会清理重连 timer、heartbeat timer、WebSocket 实例和所有 listeners。

实际业务主流程则更多分布在邻近目录。例如 `/api/agents` 数据在 `packages/desktop/src/renderer/hooks/agent/useAgents.ts` 中通过 SWR 做统一缓存，`packages/desktop/src/renderer/main.tsx` 会在配置初始化时预取 agents；很多会话、文件、预览、assistant 操作则直接走 `ipcBridge`。因此阅读主流程时，不应只停在 `renderer/api`，还要顺着 `common/adapter/httpBridge.ts` 和相关 hooks 看真实调用路径。

## 推荐阅读顺序

第一步读 `packages/desktop/src/renderer/api/index.ts`，先确认这个目录对外暴露的公共表面。它很短，能快速建立“这里是聚合导出层”的认知。

第二步读 `packages/desktop/src/renderer/api/client.ts`，重点看 `request<T>()` 的错误处理、JSON 处理、`RequestOptions` 支持的 `headers` 与 `signal`。这能帮助理解如果未来业务直接使用 `createApiClient`，它会如何表现。

第三步读 `packages/desktop/src/renderer/api/ws.ts`，重点看事件协议 `{ event, payload }`、订阅表 `Map<string, Set<EventHandler>>`、重连策略和 heartbeat。这里是目录中逻辑最多的文件。

第四步读 `packages/desktop/src/renderer/api/types.ts`，确认 `ApiResponse<T>` 只是约定响应结构的类型，不要过度解读为请求层强制协议。

第五步跳到 `packages/desktop/src/common/adapter/httpBridge.ts`，把它和 `client.ts` 对比。当前项目实际更常用的是这里的 `getBaseUrl()`、`httpRequest()`、`BackendHttpError`，它还处理 Electron 与 WebUI 两种运行模式。

第六步再看代表性业务调用点，例如 `packages/desktop/src/renderer/hooks/agent/useAgents.ts`、`packages/desktop/src/renderer/services/FileService.ts`、`packages/desktop/src/renderer/components/settings/DirectorySelectionModal.tsx`。这些位置能说明后端接口在 UI 层是如何被缓存、上传、浏览文件或发起 SSE/EventSource 的。

## 常见误区

不要把 `packages/desktop/src/renderer/api` 当成所有后端接口的业务 SDK。它没有按资源拆分的 API 模块，也没有集中列出 `/api/agents`、`/api/providers`、`/api/settings/client` 等端点。当前业务访问分散在 hooks、services、components 以及 `ipcBridge` 封装中。

不要以为 `ApiResponse<T>` 会被 `createApiClient` 自动处理。`client.ts` 只在响应是 JSON 时返回解析结果；如果后端返回 `{ success: true, data: ... }`，调用方拿到的仍是整个对象，而不是自动解出的 `data`。若代码使用的是 `httpBridge.ts` 的 `httpRequest<T>()`，行为又不同，它会在存在 `data` 字段时返回 `data`。

不要混淆 `ApiError` 和 `BackendHttpError`。`ApiError` 属于 `renderer/api/client.ts`，字段比较简单；`BackendHttpError` 属于 `common/adapter/httpBridge.ts`，包含 `code`、`backendMessage`、`details` 等结构化后端错误信息，并提供 `isBackendHttpError()`。当前业务里处理特定后端错误时，更可能需要后者。

不要忽略运行模式差异。Electron Desktop 中请求通常需要指向本机 backend port；WebUI browser mode 中请求应走同源 `/api/*` 和 `/ws` 代理。`renderer/api/client.ts` 要求调用者自己传 baseURL，不负责识别这些模式；`httpBridge.ts` 的 `getBaseUrl()` 和内部 WS URL 逻辑才处理了这部分环境差异。

不要把 `ws.ts` 的事件协议理解为浏览器原生 WebSocket 的通用协议。这里约定消息必须是 JSON，且包含 `event` 和 `payload`。如果后端发送非 JSON 或缺少对应事件名，当前实现会忽略 malformed message 或找不到 handler，不会向外抛错。
