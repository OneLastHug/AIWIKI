# 文件：packages/coding-agent/src/core/extensions/index.ts

## 一句话定位

`packages/coding-agent/src/core/extensions/index.ts` 是 coding-agent 扩展系统的统一导出入口，也就是内部模块和包级 API 对外暴露扩展能力时使用的 barrel 文件；它本身不承载加载、运行或事件分发逻辑，而是把 `loader.ts`、`runner.ts`、`types.ts`、`wrapper.ts` 以及少量相邻类型重新汇总成稳定入口。

## 它暴露/定义了什么

这个文件没有定义新的业务类型或函数，核心职责是 re-export。它暴露的内容大致分四类：

第一类是扩展加载相关 API：`createExtensionRuntime`、`discoverAndLoadExtensions`、`loadExtensionFromFactory`、`loadExtensions`，来源于 `packages/coding-agent/src/core/extensions/loader.ts`。这些函数负责创建扩展运行时、发现扩展路径、用 `jiti` 加载 TypeScript 扩展模块，以及从 factory 构造扩展对象。

第二类是扩展执行器：`ExtensionRunner` 以及 `ExtensionErrorListener`、`NewSessionHandler`、`ForkHandler`、`NavigateTreeHandler`、`SwitchSessionHandler`、`ShutdownHandler` 等 handler 类型，来源于 `runner.ts`。这是扩展事件分发、上下文创建、session 生命周期操作和错误收集的核心执行层。

第三类是大量扩展公开协议类型，来源于 `types.ts`。其中包括 `ExtensionAPI`、`ExtensionContext`、`ExtensionRuntime`、`ExtensionFactory`、`ExtensionEvent`、各类 agent/session/tool/input/provider/message 事件、事件返回值、UI context、命令、快捷键、flag、自定义工具、provider 注册、message renderer、resource discovery 等。对扩展作者来说，这些就是 `@earendil-works/pi-coding-agent` 暴露的主要类型表面。

第四类是工具适配函数：`wrapRegisteredTool`、`wrapRegisteredTools`，来源于 `wrapper.ts`，用于把扩展注册的 `ToolDefinition` 包装成 agent-core 可执行的 `AgentTool`。

此外，它还转出 `SlashCommandInfo`、`SlashCommandSource`、`SourceInfo`，让扩展和 SDK 使用方能在同一个入口拿到命令来源、源码来源等元信息类型。

## 谁调用它

直接调用或导入这个入口的主要是包内聚合层和运行核心。`packages/coding-agent/src/core/index.ts` 从这里转出 `discoverAndLoadExtensions`、`ExtensionRunner` 等，形成 core 层的公开入口；`packages/coding-agent/src/index.ts` 又继续从 core 扩展入口转出这些 API，使外部扩展示例可以通过 `@earendil-works/pi-coding-agent` 导入 `ExtensionAPI`、`defineTool`、`ExtensionContext` 等。

运行时侧，`packages/coding-agent/src/core/sdk.ts` 从这里导入 `ExtensionRunner`、`LoadExtensionsResult`、`SessionStartEvent`、`ToolDefinition` 等，用于 SDK 创建 agent session 时挂接扩展。`packages/coding-agent/src/core/agent-session.ts` 导入 `ExtensionRunner` 和 `wrapRegisteredTools`，把加载后的扩展工具并入 agent 的工具集合。`packages/coding-agent/src/modes/interactive/interactive-mode.ts`、`packages/coding-agent/src/modes/rpc/rpc-mode.ts` 也从这里拿扩展相关类型和 runner，用于 UI 快捷键、命令诊断、RPC 模式下的扩展能力暴露。

另外，`resource-loader.ts` 没有通过这个 barrel，而是直接导入 `extensions/loader.ts`，说明资源发现/重载路径更贴近加载器实现。

## 它调用谁

严格说，`index.ts` 不“调用”任何运行时代码；它只通过静态 `export ... from` 建立模块依赖。它依赖的模块包括：

`../slash-commands.ts` 提供 slash command 的信息类型；`../source-info.ts` 提供来源标识；`./loader.ts` 提供扩展加载和 runtime 创建；`./runner.ts` 提供扩展执行器和生命周期 handler 类型；`./types.ts` 提供扩展系统的完整类型协议、类型守卫和 `defineTool`；`./wrapper.ts` 提供扩展工具到 agent-core 工具的包装。

根据当前片段推断，`index.ts` 被设计为避免扩展作者直接理解内部文件布局的稳定边界。依据是 `loader.ts` 中存在注释说明扩展可从 `@earendil-works/pi-coding-agent` 导入，而 loader 又通过虚拟模块把该包名映射到包入口。

## 核心流程

这个文件本身没有控制流，但它承接了扩展系统的典型使用流程。

启动或 SDK 创建 session 时，调用方通过 `discoverAndLoadExtensions` 或 `loadExtensions` 获取 `LoadExtensionsResult`。加载器为每个扩展创建 `ExtensionAPI`，扩展在加载期通过 `api.on`、`api.registerTool`、`api.registerCommand`、`api.registerShortcut`、`api.registerFlag`、`api.registerProvider` 等注册能力。随后 `AgentSession` 构造 `ExtensionRunner`，把加载结果、UI context、session manager、model registry、核心动作绑定进去。

agent 运行时，`ExtensionRunner` 负责创建 `ExtensionContext`，并在 agent 生命周期、tool call、tool result、input、message、session 切换、project trust、resources discovery 等事件点调用扩展注册的 handler。扩展注册的工具会经 `wrapRegisteredTools` 转为 agent-core 的工具对象，使工具执行时能拿到 runner 生成的统一扩展上下文。

所以 `index.ts` 是流程入口的“目录页”，不执行流程，但决定哪些流程节点对内部和外部可见。

## 关键函数的高层作用

`createExtensionRuntime` 创建加载期可用的共享 runtime。加载阶段动作方法大多是未初始化 stub，等 `ExtensionRunner` 或 `AgentSession` 绑定核心能力后才可真正执行；这避免扩展在加载时调用需要 session 的动作。

`discoverAndLoadExtensions` 负责从配置、路径或约定位置发现扩展并加载，适合 CLI/应用启动路径。

`loadExtensions` 负责按给定路径加载扩展集合，适合资源重载、SDK 或测试构造明确扩展列表。

`loadExtensionFromFactory` 适合已经拿到 factory 的场景，例如 SDK 内联扩展，不需要从文件系统路径动态加载。

`ExtensionRunner` 是运行期枢纽，负责事件分发、错误捕获、上下文创建、命令/工具/快捷键/flag 聚合，以及将扩展动作委托给 agent session 的核心实现。

`wrapRegisteredTool` 和 `wrapRegisteredTools` 只做适配：把扩展注册格式转换成 agent-core 可执行工具，并保证执行时使用 `runner.createContext()`。

`defineTool` 和各种 `isXToolResult` 类型守卫来自 `types.ts`，主要提升扩展作者定义工具和识别内置工具结果时的类型安全。

## 修改风险

最大风险是 API 表面破坏。这个文件是 `@earendil-works/pi-coding-agent` 扩展能力的重要转出口，删除或重命名任何 export 都可能影响外部扩展示例、第三方扩展、SDK 示例，以及包内从 `./core/extensions/index.ts` 导入的模块。

第二个风险是循环依赖。`loader.ts` 会静态导入包入口并把 `@earendil-works/pi-coding-agent` 提供给扩展虚拟模块；文件内注释明确提到需要避免 circular dependency。调整 `index.ts` 的 re-export 范围时，要检查是否把 loader 不该依赖的实现也绕回包入口。

第三个风险是类型与运行时导出的边界。这里大量使用 `export type`，可避免运行时代码被引入；若把纯类型误改成普通 `export`，可能改变打包结果、触发额外依赖加载，尤其影响 Bun binary 和 jiti 加载扩展的环境。

第四个风险是工具协议不一致。`wrapRegisteredTools`、`ToolDefinition`、`RegisteredTool`、`ExtensionContext` 分布在不同文件，但通过这里形成单一入口。修改导出时要同步检查 `agent-session.ts`、`sdk.ts`、interactive/rpc modes 和 examples 中的导入，否则会出现编译层面或扩展运行期断裂。
