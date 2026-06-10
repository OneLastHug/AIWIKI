# 子系统：src/channels/turn

## 解决什么问题

`src/channels/turn` 负责把“渠道收到的一次入站事件”抽象成可复用的 turn 处理流程：接收原始事件、标准化输入、判断事件是否能启动 agent、执行访问/预检、解析会话与上下文、记录入站会话、调用回复分发器，并把最终回复投递回渠道。它位于 core channel 实现层，服务于 Discord、Telegram、Slack、Line、Feishu 等插件，但插件作者通常不应直接依赖 `src/channels/**`，而是通过 `openclaw/plugin-sdk/*` 暴露的 façade 使用相关能力。

这个目录不是某个具体渠道的实现，也不是完整消息收发框架；它更像共享的“入站消息 turn 内核”。具体渠道仍负责把平台事件转换为 `NormalizedTurnInput`、准备 `FinalizedMsgContext`、选择路由、构造投递 adapter，以及处理平台特有的权限、线程、媒体和回复目标。

## 相关目录和文件

`src/channels/turn/kernel.ts` 是主入口，导出 `runChannelTurn`、`runResolvedChannelTurn`、`runPreparedChannelTurn`、`dispatchAssembledChannelTurn` 等函数，并重新导出若干辅助类型和工具。它组织 turn 生命周期，并接入 reply pipeline、durable delivery、bot-loop protection 和 history 清理。

`src/channels/turn/types.ts` 定义 turn 层的核心数据结构，包括 `ChannelTurnAdapter`、`ChannelTurnAdmission`、`PreflightFacts`、`AssembledChannelTurn`、`PreparedChannelTurn`、`ChannelEventDeliveryAdapter`、`ChannelTurnResult` 等。理解这个文件基本就能理解目录的边界。

`src/channels/turn/durable-delivery.ts` 负责 final reply 的 durable outbound 投递：根据 `ReplyPayload`、`replyToId`、`threadId`、`silent` 推导能力要求，检查 outbound handler 是否支持，再调用 `sendDurableMessageBatch`。

`src/channels/turn/history-window.ts` 是对 `src/auto-reply/reply/history.ts` 的渠道级封装，提供短上下文窗口的记录、媒体记录、构造 pending context、构造 inbound history 和清理能力。插件侧通过 `src/plugin-sdk/reply-history.ts` 暴露它。

`src/channels/turn/dispatch-result.ts` 统一判断一次回复分发是否产生“可见投递”或“final 投递”。`src/channels/turn/delivery-result.ts` 把 `MessageReceipt` 转换为 turn 层 `ChannelDeliveryResult`。`src/channels/turn/bot-loop-protection.ts` 则基于 `src/plugin-sdk/pair-loop-guard-runtime.ts` 记录 bot pair 交互，必要时抑制循环回复。

## 核心对象

`ChannelTurnAdapter` 是渠道接入 turn 内核的主要接口。`ingest` 把平台原始事件转换成 `NormalizedTurnInput`；`classify` 判断事件类型及是否能启动 agent；`preflight` 可提前给出 `dispatch`、`observeOnly`、`handled`、`drop` 等准入结论；`resolveTurn` 构造可执行的 `PreparedChannelTurn` 或 `AssembledChannelTurn`；`onFinalize` 做结束清理。

`ChannelTurnAdmission` 表示 turn 决策结果。`dispatch` 会正常分发；`observeOnly` 会记录上下文但不真正投递；`handled` 表示事件已由渠道或命令逻辑处理；`drop` 表示丢弃，且可选择记录历史。

`AssembledChannelTurn` 面向使用 OpenClaw 标准 reply stack 的调用方，包含 `cfg`、`agentId`、`ctxPayload`、`recordInboundSession`、`dispatchReplyWithBufferedBlockDispatcher`、`delivery` 等。`PreparedChannelTurn` 更底层，调用方自己提供 `runDispatch`。

`ChannelEventDeliveryAdapter` 封装回复投递：可先 `preparePayload`，可声明 `durable` 选项，核心 `deliver` 完成平台发送，`onDelivered` 和 `onError` 处理投递后观察与错误。

## 运行流程

典型流程从 `runChannelTurn` 开始。首先 `ingest` 标准化原始事件；如果返回空，结果是 `drop: ingest-null`。随后 `classify` 判断事件类别，默认是可启动 agent 的 `message`。如果事件不能启动 agent，则返回 `handled`。

接着执行 `preflight`。这里可以完成命令权限、allowlist、mention gate、群组策略、媒体预处理等前置判断。若结果是 `handled` 或 `drop`，内核不会进入 dispatch；对于允许记录的 drop，会通过 `recordDroppedChannelTurnHistory` 把文本和媒体写入短历史窗口。

若准入允许，`resolveTurn` 生成已解析 turn。之后 `dispatchResolvedChannelTurn` 判断它是 `PreparedChannelTurn` 还是 `AssembledChannelTurn`。核心执行阶段先检查 bot-loop suppression，再调用 `recordInboundSession` 写入会话，随后执行 `runDispatch` 或标准 `dispatchReplyWithBufferedBlockDispatcher`。对于 `observeOnly`，`runPreparedChannelTurn` 会返回空投递结果；在 `runChannelTurn` 的 assembled 路径中还会使用 noop delivery adapter，避免真的发出消息。

回复投递时，`dispatchAssembledChannelTurn` 会把标准 reply pipeline 的 `deliver` 包装起来：先准备 payload，再尝试 durable delivery；如果 durable 投递已处理，则走 `onDelivered`，否则回落到渠道自定义 `delivery.deliver`。最后清理 group pending history，并调用 `onFinalize`。

## 上下游依赖

上游主要是具体渠道插件和 runtime façade。`src/plugins/runtime/runtime-channel.ts` 把 `runChannelTurn`、`runResolvedChannelTurn`、`runPreparedChannelTurn`、`dispatchAssembledChannelTurn` 暴露给插件运行时；`src/plugin-sdk/reply-history.ts`、`src/plugin-sdk/channel-message.ts`、`src/plugin-sdk/inbound-reply-dispatch.ts` 则提供更稳定的 SDK 出口。调用方分布在 `extensions/discord`、`extensions/telegram`、`extensions/slack`、`extensions/line`、`extensions/feishu`、`extensions/msteams` 等插件中。

下游依赖包括 `src/auto-reply/**` 的回复构造、dispatcher、history、templating；`src/channels/message/**` 的 durable send、receipt、capability；`src/channels/session.ts` 和 `src/config/sessions.ts` 的会话记录；`src/infra/outbound/**` 的 outbound 队列和 delivery support；以及 `src/plugin-sdk/pair-loop-guard-runtime.ts` 的循环保护。

## 修改时最容易踩的坑

第一，`src/channels/**` 是 core channel 实现，插件面向的稳定入口应经过 `openclaw/plugin-sdk/*`。如果新增能力直接让插件 import `src/channels/turn/*`，会破坏边界。

第二，`observeOnly`、`handled`、`drop` 的语义不能混用。`observeOnly` 仍会记录会话但不应产生可见回复；`handled` 和 `drop` 不进入 dispatch；`drop` 只有在 `recordOnDrop` 或 admission 指定时才记录历史。

第三，durable delivery 只处理 `info.kind === "final"`。tool/block 等非 final payload 返回 `not_applicable`，不能假设所有回复都会经过 durable outbound。

第四，错误上的 `visibleReplySent`、`sentBeforeError` 标记很重要。部分发送失败可能已经产生用户可见消息，调用方依赖这些标记避免重复补发或误判。

第五，history 清理只在 group 且带 `historyKey`、`historyMap`、`limit` 时发生。改动 pending history 时要同时考虑 dropped turn、媒体 history、finalize 清理和插件侧 `createChannelHistoryWindow` 使用。

第六，bot-loop protection 是进程内 guard，有测试专用 clear/snapshot API。修改默认开关、scope 或 sender/receiver 事实会影响多个渠道的自动回复抑制行为。

## 推荐阅读顺序

1. 先读 `src/channels/AGENTS.md`，确认 channel core 与 plugin SDK 的边界。
2. 再读 `src/channels/turn/types.ts`，建立 turn 数据模型：admission、adapter、prepared/assembled turn、delivery result。
3. 阅读 `src/channels/turn/kernel.ts`，重点看 `runChannelTurn`、`dispatchAssembledChannelTurn`、`runPreparedChannelTurnCore`。
4. 阅读 `src/channels/turn/durable-delivery.ts`，理解 final reply 如何进入 `src/channels/message/send.ts` 和 outbound delivery。
5. 阅读 `src/channels/turn/history-window.ts` 与 `src/auto-reply/reply/history.ts`，理解群聊短上下文窗口。
6. 最后选一个实际调用方，例如 `extensions/telegram/src/bot-message-dispatch.ts` 或 `extensions/discord/src/monitor/message-handler.process.ts`，对照看具体渠道如何把平台事件接入这套 turn 内核。
