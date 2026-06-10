# 目录：src/plugins/runtime

## 它负责什么

`src/plugins/runtime` 是 OpenClaw 插件系统的“运行时平面”目录，位置介于插件注册表、Gateway 请求处理、Plugin SDK 暴露面之间。上级 `src/plugins/AGENTS.md` 明确把插件体系分为 control plane 与 runtime plane：发现、manifest 解析、配置校验、setup/onboarding 提示、激活计划属于控制面；真正执行插件、为请求构造可用能力、解析运行时上下文属于这里。

从当前文件列表和引用关系看，这个目录主要负责几类事情：

第一，构造 `PluginRuntime` 对象。`src/plugins/runtime/index.ts` 是聚合入口，会组合 agent、channel、config、events、logging、media、system、taskflow、tasks 等能力，形成插件运行时可用的宿主 API。

第二，管理 Gateway 请求作用域。`src/plugins/runtime/gateway-request-scope.ts` 被 `src/gateway/server-methods.ts`、`src/gateway/server/plugins-http.ts`、`src/plugin-sdk/gateway-method-runtime.ts` 等路径引用，用来把一次 Gateway 调用中的 plugin runtime 上下文安全传递给下游处理逻辑。

第三，加载运行时注册表。`runtime-registry-loader.ts`、`metadata-registry-loader.ts`、`standalone-runtime-registry-loader.ts` 连接上层的 active plugin registry 状态与真正可执行的 plugin runtime。根据当前片段推断，metadata loader 更偏向轻量元数据路径，runtime loader 才进入可执行模块路径，这与 scoped 规则中“保持 discovery/setup 在 light path，实际执行再加载 heavy runtime surface”的要求一致。

第四，为插件提供运行时能力模块。`runtime-channel.ts`、`runtime-llm.runtime.ts`、`runtime-model-auth.runtime.ts`、`runtime-taskflow.ts`、`runtime-tasks.ts`、`runtime-web-channel-plugin.ts` 等文件分别承接 channel、LLM、模型认证、任务流、任务运行、Web channel 插件边界等能力。

## 直接子目录地图

`src/plugins/runtime` 当前没有直接子目录，所有实现文件、类型文件和测试文件都平铺在这一层。

这个目录虽然平铺，但可以按职责分成几组阅读：

`index.ts`、`types.ts`、`types-core.ts`、`types-channel.ts` 是核心入口与类型面。

`runtime-agent.ts`、`runtime-channel.ts`、`runtime-config.ts`、`runtime-events.ts`、`runtime-logging.ts`、`runtime-media.ts`、`runtime-system.ts` 是 `PluginRuntime` 的基础能力组件。

`runtime-taskflow.ts`、`runtime-taskflow.types.ts`、`runtime-tasks.ts`、`runtime-tasks.types.ts`、`task-domain-types.ts` 是任务流与任务运行相关模块。

`gateway-request-scope.ts`、`gateway-bindings.ts`、`channel-runtime-contexts.ts` 是 Gateway / channel 请求上下文桥接层。

`metadata-registry-loader.ts`、`runtime-registry-loader.ts`、`standalone-runtime-registry-loader.ts`、`load-context.ts`、`runtime-cache.ts` 是加载、上下文和缓存相关模块。

`runtime-llm.runtime.ts`、`runtime-model-auth.runtime.ts`、`runtime-embedded-pi.runtime.ts`、`runtime-web-channel-plugin.ts`、`runtime-plugin-boundary.ts`、`native-deps.ts` 是更接近具体执行边界、模型认证、插件模块隔离和原生依赖解析的运行时模块。

同名 `*.test.ts` 文件覆盖各自模块，说明这里的行为边界较敏感，很多模块不是纯工具函数，而是插件兼容性、请求作用域和运行时合同的一部分。

## 关键入口

最重要的入口是 `src/plugins/runtime/index.ts`。从它的 imports 可以看到它把多个 `createRuntime*` 工厂组合起来，包括 `createRuntimeAgent`、`createRuntimeChannel`、`createRuntimeConfig`、`createRuntimeEvents`、`createRuntimeLogging`、`createRuntimeMedia`、`createRuntimeSystem`、`createRuntimeTaskFlow`、`createRuntimeTasks`。因此阅读这个目录时，应把 `index.ts` 理解为 `PluginRuntime` 的组装中心，而不是普通 barrel 文件。

`src/plugins/runtime/types.ts` 是运行时合同入口。外部多处通过 `import type { PluginRuntime } from "./runtime/types.js"` 或 Plugin SDK 再导出这个类型，例如 `src/plugin-sdk/channel-plugin-common.ts`、`src/plugin-sdk/plugin-test-runtime.ts`、`src/plugin-sdk/plugin-runtime.ts`。这说明 `PluginRuntime` 不是目录内部私有概念，而是插件作者和测试工具也会接触的公共合同。

`src/plugins/runtime/gateway-request-scope.ts` 是请求作用域入口。Gateway 层的 `src/gateway/server-methods.ts`、`src/gateway/server/plugins-http.ts`、`src/gateway/local-request-context.ts` 都引用它。根据当前片段推断，它负责在一次 Gateway 方法调用或 HTTP 插件路由处理中绑定当前插件 runtime，避免依赖全局状态泄露到错误请求。

`src/plugins/runtime/runtime-registry-loader.ts`、`src/plugins/runtime/standalone-runtime-registry-loader.ts` 是注册表运行时加载入口。前者面向已有 active registry 的运行时解析，后者被 `src/plugins/migration-provider-runtime.ts`、`src/plugins/tools.ts`、若干测试引用，说明它用于没有完整 Gateway 启动链路时的 standalone 场景。

## 主流程位置

主流程可以按“启动加载”和“请求执行”两条线理解。

启动加载线大致从 `src/gateway/server-plugin-bootstrap.ts`、`src/gateway/server-startup-plugins.ts` 进入插件注册表初始化，再通过 `src/plugins/runtime.ts` 保存或读取 active plugin registry 状态。随后需要真正执行插件时，运行时加载器进入 `src/plugins/runtime/runtime-registry-loader.ts` 或 `src/plugins/runtime/metadata-registry-loader.ts`。这条线的重点是：manifest 和 metadata 尽量先行，runtime 模块保持懒加载，避免在 discovery、inventory、setup-state 这类冷路径中过早导入重插件代码。

请求执行线大致从 Gateway 方法或插件 HTTP 路由进入，例如 `src/gateway/server-methods.ts`、`src/gateway/server/plugins-http.ts`、`src/gateway/server.impl.ts`。这些位置会借助 `withPluginRuntimeGatewayRequestScope` 或 `getPluginRuntimeGatewayRequestScope` 把当前请求的 runtime 上下文传下去。执行过程中，如果需要 channel 能力，会进入 `runtime-channel.ts` 和 `channel-runtime-contexts.ts`；如果需要模型认证或 LLM 能力，会进入 `runtime-model-auth.runtime.ts`、`runtime-llm.runtime.ts`；如果是任务类能力，则进入 `runtime-taskflow.ts`、`runtime-tasks.ts`。

Plugin SDK 暴露线也很重要。`src/plugin-sdk/index.ts`、`src/plugin-sdk/plugin-runtime.ts`、`src/plugin-sdk/plugin-test-runtime.ts` 会从这里再导出类型或测试辅助能力，所以这里的类型和函数变化可能影响插件作者，而不只是 core 内部。

## 推荐阅读顺序

建议先读 `src/plugins/AGENTS.md`，建立 control plane 与 runtime plane 的边界意识。这个目录最容易读错的地方，就是把“插件发现/配置/manifest”与“插件执行/runtime API”混成一套逻辑。

然后读 `src/plugins/runtime/types.ts`、`src/plugins/runtime/types-core.ts`、`src/plugins/runtime/types-channel.ts`，先看 `PluginRuntime` 暴露了哪些能力。类型比实现更适合作为地图，因为它会告诉你插件最终能拿到什么，而不是陷入加载细节。

第三步读 `src/plugins/runtime/index.ts`，看 runtime 如何由 `createRuntimeAgent`、`createRuntimeChannel`、`createRuntimeConfig`、`createRuntimeEvents`、`createRuntimeLogging`、`createRuntimeMedia`、`createRuntimeSystem`、`createRuntimeTaskFlow`、`createRuntimeTasks` 组装出来。

第四步读 `gateway-request-scope.ts`、`gateway-bindings.ts`、`channel-runtime-contexts.ts`，理解 Gateway 请求、channel 上下文与 plugin runtime 的桥接方式。

第五步再读 `runtime-registry-loader.ts`、`metadata-registry-loader.ts`、`standalone-runtime-registry-loader.ts`、`load-context.ts`，理解什么时候只读 metadata，什么时候真的加载 runtime 模块。

最后按需求进入专项模块：channel 看 `runtime-channel.ts`；模型认证看 `runtime-model-auth.runtime.ts`；LLM 看 `runtime-llm.runtime.ts`；任务流看 `runtime-taskflow.ts` 和 `runtime-tasks.ts`；Web channel 插件看 `runtime-web-channel-plugin.ts` 和 `runtime-plugin-boundary.ts`。

## 常见误区

第一个误区是把 `src/plugins/runtime` 当作整个插件系统入口。它不是插件发现和 manifest 校验的总入口，而是插件真正运行时的能力层。发现、manifest、setup、registry assembly 还分布在 `src/plugins` 的其他文件中。

第二个误区是以为这里应该“加载所有插件再判断”。上级规则明确要求保持 laziness，metadata、light exports、typed contracts 足够时不应导入 heavy runtime surface。阅读 `metadata-registry-loader.ts` 与 `runtime-registry-loader.ts` 时，要特别注意这条边界。

第三个误区是把 active registry 全局状态当成理想模型。`src/plugins/AGENTS.md` 提醒 mutable global runtime registry state 更像兼容脚手架，新增请求执行流程应优先考虑 immutable 或 request-scoped handles。`gateway-request-scope.ts` 的存在正是为了避免请求期过度依赖散落的全局状态。

第四个误区是直接从 core 深读插件内部实现。这个仓库规则要求 core 与插件通过 Plugin SDK、manifest metadata、runtime helpers、documented barrels 交互。研究这里时应关注合同和边界，不应把某个 bundled plugin 的私有实现当成通用规则。

第五个误区是忽略测试文件。这里的 `*.test.ts` 很多不是简单单元测试，而是在保护请求作用域、runtime config、registry loader、taskflow、logging、model auth 等兼容边界。理解主流程时，测试文件能帮助确认哪些行为属于稳定合同。
