# 目录：packages/model-runtime/src/core

## 它负责什么

`packages/model-runtime/src/core` 是 `@lobechat/model-runtime` 的“运行时内核层”。它不直接代表某一个模型供应商，而是把不同供应商的 SDK、请求格式、流式输出、用量统计、错误和 fallback 路由，统一成 LobeHub 内部可调用的 runtime 接口。

可以把它理解成三层：

第一层是统一接口：`BaseAI.ts` 定义 `LobeRuntimeAI`，规定一个模型运行时可以具备 `chat`、`generateObject`、`embeddings`、`createImage`、`createVideo`、`textToSpeech`、`models`、`pullModel` 等能力。

第二层是外层生命周期包装：`ModelRuntime.ts` 接收一个具体 `LobeRuntimeAI` 实例，并在调用前后插入 hooks，例如 `beforeChat`、`onChatFinal`、`onChatError`、`beforeEmbeddings`、`onEmbeddingsFinal`。这些 hooks 适合做预算检查、计费、追踪、错误记录等跨 provider 的逻辑。

第三层是 provider 适配基础设施：`openaiCompatibleFactory`、`anthropicCompatibleFactory`、`RouterRuntime`、`contextBuilders`、`streams`、`usageConverters` 等模块，把不同 API 协议转换成 LobeHub 内部一致的输入输出。

## 关键组成

`BaseAI.ts` 是核心抽象入口。`LobeRuntimeAI` 是面向业务层的最小统一接口，各 provider 类只要实现其中若干方法即可。`LobeOpenAICompatibleRuntime` 是 OpenAI-compatible provider 的抽象基类，要求实现 `client`、`chat`、`createImage`、`generateObject`、`models`、`embeddings`。

`ModelRuntime.ts` 是业务调用时最常接触的包装器。它不会自己拼 provider 请求，而是把请求转给 `_runtime`。它的价值在于统一处理能力缺失、生命周期 hook、最终回调合并、错误 hook 和 timing 日志。例如 `chat()` 会先判断底层 runtime 是否支持 `chat`，再执行 `beforeChat`，然后调用底层 `_runtime.chat()`；如果配置了 `onChatFinal`，它会注入到 `options.callback.onFinal` 中，并保证 hook 失败不会影响主响应完成。

`RouterRuntime/` 用于构造“带路由与 fallback 能力”的 runtime。`createRouterRuntime()` 返回一个 `UniformRuntime` 类。它根据 `routers` 配置选择具体 provider：优先按 `baseURLPattern` 匹配，其次按 `models` 匹配，最后使用最后一个 router 作为 fallback。每个 router 的 `options` 可以是数组，数组里的多个渠道会按顺序尝试，失败后进入下一个 fallback。`baseRuntimeMap.ts` 把 `apiType` 映射到具体 provider 类，如 `openai`、`anthropic`、`google`、`bedrock`、`vertexai`、`qwen`、`zhipu` 等。`apiTypes.ts` 约束了可路由的 provider 类型。

`openaiCompatibleFactory/` 是 OpenAI-compatible API 的通用工厂。它负责把 LobeHub 的 `ChatStreamPayload` 转成 OpenAI Chat Completions 或 Responses API 请求，支持 `handlePayload`、`handleStream`、`handleError`、`contextPreFlight`、`useResponse`、`useResponseModels` 等扩展点。它还集成图像、视频、结构化输出、模型列表、流式转换和 OpenAI usage 转换。

`anthropicCompatibleFactory/` 是 Anthropic-compatible API 的通用工厂。它围绕 Anthropic SDK 构建请求，使用 `contextBuilders/anthropic` 构造 messages/tools/search tool，使用 `AnthropicStream` 统一流输出，并处理 Anthropic/DeepSeek Anthropic 兼容接口中的 max tokens、cache TTL、错误转换、payload 诊断等细节。

`contextBuilders/` 负责把内部消息格式转换成不同 provider 接受的上下文格式。已看到 `openai.ts` 会处理 `image_url`、`video_url` 的 URL 到 base64 转换，过滤内部 `thinking` content part，保留或补齐 DeepSeek 系列的 `reasoning_content`，并把 Chat Completions message 转换为 Responses API input。目录内还有 `anthropic.ts`、`google.ts`、`huggingface.ts`，分别服务不同协议。

`streams/` 定义流式响应的统一协议。`protocol.ts` 里的 `StreamProtocolChunk` 把输出归一为 `text`、`tool_calls`、`reasoning`、`content_part`、`grounding`、`usage`、`speed`、`error`、`stop` 等类型。`StreamContext` 保存流处理过程中的临时状态，例如 tool call、thinking、citation、usage。其他文件如 `anthropic.ts`、`model.ts`、`ollama.ts`、`qwen.ts`、`spark.ts`、`cloudflare.ts` 则把各 provider 的流片段翻译成这个统一协议。

`usageConverters/` 负责把不同 provider 的 usage 字段转成 LobeHub 统一的 `ModelUsage`，并暴露成本估算工具，如 `estimateChatCostFromMessages`、`computeImageCost`、`computeVideoCost`、`resolveImageSinglePrice`、`resolveVideoSinglePrice`。

`parameterResolver.ts` 从文件名和调用处看，负责统一采样参数解析。根据当前片段推断，`openaiCompatibleFactory` 和 `anthropicCompatibleFactory` 都会调用 `resolveModelSamplingParameters`，用于把温度、top_p、reasoning/thinking 等模型参数按 provider 支持情况整理后再发送。

## 上下游关系

上游入口主要来自 `packages/model-runtime/src/index.ts`。该入口导出了 `BaseAI`、`ModelRuntime`、`createOpenAICompatibleRuntime`、`RouterRuntime`、`usageConverters` 和所有 provider 类，所以外部一般通过 `@lobechat/model-runtime` 使用这些能力。

再往上，业务层会先根据 provider 和用户配置初始化 runtime。`ModelRuntime.initializeWithProvider(provider, params, hooks)` 会从 `providerRuntimeMap` 找到具体 provider 类，找不到则回退到 `LobeOpenAI`，然后包成 `new ModelRuntime(runtimeModel, hooks)`。注释中提到服务端常见入口是 `src/app/api/chat/agentRuntime.ts: initAgentRuntimeWithUserPayload`，客户端常见入口是 `src/services/chat.ts: initializeWithClientStore`；这是根据代码注释得出的调用线索。

下游是 `packages/model-runtime/src/providers/*` 下的具体 provider 实现。例如 `baseRuntimeMap.ts` 依赖 `LobeAnthropicAI`、`LobeOpenAI`、`LobeGoogleAI`、`LobeBedrockAI`、`LobeVertexAI` 等类。`core` 不关心具体 provider 内部如何鉴权或调用 SDK，只要求它们符合 `LobeRuntimeAI`。

横向依赖包括：

`types/`：定义 `ChatStreamPayload`、`ChatMethodOptions`、`GenerateObjectPayload`、`EmbeddingsPayload`、图像/视频 payload、错误类型等。

`utils/`：提供错误包装、流响应、模型价格、上下文窗口检查、URL 脱敏、安全 JSON 解析等工具。

`model-bank` / `@lobechat/types`：提供模型卡片、价格、usage、trace、performance 等领域类型。

第三方 SDK：`openai`、`@anthropic-ai/sdk`、`@google/genai` 等由 factory 或 provider 使用。

## 运行/调用流程

一次普通聊天调用大致如下：

1. 业务层根据 provider、apiKey、baseURL、用户信息等初始化具体 provider runtime。
2. 该 runtime 被包进 `ModelRuntime`，同时可传入 hooks。
3. 调用 `ModelRuntime.chat(payload, options)`。
4. `ModelRuntime` 检查底层 `_runtime.chat` 是否存在；不存在则抛 `ProviderBizError`。
5. 执行 `beforeChat`，例如预算检查或风控。
6. 如果有 `onChatFinal`，把它合并进 `options.callback.onFinal`，并保留原有 `onFinal`。
7. 调用具体 provider 的 `chat`。
8. provider 内部通常通过 `contextBuilders` 构造请求，通过 factory 调用 SDK，通过 `streams` 把响应转成统一流。
9. 流结束时触发 `onFinal`，再执行 `onChatFinal`，可做 usage 记录、计费或 trace。
10. 如果中途异常，`ModelRuntime` 调用 `onChatError`，然后继续把错误抛给上层。

如果使用 `createRouterRuntime()`，流程中会多一段路由逻辑：

1. `UniformRuntime` 接收全局 options。
2. 每次请求时根据 model 调用 `resolveRouters()`。
3. `resolveMatchedRouter()` 先看 `baseURLPattern`，再看 `models`，最后 fallback 到最后一个 router。
4. `normalizeRouterOptions()` 把单个 options 或 options 数组统一成数组。
5. `runWithFallback()` 按顺序创建具体 runtime 并请求。
6. 每次尝试都会调用 `onRouteAttempt` 上报成功/失败、耗时、channelId、routerId、apiType 等。
7. 遇到不可重试错误会立即抛出；否则可由 `shouldStopFallback` 决定是否停止 fallback。
8. 全部失败后，根据当前片段可确定会保留 `lastError` 并继续错误处理；最终抛出行为在未读取片段之外，根据当前片段推断会向上抛出最后一次错误或包装错误。

图像、视频、embedding、结构化输出也是相似模式：`ModelRuntime` 只做统一 hook 和能力转发，实际协议转换由 provider/factory 完成。

## 小白阅读顺序

建议先读 `BaseAI.ts`。这里的 `LobeRuntimeAI` 是整个目录的语言：看懂它，就知道一个 provider 需要对外提供哪些能力。

第二步读 `ModelRuntime.ts`。重点看 `chat()`、`applyHooks()`、`generateObject()`、`embeddings()` 和 `initializeWithProvider()`。这能帮助你理解业务层为什么不直接调用 provider，而是先包一层 runtime。

第三步读 `RouterRuntime/index.ts`、`apiTypes.ts`、`baseRuntimeMap.ts`。先知道路由支持哪些 provider，再进入 `createRuntime.ts`。读 `createRuntime.ts` 时只抓四个函数：`resolveRouters`、`resolveMatchedRouter`、`createRuntimeFromOption`、`runWithFallback`。

第四步读 `openaiCompatibleFactory/index.ts`。OpenAI-compatible 是很多 provider 的共同基础，理解它之后，再看具体 provider 会轻松很多。关注 `handlePayload`、`handleStream`、`handleError`、`useResponse`、`contextPreFlight` 这些扩展点。

第五步读 `contextBuilders/openai.ts` 和 `streams/protocol.ts`。前者解释“请求发出去前怎么整理 messages”，后者解释“响应回来后如何统一成内部流协议”。

第六步再看 `usageConverters/index.ts` 和各 provider usage converter。它们不决定请求是否成功，但影响计费、统计和最终 usage 展示。

最后读测试文件，如 `ModelRuntime.test.ts`、`RouterRuntime/createRuntime.test.ts`、`streams/*.test.ts`、`contextBuilders/*.test.ts`。这些测试比实现更适合验证边界条件，例如 fallback、tool call、reasoning、usage、错误流。

## 常见误区

不要把 `ModelRuntime` 当成具体模型 provider。它只是包装器，真正请求 OpenAI、Anthropic、Google 等服务的是 `providers/*` 或由 factory 生成的 provider runtime。

不要以为所有 provider 都必须实现 `LobeRuntimeAI` 的全部方法。接口里大部分方法是可选的，所以调用前要处理能力缺失。`ModelRuntime.chat()` 对缺失 `chat` 做了显式错误处理，而 `createImage()`、`models()` 等方法则是可选转发。

不要把 `RouterRuntime` 理解成简单的 provider 别名。它同时处理动态 routers、模型匹配、baseURL 匹配、多渠道 fallback、跨 apiType fallback、Vertex AI 特殊初始化、尝试结果上报和停止 fallback 策略。

不要认为 OpenAI-compatible 就等于 OpenAI 官方 API。`openaiCompatibleFactory` 专门提供大量扩展点，是为了兼容 DeepSeek、Moonshot、MiniMax、NVIDIA、OpenRouter 等不同“长得像 OpenAI 但细节不同”的接口。

不要忽略 `contextBuilders`。很多看似 provider 报错的问题，实际可能发生在上下文转换阶段，例如图片/视频是否要转 base64、Responses API tool call 是否配对、DeepSeek thinking 模式是否需要回传 `reasoning_content`。

不要把流式输出直接等同于 provider SDK 的 chunk。LobeHub 内部使用 `StreamProtocolChunk` 抽象，最终业务层消费的是 `text`、`tool_calls`、`reasoning`、`usage` 等统一事件，而不是原始 SDK chunk。

不要把 usage converter 当作展示层工具。它与成本估算、计费、trace、最终回调都有关系；如果新增 provider 或新增能力，usage 字段不统一会影响后续统计链路。
