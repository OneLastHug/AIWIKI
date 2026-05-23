# 目录：src/server/services/messenger

## 它负责什么

`src/server/services/messenger` 是 LobeHub 服务端的“系统级即时通讯机器人”集成层。它不负责普通用户自己配置的单个 Bot Provider，而是负责平台级 Messenger Bot，把 Slack、Telegram、Discord 等外部 IM 平台上的消息接入 LobeHub，再路由到已绑定的 LobeHub 用户和其选中的 Agent。

这个目录的核心职责可以概括为四件事：第一，接收 `/api/agent/messenger/...` 进入的 webhook 请求；第二，根据平台和安装信息解析出当前请求属于哪个 workspace、guild 或全局 bot；第三，把外部用户与 LobeHub 账号之间的绑定关系、当前 active agent、命令交互串起来；第四，通过已有 bot/agent 桥接能力把消息交给 Agent，并把回复发回 IM 平台。

从代码形态看，它是一个平台抽象层：公共路由逻辑集中在 `MessengerRouter.ts`，平台差异收敛在 `platforms/*/binder.ts`、`platforms/*/definition.ts`、`installations/*` 和少量 OAuth/webhook gate 中。这样 Slack 的 workspace OAuth、Telegram 的 singleton bot、Discord 的 websocket/interaction 差异不会散落到主路由里。

## 直接子目录地图

`src/server/services/messenger/installations` 负责“安装凭据解析”。这里定义 `MessengerInstallationStore` 和 `InstallationCredentials`，并按平台实现 `SlackInstallationStore`、`TelegramInstallationStore`、`DiscordInstallationStore`。Router 每次收到 webhook 后，会通过这里把原始请求解析成统一的安装凭据，例如 `slack:T0123` 或 `telegram:singleton`。它还包含 `messengerConnectionId`、`messengerConnectionIdForUser` 这类连接 ID 生成逻辑，用于后续 typing、gateway、回调路由等场景。

`src/server/services/messenger/oauth` 负责 OAuth 安装流程中的共享状态和平台 OAuth 细节。目前能看到 `stateStore.ts` 和 `slackOAuth.ts`：前者用于 install/callback 之间传递和校验 state，后者把 Slack 授权码交换结果规范化为统一的安装数据。根据 `platforms/types.ts` 的接口设计，Discord 也有对应 OAuth adapter 的扩展位置。

`src/server/services/messenger/platforms` 是平台注册和平台能力定义区。`registry.ts` 管理所有平台定义；`types.ts` 定义 `MessengerPlatformDefinition`、`MessengerPlatformOAuthAdapter`、`MessengerPlatformWebhookGate` 等抽象；`index.ts` 注册 `slack`、`telegram`、`discord`。每个平台目录下通常包含 `definition.ts` 和 `binder.ts`，有 OAuth 的平台还会有 `oauth.ts`，需要 webhook 预处理的平台还会有 `webhook.ts`。

`src/server/services/messenger/platforms/slack` 是 Slack 平台实现。它承担 workspace 级安装、签名校验、事件预处理、ephemeral 回复、App Home Messages tab 欢迎、交互按钮解析等平台细节。

`src/server/services/messenger/platforms/telegram` 是 Telegram 平台实现。它更接近全局 bot 模型，安装 key 使用 singleton 思路；命令多以普通文本消息形式进入；binder 负责 Telegram inline keyboard、callback_data、DM 文本发送和绑定提示。

`src/server/services/messenger/platforms/discord` 是 Discord 平台实现。它包含 binder、definition、oauth，并和 slash command、interaction acknowledgement、websocket/system bot 连接模式相关。根据当前片段推断，Discord 在 messenger 体系中既支持 OAuth 安装，也需要处理 Discord interaction 的特殊响应语义，依据是 `MessengerPlatformBinder` 中的 `interaction`、`extractActionFromEvent` 注释，以及 `MessengerRouter` 对 `extractDiscordInteractionContext` 的处理。

## 关键入口

最重要入口是 `src/server/services/messenger/MessengerRouter.ts`。它导出 `MessengerRouter`，并通过 `getWebhookHandler(platform)` 给外部 HTTP 层提供 webhook handler。外部路由位于邻近上下文 `src/server/agent-hono/index.ts`，其中 `/messenger/webhooks/:platform` 会进入 `messengerWebhook`，再调用 `getMessengerRouter()` 和 `getWebhookHandler()`。

`src/server/services/messenger/index.ts` 是包级导出入口。它导出 `getMessengerRouter`、`MessengerRouter`、`messengerPlatformRegistry`、各平台 Binder，以及 link token 相关函数。其他服务如果只需要使用 messenger 能力，通常应该从这个入口引入，而不是直接深入平台实现。

`src/server/services/messenger/platforms/index.ts` 是平台注册入口。它创建 singleton `messengerPlatformRegistry`，依次注册 `slack`、`telegram`、`discord`。新增平台时，这里是必须检查的位置之一。

`src/server/services/messenger/installations/index.ts` 是安装凭据 store 的统一入口。`getInstallationStore(platform)` 根据平台返回对应 store。它也是 `messengerConnectionIdForUser()` 的所在地，涉及 messenger-originated run 的连接路由，不只是安装解析工具。

`src/server/services/messenger/linkTokenStore.ts` 是账号绑定过程的重要入口。未绑定用户在 IM 中发消息时，binder 会触发绑定提示；验证页或绑定流程会使用这里的 token 发行、消费、查询能力，把外部 platform user 绑定到 LobeHub user。

## 主流程位置

Webhook 主流程在 `MessengerRouter.getWebhookHandler()`。整体顺序是：读取 raw body；平台 `webhookGate.preprocess()` 先做签名校验、challenge、卸载或 token revoked 等短路处理；通过 `getInstallationStore(definition.id)` 拿到安装 store；调用 `resolveByPayload()` 解析安装凭据；用 `getOrCreateBot()` 为该安装懒加载并缓存 Chat SDK bot；先让 binder 尝试处理 App Home 打开、按钮 callback 等 chat-sdk 不一定透出的事件；最后把重建后的 `Request` 交给 `chatBot.webhooks[platform]`。

Bot 加载主流程在 `MessengerRouter.loadBot()`。它通过 `messengerPlatformRegistry.createBinder(creds)` 创建平台 binder，再由 binder 创建底层 `PlatformClient`，随后用 `client.createAdapter()` 构造 Chat SDK `Chat` 实例。这里还会注册消息 handler、初始化 chat bot，并把共享命令注册到支持 native slash command 的平台。

消息分发主流程在 `MessengerRouter.registerHandlers()`。进入消息后先过滤 bot 自己的消息，再解析 sender、chatId、DM 或 channel mention，查 `MessengerAccountLinkModel.findByPlatformUser()` 判断这个平台用户是否已绑定 LobeHub 账号。若文本是 `/start`、`/agents`、`/new`、`/stop`、`/feedback` 等命令，则进入统一命令 registry；若未绑定，则调用 `binder.handleUnlinkedMessage()` 发送绑定提示；若已绑定但没有 active agent，则提示选择 agent；若一切就绪，则通过 `dispatchToAgent()` 把消息交给 Agent。

安装/OAuth 主流程不在本目录的 HTTP handler 中，但服务能力在这里提供。邻近入口 `src/server/agent-hono/handlers/messengerInstall.ts` 通过 `messengerPlatformRegistry.getPlatform(platform).oauth` 构造授权地址并发 state；`src/server/agent-hono/handlers/messengerOAuthCallback.ts` 消费 state、调用平台 `exchangeCode()`，再写入 `messenger_installations`。本目录的 `oauth/*` 和 `platforms/*/oauth.ts` 是这条链路的核心实现位置。

## 推荐阅读顺序

建议先读 `src/server/services/messenger/types.ts`，理解 `MessengerPlatformBinder` 提供哪些平台能力：创建 client、发送 DM、私密回复、未绑定提示、agent picker、callback action、link success 通知等。这个接口决定了平台差异怎样被主路由隐藏。

第二步读 `src/server/services/messenger/platforms/types.ts` 和 `src/server/services/messenger/platforms/registry.ts`，理解一个平台定义包含 `connectionMode`、`createBinder`、`oauth`、`webhookGate` 这些部分，以及 registry 如何统一创建 binder 和序列化平台信息。

第三步读 `src/server/services/messenger/installations/types.ts` 和 `src/server/services/messenger/installations/index.ts`，弄清楚 `installationKey`、`tenantId`、`botToken`、`signingSecret` 的含义。尤其要注意 singleton 平台和 per-tenant 平台的差别。

第四步读 `src/server/services/messenger/MessengerRouter.ts`，重点看 `getWebhookHandler()`、`loadBot()`、`registerHandlers()`、命令 registry 和 agent dispatch 相关方法。不要一开始陷入所有测试和平台细节，否则容易看不清主线。

第五步按平台选择一个实现读，例如 Slack 读 `platforms/slack/definition.ts`、`platforms/slack/binder.ts`、`platforms/slack/webhook.ts`、`installations/slack.ts`；Telegram 读 `platforms/telegram/binder.ts`、`installations/telegram.ts`；Discord 读 `platforms/discord/*`。

最后再看测试文件，例如 `MessengerRouter.test.ts`、`platforms/*/*.test.ts`、`installations/*.test.ts`。这些测试覆盖了很多边界行为，适合用来验证你对流程的理解。

## 常见误区

一个误区是把 messenger 和普通 bot provider 混为一谈。普通 bot provider 更偏用户或 agent 自己配置的 bot 通道；这里的 messenger 是系统级共享入口，安装信息在 `messenger_installations`，账号绑定在 `messenger_account_links`，并通过 `messengerInstallationKey` 参与后续回调和凭据解析。

第二个误区是认为所有平台都有相同安装模型。Slack 是典型 per-tenant 安装，`installationKey` 会带 workspace 或 enterprise 信息；Telegram 是 singleton 全局 bot；Discord 根据当前代码同时涉及 singleton websocket 和 OAuth/guild 安装语义。阅读时要以 `InstallationCredentials` 和 `MessengerPlatformDefinition.connectionMode` 为准，不要硬编码平台名推断行为。

第三个误区是忽略 raw body。`getWebhookHandler()` 一开始读取原始 body，是因为 Slack 签名校验依赖原始字节；后续又通过 `reconstructRequest()` 重建请求交给 binder 或 chat-sdk。随意提前 JSON parse 或丢弃 body，会破坏签名校验和下游 webhook handler。

第四个误区是把按钮回调都交给 Chat SDK。代码里明确保留了两条路径：有些平台通过 `extractCallbackAction(req)` 在 webhook 层从 raw request 里截获；有些平台通过 `extractActionFromEvent()` 从 chat-sdk action event 里转换。平台 binder 决定具体路径，主路由只处理统一的 `InboundCallbackAction`。

第五个误区是忽视 channel 场景的隐私。Slack channel mention 中，未绑定提示、agent 选择、命令回复通常要走 ephemeral 或 private reply，不能像 DM 一样直接公开发送。`MessengerRouter` 中围绕 `isChannelMention`、`replyEphemeral`、`replyPrivately` 的分支就是为这个问题服务的。

第六个误区是只看平台 binder 而不看 account link。真正决定消息发给哪个 LobeHub 用户和哪个 agent 的，是 `MessengerAccountLinkModel.findByPlatformUser()` 查到的绑定行和其中的 `activeAgentId`。binder 只负责平台通信和 UI 表达，不拥有业务路由决策。
