# 子系统：packages/ai/src/providers

## 解决什么问题

`packages/ai/src/providers` 是 `packages/ai` 的模型供应商适配层。它把 OpenAI、Anthropic、Google、Mistral、Amazon Bedrock、Azure OpenAI、Cloudflare、GitHub Copilot 等外部模型 API 的差异，收敛成包内统一的 `stream` / `streamSimple` 接口，并统一输出 `AssistantMessageEventStream`。

这个目录不负责“选哪个模型”，也不直接管理用户配置；它负责在已经拿到 `Model`、`Context`、`StreamOptions` 后，把内部消息、工具调用、图片输入、reasoning/thinking、缓存、请求头、响应流、usage/cost 等概念翻译成各供应商真实 API 能接受的 payload，再把供应商返回的流式事件翻译回统一的 `AssistantMessage` 事件协议。

因此它是一个典型的边界层：上游代码只面对 `packages/ai/src/stream.ts` 的统一函数，下游真实 SDK 和 HTTP 协议细节被封装在各 provider 文件内。

## 相关目录和文件

核心注册入口是 `packages/ai/src/providers/register-builtins.ts`。它调用 `registerApiProvider` 注册内置文本模型 API，例如 `anthropic-messages`、`openai-completions`、`mistral-conversations`、`openai-responses`、`azure-openai-responses`、`openai-codex-responses`、`google-generative-ai`、`google-vertex`、`bedrock-converse-stream`。

统一注册表在 `packages/ai/src/api-registry.ts`，对外提供 `registerApiProvider`、`getApiProvider`、`getApiProviders`、`unregisterApiProviders`、`clearApiProviders`。`packages/ai/src/stream.ts` 会先导入 `./providers/register-builtins.ts` 触发内置注册，然后根据 `model.api` 查找 provider 并调用。

具体实现分散在 `openai-responses.ts`、`openai-completions.ts`、`anthropic.ts`、`google.ts`、`google-vertex.ts`、`mistral.ts`、`amazon-bedrock.ts`、`azure-openai-responses.ts`、`openai-codex-responses.ts` 等文件中。跨 provider 复用逻辑主要在 `transform-messages.ts`、`simple-options.ts`、`openai-responses-shared.ts`、`openai-prompt-cache.ts`、`google-shared.ts`、`github-copilot-headers.ts`、`cloudflare.ts`。

图片生成的 provider 是独立小分支，位于 `packages/ai/src/providers/images`，通过 `packages/ai/src/images-api-registry.ts` 注册，目前片段中看到内置 `openrouter-images`。

相关上层类型定义集中在 `packages/ai/src/types.ts`；模型元数据来自 `packages/ai/src/models.ts`、`packages/ai/src/models.generated.ts`、`packages/ai/src/image-models.ts`、`packages/ai/src/image-models.generated.ts`；API key 补全来自 `packages/ai/src/env-api-keys.ts`。

## 核心对象

`ApiProvider` 是文本 provider 的注册单元，包含 `api`、`stream`、`streamSimple`。`api` 是能力协议名，不等同于 `provider`。例如多个 provider 可能共用 OpenAI-compatible 协议，但仍有不同的 `provider`、`baseUrl`、headers 或兼容性开关。

`StreamFunction` 是核心执行契约：输入 `Model<TApi>`、`Context`、可选 `StreamOptions`，返回 `AssistantMessageEventStream`。注释里明确要求：调用后请求失败、模型失败、运行时失败应编码进返回的 stream，而不是直接抛出；错误终止要产生 `stopReason` 为 `error` 或 `aborted` 的 `AssistantMessage`。

`streamSimple` 是更上层、更统一的调用入口，接受 `SimpleStreamOptions`，把通用 `reasoning`、`thinkingBudgets`、`temperature`、`maxTokens`、`headers`、`timeoutMs`、`maxRetries` 等选项映射成 provider 专属选项。`simple-options.ts` 的 `buildBaseOptions` 负责复制通用字段，`adjustMaxTokensForThinking` 负责 reasoning token budget 与最大输出 token 的折算。

`transformMessages` 是跨模型、跨供应商对话续接的关键对象。它会处理不支持图片输入的模型，把图片替换为文本占位；会在跨模型时清理或降级 thinking 内容；会规范化工具调用 ID；还会为缺失结果的 tool call 合成错误型 `toolResult`，避免下游 API 因工具调用链不完整而拒绝请求。

`AssistantMessageEventStream` 是统一输出通道。provider 实现通常先构造一个空的 assistant message，推送 `start`、增量事件，最后推送 `done` 或 `error` 并 `end`。

## 运行流程

调用从 `packages/ai/src/stream.ts` 开始。模块加载时先导入 `providers/register-builtins.ts`，注册内置 provider。业务调用 `stream(model, context, options)` 或 `streamSimple(model, context, options)` 时，会用 `model.api` 到 `api-registry` 查询对应 provider。如果调用方没有显式传 `apiKey`，`stream.ts` 会通过 `getEnvApiKey(model.provider)` 从环境变量补齐。

`register-builtins.ts` 并不会立即加载所有大型 SDK 实现，而是注册 lazy wrapper。第一次调用某个 API 时才通过动态导入加载对应模块，并缓存 module promise。这样可以降低基础包加载成本，也让 Bedrock 这类 Node-only provider 通过 `importNodeOnlyProvider` 做运行时 specifier 处理。lazy 加载失败时，wrapper 会返回一个带 `error` 事件的 `AssistantMessageEventStream`，而不是让异常穿透到调用方。

以 `openai-responses.ts` 为例，`streamSimpleOpenAIResponses` 会把通用选项转换成 `OpenAIResponsesOptions`，根据模型能力 clamp reasoning level，然后调用 `streamOpenAIResponses`。后者创建 OpenAI client，合并模型 headers、调用方 headers、session/cache headers、Cloudflare 或 Copilot 特殊 headers；再由 `buildParams` 通过 `convertResponsesMessages`、`convertResponsesTools` 把内部 `Context` 翻译成 Responses API payload；请求发出前可由 `onPayload` 修改 payload，收到 HTTP response 后通过 `onResponse` 暴露状态和 headers；最后 `processResponsesStream` 把远端流转成内部事件并计算 usage/cost。

## 上下游依赖

上游主要是 `packages/ai/src/stream.ts`、`packages/ai/src/images.ts` 以及更高层的 agent、coding-agent、tui 包。它们通常不关心具体 SDK，只传入 `Model` 和 `Context`，消费统一的 assistant event stream。

横向依赖是 `packages/ai/src/types.ts`、`models.ts`、`env-api-keys.ts`、`utils/event-stream.ts`、`utils/headers.ts`、`utils/json-parse.ts`、`utils/sanitize-unicode.ts`、`utils/hash.ts`、`utils/diagnostics.ts` 等基础设施。provider 文件大量依赖这些工具来保持统一的消息结构、错误格式、usage 统计和安全文本处理。

下游依赖是真实外部 SDK 或协议实现，例如 `openai` SDK、Anthropic SDK、Google/Vertex 接口、AWS Bedrock 客户端、Mistral SDK，以及 OpenAI-compatible HTTP endpoint。根据当前片段推断，Cloudflare、GitHub Copilot、OpenRouter 等 provider 不是全新协议栈，而是在 OpenAI-compatible 或 image API 基础上增加 base URL、headers、鉴权和兼容性处理。

## 修改时最容易踩的坑

第一，不能只改具体 provider 文件而忘记注册。新增文本 API 需要补 `KnownApi` 类型、模型元数据、provider 实现、`register-builtins.ts` 注册项；新增图片 API 则走 `images-api-registry.ts` 和 `providers/images/register-builtins.ts`。

第二，`api` 和 `provider` 不能混用。`api` 表示协议适配器，`provider` 表示服务商或模型来源。`api-registry.ts` 会校验 `model.api` 与注册 provider 的 `api` 是否一致，错配会直接报 `Mismatched api`。

第三，错误处理要进入 stream 协议。`types.ts` 对 `StreamFunction` 的契约要求很明确：请求和运行失败应生成 `error` / `aborted` assistant message。某些 `streamSimple` 在缺少 API key 时仍会同步抛错，这属于当前实现中的入口校验特例；新增 provider 时应尽量贴近已有同类实现。

第四，历史消息不能直接原样发给外部 API。跨模型 thinking signature、工具调用 ID、图片输入、孤儿 tool call 都可能触发供应商校验错误。通常应先经过 `transformMessages` 或复用对应 shared converter。

第五，`onPayload`、`onResponse`、`headers`、`timeoutMs`、`maxRetries`、`signal` 等通用选项要贯穿到真实请求，否则上层调试、取消、超时和自定义请求能力会失效。

第六，Bedrock 是特殊依赖。`register-builtins.ts` 有 `setBedrockProviderModule` 和 Node-only 动态导入逻辑，修改时要考虑浏览器/Node 运行环境差异。

## 推荐阅读顺序

1. 先读 `packages/ai/src/types.ts`，理解 `Api`、`Provider`、`Model`、`Context`、`StreamOptions`、`SimpleStreamOptions`、`AssistantMessage`、`ToolCall`、`Usage` 的统一抽象。
2. 再读 `packages/ai/src/api-registry.ts` 和 `packages/ai/src/stream.ts`，弄清 provider 如何注册、查找、注入环境 API key、返回统一 stream。
3. 阅读 `packages/ai/src/providers/register-builtins.ts`，重点看 lazy loading、错误流包装、内置 API 注册列表。
4. 阅读 `packages/ai/src/providers/transform-messages.ts` 和 `packages/ai/src/providers/simple-options.ts`，这是理解跨供应商兼容性的基础。
5. 选择一个完整 provider 深入，例如 `packages/ai/src/providers/openai-responses.ts`，再配合 `packages/ai/src/providers/openai-responses-shared.ts` 看消息转换、工具转换和响应流处理。
6. 最后按需要阅读具体厂商文件，例如 `anthropic.ts`、`google.ts`、`amazon-bedrock.ts`，对比它们如何把同一套内部协议映射到不同外部 API。
