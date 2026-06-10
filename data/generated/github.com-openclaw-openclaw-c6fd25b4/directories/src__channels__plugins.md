# 目录：src/channels/plugins

## 它负责什么

`src/channels/plugins` 是 OpenClaw core 里“频道插件”能力的中间层：它不直接等同于某个 Telegram、Slack、iMessage 等具体插件实现，而是定义、加载、注册、查询和适配这些 channel plugin 的统一合同。根据 `src/channels/AGENTS.md` 的边界说明，`src/channels/**` 属于 core channel implementation，插件作者不应直接 import 这里；对外可见的插件开发入口应经由 `openclaw/plugin-sdk/*` 暴露。

从代码形态看，这个目录承担三类职责。第一是类型合同，核心文件包括 `types.plugin.ts`、`types.core.ts`、`types.adapters.ts`、`types.public.ts`、`types.config.ts`，共同描述 `ChannelPlugin` 以及它可提供的 `config`、`setup`、`outbound`、`status`、`gateway`、`security`、`pairing`、`directory`、`threading`、`messaging`、`actions` 等 surface。第二是运行期注册与发现，例如 `registry.ts`、`registry-loaded.ts`、`registry-loader.ts`、`bundled.ts`、`bootstrap-registry.ts` 负责从已加载 registry 或 bundled channel 里拿到插件对象。第三是把插件能力接入 core 流程，例如发送、会话绑定、配置写入、pairing、setup wizard、message actions、目录查询、gateway auth bypass、状态快照等。

简化理解：这里是“core 如何认识一个频道插件”的地图和适配层，而不是“某个频道如何实现业务逻辑”的目录。

## 直接子目录地图

`src/channels/plugins/actions` 放置消息动作相关的轻量共享逻辑，目前重点是 reaction message id 与 action shared helper。它属于 message action 流程的一小块，不是全局 action 框架的唯一入口。

`src/channels/plugins/contracts` 是合同测试区，覆盖 registry-backed plugin、directory、threading、session binding、outbound payload、catalog、config write、group policy 等行为。这个目录说明 channel plugin surface 有一套稳定契约，不只是 TypeScript 类型约束。其下 `contracts/test-helpers` 是合同测试用的 fixture、manifest、runtime artifact、contract suite 生成器等辅助材料，并带有自己的 scoped `AGENTS.md`。

`src/channels/plugins/outbound` 是 outbound 发送能力的懒加载边界。`outbound/load.ts` 里的注释明确说明 full channel plugin 会拉入 status、setup、gateway monitors 等较重依赖，而 outbound delivery 只需要发送 primitives，所以这里提供更轻量的 `loadChannelOutboundAdapter`。`direct-text-media.ts`、`interactive.ts`、`presentation-limits.ts` 则围绕直接文本/媒体、交互消息和呈现限制。

`src/channels/plugins/status-issues` 存放状态问题相关共享定义，目前主要是 `shared.ts`。它服务于 status/account health 一类流程，不应被误读为完整 status 实现目录；完整状态能力还分布在 `status.ts`、`status-state.ts`、`package-state-probes.ts` 等顶层文件。

## 关键入口

`src/channels/plugins/index.ts` 是对外聚合入口之一，导出 `getChannelPlugin`、`getLoadedChannelPlugin`、`listChannelPlugins`、`normalizeChannelId`，以及 allowlist、channel config、approval adapter 和核心类型。很多 core 调用方通过它拿 channel plugin，而不是直接触碰具体 bundled loader。

`src/channels/plugins/registry.ts` 是最直接的查询入口。`getChannelPlugin(id)` 先查已加载插件，再回退到 bundled channel plugin；`listChannelPlugins()` 列出 loaded registry 内的插件。这里体现了 loaded plugin 与 bundled plugin 的两层来源。

`src/channels/plugins/registry-loader.ts` 提供 `createChannelRegistryLoader`，用于按 `ChannelId` 从 active plugin channel registry 或 active plugin registry 解析某个 surface。`src/channels/plugins/outbound/load.ts` 就用它只加载 `entry.plugin.outbound`，避免发送路径导入完整插件。

`src/channels/plugins/bootstrap-registry.ts` 面向启动期 bootstrap，能列出 bundled channel ids，并把 runtime plugin 与 setup plugin 的 section 合并为一个 bootstrap plugin。它说明 setup runtime 和 runtime surface 在启动期可能分开来源，最终再合并。

`src/channels/plugins/types.plugin.ts` 是阅读能力模型的核心。`ChannelPlugin` 类型列出了一个频道插件可选和必选的功能面：`id`、`meta`、`capabilities`、`config` 是基础；`setup`、`pairing`、`security`、`outbound`、`status`、`gateway`、`auth`、`commands`、`lifecycle`、`bindings`、`conversationBindings`、`threading`、`message`、`messaging`、`agentTools` 等是按需 surface。

## 主流程位置

插件启动加载主流程不在本目录单独闭环，而是由 gateway 和 plugin runtime 共同驱动。`src/gateway/server-startup-plugins.ts` 的 `prepareGatewayPluginBootstrap` 会在启动时运行 channel plugin startup maintenance，然后加载 plugin lookup table，并调用 `loadGatewayStartupPluginRuntime`。后者动态导入 `src/gateway/server-plugin-bootstrap.ts`，再进入 `loadGatewayStartupPlugins`。

`src/gateway/server-plugin-bootstrap.ts` 的 `prepareGatewayPluginLoad` 调用 `loadGatewayPlugins` 装载插件运行期，并通过 `pinActivePluginChannelRegistry` 固定 active channel registry，还会调用 `primeConfiguredBindingRegistry` 预热 configured binding registry。之后，`src/channels/plugins/registry-loader.ts`、`registry.ts` 这类文件才能稳定从 active registry 读到 channel plugin surface。

入站消息主流程在邻近目录而非本目录：`src/plugins/runtime/runtime-channel.ts` 组装 plugin runtime 的 `channel` 能力，把文本切分、reply dispatch、routing、pairing、media、session、mentions、reactions、groups、commands、outbound、turn、threadBindings 等能力暴露给插件运行期。其中 `outbound.loadAdapter` 指向 `src/channels/plugins/outbound/load.ts` 的 `loadChannelOutboundAdapter`，`turn` 则接到 `src/channels/turn/kernel.ts` 的 `runChannelTurn`、`runPreparedChannelTurn` 等。

Gateway 查询和管理频道的流程主要散落在 `src/gateway/server-channels.ts`、`src/gateway/server-methods/channels.ts`，它们会调用 `getChannelPlugin`、`listChannelPlugins`、`buildChannelUiCatalog`、`buildChannelAccountSnapshot` 等函数来支撑 UI catalog、账号状态、setup、start/stop、配置等操作。

## 推荐阅读顺序

1. 先读 `src/channels/AGENTS.md`，理解 channel 目录边界：core 内部实现、插件作者经 SDK、hot import path 要保持轻量。
2. 读 `src/channels/plugins/types.plugin.ts`，掌握 `ChannelPlugin` 的整体 surface；再按需看 `types.core.ts`、`types.adapters.ts`、`types.public.ts`。
3. 读 `src/channels/plugins/index.ts` 和 `src/channels/plugins/registry.ts`，理解外部如何查询 channel plugin。
4. 读 `src/channels/plugins/registry-loader.ts` 与 `src/channels/plugins/outbound/load.ts`，理解“只取某个 surface”的轻量加载模式。
5. 读 `src/channels/plugins/bootstrap-registry.ts`、`bundled.ts`、`bundled-root.ts`，理解 bundled channel 与 setup/runtime 合并。
6. 最后按主题进入 `catalog.ts`、`config-schema.ts`、`config-writes.ts`、`pairing.ts`、`setup-wizard.ts`、`message-action-discovery.ts`、`message-action-dispatch.ts`、`binding-registry.ts`、`thread-binding-api.ts` 等具体流程文件。

## 常见误区

不要把 `src/channels/plugins` 理解成第三方插件源码目录。真正插件包和 manifest 加载还涉及 `src/plugins/**`、`extensions/**` 和 `src/plugin-sdk/**`；这里主要是 core 对 channel plugin 的合同与适配。

不要从插件生产代码直接 import `src/channels/plugins/*`。仓库规则要求插件面向 `openclaw/plugin-sdk/*`，例如 `src/plugin-sdk/index.ts`、`src/plugin-sdk/channel-contract.ts`、`src/plugin-sdk/channel-runtime.ts` 会再转发必要类型和 helper。

不要以为 `getChannelPlugin` 总是只读一个来源。当前代码会优先读 loaded channel plugin，再回退 bundled plugin；而 `getLoadedChannelPlugin` 只读 loaded registry。这个差异会影响测试、启动期和外部插件场景。

不要把 outbound 发送路径和完整插件加载混在一起。`outbound/load.ts` 特意通过 `createChannelRegistryLoader` 只解析 `plugin.outbound`，目的是让发送热路径避免导入 status、setup、gateway monitor 等重模块。

不要逐个叶子文件记忆这个目录。overview 阶段应先按 surface 建模：类型合同、registry/loading、bundled/bootstrap、config/setup/pairing、message actions、binding/threading、outbound、status/catalog、contracts tests。掌握这些路径角色后，再按具体 bug 或功能进入单个文件。
