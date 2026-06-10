# 目录：src/channels

## 它负责什么

`src/channels` 是 OpenClaw 核心里的“渠道实现层”。这里的渠道不是某一个具体插件的业务代码，而是核心为 Discord、Slack、Telegram 等消息入口/出口提供的通用运行框架：消息如何进入、如何做权限判断、如何绑定会话、如何组装上下文、如何交给 agent turn、如何发送回复、如何记录 durable delivery 状态，以及渠道插件如何被发现、注册和调用。

 scoped 指南明确说明：`src/channels/**` 是 core channel implementation，插件作者不应该直接 import 这个目录。插件面向的公共契约应通过 `openclaw/plugin-sdk/*`、`src/plugin-sdk/channel-contract.ts` 以及 `src/channels/plugins/types.plugin.ts`、`types.core.ts`、`types.adapters.ts` 这类 typed contract 暴露。因此可以把这个目录理解为：它不是插件 SDK 本身，而是 SDK 背后的核心执行和适配层。

这个目录还承担很多跨渠道一致性规则，例如 allowlist、mention/command gating、typing 状态、ack reactions、status reactions、thread binding、conversation resolution、sender identity、channel config、model overrides 等。它们让不同渠道可以共享同一套核心行为，而不是每个插件重复实现。

## 直接子目录地图

`src/channels/allowlists` 放 allowlist 解析辅助逻辑，目前从文件名看主要是 resolve utils，用于把配置、账号或上下文里的 allowlist 输入整理成可判断的形式。

`src/channels/inbound-event` 处理进入系统的事件标准化。这里包含 `classification.ts`、`context.ts`、`kind.ts`、`media.ts`，说明它负责判断入站事件类型、构建事件上下文，以及把入站媒体转成后续 turn/history 可消费的事实。

`src/channels/message` 是消息收发和消息生命周期的集中区域。它导出 message adapter contract、live preview、durable receive、send、receipt、reply pipeline、state 等能力。`src/channels/message/index.ts` 是该子域的聚合入口。

`src/channels/message-access` 是入站权限判断运行时。它把 DM/group allowlist、pairing store、access groups、sender gate、route gate、identity runtime 等组合成 `ResolvedChannelMessageIngress` 一类结果，用来决定消息是否可进入 agent 流程。

`src/channels/plugins` 是渠道插件的核心注册、加载、配置和插件能力适配层。这里包含 registry、bundled plugin、module loader、setup wizard、pairing、approvals、message tool API、thread binding API、status、target parsing、config schema、lifecycle startup 等大量能力。它是核心认识“有哪些渠道插件、插件提供什么能力、如何启动维护任务”的主要位置。

`src/channels/plugins/actions` 根据目录名推断是插件 action 相关的补充区域；当前片段没有展开读取，不能确认具体职责。

`src/channels/plugins/contracts` 根据目录名和 scoped 指南推断是插件契约测试/辅助相关区域；其中还有 `test-helpers/AGENTS.md`，说明这里对子树测试有额外约束，阅读或修改时需要继续进入 scoped 指南。

`src/channels/plugins/outbound` 根据目录名推断是插件出站发送适配相关区域，和根层 `outbound.types.ts`、`message/outbound-bridge.ts` 形成呼应。

`src/channels/plugins/status-issues` 根据目录名推断是插件状态问题建模或报告相关区域，和 `plugins/status.ts`、`plugins/status-state.ts` 同属插件状态面。

`src/channels/status` 是渠道状态 read model 区域，`read-model.ts` 表明这里偏向把运行态状态整理成可读模型。

`src/channels/transport` 处理更底层的传输健康性，目前看到 `stall-watchdog.ts`，用于监控传输停滞一类问题。

`src/channels/turn` 是消息进入 agent 回合的核心管线位置。它包含 `kernel.ts`、`durable-delivery.ts`、`history-window.ts`、`bot-loop-protection.ts`、`delivery-result.ts`、`dispatch-result.ts`、`types.ts`，负责从标准化入站输入到调度、回复投递、历史记录和防循环保护的主流程。

## 关键入口

`src/channels/AGENTS.md` 是理解边界的第一入口。它规定核心渠道实现和插件 SDK 的边界，强调插件作者应走 `openclaw/plugin-sdk/*`，也提醒 `channel.ts`、`shared.ts`、`channel.setup.ts`、`gateway.ts`、`outbound.ts` 这类渠道入口是 hot import path，不能随意静态引入重型 runtime、setup/login 或大 barrel。

`src/channels/message/index.ts` 是消息子域的导出入口。它集中暴露 `createChannelReplyPipeline`、`sendDurableMessageBatch`、`createDurableInboundReceiveJournal`、`createLiveMessageState`、`deliverFinalizableLivePreview`、`createMessageReceiveContext`、各种 capability proof verifier，以及 `ChannelMessageAdapter`、`MessageReceipt`、`RenderedMessageBatch` 等类型。想理解“核心如何抽象消息发送/接收能力”，从这里看导出的概念最有效。

`src/channels/plugins/index.ts` 是插件子域的轻量公共入口，导出 `getChannelPlugin`、`getLoadedChannelPlugin`、`listChannelPlugins`、`normalizeChannelId`，以及 channel config match、allowlist match、approval capability、`ChannelPlugin` 类型等。它是核心其他模块读取渠道插件能力时更应该依赖的窄入口。

`src/channels/plugins/registry.ts` 是插件查找入口之一。它先查 loaded registry，再 fallback 到 bundled plugin：`getChannelPlugin(id)` 会返回已加载插件或内置插件。这个行为说明核心既支持运行期已注册插件，也保留 bundled 渠道的读取路径。

`src/channels/plugins/lifecycle-startup.ts` 是启动维护入口。`runChannelPluginStartupMaintenance` 遍历 `listChannelPlugins()`，调用插件可选的 `lifecycle.runStartupMaintenance`，失败时记录 warn 并继续，不让单个渠道维护任务阻断 gateway 启动。

`src/channels/message-access/runtime.ts` 是入站访问控制的重要入口。它组合配置 allowlist、pairing store fallback、DM/group 策略、access group、sender gate、route gate 和 identity subject，用来判断一条渠道消息是否允许进入后续流程。

`src/channels/turn/kernel.ts` 是 turn 主流程入口。它导出构建入站事件上下文、history window、durable delivery、dispatch result、delivery result 等能力，并包含 `recordDroppedChannelTurnHistory`、`createNoopChannelEventDeliveryAdapter`、`createChannelTurnReplyPipeline` 等与 turn 执行直接相关的函数。

## 主流程位置

一条渠道消息的大致路径可以这样读：插件或渠道 runtime 先把外部平台事件转为核心可识别的入站事件，相关上下文在 `src/channels/inbound-event/context.ts`、媒体事实在 `src/channels/inbound-event/media.ts` 附近形成。随后进入访问控制层，`src/channels/message-access/runtime.ts` 读取配置、allowlist、pairing store、access groups 和 sender/route gates，决定这条消息是 dispatch、observeOnly、handled 还是 drop。

通过 admission 后，turn 层接管。`src/channels/turn/kernel.ts` 里的类型和函数把 `NormalizedTurnInput`、`PreflightFacts`、`PreparedChannelTurn`、`ResolvedChannelTurn` 等阶段串起来。这里还处理 dropped history、bot-loop protection、history window、dispatch counts 和 durable inbound reply delivery。根据当前片段推断，`src/channels/turn/types.ts` 是理解这些阶段结构的关键类型文件，依据是 `kernel.ts` 从其中导入了主流程的大部分类型。

回复发送会进入 message 层。`src/channels/message/reply-pipeline.ts` 创建 `ChannelReplyPipeline`，合并 reply prefix、typing callbacks，以及插件可选的 `messaging.transformReplyPayload`。真正发送则由 `src/channels/message/send.ts`、`src/channels/turn/durable-delivery.ts`、`src/channels/message/outbound-bridge.ts` 等衔接。durable 相关能力通过 receipt、send state、receive journal 保证最终发送、失败恢复和可观测状态。

插件能力的发现与注册在 `src/channels/plugins`。`registry.ts`、`registry-loaded.ts`、`registry-loader.ts`、`bundled.ts`、`bundled-root.ts` 决定插件从哪里来；`types.plugin.ts`、`types.core.ts`、`types.adapters.ts` 定义核心和插件之间的契约；`message-capabilities.ts`、`message-tool-api.ts`、`thread-binding-api.ts`、`target-resolvers.ts` 等把插件提供的能力投影给核心流程使用。

## 推荐阅读顺序

先读 `src/channels/AGENTS.md`，明确边界：这个目录是核心实现，不是插件作者直接依赖的 SDK。

第二步读 `src/channels/plugins/index.ts` 和 `src/channels/plugins/registry.ts`，建立“渠道插件如何被列出、查找、fallback 到 bundled”的基本模型。

第三步读 `src/channels/message/index.ts`，只看导出清单即可，先把 message adapter、send、receive、receipt、live preview、durable state、reply pipeline 这些核心名词串起来。

第四步读 `src/channels/message-access/runtime.ts`，理解消息进入 agent 前的权限和路由判断。这里能看到 DM、group、allowlist、pairing store、access groups 等配置如何汇合。

第五步读 `src/channels/turn/kernel.ts` 和 `src/channels/turn/types.ts`，理解从入站消息到 agent turn、history、delivery result 的主流程骨架。

最后再按问题进入旁支：看配置就去 `channel-config.ts`、`config-presence.ts`、`plugins/config-schema.ts`；看会话绑定就去 `session.ts`、`conversation-binding-context.ts`、`thread-binding-id.ts`；看状态反应就去 `status-reactions.ts`、`plugins/status.ts`；看 typing 就去 `typing.ts`、`typing-lifecycle.ts`。

## 常见误区

不要把 `src/channels/plugins` 理解成具体渠道插件源码。它主要是核心里的插件加载、注册、契约和适配层；真正插件实现通常在 `extensions/` 下，通过 SDK seam 与核心交互。

不要让插件生产代码直接依赖 `src/channels/**`。scoped 指南明确要求 extension-facing channel surface 通过 `openclaw/plugin-sdk/*` 流出；如果需要新能力，应先增加 typed SDK contract 或 facade。

不要把 `message`、`turn`、`message-access` 混成一个概念。`message-access` 负责“能不能进”；`turn` 负责“进入后如何形成和调度一次 agent 回合”；`message` 负责“消息能力、发送接收、receipt、live/durable 生命周期”。

不要在 hot channel entrypoint 静态引入重型 runtime。指南特别提醒 setup/login、send、monitor、probe、directory-live、大型 `runtime-api.ts` barrel 等应保持 lazy 或通过小 seam 隔离，否则会影响 gateway 或 agent tools 的启动路径。

不要只看某个渠道的行为来判断核心规则。`src/channels` 是 shared channel layer，改动可能同时影响 bundled 和 extension channels；allowlist、command gating、pairing、reply、thread binding、setup、gateway auth bypass 等都可能有跨渠道影响。

不要把 fallback 当成任意兼容层。比如 `getChannelPlugin` 的 loaded-then-bundled fallback 是明确的 registry 行为；而配置迁移、旧 key 兼容、插件能力 fallback 等需要遵守根规则和契约，不能随意在运行时增加静默兼容。
