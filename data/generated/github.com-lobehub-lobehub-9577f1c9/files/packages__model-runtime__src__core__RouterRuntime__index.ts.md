# 文件：packages/model-runtime/src/core/RouterRuntime/index.ts

## 它负责什么

`packages/model-runtime/src/core/RouterRuntime/index.ts` 是 `RouterRuntime` 模块的公共入口文件，也就是外部代码导入路由运行时能力时最常经过的门面。

它本身不实现复杂业务逻辑，核心职责有三个：

1. 定义并导出 `RuntimeItem` 类型，用来描述一个可被路由系统持有的运行时条目。
2. 从 `./createRuntime` 重新导出关键类型：
   - `CreateRouterRuntimeOptions`
   - `RouteAttemptResult`
   - `UniformRuntime`
3. 从 `./createRuntime` 重新导出核心工厂函数：
   - `createRouterRuntime`

换句话说，这个文件是“类型与工厂函数的出口”，真正的路由匹配、fallback、provider runtime 创建、chat/image/video/embedding 调用等逻辑都在同目录的 `createRuntime.ts` 中。

它的内容很短：

```ts
import type { LobeRuntimeAI } from '../BaseAI';

export interface RuntimeItem {
  id: string;
  models?: string[] | (() => Promise<string[]>);
  runtime: LobeRuntimeAI;
}

export type { CreateRouterRuntimeOptions, RouteAttemptResult, UniformRuntime } from './createRuntime';
export { createRouterRuntime } from './createRuntime';
```

## 关键组成

`LobeRuntimeAI` 来自 `../BaseAI`，是整个 model runtime 层的统一能力接口。它描述一个模型 provider runtime 可能支持的方法，例如：

- `chat`
- `models`
- `createImage`
- `createVideo`
- `embeddings`
- `generateObject`
- `textToSpeech`
- `handleCreateVideoWebhook`
- `pullModel`

`RouterRuntime/index.ts` 里的 `RuntimeItem.runtime` 就要求符合这个接口。也就是说，不管底层是 OpenAI、Anthropic、Google、DeepSeek、Qwen、Vertex AI，最终都要表现成 `LobeRuntimeAI` 这种统一形态，才能被上层用同一种方式调用。

`RuntimeItem` 是一个运行时条目描述：

```ts
export interface RuntimeItem {
  id: string;
  models?: string[] | (() => Promise<string[]>);
  runtime: LobeRuntimeAI;
}
```

字段含义：

- `id`：运行时条目的标识，通常可理解为 provider 或 channel 的 id。
- `models`：这个 runtime 支持的模型列表，可以是静态字符串数组，也可以是异步函数。异步函数适合从远端 API 拉取模型列表。
- `runtime`：真正执行请求的 runtime 实例，必须实现 `LobeRuntimeAI` 接口。

根据当前片段推断，`RuntimeItem` 更像是早期或对外扩展用的通用描述类型；在当前仓库内通过 `rg` 查询，直接使用它的地方很少，主要是从该入口导出，供包外或未来代码使用。

`CreateRouterRuntimeOptions` 是创建路由运行时的配置类型，真实定义在 `createRuntime.ts`。它包含：

- `id`：provider 标识。
- `routers`：静态或动态路由配置。
- `apiKey`：默认 API key。
- `constructorOptions`、`defaultHeaders`、`customClient` 等底层 provider 初始化参数。
- `models`：模型列表获取与转换逻辑。
- `chatCompletion`：chat payload、stream、error 处理扩展点。
- `responses`：Responses API 相关 payload 处理。
- `createImage`、`createVideo`、`handleCreateVideoWebhook` 等能力扩展。
- `onRouteAttempt`：每次路由尝试后的观测回调。
- `shouldStopFallback`：失败后是否停止 fallback 的判断钩子。

`RouteAttemptResult` 描述一次路由尝试的结果，包含：

- `apiType`
- `channelId`
- `durationMs`
- `error`
- `metadata`
- `model`
- `optionIndex`
- `providerId`
- `remark`
- `routerId`
- `success`
- `userId`

这个类型服务于 `onRouteAttempt`，用于记录某个模型请求具体走了哪个 router、哪个 channel、耗时多少、是否成功、失败错误是什么。

`UniformRuntime` 是 `createRouterRuntime` 返回类的实例类型：

```ts
export type UniformRuntime = InstanceType<ReturnType<typeof createRouterRuntime>>;
```

它代表被路由包装后的统一 runtime 实例。上层不需要知道底层到底实例化了哪个 provider，只要调用 `chat`、`models`、`embeddings` 等方法即可。

`createRouterRuntime` 是这个模块最重要的导出。它接收 `CreateRouterRuntimeOptions`，返回一个实现 `LobeRuntimeAI` 的 class。这个 class 在 `createRuntime.ts` 中命名为 `UniformRuntime`，负责在每次请求时按模型、baseURL、路由配置选择真正的 provider runtime。

## 上下游关系

上游是各 provider 的实现文件。多个 provider 会从这个入口导入 `createRouterRuntime` 或 `CreateRouterRuntimeOptions`，然后把自己的路由配置包装成统一 runtime。例如查询到的调用方包括：

- `packages/model-runtime/src/providers/deepseek/index.ts`
- `packages/model-runtime/src/providers/moonshot/index.ts`
- `packages/model-runtime/src/providers/aihubmix/index.ts`
- `packages/model-runtime/src/providers/newapi/index.ts`
- `packages/model-runtime/src/providers/zenmux/index.ts`
- `packages/model-runtime/src/providers/lobehub/index.ts`
- `packages/model-runtime/src/providers/opencodeZen/index.ts`
- `packages/model-runtime/src/providers/opencodeCodingPlan/index.ts`

典型形态是：

```ts
import type { CreateRouterRuntimeOptions } from '../../core/RouterRuntime';
import { createRouterRuntime } from '../../core/RouterRuntime';

export const params: CreateRouterRuntimeOptions = {
  // provider-specific router config
};

export const LobeDeepSeekAI = createRouterRuntime(params);
```

也就是说，provider 文件不一定直接写一个完整 class，而是通过 `createRouterRuntime(params)` 得到一个统一 runtime class。

下游是更底层的 provider runtime class。`createRuntime.ts` 会根据路由里的 `apiType` 选择具体 runtime。这个映射在 `baseRuntimeMap.ts` 中：

```ts
export const baseRuntimeMap = {
  anthropic: LobeAnthropicAI,
  azure: LobeAzureAI,
  azureopenai: LobeAzureOpenAI,
  bedrock: LobeBedrockAI,
  cloudflare: LobeCloudflareAI,
  deepseek: LobeDeepSeekAI,
  fal: LobeFalAI,
  google: LobeGoogleAI,
  minimax: LobeMinimaxAI,
  moonshot: LobeMoonshotAI,
  openai: LobeOpenAI,
  qwen: LobeQwenAI,
  vertexai: LobeVertexAI,
  volcengine: LobeVolcengineAI,
  xai: LobeXAI,
  xiaomimimo: LobeXiaomiMiMoAI,
  zhipu: LobeZhipuAI,
}
```

对应的 `ApiType` 定义在 `apiTypes.ts`，限定了路由系统支持哪些 provider 类型。

从包级关系看，`packages/model-runtime/src/index.ts` 会再次导出：

```ts
export * from './core/RouterRuntime';
```

所以包外消费者可以通过 model-runtime 的主入口间接拿到 `createRouterRuntime`、`RuntimeItem` 和相关类型。

`packages/model-runtime/src/providers/lobehub/index.ts` 还会导入 `@lobechat/business-model-runtime` 中的 `lobehubRouterRuntimeOptions`，再交给 `createRouterRuntime`。不过当前片段里 `packages/business/model-runtime/src/router-runtime-options.ts` 的 `routers` 返回空数组，像是业务包里的占位或构建时注入点；如果实际运行时没有替换，`resolveRouters` 会抛出 `NoAvailableProvider`。

## 运行/调用流程

从 `index.ts` 看不出运行流程，因为它只做转发。实际流程要顺着 `createRouterRuntime` 看。

第一步，provider 调用 `createRouterRuntime(params)`。

例如某个 provider 传入：

```ts
{
  id: 'deepseek',
  routers: [...],
  chatCompletion: {...},
  models: {...}
}
```

`createRouterRuntime` 会返回一个 class：

```ts
class UniformRuntime implements LobeRuntimeAI
```

这个 class 实现了统一接口，所以可以被上层当成普通 provider runtime 使用。

第二步，上层实例化 runtime。

```ts
const runtime = new LobeDeepSeekAI({
  apiKey,
  baseURL,
  userId,
});
```

构造函数会合并初始化参数：

- `options.apiKey?.trim() || DEFAULT_API_KEY`
- `options.baseURL?.trim()`
- 保存 `routers`
- 保存其他配置参数
- 保存 `_id`

它不会立即创建具体 provider runtime，而是延迟到真正调用 `chat`、`models` 等方法时再创建。

第三步，调用 `chat`、`createImage`、`generateObject` 等方法。

以 `chat` 为例：

```ts
async chat(payload, options) {
  return await this.runWithFallback(
    payload.model,
    (runtime) => runtime.chat!(payload, options),
    options?.metadata,
  );
}
```

核心进入 `runWithFallback`。

第四步，解析 routers。

`resolveRouters(model)` 支持两种配置：

- 静态数组：`RouterInstance[]`
- 动态函数：`(options, { model }) => RouterInstance[] | Promise<RouterInstance[]>`

动态函数可以根据当前模型、用户配置、环境变量等生成不同 router 列表。

如果结果为空，会抛出 `AgentRuntimeErrorType.NoAvailableProvider`。

第五步，匹配 router。

`resolveMatchedRouter(model)` 的优先级是：

1. 如果用户配置了 `baseURL`，先用 `baseURLPattern` 匹配。
2. 如果 router 声明了 `models`，再按模型名匹配。
3. 如果都没有匹配到，使用最后一个 router 作为 fallback router。

这个逻辑很关键：它说明 `routers` 数组的顺序不只是普通列表，最后一个元素还承担默认兜底角色。

第六步，展开 router options。

每个 router 的 `options` 可以是单个对象，也可以是数组：

```ts
options: RouterOptionItem | RouterOptionItem[]
```

如果是数组，`runWithFallback` 会按顺序尝试。每个 option 可以理解成一个 channel 或一个 provider 配置，例如不同 API key、不同 baseURL、不同区域、不同 `apiType`。

第七步，创建具体 runtime。

`createRuntimeFromOption(router, optionItem)` 会合并参数：

```ts
const finalOptions = {
  ...this._params,
  ...this._options,
  ...optionOverrides,
};
```

优先级大致是：工厂参数 < 实例化参数 < router option 覆盖项。

然后确定最终 `apiType`：

```ts
const resolvedApiType = optionApiType ?? router.apiType;
```

如果 option 自己带了 `apiType`，它可以覆盖 router 的 `apiType`。这使 fallback 不一定只能落在同一种 provider 上。例如一个 router 可以主走 OpenAI-compatible，失败后切到 Anthropic-compatible 或其他 provider。

普通 provider 会通过 `baseRuntimeMap` 找到 class：

```ts
const providerAI =
  resolvedApiType === router.apiType
    ? (router.runtime ?? baseRuntimeMap[resolvedApiType] ?? LobeOpenAI)
    : (baseRuntimeMap[resolvedApiType] ?? LobeOpenAI);

const runtime = new providerAI({ ...finalOptions, id: this._id });
```

特殊情况是 `vertexai`。它会把 `apiKey` 当作可能的 JSON credentials 解析，并用 `LobeVertexAI.initFromVertexAI(vertexOptions)` 创建 runtime。这是因为 Vertex AI 的认证方式和普通 API key provider 不一样。

第八步，执行请求并处理 fallback。

`runWithFallback` 对每个 option 执行：

```ts
const result = await requestHandler(runtime);
```

成功时：

- 调用 `onRouteAttempt`，记录成功结果。
- 返回结果。
- 如果是后续 attempt 成功，会记录 fallback success 日志。

失败时：

- 保存 `lastError`。
- 调用 `onRouteAttempt`，记录失败结果。
- 如果 `isNonRetryableRequestError(error)` 为真，直接抛出，不继续 fallback。
- 调用 `shouldStopFallback`，如果返回 true，也停止 fallback。
- 否则尝试下一个 option。
- 全部失败后抛出最后一个错误。

第九步，`models()` 的流程略有不同。

`models()` 也会解析 routers，但它不按模型匹配，因为此时没有具体模型请求。它的逻辑是：

- 如果有 `baseURL`，优先按 `baseURLPattern` 找 router。
- 否则使用最后一个 router。
- 只取第一个 router option 创建 runtime。
- 如果 `modelsOption` 是函数，并且 runtime 上有 `client`，则调用 `modelsOption({ client })`，再 `postProcessModelList`。
- 否则调用底层 `runtime.models?.()`。

所以 `models()` 是模型发现流程，不走多 channel fallback。

## 小白阅读顺序

建议不要从 `createRuntime.ts` 一口气硬读，因为这个文件逻辑比较密。可以按下面顺序：

1. 先读 `packages/model-runtime/src/core/RouterRuntime/index.ts`  
   先明确：这里是公共出口，不是真正实现。记住它导出了 `RuntimeItem`、`CreateRouterRuntimeOptions`、`RouteAttemptResult`、`UniformRuntime`、`createRouterRuntime`。

2. 再读 `packages/model-runtime/src/core/BaseAI.ts`  
   理解 `LobeRuntimeAI` 是什么。这个接口是统一抽象：不管底层 provider 多么不同，上层最终都通过这些方法调用模型能力。

3. 再读 `packages/model-runtime/src/core/RouterRuntime/apiTypes.ts`  
   看支持哪些 `apiType`。这是路由系统识别 provider 类型的枚举联合类型。

4. 再读 `packages/model-runtime/src/core/RouterRuntime/baseRuntimeMap.ts`  
   理解 `apiType` 如何映射到真实 provider class。例如 `openai` 对应 `LobeOpenAI`，`anthropic` 对应 `LobeAnthropicAI`，`vertexai` 对应 `LobeVertexAI`。

5. 再读 `packages/model-runtime/src/core/RouterRuntime/createRuntime.ts` 的类型区  
   重点看 `CreateRouterRuntimeOptions`、`RouterInstance`、`RouterOptionItem`、`RouteAttemptResult`。先把配置结构看懂，后面的流程才容易理解。

6. 再读 `createRouterRuntime` 的构造函数  
   重点看它如何保存 `_options`、`_routers`、`_params`、`_id`，并注意它不会在构造时立即创建底层 runtime。

7. 然后读 `resolveRouters` 和 `resolveMatchedRouter`  
   这是“选择哪个 router”的逻辑。记住匹配优先级：`baseURLPattern` > `models` > 最后一个 router。

8. 再读 `createRuntimeFromOption`  
   这是“选择哪个 provider class 并实例化”的逻辑。这里要特别注意 option 可以覆盖 `apiType`，以及 `vertexai` 的特殊认证处理。

9. 最后读 `runWithFallback`  
   这是运行时最核心的控制流：按 option 顺序尝试，失败后判断是否继续 fallback，成功后返回。

10. 再抽一个 provider 看实际配置  
   例如 `packages/model-runtime/src/providers/deepseek/index.ts`。它会让你看到 provider 如何通过 `CreateRouterRuntimeOptions` 把自己的 OpenAI-compatible、Anthropic-compatible 等能力接到统一路由运行时上。

## 常见误区

误区一：以为 `index.ts` 实现了路由逻辑。  
实际上它只是入口文件。真正逻辑在 `createRuntime.ts`。阅读这个文件时要把它当成“API 门面”，不是业务实现。

误区二：以为 `RuntimeItem` 就是当前 `createRouterRuntime` 内部使用的 router item。  
不是。当前 `createRuntime.ts` 内部使用的是 `RouterInstance` 和 `RouterOptionItem`。`RuntimeItem` 只定义在 `index.ts` 并从模块导出。根据当前片段推断，它更偏向外部扩展或历史兼容类型。

误区三：以为一个 provider runtime 只会对应一个底层 provider。  
`RouterRuntime` 的设计恰恰允许一个统一 provider 包装多个底层 provider。`RouterOptionItem` 可以带 `apiType`，从而在 fallback 时切换到底层不同 runtime。

误区四：以为 fallback 是按 router 数组逐个尝试。  
不是。请求会先通过 `resolveMatchedRouter` 选中一个 router，然后在这个 router 的 `options` 数组里逐个尝试。router 数组负责“选路”，option 数组负责“fallback”。

误区五：以为模型匹配失败就报错。  
不会。`resolveMatchedRouter` 在 `baseURLPattern` 和 `models` 都没有命中时，会使用最后一个 router 作为默认兜底。因此 routers 的顺序很重要，最后一个 router 通常承担默认路由角色。

误区六：以为所有错误都会触发 fallback。  
不会。`isNonRetryableRequestError(error)` 判断为不可重试时会直接抛出；`shouldStopFallback` 返回 true 时也会停止 fallback。这可以避免 API key 错误、参数错误等无意义重试。

误区七：以为 `models()` 和 `chat()` 路由方式完全一样。  
不一样。`chat()` 根据具体 `payload.model` 匹配并执行 fallback；`models()` 没有具体模型请求，它主要根据 `baseURLPattern` 或最后一个 router 创建 runtime，并只取第一个 option。

误区八：忽略 `vertexai` 的特殊分支。  
大多数 provider 都通过 `new providerAI(options)` 创建，但 `vertexai` 会解析 credentials，并调用 `LobeVertexAI.initFromVertexAI(vertexOptions)`。这是因为它的认证模型不同于普通 API key provider。

误区九：以为 `onRouteAttempt` 会阻塞主流程。  
代码里调用后接了 `.catch(...)`，没有 `await`。它更像异步观测回调，失败只记录 debug 日志，不影响请求主结果。

误区十：以为 `createRouterRuntime` 返回的是实例。  
它返回的是 class。provider 文件通常会这样导出：

```ts
export const LobeDeepSeekAI = createRouterRuntime(params);
```

之后上层再 `new LobeDeepSeekAI(options)` 得到实例。
