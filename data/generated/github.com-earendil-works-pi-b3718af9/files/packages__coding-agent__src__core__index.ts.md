# 文件：packages/coding-agent/src/core/index.ts

## 一句话定位

`packages/coding-agent/src/core/index.ts` 是 `core` 子系统的聚合出口文件，用来把会话运行时、服务装配、bash 执行器、压缩结果、事件总线、实验特性、扩展系统和 source info 等核心能力集中 re-export；它本身不承载业务流程，更像是面向内部或潜在子路径消费者的稳定导出清单。

## 它暴露/定义了什么

这个文件没有定义新的类、函数或状态，只通过 `export ... from` 暴露若干核心模块：

- 会话主体：`AgentSession` 以及 `AgentSessionConfig`、`AgentSessionEvent`、`PromptOptions`、`SessionStats` 等类型，来自 `packages/coding-agent/src/core/agent-session.ts`。
- 会话运行时：`AgentSessionRuntime`、`createAgentSessionRuntime`、`CreateAgentSessionRuntimeFactory` 等，来自 `agent-session-runtime.ts`。
- 会话服务装配：`createAgentSessionServices`、`createAgentSessionFromServices`、`AgentSessionServices`、`AgentSessionRuntimeDiagnostic` 等，来自 `agent-session-services.ts`。
- 命令执行能力：`executeBashWithOperations`、`BashExecutorOptions`、`BashResult`，来自 `bash-executor.ts`。
- 上下文压缩结果类型：`CompactionResult`，来自 `compaction/index.ts`。
- 事件总线：`createEventBus`、`EventBus`、`EventBusController`。
- 实验特性判断：`areExperimentalFeaturesEnabled`。
- 扩展系统的大量类型和工具：`defineTool`、`discoverAndLoadExtensions`、`ExtensionRunner`、各类 session/turn/tool 事件类型、命令上下文、UI 上下文、工具定义等。
- source info 辅助：`createSyntheticSourceInfo`。

它暴露的是核心运行层能力的“精选集合”。与 `packages/coding-agent/src/index.ts` 相比，这里没有导出 CLI 参数、配置路径、认证存储、模型注册表、资源加载器、工具工厂、完整 SDK 等更多包级 API，因此范围更窄、更偏运行时核心。

## 谁调用它

根据当前片段推断，仓库内没有直接调用这个文件：检索 `core/index`、`from "./core"`、`from "../core"` 以及 `@earendil-works/pi-coding-agent/core` 没有发现匹配。依据是本地源码中引用核心能力时，大多直接导入具体模块，例如 `packages/coding-agent/src/main.ts` 从 `./core/agent-session-runtime.ts`、`./core/agent-session-services.ts` 等路径取用；测试也多直接导入 `../src/core/agent-session.ts`、`../src/core/sdk.ts`、`../src/core/extensions/index.ts`。

因此这个文件更可能是一个内部 barrel，供未来代码、构建产物、外部未纳入当前仓库的消费者，或历史遗留导入路径使用。还需要注意，`packages/coding-agent/package.json` 当前只声明包根 `.` 的导出到 `dist/index.js`，没有显式声明 `./core` 子路径导出；所以从 npm 包角度看，它未必是正式公开 API，除非构建或运行环境另有约定。

## 它调用谁

严格说，这个文件不“调用”任何函数。它只静态依赖并转发这些模块的导出：

`agent-session.ts`、`agent-session-runtime.ts`、`agent-session-services.ts`、`bash-executor.ts`、`compaction/index.ts`、`event-bus.ts`、`experimental.ts`、`extensions/index.ts`、`source-info.ts`。

模块加载时，JavaScript/TypeScript 的 re-export 会让这些目标模块成为依赖图的一部分，但 `index.ts` 自己没有执行核心逻辑，也没有创建 session、加载扩展、执行 bash 或触发事件。

## 核心流程

这个文件的核心流程可以理解为“导出聚合流程”，而不是运行时流程：

1. 上层代码如果从 `core/index.ts` 导入某个符号，TypeScript/打包器解析到该 barrel 文件。
2. `core/index.ts` 把符号继续转发到真实实现模块，例如 `AgentSessionRuntime` 转发到 `agent-session-runtime.ts`，`ExtensionRunner` 转发到 `extensions/index.ts`。
3. 实际业务仍在目标模块中完成：会话创建、运行时切换、服务重建、扩展加载、事件派发、bash 执行等，都不在本文件内发生。
4. 这个文件维护的是 API 边界：哪些核心能力可以通过一个统一入口被访问，哪些只能直接从具体模块访问。

从整体架构看，它位于 CLI/TUI/RPC/SDK 之下、具体核心模块之上。它不协调控制流，但影响导入边界和类型可见性。

## 关键函数的高层作用

`AgentSession` 是编码代理会话的核心对象，承载一次会话中的 agent 状态、消息、工具、扩展 runner、session manager 等能力。它通常是交互模式、print 模式、RPC 模式最终操作的会话实体。

`createAgentSessionRuntime` 创建初始 `AgentSessionRuntime`。它接收一个运行时工厂和初始 `cwd`、`agentDir`、`SessionManager`，先校验 session cwd，再创建 session 与服务，并把工厂保存在 runtime 中，供后续 `/new`、`/resume`、`/fork`、导入 JSONL 等会话替换流程复用。

`AgentSessionRuntime` 管理“当前 session + cwd 绑定服务”的生命周期。它负责 session 切换、创建新 session、fork、导入会话和 dispose；切换前会触发扩展的 `session_before_switch` 或 `session_before_fork`，切换时会发出 `session_shutdown`，再创建新 runtime 并让宿主重新绑定 session。修改它会影响交互模式和 RPC 等长期运行场景。

`createAgentSessionServices` 负责创建一组与当前 cwd 绑定的基础服务，包括 `AuthStorage`、`SettingsManager`、`ModelRegistry`、`DefaultResourceLoader`，并处理扩展注册 provider、扩展 flag 诊断等。它不直接创建 `AgentSession`，是为了让调用方先基于服务解析模型、工具和资源选项。

`createAgentSessionFromServices` 把已经创建好的 services 传给 `createAgentSession`，生成真正的会话对象。它是服务装配和会话实例化之间的桥。

`executeBashWithOperations` 是 bash 执行器的统一出口，底层实际行为在 `bash-executor.ts` 中，通常服务于 bash 工具执行、输出收集和操作抽象。

`createEventBus` 提供轻量事件总线，供核心模块或宿主层注册监听、派发事件。`defineTool`、`discoverAndLoadExtensions`、`ExtensionRunner` 是扩展系统的关键入口，分别对应定义工具、发现加载扩展、运行扩展事件/命令/工具逻辑。

`createSyntheticSourceInfo` 用于构造合成来源信息，常见于测试、SDK 或没有真实文件来源但仍需标注 source 的场景。

## 修改风险

这个文件的主要风险不在算法，而在导出边界。删除或改名某个导出，即使当前仓库内没有直接引用，也可能破坏外部消费者、生成后的类型声明，或扩展加载中对包 API 的假设。尤其是 `Extension`、`ToolDefinition`、`ExtensionRunner`、`AgentSessionRuntime` 这类类型和类，属于跨模块协作的契约。

新增导出看似安全，但会扩大可见 API。若未来这些符号被外部依赖，就会形成兼容性负担；虽然仓库规则说“不默认保留向后兼容”，但包级 API 的变化仍应有明确意图。

从 `extensions/index.ts` 批量 re-export 的类型很多，最容易产生命名冲突或重复导出问题。修改扩展系统导出时，需要同时检查 `packages/coding-agent/src/index.ts`，因为包根入口也大量转发扩展类型和工具；两个入口若不一致，使用者会遇到“从根入口可用、从 core 入口不可用”或相反的问题。

还要注意这是 TypeScript ESM 项目，所有导出路径都带 `.ts` 后缀。改路径、移动文件或新增 barrel 时，需要保持构建配置和 Node strip-only 约束一致，避免产生运行时模块解析问题。

如果要调整这个文件，建议先判断目标是“收缩内部 barrel”还是“公开更多核心 API”。前者需要检索仓库内外使用方；后者需要同步考虑 `src/index.ts`、生成的声明文件、扩展 loader 对 `@earendil-works/pi-coding-agent` 的内置绑定，以及相关 SDK/扩展测试。
