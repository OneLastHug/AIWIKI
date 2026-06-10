# 子系统：src/gateway/server-methods

## 解决什么问题

`src/gateway/server-methods` 是 Gateway 的 RPC 方法实现层。它把 WebSocket 或插件运行时发来的 `method + params` 请求，拆成一组按业务域维护的 handler：聊天、会话、配置、模型、频道、节点、技能、工具、审批、诊断、更新、TTS、语音唤醒等。这个目录本身不负责 socket 连接、认证握手或方法目录注册的全部逻辑，而是承接已经进入 Gateway 请求管线后的“具体动作”。

它的核心价值是把控制面和运行面方法统一成 `GatewayRequestHandlers` 形态：每个方法拿到标准化的 `req`、`params`、`client`、`respond`、`context`，再调用对应下游服务。根据当前片段推断，这里是 OpenClaw 控制 UI、CLI、Webchat、设备节点、插件 Gateway 方法之间共享的一层 RPC 业务适配层，依据是 `src/gateway/server-methods.ts` 会统一懒加载本目录模块，并由 `src/gateway/server/ws-connection/message-handler.ts` 在收到消息后调用。

## 相关目录和文件

入口聚合在 `src/gateway/server-methods.ts`，它不在目标目录内，但决定了本目录文件如何被加载、授权和调度。`src/gateway/server-methods/types.ts` 只重导出 `shared-types.ts`，后者定义 `GatewayClient`、`GatewayRequestContext`、`RespondFn`、`GatewayRequestHandlerOptions`、`GatewayRequestHandlers` 等共享类型。

目标目录内的业务文件按方法域命名：`chat.ts` 处理 `chat.send`、`chat.history`、`chat.abort`、`chat.inject`；`sessions.ts` 处理会话列表、创建、发送、压缩、恢复、删除；`config.ts` 处理配置读取、schema、patch、apply 和打开配置文件；`channels.ts` 处理频道状态与启停；`nodes.ts`、`nodes-pending.ts` 处理节点配对、调用和 pending 队列；`agent.ts`、`agents.ts` 处理 agent 运行与 agent 配置；`skills.ts`、`skills-upload.ts` 处理技能搜索、安装、更新和上传；`tools-catalog.ts`、`tools-effective.ts`、`tools-invoke.ts` 处理工具目录、有效工具和调用。测试文件大多与被测文件同目录，例如 `chat.*.test.ts`、`config.*.test.ts`、`nodes.*.test.ts`。

邻近关键目录包括 `src/gateway/protocol`，提供参数校验、错误码和请求帧类型；`src/gateway/methods`，提供方法 descriptor 和 registry；`src/gateway/server`、`src/gateway/server.impl.ts`，负责服务启动、运行态对象和 WebSocket 挂载；`src/config`、`src/agents`、`src/channels`、`src/plugins`、`src/sessions`，是各 handler 的主要业务下游。

## 核心对象

`GatewayRequestHandlers` 是最重要的对象形态，本质是 `Record<string, GatewayRequestHandler>`。每个业务文件通常导出一个形如 `chatHandlers`、`configHandlers`、`sessionsHandlers`、`channelsHandlers` 的方法表。

`GatewayRequestContext` 是 handler 的依赖容器，包含 `deps`、`cron`、`getRuntimeConfig`、`loadGatewayModelCatalog`、健康检查、广播函数、节点订阅、会话事件订阅、运行中 chat 状态、dedupe map、wizard sessions、频道 runtime snapshot、频道启停函数、voicewake 广播等。它让 handler 不直接持有 Gateway server 实例，而是通过显式能力调用外部系统。

`RespondFn` 是统一响应出口，handler 通过 `respond(ok, payload, error, meta)` 返回结果。错误通常用 `src/gateway/protocol/index.ts` 的 `errorShape` 和 `ErrorCodes` 构造。

`coreGatewayHandlers` 定义在 `src/gateway/server-methods.ts`，通过 `lazyHandlerModule` 和 `createLazyCoreHandlers` 把方法名映射到懒加载模块。这样 Gateway 启动时不必一次加载聊天、会话、技能、模型等重模块，符合 `src/gateway/AGENTS.md` 中对 Gateway hot paths 的要求。

`handleGatewayRequest` 是请求分发核心：它建立或接收 `GatewayMethodRegistry`，做角色与 scope 授权、startup unavailable 检查、控制面写操作限流，然后找到 handler，并在 `withPluginRuntimeGatewayRequestScope` 中执行。

## 运行流程

典型链路是：客户端通过 WebSocket 发来请求帧；`src/gateway/server/ws-connection/message-handler.ts` 解析消息并构造 `respond`；随后动态导入 `src/gateway/server-methods.ts`，调用 `handleGatewayRequest`。`handleGatewayRequest` 先用方法 registry 判断方法是否存在、是否属于控制面写操作、当前 client 角色和 scopes 是否允许访问。通过后，它把 `req.params` 规范成 `params`，连同 `client`、`context` 和 `respond` 交给目标 handler。

如果请求是 `chat.send`，会进入 `chat.ts`，再向 agent/session、附件、媒体、自动回复、插件 hook、广播等子系统推进；如果是 `config.patch` 或 `config.apply`，会进入 `config.ts`，读取配置快照、校验 base hash、执行 schema 校验和写入流程；如果是 `sessions.send`，`sessions.ts` 会复用聊天发送能力，把 session 维度的 API 转到 chat 运行链路。

插件方法和额外 Gateway 方法不直接写进所有 core handler。`src/gateway/server-methods.ts` 会把 core descriptors、plugin descriptors 和 aux handlers 合成 registry；`src/gateway/server.impl.ts` 在启动后把插件 registry 的 gateway handlers 与额外 handlers 一起挂到 WebSocket 层。

## 上下游依赖

上游主要是 `src/gateway/server.impl.ts`、`src/gateway/server-ws-runtime.ts`、`src/gateway/server/ws-connection/message-handler.ts`，它们负责启动状态、连接生命周期、认证结果、方法 registry 和请求上下文。插件运行时也可通过 Gateway request scope 回调 Gateway 方法，因此 `handleGatewayRequest` 必须包在插件运行时 scope 内。

下游依赖按业务分散：配置写入依赖 `src/config` 和 `src/gateway/config-write-flow.ts`；聊天依赖 `src/agents`、`src/sessions`、`src/media`、`src/auto-reply`、`src/plugins`；频道启停依赖 `src/channels` 和插件 runtime；节点调用依赖 `src/gateway/node-registry`、pending 队列和 plugin node capability；模型列表依赖 Gateway model catalog；审批依赖 `ExecApprovalManager`；健康、日志、诊断、更新分别依赖对应 command、infra 或 runtime 模块。

协议层依赖非常关键：handler 不应随意接受自由形状参数，而应优先使用 `src/gateway/protocol` 中的 validator、schema primitive 和 `ErrorCodes`。方法权限依赖 `src/gateway/method-scopes.ts`、`src/gateway/role-policy.ts` 和 method registry 的分类结果。

## 修改时最容易踩的坑

第一，新增或改名方法不能只改某个 `*.ts` handler，还要确保 `src/gateway/server-methods.ts` 的 `coreGatewayHandlers`、`src/gateway/methods` 的 descriptor 分类、scope 策略和测试同步。否则方法可能能实现但无法发现、无法授权，或被当作未知方法。

第二，配置和控制面写操作有并发保护。`config.ts` 使用 base hash 防止覆盖用户刚改过的配置，并通过 `config-write-flow.ts` 处理重载、共享认证变化和 restart handoff。绕开这些流程容易造成配置丢失、认证状态不一致或需要重启却没有提示。

第三，错误响应要走 `respond` 和 `errorShape`，不要抛出面向客户端的裸错误。外层虽然会 catch 并返回 `UNAVAILABLE`，但这会丢失具体错误码和可恢复信息。

第四，Pi session transcript 有 `parentId` 链/DAG 约束。`src/gateway/server-methods/AGENTS.md` 明确要求不要通过原始 JSONL 追加 Pi `type: "message"`，应使用 `SessionManager.appendMessage(...)` 或等价封装，否则可能破坏 compaction/history 的叶子路径。

第五，Gateway 启动热路径要求懒加载和轻量解析。不要为了静态描述符在 server method 中加载完整 bundled plugin registry；新增插件拥有的 Gateway 描述符时，需要保持轻量 artifact 与完整插件导出一致。

## 推荐阅读顺序

1. 先读 `src/gateway/server-methods/shared-types.ts`，理解 handler 的标准输入输出和 `GatewayRequestContext` 能力边界。
2. 再读 `src/gateway/server-methods.ts`，掌握懒加载、`coreGatewayHandlers`、授权、限流、registry 合成和 `handleGatewayRequest`。
3. 接着读 `src/gateway/server/ws-connection/message-handler.ts` 中调用 `handleGatewayRequest` 的片段，理解请求如何从 socket 进入方法层。
4. 选一个控制面方法读 `src/gateway/server-methods/config.ts`，理解校验、base hash、写入和错误响应风格。
5. 选一个运行面方法读 `src/gateway/server-methods/chat.ts` 或 `sessions.ts`，理解 agent、session、媒体、广播和插件 hook 的联动。
6. 最后按需要阅读 `channels.ts`、`nodes.ts`、`skills.ts`、`tools-invoke.ts` 等具体业务域，并对照同名 `*.test.ts` 看边界条件。
