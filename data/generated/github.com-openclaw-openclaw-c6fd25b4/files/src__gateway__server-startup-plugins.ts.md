# 文件：src/gateway/server-startup-plugins.ts

## 一句话定位

`src/gateway/server-startup-plugins.ts` 是 Gateway 启动阶段的插件引导编排层：它不真正实现插件加载细节，而是把启动配置、插件激活配置、lookup table、基础 Gateway 方法列表、运行时插件加载时机串起来，给 `server.impl.ts` 提供一个稳定的启动结果。

## 它暴露/定义了什么

这个文件主要导出两个核心函数和一个小型配置辅助函数。

`resolveGatewayStartupMaintenanceConfig` 用于决定启动维护任务应该使用哪份 `channels` 配置：如果 `cfgAtStart` 没有 `channels`，但 `startupRuntimeConfig` 有，则把后者补回去；如果启动配置已经显式带了 `channels`，则保持原样。测试 `src/gateway/server.startup-matrix-migration.integration.test.ts` 说明它用于覆盖“启动配置被修复后，channel 维护任务仍能看到修复结果”的场景。

`prepareGatewayPluginBootstrap` 是本文件的主入口。它负责执行 channel/plugin 启动维护、初始化 subagent registry、应用插件自动启用规则、生成插件 lookup table、计算启动插件列表，并根据参数决定是否立即加载运行时插件。

`loadGatewayStartupPluginRuntime` 是一个薄包装，动态导入 `src/gateway/server-plugin-bootstrap.ts` 的 `loadGatewayStartupPlugins`，并把本文件整理好的参数传过去。

文件内还定义了 `GatewayPluginBootstrapLog`、`GatewayStartupTrace` 两个局部类型，用来约束日志和启动 trace 的最小接口。

## 谁调用它

直接调用方主要是 `src/gateway/server.impl.ts`。Gateway 启动时先加载配置快照、准备认证和运行时配置，然后动态导入本文件并调用 `prepareGatewayPluginBootstrap`。在当前片段中，`server.impl.ts` 调用时传入 `loadRuntimePlugins: false`，表示先完成轻量 bootstrap，真正的 runtime plugin 加载延后到 post-attach 阶段。

另一个调用点仍在 `server.impl.ts` 的 post-attach 参数里：如果前面没有加载 runtime plugins，它会传入一个 `loadStartupPlugins` 回调，回调内部再次动态导入本模块并调用 `loadGatewayStartupPluginRuntime`。`src/gateway/server-startup-post-attach.ts` 会在非 minimal gateway 且存在该回调时执行它。

测试侧，`src/gateway/server-startup-plugins.test.ts` 直接验证 `prepareGatewayPluginBootstrap` 的配置合并、全局禁用插件时的 lookup 跳过、传给插件加载器的参数等行为。

## 它调用谁

它调用的上游/邻近模块可以分成几类。

配置与 agent 范围：`resolveDefaultAgentId`、`resolveAgentWorkspaceDir` 用来从最终插件配置中确定默认 agent 和 workspace；`applyPluginAutoEnable` 负责根据配置、环境、manifest/discovery 自动启用插件；`mergeActivationSectionsIntoRuntimeConfig` 把激活配置合并到运行时配置。

插件索引与运行时：`loadPluginLookUpTable` 生成启动插件计划和 deferred channel 插件列表；`createEmptyPluginRegistry`、`getActivePluginRegistry`、`setActivePluginRegistry` 处理 minimal gateway 或未加载插件时的 registry 状态；`server-plugin-bootstrap.ts` 的 `loadGatewayStartupPlugins` 才是真正加载 Gateway 插件运行时的入口。

Gateway 方法：`listGatewayMethods` 提供基础方法列表，`listCoreGatewayMethodNames` 提供核心 Gateway 方法名，用于区分核心方法和插件方法。

启动维护：通过动态 import 调用 `src/channels/plugins/lifecycle-startup.ts` 的 `runChannelPluginStartupMaintenance`；非 minimal gateway 还会调用 `src/gateway/server-startup-session-migration.ts` 的 `runStartupSessionMigration`。

## 核心流程

第一步，`prepareGatewayPluginBootstrap` 选择 activation source。默认使用 `cfgAtStart`，但调用方可传入 `activationSourceConfig`，这允许“运行时配置”和“插件激活来源配置”分离。测试表明，插件是否启用应从 source config 推导，而 runtime defaults 仍会保留在最终运行时配置中。

第二步，计算 `startupMaintenanceConfig`。这里的特殊点是 `channels` 修复：如果启动早期修复出了 channel 配置，而 `cfgAtStart` 没有 channel，则维护任务仍要看到修复后的 channel。

第三步，运行启动维护。非 minimal gateway 总会运行 channel plugin startup maintenance 和 session migration；minimal test gateway 只有在存在 `channels` 时才跑 channel 维护，以降低测试启动成本。

第四步，初始化 subagent registry，并构造 `gatewayPluginConfig`。minimal gateway 直接使用 `cfgAtStart`；普通 gateway 会先对 activation source 执行 `applyPluginAutoEnable`，再把激活段合并进 runtime config。

第五步，根据 `plugins.enabled === false` 和 `minimalTestGateway` 决定是否创建 `pluginLookUpTable`。如果插件全局禁用或是 minimal gateway，就不做插件索引；否则用默认 workspace、环境变量、metadata snapshot 和 activation source 建立 lookup table。

第六步，从 lookup table 提取 `deferredConfiguredChannelPluginIds` 和 `startupPluginIds`，准备基础 Gateway 方法，并根据 `loadRuntimePlugins` 决定是否立即调用 `loadGatewayStartupPluginRuntime`。如果不加载，则安装空 registry，或在 minimal gateway 下沿用当前 active registry。

最终返回一组启动后续阶段需要的事实：最终插件配置、默认 workspace、deferred 插件列表、startup 插件列表、lookup table、基础方法、registry、插件方法集合以及 runtime plugins 是否已加载。

## 关键函数的高层作用

`prepareGatewayPluginBootstrap` 是“启动插件计划生成器”。它的价值不是加载插件本身，而是在 Gateway 绑定端口前后之间建立清晰分界：哪些事情必须在早期做，哪些插件运行时可以延后到 post-attach。

`loadGatewayStartupPluginRuntime` 是“延迟加载适配器”。它把 `server.impl.ts` 或 post-attach 阶段已有的启动事实传给 `loadGatewayStartupPlugins`，同时保留 `hostServices`、`startupTrace`、`preferSetupRuntimeForChannelPlugins` 等运行时参数。

`resolveGatewayStartupMaintenanceConfig` 是“channel 维护配置修正器”。它只处理一个边界条件：启动配置修复出的 `channels` 不应被后续维护任务看丢。

## 修改风险

最大风险是破坏启动阶段的时序。当前设计刻意支持 `loadRuntimePlugins: false`，让 Gateway 可以先完成轻量 bootstrap，再在 `src/gateway/server-startup-post-attach.ts` 中加载 runtime plugins 和 sidecars。提前加载、重复加载或漏设 `setActivePluginRegistry` 都可能影响 Gateway 方法注册、channel sidecar、日志和 discovery 刷新。

第二类风险是配置来源混淆。`activationSourceConfig`、`cfgAtStart`、`startupRuntimeConfig` 各自含义不同：前者用于判断插件激活，`cfgAtStart` 是启动认证/修复后的配置，`startupRuntimeConfig` 带有运行时 override。把它们合并顺序改错，可能导致插件被错误启用、禁用，或 runtime defaults 覆盖用户配置。

第三类风险是 plugin lookup table 的热路径成本。`src/gateway/AGENTS.md` 明确要求 Gateway 启动路径避免为了静态描述符加载完整 bundled plugin runtime。本文件通过 `pluginMetadataSnapshot`、`loadPluginLookUpTable` 和 deferred runtime load 来降低启动成本；随意改成直接加载插件注册表，会影响测试和实际启动性能。

第四类风险是 minimal test gateway 行为。测试环境下会跳过大部分插件加载，但仍可能复用 active registry。修改这段逻辑容易造成测试间状态泄漏，或让 minimal gateway 意外执行真实 plugin startup maintenance。

第五类风险是全局禁用插件语义。`plugins.enabled === false` 时 lookup table 被跳过，但仍会把空 `pluginIds` 传入后续加载路径。改动时要确保禁用插件不会触发 discovery、manifest 加载或插件方法注入。
