# 文件：src/gateway/server-request-context.ts

## 一句话定位

`src/gateway/server-request-context.ts` 是 Gateway server 的请求上下文装配器：它把 `server.impl.ts` 中分散的运行时状态、连接集合、广播能力、订阅能力、审批管理器、channel 控制函数等统一封装成 `GatewayRequestContext`，供后续 WebSocket/RPC 方法处理逻辑使用。

## 它暴露/定义了什么

本文件主要定义并导出 `createGatewayRequestContext(params)`。它接收一个内部参数对象 `GatewayRequestContextParams`，返回 `src/gateway/server-methods/shared-types.ts` 中声明的 `GatewayRequestContext`。

文件内还定义了两个局部类型：

`GatewayRequestContextClient`：在通用 `GatewayClient` 基础上补充 `socket.close()` 和 `usesSharedGatewayAuth`，用于断开指定客户端或共享 gateway auth 客户端。

`GatewayRequestContextParams`：描述构造上下文需要注入的所有依赖。它大多直接复用 `GatewayRequestContext` 的字段类型，外加 `clients`、`runtimeState`、`enforceSharedGatewayAuthGenerationForConfigWrite` 等只有装配阶段才需要的输入。

## 谁调用它

直接调用者是 `src/gateway/server.impl.ts`。Gateway 启动过程中，`server.impl.ts` 在 `gateway.request-context` startup trace 阶段动态导入 `./server-request-context.js`，调用 `createGatewayRequestContext`，然后把结果保存为 `gatewayRequestContext`。

根据当前片段推断，这个 context 之后会被 WebSocket handler、gateway method registry、plugin registry gateway context fallback 等路径共享使用。依据是 `server.impl.ts` 创建后紧接着把它赋给 `currentPluginRegistryGatewayContext`，并通过 `setFallbackGatewayContextResolver(() => gatewayRequestContext)` 注册 fallback resolver，随后继续 attach WebSocket handlers。

## 它调用谁

本文件自身调用很少，核心外部调用只有 `disconnectAllSharedGatewayAuthClients`，来自 `src/gateway/server-shared-auth-generation.ts`，用于关闭所有使用共享 gateway auth 的客户端连接。

其他字段大多是透传函数或状态引用，例如 `broadcast`、`broadcastToConnIds`、`nodeSubscribe`、`startChannel`、`stopChannel`、`getRuntimeSnapshot`、`refreshHealthSnapshot`、`wizardRunner` 等。这些函数实际由 `server.impl.ts` 或相邻运行时模块创建，本文件只负责把它们放进统一上下文。

## 核心流程

`createGatewayRequestContext` 的流程很直接：

先定义局部函数 `hasApprovalScope(gatewayClient)`，读取客户端连接参数里的 `connect.scopes`，判断是否包含 `operator.admin` 或 `operator.approvals`。这个判断用于后续审批客户端发现。

然后返回一个 `GatewayRequestContext` 对象。绝大多数字段是从 `params` 直接透传，例如依赖、日志器、健康检查、广播、节点订阅、chat run 状态、wizard 状态、channel 生命周期函数、voice wake 广播函数等。

特殊之处在于 `cron` 和 `cronStorePath` 是 getter，而不是创建时固定值。注释说明这样可以让 config hot reload 替换 cron/store 状态时，已经持有 request context 的 handler closure 仍然读到最新 `runtimeState.cronState`。`src/gateway/server-request-context.test.ts` 专门覆盖了这个行为：创建 context 后替换 `runtimeState.cronState`，再次读取 `context.cron` 和 `context.cronStorePath` 应返回新值。

最后，context 还补充了几类面向连接集合的操作：查询是否存在审批客户端、获取审批客户端 connId 集合、按 device 断开客户端、断开共享 gateway auth 客户端。这些操作都基于传入的 `clients` live set。

## 关键函数的高层作用

`createGatewayRequestContext`：把 Gateway server 的“运行时事实”和“请求处理能力”收束为一个稳定接口。它本身不执行业务请求，而是给 request handlers 提供访问 server 能力的入口。可以把它理解为 Gateway 方法层的依赖注入边界。

`hasApprovalScope`：局部辅助函数，用于识别某个连接是否可处理执行审批或 operator 审批。它只认 `operator.admin` 和 `operator.approvals` 两个 scope。

`hasExecApprovalClients`：遍历当前连接集合，判断是否存在具备审批 scope 的客户端，可排除指定 `connId`。常用于决定审批请求是否有可达的 operator 客户端。

`getApprovalClientConnIds`：返回具备审批 scope 的连接 ID 集合，支持排除某个连接，也支持传入 `filter(client, record)` 做更细筛选。它是审批广播/定向通知的重要入口。

`disconnectClientsForDevice`：按 `connect.device.id` 关闭连接，可选按 `connect.role` 过滤。关闭码为 `4001`，原因是 `"device removed"`。异常会被吞掉，避免单个 socket 关闭失败影响遍历。

`disconnectClientsUsingSharedGatewayAuth`：委托 `disconnectAllSharedGatewayAuthClients`，关闭所有标记为共享 gateway auth 的连接，关闭原因是 `"gateway auth changed"`。

`enforceSharedGatewayAuthGenerationForConfigWrite`：不是本文件实现，只是透传注入。它连接 config 写入和共享 gateway session generation 校验，真正逻辑在 `src/gateway/server-shared-auth-generation.ts` 及 `server.impl.ts` 注入闭包中。

## 修改风险

最高风险是改变 `GatewayRequestContext` 的字段语义。这个 context 是 Gateway 方法层的共同依赖，字段新增、删除、改名或从 live 引用改成快照，都可能影响 WebSocket 方法、plugin registry、channel lifecycle、审批、chat run、session event 订阅等多个面。

`cron` 和 `cronStorePath` 尤其不能随意改成普通属性。现有测试和注释都表明它们必须随 `runtimeState.cronState` 热更新，否则 config hot reload 后旧 handler closure 可能继续操作旧 cron 实例或旧 store path。

连接遍历逻辑也有兼容风险。`hasApprovalScope` 当前只接受 `operator.admin` 和 `operator.approvals`，如果扩大或缩小 scope，会直接影响审批请求能否被 operator 客户端接收。`getApprovalClientConnIds` 的 `filter` 和 `record` 参数也可能被审批管理器依赖，修改返回集合时要确认审批广播路径。

断连函数属于用户可见行为。`disconnectClientsForDevice` 和共享 auth 断连都会主动关闭 socket，关闭码和 reason 可能被客户端或测试观察到。改动时需要同时检查 `src/gateway/server-shared-auth-generation.ts`、WebSocket runtime、设备移除/config 写入相关方法。

此外，本文件处在 Gateway hot path 装配阶段。`src/gateway/AGENTS.md` 要求 Gateway server 测试和启动路径避免不必要地物化 bundled plugin runtime。因此不应在这里加入重型 import、插件注册表扫描、文件系统 freshness polling 或请求时重复发现逻辑。它应保持为轻量的上下文组装层，把已有 live state 和函数引用传给方法层。
