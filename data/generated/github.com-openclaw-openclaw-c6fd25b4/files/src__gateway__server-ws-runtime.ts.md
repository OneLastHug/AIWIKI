# 文件：src/gateway/server-ws-runtime.ts

## 一句话定位

`src/gateway/server-ws-runtime.ts` 是 Gateway 启动阶段挂载 WebSocket 连接处理器的轻量 runtime 适配层：它不直接处理 WebSocket 帧，而是把 `server.impl.ts` 已经准备好的运行时状态、日志器、鉴权、方法注册表、广播能力和请求上下文，整理后交给 `src/gateway/server/ws-connection.ts`。

## 它暴露/定义了什么

这个文件主要定义两样东西。

第一是内部类型 `GatewayWsRuntimeParams`。它基于 `GatewayWsSharedHandlerParams` 做 `Omit<..., "refreshHealthSnapshot">`，然后补充 Gateway runtime 需要的参数，包括 `logGateway`、`logHealth`、`logWsControl`、`extraHandlers`、`getMethodRegistry`、`broadcast` 和 `context`。这里有一个重要设计点：`refreshHealthSnapshot` 不再作为顶层参数传入，而是从 `context.refreshHealthSnapshot` 派生，避免同一请求上下文里的健康状态刷新函数被拆散传递。

第二是导出的 `attachGatewayWsHandlers(params)`。这是本文件唯一的公开函数，也是 `server.impl.ts` 动态导入后调用的入口。它本身没有业务分支，只负责把参数映射到 `attachGatewayWsConnectionHandler`。

## 谁调用它

直接调用者是 `src/gateway/server.impl.ts`。在 Gateway 启动过程中，代码通过 `Promise.all` 动态导入 `./server-ws-runtime.js` 和 `./server/plugins-http/route-capability.js`，随后在 `gateway.ws-attach` 阶段调用 `attachGatewayWsHandlers(...)`。

这个调用发生在插件 runtime、Gateway discovery、认证状态、方法注册表、事件列表、广播函数、`gatewayRequestContext` 等关键对象都已经准备好之后，并且早于 `http.listen` 真正对外监听。也就是说，它属于 Gateway server 启动链路中“把已经组装好的运行时能力接到 WebSocket server 上”的步骤。

## 它调用谁

它只调用 `src/gateway/server/ws-connection.ts` 中的 `attachGatewayWsConnectionHandler`。

实际 WebSocket 连接生命周期都在被调用方完成，包括：监听 `wss.on("connection")`、生成连接 id、发送 `connect.challenge`、预认证连接预算释放、握手超时、连接关闭清理、presence 广播、节点注销、按需加载 `ws-connection/message-handler.js`、以及把认证后的客户端加入 `clients` 集合。

因此，本文件更像启动装配层，而不是协议实现层。

## 核心流程

核心流程很短：

1. `server.impl.ts` 在 Gateway 启动后段动态导入 `server-ws-runtime`。
2. `server.impl.ts` 调用 `attachGatewayWsHandlers`，传入 `wss`、`clients`、认证解析结果、限流器、启动状态、Gateway 方法名、事件名、日志器、插件能力查询函数、广播函数和 `gatewayRequestContext`。
3. `attachGatewayWsHandlers` 重新组织参数，把 `params.context.refreshHealthSnapshot` 显式作为 `refreshHealthSnapshot` 传给底层连接处理器。
4. `attachGatewayWsConnectionHandler` 在 `WebSocketServer` 上注册 connection 回调，后续每个连接的挑战、鉴权、消息处理、断开清理都由它和懒加载的 message handler 执行。

这个文件的价值在于隔离启动入口和连接实现：`server.impl.ts` 不需要知道 `ws-connection.ts` 的完整参数细节，`ws-connection.ts` 也不直接依赖庞大的 server runtime 构建过程。

## 关键函数的高层作用

`attachGatewayWsHandlers(params)` 是唯一关键函数。它的职责是做参数桥接：从 Gateway runtime 参数中取出底层 WebSocket handler 需要的字段，补齐日志器、请求处理器、方法注册表、广播函数，并用 `buildRequestContext: () => params.context` 固定当前 Gateway 请求上下文的获取方式。

这里的 `buildRequestContext` 很关键。底层连接处理器在连接关闭、节点注销、session 事件取消订阅等场景会调用它拿到 `GatewayRequestContext`。本文件把它包装成函数传入，保持了 `ws-connection.ts` 对上下文来源的抽象，而不是让底层直接捕获某个上层模块。

`GatewayWsRuntimeParams` 是辅助类型，主要用于表达“启动层必须提供哪些 runtime 能力”。它没有运行时代码，但会影响调用方和底层 handler 的类型契约。

## 修改风险

最大风险是参数契约漂移。`server-ws-runtime.ts` 是 `server.impl.ts` 和 `ws-connection.ts` 之间的薄桥，任何字段漏传、误传或默认值变化，都可能导致 WebSocket 握手、鉴权、presence、health、插件节点能力或广播行为异常。因为它本身逻辑很少，错误往往不会在本文件暴露，而是在连接建立后才表现为运行时问题。

第二个风险是 Gateway 热路径加载。`src/gateway/AGENTS.md` 明确要求 Gateway server 测试和启动路径避免不必要地 materialize bundled plugin runtime。当前设计通过动态导入 `server-ws-runtime.js`，并把插件节点能力作为 `getPluginNodeCapabilities` 延迟查询函数传入。若在这里加入静态重依赖、广泛插件注册表加载或启动时枚举逻辑，可能拉长 Gateway 启动并破坏测试隔离。

第三个风险是上下文一致性。`refreshHealthSnapshot` 从 `params.context` 取出，而不是单独传入，说明 health 刷新和请求上下文应保持同源。如果改成另一个来源，可能出现 health state、presence version、session cleanup 所用上下文不一致的问题。

第四个风险是连接处理职责误放。认证、限流、消息解析、关闭清理、节点注册注销等都属于 `src/gateway/server/ws-connection.ts` 或其 message handler。这个文件应保持装配职责；在这里加入协议分支会让启动层和连接层边界变模糊，也更容易遗漏 sibling surface 的验证。
