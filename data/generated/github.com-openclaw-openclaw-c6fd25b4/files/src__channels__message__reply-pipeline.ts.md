# 文件：src/channels/message/reply-pipeline.ts

## 一句话定位
这是消息通道回复流水线的组装层，负责把回复前缀、typing 状态、回复 payload 转换和 delivery mode 解析拼成一个可下发给上层的统一对象。它不直接发送消息，而是为 turn kernel、插件 SDK 和各类 channel 适配器提供标准化入口。

## 它暴露/定义了什么
这个文件对外暴露了几类东西：一是回复流水线的核心类型 `ChannelReplyPipeline`、`CreateChannelReplyPipelineParams`、`ReplyPrefixContext`、`ReplyPrefixOptions`、`TypingCallbacks`、`SourceReplyDeliveryMode`；二是工厂函数 `createChannelReplyPipeline`；三是 `resolveChannelSourceReplyDeliveryMode` 这个 delivery mode 解析包装；四是把 `createReplyPrefixContext`、`createReplyPrefixOptions`、`createTypingCallbacks` 直接再导出，方便上层按需组合。根据当前片段推断，它的设计目标是把“回复相关的共享拼装逻辑”收敛成一个稳定边界，避免各通道各自复制。

## 谁调用它
主调用方是 `src/channels/turn/kernel.ts`，那里会在 turn 组装阶段把 `replyPipeline` 合并进 dispatcher 和 reply options。它也被 `src/channels/message/index.ts` 统一对外导出，再经 `src/plugin-sdk/channel-reply-core.ts`、`src/plugin-sdk/channel-message.ts` 进入插件 SDK。结合仓库检索结果，`extensions/*` 下大量消息通道和 inbound/monitor 路径都通过这些 SDK 入口间接使用它，因此它属于高频共享基础设施。

## 它调用谁
它内部直接依赖 `normalizeAnyChannelId` 来规范 channel 标识，依赖 `getLoadedChannelPluginForRead` 按 channel 找到已加载插件，再从插件的 `messaging.transformReplyPayload` 读取通道特定的 payload 转换逻辑。它还调用 `createReplyPrefixOptions` 组装回复前缀相关配置，调用 `createTypingCallbacks` 把 typing 配置变成可执行回调；`resolveChannelSourceReplyDeliveryMode` 则只是把参数转交给 `resolveSourceReplyDeliveryMode`。

## 核心流程
核心流程很短，但位置很关键：先把传入的 `channel` 做规范化，得到统一的 `channelId`；然后构造一个惰性解析函数，只在需要时去加载对应 channel 插件并读取 `transformReplyPayload`，避免无谓的插件查询。接着决定最终的 payload 转换策略：如果调用方自己传了 `transformReplyPayload`，优先使用；否则在有 `channelId` 时，包装一层“从插件读取转换函数，再把结果应用到 payload”的默认逻辑。最后把 `createReplyPrefixOptions` 的结果、可选的 `transformReplyPayload`、以及 `typingCallbacks` 合并成一个完整的 `ChannelReplyPipeline` 返回给上层。

## 关键函数的高层作用
`createChannelReplyPipeline` 是主入口，职责是“把回复所需的共享能力装配好并返回”。`resolveChannelSourceReplyDeliveryMode` 只是一个轻包装，语义上表示“基于通道场景解析 source reply 的投递模式”。`createReplyPrefixContext`、`createReplyPrefixOptions`、`createTypingCallbacks` 这些被再导出的辅助函数，分别负责构造前缀上下文、前缀配置和 typing 回调；它们更像积木，不在这里展开业务规则。

## 修改风险
这个文件是共享边界，改动会同时影响 turn kernel、插件 SDK 兼容层以及所有复用 `createChannelMessageReplyPipeline` 的通道实现。最敏感的点有三个：一是 channel 规范化规则，二是插件侧 `transformReplyPayload` 的优先级和懒加载时机，三是 typing 回调和 prefix 配置的合并方式。任何一个变化都可能让不同 channel 的回复格式、发送前处理、或输入状态表现出现回归。由于它还承载旧 subpath 的兼容语义，改这里要特别注意外部插件和旧调用方是否仍能拿到同样的 pipeline 结构。
