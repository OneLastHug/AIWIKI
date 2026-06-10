# 子系统：src/channels/inbound-event

## 解决什么问题

这个目录负责把“渠道进来的原始消息”整理成统一的入站事件语义。它解决的不是具体渠道怎么收消息，而是“收到之后怎么归类、怎么补齐上下文、怎么把媒体和命令信息整理成后续自动回复能直接消费的格式”。

从当前代码看，它主要把三类事情收拢到一起：一是判断这条入站内容应当按 `user_request` 还是 `room_event` 处理；二是把会话、发送者、回复目标、权限、补充上下文等事实拼成最终的消息上下文；三是把图片、音频等媒体转成稳定的历史记录和模板字段。根据当前片段推断，这一层是各渠道适配器进入核心回复管线前的统一归一化层。

## 相关目录和文件

核心文件只有几块：

- `src/channels/inbound-event/kind.ts`：定义 `InboundEventKind`，目前只有 `"user_request"` 和 `"room_event"` 两种。
- `src/channels/inbound-event/classification.ts`：负责事件分类，以及读取配置里的“群聊未提及消息”策略。
- `src/channels/inbound-event/context.ts`：把入站事实组装成最终的 `FinalizedMsgContext`。
- `src/channels/inbound-event/media.ts`：把渠道侧媒体输入标准化，并生成兼容历史和模板系统的媒体字段。
- `src/channels/inbound-event/*.test.ts`：用例覆盖分类、上下文拼装和媒体归一化，说明这几个文件的边界就是该子系统的稳定契约。

相邻但强相关的依赖主要在 `src/channels/turn/types.ts`、`src/auto-reply/**`、`src/config/types.openclaw.js`、`src/security/context-visibility.js`。

## 核心对象

最关键的对象是 `InboundEventKind`，它是整个子系统的输出语义标签。`classifyChannelInboundEvent()` 根据会话类型、是否被提及、是否是控制命令、是否是中止请求、命令来源等条件，决定是否按房间事件处理。

`buildChannelInboundEventContext()` 是另一个中心函数。它接收一组已经归一化的事实对象：`ConversationFacts`、`RouteFacts`、`ReplyPlanFacts`、`MessageFacts`、`AccessFacts`、`CommandFacts`、`SupplementalContextFacts`、`InboundMediaFacts[]`，然后输出 `BuiltChannelInboundEventContext`。这个结果本质上是 `FinalizedMsgContext` 的加强版，额外携带 `Body`、`RawBody`、`ChatType`、`SessionKey`、`CommandAuthorized`、`InboundEventKind` 等字段。

媒体相关的核心对象是 `InboundMediaFacts`。`toInboundMediaFacts()`、`toHistoryMediaEntries()`、`buildChannelInboundMediaPayload()` 分别面向不同下游：一个给当前上下文，一个给历史记录，一个给旧式模板字段。

## 运行流程

典型流程可以理解成四步：

1. 渠道适配器先收集原始消息事实，并在更上层生成 `ConversationFacts`、`RouteFacts`、`ReplyPlanFacts` 等结构。
2. `resolveUnmentionedGroupInboundPolicy()` 先从 agent 级配置或全局配置里取出群聊未提及消息策略。
3. `classifyChannelInboundEvent()` 根据策略和当前消息条件，得到 `user_request` 或 `room_event`。
4. `buildChannelInboundEventContext()` 把正文、回复链、线程信息、发送者信息、命令授权状态、补充上下文、媒体信息全部合并，交给 `finalizeInboundContext()` 输出最终模板上下文。

补充上下文会经过 `filterChannelInboundSupplementalContext()` 过滤，是否保留 quote、forwarded、thread 这类内容，取决于 `ContextVisibilityMode` 和 `shouldIncludeSupplementalContext()`。媒体则先被标准化，再同时写入单值字段和数组字段，保证老模板和新逻辑都能读。

## 上下游依赖

上游主要是渠道实现、消息接入层和路由层。也就是说，Telegram、Matrix 之类的渠道适配器先把“某条原始消息”翻译成这套事实对象，再交给这里统一处理。这个目录本身不负责网络、轮询、Webhook 或平台鉴权。

下游主要是自动回复和模板系统。`context.ts` 直接依赖 `createCommandTurnContext()`、`finalizeInboundContext()` 和 `shouldIncludeSupplementalContext()`，说明这里的输出是给回复管线、命令系统和上下文渲染器直接消费的。`media.ts` 还要兼容历史媒体结构，说明它同时服务新旧两套消费面。

配置依赖也很明确：`resolveUnmentionedGroupInboundPolicy()` 读取 `OpenClawConfig`，并通过 `resolveAgentConfig()` 优先使用 agent 级 `groupChat.unmentionedInbound`。这意味着事件分类并非纯逻辑判断，而是受配置和 agent 范围影响。

## 修改时最容易踩的坑

第一，别把 `user_request` 和 `room_event` 的边界改松。当前规则很明确：只有群聊或频道、且启用了 `room_event` 策略、同时没有提及、控制命令、abort 请求或 native 命令来源时，才会进入 `room_event`。

第二，`buildChannelInboundEventContext()` 里很多字段都有“回退顺序”，例如 `Body`、`BodyForAgent`、`CommandBody`、`SessionKey`、`To`、`ReplyToId`。改动时最容易破坏历史兼容或让模板字段为空。

第三，媒体数组必须保持索引对齐。`MediaPaths`、`MediaUrls`、`MediaTypes` 不是简单的压缩列表，而是为了和历史附件解析器兼容，空值也会被保留成位置占位。

第四，补充上下文过滤不是简单删字段。quote、forwarded、thread 是否保留，和可见性模式、发送者是否被允许有关，改这里很容易影响隐私边界。

## 推荐阅读顺序

1. `src/channels/inbound-event/kind.ts`
2. `src/channels/inbound-event/classification.ts`
3. `src/channels/inbound-event/media.ts`
4. `src/channels/inbound-event/context.ts`
5. `src/channels/inbound-event/classification.test.ts`
6. `src/channels/inbound-event/context.test.ts`
7. `src/channels/inbound-event/media.test.ts`
8. `src/channels/turn/types.ts`

按这个顺序读，能先建立事件语义，再看上下文拼装，最后理解媒体和历史兼容层。
