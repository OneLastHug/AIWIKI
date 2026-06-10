# 目录：extensions/tlon

## 它负责什么

`extensions/tlon` 是 OpenClaw 的 Tlon/Urbit channel plugin。它把 OpenClaw 的通道抽象接到 Tlon/Urbit 消息体系上，覆盖三类核心能力：发送 DM、发送群组消息、在线监听并自动回复。插件元数据声明在 `extensions/tlon/openclaw.plugin.json` 和 `extensions/tlon/package.json` 的 `openclaw` 字段中，通道 id 是 `tlon`，对外选择名是 `Tlon (Urbit)`，并声明了 CLI 添加配置时可用的 `--ship`、`--code`、`--group-channels`、`--dm-allowlist`、`--auto-discover-channels` 等选项。

从边界上看，它是一个 bundled plugin，但需要遵守第三方插件同样的边界：生产代码主要依赖 `openclaw/plugin-sdk/*` 和本插件自己的 `api.ts`、`runtime-api.ts` 等本地 barrel，不直接穿透核心 `src/**`。目录里的 `README.md` 只给出一句定位：Tlon/Urbit channel plugin，支持 DM、group mentions 和 thread replies。

## 直接子目录地图

这个目录的直接子目录很少，主干集中在 `src/`：

- `src/`：插件主要实现目录，包含配置解析、通道定义、运行时、setup、doctor、目标地址解析、账号字段、Tlon API 封装，以及测试。
- `src/monitor/`：入站监听和自动回复主线。负责连接 Urbit SSE、发现频道、读取/迁移设置、判断授权、处理审批、抓取历史、下载媒体、去重已处理消息，并把合格消息交给 OpenClaw runtime。
- `src/urbit/`：Urbit/Tlon 底层交互封装。包括认证、SSRF 约束下的 fetch、SSE client、发送 DM/群组消息、上传媒体、频道操作、story/foreigns/context/error 等协议侧工具。

根目录文件大多是插件边界文件：`index.ts` 是 bundled channel entry；`api.ts`、`runtime-api.ts`、`channel-plugin-api.ts`、`setup-api.ts`、`doctor-contract-api.ts`、`test-api.ts` 是对核心、测试或插件 SDK 暴露的窄入口；`setup-entry.ts` 是 setup 入口；`openclaw.plugin.json`、`package.json`、`npm-shrinkwrap.json`、`tsconfig.json` 是发现、打包、依赖和编译元数据。

## 关键入口

`extensions/tlon/index.ts` 是 OpenClaw 发现这个 bundled channel plugin 的第一站。它调用 `defineBundledChannelEntry`，声明插件 id、名称、描述、`channel-plugin-api.js` 中的 `tlonPlugin`，以及 `api.js` 中的 `setTlonRuntime`。这说明插件不是靠导入时副作用注册，而是通过明确的 entry descriptor 交给宿主加载。

`extensions/tlon/src/channel.ts` 是通道插件对象的核心定义。这里创建 `tlonPlugin`，设置 `base.meta`、capabilities、setup、config schema、doctor、messaging、message adapter、status adapter 和 gateway 启动函数。它还定义了 `tlonChannelOutbound`，但真实发送逻辑通过 `createLazyRuntimeModule(() => import("./channel.runtime.js"))` 延迟加载，避免通道元数据路径过早加载运行时依赖。

`extensions/tlon/src/channel.runtime.ts` 是运行时实现的中心。它包含 `tlonRuntimeOutbound`，负责 `sendText`、`sendMedia`；也包含 `probeTlonAccount` 和 `startTlonGatewayAccount`。发送流程会解析账号和目标，认证 Urbit，再调用 `src/urbit/send.ts` 中的 `sendDm`、`sendGroupMessage`、`sendDmWithStory`、`sendGroupMessageWithStory`。

`extensions/tlon/src/monitor/index.ts` 是入站监听的主入口，导出 `monitorTlonProvider`。这里从 plugin runtime 读取当前配置，解析账号，认证，创建 `UrbitSSEClient`，加载 settings store，执行自动发现，再进入消息处理和自动回复流程。根据当前片段推断，`startTlonGatewayAccount` 最终会把 gateway account 启动接到这条监听主线上，依据是 `channel.ts` 的 `gateway.startAccount` 委托到 `channel.runtime.ts`，而 `channel.runtime.ts` 导入了 `monitorTlonProvider`。

## 主流程位置

插件发现流程：`openclaw.plugin.json` 和 `package.json` 提供静态元数据，`index.ts` 提供 bundled entry，核心加载后通过 `channel-plugin-api.ts` 取到 `tlonPlugin`，再通过 `api.ts` 注入或读取插件运行时。学习时要把“元数据发现”和“运行时启动”分开看。

配置与 setup 流程：配置 schema 在 `src/config-schema.ts`，账号解析在 `src/types.ts`，账号字段在 `src/account-fields.ts`，setup 逻辑分布在 `src/setup-core.ts`、`src/setup-surface.ts`、`setup-entry.ts`。`src/channel.ts` 通过 `createHybridChannelConfigAdapter` 把 `channels.tlon` 下的配置映射成账号视图，并支持默认账号、allowlist、删除字段保留等行为。

出站发送流程：入口是 `src/channel.ts` 的 message adapter 和 outbound adapter，实际执行在 `src/channel.runtime.ts` 的 `tlonRuntimeOutbound`。目标字符串先由 `src/targets.ts` 解析成 DM 或 group channel，再通过 `src/urbit/auth.ts` 登录，通过 `src/urbit/fetch.ts` 发 HTTP poke，最后在 `src/urbit/send.ts` 组装 Tlon/Urbit 所需的 `chat-dm-action` 或 `channel-action-1` payload。媒体发送还会经过 `src/urbit/upload.ts` 和 `buildMediaStory`。

入站监听流程：入口是 `src/monitor/index.ts` 的 `monitorTlonProvider`。它先读取配置、检查启用状态和账号完整性，然后认证并建立 `UrbitSSEClient`。之后会加载 settings store，可能把文件配置迁移进去，执行频道自动发现，合并手动频道，随后处理 DM、group mention、thread reply、审批响应、管理员命令、媒体下载、历史上下文和引用解析。这个目录下的监听逻辑是最复杂的部分，`src/monitor/utils.ts`、`authorization.ts`、`approval.ts`、`history.ts`、`media.ts`、`processed-messages.ts` 是理解判断链路的关键配套文件。

健康检查和修复流程：`src/doctor.ts`、`src/doctor-contract.ts`、`doctor-contract-api.ts` 负责 doctor 相关能力；`src/channel.ts` 的 status/probe 负责显示账号配置状态和探测账号可用性。`probeTlonAccount` 会认证后请求 Urbit 的 `/~/name` 路径，用于判断账号是否能正常访问。

## 推荐阅读顺序

1. 先看 `extensions/tlon/package.json` 和 `extensions/tlon/openclaw.plugin.json`，理解这个插件声明了什么能力、安装信息、channel 元数据和 CLI 配置面。
2. 再看 `extensions/tlon/index.ts`，确认 OpenClaw 如何发现并加载这个 bundled channel entry。
3. 阅读 `extensions/tlon/src/channel.ts`，这是插件对象地图，能看到 setup、config、doctor、messaging、status、gateway、outbound 如何拼在一起。
4. 顺着出站路径读 `extensions/tlon/src/channel.runtime.ts`、`extensions/tlon/src/targets.ts`、`extensions/tlon/src/urbit/send.ts`、`extensions/tlon/src/urbit/auth.ts`、`extensions/tlon/src/urbit/fetch.ts`。
5. 再读入站路径 `extensions/tlon/src/monitor/index.ts`，需要时补看 `src/monitor/authorization.ts`、`src/monitor/approval.ts`、`src/monitor/history.ts`、`src/monitor/media.ts`、`src/monitor/discovery.ts`。
6. 最后读 `extensions/tlon/src/setup-core.ts`、`src/setup-surface.ts`、`src/doctor.ts` 和各类 `*.test.ts`，用测试反证配置、发送、安全、媒体和监听边界。

## 常见误区

不要把 `extensions/tlon/index.ts` 当成业务实现文件。它主要是插件发现描述，真正的 channel 行为在 `src/channel.ts`，真正的网络运行时在 `src/channel.runtime.ts` 和 `src/monitor/index.ts`。

不要把 Tlon 目标当作普通字符串直接发送。目标必须经过 `src/targets.ts` 解析，DM、group channel、thread reply 的目标格式和 receipt/conversationId 语义不同。

不要认为 `src/channel.ts` 会直接导入所有重运行时依赖。这里有意使用 lazy runtime，把发送、探测、gateway 启动等行为延迟到 `channel.runtime.ts`，这是插件元数据路径和运行时路径分离的一部分。

不要绕过 `src/urbit/fetch.ts`、`src/urbit/context.ts` 直接 `fetch` Urbit 地址。这个插件涉及登录 code、cookie、私网访问和 SSRF 策略，底层请求封装是安全边界的一部分。

不要只看发送流程就认为插件只有 outbound。`src/monitor/` 是同等重要的主流程，负责监听 DM、群组 mention、thread reply、审批和设置热更新，是自动回复行为的核心。

不要把 `settings store` 和文件配置看成互斥。根据 `monitor/index.ts` 当前片段，运行时会读取 settings store，并在需要时把文件配置迁移或合并为有效配置，因此排查行为时要同时考虑文件配置、settings 覆盖和账号解析结果。
