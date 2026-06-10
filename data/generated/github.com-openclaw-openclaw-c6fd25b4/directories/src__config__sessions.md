# 子系统：src/config/sessions

## 解决什么问题

`src/config/sessions` 是 OpenClaw 的“会话状态持久化与索引”子系统。它解决的不是单次消息如何调用模型，而是多轮会话如何被稳定定位、复用、落盘、清理和恢复：同一个用户、群组、agent、线程或显式 `SessionKey` 应该落到哪个会话桶；该桶当前绑定哪个 `sessionId`；真实 transcript 文件在哪里；运行时产生的 delivery、artifact、模型覆盖、压缩检查点、上下文预算等元数据如何保存。

从 `src/config/sessions.ts` 可以看出这里对外提供一个聚合出口，向上层暴露 `session-key`、`store`、`transcript`、`lifecycle`、`reset`、`targets`、`cleanup-service` 等能力。也就是说，上层通常不直接操作目录内所有细节文件，而是通过这个 barrel 引入会话相关 API。

## 相关目录和文件

`src/config/sessions/session-key.ts` 负责把消息上下文解析成规范会话键。它处理 `per-sender` 与 `global` 两种 `SessionScope`，也会识别显式 `ctx.SessionKey`，并把普通直聊归并到类似 `agent:<agentId>:<mainKey>` 的主会话键；群组或频道会话则保持隔离。

`src/config/sessions/store.ts`、`store-load.ts`、`store-writer.ts`、`store-entry.ts` 是会话索引的核心。它们维护 `sessionKey -> SessionEntry` 的映射，处理读取、写入、缓存、旧键归一化、迁移和维护裁剪。

`src/config/sessions/session-file.ts`、`paths.ts`、`session-file-rotation.ts` 管理 `sessionId` 到实际 session/transcript 文件路径的解析与持久化，避免仅靠运行时临时路径导致重启后找不到历史。

`src/config/sessions/transcript.ts`、`transcript-append.ts`、`transcript-stream.ts`、`transcript-mirror.ts`、`transcript-resolve.runtime.ts` 负责 transcript 文件的创建、追加、倒序读取、镜像文本、流式读取与运行时解析。根据当前片段推断，transcript 是 JSONL 形态，首行可能是来自 `@earendil-works/pi-coding-agent` 的 session header，后续追加消息或 OpenClaw 自定义事件。

`src/config/sessions/lifecycle.ts`、`cleanup-service.ts`、`reset.ts`、`disk-budget.ts` 处理生命周期维护：过期清理、重置、磁盘预算、保留策略。`targets.ts`、`delivery-info.ts`、`artifacts.ts`、`metadata.ts` 则记录与消息投递、附件/产物、会话元信息相关的辅助状态。

## 核心对象

`SessionEntry` 是 store 的基本值对象，定义在 `src/config/sessions/types.ts`。它至少承载 `sessionId`、`updatedAt`、`sessionStartedAt`、`sessionFile` 等持久化索引信息，并扩展出运行态模型字段、delivery 上下文、CLI session binding、ACP 元数据、上下文预算、压缩检查点、插件注入信息等。

`SessionScope` 决定会话隔离粒度，目前主要是 `"per-sender"` 和 `"global"`。`SessionOrigin` 描述消息来源，包括 provider、surface、chatType、from、to、threadId、accountId 等，用来把 channel 世界里的身份转成会话可理解的来源信息。

`CliSessionBinding` 描述 OpenClaw 会话与底层 CLI/runtime 会话之间的绑定，包含 `sessionId`、认证 profile、prompt/tool/MCP 指纹等。它的存在说明这里不仅存聊天历史，也保存“能否复用底层 agent runtime”的判断依据。

`SessionCompactionCheckpoint` 和 `SessionContextBudgetStatus` 服务于上下文压缩与预算控制。前者记录压缩前后 transcript 引用，后者记录模型、token 预算、是否应压缩以及采取的路线。

## 运行流程

典型入口从消息上下文开始。上游 channel 或 agent runner 传入 `MsgContext`、`SessionScope`、`agentId` 等信息，`resolveSessionKey` 先检查显式 `SessionKey`，否则按群组、频道、直聊、全局作用域推导规范 key。直聊默认会收敛到 agent 主会话，群组和频道则被加上 agent 前缀后独立保存。

随后 store 层读取会话索引。`loadSessionStore` 会从默认或指定路径读取 JSON store，应用迁移、归一化 entry 形状，并按维护配置裁剪陈旧或超量条目。`resolveSessionStoreEntry` 会把大小写折叠、历史旧 key、保留 opaque peer id 的规范化规则合并起来，选择最新的现存 entry。

如果需要 transcript，`resolveSessionTranscriptFile` 会根据 `sessionId`、`sessionKey`、`agentId` 和可选线程信息解析文件路径。若 store 中缺少 `sessionFile`，`resolveAndPersistSessionFile` 会把解析出的路径写回 store，使后续运行不必重新猜路径。

当 assistant 产生回复时，`appendAssistantMessageToSessionTranscript` 会检查 `sessionKey` 和文本/媒体内容，必要时创建 session header，然后把消息追加到 transcript。读取最新回复时，`readLatestAssistantTextFromSessionTranscript` 会倒序扫描 transcript，并跳过仅用于 OpenClaw delivery mirror 或 gateway 注入的内部 assistant 消息，避免把系统镜像当成用户可见回复。

## 上下游依赖

上游主要来自 `src/channels/**`、`src/agents/**`、`src/gateway/**` 和配置 schema。channel 层提供 sender、thread、account、route 等来源信息；agent runner 使用 session file 和 transcript 恢复上下文、执行压缩、绑定底层 runtime；gateway 可能通过 session 元数据向外暴露或更新状态。

下游依赖包括 Node 的 `fs`、`path`、`crypto`，OpenClaw 自己的 `src/routing/session-key.ts`、`src/utils/delivery-context.*`、`src/plugins/**`，以及外部包 `@earendil-works/pi-coding-agent`、`@earendil-works/pi-agent-core`。这里对外部 session 文件格式的处理必须尊重上游包的 contract，例如 session header 版本、`SessionManager.appendMessage` 的消息形状等，不能凭空改字段。

## 修改时最容易踩的坑

第一，不能把 `sessionKey` 当普通字符串随意 lower-case。`store-entry.ts` 明确使用 `normalizeSessionKeyPreservingOpaquePeerIds`，说明某些 peer id 是不透明标识，错误折叠会把不同会话合并。

第二，store 和 transcript 是两层状态。`SessionEntry.sessionFile` 只是索引，真实 transcript 仍在文件里。只更新其中一边会导致重启后找不到历史、重复创建 session，或读取到旧 transcript。

第三，直聊主会话、群组会话、显式 `SessionKey` 的隔离规则不同。修改 `resolveSessionKey` 时要同时考虑 agent 主会话、group/channel key、`normalizeExplicitSessionKey`，否则会破坏已有用户的会话连续性。

第四，维护和清理不是简单删除。`store-maintenance-*`、`disk-budget.ts`、`cleanup-service.ts` 暗示这里有保留 key、预算、活跃会话保护等策略。新增清理逻辑要证明不会删掉当前活跃或刚迁移的会话。

第五，transcript 中可能混有内部事件和非用户可见 assistant 消息。读取“最后回复”时要保持过滤逻辑，否则 delivery mirror、gateway injected 这类内部消息会污染用户可见状态。

## 推荐阅读顺序

1. 先读 `src/config/sessions.ts`，了解公共出口。
2. 再读 `src/config/sessions/types.ts`，建立 `SessionEntry`、`SessionOrigin`、`CliSessionBinding`、压缩与预算对象的整体模型。
3. 读 `src/config/sessions/session-key.ts`、`explicit-session-key-normalization.ts`、`group.ts`，理解会话桶如何命名。
4. 读 `src/config/sessions/store-entry.ts`、`store-load.ts`、`store-writer.ts`、`store.ts`，理解索引读写、归一化、迁移和维护。
5. 读 `src/config/sessions/paths.ts`、`session-file.ts`、`transcript.ts`、`transcript-append.ts`，串起 store entry 与真实 transcript 文件。
6. 最后读 `cleanup-service.ts`、`reset.ts`、`disk-budget.ts`、相关 `*.test.ts`，确认生命周期边界和回归保护。
