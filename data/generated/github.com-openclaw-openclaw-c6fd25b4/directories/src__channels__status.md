# 子系统：src/channels/status

## 解决什么问题

`src/channels/status` 是频道状态读取模型的核心小目录，主要解决“如何把运行时 Gateway 上报的频道账号状态，整理成稳定、可用于状态页/健康检查/控制端展示的账号状态视图”的问题。它不负责启动频道、不负责探测网络连接，也不直接调用 Discord、Slack、Telegram 等插件运行时代码，而是把外部传入的 `channelAccounts` payload 规范化、合并本地配置账号与运行时账号，并判断某个账号凭据当前是否可用。

从当前片段看，这个目录更像“状态读模型”而不是完整业务服务：它接受已经收集好的运行时状态和本地配置快照，输出按 `channelId`、`accountId` 组织的 `ChannelAccountSnapshot` 或状态行。这样上游可以把不同频道插件的状态统一展示，下游也能避免直接依赖某个插件内部字段。

## 相关目录和文件

`src/channels/status/read-model.ts` 是核心实现，导出读取、规范化、查找和合并状态的函数。

`src/channels/status/read-model.test.ts` 是行为测试，覆盖 Gateway 快照规范化、运行时账号优先、本地配置补齐、旧格式账号标识兼容、不可用凭据状态判断等场景。

邻近的 `src/channels/account-snapshot-fields.ts` 提供凭据状态字段判断，例如 `tokenStatus`、`botTokenStatus`、`appTokenStatus`、`signingSecretStatus`、`userTokenStatus` 是否表示 `configured_unavailable`。

`src/channels/plugins/types.public.ts` 定义 `ChannelAccountSnapshot` 这类面向频道公共状态面的数据形状。

`src/gateway/server-methods/channels.ts` 根据搜索结果可见包含 `channels.status` 处理、状态 hook 执行、probe/audit、timeout 与 summary 逻辑。根据当前片段推断，它是 `src/channels/status` 的重要上游调用方：负责收集运行时结果，再交由读模型规整。

`src/gateway/protocol/schema/channels.ts` 和 `src/gateway/protocol/channels.schema.test.ts` 属于协议层，约束 Gateway 对外暴露的频道状态请求/响应结构；读模型输出需要与这些协议结构保持一致。

## 核心对象

`RuntimeChannelStatusPayload` 表示运行时频道状态 payload，目前关注 `channelAccounts?: unknown`。这里刻意使用 `unknown`，说明输入来自外部边界，需要在本目录内做安全读取，而不是假设结构可靠。

`RuntimeChannelAccount` 是 `Record<string, unknown>`，表示运行时账号的松散对象。它保留了插件或 Gateway 可能传来的额外字段，但读取时只使用有限字段，如 `accountId`、`id`、`name`、`running`、`connected` 以及凭据状态字段。

`ChannelAccountSnapshot` 是规范化后的账号状态快照。`normalizeRuntimeChannelAccountSnapshots` 只接受带字符串 `accountId` 的对象作为有效快照，并按 `channelId` 放入 `Map<string, ChannelAccountSnapshot[]>`，过滤非数组、缺少 `accountId` 或结构不合法的条目。

`resolveChannelAccountStatusRows` 生成最终状态行。每行包含 `accountId`、`snapshot` 和 `source`，其中 `source` 为 `"gateway"` 表示来自运行时快照，为 `"config"` 表示由本地配置解析补齐。

`CREDENTIAL_STATUS_KEYS` 是状态判断的关键字段集合。`markConfiguredUnavailableCredentialStatusesAvailable` 会把 `configured_unavailable` 改写为 `available`，用于运行时已证明可用但配置视角仍显示不可用的摘要场景。

## 运行流程

典型流程从 Gateway 或状态命令收集到一个运行时 payload 开始，payload 中的 `channelAccounts` 按频道 id 存放账号数组。`readRuntimeAccountsByChannel` 先通过 `asRecord` 把未知输入安全收窄成普通对象，避免外部 payload 结构异常时抛出不必要错误。

如果调用方只关心某个频道，会用 `getRuntimeChannelAccounts` 按 `channelId` 取出账号列表；非数组输入会被视为空数组。随后 `resolveRuntimeChannelAccountId` 解析账号 id，优先级是 `accountId`、`id`、`name`，最后回退到 `DEFAULT_ACCOUNT_ID`。这个设计保留了旧运行时账号只带 `name` 的兼容读取能力，测试中也明确覆盖了 `{ name: "default", running: true }` 的场景。

如果需要构建全量状态视图，`normalizeRuntimeChannelAccountSnapshots` 会按频道过滤有效快照。之后 `resolveChannelAccountStatusRows` 合并本地账号 id 与运行时账号 id，使用 `uniqueStrings` 保持去重后的稳定集合。对每个账号，若 Gateway 有运行时快照，则优先使用 Gateway 快照；否则调用 `resolveLocalSnapshot(accountId)` 从本地配置生成一个快照，并标记来源为 `"config"`。

凭据可用性判断由 `hasRuntimeCredentialAvailable` 完成：先用 `findRuntimeChannelAccount` 找到目标账号，再排除包含 `configured_unavailable` 凭据状态的账号，最后要求 `running === true` 或 `connected === true`。因此，“运行中/已连接”和“凭据字段没有不可用标记”两个条件都要满足。

## 上下游依赖

上游主要是状态收集与协议入口。`src/gateway/server-methods/channels.ts` 负责 `channels.status` 请求、probe/audit hook、summary 聚合和超时处理；它需要一个稳定的读模型把插件返回的松散状态变成可展示数据。`src/gateway/server-methods/health.ts`、`src/commands/status.js` 相关状态命令也可能间接受益于统一的频道状态摘要；这一点根据搜索结果推断，依据是 Gateway health 会调用 `getStatusSummary`，频道状态又在 Gateway methods 中单独实现。

下游主要是展示层、控制端、CLI 或健康检查响应。它们不应理解每个频道插件的内部账号字段，而应消费 `ChannelAccountSnapshot` 或状态行中的 `accountId`、`snapshot`、`source`。

横向依赖包括 `src/routing/session-key.js` 中的 `DEFAULT_ACCOUNT_ID`，用于默认账号回退；`src/shared/record-coerce.js`、`src/shared/string-coerce.js`、`src/shared/string-normalization.js` 用于边界输入收窄、字符串规范化与去重；`src/channels/account-snapshot-fields.ts` 用于凭据状态语义判断。

## 修改时最容易踩的坑

不要把 `channelAccounts` 当成可信结构。这里的输入类型是 `unknown`，说明它可能来自 Gateway、插件 hook 或旧版本运行时，必须继续通过 `asRecord`、数组判断和字段类型判断收窄。

不要轻易删除 `id`、`name` 到 `accountId` 的回退。测试明确说明旧 live account 可能只有 `name`，状态摘要仍要能识别默认账号。

不要只看 `running` 或 `connected` 就认定凭据可用。`configured_unavailable` 是更强的否定信号，`hasRuntimeCredentialAvailable` 会优先排除这类账号。

不要改变 Gateway 快照优先级。`resolveChannelAccountStatusRows` 当前明确偏向运行时状态，因为它比本地配置更接近真实连接状态；本地配置只作为缺失账号的补充。

不要把插件专有字段扩散到核心读模型。`src/channels/AGENTS.md` 强调 `src/channels/**` 是核心频道实现，插件作者不应直接导入，插件面向外部的能力应该走 `openclaw/plugin-sdk/*` 或类型化 SDK seam。

## 推荐阅读顺序

先读 `src/channels/status/read-model.ts`，把输入 payload、账号 id 解析、凭据可用性、状态行合并四块逻辑串起来。

再读 `src/channels/status/read-model.test.ts`，测试比实现更清楚地展示了该目录承诺支持的行为边界，尤其是运行时优先、旧账号字段兼容、不可用凭据处理。

然后读 `src/channels/account-snapshot-fields.ts`，理解 `configured_unavailable`、`available` 等凭据状态字段如何影响账号配置判断。

接着读 `src/channels/plugins/types.public.ts` 中的 `ChannelAccountSnapshot`，确认状态快照面向外部暴露哪些字段。

最后再看 `src/gateway/server-methods/channels.ts` 和 `src/gateway/protocol/schema/channels.ts`，从入口请求、probe/audit、summary 和协议 schema 的角度理解这个读模型如何接入 Gateway 对外的频道状态接口。
