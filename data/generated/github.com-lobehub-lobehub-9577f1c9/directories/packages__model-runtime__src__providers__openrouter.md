# 目录：packages/model-runtime/src/providers/openrouter

## 它负责什么

`packages/model-runtime/src/providers/openrouter` 是 `model-runtime` 包里对 OpenRouter 供应商的适配层。它把 LobeHub 内部统一的模型调用参数，转换成 OpenRouter 兼容 OpenAI Chat Completions API 的请求格式，并把 OpenRouter 的模型列表接口返回值转换成项目内部统一的模型元数据格式。

这个目录的职责可以拆成两类：

1. **运行时调用适配**：导出 `LobeOpenRouterAI`，供上层通过统一 runtime 调用 OpenRouter。
2. **模型清单转换**：从 `[URL已移除] 拉取模型列表，整理 `displayName`、上下文长度、价格、视觉能力、函数调用能力、推理能力、扩展设置项等字段。

它不是一个完整的 HTTP 客户端实现，而是基于项目通用的 `createOpenAICompatibleRuntime` 工厂，只提供 OpenRouter 特有的配置和参数转换规则。

## 关键组成

目录下直接包含：

- `index.ts`
- `type.ts`
- `index.test.ts`
- `fixtures/frontendModels.json`
- `fixtures/models.json`

`index.ts` 是核心入口，主要导出两个对象：

- `params`
- `LobeOpenRouterAI`

`params` 使用 `satisfies OpenAICompatibleFactoryOptions` 约束结构，说明 OpenRouter 被当作一个 OpenAI-compatible provider 接入。它包含以下关键配置：

- `baseURL: '[URL已移除]'`
- `provider: ModelProvider.OpenRouter`
- `constructorOptions.defaultHeaders`
- `chatCompletion.handlePayload`
- `debug.chatCompletion`
- `models`

`constructorOptions.defaultHeaders` 会给 OpenRouter 请求加上：

- `HTTP-Referer: [URL已移除]
- `X-Title: LobeHub`

这些 header 是 OpenRouter 常见的站点标识字段，用于告诉 OpenRouter 请求来源和应用名称。

`chatCompletion.handlePayload` 是请求参数转换的核心。它会从内部 payload 中取出并处理这些字段：

- `reasoning_effort`
- `thinking`
- `reasoning`
- `thinkingLevel`
- `imageAspectRatio`
- `imageResolution`
- `model`

然后生成 OpenRouter 需要的请求参数。

推理参数转换规则大致是：

- `thinking.type === 'disabled'` 时，生成 `reasoning: { enabled: false }`
- `thinking.budget_tokens` 存在时，生成 `reasoning: { max_tokens: budget_tokens }`
- `reasoning_effort` 存在时，生成 `reasoning: { effort: reasoning_effort }`
- `thinkingLevel` 存在时，生成 `reasoning: { effort: thinkingLevel }`

搜索开关的处理也在这里完成：

- 如果 `payload.enabledSearch` 为真，模型名会从 `payload.model` 变成 `${payload.model}:online`
- 例如 `openai/gpt-4` 会变成 `openai/gpt-4:online`

图片模型也有特殊逻辑。代码通过模型名判断：

- 包含 `-image`
- 或包含 `flux`

就认为它是图片生成模型，并默认补上：

```ts
modalities: ['image', 'text']
```

如果传入 `imageAspectRatio` 或 `imageResolution`，还会生成 `image_config`。其中 `imageResolution === '512'` 会被转换成 OpenRouter 期望的 `'0.5K'`，其他如 `'1K'`、`'2K'`、`'4K'` 会原样传递。`imageAspectRatio === 'auto'` 表示使用模型默认值，因此不会传给 OpenRouter。

`models` 函数负责获取并标准化 OpenRouter 模型列表。它会请求：

```ts
[URL已移除]
```

返回后将每个 `OpenRouterModelCard` 转成项目内部模型结构，并交给：

```ts
processMultiProviderModelList(formattedModels, 'openrouter')
```

继续做多 provider 模型列表的统一处理。

`type.ts` 定义 OpenRouter 返回结构相关类型：

- `OpenRouterModelCard`
- `OpenRouterReasoning`
- 内部辅助接口 `ModelPricing`
- 内部辅助接口 `TopProvider`
- 内部辅助接口 `Architecture`

`OpenRouterModelCard` 基本对应 OpenRouter `/models` 接口的模型卡片结构，包含 `architecture`、`pricing`、`supported_parameters`、`top_provider` 等字段。

`OpenRouterReasoning` 描述发送给 OpenRouter 的 `reasoning` 参数形态，支持：

- `effort`
- `enabled`
- `exclude`
- `max_tokens`

`index.test.ts` 是该目录行为说明最完整的文件，覆盖了参数导出、debug 开关、构造参数、payload 转换、模型列表转换、价格转换、图片模型处理、搜索开关和 reasoning 映射等场景。

`fixtures/frontendModels.json` 和 `fixtures/models.json` 没有在当前片段中直接阅读；根据文件名和目录位置推断，它们是 OpenRouter 模型列表相关的测试或开发样例数据。

## 上下游关系

上游主要是 `model-runtime` 的统一运行时注册和业务调用方。

从搜索结果可见：

```ts
packages/model-runtime/src/index.ts
```

会导出：

```ts
export { LobeOpenRouterAI } from './providers/openrouter';
```

也就是说外部包可以从 `model-runtime` 的包入口拿到 OpenRouter runtime。

另一个关键上游是：

```ts
packages/model-runtime/src/runtimeMap.ts
```

其中存在：

```ts
import { LobeOpenRouterAI } from './providers/openrouter';
```

并将：

```ts
openrouter: LobeOpenRouterAI
```

注册到 runtime map 中。根据当前片段推断，上层业务根据 provider id 选择 runtime 时，会通过这个 map 找到 OpenRouter 的运行时类。

下游主要有三个方向：

1. `../../core/openaiCompatibleFactory`

   `index.ts` 从这里导入：

   ```ts
   createOpenAICompatibleRuntime
   ```

   OpenRouter 自己不直接实现完整请求逻辑，而是把 `params` 交给这个工厂生成 `LobeOpenRouterAI`。

2. `../../utils/modelParse`

   `models` 函数最后调用：

   ```ts
   processMultiProviderModelList(formattedModels, 'openrouter')
   ```

   说明 OpenRouter 的模型清单先被整理成中间结构，再由通用工具补齐或转换成最终格式。

3. `model-bank`

   `index.ts` 使用：

   ```ts
   ModelProvider.OpenRouter
   ```

   测试中还从 `model-bank` 导入 `openrouter` 模型列表，用于验证 reasoning token 限制相关行为。根据当前片段推断，`model-bank` 是项目内或依赖包中的静态模型数据来源之一。

此外，OpenRouter 还和通用 OpenAI 流处理逻辑有间接关系。搜索结果显示：

- `core/streams/openai/openai.ts`
- `core/streams/openai/openai.test.ts`

中包含 OpenRouter 特有响应字段，例如 Gemini 模型返回的 `thoughtSignature`、OpenRouter response 中的 `reasoning` key。这说明 OpenRouter 虽然走 OpenAI-compatible 通道，但响应流里仍有 provider-specific 细节需要通用流解析层兼容。

## 运行/调用流程

一次普通聊天调用大致是：

1. 上层根据 provider 选择 `openrouter`。
2. `runtimeMap.ts` 找到 `LobeOpenRouterAI`。
3. 调用方创建 runtime 实例，例如测试中：

   ```ts
   new LobeOpenRouterAI({ apiKey: 'test' })
   ```

4. `LobeOpenRouterAI` 由 `createOpenAICompatibleRuntime(params)` 生成，默认 base URL 是：

   ```ts
   [URL已移除]
   ```

5. 调用 `instance.chat(...)` 时，通用 OpenAI-compatible runtime 会在发请求前执行 `params.chatCompletion.handlePayload`。
6. `handlePayload` 对内部参数做 OpenRouter 适配：
   - 默认 `stream` 为 `true`
   - `enabledSearch` 转成模型名后缀 `:online`
   - `thinking` / `reasoning_effort` / `thinkingLevel` 转成 `reasoning`
   - 图片模型补充 `modalities`
   - 图片尺寸和比例转成 `image_config`
7. 转换后的 payload 被传给 OpenAI SDK 风格的：

   ```ts
   client.chat.completions.create(...)
   ```

模型列表加载流程则是：

1. 调用 `params.models()`。
2. 请求 OpenRouter 模型接口。
3. 如果请求失败或抛错，返回空数组；抛错时会打印：

   ```ts
   Failed to fetch OpenRouter frontend models:
   ```

4. 遍历 OpenRouter 原始模型列表。
5. 处理展示名称：
   - 普通 `Provider: Model Name` 会去掉冒号前缀
   - `DeepSeek: Chat` 这种特殊情况会保留 DeepSeek 前缀，避免展示名过短或失真
   - `DeepSeek: DeepSeek R1` 会去掉重复前缀，显示为 `DeepSeek R1`
6. 处理价格：
   - OpenRouter 原始价格乘以 `1e6`
   - `'-1'` 和 `undefined` 视为无价格
   - `0` 是有效价格
   - 输入、输出、cache read、cache write 都会分别转换
7. 判断能力：
   - `supported_parameters` 包含 `tools`，则 `functionCall: true`
   - `supported_parameters` 包含 `reasoning`，则 `reasoning: true`
   - `architecture.input_modalities` 包含 `image`，则 `vision: true`
8. 根据模型 id 和能力补充 `settings.extendParams`：
   - GPT-5.2 / GPT-5.4 / GPT-5.5 系列：`gpt5_2ReasoningEffort`、`textVerbosity`
   - GPT-5.1：`gpt5_1ReasoningEffort`、`textVerbosity`
   - GPT-5：`gpt5ReasoningEffort`、`textVerbosity`
   - OpenAI reasoning 模型：`reasoningEffort`、`textVerbosity`
   - Claude reasoning 模型：`enableReasoning`、`reasoningBudgetToken`
   - Claude 且存在 cache write 价格：`disableContextCaching`
   - Gemini 2.5 reasoning 模型：`reasoningBudgetToken`
   - Gemini 3 Pro：`thinkingLevel2`
   - Gemini 3 Flash：`thinkingLevel`

## 小白阅读顺序

1. 先看 `index.ts` 顶部 import。

   重点理解这个目录依赖三类东西：

   - `model-bank` 里的 provider 枚举
   - `openaiCompatibleFactory` 里的通用 runtime 工厂
   - `modelParse` 里的模型列表后处理工具

2. 再看 `params` 的第一层结构。

   先不要陷入细节，只记住它给通用工厂提供：

   - baseURL
   - provider
   - constructorOptions
   - chatCompletion payload 处理
   - debug 开关
   - models 拉取函数

3. 然后读 `chatCompletion.handlePayload`。

   这里是调用 OpenRouter 时最重要的适配逻辑。建议按四块理解：

   - reasoning 参数
   - web search 的 `:online`
   - image model 的 `modalities`
   - image config 的尺寸和比例转换

4. 接着读 `models` 函数。

   它比较长，但可以按字段转换来看：

   - 名称：`displayName`
   - 价格：`pricing`
   - 能力：`functionCall`、`reasoning`、`vision`
   - 长度：`contextWindowTokens`、`maxOutput`
   - 设置项：`settings.extendParams`

5. 再看 `type.ts`。

   看完 `models` 后再看类型会更容易，因为你已经知道哪些字段被实际使用了。

6. 最后看 `index.test.ts`。

   测试文件很长，但它是行为索引。新手可以优先搜索这些 describe：

   - `handlePayload`
   - `image model handling`
   - `models mapping`
   - `models`
   - `formatPrice utility`

## 常见误区

1. 不要把 `LobeOpenRouterAI` 理解成手写的完整 OpenRouter SDK。

   它是通过 `createOpenAICompatibleRuntime(params)` 生成的。OpenRouter 的特殊性主要集中在 `params`，通用请求、流式处理、错误处理等大部分逻辑在 `core/openaiCompatibleFactory` 和相关 core 模块中。

2. `reasoning` 不是简单透传。

   内部 payload 里可能出现 `thinking`、`thinkingLevel`、`reasoning_effort` 等多种字段。`handlePayload` 会统一转换成 OpenRouter 的 `reasoning` 对象，而且优先级是由代码顺序决定的：`thinking.type === 'disabled'`、`thinking.budget_tokens`、`reasoning_effort`、`thinkingLevel`。

3. `enabledSearch` 不是请求参数。

   它不会作为 `enabledSearch` 发给 OpenRouter，而是通过修改模型名实现：

   ```ts
   model: `${payload.model}:online`
   ```

4. `stream` 默认是 `true`。

   如果调用方没有显式传 `stream`，最终请求会带上 `stream: true`。只有显式传 `stream: false` 时才会保留 false。

5. 图片生成模型的判断比较朴素。

   当前代码只根据模型 id 是否包含 `-image` 或 `flux` 来判断是否自动加 `modalities`。因此某些 OpenRouter 新图片模型如果命名不符合这个规则，根据当前片段推断，可能不会自动走图片模型参数补全。

6. `imageAspectRatio: 'auto'` 不会被传给 OpenRouter。

   这里的语义是“使用模型默认值”，所以代码会省略 `aspect_ratio`，而不是传字符串 `'auto'`。

7. 价格中的 `0` 和 `-1` 含义不同。

   `0` 是有效价格，表示免费；`'-1'` 会被当作未知价格并转换成 `undefined`。测试里也覆盖了 `null`，当前实现会通过 `Number(null)` 转成 `0`，因此 `null` 会表现为免费价格。

8. `displayName` 的冒号处理有 DeepSeek 特例。

   普通模型名 `Provider: Model` 会去掉 provider 前缀，但 `DeepSeek: Chat` 会保留完整名称，因为 suffix 里不含 `deepseek`；`DeepSeek: DeepSeek R1` 则会去掉前缀，避免重复。

9. `fixtures` 不一定是运行时依赖。

   当前阅读片段没有看到 `index.ts` 直接导入 fixtures。根据当前片段推断，它们更可能用于测试、生成或人工对照，不属于正常调用 OpenRouter 时的必经路径。
