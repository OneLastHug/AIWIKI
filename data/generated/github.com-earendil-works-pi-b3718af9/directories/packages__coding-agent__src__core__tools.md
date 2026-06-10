# 目录：packages/coding-agent/src/core/tools

## 它负责什么

`packages/coding-agent/src/core/tools` 是 `coding-agent` 内置工具层。它把 Agent 可调用的文件读取、命令执行、文件编辑、全文搜索、目录遍历等能力封装成统一的 `ToolDefinition` 和 `AgentTool`，供 `AgentSession` 注册到运行时，再由模型通过 tool call 调用。

这个目录不负责模型请求、会话持久化、扩展加载或交互式 UI 的整体调度；它主要负责三件事：定义工具参数 schema，执行工具逻辑，渲染工具调用和结果。每个核心工具通常都遵循相同形态：`Type.Object(...)` 定义输入参数，`createXToolDefinition(cwd, options)` 返回扩展系统认识的 `ToolDefinition`，`createXTool(cwd, options)` 再通过 `wrapToolDefinition` 转成 `@earendil-works/pi-agent-core` 使用的 `AgentTool`。

内置工具集合包括 `read`、`bash`、`edit`、`write`、`grep`、`find`、`ls`。默认激活工具不是全部，而是 `read`、`bash`、`edit`、`write`；`grep`、`find`、`ls` 属于可注册、可启用的只读探索工具。

## 直接子目录地图

这个目录当前没有直接子目录，是一个扁平模块目录。文件大致分为四组：

第一组是具体工具实现：`read.ts`、`bash.ts`、`edit.ts`、`write.ts`、`grep.ts`、`find.ts`、`ls.ts`。它们分别处理文件读取、shell 命令、局部替换编辑、完整写文件、文本搜索、文件查找、目录列举。

第二组是聚合和适配入口：`index.ts`、`tool-definition-wrapper.ts`。`index.ts` 统一导出所有工具、类型和批量创建函数；`tool-definition-wrapper.ts` 在 `ToolDefinition` 与 `AgentTool` 之间做适配。

第三组是工具共享基础设施：`path-utils.ts`、`truncate.ts`、`render-utils.ts`、`output-accumulator.ts`、`file-mutation-queue.ts`。它们提供路径解析、输出截断、终端渲染、增量输出累计、同一文件写入串行化等公共能力。

第四组是编辑辅助：`edit-diff.ts`。它服务于 `edit` 之类的文件变更工具，用来生成或呈现编辑差异；具体编辑入口仍在 `edit.ts`。

## 关键入口

最重要的入口是 `packages/coding-agent/src/core/tools/index.ts`。这里声明了 `ToolName = "read" | "bash" | "edit" | "write" | "grep" | "find" | "ls"`，并维护 `allToolNames`。外部如果只想按名称创建某个工具，会走 `createToolDefinition(toolName, cwd, options)` 或 `createTool(toolName, cwd, options)`；如果要批量创建，会走 `createCodingToolDefinitions`、`createReadOnlyToolDefinitions`、`createAllToolDefinitions`、`createCodingTools`、`createReadOnlyTools`、`createAllTools`。

`createCodingToolDefinitions` 和 `createCodingTools` 只包含默认编码能力：`read`、`bash`、`edit`、`write`。`createReadOnlyToolDefinitions` 和 `createReadOnlyTools` 包含 `read`、`grep`、`find`、`ls`。`createAllToolDefinitions` 和 `createAllTools` 才覆盖全部七个内置工具。

另一个关键入口是 `packages/coding-agent/src/core/tools/tool-definition-wrapper.ts`。`wrapToolDefinition` 把扩展层的 `ToolDefinition` 包装成 Agent 核心需要的 `AgentTool`，并把可选 `ExtensionContext` 传给工具的 `execute`。`createToolDefinitionFromAgentTool` 走反方向：当外部直接传入 `AgentTool` 覆盖内置工具时，它合成最小的 `ToolDefinition`，让 `AgentSession` 内部仍保持“definition-first”的注册模型。

## 主流程位置

主流程不在这个目录内部，而在 `packages/coding-agent/src/core/agent-session.ts` 和 `packages/coding-agent/src/core/sdk.ts`。

创建会话时，`packages/coding-agent/src/core/sdk.ts` 根据 `tools`、`excludeTools`、`noTools` 等选项决定初始激活工具名。默认情况下，初始激活列表是 `read`、`bash`、`edit`、`write`。然后 `AgentSession` 构建运行时。

在 `AgentSession._buildRuntime` 中，如果没有 `_baseToolsOverride`，会调用 `createAllToolDefinitions(this._cwd, { read: { autoResizeImages }, bash: { commandPrefix, shellPath } })` 创建全部内置工具定义。注意这里是“注册全部定义”，不是“激活全部工具”。随后 `_refreshToolRegistry` 会合并三类来源：内置工具定义、扩展注册工具、SDK 传入的 custom tools。扩展或自定义工具可以覆盖同名工具，因为后加入的 custom/extension definition 会写入同一个 registry map。

工具真正进入模型可用状态发生在 `setActiveToolsByName`。它从 `_toolRegistry` 里取出名字匹配的 `AgentTool`，写入 `this.agent.state.tools`，并重建 system prompt。`packages/coding-agent/src/core/system-prompt.ts` 根据当前工具名、`promptSnippet` 和 `promptGuidelines` 生成 “Available tools” 和指南文本。也就是说，工具是否“被模型看见”，取决于 active tool names 和对应 definition 是否提供 prompt snippet。

工具调用前后还有扩展钩子。`AgentSession._installAgentToolHooks` 设置 `beforeToolCall` 和 `afterToolCall`，分别触发扩展系统的 `tool_call`、`tool_result` 事件。根据当前片段推断，内置工具本身只负责执行和渲染，跨工具拦截、审计、改写结果由 `AgentSession` 与 extension runner 承担。

## 推荐阅读顺序

建议先读 `packages/coding-agent/src/core/tools/index.ts`，建立内置工具集合、批量创建函数和默认分组的概念。第二步读 `packages/coding-agent/src/core/tools/tool-definition-wrapper.ts`，理解 `ToolDefinition` 与 `AgentTool` 的边界。

第三步读一个代表性只读工具，例如 `packages/coding-agent/src/core/tools/read.ts`。它展示了完整结构：schema、operations 抽象、路径解析、文本或图片处理、截断、`renderCall`、`renderResult`。第四步读一个变更型工具，例如 `packages/coding-agent/src/core/tools/edit.ts` 或 `packages/coding-agent/src/core/tools/write.ts`，重点看 `withFileMutationQueue` 如何避免同一文件并发写入。第五步再读 `bash.ts`、`grep.ts`、`find.ts`、`ls.ts`，这些更偏执行外部命令或文件系统探索。

最后回到邻近主流程：读 `packages/coding-agent/src/core/agent-session.ts` 的 `_buildRuntime`、`_refreshToolRegistry`、`setActiveToolsByName`、`_installAgentToolHooks`，再读 `packages/coding-agent/src/core/system-prompt.ts` 的工具提示生成逻辑。这样能把“工具定义”与“会话中如何启用工具”连起来。

## 常见误区

一个误区是把 `createAllToolDefinitions` 理解成默认启用全部工具。实际它只是创建全部内置定义；默认 active tools 仍是 `read`、`bash`、`edit`、`write`，除非 CLI、SDK 或扩展流程改变激活列表。

第二个误区是以为 `grep`、`find`、`ls` 是 shell 命令的简单别名。它们确实可能依赖底层工具或本地操作，但在这里被包装成独立 tool，拥有自己的 schema、结果截断、渲染和 prompt 描述，和模型直接调用 `bash` 不同。

第三个误区是把路径安全和显示格式混在一起。`path-utils.ts` 负责解析读写路径，`render-utils.ts` 更偏结果展示；不要只看渲染出来的路径判断实际访问路径。

第四个误区是忽略 `operations` 选项。`read`、`edit`、`write`、`bash`、`grep`、`find`、`ls` 都暴露各自的 operations 类型或 options，说明这些工具可被替换成本地文件系统之外的执行环境。根据当前片段推断，这也是 SDK、测试或远程运行时复用工具定义的重要扩展点。

第五个误区是认为工具调用事件在每个工具文件里处理。实际 `tool_call` 和 `tool_result` 的扩展拦截在 `AgentSession` 安装的 hooks 中完成；工具文件只提供执行单元和渲染单元。
