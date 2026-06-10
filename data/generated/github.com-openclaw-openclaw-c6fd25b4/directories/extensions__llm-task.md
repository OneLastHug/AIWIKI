# 目录：extensions/llm-task

## 它负责什么

`extensions/llm-task` 是一个 bundled plugin，提供名为 `llm-task` 的可选 agent tool。它的定位不是一个通用聊天入口，而是“把一次结构化任务交给模型执行，并强制返回 JSON”的工作流工具。典型用途是让外部编排系统通过 `openclaw.invoke` 之类的调用方式，把摘要、分类、草稿生成、字段抽取等小任务转成一次嵌入式 LLM 运行，然后拿到可解析、可校验的 JSON 结果。

这个插件的边界很清楚：注册层在 `index.ts`，公共转出口在 `api.ts`，真正的工具执行逻辑在 `src/llm-task-tool.ts`。它依赖 OpenClaw Plugin SDK 暴露的 agent runtime、JSON Schema 校验、临时目录等能力，不直接承担 provider 实现、模型认证、工作流审批或副作用动作。README 也说明它更像随 OpenClaw 分发的内置插件，不是面向用户复制到本地插件目录的独立插件。

从配置看，`openclaw.plugin.json` 和 `index.ts` 都声明了 `defaultProvider`、`defaultModel`、`defaultAuthProfileId`、`allowedModels`、`maxTokens`、`timeoutMs` 等配置项。它通过 `contracts.tools` 声明工具 `llm-task`，并把工具标记为 optional，因此启用插件后还需要在 agent 的 tool allowlist 里允许它。

## 直接子目录地图

这个目录很小，只有一个直接子目录：

`src/`：插件内部实现和测试所在位置。核心文件是 `src/llm-task-tool.ts`，负责定义 tool 参数、解析配置、调用嵌入式 agent、解析 JSON、执行 schema 校验并返回结果。`src/runtime-api.ts` 是运行时 API 的轻量转出口，把临时目录相关能力从 Plugin SDK 暴露给本插件使用。`src/llm-task-tool.test.ts` 覆盖 JSON 解析、schema 校验、provider/model 解析、thinking 参数、allowlist 和禁用工具等行为。

根层文件主要承担插件包装和元数据职责：`index.ts` 是插件入口；`openclaw.plugin.json` 是发现、激活、配置 schema 和工具契约的静态描述；`package.json` 声明包名、依赖和 OpenClaw extension 入口；`api.ts` 是本插件对外或内部统一导入的 SDK facade；`README.md` 是使用说明；`tsconfig.json` 是编译配置。

## 关键入口

最重要的入口是 `extensions/llm-task/index.ts`。它调用 `defineToolPlugin` 定义插件，设置 `id: "llm-task"`、名称、描述、`configSchema`，并在 `tools` 回调里注册 `llm-task`。注册时合并 `llmTaskToolDefinition`，设置 `optional: true`，并把 factory 指向 `createLlmTaskTool(api)`。学习这个目录时，可以把 `index.ts` 理解为“OpenClaw 如何看见这个插件”的入口。

第二个入口是 `extensions/llm-task/src/llm-task-tool.ts`。这里导出两个关键符号：`llmTaskToolDefinition` 和 `createLlmTaskTool`。前者定义工具名、label、描述和参数 schema；后者返回带 `execute` 方法的实际工具对象。所有运行时行为都从 `execute(_id, params)` 展开。

`extensions/llm-task/openclaw.plugin.json` 是静态发现入口。它声明 `activation.onStartup: true`，说明插件会在启动时激活；同时声明配置 schema 和工具契约。和 `index.ts` 对照阅读，可以看到静态 metadata 与运行时注册基本保持一致。

`extensions/llm-task/api.ts` 是边界入口。它从 `openclaw/plugin-sdk/plugin-entry` 转出 `definePluginEntry`、`AnyAgentTool`、`OpenClawPluginApi`，并转出临时目录工具。根据当前片段推断，这个文件的作用是给插件内部提供一个稳定、局部的 SDK 导入面，避免实现文件到处直接拼接 SDK 子路径。

## 主流程位置

主流程集中在 `src/llm-task-tool.ts` 的 `createLlmTaskTool(...).execute(...)`。

第一步是参数和配置归一。`execute` 先要求 `prompt` 必须是非空字符串，然后读取 `api.pluginConfig`。模型来源按优先级合成：调用参数里的 `provider`、`model` 优先，其次是插件配置 `defaultProvider`、`defaultModel`，再退到 agent 默认模型。`resolveLlmTaskModelRef` 会结合 `api.config` 和 `buildModelAliasIndex`、`resolveModelRefFromString` 解析模型别名；如果调用方传入的 model 已经带有 provider 前缀，`stripDuplicateProviderPrefix` 会去掉重复前缀。

第二步是安全和能力约束。代码会生成 `provider/model` 形式的 `modelKey`，如果缺少 provider 或 model 就报错。如果插件配置了 `allowedModels`，请求模型必须在 allowlist 内。`thinking` 参数也不是原样透传，而是先用 `api.runtime.agent.resolveThinkingPolicy` 查询当前 provider/model 支持哪些 thinking level，再用 `normalizeThinkingLevel` 标准化，最后确认该 level 被当前模型支持。

第三步是构造一次 JSON-only 嵌入式 agent 运行。实现会把 `input` 序列化为 JSON，拼出包含系统约束、任务说明和 `INPUT_JSON` 的 `fullPrompt`。系统约束明确要求模型只返回合法 JSON、不使用 markdown fence、不输出解释、不调用工具。然后代码通过 `withTempWorkspace` 创建临时 workspace，并调用 `api.runtime.agent.runEmbeddedPiAgent`。关键参数包括 `sessionId`、`sessionFile`、`workspaceDir`、`config`、`prompt`、`timeoutMs`、`provider`、`model`、`authProfileId`、`thinkLevel`、`streamParams`，以及非常重要的 `disableTools: true`。

第四步是结果解析和校验。`collectText` 从返回 payloads 中收集非错误文本；`stripCodeFences` 容忍模型偶尔包了 JSON fence；随后 `JSON.parse` 得到结构化结果。如果调用方提供了 `schema` 且它是对象，会用 `validateJsonSchemaValue` 校验返回值，不通过则抛出错误。最终返回形状包含 `content: [{ type: "text", text: ... }]` 和 `details: { json, provider, model }`。

## 推荐阅读顺序

建议先读 `extensions/llm-task/README.md`，理解它的用途、启用方式、配置项和工具参数。这里会先建立正确心智：它是 JSON-only task tool，不是 provider 插件，也不是工作流引擎。

第二步读 `extensions/llm-task/openclaw.plugin.json` 和 `extensions/llm-task/package.json`。前者说明插件如何被发现、何时激活、暴露什么工具、允许什么配置；后者说明包名、依赖和 `openclaw.extensions` 入口。这样能把“插件元数据”和“包级入口”先对齐。

第三步读 `extensions/llm-task/index.ts`。这里代码很短，但它连接了 Plugin SDK 的 `defineToolPlugin` 和内部的 `createLlmTaskTool`，是从 OpenClaw 插件系统进入业务实现的桥。

第四步读 `extensions/llm-task/src/llm-task-tool.ts`。阅读时按 `llmTaskToolDefinition`、模型解析 helper、`execute` 主流程、结果校验顺序看，不需要逐个 helper 展开。最后再看 `extensions/llm-task/src/llm-task-tool.test.ts`，用测试确认哪些行为是契约：fenced JSON 容错、schema mismatch 报错、模型别名解析、thinking 校验、`allowedModels` 拦截、嵌入式运行禁用工具。

## 常见误区

第一个误区是把 `llm-task` 当成普通聊天工具。它的设计目标是结构化任务，返回值必须能被 JSON 解析，并可选用 JSON Schema 校验；自然语言解释、markdown 包装和工具调用都被明确排除在主流程之外。

第二个误区是以为启用插件就一定能被 agent 使用。它在注册时是 `optional: true`，所以除了在 `plugins.entries` 中启用，还需要在 agent 的 tools allowlist 中允许 `llm-task`。

第三个误区是忽略模型解析优先级。`provider` 和 `model` 可能来自调用参数、插件配置或 agent defaults；`model` 还可能是别名，最终会被解析成 provider/model。阅读报错或调试时不要只看调用参数，也要看 `pluginConfig` 和 `api.config.agents.defaults`。

第四个误区是把 `allowedModels` 当成默认模型列表。它实际上是 allowlist：配置后，请求模型不在列表内会被拒绝，而不是自动回退到列表中的某个模型。

第五个误区是认为 schema 会约束模型生成过程。当前实现是在模型返回后做 `validateJsonSchemaValue` 校验；schema 不会直接变成 provider 的 response format 参数。也就是说，它保证“不合格就失败”，不保证模型第一次一定生成合格 JSON。

第六个误区是把这个插件当成可独立复制的第三方插件。README 明确说明它依赖 OpenClaw 的嵌入式 agent runner 等内部能力，当前更适合作为 bundled extension 随产品分发。
