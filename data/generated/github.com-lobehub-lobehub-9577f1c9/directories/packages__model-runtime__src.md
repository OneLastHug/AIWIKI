# 目录：packages/model-runtime/src

## 它负责什么

`packages/model-runtime/src` 是 LobeHub 的“模型运行时适配层”。它把不同 AI 服务商的 SDK、HTTP 协议、流式响应格式、错误结构、模型列表、用量统计、图片/视频/语音/Embedding 等能力，统一包装成一个应用内部可调用的 `ModelRuntime` 门面。

从 `package.json` 看，这个包名是 `@lobechat/model-runtime`，主出口是 `./src/index.ts`。业务代码不应该直接理解 OpenAI、Anthropic、Google、Bedrock、Ollama、ComfyUI 等每个 provider 的细节，而是通过这里暴露的统一类型和方法调用，例如：

- `ModelRuntime.chat(...)`
- `ModelRuntime.embeddings(...)`
- `ModelRuntime.generateObject(...)`
- `ModelRuntime.createImage(...)`
- `ModelRuntime.createVideo(...)`
- `ModelRuntime.models(...)`
- `AgentRuntimeError`
- `ChatStreamPayload`
- `consumeStreamUntilDone`

一句话概括：这个目录负责把“上层业务的一套模型调用语义”翻译成“各家模型服务商能理解的请求”，再把“各家服务商不同的响应”翻译回 LobeHub 统一协议。

## 关键组成

`src/index.ts` 是公共出口。它集中导出常量、核心类、兼容工厂、RouterRuntime、用量换算器、helpers、provider 类、types 和部分 utils。业务层通常从 `@lobechat/model-runtime` 引入，而不是深入引用子路径。

`core/BaseAI.ts` 定义 provider 运行时接口 `LobeRuntimeAI`。这个接口是所有 provider 的共同能力面，但每个方法都是可选的：`chat`、`createImage`、`createVideo`、`embeddings`、`generateObject`、`models`、`pullModel`、`textToSpeech` 等。也就是说，一个 provider 可以只支持聊天，不支持图片或视频。`LobeOpenAICompatibleRuntime` 则是 OpenAI-compatible provider 的抽象基类。

`core/ModelRuntime.ts` 是统一门面。它持有一个具体 provider runtime，并在调用前后插入生命周期 hooks。`chat` 会先检查底层 runtime 是否实现了 `chat`，再执行 `beforeChat`，然后调用 `_runtime.chat(...)`，并在流结束时把 `onChatFinal` 合并进 `options.callback.onFinal`。`embeddings` 和 `generateObject` 也有类似的前置、完成、错误 hook。这里的 hook 用于预算检查、计费、追踪、错误记录等横切逻辑。

`runtimeMap.ts` 是 provider id 到实现类的注册表，例如 `openai -> LobeOpenAI`、`anthropic -> LobeAnthropicAI`、`google -> LobeGoogleAI`、`deepseek -> LobeDeepSeekAI`、`ollama -> LobeOllamaAI`、`comfyui -> LobeComfyUI` 等。上层只要拿到 provider 字符串，就可以根据这个 map 初始化对应运行时。

`core/openaiCompatibleFactory` 是非常重要的复用层。大量服务商都兼容 OpenAI Chat Completions 或 Responses API，因此不必每家都手写完整 runtime。`createOpenAICompatibleRuntime(...)` 接收 `provider`、`baseURL`、`apiKey`、`chatCompletion.handlePayload`、`models`、`createImage`、`createVideo`、`generateObject`、错误类型、debug 开关等配置，生成一个实现了 `LobeRuntimeAI` 的运行时类。

`core/anthropicCompatibleFactory` 是 Anthropic 协议复用层。它负责构造 Anthropic messages/tools/search/thinking/cache/max_tokens 等请求，并把 Anthropic 流式响应转成统一流协议。DeepSeek 这类既有 OpenAI-compatible 又有 Anthropic-compatible 通道的 provider，会在自己的目录里组合这些工厂。

`core/contextBuilders` 负责消息上下文转换。例如 OpenAI、Anthropic、Google、HuggingFace 的消息格式不同，业务层传入的是统一的 `ChatStreamPayload.messages`，这里负责变成目标 SDK 所需结构。

`core/streams` 是流式响应标准化层。`protocol.ts` 定义统一的 `StreamProtocolChunk` 类型，流 chunk 可以是 `text`、`reasoning`、`tool_calls`、`grounding`、`usage`、`speed`、`stop`、`error`、`base64_image`、`content_part` 等。OpenAI、Anthropic、Google、Ollama、Qwen、Spark、Bedrock 等 provider 都有自己的 stream transformer，最终输出统一协议。

`core/usageConverters` 负责把 provider 返回的 token/image/video 用量转换成 LobeHub 的 `ModelUsage`，并结合 `model-bank` 里的 pricing 计算成本。它是计费、统计、性能展示的基础。

`providers/*` 是具体服务商实现。比如 `providers/openai/index.ts` 使用 `createOpenAICompatibleRuntime(params)` 生成 `LobeOpenAI`，并针对 OpenAI 的 Responses API、search、reasoning、service tier flex、模型列表做特殊处理。`providers/google/index.ts` 则直接实现 `LobeRuntimeAI`，因为 Gemini SDK、消息格式、安全设置、thinking、图片模态、工具调用都和 OpenAI 差异很大。`providers/deepseek/index.ts` 展示了更复杂的 provider：它既处理 DeepSeek OpenAI payload，也处理 DeepSeek Anthropic payload，并对 reasoning/thinking 历史做兼容。

`types/*` 是运行时的公共类型层。`types/chat.ts` 中的 `ChatStreamPayload` 是聊天请求核心结构，包含 `model`、`messages`、`temperature`、`max_tokens`、`tools`、`thinking`、`reasoning_effort`、`enabledSearch`、`response_format`、`imageAspectRatio`、`urlContext` 等统一字段。`types/image.ts`、`video.ts`、`embeddings.ts`、`tts.ts`、`structureOutput.ts` 分别描述其他能力。

`utils/*` 是错误、模型、流、URL、JSON、安全解析等辅助工具。例如 `createError` 构造 `AgentRuntimeError`，`handleOpenAIError` 处理 OpenAI 风格错误，`resolveSafeMaxTokens` 做上下文窗口预检查，`getModelPricing` 查询价格，`postProcessModelList` 处理模型列表，`consumeStream` 消费流直到结束。

## 上下游关系

上游输入主要来自服务端模块和 API 路由。根据调用方搜索结果，`src/server/modules/ModelRuntime` 会初始化这个包里的 `ModelRuntime`，并被大量业务服务复用，例如聊天接口、模型列表接口、图片/视频生成、知识库、记忆、任务生命周期、follow-up action、AgentRuntime 等。

典型调用方包括：

- `src/app/(backend)/webapi/chat/[provider]/route.ts`：初始化 runtime 后执行聊天。
- `src/app/(backend)/webapi/models/[provider]/route.ts`：调用 `models()` 拉取模型列表。
- `src/server/routers/async/image.ts`、`video.ts`：调用图片/视频生成能力。
- `src/server/services/knowledgeBase/index.ts`：调用 embedding 或模型能力。
- `src/server/modules/AgentRuntime/RuntimeExecutors.ts`：Agent 执行过程中初始化模型 runtime。
- 前端错误展示也会引用 `AgentRuntimeErrorType`，例如 conversation error UI 和生成错误状态。

下游依赖则是各家 provider SDK 和内部模型资料库。`package.json` 显示它依赖 `openai`、`@anthropic-ai/sdk`、`@google/genai`、`@aws-sdk/client-bedrock-runtime`、`ollama`、`replicate`、`@fal-ai/client`、`@huggingface/inference`，同时依赖 `model-bank`、`@lobechat/business-model-bank`、`@lobechat/types`、`@lobechat/utils` 等内部包。

所以它位于“业务服务”和“外部模型服务商”之间：上面接 LobeHub 的聊天、Agent、生成、知识库等业务，下面接 OpenAI/Anthropic/Gemini/Bedrock/Ollama/ComfyUI 等外部或本地模型运行环境。

## 运行/调用流程

一次普通聊天调用大致是：

1. 业务层拿到用户、provider、模型配置、keyVault 等信息。
2. `src/server/modules/ModelRuntime` 根据 provider 创建具体 provider runtime。根据当前片段推断，这一步会用到 `providerRuntimeMap`，把 provider id 映射到 `LobeOpenAI`、`LobeGoogleAI` 等类。
3. 具体 provider runtime 被包进 `new ModelRuntime(runtime, hooks)`。
4. 业务层构造统一的 `ChatStreamPayload`，里面包含 `model`、`messages`、采样参数、tools、thinking、search 等。
5. 调用 `modelRuntime.chat(payload, options)`。
6. `ModelRuntime.chat` 执行 `beforeChat` hook，可用于预算、权限或限额检查。
7. `ModelRuntime` 把 `onChatFinal` hook 注入 `options.callback.onFinal`，保证原有 callback 和全局 hook 都会执行。
8. 底层 provider 的 `chat` 被调用。
9. 如果是 OpenAI-compatible provider，工厂生成的 runtime 会用 `handlePayload` 转换请求，调用 OpenAI SDK 或兼容接口，再用 `OpenAIStream` / `OpenAIResponsesStream` 转成统一 `ReadableStream`。
10. 如果是 Google 这类自实现 provider，则 provider 自己构造 SDK payload、调用 Gemini API，再通过 `GoogleGenerativeAIStream` 转成统一流协议。
11. 流式 chunk 输出统一的 `StreamProtocolChunk`，包含文本、reasoning、tool calls、usage、grounding、stop 等。
12. 流结束后触发 `onFinal`，业务可记录 usage、cost、latency、trace。
13. 如果发生错误，`ModelRuntime` 调用对应 `onChatError` hook，然后继续抛出错误，由 API 路由或中间件格式化响应。

结构化输出 `generateObject`、Embedding、图片、视频的流程类似，只是底层调用不同能力方法。图片/视频还会涉及 `createImage`、`createVideo`、`handlePollVideoStatus`、`handleCreateVideoWebhook` 等接口。

## 小白阅读顺序

建议先读 `src/index.ts`，看这个包对外暴露了什么。这里能快速建立“公共 API 面”的概念。

第二步读 `src/core/BaseAI.ts`，重点看 `LobeRuntimeAI`。它告诉你一个 provider 最多可以实现哪些能力，也能理解为什么很多方法是可选的。

第三步读 `src/core/ModelRuntime.ts`，理解统一门面的价值：它不关心 OpenAI 还是 Google，只关心底层 runtime 有没有对应方法，并统一处理 hooks、错误和最终回调。

第四步读 `src/runtimeMap.ts`，把 provider id 和具体实现对应起来。这个文件适合当“服务商目录”看。

第五步读 `src/types/chat.ts` 和 `src/core/streams/protocol.ts`。前者是统一请求结构，后者是统一响应结构。理解这两个类型后，再看 provider 代码会轻松很多。

第六步读 `src/core/openaiCompatibleFactory/index.ts`。这是最多 provider 复用的核心工厂，读懂它就能看懂大量 `providers/*/index.ts` 为什么很短。

第七步抽样 provider：先看 `providers/openai/index.ts`，再看 `providers/deepseek/index.ts`，最后看 `providers/google/index.ts`。这三个分别代表“标准 OpenAI provider”“复杂兼容 provider”“非 OpenAI 协议自实现 provider”。

第八步再看 `core/streams` 和 `core/usageConverters`。这两块细节较多，适合在已经理解主流程后阅读。

## 常见误区

不要把 `ModelRuntime` 理解成真正调用外部 API 的地方。它更像统一门面和生命周期包装器；真正调用外部 SDK 的逻辑在具体 provider 或兼容工厂里。

不要以为所有 provider 都支持所有能力。`LobeRuntimeAI` 的方法大多是可选的，某些 provider 只支持 `chat`，某些支持 `models`，某些支持图片或视频。`ModelRuntime.chat` 会显式检查 `chat` 是否存在，但其他方法多是可选链调用。

不要把 `ChatStreamPayload` 当成 OpenAI 原生参数。它是 LobeHub 的内部统一抽象，里面有 OpenAI 字段，也有 Claude/Gemini/业务自定义字段，例如 `thinking`、`enabledSearch`、`urlContext`、`imageAspectRatio`。各 provider 必须把它转换成自己的真实请求。

不要忽略 stream 协议层。上层消费的不是各家 SDK 原始 chunk，而是 `StreamProtocolChunk` 这套统一格式。工具调用、推理内容、引用、usage、错误都要在 stream transformer 中被标准化。

不要认为 OpenAI-compatible provider 完全一样。`createOpenAICompatibleRuntime` 提供通用骨架，但 provider 仍可能通过 `handlePayload`、`handleStream`、`handleError`、`models.transformModel` 等钩子处理差异，比如 Responses API、reasoning、search、上下文窗口、模型列表过滤。

不要把 `runtimeMap.ts` 和 `index.ts` 混为一谈。`index.ts` 是包的导出面；`runtimeMap.ts` 是运行时初始化时用的 provider 注册表。有些 provider 可能在 map 中注册，但不一定从主入口显式导出类给外部直接使用。

不要跳过测试文件。这个目录下每个核心工具、stream transformer、provider 基本都有对应 `.test.ts`。如果要改 provider 行为，测试往往比文档更能说明预期边界。
