# 子系统：src/gateway/protocol/schema

## 解决什么问题

`src/gateway/protocol/schema` 是 Gateway 线协议的“契约定义层”。它用 `typebox` 描述 WebSocket/控制面 RPC 的请求参数、响应载荷、事件载荷、错误形状和快照结构，再由 `src/gateway/protocol/schema.ts` 统一导出，供 `src/gateway/protocol/index.ts` 生成运行时校验器和 TypeScript 类型使用。

这个目录解决的核心问题不是“某个接口怎么处理业务”，而是“客户端、节点、控制 UI、插件相关入口和 Gateway server 之间到底允许交换什么 JSON”。因此它处在协议边界上：字段是否必填、枚举有哪些、是否允许额外属性、请求帧和事件帧如何区分，都在这里变成稳定契约。`src/gateway/protocol/AGENTS.md` 也明确要求：schema 变更视为协议变更，不是本地重构；新增 Gateway method、event 或 payload field 应通过这里的 typed protocol definitions 落地。

## 相关目录和文件

`src/gateway/protocol/schema.ts` 是外部聚合入口，把 `schema/*.ts` 的 schema 全部 re-export。真正的总注册表在 `src/gateway/protocol/schema/protocol-schemas.ts`，它导入各领域 schema，并导出 `ProtocolSchemas` 这个 `Record<string, TSchema>`。

`src/gateway/protocol/schema/types.ts` 从 `ProtocolSchemas` 反推出 `ConnectParams`、`RequestFrame`、`SessionsSendParams`、`ToolsInvokeResult` 等静态类型，避免手写类型和运行时 schema 分叉。

领域文件按 Gateway 能力域拆分：`frames.ts` 定义顶层连接和帧结构；`primitives.ts` 放通用基础类型；`snapshot.ts` 描述初始状态快照；`agent.ts`、`sessions.ts`、`tasks.ts`、`nodes.ts`、`channels.ts`、`config.ts`、`cron.ts`、`devices.ts`、`plugins.ts` 等分别承载对应 RPC 或事件载荷。邻近的 `src/gateway/protocol/index.ts` 使用这些 schema 建 Ajv 校验器；`src/gateway/methods/registry.ts` 管 method 名称、handler 和权限 scope；`src/gateway/server/ws-connection/message-handler.ts` 在握手和消息处理时导入 `validateConnectParams`、`validateRequestFrame` 等校验入口。

## 核心对象

`ProtocolSchemas` 是本目录最重要的对象。它把分散在领域文件中的 `*Schema` 收敛成命名注册表，例如 `ConnectParams`、`HelloOk`、`GatewayFrame`、`SessionsCreateParams`、`ToolsInvokeParams`、`CronJob`、`DevicePairRequestedEvent`。这个注册表同时服务运行时校验、类型推导和协议文档/生成物同步。

`GatewayFrameSchema` 定义顶层消息帧，是 `RequestFrameSchema`、`ResponseFrameSchema`、`EventFrameSchema` 的 discriminated union，判别字段是 `type`。请求帧包含 `id`、`method`、可选 `params`；响应帧包含 `id`、`ok`、可选 `payload` 或 `error`；事件帧包含 `event`、可选 `payload`、`seq`、`stateVersion`。

`ConnectParamsSchema` 和 `HelloOkSchema` 描述连接握手。前者声明客户端协议版本范围、client 元数据、能力、权限、认证信息、设备身份等；后者返回协商后的协议版本、server 信息、可用 methods/events、初始 `snapshot`、认证上下文和连接策略。

`ErrorShapeSchema` 是协议级错误结构，包含 `code`、`message`、可选 `details`、`retryable`、`retryAfterMs`。`error-codes.ts` 则提供错误码集合，保证调用侧能围绕稳定 code 做分支。

## 运行流程

一次典型 Gateway WebSocket 交互会先进入连接握手。客户端发送的连接参数要满足 `ConnectParamsSchema`，server 侧通过 `src/gateway/protocol/index.ts` 暴露的 `validateConnectParams` 校验，再结合认证、设备配对、协议版本等逻辑决定是否返回 `HelloOk`。`HelloOk` 中的 `features.methods` 和 `features.events` 告诉客户端当前可调用的方法和可订阅事件。

握手成功后，客户端发送 `RequestFrame`，其中 `method` 是字符串，`params` 是待校验载荷。帧本身先由 `RequestFrameSchema` 校验；随后 method registry 找到对应 handler，具体参数类型则与 `ProtocolSchemas` 中的领域 schema 对齐。handler 执行业务逻辑后返回 `ResponseFrame`，成功时放 `payload`，失败时放 `ErrorShape`。

server 主动推送状态变化时使用 `EventFrame`。例如 agent、chat、session、node、device、shutdown、tick 等事件都在各领域 schema 中定义 payload 形状，再通过统一事件帧发送。根据当前片段推断，schema 注册表也承担生成客户端类型或协议文档的输入，因为 `frames.ts` 注释提到 discriminator 会让下游 codegen 生成更紧的类型。

## 上下游依赖

上游依赖主要是 `typebox` 和 Ajv。`schema/*.ts` 用 `Type.Object`、`Type.Array`、`Type.Union`、`Type.Literal` 等构造 JSON schema；`src/gateway/protocol/index.ts` 引入 Ajv，将 schema 编译为 `validate*` 函数，并提供 `formatValidationErrors`、`errorShape` 等协议辅助能力。`types.ts` 通过 `typebox` 的 `Static` 从运行时 schema 推导静态类型，形成单一事实来源。

下游依赖包括 Gateway WebSocket server、HTTP/RPC 方法实现、控制 UI、节点客户端、插件能力面和测试。`src/gateway/server/ws-connection/message-handler.ts` 消费连接与请求帧校验；`src/gateway/server-methods/*` 实现 schema 对应的业务方法；`src/gateway/methods/*` 管 method 注册和权限；`src/gateway/protocol/*.test.ts`、`src/gateway/protocol/schema/*.test.ts` 验证协议兼容性和具体字段规则。文档层面，`docs/gateway/protocol.md`、`docs/gateway/bridge-protocol.md`、`docs/concepts/architecture.md` 是需要同步的公开说明面。

## 修改时最容易踩的坑

第一，不能只改某个领域 schema。新增或改名 schema 后，通常还要同步 `protocol-schemas.ts`、`types.ts`、`schema.ts` 导出、server method handler、客户端使用处和测试。漏掉注册表会导致运行时校验或类型导出缺失。

第二，字段删除、改必填、收紧枚举、关闭旧形状都可能是破坏性协议变更。此目录的 scoped 规则要求优先 additive evolution；不兼容变更需要显式版本处理，并更新所有受影响客户端。

第三，不要把 gateway runtime、server method helper 或插件运行时代码反向导入 schema。协议模块应保持 data-first、低成本、无环依赖，否则会让协议契约在 import 阶段变重，甚至引入启动顺序问题。

第四，`additionalProperties: false` 很常见，意味着客户端多传字段会被拒。新增字段时要明确是否可选、默认值是否只存在于 schema 描述里，以及旧客户端是否能继续工作。

第五，`params` 和 `payload` 在顶层 frame 中是 `Unknown`，真正的语义校验依赖 method/event 对应 schema。不要误以为帧校验已经覆盖了业务载荷。

## 推荐阅读顺序

1. 先读 `src/gateway/protocol/AGENTS.md`，理解这里是协议边界，不是普通内部类型目录。
2. 读 `src/gateway/protocol/schema/frames.ts`，掌握连接握手、请求、响应、事件的顶层形状。
3. 读 `src/gateway/protocol/schema/protocol-schemas.ts`，看所有公开 schema 如何汇总成 `ProtocolSchemas`。
4. 读 `src/gateway/protocol/schema/types.ts`，理解运行时 schema 如何反推 TypeScript 类型。
5. 选择一个领域文件深入，例如 `sessions.ts`、`nodes.ts` 或 `channels.ts`，再对照对应的 `src/gateway/server-methods/*.ts` 看业务实现。
6. 最后读 `src/gateway/protocol/index.ts` 和 `src/gateway/server/ws-connection/message-handler.ts`，把 schema、Ajv 校验、握手和 request dispatch 串起来。
