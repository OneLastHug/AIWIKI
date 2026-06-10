# 文件：packages/coding-agent/examples/sdk/README.md

## 一句话定位

`packages/coding-agent/examples/sdk/README.md` 是 `pi-coding-agent` SDK 示例目录的入口说明文档，用来把 `createAgentSession()`、`createAgentSessionRuntime()` 以及相关配置对象的程序化用法组织成一组可运行示例和速查表。

## 它暴露/定义了什么

这个文件本身不暴露 TypeScript API，也不参与编译运行；它定义的是面向 SDK 使用者的学习入口和约定性说明。核心内容包括：

- SDK 示例目录的总体目的：用代码方式创建和驱动 coding agent session。
- 示例清单：从最小启动、模型选择、系统提示词、skills、tools、extensions、上下文文件、认证、settings、sessions，到完全自定义和 runtime-backed session replacement。
- 运行方式：在 `packages/coding-agent` 下通过 `npx tsx examples/sdk/01-minimal.ts` 启动示例。
- Quick Reference：集中展示 `AuthStorage`、`ModelRegistry`、`DefaultResourceLoader`、`SessionManager`、`SettingsManager`、`createAgentSession()` 等主要入口的组合方式。
- Options 表：说明 `createAgentSession()` 可接收的主要配置项及默认行为。
- Events 示例：展示如何订阅 session 事件并处理文本流、工具开始/结束、agent 结束等状态。

需要注意一个文档一致性风险：README 的示例表写的是 `08-slash-commands.ts`，但当前目录实际文件列表显示存在的是 `08-prompt-templates.ts`。根据当前片段推断，这可能是文档未随示例重命名同步更新。

## 谁调用它

没有代码“调用”这个 README。它的直接使用者是希望以库方式嵌入 `pi-coding-agent` 的开发者、维护 SDK 示例的人，以及新贡献者。间接看，它也服务于仓库内 `packages/coding-agent/examples/sdk/*.ts` 这些示例文件：README 为这些示例提供索引、运行说明和概念地图。

如果从项目维护流程看，修改这个文件通常不会影响运行时行为，但会影响用户对 SDK 能力边界、默认配置和扩展点的理解。

## 它调用谁

作为 Markdown 文档，它不执行调用。但文档中的代码片段示范了 SDK 使用链路，主要涉及：

- `@earendil-works/pi-ai` 的 `getModel()`：按 provider 和模型名选择具体模型。
- `@earendil-works/pi-coding-agent` 的 `createAgentSession()`：创建可交互 agent session。
- `createAgentSessionRuntime()`：用于 runtime 管理场景，尤其是 session cwd 变化后重建 cwd-bound services 和 sessions。
- `AuthStorage`：管理 API key、OAuth 或运行时凭据来源。
- `ModelRegistry`：基于认证信息建立模型注册表。
- `DefaultResourceLoader`：加载或覆盖系统提示词、extensions、skills、AGENTS.md 上下文文件、prompt templates 等资源。
- `SessionManager`：控制 session 的内存态、持久化、继续会话和列表能力。
- `SettingsManager`：控制 compaction、retry、terminal 等配置覆盖。
- session 对象的 `subscribe()` 和 `prompt()`：分别用于监听运行事件和提交用户 prompt。

## 核心流程

这份 README 描述的主流程可以概括为“准备依赖、创建 session、订阅事件、发送 prompt”。

第一步是建立认证和模型上下文。最小配置里使用 `AuthStorage.create()` 创建默认凭据存储，再用 `ModelRegistry.create(authStorage)` 建立模型注册表。如果需要指定模型，则通过 `getModel("anthropic", "claude-opus-4-5")` 得到模型对象，并把 `thinkingLevel` 一起传入 `createAgentSession()`。

第二步是按需定制资源加载。`DefaultResourceLoader` 支持 `systemPromptOverride`、`extensionFactories`、`skillsOverride`、`agentsFilesOverride`、`promptsOverride` 等覆盖点。文档强调调用 `await loader.reload()`，说明 loader 需要先完成资源发现或重载，再交给 session 创建流程。

第三步是配置工具边界。`tools` 选项作为 allowlist，覆盖 built-in tools、extension tools 和 custom tools 的可用范围。README 中的 read-only 示例只允许 `read`、`grep`、`find`、`ls`，而 full-control 示例同时放入内置工具和 `my_tool`，并通过 `customTools` 注入自定义工具定义。

第四步是管理会话和设置。默认 `SessionManager.create(cwd)` 做持久化；也可以用 `SessionManager.inMemory()` 创建内存会话。`SettingsManager.create(cwd, agentDir)` 默认从工作目录和 agent 配置目录解析设置；`SettingsManager.inMemory()` 则适合测试、嵌入式或完全受宿主应用控制的场景。

第五步是运行交互。调用方通过 `session.subscribe()` 监听 `message_update`、`tool_execution_start`、`tool_execution_end`、`agent_end` 等事件，再用 `await session.prompt("Hello")` 推动 agent 执行。

## 关键函数的高层作用

`createAgentSession()` 是文档的核心入口。它把认证、模型、cwd、资源加载器、工具 allowlist、自定义工具、session 管理器和 settings 管理器组合成一个可运行的 agent session。根据 README 推断，它是面向“单个当前 session”最直接的 SDK API。

`createAgentSessionRuntime()` 面向更复杂的宿主集成。README 明确说 runtime 示例展示如何构造 recreate function：固定 process-global 输入，同时在 active session 的 cwd 变化时重建 cwd-bound services 和 sessions。也就是说，它解决的不是一次性创建 session，而是长期运行环境中 session 替换、cwd 绑定资源更新和生命周期收束问题。

`AuthStorage.create()` 负责凭据来源。默认可使用标准 agent 位置，也可传入自定义路径；还可以通过 `setRuntimeApiKey()` 注入宿主应用自己的 key。

`ModelRegistry.create()` 基于 `AuthStorage` 建立可用模型集合。它和 `getModel()` 共同决定最终使用哪个 provider/model。

`DefaultResourceLoader.reload()` 是资源覆盖生效前的重要步骤。修改 prompt、skills、extensions、AGENTS.md 或 prompt templates 后，如果未 reload，session 可能拿不到预期资源。

`SessionManager.inMemory()`、`SettingsManager.inMemory()` 是示例中用于去持久化、完全由调用方控制状态的入口，常用于测试、demo、嵌入式应用或不希望写入本地配置的场景。

## 修改风险

主要风险不是运行时崩溃，而是文档误导。README 是 SDK 示例入口，如果示例表、Quick Reference 或 Options 与真实 API 不一致，用户会直接复制出错。例如当前 `08-slash-commands.ts` 与实际 `08-prompt-templates.ts` 的不一致，就会导致文件查找失败或误解该示例主题。

第二类风险是默认值描述过期。`tools`、`agentDir`、`thinkingLevel`、`sessionManager`、`settingsManager` 这类默认行为如果随源码变化而文档未更新，会让调用方错误估计权限边界、持久化位置或模型行为，尤其是工具 allowlist 会影响安全边界。

第三类风险是认证示例。`customAuth.setRuntimeApiKey("anthropic", process.env.MY_KEY!)` 展示了运行时 key 注入方式，但真实应用需要处理缺失环境变量、provider 名称变化和凭据存储路径。文档如果过度简化，容易让集成方把 demo 代码当生产代码。

第四类风险是 runtime 说明不足。`createAgentSessionRuntime()` 涉及 cwd-bound services、session replacement 和关闭旧 session 的生命周期管理；这类 API 一旦示例不清楚，宿主应用可能出现资源泄漏、旧 cwd 资源继续生效、事件订阅残留等问题。修改该 README 时应同步检查 `13-session-runtime.ts` 和 SDK 导出的真实类型。
