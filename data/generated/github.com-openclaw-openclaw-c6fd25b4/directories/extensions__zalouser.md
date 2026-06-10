# 目录：extensions/zalouser

## 它负责什么

`extensions/zalouser` 是 OpenClaw 的 Zalo Personal Account 插件目录，包名是 `@openclaw/zalouser`。它把个人 Zalo 账号接入 OpenClaw 的 channel/plugin 体系，能力包括 QR 登录、会话凭据保存、多账号配置、消息监听、文本/图片/链接发送、目录查询、agent tool 调用、doctor 修复与安全审计。

从 `package.json`、`openclaw.plugin.json` 和 `README.md` 可以看出，这不是核心内置 channel 的深层实现，而是一个遵循 `openclaw/plugin-sdk/*` 边界的 bundled plugin。插件声明的 channel id 是 `zalouser`，选择文案是 `Zalo (Personal Account)`，依赖 `zca-js` 作为 Zalo 原生集成层。顶层 manifest 同时声明了 channel、tool contract、环境变量 `ZALOUSER_PROFILE` / `ZCA_PROFILE`、setup entry 和安装元数据。

这个目录的职责边界比较清楚：OpenClaw core 只通过插件 SDK 和顶层 entry/barrel 认识它；Zalo 登录、发送、监听、账号、配置兼容、群组策略等 owner-specific 行为都留在插件内部。

## 直接子目录地图

该目录结构很浅，直接子目录只有：

`extensions/zalouser/src`

`src` 是主要实现区，承载所有私有运行时代码和测试。顶层则主要是插件发现、公开导出和包元数据：`index.ts`、`runtime-api.ts`、`api.ts`、`channel-plugin-api.ts`、`setup-entry.ts`、`setup-plugin-api.ts`、`contract-api.ts`、`doctor-contract-api.ts`、`secret-contract-api.ts`、`openclaw.plugin.json`、`package.json`、`README.md` 等。

根据当前片段推断，顶层 `*-api.ts` 文件的作用是把内部实现包装成稳定、窄口的插件入口，避免 core 或发现流程 deep import `src/**`。依据是 `extensions/AGENTS.md` 明确要求 extension production code 通过 SDK 和本包 barrel 暴露公共能力，且 `channel-plugin-api.ts` 注释说明轻量 bootstrap/discovery 路径不应拖入 setup-only 或 tool runtime surface。

## 关键入口

最核心的入口是 `index.ts`。它调用 `defineBundledChannelEntry` 注册 bundled channel entry，声明插件 id `zalouser`、名称 `Zalo Personal`、描述、plugin 入口 `./channel-plugin-api.js`、runtime 入口 `./runtime-api.js`，并在 `registerFull` 中注册名为 `zalouser` 的 agent tool。tool 创建过程通过 `loadBundledEntryExportSync` 从 `api.js` 加载 `createZalouserTool`。

`channel-plugin-api.ts` 是轻量 channel 插件入口，只导出 `src/channel.ts` 里的 `zalouserPlugin`。真正 channel 插件对象在 `src/channel.ts` 中构造，使用 `createChatChannelPlugin`，并连接 setup、status、directory、monitor 等能力。

`runtime-api.ts` 是运行时聚合入口。它一方面从 `api.ts` 重新导出插件、setup、tool、安全审计等能力，另一方面导出 `src/runtime.ts` 的 `setZalouserRuntime`，并重新导出大量 `openclaw/plugin-sdk/*` 类型和 helper。这个文件是 bundled runtime 激活时的主要桥接层。

`setup-entry.ts` 是 setup 专用入口，调用 `defineBundledChannelSetupEntry` 指向 `setup-plugin-api.ts`。setup 的实际向导在 `src/setup-surface.ts`，setup 适配层在 `src/setup-core.ts`，channel setup plugin 在 `src/channel.setup.ts`。

`api.ts` 是全量公开 barrel，导出 `zalouserPlugin`、`zalouserSetupPlugin`、`createZalouserTool`、setup wizard/proxy、安全审计等。读代码时可以把它当成“外部能看到哪些能力”的索引。

## 主流程位置

启动和注册流程从 `index.ts` 进入：OpenClaw 发现 bundled channel entry 后，通过 manifest 和 entry metadata 知道 `zalouser` channel 存在；需要完整能力时再加载 `channel-plugin-api.ts`、`runtime-api.ts` 或 `api.ts`。

channel 主流程在 `src/channel.ts`。这里组装 `zalouserPlugin`，把插件基础信息、setup wizard、账号状态、目录能力和监听启动点挂到 OpenClaw channel contract 上。它通过 lazy runtime 方式加载 `src/channel.runtime.ts`，并在启动监听时动态引入 `src/monitor.ts` 的 `monitorZalouserProvider`。

登录/setup 主流程在 `src/setup-surface.ts`、`src/setup-core.ts`、`src/channel.setup.ts` 和 `src/zalo-js.ts` 之间流动。`setup-surface.ts` 负责交互式 wizard、DM policy、allowlist、group policy、帮助提示和 QR 登录步骤；`setup-core.ts` 提供代理和 patched account setup adapter；底层 QR 登录、等待登录、凭据写入由 `src/zalo-js.ts` 的 `startZaloQrLogin`、`waitForZaloQrLogin` 等函数承接。

发送流程主要在 `src/send.ts` 和 `src/zalo-js.ts`。`sendMessageZalouser` 负责文本分块、样式处理和 receipt 组装，然后调用 `sendZaloTextMessage`；`sendImageZalouser`、`sendLinkZalouser`、`sendTypingZalouser`、`sendReactionZalouser` 等分别覆盖媒体、链接、输入状态和 reaction。真正与 `zca-js` API 交互的位置集中在 `src/zalo-js.ts`。

监听与入站处理主流程在 `src/monitor.ts`。它处理 allowlist、pairing、group gating、mention requirement、session key、delivery ack、消息排队与 agent ingress。底层监听由 `src/zalo-js.ts` 的 `startZaloListener` 提供，消息转换逻辑也在 `src/zalo-js.ts` 中靠近 `toInboundMessage` 一带。

账号与配置解析在 `src/accounts.ts`、`src/config-schema.ts`、`src/types.ts`。其中 `accounts.ts` 解析默认账号、多账号、profile 和认证状态；`config-schema.ts` 定义 channel 配置 schema；`types.ts` 放 Zalo friend/group/message/send/config 等领域类型。

doctor 与兼容迁移在 `src/doctor.ts`、`src/doctor-contract.ts`。安全检查在 `src/security-audit.ts`，重点是可变 group name matching 之类风险。agent tool 在 `src/tool.ts`，支持 `send`、`image`、`link`、`friends`、`groups`、`me`、`status` 等 action。

## 推荐阅读顺序

1. 先读 `openclaw.plugin.json` 和 `package.json`，确认插件 id、channel metadata、setup entry、依赖和发布形态。
2. 再读 `index.ts`、`channel-plugin-api.ts`、`runtime-api.ts`、`api.ts`，建立“OpenClaw 怎么加载这个插件”的入口地图。
3. 接着读 `src/channel.ts`，理解 `zalouserPlugin` 如何把 setup、status、directory、monitor 串进 channel contract。
4. 然后按主流程分支阅读：登录看 `src/setup-surface.ts`、`src/setup-core.ts`、`src/zalo-js.ts`；发送看 `src/send.ts`、`src/zalo-js.ts`；接收看 `src/monitor.ts`、`src/zalo-js.ts`。
5. 最后读支撑层：`src/accounts.ts`、`src/config-schema.ts`、`src/group-policy.ts`、`src/directory.ts`、`src/doctor-contract.ts`、`src/security-audit.ts`、`src/tool.ts`。
6. 测试文件可以按同名关系补读，例如 `src/send.test.ts`、`src/monitor.group-gating.test.ts`、`src/channel.setup.test.ts`，用来确认行为边界。

## 常见误区

不要把 `extensions/zalouser/src/**` 当成 core 可直接引用的公共 API。按照 `extensions/AGENTS.md`，插件内部实现应通过 `api.ts` 或更窄的 `*-api.ts` 暴露，core 不应 deep import 插件私有文件。

不要以为 `index.ts` 包含完整运行逻辑。它主要是 bundled entry 和 tool 注册，真正的 channel 行为在 `src/channel.ts`，底层 Zalo API 交互集中在 `src/zalo-js.ts`。

不要把 setup 和 runtime 混在一起理解。`setup-entry.ts`、`setup-plugin-api.ts`、`src/setup-surface.ts` 处理登录配置体验；`runtime-api.ts`、`src/runtime.ts`、`src/monitor.ts`、`src/send.ts` 处理运行期收发和状态。

不要忽略多账号路径。配置里有 `defaultAccount`、`accounts`、`profile`，`src/accounts.ts` 会把 channel 级配置和 account 级配置合并；读发送、监听或 doctor 行为时都要确认当前 account/profile。

不要把群组名字匹配当成稳定标识。`src/security-audit.ts` 对 mutable group entry 有专门审计，README 也提示 name resolution 问题优先使用数值 ID 或精确名称。根据当前片段推断，群组策略和 allowlist 是这个插件的重要安全边界，依据是 `monitor.ts`、`group-policy.ts`、`security-audit.ts` 和 manifest 的 doctor capabilities 都围绕 DM/group policy 展开。
