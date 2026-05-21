# 目录：packages/model-runtime/src/providers

## 它负责什么

`packages/model-runtime/src/providers` 是 `@lobechat/model-runtime` 包里的“模型供应商适配层”。它把 OpenAI、Anthropic、Google、Bedrock、Azure、Ollama、Qwen、Zhipu、Minimax、OpenRouter 等大量不同模型服务，统一包装成仓库内部可调用的运行时对象。

从邻近入口可以看出，这一层最终要满足 `packages/model-runtime/src/core/BaseAI.ts` 里定义的 `LobeRuntimeAI` 接口。该接口把供应商能力抽象成一组可选方法：

- `chat`：对话/流式聊天
- `embeddings`：向量生成
- `generateObject`：结构化对象生成
- `createImage`：图像生成
- `createVideo`：视频生成
- `handleCreateVideoWebhook` / `handlePollVideoStatus`：视频异步任务回调和轮询
- `models`：模型列表
- `pullModel`：本地模型拉取，主要面向 Ollama 等本地运行时
- `textToSpeech`：文本转语音

也就是说，`providers` 目录不直接负责 UI、业务计费、用户配置读取，也不负责统一生命周期钩子；它的核心职责是：把“某个厂商的 API 形状”转换成“LobeHub 内部统一的 runtime 能力”。

## 关键组成

这个目录下面几乎每个一级子目录对应一个供应商或一种供应商兼容协议，例如：

- `openai`
- `anthropic`
- `google`
- `azureOpenai`
- `azureai`
- `bedrock`
- `ollama`
- `ollamacloud`
- `openrouter`
- `qwen`
- `zhipu`
- `minimax`
- `hunyuan`
- `wenxin`
- `volcengine`
- `xai`
- `deepseek`
- `moonshot`
- `mistral`
- `groq`
- `togetherai`
- `huggingface`
- `githubCopilot`
- `comfyui`
- `replicate`
- `fal`
- `bfl`

每个供应商目录通常包含：

- `index.ts`：该供应商 runtime 的主实现文件，导出类似 `LobeOpenAI`、`LobeAnthropicAI`、`LobeGoogleAI` 这样的类。
- `index.test.ts`：供应商适配测试。
- `createImage.ts` / `createVideo.ts`：当供应商有图像或视频生成能力时，会拆出独立实现。
- `type.ts` / `types.ts`：供应商特有类型。
- 其他辅助文件：例如 `anthropic/claudeThinkingHistory.ts`、`google/thinkingResolver.ts`、`google/generateObject.ts`。

需要注意的是，`providers` 目录本身没有看到独立的根级 `index.ts`。它的统一注册和导出主要发生在两个邻近文件里：

- `packages/model-runtime/src/runtimeMap.ts`
- `packages/model-runtime/src/index.ts`

`runtimeMap.ts` 是运行时选择的核心映射表。它把字符串 provider id 映射到具体类，例如：

- `openai` -> `LobeOpenAI`
- `anthropic` -> `LobeAnthropicAI`
- `google` -> `LobeGoogleAI`
- `bedrock` -> `LobeBedrockAI`
- `ollama` -> `LobeOllamaAI`
- `openrouter` -> `LobeOpenRouterAI`
- `router` -> `LobeNewAPIAI`

`src/index.ts` 则是包的对外导出入口。它导出核心 runtime、类型、工具函数，以及一部分供应商类。根据当前片段可见，并不是 `runtimeMap.ts` 里的所有 provider 都一定从 `src/index.ts` 直接导出；有些 provider 可能只通过运行时映射被内部使用。

## 上下游关系

上游是 `core` 层，尤其是：

- `packages/model-runtime/src/core/BaseAI.ts`
- `packages/model-runtime/src/core/ModelRuntime.ts`
- `packages/model-runtime/src/runtimeMap.ts`

`BaseAI.ts` 定义供应商需要实现的统一接口。`providers/*/index.ts` 中的类只要实现其中一部分能力即可，因为这些方法在接口中大多是可选的。比如一个纯文本聊天供应商可能只实现 `chat` 和 `models`；图像平台可能主要实现 `createImage`；本地模型供应商可能额外实现 `pullModel`。

`ModelRuntime.ts` 是调用方实际拿到的统一门面。它内部持有一个 `_runtime: LobeRuntimeAI`，并提供统一方法：

- `chat`
- `generateObject`
- `createImage`
- `createVideo`
- `models`
- `embeddings`
- `textToSpeech`
- `pullModel`

当调用 `ModelRuntime.initializeWithProvider(provider, params, hooks)` 时，会从 `providerRuntimeMap` 中取出对应 provider 类。如果找不到，则回退到 `LobeOpenAI`。然后它执行：

```ts
const runtimeModel: LobeRuntimeAI = new providerAI(params);
return new ModelRuntime(runtimeModel, hooks);
```

这说明 `providers` 是被 `ModelRuntime` 实例化和包裹的底层实现。业务侧不应该到处直接 new 某个供应商类，而是优先通过 `ModelRuntime.initializeWithProvider` 这类统一入口进入。

下游是各个实际模型服务的 HTTP API、SDK 或兼容协议。根据目录结构和命名可以分几类：

- OpenAI 兼容类供应商：许多平台可能复用 OpenAI SDK 或 OpenAI-compatible 工厂。
- 原生协议供应商：如 `anthropic`、`google`、`bedrock`、`azureai`，通常要处理各自特殊参数、消息格式和流式响应。
- 本地/自托管供应商：如 `ollama`、`lmstudio`、`vllm`、`xinference`。
- 多模态任务供应商：如 `bfl`、`fal`、`replicate`、`comfyui`、`minimax`、`hunyuan`、`wenxin`、`xai`、`zhipu` 等，可能包含图像或视频生成文件。
- Coding Plan 类供应商：如 `bailianCodingPlan`、`glmCodingPlan`、`kimiCodingPlan`、`minimaxCodingPlan`、`volcengineCodingPlan`、`opencodeCodingPlan`。根据当前片段推断，这些是面向特定编码模型套餐或编码代理能力的适配实现，依据是它们被单独注册到 `runtimeMap.ts` 并以 provider id 暴露。

## 运行/调用流程

典型调用链可以按下面理解：

1. 业务层拿到用户选择的 `provider` 字符串和模型调用参数。
2. 调用 `ModelRuntime.initializeWithProvider(provider, params, hooks)`。
3. `ModelRuntime` 查询 `providerRuntimeMap`。
4. 找到对应供应商类，例如 `LobeAnthropicAI` 或 `LobeOpenRouterAI`。
5. 使用 `params` 实例化该供应商 runtime。
6. 用统一的 `ModelRuntime` 包一层，返回给业务代码。
7. 业务代码调用 `runtime.chat(payload, options)`、`runtime.createImage(payload, options)` 等统一方法。
8. `ModelRuntime` 先处理通用逻辑，例如能力检查、hooks、错误回调、最终用量回调。
9. `ModelRuntime` 再把请求转给具体 provider 的同名方法。
10. provider 将内部统一 payload 转换为厂商 API 请求，调用外部服务，并把响应转换回统一格式。

以 `chat` 为例，`ModelRuntime.chat` 会先检查底层 provider 是否实现了 `chat`。如果没有实现，会抛出 `ProviderBizError` 类型错误，提示该 provider 不支持聊天能力。然后它会执行 `beforeChat` hook，再调用 `_runtime.chat(payload, finalOptions)`。如果流式响应结束，还会通过包装后的 `onFinal` 调用 `onChatFinal` hook，用于追踪、计费或记录用量。

`embeddings` 和 `generateObject` 也有类似的 hook 包装逻辑。`createImage`、`createVideo`、`models` 等方法相对更直接，主要是转发到底层 provider。

这个设计的重点是：供应商只处理“怎么调这个厂商”，`ModelRuntime` 处理“调用前后统一做什么”。

## 小白阅读顺序

建议先不要从几十个 provider 目录里随便点进去看，否则容易被厂商细节淹没。可以按这个顺序读：

1. 先读 `packages/model-runtime/src/core/BaseAI.ts`  
   明确所有 provider 最终要实现什么能力。重点看 `LobeRuntimeAI`，理解 `chat`、`createImage`、`createVideo`、`embeddings` 等方法都是可选能力。

2. 再读 `packages/model-runtime/src/core/ModelRuntime.ts`  
   这是统一调用门面。重点看 `initializeWithProvider`、`chat`、`embeddings`、`generateObject`。读完这里，就知道 provider 是如何被选择、实例化、包裹和调用的。

3. 再读 `packages/model-runtime/src/runtimeMap.ts`  
   这里是 provider id 到 provider 类的注册表。新增供应商通常绕不开这个文件。特别注意 id 的大小写和命名，比如 `githubcopilot`、`glmcodingplan`、`vercelaigateway` 都是运行时识别用的 key。

4. 再读 `packages/model-runtime/src/index.ts`  
   这里是包的公共导出入口。它告诉你哪些 provider 类和 core 工具会暴露给包外使用。

5. 然后选一个最基础的 provider 看，例如 `providers/openai/index.ts`  
   OpenAI 通常是其他兼容供应商的参照物。根据当前目录结构推断，许多 OpenAI-compatible provider 会复用或模仿它的实现。

6. 再选一个非 OpenAI 协议 provider，例如 `providers/anthropic/index.ts` 或 `providers/google/index.ts`  
   重点比较它们如何处理消息格式、thinking、结构化输出、流式响应等差异。

7. 最后看多模态 provider，例如 `providers/google/createImage.ts`、`providers/minimax/createVideo.ts`、`providers/bfl/createImage.ts`  
   这些能帮助理解图片、视频任务为什么会拆成独立文件，以及异步任务、webhook、轮询状态如何接入统一 runtime。

## 常见误区

1. 误以为每个 provider 都必须实现所有方法。  
   实际上 `LobeRuntimeAI` 中大多数能力都是可选的。`ModelRuntime` 会在调用时根据方法是否存在来转发；例如 `chat` 没实现时会明确抛错，其他如 `createImage`、`models` 可能返回 `undefined`。

2. 误以为 `providers` 目录有统一根入口。  
   当前片段显示，统一注册不在 `providers/index.ts`，而在 `packages/model-runtime/src/runtimeMap.ts`；公共导出则在 `packages/model-runtime/src/index.ts`。

3. 误以为 provider id 一定等于目录名或产品名。  
   大多数情况下接近，但运行时真正使用的是 `providerRuntimeMap` 的 key。例如 `azure` 映射到 `LobeAzureOpenAI`，`router` 映射到 `LobeNewAPIAI`，这些并不完全等同于目录名直觉。

4. 误以为 `ModelRuntime` 只是简单转发。  
   它除了转发，还做生命周期 hook、错误 hook、用量 hook、耗时日志、能力检查等统一处理。provider 实现不应该重复承担这些横切逻辑。

5. 误以为新增 provider 只要加一个目录。  
   根据当前结构，新增 provider 至少要考虑：新增 `providers/<name>/index.ts`，实现 `LobeRuntimeAI` 兼容方法，在 `runtimeMap.ts` 注册 provider id，必要时在 `src/index.ts` 导出，并补充对应测试。

6. 误以为 OpenAI-compatible 和 OpenAI 是一回事。  
   很多供应商可能使用 OpenAI 风格 API，但仍有自己的 `baseURL`、鉴权、模型列表、参数兼容性、流式事件差异。适配层存在的价值就是把这些差异收敛起来。

7. 误以为测试只测网络真实调用。  
   目录中大量 `index.test.ts`、`createImage.test.ts`、`createVideo.test.ts` 表明 provider 行为需要被单元测试覆盖。根据当前片段推断，这些测试更可能关注请求构造、参数转换、错误处理、流式解析等适配逻辑，而不是依赖真实外部服务。
