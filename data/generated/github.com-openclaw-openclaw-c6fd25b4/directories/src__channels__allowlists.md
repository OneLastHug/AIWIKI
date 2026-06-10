# 子系统：src/channels/allowlists

## 解决什么问题

`src/channels/allowlists` 负责频道 allowlist 配置在“人类可写标识”和“平台稳定 ID”之间的解析辅助。它不是最终的消息准入判定引擎，而是给 Discord、Slack、Matrix、MSTeams、Zalo 等 channel plugin 在启动、配置归一化或 monitor 初始化阶段使用：把配置里的用户名、tag、room/channel 成员等条目解析成稳定 ID，合并回 allowlist，并输出简短诊断日志。

OpenClaw 的频道配置常见形态是 `allowFrom`、`groupAllowFrom`，以及 channel/group 配置项内部的 `users` 字段。用户可能写入 `Alice#1234`、用户名、房间名或数字 ID。运行时真正判定访问时更希望使用稳定、不易变化的平台 ID。该目录的核心价值就是集中处理“解析结果汇总、去重、保留通配符、补丁嵌套配置、记录已解析/未解析结果”这些重复逻辑，避免每个插件各写一套。

## 相关目录和文件

`src/channels/allowlists/resolve-utils.ts` 是主实现文件，导出 allowlist 解析后的合并、规范化、嵌套补丁和日志摘要工具。`src/channels/allowlists/resolve-utils.test.ts` 覆盖这些工具的行为边界，例如 `*` 不作为普通用户条目收集、解析成功才加入 ID、canonicalize 会把已解析名称替换成 ID、空映射不打日志。

相邻的 `src/channels/allowlist-match.ts` 负责编译和匹配 allowlist，是实际“某个 sender 是否命中 allowlist”的基础工具。`src/channels/message-access/allowlist.ts` 处理 ingress 访问策略中的 allowlist 状态合并、失败原因、redacted diagnostics、mutable identifier policy。`src/channels/plugins/allowlist-match.ts` 只是把核心匹配类型和 `formatAllowlistMatchMeta` 转给插件侧使用。

对外暴露层在 `src/plugin-sdk/allow-from.ts`。根据调用点，这个 SDK barrel 会重导出 `src/channels/allowlists/resolve-utils.ts` 中的工具，供 `extensions/discord`、`extensions/slack`、`extensions/matrix`、`extensions/msteams`、`extensions/zalouser` 等插件 monitor 使用。也就是说，插件作者不应直接 import `src/channels/**`，而应通过 `openclaw/plugin-sdk/allow-from` 使用这些能力。

## 核心对象

`AllowlistUserResolutionLike` 是最小解析结果契约：包含原始 `input`、是否 `resolved`、以及可选稳定 `id`。各插件可以附带额外字段，但只要满足这个结构，就能交给通用工具处理。

`mergeAllowlist` 接收已有条目和新增 ID，先通过 `mapAllowFromEntries` 把旧配置转成字符串列表，再 trim、过滤空值，并按小写 key 去重。它保留首次出现的原始写法，因此更像“温和合并”而不是强制重写。

`buildAllowlistResolutionSummary` 把一批解析结果拆成四个部分：`resolvedMap` 供后续按原始输入查找；`mapping` 用于日志，例如 `input→id`；`unresolved` 用于提示未解析条目；`additions` 是可合并回 allowlist 的稳定 ID 列表。它支持自定义 resolved/unresolved 的格式化函数，方便不同平台输出带上下文的摘要。

`canonicalizeAllowlistWithResolvedIds` 更偏配置规范化：它遍历已有条目，空值跳过，`*` 原样保留，能解析的条目替换成稳定 ID，不能解析的保留原值，最后去重。相比 `mergeAllowlist`，它会减少旧名称和新 ID 并存的情况。

`patchAllowlistUsersInConfigEntries` 面向 `{ [key]: { users: [...] } }` 这类嵌套配置。默认策略是 merge：保留原 users 并追加解析出的 ID；`strategy: "canonicalize"` 则把可解析用户替换为 ID。`addAllowlistUserEntriesFromConfigEntry` 用于扫描单个配置项的 `users` 字段，把非空、非 `*` 条目加入待解析集合。`summarizeMapping` 负责把 resolved/unresolved 摘要写入 `RuntimeEnv.log`，并通过 `summarizeStringEntries` 限制输出长度，避免日志泄露过多配置细节。

## 运行流程

典型流程发生在插件 monitor 或配置加载逻辑中。插件先读取 `allowFrom`、`groupAllowFrom` 或 channel/group 配置中的 `users` 字段。对于嵌套配置，先用 `addAllowlistUserEntriesFromConfigEntry` 收集需要解析的用户标识，跳过通配符 `*`，因为通配符表示允许所有人，不需要解析成 ID。

随后插件调用平台 API 或本地目录能力，把这些输入解析成 `AllowlistUserResolutionLike[]`。这些解析细节归插件所有，核心目录不关心 Discord tag、Slack user handle、Matrix room alias 等平台差异。解析结果交给 `buildAllowlistResolutionSummary`，得到 `resolvedMap`、`mapping`、`unresolved` 和 `additions`。

如果是顶层 allowlist，插件可用 `mergeAllowlist` 将 `additions` 加回配置，或用 `canonicalizeAllowlistWithResolvedIds` 把已解析名称替换成 ID。如果是嵌套 entries，则用 `patchAllowlistUsersInConfigEntries` 批量更新每个 entry 的 `users` 字段。最后用 `summarizeMapping` 记录“哪些被解析、哪些没解析”的采样日志。

消息到达后的真正准入判定不在该目录完成。进入 runtime 后，`src/channels/allowlist-match.ts` 会把 allowlist 编译为 set 和 wildcard 标记，再基于 sender id、name 或其他候选 key 判定是否匹配；更高层的 ingress 策略会在 `src/channels/message-access/allowlist.ts` 合并 DM/group/route allowlist 并处理失败原因。

## 上下游依赖

上游输入主要来自插件配置和插件平台解析能力。配置结构来自 `openclaw/plugin-sdk/channel-config-helpers` 的 `mapAllowFromEntries` 以及各插件自己的 monitor config。平台解析由插件实现，例如 Discord、Slack、Matrix 等各自根据平台目录、成员列表或 API 返回稳定 ID。

该目录依赖 `src/shared/string-coerce.ts` 做字符串归一化，依赖 `src/shared/string-sample.ts` 做日志采样摘要，依赖 `src/runtime.ts` 的 `RuntimeEnv` 类型完成可选日志输出。它不直接依赖具体 channel plugin，也不接触网络、文件持久化或消息发送。

下游包括 `src/plugin-sdk/allow-from.ts` 的 SDK 导出，以及多个 `extensions/*` monitor 模块。根据当前片段推断，它是 channel plugin setup/monitor 生命周期里的共享工具层，而不是核心消息循环热路径；依据是调用点集中在 `extensions/*/monitor*` 和 `runtime-api.ts`，实际匹配逻辑则在 `src/channels/allowlist-match.ts`、`src/channels/message-access/allowlist.ts`。

## 修改时最容易踩的坑

第一，不要把解析辅助和准入判定混在一起。`resolve-utils.ts` 只处理配置条目如何被解析、合并、替换和记录；sender 是否被允许，应继续留在 `allowlist-match` 和 `message-access` 层。

第二，谨慎处理 `*`。在 canonicalize 中 `*` 要保留；在收集待解析用户时 `*` 要跳过。如果把 `*` 当作普通用户解析，可能破坏“允许所有”的语义，或制造无意义日志。

第三，去重是大小写不敏感但保留首个原始值。修改 `dedupeAllowlistEntries` 时要注意配置可读性和兼容性，不能简单改成全部 lowercase，否则可能影响用户可见配置或日志。

第四，`merge` 和 `canonicalize` 的行为不同。`merge` 会让旧名称和稳定 ID 共存，适合保守迁移；`canonicalize` 会替换已解析名称，适合平台已确认 ID 的配置清理。插件选择策略时要考虑是否会改变已有配置文件。

第五，日志要保持采样和低敏。`summarizeMapping` 使用 `summarizeStringEntries` 限制数量，修改时不要输出完整成员列表、真实敏感标识或平台 token 相关内容。

第六，边界规则要求插件通过 `openclaw/plugin-sdk/*` 使用能力。新增工具如果是给插件用，应检查 `src/plugin-sdk/allow-from.ts` 和相关 SDK contract 测试，而不是让插件直接 import `src/channels/allowlists/resolve-utils.ts`。

## 推荐阅读顺序

1. 先读 `src/channels/AGENTS.md`，理解 `src/channels/**` 是核心实现边界，插件侧应走 SDK。
2. 再读 `src/channels/allowlists/resolve-utils.ts`，把 `mergeAllowlist`、`buildAllowlistResolutionSummary`、`canonicalizeAllowlistWithResolvedIds`、`patchAllowlistUsersInConfigEntries` 串成配置解析流程。
3. 接着读 `src/channels/allowlists/resolve-utils.test.ts`，确认空值、`*`、未解析项、重复 ID、日志采样等边界。
4. 然后读 `src/plugin-sdk/allow-from.ts`，看这些工具如何成为插件可用 API。
5. 最后读一个具体插件调用点，例如 `extensions/discord/src/monitor/provider.allowlist.ts` 或 `extensions/matrix/src/matrix/monitor/config.ts`，再对照 `src/channels/allowlist-match.ts` 和 `src/channels/message-access/allowlist.ts`，区分“配置解析”和“消息准入判定”的职责分层。
