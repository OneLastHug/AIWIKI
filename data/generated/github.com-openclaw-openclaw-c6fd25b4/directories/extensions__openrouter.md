# 目录：extensions/openrouter

## 它负责什么

`extensions/openrouter` 是 OpenClaw 内置的 OpenRouter provider plugin。它把 OpenRouter 接入到 OpenClaw 的插件体系里，主要覆盖几类能力：文本模型推理、动态模型解析、模型目录与价格/能力信息、API key 鉴权、OpenRouter 专属请求参数透传、流式请求兼容补丁，以及图像生成、媒体理解、音乐生成、视频生成、语音相关能力。

从 `openclaw.plugin.json` 可以看出，这个插件的 id 是 `openrouter`，默认启用，但不在启动时主动激活；它声明了 provider、模型 id 归一化、OpenRouter endpoint 归属、`OPENROUTER_API_KEY` 环境变量、onboarding 鉴权选项，以及多媒体能力契约：`mediaUnderstandingProviders`、`imageGenerationProviders`、`musicGenerationProviders`、`videoGenerationProviders`、`speechProviders`。这说明它不是单一“聊天模型适配器”，而是一个围绕 OpenRouter 的综合 provider 插件。

边界上，这个目录遵循 `extensions/AGENTS.md` 的插件约束：生产代码应通过 `openclaw/plugin-sdk/*` 与本插件本地 API 暴露能力，不能直接依赖 core 内部路径。当前代码也基本体现了这一点，例如 `index.ts`、各类 provider 文件主要从 `openclaw/plugin-sdk/...` 引入 SDK 契约和工具。

## 直接子目录地图

这个目标目录当前没有直接子目录，所有源码、测试、清单和配置文件都平铺在 `extensions/openrouter` 下。阅读时可以按角色把文件分成几组，而不是按物理子目录理解：

- 插件入口与清单：`openclaw.plugin.json`、`package.json`、`index.ts`。
- 对外/测试辅助 API：`api.ts`、`provider-contract-api.ts`、`provider-policy-api.ts`、`test-api.ts`。
- 文本模型与路由主干：`provider-catalog.ts`、`provider-routing.ts`、`stream.ts`、`thinking-policy.ts`、`models.ts`。
- 多模态 provider：`image-generation-provider.ts`、`media-understanding-provider.ts`、`music-generation-provider.ts`、`speech-provider.ts`、`video-generation-provider.ts`、`video-http.ts`、`video-model-catalog.ts`。
- onboarding 与配置写入：`onboard.ts`。
- 行为验证：`*.test.ts`、`openrouter.live.test.ts`、`provider-runtime.contract.test.ts`。

因为没有子目录分层，文件名本身就是主要地图。`*-provider.ts` 通常是某项能力的 SDK provider 实现，`*-test.ts` 则对应验证该能力或契约。

## 关键入口

最核心入口是 `index.ts`。它通过 `definePluginEntry` 声明插件，设置 `id`、`name`、`description`，并在 `register(api)` 中把 OpenRouter 注册进 OpenClaw 的 provider 系统。这里能看到几条关键线索：`api.registerProvider` 负责 provider 注册；`createProviderApiKeyAuthMethod` 负责 API key 鉴权入口；`buildDynamicOpenRouterModel` 根据模型 id 和已加载能力构造 `ProviderRuntimeModel`；`wrapOpenRouterProviderStream` 参与流式请求包装；`resolveOpenRouterExtraParamsForTransport` 负责把配置、模型参数和调用时 `extraParams` 合并进传输层。

`openclaw.plugin.json` 是静态发现入口。它让核心在不执行插件运行时代码的情况下知道该插件提供哪些 provider、认证方式、endpoint 分类、默认 capability 和配置 schema。对学习者来说，它回答“插件向系统声明了什么”；`index.ts` 回答“插件激活后实际注册了什么”。

`api.ts` 是本插件较窄的本地公开面。它导出 `buildOpenRouterImageGenerationProvider`、`buildOpenRouterMusicGenerationProvider`、`buildOpenrouterProvider`、`buildOpenRouterSpeechProvider`、`applyOpenrouterConfig`、`OPENROUTER_DEFAULT_MODEL_REF` 等符号，供插件边界允许的调用方或测试使用。不要把所有内部文件都视为公共 API。

## 主流程位置

文本模型主流程集中在 `index.ts`、`provider-catalog.ts`、`provider-routing.ts`、`stream.ts`。大致顺序是：插件被发现后，核心按需激活 `index.ts`；`register(api)` 调用 `api.registerProvider` 注册 `openrouter`；鉴权通过 `OPENROUTER_API_KEY`、CLI option 或 auth store 进入；catalog 阶段在有 key 时构造 provider 模型目录；运行时如果用户选择了 OpenRouter 模型，动态模型解析会用 `getOpenRouterModelCapabilities` 补齐名称、输入类型、上下文窗口、成本、reasoning 和工具支持等信息。

请求发出前，`provider-routing.ts` 会处理 OpenRouter 特有的 `provider` routing 参数。它从 provider config、model params、调用时 extra params 三处读取 JSON-like 参数，过滤 `__proto__`、`prototype`、`constructor` 等危险 key，再合并成 transport patch。`stream.ts` 则是兼容层重点位置：根据模型 id、baseUrl、provider 判断是否确实走 OpenRouter route，然后处理 Anthropic、DeepSeek V4、reasoning、assistant prefill、provider routing 注入等流式 payload 差异。根据当前片段推断，`stream.ts` 是 OpenRouter 文本请求最容易出现供应商兼容逻辑的位置，依据是它引入了 `provider-stream-family`、`provider-stream-shared`，并包含多种模型族判断与 payload patch 函数。

多模态主流程分别落在独立 provider 文件中。`image-generation-provider.ts` 构建 `ImageGenerationProvider`，通过 OpenRouter chat completions 形式请求图像，并从 `choices[].message.images`、content data URL、inline data 等响应形态中抽取图片。`media-understanding-provider.ts` 同时声明 image/audio 能力，其中图像描述复用 SDK 的 `describeImageWithModel` / `describeImagesWithModel`，音频转写走 `transcribeOpenRouterAudio`，向 `/audio/transcriptions` 风格接口发送 base64 音频。`music-generation-provider.ts`、`video-generation-provider.ts`、`speech-provider.ts` 分别承载音乐、视频、语音能力；其中视频还拆出 `video-http.ts` 和 `video-model-catalog.ts`，说明视频请求/轮询和模型目录有相对独立的复杂度。

onboarding 主流程在 `onboard.ts`。`index.ts` 的认证方法把 `applyConfig` 指向 `applyOpenrouterConfig`，`api.ts` 也导出相关函数，说明用户输入 OpenRouter API key 或选择默认模型后，配置写入与默认模型引用由这里负责。

## 推荐阅读顺序

1. 先读 `openclaw.plugin.json`，建立插件声明地图：id、provider、auth env、capability contracts、metadata。
2. 再读 `package.json`，确认包名、私有 bundled plugin 属性，以及 `openclaw.extensions` 指向 `./index.ts`。
3. 读 `index.ts`，重点看 `definePluginEntry`、`register(api)`、`api.registerProvider`、动态模型解析、catalog、stream wrapper 和多模态 provider 注册位置。
4. 读 `provider-catalog.ts`，理解默认模型、base URL 归一化、模型清单与 reasoning 支持判断。
5. 读 `provider-routing.ts` 和 `stream.ts`，理解 OpenRouter 专属请求参数、模型族兼容补丁和流式传输改写。
6. 按兴趣读能力 provider：图像看 `image-generation-provider.ts`，音频/图片理解看 `media-understanding-provider.ts`，音乐看 `music-generation-provider.ts`，视频看 `video-generation-provider.ts`、`video-http.ts`、`video-model-catalog.ts`，语音看 `speech-provider.ts`。
7. 最后读对应测试，如 `index.test.ts`、`provider-runtime.contract.test.ts`、各 `*-provider.test.ts`，用测试反推边界条件和错误处理预期。

## 常见误区

第一，不要把 `openclaw.plugin.json` 当成可选说明文件。它是插件发现、能力声明、auth choice、endpoint 分类和契约注册的重要静态入口；很多控制面信息应从这里读取，而不是靠执行 `index.ts` 推断。

第二，不要把 OpenRouter 只理解为 OpenAI-compatible chat completions。目录里同时有 image、media understanding、music、video、speech provider，且每类能力有自己的请求形态、默认模型、超时、响应解析和错误处理。

第三，不要绕过插件 SDK 去找 core 内部实现。`extensions/AGENTS.md` 明确要求插件生产代码使用 `openclaw/plugin-sdk/*` 和本地 barrel；因此学习这个目录时也应优先从 SDK 契约角度理解，而不是假设它能任意调用 `src/**`。

第四，不要忽略 `stream.ts`。OpenRouter 会代理多个模型供应商，表面上都是 OpenRouter provider，实际 payload 兼容点可能随模型族变化。Anthropic、DeepSeek V4、reasoning、tool calls、assistant trailing message 等逻辑都可能影响运行时行为。

第五，不要把 `api.ts` 以外的内部 helper 默认视为公共 API。`provider-contract-api.ts`、`provider-policy-api.ts`、`test-api.ts` 的具体用途需要结合调用方判断；根据当前片段推断，它们更像为契约测试、策略测试或窄入口暴露准备的辅助面，依据是文件命名和插件边界规则，而不是完整调用链证明。
