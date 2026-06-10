# 文件：src/channels/message/receive.ts

## 一句话定位

`src/channels/message/receive.ts` 是消息接收链路里的轻量 ack/nack 上下文工厂：它不负责拉取、解析或分发消息，只负责把“这条入站消息什么时候算已接收、什么时候确认、失败时如何记录”封装成统一的 `MessageReceiveContext`。

## 它暴露/定义了什么

这个文件定义并导出几组接收确认相关类型：`MessageAckPolicy`、`MessageAckStage`、`MessageAckState`、`MessageReceiveContext<TMessage>`。其中 `MessageAckPolicy` 直接复用 `src/channels/message/types.ts` 里的 `ChannelMessageReceiveAckPolicy`，策略包括 `after_receive_record`、`after_agent_dispatch`、`after_durable_send`、`manual`。

它还导出两个核心函数：`shouldAckMessageAfterStage(policy, stage)` 和 `createMessageReceiveContext(params)`。前者是策略到生命周期阶段的纯映射，后者创建包含消息、通道、时间戳、取消信号、ack 状态、`ack()`、`nack()` 的上下文对象。

## 谁调用它

直接导出路径是 `src/channels/message/index.ts`，随后又通过 `src/plugin-sdk/channel-message.ts` 暴露给插件侧使用。实际调用点主要在通道插件的入站接收适配层。

Telegram 侧由 `extensions/telegram/src/bot-update-tracker.ts` 调用 `createMessageReceiveContext`，用于跟踪 Telegram update 的接收、去重和 offset 持久化。`extensions/telegram/src/bot-core.ts` 创建 tracker 时把 ack 策略设为 `after_agent_dispatch`，而 `extensions/telegram/src/channel.ts` 声明 Telegram receive 默认策略也是 `after_agent_dispatch`，支持 `after_receive_record` 与 `after_agent_dispatch`。

LINE 侧由 `extensions/line/src/webhook.ts`、`extensions/line/src/webhook-node.ts` 调用，用于 webhook 请求通过签名校验和 body 解析后立即构建接收上下文。LINE 当前使用 `after_receive_record`，ack hook 会返回 HTTP 200 JSON 响应。

测试覆盖集中在 `src/channels/message/lifecycle.test.ts`，并且 `src/channels/message/contracts.test.ts`、`src/plugin-sdk/channel-message.test.ts` 会验证 receive ack policy 的声明与能力证明。

## 它调用谁

本文件几乎不依赖外部运行时代码，只从 `src/channels/message/types.ts` 引入 `ChannelMessageReceiveAckPolicy` 类型。运行时调用主要来自传入参数里的 hook：`onAck` 和 `onNack`。也就是说，真正的平台确认动作由调用方注入：Telegram 的 `onAck` 会触发 update id 持久化；LINE 的 `onAck` 会写 HTTP 响应。

除此之外，它使用 `AbortController().signal` 创建一个永不主动 abort 的默认信号，用于调用方未传 `signal` 时保持 `MessageReceiveContext.signal` 字段总是存在。

## 核心流程

创建接收上下文时，调用方传入 `id`、`channel`、`message`，可选传入 `accountId`、`ackPolicy`、`receivedAt`、`signal`、`onAck`、`onNack`。`createMessageReceiveContext` 会默认把 `ackPolicy` 设为 `after_receive_record`，把 `ackState` 设为 `pending`，把 `receivedAt` 设为当前时间。

后续调用方在不同生命周期阶段调用 `ctx.shouldAckAfter(stage)` 判断是否应该确认。例如 LINE 在记录收到 webhook 后检查 `receive_record`，命中后立即 `ack()`；Telegram 在 `beginUpdate` 后可按 `receive_record` 处理，在 agent dispatch 完成后再按 `agent_dispatch` 推进 offset。根据当前片段推断，`durable_send` 是给更强持久化发送链路预留或由其他 durable receive/send 组合使用，依据是策略已在类型和测试中存在，但当前搜索到的生产调用主要覆盖前两个阶段。

`ack()` 是幂等的：如果状态已经是 `acked`，会直接返回，不会重复执行 `onAck`。首次 ack 会先执行 `onAck`，成功后把 `ackState` 置为 `acked`，记录 `ackedAt`，并清除 `nackErrorMessage`。`nack(error)` 会执行 `onNack`，然后把状态置为 `nacked`，并把错误标准化为字符串保存在 `nackErrorMessage`。

## 关键函数的高层作用

`shouldAckMessageAfterStage` 是策略解释器。它把 `after_receive_record` 映射到 `receive_record`，把 `after_agent_dispatch` 映射到 `agent_dispatch`，把 `after_durable_send` 映射到 `durable_send`，而 `manual` 永远不会因阶段自动触发 ack。这个函数的价值在于让各通道不用重复写策略判断，也避免插件各自理解 ack 时机。

`createMessageReceiveContext` 是上下文构造器和状态机边界。它把平台消息与 OpenClaw 的通道接收生命周期绑定起来，同时通过 hook 把平台相关副作用留在调用方。这样核心 message 包不需要知道 Telegram offset、LINE HTTP response 或其他平台的确认机制。

`normalizeAckErrorMessage` 只是辅助函数，用于把 `Error` 或非 `Error` 异常统一成可记录字符串，不展开复杂语义。

## 修改风险

第一类风险是 ack 时机改变。`after_receive_record`、`after_agent_dispatch`、`after_durable_send` 看似只是字符串映射，但它们对应真实平台语义：LINE 过早或过晚返回 HTTP 200 会影响 webhook 重试；Telegram 过早持久化 update id 可能导致 agent dispatch 失败后消息不再重放，过晚则可能造成重复处理。

第二类风险是 `ack()`/`nack()` 状态语义。当前 `ack()` 对重复调用幂等，但 `nack()` 可以在 ack 后把状态改成 `nacked`，测试也覆盖了先 ack 再 nack 的行为。改成“终态不可逆”前必须确认调用方是否依赖当前行为，尤其是错误恢复、offset 记录和测试断言。

第三类风险是默认策略。`createMessageReceiveContext` 默认 `after_receive_record`，这会影响所有未显式声明策略的新通道或测试夹具。修改默认值属于兼容性敏感变更，需要同步 `src/channels/message/types.ts` 的能力声明、`src/channels/message/contracts.test.ts` 的证明、插件适配层以及 SDK 文档。

第四类风险是 SDK 边界。该文件位于 `src/channels/**`，但通过 `src/plugin-sdk/channel-message.ts` 重新导出给插件使用。新增字段、重命名类型或改变 hook 执行顺序，都可能影响外部插件的编译和运行。按仓库边界规则，插件作者应通过 SDK seam 使用这些能力，因此这里的公开形状要按插件契约处理，而不是仅当作内部实现。
