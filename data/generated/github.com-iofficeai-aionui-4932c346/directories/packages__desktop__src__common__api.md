# 目录：packages/desktop/src/common/api

## 它负责什么

`packages/desktop/src/common/api` 是桌面端公共层里面向 AI Provider 的客户端适配目录。它的核心职责不是封装普通 HTTP API，也不是 Electron IPC，而是把不同模型服务商的 SDK 调用统一成一套更接近 OpenAI Chat Completion 的使用方式，并在调用失败时支持多 API Key 轮换、重试和协议转换。

从当前片段看，这个目录围绕三类 Provider 展开：OpenAI 兼容接口、Gemini / Vertex AI、Anthropic / Claude。上层只需要拿到 `TProviderWithModel` 这类 provider 配置，然后通过 `ClientFactory.createRotatingClient()` 创建对应客户端；下层则由 `OpenAIRotatingClient`、`GeminiRotatingClient`、`AnthropicRotatingClient` 分别对接官方 SDK 或兼容 SDK。

它还有一个重要设计：内部尽量用 OpenAI 风格的 `createChatCompletion()` 作为统一接口。对 OpenAI 兼容服务，它直接调用 `client.chat.completions.create()`；对 Gemini 和 Anthropic，它先用 converter 把 OpenAI 风格请求转换成目标服务商请求，再把响应转换回 OpenAI 风格响应。这样调用方可以用相对稳定的数据结构处理文本和图片结果。

## 直接子目录地图

这个目录当前没有直接子目录，是一个扁平 API 适配层。文件大致可以按职责分成四组：

`index.ts` 是导出入口，向外暴露主要客户端、工厂和类型。

`ClientFactory.ts` 是创建入口，根据 provider 的平台、模型协议和认证类型选择具体客户端，并处理 new-api 网关的 base URL 规范化、OpenAI 兼容请求头、代理配置等。

`RotatingApiClient.ts`、`ApiKeyManager.ts` 是通用基础设施。前者定义重试与执行模板，后者负责多 key 解析、随机初始 key、失败 key 临时黑名单和环境变量同步。

`OpenAIRotatingClient.ts`、`GeminiRotatingClient.ts`、`AnthropicRotatingClient.ts` 是三种具体客户端包装器。它们都继承 `RotatingApiClient`，区别在于创建 SDK client 的方式、默认模型、原生调用方法和是否需要协议转换。

`ProtocolConverter.ts`、`OpenAI2GeminiConverter.ts`、`OpenAI2AnthropicConverter.ts` 是协议转换层。`ProtocolConverter` 定义抽象接口；两个具体 converter 负责把 OpenAI chat message、工具调用、图片输入、停止原因、usage 等字段映射到 Gemini 或 Anthropic 的格式。

## 关键入口

最重要的入口是 `packages/desktop/src/common/api/ClientFactory.ts` 里的 `ClientFactory.createRotatingClient(provider, options)`。它接收 `TProviderWithModel`，通过 `getProviderAuthType()` 判断 provider 应该走 `AuthType.USE_OPENAI`、`AuthType.USE_GEMINI`、`AuthType.USE_VERTEX_AI` 还是 `AuthType.USE_ANTHROPIC`，然后返回联合类型 `RotatingClient`。

`normalizeNewApiBaseUrl()` 也是关键函数。它只服务于 new-api 网关场景：先剥离已有的 `/v1` 或 `/v1beta` 后缀，再按目标协议重新补 URL 后缀。OpenAI SDK 需要 `/v1`，Gemini 和 Anthropic SDK 则使用根地址。这里的作用是避免用户配置的 base URL 已经带有协议路径时，经过不同 SDK 再拼接出错误路径。

`packages/desktop/src/common/api/index.ts` 是模块导出入口，但当前它没有导出 Gemini 客户端和 converter 类型，只导出了 `OpenAIRotatingClient`、`AnthropicRotatingClient`、`RotatingApiClient`、`ClientFactory` 及相关类型。根据当前片段推断，仓库内更常用的是直接从 `ClientFactory.ts` 引入工厂和 `RotatingClient`，而不是全部通过 `index.ts` 聚合导入；依据是 `packages/desktop/src/common/chat/imageGenCore.ts` 直接 import `@/common/api/ClientFactory`。

## 主流程位置

当前能看到的主要调用流程在 `packages/desktop/src/common/chat/imageGenCore.ts`。该文件在处理图片生成请求时，会先构造 OpenAI 风格的 `messages`，再调用：

`ClientFactory.createRotatingClient(provider, { proxy, rotatingOptions })`

工厂根据 provider 创建具体客户端后，上层继续调用：

`rotatingClient.createChatCompletion({ model: provider.use_model, messages }, { signal, timeout })`

如果实际客户端是 OpenAI 兼容服务，流程进入 `OpenAIRotatingClient.createChatCompletion()`，再通过 `RotatingApiClient.executeWithRetry()` 执行 SDK 调用。如果实际客户端是 Gemini，流程进入 `GeminiRotatingClient.createChatCompletion()`，先由 `OpenAI2GeminiConverter.convertRequest()` 转换请求，再调用 `client.models.generateContent()`，最后用 `convertResponse()` 转回统一响应。如果实际客户端是 Anthropic，流程类似，进入 `AnthropicRotatingClient.createChatCompletion()`，转换为 `client.messages.create()` 所需结构，再转回 OpenAI 风格响应。

重试和 key 轮换集中在 `RotatingApiClient.executeWithRetry()`。它会捕获错误，判断状态码是否属于 401、429、503 或其他 5xx。如果存在多个 key，且错误可重试、还没到最后一次尝试，就调用 `ApiKeyManager.rotateKey()`，把当前 key 加入 90 秒黑名单，切换到下一个可用 key，重新初始化 SDK client，再按递增 delay 继续执行。没有多 key 时，它仍会对可重试错误做普通重试。

provider 认证类型判断不在本目录，而在邻近的 `packages/desktop/src/common/utils/platformAuthType.ts`。它会优先使用 provider 显式的 `auth_type`；如果是 new-api 平台，还会读取 `model_protocols[use_model]` 来按模型覆盖协议；否则按 platform 字符串推断 Gemini、Vertex AI、Anthropic、Bedrock 或默认 OpenAI 兼容协议。

## 推荐阅读顺序

建议先读 `ClientFactory.ts`，因为这里能最快建立“provider 配置如何变成具体 SDK client”的地图。重点看 `createRotatingClient()` 的 `switch (authType)`，以及 new-api 的 `normalizeNewApiBaseUrl()`。

第二步读 `RotatingApiClient.ts` 和 `ApiKeyManager.ts`。这两个文件解释了为什么具体客户端只需要提供 `createClientFn` 和业务调用函数，就能获得统一的重试、多 key、黑名单和状态查询能力。

第三步读三个具体客户端：`OpenAIRotatingClient.ts`、`GeminiRotatingClient.ts`、`AnthropicRotatingClient.ts`。建议从 OpenAI 开始，因为它最直接；再看 Gemini 和 Anthropic，可以看清楚它们为什么需要 converter，以及它们在默认模型、base URL、环境变量读取上的差异。

第四步读 `ProtocolConverter.ts`、`OpenAI2GeminiConverter.ts`、`OpenAI2AnthropicConverter.ts`。这里适合在理解主流程后再看，否则容易陷入字段映射细节。overview 阶段只需要掌握：Gemini converter 当前主要处理第一条 message、base64 图片、工具函数名清洗、图片生成响应；Anthropic converter 处理 system message 拆分、user / assistant 消息交替、tool schema、stop reason 和 usage 映射。

最后再回到调用方 `packages/desktop/src/common/chat/imageGenCore.ts`，看它如何把统一响应中的 `choice.message.content` 和 `choice.message.images` 继续加工成图片生成结果。

## 常见误区

不要把这个目录理解成“所有后端 API 请求层”。它更准确的角色是“AI 模型服务商 SDK 适配层”，服务对象是 OpenAI 兼容、Gemini、Anthropic 这类模型调用。

不要认为 `createChatCompletion()` 一定是 OpenAI SDK 原生方法。对 Gemini 和 Anthropic 来说，它是本项目包装出来的统一方法，内部会走协议转换，再调用各自 SDK 的 `generateContent()` 或 `messages.create()`。

不要忽略 `AuthType` 的来源。provider 的 `platform` 只是默认推断依据；如果 provider 显式设置了 `auth_type`，或者 new-api provider 对当前 `use_model` 配置了 `model_protocols`，实际创建的客户端可能和平台名直觉不一致。

不要把多 key 轮换理解成每次请求轮询。`ApiKeyManager` 会在多 key 场景随机选择初始 key，但正常请求不会主动轮询；只有遇到可重试错误时，当前 key 才会被临时拉黑并切换。

不要在调用方绕过 `ClientFactory` 自己 new 客户端，除非有明确原因。工厂里包含 new-api base URL 规范化、代理注入、默认 retry 配置和 provider 协议判断，绕过后容易造成不同 Provider 行为不一致。

不要假设 converter 支持完整 OpenAI 协议。根据当前片段，Gemini converter 对消息结构、HTTP 图片 URL、工具名格式和图片响应都有特定限制；Anthropic converter 也需要处理 Anthropic 对消息顺序、system 参数、temperature / top_p 同时出现等限制。这些转换是兼容层，不是无损协议桥。
