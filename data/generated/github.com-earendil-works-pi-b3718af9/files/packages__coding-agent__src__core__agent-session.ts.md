# 文件：packages/coding-agent/src/core/agent-session.ts

## 一句话定位

`AgentSession` 是 `packages/coding-agent` 的核心会话门面：它把底层 `@earendil-works/pi-agent-core` 的 `Agent` 包装成可被 CLI、SDK、interactive、print、rpc 等运行模式复用的“完整会话运行时”，统一处理模型认证、消息提交、事件转发、会话持久化、工具注册、扩展系统、compaction、重试与 bash 执行。

## 它暴露/定义了什么

该文件主要定义并导出：

- `parseSkillBlock()` 与 `ParsedSkillBlock`：解析用户消息开头的 `<skill ...>` 块，把 skill 名称、位置、正文和后续用户消息拆出来。
- `AgentSessionEvent`、`AgentSessionEventListener`：在底层 `AgentEvent` 之上增加 session 级事件，例如 `queue_update`、`compaction_start`、`compaction_end`、`session_info_changed`、`thinking_level_changed`、`auto_retry_start/end`。
- `AgentSessionConfig`：构造 `AgentSession` 所需的依赖集合，包括 `Agent`、`SessionManager`、`SettingsManager`、`ResourceLoader`、`ModelRegistry`、工具白名单/黑名单、扩展 runner 引用等。
- `ExtensionBindings`：运行模式绑定扩展 UI、命令上下文、abort/shutdown/error 处理器时使用。
- `PromptOptions`：提交 prompt 时的控制项，包括是否展开 prompt template、图片、流式期间的排队方式、输入来源、preflight 回调。
- `ModelCycleResult`、`SessionStats` 等查询结果类型。
- `AgentSession` 类：文件的核心，承载会话生命周期和大多数跨模式能力。

根据文件头注释和构造逻辑，这个类被设计成“模式无关”的中间层：具体 I/O 由 mode 模块实现，而会话状态、模型、工具、扩展和持久化都收敛在这里。

## 谁调用它

直接创建 `AgentSession` 的路径根据当前片段和搜索结果推断主要经过 `packages/coding-agent/src/core/agent-session-services.ts`、`packages/coding-agent/src/core/sdk.ts`、`packages/coding-agent/src/main.ts` 这一层服务/SDK 工厂，而不是由终端模式直接手写构造。`main.ts` 会先组装 CLI 参数、服务、runtime factory，再调用 `createAgentSessionFromServices()` 和 `createAgentSessionRuntime()`。

对外用户通常通过 `createAgentSession()` 使用它，相关示例集中在 `packages/coding-agent/examples/sdk/*.ts`，例如 minimal、自定义模型、自定义工具、session 管理、extension、runtime 等示例。运行模式层根据文件头注释包括 interactive、print、rpc，它们把 `AgentSession` 当作业务会话对象，在其上挂接输入输出、UI、命令和事件展示。

文档 `packages/coding-agent/docs/json.md` 也引用了 `AgentSessionEvent`，说明 JSON/RPC 或事件输出模式依赖这里定义的事件结构。

## 它调用谁

`AgentSession` 的依赖非常集中，按职责可分为几类：

- 底层 agent：`@earendil-works/pi-agent-core` 的 `Agent`、`AgentEvent`、`AgentMessage`、`AgentTool`。`AgentSession` 订阅 agent 事件，安装 `beforeToolCall`、`afterToolCall` hook，并驱动模型生成。
- AI 层：`@earendil-works/pi-ai` 的 `Model`、`Message`、`streamSimple`、`resetApiProviders`、`isContextOverflow`、`cleanupSessionResources`、`clampThinkingLevel` 等。用于模型认证、上下文溢出判断、thinking level 管理和资源清理。
- 会话与设置：`SessionManager`、`SettingsManager`、`SessionHeader`、`CompactionEntry`、`BranchSummaryEntry` 等。用于保存消息、读取/更新 session 元数据、统计和 compaction 记录。
- compaction 子系统：`calculateContextTokens()`、`estimateContextTokens()`、`shouldCompact()`、`prepareCompaction()`、`compact()`、`generateBranchSummary()` 等。用于手动压缩、阈值自动压缩、溢出恢复和分支摘要。
- 扩展系统：`ExtensionRunner`、`wrapRegisteredTools()` 以及大量 extension event 类型。`AgentSession` 将输入、turn、message、tool、tree、compact、shutdown 等运行时事件发给扩展，并把扩展注册的工具合并进工具表。
- 工具系统：`createAllToolDefinitions()`、`createToolDefinitionFromAgentTool()`、`createLocalBashOperations()`、`executeBashWithOperations()`。用于构建内置工具、包装外部工具、执行 bash。
- prompt 与资源：`ResourceLoader`、`expandPromptTemplate()`、`buildSystemPrompt()`、`stripFrontmatter()`、`resolvePath()`。用于加载系统提示、资源扩展路径、上下文文件和模板。
- 输出辅助：`exportSessionToHtml()`、`createToolHtmlRenderer()`，用于会话导出和工具调用 HTML 渲染。

## 核心流程

构造阶段，`AgentSession` 保存传入的核心依赖，初始化模型范围、工具过滤规则、cwd、resource loader、model registry 等状态。随后它立刻订阅底层 `agent.subscribe(this._handleAgentEvent)`，安装工具 hook，并调用 `_buildRuntime()` 构建运行时工具表和 extension runner。也就是说，一旦实例创建完成，它就已经具备监听 agent、保存 session、拦截工具调用和向扩展发事件的能力。

提交 prompt 时，根据当前片段推断，`prompt()` 会先做模型与认证前置检查：没有模型时抛出 `formatNoModelSelectedMessage()`，没有 API key 或 OAuth 失效时通过 `_getRequiredRequestAuth()` 给出明确错误。然后它会处理 prompt template、图片、skill block、扩展输入事件、streaming 时的排队策略。若 agent 正在流式响应，`streamingBehavior` 决定新输入进入 steering 队列还是 follow-up 队列，并通过 `queue_update` 通知 UI。真正发给模型前，会保证系统 prompt、工具列表、thinking level、扩展追加内容等 runtime 状态是最新的。

agent 运行期间，`_handleAgentEvent` 是中心事件管道。它接收底层 `AgentEvent`，转成或补充为 `AgentSessionEvent`，通知 session listener；同时承担自动保存消息、触发扩展事件、检测上下文阈值、决定是否自动 compaction 或 retry 等副作用。`agent_end` 被扩展为包含 `messages` 和 `willRetry` 的事件，说明上层 UI 可以区分一次响应是彻底结束还是会进入自动重试。

工具调用时，`_installAgentToolHooks()` 把 `agent.beforeToolCall` 和后续结果 hook 指向当前 `ExtensionRunner`。这样扩展 reload 后不用重装 hook，因为回调运行时读取 `this._extensionRunner`。工具调用事件会先交给扩展的 `tool_call` / `tool_result` 处理器，扩展可以改写输入、输出、错误状态或附加 details。

compaction 流程由手动入口、阈值检查和上下文溢出恢复共同使用。它会估算或计算当前上下文 token，调用 `shouldCompact()` 判断是否需要压缩，再经 `prepareCompaction()`、`compact()` 生成压缩结果并写回 session。过程中通过 `compaction_start/end` 暴露状态，使用独立的 `AbortController` 支持取消。分支摘要则由 `collectEntriesForBranchSummary()` 和 `generateBranchSummary()` 辅助生成，用于 session tree 或 fork 相关展示，根据当前片段推断其依据是导入和字段 `_branchSummaryAbortController`。

bash 流程由 `executeBashWithOperations()` 和 `createLocalBashOperations()` 实现实际执行。`AgentSession` 保存 `_bashAbortController` 和 `_pendingBashMessages`，用来表达当前 bash 是否运行、能否取消，以及流式响应期间产生的 bash 输出如何延后写入 agent state/session，避免破坏 tool use 与 tool result 的消息顺序。

## 关键函数的高层作用

`parseSkillBlock(text)`：一个独立的小解析器，只识别完整包裹在消息开头的 `<skill name="..." location="...">...</skill>` 结构，并返回 skill 内容和可选的后续用户消息。它不做复杂 XML 解析，适合当前受控格式。

`constructor(config)`：建立会话对象的依赖边界，订阅 agent 事件，安装工具 hook，构建初始 runtime。它是模式层和核心 agent 之间的装配点。

`_getRequiredRequestAuth(model)`：从 `ModelRegistry` 获取 API key 和 headers，并把底层错误转换成面向用户的认证提示。它区分普通 API key 缺失和 OAuth 凭据失效，是 prompt 前置校验的关键。

`_getCompactionRequestAuth(model)`：为 compaction 请求准备认证。若 agent 使用默认 `streamSimple`，必须具备认证；若调用方自定义了 stream 函数，则允许认证缺失，体现 SDK 嵌入场景的兼容性。

`_installAgentToolHooks()`：把工具调用前后事件桥接到扩展系统。这个函数的关键设计是 hook 只安装一次，但每次执行读取当前 runner，从而支持扩展 reload。

`prompt(text, options)`：根据当前片段和导入推断，这是最核心的用户输入入口，负责 preflight、模板展开、队列策略、扩展事件、消息提交、模型调用和后续自动流程串联。任何调用方想让 agent 回答，最终都应经由这里或其同层封装。

`_handleAgentEvent(event)`：底层 agent 事件进入 session 世界的主通道。它不是单纯转发，而是会叠加 session 保存、扩展通知、自动压缩、重试、队列更新等会话级副作用。

`_buildRuntime(...)`：根据当前片段推断，它重建系统 prompt、工具定义、工具 registry 和 `ExtensionRunner`。它决定本轮 agent 能看到哪些工具、哪些扩展、哪些 prompt snippet/guideline。

compaction 相关方法：手动压缩、自动压缩、溢出恢复和分支摘要共享导入的 compaction 模块。高层作用是控制上下文长度，同时尽量保留可恢复的历史摘要。

bash 相关方法：负责运行 shell 命令、取消命令、把结果转成 `BashExecutionMessage`，并在安全的时机写入 agent state 和 session。

session/export/stats 相关方法：围绕 `SessionManager` 读取当前 session 文件、消息数、token、cost、上下文使用率，并可导出 HTML。这些是 `/session`、导出和诊断类功能的支撑。

## 修改风险

`AgentSession` 是高耦合的核心枢纽，修改风险主要来自副作用顺序。事件处理、session 保存、extension emit、auto compaction、retry、queue update 都可能发生在同一次 agent 生命周期内，调整 `_handleAgentEvent` 或 `prompt()` 顺序容易造成重复保存、UI 状态错乱、扩展事件缺失，或 `agent_end.willRetry` 语义不一致。

工具相关改动风险也很高。`_installAgentToolHooks()` 同时承担扩展拦截和工具结果改写，如果错误处理、`isError`、`details` 或输入覆盖逻辑变化，可能影响所有内置工具、自定义工具和扩展工具。工具白名单/黑名单、`baseToolsOverride`、extension tools 的合并顺序也会直接影响模型可用能力。

compaction 改动需要特别谨慎。手动压缩、阈值压缩和上下文溢出恢复共享状态，但使用不同 `AbortController` 和不同事件原因。错误地复用状态可能导致压缩无法取消、重复压缩、压缩后 session 历史不一致，甚至在上下文溢出后无法恢复。

认证逻辑不宜随意放宽。`_getRequiredRequestAuth()` 与 `_getCompactionRequestAuth()` 的差异服务于普通请求和 SDK 自定义 stream 场景；如果统一处理，可能破坏嵌入式 SDK 或让真实模型请求在无凭据时失败得不清晰。

bash 和流式消息的交互是另一个敏感点。流式期间插入 bash 输出必须维护消息顺序，否则容易破坏 provider 对 tool use/tool result 的格式要求。修改 `_pendingBashMessages` 写入时机时，需要同时检查 interactive UI、session 持久化和后续 prompt 上下文。

最后，运行时重建和扩展绑定涉及 mutable ref、shutdown handler、error listener、UI context 和 mode。若新增功能需要重建 runner，应确认旧 runner 的监听器和资源被清理，否则会出现重复事件、悬挂监听器或 session 切换后仍使用旧 cwd/旧工具的问题。
