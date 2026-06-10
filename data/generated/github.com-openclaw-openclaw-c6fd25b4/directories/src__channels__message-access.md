# 目录：src/channels/message-access

## 它负责什么

`src/channels/message-access` 是 OpenClaw 核心 channel 层里的“入站消息访问判定”模块。它不负责收消息、发消息、渲染消息，也不直接实现 Telegram、Discord、iMessage 等具体平台逻辑；它负责把某个 channel 收到的一次 inbound message / command / event 转换成统一的访问图，然后给出是否 `dispatch`、`observe`、`skip`、`drop` 或 `pairing-required` 的结论。

从职责上看，这个目录是 channel 入站安全与路由策略的共享内核。它处理的核心问题包括：发送者是否在 `allowFrom` 或 `groupAllowFrom` 中；DM 策略是 pairing、allowlist、open 还是 disabled；群组策略是否开放；route / thread / room 等路由 gate 是否允许；control command 是否被 owner 或 access group 授权；事件是否需要按 sender、command、origin subject 或 route-only 模式认证；群聊里是否需要 mention 才激活 agent。

它位于 `src/channels/**`，按作用域规则属于核心 channel implementation。插件作者不应直接依赖这个目录；面向插件的稳定边界应通过 `openclaw/plugin-sdk/*`、channel contract 或 facade 暴露。这个目录里的代码更像“核心判定引擎”，由 channel/plugin runtime 的适配层提供身份描述、会话信息、配置和 access group 事实。

## 直接子目录地图

这个目标目录当前没有直接子目录，所有模块都平铺在 `src/channels/message-access` 下。可以按角色分成几组阅读：

入口与导出层：`index.ts` 汇总对外导出，暴露 `resolveChannelMessageIngress`、`createChannelIngressResolver`、`resolveStableChannelMessageIngress`、`decideChannelIngress`、`resolveChannelIngressState` 以及相关类型。

运行时编排层：`runtime.ts` 负责把调用方传入的 channel id、account id、identity、subject、conversation、policy、route、allowlist、access groups、mention facts 等输入组织起来，读 pairing store，合并有效 allowlist，然后调用 state 和 decision 层。

状态解析层：`state.ts` 负责把原始输入解析成 `ChannelIngressState`，包括 allowlist 标准化、sender 匹配、access group 展开、route sender allowlist 处理、origin subject 匹配等。

判定层：`decision.ts` 负责把 `ChannelIngressState` 和 `ChannelIngressPolicyInput` 转成最终 `ChannelIngressDecision`，并构造 route、sender、command、event、activation 等 gate。

身份与 allowlist 辅助层：`runtime-identity.ts` 定义稳定身份描述并创建 identity adapter / subject；`allowlist.ts`、`sender-gates.ts`、`runtime-access-groups.ts`、`dm-allow-state.ts` 分别处理 allowlist 诊断、DM/群 sender gate、运行时 access group membership、DM allow 审计状态。

类型层：`types.ts` 和 `runtime-types.ts` 是理解全目录的关键。前者定义内部 access graph、reason code、state、decision、allowlist、route gate 等基础类型；后者定义运行时入口参数、resolver 类型、插件侧身份描述和投影后的访问结果类型。

测试：`message-access.test.ts` 是该目录的行为样例集合，适合在读完主流程后反向确认各种 policy 组合的预期。

## 关键入口

最推荐从 `index.ts` 看公开面。它说明这个目录真正希望外部使用的入口并不多：`createChannelIngressResolver`、`resolveChannelMessageIngress`、`resolveStableChannelMessageIngress`、`channelIngressRoutes`、`readChannelIngressStoreAllowFromForDmPolicy`、`decideChannelIngress`、`resolveChannelIngressState`。

`createChannelIngressResolver` 是上层 channel 集成时更顺手的入口。调用方先为一个 channel account 准备固定的 `channelId`、`accountId`、`identity`、配置和 access group resolver，然后得到带有 `message`、`command`、`event` 三种方法的 resolver。它适合复用同一 channel 账号和身份规则，避免每次入站事件都重复拼完整参数。

`resolveChannelMessageIngress` 是底层主入口。它接收一次完整入站事件的所有事实，内部会构造 subject、读取或合并 allowlist、解析 route descriptors、解析 access group membership、生成 state，然后调用 `decideChannelIngress`。返回值是 `ResolvedChannelMessageIngress`，不仅包含最终 `ingress` decision，还包含投影后的 `sender`、`command`、`route`、`activation` 等访问视图，方便调用方做调试、审计或后续分支。

`resolveStableChannelMessageIngress` 是简化入口，用 `defineStableChannelIngressIdentity` 包装一个稳定身份字段，适合只有一个主要 sender id、再加少量 alias 的场景。

## 主流程位置

主流程在 `runtime.ts`、`state.ts`、`decision.ts` 三层之间展开。

第一步在 `runtime.ts`。调用方传入 raw config 和 event facts 后，`resolveChannelIngressEffectiveAllowFromLists` 会把 DM allowlist、group allowlist、pairing store allowlist 按策略合成 `effectiveAllowFrom` 和 `effectiveGroupAllowFrom`。如果是 direct conversation 且 DM policy 需要 pairing store，`readChannelIngressStoreAllowFromForDmPolicy` 或调用方注入的 `readStoreAllowFrom` 会参与读取。随后 `routeFactsFromDescriptors` 会把 route descriptors 转成 route gate facts，access group 相关输入也会被收集。

第二步在 `state.ts` 的 `resolveChannelIngressState`。它将 subject identity 和 allowlist entries 交给 channel-specific adapter 标准化和匹配。这里的重要抽象是 `InternalChannelIngressAdapter`：核心不猜测平台身份格式，而是要求 adapter 提供 `normalizeEntries` 和 `matchSubject`。这让同一套 sender gate 逻辑可以用于 phone、email、username、stable id、plugin-specific id 等不同身份材料。`state.ts` 还会把 access group entries 展开为实际 sender entries 或 membership facts，并生成 redacted diagnostics，避免把原始敏感标识泄漏到 access graph。

第三步在 `decision.ts` 的 `decideChannelIngress`。它按 gate 组织判定：先考虑 route block 和 route sender empty，再生成 direct 或 group sender gate，然后处理 command gate、event gate、activation gate。每个 gate 都带有 `phase`、`kind`、`effect`、`allowed`、`reasonCode` 等信息。最终 decision 不只是一个布尔值，而是一张 access graph，调用方可以知道到底是 route、sender、command、event 还是 mention activation 阻止了这次入站。

最后回到 `runtime.ts`，主结果会被投影成更便于调用方使用的结构，例如 `projectSenderAccess`、`projectCommandAccess`、`projectRouteAccess`、`projectActivationAccess` 这些逻辑会把底层 gate graph 转成上层字段。

## 推荐阅读顺序

1. 先读 `src/channels/message-access/index.ts`，确认公开入口和导出类型范围。
2. 再读 `src/channels/message-access/runtime-types.ts`，理解调用方需要提供什么：`ResolveChannelMessageIngressParams`、`CreateChannelIngressResolverParams`、`ChannelIngressIdentityDescriptor`、`ChannelIngressRouteDescriptor`。
3. 接着读 `src/channels/message-access/types.ts`，重点看 `ChannelIngressStateInput`、`ChannelIngressPolicyInput`、`AccessGraphGate`、`ChannelIngressDecision`、`IngressReasonCode`。
4. 然后读 `src/channels/message-access/runtime.ts`，抓住从 resolver 到 state/decision 的编排路径。
5. 再读 `src/channels/message-access/state.ts` 和 `src/channels/message-access/decision.ts`，分别理解“事实归一化”和“策略判定”。
6. 最后用 `src/channels/message-access/message-access.test.ts` 对照具体场景，尤其是 DM pairing、group allowlist、command owner、route sender policy、origin subject 和 mention activation。

## 常见误区

不要把这个目录理解成某个具体聊天平台的权限实现。它是共享内核，平台差异主要通过 `identity` descriptor、adapter、route facts、access group resolver 和调用方传入的 conversation facts 进入。

不要把 `allowFrom` 简单理解成唯一权限来源。实际判定会合并 DM 配置、group 配置、pairing store、route sender allowlist、command owner allowlist、access groups，以及 event auth mode。某些场景下 sender 不通过并不一定直接 drop，例如 activation gate 可能只是 `skip`，DM policy 也可能返回 `pairing-required`。

不要忽略 access graph。最终结论之外，`graph.gates` 才是定位原因的主要证据。看 `reasonCode` 时要结合 `phase` 和 `kind`，否则容易把 route block、sender block、command unauthorized、event unauthorized、activation skipped 混为一类。

不要在插件代码里直接 import `src/channels/message-access/*`。根据 `src/channels/AGENTS.md`，`src/channels/**` 是核心实现区域，插件侧应通过 SDK 或 channel contract 获取稳定能力。根据当前片段推断，这个目录的类型虽然很完整，但并不等同于插件公共 API；依据是 scoped guide 明确要求 extension-facing channel surfaces 走 `openclaw/plugin-sdk/*`，且 `message-access` 位于核心 channel tree 内。

不要把 mutable identifier matching 当成默认安全行为。`types.ts` 里区分了 `stable-id`、`username`、`email`、`phone`、`role`、`plugin:*` 等 identifier kind，也有 `dangerous` 和 `sensitivity` 标记；`allowlist.ts` 中还存在 `applyMutableIdentifierPolicy`。这说明身份匹配需要考虑可变标识和敏感标识的诊断边界，不能只按字符串相等理解。
