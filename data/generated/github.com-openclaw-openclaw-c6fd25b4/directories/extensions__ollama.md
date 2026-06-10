# 目录：extensions/ollama

## 它负责什么

`extensions/ollama` 是 OpenClaw 内置的 Ollama provider plugin。它把本地或远端 Ollama 服务接入 OpenClaw 的模型运行体系，主要负责四类事情：插件注册、模型发现、运行时请求流、以及 Ollama 相关能力扩展。

从 `package.json` 看，这个包名是 `@openclaw/ollama-provider`，通过 `openclaw.extensions` 指向 `./index.ts` 作为插件入口；从 `openclaw.plugin.json` 的存在可以看出，它还提供静态插件元数据，供发现、安装、设置等控制面流程读取。按 `extensions/AGENTS.md` 的边界规则，这里属于 bundled plugin，但应像第三方插件一样通过 `openclaw/plugin-sdk/*` 与核心交互，生产代码不应依赖 core 内部路径。

功能上，这个目录不是单纯的 HTTP client，而是一个完整 provider 插件：它注册 Ollama 模型 provider，支持设置向导和非交互配置，能从 Ollama 实例发现模型并补充上下文窗口等信息；运行时可走 Ollama 原生 chat API，也能处理 OpenAI-compatible 传输场景的参数包装；同时还注册 embedding、memory embedding、media understanding、web search 等 Ollama 相关能力。

## 直接子目录地图

`extensions/ollama` 的结构比较扁平，直接子目录只有两个层级值得关注。

`src/` 是主要实现区。这里放 provider 的内部逻辑，包括默认值、模型发现、setup、stream、embedding、media understanding、web search、base URL 读取、model id 规范化、模型行为判断、WSL2 crash loop 检查等。大多数真实业务逻辑都在这个目录里，而根目录更多承担插件入口、公开 API、契约测试和适配层角色。

`src/sanitizers/` 是输出清理和模型特定 sanitizer 的区域。根据当前片段推断，它服务于 `src/stream.ts` 的可见文本清理，以及 `src/model-behavior.ts` 对 Kimi/Moonshot thinking 类模型的特殊判断；依据是 `src/model-behavior.ts` 导入 `./sanitizers/kimi-inline-reasoning.js`，并且 `src/stream.ts` 中出现 `createOllamaVisibleContentSanitizer`、`sanitizeOllamaFinalVisibleContent`、garbled visible text 检查等调用。

根目录下还有一组测试文件，例如 `index.test.ts`、`provider-discovery.test.ts`、`provider-policy-api.test.ts`、`ollama.live.test.ts`、`plugin-registration.contract.test.ts`。这些不是子目录，但能帮助理解该插件的边界：注册契约、发现导入保护、provider policy、live Ollama 行为都有专门覆盖。

## 关键入口

最重要的入口是 `extensions/ollama/index.ts`。它默认导出 `definePluginEntry(...)`，在 `register(api)` 中把 Ollama 接入 OpenClaw。这里可以看到插件注册的总装配：`api.registerProvider(...)` 注册 provider，`api.registerWebSearchProvider(...)` 注册 web search，`api.registerEmbeddingProvider(...)`、`api.registerMemoryEmbeddingProvider(...)`、`api.registerMediaUnderstandingProvider(...)` 注册额外能力。阅读这个文件可以快速知道 Ollama 插件向宿主暴露了哪些能力，以及这些能力分别转到哪些实现文件。

`extensions/ollama/api.ts` 和 `extensions/ollama/runtime-api.ts` 是更窄的公开出口。按照 `extensions/AGENTS.md` 的规则，如果 core 或其他边界需要使用 bundled plugin helper，应优先通过这类 barrel 暴露，而不是深 import `src/**`。所以学习时可以把它们看成“对外可见的插件 API 面”，而 `src/**` 是私有实现。

`extensions/ollama/provider-discovery.ts` 是 provider 发现相关的根部入口，和 `src/discovery-shared.ts`、`src/provider-models.ts` 配合。它面向控制面或发现流程，避免调用方直接穿透到内部实现细节。

`extensions/ollama/provider-policy-api.ts` 是策略入口，片段中 `index.ts` 会从这里导入 `resolveThinkingProfile` 并重命名为 `resolveOllamaThinkingProfile`。它主要用于把模型 thinking/profile 这类策略判断整理成可复用的 provider policy API。

`extensions/ollama/web-search-provider.ts`、`extensions/ollama/web-search-contract-api.ts` 是 web search 能力的根部入口或契约出口；内部实现对应 `src/web-search-provider.ts`。

## 主流程位置

插件启动与注册主流程在 `index.ts`。OpenClaw 发现该插件后加载 `index.ts`，执行 `definePluginEntry` 定义的注册逻辑。注册时会读取启动期 plugin config，并提供运行期解析函数，然后把 provider、embedding、media understanding、memory embedding、web search 等能力挂到宿主 API 上。

配置与 onboarding 主流程在 `src/setup.ts`。`index.ts` 中 provider 的 setup/onboard 相关逻辑会调用 `promptAndConfigureOllama(...)`、`configureOllamaNonInteractive(...)`、`ensureOllamaModelPulled(...)`。这说明用户选择 Ollama、填写 base URL 或模型 ID、非交互初始化、模型 pull 检查等流程主要落在这里。

模型发现主流程在 `src/provider-models.ts`。关键函数包括 `resolveOllamaApiBase(...)`、`fetchOllamaModels(...)`、`queryOllamaModelShowInfo(...)`、`enrichOllamaModelsWithContext(...)`、`buildOllamaModelDefinition(...)`、`buildOllamaProvider(...)`。整体路径是：解析 base URL，访问 Ollama tags 接口拿模型列表，再对部分模型调用 show 信息补充 context window 和 capability，最后构造成 OpenClaw 的 `ModelProviderConfig` / model definition。这里还包含 SSRF policy、show 信息缓存、reasoning model heuristic 等安全与体验细节。

运行时对话主流程在 `src/stream.ts`。它承担消息转换、工具 schema 规范化、Ollama chat 请求构造、NDJSON stream 解析、assistant message 构建、usage fallback、thinking/text 事件推送、可见内容 sanitizer、tool call 处理等。`createOllamaStreamFn(...)` 是原生 Ollama stream 的核心工厂，`createConfiguredOllamaStreamFn(...)` 根据模型和 provider base URL 生成运行时 stream function；`createConfiguredOllamaCompatStreamWrapper(...)` 则处理 OpenAI-compatible 传输下的 `num_ctx`、thinking 等兼容包装。

辅助能力主流程分散在 `src/embedding-provider.ts`、`src/memory-embedding-adapter.ts`、`src/media-understanding-provider.ts`、`src/web-search-provider.ts`。它们不是 provider 注册的主线，但会在 `index.ts` 中被一起注册，属于 Ollama 插件暴露给 OpenClaw 的能力扩展。

## 推荐阅读顺序

1. 先读 `extensions/ollama/package.json` 和 `extensions/ollama/openclaw.plugin.json`，确认这是哪个插件、入口在哪里、静态元数据如何描述。
2. 再读 `extensions/ollama/index.ts`，建立全局地图：插件注册了哪些 provider/capability，setup、discover、stream 分别跳到哪里。
3. 接着读 `extensions/ollama/src/defaults.ts`、`extensions/ollama/src/provider-base-url.ts`、`extensions/ollama/src/model-id.ts`，先掌握默认值、base URL 读取和模型 ID 规范化这些基础规则。
4. 然后读 `extensions/ollama/src/provider-models.ts` 和 `extensions/ollama/src/discovery-shared.ts`，理解“如何从 Ollama 实例变成 OpenClaw provider/model 配置”。
5. 再读 `extensions/ollama/src/setup.ts`，把用户配置路径和自动发现路径串起来。
6. 最后读 `extensions/ollama/src/stream.ts`，这是最大也最复杂的运行时文件，适合在已有 provider/config 背景后再看。
7. 如果只关心某个扩展能力，再单独读 `src/embedding-provider.ts`、`src/media-understanding-provider.ts`、`src/web-search-provider.ts`，不要一开始就陷入这些支线。

## 常见误区

一个常见误区是把 `extensions/ollama` 当成 core provider 代码。实际上它是 bundled plugin，边界上仍按插件处理。生产代码应通过 `openclaw/plugin-sdk/*` 和本插件自己的 `api.ts`、`runtime-api.ts` 交互，不应反向依赖 `src/**` core 内部或其他 plugin 私有实现。

另一个误区是只看 `src/stream.ts` 就理解整个插件。`stream.ts` 只覆盖运行时聊天请求和事件流；模型从哪里来、配置如何生成、base URL 如何解析、setup 如何提示用户，分别在 `src/provider-models.ts`、`src/discovery-shared.ts`、`src/setup.ts`、`src/provider-base-url.ts` 等位置。学习时应先看注册和发现，再看 stream。

还容易混淆 Ollama 原生 API 和 OpenAI-compatible 传输。目录里既有 `createOllamaStreamFn(...)` 这种原生 Ollama chat 流，也有 `createConfiguredOllamaCompatStreamWrapper(...)` 这类兼容包装逻辑。它们处理的参数位置、thinking、`num_ctx` 注入策略并不完全相同，不能简单合并理解。

不要把根目录下的测试文件视为噪音。`plugin-registration.contract.test.ts`、`provider-discovery.import-guard.test.ts` 这类测试说明了插件发现和边界导入的契约；`provider-models.*.test.ts`、`stream*.test.ts` 则能反向证明模型发现、SSRF 策略、stream 事件转换等行为是这个目录的重要稳定面。

最后，`plugin.json` 不是这个目录的元数据文件名；当前目录使用的是 `openclaw.plugin.json`。如果按旧名字查找会误判插件元数据缺失。
