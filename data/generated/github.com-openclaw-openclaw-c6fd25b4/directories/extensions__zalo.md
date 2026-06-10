# 目录：extensions/zalo

## 它负责什么

`extensions/zalo` 是 OpenClaw 的 Zalo 通道插件，面向 Zalo Bot API，把 Zalo 私聊和群聊接入 OpenClaw 的通道体系。它的角色不是实现核心调度或模型能力，而是把“Zalo 上收到的消息”转换成 OpenClaw 能处理的入站 envelope，再把 OpenClaw 生成的回复通过 Zalo Bot API 发回目标会话。

从插件边界看，它遵循 `extensions/AGENTS.md` 的约束：生产代码主要通过 `openclaw/plugin-sdk/*` 和本插件自己的公开 barrel 交互，不直接依赖核心内部路径。根部的 `openclaw.plugin.json` 和 `package.json` 提供静态发现信息，包括插件 id `zalo`、通道名、环境变量 `ZALO_BOT_TOKEN`、`ZALO_WEBHOOK_SECRET`、安装元数据、setup 入口和 docsPath。真正的运行时代码集中在 `extensions/zalo/src`。

这个目录覆盖的能力包括：账号和 token 解析、通道配置 schema、setup/onboarding、allowlist 与 DM/group 安全策略、Zalo API 请求封装、轮询或 webhook 两种入站模式、出站文本和图片发送、媒体回复托管、pairing approval 通知、状态探测和测试辅助。

## 直接子目录地图

`extensions/zalo` 只有两个直接子目录层级需要先记住。

`extensions/zalo/src` 是主体实现目录。这里放通道插件定义、运行时启动、Zalo API 封装、消息监控、配置解析、账号解析、安全策略、setup 表面、发送逻辑、webhook 处理、媒体出站辅助以及大量 colocated 测试。它是学习这个插件主流程时最重要的目录。

`extensions/zalo/src/test-support` 是测试支持目录。根据当前片段推断，它不属于插件运行时主路径，而是为 `src/*.test.ts` 或根部测试提供 fixture、mock、helper 一类支撑；依据是它位于 `src` 下且目录名明确为 `test-support`，同时插件入口没有从该目录导出运行时能力。

根目录本身也承担“入口层”职责，并不是空壳。`index.ts`、`setup-entry.ts`、`channel-plugin-api.ts`、`runtime-api.ts`、`api.ts`、`contract-api.ts`、`secret-contract-api.ts`、`setup-api.ts` 等文件负责把 `src` 内部实现包装成插件 SDK 可发现、可加载、可测试的公开面。

## 关键入口

`extensions/zalo/index.ts` 是插件主发现入口。它调用 `defineBundledChannelEntry`，声明 id 为 `zalo`，并把插件实现、secret contract、runtime setter 分别指向 `./channel-plugin-api.js`、`./secret-contract-api.js`、`./runtime-api.js`。也就是说，核心发现插件时先看到的是这个文件，而不是直接进入 `src/monitor.ts`。

`extensions/zalo/setup-entry.ts` 是 setup 流程入口，使用 `defineBundledChannelSetupEntry` 暴露 setup 所需的插件和 secrets。安装、配置引导或 onboarding 相关流程会从这里接触 Zalo 插件。

`extensions/zalo/channel-plugin-api.ts` 是通道插件公开 barrel，直接导出 `zaloPlugin`，实际实现来自 `extensions/zalo/src/channel.ts`。外部需要拿到通道定义时，不应该深挖 `src/channel.ts`，而是走这个入口。

`extensions/zalo/runtime-api.ts` 是运行时公开 barrel，重新导出 `extensions/zalo/src/runtime-api.ts` 中的 SDK 类型、工具和 `setZaloRuntime` 等运行时相关能力。它还把一组 plugin-sdk 能力重新暴露给本插件运行时边界使用，避免运行时代码和核心内部路径耦合。

`extensions/zalo/openclaw.plugin.json` 和 `extensions/zalo/package.json` 是静态元数据入口。前者描述插件 id、启动策略、通道环境变量和配置 schema；后者描述 npm 包、OpenClaw plugin metadata、setupEntry、channel 展示信息、安装策略、兼容版本和依赖。理解插件如何被发现和安装，要先看这两个文件。

## 主流程位置

通道定义主流程在 `extensions/zalo/src/channel.ts`。这里构造 `zaloPlugin`，核心调用是 `createChatChannelPlugin`。该文件把 metadata、setup、capabilities、reload 配置、账号配置解析、approval capability、secrets、群策略、actions、messaging、directory、status、gateway、message、security、pairing、threading、outbound 这些面统一挂到 ChannelPlugin 上。它是“Zalo 插件向 OpenClaw 声明自己能做什么”的中心。

运行时启动主流程在 `extensions/zalo/src/channel.runtime.ts`。`startZaloGatewayAccount` 会读取账号 token，判断模式是 `webhook` 还是 `polling`，先通过 `probeZalo` 做启动前探测，然后创建 account status sink，最后动态导入 `monitorZaloProvider` 并把 token、account、config、runtime、abortSignal、webhook 配置、proxy fetcher 和状态回写函数传进去。这个文件连接了插件定义和真正的消息循环。

入站监听和消息处理主流程在 `extensions/zalo/src/monitor.ts`。它包含 `monitorZaloProvider`、`startPollingLoop`、`processUpdate`、`handleZaloWebhookRequest` 等关键位置。根据当前片段，`monitorZaloProvider` 是运行时入口；轮询模式通过 `getUpdates` 取更新并交给 `processUpdate`；webhook 模式通过 `handleZaloWebhookRequest` 和 `monitor.webhook.ts` 的内部处理交给同一个 `processUpdate`。因此 `processUpdate` 是入站消息进入 OpenClaw 前的核心收敛点。

Zalo API 封装在 `extensions/zalo/src/api.ts`。`monitor.ts` 和 `send.ts` 都依赖这里的 `getUpdates`、`sendMessage`、`sendPhoto`、`setWebhook`、`deleteWebhook`、`getWebhookInfo`、`sendChatAction` 等函数。学习网络请求、错误模型和 Bot API payload 时，应读这里，而不是从业务流程里猜 API 合约。

出站发送主流程在 `extensions/zalo/src/send.ts`。`sendMessageZalo` 负责解析发送上下文、校验 token 和 chat id，并在有 `mediaUrl` 时转到 `sendPhotoZalo`。`sendPhotoZalo` 负责图片 URL 和 caption 发送。`src/channel.ts` 中的 `zaloMessageAdapter`、`zaloRawSendResultAdapter` 以及 outbound `sendPayload` 最终都会落到 `channel.runtime.ts` 的 `sendZaloText`，再进入 `send.ts`。

配置和账号解析主流程分布在 `extensions/zalo/src/config-schema.ts`、`extensions/zalo/src/accounts.ts`、`extensions/zalo/src/token.ts`。`channel.ts` 使用 `ZaloConfigSchema`、`resolveZaloAccount`、`listZaloAccountIds`、`resolveDefaultZaloAccountId` 把 `channels.zalo` 配置转成可运行的 account。README 中示例字段如 `botToken`、`dmPolicy`、`proxy`、`webhookUrl`、`webhookSecret`、`webhookPath` 的真实解析逻辑，应以这些文件为准。

setup 主流程在 `extensions/zalo/src/setup-core.ts` 和 `extensions/zalo/src/setup-surface.ts`。`channel.ts` 通过 `zaloSetupAdapter` 和懒加载的 `zaloSetupWizard` 挂入通道定义；根部 `setup-entry.ts` 则让 setup 入口在插件安装和引导阶段可被发现。

## 推荐阅读顺序

1. 先读 `extensions/zalo/openclaw.plugin.json` 和 `extensions/zalo/package.json`，建立插件 id、通道元数据、安装方式、setupEntry、channel docsPath、兼容版本这些静态概念。
2. 再读 `extensions/zalo/index.ts`、`extensions/zalo/setup-entry.ts`、`extensions/zalo/channel-plugin-api.ts`，理解插件如何被 OpenClaw 发现，以及公开入口如何跳到 `src` 内部。
3. 接着读 `extensions/zalo/src/channel.ts`，这是总装配文件。不要一开始钻进每个 helper，先把 `createChatChannelPlugin` 的各个 section 画成地图。
4. 然后读 `extensions/zalo/src/channel.runtime.ts`，看 gateway account 如何启动、如何 probe、如何选择 webhook/polling、如何进入 `monitorZaloProvider`。
5. 再读 `extensions/zalo/src/monitor.ts`、`extensions/zalo/src/monitor.webhook.ts`，重点找 `monitorZaloProvider`、`startPollingLoop`、`processUpdate`、`handleZaloWebhookRequest`，这几处决定入站消息生命周期。
6. 最后按问题补读：出站看 `extensions/zalo/src/send.ts` 和 `extensions/zalo/src/outbound-media.ts`；配置看 `extensions/zalo/src/config-schema.ts`、`extensions/zalo/src/accounts.ts`、`extensions/zalo/src/token.ts`；setup 看 `extensions/zalo/src/setup-core.ts`、`extensions/zalo/src/setup-surface.ts`；安全策略看 `extensions/zalo/src/group-access.ts`、`extensions/zalo/src/approval-auth.ts`、`extensions/zalo/src/status-issues.ts`。

## 常见误区

不要把 `extensions/zalo/src/monitor.ts` 当成插件入口。它是运行时消息循环核心，但插件发现入口是 `extensions/zalo/index.ts`，通道装配入口是 `extensions/zalo/src/channel.ts`，gateway 启动才会经 `extensions/zalo/src/channel.runtime.ts` 进入 monitor。

不要忽略根目录的 `*-api.ts` 文件。它们看起来像薄封装，但在插件边界里很重要：核心或测试应通过这些公开面访问插件能力，而不是随意 deep import `src/**`。

不要把 polling 和 webhook 看成两套完全独立的业务逻辑。根据当前片段，二者入口不同，但都会收敛到 `processUpdate` 处理更新；区别主要在获取 update 的方式、webhook route 注册和 webhook secret/path 处理。

不要把 `allowFrom` 只理解成私聊白名单。`src/channel.ts` 里同时处理 DM policy、group policy、`groupAllowFrom`、mention-gated 行为和安全警告。群聊默认需要 mention，开放群策略还会触发 warning 收集。

不要直接按 README 示例推断完整配置契约。README 只是使用说明；真正的 schema、默认值、多账号结构、token 来源和兼容处理要看 `src/config-schema.ts`、`src/accounts.ts`、`src/token.ts`、`src/secret-contract.ts`。

不要认为发送文本和媒体是两条无关路径。`sendMessageZalo` 在存在 `mediaUrl` 时会转入 `sendPhotoZalo`，而 `src/channel.ts` 的 outbound 还会通过 `sendPayloadWithChunkedTextAndMedia` 和 `chunkTextForOutbound` 处理长文本、媒体和空结果。

不要把 `src/test-support` 当运行时代码入口。它的命名和位置都表明它服务测试；运行时入口链路中没有看到它参与插件发现、启动、收发或 setup。
