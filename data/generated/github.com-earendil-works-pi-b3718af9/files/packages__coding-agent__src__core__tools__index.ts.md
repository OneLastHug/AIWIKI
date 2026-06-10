# 文件：packages/coding-agent/src/core/tools/index.ts

## 一句话定位

`packages/coding-agent/src/core/tools/index.ts` 是 `coding-agent` 内置工具系统的统一出口和轻量工厂层：它把 `read`、`bash`、`edit`、`write`、`grep`、`find`、`ls` 这些工具模块集中导出，并提供按名称或按工具集合创建 `ToolDefinition` / `AgentTool` 的入口。

## 它暴露/定义了什么

这个文件主要暴露三类内容。

第一类是各工具模块的公开 API 转发，包括 `createReadTool`、`createBashTool`、`createEditTool`、`createWriteTool`、`createGrepTool`、`createFindTool`、`createLsTool` 以及对应的 `createXToolDefinition`、`XToolOptions`、`XToolInput`、`XToolDetails` 等类型。它还转发 `truncate.ts` 里的截断工具函数和常量，以及 `file-mutation-queue.ts` 的 `withFileMutationQueue`。

第二类是本文件定义的工具聚合类型：`Tool` 是 `AgentTool<any>` 的别名，`ToolDef` 是 `ToolDefinition<any, any>` 的别名，`ToolName` 限定为七个内置工具名，`allToolNames` 是这些名称的集合，`ToolsOptions` 按工具名承载每个工具自己的 options。

第三类是工厂函数：`createToolDefinition`、`createTool`、`createCodingToolDefinitions`、`createReadOnlyToolDefinitions`、`createAllToolDefinitions`、`createCodingTools`、`createReadOnlyTools`、`createAllTools`。

## 谁调用它

直接调用方主要有三类。

`packages/coding-agent/src/core/agent-session.ts` 调用 `createAllToolDefinitions` 构造 `_baseToolDefinitions`。这些定义之后会进入 `_refreshToolRegistry`，再和扩展工具、自定义工具合并，最终形成运行时的 `_toolRegistry` 和激活工具列表。

`packages/coding-agent/src/core/sdk.ts` 和 `packages/coding-agent/src/index.ts` 把这里的工具工厂和类型继续作为 SDK / 包入口导出，供外部以编程方式创建工具或注册自定义运行环境。

`packages/coding-agent/src/modes/interactive/components/tool-execution.ts` 调用 `createAllToolDefinitions(cwd)` 获取内置工具的渲染定义，用于 TUI 中展示工具调用和工具结果。根据当前片段推断，这里并不负责执行工具，而是复用内置定义里的 `renderCall`、`renderResult`、`renderShell` 等渲染能力。

## 它调用谁

这个文件运行时调用的对象都来自同目录下的具体工具模块：`bash.ts`、`edit.ts`、`find.ts`、`grep.ts`、`ls.ts`、`read.ts`、`write.ts`。`createToolDefinition` 和各类 `createXToolDefinitions` 调用对应模块的 `createXToolDefinition`；`createTool` 和各类 `createXTools` 调用对应模块的 `createXTool`。

它还依赖 `@earendil-works/pi-agent-core` 的 `AgentTool` 类型，以及 `packages/coding-agent/src/core/extensions/types.ts` 的 `ToolDefinition` 类型，用来统一内置工具和扩展工具的抽象边界。

## 核心流程

工具注册的核心流程可以概括为三段。

第一段是定义聚合。调用方传入 `cwd` 和可选 `ToolsOptions`，本文件根据工具名调用具体工具模块，生成 `ToolDefinition` 或 `AgentTool`。`cwd` 是所有工具的工作目录上下文，单个工具的配置则通过 `options?.read`、`options?.bash` 这类字段下发。

第二段是会话初始化。在 `AgentSession._buildRuntime` 中，如果没有 `baseToolsOverride`，会调用 `createAllToolDefinitions(this._cwd, { read: { autoResizeImages }, bash: { commandPrefix, shellPath } })`，生成七个内置工具定义，并保存到 `_baseToolDefinitions`。如果有 `baseToolsOverride`，则绕过这里的默认定义。

第三段是运行时注册。`AgentSession._refreshToolRegistry` 会把 `_baseToolDefinitions`、扩展注册的工具和 SDK 自定义工具合并成 definition registry，再通过 extension runner 包装为可执行的 `AgentTool`，写入 `_toolRegistry`。因此本文件不是最终调度器，它只负责“生产内置工具定义/实例”，实际启用、过滤、覆盖和执行由 `agent-session.ts` 负责。

## 关键函数的高层作用

`createToolDefinition(toolName, cwd, options)` 是按单个 `ToolName` 创建工具定义的入口。它用 `switch` 把名称分派到对应 `createXToolDefinition`，未知名称会抛错。这个函数适合需要动态按名称取定义的场景。

`createTool(toolName, cwd, options)` 与上面类似，但返回的是可执行 `AgentTool`，不是 `ToolDefinition`。它同样按名称分派到具体工具模块。

`createCodingToolDefinitions(cwd, options)` 返回默认编码场景的四个工具定义：`read`、`bash`、`edit`、`write`。它不包含 `grep`、`find`、`ls`。

`createReadOnlyToolDefinitions(cwd, options)` 返回只读场景的四个工具定义：`read`、`grep`、`find`、`ls`。它排除了会执行命令或修改文件的 `bash`、`edit`、`write`。

`createAllToolDefinitions(cwd, options)` 返回以工具名为 key 的完整定义对象，包含七个内置工具。`agent-session.ts` 使用的是这个函数，因此它对内置工具集合的完整性最关键。

`createCodingTools`、`createReadOnlyTools`、`createAllTools` 是对应的 `AgentTool` 实例版本，主要面向 SDK 或需要直接执行工具的内部调用方。辅助性的 re-export 只负责转发模块 API，不承载业务流程。

## 修改风险

最大风险是新增、删除或重命名工具时漏改聚合层。`ToolName`、`allToolNames`、`ToolsOptions`、两个单工具 `switch`、三组 `ToolDefinition` 工厂、三组 `Tool` 工厂都需要保持一致；否则可能出现类型允许但运行时找不到、运行时有工具但 UI 没有渲染定义、SDK 导出不完整等问题。

第二个风险是工具集合语义变化。`createCodingToolDefinitions` 当前代表可读、可执行命令、可编辑、可写入的编码工具集；`createReadOnlyToolDefinitions` 当前代表不会修改文件或执行 shell 的只读工具集。如果把 `bash` 放入只读集合，或把 `grep/find/ls` 加入默认编码集合，会改变会话默认能力边界，影响安全策略、系统提示和用户预期。

第三个风险是 `cwd` 和 options 透传不一致。不同工具依赖自己的 options，例如 `bash` 会接收 shell 相关配置，`read` 会接收图片自适应配置。若聚合层漏传或传错字段，问题会表现为工具局部行为异常，但根因在这个分派文件。

第四个风险是 `createAllToolDefinitions` 的返回形状影响 `agent-session.ts` 和 TUI。`agent-session.ts` 会把它转为 `_baseToolDefinitions`，TUI 也按工具名索引内置渲染定义。因此修改返回 key、遗漏工具或改变定义类型，可能同时破坏运行时注册和交互界面展示。
