# 目录：src/gateway

## 它负责什么

`src/gateway` 是 OpenClaw 的本地网关层，负责把 CLI、Control UI、移动端、插件、节点、模型兼容 HTTP API 等入口统一接到同一个运行时控制面。它既包含服务端启动、HTTP/WebSocket 接入、鉴权、方法分发、会话与聊天流转，也包含客户端调用网关的封装。可以把它理解为“OpenClaw 运行时对外暴露能力的中枢”：外部请求进入后，先经过连接信息、TLS、鉴权、scope、method registry，再落到具体的 server method、session/chat、plugin/node、model/tool 等子系统。

这个目录很大，文件命名呈现出明显的按功能切分风格：`server-*` 多数是服务端运行期模块，`client*` 和 `call*` 是客户端连接与调用，`auth*`、`credentials*`、`method-scopes*` 是访问控制基础设施，`session-*` 和 `server-chat*` 处理会话、聊天、事件和 transcript，`openai-http*`、`openresponses-http*`、`mcp-http*`、`models-http*` 等提供 HTTP 兼容面。根据当前片段推断，Gateway 不是单一服务器文件，而是一组“启动装配 + 协议定义 + 方法注册 + 运行时服务 + 多种 HTTP/WS 表面”的集合，依据是 `src/gateway/server.ts`、`src/gateway/server.impl.ts`、`src/gateway/server-http.ts`、`src/gateway/server-ws-runtime.ts`、`src/gateway/methods/registry.ts`、`src/gateway/server-methods.ts` 同时存在且职责命名互补。

## 直接子目录地图

`src/gateway/methods` 是 Gateway RPC 方法描述与注册的小目录。核心文件包括 `descriptor.ts`、`registry.ts`、`core-descriptors.ts`，用于把方法名、描述、scope 或处理器元数据组织成可查询的 registry。阅读 Gateway 的“有哪些 RPC 方法、如何被声明和分类”时先看这里。

`src/gateway/protocol` 是客户端与服务端共享的协议契约层。它有自己的 `AGENTS.md`，说明这是更敏感的协议边界。目录里有 `index.ts`、`schema.ts`、`version.ts`、`client-info.ts`、`startup-unavailable.ts` 以及 `schema/`，还带有多组 contract/validator 测试。它定义消息形状、协议版本、客户端信息、错误细节和推送相关结构，是跨端兼容的根。

`src/gateway/server` 是较新的服务端内部拆分区，放置 HTTP 监听、WebSocket connection、readiness、health、hooks、TLS、plugin HTTP route、preauth budget 等运行时部件。它更偏底层 transport 和 server infrastructure，例如 `http-listen.ts`、`ws-connection.ts`、`readiness.ts`、`health-state.ts`、`plugins-http.ts`。

`src/gateway/server-methods` 是 RPC 业务方法实现区，也有自己的 `AGENTS.md`。这里按方法族拆分：`agents.ts`、`chat.ts`、`sessions.ts`、`config.ts`、`models.ts`、`channels.ts`、`nodes.ts`、`skills.ts`、`tools-invoke.ts`、`doctor.ts`、`usage.ts`、`talk.ts` 等。它回答“某个 Gateway method 最终做什么”。

`src/gateway/test` 放少量跨文件测试辅助内容。根目录下同时有大量 colocated `*.test.ts`，所以测试并不都集中在这个子目录。

`src/gateway/server/__tests__` 是 `server` 子目录自己的测试区域；根目录和各功能文件旁还有大量同名测试，说明这个目录采用“重点模块旁置测试 + 子目录局部测试”的混合布局。

## 关键入口

`src/gateway/server.ts` 和 `src/gateway/server.impl.ts` 是理解服务端装配的第一入口。前者通常承担外部导出或轻量入口角色，后者从命名看更像完整实现。它们与 `src/gateway/server-http.ts`、`src/gateway/server-ws-runtime.ts`、`src/gateway/server-runtime-state.ts`、`src/gateway/server-runtime-services.ts`、`src/gateway/server-runtime-handles.ts` 共同构成 Gateway server 的启动、运行状态、服务依赖和连接处理骨架。

`src/gateway/call.ts` 是客户端侧发起 Gateway 调用的重要入口。当前片段显示它导入 `GatewayClient`、`startGatewayClientWhenEventLoopReady`、`buildGatewayConnectionDetailsWithResolvers`、`MIN_CLIENT_PROTOCOL_VERSION`、`PROTOCOL_VERSION`，并定义 `CallGatewayOptions`、`GatewayTransportError`、`buildGatewayConnectionDetails`、`resolveExplicitGatewayAuth` 等。这说明 CLI 或内部代码调用 Gateway 时，会先解析连接详情、凭据、协议版本和鉴权策略，再创建客户端发起 method request。

`src/gateway/client.ts` 是 Gateway 客户端实现入口，配合 `client-bootstrap.ts`、`client-start-readiness.ts`、`connection-details.ts` 使用。想理解“调用方怎么连上 Gateway、何时认为连接 ready、如何超时或重连”，应从这些文件开始。

`src/gateway/protocol/index.ts` 是协议公共导出入口，`src/gateway/protocol/schema.ts` 是 schema 聚合入口，`src/gateway/protocol/version.ts` 维护协议版本。任何改动协议形状、客户端能力、native protocol level、startup unavailable 等行为时，都应先确认这里的契约。

`src/gateway/server-methods.ts` 和 `src/gateway/server-methods-list.ts` 是 server method 组装层。前者把具体 method handlers 接进 Gateway，后者从命名看提供方法列表或枚举。具体方法实现则继续下钻到 `src/gateway/server-methods/*.ts`。

`src/gateway/methods/registry.ts` 是 method registry 的中心；`src/gateway/method-scopes.ts`、`src/gateway/operator-scopes.ts`、`src/gateway/role-policy.ts` 则是方法访问权限判断的关键配套。

## 主流程位置

启动主流程大致在 `src/gateway/server.ts`、`src/gateway/server.impl.ts`、`src/gateway/server-startup-config.ts`、`src/gateway/server-startup-early.ts`、`src/gateway/server-startup-plugins.ts`、`src/gateway/server-startup-post-attach.ts` 一带。这里负责读取运行配置、初始化认证材料、装配插件、创建运行时状态，并把 HTTP/WS handler 挂到 server 上。根据 `src/gateway/AGENTS.md`，Gateway 启动和测试路径要避免为了静态插件描述而加载完整 bundled plugin runtime，因此启动路径也承担性能与边界约束。

HTTP 请求主流程在 `src/gateway/server-http.ts` 和 `src/gateway/server/*.ts`。通用 HTTP 工具位于 `src/gateway/http-common.ts`、`src/gateway/http-utils.ts`、`src/gateway/http-auth-utils.ts`、`src/gateway/http-endpoint-helpers.ts`。模型、MCP、OpenAI 兼容、OpenResponses、embeddings、sessions history、tools invoke 等专用 HTTP 表面分别落在 `models-http.ts`、`mcp-http.ts`、`openai-http.ts`、`openresponses-http.ts`、`embeddings-http.ts`、`sessions-history-http.ts`、`tools-invoke-http.ts`。

WebSocket/RPC 主流程在 `src/gateway/server-ws-runtime.ts`、`src/gateway/server/ws-connection.ts`、`src/gateway/client.ts`、`src/gateway/call.ts`、`src/gateway/server-methods.ts`、`src/gateway/methods/registry.ts` 之间。请求从 client 组装连接和协议版本开始，经 WS connection 完成握手、鉴权、scope 检查，再进入 method registry 和具体 server-method handler。

聊天与会话主流程集中在 `src/gateway/server-chat.ts`、`src/gateway/server-chat-state.ts`、`src/gateway/server-session-events.ts`、`src/gateway/session-utils.ts`、`src/gateway/session-transcript-files.fs.ts`、`src/gateway/server-methods/chat.ts`、`src/gateway/server-methods/sessions.ts`。这条线处理 agent event、assistant text projection、session lifecycle、transcript 持久化、abort/reset/list/send 等行为。

插件、节点和通道相关流程分布在 `src/gateway/server-plugins.ts`、`src/gateway/server-plugin-bootstrap.ts`、`src/gateway/plugin-*`、`src/gateway/node-*`、`src/gateway/server-methods/channels.ts`、`src/gateway/server-methods/nodes.ts`。它们负责把 Gateway 的控制面连接到插件运行时、channel 状态、node pairing/invoke/pending work 等能力。

## 推荐阅读顺序

1. 先读 `src/gateway/AGENTS.md`，掌握 Gateway 热路径和插件加载边界，尤其是不要在 HTTP/server 路径为了静态信息加载完整 channel plugin registry。
2. 读 `src/gateway/protocol/index.ts`、`src/gateway/protocol/schema.ts`、`src/gateway/protocol/version.ts`，先建立协议和版本概念。
3. 读 `src/gateway/call.ts`、`src/gateway/client.ts`、`src/gateway/connection-details.ts`，从调用方视角理解连接、凭据、TLS、ready 和错误。
4. 读 `src/gateway/server.ts`、`src/gateway/server.impl.ts`、`src/gateway/server-http.ts`、`src/gateway/server-ws-runtime.ts`，建立服务端装配图。
5. 读 `src/gateway/methods/registry.ts`、`src/gateway/server-methods.ts`、`src/gateway/server-methods-list.ts`，理解 method 如何声明和分发。
6. 按需求进入具体业务族：会话聊天看 `server-chat.ts` 与 `server-methods/chat.ts`；配置看 `server-methods/config.ts`；插件看 `server-plugins.ts`；节点看 `server-methods/nodes.ts`；模型 HTTP 看 `models-http.ts`、`openai-http.ts`、`openresponses-http.ts`。

## 常见误区

不要把 `src/gateway/server-methods` 当成底层 transport。它主要是业务 RPC handler；真正的 HTTP/WS 接入、连接预算、readiness、health、TLS、plugin route 等更靠近 `src/gateway/server` 和根下 `server-http.ts`、`server-ws-runtime.ts`。

不要只看 `src/gateway/server.ts` 就认为 Gateway 是单文件入口。这个目录明显把启动、运行状态、HTTP 表面、WS 表面、method registry、会话、插件、节点、鉴权分散到多个模块，单个文件只能解释一段流程。

不要绕过 `src/gateway/protocol` 直接改消息形状。协议版本、schema、客户端信息和 native/client 兼容测试都在这里附近；协议变更通常需要同时考虑客户端、服务端和测试契约。

不要在 Gateway 热路径中随意加载完整插件运行时。`src/gateway/AGENTS.md` 明确要求 plugin-owned Gateway 行为优先使用轻量 public artifact resolver，避免 server/http 路径为了静态问题加载 broad bundled channel registries。

不要把所有鉴权都理解成一个 token 检查。这里有 `auth-*`、`credentials-*`、`connection-auth.ts`、`method-scopes.ts`、`operator-scopes.ts`、`role-policy.ts`、`origin-check.ts`、`preauth` 等多层控制；不同入口和方法族可能要求不同 scope。
