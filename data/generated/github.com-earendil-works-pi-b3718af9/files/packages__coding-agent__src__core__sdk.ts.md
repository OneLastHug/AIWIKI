# 文件：packages/coding-agent/src/core/sdk.ts

## 一句话定位

`packages/coding-agent/src/core/sdk.ts` 是 `coding-agent` 的 SDK 入口文件，负责把认证、模型、设置、会话、资源加载、扩展、工具和底层 `Agent` 组装成一个可直接使用的 `AgentSession`。

## 它暴露/定义了什么

这个文件主要定义并导出 `createAgentSession(options)`，以及围绕它的两个接口：

`CreateAgentSessionOptions` 描述创建会话时可注入或覆盖的依赖，包括 `cwd`、`agentDir`、`authStorage`、`modelRegistry`、`model`、`thinkingLevel`、`scopedModels`、`tools`、`excludeTools`、`noTools`、`customTools`、`resourceLoader`、`sessionManager`、`settingsManager`、`sessionStartEvent` 等。

`CreateAgentSessionResult` 返回创建好的 `AgentSession`、扩展加载结果 `extensionsResult`，以及可能出现的 `modelFallbackMessage`。这个 fallback 信息用于解释继续旧会话时原模型无法恢复、或当前没有可用模型的情况。

此外它也是 SDK 聚合出口之一，会 re-export `agent-session-runtime.ts`、`extensions/index.ts` 中的扩展类型、`prompt-templates.ts`、`skills.ts`、`tools/index.ts` 的类型，并显式导出 `createCodingTools`、`createReadOnlyTools`、`createReadTool`、`createBashTool`、`createEditTool`、`createWriteTool`、`createGrepTool`、`createFindTool`、`createLsTool`、`withFileMutationQueue`。这说明外部 SDK 使用者不仅能创建标准会话，也能复用内置工具工厂来构造自定义运行环境。

## 谁调用它

直接调用关系中，`packages/coding-agent/src/core/agent-session-services.ts` 引入 `createAgentSession` 和相关类型，用它作为默认的会话创建服务。`packages/coding-agent/src/core/agent-session-runtime.ts` 引入 `CreateAgentSessionResult`，说明运行时层依赖这里的返回契约。`packages/coding-agent/src/index.ts` 从该文件 re-export SDK 能力，把它提升为包级公共 API。

示例目录也大量使用它，例如 `packages/coding-agent/examples/sdk/09-api-keys-and-oauth.ts`、`packages/coding-agent/examples/sdk/10-settings.ts`、`packages/coding-agent/examples/sdk/12-full-control.ts`、`packages/coding-agent/examples/sdk/13-session-runtime.ts`。根据当前片段推断，CLI 主流程不一定直接调用 `createAgentSession`，而是通过 runtime/service 层间接使用；依据是 `packages/coding-agent/src/main.ts` 只搜索到导入 `CreateAgentSessionOptions` 类型，以及调用 `createAgentSessionRuntime`。

## 它调用谁

它向下连接了几类核心模块。

配置与路径层：`getAgentDir`、`resolvePath`、`SettingsManager`、`SessionManager`、`getDefaultSessionDir`，用于确定工作目录、全局 agent 目录、设置来源和会话存储位置。

认证与模型层：`AuthStorage`、`ModelRegistry`、`findInitialModel`、`formatNoModelsAvailableMessage`、`clampThinkingLevel`、`DEFAULT_THINKING_LEVEL`，用于恢复或选择模型，并把 thinking level 限制在模型能力范围内。

资源与扩展层：`DefaultResourceLoader`、`ResourceLoader`、`ExtensionRunner`、`LoadExtensionsResult`、`SessionStartEvent`、`ToolDefinition`，用于加载项目资源、扩展、扩展工具和启动事件上下文。

Agent 与消息层：`Agent`、`AgentMessage`、`streamSimple`、`convertToLlm`、`mergeProviderAttributionHeaders`。其中 `convertToLlm` 负责把 agent 内部消息转换为 LLM 请求消息，`streamSimple` 负责实际模型流式调用，provider attribution 相关逻辑用于合并供应商归因请求头。

工具层：`createReadTool`、`createBashTool`、`createEditTool`、`createWriteTool`、`createGrepTool`、`createFindTool`、`createLsTool`、`createCodingTools`、`createReadOnlyTools`、`withFileMutationQueue`。这些工具构成 agent 可执行文件读写、搜索、shell 等能力的基础。

## 核心流程

`createAgentSession` 的第一步是解析运行目录。它优先使用 `options.cwd`，其次使用 `options.sessionManager?.getCwd()`，最后落到 `process.cwd()`；`agentDir` 则来自传入参数或默认 `getAgentDir()`。随后它按需创建 `AuthStorage`、`ModelRegistry`、`SettingsManager`、`SessionManager`。如果调用方没有提供 `resourceLoader`，它会构造 `DefaultResourceLoader` 并执行 `reload()`，这一步是扩展、资源和项目上下文进入会话创建流程的入口。

第二步是恢复已有会话状态。它通过 `sessionManager.buildSessionContext()` 读取当前分支上下文，并检查是否存在历史消息、是否存在 `thinking_level_change` 条目。如果已有会话记录了模型，且 `ModelRegistry` 能找到该模型并确认认证可用，则恢复该模型；否则生成 `modelFallbackMessage`。如果仍没有模型，则调用 `findInitialModel`，按设置默认 provider、默认 model、默认 thinking level 和可用认证选择初始模型。没有模型时会返回无模型可用的提示。

第三步是确定 `thinkingLevel`。显式传入优先；继续会话时优先恢复会话里的 thinking level；否则使用设置默认值或 `DEFAULT_THINKING_LEVEL`。如果最终没有模型，thinking level 被置为 `"off"`；如果有模型，则通过 `clampThinkingLevel` 按模型能力收敛。

第四步是组装工具集合。默认启用的内置工具名是 `read`、`bash`、`edit`、`write`。`tools` 是 allowlist，`excludeTools` 是后置 denylist，`noTools` 可关闭全部工具或内置工具。根据当前片段推断，后续还会合并扩展工具和 `customTools`，并可能通过 `withFileMutationQueue` 串行化文件变更类工具；依据是文件导入了扩展 runner、工具工厂和 mutation queue，且 options 明确支持 `customTools`。

第五步是创建底层 `Agent` 和 `AgentSession`。文件中出现了 `convertToLlmWithBlockImages` 包装函数：它先调用 `convertToLlm`，再根据 `settingsManager.getBlockImages()` 动态过滤图片内容。这是防御性处理，保证会话中途修改 block images 设置也能影响后续请求。根据当前片段推断，`Agent` 会使用这个转换函数、选定模型、thinking level、streaming provider 调用和工具列表；最后这些依赖被传入 `AgentSession`，形成 SDK 返回值。

## 关键函数的高层作用

`createAgentSession` 是唯一需要重点理解的函数。它不是单纯构造对象，而是一个组合根：负责创建默认依赖、加载资源、恢复历史状态、选择模型、收敛 thinking level、配置工具、处理图片阻断策略，并返回可运行的 `AgentSession`。因此它位于 CLI、SDK 示例、runtime service 和底层会话执行之间，是外部使用者进入 coding agent 能力的主要门面。

`getDefaultAgentDir` 只是薄包装，返回 `getAgentDir()`，用于给 `agentDir` 提供默认值。

`convertToLlmWithBlockImages` 是 `createAgentSession` 内部局部函数，作用是在消息进入 LLM 前做格式转换和图片过滤。它的关键点是动态读取 `settingsManager.getBlockImages()`，不是只在会话创建时固定一次。

工具工厂 re-export 本身不是业务流程，但对 SDK 边界很重要：它允许外部代码复用 pi 的标准工具实现，同时仍能自行控制 cwd、工具列表和 session manager。

## 修改风险

最高风险是模型恢复与选择逻辑。`createAgentSession` 同时服务新会话、继续会话、显式模型、默认设置、认证可用性和无模型提示。改动 `findInitialModel` 调用参数、`modelFallbackMessage` 拼接或 `hasConfiguredAuth` 判断，可能导致 CLI 继续旧会话时静默换模型，或 SDK 使用者拿不到正确的失败说明。

第二类风险是会话上下文恢复。`sessionManager.buildSessionContext()`、`getBranch()`、`thinking_level_change` 的判断影响继续会话的模型和 thinking level。若这里误判，会出现历史会话与当前运行参数不一致的问题，尤其在分支、压缩、模型切换后更难排查。

第三类风险是工具过滤语义。`tools`、`excludeTools`、`noTools` 三者叠加决定 agent 能做什么。修改默认启用工具或过滤顺序，可能直接改变安全边界：例如本应只读的 SDK 会话获得 `bash` 或 `write`，或扩展工具被意外禁用。这里还牵涉 `ToolName`、扩展 `ToolDefinition` 和自定义工具，测试应覆盖 allowlist、denylist、`noTools: "all"`、`noTools: "builtin"` 的组合。

第四类风险是图片过滤。`convertToLlmWithBlockImages` 是“进入模型前”的最后一道约束。如果只在 UI 或消息写入层过滤，SDK、自定义 runtime 或扩展仍可能绕过；因此修改时应保留这里的 defense-in-depth 思路。

第五类风险是扩展与资源加载时机。`DefaultResourceLoader.reload()` 在会话创建早期执行，后续设置、工具、扩展事件都依赖它。提前、延后或跳过 reload，可能导致扩展命令、扩展工具、项目资源或 session start metadata 不完整。

最后，`sdk.ts` 是公共 API 聚合文件。删除或重命名 re-export 会影响包外使用者和示例，即使内部测试不直接失败也可能造成 SDK 破坏。修改时应同步检查 `packages/coding-agent/src/index.ts`、`packages/coding-agent/src/core/agent-session-services.ts`、`packages/coding-agent/examples/sdk` 下的示例，以及针对会话创建、工具过滤、模型 fallback、扩展加载的测试。
