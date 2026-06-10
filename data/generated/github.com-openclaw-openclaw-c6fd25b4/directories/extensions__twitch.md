# 目录：extensions/twitch

## 它负责什么

`extensions/twitch` 是 OpenClaw 的 Twitch channel plugin，负责把 OpenClaw 的通道抽象接到 Twitch chat。它不是核心通道实现的一部分，而是一个 bundled plugin：通过 `openclaw.plugin.json`、`package.json` 的 `openclaw` 元数据，以及 `index.ts` 暴露给宿主的 channel entry 参与发现、安装、启动和运行。

从当前片段看，这个目录覆盖了 Twitch 集成的几类职责：插件注册、运行时注入、配置解析、账号选择、CLI setup wizard、Twitch API/IRC 客户端管理、消息接收、出站发送、消息动作、权限控制、状态探测和测试。它的外部依赖主要是 `@twurple/api`、`@twurple/auth`、`@twurple/chat` 和 `zod`，说明 Twitch 平台交互走 Twurple 生态，配置校验走 schema 化路径。

这个插件的 channel id 是 `twitch`，面向的是群聊式 Twitch Chat，manifest 中声明了 `channels: ["twitch"]`，并声明环境变量 `OPENCLAW_TWITCH_ACCESS_TOKEN` 可作为 Twitch channel credential 来源之一。

## 直接子目录地图

`extensions/twitch` 的目录层级很浅，直接子目录只有两个：

`extensions/twitch/src` 是核心实现目录。这里放 Twitch plugin 的业务逻辑，包括 `plugin.ts` 组合 channel plugin，各类 adapter、配置、状态、token、resolver、monitor、send/outbound、access control 和 Twitch client 封装。学习这个目录时应按“入口组合 -> 配置/账号 -> 运行链路 -> 平台边界”的顺序看，而不是按文件名逐个扫。

`extensions/twitch/src/utils` 是小型工具目录，目前从文件名看包含 `markdown.ts` 和 `twitch.ts`。它承载格式化、Twitch 字符串/token 规范化、账号配置判断等低层辅助逻辑。根据当前片段推断，`utils/twitch.ts` 至少被 `config.ts`、`resolver.ts`、`plugin.ts` 使用，用于 token normalization 和账号 configured 状态判断。

`extensions/twitch/test` 是测试环境支持目录，目前可见 `test/setup.ts`。它不是主流程入口，而是 Vitest 或插件测试的共享 setup。

根目录文件承担插件边界角色：`index.ts`、`api.ts`、`runtime-api.ts`、`channel-plugin-api.ts`、`setup-entry.ts`、`setup-plugin-api.ts` 是对宿主暴露的窄入口；`openclaw.plugin.json` 和 `package.json` 是发现、安装和兼容性元数据；`README.md` 是人工说明；`npm-shrinkwrap.json` 锁定插件发布依赖。

## 关键入口

最顶层入口是 `extensions/twitch/index.ts`。它调用 `defineBundledChannelEntry`，声明插件 id、名称、描述、`importMetaUrl`，并把宿主需要加载的两个面拆开：`plugin` 指向 `./channel-plugin-api.js` 的 `twitchPlugin`，`runtime` 指向 `./api.js` 的 `setTwitchRuntime`。这体现了 bundled channel plugin 的标准入口形态：宿主先识别 entry，再按需加载插件对象和运行时注入函数。

`extensions/twitch/channel-plugin-api.ts` 是 channel plugin 的窄导出面，只导出 `twitchPlugin`。真正的组合逻辑在 `extensions/twitch/src/plugin.ts`。这里用 `createChatChannelPlugin` 把 base metadata、setup、capabilities、message adapter、config schema、actions、resolver、status、gateway start/stop 统一装配成 `ChannelPlugin`。

`extensions/twitch/api.ts` 和 `extensions/twitch/runtime-api.ts` 是运行时边界。`api.ts` 主要导出 `setTwitchRuntime`，`runtime-api.ts` 从 `openclaw/plugin-sdk/*` 重新导出 channel、runtime、setup 相关类型，避免插件内部直接依赖核心私有路径。`extensions/twitch/src/runtime.ts` 用 `createPluginRuntimeStore` 保存宿主注入的 `PluginRuntime`，并给出 `getTwitchRuntime` / `setTwitchRuntime`。

`extensions/twitch/setup-entry.ts` 和 `extensions/twitch/setup-plugin-api.ts` 是 setup 专用入口。它们避免 setup 阶段拉入完整 channel plugin surface，最终导向 `extensions/twitch/src/setup-surface.ts` 中的 `twitchSetupPlugin`、`twitchSetupAdapter`、`twitchSetupWizard` 等 setup 能力。

## 主流程位置

插件装配主流程在 `extensions/twitch/src/plugin.ts`。这是一张总控地图：`base.meta` 定义 Twitch 在 OpenClaw 中显示和选择时的元信息；`capabilities.chatTypes` 声明只支持 `group`；`message` 接 `twitchMessageAdapter`；`outbound` 接 `twitchOutbound`；`actions` 接 `twitchMessageActions`；`resolver.resolveTargets` 调 `resolveTwitchTargets`；`status` 用 SDK 的 `createComputedAccountStatusAdapter` 加上 `probeTwitch` 和 `collectTwitchStatusIssues`；`gateway.startAccount` / `stopAccount` 控制真实连接生命周期。

配置和账号解析主流程在 `extensions/twitch/src/config.ts`、`extensions/twitch/src/config-schema.ts`。`TwitchConfigSchema` 支持两种形态：单账号的顶层 `username`、`accessToken`、`clientId`、`channel`，以及多账号的 `accounts` map。`getAccountConfig`、`listAccountIds`、`resolveDefaultTwitchAccountId`、`resolveTwitchAccountContext` 负责把 OpenClaw 的全局 config 规整成 Twitch account context。这里尤其要注意 `default` 账号：顶层配置会形成 implicit default account，并且在 default 场景中优先于 `accounts.default` 的同名字段。

setup 主流程在 `extensions/twitch/src/setup-surface.ts`。它负责交互式收集 `username`、`accessToken`、`clientId`、`channel`，可选收集 `clientSecret` 和 `refreshToken`，并通过 `setTwitchAccount` 写回 `channels.twitch.accounts[accountId]`。根据当前片段推断，环境变量 token 会在 setup 时被优先提示或复用，依据是 `configureWithEnvToken`、`promptToken` 以及 manifest 的 `channelEnvVars`。

收消息主流程从 `gateway.startAccount` 开始：`plugin.ts` 设置运行状态，然后通过 `runStoppablePassiveMonitor` 懒加载 `extensions/twitch/src/monitor.ts` 的 `monitorTwitchProvider`。注释说明这里必须让 `startAccount` 保持 pending，直到 abort 触发，否则 supervisor 会把已完成任务视为 channel 退出并触发重启循环。真正连接 Twitch chat、监听消息、进入回复管线的位置应在 `monitor.ts`，其底层客户端管理从文件名看分布在 `twitch-client.ts`、`client-manager-registry.ts`。

发消息主流程分布在 `extensions/twitch/src/outbound.ts` 和 `extensions/twitch/src/send.ts`。`plugin.ts` 中的 `twitchOutbound` 是宿主看到的 outbound adapter，实际发送动作根据命名应落到 `send.ts`，并复用 Twitch client 或账号配置。消息动作和访问控制分别在 `actions.ts`、`access-control.ts`，用于决定收到的 Twitch chat message 是否能触发 OpenClaw 响应，以及如何处理 pairing、allowlist、role、mention 等规则。

状态与探测主流程在 `extensions/twitch/src/status.ts`、`extensions/twitch/src/probe.ts`、`extensions/twitch/src/token.ts`。`plugin.ts` 把 `probeTwitch` 接入 SDK status adapter，并通过 `resolveTwitchAccountContext`、`resolveTwitchToken`、`isAccountConfigured` 判断账号是否具备运行条件。`resolver.ts` 则是另一条平台 API 边界：它使用 `ApiClient` 和 `StaticAuthProvider` 把 Twitch username 或 numeric user id 解析为 OpenClaw channel target。

## 推荐阅读顺序

1. 先读 `extensions/twitch/openclaw.plugin.json` 和 `extensions/twitch/package.json`，确认 plugin id、channel 元数据、setup entry、依赖和发布形态。
2. 再读 `extensions/twitch/index.ts`、`extensions/twitch/channel-plugin-api.ts`、`extensions/twitch/api.ts`、`extensions/twitch/setup-entry.ts`，理解宿主如何发现和加载这个插件。
3. 然后读 `extensions/twitch/src/plugin.ts`，把 setup、message、outbound、resolver、status、gateway 的组合关系画成一张主流程图。
4. 接着读 `extensions/twitch/src/config-schema.ts` 和 `extensions/twitch/src/config.ts`，理解单账号、多账号、默认账号、环境 token 与 configured 状态。
5. 再读运行链路相关文件：`extensions/twitch/src/monitor.ts`、`extensions/twitch/src/twitch-client.ts`、`extensions/twitch/src/client-manager-registry.ts`、`extensions/twitch/src/outbound.ts`、`extensions/twitch/src/send.ts`。
6. 最后读 `extensions/twitch/src/access-control.ts`、`extensions/twitch/src/actions.ts`、`extensions/twitch/src/status.ts`、`extensions/twitch/src/probe.ts`、`extensions/twitch/src/resolver.ts` 和对应 `*.test.ts`，用测试反推边界条件。

## 常见误区

不要把 `extensions/twitch` 当成核心 channel 框架。它只是 Twitch 这个 channel 的 bundled plugin，生产代码应通过 `openclaw/plugin-sdk/*` 和本地 barrel 工作，不能直接依赖核心内部实现。

不要只看 `openclaw.plugin.json` 的空 `configSchema.properties` 就认为 Twitch 没有配置。真正的 channel 配置 schema 在 `extensions/twitch/src/config-schema.ts`，并通过 `plugin.ts` 的 `buildChannelConfigSchema(TwitchConfigSchema)` 接入。

不要混淆 `channel-plugin-api.ts` 和 `setup-plugin-api.ts`。前者导出完整 channel runtime plugin，后者只给 setup 流程使用；这种拆分是为了避免 setup 阶段加载完整运行时 surface。

不要把 Twitch username 当成稳定权限标识。`types.ts` 中 `allowFrom` 注释强调使用 Twitch user id 更安全，`resolver.ts` 也专门把用户名解析为 user id。

不要忽略 `gateway.startAccount` 的生命周期细节。这里的 passive monitor 必须随 abort signal 运行并保持 pending，否则 supervisor 会误判 channel 退出。

不要把单账号和多账号配置混在一起理解。当前 schema 明确支持 simplified single-account 和 `accounts` multi-account 两种模式，而 `config.ts` 对 implicit `default`、`defaultAccount`、显式 accounts 的优先级有专门逻辑。
