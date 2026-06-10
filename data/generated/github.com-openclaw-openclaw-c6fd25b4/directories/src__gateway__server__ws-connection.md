# 子系统：src/gateway/server/ws-connection

## 解决什么问题

这个目录负责 Gateway 的 WebSocket 连接生命周期中，**“连上之前怎么判定能不能进、连上之后怎么接消息、缺设备身份时如何分流”** 这一整段逻辑。根据当前片段推断，它不是单纯的消息分发层，而是把握了连接握手、鉴权结果归并、Control UI / node / CLI 的差异化策略，以及一些连接后健康信息刷新和异常拒绝语义。

它的核心价值在于：把复杂的连接前判断拆成可测试的小模块，避免 `message-handler.ts` 里堆满分支，同时让“共享密钥、设备 token、bootstrap token、trusted proxy、Control UI 安全策略”这些规则能被统一裁决。

## 相关目录和文件

这个目录内最关键的是 `message-handler.ts`，它是连接后的主入口；`auth-context.ts` 负责把 HTTP/WS 握手里可用的鉴权材料整理成统一状态，再做二阶段决策；`connect-policy.ts` 专门处理 Control UI 的设备身份策略、是否跳过配对、是否清理未绑定 scope；`handshake-auth-helpers.ts` 则聚焦“握手阶段”的安全上下文、会话本地性、静默配对条件等。

配套测试也很重要：`auth-context.test.ts`、`connect-policy.test.ts`、`handshake-auth-helpers.test.ts`、`unauthorized-flood-guard.test.ts`、`message-handler.post-connect-health.test.ts`。它们说明这个目录的行为是强规则化的，改动时应优先看测试覆盖的决策面，而不是只看单个函数。

邻近依赖主要来自 `src/gateway/auth.ts`、`src/gateway/protocol/index.ts`、`src/gateway/role-policy.ts`、`src/gateway/server-methods/types.ts`，以及 `src/infra/device-pairing.js`、`src/infra/device-identity.js`、`src/infra/node-pairing.js` 等运行时基础设施。

## 核心对象

`ConnectAuthState` 和 `ConnectAuthDecision` 是这里最关键的中间态。前者把共享密钥、device token、bootstrap token、是否存在设备身份等事实汇总起来；后者决定最终认证是否成立、应该按哪种 `authMethod` 记账。`ControlUiAuthPolicy` 则把 Control UI 的配置项和设备约束压成一个小对象，方便后续判断是否允许绕过设备身份。

`HandshakeBrowserSecurityContext`、`PairingLocalityKind` 这类对象说明这里不仅关心“鉴权是否成功”，还关心“请求是不是本地、是不是浏览器发起、是否需要更严格的 Origin 约束”。`UnauthorizedFloodGuard` 说明目录内还处理失败重试/暴力尝试的节流。

## 运行流程

1. WebSocket upgrade 进入 `message-handler.ts`，先读取请求头、客户端模式、角色、协议版本和原始连接信息。
2. 调用 `resolveConnectAuthState()`，把共享 token/password 和 device token 候选项分别归并；同时走 `authorizeWsControlUiGatewayConnect()`、必要时再做 `authorizeHttpGatewayConnect()` 预检。
3. 再调用 `resolveConnectAuthDecision()`，把 bootstrap token、device token、rate limit、角色和 scope 合并成最终的连接认证结果。
4. 若缺少设备身份，则通过 `connect-policy.ts` 判断是否允许 Control UI 例外、是否是 trusted proxy operator、是否允许静默本地配对，或是否必须拒绝。
5. `handshake-auth-helpers.ts` 负责判定本地性、browser-origin 安全上下文、是否允许 silent pairing / self pairing。
6. 认证通过后，`message-handler.ts` 才接管具体消息：health refresh、pairing、node 状态、presence 更新、诊断 trace、拒绝原因封装等。

## 上下游依赖

上游输入主要是 WebSocket upgrade 请求、HTTP 头、配置、设备身份、角色和 scope、rate limiter，以及来自 `src/gateway/protocol/index.ts` 的连接参数 schema。下游输出则是：连接是否接受、以什么 `authMethod` 接受、是否需要补设备身份、是否触发 pairing、是否刷新健康快照、是否写入 presence 或节点元数据。

它还强依赖 `src/gateway/auth.ts` 的鉴权语义与 `src/gateway/role-policy.ts` 的角色授权规则。设备相关的真实状态则来自 `src/infra/device-pairing.js`、`src/infra/device-identity.js`、`src/infra/node-pairing.js`。`message-handler.ts` 最终再把这些决策落到 `GatewayWsClient`、`GatewayRequestContext` 和协议错误结构上。

## 修改时最容易踩的坑

这里最容易出问题的是把“共享认证成功”误当成“可以跳过设备身份”，或者把 Control UI 的 break-glass 路径扩散到 node 角色。另一个高风险点是本地性判断：`browser-origin`、loopback、proxy header、Docker 容器内访问这些条件一变，静默配对和拒绝策略就可能反转。

还要注意鉴权原因码不能乱改。测试里明显依赖 `token_mismatch`、`device_token_mismatch`、`scope_mismatch`、`bootstrap_token_invalid` 等语义，`auth-context.ts` 还会区分 explicit device token 和 shared-token fallback。改这里如果只看“成功/失败”，很容易把运维可读性和重试提示弄坏。

## 推荐阅读顺序

先看 `connect-policy.ts`，理解这套连接策略到底在保护什么；再看 `auth-context.ts`，理解鉴权状态如何被归并；然后看 `handshake-auth-helpers.ts`，补足本地性和静默配对规则；最后看 `message-handler.ts`，把前面的决策如何落到完整连接流程串起来。

测试建议同步看 `connect-policy.test.ts`、`auth-context.test.ts`、`handshake-auth-helpers.test.ts`、`message-handler.post-connect-health.test.ts`，它们基本覆盖了这个目录最关键的行为边界。
