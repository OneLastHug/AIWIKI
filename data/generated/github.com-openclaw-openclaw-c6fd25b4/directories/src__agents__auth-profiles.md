# 子系统：src/agents/auth-profiles

## 解决什么问题

`src/agents/auth-profiles` 是 OpenClaw 的“模型认证档案”子系统，负责把不同 provider 的认证材料抽象成统一的 profile，并在 agent 运行时完成读取、选择、轮换、刷新、失败冷却和迁移修复。它处理的不是 provider 的 endpoint、model id 或请求参数，而是“这个 agent 该用哪个凭据访问哪个 provider”。

认证数据主要分成两类：凭据本体和运行状态。凭据本体存放在 `auth-profiles.json`，由 `api_key`、`token`、`oauth` 三种 `AuthProfileCredential` 表达；运行状态存放在 `auth-state.json`，包括每个 provider 的顺序覆盖、`lastGood`、`usageStats`、冷却和禁用窗口。这样设计可以避免把轮换状态混进长期凭据文件，也方便 per-agent 覆盖全局配置。

这个目录还承担兼容旧格式、合并主 agent 与子 agent store、接入外部 CLI OAuth、刷新 OAuth token、阻止错误 profile 反复命中等职责。根据当前片段推断，它是 provider auth、agent 执行、CLI runner、doctor、插件 SDK 之间的认证枢纽。

## 相关目录和文件

`src/agents/auth-profiles.ts` 是对外 barrel，向 agent、插件 SDK 和 provider 运行时导出稳定 API。目录内部可以按职责分成几组：

`types.ts` 定义核心数据结构：`AuthProfileStore`、`AuthProfileCredential`、`OAuthCredential`、`ProfileUsageStats` 等。`paths.ts`、`path-resolve.ts`、`path-constants.ts` 负责定位 `auth-profiles.json`、`auth-state.json`、旧版 `auth.json` 和 OAuth refresh lock。

`store.ts` 是加载、保存、缓存、合并和加锁更新的中心。它会读取持久化 store，合并 state，必要时迁移 legacy store，并在 runtime 路径上叠加外部认证 profile。`persisted.ts` 负责把磁盘上的旧/新 JSON 规范化成当前结构。`state.ts` 只处理 order、lastGood、usageStats 这类状态文件。

`profiles.ts` 提供增删改和成功标记，例如 `upsertAuthProfileWithLock`、`removeProviderAuthProfilesWithLock`、`markAuthProfileSuccess`。`order.ts` 根据 provider、config、store、cooldown 和 preferred profile 计算候选顺序。`usage.ts`、`usage-state.ts` 负责失败统计、冷却、禁用窗口和 blocked 状态。

OAuth 相关集中在 `oauth.ts`、`oauth-manager.ts`、`oauth-shared.ts`、`effective-oauth.ts`、`oauth-identity.ts`。外部 CLI 和插件外部认证在 `external-auth.ts`、`external-cli-sync.ts`、`external-cli-discovery.ts`、`external-cli-scope.ts`。迁移与自愈相关文件包括 `repair.ts`、`doctor.ts`、`legacy-oauth-sidecar.ts`、`policy.ts`、`source-check.ts`。展示和辅助能力在 `display.ts`、`identity.ts`、`credential-state.ts`、`portability.ts`、`session-override.ts`、`runtime-snapshots.ts`。

## 核心对象

`AuthProfileStore` 是核心容器，等价于 `AuthProfileSecretsStore & AuthProfileState`。其中 `profiles` 是 `profileId -> credential` 的映射，`order` 是 provider 维度的 profile 顺序，`lastGood` 记录最近成功使用的 profile，`usageStats` 存放失败、冷却、禁用和 round-robin 数据。

`AuthProfileCredential` 是三类凭据的 union。`ApiKeyCredential` 可保存 `key` 或 `keyRef`；`TokenCredential` 可保存 `token` 或 `tokenRef`，并可带 `expires`；`OAuthCredential` 保存 access、refresh、expires、provider、email、accountId 等可刷新材料。代码明确把 `aws-sdk` 这类外部认证模式排除在凭据 store 之外，相关配置应在 `openclaw.json` 的 `auth.profiles` 元数据中表达。

`OAuthManagerAdapter` 是 OAuth 刷新的依赖倒置接口。它把 provider 具体行为放到 adapter：如何用 OAuth credential 构造 API key、如何 refresh、如何读外部 CLI bootstrap/fallback credential、如何识别 refresh token reuse 错误。`createOAuthManager` 则提供通用刷新、锁、复用、回退和错误脱敏逻辑。

`ExternalCliResolvedProfile` 表示从 Codex、Claude、MiniMax 等外部 CLI 发现的 OAuth profile。它带有 `persistence: "runtime-only" | "persisted"`，用于区分只在运行时叠加，还是可以同步写回本地 store。

## 运行流程

典型读取流程从 `ensureAuthProfileStore` 或 `loadAuthProfileStoreForRuntime` 开始。`store.ts` 先解析 agentDir 对应路径，尝试命中 mtime 缓存；未命中时读取 `auth-profiles.json`，再读取 `auth-state.json` 并合并状态。如果新 store 不存在，会尝试加载旧版 `auth.json` 或旧 OAuth sidecar，并在允许写入时迁移为 canonical store。运行时加载还会合并主 agent store 与当前 agent store，并通过 `overlayExternalAuthProfiles` 叠加插件或外部 CLI 提供的 runtime profile。

选择流程由 `resolveAuthProfileOrder` 完成。它先解析 provider auth alias，例如 `openai-codex` 与 `openai` 的兼容关系；再合并 store order、config order、config profiles 和 store profiles。之后用 `resolveAuthProfileEligibility` 过滤 provider 不匹配、mode 不匹配、缺少凭据、token 过期等不可用项。没有显式 order 时，会按 credential 类型优先级排序：`oauth` 优先，其次 `token`，再到 `api_key`；同类型按 `lastUsed` 做 round-robin。处于 cooldown/blocked/disabled 的 profile 会被放到后面，并按恢复时间排序。

调用成功后，`markAuthProfileSuccess` 会更新 `lastGood` 和 `lastUsed`，同时清理失败与冷却字段。调用失败后，`markAuthProfileFailure` 会按错误原因累加失败计数，计算 cooldown 或 disabled 窗口；部分 OpenAI/Codex 相关失败还会探测 WHAM 使用状态，用于标记 subscription limit 等 blocked 状态。

OAuth 访问流程先用 `resolveEffectiveOAuthCredential` 决定是否采用本地凭据、主 store 较新的凭据或外部 CLI bootstrap。若 access token 仍可用，直接构造 API key；否则 `createOAuthManager` 进入刷新路径。刷新同时使用全局 refresh lock 和 auth store lock，避免多个进程/agent 用同一个 refresh token 并发刷新。刷新成功后写回 owner store，必要时镜像到主 store；刷新失败时会尝试读取已被其他进程刷新的 store、主 store 或外部 fallback credential，最后才抛出 `OAuthManagerRefreshError`，且错误消息会脱敏 access、refresh、idToken。

## 上下游依赖

上游输入主要来自 `OpenClawConfig`、provider auth alias、agentDir、外部 CLI 凭据读取器、插件 provider runtime，以及 legacy auth 文件。配置类型来自 `src/config/types.openclaw.ts` 和 secrets 类型；文件读写依赖 `src/infra/json-file.ts`、`src/infra/file-lock.ts`；provider 归一化依赖 `src/agents/provider-id.ts` 和 `src/agents/provider-auth-aliases.ts`。

下游使用者包括 `src/agents/command/attempt-execution.ts`，它用 `ensureAuthProfileStore` 和 `resolveAuthProfileOrder` 为 harness 选择 profile；`src/agents/cli-runner/prepare.ts` 会用 `loadAuthProfileStoreForRuntime` 把有效 profile 凭据带入 CLI runner 上下文；`src/agents/auth-health.ts` 用 order、display、credential-state 生成健康状态。插件侧通过 `src/plugin-sdk/provider-auth-api-key.ts`、`src/plugin-sdk/provider-auth-result.ts` 和 provider runtime 接入 profile 的创建、查询与外部认证。

## 修改时最容易踩的坑

第一，不要把非凭据配置写进 `auth-profiles.json`。endpoint、baseUrl、model、headers、timeout 属于 provider config；`aws-sdk` 这种外部认证模式也不是 `AuthProfileCredential` 类型。

第二，写 store 必须走锁。`updateAuthProfileStoreWithLock` 在锁内重新从磁盘读取，避免 live gateway 用旧内存快照覆盖 CLI 或其他进程刚写入的认证状态。直接读缓存后写回很容易造成 token 回退或 usageStats 丢失。

第三，OAuth 不能只看 token 字符串是否存在。identity 约束很重要，`accountId`、`email`、provider 不匹配时，代码会拒绝采纳主 store 或外部 CLI 凭据。绕过这些判断可能导致一个 agent 使用另一个账号的刷新 token。

第四，外部 CLI profile 有 runtime-only 和 persisted 的区别。Codex 这类 bootstrap-only provider 在本地已有 inline OAuth material 时，不应继续用外部 CLI 状态覆盖本地刷新后的 token。

第五，order 逻辑不是简单数组拼接。它要考虑 provider alias、config profile、store profile、显式顺序、preferred profile、cooldown 和 round-robin。改动时应同时看 `order.ts`、`usage-state.ts`、相关测试和调用方。

第六，agent 目录继承主 store 是有条件的。`store.ts` 会判断 profile 是否本地持久化、是否可安全采用主 store、是否应把刷新结果镜像回主 store。随意改变 owner agentDir 解析，会影响多 agent 共享 OAuth 的安全性和稳定性。

## 推荐阅读顺序

1. 先读 `src/agents/auth-profiles.ts`，了解公开 API 边界。
2. 再读 `src/agents/auth-profiles/types.ts`，建立 store、credential、state 的数据模型。
3. 读 `src/agents/auth-profiles/paths.ts`、`src/agents/auth-profiles/state.ts`、`src/agents/auth-profiles/persisted.ts`，理解磁盘格式和迁移入口。
4. 读 `src/agents/auth-profiles/store.ts`，掌握加载、合并、缓存、外部 profile overlay 和加锁写入。
5. 读 `src/agents/auth-profiles/order.ts`、`src/agents/auth-profiles/usage.ts`，理解认证轮换、冷却和失败恢复。
6. 最后读 `src/agents/auth-profiles/oauth-manager.ts`、`src/agents/auth-profiles/oauth-shared.ts`、`src/agents/auth-profiles/external-auth.ts`、`src/agents/auth-profiles/external-cli-sync.ts`，把 OAuth 刷新、外部 CLI 接入和身份安全规则串起来。
