# 目录：extensions/xai

## 它负责什么

`extensions/xai` 是 OpenClaw 内置的 xAI provider plugin，负责把 xAI/Grok 接入到 OpenClaw 的模型、认证、媒体能力、工具能力和配置发现体系中。它位于 `extensions/` 下，因此按插件边界工作：生产代码主要依赖 `openclaw/plugin-sdk/*`，通过插件入口和本目录自己的公开 barrel 暴露能力，而不是直接穿透到 core 内部。

从当前片段看，这个目录承担三类职责。第一类是模型 provider：声明 `xai` provider、默认模型、模型目录、模型 ID 归一化、runtime compat、Responses/OpenAI-compatible transport 转换、thinking policy 等。第二类是能力 provider：注册 web search、image generation、video generation、speech、realtime transcription、media understanding 等能力。第三类是工具与认证：提供 `code_execution`、`x_search` 两个工具，并支持 API key、OAuth、device code 等认证路径。

这个目录不是一个普通工具包，而是一个完整插件包。`package.json` 中包名是 `@openclaw/xai-plugin`，`openclaw.extensions` 指向 `./index.ts`；`openclaw.plugin.json` 则提供无需执行代码即可读取的插件元数据、认证选项、配置 schema、UI hints、contracts 和 provider discovery 信息。

## 直接子目录地图

`extensions/xai/.boundary-stubs` 是边界检查用的声明桩目录。里面放了若干 `.d.ts` 文件，例如 `anthropic-vertex-api.d.ts`、`ollama-api.d.ts`、`ollama-runtime-api.d.ts`、`speech-core-runtime-api.d.ts`。根据当前片段推断，它们不是 xAI 运行主流程的一部分，而是用于测试或类型边界验证，帮助确保插件不会错误依赖其他插件或 core 内部实现。

`extensions/xai/src` 放共享 runtime 辅助、工具配置、工具认证和 web/X search 相关的内部实现。典型文件包括 `src/tool-auth-shared.ts`、`src/tool-config-shared.ts`、`src/web-search-provider.runtime.ts`、`src/web-search-shared.ts`、`src/x-search-config.ts`、`src/x-search-shared.ts`、`src/code-execution-shared.ts`、`src/xai-user-agent.ts`。这里的代码更偏“被根层入口调用的内部积木”，而不是插件对外入口。目录下也有 colocated tests，例如 `src/tool-auth-shared.test.ts`、`src/responses-tool-shared.test.ts`。

除这两个子目录外，`extensions/xai` 根部是扁平模块布局：入口、provider 组装、模型定义、认证、各能力 provider、工具实现和测试文件都直接放在根层。这种布局使 `index.ts` 可以清楚地把插件注册面收束在一个地方。

## 关键入口

最重要的入口是 `extensions/xai/index.ts`。它默认导出 `defineSingleProviderPluginEntry(...)`，声明插件 `id: "xai"`、provider 元信息、认证方式、模型目录、stream 包装、transport 归一化、动态模型解析、OAuth refresh、thinking profile 等，并在 `register(api)` 中把能力注册进 OpenClaw：`registerWebSearchProvider`、`registerMediaUnderstandingProvider`、`registerVideoGenerationProvider`、`registerImageGenerationProvider`、`registerSpeechProvider`、`registerRealtimeTranscriptionProvider`、`registerTool`。

`extensions/xai/openclaw.plugin.json` 是静态元数据入口。它描述插件是否默认启用、provider ID、provider endpoint class、认证环境变量 `XAI_API_KEY`、onboarding 认证 choices、UI 配置提示、能力 contracts、工具 metadata、配置兼容路径和 `configSchema`。OpenClaw 的发现、设置、配置 UI 或能力规划流程可以优先读这个文件，而不是运行插件代码。

`extensions/xai/api.ts` 是本插件的公开 barrel。它导出 `buildXaiProvider`、`applyXaiConfig`、`buildXaiImageGenerationProvider`、模型定义函数、runtime compat 函数和若干归一化工具，例如 `normalizeXaiModelId`、`resolveXaiTransport`、`resolveXaiBaseUrl`。如果 core 或测试需要复用 xAI 插件能力，按 `extensions/AGENTS.md` 的边界规则，应优先从这里取，而不是 deep import 私有文件。

`extensions/xai/package.json` 是包级入口配置，说明这是 ESM 私有包，运行依赖包含 `@earendil-works/pi-ai` 和 `typebox`，开发依赖包含 `@openclaw/plugin-sdk` 与 `ws`，并把 `./index.ts` 声明为 OpenClaw 插件入口。

## 主流程位置

provider 注册主流程在 `extensions/xai/index.ts`。文件顶部汇入模型、认证、stream、工具、媒体 provider 等模块；中部定义懒加载工具 `createLazyCodeExecutionTool` 和 `createLazyXSearchTool`；底部通过 `register(api)` 完成全部能力挂载。理解“xAI 插件启动后给系统贡献了什么”，应从这里开始。

模型目录和默认模型主流程在 `extensions/xai/model-definitions.ts`、`extensions/xai/provider-catalog.ts`、`extensions/xai/provider-models.ts`。`model-definitions.ts` 定义 `XAI_BASE_URL`、`XAI_DEFAULT_MODEL_ID`、`XAI_IMAGE_MODELS`、catalog entries、retired model 判断和 `buildXaiCatalogModels()` 等；`provider-catalog.ts` 负责构造 provider catalog；`provider-models.ts` 处理现代模型判断与 forward-compatible 动态模型解析。

认证与 onboarding 主流程在 `extensions/xai/onboard.ts`、`extensions/xai/xai-oauth.ts`、`extensions/xai/setup-api.ts` 和 `src/tool-auth-shared.ts`。`onboard.ts` 负责把 xAI provider 配置写入 OpenClaw config，并清理 retired built-in models；`xai-oauth.ts` 负责 OAuth、device code、token refresh 等认证细节；`src/tool-auth-shared.ts` 处理工具运行时如何从 provider auth、插件配置、旧 web search 配置或环境变量解析 xAI 凭据。

模型 runtime 兼容主流程在 `extensions/xai/model-compat.ts`、`extensions/xai/runtime-model-compat.ts`、`extensions/xai/stream.ts` 和 `api.ts` 中的 `resolveXaiTransport()`。这些文件处理 xAI native endpoint、OpenAI-compatible 请求形态、tool schema profile、HTML entity tool-call 参数编码、stream 包装和模型 compat patch。

媒体能力主流程分散在几个 provider 文件：`image-generation-provider.ts` 负责图片生成与编辑，`video-generation-provider.ts` 负责视频生成、轮询和下载，`speech-provider.ts` 负责 TTS，`realtime-transcription-provider.ts` 与 `stt.ts` 负责实时转录和媒体理解。它们最终都由 `index.ts` 的 `register(api)` 注册。

web 与工具能力主流程在 `web-search.ts`、`src/web-search-provider.runtime.ts`、`x-search.ts`、`x-search-tool-shared.ts`、`code-execution.ts`、`src/code-execution-shared.ts`。`web-search.ts` 提供 Grok web search provider；`x-search.ts` 提供 `x_search` 工具的执行逻辑；`code-execution.ts` 提供远程 Python sandbox 风格的 `code_execution` 工具。`index.ts` 对后两者采用 dynamic import 懒加载，避免插件注册阶段 eagerly 拉起较重运行逻辑。

## 推荐阅读顺序

1. 先读 `extensions/xai/openclaw.plugin.json`，建立静态视角：插件 ID、provider、认证方式、contracts、tools、配置 schema 分别是什么。
2. 再读 `extensions/xai/index.ts`，看运行时如何把静态能力真正注册到 OpenClaw 插件 API。
3. 接着读 `extensions/xai/api.ts`，理解哪些东西是本插件刻意暴露给外部复用的公开面。
4. 然后读模型链路：`model-definitions.ts`、`provider-catalog.ts`、`provider-models.ts`、`model-compat.ts`、`runtime-model-compat.ts`。
5. 再读认证链路：`onboard.ts`、`xai-oauth.ts`、`src/tool-auth-shared.ts`，把 API key、OAuth、device code、fallback auth 的关系串起来。
6. 最后按能力选择阅读：搜索看 `web-search.ts`、`src/web-search-provider.runtime.ts`、`x-search.ts`；代码执行看 `code-execution.ts`、`src/code-execution-shared.ts`；媒体看 `image-generation-provider.ts`、`video-generation-provider.ts`、`speech-provider.ts`、`realtime-transcription-provider.ts`、`stt.ts`。

## 常见误区

不要把 `extensions/xai/src` 理解成唯一源码目录。这个插件的大部分关键模块直接位于 `extensions/xai` 根层，`src/` 主要承载共享内部 helper 和 runtime 支撑代码。

不要只看 `openclaw.plugin.json` 就判断插件行为。它提供 discovery、UI、schema 和 contracts 的静态事实，但真正的注册、懒加载、stream 包装、OAuth refresh、动态模型解析都在 `index.ts` 和相关 TS 模块里。

不要把 `web_search`、`x_search` 和 `code_execution` 混为同一条流程。`web_search` 是 web search provider 能力；`x_search` 是注册给 agent 的工具，面向 X 内容搜索；`code_execution` 也是工具，但走 xAI 远程代码执行请求。三者共享部分认证和 Responses API 辅助，但入口和配置段不同。

不要把所有 credential 都看成单一 `XAI_API_KEY`。当前代码同时支持 provider auth profile、OAuth/device code、环境变量、插件配置 `plugins.entries.xai.config.webSearch.apiKey`，以及旧 `tools.web.search.grok.apiKey` 兼容读取。具体运行时解析位置在 `src/tool-auth-shared.ts` 和 `src/web-search-provider.runtime.ts`。

不要从 core 深入导入本目录私有文件。按 `extensions/AGENTS.md`，插件对外复用应通过 `api.ts` 或专门的轻量 `*-api.ts` 文件，例如 `provider-contract-api.ts`、`provider-policy-api.ts`、`web-search-contract-api.ts`、`setup-api.ts`。这也是阅读时区分“公开边界”和“内部实现”的关键。
