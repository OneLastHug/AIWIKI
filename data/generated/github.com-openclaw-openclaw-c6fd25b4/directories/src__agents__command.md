# 子系统：src/agents/command

## 解决什么问题

`src/agents/command` 是 OpenClaw agent 一次“命令式运行”的编排层：把来自 CLI、gateway、channel ingress、子 agent 或内部任务的一条输入，规整成可执行的 agent run，并把运行结果写回 session、transcript、delivery 通道和调用方结果。它不直接定义某个模型 provider 的底层协议，也不应承担 plugin/channel 的发现逻辑；它更像 agent runtime 前面的“请求归一化与会话事务层”。

从当前片段看，这个目录主要解决四类问题：第一，解析本次运行该绑定到哪个 `sessionId`、`sessionKey`、agent store；第二，把输入上下文整理成 `AgentCommandOpts` 和 `AgentRunContext`，包括 channel、account、thread、group、workspace、模型覆盖权限等；第三，在 CLI runtime、embedded Pi runtime、ACP 等执行路径之间选择并衔接；第四，持久化 session entry、transcript、usage、auth profile、fallback 元数据，并在需要时触发消息投递。

## 相关目录和文件

核心入口类型在 `src/agents/command/types.ts`，其中 `AgentCommandOpts` 是本目录最重要的输入契约，覆盖消息正文、附件、agent/model/provider override、delivery、session、tool allow-list、子 agent 元数据、bootstrap context、internal events、stream params 等运行参数。`shared-types.ts` 放较小的共享类型，例如 `AgentStreamParams` 和 client tool 定义。

`session.ts` 负责 session key/session id 解析，依赖 `src/config/sessions/*` 和 `src/routing/session-key.ts`。它会处理显式 `sessionKey`、显式 `sessionId`、按发送者派生 key、默认 agent、旧 main session 兼容迁移，以及跨 agent store 的 session id 匹配。

`run-context.ts` 负责把 `AgentCommandOpts` 中分散的 channel/account/thread/group 信息折叠为 `AgentRunContext`。它会用 `resolveMessageChannel`、`normalizeAccountId` 和 `stringifyRouteThreadId` 做规范化，并从 `to` 推导 `currentChannelId`，供 channel threading 适配层判断是否为同一会话。

`attempt-execution.ts` 是执行编排的重心。它连接 `runCliAgent`、`runEmbeddedPiAgent`、模型 runtime 选择、auth profile 选择、workspace skill snapshot、session write lock、transcript append、agent event、fallback/error 处理等。`attempt-execution.shared.ts` 放跨执行路径共用的小事务，例如 `persistSessionEntry`、internal events prompt 前缀、ACP prompt body 规整。`attempt-execution.helpers.ts` 根据导出名推断承载 CLI fallback prelude、session 文件内容判断、ACP visible text accumulator 等辅助逻辑。

`session-store.ts`、`session-store.runtime.ts` 根据文件名和调用点推断负责 session store 中 CLI session binding 的清理或更新。`delivery.ts`、`delivery.runtime.ts` 根据当前片段只能推断为结果投递相关层，和 `replyTo`、`replyChannel`、`bestEffortDeliver`、`sourceReplyDeliveryMode` 等选项相邻。`cli-compaction.ts` 处理 CLI 会话压缩。测试文件如 `attempt-execution.*.test.ts`、`session.resolve-session-key.test.ts`、`delivery.test.ts` 覆盖这些边界行为。

## 核心对象

`AgentCommandOpts` 是命令运行的总输入。需要特别区分其中几组字段：`message` 是模型输入，`transcriptMessage` 是用户可见 transcript 文本；`to`、`sessionId`、`sessionKey` 决定会话绑定；`replyTo`、`replyChannel`、`replyAccountId`、`threadId` 决定输出投递；`provider`、`model` 只在 `allowModelOverride` 允许时才应生效；`runContext` 是已准备好的上下文承载点，避免热路径重新查找 channel/plugin runtime。

`AgentCommandIngressOpts` 是 ingress 侧更严格的输入类型。它移除了本地可信默认值，要求调用方显式传入 `allowModelOverride`，并让 `senderIsOwner` 默认语义更保守。这是防止远端消息和本地 CLI 权限混淆的关键边界。

`SessionResolution` 描述一次运行最终使用的 session：包括 `sessionId`、可选 `sessionKey`、`SessionEntry`、store path、是否新会话，以及持久化的 thinking/verbose 等偏好。`SessionKeyResolution` 虽是内部类型，但体现了该目录的设计重点：session key、store 内容、store 路径必须一起流动，否则容易写错 agent 的 session store。

`PersistSessionEntryParams` 和 `persistSessionEntry` 是 session 写入的小事务封装。它通过 `updateSessionStore` 读取当前 entry，再用 `mergeSessionEntry` 合并，并支持 `clearedFields` 删除旧字段。这说明 session entry 更新不是简单覆盖，而是增量合并加少量显式清理。

## 运行流程

一次典型运行从调用方构造 `AgentCommandOpts` 开始。入口先解析 agent、provider、model、workspace、权限和 run context；`resolveAgentRunContext` 会把消息来源、回复目标、account、thread、group 信息归一化。随后 session 层通过 `resolveSessionKeyForRequest` 或相关函数决定目标 store 和 key：有显式 session id 时优先复用已有 entry；没有显式 key 时按配置 scope、`to` 和默认 agent 派生；遇到旧默认 agent main session 时存在兼容复制逻辑。

进入执行阶段后，`attempt-execution.ts` 会选择可用 harness/runtime。根据当前片段，CLI provider 会走 `runCliAgent`，Pi/OpenAI 相关路径可能走 `runEmbeddedPiAgent` 或经过 `resolveOpenAIRuntimeProviderForPi` 等路由。运行前还会解析 auth profile，准备 workspace skill snapshot，并把 internal events 注入 prompt；ACP 场景会使用 plain prompt body，避免把内部 runtime 标记原样暴露到 transcript。

执行完成后，系统把用户输入和 assistant 输出写入 transcript。写 transcript 前会通过 `resolveSessionTranscriptFile` 找文件，并用 `acquireSessionWriteLock` 加锁，避免并发写入破坏会话文件。对于 embedded assistant gap fill，代码会读取 transcript 尾部 assistant 文本，避免重复追加同一回复。最后 session entry 会写回 store，usage 会规整为无成本 usage 结构，必要时触发 delivery 或事件通知。

错误路径同样重要。`shouldClearReusedCliSessionAfterError` 表明某些错误会清除复用的 CLI session，例如 `AbortError` 或非 `session_expired` 的 `FailoverError`。这避免后续请求继续绑定到已失效或状态不可信的外部 CLI 会话。

## 上下游依赖

上游调用方包括 CLI 命令、gateway/ACP runtime、channel ingress、auto-reply、子 agent spawn 和内部定时/heartbeat 类任务。它们通过 `AgentCommandOpts` 或 `AgentCommandIngressOpts` 把输入传入本目录。

下游主要是三类。第一类是配置和 session 系统：`src/config/sessions/*`、`src/routing/session-key.ts`、`src/sessions/*`，用于 session key、store、transcript、reset/lifecycle 规则。第二类是 agent runtime：`src/agents/cli-runner.ts`、`src/agents/pi-embedded.ts`、model selection、harness selection、auth profile、skills、bootstrap cache 等。第三类是 channel/delivery 边界：`src/channels/*`、`src/plugin-sdk/channel-route.ts`、auto-reply reply normalization，以及 message channel/account/thread 规范化工具。

需要注意，`src/agents/AGENTS.md` 明确提示 agent 热路径应避免为了分类 target 或推断上下文而加载完整 channel/plugin runtime。因此本目录理想上消费已经准备好的 channel id、account id、thread id、target mode，而不是在请求时做大范围发现。

## 修改时最容易踩的坑

最常见风险是把 session routing 和 delivery routing 混在一起。`to`、`sessionId`、`sessionKey` 决定模型上下文归属；`replyTo`、`replyChannel`、`replyAccountId`、`threadId` 决定回复发到哪里。两者可以不同，不能随手共用。

第二个风险是权限默认值。CLI 本地调用可以更可信，但 ingress 必须显式证明 `senderIsOwner` 和 `allowModelOverride`。如果新增入口复用 `AgentCommandOpts` 而绕过 `AgentCommandIngressOpts`，可能让远端消息获得 provider/model override 或 owner-only 行为。

第三个风险是 session store 写入。不要直接改内存对象后假设已持久化，应走 `persistSessionEntry` 或现有 store helper，并携带正确的 `storePath`、`sessionKey`、agent id。显式 session id 匹配还可能跨 agent store，修改时要保留确定性选择逻辑。

第四个风险是 transcript 重复或泄露内部上下文。`transcriptMessage`、`resolveInternalEventTranscriptBody`、`suppressPromptPersistence`、embedded gap fill 都说明“给模型看的文本”和“给用户/会话看的文本”并不总是同一个东西。

第五个风险是引入新的热路径 runtime lookup。根据当前片段推断，本目录应依赖 `resolveAgentRunContext` 和轻量工具完成上下文规整；若为了 channel threading 或 target 解析加载完整 plugin runtime，会违背 agent 性能约束。

## 推荐阅读顺序

建议先读 `src/agents/command/types.ts`，建立 `AgentCommandOpts` 的字段地图。然后读 `src/agents/command/run-context.ts`，理解 channel/account/thread/group 如何归一化。第三步读 `src/agents/command/session.ts`，重点看 `resolveSessionKeyForRequest`、显式 `sessionId` 匹配和旧 main session 处理。第四步读 `src/agents/command/attempt-execution.shared.ts`，掌握 session entry 和 internal event prompt 的共用事务。最后读 `src/agents/command/attempt-execution.ts`，把 runtime 选择、auth profile、transcript、fallback、delivery 串起来。测试可按 `session.resolve-session-key.test.ts`、`attempt-execution.test.ts`、`attempt-execution.error-propagation.test.ts`、`delivery.test.ts` 的顺序辅助验证理解。
