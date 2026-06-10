# 目录：packages/coding-agent/src/core/extensions

## 它负责什么

`packages/coding-agent/src/core/extensions` 是 `coding-agent` 的扩展系统核心层，负责把外部扩展模块接入到 agent 运行时。它不直接实现某个具体扩展，而是定义“扩展能做什么”和“扩展如何进入主流程”：加载扩展文件、创建扩展 API、保存扩展注册的事件处理器、工具、命令、快捷键、CLI flag、消息渲染器和 provider，然后在会话运行过程中由 `ExtensionRunner` 统一调度。

这个目录的边界比较清晰：`loader.ts` 负责“发现和加载”，`runner.ts` 负责“运行和派发”，`types.ts` 负责“扩展契约”，`wrapper.ts` 负责“把扩展工具适配成 agent-core 工具”，`index.ts` 负责对外导出。它属于核心基础设施，不关心交互界面具体怎么画，也不关心模型请求具体怎么发送；这些能力通过 runtime actions、UI context、session manager、model registry 等邻近模块注入进来。

扩展的典型能力包括：监听 agent 生命周期事件、拦截或补充工具调用流程、注册 LLM 可调用工具、注册 slash command、注册快捷键、扩展 CLI 参数、注册自定义 provider、定制消息渲染、读取或操作当前 session 状态、在 interactive 模式中调用 UI primitives。

## 直接子目录地图

这个目标目录当前没有直接子目录，是一个平面模块目录：

`index.ts`：扩展系统的公共导出门面。它重导出 loader、runner、wrapper 的主要函数和大量 `types.ts` 类型，让外部代码或扩展作者从统一入口拿到 API 类型。

`types.ts`：最大、最核心的类型定义文件。它定义 `ExtensionAPI`、`ExtensionContext`、`ExtensionRuntime`、`Extension`、`ToolDefinition`、各种事件类型、事件返回类型、UI context、命令、快捷键、provider config、message renderer、工具调用与工具结果类型等。阅读扩展能力边界时先看这里。

`loader.ts`：扩展加载器。它用 `jiti` 加载 TypeScript 或 JavaScript 扩展模块，创建扩展对象和扩展 API，并支持标准位置发现、显式路径加载、目录 manifest、内联 factory 加载等路径。

`runner.ts`：扩展执行器。`ExtensionRunner` 保存已加载扩展，绑定核心运行时动作，创建事件上下文，派发扩展事件，处理错误监听、快捷键冲突、命令解析、provider 注册刷新、session 替换后的 stale context 防护等。

`wrapper.ts`：工具适配层。它把扩展注册的 `ToolDefinition` 包装为 `@earendil-works/pi-agent-core` 可执行的 `AgentTool`，并确保工具执行时拿到与事件处理器一致的 `ExtensionContext`。

## 关键入口

`discoverAndLoadExtensions` 是面向正常启动流程的加载入口。它会从项目本地配置目录下的 `extensions`、全局 agent 目录下的 `extensions`、以及 CLI 或 settings 显式配置的路径中发现扩展。目录发现规则是：直接加载 `.ts` 或 `.js` 文件；子目录优先看 `package.json` 里的 `pi.extensions`；否则看 `index.ts` 或 `index.js`。发现后交给 `loadExtensions` 统一加载，并用 resolved path 去重。

`loadExtensions` 是更底层的批量加载入口。它接受扩展路径列表、cwd、可选 `EventBus` 和可选 `ExtensionRuntime`，逐个调用内部的 `loadExtension`。每个扩展模块必须导出一个 factory function；加载成功后会创建 `Extension` 容器，再调用 factory，把 `ExtensionAPI` 传给扩展完成注册。

`loadExtensionFromFactory` 是测试、SDK 或内联扩展场景的入口。它绕过文件发现，直接从 `ExtensionFactory` 创建 `Extension`。根据当前片段推断，`DefaultResourceLoader` 的 `extensionFactories` 选项会把这种内联扩展并入资源加载流程。

`createExtensionRuntime` 创建共享 runtime。扩展加载阶段很多 action 还没有绑定到真实 session，所以 runtime 先提供抛错 stub；注册工具、注册 flag、注册 provider 这类加载期动作可以先写入 extension 或 pending queue。之后 `ExtensionRunner.bindCore` 会把真实的 `sendMessage`、`setModel`、`setActiveTools`、`registerProvider` 等动作接上。

`ExtensionRunner` 是运行期入口。它接收 `extensions`、`runtime`、`cwd`、`SessionManager`、`ModelRegistry`，然后由上层调用 `bindCore`、`bindCommandContext`、`setUIContext` 完成能力注入。后续事件派发、命令解析、快捷键读取、工具读取、消息渲染器查找都从这里走。

`wrapRegisteredTool` 和 `wrapRegisteredTools` 是扩展工具进入 agent-core 工具系统的入口。它们只做适配，不负责工具调用事件拦截；文件注释明确说明工具调用和结果拦截由 `AgentSession` 通过 agent-core hooks 处理。

## 主流程位置

启动主线在 `packages/coding-agent/src/main.ts` 附近。CLI 参数会先解析出 `--extensions`、`--skills`、`--prompt-templates`、`--themes` 等资源路径，并用 `resolveCliPaths` 转成相对当前 cwd 的路径。随后 `createAgentSessionServices` 被调用，资源加载参数里会传入 `additionalExtensionPaths`、`noExtensions` 和 `extensionFactories`。

资源装载主线在 `packages/coding-agent/src/core/resource-loader.ts`。`DefaultResourceLoader` 持有 `extensionsResult`，并在 reload 过程中加载扩展、技能、prompt、theme、上下文文件等资源。扩展加载结果通过 `getExtensions()` 暴露给后续 session 创建、help 输出、diagnostics 汇总等流程。

服务创建主线在 `packages/coding-agent/src/core/agent-session-services.ts`。`createAgentSessionServices` 创建 `SettingsManager`、`ModelRegistry`、`DefaultResourceLoader`，然后执行 `resourceLoader.reload()`。扩展在加载期注册的 provider 会先进入 `runtime.pendingProviderRegistrations`，这里会尝试注册到 `ModelRegistry` 并清空 pending queue；扩展 CLI flag 值也在这里按已注册 flag 校验和写入 runtime。

会话运行主线根据当前片段推断在 `packages/coding-agent/src/core/sdk.ts`、`packages/coding-agent/src/core/agent-session-runtime.ts`、`packages/coding-agent/src/core/agent-session.ts` 一带完成衔接。证据是 `createAgentSessionFromServices` 调用 `createAgentSession`，`AgentSessionRuntime` 会在 session 切换、fork、shutdown 等节点调用扩展事件辅助函数，`InteractiveMode` 会读取 `ExtensionRunner` 的快捷键、UI context 和 user bash 事件。换句话说，`extensions` 目录本身提供机制，真正触发点散布在 session runtime、agent session、interactive mode 和 resource loader 中。

## 推荐阅读顺序

第一步读 `index.ts`，先确认这个目录对外暴露了哪些能力。这里不用深读所有类型名，只需要建立“loader、runner、types、wrapper”四块结构。

第二步读 `types.ts` 的顶部注释、`ExtensionAPI`、`ExtensionContext`、`ExtensionRuntime`、`Extension`、事件类型分组。这个文件决定扩展作者能注册什么、事件 handler 能收到什么、handler 能返回什么。

第三步读 `loader.ts`，重点看 `createExtensionRuntime`、`createExtensionAPI`、`loadExtensions`、`discoverAndLoadExtensions`。这能回答“扩展文件从哪里来”“扩展 factory 什么时候执行”“注册动作写到哪里”“加载期不能调用哪些 runtime action”。

第四步读 `runner.ts`，重点看 `ExtensionRunner` 的构造、`bindCore`、`bindCommandContext`、`setUIContext`、`getAllRegisteredTools`、`getFlags`、`getShortcuts`、事件 emit 方法和 `createContext`。这能回答“扩展注册后的内容如何在真实会话里生效”。

第五步读 `wrapper.ts`，再去邻近的 `packages/coding-agent/src/core/tools/tool-definition-wrapper.ts`，理解扩展工具如何适配为 agent-core 的工具执行协议。

第六步沿主流程读 `packages/coding-agent/src/core/resource-loader.ts`、`packages/coding-agent/src/core/agent-session-services.ts`、`packages/coding-agent/src/main.ts`，最后再看 `InteractiveMode` 中 UI context、快捷键和 user bash 事件的绑定位置。

## 常见误区

不要把 `loader.ts` 理解成运行期调度器。它只负责发现、导入和执行扩展 factory，让扩展完成注册；事件何时触发、上下文如何创建、错误如何上报，主要是 `runner.ts` 的职责。

不要以为扩展加载时就能调用所有 agent action。`createExtensionRuntime` 在加载阶段给很多动作放的是未初始化 stub；例如发送消息、切换模型、读写 session 等依赖真实 session 的能力，必须等 `ExtensionRunner.bindCore` 后才能安全使用。加载期适合做注册，不适合做会话操作。

不要忽略 pending provider 注册。扩展可以在加载期注册 provider，但此时 `ModelRegistry` 可能还没有完成绑定，所以 provider 注册会先进 `pendingProviderRegistrations`，之后由 services 创建或 runner bind 阶段刷新。

不要把扩展工具包装和工具事件拦截混为一谈。`wrapper.ts` 只把扩展工具变成 `AgentTool` 并注入 context；工具调用前后事件、结果处理等不是在 wrapper 里完成的。

不要认为这个目录会处理所有 UI 行为。`types.ts` 定义 `ExtensionUIContext`，`runner.ts` 提供 no-op fallback 和 setter；interactive 模式里的真实 UI 实现位于 `packages/coding-agent/src/modes/interactive/interactive-mode.ts`。

不要按每个事件逐个死记。更有效的方式是先按生命周期分组：加载注册、session 生命周期、agent turn、provider request/response、tool call/result、message rendering、resources discovery、input/user bash、project trust。事件名很多，但主轴是“扩展声明 handler，runner 在对应业务节点 emit”。
