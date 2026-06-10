# 目录：extensions/nostr

## 它负责什么

`extensions/nostr` 是 OpenClaw 的 Nostr channel plugin，主要把 OpenClaw 的通道抽象接到 Nostr relay 网络上，支持通过 NIP-04 encrypted DMs 收发文本消息。它属于 `extensions/` 下的 bundled plugin，但边界上按第三方插件对待：生产代码主要通过 `openclaw/plugin-sdk/*` 和本插件自己的 barrel 文件对接核心能力，不直接依赖 core 内部实现。

从职责看，这个目录覆盖四类事情：插件发现与注册、通道配置与 setup、Nostr 网络收发循环、Nostr profile 与状态管理。插件元数据在 `package.json` 的 `openclaw` 字段和 `openclaw.plugin.json` 中声明；真正的 channel 能力由 `src/channel.ts` 组合出来；运行时 relay 连接、加密 DM、去重、指标、断路器等底层逻辑集中在 `src/nostr-bus.ts`；OpenClaw gateway 启动账号、处理 inbound DM、发送 outbound DM 的桥接在 `src/gateway.ts`。

这个插件目前偏“直接私信通道”：`capabilities.chatTypes` 是 `direct`，`media` 为 `false`。也就是说，它不是一个完整 Nostr 客户端，而是把 Nostr pubkey/relay/DM policy/profile 这些能力封装成 OpenClaw 的 channel surface。

## 直接子目录地图

`src/` 是主体实现目录。它包含通道插件定义、配置 schema、账号解析、setup 适配、gateway 桥接、Nostr bus、profile 发布、HTTP profile route、状态持久化、seen tracker、metrics，以及对应测试。这里不是按“领域子目录”拆分，而是平铺成一组边界清晰的模块，所以阅读时应按主流程找入口，不要从文件名列表逐个扫。

`test/` 是测试辅助目录，目前可见的是 `test/setup.ts`，用于测试环境准备。大量实际测试文件 colocated 在 `src/` 下，例如 `src/channel.test.ts`、`src/nostr-bus.test.ts`、`src/nostr-profile.test.ts` 等。

根目录文件是插件对外表面和包元数据。`index.ts` 是 bundled channel entry；`api.ts`、`runtime-api.ts`、`channel-plugin-api.ts`、`setup-api.ts`、`setup-plugin-api.ts`、`test-api.ts` 是不同场景的导出面；`setup-entry.ts` 是 setup entry；`package.json`、`openclaw.plugin.json`、`npm-shrinkwrap.json`、`tsconfig.json` 负责包、发现、依赖锁定和编译配置；`README.md` 是面向使用者的说明入口。

## 关键入口

最外层入口是 `extensions/nostr/index.ts`。它调用 `defineBundledChannelEntry` 声明 `id: "nostr"`、名称、描述、插件实现位置和 runtime 注入位置。这里还注册了 `/api/channels/nostr` 前缀的 gateway HTTP route，用于 Nostr profile 相关接口。注意这个文件本身保持很薄，主要通过 `loadBundledEntryExportSync` 去加载 `api.ts` 中暴露的实现。

`extensions/nostr/api.ts` 是主 runtime barrel。它导出 `nostrPlugin`、`createNostrProfileHttpHandler`、`getNostrRuntime`、`setNostrRuntime`、`resolveNostrAccount` 等核心能力。需要理解插件向核心暴露了什么，先看这里比直接钻进 `src/` 更有效。

`extensions/nostr/src/channel.ts` 是 channel plugin 的中心装配点。它通过 `createChatChannelPlugin` 把 meta、capabilities、reload、configSchema、setup、setupWizard、config、messaging、message、status、gateway、pairing、security、outbound 等能力拼成 `nostrPlugin`。读懂这个文件，就能知道 Nostr 通道在 OpenClaw 眼里“长什么样”。

`extensions/nostr/setup-entry.ts` 和 `extensions/nostr/src/channel.setup.ts` 是 setup 流程入口。前者定义 bundled setup entry，后者提供轻量 setup plugin，用于配置状态、私钥校验、默认 relay 展示和 setup wizard 代理。

## 主流程位置

配置解析主线在 `src/config-schema.ts` 和 `src/types.ts`。`NostrConfigSchema` 定义 `channels.nostr` 下的字段，包括 `privateKey`、`relays`、`dmPolicy`、`allowFrom`、`profile`、`markdown` 等；`resolveNostrAccount` 从 OpenClaw config 中解析账号，计算 `configured`、`publicKey`、`relays`、`profile` 等运行时需要的账号快照。

启动主线从 `src/channel.ts` 的 `gateway.startAccount` 指到 `src/gateway.ts` 的 `startNostrGatewayAccount`。这里会设置状态，检查私钥，创建 pairing controller，解析 inbound access policy，然后调用 `startNostrBus` 建立 Nostr relay 连接。active bus 也由 `src/gateway.ts` 维护，供发送消息和 profile 发布状态查询使用。

入站消息主线大致是：`src/nostr-bus.ts` 从 relay 收到 DM 事件，验签、预解密 guard、NIP-04 decrypt、去重和策略检查后，回调 `src/gateway.ts` 的 `onMessage`；`src/gateway.ts` 再调用 `dispatchInboundDirectDmWithRuntime` 把消息转成 OpenClaw 的 direct DM 会话输入，并把回复通过 Nostr `reply` 函数发回。

出站消息主线在 `src/channel.ts`、`src/gateway.ts` 和 `src/session-route.ts` 之间。`src/session-route.ts` 的 `resolveNostrOutboundSessionRoute` 把 `nostr:` target 或 pubkey 解析成 direct peer route；`nostrOutboundAdapter` 负责把 OpenClaw outbound text 交给对应账号的 active bus；底层发送则落到 `src/nostr-bus.ts` 的 `sendDm`，完成加密、事件签名和 relay 发布。

profile 主线分两部分：配置与 HTTP handler 在 `src/nostr-profile-http.ts` 及 `index.ts` 注册的 route；真正发布 kind:0 profile 的能力在 `src/nostr-profile.ts`，并通过 `src/channel.ts` 的 `publishNostrProfile` 调到 active bus。profile schema 本身在 `src/config-schema.ts`，并限制 picture、banner、website 等 URL 必须是 `https`。

## 推荐阅读顺序

1. 先读 `extensions/nostr/package.json` 和 `extensions/nostr/openclaw.plugin.json`，了解插件 id、channel metadata、安装信息、环境变量和发现方式。
2. 再读 `extensions/nostr/index.ts`、`extensions/nostr/api.ts`，建立“核心如何加载这个插件、插件暴露什么”的外层地图。
3. 接着读 `extensions/nostr/src/channel.ts`，这是最重要的总装文件，能串起配置、setup、状态、消息、gateway、安全策略和 outbound。
4. 然后读 `extensions/nostr/src/config-schema.ts`、`extensions/nostr/src/types.ts`，理解配置数据如何变成 `ResolvedNostrAccount`。
5. 再读 `extensions/nostr/src/gateway.ts`，看 OpenClaw channel runtime 和 Nostr bus 之间如何互相调用。
6. 最后读 `extensions/nostr/src/nostr-bus.ts`，深入 Nostr relay、NIP-04 加密 DM、去重、状态持久化、metrics、断路器等底层细节。profile 相关需求再补读 `src/nostr-profile.ts`、`src/nostr-profile-http.ts`。

## 常见误区

不要把 `extensions/nostr` 当成普通内部模块。它虽然在仓库内，但遵循 plugin boundary，核心或测试如需使用能力，应通过 `api.ts` 这类公开 barrel，而不是深 import `src/**` 私有实现。

不要误以为 `openclaw.plugin.json` 承载完整 channel 配置 schema。它只提供插件发现和静态元数据；真实的 `channels.nostr` 配置校验在 `src/config-schema.ts`，并被 `src/channel.ts` 通过 `buildChannelConfigSchema` 接入 channel plugin。

不要把 `src/nostr-bus.ts` 看成 OpenClaw 会话层。它更接近 Nostr 网络适配层，负责 relay 连接、事件处理、加密解密、发送和状态；OpenClaw 的 inbound session dispatch、pairing、access policy 对接主要在 `src/gateway.ts`。

不要认为 Nostr 支持群聊或媒体。根据当前片段，插件能力明确是 direct chat，`media: false`，目标解析也围绕 `npub`、hex pubkey 和 `nostr:` 前缀展开。

不要忽略 setup 与 runtime 的分离。`src/channel.setup.ts` 提供 setup 场景下的轻量能力，避免 setup 流程加载完整 runtime；真正运行时使用的是 `src/channel.ts`、`src/gateway.ts` 和 `src/nostr-bus.ts`。
