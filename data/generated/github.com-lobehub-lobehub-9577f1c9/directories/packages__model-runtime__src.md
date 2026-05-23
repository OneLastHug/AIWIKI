# 目录：packages/model-runtime/src

## 它负责什么

根据当前片段推断，这个目录是 `@lobechat/model-runtime` 的核心实现层，职责不是“某一个模型供应商的 SDK”，而是把大量模型供应商接入统一成一套可调用的运行时接口。它一边维护通用能力，比如错误归一、流式消费、模型参数裁剪、价格与上下文窗口推导；一边为不同 provider 提供适配器，让上层可以用同一种 `chat`、`embeddings`、`generateObject`、`createImage`、`createVideo` 之类的调用方式工作。

从 `packages/model-runtime/package.json` 看，这个包的对外入口就是 `src/index.ts`，说明这里是一个典型的“barrel + runtime core + provider adapters”结构。

## 直接子目录地图

`src` 下的直接子目录主要是这 6 类：

- `const`：模型与常量定义，偏静态数据和能力标记。
- `core`：运行时核心层，负责调度、兼容层和上下文构造。
- `helpers`：辅助封装，通常是跨 provider 复用的轻量方法。
- `providers`：各家模型服务的适配实现，是这个目录体量最大的部分。
- `types`：统一的请求、响应、错误、图像、视频等类型定义。
- `utils`：通用工具层，覆盖错误判断、流处理、JSON 解析、URL 处理、模型解析等。

其中 `core` 下面还能看到这些功能块：

- `RouterRuntime`
- `anthropicCompatibleFactory`
- `openaiCompatibleFactory`
- `contextBuilders`
- `streams`
- `usageConverters`

这说明核心不是单点实现，而是围绕“兼容不同协议形态”的一组基础设施。

`providers` 目录非常大，按服务商或能力域拆分，例如 `openai`、`anthropic`、`google`、`azureOpenai`、`bedrock`、`qwen`、`volcengine`、`comfyui`、`stepfun`、`vertexai` 等。根据当前片段推断，这里的组织方式是“每个 provider 一个目录，目录内再按模型能力继续拆分”，例如图像、视频、认证或特定工作流。

## 关键入口

最重要的对外入口是 `src/index.ts`。它不是业务逻辑文件，而是统一出口，集中导出：

- `ModelRuntime`
- `createOpenAICompatibleRuntime`
- `BaseAI`
- `RouterRuntime`
- `usageConverters`
- `helpers`
- 各个 provider 的 `LobeXXXAI` 类
- 通用工具函数和类型

这意味着上层代码通常不直接深入某个 provider 文件，而是从 `@lobechat/model-runtime` 直接拿到所需 runtime 类。

第二个关键入口是 `src/core/ModelRuntime.ts`。它是运行时的编排层：先检查 provider 是否支持对应能力，再执行 hook，再调用底层 runtime，最后处理错误和收尾回调。这里还能看到 `beforeChat`、`onChatError`、`onChatFinal`、`beforeEmbeddings`、`beforeGenerateObject` 等生命周期钩子，说明它承担的是“统一生命周期管理”而不是协议拼装本身。

第三个典型入口是具体 provider 的 `index.ts`，例如 `src/providers/openai/index.ts`。这个文件展示了 provider 的典型形态：定义参数、处理 payload、决定是否切换 OpenAI 的 `responses` / `chat completions` 模式，然后通过 `createOpenAICompatibleRuntime` 生成最终 runtime。其他 provider 大体也会沿着类似路径做适配。

## 主流程位置

主流程可以理解成三层：

1. 上层调用从 `src/index.ts` 进入，拿到 `ModelRuntime` 或具体 provider runtime。
2. `ModelRuntime` 负责生命周期控制、hook 注入、计时埋点和异常统一处理。
3. 具体 provider 目录里的 `index.ts` 负责把上层通用请求翻译成该服务商可理解的 payload，再交给 `core/openaiCompatibleFactory`、`core/anthropicCompatibleFactory` 或各自专用逻辑。

就 `openai` 这条线看，主流程位置很清晰：`src/providers/openai/index.ts` 先根据模型名和能力位决定走哪种 API 形态，再由 `src/core/openaiCompatibleFactory` 生成 runtime，最终由 `ModelRuntime` 统一包裹调用。这种结构让“协议差异”留在 provider 层，“运行期控制”留在 core 层。

另外，`src/utils/modelParse.ts`、`src/utils/postProcessModelList.ts`、`src/utils/getModelPricing.ts` 这类文件，通常会插入在“模型列表加载、能力识别、展示信息补全”这些流程节点上，不属于主调度，但属于主链路的关键支撑。

## 推荐阅读顺序

1. 先看 `src/index.ts`，建立这个包的对外面貌。
2. 再看 `src/core/ModelRuntime.ts`，理解统一调度、hook 和错误处理。
3. 接着看 `src/core/openaiCompatibleFactory` 和 `src/core/anthropicCompatibleFactory`，理解兼容层是怎么搭起来的。
4. 然后选一个最典型的 provider，比如 `src/providers/openai/index.ts`，看 payload 是如何分流的。
5. 最后回到 `src/utils/` 和 `src/types/`，补齐错误、流、模型解析和接口结构的细节。

## 常见误区

- 把 `src/index.ts` 当成业务实现。它实际上是公共出口，逻辑密度很低。
- 只盯某一个 provider，忽略 `core`。这个包的真正价值在于统一运行时和兼容层，而不是单个供应商适配。
- 以为 `ModelRuntime` 直接负责协议转换。它更像编排器，真正的 payload 适配大多在 provider 或 factory 里。
- 忽略 `utils`。这里很多函数看起来只是辅助，但实际上承载了错误分类、模型参数裁剪、流式消费、价格和上下文推导，直接影响主流程稳定性。
- 只看源码不看测试。这个目录里大量 `*.test.ts` 和 `__tests__` 与实现并排，说明它对兼容性和回归非常敏感。
