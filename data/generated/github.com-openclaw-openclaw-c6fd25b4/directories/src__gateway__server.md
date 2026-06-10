# 子系统：src/gateway/server

## 解决什么问题

`src/gateway/server` 是 Gateway 进程的网络入口层，负责把外部 HTTP、WebSocket、插件 HTTP route、hook 调用、健康/就绪状态等请求接入到 Gateway 的内部方法、会话、频道和插件运行时。它不是业务能力本身，而是“连接、鉴权、限流、路由、状态广播”的边界层：客户端先通过这里完成握手和权限判断，再进入 `src/gateway/server-methods` 的方法分发、`src/gateway/protocol` 的协议帧校验，或插件注册的 HTTP/Upgrade handler。

这个目录的核心价值是把多种接入形态统一成 Gateway 可信上下文。WebSocket 客户端会变成 `GatewayWsClient`；插件 HTTP 请求会被包进 `withPluginRuntimeGatewayRequestScope`；hook 请求会经过 token、IP、幂等和目标策略校验；健康检查会汇总 presence、channel runtime、event loop 等状态。这样下游代码可以依赖“已校验、已归一化”的请求上下文，而不是在每个业务处理点重复判断来源和权限。

## 相关目录和文件

`src/gateway/server/ws-connection.ts` 是 WebSocket 连接装配层，负责连接生命周期、预认证队列、payload 限制、连接元数据、presence 更新和按需加载 message handler。真正处理协议帧的逻辑在 `src/gateway/server/ws-connection/message-handler.ts`，它读取 `ConnectParams`、校验请求帧、处理设备/节点配对、来源检查、scope、rate limit 和 method dispatch。

`src/gateway/server/plugins-http.ts` 是插件 HTTP/Upgrade 路由入口，依赖 `src/plugins/registry` 中的 `httpRoutes`，并用 `src/gateway/server/plugin-route-runtime-scopes.ts` 计算插件运行时可见的 operator scopes。它下面的 `plugins-http/path-context.ts`、`route-match.ts`、`route-auth.ts` 负责路径归一、route 匹配和认证策略判断。

`src/gateway/server/hooks-request-handler.ts` 处理外部 hook POST 请求，依赖 `src/gateway/hooks.ts` 的配置、payload 归一和目标解析。`src/gateway/server/health-state.ts` 维护 Gateway snapshot、presence/health 版本和健康缓存。`src/gateway/server/readiness.ts` 判断服务是否可接流量。`src/gateway/server/http-listen.ts` 封装 HTTP server 监听和端口占用重试。`src/gateway/server/ws-types.ts` 定义已连接 WebSocket 客户端的最小共享形状。

邻近上下文包括 `src/gateway/protocol` 的协议 schema 和版本，`src/gateway/server-methods` 的请求上下文和方法处理，`src/gateway/auth.ts`、`src/gateway/http-auth-utils.ts`、`src/gateway/net.ts` 的认证与网络来源判断，以及 `src/plugins/runtime/gateway-request-scope.ts` 的插件运行时上下文注入。

## 核心对象

`GatewayWsSharedHandlerParams` 描述 WebSocket handler 需要的共享依赖，包括 `WebSocketServer`、客户端集合、预认证连接预算、端口、认证配置、rate limiter、startup 状态、可用方法/事件列表和 health refresh 函数。它把 server 层从全局对象中解耦出来，方便测试和运行时注入。

`AttachGatewayWsConnectionHandlerParams` 在共享参数上增加日志、额外 handler、method registry、broadcast 和 `buildRequestContext`。它代表“把一个 ws server 接到完整 Gateway 运行时”的装配参数。

`GatewayWsClient` 是连接后的客户端对象，包含 `socket`、`connect`、`connId`、认证来源标记、shared gateway session generation、presence key、client IP，以及插件节点 capability 信息。下游广播、presence、权限和插件能力都通过这个对象关联到具体连接。

`PluginHttpRequestHandler` 和 `PluginHttpUpgradeHandler` 是插件 HTTP 路由的统一函数类型。`PluginRouteDispatchContext` 则携带 Gateway HTTP auth 是否满足、已解析的请求认证对象和 operator scopes。插件 route 是否能被调用，取决于这些上下文和 route 自身的 `auth`、`gatewayRuntimeScopeSurface` 设置。

`ReadinessChecker` 返回 `ReadinessResult`，包含 `ready`、失败 channel 列表、uptime 和可选 event loop 状态。`health-state.ts` 中的 `buildGatewaySnapshot` 和 `refreshGatewayHealthSnapshot` 则负责生成面向客户端的 snapshot 和异步健康摘要。

## 运行流程

WebSocket 路径大致是：HTTP upgrade 到达 Gateway 后，`ws-connection.ts` 建立连接对象，先执行预认证约束、origin/header 日志清理、payload 上限和 startup pending 判断；随后按需动态导入 `ws-connection/message-handler.ts`。这种按需加载符合 `src/gateway/AGENTS.md` 对 Gateway hot path 的约束：启动和轻量路径不要过早 materialize 复杂运行时。message handler 收到 `connect` 后，会通过 `src/gateway/protocol/index.ts` 的校验器检查协议版本和请求帧，再结合设备配对、节点配对、trusted proxy、browser origin、role scope、shared auth generation 等策略，最终把请求交给 method registry 或 extra handlers。

插件 HTTP 路径大致是：`plugins-http.ts` 根据请求 path 解析 `PluginRoutePathContext`，从插件 registry 找匹配 route；如果 route 要求 Gateway auth，但 dispatch context 没有认证成功，就 fail closed。对 `gateway` auth route，还会根据 `gatewayRuntimeScopeSurface` 决定传入默认 write scope，还是使用 trusted operator 声明的 scopes。随后它通过 `withPluginRuntimeGatewayRequestScope` 调用插件 handler，使插件代码能在受控 scope 内访问 Gateway 能力。

Hook 路径大致是：`hooks-request-handler.ts` 只接受配置 base path 下的 POST；拒绝 query token；从 header 提取 token，按 client IP 做认证失败限流；读取 JSON body，应用 hook mapping，解析 session key、channel、agent、deliver 策略和幂等 key；对于重复 idempotency 请求返回缓存 run id，避免重复触发。

健康与就绪路径相对独立：`health-state.ts` 维护 presence/health 版本号和缓存，`readiness.ts` 从 channel manager snapshot 判断是否有不可忽略的 channel failure，并把 startup pending 和 event loop health 纳入结果。根据当前片段推断，这些状态会通过 WebSocket broadcast 和 HTTP probe 暴露给控制端，依据是 `GatewayWsSharedHandlerParams.refreshHealthSnapshot`、`broadcast` 参数以及 `buildGatewaySnapshot` 中的 `stateVersion` 字段。

## 上下游依赖

上游调用者主要是 Gateway 主 server 组装代码，例如 `src/gateway/server-network-runtime.ts`、`src/gateway/server-ws-runtime.ts`、`src/gateway/server-runtime-services.ts` 等邻近文件。它们负责创建 HTTP server、WebSocket server、插件 registry、channel manager、auth config 和运行时服务，再把依赖传进 `src/gateway/server`。

下游依赖分几类。协议层依赖 `src/gateway/protocol/index.ts`、`src/gateway/protocol/client-info.ts` 和 startup unavailable 定义；认证和网络来源依赖 `src/gateway/auth.ts`、`src/gateway/http-auth-utils.ts`、`src/gateway/net.ts`、`src/gateway/auth-rate-limit.ts`；会话和业务方法依赖 `src/gateway/server-methods/types.ts` 与 method registry；插件路径依赖 `src/plugins/registry.ts` 和 `src/plugins/runtime/gateway-request-scope.ts`；运行状态依赖 `src/infra/system-presence.ts`、`src/commands/health.ts`、channel manager 和 event loop health。

## 修改时最容易踩的坑

第一，认证路径容易误放宽。`plugins-http.ts` 对 gateway-auth route 明确要求缺少 auth context 或 scope context 时 fail closed；修改插件 route、trusted proxy 或 scope 透传时，不能只看 route handler 是否能工作，还要证明未授权路径会被拒绝。

第二，WebSocket 连接前后状态不同。预认证阶段有 `MAX_PREAUTH_PAYLOAD_BYTES`、连接预算、startup pending close code 和 message handler 动态加载队列；连接后才有完整 `GatewayWsClient.connect`、scope、presence 和 method dispatch。把 post-connect 假设提前用在 handshake 阶段，会造成安全或稳定性问题。

第三，Gateway hot path 不能随意加载插件全集。`src/gateway/AGENTS.md` 明确要求 server/startup 路径需要静态描述时优先轻量 resolver，不要为了回答静态问题加载 broad bundled channel registries。新增插件 Gateway 描述时，应同时维护 core resolver、插件 artifact 和完整插件导出，避免两套行为分叉。

第四，健康状态有缓存和版本语义。`refreshGatewayHealthSnapshot` 对敏感/非敏感 health refresh 分开缓存，非敏感刷新会递增 `healthVersion` 并触发广播；presence 也有独立版本。修改 snapshot 字段时要考虑客户端增量更新和权限，敏感字段只应出现在 `includeSensitive` 场景。

第五，hook token 不能出现在 query。当前实现显式拒绝 `?token=`，只允许 `Authorization: Bearer` 或 `X-OpenClaw-Token`。改 hook 兼容性时不要为了方便恢复 query token，否则会扩大日志、代理和浏览器历史泄露面。

## 推荐阅读顺序

1. 先读 `src/gateway/AGENTS.md`，理解 Gateway hot path 和测试约束。
2. 再读 `src/gateway/server/ws-types.ts`，掌握连接对象的共享字段。
3. 读 `src/gateway/server/ws-connection.ts`，看连接装配、预认证和动态加载边界。
4. 读 `src/gateway/server/ws-connection/message-handler.ts`，理解 connect、auth、pairing、scope、protocol validation 如何汇合。
5. 读 `src/gateway/server/plugins-http.ts` 和 `src/gateway/server/plugin-route-runtime-scopes.ts`，理解插件 HTTP route 如何获得 Gateway runtime scope。
6. 读 `src/gateway/server/hooks-request-handler.ts`，理解外部 webhook 如何被安全转换成内部 wake/agent dispatch。
7. 最后读 `src/gateway/server/health-state.ts`、`src/gateway/server/readiness.ts`、`src/gateway/server/http-listen.ts`，补齐运行状态、探针和监听失败处理。
