# 目录：src/server/services/bot/platforms

## 它负责什么

`src/server/services/bot/platforms` 是服务端 bot 系统的“平台适配层”。它把 Discord、Telegram、Slack、Feishu/Lark、QQ、WeChat、Line 等不同即时通讯平台，统一包装成 LobeHub 内部可消费的 `PlatformDefinition`、`PlatformClient`、`PlatformMessenger` 接口。

从架构位置看，它位于 `src/server/services/bot` 下面，不直接承担 Agent 执行，也不负责数据库中的 bot 配置生命周期；它的职责更偏“平台差异收敛”：定义每个平台需要哪些凭证与设置、如何校验凭证、如何创建 Chat SDK adapter、如何从平台消息里取出线程 ID / 用户 ID / 附件 / locale，以及如何把 Agent 的回复、进度、reaction、附件发送回平台。

上层服务通过 `platformRegistry` 找到平台定义，再创建对应客户端。这样 `BotMessageRouter`、`AgentBridgeService`、`BotCallbackService` 可以主要依赖统一接口，而不是到处写平台分支。

## 直接子目录地图

`src/server/services/bot/platforms/discord` 是 Discord 适配。目录里有 `definition.ts`、`client.ts`、`service.ts`、`api.ts`、`schema.ts`、`sendAttachments.ts`，以及 `patch/`。其中 `patch/` 根据命名和测试文件推断用于处理 Discord Chat SDK 或平台协议的特殊兼容逻辑，例如 forwarded interactions、thread recovery。

`src/server/services/bot/platforms/feishu` 是飞书和 Lark 共享的适配区域。它有 `definitions/feishu.ts`、`definitions/lark.ts`、`definitions/shared.ts`、`definitions/schema.ts`，说明 Feishu 与 Lark 在同一套实现上分出两个平台注册定义。`gateway.ts`、`client.ts`、`service.ts`、`sendAttachments.ts` 处理连接、平台客户端和附件发送。

`src/server/services/bot/platforms/slack` 是 Slack 适配。它包含 `definition.ts`、`client.ts`、`service.ts`、`api.ts`、`gateway.ts`、`schema.ts`、`sendAttachments.ts`，另有 `markdownToMrkdwn.ts`，说明 Slack 的出站内容需要从通用 Markdown 转为 Slack 的 mrkdwn 表达。

`src/server/services/bot/platforms/telegram` 是 Telegram 适配。它包含 `definition.ts`、`client.ts`、`service.ts`、`api.ts`、`helpers.ts`、`schema.ts`、`sendAttachments.ts`，以及 `markdownToHTML.ts`，说明 Telegram 出站 Markdown 会转换成平台支持的 HTML 或兼容格式。

`src/server/services/bot/platforms/qq`、`src/server/services/bot/platforms/wechat`、`src/server/services/bot/platforms/line` 分别承载 QQ、微信、Line 的平台实现。它们都以 `definition.ts`、`client.ts`、`schema.ts`、`sendAttachments.ts`、`protocol-spec.md` 这类文件为主；QQ 和 WeChat 还有 `service.ts`，Line 当前从文件地图看没有 `service.ts`，根据当前片段推断其平台操作可能更多集中在 `client.ts` 或 Chat SDK adapter 配置里。

`src/server/services/bot/platforms/__tests__` 和各平台目录内的 `*.test.ts` 是平台适配层测试。它们覆盖注册表、常量策略、客户端行为、附件发送、Markdown 转换、gateway 和平台 service 等关键差异点。

## 关键入口

最核心入口是 `src/server/services/bot/platforms/index.ts`。它导出公共类型、工具函数、平台定义，并创建单例 `platformRegistry`。当前注册顺序包括 `discord`、`telegram`、`slack`、`feishu`、`lark`、`qq`、`wechat`、`line`。外部服务一般不直接 import 某个平台目录，而是从这里拿 `platformRegistry` 或相关类型。

`src/server/services/bot/platforms/registry.ts` 定义 `PlatformRegistry`。它维护平台 ID 到 `PlatformDefinition` 的映射，提供 `register()`、`getPlatform()`、`listPlatforms()`、`listSerializedPlatforms()`、`createClient()`、`validateCredentials()`。其中 `listSerializedPlatforms()` 会去掉 `clientFactory`，用于给前端消费平台元数据；`createClient()` 和 `validateCredentials()` 则是服务端运行时路径。

`src/server/services/bot/platforms/types.ts` 是平台契约中心。这里定义 `ConnectionMode`、`FieldSchema`、`BotMessageAttachment`、`MessengerContent`、`PlatformMessenger`、`UsageStats`、`PlatformClient` 等类型。理解这个文件，基本就能知道“新增一个平台必须向上层提供什么能力”。

`src/server/services/bot/platforms/const.ts` 是跨平台设置和策略工具的集中地。它包含表单字段工厂、bot 回复语言、locale 归一化、DM / group 访问策略、allowlist、watch keywords、reaction emoji 等公共规则。它不是某个平台的实现，而是所有平台共享的策略层。

## 主流程位置

入站主流程从 `src/server/services/bot/BotMessageRouter.ts` 开始。`BotMessageRouter.getWebhookHandler(platform, appId)` 根据 webhook URL 中的平台和 appId 找到平台定义；随后 `getOrCreateBot()` 按 `platform:applicationId` 缓存或加载 bot；加载时会从数据库读取 provider 配置、解密凭证、调用 `resolveBotProviderConfig()`，再通过平台注册定义创建 `PlatformClient` 和 Chat SDK bot。真正收到平台 webhook 后，它会交给 `chatBot.webhooks[platform]` 处理。

消息进入 Chat SDK 后，平台差异逐步被压到 `PlatformClient` 接口里：例如 `createAdapter()` 负责创建平台 adapter，`extractAuthorLocale()` 取作者语言，`extractFiles()` 处理附件，`extraGroupAllowlistChannels()` 处理平台线程 / 频道 ID 差异，`formatMarkdown()` 和 `formatReply()` 处理出站文本格式。

Agent 执行桥接在 `src/server/services/bot/AgentBridgeService.ts`。它是平台无关的 Agent Runtime 桥，负责把 Chat SDK message/thread 转为 Agent 执行请求，并处理 start、progress、stop、error、final reply 等反馈。这里会使用 `PlatformClient` 做 reaction、typing、message edit、thread name 更新等平台能力，但不关心具体 API 细节。

出站回调主流程在 `src/server/services/bot/BotCallbackService.ts`。队列或 hook 回调到达后，它根据 `platformThreadId` 解析 platform，通过 `platformRegistry` 创建 client，再调用 `client.getMessenger(platformThreadId)` 得到 `PlatformMessenger`。之后 completion / step 分支会通过 `createMessage()`、`editMessage()`、`replaceReaction()`、`triggerTyping()` 等统一接口，把 Agent 结果送回平台。

## 推荐阅读顺序

1. 先读 `src/server/services/bot/platforms/types.ts`，建立统一接口模型，重点看 `PlatformDefinition`、`PlatformClient`、`PlatformMessenger`、`FieldSchema`、`BotMessageAttachment`。
2. 再读 `src/server/services/bot/platforms/registry.ts` 和 `src/server/services/bot/platforms/index.ts`，理解平台注册、序列化、客户端创建和凭证校验如何被统一调度。
3. 接着读 `src/server/services/bot/platforms/const.ts`，掌握 DM / group 策略、allowlist、watch keywords、reply locale、reaction emoji 等跨平台规则。
4. 选择一个平台作为样本阅读。建议先看 `src/server/services/bot/platforms/telegram` 或 `src/server/services/bot/platforms/slack`，因为它们的 `definition/client/api/schema/sendAttachments/markdown` 分层比较清楚。
5. 再回到上层读 `src/server/services/bot/BotMessageRouter.ts`、`src/server/services/bot/AgentBridgeService.ts`、`src/server/services/bot/BotCallbackService.ts`，把平台入口和 Agent 主流程串起来。
6. 最后按需看 `protocol-spec.md` 和 `*.test.ts`。前者帮助理解平台协议约束，后者说明哪些行为被认为是稳定契约。

## 常见误区

不要把这个目录理解成“bot 业务主流程”。它主要是平台适配层；真正的消息路由、Agent 调用、回调处理分别在 `BotMessageRouter.ts`、`AgentBridgeService.ts`、`BotCallbackService.ts`。

不要认为每个平台文件结构完全一致。多数平台都有 `definition.ts`、`client.ts`、`schema.ts`、`sendAttachments.ts`，但是否有 `api.ts`、`service.ts`、`gateway.ts`、Markdown 转换文件取决于平台能力和连接方式。

不要跳过 `types.ts` 直接读某个平台实现。平台代码里很多方法的意义来自统一接口，例如 `getMessenger()`、`formatMarkdown()`、`extractFiles()`、`replaceReaction()`；先看契约会更容易理解为什么平台实现要拆成这些函数。

不要把 `platformThreadId` 当作普通 channel ID。根据当前片段推断，它包含平台前缀，并被 `BotCallbackService` 用 `platformThreadId.split(':')[0]` 解析平台；各平台还可能通过 `extractChatId()` 或 `extraGroupAllowlistChannels()` 处理线程、频道、父频道之间的差异。

不要忽略 `const.ts` 中的访问策略。DM、群聊、allowlist、watch keywords、reply locale 这些看似配置表单的问题，会直接影响 `BotMessageRouter` 是否处理一条入站消息。新增平台时只实现发送 API 不够，还要接入这些共享策略字段。
