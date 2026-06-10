# 文件：src/channels/message/send.ts

## 一句话定位

`src/channels/message/send.ts` 是 OpenClaw “durable message send” 的核心编排层：它把上层要发送的 `ReplyPayload[]` 渲染成批次，交给 outbound 投递系统发送，并统一产出回执、发送状态、部分失败、抑制原因和生命周期钩子结果。

## 它暴露/定义了什么

这个文件主要定义两类内容。

第一类是 durable 发送的类型契约，包括 `DurableMessageBatchSendParams`、`DurableMessageBatchSendResult`、`DurableMessagePayloadDeliveryOutcome`、`DurableMessageSendContextParams`、`DurableMessageSendContext` 等。它们把底层 outbound delivery 的结果包装成 message 层能理解的状态：`sent`、`suppressed`、`partial_failed`、`failed`。

第二类是两个入口函数：`withDurableMessageSendContext` 和 `sendDurableMessageBatch`。前者创建一个可扩展的发送上下文，适合需要自定义 render、preview、edit、delete、commit、fail 流程的调用方；后者是默认批量发送入口，执行 “render -> send -> commit/fail” 的标准流程。

## 谁调用它

内部调用方主要通过 `src/channels/message/runtime.ts` 的再导出使用它，保持 channel message 运行时代码的懒加载边界。典型调用点包括 `src/channels/turn/durable-delivery.ts`、`src/cron/delivery.ts`、`src/gateway/server-methods/send.ts`、`src/gateway/server-node-events.ts`、`src/agents/command/delivery.ts`、`src/infra/outbound/message.ts`、`src/infra/heartbeat-runner.ts`、`src/infra/session-maintenance-warning.ts`、`src/auto-reply/reply/route-reply.ts`、`src/media-understanding/echo-transcript.ts`。

插件侧不能直接依赖 `src/channels/**`，而是通过 SDK facade 使用。证据是 `src/plugin-sdk/channel-message.ts`、`src/plugin-sdk/channel-message-runtime.ts` 会导出或动态加载这里的能力，`extensions/discord/src/monitor/reply-delivery.ts` 通过 `openclaw/plugin-sdk/channel-message` 调用 `sendDurableMessageBatch`。

## 它调用谁

发送链路的核心下游是 `src/infra/outbound/deliver.ts` 中的 `deliverOutboundPayloadsInternal`，负责真正按 channel、target、queue policy 和 adapter 执行 payload 投递。它还依赖 `src/channels/message/rendered-batch.ts` 的 `createRenderedMessageBatch` 生成渲染批次，依赖 `src/channels/message/receipt.ts` 的 `createMessageReceiptFromOutboundResults` 把 outbound 结果整理成 message receipt，依赖 `src/channels/message/live.ts` 的 `createLiveMessageState`、`markLiveMessagePreviewUpdated` 维护预览状态。错误识别和结果类型来自 `src/infra/outbound/deliver-types.ts`，日志和错误格式化来自 `src/logging/subsystem.ts`、`src/infra/errors.ts`。

## 核心流程

`sendDurableMessageBatch` 是默认流程入口。它先调用 `withDurableMessageSendContext` 创建上下文，然后调用 `ctx.render()` 把 `payloads` 转成 `RenderedMessageBatch`，再调用 `ctx.send(rendered)` 发送。发送结果如果是 `sent` 或 `suppressed`，会执行 `ctx.commit(receipt)`；如果是失败或部分失败，会执行 `ctx.fail(error)`，最后把结构化结果返回给调用者。

`withDurableMessageSendContext` 负责组装上下文。它会解析 `signal` 和 deprecated 的 `abortSignal`，根据 `durability` 选择 `queuePolicy`，初始化 live preview，并把发送上下文中的 `render`、`previewUpdate`、`send`、`edit`、`delete`、`commit`、`fail` 函数组装好。`send` 内部调用 `deliverOutboundPayloadsInternal`，同时收集每个 payload 的投递 outcome，并通过 `onDeliveryIntent` 把 outbound intent 转成 durable message intent 写回 `ctx.intent`。

结果归一化是这个文件的重要职责。底层返回非空 `results` 时视为 `sent`；返回空结果但无失败时视为 `suppressed`，原因来自 payload outcome，兜底为 `no_visible_result`；如果某个 payload 失败但已有部分结果，则返回 `partial_failed` 并附带 receipt；如果没有任何成功结果，则返回 `failed`。如果底层抛出 `OutboundDeliveryError`，也会按 `error.results` 是否为空区分部分失败和完全失败。

## 关键函数的高层作用

`withDurableMessageSendContext` 是生命周期编排器。它不只发送消息，还提供发送前渲染、预览更新、编辑已有 receipt、删除 receipt、提交 receipt、失败清理等钩子，因此适合 inbound reply、turn delivery、gateway send 等不同场景复用同一套 durable 语义。

`sendDurableMessageBatch` 是标准化便捷入口。调用方只要传入 channel、target、payloads、thread/reply 信息、账号和钩子，就能得到稳定的 `DurableMessageBatchSendResult`，不必自己处理 outbound error、receipt、partial failure 和 suppression。

`toDurableMessageIntent` 把 outbound 层的 `OutboundDeliveryIntent` 转成 message 层的 `DurableMessageSendIntent`，关键转换是把 `queuePolicy` 映射为 `required` 或 `best_effort` durability，并携带 rendered batch。`toDurablePayloadOutcome` 和 `toDurablePayloadOutcomes` 目前只是类型层转接，辅助维持 message 层结果类型。

## 修改风险

最高风险是改变状态归一化语义。`sent`、`suppressed`、`partial_failed`、`failed` 被 gateway、cron、agent command、turn delivery、插件 SDK 和测试共同依赖；例如空 `results` 现在不是失败，而是可解释的 suppressed。随意改动会影响用户可见的发送结果、重试判断和上层错误处理。

第二类风险是 durability 和 queue policy。当前除显式 `best_effort` 外默认使用 `required`，这直接影响是否必须进入队列/持久投递路径。修改默认值、`signal` 传递或 `onDeliveryIntent` 行为，可能破坏队列契约、取消语义和回执追踪。

第三类风险是插件边界。`src/channels/**` 是核心 channel 实现，插件应走 `openclaw/plugin-sdk/*`。如果把新能力只加在此文件而不更新 SDK facade、类型或测试，外部/官方插件可能拿不到一致行为；反过来，若在热路径中静态引入更重的 runtime，也可能违反 `src/channels/AGENTS.md` 对 lazy boundary 的约束。

第四类风险是失败清理。`ctx.fail` 会捕获 `onSendFailure` 自身错误并保留原始发送错误；这避免 cleanup 覆盖真正失败原因。修改这里的异常优先级，会改变诊断信息和上层重试依据。测试证据集中在 `src/channels/message/send.test.ts`、`src/channels/turn/durable-delivery.test.ts`、`src/gateway/server-methods/send.test.ts` 以及插件侧 durable delivery 测试，改动时应优先覆盖这些状态矩阵。
