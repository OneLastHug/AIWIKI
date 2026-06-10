# 文件：src/gateway/server-plugin-bootstrap.ts

## 一句话定位

`src/gateway/server-plugin-bootstrap.ts` 是 Gateway 启动和重载插件运行时的“编排入口”：它不实现具体插件能力，而是把配置自动启用、运行时环境安装、插件加载、channel binding 预热、诊断日志输出串成一个稳定流程，供 Gateway server 在启动、配置热重载和延迟加载阶段复用。

## 它暴露/定义了什么

这个文件主要定义并导出三个函数：

`prepareGatewayPluginLoad` 是核心函数，接收 `GatewayPluginBootstrapParams`，完成一次完整的 Gateway 插件加载准备与加载。

`loadGatewayStartupPlugins` 是启动期包装函数，调用 `prepareGatewayPluginLoad`，并在 prime binding 前注入 `pinActivePluginChannelRegistry`，用于固定当前活跃 plugin channel registry。

`reloadDeferredGatewayPlugins` 是延迟插件重载包装函数，行为也委托给 `prepareGatewayPluginLoad`，但参数类型去掉了 `preferSetupRuntimeForChannelPlugins`，说明它面向启动后补载/替换场景，而不是 setup runtime 优先策略场景。

文件内还定义了两个非导出的辅助函数：`installGatewayPluginRuntimeEnvironment` 用来安装 Gateway 插件运行时全局绑定；`logGatewayPluginDiagnostics` 用来把插件 registry 的诊断信息统一写入日志。

## 谁调用它

主要调用方在 Gateway server 启动链路中：

`src/gateway/server-startup-plugins.ts` 的 `loadGatewayStartupPluginRuntime` 动态导入 `loadGatewayStartupPlugins`，把启动阶段筛选出的 `startupPluginIds`、`pluginLookUpTable`、`baseMethods`、`hostServices` 等传入。这说明本文件是启动插件运行时真正落地的位置。

`src/gateway/server.impl.ts` 在配置重载路径中动态导入 `prepareGatewayPluginLoad`，先重新生成 `pluginLookUpTable`，再调用本文件重新加载插件，并把结果交给 `replaceAttachedPluginRuntime`。

`src/gateway/server.impl.ts` 还在启动后处理 `deferredConfiguredChannelPluginIds` 时调用 `reloadDeferredGatewayPlugins`，用于延迟补载配置中的 channel 插件，然后刷新 attached gateway discovery。

相关测试包括 `src/gateway/server-plugins.test.ts`、`src/gateway/server-startup-plugins.test.ts`、`src/gateway/server-plugin-bootstrap.browser-plugin.integration.test.ts`，覆盖启动加载、重载、浏览器插件集成等行为。

## 它调用谁

它依赖的下游可以分成几类：

配置与激活：`applyPluginAutoEnable` 根据配置、环境变量、manifest registry、discovery 自动启用插件；当 `activationSourceConfig` 和运行时 `cfg` 不是同一个对象时，`mergeActivationSectionsIntoRuntimeConfig` 只把 activation 配置中的 `plugins.allow`、`plugins.entries.*.enabled`、`channels.*.enabled` 合并回运行时配置。

插件运行时安装：`setPluginSubagentOverridePolicies`、`createGatewaySubagentRuntime`、`setGatewaySubagentRuntime`、`createGatewayNodesRuntime`、`setGatewayNodesRuntime` 负责把 subagent、nodes 等 Gateway runtime 能力注册到 plugin runtime 全局绑定中。

插件加载与 registry：`loadGatewayPlugins` 执行实际插件加载，返回包含 `pluginRegistry` 等内容的加载结果；`pinActivePluginChannelRegistry` 固定活跃 channel registry；`primeConfiguredBindingRegistry` 根据最终配置预热 channel/plugin binding registry。

## 核心流程

`prepareGatewayPluginLoad` 的流程可以概括为五步。

第一步，确定激活配置来源。默认使用 `params.cfg`，如果调用方传入 `activationSourceConfig`，则用它来决定哪些插件或 channel 应启用。

第二步，调用 `applyPluginAutoEnable`。这里会把环境变量、manifest registry、discovery 作为自动启用依据。自动启用返回的新配置不是简单覆盖运行时配置：如果激活源就是运行时配置，则直接使用；否则只把激活相关 section 合并进 `params.cfg`，避免把 setup/activation 专用配置整体污染 runtime config。

第三步，安装插件运行时环境。`installGatewayPluginRuntimeEnvironment` 会先设置 subagent override policy，再创建并注册 Gateway subagent runtime 和 nodes runtime。这个顺序很重要，因为后续插件加载或运行可能依赖这些全局 runtime binding。

第四步，调用 `loadGatewayPlugins`。它把 resolved config、workspace、日志、core gateway handlers/method names、host services、base methods、plugin ids、lookup table、setup runtime 偏好、startup trace 等参数继续传下去。具体插件发现、模块加载、registry 构建不在本文件中完成。

第五步，执行加载后的固定与预热。先调用可选的 `beforePrimeRegistry`，启动和延迟重载包装函数都会传入 `pinActivePluginChannelRegistry`；然后调用 `primeConfiguredBindingRegistry`。最后如果启用诊断日志且 registry 有 diagnostics，就统一输出。

## 关键函数的高层作用

`prepareGatewayPluginLoad` 是唯一需要重点理解的函数。它的职责不是“加载插件”本身，而是为加载建立正确的配置、runtime 和 registry 时序。它把 activation config 与 runtime config 的边界显式化，避免自动启用逻辑直接变成运行时完整配置替换。

`loadGatewayStartupPlugins` 是启动期入口。它把 `pinActivePluginChannelRegistry` 固定进流程，保证启动加载出来的 channel registry 成为当前活跃 registry。

`reloadDeferredGatewayPlugins` 是延迟加载入口。根据当前片段推断，它服务于 Gateway 启动后补载 deferred channel plugin 的场景，依据是 `server.impl.ts` 在 `deferredConfiguredChannelPluginIds.length > 0` 时调用它，并随后执行 `replaceAttachedPluginRuntime` 与 `refreshAttachedGatewayDiscovery`。

`installGatewayPluginRuntimeEnvironment` 是运行时绑定安装器。它把 config 中的 subagent override 策略写入 runtime policy state，并安装 Gateway 提供给插件的 subagent/nodes 能力。

`logGatewayPluginDiagnostics` 只是诊断日志格式化器，把 `pluginId`、`source` 等上下文附加到 `[plugins]` 日志前缀下。

## 修改风险

最高风险是配置合并语义。`activationSourceConfig` 与 `cfg` 分离时，本文件只合并 activation section；如果改成整体合并或直接替换，可能把 setup、默认值、临时发现状态带入运行时，影响升级、配置热重载和插件启用行为。

第二个风险是运行时安装顺序。`setPluginSubagentOverridePolicies`、`setGatewaySubagentRuntime`、`setGatewayNodesRuntime` 必须在 `loadGatewayPlugins` 前完成，否则插件加载或运行时回调可能看到缺失的 runtime binding。

第三个风险是 registry pin 与 binding prime 的时机。`beforePrimeRegistry` 当前发生在 `primeConfiguredBindingRegistry` 之前；调整顺序可能导致 channel binding registry 基于旧 registry 或未固定 registry 预热，进而影响 Gateway channel 路由。

第四个风险是诊断日志策略。`logDiagnostics` 默认开启，但延迟加载路径会传 `false` 抑制重复日志。改变默认值或忽略该开关，可能让启动日志重复、测试断言变化，或掩盖插件加载诊断。

第五个风险是动态导入边界。调用方通过动态 import 引入本文件，符合 Gateway 热路径避免过早物化插件运行时的约束。把相关导入上移到静态启动路径，可能扩大启动成本，并违反 `src/gateway/AGENTS.md` 对 Gateway hot paths 的要求。
