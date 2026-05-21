# 文件：packages/model-runtime/src/providers/openrouter/index.ts

## 它负责什么

`packages/model-runtime/src/providers/openrouter/index.ts` 是 LobeHub 中 OpenRouter 模型运行时的提供者适配文件。它不直接实现完整的聊天、流式解析、错误处理或 OpenAI SDK 调用，而是把 OpenRouter 的差异化规则整理成一个 `params` 配置对象，再交给通用工厂 `createOpenAICompatibleRuntime(params)` 生成运行时类 `LobeOpenRouterAI`。

它主要负责三件事：

1. 定义 OpenRouter 的默认 API 入口：`[URL已移除]
2. 在调用 Chat Completions 前，把 LobeHub 内部的统一 payload 转成 OpenRouter 需要的格式。
3. 拉取 OpenRouter 模型列表，并转换成 LobeHub 标准模型卡格式。

这个文件可以理解成“OpenRouter 方言翻译器”：上层业务都按 LobeHub 的统一模型运行时接口调用，下层真正发给 OpenRouter 时，则由这里补齐 `reasoning`、`:online`、`modalities`、`image_config`、默认 headers、模型价格、模型能力等 OpenRouter 专属细节。

## 关键组成

### `formatPrice`

```ts
const formatPrice = (price?: string) => {
  if (price === undefined || price === '-1') return undefined;
  return Number((Number(price) * 1e6).toPrecision(5));
};
```

OpenRouter 返回的价格字段来自 `pricing.prompt`、`pricing.completion`、`pricing.input_cache_read`、`pricing.input_cache_write` 等，类型是字符串。这里将其转换为 LobeHub 更常用的“每百万 token 价格”数值。

规则是：

- `undefined` 表示无价格信息，返回 `undefined`。
- `'-1'` 表示不可用或未知，返回 `undefined`。
- 其他字符串先转成数字，再乘以 `1e6`，最后用 `toPrecision(5)` 控制有效数字。

例如 OpenRouter 返回按单 token 计价的很小数字，这里会放大成“每 1M token”的展示或计算单位。

### `params`

`params` 是本文件的核心导出之一，类型通过：

```ts
satisfies OpenAICompatibleFactoryOptions
```

约束，说明它必须符合 OpenAI-compatible provider 工厂要求。

它包含以下关键字段。

### `baseURL`

```ts
baseURL: '[URL已移除]'
```

这是 OpenRouter 的默认 OpenAI-compatible API 地址。后续实例化 `new LobeOpenRouterAI({ apiKey })` 时，如果没有传入自定义 `baseURL`，工厂会使用这个地址。

### `chatCompletion.handlePayload`

这是最重要的请求转换逻辑。它接收 LobeHub 内部统一的 `ChatStreamPayload`，返回真正传给 OpenAI SDK `chat.completions.create` 的 payload。

它会先从 payload 中拆出 OpenRouter 或 LobeHub 内部不应原样透传的字段：

```ts
const {
  reasoning_effort,
  thinking,
  reasoning: _reasoning,
  thinkingLevel,
  imageAspectRatio,
  imageResolution,
  model,
  ...rest
} = payload;
```

注意这里的 `reasoning: _reasoning` 是有意丢弃原始 `reasoning` 字段，避免上层 payload 中已有的 `reasoning` 直接穿透到 OpenRouter。OpenRouter 的 `reasoning` 会在本函数中按 LobeHub 的统一参数重新组装。

#### reasoning 转换

OpenRouter 支持 `reasoning` 参数。本文件会根据以下字段生成 `OpenRouterReasoning`：

- `thinking`
- `reasoning_effort`
- `thinkingLevel`

优先级大致是：

1. 如果 `thinking.type === 'disabled'`，生成：

   ```ts
   { enabled: false }
   ```

2. 如果有 `thinking.budget_tokens`，生成：

   ```ts
   { max_tokens: thinking.budget_tokens }
   ```

3. 如果有 `reasoning_effort`，生成：

   ```ts
   { effort: reasoning_effort }
   ```

4. 如果有 `thinkingLevel`，生成：

   ```ts
   { effort: thinkingLevel }
   ```

对应类型来自同目录的 `type.ts`：

```ts
export interface OpenRouterReasoning {
  effort?: 'none' | 'minimal' | 'low' | 'medium' | 'high' | 'xhigh' | 'max';
  enabled?: boolean;
  exclude?: boolean;
  max_tokens?: number;
}
```

也就是说，LobeHub 内部可以用不同抽象表达“思考强度”或“思考 token 预算”，最终这里统一翻译成 OpenRouter 的 `reasoning`。

#### 联网搜索转换

```ts
model: payload.enabledSearch ? `${payload.model}:online` : payload.model
```

OpenRouter 使用模型名后缀 `:online` 表达联网搜索能力。LobeHub 上层只需要设置 `enabledSearch: true`，这里会把：

```ts
openai/gpt-4
```

改成：

```ts
openai/gpt-4:online
```

如果 `enabledSearch` 为 `false` 或未传，则保留原始模型名。

#### 图片生成模型参数转换

本文件还处理 OpenRouter 上通过聊天接口触发图片生成的模型。

判断逻辑是：

```ts
const isImageModel = model.includes('-image') || model.includes('flux');
```

如果模型 ID 包含 `-image` 或 `flux`，则认为它可能是图片模型。

随后设置 `modalities`：

```ts
const modalities =
  (payload as any).modalities ?? (isImageModel ? ['image', 'text'] : undefined);
```

也就是说，如果调用方已经传了 `modalities`，优先使用调用方传入的；否则对图片模型默认加上：

```ts
['image', 'text']
```

图片尺寸字段也会转换。LobeHub 内部的 `imageResolution` 如果是 `'512'`，会被转成 OpenRouter 需要的 `'0.5K'`：

```ts
const imageSizeValue = imageResolution
  ? imageResolution === '512'
    ? '0.5K'
    : imageResolution
  : undefined;
```

其他值如 `'1K'`、`'2K'`、`'4K'` 会原样传递。

`imageAspectRatio` 如果是 `'auto'`，表示使用模型默认值，因此不会传给 OpenRouter：

```ts
const aspectRatioValue =
  imageAspectRatio && imageAspectRatio !== 'auto' ? imageAspectRatio : undefined;
```

最后生成 OpenRouter 的 `image_config`：

```ts
{
  aspect_ratio: aspectRatioValue,
  image_size: imageSizeValue,
}
```

同样，如果调用方已经显式传入 `(payload as any).image_config`，则优先使用调用方传入的配置。

#### 默认流式输出

```ts
stream: payload.stream ?? true
```

如果上层没有明确传 `stream`，默认使用流式输出。测试中也覆盖了这个行为：未传 `stream` 时应传给 SDK `{ stream: true }`；显式传 `false` 时保留 `false`。

### `constructorOptions`

```ts
constructorOptions: {
  defaultHeaders: {
    'HTTP-Referer': '[URL已移除]',
    'X-Title': 'LobeHub',
  },
}
```

OpenRouter 推荐客户端带上来源信息。这里通过 OpenAI SDK 的构造参数设置默认 headers：

- `HTTP-Referer`: `[URL已移除]
- `X-Title`: `LobeHub`

这些 headers 会在 `createOpenAICompatibleRuntime` 创建 OpenAI client 时合并进初始化参数。

### `debug`

```ts
debug: {
  chatCompletion: () => process.env.DEBUG_OPENROUTER_CHAT_COMPLETION === '1',
}
```

用于控制 OpenRouter Chat Completion 调试日志。只有环境变量：

```bash
DEBUG_OPENROUTER_CHAT_COMPLETION=1
```

时才启用。

### `models`

`models` 是一个异步函数，用于拉取并格式化 OpenRouter 模型列表。

第一步，请求 OpenRouter 模型接口：

```ts
const response = await fetch('[URL已移除]');
```

如果响应成功，从返回 JSON 的 `data` 字段中拿模型列表：

```ts
modelList = data['data'];
```

如果请求失败，会打印：

```ts
console.error('Failed to fetch OpenRouter frontend models:', error);
```

并返回空数组。

第二步，把每个 `OpenRouterModelCard` 转成 LobeHub 标准模型卡字段。原始类型定义在同目录 `type.ts`，包括：

- `id`
- `name`
- `description`
- `created`
- `context_length`
- `architecture.input_modalities`
- `pricing`
- `supported_parameters`
- `top_provider.context_length`
- `top_provider.max_completion_tokens`

转换后的关键字段包括：

```ts
{
  contextWindowTokens,
  description,
  displayName,
  functionCall,
  id,
  maxOutput,
  pricing,
  reasoning,
  releasedAt,
  vision,
  settings
}
```

#### `displayName` 处理

OpenRouter 模型名经常带有厂商前缀，例如：

```ts
OpenAI: GPT-4
Anthropic: Claude ...
```

代码默认会去掉冒号前的部分，只保留后缀。

但对 `DeepSeek` 做了特殊保护：

```ts
const isDeepSeekPrefix = prefix.toLowerCase() === 'deepseek';
const suffixHasDeepSeek = suffix.toLowerCase().includes('deepseek');

if (isDeepSeekPrefix && !suffixHasDeepSeek) {
  displayName = model.name;
} else {
  displayName = suffix;
}
```

也就是说，如果原名是 `DeepSeek: R1`，而后缀没有 `deepseek`，就保留完整名称，避免显示名丢失品牌识别。

#### 免费模型标记

```ts
const isFree = inputPrice === 0 && outputPrice === 0 && !displayName.endsWith('(free)');
if (isFree) {
  displayName += ' (free)';
}
```

如果输入和输出价格都为 0，并且显示名还没有 `(free)`，则自动追加 `(free)`。

#### 能力识别

```ts
functionCall: supported_parameters.includes('tools')
reasoning: supported_parameters.includes('reasoning')
vision: inputModalities.includes('image')
```

这些字段会告诉上层 UI 或运行时：

- 是否支持工具调用。
- 是否支持 reasoning。
- 是否支持图片输入。

#### 上下文和输出长度

```ts
contextWindowTokens: top_provider.context_length || model.context_length
```

优先使用 `top_provider.context_length`，否则回退到模型自身的 `context_length`。

`maxOutput` 优先使用：

```ts
top_provider.max_completion_tokens
```

如果它不是数字，则回退到 `model.context_length`。

### `settings.extendParams`

这是模型设置面板的重要配置。代码会根据模型描述、模型 ID 和能力动态追加设置项。

例如：

- 描述中包含 `` `reasoning` `enabled` `` 时，追加 `enableReasoning`。
- `gpt-5.2`、`gpt-5.4`、`gpt-5.5` 且支持 reasoning 时，追加：

  ```ts
  gpt5_2ReasoningEffort
  textVerbosity
  ```

- `gpt-5.1` 追加：

  ```ts
  gpt5_1ReasoningEffort
  textVerbosity
  ```

- 普通 `gpt-5` 追加：

  ```ts
  gpt5ReasoningEffort
  textVerbosity
  ```

- OpenAI reasoning 模型追加：

  ```ts
  reasoningEffort
  textVerbosity
  ```

- Claude reasoning 模型追加：

  ```ts
  enableReasoning
  reasoningBudgetToken
  ```

- Claude 且存在非零写入缓存价格时，追加：

  ```ts
  disableContextCaching
  ```

- Gemini 2.5 reasoning 模型追加：

  ```ts
  reasoningBudgetToken
  ```

- Gemini 3 Pro 追加：

  ```ts
  thinkingLevel2
  ```

- Gemini 3 Flash 追加：

  ```ts
  thinkingLevel
  ```

根据当前片段推断，`settings.extendParams` 主要被上层模型设置 UI 使用，用来决定某个模型应展示哪些高级参数控件。依据是这些字段名明显对应 reasoning、thinking、verbosity、context caching 等用户可配置项。

### `processMultiProviderModelList`

模型转换完成后，函数返回：

```ts
return await processMultiProviderModelList(formattedModels, 'openrouter');
```

`processMultiProviderModelList` 是共享模型列表后处理工具。根据命名和调用方式，它会继续补全多供应商模型的通用字段，例如模型类型、显示信息、搜索/图片输出能力、价格格式等。这里传入 `'openrouter'`，表示这些模型属于 OpenRouter provider。

### `provider`

```ts
provider: ModelProvider.OpenRouter
```

`ModelProvider` 来自 `model-bank`。这里标记当前 provider ID 是 OpenRouter，也就是字符串值：

```ts
'openrouter'
```

这会影响运行时注册、模型提供商识别、价格查找、错误提示和上层 provider 选择。

### `LobeOpenRouterAI`

```ts
export const LobeOpenRouterAI = createOpenAICompatibleRuntime(params);
```

这是最终运行时类。它由通用 OpenAI-compatible 工厂生成，而不是手写 class。

根据读取到的工厂代码，`createOpenAICompatibleRuntime` 会生成一个实现 `LobeRuntimeAI` 的类，负责：

- 校验 `apiKey`。
- 创建 OpenAI SDK client。
- 合并 `baseURL`、`constructorOptions` 和实例化参数。
- 在 `chat()` 时调用 provider 自己的 `chatCompletion.handlePayload`。
- 执行消息转换、采样参数修正、流式响应处理、错误处理等通用逻辑。

因此本文件只定义 OpenRouter 差异点，通用运行时能力由工厂统一提供。

## 上下游关系

### 上游：谁会用它

这个文件对外导出两个对象：

```ts
export const params = ...
export const LobeOpenRouterAI = ...
```

调用方主要有：

- `packages/model-runtime/src/index.ts`

  ```ts
  export { LobeOpenRouterAI } from './providers/openrouter';
  ```

  这是包级出口，外部可以从 `model-runtime` 统一导入 OpenRouter 运行时。

- `packages/model-runtime/src/runtimeMap.ts`

  ```ts
  import { LobeOpenRouterAI } from './providers/openrouter';

  openrouter: LobeOpenRouterAI
  ```

  这里把 provider ID `openrouter` 映射到运行时类。上层只要选择 `ModelProvider.OpenRouter`，就能通过 runtime map 找到 `LobeOpenRouterAI`。

- 服务端模块和客户端运行时测试中也会验证：当 provider 是 `ModelProvider.OpenRouter` 且有 API key 时，初始化出来的 runtime 是 `LobeOpenRouterAI` 实例。

### 下游：它依赖谁

它依赖几个关键模块：

- `model-bank`

  ```ts
  import { ModelProvider } from 'model-bank';
  ```

  用来拿 `ModelProvider.OpenRouter`，保证 provider ID 和全局模型库一致。

- `../../core/openaiCompatibleFactory`

  ```ts
  createOpenAICompatibleRuntime
  OpenAICompatibleFactoryOptions
  ```

  提供通用 OpenAI-compatible runtime 工厂。OpenRouter 的实际 SDK 调用、流式处理、错误包装等不在本文件实现。

- `../../utils/modelParse`

  ```ts
  processMultiProviderModelList
  ```

  对 OpenRouter 模型列表做统一后处理，使它符合 LobeHub 的标准模型卡格式。

- `./type`

  ```ts
  OpenRouterModelCard
  OpenRouterReasoning
  ```

  描述 OpenRouter `/models` 接口返回结构和 OpenRouter reasoning 请求结构。

### 外部服务

它直接访问两个 OpenRouter API 相关入口：

- Chat Completions 默认 base URL：

  ```ts
  [URL已移除]
  ```

- 模型列表接口：

  ```ts
  [URL已移除]
  ```

聊天请求本身不是在这个文件直接 `fetch`，而是由工厂创建的 OpenAI SDK client 发送。模型列表则由本文件里的 `models()` 直接 `fetch`。

## 运行/调用流程

### 聊天调用流程

一次 OpenRouter 聊天调用大致如下：

1. 上层根据 provider 选择 `openrouter`。
2. `runtimeMap` 找到 `LobeOpenRouterAI`。
3. 业务层实例化：

   ```ts
   new LobeOpenRouterAI({ apiKey })
   ```

4. `createOpenAICompatibleRuntime` 生成的构造函数合并参数：

   - `apiKey`
   - `baseURL`
   - `constructorOptions.defaultHeaders`
   - 其他 OpenAI SDK 选项

5. 工厂创建 OpenAI SDK client：

   ```ts
   new OpenAI(initOptions)
   ```

6. 上层调用：

   ```ts
   runtime.chat(payload)
   ```

7. 工厂的 `chat()` 方法先做通用处理，例如是否走 Responses API、上下文预检查等。
8. 进入 OpenRouter 自己的：

   ```ts
   params.chatCompletion.handlePayload(payload, options)
   ```

9. `handlePayload` 做 OpenRouter 专属转换：

   - `thinking` / `reasoning_effort` / `thinkingLevel` 转 `reasoning`
   - `enabledSearch` 转模型后缀 `:online`
   - 图片模型补 `modalities`
   - `imageResolution` / `imageAspectRatio` 转 `image_config`
   - 默认 `stream: true`
   - 去掉不应直接发送的内部字段

10. 工厂继续做通用转换：

   - 转换 OpenAI messages。
   - 修正采样参数。
   - 读取模型价格。
   - 调用 OpenAI SDK 的 `chat.completions.create`。
   - 把 OpenAI-compatible stream 转成 LobeHub 内部流协议。

### 模型列表流程

模型列表获取流程如下：

1. 上层调用 OpenRouter provider 的 `models()`。
2. 本文件请求：

   ```ts
   [URL已移除]
   ```

3. 从返回 JSON 中读取 `data`。
4. 遍历 `OpenRouterModelCard[]`。
5. 对每个模型计算：

   - `displayName`
   - `contextWindowTokens`
   - `maxOutput`
   - `pricing`
   - `functionCall`
   - `reasoning`
   - `vision`
   - `releasedAt`
   - `settings.extendParams`

6. 调用：

   ```ts
   processMultiProviderModelList(formattedModels, 'openrouter')
   ```

7. 返回 LobeHub 标准模型列表。

## 小白阅读顺序

1. 先看文件底部：

   ```ts
   export const LobeOpenRouterAI = createOpenAICompatibleRuntime(params);
   ```

   先明确：这个文件不是完整运行时实现，而是把 `params` 交给工厂生成运行时。

2. 再看 `params.provider` 和 `params.baseURL`：

   ```ts
   provider: ModelProvider.OpenRouter
   baseURL: '[URL已移除]'
   ```

   这两行决定“它是谁”和“默认请求发到哪里”。

3. 接着看 `chatCompletion.handlePayload`。

   这是最值得细读的部分，因为它解释了 LobeHub 内部参数如何变成 OpenRouter API 参数。重点看四个转换：

   - `thinking` / `reasoning_effort` 到 `reasoning`
   - `enabledSearch` 到 `model:xxx:online`
   - 图片模型到 `modalities`
   - `imageResolution` / `imageAspectRatio` 到 `image_config`

4. 然后看 `constructorOptions` 和 `debug`。

   它们比较简单，分别负责默认 headers 和调试开关。

5. 再看 `models()`。

   这部分负责模型市场/模型列表展示。重点理解：

   - 它从 OpenRouter 拉 `/models`。
   - 它把 OpenRouter 原始字段转换为 LobeHub 标准字段。
   - 它根据模型能力动态生成 `settings.extendParams`。

6. 最后看同目录 `type.ts`。

   `type.ts` 能帮助你理解 `OpenRouterModelCard` 和 `OpenRouterReasoning` 的字段来源。读完类型后，再回到 `models()`，很多字段如 `top_provider`、`architecture`、`pricing`、`supported_parameters` 就更清楚了。

7. 如果继续追下游，再看：

   - `packages/model-runtime/src/core/openaiCompatibleFactory/index.ts`
   - `packages/model-runtime/src/runtimeMap.ts`
   - `packages/model-runtime/src/index.ts`

   前者解释运行时类如何工作，后两者解释这个 provider 如何被注册和导出。

## 常见误区

1. 误以为这里直接发起聊天请求。

   这个文件不会直接调用 `client.chat.completions.create`。它只提供 `handlePayload` 和配置。真正的 SDK 调用在 `createOpenAICompatibleRuntime` 生成的通用运行时里完成。

2. 误以为 `reasoning` 会原样透传。

   不会。代码中明确把 payload 里的 `reasoning` 解构成 `_reasoning`，但没有继续使用。真正传给 OpenRouter 的 `reasoning` 是根据 `thinking`、`reasoning_effort`、`thinkingLevel` 重新计算出来的。

3. 误以为 `enabledSearch` 是 OpenRouter API 原生字段。

   对 OpenRouter 来说，联网搜索是通过模型 ID 后缀 `:online` 表达的。`enabledSearch` 是 LobeHub 内部抽象，发送前会被转换成：

   ```ts
   model: `${payload.model}:online`
   ```

4. 误以为所有模型都会带 `modalities`。

   只有当调用方显式传了 `modalities`，或模型 ID 看起来像图片模型时，才会带 `modalities`。图片模型的判断目前是：

   ```ts
   model.includes('-image') || model.includes('flux')
   ```

   根据当前片段推断，这是一种基于模型 ID 的轻量判断，不是从 OpenRouter 模型元数据实时判断。

5. 误以为 `imageAspectRatio: 'auto'` 会传给 OpenRouter。

   不会。`'auto'` 表示使用模型默认值，所以会被省略。只有非 `'auto'` 的比例才会进入 `image_config.aspect_ratio`。

6. 误以为 `imageResolution: '512'` 会原样发送。

   不会。OpenRouter 的 `image_size` 对 512px 使用 `'0.5K'`，所以这里会把 `'512'` 转成 `'0.5K'`。其他如 `'1K'`、`'2K'`、`'4K'` 才原样传递。

7. 误以为 `models()` 返回的是 OpenRouter 原始模型数据。

   不是。`models()` 会先把 OpenRouter 原始数据映射成 LobeHub 模型卡字段，再经过 `processMultiProviderModelList` 做统一后处理。上层拿到的是标准化后的模型列表。

8. 误以为 `displayName` 总是简单去掉冒号前缀。

   大多数情况下是这样，但 `DeepSeek` 有特殊逻辑。如果前缀是 `DeepSeek`，而后缀没有包含 `deepseek`，代码会保留完整名称，避免品牌名丢失。

9. 误以为免费模型必须由 OpenRouter 名称自带 `(free)`。

   如果价格解析后输入和输出都为 0，且显示名还没有 `(free)`，本文件会自动追加 `(free)`。

10. 误以为 `settings.extendParams` 是固定配置。

   它是按模型动态生成的。不同模型 ID、不同 `supported_parameters`、不同描述文本、不同缓存价格，都会影响上层设置面板展示哪些参数。比如 GPT-5 系列、Claude、Gemini 2.5、Gemini 3 Pro、Gemini 3 Flash 都有不同分支。
