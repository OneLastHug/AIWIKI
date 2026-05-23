# 目录：src/server/services/bot

## 它负责什么

`src/server/services/bot` 是 LobeHub 服务端的“按 Agent 绑定的外部聊天平台机器人”集成层。它把 Discord、Slack、Telegram、飞书、QQ、Line、微信等平台的消息事件，转换成 LobeHub 内部可以理解的 Agent 对话请求；也把 Agent 执行过程中的进度、最终回复、附件、反应表情、线程标题等，再转换回各平台的发送或编辑消息 API。

从层次上看，它不是前端 UI，也不是数据库模型本身，而是位于 `src/server/services` 的服务编排层。它会读取 `agent_bot_providers` 这类配置数据，解密平台凭据，创建平台客户端，注册 Chat SDK 事件处理器，并调用 `src/server/services/aiAgent` 发起 Agent 执行。Agent 执行完成后，又通过 `BotCallbackService` 走回平台消息发送链路。

这个目录还被共享机器人体系复用：`src/server/services/messenger/MessengerRouter.ts` 会复用 `AgentBridgeService`、`buildBotContext`、`replyTemplate`、`PlatformClient` 等能力。因此这里既服务“每个 Agent 自己配置一个 bot”的路径，也沉淀了一部分“平台消息接入”的通用抽象。

## 直接子目录地图

`src/server/services/bot/__tests__` 存放核心服务级测试，覆盖 `AgentBridgeService`、`BotCallbackService`、`BotMessageRouter`、DM 配对、提示词格式化、回复模板等行为。它适合用来理解主流程的边界条件。

`src/server/services/bot/ackPhrases` 提供处理中间态的短回复文案资源，例如 `vibeMatrix.ts`。这些文案通常用于消息已收到、正在处理之类的即时反馈，不承担平台协议逻辑。

`src/server/services/bot/platforms` 是最大的一块，负责平台适配。其根部有 `types.ts`、`registry.ts`、`const.ts`、`utils.ts`、`stripMarkdown.ts` 等共享抽象和工具；下方按平台拆分为 `discord`、`feishu`、`line`、`qq`、`slack`、`telegram`、`wechat`。每个平台目录大致包含 `client.ts`、`service.ts`、`schema.ts`、`definition.ts`、`sendAttachments.ts`、`protocol-spec.md` 等文件，但并非每个平台完全一致。根据当前片段推断，`client.ts` 更偏 Chat SDK 适配与入站事件解析，`service.ts` 更偏平台消息能力封装，`api.ts` 则用于直接调用平台 HTTP API。

## 关键入口

`src/server/services/bot/index.ts` 是该服务目录的聚合出口，外部如果只需要引用 bot 服务的公共能力，通常会从这里或具体服务文件导入。

`src/server/services/bot/BotMessageRouter.ts` 是入站消息的核心路由器。根据调用片段，它会被 `src/server/routers/lambda/agentBotProvider.ts` 使用，并提供 `getBotMessageRouter().invalidateBot(...)` 之类的缓存失效能力。它的职责是解析平台、加载或创建 bot、注册消息事件处理器，并把平台事件转交给 Agent 桥接层。

`src/server/services/bot/AgentBridgeService.ts` 是平台消息进入 Agent 执行的桥。它负责把一次提及、订阅消息或命令上下文，转换为 LobeHub 内部的 Agent 调用参数。它还维护线程活跃状态，例如 `isThreadActive`、`getActiveOperationId`、`requestStop`、`clearActiveThread`，用于避免同一平台线程中多轮执行互相覆盖，并支持 `/stop` 这类停止语义。

`src/server/services/bot/BotCallbackService.ts` 是 Agent 执行结果回调到聊天平台的入口。它接收 `BotCallbackBody`，区分 `type: 'step'` 与 `type: 'completion'`。step 阶段会编辑进度消息、替换反应表情、续租 typing 状态；completion 阶段会停止 typing、发送或编辑最终回复、清理反应状态、清理活跃线程，并尝试总结平台线程标题。

`src/server/services/bot/buildBotContext.ts` 负责构建传给 Agent 的 `botContext`。这类上下文会影响权限判断、设备工具访问、平台来源识别、发送者身份识别等逻辑。`src/server/services/aiAgent/index.ts` 中可见 `botContext`、`botPlatformContext` 被用于执行元数据、工具权限和附件摄取流程。

`src/server/services/bot/platforms/registry.ts` 与 `src/server/services/bot/platforms/index.ts` 是平台能力注册与导出的中心。新增平台或读取平台默认配置时，通常要先看这里。`platformRegistry`、`mergeWithDefaults`、`resolveBotProviderConfig` 等能力会被 bot 配置路由和消息路由复用。

`src/server/services/bot/agentBotProviderSettings.ts` 关联每个平台的配置字段和默认值。`src/server/routers/lambda/agentBotProvider.ts` 会使用它处理用户创建、更新、启停 bot provider 的流程。

## 主流程位置

入站主流程大致是：平台 webhook、websocket 或 polling 事件进入服务端后，由 agent bot provider 相关路由或平台连接层找到 `BotMessageRouter`；`BotMessageRouter` 根据平台与 `applicationId` 查找配置，创建对应 `PlatformClient` 和 Chat SDK bot；随后注册消息、提及、命令等处理器。根据当前片段推断，普通消息或提及最终会进入 `AgentBridgeService`，由它构造 prompt、附件、平台上下文和 `botContext`，再调用 `src/server/services/aiAgent/index.ts` 发起 Agent 执行。

执行期间的异步回调走另一条链路：Agent runtime 通过 completion webhook 或 hook 回调提交 `BotCallbackBody`；`BotCallbackService.handleCallback` 根据 `platformThreadId` 前缀识别平台，创建平台 messenger；如果是 step，就更新进度消息、反应表情与 typing；如果是 completion，就渲染最终回复、处理附件、拆分长消息、编辑或发送到平台，并清理活跃线程状态。

主动发送平台消息的主流程在 `src/server/routers/lambda/botMessage.ts`。该路由通过 `resolveBot` 或 messenger installation 解析出平台服务，然后调用 `sendDirectMessage`、`sendMessage`、`readMessages`、`editMessage`、`deleteMessage`、`reactToMessage`、`pinMessage`、`listChannels`、`createThread`、`replyToThread`、`createPoll` 等能力。这里说明 `src/server/services/bot/platforms/*/service.ts` 不只服务入站机器人，也支撑服务端主动操作外部平台消息。

## 推荐阅读顺序

第一步先读 `src/server/services/bot/platforms/types.ts`，理解 `PlatformClient`、`PlatformMessenger`、`ConnectionMode`、`FieldSchema`、`BotMessageAttachment` 等统一接口。这个文件定义了平台适配层和上层服务之间的契约。

第二步读 `src/server/services/bot/platforms/registry.ts`、`src/server/services/bot/platforms/index.ts`、`src/server/services/bot/platforms/const.ts`，建立“有哪些平台、各平台能力如何声明、默认配置如何合并”的整体地图。

第三步读 `src/server/services/bot/BotMessageRouter.ts` 和 `src/server/services/bot/AgentBridgeService.ts`，把入站事件到 Agent 执行的主链路串起来。读这两个文件时可以对照 `src/server/services/bot/buildBotContext.ts`、`src/server/services/bot/formatPrompt.ts`、`src/server/services/bot/dmPairingStore.ts`。

第四步读 `src/server/services/bot/BotCallbackService.ts`、`src/server/services/bot/replyTemplate.ts`、`src/server/services/bot/reactionState.ts`，理解 Agent 输出如何变成平台上的进度消息、最终回复、反应表情和线程标题。

第五步选择一个平台纵向阅读，例如 `src/server/services/bot/platforms/telegram` 或 `src/server/services/bot/platforms/slack`。优先看 `definition.ts`、`schema.ts`、`client.ts`、`service.ts`、`sendAttachments.ts`，再看对应测试。不要一开始横向扫所有平台，否则容易被平台差异淹没。

## 常见误区

不要把 `bot` 和 `messenger` 两个目录完全等同。`src/server/services/bot` 偏“Agent bot provider”和平台抽象；`src/server/services/messenger` 偏共享 Messenger bot、安装绑定、账号链接等体系。但二者有复用关系，尤其是 `AgentBridgeService`、`buildBotContext`、平台 client 类型和回复模板。

不要以为 `platforms/*/client.ts` 就是所有平台 API。很多平台会同时有 `client.ts`、`api.ts`、`service.ts`：`client.ts` 通常面向 Chat SDK 适配和事件解析，`api.ts` 面向底层 HTTP 调用，`service.ts` 面向 LobeHub 统一消息能力。

不要忽略 `platformThreadId` 的复合含义。`BotCallbackService` 会从 `platformThreadId.split(':')[0]` 推导平台，这意味着线程 ID 不只是外部平台的裸 ID，还携带了路由所需的前缀信息。

不要把 step 回调和 completion 回调混在一起。step 主要负责进度、typing、工具调用展示和反应状态；completion 才负责最终回复、清理活跃线程和标题总结。

不要认为所有平台能力一致。`supportsMessageEdit`、附件发送、reaction、typing、线程、poll、channel list 等能力都有平台差异，上层通常通过 `PlatformClient`、`PlatformMessenger` 和 registry 的能力声明做条件分支。

不要绕过 `agentBotProviderSettings.ts` 和 `platforms/*/schema.ts` 手写配置字段。凭据、设置项、默认值、前端表单和服务端校验之间存在约定，直接散落硬编码会破坏平台配置的一致性。
