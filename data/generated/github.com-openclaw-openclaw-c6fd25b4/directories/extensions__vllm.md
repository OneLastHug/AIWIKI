# 目录：extensions/vllm

## 它负责什么

`extensions/vllm` 是 OpenClaw 内置的 vLLM provider plugin。它把本地或自托管的 vLLM OpenAI-compatible 服务接入 OpenClaw 的 provider 体系，让用户可以通过 `VLLM_API_KEY`、自定义 `baseUrl` 和模型名完成配置，并把 vLLM 暴露为一个 `openai-completions` 风格的模型提供方。

从边界上看，它属于 `extensions/` 下的 bundled plugin，但仍按第三方插件可见的 SDK 边界编写：生产代码主要从 `openclaw/plugin-sdk/*` 引入能力，不直接进入 core 的 `src/**` 内部实现。这个目录的职责不是实现 vLLM 服务本身，也不是实现通用 OpenAI client，而是做三件事：声明插件元数据、注册 provider/setup/catalog/wizard 入口、对 vLLM 特有的 streaming payload 做少量兼容包装。

该目录没有复杂分层，是一个扁平的小插件目录。关键逻辑集中在 `index.ts`、`models.ts`、`stream.ts`，对外窄接口集中在 `api.ts` 和 `register.runtime.ts`，元数据集中在 `openclaw.plugin.json` 和 `package.json`。

## 直接子目录地图

`extensions/vllm` 当前没有直接子目录，只有顶层文件。

因此阅读时不需要按“模块目录”展开，而应按文件角色理解：

`openclaw.plugin.json` 描述插件静态元数据，包括 `id`、是否默认启用、provider id、provider request family、auth env var、setup choice、config schema 等。

`package.json` 声明 npm 包名 `@openclaw/vllm-provider`、插件入口 `./index.ts`，以及对 `@openclaw/plugin-sdk` 的 workspace 依赖。

`index.ts` 是插件注册主入口。

`models.ts` 负责根据 vLLM 的 OpenAI-compatible endpoint 发现本地模型并构造 provider config。

`stream.ts` 负责 vLLM 特有的 stream payload 包装，尤其是 Qwen thinking 参数格式和 Nemotron thinking-off 兼容。

`defaults.ts` 存放默认常量，例如默认 base URL、provider label、默认 API key 环境变量和模型占位符。

`api.ts`、`register.runtime.ts` 是较窄的导出面，用于让 core 或其他插件边界内代码通过公开 barrel 读取需要的能力，而不是 deep import 内部文件。

`provider-discovery.contract.test.ts` 和 `stream.test.ts` 是行为与契约测试，分别覆盖 provider 发现/元数据契约和 streaming payload 兼容逻辑。

`README.md` 只给出极简说明：这是用于 vLLM discovery 和 setup 的 bundled provider plugin。

## 关键入口

最重要的入口是 `extensions/vllm/index.ts`。它默认导出 `definePluginEntry(...)`，插件 id 是 `vllm`，注册名是 `vLLM Provider`。在 `register(api)` 中，它调用 `api.registerProvider(...)`，把 vLLM provider 接进 OpenClaw provider registry。

`api.registerProvider` 里有几个关键字段：

`id: "vllm"` 是 provider 标识。

`docsPath: "/providers/vllm"` 是文档路径引用。注意文档学习中不要把它扩展成真实网址。

`envVars: ["VLLM_API_KEY"]` 表示认证环境变量。

`auth` 定义一个 `custom` 方法，交互式配置走 `promptAndConfigureOpenAICompatibleSelfHostedProviderAuth`，非交互式配置走 `configureOpenAICompatibleSelfHostedProviderNonInteractive`。这说明 vLLM 被当作“OpenAI-compatible self-hosted provider”处理，而不是单独造一套认证流程。

`catalog.run` 调用 `discoverOpenAICompatibleSelfHostedProvider`，并把 `buildVllmProvider` 作为 provider 构造函数传入。模型发现的实际 provider config 构建在 `extensions/vllm/models.ts`。

`wizard` 提供 setup 和 model picker 所需的展示信息，例如 choice、group、method、label、hint。

`buildUnknownModelHint` 在模型未知时给用户配置提示，核心意思是：vLLM 需要先注册 provider，可设置 `VLLM_API_KEY` 或运行配置命令。

`wrapStreamFn: wrapVllmProviderStream` 把 streaming 兼容逻辑挂到 provider 请求链路上。

## 主流程位置

配置和发现主流程在 `extensions/vllm/index.ts` 到 `extensions/vllm/models.ts` 之间。

用户选择 vLLM provider 后，`index.ts` 中的 `auth.run` 或 `auth.runNonInteractive` 会加载 `openclaw/plugin-sdk/provider-setup`，并调用 SDK 提供的 OpenAI-compatible self-hosted 配置函数。默认 base URL 来自 `extensions/vllm/defaults.ts`，当前是 `[URL已移除] env var 是 `VLLM_API_KEY`；模型占位符是 `meta-llama/Meta-Llama-3-8B-Instruct`。

provider catalog 发现流程也从 `index.ts` 出发。`catalog.run` 调用 `discoverOpenAICompatibleSelfHostedProvider`，再进入 `buildVllmProvider`。`buildVllmProvider` 会规范化 `baseUrl`，去掉末尾斜杠，然后调用 `discoverOpenAICompatibleLocalModels`。返回的 provider config 形状包括 `baseUrl`、`api: "openai-completions"` 和发现到的 `models`。

streaming 兼容主流程在 `extensions/vllm/stream.ts`。入口是 `wrapVllmProviderStream(ctx)`。它先确认 provider 归一化后是 `vllm`，且模型 API 是 `openai-completions`。然后读取 `extraParams.qwenThinkingFormat` 或 `extraParams.qwen_thinking_format`，支持把若干写法归一为 `chat-template` 或 `top-level`。如果需要处理 Qwen thinking，代码会通过 `createVllmQwenThinkingWrapper` 修改请求 payload：可能写入 `chat_template_kwargs.enable_thinking`，也可能写入顶层 `enable_thinking`，同时删除 `reasoning_effort`、`reasoningEffort`、`reasoning` 这些不适合继续传给 vLLM 的字段。

另一个分支是 Nemotron thinking-off 兼容。`isVllmNemotronModel` 会识别 provider 为 `vllm`、API 为 `openai-completions`、模型 id 匹配 `nemotron-3` 系列的模型。当 `thinkingLevel === "off"` 时，wrapper 会把 `chat_template_kwargs` 中的 `enable_thinking` 设为 `false`，并补上 `force_nonempty_content: true`。根据当前片段推断，这属于 vLLM 对特定模型 chat template 参数的 provider-local 兼容处理，依据是相关逻辑只在 `stream.ts` 中针对 vLLM provider 和 Nemotron 模型名生效。

## 推荐阅读顺序

第一步读 `extensions/vllm/openclaw.plugin.json`，先建立静态地图：插件 id、provider id、默认启用状态、auth env var、OpenAI-compatible family、config schema。

第二步读 `extensions/vllm/package.json`，确认插件入口是 `./index.ts`，以及它只依赖 `@openclaw/plugin-sdk`，符合 bundled plugin 的边界预期。

第三步读 `extensions/vllm/defaults.ts`，把默认 base URL、env var、label、模型占位符记住。后面阅读 setup 和 discovery 时会反复看到这些常量。

第四步读 `extensions/vllm/index.ts`，这是理解全局流程的核心。重点看 `definePluginEntry`、`api.registerProvider`、`auth`、`catalog`、`wizard`、`wrapStreamFn`。

第五步读 `extensions/vllm/models.ts`，理解 vLLM 如何通过 OpenAI-compatible local model discovery 构造 provider config。

第六步读 `extensions/vllm/stream.ts`，理解请求流包装如何处理 Qwen thinking 和 Nemotron thinking-off。

最后看 `extensions/vllm/provider-discovery.contract.test.ts`、`extensions/vllm/stream.test.ts`，用测试反推哪些行为是稳定契约，哪些只是实现细节。

## 常见误区

不要把 `extensions/vllm` 理解成完整的 vLLM SDK。它不启动 vLLM，不管理模型服务生命周期，也不实现底层推理；它只是把已有的 OpenAI-compatible vLLM endpoint 接入 OpenClaw。

不要把 `openclaw.plugin.json` 当成注释文件。这里的 provider id、auth choices、env vars、request family、config schema 都会影响插件发现、配置向导和运行时规划，是控制面元数据。

不要绕过 `api.ts` 或 `register.runtime.ts` 去 deep import 内部实现。`extensions/AGENTS.md` 明确要求 bundled plugin 也按插件边界工作；如果 core 或测试需要插件能力，应优先通过公开 barrel。

不要把 `VLLM_API_KEY` 理解为一定要是真实远端密钥。vLLM 常见部署是本地或自托管 OpenAI-compatible server，有些环境中任意值即可满足 OpenAI-compatible client 的认证字段要求；具体行为仍取决于用户的 vLLM 服务配置。

不要误以为所有 thinking 逻辑都是通用 provider 行为。`stream.ts` 里的 Qwen format、Nemotron model detection 和 payload patch 都是 vLLM provider-local 的兼容层，入口也通过 `wrapVllmProviderStream` 限定在 provider 为 `vllm` 且 API 为 `openai-completions` 的请求上。

不要把 `README.md` 当成完整文档。它只说明目录用途，真正的流程证据在 `index.ts`、`models.ts`、`stream.ts`、`openclaw.plugin.json`。
