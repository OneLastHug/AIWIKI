# 目录：packages/model-runtime/src/core/RouterRuntime

## 它负责什么

`RouterRuntime` 是 `packages/model-runtime` 里的“多后端路由型运行时”工厂。它的核心职责不是直接调用某个模型供应商，而是把一组可能的供应商 runtime、模型匹配规则、URL 匹配规则和 fallback 配置包装成一个统一的 `LobeRuntimeAI` 实现。

简单说：普通 provider runtime 通常是一对一的，比如 `LobeOpenAI` 只面向 OpenAI 风格接口；而 `RouterRuntime` 面向“一个逻辑 provider 背后可能有多个协议、多个通道、多个兼容后端”的场景。例如 `Moonshot`、`DeepSeek` 既可能走 OpenAI-compatible 格式，也可能走 Anthropic-compatible 格式；`lobehub` 云端入口也可能根据动态配置选择不同 channel。`RouterRuntime` 负责在请求发生时选择正确 runtime，并在失败时按配置尝试下一个通道。

它最终暴露的仍然是 `LobeRuntimeAI` 形状的方法，例如 `chat`、`models`、`embeddings`、`textToSpeech`、`createImage`、`createVideo`、`generateObject`。调用方不需要知道底层当前走的是 `openai`、`anthropic`、`vertexai` 还是别的 runtime。

## 关键组成

`index.ts` 是目录入口，定义并导出基础类型：

- `RuntimeItem`：描述一个 runtime 项，包含 `id`、可选 `models`、以及 `runtime: LobeRuntimeAI`。
- 重新导出 `CreateRouterRuntimeOptions`、`RouteAttemptResult`、`UniformRuntime`。
- 导出核心函数 `createRouterRuntime`。

`apiTypes.ts` 定义 RouterRuntime 可识别的底层 API 类型：

```ts
export type ApiType =
  | 'anthropic'
  | 'azure'
  | 'azureopenai'
  | 'bedrock'
  | 'cloudflare'
  | 'deepseek'
  | 'fal'
  | 'google'
  | 'minimax'
  | 'moonshot'
  | 'openai'
  | 'qwen'
  | 'vertexai'
  | 'volcengine'
  | 'xai'
  | 'xiaomimimo'
  | 'zhipu';
```

同时定义 `RuntimeClass = new (options?: any) => LobeRuntimeAI`，也就是所有可被 RouterRuntime 实例化的 provider runtime 构造器形状。

`baseRuntimeMap.ts` 是 `ApiType` 到具体 provider runtime class 的映射表，例如：

- `openai -> LobeOpenAI`
- `anthropic -> LobeAnthropicAI`
- `deepseek -> LobeDeepSeekAI`
- `vertexai -> LobeVertexAI`
- `zhipu -> LobeZhipuAI`

这个文件的作用是提供默认 runtime。某个 router 可以自己传 `runtime` 覆盖默认值；如果没有传，`createRuntimeFromOption` 会从 `baseRuntimeMap` 里按 `apiType` 找对应实现，找不到时再退到 `LobeOpenAI`。

`createRuntime.ts` 是核心实现。它导出 `createRouterRuntime(options)`，返回一个实现 `LobeRuntimeAI` 的 class：`UniformRuntime`。这个 class 不在构造函数里立即创建所有底层 runtime，而是保存配置，等真正调用 `chat`、`models`、`embeddings` 等方法时再解析 router 并创建目标 runtime。这种延迟创建让动态路由、按模型路由、按请求 options 路由成为可能。

`CreateRouterRuntimeOptions` 是最重要的配置接口，关键字段包括：

- `id`：逻辑 provider id，例如 `moonshot`、`deepseek`、`lobehub`。
- `apiKey`：默认 key，构造实例时没有传 key 时使用。
- `routers`：路由配置，可以是静态数组，也可以是函数 `(options, runtimeContext) => RouterInstance[] | Promise<RouterInstance[]>`。
- `models`：模型列表获取方式，可以是函数，也可以带 `transformModel`。
- `chatCompletion`：聊天请求的 payload、stream、错误处理等适配钩子。
- `responses`：Responses API payload 处理钩子。
- `onRouteAttempt`：每次路由尝试成功或失败后的异步回调，用于审计、统计或上报。
- `shouldStopFallback`：失败后是否停止继续 fallback 的自定义判断。
- `createImage`、`createVideo`、`handleCreateVideoWebhook`：图像/视频能力相关适配。

内部还有几个关键类型：

- `RouterInstance`：一条路由，包含 `apiType`、可选 `baseURLPattern`、可选 `models`、`options`、可选自定义 `runtime`。
- `RouterOptionItem`：一次实际请求使用的 provider 初始化选项，可以在单个 option 上覆盖 `apiType`、`id`、`remark` 等。
- `RouteAttemptResult`：记录一次路由尝试的结果，包括 `apiType`、`channelId`、`durationMs`、`model`、`optionIndex`、`routerId`、`success`、`error`、`metadata`、`userId` 等。

## 上下游关系

上游接口来自 `../BaseAI` 的 `LobeRuntimeAI`。RouterRuntime 返回的 `UniformRuntime` 必须实现这套统一接口，因此它能被整个 `model-runtime` 包当成普通 provider runtime 使用。

向下游看，RouterRuntime 依赖各 provider runtime：

- `../../providers/openai`
- `../../providers/anthropic`
- `../../providers/azureai`
- `../../providers/azureOpenai`
- `../../providers/bedrock`
- `../../providers/google`
- `../../providers/vertexai`
- 以及 `deepseek`、`moonshot`、`qwen`、`xai`、`zhipu` 等 provider。

这些 runtime 通过 `baseRuntimeMap` 被统一索引。特殊的是 `vertexai`：`createRuntimeFromOption` 对它有单独分支，会把 `apiKey` 尝试解析为 JSON credentials，并通过 `LobeVertexAI.initFromVertexAI(vertexOptions)` 初始化，而不是直接 `new providerAI(...)`。

向上游调用方看，`packages/model-runtime/src/index.ts` 会 `export * from './core/RouterRuntime'`，因此包外可以拿到 `createRouterRuntime` 和相关类型。包内多个 provider 已经使用它创建自己的 runtime，例如：

- `providers/moonshot/index.ts`：根据 `sdkType` 或 `baseURLPattern` 在 Anthropic-compatible 和 OpenAI-compatible 之间切换。
- `providers/deepseek/index.ts`：同样支持 OpenAI / Anthropic 两种协议路由。
- `providers/lobehub/index.ts`：从 `@lobechat/business-model-runtime` 读取云端业务路由配置，再通过 `createRouterRuntime` 生成 `LobeHubAI`。
- `providers/newapi`、`providers/aihubmix`、`providers/zenmux`、`providers/opencodeZen`、`providers/opencodeCodingPlan` 也使用这个工厂。

根据当前片段推断，RouterRuntime 是“兼容聚合类 provider”的基础设施：当一个 provider 名称背后不再对应单一 API，而是对应多种协议、多条 channel 或动态业务配置时，就用它把复杂性收敛到统一 runtime 接口后面。依据是 `rg` 结果中多处 provider 都通过 `createRouterRuntime(params)` 导出自己的 `LobeXXXAI`。

## 运行/调用流程

一次典型的 `chat` 调用流程如下：

1. 调用方先通过 `createRouterRuntime(params)` 得到一个 `UniformRuntime` class。
2. 实例化时传入 constructor options，例如 `apiKey`、`baseURL`、`userId`、业务扩展字段等。
3. 构造函数只保存配置，并会对 `apiKey`、`baseURL` 做 `trim`；不会立即创建底层 provider runtime。
4. 调用 `runtime.chat(payload, options)`。
5. `chat` 内部调用 `runWithFallback(payload.model, requestHandler, options?.metadata)`。
6. `runWithFallback` 先调用 `resolveMatchedRouter(model)` 找路由。
7. `resolveMatchedRouter` 内部先 `resolveRouters(model)`，如果 `routers` 是函数，就用当前 constructor options 和 `{ model }` 动态生成路由；如果是数组就直接使用。
8. 路由选择优先级是：
   - 第一优先：如果 constructor options 里有 `baseURL`，并且某个 router 的 `baseURLPattern` 匹配它，则选这个 router。
   - 第二优先：如果 router 声明了非空 `models`，并且包含当前 `model`，则选这个 router。
   - 最后兜底：使用最后一个 router。
9. 选中 router 后，`normalizeRouterOptions` 把 `router.options` 统一变成数组。数组里的每一项就是一个可尝试 channel。
10. `runWithFallback` 按顺序遍历这些 option：
    - 调用 `createRuntimeFromOption` 创建底层 runtime。
    - 用 `requestHandler(runtime)` 执行实际请求，例如 `runtime.chat(payload, options)`。
    - 成功则调用 `onRouteAttempt` 上报成功并返回结果。
    - 失败则调用 `onRouteAttempt` 上报失败，然后判断是否继续 fallback。
11. 如果错误是 `isNonRetryableRequestError(error)` 认为的不可重试错误，会直接抛出，不继续尝试后续 option。
12. 如果配置了 `shouldStopFallback` 且返回 `true`，也会停止 fallback 并抛出当前错误。
13. 否则继续尝试下一个 option。
14. 所有 option 都失败后，抛出最后一次错误。

`models()` 的流程稍有不同：它也会先解析 routers，但匹配逻辑主要看 constructor 里的 `baseURL`；如果有 `baseURLPattern` 命中就选该 router，否则使用最后一个 router。然后只用该 router 的第一个 option 创建 runtime。如果 `modelsOption` 是函数，并且 runtime 上有 `client`，就把 `client` 传给 `modelsOption({ client })`，再经过 `postProcessModelList` 处理；否则直接调用底层 `runtime.models?.()`。

其他方法基本复用同一套 `runWithFallback`：

- `createImage(payload, options)` 按 `payload.model` 路由。
- `createVideo(payload, options)` 按 `payload.model` 路由。
- `generateObject(payload, options)` 按 `payload.model` 路由。
- `embeddings(payload, options)` 按 `payload.model` 路由。
- `textToSpeech(payload, options)` 按 `payload.model` 路由。
- `handleCreateVideoWebhook(payload)` 比较特殊，它从 `payload.body.model` 取模型，解析 routers 后固定使用第一个 router 和第一个 option。

测试文件 `createRuntime.test.ts` 覆盖了这些行为：空 routers 延迟到使用时报 `NoAvailableProvider`、constructor options 合并、动态 routers、异步 routers、fallback、不可重试错误、`shouldStopFallback`、option 级别 `apiType` 覆盖、`baseURLPattern` 优先于 models、模型不匹配时使用最后 router、metadata 传给 `onRouteAttempt`、默认 apiKey、嵌套路由 runtime id 继承等。

## 小白阅读顺序

1. 先读 `packages/model-runtime/src/core/BaseAI.ts`  
   重点看 `LobeRuntimeAI` 接口，理解整个 model-runtime 希望 provider 暴露哪些能力。RouterRuntime 的目标就是“伪装成”这个接口。

2. 再读 `packages/model-runtime/src/core/RouterRuntime/index.ts`  
   这个文件很短，可以先知道目录对外导出了什么：`createRouterRuntime`、配置类型、运行时类型。

3. 接着读 `apiTypes.ts` 和 `baseRuntimeMap.ts`  
   这里能建立“`apiType` 字符串如何映射到底层 provider class”的直觉。读完后会明白 `apiType: 'anthropic'` 不是普通标签，而是能决定实例化哪个 runtime。

4. 重点读 `createRuntime.ts` 的类型定义部分  
   先看 `RouterOptionItem`、`RouterInstance`、`Routers`、`CreateRouterRuntimeOptions`、`RouteAttemptResult`。这些类型就是 RouterRuntime 的配置语言。

5. 再读 `createRouterRuntime` 里的私有方法  
   建议顺序是：
   - `resolveRouters`
   - `resolveMatchedRouter`
   - `normalizeRouterOptions`
   - `createRuntimeFromOption`
   - `runWithFallback`

   这五个方法串起来就是完整路由引擎。

6. 最后读公开方法  
   看 `chat` 如何包装错误处理，`models` 为什么单独处理，其他方法如何复用 `runWithFallback`。

7. 对照实际 provider  
   推荐看 `providers/moonshot/index.ts` 和 `providers/deepseek/index.ts`。这两个例子最适合理解“同一个 provider 根据 `sdkType` 或 `baseURLPattern` 切换 OpenAI-compatible / Anthropic-compatible runtime”的设计。

8. 用测试文件补边界  
   `createRuntime.test.ts` 很长，但测试名称本身已经是行为清单。小白不一定要逐行读完，可以先按 `describe` 分组看：initialization、chat、models、dynamic routers、fallback、router matching、createImage、createVideo、constructor options。

## 常见误区

1. 不要以为 `createRouterRuntime` 会立刻创建所有 provider runtime。  
   它是延迟创建的。constructor 只保存 `_options`、`_routers`、`_params`、`_id`；真正的底层 runtime 在 `chat`、`models` 等方法调用时才由 `createRuntimeFromOption` 创建。

2. 不要把 `routers` 理解成只能静态配置。  
   `routers` 可以是函数，也可以是 async 函数。它能根据 constructor options 和当前 `model` 动态返回不同路由。这对云端动态 channel、按用户配置、按模型选择供应商很重要。

3. 不要忽略路由匹配优先级。  
   `baseURLPattern` 的优先级高于 `models`。如果传入的 `baseURL` 命中了某个 router，即使模型也能匹配别的 router，也会先走 `baseURLPattern` 命中的那个。

4. 不要以为第一个 router 是默认兜底。  
   在 `resolveMatchedRouter` 里，如果没有 `baseURLPattern` 和 `models` 命中，兜底使用的是最后一个 router。很多配置会把“默认协议”放在最后，这一点读 provider 配置时要特别注意。

5. 不要把 router 的 `options` 和 constructor options 看成互斥。  
   实际创建 runtime 时会合并：
   `this._params`、`this._options`、`optionOverrides`。后面的 option override 可以覆盖前面的配置。也就是说 constructor 传入的 `apiKey`、`baseURL` 可能会被具体 channel option 覆盖。

6. 不要以为 fallback 会重试所有错误。  
   `isNonRetryableRequestError(error)` 判断为不可重试的错误会立即抛出；`shouldStopFallback` 返回 `true` 也会停止。测试里覆盖了上下文长度超限、请求 payload 被上游拒绝、schema 无效、不支持的模型参数等不应继续 fallback 的情况。

7. 不要以为 option 只能继承 router 的 `apiType`。  
   `RouterOptionItem` 自己也可以带 `apiType`。这意味着同一个 router 的 fallback option 可以切换到底层不同 provider 类型，例如第一路走 OpenAI-compatible，第二路走 Anthropic-compatible。

8. 不要把 `models()` 和 `chat()` 的路由逻辑完全等同。  
   `chat()` 按具体 `payload.model` 匹配，并执行 fallback；`models()` 更偏向选择一个用于发现模型列表的 runtime，主要根据 `baseURLPattern` 或最后 router 来选，并只使用第一个 option。

9. 不要把 `id` 混淆。  
   `CreateRouterRuntimeOptions.id` 是逻辑 provider id；`RouterInstance.id` 是路由 id；`RouterOptionItem.id` 在运行中会变成 `channelId`；底层 runtime 初始化时还会收到 `{ id: this._id }`。读 `onRouteAttempt` 日志或统计时要区分 `providerId`、`routerId`、`channelId`。

10. 不要把 Vertex AI 当普通 API key provider。  
    `vertexai` 有特殊初始化路径：它会尝试把 `apiKey` 当 JSON credentials 解析，并构造 `GoogleGenAIOptions`，最终走 `LobeVertexAI.initFromVertexAI`。这和普通 `new providerAI(options)` 不同。
