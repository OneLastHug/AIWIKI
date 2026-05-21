# 目录：packages/model-runtime

## 它负责什么

`packages/model-runtime` 是 LobeHub 对“模型供应商运行时”的统一封装层。它把 OpenAI、Anthropic、Bedrock、Google、Ollama、OpenRouter、DeepSeek、Qwen、Volcengine 等大量模型服务商，抽象成一组统一能力：`chat`、`embeddings`、`generateObject`、`createImage`、`createVideo`、`textToSpeech`、`models`、`pullModel` 等。

从职责上看，它不是 UI 层，也不是业务配置层，而是“模型调用适配层”。上层只需要知道 provider 名称和请求 payload，就可以通过 `ModelRuntime.initializeWithProvider(...)` 得到一个统一的 `ModelRuntime` 实例；下层则由各 provider 类负责把 LobeHub 内部 payload 转换成对应厂商 SDK/API 能理解的参数。

这个包的另一个重要职责是“统一生命周期处理”：`ModelRuntimeHooks` 支持在请求前、请求成功后、请求失败后插入逻辑。例如 `beforeChat` 可做预算检查，`onChatFinal` 可做用量统计或计费，`onChatError` 可做错误记录。也就是说，模型调用并不是简单转发，而是在统一入口里挂上了观测、计费、风控等扩展点。

## 关键组成

`package.json` 定义包名为 `@lobechat/model-runtime`，入口导出为 `./src/index.ts`，还额外导出了 `./vertexai` 指向 `./src/providers/vertexai/index.ts`。依赖里包含 `openai`、`@anthropic-ai/sdk`、`@aws-sdk/client-bedrock-runtime`、`@google/genai`、`ollama`、`replicate`、`@fal-ai/client` 等，说明它直接承担多厂商 SDK 适配。

`src/index.ts` 是公共出口，集中导出：

- `./core/BaseAI`：定义运行时接口 `LobeRuntimeAI` 和 OpenAI 兼容运行时抽象类。
- `./core/ModelRuntime`：统一运行时外壳，负责 hooks、错误转发、能力调用。
- `./core/openaiCompatibleFactory`：生成 OpenAI-compatible provider 的工厂。
- `./core/RouterRuntime`、`usageConverters`、`helpers`、`utils`、`types`：公共协议、工具和转换逻辑。
- 大量 `LobeXXXAI` provider 类：如 `LobeOpenAI`、`LobeAnthropicAI`、`LobeBedrockAI`、`LobeGoogleAI`、`LobeOllamaAI` 等。

`src/runtimeMap.ts` 是 provider 名称到运行时类的注册表。它把字符串 key，例如 `openai`、`anthropic`、`bedrock`、`google`、`ollama`、`deepseek`、`qwen`、`volcengine`，映射到对应的 `LobeXXXAI` 类。`ModelRuntime.initializeWithProvider` 就依赖这个 map 创建具体运行时。如果找不到 provider，会回退到 `LobeOpenAI`。

`src/core/BaseAI.ts` 定义核心接口 `LobeRuntimeAI`。它不是强制所有 provider 都实现所有方法，而是把能力定义成可选方法：

```ts
chat?
embeddings?
generateObject?
createImage?
createVideo?
models?
pullModel?
textToSpeech?
```

这解释了为什么有些 provider 只能聊天，有些支持图片，有些支持 embeddings。上层调用时需要意识到这些能力并非每个 provider 都存在。

`src/core/ModelRuntime.ts` 是最重要的统一入口。它内部持有 `_runtime: LobeRuntimeAI`，对外暴露 `chat`、`embeddings`、`generateObject` 等方法。以 `chat` 为例，流程是先检查 runtime 是否实现 `chat`，再执行 `beforeChat` hook，然后调用具体 provider 的 `chat`，出错时执行 `onChatError`，完成流式响应时通过包装 `options.callback.onFinal` 注入 `onChatFinal`。

`src/core/openaiCompatibleFactory/index.ts` 是 OpenAI 兼容 provider 的核心复用机制。很多供应商的接口与 OpenAI Chat Completions 或 Responses API 类似，因此不需要每个 provider 手写完整逻辑，而是通过 `createOpenAICompatibleRuntime(options)` 传入 provider 名、baseURL、错误处理、payload 改写、模型列表转换、图片/视频生成处理等配置，生成一个完整运行时。

`src/providers/openai/index.ts` 是一个代表性 provider。它通过 `createOpenAICompatibleRuntime(params)` 生成 `LobeOpenAI`，并在 `params` 中定义 OpenAI 的 `baseURL`、payload 处理、Responses API 切换、搜索工具接入、模型列表拉取、debug 开关等。比如当模型属于 `responsesAPIModels` 或启用了搜索时，它会把请求转向 Responses API 形态；当模型以 `o1`、`o3`、`o4`、`gpt-5` 等前缀开头时，会调用 `pruneReasoningPayload` 裁剪 reasoning 相关字段。

## 上下游关系

上游调用方主要是服务端聊天、客户端服务或其他需要模型能力的模块。`ModelRuntime.ts` 的注释里明确提到两类典型入口：

- 服务端：`src/app/api/chat/agentRuntime.ts: initAgentRuntimeWithUserPayload`
- 客户端：`src/services/chat.ts: initializeWithClientStore`

根据当前片段推断，实际调用时，上游会根据用户配置、provider、API key、baseURL、模型参数等组装 provider options，然后调用：

```ts
ModelRuntime.initializeWithProvider(provider, params, hooks)
```

返回统一的 `ModelRuntime` 实例后，再执行：

```ts
runtime.chat(payload, options)
runtime.embeddings(payload, options)
runtime.generateObject(payload, options)
```

下游关系则是各模型厂商 SDK/API。例如 OpenAI-compatible provider 会走 `openai` SDK；Bedrock provider 依赖 AWS Bedrock Runtime SDK；Google provider 依赖 `@google/genai`；Ollama provider 依赖 `ollama` 包。`model-bank` 和 `@lobechat/business-model-bank` 提供模型卡、模型能力、价格、上下文窗口等元数据；`@lobechat/types` 提供统一的 payload、usage、trace 类型。

可以把关系理解成：

```text
业务/聊天服务
  -> ModelRuntime
    -> providerRuntimeMap
      -> LobeOpenAI / LobeAnthropicAI / LobeBedrockAI / ...
        -> 厂商 SDK 或 HTTP API
```

## 运行/调用流程

一次典型聊天请求大致如下：

1. 上层拿到 provider，例如 `openai`、`anthropic`、`qwen`。
2. 上层准备 provider 参数，例如 `apiKey`、`baseURL`、`userId`。
3. 调用 `ModelRuntime.initializeWithProvider(provider, params, hooks)`。
4. `initializeWithProvider` 从 `providerRuntimeMap` 中找到对应的 provider 类。
5. 使用 `new providerAI(params)` 创建具体运行时，例如 `new LobeOpenAI(params)`。
6. 用具体运行时创建统一外壳：`new ModelRuntime(runtimeModel, hooks)`。
7. 上层调用 `modelRuntime.chat(payload, options)`。
8. `ModelRuntime.chat` 检查当前 provider 是否支持 `chat`。
9. 执行 `beforeChat` hook，例如预算检查、权限检查、风控检查。
10. 调用具体 provider 的 `chat` 方法。
11. provider 将 LobeHub 内部 payload 转成厂商请求格式。
12. 厂商返回流式或非流式响应。
13. runtime 将响应转换成 LobeHub 统一可消费的 `Response` 或 stream。
14. 流结束时触发 `onChatFinal`，常用于 usage、latency、计费、trace。
15. 如果中途出错，触发 `onChatError`，然后继续向上抛出错误。

`embeddings` 和 `generateObject` 的流程类似，也支持 `beforeEmbeddings`、`onEmbeddingsFinal`、`beforeGenerateObject`、`onGenerateObjectFinal` 等 hooks。这里有一个设计重点：final hook 的失败不会打断主响应完成，代码里会捕获 hook 异常并打印错误。这说明计费、追踪等后置副作用不应该影响用户已经完成的模型响应。

对于 OpenAI-compatible provider，运行流程还多一层工厂逻辑：

```text
provider/index.ts 配置 params
  -> createOpenAICompatibleRuntime(params)
    -> 生成 LobeXXXAI 类
      -> chat / embeddings / generateObject / models 等方法复用通用实现
```

这种模式减少了重复代码。像 `openai` 这类 provider 只需要重点定制 `handlePayload`、`responses.handlePayload`、`models`、`debug` 等差异点。

## 小白阅读顺序

建议先读 `src/core/BaseAI.ts`。这个文件最短，但最能帮助建立心智模型：所有 provider 本质上都要实现 `LobeRuntimeAI` 的一部分能力。读完后要记住一点：`chat`、`embeddings`、`createImage` 这些能力是可选的，不是每个 provider 都支持。

第二步读 `src/core/ModelRuntime.ts`。重点看 `constructor`、`chat`、`applyHooks`、`embeddings`、`generateObject`、`initializeWithProvider`。这里能看懂“统一入口如何包住具体 provider”，以及 hooks 是怎么插入调用链的。

第三步读 `src/runtimeMap.ts`。它像一张 provider 注册表。小白常常会问“为什么传 provider 字符串就能创建模型运行时”，答案就在这里：字符串 key 被映射到了具体类。

第四步读 `src/providers/openai/index.ts`。OpenAI 是最典型、最容易理解的样例。重点看 `params` 里如何配置 `baseURL`、`chatCompletion.handlePayload`、`responses.handlePayload`、`models`。读完它，再看其他 OpenAI-compatible provider 会容易很多。

第五步再读 `src/core/openaiCompatibleFactory/index.ts`。这个文件较长，不建议一开始就啃。应该先知道 provider 需要什么，再回头看工厂如何生成通用 runtime。

第六步根据需求抽读具体 provider。例如要理解本地模型，看 `providers/ollama`；要理解 AWS，看 `providers/bedrock`；要理解 Anthropic，看 `providers/anthropic`；要理解图片/视频生成，看实现了 `createImage`、`createVideo` 的 provider。

## 常见误区

第一个误区是把 `ModelRuntime` 当成具体模型实现。它其实是统一外壳，真正与厂商通信的是 `_runtime` 指向的具体 `LobeXXXAI` 实例。`ModelRuntime` 更关注生命周期、错误处理、能力转发和 hooks。

第二个误区是以为所有 provider 都支持同样能力。`LobeRuntimeAI` 里的方法大多是可选的，例如有些 provider 不支持 `embeddings`，有些不支持 `createImage`。`ModelRuntime.chat` 对不支持聊天的 provider 会抛出 `ProviderBizError`；其他能力很多是通过可选链调用，调用方需要理解返回值可能为空。

第三个误区是忽略 `providerRuntimeMap` 的 key。传入 provider 字符串时，必须和 map 里的 key 对上，例如 `azure` 映射到 `LobeAzureOpenAI`，`azureai` 映射到 `LobeAzureAI`，`router` 映射到 `LobeNewAPIAI`。名字相近但语义可能不同。

第四个误区是认为 `src/index.ts` 和 `runtimeMap.ts` 导出的 provider 完全一致。当前片段里，`runtimeMap.ts` 注册了比 `index.ts` 更多的 provider，例如 `ai21`、`ai302`、`cloudflare`、`cohere`、`fal` 等；而 `index.ts` 主要导出公共 API 和一批 provider 类。也就是说，运行时可注册使用和包公共导出不是同一个概念。

第五个误区是把 OpenAI-compatible provider 理解成“只支持 OpenAI”。这里的 “OpenAI-compatible” 指接口协议相似，可以复用 OpenAI SDK 或请求格式。很多第三方服务只需要配置不同的 `baseURL`、错误类型、payload transform，就可以通过 `createOpenAICompatibleRuntime` 接入。

第六个误区是忽略 hooks 的副作用边界。`beforeChat` 失败会阻止请求继续，适合预算、权限、风控；`onChatFinal` 失败不会影响响应完成，适合计费、trace、usage 落库等后置工作。读调用链时要分清“前置阻断”和“后置记录”。

第七个误区是直接从 provider 文件开始读。provider 数量很多，容易迷路。更稳妥的路径是先读 `BaseAI` 和 `ModelRuntime`，再看 `runtimeMap`，最后带着“这个 provider 如何实现统一接口”的问题去读具体 provider。
